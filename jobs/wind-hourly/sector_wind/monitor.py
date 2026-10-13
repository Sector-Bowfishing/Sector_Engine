"""Live-shadow milestone checks (Stage 3 Milestone A at 14 days, B at 30 days).

Reads the archive (local mirror or GCS) and reports, for a window:
  - hourly NBM cycle and RTMA-RU :00 completeness per lake (rubric dim 8: >= 99%)
  - median and 95th-percentile availability age = retrievedAt - initTime (dim 8: median <= 90 min)
  - partial cycles, decoder self-check failures and other run errors (no silent failures)
  - schema stability (every object carries sector-wind-cycle-v1)
  - time-leak sanity: nothing retrieved before it could have been published
  - fallback evidence: runs that used catch-up (an earlier cycle re-ingested later)
It does NOT score holdout field data and never changes anything."""
from __future__ import annotations

import statistics
from datetime import datetime, timedelta, timezone

from . import SCHEMA
from .sample import parse_iso

NBM_EARLIEST_POST_MIN = 45   # measured ~57 min; anything earlier would be impossible (time leak)


def milestone(store, cfg: dict, start: datetime, end: datetime) -> dict:
    lakes = list(cfg["lakes"])
    hours = [start + timedelta(hours=h) for h in range(int((end - start).total_seconds() // 3600) + 1)]
    out = {"window": [start.isoformat(), end.isoformat()], "hours": len(hours), "lakes": {}, "problems": []}
    ages, partial, schema_bad, leaks = [], 0, 0, 0
    for lake in lakes:
        got_nbm = got_rtma = 0
        for t in hours:
            c = store.get_json(f"nbm/{lake}/{t:%Y%m%d%H}.json.gz")
            if c:
                got_nbm += 1
                schema_bad += c.get("schema") != SCHEMA
                partial += c.get("status") != "complete"
                age = (parse_iso(c["retrievedAt"]) - parse_iso(c["initTime"])).total_seconds() / 60
                ages.append(age)
                leaks += age < NBM_EARLIEST_POST_MIN
            got_rtma += store.exists(f"rtma/{lake}/{t:%Y%m%d}/{t:%H%M}.json.gz")
        out["lakes"][lake] = {"nbmShare": got_nbm / len(hours), "rtmaShare": got_rtma / len(hours)}
    runs = [k for k in store.list("runs/") if start.strftime("%Y%m%d") <= k.split("/")[1] <= end.strftime("%Y%m%d")]
    errs, catchups = 0, 0
    for k in runs:
        r = store.get_json(k)
        if r and r.get("errors"):
            errs += 1
            out["problems"].append({"run": k, "errors": r["errors"][:3]})
        if r and len(r.get("nbm", {})) > 1:
            catchups += 1
    out.update({
        "nbmAvailabilityAgeMin": {"median": statistics.median(ages) if ages else None,
                                  "p95": sorted(ages)[int(0.95 * (len(ages) - 1))] if ages else None},
        "partialCycles": partial, "schemaMismatches": schema_bad, "timeLeakSuspects": leaks,
        "runs": len(runs), "runsWithErrors": errs, "runsUsingCatchup": catchups,
    })
    worst = min(min(v["nbmShare"], v["rtmaShare"]) for v in out["lakes"].values()) if out["lakes"] else 0
    out["gate"] = {"completeness>=99%": worst >= 0.99,
                   "medianAge<=90min": bool(ages) and statistics.median(ages) <= 90,
                   "noSchemaDrift": schema_bad == 0, "noTimeLeak": leaks == 0,
                   "fallbacksExercised": catchups > 0}
    return out
