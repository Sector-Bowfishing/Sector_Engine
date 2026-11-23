#!/usr/bin/env python3
"""Lake Brain operator-truth validation v2 (`lake-operator-truth-v2`): build the FROZEN lake set and truth assignment (no network, no values).

Pre-registration: PREREGISTRATION_v2.md beside this file (sections 3 and 4 are implemented here literally). Supersedes v1 (commit 469a15f) after
the independent review of Sector_Engine PR #243. Inputs are committed metadata only: the runtime binding table the Lake Brain runs on
(LakeSourceBindingsGenerated.swift), the accepted lake lists (accepted_batch.json + accepted_batch2.json, 289 lakes) and the reviewed binding contract
(datums). It reads no water-level value from anywhere.

usage: build_sample_v2.py [--out sample_v2.json] [--check]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
GENERATED = os.path.join(ROOT, "brains", "lake", "runtime", "LakeBrain", "LakeSourceBindingsGenerated.swift")
ACCEPTED = [os.path.join(ROOT, "jobs", "lake-brain", "data", f) for f in ("accepted_batch.json", "accepted_batch2.json")]
REVIEWED = os.path.join(ROOT, "brains", "lake", "contracts", "reviewed-lake-bindings-v1.json")
OUT = os.path.join(HERE, "sample_v2.json")

PROTOCOL = "lake-operator-truth-v2"
SEED = "sector-lake-operator-truth-v2"
REPORT_ONLY_PER_STRATUM = 5

FAMILY = {"a2w": "CWMS", "cwms": "CWMS", "cwmsDaily": "CWMS", "usgs": "USGS", "usgsDaily": "USGS", "nwps": "NWS", "hadsDaily": "NWS",
          "rise": "USBR", "riseDaily": "USBR", "tva": "TVA", "tvaOperatingGuide": "TVA"}
RECONSTRUCTIBLE = {"a2w", "cwms", "usgs", "nwps", "rise"}      # tva: the public live feed covers only the last 48 h
USGS_DATUM = {"62614": "NGVD29", "62615": "NAVD88"}           # 00062 / 62616 / 72020 / 72022: datum not identified by the parameter
INDEPENDENT_CLASSES = ("OPERATOR_OTHER_SERIES", "AGENCY_OTHER_SERIES", "CROSS_AGENCY")
TIER = {"CROSS_AGENCY": 1, "OPERATOR_OTHER_SERIES": 2, "AGENCY_OTHER_SERIES": 2, "SAME_SENSOR_SUSPECTED": 3, "NWS_REDISTRIBUTION": 4}


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


def load_reviewed(path: str = REVIEWED) -> dict:
    with open(path, encoding="utf-8") as fh:
        return {r["lakeId"]: r for r in json.load(fh)["reviewed"]}


def operator_family(rec: dict):
    name = ((rec.get("dam") or {}).get("operatorName") or "")
    if "Army Corps" in name:
        return "CWMS"
    if "Tennessee Valley" in name:
        return "TVA"
    if "Reclamation" in name:
        return "USBR"
    return None


def tsid_parts(tsid: str) -> dict:
    p = tsid.split(".")
    version = p[-1] if len(p) >= 6 else ""
    norm = re.sub(r"[-_ ]?(raw|rev)$", "", version.lower())
    loc = re.sub(r"[-_ ]?(lake|reservoir|res)$", "", p[0].lower())     # Kinzua-Lake ~ Kinzua, MissHW_Leech-Lake ~ MissHW_Leech
    return {"location": loc, "nwsLid": bool(re.fullmatch(r"[A-Z]{4}[0-9]", p[0])), "param": (p[1] if len(p) > 1 else "").lower(), "version": version, "versionNorm": norm}


def candidate(entry: dict, role: str) -> dict:
    kind = entry.get("provider") or entry.get("kind")
    fam = FAMILY[kind]
    if fam == "CWMS":
        office = (entry.get("station") or entry.get("office")).split(":")[0].upper()
        ident = [office, entry["series"]]
    elif fam == "USGS":
        ident = [entry.get("station") or entry.get("site"), entry.get("series") or entry.get("param")]
    elif fam == "NWS":
        ident = [entry.get("station") or entry.get("lid")]
    elif fam == "USBR":
        ident = [entry.get("station") or entry.get("item")]
    else:
        ident = [entry.get("station") or entry.get("locationId")]
    offset = entry.get("datumOffsetFt") if role in ("live", "value") else entry.get("offsetFt")
    if fam == "CWMS":
        daily = "1Day" in entry["series"]
    elif kind == "usgsDaily":
        daily = entry.get("stat") != "iv"
    else:
        daily = kind in ("rise", "riseDaily", "tvaOperatingGuide")
    c = {"kind": kind, "family": fam, "key": ident, "boundRole": {"value": "BRAIN_VALUE", "live": "FALLBACK_LIVE"}.get(role, "HISTORY"),
         "offsetFt": float(offset or 0.0), "cadence": "DAILY" if daily else "SUB_DAILY",
         "datum": USGS_DATUM.get(ident[1]) if fam == "USGS" else None}
    for k in ("station", "series", "office", "site", "param", "stat", "lid", "pe", "item", "locationId", "cadenceMin", "lagMin"):
        if k in entry:
            c[k] = entry[k]
    return c


def classify(p: dict, c: dict, op_family) -> str:
    """Independence class of truth candidate `c` against the Brain's value series `p` (pre-registration v2 section 3.2, rules in order)."""
    fp, fc = p["family"], c["family"]
    # SAME_SERIES
    if fp == fc and p["key"] == c["key"]:
        return "SAME_SERIES"
    if fp == fc == "CWMS":
        a, b = tsid_parts(p["key"][1]), tsid_parts(c["key"][1])
        if a["location"] == b["location"] and a["param"] == b["param"]:
            if p["key"][0] != c["key"][0] or a["versionNorm"] == b["versionNorm"]:
                return "SAME_SERIES"                     # one location+parameter across offices, or -raw / -rev of one feed
            return "SAME_SENSOR_SUSPECTED"               # same location+parameter, other version / interval / type (OBS vs RESOPS, Inst vs ~1Day)
    if fp == fc == "USGS" and p["key"][0] == c["key"][0]:
        return "SAME_SERIES"
    if fp == fc == "NWS" and p["key"][0] == c["key"][0]:
        return "SAME_SERIES"
    if fp == fc == "TVA" and p["kind"] == c["kind"]:
        return "SAME_SERIES"
    # SAME_SENSOR_SUSPECTED
    for x, y in ((p, c), (c, p)):
        if x["family"] == "CWMS" and y["family"] == "USGS":
            t = tsid_parts(x["key"][1])
            if "usgs" in t["versionNorm"] or t["nwsLid"]:
                return "SAME_SENSOR_SUSPECTED"           # a CWMS series ingested from a USGS gauge (version USGS-*), or a DCP decode filed under
                                                         # an NWS location id (e.g. PSMT2, TRNT2), against a USGS series
    if fp == "NWS" and fc != "NWS":
        return "SAME_SENSOR_SUSPECTED"                   # the NWS redistributes the gauge operator's DCP; it operates no lake gauge
    if fc == "NWS":
        return "NWS_REDISTRIBUTION"
    if fc == op_family:
        return "OPERATOR_OTHER_SERIES"
    if fc == fp:
        return "AGENCY_OTHER_SERIES"
    return "CROSS_AGENCY"


def a2w_office(rec: dict, ref: dict):
    """CWMS office under which an a2w tsid is evidenced in committed metadata: a cwms / cwmsDaily entry of the same lake with the identical
    tsid. None = assumption A1 not checkable from committed metadata (the series is then not evaluable)."""
    for e in list(rec["live"]) + list(rec.get("history") or []):
        k = e.get("provider") or e.get("kind")
        if k in ("cwms", "cwmsDaily") and e.get("series") == ref["key"][1]:
            return (e.get("station") or e.get("office")).split(":")[0].upper()
    return None


def verdict_block(c: dict, value_datum) -> str | None:
    """Why a candidate of an independent class cannot be a VERDICT truth (sections 3.3-3.4); None = verdict-eligible."""
    if c["boundRole"] == "FALLBACK_LIVE":
        return "FALLBACK_LIVE (pre-filtered by dry-run check (b))"
    if c["offsetFt"] != 0.0:
        return "OFFSET_FITTED"
    if c.get("a2wOffice") is None and c["kind"] == "a2w":
        return "A1_UNVERIFIED"
    if c["datum"] and value_datum and c["datum"] != value_datum:
        return "DATUM_MISMATCH"
    return None


def assign(rec: dict, reviewed: dict) -> dict:
    p = candidate(rec["live"][0], "value")
    op = operator_family(rec)
    value_datum = (reviewed.get(rec["lakeId"]) or {}).get("datum") or p.get("datum")
    cands = [candidate(e, "live") for e in rec["live"][1:]] + [candidate(e, "history") for e in rec.get("history") or []]
    for x in [p] + cands:
        if x["kind"] == "a2w":
            x["a2wOffice"] = a2w_office(rec, x)
            if x["a2wOffice"]:
                x["key"] = [x["a2wOffice"], x["key"][1]]
    for i, c in enumerate(cands):
        c["order"] = i
        c["independence"] = classify(p, c, op)
        c["verdictBlock"] = verdict_block(c, value_datum) if c["independence"] in INDEPENDENT_CLASSES else "CLASS"
    order = lambda c: (TIER.get(c["independence"], 9), c["offsetFt"] != 0.0, c["cadence"] == "DAILY", c["order"])  # noqa: E731
    eligible = sorted((c for c in cands if c["verdictBlock"] is None), key=order)
    reportable = sorted((c for c in cands if c["independence"] in TIER), key=order)
    if p["kind"] not in RECONSTRUCTIBLE:
        status, truth = "EXCLUDED_BRAIN_VALUE_NOT_RECONSTRUCTIBLE", None
    elif p["kind"] == "a2w" and not p["a2wOffice"]:
        status, truth = "EXCLUDED_A1_UNVERIFIED", None
    elif eligible:
        status, truth = "VERDICT", eligible[0]
    elif reportable:
        status, truth = "REPORT_ONLY_ELIGIBLE", reportable[0]
    else:
        status, truth = ("EXCLUDED_SAME_SERIES_ONLY" if cands else "EXCLUDED_NO_SECOND_SERIES"), None
    return {"lakeId": rec["lakeId"], "timeZone": rec.get("timeZone"), "capability": rec.get("capability"), "operatorFamily": op,
            "valueDatum": value_datum, "primaryProvider": rec["live"][0]["provider"], "primary": p, "truth": truth,
            "independentTruth": bool(truth and status == "VERDICT" and truth["independence"] == "CROSS_AGENCY"),
            "candidates": cands, "status": status}


def rank(lake_id: str) -> str:
    return hashlib.sha256(f"{SEED}|{lake_id}".encode("utf-8")).hexdigest()


def build(generated: dict, accepted: list, reviewed: dict) -> dict:
    rows = [assign(generated[k], reviewed) for k in accepted]
    by_id = {r["lakeId"]: r for r in rows}
    verdict = sorted(r["lakeId"] for r in rows if r["status"] == "VERDICT")          # census: every verdict-eligible lake (section 4)
    report = {}
    for r in rows:
        if r["status"] == "REPORT_ONLY_ELIGIBLE":
            report.setdefault(r["primaryProvider"], []).append(r["lakeId"])
    report_only = sorted(lid for v in report.values() for lid in sorted(v, key=rank)[:REPORT_ONLY_PER_STRATUM])
    frame = {}
    for r in rows:
        frame.setdefault(r["primaryProvider"], {}).setdefault(r["status"], 0)
        frame[r["primaryProvider"]][r["status"]] += 1
    blocks = {}
    for r in rows:
        if r["status"] != "VERDICT":
            for c in r["candidates"]:
                if c["independence"] in INDEPENDENT_CLASSES:
                    b = c["verdictBlock"] or "NONE (lake excluded for its value series)"
                    blocks[b] = blocks.get(b, 0) + 1
    return {
        "protocol": PROTOCOL, "seed": SEED, "rule": "build_sample_v2.py (pre-registration v2 sections 3-4)",
        "inputs": {"generatedBindings": os.path.relpath(GENERATED, ROOT), "accepted": [os.path.relpath(p, ROOT) for p in ACCEPTED],
                   "reviewed": os.path.relpath(REVIEWED, ROOT), "generatedSha256": _sha(GENERATED),
                   "acceptedSha256": [_sha(p) for p in ACCEPTED], "reviewedSha256": _sha(REVIEWED)},
        "frameCount": len(rows), "frameByPrimaryProvider": frame, "independentCandidateBlocksOnNonVerdictLakes": dict(sorted(blocks.items())),
        "verdictSet": [by_id[k] for k in verdict], "reportOnlySample": [by_id[k] for k in report_only],
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
    text = dumps(build(load_generated(), load_accepted(), load_reviewed()))
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
