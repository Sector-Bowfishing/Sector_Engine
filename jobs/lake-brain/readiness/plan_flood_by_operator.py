#!/usr/bin/env python3
"""Operator plan / flood-pool evidence by operator group (docs/brains/LAKE_BRAIN_OPERATOR_PLAN_FLOOD_EVIDENCE.md). READ-ONLY analysis.

Inputs: the committed proposed bindings table (196 lakes) and, optionally, the research evidence table `plan_flood_evidence.csv`
(research branch origin/docs/lake-brain-research:docs/research/lake-brain/data/plan_flood_evidence.csv). It adds no evidence to any profile.

  git show origin/docs/lake-brain-research:docs/research/lake-brain/data/plan_flood_evidence.csv > /tmp/pfe.csv
  python3 jobs/lake-brain/readiness/plan_flood_by_operator.py --evidence /tmp/pfe.csv
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
BINDINGS = os.path.join(REPO, "jobs", "lake-brain", "data", "bindings.proposed.v1.json")
LOWER_POOL_LABELS = ("Top of Inactive", "Bottom of Power", "Minimum", "Bottom of Operating", "Top of Power")   # documented lower-pool levels, NOT a zone bottom under the strict rule


def operator_group(name: str | None) -> str:
    n = name or "unknown"
    if n in ("US Army Corps of Engineers", "USACE"):
        return "USACE"
    if n in ("Bureau of Reclamation", "USBR"):
        return "USBR"
    if n == "Tennessee Valley Authority":
        return "TVA"
    return "non-federal: " + n


def analyse(bindings: list[dict], evidence: dict[str, dict] | None = None) -> dict:
    evidence = evidence or {}
    by_group: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    flood_only_lower = []
    unmatched: dict[str, list[str]] = collections.defaultdict(list)
    tier2 = []
    for x in bindings:
        plan = x.get("plan") or {}
        roles = {lv["role"] for lv in plan.get("levels", [])}
        has_plan = bool(plan.get("planStrict"))
        has_flood = bool(plan.get("floodStrict"))
        g = operator_group((x.get("dam") or {}).get("operatorName"))
        c = by_group[g]
        c["lakes"] += 1
        c["plan"] += has_plan
        c["flood"] += has_flood
        c["both"] += has_plan and has_flood
        c["neither"] += not (has_plan or has_flood)
        e = evidence.get(x["lakeId"], {})
        if has_flood and not has_plan and any(lbl in (e.get("levelLabels") or "") for lbl in LOWER_POOL_LABELS):
            flood_only_lower.append(x["lakeId"])
        if not plan.get("verifiedMatch"):
            unmatched[g].append(x["lakeId"])
        if e.get("tier2Source") and not (has_plan and has_flood):
            tier2.append((x["lakeId"], e["tier2Source"], e.get("tier2Flood"), e.get("tier2Zone")))
    return {"byGroup": {g: dict(c) for g, c in by_group.items()}, "floodOnlyWithLowerPoolLevel": sorted(flood_only_lower),
            "noVerifiedOperatorMatch": {g: sorted(v) for g, v in unmatched.items()}, "tier2OnLakesLackingBoth": tier2}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--evidence", default=None, help="research plan_flood_evidence.csv (optional)")
    a = ap.parse_args()
    ev = {r["lakeId"]: r for r in csv.DictReader(open(a.evidence))} if a.evidence else {}
    rows = json.load(open(BINDINGS))["bindings"]
    out = analyse(rows, ev)
    out["lakes"] = len(rows)
    print(json.dumps(out, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
