#!/usr/bin/env python3
"""Lake Brain operator-truth validation v1: build the FROZEN sample and truth assignment (no network, no data values).

Pre-registration: docs/brains/LAKE_BRAIN_OPERATOR_TRUTH_PREREGISTRATION.md (section 3 and 4 are implemented here, literally).
Inputs are committed metadata only: the runtime binding table (LakeSourceBindingsGenerated.swift, the records the Lake Brain runs on)
and the accepted lake lists (accepted_batch.json + accepted_batch2.json, 289 lakes). It reads no water-level value from anywhere.

usage: build_sample.py [--out sample_v1.json] [--check]
  --check  rebuild in memory and exit 1 if the committed sample differs (CI and the runner use this to prove the frozen file is the rule's output)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
GENERATED = os.path.join(ROOT, "brains", "lake", "runtime", "LakeBrain", "LakeSourceBindingsGenerated.swift")
ACCEPTED = [os.path.join(ROOT, "jobs", "lake-brain", "data", f) for f in ("accepted_batch.json", "accepted_batch2.json")]
OUT = os.path.join(HERE, "sample_v1.json")

PROTOCOL = "lake-operator-truth-v1"
SEED = "sector-lake-operator-truth-v1"
SAMPLE_SIZE = 60          # verdict sample (section 4)
TAKE_ALL_MAX = 10         # a stratum with <= 10 eligible lakes is taken whole
MIN_PER_STRATUM = 6       # every larger stratum gets at least this many
REPORT_ONLY_PER_STRATUM = 5

FAMILY = {"a2w": "CWMS", "cwms": "CWMS", "cwmsDaily": "CWMS", "usgs": "USGS", "usgsDaily": "USGS", "nwps": "NWS", "hadsDaily": "NWS",
          "rise": "USBR", "riseDaily": "USBR", "tva": "TVA", "tvaOperatingGuide": "TVA"}
RECONSTRUCTIBLE = {"a2w", "cwms", "usgs", "nwps", "rise"}      # tva: the public live feed covers only the last 48 h (section 3.1)
DAILY_KINDS = {"riseDaily", "tvaOperatingGuide"}


def load_generated(path: str = GENERATED) -> dict:
    out = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            s = line.strip()
            if s.startswith('{"lakeId"'):
                rec = json.loads(s.rstrip(","))
                out[rec["lakeId"]] = rec
    return out


def load_accepted(paths=ACCEPTED) -> list:
    ids = []
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            ids += json.load(fh)["lakeIds"]
    return ids


def operator_family(rec: dict):
    """The publishing agency of the dam operator, when the operator is one of the agencies the Lake Brain reads (section 3.2)."""
    name = ((rec.get("dam") or {}).get("operatorName") or "")
    if "Army Corps" in name:
        return "CWMS"
    if "Tennessee Valley" in name:
        return "TVA"
    if "Reclamation" in name:
        return "USBR"
    return None


def candidate(entry: dict, role: str) -> dict:
    """A normalised series reference: provider/kind, family, identity key, offset, cadence class."""
    kind = entry.get("provider") or entry.get("kind")
    fam = FAMILY[kind]
    if fam == "CWMS":
        office = (entry.get("station") or entry.get("office")).split(":")[0].upper()
        ident = (office, entry["series"])
    elif fam == "USGS":
        ident = (entry.get("station") or entry.get("site"), entry.get("series") or entry.get("param"))
    elif fam == "NWS":
        ident = (entry.get("station") or entry.get("lid"),)
    elif fam == "USBR":
        ident = (entry.get("station") or entry.get("item"),)
    else:
        ident = (entry.get("station") or entry.get("locationId"),)
    offset = entry.get("datumOffsetFt") if role == "live" else entry.get("offsetFt")
    if fam == "CWMS":
        daily = "1Day" in entry["series"]
    elif kind == "usgsDaily":
        daily = entry.get("stat") != "iv"
    else:
        daily = kind in DAILY_KINDS or (kind == "rise")
    c = {"kind": kind, "family": fam, "key": list(ident), "boundRole": "FALLBACK_LIVE" if role == "live" else "HISTORY",
         "offsetFt": float(offset or 0.0), "cadence": "DAILY" if daily else "SUB_DAILY"}
    for k in ("station", "series", "office", "site", "param", "stat", "lid", "pe", "item", "locationId", "cadenceMin", "lagMin"):
        if k in entry:
            c[k] = entry[k]
    return c


def classify(primary: dict, cand: dict, op_family) -> str:
    """Independence class of a truth candidate relative to the Lake Brain's value series (section 3.2)."""
    if cand["family"] == primary["family"]:
        if cand["key"] == primary["key"]:
            return "SAME_SERIES"
        if cand["family"] == "USGS" and cand["key"][0] == primary["key"][0]:
            return "SAME_SERIES"          # same USGS site: same instrument (another parameter is a datum conversion; dv is derived)
        if cand["family"] == "NWS":
            return "SAME_SERIES" if cand["key"][0] == primary["key"][0] else "NWS_REDISTRIBUTION"
        if cand["family"] == "TVA":
            return "SAME_SERIES" if cand["kind"] == primary["kind"] else "OPERATOR_OTHER_SERIES"
    if cand["family"] == "NWS":
        return "NWS_REDISTRIBUTION"
    if cand["family"] == op_family:
        return "OPERATOR_OTHER_SERIES"
    if cand["family"] == primary["family"]:
        return "AGENCY_OTHER_SERIES"      # same agency, another series, and the agency is not the dam operator
    return "CROSS_AGENCY"


TIER = {"OPERATOR_OTHER_SERIES": 1, "CROSS_AGENCY": 2, "AGENCY_OTHER_SERIES": 2, "NWS_REDISTRIBUTION": 3}


def assign(rec: dict) -> dict:
    """The lake's primary (Brain value) series, every candidate with its class, and the pre-registered truth choice."""
    primary = candidate(rec["live"][0], "live")
    primary["boundRole"] = "BRAIN_VALUE"
    op = operator_family(rec)
    cands = [candidate(e, "live") for e in rec["live"][1:]] + [candidate(e, "history") for e in rec.get("history") or []]
    for i, c in enumerate(cands):
        c["order"] = i
        c["independence"] = classify(primary, c, op)
    usable = [c for c in cands if c["independence"] in TIER]
    # lowest tier; then an un-calibrated series (offset 0) before a calibrated one; then sub-daily before daily; then binding order
    usable.sort(key=lambda c: (TIER[c["independence"]], c["offsetFt"] != 0.0, c["cadence"] == "DAILY", c["order"]))
    truth = usable[0] if usable else None
    if rec["live"][0]["provider"] not in RECONSTRUCTIBLE:
        status = "EXCLUDED_BRAIN_VALUE_NOT_RECONSTRUCTIBLE"
    elif truth is None:
        status = "EXCLUDED_SAME_SERIES_ONLY" if cands else "EXCLUDED_NO_SECOND_SERIES"
    elif TIER[truth["independence"]] <= 2:
        status = "VERDICT_ELIGIBLE"
    else:
        status = "REPORT_ONLY_ELIGIBLE"
    return {"lakeId": rec["lakeId"], "timeZone": rec.get("timeZone"), "capability": rec.get("capability"),
            "operatorFamily": op, "primaryProvider": rec["live"][0]["provider"], "primary": primary,
            "truth": truth, "candidates": cands, "status": status}


def rank(lake_id: str) -> str:
    return hashlib.sha256(f"{SEED}|{lake_id}".encode("utf-8")).hexdigest()


def allocate(sizes: dict, total: int = SAMPLE_SIZE) -> dict:
    """Take-all for strata of <= TAKE_ALL_MAX; the rest of `total` split over larger strata in proportion to size (largest remainder),
    each at least MIN_PER_STRATUM and never more than its size."""
    alloc = {s: n for s, n in sizes.items() if n <= TAKE_ALL_MAX}
    big = {s: n for s, n in sizes.items() if n > TAKE_ALL_MAX}
    left = max(0, total - sum(alloc.values()))
    if big:
        tot = sum(big.values())
        raw = {s: left * n / tot for s, n in big.items()}
        base = {s: max(MIN_PER_STRATUM, min(big[s], int(raw[s]))) for s in big}
        rem = left - sum(base.values())
        for s in sorted(big, key=lambda s: (-(raw[s] - int(raw[s])), s)):
            if rem <= 0:
                break
            if base[s] < big[s]:
                base[s] += 1
                rem -= 1
        alloc.update(base)
    return alloc


def build(generated: dict, accepted: list) -> dict:
    rows = [assign(generated[k]) for k in accepted]
    strata, report = {}, {}
    for r in rows:
        if r["status"] == "VERDICT_ELIGIBLE":
            strata.setdefault(r["primaryProvider"], []).append(r["lakeId"])
        elif r["status"] == "REPORT_ONLY_ELIGIBLE":
            report.setdefault(r["primaryProvider"], []).append(r["lakeId"])
    alloc = allocate({s: len(v) for s, v in strata.items()})
    verdict = sorted(lid for s, v in strata.items() for lid in sorted(v, key=rank)[:alloc[s]])
    report_only = sorted(lid for s, v in report.items() for lid in sorted(v, key=rank)[:REPORT_ONLY_PER_STRATUM])
    by_id = {r["lakeId"]: r for r in rows}
    frame = {}
    for r in rows:
        frame.setdefault(r["primaryProvider"], {}).setdefault(r["status"], 0)
        frame[r["primaryProvider"]][r["status"]] += 1
    return {
        "protocol": PROTOCOL, "seed": SEED, "rule": "build_sample.py (pre-registration sections 3-4)",
        "inputs": {"generatedBindings": os.path.relpath(GENERATED, ROOT), "accepted": [os.path.relpath(p, ROOT) for p in ACCEPTED],
                   "generatedSha256": _sha(GENERATED), "acceptedSha256": [_sha(p) for p in ACCEPTED]},
        "frameCount": len(rows), "frameByPrimaryProvider": frame,
        "allocation": alloc, "verdictSample": [by_id[k] for k in verdict], "reportOnlySample": [by_id[k] for k in report_only],
        "excluded": sorted(({"lakeId": r["lakeId"], "primaryProvider": r["primaryProvider"], "status": r["status"]} for r in rows
                            if r["status"].startswith("EXCLUDED")), key=lambda x: x["lakeId"]),
    }


def _sha(path: str) -> str:
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def dumps(obj) -> str:
    return json.dumps(obj, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    text = dumps(build(load_generated(), load_accepted()))
    if a.check:
        with open(a.out, encoding="utf-8") as fh:
            same = fh.read() == text
        print("sample matches the rule" if same else "SAMPLE DIFFERS from the rule's output")
        return 0 if same else 1
    with open(a.out, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"wrote {a.out} sha256={hashlib.sha256(text.encode('utf-8')).hexdigest()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
