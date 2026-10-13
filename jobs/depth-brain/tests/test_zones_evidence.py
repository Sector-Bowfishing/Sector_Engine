import pytest
from depth_brain import contract as C
from depth_brain import evidence as E
from depth_brain import zones as Z

SH = {"lt3": 0.10, "lt6": 0.20, "lt10": 0.30}


def zref(interval, verified=True, **kw):
    return Z.reference_zones_from_shares(SH, interval, kw.pop("coverage", 0.95), "A", "TWDB", reference_verified=verified, **kw)


# ── contour interval handling ───────────────────────────────────────────────────────────────────
def test_supported_edges_by_interval():
    assert Z.supported_edges(1) == [3.0, 6.0, 10.0] and Z.supported_edges(2) == [3.0, 6.0, 10.0]
    assert Z.supported_edges(5) == [10.0]                  # only 10 is a multiple of 5; 3 and 6 would need interpolation
    assert Z.supported_edges(10) == [10.0]
    assert Z.supported_edges(3) == [3.0, 6.0, 10.0]
    assert Z.supported_edges(None) == [] and Z.supported_edges(0) == []


def test_coarse_interval_never_yields_fine_bands():
    st = Z.reference_state(zref(5))
    assert "shareUnder3Ft" not in st and "share3To6Ft" not in st and "shareUnder6Ft" not in st
    assert st == {"shareUnder10Ft": 0.3, "shareDeeper": 0.7}
    assert Z.reference_state(zref(10)) == {"shareUnder10Ft": 0.3, "shareDeeper": 0.7}


def test_fine_interval_gives_all_bands():
    st = Z.reference_state(zref(2))
    assert st["shareUnder3Ft"] == 0.1 and st["share3To6Ft"] == 0.1 and st["share6To10Ft"] == 0.1 and st["shareDeeper"] == 0.7


def test_bad_input_is_refused_not_repaired():
    assert Z.reference_zones_from_shares({"lt3": 0.4, "lt6": 0.2, "lt10": 0.3}, 2, 1, "A", "x") is None      # non-monotone
    assert Z.reference_zones_from_shares({"lt3": 1.4}, 2, 1, "A", "x") is None
    assert Z.reference_zones_from_shares({}, 2, 1, "A", "x") is None
    assert Z.reference_zones_from_shares(SH, None, 1, "A", "x") is None


# ── effective zones ─────────────────────────────────────────────────────────────────────────────────
def test_effective_zones_withheld_until_survey_reference_is_verified():
    r = Z.effective_zones(zref(2, verified=False), -2.0, 0.3)
    assert r == {"available": False, "reason": "SURVEY_REFERENCE_POOL_UNVERIFIED"}


def test_zero_shift_reproduces_reference_shares():
    r = Z.effective_zones(zref(2), 0.0, 0.0)["shares"]
    assert r["under3"] == {"lo": 0.1, "hi": 0.1} and r["threeToSix"] == {"lo": 0.1, "hi": 0.1} and r["deeper"] == {"lo": 0.7, "hi": 0.7}
    assert r["dry"] == {"lo": 0.0, "hi": 0.0}


def test_lowering_exposes_shallow_water_and_brackets_the_surface():
    r = Z.effective_zones(zref(2), -3.0, 0.0)["shares"]
    assert r["dry"] == {"lo": 0.1, "hi": 0.1}                                   # reference depth < 3 ft is now dry (edge supported)
    assert r["under3"]["lo"] == pytest.approx(0.1) and r["under3"]["hi"] == pytest.approx(0.1)       # ref 3-6 ft -> now 0-3 ft
    assert r["threeToSix"] == {"lo": 0.0, "hi": 0.1}                            # ref 6-9 ft: 9 ft is not a supported edge -> bound
    lo = sum(r[k]["lo"] for k in ("dry", "under3", "threeToSix", "sixToTen", "deeper"))
    hi = sum(r[k]["hi"] for k in ("dry", "under3", "threeToSix", "sixToTen", "deeper"))
    assert lo <= 1.0 + 1e-9 <= hi + 1e-9                                        # the true partition lies inside the bounds


def test_between_edges_gives_bounds_not_invented_precision():
    r = Z.effective_zones(zref(2), -2.0, 0.0)["shares"]           # -2 ft: dry edge at 2 ft lies between 0 and the 3 ft edge
    assert r["dry"]["lo"] == 0.0 and r["dry"]["hi"] == pytest.approx(0.1)


def test_shift_uncertainty_widens_bounds():
    a = Z.effective_zones(zref(2), -3.0, 0.0)["shares"]["dry"]
    b = Z.effective_zones(zref(2), -3.0, 1.0)["shares"]["dry"]
    assert (b["hi"] - b["lo"]) > (a["hi"] - a["lo"])


def test_rising_lake_flags_unquantified_flooded_margin():
    r = Z.effective_zones(zref(2), 2.0, 0.0)
    assert r["floodedMarginUnquantified"] is True and r["shares"]["dry"] == {"lo": 0.0, "hi": 0.0}


def test_coarse_survey_cannot_resolve_shallow_effective_zones():
    r = Z.effective_zones(zref(5), -2.0, 0.0)["shares"]           # only the 10 ft edge is known
    assert r["under3"]["hi"] - r["under3"]["lo"] > 0.2           # honest, wide bound


# ── evidence tiers + GLOBathy policy ───────────────────────────────────────────────────────────────
def test_tier_precedence_a_over_b_over_c_over_d():
    items = [E.Evidence("D", "modeled", "globathy"), E.Evidence("C", "contour", "ienc"), E.Evidence("A", "contour", "twdb"), E.Evidence("B", "contour", "mn")]
    assert E.best_evidence(items).tier == "A"
    assert E.best_evidence(items[:2]).tier == "C"
    assert E.best_evidence([]).tier == "UNKNOWN" and E.best_evidence([None]).tier == "UNKNOWN"


def test_research_tier_mapping_never_promotes_partial_or_binary():
    m = E.depth_tier_from_research
    assert m("A") == "A" and m("B") == "B"
    assert m("B-partial") == "C" and m("B-binary") == "C"          # NOT promoted to full bathymetry
    assert m("D") == "D" and m("U") == "UNKNOWN" and m(None) == "UNKNOWN" and m("weird") == "UNKNOWN"


def test_globathy_is_forbidden_for_every_measured_product():
    for use in E.FORBIDDEN_MODEL_USES:
        with pytest.raises(E.ForbiddenEvidenceUse):
            E.assert_allowed_use("globathy", use)
        with pytest.raises(E.ForbiddenEvidenceUse):
            E.assert_allowed_use("modeled", use)
    for use in ("absolute_depth", "flats", "dropoffs", "lake_depth_ranking", "customer_contour_layer", "depth_zones"):
        assert use in E.FORBIDDEN_MODEL_USES
    E.assert_allowed_use("contour", "zone_shares")                  # measured evidence is fine


def test_zone_builder_guard_rejects_modeled_source():
    with pytest.raises(E.ForbiddenEvidenceUse):
        Z.forbid_modeled_zones("globathy")
    Z.forbid_modeled_zones("contour")


def test_globathy_prior_is_disabled_by_default():
    assert E.ENABLE_GLOBATHY_COARSE_PRIOR is False
    assert E.globathy_coarse_prior(8.0, "verified") is None


def test_globathy_prior_when_enabled_is_a_class_only_and_cannot_override_measured(monkeypatch):
    monkeypatch.setattr(E, "ENABLE_GLOBATHY_COARSE_PRIOR", True)
    p = E.globathy_coarse_prior(8.0, "verified")
    assert p["class"] in E.ALLOWED_PRIOR_CLASSES and p["tier"] == "D" and p["scored"] is False
    assert not any(k in p for k in ("depthFt", "zones", "shares", "meanDepthFt", "polygon", "rank"))
    assert E.globathy_coarse_prior(8.0, "suspect") is None and E.globathy_coarse_prior(8.0, None) is None and E.globathy_coarse_prior(None, "verified") is None
    for tier in "ABC":
        assert E.globathy_coarse_prior(8.0, "verified", best_existing=E.Evidence(tier, "contour", "x")) is None
    assert E.globathy_coarse_prior(25.0, "verified")["class"] == "unknown"
    assert E.globathy_coarse_prior(80.0, "verified")["class"] == "likelyDeep"
