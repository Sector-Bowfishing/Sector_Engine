"""Cell-level scoring of Sector's grass rule (+ persistence composites) against Snohomish polygons. Usage: 12_cell_metrics.py snoco"""
import sys, json, datetime as dt, numpy as np
from pathlib import Path
from scipy import ndimage
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
import cell_lib as C
tag = sys.argv[1] if __name__ == "__main__" else "snoco"
LAKES = {"snoco": ["Serene","Blackmans","Storm","Roesiger","Bosworth"]}[tag]

def prf(pred, pos, neg):
    tp = int((pred & pos).sum()); fp = int((pred & neg).sum()); fn = int((~pred & pos).sum()); tn = int((~pred & neg).sum())
    P = tp/max(1, tp+fp); R = tp/max(1, tp+fn); F = 2*P*R/max(1e-9, P+R); I = tp/max(1, tp+fp+fn)
    return dict(tp=tp, fp=fp, fn=fn, tn=tn, P=round(P,3), R=round(R,3), F1=round(F,3), IoU=round(I,3), FPR=round(fp/max(1,fp+tn),3))

def methods(z, win):
    G, H = z["G"], z["H"]; clear = z["clear"]; dates = [dt.date.fromisoformat(str(d)) for d in z["dates"]]
    sv = dt.date.fromisoformat(str(z["survey"])); cl = z["clarity"]; lake = z["lake"]
    good = [i for i in range(len(dates)) if clear[i] >= 0.75 and abs((dates[i]-sv).days) <= win]
    if not good: return None
    fr = type("F", (), {"ground_m": lambda self: float(z["ground_m"])})()
    gp = np.where(H, 0.0, G)                                   # g' : read cells cannot be grass (the 'isnan(acc)' guard)
    votes = np.stack([C.grass_vote(G[i], H[i], cl) for i in range(len(G))])
    seen = ~np.isnan(G)
    i0 = min(good, key=lambda i: abs((dates[i]-sv).days))
    # Sector pass acceptance: pass must READ >= 50 % of the non-grass clarity water (else fall back to >= 25 % if none)
    cov = np.array([((H[i] & cl & ~votes[i]).sum()) / max(1, (cl & ~votes[i]).sum()) for i in range(len(G))])
    cand = [i for i in range(len(dates)) if abs((dates[i]-sv).days) <= win]
    pas = sorted([i for i in cand if cov[i] >= 0.5], key=lambda i: abs((dates[i]-sv).days))
    if pas: ship = pas[0]
    else:
        fb = [i for i in cand if cov[i] >= 0.25]; ship = max(fb, key=lambda i: cov[i]) if fb else None
    goodp = [i for i in good if cov[i] >= 0.5]
    Gs = gp[good]; N = len(good)
    srt = np.sort(np.where(np.isnan(Gs), -1, Gs), axis=0)       # ascending; -1 = unseen
    m = {}
    m["single (closest clear date)"] = votes[i0]
    m["SHIPPED pass (cov>=0.5, closest to survey)"] = votes[ship] if ship is not None else np.zeros_like(cl)
    if len(goodp) >= 2:
        sp_ = np.sort(np.where(np.isnan(gp[goodp]), -1, gp[goodp]), axis=0)
        m["votes >= 2 of N (only cov>=0.5 passes)"] = (votes[goodp].sum(0) >= 2) & cl
        m["median g' >= 0.5 (only cov>=0.5 passes)"] = (np.nan_to_num(np.nanmedian(np.where(seen[goodp], gp[goodp], np.nan), axis=0)) >= 0.5) & cl
    m["max g' >= 0.5 (any date)"] = (srt[-1] >= 0.5) & cl
    m["votes >= 2 of N"] = (votes[good].sum(0) >= min(2, N)) & cl
    m["votes >= 3 of N"] = (votes[good].sum(0) >= min(3, N)) & cl
    m["majority of seen dates"] = (votes[good].sum(0) >= np.maximum(1, np.ceil(0.5*seen[good].sum(0)))) & (seen[good].sum(0) > 0) & cl
    m["second-highest g' >= 0.5"] = ((srt[-2] if N >= 2 else srt[-1]) >= 0.5) & cl
    med = np.nanmedian(np.where(seen[good], Gs, np.nan), axis=0) if N else None
    m["median g' >= 0.5"] = (np.nan_to_num(med) >= 0.5) & cl
    return m, i0, N, dates[i0], good, votes, dict(ship=None if ship is None else str(dates[ship]), cov_ship=None if ship is None else round(float(cov[ship]),2), n_passes=len(goodp))

def run(win):
    res = {}; per = {}
    pools = {}
    for nm in LAKES:
        z = np.load(ROOT/f"out/cell_{tag}_{nm}.npz", allow_pickle=True)
        out = methods(z, win)
        if out is None: continue
        m, i0, N, d0, good, votes, info = out
        cl = z["clarity"]; lake = z["lake"]
        tf = {k[6:]: z[k] for k in z.files if k.startswith("truth_")}
        tfl = np.nan_to_num(tf["floating_leaf"]); tsub = np.nan_to_num(tf.get("submerged_assemblage", np.zeros_like(tfl))); tarr = np.nan_to_num(tf.get("arrowhead", np.zeros_like(tfl)))
        anyv = np.maximum(np.maximum(tfl, tsub), tarr)
        defs = {
          "floating_leaf>=0.5 vs strict-none(<0.05 any class)": ((tfl >= 0.5), (anyv < 0.05)),
          "floating_leaf>=0.5 vs not-floating(<0.05 fl)": ((tfl >= 0.5), (tfl < 0.05)),
          "floating_leaf>=0.25 vs strict-none": ((tfl >= 0.25), (anyv < 0.05)),
          "floating_leaf>=0.5 vs buffered-none (no label within 2 cells)": ((tfl >= 0.5), (ndimage.distance_transform_edt(anyv < 0.05) > 2.0)),
          "any-veg>=0.5 vs strict-none": ((anyv >= 0.5), (anyv < 0.05)),
        }
        # extension variant (what ships): grass | strip behind a bed
        fr = type("F", (), {"ground_m": lambda self: float(z["ground_m"])})()
        ext = C.to_bank_extension(m["SHIPPED pass (cov>=0.5, closest to survey)"], z["H"][i0], lake, cl, fr)
        for dn, (pos, neg) in defs.items():
            for pop, mask in (("grass-eligible cells (lake eroded 40 m)", cl), ("whole lake, with bed-to-bank strip", lake)):
                for mn, pred in list(m.items()) + [("single + to_bank strip", ext)]:
                    if pop.startswith("grass") and mn.endswith("strip"): continue
                    if pop.startswith("whole") and mn != "single + to_bank strip" and not mn.startswith("single"): 
                        pass
                    pr = pred & mask if pop.startswith("grass") else (pred | False) & lake
                    key = (dn, pop, mn)
                    d = pools.setdefault(key, np.zeros(4, int))
                    r = prf(pr, pos & mask, neg & mask)
                    d += np.array([r["tp"], r["fp"], r["fn"], r["tn"]])
                    per[(nm,)+key] = r
        res[nm] = dict(**info, N=N, single_date=str(d0), n_pos=int((tfl>=0.5).sum()), n_pos_in_clarity=int(((tfl>=0.5)&cl).sum()), lake_cells=int(lake.sum()), clarity_cells=int(cl.sum()))
    pooled = {}
    for key, v in pools.items():
        tp, fp, fn, tn = v; P = tp/max(1,tp+fp); R = tp/max(1,tp+fn); F = 2*P*R/max(1e-9,P+R)
        pooled["|".join(key)] = dict(tp=int(tp), fp=int(fp), fn=int(fn), tn=int(tn), P=round(P,3), R=round(R,3), F1=round(F,3), IoU=round(tp/max(1,tp+fp+fn),3), FPR=round(fp/max(1,fp+tn),4))
    perj = {"|".join(k): v for k, v in per.items()}
    return res, pooled, perj

if __name__ == "__main__":
    allres = {}
    for win in (45, 21):
        res, pooled, perj = run(win)
        allres[f"win{win}"] = dict(lakes=res, pooled=pooled, per_lake=perj)
    json.dump(allres, open(ROOT/f"out/metrics_cell_{tag}.json", "w"), indent=1)
    r = allres["win45"]
    print(json.dumps(r["lakes"], indent=0))
    for k, v in r["pooled"].items():
        if k.startswith("floating_leaf>=0.5 vs strict") and "grass-eligible" in k: print(k.split("|")[2].ljust(34), v)
    print()
    for k, v in r["pooled"].items():
        if k.startswith("floating_leaf>=0.5 vs strict") and "whole" in k and (k.split("|")[2].startswith("single") or k.split("|")[2].startswith("SHIPPED")): print(k.split("|")[2].ljust(34), v)
