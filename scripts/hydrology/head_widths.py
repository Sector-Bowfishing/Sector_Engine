"""Stage 3B item 11/12: how wide is the water in each zone? (Feasibility.)

Width ~ 2 x the distance to the nearest non-lake cell, taken at each zone's
'channel' cells (the 90th percentile of distance-to-shore within the zone,
i.e. mid-channel), on the 29.6 m frame. Reported with the pixels a 10 m
sensor keeps across that width after one bank pixel each side (Sentinel-2 as
read in production) and a 3 m one (PlanetScope-class).

usage: geo/bin/python head_widths.py <positions dir> <out.json>
"""
import sys, json, os
import numpy as np
from scipy import ndimage
P = np.load(os.path.join(sys.argv[1], "arm_positions.npz")); Z = json.load(open(os.path.join(sys.argv[1], "arm_zones.json")))
G = Z["frame"]["cellGroundM"]
d = ndimage.distance_transform_edt(P["lake"]) * G       # metres to the nearest non-lake cell centre
zone = P["zone"]
out = {}
for z in Z["zones"]:
    m = zone == z["zone"]
    if not m.any(): continue
    mid = float(np.percentile(d[m], 90)); med = float(np.median(d[m]))
    w = 2 * mid
    out[f"{z['arm']} {z['name']}"] = {"of": z["of"], "midChannelWidthM": round(w), "medianCellToShoreM": round(med),
                                      "s2PixelsAcrossAfterBanks": max(0, int(w // 10) - 2), "p3mPixelsAcrossAfterBanks": max(0, int(w // 3) - 2)}
json.dump(out, open(sys.argv[2], "w"), indent=1)
for k, v in out.items():
    if v["of"] == 5 and (" head" in k or " upper" in k): print(k, v)
