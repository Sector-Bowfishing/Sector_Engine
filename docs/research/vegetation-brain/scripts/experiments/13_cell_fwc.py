"""Cell-level Sector grass rule vs FWC LTM point intercepts (presence-only). Recall on cells holding surface (floating/emergent) points,
vote rate on submersed-only cells, flag rate on unsurveyed cells, for single/shipped/persistence methods."""
import sys, json, numpy as np, importlib
from pathlib import Path
from scipy import ndimage
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
M = importlib.import_module("12_cell_metrics")
LAKES = ["Orange","Griffin","Apopka","Harris","Panasoffkee","Yale","Cypress"]
agg = {}; per = {}; info = {}
for nm in LAKES:
    z = np.load(ROOT/f"out/cell_fwc_{nm}.npz", allow_pickle=True)
    out = M.methods(z, 45)
    if out is None: print("no scenes", nm); continue
    m, i0, N, d0, good, votes, inf = out
    cl = z["clarity"]
    tr = {k[6:]: np.nan_to_num(z[k]) for k in z.files if k.startswith("truth_")}
    surf = (np.maximum(tr.get("floating", 0), tr.get("emergent", 0)) > 0) & cl
    flo = (tr.get("floating", 0) > 0) & cl; emg = (tr.get("emergent", 0) > 0) & ~flo & cl
    sub = (tr.get("submersed", 0) > 0) & ~surf & cl
    anyp = np.zeros_like(cl)
    for v in tr.values(): anyp |= v > 0
    bg = cl & (ndimage.distance_transform_edt(~anyp) > 3)       # >3 cells (~130 m) from any recorded point
    info[nm] = dict(**inf, N=N, single=str(d0), surf=int(surf.sum()), floating=int(flo.sum()), emergent=int(emg.sum()), sub_only=int(sub.sum()), bg=int(bg.sum()))
    for mn, pred in m.items():
        for key, msk in (("surface", surf), ("floating", flo), ("emergent", emg), ("submersed_only", sub), ("background_flag", bg)):
            a = agg.setdefault((mn, key), np.zeros(2, int)); a += [int((pred & msk).sum()), int(msk.sum())]
            per[f"{nm}|{mn}|{key}"] = round((pred & msk).sum() / max(1, msk.sum()), 3)
res = {}
for (mn, key), (a, n) in agg.items(): res.setdefault(mn, {})[key] = dict(hit=int(a), n=int(n), rate=round(a / max(1, n), 3))
json.dump(dict(pooled=res, per=per, lakes=info), open(ROOT/"out/metrics_cell_fwc.json", "w"), indent=1)
for mn, d in res.items():
    print(mn.ljust(46), " ".join(f"{k}={v['rate']:.3f}" for k, v in d.items()))
print(json.dumps(info, indent=0)[:1500])
