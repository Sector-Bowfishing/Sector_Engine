#!/usr/bin/env python3
"""Regenerate Sources/SectorEngine/LakeBrain/LakeSourceBindingsGenerated.swift (the Lake Brain bindings table).

    python3 scripts/generate-lake-bindings.py [--check]

Inputs
  jobs/lake-brain/data/bindings.proposed.v1.json   MACHINE_VERIFIED records (jobs/lake-brain/bindings/build_bindings_table.py)
  jobs/lake-brain/data/accepted_batch.json         lakeIds Michael accepted AFTER review. Does not exist until then: treated as an
                                                   EMPTY list. This script never creates it.

THE GATE: every generated binding is CANDIDATE (never publishes a state) unless its lakeId is in accepted_batch.json, in which case
the Swift side marks it REVIEWED. The accepted ids are embedded below as `acceptedLakeIds`; a stale accepted id (not in the table, or in
the excluded list) fails the build here instead of silently publishing nothing or the wrong lake.

accepted_batch.json may be a JSON array of lakeIds (strings) or of {"lakeId": ...} objects, or an object
{"lakeIds": [...] | "accepted": [...] | "lakes": [...], "reviewedAt": "YYYY-MM-DD", "reviewedBy": "..."}.

The table is embedded as ONE raw string literal that LakeGeneratedBindings decodes once: ~210 typed Swift literals would cost minutes of
type-checking; a string costs nothing and is validated by the tests (count == the Python table, ids unique and in LakeDirectory, ...).
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
DATA = os.path.join(ROOT, "jobs", "lake-brain", "data")
PROPOSED = os.path.join(DATA, "bindings.proposed.v1.json")
EXCLUDED = os.path.join(DATA, "bindings.proposed.v1.excluded.json")
ACCEPTED = os.path.join(DATA, "accepted_batch.json")
OUT = os.path.join(ROOT, "Sources", "SectorEngine", "LakeBrain", "LakeSourceBindingsGenerated.swift")

ADAPTER_PROVIDERS = {"tva", "cwms", "usgs", "a2w", "rise", "nwps", "twdb"}
FORBIDDEN_PROVIDERS = {"nipsco", "njwsa", "duke", "wps-hydro", "alliant", "srp", "cnppid", "nppd", "utahlake", "aep", "eccc", "mncsg",
                       "sjrwmd", "nhdes"}


def load_accepted() -> tuple[list[str], str | None]:
    if not os.path.exists(ACCEPTED):
        return [], None
    raw = json.load(open(ACCEPTED))
    reviewed_at = None
    if isinstance(raw, dict):
        reviewed_at = raw.get("reviewedAt")
        raw = raw.get("lakeIds") or raw.get("accepted") or raw.get("lakes") or []
    ids = []
    for x in raw:
        ids.append(x["lakeId"] if isinstance(x, dict) else x)
    if len(set(ids)) != len(ids):
        raise SystemExit("accepted_batch.json lists a lakeId twice")
    return sorted(ids), reviewed_at


def compact(rec: dict) -> dict:
    """The runtime shape (LakeGeneratedBindings.Record): only what the engine reads."""
    live = []
    for l in rec["live"]:
        assert l["provider"] in ADAPTER_PROVIDERS, f"{rec['lakeId']}: provider {l['provider']} has no adapter"
        assert l["provider"] not in FORBIDDEN_PROVIDERS
        x = {k: l[k] for k in ("provider", "capability", "station", "cadenceMin", "lagMin") if l.get(k) is not None}
        if l.get("series") is not None:
            x["series"] = l["series"]
        if l.get("datumOffsetFt"):
            x["datumOffsetFt"] = l["datumOffsetFt"]
        live.append(x)
    hist = []
    for h in rec["history"]:
        x = {k: v for k, v in h.items() if k != "note" and v is not None}
        if x.get("offsetFt") == 0:
            x.pop("offsetFt")
        hist.append(x)
    v = rec["verification"]
    pr = v.get("probe") or {}
    out = {
        "lakeId": rec["lakeId"], "capability": rec["capability"], "timeZone": rec["timeZone"],
        "live": live, "history": hist,
        "historyCompleteYears": int(rec["historyCompleteYears"]), "historyClass": rec["historyClass"],
        "verification": {"criteriaVersion": v["criteriaVersion"], "researchStatus": v["researchStatus"], "wave": v["wave"],
                         "checksPassed": ",".join(v["checksPassed"]), "probedAt": v["probedAt"],
                         **({"lastObservationAt": pr["lastObservationAt"]} if pr.get("lastObservationAt") else {}),
                         **({"ageHours": pr["ageHours"]} if pr.get("ageHours") is not None else {})},
    }
    p = rec.get("plan")
    if p and (p["planStrict"] or p["floodStrict"]):
        keep = []
        for l in p["levels"]:
            if l["role"] in ("guideCurve", "zoneTop", "zoneBottom") and not p["planStrict"]:
                continue
            if l["role"] == "floodPoolBottom" and not p["floodStrict"]:
                continue
            x = {k: l[k] for k in ("role", "name", "kind", "source", "seasonal") if k in l}
            for k in ("valueFt", "office", "location", "id"):
                if l.get(k) is not None:
                    x[k] = l[k]
            keep.append(x)
        if keep:
            plan = {"planSource": p["planSource"], "verifiedMatch": bool(p["verifiedMatch"]), "levels": keep}
            for k in ("matchedProject", "matchBasis", "tvaOperatingGuide"):
                if p.get(k):
                    plan[k] = p[k]
            out["plan"] = plan
    d = rec.get("dam") or {}
    if d:
        out["dam"] = {k: d[k] for k in ("nidId", "damName", "operatorName", "hydropower", "floodControl", "source") if d.get(k) is not None}
    if rec.get("context"):
        out["context"] = rec["context"]
    return out


def render() -> str:
    doc = json.load(open(PROPOSED))
    assert doc["schema"] == "lake-brain-bindings-proposed/v1" and doc["bindingStatus"] == "MACHINE_VERIFIED"
    recs = doc["bindings"]
    ids = [r["lakeId"] for r in recs]
    assert len(ids) == len(set(ids)), "duplicate lakeId in the proposed table"
    excluded = {x["lakeId"] for x in json.load(open(EXCLUDED))["excluded"]} if os.path.exists(EXCLUDED) else set()
    assert not (set(ids) & excluded), f"lakes both proposed and excluded: {sorted(set(ids) & excluded)}"
    accepted, reviewed_at = load_accepted()
    unknown = [a for a in accepted if a not in set(ids)]
    if unknown:
        raise SystemExit(f"accepted_batch.json names lakes that are not in the proposed table (or were excluded): {unknown}")
    lines = [json.dumps(compact(r), separators=(",", ":"), ensure_ascii=False, sort_keys=False) for r in recs]
    blob = "[\n" + ",\n".join(lines) + "\n]"
    assert '"""#' not in blob and "\\#" not in blob, "table contains a raw-string terminator"
    fp = hashlib.sha256("\n".join(accepted).encode()).hexdigest()[:8] if accepted else ""
    table_fp = hashlib.sha256(blob.encode()).hexdigest()[:12]
    acc = ", ".join(json.dumps(a, ensure_ascii=False) for a in accepted)
    return f'''//
//  LakeSourceBindingsGenerated.swift
//  Sector — Lake Brain: the generated level-source bindings table (GENERATED — do not hand-edit)
//
//  Source: jobs/lake-brain/data/bindings.proposed.v1.json  ({len(recs)} MACHINE_VERIFIED rows, binding-review-v1, research 2026-10-13)
//          jobs/lake-brain/data/accepted_batch.json         ({len(accepted)} accepted lake(s))
//  Regenerate with: python3 scripts/generate-lake-bindings.py
//
//  EVERY row is a CANDIDATE (never publishes a state) unless its lakeId is in `acceptedLakeIds`. That list is
//  the content of accepted_batch.json, which exists only after Michael's review. See LakeGeneratedBindings.swift.
//

import Foundation

enum LakeSourceBindingsGenerated {{
    /// Hash of the embedded table (changes with every regeneration).
    static let tableFingerprint = "{table_fp}"
    /// accepted_batch.json lakeIds. EMPTY until the binding review is done.
    static let acceptedLakeIds: [String] = [{acc}]
    static let acceptedReviewedAt: String? = {json.dumps(reviewed_at) if reviewed_at else "nil"}
    static let acceptedFingerprint = "{fp}"

    /// {len(recs)} records, one per line (see LakeGeneratedBindings.Record).
    static let json = #"""
{blob}
"""#
}}
'''


def main() -> int:
    text = render()
    if "--check" in sys.argv:
        ok = os.path.exists(OUT) and open(OUT).read() == text
        print("LakeSourceBindingsGenerated.swift is up to date" if ok else "LakeSourceBindingsGenerated.swift differs from a fresh render")
        return 0 if ok else 1
    with open(OUT, "w") as f:
        f.write(text)
    print(f"wrote {os.path.relpath(OUT, ROOT)} ({len(text) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
