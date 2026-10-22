import json
import os
from datetime import datetime, timezone

import pytest

from helpers import REF, patch, scene
from vegetation_brain import contract as C
from vegetation_research import fleet as F
from vegetation_research import maturity as M
from vegetation_brain import observer as O
from vegetation_brain import ops_summary as OPS
from vegetation_brain.publish import publish
from vegetation_brain.writer import DryRunWriter, WriteError

NOW = datetime(2025, 7, 22, 12, tzinfo=timezone.utc)
HERE = os.path.dirname(__file__)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def reg():
    def e(lid, area, conf="HIGH", geom=True):
        return {"lakeId": lid, "name": lid, "state": "AL", "lakeKey": lid.replace("|", "_"), "areaKm2": area if geom else None,
                "geometry": {"x": 1} if geom else None, "geometryConfidence": {"level": conf if geom else "MISSING"},
                "classification": {"region": "SE", "lakeClass": "R1"}, "geometryVersion": "v1"}
    return {"generatedAt": "t", "geometryVersion": "v1", "lakes": [e("Big|AL", 100), e("Small|AL", 0.2), e("None|AL", None, geom=False)]}


def test_dry_run_writes_only_vegetation_owned_paths_and_blocked_states():
    m = F.build_manifest(reg(), version="t")
    w = DryRunWriter()
    rep = publish(m, w, now=NOW)
    assert rep["ok"], rep["errors"]
    tree = w.tree
    assert tree["brains"]["vegetation"]["status"] == "PROFILED"
    assert tree["validation"]["vegetation"]["status"] == "NOT_VALIDATED"
    assert tree["brains"]["vegetation"]["scoreStatus"] == "NOT_ESTABLISHED"
    assert tree["brains"]["vegetation"]["research"]["official"] is False
    assert "scores" not in tree                                      # never writes /scores
    assert tree["lakeFleet"]["Small_AL"]["readiness"]["vegetation"] == "BLOCKED"
    assert tree["lakeFleet"]["Big_AL"]["readiness"]["vegetation"] == "PROFILED"   # observable but nothing run: no state written
    assert "Big_AL" not in tree.get("lakes", {})


def test_observed_lake_gets_a_state_and_calibration_readiness():
    m = F.build_manifest(reg(), version="t")
    bed = patch((30, 60), (30, 60))
    obs = O.observe([scene("a", REF, plant=bed), scene("b", REF, plant=bed), scene("c", REF, plant=bed)], REF, mode="P")
    w = DryRunWriter()
    rep = publish(m, w, observations={"Big|AL": obs}, now=datetime(2025, 7, 22, tzinfo=timezone.utc))
    st = w.tree["lakes"]["Big_AL"]["states"]["vegetation"]
    assert st["surfaceVegetation"]["status"] == "PRESENT" and st["submergedVegetation"]["observed"] is False
    assert w.tree["lakeFleet"]["Big_AL"]["readiness"]["vegetation"] == "CALIBRATION"
    assert rep["observed"] == 1
    assert w.tree["brains"]["vegetation"]["fleet"]["observedLakes"] == 1


def test_ownership_refuses_other_brains_paths():
    w = DryRunWriter()
    with pytest.raises(WriteError):
        w.patch({"lakes/Big_AL/states/depth": {"x": 1}})
    with pytest.raises(WriteError):
        w.patch({"scores/vegetation": {"value": 9}})


def test_no_live_writer_exists():
    import vegetation_brain.writer as W
    assert not hasattr(W, "RtdbWriter")
    src = open(os.path.join(HERE, "..", "runtime", "vegetation_brain", "publish.py")).read() + open(os.path.join(HERE, "..", "runtime", "run.py")).read()
    assert "--rtdb" not in src and "yes-write" not in src


def test_registry_extras_computed_not_hardcoded():
    m = F.build_manifest(reg(), version="t")
    a = OPS.registry_extras(m, 0)
    m2 = F.build_manifest({"lakes": reg()["lakes"][:1]}, version="t")
    b = OPS.registry_extras(m2, 0)
    assert a["fleet"]["totalLakes"] == 3 and b["fleet"]["totalLakes"] == 1
    assert a["scoreStatus"] == "NOT_ESTABLISHED" and a["scope"]["submergedObserved"] is False
    assert a["breakdowns"]["observability"] == {"HIGH": 1, "LOW": 1, "UNKNOWN": 1}


# ---------------------------------------------------------------- maturity
def test_maturity_is_research_only_and_far_below_the_gate():
    m = F.build_manifest(reg(), version="t")
    ev = M.evaluate(m)
    assert ev["official"] is False and ev["meetsProductionPolicy"] is False
    assert {"authority", "spatial", "presence", "validation", "provenance"} <= set(ev["criticalBelowThreshold"])


def test_density_becomes_critical_only_when_exposed():
    m = F.build_manifest(reg(), version="t")
    assert "density" not in M.evaluate(m)["criticalBelowThreshold"]
    assert "density" in M.evaluate(m, exposed=("density",))["criticalBelowThreshold"]


def test_coverage_is_truth_backed_not_raw_shadow_observations():
    m = F.build_manifest(reg(), version="t")
    assert M.evaluate(m, observed_lakes=0)["dimensions"]["coverage"]["score"] == 0
    assert M.evaluate(m, observed_lakes=3, truth_backed_lakes=0)["dimensions"]["coverage"]["score"] == 0     # 3 unvalidated observations earn nothing
    assert M.evaluate(m, observed_lakes=3, truth_backed_lakes=3)["dimensions"]["coverage"]["score"] == 10
    assert M.evaluate(m, observed_lakes=3, truth_backed_lakes=1)["dimensions"]["coverage"]["score"] == 5


def test_unsupported_score_increase_is_refused():
    prev = M.load_inputs()
    new = json.loads(json.dumps(prev))
    new["dimensions"]["presence"]["score"] = 6.0
    assert M.check_increase(prev, new, REPO)                                     # no new evidence
    new["dimensions"]["presence"]["evidence"] = prev["dimensions"]["presence"]["evidence"] + ["docs/does/not/exist.md"]
    assert any("missing" in v for v in M.check_increase(prev, new, REPO))
    new["dimensions"]["presence"]["evidence"] = prev["dimensions"]["presence"]["evidence"] + ["brains/vegetation/research/tools/vegetation_research/records/VEGETATION_VALIDATION_PREREGISTRATION.md"]
    assert not M.check_increase(prev, new, REPO)
    new["dimensions"]["presence"]["score"] = 2.0
    assert not M.check_increase(prev, new, REPO)                                 # decreases never need justification


def test_every_judgment_dimension_cites_evidence():
    for k, d in M.load_inputs()["dimensions"].items():
        if d["basis"] == "judgment":
            assert d["evidence"], k


# ---------------------------------------------------------------- Sector Brain Model v1: fingerprint-first and claim maturity
def test_unchanged_inputs_skip_and_changed_inputs_publish():
    m = F.build_manifest(reg(), version="t")
    bed = patch((30, 60), (30, 60))
    obs = O.observe([scene("a", REF, plant=bed), scene("b", REF, plant=bed), scene("c", REF, plant=bed)], REF, mode="P")
    w = DryRunWriter()
    r1 = publish(m, w, observations={"Big|AL": obs}, now=NOW)
    n1 = len(w.patches)
    r2 = publish(m, w, observations={"Big|AL": obs}, now=NOW)
    assert r1["skippedUnchanged"] == 0 and r2["skippedUnchanged"] == 3     # Big + the two BLOCKED lakes: nothing changed
    st1 = [p for p in w.patches if any(k.startswith("lakes/Big_AL/states") for k in p)]
    assert len(st1) == 1                                          # the second run wrote no new lake state
    obs2 = O.observe([scene("z", REF, plant=bed)] * 3, REF, mode="P")
    obs2.scene_ids = ["z1", "z2", "z3"]
    r3 = publish(m, w, observations={"Big|AL": obs2}, now=NOW)
    assert r3["skippedUnchanged"] == 2 and w.get("lakes/Big_AL/states/vegetation/provenance/inputFingerprint")   # only the changed lake rewrote


def test_claim_maturity_separates_levels_and_never_marks_submerged_observable():
    from vegetation_brain import state as S
    st, _ = S.build_state({"lakeId": "Big|AL", "tier": "HIGH", "readiness": "PROFILED", "reasons": [], "areaKm2": 40.0,
                           "geometryConfidence": "HIGH", "geometryVersion": "v1"}, None, NOW)
    cm = st["claimMaturity"]
    assert cm["geometryTier"]["level"] == 2 and cm["geometryTier"]["state"] == "VERIFIED"
    assert cm["agencyVegetationObservation"]["level"] == 1 and cm["agencyVegetationObservation"]["state"] == "NOT_ASSESSED"
    assert cm["surfaceVegetationPresence"]["level"] == 3 and cm["surfaceVegetationPresence"]["state"] == "NOT_VALIDATED"
    assert cm["submergedVegetation"]["state"] == "NOT_OBSERVABLE"
    assert all(v["state"] in C.CLAIM_STATES for v in cm.values())
    assert not any(v["state"] in ("VALIDATED", "PROVIDER_VERIFIED") for k, v in cm.items() if v["level"] == 3)


def test_v1_scope_variant_is_a_proposal_that_cannot_reach_the_policy_by_dropping_refused_dimensions():
    m = F.build_manifest(reg(), version="t")
    full = M.evaluate(m)
    v1 = M.evaluate_v1_scope(m)
    assert v1["proposal"] is True and v1["official"] is False and set(v1["refusedByDesign"]) == {"density", "seasonality", "submerged"}
    assert sum(v1["weights"].values()) == 100
    assert v1["meetsProductionPolicy"] is False and {"presence", "validation"} <= set(v1["criticalBelowThreshold"])
    # truth-backed coverage/freshness: unvalidated observations earn nothing
    assert v1["scores"]["coverage"] == 0 and v1["scores"]["freshness"] == 0
    assert M.evaluate_v1_scope(m, truth_backed_lakes=3, truth_backed_fresh_lakes=3)["scores"]["coverage"] == 10
