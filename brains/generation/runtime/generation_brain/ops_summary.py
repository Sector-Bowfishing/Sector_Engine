"""Engine-side Ops summary for the Generation registry node (`/brains/generation`). Pure; every number is computed from the dam catalog, the
source-access list and the run itself. Generation publishes no score."""
from __future__ import annotations

from collections import Counter

from . import contract as C
from .state import readiness_of


def coverage(catalog: dict, access: dict) -> dict:
    dams = catalog["dams"]
    readable = sum(1 for d in dams if readiness_of(d, access) == "CALIBRATION")
    return {"directoryLakeCount": catalog.get("directoryLakeCount"), "noDamLakeCount": catalog.get("noDamLakeCount"), "damLakeCount": len(dams),
            "readableNow": readable, "byGroup": dict(sorted(Counter(d["group"] for d in dams).items())),
            "byCoverage": dict(sorted(Counter(d["coverage"] for d in dams).items())),
            "byReadiness": dict(sorted(Counter(readiness_of(d, access) for d in dams).items()))}


def registry_extras(catalog: dict, access: dict, run: dict | None = None, release: dict | None = None) -> dict:
    cov = coverage(catalog, access)
    pend = cov["byCoverage"].get("DISCOVERY_PENDING", 0)
    blockers = [
        f"{pend} dam lakes have an allowed official source whose release series is not yet bound (CWMS / RISE / TVA probe pass)",
        f"{cov['byCoverage'].get('BOUND_ACCESS_CHECK', 0)} SWPA lakes wait on the energy.gov robots.txt / terms check",
        f"{cov['byCoverage'].get('PERMISSION_REQUIRED', 0)} dam lakes are run by operators that publish only on their own pages (permission first)",
        "Knowledge release not approved; validation (week-long schedule comparison) not started; not scheduled",
    ]
    return {
        "directoryLakeCount": cov["directoryLakeCount"],
        "fleet": cov,
        "breakdowns": {"group": cov["byGroup"], "coverage": cov["byCoverage"], "readiness": cov["byReadiness"]},
        "sourceIds": sorted(p for p, a in access.items() if a.get("status") == "ALLOWED"),
        "sourceAccess": {p: {"agency": a.get("agency"), "status": a.get("status")} for p, a in sorted(access.items())},
        "knowledgeRelease": release,
        "catalogVersion": catalog.get("catalogVersion"),
        "lastRun": run,
        "orchestration": {"status": "DISABLED", "registered": True, "scheduled": False,
                          "note": "registered in the control manifest PARKED with no execution target; execution control off"},
        "primaryBlocker": blockers[0],
        "blockers": blockers,
        "statusBasis": (f"Calibration: {cov['readableNow']} of {cov['damLakeCount']} dam lakes readable now from bound, allowed official sources; "
                        f"{cov['noDamLakeCount']} directory lakes have no dam. Not validated, not scheduled, no score."),
    }
