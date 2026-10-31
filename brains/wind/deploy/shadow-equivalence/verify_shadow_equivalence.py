#!/usr/bin/env python3
"""Verify a Wind shadow-equivalence window (PREPARED 2026-10-31). Read-only: it reads digest-only evidence records and prints one verdict.

  python verify_shadow_equivalence.py --evidence DIR [--config shadow-equivalence-7day.json] [--until 2026-11-08T00:00:00Z]
  python verify_shadow_equivalence.py --bucket B ...      (reads exports/shadow-equivalence/wind/ with the caller's read-only identity)

Verdict: PASS (window long and dense enough, every run equivalent, only the allowed compatibility rules open), FAIL (any non-equivalent or error run,
or an unexpected open rule), INSUFFICIENT (not enough evidence yet). Exit 0 only on PASS.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, "shadow-equivalence-7day.json")
RUN_SCHEMA = "wind-shadow-equivalence-run-v1"


def _t(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def verify(records: list, cfg: dict, until: dt.datetime | None = None) -> dict:
    w, p = cfg["window"], cfg["pass"]
    runs = sorted((r for r in records if r.get("schema") == RUN_SCHEMA and r.get("brainId") == "wind" and r.get("runAt")), key=lambda r: r["runAt"])
    ignored = len(records) - len(runs)
    if until:
        runs = [r for r in runs if _t(r["runAt"]) <= until]
    out = {"schema": "wind-shadow-equivalence-verdict-v1", "runs": len(runs), "ignoredRecords": ignored, "problems": []}
    if not runs:
        return {**out, "verdict": "INSUFFICIENT", "reason": "no evidence records"}
    first, last = _t(runs[0]["runAt"]), _t(runs[-1]["runAt"])
    span_h = (last - first).total_seconds() / 3600
    hours = {_t(r["runAt"]).replace(minute=0, second=0) for r in runs}
    expected = int(span_h) + 1
    gaps = [(b - a).total_seconds() / 3600 for a, b in zip(sorted(hours), sorted(hours)[1:])]
    out.update(first=runs[0]["runAt"], last=runs[-1]["runAt"], spanHours=round(span_h, 1), coveredHours=len(hours), coverage=round(len(hours) / expected, 3),
               maxGapHours=max(gaps, default=0))
    counts: dict = {}
    for r in runs:
        counts[r.get("verdict", "MISSING")] = counts.get(r.get("verdict", "MISSING"), 0) + 1
    out["verdicts"] = counts
    bad = [r for r in runs if r.get("verdict") not in p["verdictsAccepted"] + ["NO_LEGACY_WRITE"]]
    not_eq = [r for r in bad if r.get("verdict") == "NOT_EQUIVALENT"]
    errs = [r for r in bad if r.get("verdict") != "NOT_EQUIVALENT"]
    rules = sorted({x for r in runs for x in r.get("openCompatibilityRules") or []})
    unexpected = sorted(set(rules) - set(p["allowedOpenCompatibilityRules"]))
    out["openCompatibilityRules"] = rules
    if len(not_eq) > p["maxNotEquivalentRuns"]:
        out["problems"].append({"kind": "NOT_EQUIVALENT", "runs": [r["runAt"] for r in not_eq][:20]})
    if len(errs) > p["maxErrorRuns"]:
        out["problems"].append({"kind": "ERROR_RUNS", "runs": [r["runAt"] for r in errs][:20]})
    if unexpected:
        out["problems"].append({"kind": "UNEXPECTED_OPEN_RULES", "rules": unexpected})
    if p.get("sameCodeVersionRequired") and len({r.get("codeVersion") for r in runs}) > 1:
        out["problems"].append({"kind": "CODE_VERSION_CHANGED", "versions": sorted({str(r.get("codeVersion")) for r in runs})})
    if out["problems"]:
        return {**out, "verdict": "FAIL"}
    short = []
    if span_h < max(w["minContinuousHours"], 24 * w["minDays"]) - 1:
        short.append(f"span {span_h:.0f} h < {w['minContinuousHours']} h")
    if len(hours) / expected < w["minCoverage"]:
        short.append(f"coverage {len(hours) / expected:.2f} < {w['minCoverage']}")
    if out["maxGapHours"] > w["maxGapHours"]:
        short.append(f"gap {out['maxGapHours']:.0f} h > {w['maxGapHours']} h")
    if short:
        return {**out, "verdict": "INSUFFICIENT", "reason": "; ".join(short)}
    return {**out, "verdict": "PASS"}


def _load_dir(d):
    out = []
    for root, _, files in os.walk(d):
        for f in sorted(files):
            if f.endswith(".json"):
                with open(os.path.join(root, f), encoding="utf-8") as fh:
                    try:
                        out.append(json.load(fh))
                    except ValueError:
                        out.append({"unreadable": f})
    return out


def _load_bucket(bucket, prefix):
    sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "jobs", "brain_platform"))
    from sector_brain_platform.object_bucket import GcsRestObjectStore
    from sector_brain_platform.rtdb import TokenProvider
    s = GcsRestObjectStore(bucket, TokenProvider())
    return [json.loads(s.get(k)) for k in s.list(prefix) if k.endswith(".json")]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--evidence")
    g.add_argument("--bucket")
    ap.add_argument("--config", default=CONFIG)
    ap.add_argument("--until", default=None)
    a = ap.parse_args(argv)
    cfg = json.load(open(a.config, encoding="utf-8"))
    recs = _load_dir(a.evidence) if a.evidence else _load_bucket(a.bucket, cfg["evidencePrefix"])
    res = verify(recs, cfg, _t(a.until) if a.until else None)
    print(json.dumps(res, indent=1, sort_keys=True))
    return 0 if res["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
