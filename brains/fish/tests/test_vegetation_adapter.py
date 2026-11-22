"""Vegetation Brain output -> Fish's vegetation input contract. SYNTHETIC fixtures. The published-state cases use states pinned in
fixtures/vegetation_states_v1.json, which the Vegetation Brain's own state builder produced (see its _provenance): a Fish test may not import
another Brain's code, so the published shape is the contract tested here."""
import copy
import datetime as dt
import json
import os

import pytest

import contracts_in as ci
import vegetation_adapter as va

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = json.load(open(os.path.join(HERE, "fixtures", "vegetation_states_v1.json"), encoding="utf-8"))
NOW = dt.datetime.fromisoformat(FIXTURE["now"].replace("Z", "+00:00"))
PERSISTENT_PRESENT, PERSISTENT_CLEAR, TOO_LITTLE_SEEN = "present", "notObserved", "unknown"


def published(which):
    st = copy.deepcopy(FIXTURE["states"][which])
    assert st["stateSchema"] == va.VEG_STATE_SCHEMA
    return st


# ------------------------------------------------------------------------------------------- published state (pinned producer output)
def test_present_unclassified_lake_maps_to_surface_reaching_mixed_with_no_invented_density():
    st = published(PERSISTENT_PRESENT)
    assert st["surfaceVegetation"]["status"] == "PRESENT" and st["surfaceVegetation"]["coverageClass"] == "NOT_CALIBRATED"
    a = va.adapt(st)
    c = a["cell"]
    assert (c["class"], c["tier"], c["density"], c["scope"]) == ("SURFACE_REACHING_MIXED", "OBSERVED_SATELLITE", None, "LAKE")
    assert c["observedAt"] == st["surfaceVegetation"]["observedAt"] + "T00:00:00Z" and c["sceneIds"]
    # density is not calibrated by Vegetation, so Fish cannot call it shallow vegetated habitat yet: UNKNOWN, not TRUE
    r = va.vegetation_habitat(st, "shallowVegetatedHabitat", NOW)
    assert r["state"] == "UNKNOWN" and "density" in r["reason"]
    # an unclassified type can never say there is no flooded vegetation
    assert va.vegetation_habitat(st, "floodedVegetation", NOW)["state"] == "UNKNOWN"


def test_calibrated_density_is_carried_through_and_gives_true():
    st = published(PERSISTENT_PRESENT)
    for cov, dens in (("SPARSE", "SCATTERED"), ("MODERATE", "MODERATE"), ("DENSE", "DENSE")):   # a class Vegetation publishes once its density gate passes
        st["surfaceVegetation"]["coverageClass"] = cov
        r = va.vegetation_habitat(st, "shallowVegetatedHabitat", NOW)
        assert (r["state"], r["class"], r["density"]) == ("TRUE", "SURFACE_REACHING_MIXED", dens)
    st["surfaceVegetation"]["coverageClass"] = "UNKNOWN"
    assert va.vegetation_habitat(st, "shallowVegetatedHabitat", NOW)["state"] == "UNKNOWN"


def test_not_observed_lake_is_false():
    st = published(PERSISTENT_CLEAR)
    assert st["surfaceVegetation"]["status"] == "NOT_OBSERVED"
    assert va.adapt(st)["cell"]["class"] == "NONE_SIGNIFICANT"
    for h in ("shallowVegetatedHabitat", "floodedVegetation"):
        assert va.vegetation_habitat(st, h, NOW)["state"] == "FALSE"


def test_unknown_vegetation_is_a_refusal_with_vegetations_reason():
    st = published(TOO_LITTLE_SEEN)
    assert st["surfaceVegetation"]["status"] == "UNKNOWN"
    r = va.vegetation_habitat(st, "shallowVegetatedHabitat", NOW)
    assert (r["state"], r["reasonCode"]) == ("UNKNOWN", va.REFUSED)


def test_the_45_day_rule_is_unchanged_and_applies_to_adapted_readings():
    assert ci.MAX_VEG_AGE_DAYS == 45.0
    st = published(PERSISTENT_CLEAR)
    observed = dt.datetime.fromisoformat(va.adapt(st)["cell"]["observedAt"].replace("Z", "+00:00"))
    assert va.vegetation_habitat(st, "shallowVegetatedHabitat", observed + dt.timedelta(days=45))["state"] == "FALSE"
    late = va.vegetation_habitat(st, "shallowVegetatedHabitat", observed + dt.timedelta(days=46))
    assert late["state"] == "UNKNOWN" and "days old" in late["reason"]
    # Nov 30 reading of a Jul-Sep window: UNKNOWN by design (Fish all-lakes plan, 2026-11-22, section 0)
    a6 = {"presence": "NOT_OBSERVED", "sceneIds": ["S2"], "acquisitionDates": ["2026-08-01", "2026-09-30"], "oldestPassOn": "2026-08-01"}
    assert va.vegetation_habitat(a6, "shallowVegetatedHabitat", dt.datetime(2026, 11, 30, tzinfo=dt.timezone.utc))["state"] == "UNKNOWN"


def test_single_unaccepted_pass_or_no_evidence_is_not_an_observation():
    st = published(PERSISTENT_PRESENT)
    st["observation"]["evidenceKind"] = "SATELLITE_SINGLE_PASS"
    assert va.adapt(st)["reasonCode"] == va.NOT_AN_OBSERVATION
    st["observation"]["evidenceKind"] = "NONE"
    assert va.vegetation_habitat(st, "shallowVegetatedHabitat", NOW)["reasonCode"] == va.NOT_AN_OBSERVATION


# ------------------------------------------------------------------------------------------- A6 fleet answer (provisional shape)
A6_NOW = dt.datetime(2026, 8, 20, tzinfo=dt.timezone.utc)


def a6(**kw):
    d = {"presence": "PRESENT", "observedSharePct": 6.2, "observedHa": 140.0, "sceneIds": ["S2A_1", "S2B_2", "S2A_3"],
         "acquisitionDates": ["2026-07-28", "2026-08-05", "2026-08-12"], "oldestPassOn": "2026-07-28", "sensor": "sentinel-2", "observerVersion": "v1"}
    d.update(kw)
    return d


def test_a6_uses_oldest_pass_and_never_derives_density_from_the_share():
    c = va.adapt(a6())["cell"]
    assert (c["class"], c["tier"], c["observedAt"], c["density"]) == ("SURFACE_REACHING_MIXED", "OBSERVED_SATELLITE", "2026-07-28T00:00:00Z", None)
    assert va.vegetation_habitat(a6(), "shallowVegetatedHabitat", A6_NOW)["state"] == "UNKNOWN"
    assert va.vegetation_habitat(a6(coverageClass="DENSE"), "shallowVegetatedHabitat", A6_NOW)["state"] == "TRUE"


def test_a6_without_oldest_pass_uses_the_earliest_acquisition_date():
    c = va.adapt(a6(oldestPassOn=None, acquisitionDates=["2026-08-12", "2026-07-30"]))["cell"]
    assert c["observedAt"] == "2026-07-30T00:00:00Z"
    c = va.adapt(a6(oldestPassOn=None, acquisitionDates=[]))["cell"]
    assert c["observedAt"] is None
    assert va.vegetation_habitat(a6(oldestPassOn=None, acquisitionDates=[]), "shallowVegetatedHabitat", A6_NOW)["reason"] == "no observation date"


def test_a6_not_observed_unknown_and_undated():
    assert va.vegetation_habitat(a6(presence="NOT_OBSERVED"), "shallowVegetatedHabitat", A6_NOW)["state"] == "FALSE"
    r = va.vegetation_habitat(a6(presence="UNKNOWN", reason="BELOW_NOISE_TOLERANCE"), "shallowVegetatedHabitat", A6_NOW)
    assert (r["state"], r["reasonCode"]) == ("UNKNOWN", va.REFUSED) and "BELOW_NOISE_TOLERANCE" in r["reason"]
    assert va.adapt(a6(sceneIds=[]))["reasonCode"] == va.NOT_AN_OBSERVATION


def test_classified_broad_types_map_to_fish_classes():
    assert va.adapt(a6(broadType="EMERGENT"))["cell"]["class"] == "EMERGENT"
    assert va.adapt(a6(broadType="FLOATING_MAT"))["cell"]["class"] == "FLOATING"
    assert va.adapt(a6(broadType="FLOATING_LEAF"))["cell"]["class"] == "FLOATING"
    r = va.vegetation_habitat(a6(broadType="EMERGENT", coverageClass="SPARSE"), "floodedVegetation", A6_NOW)
    assert r["state"] == "FALSE"                                                                # classified emergent is not flooded terrestrial


@pytest.mark.parametrize("bad", [None, {}, [], "x", {"stateSchema": "sector-brain-vegetation-state-v0"}, {"presence": "PRESENT"}])
def test_unrecognised_shapes_are_not_published(bad):
    r = va.vegetation_habitat(bad, "shallowVegetatedHabitat", NOW)
    assert (r["state"], r["reasonCode"]) == ("UNKNOWN", va.NOT_PUBLISHED)


def test_non_vegetation_habitat_classes_stay_unknown():
    assert va.vegetation_habitat(a6(coverageClass="DENSE"), "backwaterHabitat", A6_NOW)["state"] == "UNKNOWN"
