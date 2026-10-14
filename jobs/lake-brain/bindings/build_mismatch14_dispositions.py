#!/usr/bin/env python3
"""Apply the PRE-REGISTERED criteria (mismatch14_criteria.py) to the probe results and write mismatch14_dispositions.json.

    python3 jobs/lake-brain/bindings/build_mismatch14_dispositions.py [--check]

Inputs (all committed): jobs/lake-brain/data/mismatch14_probe_results.json (mismatch14_probe.py output), jobs/lake-brain/bindings/mismatch14_specs.json
(probe plan + per-lake operator references and the reasons for the non-FIXED dispositions). Output: jobs/lake-brain/bindings/mismatch14_dispositions.json.

A lake is FIXED only when every criterion passes; otherwise it takes the disposition its spec names (NEEDS HUMAN REVIEW / NO DEFENSIBLE MATCH /
CORRECTLY HELD). FIXED never means REVIEWED: every FIXED lake is a "newly recovered" MACHINE_VERIFIED candidate that needs human review.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import mismatch14_criteria as C  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
PROBE = os.path.join(REPO, "jobs", "lake-brain", "data", "mismatch14_probe_results.json")
SPECS = os.path.join(HERE, "mismatch14_specs.json")
OUT = os.path.join(HERE, "mismatch14_dispositions.json")
SCHEMA = "lake-brain-mismatch14-dispositions/v1"
DISPOSITIONS = ("FIXED", "CORRECTLY HELD", "NEEDS HUMAN REVIEW", "NO DEFENSIBLE MATCH")


def p1(directory_full: float | None, operator_full: float | None) -> dict:
    if directory_full is None or operator_full is None:
        return {"P1": False, "reason": "operator or directory full pool missing"}
    d = round(abs(directory_full - operator_full), 3)
    return {"P1": d <= C.POOL_TOL_FT + 1e-9, "directoryFullPoolFt": directory_full, "operatorFullPoolFt": operator_full, "diffFt": d}


def p2(live_range: dict | None, lo: float | None, hi: float | None) -> dict:
    """The live values of the window lie inside the operator's documented [min, max] +/- tolerance. An undocumented bound fails."""
    if not live_range or not live_range.get("n"):
        return {"P2": False, "reason": "no live values in window"}
    if lo is None or hi is None:
        return {"P2": False, "reason": "operator minimum or maximum pool not documented", "liveMinFt": live_range["min"], "liveMaxFt": live_range["max"]}
    ok = live_range["min"] >= lo - C.POOL_TOL_FT and live_range["max"] <= hi + C.POOL_TOL_FT
    return {"P2": ok, "liveMinFt": live_range["min"], "liveMaxFt": live_range["max"], "operatorRangeFt": [lo, hi]}


def s1(short_feed: str | None, test: dict) -> dict:
    """Short-feed rule. NWPS: the probe's s1a block. A2W: only the latest value exists, so a one-point tie can never reach SHORT_MIN_DAYS."""
    if not short_feed:
        return {"S1": True, "applies": False}
    if short_feed == "nwps":
        a = test.get("s1a") or {}
        return {"S1": bool(a.get("S1a")), "applies": True, "feed": "nwps", **{k: v for k, v in a.items() if k != "S1a"}}
    if short_feed == "a2w":
        t = test.get("a2wTie") or {}
        n = int(t.get("matchedPoints") or 0)
        return {"S1": n >= C.SHORT_MIN_DAYS, "applies": True, "feed": "a2w", "matchedDays": n,
                "singlePointDiffFt": t.get("diffFt"), "reason": "Access2Water serves only the latest value; the 20-day tie cannot be built in one session"}
    raise ValueError(short_feed)


def evaluate_lake(lake: str, spec: dict, probe: dict, directory_full: float | None) -> dict:
    dec = spec["decision"]
    tests = {t["id"]: t for t in probe["tests"]}
    test = tests[dec["test"]]
    ov = test.get("overlap") or {}
    op = dec["operator"]
    crit = {
        "O1": bool(ov.get("O1")), "O2": bool(ov.get("O2")), "O3": bool(ov.get("O3")), "O4": bool(test.get("O4")),
        **p1(directory_full, op.get("fullPoolFt")),
        **p2(test.get("liveWindowRange"), op.get("minFt"), op.get("maxFt")),
        "D1": dec["datum"]["relation"] in ("identical-by-construction", "documented"),
    }
    short = s1(dec.get("shortFeed"), test)
    crit["S1"] = short["S1"]
    gates = ("O1", "O2", "O3", "O4", "P1", "P2", "D1", "S1")
    fixed = all(crit[g] for g in gates)
    disp = "FIXED" if fixed else dec["fallback"]
    assert disp in DISPOSITIONS
    out = {
        "lakeId": lake, "disposition": disp, "classifiedOn": dec["test"],
        "criteria": {g: crit[g] for g in gates}, "failedCriteria": [g for g in gates if not crit[g]],
        "overlap": {k: ov[k] for k in ("window", "matchedDays", "medianAbsFt", "p95AbsFt", "maxAbsFt", "medianSignedFt") if k in ov},
        "history": {"last": test.get("historyLast"), "staleDays": test.get("staleDays")},
        "poolCheck": {k: v for k, v in {**p1(directory_full, op.get("fullPoolFt")), **p2(test.get("liveWindowRange"), op.get("minFt"), op.get("maxFt"))}.items()},
        "shortFeed": short, "datum": dec["datum"], "datumOffsetFt": 0.0,
        "operator": op, "qaReproduction": test.get("qaReproduction"),
        "reason": dec.get("reason") or None,
        "diagnostic": dec.get("diagnostic"),
    }
    if fixed:
        out["fixType"] = "live-series-replacement" if dec.get("correction") else "no-series-change (hold-out QA artifact; the generator's own series pass)"
        out["status"] = "MACHINE_VERIFIED_CANDIDATE"
        out["reviewRequired"] = True
        out["correction"] = dec.get("correction")
    else:
        out["correction"] = None
    return out


def build(probe_path: str = PROBE, specs_path: str = SPECS, directory: dict | None = None) -> dict:
    probe = json.load(open(probe_path))
    specs = json.load(open(specs_path))
    if directory is None:
        directory = default_directory_full()
    lakes = {}
    for lake, sp in specs["lakes"].items():
        lakes[lake] = evaluate_lake(lake, sp, probe["results"][lake], directory.get(lake))
    counts = {d: sum(1 for v in lakes.values() if v["disposition"] == d) for d in DISPOSITIONS}
    return {
        "schema": SCHEMA, "criteriaVersion": C.CRITERIA_VERSION, "runDate": C.RUN_DATE,
        "note": "FIXED = every pre-registered criterion passed. Not REVIEWED: every FIXED lake is a newly recovered MACHINE_VERIFIED candidate that needs Michael's review "
                "and must not be added to any already-built review sample or pack. Source: jobs/lake-brain/bindings/mismatch14_probe.py + mismatch14_specs.json.",
        "criteria": {"MIN_MATCHED_DAYS": C.MIN_MATCHED_DAYS, "WINDOW_DAYS": C.WINDOW_DAYS, "MEDIAN_ABS_FT": C.MEDIAN_ABS_FT, "P95_ABS_FT": C.P95_ABS_FT,
                     "HISTORY_MAX_STALE_DAYS": C.HISTORY_MAX_STALE_DAYS, "POOL_TOL_FT": C.POOL_TOL_FT, "SHORT_MIN_DAYS": C.SHORT_MIN_DAYS,
                     "SHORT_MEDIAN_FT": C.SHORT_MEDIAN_FT, "SHORT_MAX_FT": C.SHORT_MAX_FT},
        "counts": counts,
        "newlyRecovered": sorted(k for k, v in lakes.items() if v["disposition"] == "FIXED"),
        "lakes": lakes,
    }


def default_directory_full() -> dict:
    """lakeId -> directory fullPoolFt from the Swift directory (the code under test), no research checkout needed."""
    path = os.path.join(REPO, "Sources", "SectorEngine", "Support", "LakeDirectory.swift")
    out = {}
    for line in open(path):
        line = line.strip().rstrip(",")
        if line.startswith('{"name"'):
            try:
                o = json.loads(line)
            except ValueError:
                continue
            out[f"{o['name']}|{o['state']}"] = o.get("fullPoolFt")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    doc = build()
    text = json.dumps(doc, indent=1, ensure_ascii=False) + "\n"
    if args.check:
        ok = os.path.exists(OUT) and open(OUT).read() == text
        print("dispositions up to date" if ok else "dispositions differ from a fresh build")
        return 0 if ok else 1
    open(OUT, "w").write(text)
    print(json.dumps(doc["counts"]))
    for k, v in doc["lakes"].items():
        print(f"{k:28} {v['disposition']:20} failed={v['failedCriteria']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
