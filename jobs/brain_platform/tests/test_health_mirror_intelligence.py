"""Sector_Ops #50 SI-A3: Intelligence's /health paths become Orchestrator-derived (as Water Clarity's, Lake's and Water Temp's), from published data only."""
import os
import sys

from sector_brain_platform import health_mirror as HM
from sector_brain_platform.publisher.registry import INTELLIGENCE, INTELLIGENCE_HEALTH_DOMAIN_CHILDREN

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def test_intelligence_health_is_derived_from_its_published_registry():
    out = HM.derive(INTELLIGENCE, {"status": "CALIBRATION", "health": "HEALTHY", "lastSuccessfulRun": "t", "deploymentVersion": "d", "publishMode": "manual",
                                   "directoryLakeCount": 621, "evaluatedLakeCount": 5}, None)
    assert out[f"health/brains/{INTELLIGENCE}/status"] == "HEALTHY"                 # never the lifecycle
    assert out[f"health/brains/{INTELLIGENCE}/lakesPublished"] == 621 and out[f"health/brains/{INTELLIGENCE}/evaluatedLakes"] == 5
    assert out[f"health/brains/{INTELLIGENCE}/lastRun"] is None
    assert set(INTELLIGENCE_HEALTH_DOMAIN_CHILDREN) <= set(HM.SPECS[INTELLIGENCE]["registryChildren"])


def test_every_child_the_legacy_writer_builds_is_either_derived_or_retired():
    sys.path.insert(0, os.path.join(REPO, "brains", "sector-intelligence", "tests"))
    sys.path.insert(0, os.path.join(REPO, "brains", "sector-intelligence", "runtime"))
    import intelligence_support as S
    legacy = set(S.run_updates()[f"/health/brains/{INTELLIGENCE}"]) | {"staleInputs", "notRegisteredInputs", "evaluationErrors", "latestError"}
    spec = HM.SPECS[INTELLIGENCE]
    assert legacy <= set(spec["registryChildren"]) | set(spec["retireChildren"]), legacy - set(spec["registryChildren"]) - set(spec["retireChildren"])


def test_the_publisher_registry_no_longer_authorises_intelligence_health_paths():
    from sector_brain_platform.publisher import default_registry
    reg = default_registry()
    path = f"/health/brains/{INTELLIGENCE}/status"
    assert not any(reg.authorizing_family(sp, path, delete=False) is not None for sp in (reg.spec(s) for s in reg.schemas_for(INTELLIGENCE)))
