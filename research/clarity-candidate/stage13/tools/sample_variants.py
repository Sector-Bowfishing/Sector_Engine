"""Stage 13 section 8 (acolite venv): sample an unmasked ACOLITE L2W (run with l2w_mask=False) at a station under the
pre-registered mask variants. Default mask bits: 0 SWIR non-water, 1 cirrus, 2 high TOA, 3 negative, 5 mixed.
M0 default (no default bit); M1 ignore bit 3 (disk medians of B02-B05 must be > 0); M2 ignore bit 0 where NDWI(B03,B08) > 0;
M3 both. >= 5 valid pixels. Returns {variant: {B01..B12 medians, n}}."""
import numpy as np, sys, json, os
from netCDF4 import Dataset
S11 = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/stage11"
sys.path.insert(0, f"{S11}/tools/acolite")
import sample as SM
DEFAULT = (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 5)
def sample(nc_path, lat, lon, radius_m=60):
    with Dataset(nc_path) as nc:
        la, lo = np.array(nc["lat"][:]), np.array(nc["lon"][:])
        dist = np.hypot((la - lat) * 111320.0, (lo - lon) * 111320.0 * np.cos(np.radians(lat)))
        m = dist <= radius_m
        if not m.any(): return {"n_radius": 0}
        bm = SM._band_map(nc)
        vals = {b: np.array(nc[v][:], dtype="float64")[m] for b, v in bm.items()}
        fl = np.array(nc["l2_flags"][:]).astype("int64")[m]
    with np.errstate(invalid="ignore", divide="ignore"):
        ndwi = (vals["B03"] - vals["B08"]) / (vals["B03"] + vals["B08"]) if "B08" in vals else np.zeros(m.sum())
    fin = np.all([np.isfinite(vals[b]) for b in ("B02", "B03", "B04", "B05")], axis=0)
    base = fl & DEFAULT
    V = {"M0": base == 0,
         "M1": (base & ~(1 << 3)) == 0,
         "M2": ((base & ~(1 << 0)) == 0) & (((fl & 1) == 0) | (ndwi > 0)),
         "M3": ((base & ~((1 << 0) | (1 << 3))) == 0) & (((fl & 1) == 0) | (ndwi > 0))}
    out = {"n_radius": int(m.sum())}
    for k, ok in V.items():
        ok = ok & fin; n = int(ok.sum()); r = {"n": n}
        if n >= 5:
            r.update({b: float(np.median(v[ok])) for b, v in vals.items()})
            if k in ("M1", "M3") and not all(r[b] > 0 for b in ("B02", "B03", "B04", "B05")): r = {"n": n, "rejected": "non-positive median"}
        out[k] = r
    return out
if __name__ == "__main__":
    print(json.dumps(sample(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]))))
