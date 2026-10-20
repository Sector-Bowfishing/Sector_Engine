"""Wind Bowfishing Assessment layer (V2) tests: real Guntersville geometry (committed subset of the frozen fetch table), SYNTHETIC
wind. These verify bowfishing behaviour and contract honesty; they are never evidence of observed accuracy."""
import gzip
import hashlib
import json
import os
import sys
from datetime import timedelta

import pytest

from sector_wind import bowfishing as BF
from sector_wind.brain import contract as C
from sector_wind.brain.state import build_state
from sector_wind.assessment import build as B, limitations as LIM, ranking as R, scenarios as SCN, schema as SC, semantics as S, timeline as T
import test_brain as TB

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "architecture"))
try:
    from jsonschema_lite import iter_errors  # noqa: E402
except ImportError:      # the clean-copy gate (verification/integration/test_wind_package.py) ships brains/wind without tools/
    iter_errors = None

FIXTURE = os.path.join(HERE, "fixtures", "guntersville_fetch_subset.json.gz")
SCHEMA = json.load(open(os.path.join(HERE, "..", "contracts", "wind-exposure-assessment-v1.json")))
LAKE = "Guntersville|AL"
A, Bk = "GT-005719", "GT-001172"          # audit pair: SW-open creek-arm bank / sheltered minor tributary


@pytest.fixture(scope="module")
def fx():
    return json.loads(gzip.decompress(open(FIXTURE, "rb").read()))


@pytest.fixture(scope="module")
def L(fx):
    return R.geometry(fx, LAKE)


def dec(L, mph, d=225.0, **k):
    return B.build(LAKE, B.synthetic_wind(mph, d, k.pop("dur", 6.0), k.pop("gust", None)), L, SCN.NOW, **k)


def valid(d):
    if iter_errors is not None:
        errs = list(iter_errors(d, SCHEMA))
        assert errs == [], errs[:5]
    assert SC.check(d) == []


def bank(d, bid):
    return next(x for x in d["shorelines"]["requested"] if x["bankId"] == bid)


# ── geometry provenance ───────────────────────────────────────────────────────────────────────

def test_fixture_is_verbatim_real_geometry(fx, L):
    import base64
    assert hashlib.sha256(base64.b64decode(fx["tableBase64"])).hexdigest() == fx["tableSha256"]
    assert fx["sourceTableSha256"] and fx["geometry"]["source"].startswith("USGS NHD")
    assert len(L["banks"]) == L["table"].shape[0] and L["table"].shape[1] == BF.NB
    assert {A, Bk} <= {b["id"] for b in L["banks"]}


# ── 1/2 wind input normalisation + direction convention ──────────────────────────────────────

def test_synthetic_wind_units_and_label():
    w = B.synthetic_wind(10, 225)
    assert w["kind"] == "synthetic" and abs(w["speedMS"] - 4.4704) < 1e-9 and "SYNTHETIC" in w["source"]


def test_direction_is_from_convention(L):
    # Wind FROM 225 (SW) blows across the long SW fetch of bank A; wind FROM 45 (NE) does not.
    sw, ne = dec(L, 10, 225, bank_ids=(A,)), dec(L, 10, 45, bank_ids=(A,))
    assert bank(sw, A)["fetch"]["effectiveM"] > 20 * bank(ne, A)["fetch"]["effectiveM"]
    assert sw["wind"]["directionCardinal"] == "SW" and sw["wind"]["units"]["direction"].startswith("degrees FROM")


def test_wind_from_state_end_to_end(tmp_path, fx):
    """Layer 1 -> Layer 2 through the real state builder (test archive, SYNTHETIC values)."""
    st = TB.make_store(tmp_path, speed=6.0, direction=225.0)
    state, rows, meta = build_state(st, TB.CFG, "guntersville", LAKE, TB.DIRECTORY[0], TB.NOW, fetch_obj=fx)
    w = B.wind_from_state(state)
    assert w["kind"] == "analysis" and abs(w["speedMS"] - 6.0) < 0.05 and w["dirFromDeg"] == 225
    assert w["durationH"] == state["surfaceState"]["durationH"]
    d = B.build(LAKE, w, R.geometry(fx, LAKE), TB.NOW, bank_ids=(A, Bk), window_hours=w["hourly"][:6])
    valid(d)
    assert d["status"] == "READY" and d["wind"]["kind"] == "analysis"
    assert bank(d, A)["windExposure"]["code"] in S.EXPOSED and bank(d, Bk)["windExposure"]["code"] in S.SHELTERED
    assert len(d["timeline"]["hours"]) == 6 and all(h["kind"] == "forecast" for h in d["timeline"]["hours"])
    # same frozen functions and duration as the state's own bank rows; the only difference is the published state's 0.1 mph
    # rounding of the wind (6.0 m/s -> 13.4 mph -> 5.99 m/s), worth < 0.1 in here
    row = next(r for r in rows if r["bankId"] == A)
    assert abs(row["hm0In"] - bank(d, A)["predictedSurface"]["waveHeightIn"]) <= 0.1 and row["exposureRank"] == bank(d, A)["windExposure"]["code"]


# ── 3/4/5/8 exposure, protected shores, ranking, fetch ───────────────────────────────────────

def test_exposed_vs_sheltered_audit_pair(L):
    d = dec(L, 12, bank_ids=(A, Bk))
    valid(d)
    a, b = bank(d, A), bank(d, Bk)
    assert a["windExposure"]["code"] == "HIGH_EXPOSURE" and b["windExposure"]["code"] == "PROTECTED"
    assert a["predictedSurface"]["waveHeightIn"] == pytest.approx(8.8, abs=0.1)        # Oct 19 audit scenario E value
    assert a["fetch"]["effectiveM"] == pytest.approx(7800, abs=1) and b["fetch"]["effectiveM"] < 40
    assert "long open fetch" in a["explanation"] and "land within" in b["explanation"]


def test_ranking_uses_frozen_order_and_is_bounded(L):
    d = dec(L, 12, top=7)
    allr = BF.rank_banks_for_wind(L, 12 * BF.MPH, 225.0)["all"]
    frozen_best = [r["bankId"] for r in allr if r["exposureRank"] in S.SHELTERED][:7]
    assert [b["bankId"] for b in d["shorelines"]["sheltered"]] == frozen_best[: len(d["shorelines"]["sheltered"])]
    assert len(d["shorelines"]["exposed"]) <= 7 and "fullRanking" not in d
    full = dec(L, 12, include_full_ranking=True)["fullRanking"]
    assert len(full) == d["lakeSummary"]["resolvableBanks"]
    assert sum(d["lakeSummary"]["exposureCounts"].values()) == d["lakeSummary"]["resolvableBanks"]
    with pytest.raises(Exception):
        R.rank(L, 1.0, 225.0, top="x")


def test_top_is_clamped(L):
    assert len(R.rank(L, 8.0, 225.0, top=10_000)["sheltered"]) <= R.MAX_TOP


# ── 6/7 surface classification + exposure/surface consistency ────────────────────────────────

def test_audit_inconsistency_is_two_concepts_not_a_contradiction(L):
    b = bank(dec(L, 15, bank_ids=(Bk,)), Bk)
    assert b["windExposure"]["code"] == "PROTECTED" and b["windExposure"]["label"] == "Sheltered"
    assert b["predictedSurface"]["label"] == "Light chop" and b["predictedSurface"]["driver"] == "WIND_TEXTURE"
    assert b["predictedSurface"]["waveHeightIn"] < 1.0 and "wind itself roughens the surface" in b["explanation"]


def test_semantic_invariants_every_bank_every_wind(L):
    for mph in (0.5, 3, 5, 8, 10, 12, 15, 20, 25):
        for d in range(0, 360, 45):
            r = BF.rank_banks_for_wind(L, mph * BF.MPH, d)["all"]
            for row in r:
                v = S.describe(row, LAKE, mph * BF.MPH, 6.0)
                assert SC.check_bank(v) == [], (mph, d, row["bankId"])


def test_surface_labels_do_not_reuse_exposure_words():
    assert set(S.SURFACE_LABEL.values()).isdisjoint(set(S.EXPOSURE_LABEL.values()))
    assert BF.CHOP[1] == "Protected"       # the frozen internal label is unchanged; only the V2 user-facing label differs


def test_frozen_physics_unchanged():
    # spot values of the frozen CEM / classes (any change here is a physics change, not a V2 change)
    assert BF.cem(12 * BF.MPH, 7800, 6 * 3600) == pytest.approx(0.2243, abs=2e-4)
    assert [BF.chop_class(h) for h in (0.02, 0.05, 0.1, 0.2, 0.4)] == [1, 2, 3, 4, 5]
    assert BF.surface_p(0.018, 6.7) == 3


def test_range_added_to_evaluate_bank_is_consistent(L):
    r = BF.evaluate_bank(L, 0, 6.0, 225.0)
    lo, hi = r["predictedHm0RangeIn"]
    assert lo <= r["predictedHm0In"] <= hi
    assert r["confidence"] == ("firm" if BF.chop_class(lo * 0.0254) == BF.chop_class(hi * 0.0254) else "boundary")


# ── 9/10 duration + changing directions ─────────────────────────────────────────────────────

def test_duration_growth_then_fetch_limit(L):
    hs = [bank(dec(L, 12, dur=h, bank_ids=(A,)), A)["predictedSurface"]["waveHeightIn"] for h in (0.5, 1, 2, 3, 6, 12)]
    assert hs == sorted(hs) and hs[-1] == hs[-2] == hs[-3]


def test_timeline_direction_shift_flips_shores(L):
    r = SCN.run(L, only=("S04",))["scenarios"][0]
    assert r["pass"], r["checks"]


def test_timeline_without_history_discloses_underestimate(L):
    t = T.timeline(L, SCN._hours([(10, 225)] * 3), [A])
    assert "UNDER-estimated" in t["durationBasis"] and t["priorHistoryHours"] == 0
    t2 = T.timeline(L, SCN._hours([(10, 225)] * 3), [A], prior=SCN._hours([(10, 225)] * 6, SCN.NOW - timedelta(hours=6)))
    assert t2["banks"][0]["hours"][0]["waveHeightIn"] > t["banks"][0]["hours"][0]["waveHeightIn"]


def test_timeline_unknown_hour_stays_unknown(L):
    hrs = SCN._hours([(10, 225), (10, 225)])
    hrs[1]["speedMS"] = None
    t = T.timeline(L, hrs, [A])
    assert t["hours"][1]["status"] == "WIND_UNAVAILABLE" and t["banks"][0]["hours"][1]["exposure"] == "UNKNOWN"


def test_rapid_decrease_flags_optimistic_recession(L):
    r = SCN.run(L, only=("S14",))["scenarios"][0]
    assert r["pass"], r["checks"]


# ── 11/12/13/14/15 strong wind, unknown data, missing geometry, confidence, geographic limits ─

def test_strong_wind_limitation_always_attached(L):
    for mph in (3, 8, 12, 20):
        ids = [x["id"] for x in dec(L, mph)["limitations"]]
        assert "STRONG_WIND_UNDERFORECAST" in ids
    assert "WINDY_HOUR_ERROR" in [x["id"] for x in dec(L, 12)["limitations"]]


def test_limitation_numbers_come_from_published_evidence():
    ev = LIM.evidence()["metrics"]
    txt = LIM.catalogue()["STRONG_WIND_UNDERFORECAST"][1]
    assert f"{ev['event15mphPod']:.2f}" in txt and "H2" not in json.dumps(LIM.evidence()["window"]["splits"])


@pytest.mark.parametrize("wind,geom,supported,status", [
    (dict(speedMS=None), True, True, "WIND_UNAVAILABLE"),
    (dict(dirFromDeg=None), True, True, "DIRECTION_UNKNOWN"),
    (dict(stale=True, staleReasons=["forecastCycleStale:4.0h>3h"]), True, True, "INPUT_STALE"),
    (dict(), False, True, "GEOMETRY_UNAVAILABLE"),
    (dict(), False, False, "UNSUPPORTED_LAKE"),
])
def test_never_fabricate(L, wind, geom, supported, status):
    w = {**B.synthetic_wind(10, 225), **wind}
    d = B.build(LAKE, w, L if geom else None, SCN.NOW, supported=supported, bank_ids=(A,))
    valid(d)
    assert d["status"] == status and d["shorelines"] is None and d["lakeSummary"] is None and d["confidence"]["level"] == "UNKNOWN"


def test_calm_without_direction_is_ready_and_flat(L):
    d = B.build(LAKE, B.synthetic_wind(0.6, None), L, SCN.NOW, bank_ids=(A,))
    valid(d)
    assert d["status"] == "READY" and d["lakeSummary"]["exposedPct"] == 0 and "Calm" in d["explanation"]


def test_unknown_bank_never_sheltered(L):
    unk = next(b["id"] for b in L["banks"] if b.get("belowResolution"))
    d = dec(L, 10, bank_ids=(unk,), top=25)
    valid(d)
    b = bank(d, unk)
    assert b["windExposure"]["code"] == "UNKNOWN" and b["predictedSurface"] is None and b["confidence"] == "unknown"
    assert unk not in [x["bankId"] for x in d["shorelines"]["sheltered"]]
    for x in d["shorelines"]["exposed"]:
        assert all(a["bankId"] != unk for a in x.get("nearestSheltered", []) + x.get("lessExposedAlternatives", []))


def test_confidence_levels(L):
    assert dec(L, 5)["confidence"]["level"] == "LOW"                                    # synthetic is always LOW
    f = lambda **k: B.build(LAKE, B.wind_from_state(SCN._state(False, **k)), L, SCN.NOW)
    assert f(lead=2, mph=6.0)["confidence"]["level"] == "MODERATE"
    assert f(lead=2, mph=11.0)["confidence"]["level"] == "LOW"
    assert f(lead=18, mph=6.0)["confidence"]["level"] == "LOW"
    for lvl in (f(lead=2, mph=6.0), dec(L, 25)):
        assert lvl["confidence"]["ceiling"] == "MODERATE" and lvl["confidence"]["level"] != "HIGH"


def test_geographic_limits(L):
    r = SCN.run(L, only=("S15",))["scenarios"][0]
    assert r["pass"], r["checks"]


# ── alternatives ────────────────────────────────────────────────────────────────────────────

def test_alternatives_for_exposed_bank(L):
    b = bank(dec(L, 15, bank_ids=(A,)), A)
    assert b["windExposure"]["code"] in S.EXPOSED
    assert b["lessExposedAlternatives"] and b["nearestSheltered"]
    assert all(x["windExposure"]["code"] in S.SHELTERED for x in b["nearestSheltered"])
    assert all("not checked for fish, access" in x["note"] for x in b["lessExposedAlternatives"] + b["nearestSheltered"])
    assert "nearestSheltered" not in bank(dec(L, 15, bank_ids=(Bk,)), Bk)          # only HIGH/EXTREME banks get alternatives


# ── 16 versioned output + schema ────────────────────────────────────────────────────────────

def test_decision_is_versioned_and_schema_valid(L):
    d = dec(L, 12, bank_ids=(A, Bk), window_hours=SCN._hours([(12, 225)] * 3))
    valid(d)
    assert d["assessmentSchema"] == "sector-wind-exposure-assessment-v1" and d["knowledgeVersion"] == SC.KNOWLEDGE_VERSION
    assert d["provenance"]["aiUsed"] is False and d["provenance"]["modelVersion"] == C.CANDIDATE_MODEL
    assert len(json.dumps(d)) < 120_000        # bounded payload


def test_check_catches_violations(L):
    d = dec(L, 12, bank_ids=(A,))
    bad = json.loads(json.dumps(d)); bad["validation"]["validated"] = True
    assert "assessment claims validation" in SC.check(bad)
    bad = json.loads(json.dumps(d)); bad["shorelines"]["requested"][0]["predictedSurface"]["class"] = 1
    assert any("below the wave" in p for p in SC.check(bad))
    bad = json.loads(json.dumps(d)); bad["status"] = "INPUT_STALE"
    assert "non-READY assessment carries shoreline results" in SC.check(bad)


# ── full scenario catalogue (Layer 3) ───────────────────────────────────────────────────────

def test_all_bowfishing_scenarios_pass(L):
    r = SCN.run(L)
    failed = [(s["id"], [c for c in s["checks"] if not c["pass"]]) for s in r["scenarios"] if not s["pass"]]
    assert not failed, failed
    assert r["total"] == len(SCN.SCENARIOS) == 18 and set(SCN.CAPABILITY) <= set(SCN.SCENARIOS)
    assert r["evidenceClass"].startswith("MODEL_CAPABILITY")


def test_scenario_crash_is_a_failure_not_a_pass(L, monkeypatch):
    monkeypatch.setitem(SCN.SCENARIOS, "S01", ("boom", lambda L: 1 / 0))
    r = SCN.run(L, only=("S01",))
    assert r["passed"] == 0 and "ZeroDivisionError" in r["scenarios"][0]["checks"][0]["detail"]


# ── 25 existing application compatibility ───────────────────────────────────────────────────

def test_existing_state_and_publication_untouched(tmp_path, fx):
    """The assessment layer is not wired into the hourly job or the publication: the state carries no assessment, and the
    production publish path does not import the assessment package."""
    st = TB.make_store(tmp_path)
    state, rows, _ = build_state(st, TB.CFG, "guntersville", LAKE, TB.DIRECTORY[0], TB.NOW, fetch_obj=fx)
    assert "assessment" not in json.dumps(sorted(state))
    for mod in ("publish.py", "artifact.py", "state.py", "writer.py"):
        src = open(os.path.join(HERE, "..", "runtime", "sector_wind", "brain", mod)).read()
        assert "assessment" not in src.split('"""', 2)[-1] or "from ..assessment" not in src
    main_src = open(os.path.join(HERE, "..", "runtime", "main.py")).read()
    assert "sector_wind.assessment" not in main_src and "from .assessment" not in main_src


# ── 17/22/26 evaluation evidence and Pulse contracts stay in step with the runtime ──────────

def test_committed_measurement_evidence_matches_runtime():
    """Bumping KNOWLEDGE_VERSION or the scenario catalogue without regenerating the evidence fails here (stale evidence)."""
    p = os.path.join(ROOT, "docs", "brains", "scoring", "evidence", "wind-measurements-evidence.json")
    if not os.path.exists(p):
        pytest.skip("repository docs not present (clean-copy gate); the platform suite requires the file")
    ev = json.load(open(p))
    rubric = json.load(open(os.path.join(ROOT, "docs", "brains", "scoring", "wind-specialist-capability-v2.json")))
    assert ev["knowledgeVersion"] == SC.KNOWLEDGE_VERSION and ev["assessmentSchema"] == SC.ASSESSMENT_SCHEMA
    assert ev["scenarios"]["suite"] == SCN.SUITE_ID == rubric["scenarioSuite"]
    assert ev["scenarios"]["capabilityMap"] == SCN.CAPABILITY
    for lk in rubric["developmentLakes"]:
        assert set(ev["scenarios"]["lakes"][lk]["results"]) == set(SCN.SCENARIOS)
    used = {s for c in rubric["categories"] for it in c["items"] for s in it.get("scenarios", [])}
    assert used <= set(SCN.SCENARIOS)
    assert {SCN.CAPABILITY[s] for s in used} <= {it["id"] for c in rubric["categories"] for it in c["items"]}


def test_pulse_entrypoints_contract():
    ep = json.load(open(os.path.join(HERE, "..", "contracts", "wind-validation-entrypoints-v1.json")))
    assert ep["constraints"]["aiRequired"] is False and ep["constraints"]["newScheduler"] is False and ep["constraints"]["productionWrites"] == "none"
    ids = {e["id"] for e in ep["entrypoints"]}
    assert {"wind.assessment.scenarios", "wind.assessment.assess", "platform.wind.measurements", "platform.wind.certificationRefresh"} <= ids
    from sector_wind.assessment import __main__ as CLI
    assert CLI.main(["scenarios", "--fetch", FIXTURE, "--lake", LAKE, "--json", os.devnull]) == 0


# ── 26/27 specialist boundary: Intelligence-consumable, no cross-Brain recommendation fields ──

def test_no_cross_brain_recommendation_fields(L):
    for d in (dec(L, 16, bank_ids=(A, Bk), window_hours=SCN._hours([(12, 225), (16, 270)])), dec(L, 0.5), dec(L, 12, top=25)):
        assert SC.boundary_problems(d) == []
        txt = json.dumps({k: v for k, v in d.items() if k not in ("scope", "limitations")})
        for bad in ("fishingImpact", "SURFACE_NOT_LIMITING", "VERY_POOR", "spot", "shoot", "best place", "bowfish here"):
            assert bad not in txt, bad


def test_boundary_check_catches_leaks(L):
    d = dec(L, 12, bank_ids=(A,))
    leak = json.loads(json.dumps(d)); leak["shorelines"]["requested"][0]["fishingOpportunity"] = "GOOD"
    assert any("outside the wind domain" in p for p in SC.check(leak))
    leak = json.loads(json.dumps(d)); leak["explanation"] = "This is the best place to bowfish tonight."
    assert any("fishing language" in p for p in SC.check(leak))
    leak = json.loads(json.dumps(d)); leak["shorelines"]["requested"][0]["windSurfaceDisturbance"]["text"] = "Too rough to spot fish."
    assert any("fishing language" in p for p in SC.check(leak))


def test_surface_disturbance_is_wind_domain_and_structured(L):
    for mph, lvl in ((0.5, "NONE"), (15, "MODERATE"), (20, "VERY_HIGH")):
        b = bank(dec(L, mph, bank_ids=(A,)), A)
        w = b["windSurfaceDisturbance"]
        assert w["surfaceClass"] == b["predictedSurface"]["class"] and w["mechanism"] == b["predictedSurface"]["driver"]
        assert w["text"].startswith(("No ", "Low ", "Moderate ", "High ", "Very high ")) and "wind-driven surface disturbance expected" in w["text"]
    assert bank(dec(L, 20, bank_ids=(A,)), A)["windSurfaceDisturbance"]["level"] in ("HIGH", "VERY_HIGH")
    sheltered = bank(dec(L, 15, bank_ids=(Bk,)), Bk)["windSurfaceDisturbance"]
    assert sheltered["mechanism"] == "WIND_TEXTURE" and "waves stay small" in sheltered["text"]


def test_intelligence_brain_can_consume_without_parsing_text(L):
    """Every per-bank fact Intelligence needs is a typed field (codes, numbers, ids), never only prose."""
    d = dec(L, 16, bank_ids=(A,), window_hours=SCN._hours([(12, 225), (16, 270)]))
    assert d["scope"]["synthesisOwner"] == "sector-intelligence" and "where to bowfish" in d["scope"]["doesNotAnswer"]
    b = bank(d, A)
    typed = (b["windExposure"]["code"], b["relativeExposure"]["lakePercentile"], b["predictedSurface"]["class"], b["predictedSurface"]["waveHeightIn"],
             b["windSurfaceDisturbance"]["level"], b["fetch"]["effectiveM"], b["confidence"], b["anchor"])
    assert all(x is not None for x in typed)
    for alt in b["lessExposedAlternatives"] + b["nearestSheltered"]:
        assert alt["windExposure"]["code"] and isinstance(alt["distanceM"], int) and alt["rule"]
    assert all(x["severity"] in ("WARNING", "CAUTION", "INFO") and x["id"].isupper() for x in d["limitations"])
    assert d["confidence"]["level"] in ("LOW", "MODERATE") and d["reference"] and d["provenance"]["modelVersion"]
    assert all(h["exposure"] for x in d["timeline"]["banks"] for h in x["hours"])
    assert "biological-state" not in json.dumps(d) and "water-clarity" not in json.dumps(d)       # no other Brain consumed


def test_wind_has_no_cross_brain_dependency():
    import glob
    for f in glob.glob(os.path.join(HERE, "..", "runtime", "sector_wind", "assessment", "*.py")):
        src = open(f).read()
        for other in ("sector_fish", "biological", "water_clarity", "waterClarity", "sector_intelligence", "lake_brain"):
            assert other not in src, (f, other)
    brain = json.load(open(os.path.join(HERE, "..", "brain.json")))
    assert [c["registry"] for c in brain["consumes"]] == ["lakes"] and "sector-intelligence" in brain["authorizedConsumers"]
