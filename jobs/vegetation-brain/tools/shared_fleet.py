#!/usr/bin/env python3
"""Fleet SHADOW run on the shared Clarity per-pass JSON (no PNG, no Sentinel scene, no new schedule). Read-only.

A few wildcard `gcloud storage cat` calls stream the small `<date>.json` pass summaries of every lake (~4 KB each); lake-level observation
rules from shared.observe_shared are applied; states go to the DRY-RUN store twice (the second run must skip every unchanged lake);
a compact summary is written (no per-lake raster, no raw passes).
   python tools/shared_fleet.py --registry lakes.v1.json --out fleet_shadow_summary.json --since 2026-09-14"""
import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from vegetation_brain import agency as AG  # noqa: E402
from vegetation_brain import contract as C  # noqa: E402
from vegetation_brain import fleet as F  # noqa: E402
from vegetation_brain import shared as SH  # noqa: E402
from vegetation_brain.publish import publish  # noqa: E402
from vegetation_brain.writer import DryRunWriter  # noqa: E402

BUCKET = "gs://sector-lake-surface/lakes"


def stream(pattern: str) -> tuple[list, int]:
    r = subprocess.run(["gcloud", "storage", "cat", pattern], capture_output=True, text=True)
    txt, dec, i, out = r.stdout, json.JSONDecoder(), 0, []
    while i < len(txt):
        while i < len(txt) and txt[i] in " \r\n\t":
            i += 1
        if i >= len(txt):
            break
        try:
            obj, j = dec.raw_decode(txt, i)
        except ValueError:
            i += 1
            continue
        out.append(obj)
        i = j
    return out, len(txt.encode())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--since", default="2026-09-14")
    ap.add_argument("--now", default=None)
    ap.add_argument("--agency", default=os.path.join(HERE, "..", "vegetation_brain", "data", "agency_fwc_pacpvi.json"))
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    since = datetime.fromisoformat(a.since).date()
    reg = json.load(open(a.registry))
    manifest = F.build_manifest(reg, version="fleet-shadow-" + now.strftime("%Y-%m-%d"))
    t0, wall0 = time.process_time(), time.time()
    docs, nbytes = [], 0
    months = sorted({x[:7] for x in [(since + timedelta(days=i)).isoformat() for i in range((now.date() - since).days + 1)]})
    for m in months:
        got, nb = stream(f"{BUCKET}/*/clarity/{m}-??.json")
        docs += got
        nbytes += nb
    by = {}
    for doc in docs:
        if "pass" not in doc or not doc.get("lakeId"):
            continue
        sp = SH.pass_from_clarity_json(doc)
        if sp.when >= since:
            by.setdefault(doc["lakeId"], {})[sp.when] = sp
    areas = {e["lakeId"]: e.get("areaKm2") for e in reg["lakes"]}
    cands = {c["lakeId"]: c for c in manifest["candidates"]}
    observations = {}
    for lid, ps in by.items():
        if lid not in cands or cands[lid]["readiness"] == "BLOCKED":
            continue
        passes = sorted(ps.values(), key=lambda p: p.when)
        observations[lid] = SH.observe_shared(passes, passes[-1].when, areas.get(lid))
    agency = json.load(open(a.agency))["records"]
    w = DryRunWriter()
    r1 = publish(manifest, w, observations=observations, agency=agency, now=now)
    n1 = len(w.patches)
    r2 = publish(manifest, w, observations=observations, agency=agency, now=now)
    cpu = time.process_time() - t0
    from sector_brain_platform import lake_key
    rows = []
    for lid in observations:
        st = w.tree["lakes"][lake_key(lid)]["states"]["vegetation"]
        sv, ob = st["surfaceVegetation"], st["observation"]
        rows.append({"lakeId": lid, "status": sv["status"], "evidence": ob["evidenceKind"], "accepted": ob["acceptedScenes"],
                     "share": (round(observations[lid].observed_share_pct, 1) if observations[lid].observed_share_pct is not None else None),
                     "fallback": ob["lowCoverageFallback"], "ageDays": sv["ageDays"], "bytes": len(json.dumps(st))})
    shares = sorted(r["share"] for r in rows if r["share"] is not None)
    q = lambda p: shares[int(p * (len(shares) - 1))] if shares else None
    out = {"generatedAt": now.isoformat(), "since": a.since, "lakesInRegistry": len(manifest["candidates"]), "lakesWithPasses": len(by),
           "lakesObserved": len(observations), "passDocs": len(docs),
           "status": dict(Counter(r["status"] for r in rows)), "evidence": dict(Counter(r["evidence"] for r in rows)),
           "persistenceReachable": sum(1 for r in rows if r["evidence"] == "SATELLITE_PERSISTENCE"),
           "fallbackOnly": sum(1 for r in rows if r["fallback"]), "ageDaysQuantiles": [sorted(r["ageDays"] for r in rows if r["ageDays"] is not None)[int(p * (len(rows) - 1))] for p in (0.5, 0.9)] if rows else None,
           "observedSharePctQuantiles": {"p10": q(0.1), "p50": q(0.5), "p90": q(0.9), "max": shares[-1] if shares else None},
           "run1": {k: r1.get(k) for k in ("evaluated", "observed", "skippedUnchanged", "writes", "health")},
           "run2": {k: r2.get(k) for k in ("evaluated", "observed", "skippedUnchanged", "writes", "health")},
           "patchesAfterRun1": n1, "patchesAfterRun2": len(w.patches), "bytesStreamed": nbytes, "cpuSeconds": round(cpu, 2),
           "wallSeconds": round(time.time() - wall0, 1), "stateBytes": {"total": sum(r["bytes"] for r in rows), "max": max((r["bytes"] for r in rows), default=0)},
           "agencyLakes": sum(1 for lid in agency if lid in cands)}
    json.dump(out, open(a.out, "w"), indent=1, sort_keys=True)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
