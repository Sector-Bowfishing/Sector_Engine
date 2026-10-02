"""Stage 12 shared helpers (rules from PREREGISTRATION_STAGE12.md). Reuses the Stage 11 folds, classes and water types."""
import json, math, os, sys, glob, random, collections
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D12 = f"{S}/stage12"
sys.path.insert(0, f"{S}/stage11/analysis"); sys.path.insert(0, f"{S}/stage10/frozen")
from common import champ, cls, fold, lake_boot, insitu_type, ndci, FT     # Stage 11 definitions
from p1 import p1 as P1
import p2 as P2, models as M
sys.path.insert(0, os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion/jobs/lake-surface"))
import derive_water_surface as dws
BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"]
def dog(r):
    r = max(r, 0.0); return float(dws.TURB_SATURATED_FNU if r >= dws.TURB_SATURATED else dws.TURB_A * r / max(1e-6, 1 - r / dws.TURB_C))
def gunt(x):
    return x["set"] == "G" or (34.27 <= x["lat"] <= 35.06 and -86.42 <= x["lon"] <= -85.60)
def owt_from(raw, fnu, sun, swir):
    """Stage 11 section 6 satellite water type, on any reflectance (raw: blue/green/red/re1; swir = B11)."""
    if sun is None or sun < 20: return "unsupported"
    if any(raw.get(k) is None for k in ("blue", "green", "red", "re1")): return "unsupported"
    if not all(0.001 < raw[k] < 0.15 for k in ("blue", "green", "red", "re1")): return "unsupported"
    if swir is not None and swir > 0.02: return "unsupported"
    if raw["re1"] < 0.003 and raw["red"] > 0.02: return "unsupported"
    nd = (max(raw["re1"], .001) - max(raw["red"], .001)) / (max(raw["re1"], .001) + max(raw["red"], .001))
    if nd > 0.03 and fnu >= 8: return "mixed"
    if nd > 0.03: return "algal"
    if fnu >= 8: return "sediment"
    return "clear"
CLASSES = ["clear", "normal", "stained", "limited"]
def cname(ft): return CLASSES[cls(ft)]
def load12():
    return json.load(open(f"{D12}/analysis/rows12.json"))
