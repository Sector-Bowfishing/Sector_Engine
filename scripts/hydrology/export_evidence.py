"""Write the per-cell Sentinel-2 evidence file for Guntersville (Clarity Fusion
Stage 1, item 8). The Water Clarity raster itself is NOT touched; this reads
the shipped raster, its measured / distance PNGs and sidecar, the per-cell
exclusion reasons (sentinel_evidence.py, which rebuilt the pass cell for cell),
and the arm grid, all on one frame.

Layers (row-major from the top row, zlib, base64):
  fnuCode        uint8   the raster's own code (log10 encoding in `encoding`), 0 = none
  source         uint8   255 observed | 3 grass bed | 2 cloud/haze | 1 unreadable | 0 off lake
  distanceCode   uint8   estimated cells: 1 + through-water m to a reading / step; 0 observed/none
  reason         uint8   0 observed; 1-22 the first gate the cell's pixels failed (legend);
                         30 surface grass; 40-43 read then dropped; 255 off the lake
  arm            uint8   index into `arms` (0 = main stem)
  visCentral/Low/High uint16  canonical visibility (VisibilityModel secchi-power-v1), 0.01 ft

usage: geo/bin/python export_evidence.py <evidence audit prefix> <final dir> <out.json>
"""
import sys, os, json, zlib, base64, math
import numpy as np
from PIL import Image

prefix, final, out = sys.argv[1:4]
A = os.path.expanduser("~/Desktop/Development/iOS/Sector-mapbox/Sector/Assets.xcassets/FishIntel/")
meta = json.load(open(A + "GuntersvilleClarityMeta.dataset/Guntersville.clarity.json"))
q = np.asarray(Image.open(A + "GuntersvilleClarity.dataset/Guntersville.clarity.png"))
if q.ndim == 3:
    q = q[..., 0]
src = np.asarray(Image.open(A + "GuntersvilleClarityMeasured.dataset/Guntersville.clarity.measured.png"))
dist = np.asarray(Image.open(A + "GuntersvilleClarityDistance.dataset/Guntersville.clarity.distance.png"))
reason = np.load(prefix + ".reason.npy")
audit = json.load(open(prefix + ".json"))
assert audit["reproducesShipped"], "the evidence rebuild does not match the shipped raster"
cells = json.load(open(os.path.join(final, "guntersville.arm_cells.json")))
arm = np.frombuffer(zlib.decompress(base64.b64decode(cells["armGrid"])), np.uint8).reshape(cells["height"], cells["width"])
assert q.shape == arm.shape == reason.shape, (q.shape, arm.shape, reason.shape)

e = meta["encoding"]; lo, hi, top = e["lo"], e["hi"], e["top"]
fnu = np.where((q > 0) & (q <= top), 10 ** (lo + (q.astype(float) - 1) / (top - 1) * (hi - lo)), np.nan)
# VisibilityModel.secchi-power-v1 (Sources/SectorEngine/Hydrology/VisibilityModel.swift)
A_, B_ = 11.123, -0.637
central = A_ * np.maximum(np.nan_to_num(fnu, nan=1.0), 0.1) ** B_
lo_obs, hi_obs = -0.356, 0.520
step = meta["measured"]["distanceStepM"]
d_m = np.where(dist > 0, (dist.astype(float) - 1) * step, np.inf)
err_tab = [(250, 0.32), (500, 0.45), (1000, 0.60), (2000, 0.78), (5000, 0.94), (math.inf, 1.11)]
err_ft = np.select([d_m <= t for t, _ in err_tab], [v for _, v in err_tab], 1.11)
w = np.log10(1 + err_ft / np.maximum(central, 0.1))
estimated = (src > 0) & (src < 255)
lo_l = np.where(estimated, -np.sqrt(lo_obs ** 2 + w ** 2), lo_obs)
hi_l = np.where(estimated, np.sqrt(hi_obs ** 2 + w ** 2), hi_obs)
valued = ~np.isnan(fnu)
def cft(x):
    return np.where(valued, np.clip(np.round(x * 100), 0, 65535), 0).astype(np.uint16)
layers = {"fnuCode": q.astype(np.uint8), "source": src.astype(np.uint8), "distanceCode": dist.astype(np.uint8),
          "reason": reason.astype(np.uint8), "arm": arm.astype(np.uint8),
          "visCentral": cft(central), "visLow": cft(central * 10 ** lo_l), "visHigh": cft(central * 10 ** hi_l)}
enc = {k: {"dtype": str(v.dtype), "data": base64.b64encode(zlib.compress(v.tobytes(), 9)).decode()} for k, v in layers.items()}
reasons = {0: "observed", 1: "no scene data", 2: "SCL defective", 3: "SCL cloud", 4: "SCL cirrus", 5: "SCL cloud shadow",
           6: "SCL snow", 7: "SCL dark area", 8: "SCL vegetation inside the outline", 9: "SCL bare/not vegetated",
           10: "SCL unclassified", 11: "within 60 m of cloud/shadow", 12: "within 600 m of a real cloud",
           13: "haze at a cloud edge", 14: "hazy water", 15: "within 100 m of bright water (hull/missed cloud)",
           16: "touching an SCL bank pixel", 17: "within 100 m of a structure", 18: "SWIR too high",
           19: "floating-algae index", 20: "NDVI > 0.10", 21: "invalid red", 22: "no tile pixel in the cell",
           30: "surface grass (NDVI >= 0.3)", 40: "read, dropped: muddy speck", 41: "read, dropped: shadow patch",
           42: "read, dropped: patch under 5 cells", 43: "read, dropped: muddy pocket beside grass", 255: "off the lake"}
doc = {"lakeId": "Guntersville|AL", "pass": meta["pass"], "observationDate": meta["pass"]["date"],
       "width": int(q.shape[1]), "height": int(q.shape[0]), "cornersLonLat": cells["cornersLonLat"],
       "cellMetresMercator": meta.get("cellMetresMercator", 36.0), "encoding": e,
       "sourceCodes": {"255": "observed", "3": "grass bed (estimated)", "2": "cloud/haze (estimated)",
                       "1": "unreadable (estimated)", "0": "off the lake"},
       "distanceStepM": step, "reasons": {str(k): v for k, v in reasons.items()},
       "arms": cells["arms"], "visibilityModel": "secchi-power-v1 (11.123*FNU^-0.637 ft; 80% range)",
       "counts": {"observed": int((src == 255).sum()), "estimated": int(estimated.sum())},
       "layers": enc}
json.dump(doc, open(out, "w"))
print(f"wrote {out}: {os.path.getsize(out) / 1e6:.1f} MB; observed {doc['counts']['observed']:,}, estimated {doc['counts']['estimated']:,}")
