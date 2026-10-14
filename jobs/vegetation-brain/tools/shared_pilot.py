#!/usr/bin/env python3
"""Small SHADOW pilot: run the Vegetation Brain on SHARED Clarity lake-surface pass evidence for a handful of lakes.

Read-only: it GETs small per-pass JSON/PNG files from gs://sector-lake-surface via the gcloud CLI (the Clarity job already produced them),
decodes PNG class counts, runs shared.observe_shared, builds states into the DRY-RUN store twice (the second run must SKIP), prints a compact
report, and deletes its temporary files. It reads no Sentinel scene, writes nothing to GCS/RTDB, and has no schedule.
Needs: gcloud (authenticated), Pillow, numpy.   python tools/shared_pilot.py --registry lakes.v1.json --out pilot_report.json"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime, timedelta, timezone

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from vegetation_brain import contract as C  # noqa: E402
from vegetation_brain import fleet as F  # noqa: E402
from vegetation_brain import shared as SH  # noqa: E402
from vegetation_brain.publish import publish  # noqa: E402
from vegetation_brain.writer import DryRunWriter  # noqa: E402

BUCKET = "gs://sector-lake-surface/lakes"
PILOT = ["Guntersville_AL", "Lake_Hartwell_SC", "Istokpoga_FL", "Okeechobee_FL", "Sam_Rayburn_Reservoir_TX", "Toledo_Bend_Reservoir_TX",
         "Leech_Lake_MN", "Lake_Pepin_MN"]


def gcs(*args) -> str:
    return subprocess.run(["gcloud", "storage", *args], check=True, capture_output=True, text=True).stdout


def fetch(lake_key: str, tmp: str, since: date) -> tuple[list, int]:
    names = [n.rsplit("/", 1)[-1] for n in gcs("ls", f"{BUCKET}/{lake_key}/clarity/").split()]
    dates = sorted({n[:10] for n in names if len(n) >= 15 and n[10:] == ".json" and n[:4].isdigit()})
    dates = [d for d in dates if date.fromisoformat(d) >= since]
    passes, nbytes = [], 0
    for d in dates:
        jp, pp = os.path.join(tmp, f"{lake_key}_{d}.json"), os.path.join(tmp, f"{lake_key}_{d}.png")
        subprocess.run(["gcloud", "storage", "cp", "-q", f"{BUCKET}/{lake_key}/clarity/{d}.json", jp], check=True, capture_output=True)
        has_png = f"{d}.measured.png" in names
        if has_png:
            subprocess.run(["gcloud", "storage", "cp", "-q", f"{BUCKET}/{lake_key}/clarity/{d}.measured.png", pp], check=True, capture_output=True)
        counts, arr = None, None
        if has_png:
            arr = np.array(Image.open(pp))
            counts = {int(k): int(v) for k, v in zip(*np.unique(arr, return_counts=True)) if int(k) in (255, 3, 2, 1, 0)}
        nbytes += os.path.getsize(jp) + (os.path.getsize(pp) if has_png else 0)
        sp = SH.pass_from_clarity_json(json.load(open(jp)), counts)
        sp.codes = arr
        passes.append(sp)
    return passes, nbytes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--registry", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--lakes", nargs="*", default=PILOT)
    ap.add_argument("--now", default=None)
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now) if a.now else datetime.now(timezone.utc)
    reg = json.load(open(a.registry))
    pick = [e for e in reg["lakes"] if e["lakeKey"] in a.lakes]
    manifest = F.build_manifest({**reg, "lakes": pick}, version="pilot-" + now.strftime("%Y-%m-%d"))
    tmp = tempfile.mkdtemp(prefix="veg_pilot_")
    t0 = time.process_time()
    wall0 = time.time()
    observations, report, total_bytes = {}, [], 0
    try:
        for e in pick:
            passes, nb = fetch(e["lakeKey"], tmp, (now - timedelta(days=60)).date())
            total_bytes += nb
            ref = max((p.when for p in passes), default=None)
            cand = next(c for c in manifest["candidates"] if c["lakeId"] == e["lakeId"])
            row = {"lakeId": e["lakeId"], "areaKm2": e.get("areaKm2"), "passesFetched": len(passes), "bytes": nb,
                   "passes": [{"date": p.when.isoformat(), "knownPct": round(p.known_pct, 1), "grassPct": p.grass_pct,
                               "toBankPct": p.grass_to_bank_pct, "observedGrassPct": round(p.observed_grass_pct, 1),
                               "accepted": p.known_pct >= SH.PASS_MIN_KNOWN_PCT} for p in passes]}
            if ref is not None and cand["readiness"] != "BLOCKED":
                ob = SH.observe_shared(passes, ref, e.get("areaKm2"))
                used = [p for p in passes if p.known_pct >= SH.PASS_MIN_KNOWN_PCT and abs((p.when - ref).days) <= C.PERSISTENCE_WINDOW_DAYS
                        and getattr(p, "codes", None) is not None and p.corners]
                if used and ob.evidence_kind != "NONE":
                    ob.zones = SH.zones_from_codes([p.codes for p in used], used[0].corners, used[0].cell_m)
                observations[e["lakeId"]] = ob
            report.append(row)
        w = DryRunWriter()
        r1 = publish(manifest, w, observations=observations, now=now)
        n1 = len(w.patches)
        r2 = publish(manifest, w, observations=observations, now=now)
        cpu = time.process_time() - t0
        states = {}
        for lid in observations:
            from sector_brain_platform import lake_key
            st = w.tree["lakes"][lake_key(lid)]["states"]["vegetation"]
            sv, ob = st["surfaceVegetation"], st["observation"]
            states[lid] = {"generatedAt": st["generatedAt"], "headline": st["headline"], "status": sv["status"], "statusReason": sv["statusReason"],
                           "coverageClass": sv["coverageClass"], "observedAt": sv["observedAt"], "ageDays": sv["ageDays"],
                           "observedAreaKm2": sv.get("observedAreaKm2"), "confidence": sv["confidence"]["level"], "confidenceScore": sv["confidence"]["score"],
                           "evidenceKind": ob["evidenceKind"], "persistence": ob["persistence"], "acceptedScenes": ob["acceptedScenes"],
                           "refusalShares": ob["refusalShares"], "lowCoverageFallback": ob["lowCoverageFallback"], "notes": ob["notes"],
                           "claimMaturity": {k: v["state"] for k, v in st["claimMaturity"].items()},
                           "inputFingerprint": st["provenance"]["inputFingerprint"], "stateBytes": len(json.dumps(st)),
                           "sceneIds": sv["source"]["sceneIds"][:6], "source": sv["source"]["sourceId"],
                           "zones": (sv.get("zones") or {}).get("zones"), "zoneCountAboveMin": (sv.get("zones") or {}).get("zoneCountAboveMin")}
        out = {"generatedAt": now.isoformat(), "lakes": report, "states": states,
               "run1": {k: r1.get(k) for k in ("evaluated", "observed", "skippedUnchanged", "writes", "health")},
               "run2": {k: r2.get(k) for k in ("evaluated", "observed", "skippedUnchanged", "writes", "health")},
               "patchesAfterRun1": n1, "patchesAfterRun2": len(w.patches), "bytesFetched": total_bytes, "cpuSeconds": round(cpu, 2),
               "wallSeconds": round(time.time() - wall0, 1), "stateBytesTotal": sum(s["stateBytes"] for s in states.values())}
        json.dump(out, open(a.out, "w"), indent=1, sort_keys=True)
        print(json.dumps({k: out[k] for k in ("run1", "run2", "patchesAfterRun1", "patchesAfterRun2", "bytesFetched", "cpuSeconds", "stateBytesTotal")}, indent=1))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
