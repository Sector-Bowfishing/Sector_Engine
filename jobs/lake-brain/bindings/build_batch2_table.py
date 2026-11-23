#!/usr/bin/env python3
"""Build the Lake Brain batch 2 bindings table: excluded research-bound lakes that passed the 2026-11-22 Mac mini re-check.

    python3 jobs/lake-brain/bindings/build_batch2_table.py [--check]

Writes (deterministically; no network):
    jobs/lake-brain/data/bindings.batch2.v1.json   one MACHINE_VERIFIED record per batch 2 lake, same record shape as
                                                   bindings.proposed.v1.json (live, history, plan, dam, context, verification)
                                                   plus verification.batch2Check, the 2026-11-22 check evidence for that lake

Batch 2 = the lakes in jobs/lake-brain/data/batch2/checks_2026-11-22.csv (the per-lake evidence, one row per lake). Those lakes are in
bindings.proposed.v1.excluded.json (coordinate flag, wave-1 flag, post-hoc status or history/live mismatch) and were re-checked on
2026-11-22 against fresh readings with the binding-review-v1 machine checks, the two-gauge comparison and the history checks
(Sector_Ops #51 comments 7074433014 and 7075462499). Records are built with build_bindings_table.build_record from the same research
inputs; FIXES below corrects the series the re-check found wrong (guide curve or rule curve instead of the observed level, or a history
series that stopped). A record becomes REVIEWED only through jobs/lake-brain/data/accepted_batch2.json.
"""
from __future__ import annotations

import argparse
import collections
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_bindings_table as B  # noqa: E402

OUT = os.path.join(B.OUT_DIR, "bindings.batch2.v1.json")
CHECKS = os.path.join(B.OUT_DIR, "batch2", "checks_2026-11-22.csv")
CHECK_DATE = "2026-11-22"
SOURCE = "2026-11-22 batch 2 re-check (Sector_Ops #51)"

# Series corrections found by the 2026-11-22 re-check. Same pattern as the 2026-11-21 dry-run fixes in bindings.proposed.v1.json.
FIXES = {
    "Logan Martin|AL": {
        "live0": {"series": "LoganMartin.Elev.Inst.1Hour.0.Raw-APCO",
                  "note": f"USACE CWMS SAM observed (Alabama Power raw; was GC-APCO guide curve) [{SOURCE}]"},
        "history": [{"kind": "cwmsDaily", "office": "SAM", "series": "LoganMartin.Elev.Inst.1Hour.0.Raw-APCO"}],
        "historyNote": "live series LoganMartin.Elev.Inst.1Hour.0.GC-APCO was Alabama Power's guide curve; now "
                       "LoganMartin.Elev.Inst.1Hour.0.Raw-APCO (2026-11-22: 462.70 ft vs guide 462.44 ft); history the same observed series",
    },
    "Weiss|AL": {
        "live0": {"series": "Weiss.Elev.Inst.1Hour.0.Raw-APCO",
                  "note": f"USACE CWMS SAM observed (Alabama Power raw; was GC-APCO guide curve) [{SOURCE}]"},
        "historyNote": "live series Weiss.Elev.Inst.1Hour.0.GC-APCO was Alabama Power's guide curve; now Weiss.Elev.Inst.1Hour.0.Raw-APCO "
                       "(2026-11-22: 561.73 ft vs guide 561.43 ft), the series history already used",
    },
    "East Lynn Lake|WV": {
        "history": [{"kind": "cwmsDaily", "office": "LRH", "series": "EastLynn-Lake.Elev.Inst.15Minutes.0.OBS"}],
        "historyNote": "history was EastLynn-Lake.Elev.Inst.1Day.0.RUL (rule curve); now the observed EastLynn-Lake.Elev.Inst.15Minutes.0.OBS, "
                       "the same series as live (as for Sutton, Bluestone and the other LRH lakes on 2026-11-21)",
    },
    "Rend Lake|IL": {
        "history": [{"kind": "cwmsDaily", "office": "MVS", "series": "Rend Lk-Big Muddy.Elev.Inst.~1Day.0.datman-rev"}],
        "historyNote": "history was Rend Lk-Big Muddy.Elev.Inst.~1Day.0.MVDhist-rev, which stops in 2024-07; now the continuing daily "
                       "datman-rev series (from 1971). Over the last 71 days it reads +0.55 ft (max 0.61 ft) above the live lrgsShef-raw series",
    },
}

# Review of #222 (2026-11-22): lakes the re-check passed but that are HELD out of batch 2 until the Mac mini checks them with live data.
# Their rows stay in checks_2026-11-22.csv with result HOLD (the evidence is kept); they get no record and are not accepted.
LIVE = "2026-11-22 Mac mini live checks (Sector_Ops #51 comment 7085401013; research folder batch2-live-checks-2026-11-22)"
HOLD = {
    "Lake Mattamuskeet|NC": "history reads a different site and parameter (USGS 0208458893 00062) from live (020845889205 62615) and the lake "
                            "has no full pool, so checks R7 and d do not apply; to batch 3 once the history/live relation is checked",
    "Blue Marsh Lake|PA": "check (b) FAIL: datum mix, live NAVD88 minus NGVD29 (fallback and Rev-DCP history) = -0.74 ft, sd 0.00, 2,877 pairs over "
                          "61 days, a constant shift (Beltzville was 0.66 ft); for batch 3: apply -0.74 ft to the NGVD29 fallback and history "
                          f"({LIVE})",
    "Lake Darling|ND": "check (b) FAIL (pre-registered rule: any check-(b) FAIL is held out): NWS DARN8 fallback reads +1.06 ft above the dam "
                       "series at every matched time over 7 days; the CWMS fallback agrees exactly (0.00), so DARN8 is on another datum. "
                       f"Options: drop DARN8 as a fallback or give it a -1.06 ft offset ({LIVE})",
    "Rend Lake|IL": "check (b) FAIL (pre-registered rule): NWS RNDI2 fallback reads +0.55 ft above the live CWMS lrgsShef-raw series at every "
                    "matched time, and the datman-rev history is also +0.55 ft above it; two series agree with each other and not with live, so "
                    f"the live -raw series probably reads 0.55 ft low. Decide which Rend Lake series is right before release ({LIVE})",
}

# Measured history offsets (review of #222). `offsetFt` is ADDED to the history reading so it lines up with live (the convention of
# usgsDaily / hadsDaily offsets). The basis of each value goes in the history entry's `note`, as the datum-offset rows already do.
# The runner applies offsetFt once for every provider (#229, LakeHistoryOffsets).
HISTORY_OFFSETS = {
    "Lake Washington|WA": {
        "index": 0, "series": "LWSC.Elev-Lake.Inst.1Hour.0.NWSRADIO-RAW", "offsetFt": 0.36,
        "note": "history/live offset +0.36 ft: 1874-day mean difference, sd 0.08 ft (research comparator; the value had leaked into the "
                "series id as '(+0.36ft over 1874d, sd 0.08)'). Sign confirmed by the 2026-11-22 Mac mini live check: live minus history "
                "= +0.44 ft, sd 0.06, 1,369 hourly pairs 2026-06-18..08-17 (post-hoc window: the history series stopped on 2026-08-17; "
                "Sector_Ops #51 comment 7085401013). +0.36 kept pending the owner's choice between the long-run and the recent mean",
    },
    "Devils Lake|ND": {
        "index": 0, "offsetFt": 1400.00,
        "note": "gage height + site altitude (datum offset), corrected from 1401.33 to 1400.00: with 1401.33 the history read 1.33 ft above "
                "live on 30 matching days (sd 0.02) in the 2026-11-22 Mac mini live check (Sector_Ops #51 comment 7085401013)",
    },
    "Toledo Bend Reservoir|TX": {
        "index": 0, "offsetFt": -0.18,
        "note": "history/live offset -0.18 ft: two-gauge check, live 312914093422701 (62615, NAVD88) minus USGS 08025350 (62614, NGVD29), "
                "n=9, mean -0.178 ft, sd 0.0995 ft (VDatum -0.285 ft; Sector_Ops #51 comment 7076370263, "
                "docs/cortex/sessions/2026-11-22-depth-datum-verification.md)",
    },
}

CRITERIA = ("binding-review-v1 R1-R9 + dry-run checks b/c/d (check b on live fallbacks run 2026-11-22: any FAIL held out); R9 counts only "
            "an independent second gauge (the same gauge read through another endpoint is not R9); 15 ft history/live series rule run "
            "2026-11-22 on the Mac mini: 4 lakes flagged as written with history and live the same series (owner decision: keep in, 2026-11-23, Sector_Ops #51 comment 7089961733)")


def apply_history_offset(rec: dict, spec: dict) -> None:
    h = rec["history"][spec["index"]]
    if "series" in spec:
        h["series"] = spec["series"]
    h["offsetFt"] = spec["offsetFt"]
    h["note"] = f"{spec['note']} [{SOURCE}, review of #222]"


def summarize(records: list[dict]) -> dict:
    by_provider = collections.Counter(r["provider"] for r in records)
    hist = collections.Counter(r["historyClass"] for r in records)
    reasons = collections.Counter(p for r in records for p in (r["verification"]["batch2Check"]["excludedFor"] or "").split(";") if p)
    return {"records": len(records), "byProvider": dict(sorted(by_provider.items())), "history": dict(sorted(hist.items())),
            "excludedForAnyReason": dict(sorted(reasons.items())), "seriesFixes": sorted(f for f in FIXES if f not in HOLD),
            "historyOffsets": sorted(f for f in HISTORY_OFFSETS if f not in HOLD), "held": sorted(HOLD)}


CHECK_FIELDS = ["checkedAt", "value", "observedAt", "ageH", "median30", "median30MinusFullPool", "gaugePosition", "distToOutlineKm",
                "R6", "R7", "b_fallback", "secondSource", "c_history", "d_reference", "seriesCheck", "excludedFor", "fetchedFrom"]


def num_or_str(v: str):
    if v in ("", None):
        return None
    try:
        f = float(v)
        return round(f, 2)
    except ValueError:
        return v


def load_checks() -> dict[str, dict]:
    rows = {}
    for r in csv.DictReader(open(CHECKS, newline="")):
        assert r["result"] == "PASS" or (r["result"] == "HOLD" and r["lakeId"] in HOLD), f"{r['lakeId']}: batch 2 lists only PASS or HOLD rows"
        assert r["lakeId"] not in rows, f"{r['lakeId']} listed twice"
        rows[r["lakeId"]] = r
    return rows


def apply_fix(rec: dict, fix: dict) -> None:
    if "live0" in fix:
        rec["live"][0].update(fix["live0"])
        rec["series"] = rec["live"][0]["series"]
    if "history" in fix:
        rec["history"] = fix["history"]
    rec["historyNotes"] = list(rec["historyNotes"]) + [f"{fix['historyNote']} [{SOURCE}]"]


def build() -> dict:
    inp = B.Inputs()
    checks = load_checks()
    rows = {r["lake_id"]: r for r in inp.v2}
    excluded = {r["lake_id"] for r, _ in B.classify_lakes(inp)[1]}
    records = []
    assert {l for l, c in checks.items() if c["result"] == "HOLD"} == set(HOLD), "HOLD rows and HOLD must agree"
    for lake in sorted(checks):
        if lake in HOLD:
            continue
        assert lake in rows, f"{lake}: no research row"
        assert lake in excluded, f"{lake}: not an excluded lake (batch 2 is only excluded lakes)"
        rec, _ = B.build_record(inp, rows[lake])
        assert rec is not None, f"{lake}: no live ref for {rows[lake]['provider']} {rows[lake]['series_or_param']} (needs a new provider)"
        if lake in FIXES:
            apply_fix(rec, FIXES[lake])
        if lake in HISTORY_OFFSETS:
            apply_history_offset(rec, HISTORY_OFFSETS[lake])
        c = checks[lake]
        live0 = rec["live"][0]
        assert (live0["provider"], live0["station"]) == (c["provider"], c["station"]) or lake in FIXES, f"{lake}: record/check mismatch"
        rec["verification"]["batch2Check"] = {k: num_or_str(c.get(k, "")) for k in CHECK_FIELDS} | {
            "result": c["result"], "criteria": CRITERIA,
            "approvalRef": "sector-ops-51-7075462499"}
        records.append(rec)
    return {
        "schema": B.SCHEMA, "bindingStatus": B.STATUS, "criteriaVersion": B.CRITERIA_VERSION, "batch": 2,
        "note": "MACHINE_VERIFIED, NOT REVIEWED. Generated by jobs/lake-brain/bindings/build_batch2_table.py. Excluded research-bound lakes "
                "that passed the 2026-11-22 re-check (jobs/lake-brain/data/batch2/checks_2026-11-22.csv). A binding becomes REVIEWED only by "
                "listing its lakeId in jobs/lake-brain/data/accepted_batch2.json.",
        "researchDate": "2026-10-13", "checkDate": CHECK_DATE,
        "inputs": {k: {"sha256": B.sha256(p)} for k, p in sorted(inp.files.items())} | {"checks_2026-11-22.csv": {"sha256": B.sha256(CHECKS)}},
        "counts": summarize(records),
        "bindings": records,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="build in memory and fail if the committed file differs")
    args = ap.parse_args(argv)
    doc = build()
    text = json.dumps(doc, indent=1, sort_keys=False, ensure_ascii=False) + "\n"
    if args.check:
        ok = os.path.exists(OUT) and open(OUT).read() == text
        print("batch 2 table up to date" if ok else "batch 2 table differs from a fresh build")
        return 0 if ok else 1
    with open(OUT, "w") as f:
        f.write(text)
    print(f"batch 2: {doc['counts']['records']} records -> {os.path.relpath(OUT, B.REPO)}")
    print("  by provider:", doc["counts"]["byProvider"], " history:", doc["counts"]["history"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
