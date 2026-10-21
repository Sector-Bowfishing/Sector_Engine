import os

import pytest
from datetime import datetime, timezone

NOW = datetime(2026, 10, 13, 19, 0, tzinfo=timezone.utc)


def lake_state(elev=593.6, obs="2026-10-13T18:00:00Z", datum="NGVD29", cap="DIRECT_OPERATOR_POOL", kind="OBSERVED", diff=None, unit="ft", stale=False):
    s = {"kind": kind, "sourceCapability": cap, "currentElevationFt": elev, "unit": unit, "observationTime": obs,
         "freshness": {"stale": stale}, "provenance": {"brainVersion": "1.0.0"}}
    if datum is not None:
        s["datum"] = datum
    if diff is not None:
        s["differenceFromNormalPoolFt"] = diff
    return s


def candidate(pool=595.0, conf="high", basis="fullPool", status="SAME_DATUM", sigma=0.1, tier="UNKNOWN", possible=True, level_datum="NGVD29", **kw):
    rec = {"lakeId": kw.pop("lakeId", "Guntersville|AL"), "shiftPossible": possible, "rollout": "PILOT_VERIFIED",
           "reference": {"poolFt": pool, "basis": basis, "confidence": conf, "datum": "NGVD29", "source": "engine-directory:fullPoolFt"},
           "levelSource": {"status": "LIVE_REVIEWED", "datum": level_datum},
           "datum": {"status": status, "sigmaFt": sigma}, "evidence": {"tier": tier, "kind": "unknown"}}
    rec.update(kw)
    return rec


def research_file(*parts):
    """A file of the Depth research dataset snapshot ($DEPTH_RESEARCH_DATA; never in the repository). Absent -> the test is skipped."""
    root = os.environ.get("DEPTH_RESEARCH_DATA")
    p = os.path.join(root, *parts) if root else None
    if not p or not os.path.exists(p):
        pytest.skip(f"research dataset file {'/'.join(parts)} not available (set DEPTH_RESEARCH_DATA)")
    return p
