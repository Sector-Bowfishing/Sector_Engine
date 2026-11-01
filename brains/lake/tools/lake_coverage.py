"""LB-14: per-lake, per-capability coverage record for the Lake Brain Beta set (Sector_Ops #43; Lake contract §3.1).

  python3 brains/lake/tools/lake_coverage.py SOURCES.csv OUT.json [--fresh-lakes FRESH.txt]

SOURCES.csv is a source-coverage table with one row per Registry lake (the columns of the Sector_Ops #34 table: lakeId, hasDam, level,
levelMissing, levelProvider, levelCurrent, checkGauge, release, inflow). The table itself is research output and is not in this repository.
FRESH.txt (optional) lists lake ids whose Lake state is published and fresh, one per line. Without it no lake is COVERED: freshness is
never assumed.

Every capability gets one status (lake.md LB-14): COVERED, ELIGIBLE_NOT_COVERED, SOURCES_UNKNOWN or NOT_APPLICABLE, with a reason code.
Applicability comes from the lake's own facts (a dam or not). Deterministic: the same inputs give the same bytes."""
import csv
import json
import sys
from collections import Counter

SCHEMA = "sector-lake-coverage-v1"
COVERED, ELIGIBLE, UNKNOWN, NA = "COVERED", "ELIGIBLE_NOT_COVERED", "SOURCES_UNKNOWN", "NOT_APPLICABLE"
CAPABILITIES = ["LB-04", "LB-07", "LB-11", "LB-09", "LB-13", "LB-08"]   # Beta set, Beta prerequisite LB-13, then KEEP LB-08
REQUIRED = {"lakeId", "hasDam", "level", "levelMissing", "levelProvider", "levelCurrent", "checkGauge", "release", "inflow"}


def _level(r, fresh):
    """LB-04 current level; LB-07 trend and LB-11 abstention follow it, since both come from the same series."""
    if r["level"] == "UNKNOWN":
        return UNKNOWN, r["levelMissing"] or "level-no-source"
    if r["levelCurrent"] == "STALE":
        return ELIGIBLE, "level-source-stale"
    if r["level"] == "PUBLISHED":
        return (COVERED, "published-fresh") if r["lakeId"] in fresh else (ELIGIBLE, "published-freshness-not-shown")
    return ELIGIBLE, "level-source-verified-not-published"


def _release(r, fresh):
    if r["hasDam"] != "True":
        return NA, "no-dam"
    if r["release"] in ("OPERATOR_OUTFLOW", "TAILWATER_GAUGE"):
        # Lake publishes release only from the level's own operator feed (TVA today), and only where that level is published and fresh.
        if r["release"] == "OPERATOR_OUTFLOW" and r["levelProvider"] == "tva" and r["level"] == "PUBLISHED" and r["lakeId"] in fresh:
            return COVERED, "operator-outflow-published"
        return ELIGIBLE, "operator-outflow-source" if r["release"] == "OPERATOR_OUTFLOW" else "tailwater-gauge-source"
    return UNKNOWN, "release-no-public-series"


def _validation(r):
    if r["level"] == "UNKNOWN":
        return UNKNOWN, "no-level-source"
    return (ELIGIBLE, "independent-gauge-recorded") if r["checkGauge"] == "CHECK_GAUGE" else (UNKNOWN, "no-independent-gauge-recorded")


def _inflow(r):
    if r["inflow"] in ("OPERATOR_INFLOW", "INFLOW_GAUGE"):
        return ELIGIBLE, "operator-inflow-source" if r["inflow"] == "OPERATOR_INFLOW" else "upstream-gauge-source"
    return UNKNOWN, "inflow-no-public-series"


def lake_record(r, fresh):
    level = _level(r, fresh)
    cov = {"LB-04": level, "LB-07": level, "LB-11": level, "LB-09": _release(r, fresh), "LB-13": _validation(r), "LB-08": _inflow(r)}
    return {"lakeId": r["lakeId"], "capabilityCoverage": {k: {"status": s, "reason": why} for k, (s, why) in cov.items()}}


def build(rows, fresh=frozenset()):
    missing = REQUIRED - set(rows[0]) if rows else REQUIRED
    if missing:
        raise ValueError(f"source table lacks columns: {sorted(missing)}")
    ids = [r["lakeId"] for r in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate lakeId in the source table")
    lakes = [lake_record(r, set(fresh)) for r in sorted(rows, key=lambda r: r["lakeId"])]
    summary = {c: dict(sorted(Counter(l["capabilityCoverage"][c]["status"] for l in lakes).items())) for c in CAPABILITIES}
    return {"schema": SCHEMA, "brainId": "lake-brain", "lakeCount": len(lakes), "capabilities": CAPABILITIES,
            "freshnessSupplied": bool(fresh), "summary": summary, "lakes": lakes}


def main(argv):
    src, out = argv[1], argv[2]
    fresh = set()
    if "--fresh-lakes" in argv:
        fresh = {l.strip() for l in open(argv[argv.index("--fresh-lakes") + 1]) if l.strip()}
    rec = build(list(csv.DictReader(open(src, newline=""))), fresh)
    with open(out, "w") as f:
        json.dump(rec, f, indent=1, sort_keys=True)
        f.write("\n")
    print(json.dumps(rec["summary"]))


if __name__ == "__main__":
    main(sys.argv)
