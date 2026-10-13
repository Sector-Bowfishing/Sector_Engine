#!/usr/bin/env python3
"""Depth Brain / terrain (Question B): how large is the NGVD29 -> NAVD88 vertical datum shift at each directory lake (NOAA NGS NCAT / VERTCON 3.0)?
Many operator pool figures (TVA, Duke, most older USACE, Santee Cooper) are NGVD29 or a local datum while 3DEP is NAVD88, so a DEM-vs-pool
comparison carries this shift as a systematic error.  1 req/s.  Output docs/research/depth-brain/data/datum_shift_ngvd29_navd88.csv (resumable)."""
import csv, json, sys, time
from pathlib import Path
import requests
REPO = Path(__file__).resolve().parents[2]
SRC = Path("/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/lake_features.csv")
OUT = REPO / "docs/research/depth-brain/data/datum_shift_ngvd29_navd88.csv"
FP = Path("/Users/mcather/Desktop/Development/Sector_Engine/docs/data/full_pool.csv")


def main():
    fp = {r["id"]: r for r in csv.DictReader(open(FP))}
    feats = list(csv.DictReader(open(SRC)))
    done = {}
    if OUT.exists():
        done = {r["id"]: r for r in csv.DictReader(open(OUT))}
    rows = list(done.values())
    for f in feats:
        if f["id"] in done: continue
        p = fp.get(f["id"])
        if not p or not p["fullPoolFt"]: continue
        ft = float(p["fullPoolFt"]); lat, lon = float(f["lat"]), float(f["lon"])
        if not (24 < lat < 50 and -125 < lon < -66): continue
        shift = ""
        for a in range(3):
            try:
                r = requests.get("https://geodesy.noaa.gov/api/ncat/llh", params=dict(lat=lat, lon=lon, inDatum="NAD83(2011)", outDatum="NAD83(2011)", inVertDatum="NGVD29", outVertDatum="NAVD88", orthoHt=ft * 0.3048, format="json"), timeout=60).json()
                shift = (float(r["destOrthoht"]) - float(r["srcOrthoht"])) / 0.3048; break
            except Exception:
                time.sleep(2)
        rows.append(dict(id=f["id"], state=f["state1"], operator_family=f["operator_family"], lat=lat, lon=lon, fullPoolFt=ft, basis=p["basis"], conf=p["conf"], shift_ft_ngvd29_to_navd88=("" if shift == "" else round(shift, 3))))
        time.sleep(1.0)
        if len(rows) % 25 == 0: write(rows)
    write(rows)


def write(rows):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    w = csv.DictWriter(open(OUT, "w", newline=""), fieldnames=list(rows[0]))
    w.writeheader(); w.writerows(rows)


if __name__ == "__main__":
    main()
