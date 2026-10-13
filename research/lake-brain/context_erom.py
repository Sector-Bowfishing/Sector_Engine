#!/usr/bin/env python3
"""Track 5: mean annual flow + drainage area at each matched dam from the NHDPlus HR service (EROM gage-adjusted qema, runoff qama, VAA).
Start = matched NID dam (external_join.json).  Query NetworkNHDFlowline within +-0.004 deg of the dam; keep the flowline with the largest
totdasqkm.  Output <DATA>/context/erom.json (resumable, rebuildable).  3 threads, 0.3 s spacing."""
import json, sys, time, concurrent.futures as cf
from pathlib import Path
import requests
DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
U = "https://hydro.nationalmap.gov/arcgis/rest/services/NHDPlus_HR/MapServer/3/query"
F = "gnis_name,ftype,streamorde,streamleve,totdasqkm,qama,qema,vama,hydroseq,dnhydroseq,nhdplusid,divergence,wbarea_permanent_identifier"


def one(k, y, x):
    for pad in (0.004, 0.012):
        for a in range(3):
            try:
                r = requests.get(U, params=dict(where="1=1", geometry=f"{x-pad},{y-pad},{x+pad},{y+pad}", geometryType="esriGeometryEnvelope", inSR=4326,
                                                spatialRel="esriSpatialRelIntersects", outFields=F, returnGeometry="false", f="json"), timeout=90).json()
                fs = [f["attributes"] for f in r.get("features", [])]
                if fs:
                    best = max(fs, key=lambda a: a.get("totdasqkm") or 0)
                    return k, dict(best, pad=pad)
                break
            except Exception:
                time.sleep(3 * (a + 1))
    return k, None


def main():
    ej = json.load(open(DATA / "context/external_join.json"))
    outp = DATA / "context/erom.json"
    out = json.load(open(outp)) if outp.exists() else {}
    todo = [(k, v["nid_lat"], v["nid_lon"]) for k, v in ej.items() if v.get("nid_lat") and k not in out]
    print("todo", len(todo), flush=True)
    with cf.ThreadPoolExecutor(3) as ex:
        futs = []
        for t in todo:
            futs.append(ex.submit(one, *t)); time.sleep(0.3)
        for i, f in enumerate(cf.as_completed(futs)):
            k, v = f.result(); out[k] = v
            if i % 25 == 0: outp.write_text(json.dumps(out)); print(i, k, v and (v.get("totdasqkm"), v.get("qema")), flush=True)
    outp.write_text(json.dumps(out)); print("done", len(out), sum(1 for v in out.values() if v))


if __name__ == "__main__":
    main()
