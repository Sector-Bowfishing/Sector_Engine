"""Score S/A/P on Snohomish polygons (cell presence/absence) and FWC LTM points (recall only).
usage: 20_score.py CELL_M MODE USE_REJECTED(0/1)   -> out/score_{CELL}_{MODE}_rej{U}.json"""
import sys; sys.dont_write_bytecode = True
sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
import numpy as np, json, datetime as dt, warnings
warnings.filterwarnings("ignore")
from scipy import ndimage
from pathlib import Path
import score_lib as SL
ROOT = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/prod_harness")
CELL, MODE, USEREJ = int(sys.argv[1]), sys.argv[2], bool(int(sys.argv[3]))
SNOCO = ["Serene","Blackmans","Storm","Roesiger","Bosworth"]; FWC = ["Orange","Griffin","Apopka","Harris","Panasoffkee","Yale","Cypress"]

def load(tag, nm): return np.load(ROOT/f"out/cells{CELL}_{tag}_{nm}.npz", allow_pickle=True)

def snoco_truth(z):
    nz = lambda k: np.nan_to_num(z[k]) if k in z.files else np.zeros(z["lake"].shape, "float32")
    tfl, tsub, tarr = nz("truth_floating_leaf"), nz("truth_submerged_assemblage"), nz("truth_arrowhead")
    anyv = np.maximum(np.maximum(tfl, tsub), tarr)
    pos = tfl >= 0.5
    neg_strict = anyv < 0.05
    neg_buf = ndimage.distance_transform_edt(anyv < 0.05) > 2.0
    return pos, neg_strict, neg_buf

def counts(st, pos, neg, w, bins=None):
    """cell confusion with UNKNOWN handling. pos/neg are boolean masks already restricted to the analysed population.
    w: per-cell weight for negatives (matched), None = 1."""
    flag = st == SL.FLAG; known = (st == SL.CLEAR) | flag
    wn = np.ones(st.shape) if w is None else w
    d = dict(tp=int((flag & pos).sum()), fn_known=int((~flag & known & pos).sum()), pos_unknown=int((~known & pos).sum()), npos=int(pos.sum()),
             fp=int((flag & neg).sum()), tn=int((~flag & known & neg).sum()), neg_unknown=int((~known & neg).sum()), nneg=int(neg.sum()),
             fpw=float((wn * (flag & neg)).sum()), tnw=float((wn * (~flag & known & neg)).sum()), unkw=float((wn * (~known & neg)).sum()))
    return d

def metrics_from(d):
    tp, fp = d["tp"], d["fp"]; fn_all = d["npos"] - tp; fn_known = d["fn_known"]
    out = {}
    # raw prevalence, UNKNOWN positives counted as misses (headline) and recall among known
    P, R, F, I = SL_prf(tp, fp, fn_all)
    out.update(P_raw=P, R_all=R, F1_raw=F, IoU_raw=I, R_known=tp / max(1, tp + fn_known) if tp + fn_known else float("nan"),
               FPR_raw_all=d["fp"] / max(1, d["nneg"]), FPR_raw_known=d["fp"] / max(1, d["fp"] + d["tn"]),
               pos_unknown_share=d["pos_unknown"] / max(1, d["npos"]), neg_unknown_share=d["neg_unknown"] / max(1, d["nneg"]))
    # shore-matched (negatives weighted to positives' distance histogram; prevalence 50 %)
    Pm = tp / (tp + d["fpw"]) if tp + d["fpw"] > 0 else float("nan")
    R = out["R_all"]; Fm = 2 * Pm * R / (Pm + R) if Pm == Pm and R == R and Pm + R > 0 else float("nan")
    Im = tp / (tp + d["fpw"] + fn_all) if tp + d["fpw"] + fn_all > 0 else float("nan")
    spec = d["tnw"] / (d["tnw"] + d["fpw"]) if d["tnw"] + d["fpw"] > 0 else float("nan")
    out.update(P_matched=Pm, F1_matched=Fm, IoU_matched=Im, BA_matched=(R + spec) / 2 if spec == spec and R == R else float("nan"),
               FPR_matched=d["fpw"] / max(1e-9, d["fpw"] + d["tnw"] + d["unkw"]) if (d["fpw"] + d["tnw"] + d["unkw"]) > 0 else float("nan"))
    return out

def SL_prf(tp, fp, fn):
    P = tp / (tp + fp) if tp + fp > 0 else float("nan")
    R = tp / (tp + fn) if tp + fn > 0 else float("nan")
    F = 2 * P * R / (P + R) if P == P and R == R and P + R > 0 else float("nan")
    I = tp / (tp + fp + fn) if tp + fp + fn > 0 else float("nan")
    return P, R, F, I

def main():
    res = {"cell": CELL, "mode": MODE, "use_rejected": USEREJ, "snoco": {}, "fwc": {}}
    # ------------------------------------------------------------------ Snohomish
    LK = {}
    for nm in SNOCO:
        z = load("snoco", nm); ref = dt.date.fromisoformat(str(z["survey"]))
        sc = SL.prep(z, MODE, USEREJ)
        bins, dist = SL.dist_bin(z)
        pos, nstrict, nbuf = snoco_truth(z)
        LK[nm] = dict(z=z, ref=ref, sc=sc, bins=bins, pos=pos, nstrict=nstrict, nbuf=nbuf, cl=z["clarity"], lake=z["lake"])
    for oname, ofn in SL.OBS.items():
        for negname in ("nstrict", "nbuf"):
            # pooled shore matching weights (reachable = clarity population)
            nb = len(SL.BINS) - 1
            ph = np.zeros(nb); nh = np.zeros(nb)
            for nm, L in LK.items():
                ph += np.bincount(L["bins"][L["pos"] & L["cl"]], minlength=nb)[:nb]
                nh += np.bincount(L["bins"][L[negname] & L["cl"]], minlength=nb)[:nb]
            wb = np.where(nh > 0, ph / np.maximum(nh, 1), 0.0)
            pos_matchable = float(ph[nh > 0].sum()); 
            per = {}; perw = []
            for nm, L in LK.items():
                st, info = ofn(L["z"], L["sc"], L["ref"])
                pos, neg, cl = L["pos"] & L["cl"], L[negname] & L["cl"], L["cl"]
                w = wb[L["bins"]]
                d = counts(st, pos, neg, w)
                # whole-lake positives (incl. shore band, where the observer must refuse): recall with shore-band positives as misses
                d["npos_wholelake"] = int(L["pos"].sum()); d["pos_in_shore_band"] = int((L["pos"] & ~cl).sum())
                m = metrics_from(d); m["R_wholelake"] = d["tp"] / max(1, d["npos_wholelake"])
                # per-lake own shore matching (only if >= 3 positives)
                if d["npos"] >= 3:
                    ph1 = np.bincount(L["bins"][pos], minlength=nb)[:nb]; nh1 = np.bincount(L["bins"][neg], minlength=nb)[:nb]
                    wb1 = np.where(nh1 > 0, ph1 / np.maximum(nh1, 1), 0.0)
                    d1 = counts(st, pos, neg, wb1[L["bins"]]); m1 = metrics_from(d1)
                    m["P_matched_ownweights"] = m1["P_matched"]; m["F1_matched_ownweights"] = m1["F1_matched"]
                # UNKNOWN accounting on all clarity cells
                unk = {SL.NAMES[c]: int(((st == c) & cl).sum()) for c in SL.NAMES}
                m.update(d=d, info={k: v for k, v in info.items() if k != "A"}, unknown_cells=unk, clarity_cells=int(cl.sum()),
                         flagged_cells=int(((st == SL.FLAG) & cl).sum()))
                per[nm] = m; perw.append({k: d[k] for k in ("tp","fn_known","pos_unknown","npos","fp","tn","neg_unknown","nneg","fpw","tnw","unkw")})
            tot = {k: sum(p[k] for p in perw) for k in perw[0]}
            pooled = metrics_from(tot); pooled["d"] = tot; pooled["matchable_pos"] = pos_matchable; pooled["pos_hist"] = ph.tolist(); pooled["neg_hist"] = nh.tolist()
            lo, hi, nv = SL.bootstrap_lakes(perw, lambda t: metrics_from(t)["F1_matched"])
            lo2, hi2, nv2 = SL.bootstrap_lakes(perw, lambda t: metrics_from(t)["P_matched"])
            lo3, hi3, nv3 = SL.bootstrap_lakes(perw, lambda t: metrics_from(t)["R_all"])
            lo4, hi4, nv4 = SL.bootstrap_lakes(perw, lambda t: metrics_from(t)["FPR_raw_all"])
            pooled["boot"] = dict(F1_matched=[lo, hi, nv], P_matched=[lo2, hi2, nv2], R_all=[lo3, hi3, nv3], FPR_raw=[lo4, hi4, nv4], n_lakes=len(perw), n_lakes_with_pos=int(sum(p["npos"] > 0 for p in perw)))
            res["snoco"][f"{oname}|{negname}"] = dict(pooled=pooled, per_lake=per)
    # ------------------------------------------------------------------ FWC points (recall only)
    for nm in FWC:
        z = load("fwc", nm); ref = dt.date.fromisoformat(str(z["survey"]))
        sc = SL.prep(z, MODE, USEREJ)
        lake, cl = z["lake"], z["clarity"]
        tf = lambda k: np.nan_to_num(z[k]) > 0 if k in z.files else np.zeros(lake.shape, bool)
        fl, em, sub = tf("truth_floating"), tf("truth_emergent"), tf("truth_submersed")
        surf = (fl | em) & lake
        anyp = fl | em | sub | tf("truth_algae") | tf("truth_other")
        bg = cl & (ndimage.distance_transform_edt(~anyp) > 3.0)
        r = {}
        for oname, ofn in SL.OBS.items():
            st, info = ofn(z, sc, ref)
            flag = st == SL.FLAG; known = (st == SL.CLEAR) | flag
            def rec(mask):
                n = int(mask.sum());
                return dict(n=n, tp=int((flag & mask).sum()), recall_all=(flag & mask).sum() / max(1, n), recall_known=(flag & mask).sum() / max(1, (known & mask).sum()),
                            unknown_share=1 - (known & mask).sum() / max(1, n))
            r[oname] = dict(info={k: v for k, v in info.items() if k != "A"}, surface_reachable=rec(surf & cl), surface_all_incl_shore=rec(surf), floating=rec(fl & cl & lake),
                            emergent=rec(em & cl & lake), submersed_only=rec(sub & ~fl & ~em & cl & lake),
                            background_flag_share=dict(n=int(bg.sum()), flagged=int((flag & bg).sum()), share_known=(flag & bg).sum() / max(1, (known & bg).sum())),
                            unknown_cells={SL.NAMES[c]: int(((st == c) & cl).sum()) for c in SL.NAMES}, clarity_cells=int(cl.sum()), flagged_cells=int((flag & cl).sum()),
                            ref=str(ref), n_scenes=len(sc), n_scenes_incl_rejected=int(z["ok"].sum()), n_rejected_by_prod_gate=int(sum(1 for x in z["rejected"] if str(x) != "")))
        res["fwc"][nm] = r
    json.dump(res, open(ROOT/f"out/score_{CELL}_{MODE}_rej{int(USEREJ)}.json", "w"), indent=1, default=float)

if __name__ == "__main__": main()
