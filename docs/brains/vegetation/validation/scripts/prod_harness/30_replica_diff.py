"""Replica (note 05, scripts/cell_lib.py) vs IMPORTED production: per-scene cell agreement and re-run of note-05's own metric code on production arrays."""
import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, json, importlib, shutil, os, warnings
warnings.filterwarnings("ignore")
from pathlib import Path
EXP = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments")
H = EXP/"adoption/prod_harness"
sys.path.insert(0, str(EXP/"scripts"))
import cell_lib as C
SNOCO = ["Serene","Blackmans","Storm","Roesiger","Bosworth"]; FWC = ["Orange","Griffin","Apopka","Harris","Panasoffkee","Yale","Cypress"]
rep = {}
shimA = H/"out/_shim_all"; shimB = H/"out/_shim_gate"
for d in (shimA, shimB): (d/"out").mkdir(parents=True, exist_ok=True)
tot = dict(scenes=0, cells=0, vote_diff=0, gfrac_diff=0, nan_diff=0, read_diff=0, scenes_with_any_diff=0, maxabs=0.0)
per = {}
for tag, names in (("snoco", SNOCO), ("fwc", FWC)):
    for nm in names:
        zr = np.load(EXP/f"out/cell_{tag}_{nm}.npz", allow_pickle=True); zp = np.load(H/f"out/cells50_{tag}_{nm}.npz", allow_pickle=True)
        assert zr["lake"].shape == zp["lake"].shape and (zr["lake"] == zp["lake"]).all() and (zr["clarity"] == zp["clarity"]).all(), "frame mismatch"
        lake = zp["lake"]; S = zr["G"].shape[0]; dv = dg = dn = dr = nd = 0; mx = 0.0
        for i in range(S):
            if not zp["ok"][i]: continue
            Gp = zp["gfrac"][i]; Hp = zp["read"][i]; vp = zp["grass_prod"][i]
            vr = C.grass_vote(zr["G"][i], zr["H"][i], zr["clarity"])
            a = int((vr != vp)[lake].sum()); dv += a
            nanm = (np.isnan(zr["G"][i]) != np.isnan(Gp))[lake].sum(); dn += int(nanm)
            diff = np.abs(np.nan_to_num(zr["G"][i]) - np.nan_to_num(Gp))[lake]; dg += int((diff > 1e-4).sum()); mx = max(mx, float(diff.max()) if diff.size else 0)
            dr += int((zr["H"][i] != Hp)[lake].sum()); nd += int(lake.sum())
            tot["scenes_with_any_diff"] += int(a > 0 or nanm > 0)
        tot["scenes"] += int(zp["ok"].sum()); tot["cells"] += nd; tot["vote_diff"] += dv; tot["gfrac_diff"] += dg; tot["nan_diff"] += dn; tot["read_diff"] += dr; tot["maxabs"] = max(tot["maxabs"], mx)
        per[f"{tag}|{nm}"] = dict(scenes=int(zp["ok"].sum()), cells_compared=nd, vote_diff=dv, gfrac_diff=dg, nan_diff=dn, read_diff=dr, max_abs_gfrac_diff=mx,
                                  prod_gate_rejected_scenes=int(sum(1 for r in zp["rejected"] if str(r))))
        # shim files for note-05's own metric code
        for shim, drop in ((shimA, False), (shimB, True)):
            G = zp["gfrac"].copy(); Hh = zp["read"].copy(); clear = zr["clear"].copy()
            if drop:
                for i in range(S):
                    if str(zp["rejected"][i]) or not zp["ok"][i]: G[i] = np.nan; Hh[i] = False; clear[i] = 0.0
            keep = {k: zr[k] for k in zr.files if k not in ("G", "H", "clear")}
            np.savez_compressed(shim/f"out/cell_{tag}_{nm}.npz", G=G, H=Hh, clear=clear, **keep)
rep["per_scene_cell_agreement"] = dict(total=tot, per_lake=per)
# note-05 metric code re-run on production arrays
M = importlib.import_module("12_cell_metrics")
orig = json.load(open(EXP/"out/metrics_cell_snoco.json"))
res = {}
for label, shim in (("prod_arrays_all_scenes", shimA), ("prod_arrays_minus_gate_rejected", shimB)):
    M.ROOT = shim; M.tag = "snoco"
    out = {}
    for win in (45, 21):
        r, pooled, perj = M.run(win)
        sel = {k.split("|")[2]: v for k, v in pooled.items() if k.startswith("floating_leaf>=0.5 vs strict-none(<0.05 any class)") and "grass-eligible" in k}
        out[f"win{win}"] = sel
    res[label] = out
rep["note05_metric_code_on_prod_arrays"] = res
rep["note05_original"] = {f"win{w}": {k.split("|")[2]: v for k, v in orig[f"win{w}"]["pooled"].items() if k.startswith("floating_leaf>=0.5 vs strict-none(<0.05 any class)") and "grass-eligible" in k} for w in (45, 21)}
# FWC surface recall, note-05 method set, on prod arrays vs original metrics_cell_fwc.json
from scipy import ndimage
fo = json.load(open(EXP/"out/metrics_cell_fwc.json"))["pooled"]
fres = {}
for label, shim in (("prod_arrays_all_scenes", shimA), ("prod_arrays_minus_gate_rejected", shimB)):
    agg = {}
    for nm in FWC:
        z = np.load(shim/f"out/cell_fwc_{nm}.npz", allow_pickle=True)
        out = M.methods(z, 45)
        if out is None: continue
        m = out[0]; cl = z["clarity"]
        tr = {k[6:]: np.nan_to_num(z[k]) for k in z.files if k.startswith("truth_")}
        surf = (np.maximum(tr.get("floating", 0), tr.get("emergent", 0)) > 0) & cl
        for mn in ("single (closest clear date)", "SHIPPED pass (cov>=0.5, closest to survey)", "median g' >= 0.5"):
            if mn in m:
                a = agg.setdefault(mn, np.zeros(2, int)); a += [int((m[mn] & surf).sum()), int(surf.sum())]
    fres[label] = {k: round(v[0] / max(1, v[1]), 3) for k, v in agg.items()}
rep["fwc_surface_recall_note05_methods"] = dict(prod=fres, original={k: fo[k]["surface"]["rate"] for k in ("single (closest clear date)", "SHIPPED pass (cov>=0.5, closest to survey)", "median g' >= 0.5") if k in fo})
json.dump(rep, open(H/"out/replica_vs_production.json", "w"), indent=1)
print(json.dumps(rep["per_scene_cell_agreement"]["total"]))
for k, v in rep["note05_original"]["win45"].items():
    if k.startswith(("single", "SHIPPED", "median g' >= 0.5", "max")): print("orig ", k.ljust(44), {a: v[a] for a in ("tp","fp","fn","P","R","F1")})
for lab in res:
    for k, v in res[lab]["win45"].items():
        if k.startswith(("single", "SHIPPED", "median g' >= 0.5", "max")): print(lab[:24].ljust(24), k.ljust(44), {a: v[a] for a in ("tp","fp","fn","P","R","F1")})
print(json.dumps(rep["fwc_surface_recall_note05_methods"], indent=0))
