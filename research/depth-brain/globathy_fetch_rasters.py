#!/usr/bin/env python3
"""Fetch individual GLOBathy bathymetry GeoTIFFs out of the 16.7 GB figshare zip with HTTP range requests
(zip central directory index from globathy_zip_index.py). Usage: globathy_fetch_rasters.py <hylak_id> [...] or --fleet.
Raster dir: Sector_Research_Data/depth-brain/globathy/rasters/  (never committed)."""
import sys, struct, zlib, subprocess, os, pandas as pd
from concurrent.futures import ThreadPoolExecutor
R = "/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/globathy/"
URL = "https://ndownloader.figshare.com/files/28919850"
os.makedirs(R + "rasters", exist_ok=True)
z = pd.read_csv(R + "zip_index.csv")
z["hid"] = z.name.str.extract(r"/(\d+)_bathymetry\.tif$")[0].astype(float)
z = z.dropna(subset=["hid"]).set_index("hid")

def fetch(h):
    h = int(h); out = f"{R}rasters/{h}.tif"
    if os.path.exists(out) and os.path.getsize(out) > 0: return h, "cached"
    r = z.loc[h]
    if r.offset == 0xFFFFFFFF: return h, "offset_unresolved"
    off = int(r.offset); n = 30 + 400 + int(r.csize)
    p = subprocess.run(["curl", "-sL", "--retry", "3", "-r", f"{off}-{off+n-1}", URL], capture_output=True, timeout=600)
    b = p.stdout
    if b[:4] != b"PK\x03\x04": return h, f"bad_header({len(b)})"
    nl, el = struct.unpack("<HH", b[26:30]); s = 30 + nl + el
    data = b[s:s + int(r.csize)]
    raw = zlib.decompress(data, -15) if r.method == 8 else data
    open(out, "wb").write(raw)
    return h, "ok"

if __name__ == "__main__":
    ids = sys.argv[1:]
    if ids == ["--fleet"]:
        ids = pd.read_csv("/Users/mcather/Desktop/Development/Sector_Engine-depth-research/docs/research/depth-brain/data/globathy_fleet_match.csv").hl_id.dropna().astype(int).unique().tolist()
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(fetch, ids))
    from collections import Counter
    print(Counter(s.split("(")[0] for _, s in res)); print([r for r in res if r[1] not in ("ok", "cached")][:20])
