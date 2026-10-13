#!/usr/bin/env python3
"""Lake Brain binding pipeline (research, read-only). Automates the 'probed and reviewed by hand' step of LAKE_BRAIN_INTEGRATION s5.

  candidate (catalogs + spatial/name matcher) -> machine probe (live data queries) -> review criteria (binding-review-v1)
  -> history completeness -> chosen binding per lake -> spot-check -> summary

Usage:
  python research/lake-brain/binding_pipeline.py --list
  python research/lake-brain/binding_pipeline.py --stage all          # full rebuild (network: ~1.5 h, polite rate limits)
  python research/lake-brain/binding_pipeline.py --stage verify finalize spotcheck summary   # re-run offline from cached probes
Environment: LB_DATA (default ~/Desktop/Development/Sector_Research_Data/lake-brain). Bulk data never goes in Git.
Requires: python3 with shapely and numpy (pip install shapely numpy).
GET-only against public APIs; no credentials; writes only under $LB_DATA/binding.
"""
import argparse, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
B = os.path.join(HERE, "binding")
STAGES = [
    ("fetch_misc", "fetch_misc.py", "USGS NWIS per-state site/series catalogs, TWDB, NWPS, CO-OPS, TVA locations"),
    ("fetch_cwms", "fetch_cwms.py", "USACE CWMS Data API catalogs (locations + level timeseries) for every office"),
    ("fetch_a2w", "fetch_a2w.py", "USACE Access2Water reporting API: projects, latest pool, operator levels, NIDID"),
    ("fetch_rise", "fetch_rise.py", "Reclamation RISE locations + level catalog items"),
    ("fetch_rise_records", "fetch_rise_records.py", "RISE item -> location mapping"),
    ("fetch_nid", "fetch_nid.py", "National Inventory of Dams (hosted FeatureServer)"),
    ("catalog", "build_catalog.py", "normalise USGS/CWMS/A2W/RISE/TWDB/NWPS/CO-OPS/TVA series into catalog.jsonl"),
    ("match", "match.py", "spatial + name + type + state + operator candidate scoring"),
    ("probe", "probe.py", "live probe: last observation, age, 30-day median per candidate"),
    ("verify", "verify.py", "apply review criteria R1-R9 (binding-review-v1)"),
    ("history", "history.py", "daily-value history and year completeness (>=90% days per year)"),
    ("nid", "nid_link.py", "lake -> dam via NID"),
    ("finalize", "finalize.py", "choose binding per lake, write verified.csv + committed summaries"),
    ("spotcheck", "spotcheck.py", "independent stratified spot-check"),
    ("summary", "assemble_summary.py", "cross-validation / trap / NID / pilot blocks in binding_summary.json"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--stage", nargs="*", default=[])
    a = ap.parse_args()
    if a.list or not a.stage:
        for n, f, d in STAGES:
            print(f"{n:20s} {f:24s} {d}")
        return
    todo = [s for s in STAGES if "all" in a.stage or s[0] in a.stage]
    for n, f, d in todo:
        print(f"== {n}: {d}", flush=True)
        r = subprocess.run([sys.executable, os.path.join(B, f)], cwd=B)
        if r.returncode:
            sys.exit(f"stage {n} failed ({r.returncode})")


if __name__ == "__main__":
    main()
