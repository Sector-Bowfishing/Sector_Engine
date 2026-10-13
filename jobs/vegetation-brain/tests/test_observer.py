from datetime import date

import numpy as np
import pytest

from helpers import REF, cells_for, days, lake_mask, patch, scene, scene_arrays
from vegetation_brain import contract as C
from vegetation_brain import observer as O

BED = patch((30, 60), (30, 60))     # a 30x30 pixel (900 m x 900 m... 300 m x 300 m) interior bed


# ---------------------------------------------------------------- reflectance conventions
def test_offset_convention_is_per_collection():
    dn = np.array([[1100, 0, 65535]], dtype="uint16")
    c1 = O.reflectance(dn, "sentinel-2-c1-l2a")
    l2 = O.reflectance(dn, "sentinel-2-l2a")
    assert c1[0, 0] == pytest.approx(0.01, abs=1e-6)
    assert l2[0, 0] == pytest.approx(0.11, abs=1e-6)         # NOT interchangeable: applying -0.1 twice was the research error
    assert np.isnan(c1[0, 1]) and np.isnan(c1[0, 2])
    with pytest.raises(ValueError):
        O.reflectance(dn, "landsat")


def test_offset_check_flags_a_wrong_convention():
    O.check_offset_convention(1050, "sentinel-2-c1-l2a")
    with pytest.raises(ValueError):
        O.check_offset_convention(100, "sentinel-2-c1-l2a")
    with pytest.raises(ValueError):
        O.check_offset_convention(1050, "sentinel-2-l2a")


# ---------------------------------------------------------------- surface class
def test_plant_bed_is_plant_and_open_water_is_not():
    c = cells_for(plant=BED)
    assert (c.state == O.PLANT).sum() > 0
    inside = c.state[13:16, 13:16]                            # cells far from the bed
    assert (inside == O.NO_PLANT).all()
    assert c.plant_fraction[np.nonzero(c.state == O.PLANT)].min() >= 0.5


def test_single_noisy_pixel_never_makes_a_cell_vegetation():
    one = np.zeros((100, 100), bool)
    one[42, 42] = True
    c = cells_for(plant=one)
    assert (c.state == O.PLANT).sum() == 0                   # 1/25 pixels < 0.5 plant fraction


def test_dark_water_ratio_noise_is_not_plant():
    # red 0.004, nir 0.008: NDVI = 0.33 >= 0.30 but both are rounding-noise dark water
    scl, red, nir, swir = scene_arrays(nir_water=0.008, red_water=0.004)
    f = O.scene_fields(scl, red, nir, swir, lake_mask())
    assert f.plant.sum() == 0
    assert f.dark_artifact.sum() > 0
    c = O.to_cells(f)
    assert (c.state == O.PLANT).sum() == 0


def test_submerged_never_appears_as_a_class():
    # the observer only has PLANT/NO_PLANT/UNKNOWN; there is no submerged code at all
    assert set(O.REASON_CODES) == set(C.REFUSALS)
    assert {O.UNKNOWN, O.NO_PLANT, O.PLANT, O.OUTSIDE} == {0, 1, 2, -1}


# ---------------------------------------------------------------- refusals
def test_cloud_makes_unknown_not_no_plant():
    cloud = patch((20, 80), (20, 50))
    c = cells_for(cloud=cloud)
    assert (c.state[c.interior] == O.NO_PLANT).sum() < c.interior.sum()
    cloudy = c.interior & (c.state == O.UNKNOWN)
    assert cloudy.sum() > 0
    reasons = {O.REASON_NAMES[int(r)] for r in c.reason[cloudy]}
    assert reasons <= {"CLOUD", "INSUFFICIENT_VALID_PIXELS"} and "CLOUD" in reasons


def test_shadow_haze_and_dark_have_distinct_reasons():
    sh = cells_for(shadow=patch((20, 40), (20, 40)))
    assert O.REASON_CODES["SHADOW"] in set(sh.reason[sh.interior & (sh.state == O.UNKNOWN)])
    scl, red, nir, swir = scene_arrays(haze=patch((20, 40), (20, 40)))
    hz = O.to_cells(O.scene_fields(scl, red, nir, swir, lake_mask(), haze_swir=0.02, haze_standoff_px=10))
    unk = hz.interior & (hz.state == O.UNKNOWN)
    assert unk.sum() > 0 and O.REASON_CODES["HAZE"] in set(hz.reason[unk])


def test_shore_adjacent_cells_are_never_claimed():
    edge_bed = patch((10, 25), (10, 25))                    # vegetation touching the lake edge
    c = cells_for(plant=edge_bed)
    shore = c.eligible & ~c.interior
    assert shore.sum() > 0
    assert (c.state[shore] == O.UNKNOWN).all()
    assert (c.reason[shore] == O.REASON_CODES["SHORE_ADJACENT"]).all()


def test_glare_only_when_wind_brain_says_disturbed():
    scl, red, nir, swir = scene_arrays()
    swir[30:50, 30:50] = 0.015                              # bright-ish water: below the haze limit, above the disturbed-surface limit
    f = O.scene_fields(scl, red, nir, swir, lake_mask())
    # not flagged as glare by itself (haze logic handles it); glare needs the Wind flag
    assert not f.blocked["GLARE"].any()
    f2 = O.apply_surface_disturbance(f, swir, True)
    assert f2.blocked["GLARE"].any()
    c = O.to_cells(f2)
    assert O.REASON_CODES["GLARE"] in set(c.reason[c.interior & (c.state == O.UNKNOWN)])


def test_insufficient_valid_pixels_when_cell_mostly_unseen():
    scl, red, nir, swir = scene_arrays()
    nan = patch((40, 60), (40, 60))
    red[nan] = np.nan
    c = O.to_cells(O.scene_fields(scl, red, nir, swir, lake_mask()))
    assert c.state[9, 9] == O.UNKNOWN and c.reason[9, 9] == O.REASON_CODES["INSUFFICIENT_VALID_PIXELS"]


# ---------------------------------------------------------------- pass acceptance
def test_pass_acceptance_rejects_a_mostly_cloudy_scene():
    good = scene("g", days(0), plant=BED)
    bad = scene("b", days(1), plant=BED, cloud=patch((10, 90), (10, 70)))
    assert O.accept_pass(good) and not O.accept_pass(bad)


def test_accepted_pass_fallback_flags_low_coverage():
    s = scene("s", days(0), plant=BED, cloud=patch((10, 90), (10, 60)))
    cov = s.cells.coverage()
    assert C.PASS_FALLBACK_COVERAGE <= cov < C.PASS_MIN_COVERAGE, cov
    obs = O.observe([s], REF, mode="A")
    assert obs.low_coverage_fallback and obs.evidence_kind == "SATELLITE_ACCEPTED_PASS"


def test_no_scene_is_empty_observation_and_unknown_presence():
    obs = O.observe([], REF, mode="P")
    assert obs.evidence_kind == "NONE"
    assert O.presence(obs)[0] == "UNKNOWN"


def test_scene_outside_window_is_ignored():
    obs = O.observe([scene("old", days(-40), plant=BED)], REF, mode="P")
    assert obs.evidence_kind == "NONE"


# ---------------------------------------------------------------- persistence
def test_persistence_median_removes_a_one_scene_false_positive():
    noisy = patch((60, 75), (60, 75))
    scenes = [scene("a", days(-5), plant=BED), scene("b", days(0), plant=BED), scene("c", days(5), plant=BED | noisy)]
    # 'c' has an extra bed that exists in only one of three scenes
    obs = O.observe(scenes, REF, mode="P")
    assert obs.evidence_kind == "SATELLITE_PERSISTENCE" and obs.persistence == "MEDIAN_OF_ACCEPTED"
    single = O.observe([scenes[2]], REF, mode="A")
    assert obs.plant_cells < single.plant_cells                # the transient patch is not in the median


def test_persistence_needs_three_accepted_scenes_else_declared_insufficient():
    obs = O.observe([scene("a", days(-5), plant=BED), scene("b", days(2), plant=BED)], REF, mode="P")
    assert obs.evidence_kind == "SATELLITE_ACCEPTED_PASS" and obs.persistence == "INSUFFICIENT"
    assert any("persistence needs" in n for n in obs.notes)


def test_max_composite_is_not_available():
    for m in ("max", "M", "second_highest"):
        with pytest.raises(ValueError):
            O.observe([], REF, mode=m)
    assert "max" in C.FORBIDDEN_COMPOSITES


def test_isolated_single_cells_are_dropped_and_counted():
    one_cell = patch((50, 55), (50, 55))
    obs = O.observe([scene("a", days(0), plant=one_cell)], REF, mode="A")
    assert obs.plant_cells == 0 and obs.isolated_dropped == 1


# ---------------------------------------------------------------- presence semantics
def test_not_observed_requires_a_real_look():
    clear = O.observe([scene("a", days(0))], REF, mode="A")
    assert O.presence(clear)[0] == "NOT_OBSERVED"
    cloudy = O.observe([scene("c", days(0), cloud=patch((10, 90), (10, 62)))], REF, mode="A")
    p, why = O.presence(cloudy)
    assert p in ("UNKNOWN", "NOT_OBSERVED")
    if cloudy.low_coverage_fallback or cloudy.coverage < C.PASS_FALLBACK_COVERAGE:
        assert p == "UNKNOWN"


def test_present_when_enough_connected_plant_cells():
    obs = O.observe([scene("a", days(0), plant=BED)], REF, mode="A")
    p, _ = O.presence(obs)
    assert p == "PRESENT" and obs.plant_cells >= O.MIN_PLANT_CELLS


def test_single_pass_mode_requires_mostly_clear_scene():
    cloudy = scene("c", days(0), plant=BED, cloud=patch((10, 90), (10, 50)))
    assert O.observe([cloudy], REF, mode="S").evidence_kind == "NONE"


# ---------------------------------------------------------------- burst check (production scoring, note 06)
def test_a_burst_scene_among_consistent_scenes_is_excluded():
    big = patch((12, 88), (12, 88))                        # nearly the whole lake "flags": implausible vs the neighbours
    scenes = [scene("a", days(-6), plant=BED), scene("b", days(-1), plant=BED), scene("c", days(3), plant=BED), scene("burst", days(0), plant=big)]
    sel = O.select_scenes(scenes, REF)
    assert sel["bursts"] == ["burst"] and all(s.id != "burst" for s in sel["accepted"])
    obs = O.observe(scenes, REF, mode="P")
    assert "burst" not in obs.scene_ids and any("burst" in n for n in obs.notes)


def test_single_accepted_pass_declares_it_cannot_be_burst_checked():
    obs = O.observe([scene("only", days(0), plant=BED)], REF, mode="A")
    assert any("burst check" in n for n in obs.notes)


# ---------------------------------------------------------------- v0.2: scene-adaptive NIR floor, tunable haze
def test_adaptive_floor_follows_the_scenes_own_open_water_tail():
    scl, red, nir, swir = scene_arrays()
    f = O.scene_fields(scl, red, nir, swir, lake_mask())
    assert f.nir_floor == O.NIR_PLANT_MIN and f.floor_diag["tail"] < 0.01          # clean water: floor stays at the minimum
    nir2 = nir.copy()
    nir2[lake_mask()] = 0.06                                                          # a slightly bright but not-blooming lake
    red2 = np.full_like(red, 0.06)
    f2 = O.scene_fields(scl, red2, nir2, swir, lake_mask())
    assert f2.nir_floor == pytest.approx(0.06, abs=1e-4)


def test_bloom_or_ice_edge_scene_is_refused_not_called_clear():
    scl, red, nir, swir = scene_arrays()
    nir[lake_mask()] = 0.15
    red[lake_mask()] = 0.14                                                            # NDVI ~0.03 bright water: bloom / ice-edge look
    f = O.scene_fields(scl, red, nir, swir, lake_mask())
    c = O.to_cells(f)
    unk = c.interior & (c.state == O.UNKNOWN)
    assert unk.sum() == c.interior.sum() and set(c.reason[unk]) == {O.REASON_CODES["BLOOM_AMBIGUOUS"]}
    assert (c.state == O.NO_PLANT).sum() == 0                                          # never a false 'no vegetation'


def test_plant_bed_survives_the_adaptive_floor_on_clean_water():
    c = cells_for(plant=BED)
    assert (c.state == O.PLANT).sum() > 0


def test_haze_parameters_are_explicit_and_change_the_refusal():
    scl, red, nir, swir = scene_arrays(haze=patch((20, 40), (20, 40)))
    wide = O.to_cells(O.scene_fields(scl, red, nir, swir, lake_mask(), haze_swir=0.02, haze_standoff_px=10))
    none = O.to_cells(O.scene_fields(scl, red, nir, swir, lake_mask(), haze_swir=0.02, haze_standoff_px=0))
    assert (none.state == O.UNKNOWN).sum() < (wide.state == O.UNKNOWN).sum()


def test_cloud_pixels_never_feed_the_bloom_tail_v03():
    # a bright cloud patch (NIR 0.4, NDVI ~0) that SCL flags as cloud must not make the whole lake BLOOM_AMBIGUOUS
    scl, red, nir, swir = scene_arrays()
    cl = patch((20, 60), (20, 60))
    scl[cl] = 9
    nir[cl], red[cl] = 0.40, 0.39
    f = O.scene_fields(scl, red, nir, swir, lake_mask())
    assert not f.blocked["BLOOM_AMBIGUOUS"].any() and f.nir_floor == O.NIR_PLANT_MIN


def test_default_haze_pair_is_the_evaluated_v02_pair():
    assert (O.HAZE_SWIR_DEFAULT, O.HAZE_STANDOFF_DEFAULT) == (0.10, 0)
