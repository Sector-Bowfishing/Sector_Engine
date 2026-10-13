"""Reitz Lake MN: S2 indices vs sonar biovolume (fraction of water column = canopy height / depth), per scene, shore-matched. Unknown survey date -> all clear summer scenes."""
import sys, json, numpy as np, datetime as dt
from pathlib import Path
from scipy.ndimage import binary_closing, binary_fill_holes, distance_transform_edt
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
import bvlib
z = np.load(ROOT/"out/stack_carver_reitz.npz", allow_pickle=True)
X, V, dates, BV, npts = z["X"], z["V"], z["dates"], z["BV"], z["npts"]; idx = list(z["idx"])
surv = binary_fill_holes(binary_closing(npts > 0, iterations=2))
dist = distance_transform_edt(surv) * 10.0                      # m to edge of surveyed region (proxy for shore)
core = surv & (dist >= 10)
none = core & (BV < 0.02); anyv = core & (BV >= 0.10); hi = core & (BV >= 0.50); mod = core & (BV >= 0.25)
print("pixels: none", none.sum(), ">=0.10", anyv.sum(), ">=0.25", mod.sum(), ">=0.5", hi.sum())
bins = [(0.02, 0.10), (0.10, 0.25), (0.25, 0.5), (0.5, 1.01)]
rows = []
for i, d in enumerate(dates):
    valid = V[i] & core
    if valid.sum() / max(1, core.sum()) < 0.75: continue
    f = bvlib.features(X[i], idx, none_mask=none & V[i])
    r = {"date": str(d), "valid": round(float(valid.sum() / core.sum()), 2)}
    for cname, pos in (("any>=0.10", anyv), ("mod>=0.25", mod), ("high>=0.50", hi)):
        sel = valid & (pos | none); y = pos[sel]; w = bvlib.match_weights(y, dist[sel])
        r[cname] = {k: (None if (a := bvlib.auc(f[k][sel], y, w)) is None else round(a if bvlib.ORIENT.get(k, 1) > 0 else 1 - a, 3)) for k in f}
    for lo, hi_ in bins:
        pos = core & (BV >= lo) & (BV < hi_); sel = valid & (pos | none); y = pos[sel]
        if y.sum() < 30: continue
        w = bvlib.match_weights(y, dist[sel])
        r[f"bin{lo}-{hi_}"] = {k: (None if (a := bvlib.auc(f[k][sel], y, w)) is None else round(a if bvlib.ORIENT.get(k, 1) > 0 else 1 - a, 3)) for k in ["NDVI", "NDAVI", "FAI", "NDRE1", "lnG_B", "lnR_B", "DII_G_B", "DII_G_R", "NIR", "SWIR"]}
        r[f"bin{lo}-{hi_}"]["n"] = int(y.sum())
    sec = (f["NDVI"] >= 0.30)  # approximate (B8 version); exact B8A rule
    nds = X[i][idx.index("NDVI_sector")] >= 0.30
    r["sector_flag_rate_none"] = round(float(nds[none & V[i]].mean()), 3); r["sector_recall_any"] = round(float(nds[anyv & V[i]].mean()), 3); r["sector_recall_high"] = round(float(nds[hi & V[i]].mean()), 3) if (hi & V[i]).sum() else None
    rows.append(r)
json.dump(rows, open(ROOT/"out/metrics_carver_reitz.json", "w"), indent=1)
for r in rows:
    print(r["date"], r["valid"], "any:", {k: r["any>=0.10"][k] for k in ["NDVI", "NDAVI", "FAI", "lnG_B", "DII_G_B", "DII_G_R", "NIR"]}, "hi:", {k: r["high>=0.50"][k] for k in ["NDVI", "NDAVI", "DII_G_B"]}, "sector", r["sector_flag_rate_none"], r["sector_recall_any"], r["sector_recall_high"])
