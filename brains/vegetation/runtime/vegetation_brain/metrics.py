"""Fleet metrics computed from the fleet manifest and the run only (counts and shares, no judgment). Used by the Ops summary.

The research maturity RUBRIC that used to sit next to these numbers is offline research tooling (research/tools/vegetation_research/maturity.py):
Vegetation publishes no maturity number and no score; the shared scorer is the only score authority and has no Vegetation entry."""
from __future__ import annotations


def fleet_metrics(manifest: dict, observed_lakes: int = 0, truth_backed_lakes: int | None = None) -> dict:
    c = manifest["candidates"]
    n = len(c)
    tiers = {t: sum(1 for x in c if x["tier"] == t) for t in ("HIGH", "MEDIUM", "LOW", "UNKNOWN")}
    return {"totalLakes": n, "observableLakes": tiers["HIGH"] + tiers["MEDIUM"], "tiers": tiers,
            "observedLakes": observed_lakes, "observedShare": round(observed_lakes / n, 4) if n else 0.0,
            "truthBackedLakes": observed_lakes if truth_backed_lakes is None else truth_backed_lakes,
            "truthBackedShare": round((observed_lakes if truth_backed_lakes is None else truth_backed_lakes) / n, 4) if n else 0.0,
            "withIndependentTruth": sum(1 for x in c if x.get("groundTruth")), "manifestVersion": manifest.get("manifestVersion")}
