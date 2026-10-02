"""EXPLORATORY (not pre-registered; no verdict uses it): is the clear-water turbidity over-read an additive
reflectance residual? Dogliotti on (B04 - r) with r = the pixel's own B11 or B8A-derived residual, against in-situ
turbidity, same-day rows, by Secchi class. Writes explore_additive.json."""
import json, math, sys, os, numpy as np
from common import *
sys.path.insert(0, os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion/jobs/lake-surface"))
import derive_water_surface as dws
def dog(r):
    r = max(r, 0.0)
    return float(dws.TURB_SATURATED_FNU if r >= dws.TURB_SATURATED else dws.TURB_A * r / max(1e-6, 1 - r / dws.TURB_C))
rows = [x for x in load() if x.get("turb") is not None and x["dt"] == 0 and x["raw"].get("swir16") is not None]
out = {}
for c, lab in ((0, "clear >=6"), (1, "normal 3-6"), (2, "stained 2-3"), (3, "limited <2")):
    R = [x for x in rows if cls(x["secchi"]) == c]
    e0 = [math.log10(max(dog(x["raw"]["red"]), .1) / max(x["turb"], .1)) for x in R]
    e1 = [math.log10(max(dog(x["raw"]["red"] - max(x["raw"]["swir16"], 0)), .1) / max(x["turb"], .1)) for x in R]
    s0 = [math.log10(champ(dog(x["raw"]["red"])) / x["secchi"]) for x in R]
    s1 = [math.log10(champ(dog(x["raw"]["red"] - max(x["raw"]["swir16"], 0))) / x["secchi"]) for x in R]
    out[lab] = {"n": len(R), "median_eT": round(float(np.median(e0)), 3), "median_eT_minus_B11": round(float(np.median(e1)), 3),
                "median_eS": round(float(np.median(s0)), 3), "median_eS_minus_B11": round(float(np.median(s1)), 3),
                "median_abs_eS": round(float(np.median(np.abs(s0))), 3), "median_abs_eS_minus_B11": round(float(np.median(np.abs(s1))), 3),
                "median_red": round(float(np.median([x["raw"]["red"] for x in R])), 4), "median_B11": round(float(np.median([x["raw"]["swir16"] for x in R])), 4)}
json.dump(out, open("explore_additive.json", "w"), indent=1); print(json.dumps(out, indent=1))
