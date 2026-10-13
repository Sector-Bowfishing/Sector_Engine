#!/usr/bin/env python3
"""Lake Brain production-readiness PROJECTIONS (docs/brains/LAKE_BRAIN_PRODUCTION_READINESS_MATRIX.md).

Runs the real, unmodified rubric code (jobs/brain_platform/sector_brain_platform/scoring.py::score_lake, rubric
docs/brains/scoring/lake-brain-score-v1.json) over SYNTHETIC facts derived from the proposed bindings table
(jobs/lake-brain/data/bindings.proposed.v1.json). It publishes nothing, reads no network, and changes no status:
every number is a projection that assumes the stated hypothesis (accepted batch, validation status).

  python3 jobs/lake-brain/readiness/project_scores.py            # prints the scenario table as JSON
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "jobs", "brain_platform"))
from sector_brain_platform.scoring import score_lake  # noqa: E402

BINDINGS = os.path.join(REPO, "jobs", "lake-brain", "data", "bindings.proposed.v1.json")
DIRECTORY = 621
# The five REVIEWED pilots are hand-written bindings, not generated rows. Published live (2026-10-13): the four TVA pilots have a guide curve + zone
# and 16-18 complete years (SUFFICIENT) even though the generated table (research history) says NONE for them; Hartwell has a CWMS guide + flood-pool bottom.
PILOT_HISTORY_SUFFICIENT = {"Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN"}


def lake_facts(row: dict) -> tuple[dict, dict]:
    """(profile, state) of one lake as the Brain would publish it if its binding were REVIEWED."""
    plan = row.get("plan") or {}
    roles = {lv["role"] for lv in plan.get("levels", [])}
    has_guide = "guideCurve" in roles
    has_zone = {"zoneTop", "zoneBottom"} <= roles
    has_flood = "floodPoolBottom" in roles
    hist = row["historyClass"]
    if row["lakeId"] in PILOT_HISTORY_SUFFICIENT:
        hist = "SUFFICIENT"
    profile = {"sourceCapability": {"level": row["capability"]},
               "operatingPools": {"guideCurve": {"available": has_guide}, "operatingZoneSource": "zone" if has_zone else None},
               "historicalCoverage": {"baselineStatus": hist}}
    state = {"kind": "OBSERVED", "floodPoolState": "NORMAL" if has_flood else "UNKNOWN"}
    return profile, state


def score(rows: list[dict], validation: str, directory: int = DIRECTORY, health: str = "HEALTHY") -> dict:
    profiles, states = {}, {}
    for r in rows:
        p, s = lake_facts(r)
        profiles[r["lakeId"]], states[r["lakeId"]] = p, s
    facts = {"registry": {"health": health, "directoryLakeCount": directory}, "validation": {"status": validation},
             "health": {"status": health}, "profiles": profiles, "states": states, "directoryLakeCount": directory}
    return score_lake(facts, dt.datetime(2026, 10, 13, tzinfo=dt.timezone.utc))


def summary(sc: dict) -> dict:
    b = sc["scoreBreakdown"]
    return {"displayed": sc["value"], "uncapped": sc["uncapped"], "dims": {k: v["value"] for k, v in b.items()},
            "gates": [g["gate"] + f"<={g['cap']}" for g in sc["scoreBlockers"] if "cap" in g]}


WEIGHTS = {"sourceAuthority": 15, "operatorPlan": 10, "historyQuality": 15, "seasonalBaseline": 10, "trendQuality": 10,
           "floodDroughtContext": 5, "validation": 15, "coverage": 20}


def from_counts(n: int, counts: dict[str, int], validation: str, directory: int = DIRECTORY) -> dict:
    """What-if arithmetic with the rubric's own functions: `counts` are lakes (of `n` profiled) per share dimension
    (sourceAuthority, operatorPlan, historyQuality, seasonalBaseline, trendQuality, floodDroughtContext). Returns dim values (rounded to 0.1
    as the rubric does), the uncapped sum, and the displayed value with the validation gate. No lake data involved."""
    from sector_brain_platform.scoring import ladder
    dims = {k: round(10.0 * counts[k] / n, 1) for k in ("sourceAuthority", "operatorPlan", "historyQuality", "seasonalBaseline", "trendQuality", "floodDroughtContext")}
    dims["validation"] = {"NOT_VALIDATED": 0, "PARTIAL": 5, "VALIDATED": 10}[validation]
    dims["coverage"] = ladder(n / directory)
    uncapped = round(sum(dims[k] * WEIGHTS[k] for k in WEIGHTS) / 100.0, 1)
    cap = 5.0 if validation == "NOT_VALIDATED" else 10.0
    if n / directory < 0.10:
        cap = min(cap, 3.0)
    return {"dims": dims, "uncapped": uncapped, "displayed": round(min(uncapped, cap), 1)}


def main() -> int:
    d = json.load(open(BINDINGS))
    rows = d["bindings"]
    out = {"lakes": len(rows)}
    for v in ("NOT_VALIDATED", "PARTIAL", "VALIDATED"):
        out[v] = summary(score(rows, v))
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
