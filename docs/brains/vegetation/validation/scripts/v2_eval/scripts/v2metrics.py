"""Cell metrics for Snohomish (interior population, A1.5) and FWC recall. Logic follows v1_eval/s3_metrics_snoco_fwc.py; generalised to lake subsets and v0.2 run keys."""
from v2lib import *
BINS = [0, 15, 30, 45, 60, 90, 150, 300]
PLANT, UNK = O.PLANT, O.UNKNOWN
NB = len(BINS)

def flags(r, key, m):
    s = r["runs"][key]["obs"][m]["state"]
    if s is None:
        z = np.zeros(r["eligible"].shape, bool); return z, z
    return (s == PLANT), (s != UNK) & (s != O.OUTSIDE)

def binidx(d): return np.digitize(d, BINS[1:])

def prf(tp, fp, fn):
    P = tp / (tp + fp) if tp + fp else float("nan"); Rr = tp / (tp + fn) if tp + fn else float("nan")
    F = 2 * P * Rr / (P + Rr) if P == P and Rr == Rr and P + Rr > 0 else float("nan"); I = tp / (tp + fp + fn) if tp + fp + fn else float("nan")
    return P, Rr, F, I

def truth(r):
    L = r["lab"]; z = np.zeros_like(r["dist"])
    tfl, tsub, tarr = L.get("floating_leaf", z), L.get("submerged_assemblage", z), L.get("arrowhead", z)
    anyv = np.maximum(np.maximum(tfl, tsub), tarr)
    pos = (tfl >= 0.5) & r["eligible"]
    ns = (anyv < 0.05) & r["interior"]
    nbuf = (ndimage.distance_transform_edt(anyv < 0.05) > 2.0) & r["interior"]
    return pos, ns, nbuf

def counts(r, key, m, pos, neg, w):
    fl, kn = flags(r, key, m); it = r["interior"]
    p_i = pos & it
    return dict(tp=int((fl & p_i).sum()), fn_known=int((~fl & kn & p_i).sum()), pos_unknown=int((~kn & p_i).sum()), npos=int(p_i.sum()), npos_whole=int(pos.sum()),
                tp_whole=int((fl & pos).sum()), fp=int((fl & neg).sum()), tn=int((~fl & kn & neg).sum()), neg_unknown=int((~kn & neg).sum()), nneg=int(neg.sum()),
                fpw=float((w * (fl & neg)).sum()), tnw=float((w * (~fl & kn & neg)).sum()), unkw=float((w * (~kn & neg)).sum()),
                flagged_all=int((fl & it).sum()), interior_n=int(it.sum()), interior_unknown=int((~kn & it).sum()))

def derive(d, scale=1.0):
    tp, fp = d["tp"], d["fp"]; fn = d["npos"] - tp
    P, Rr, F, I = prf(tp, fp, fn)
    out = dict(TP=tp, FP=fp, FN=fn, npos_int=d["npos"], npos_whole=d["npos_whole"], P_raw=P, R_int=Rr, F1_raw=F, IoU_raw=I,
               R_whole=d["tp_whole"] / d["npos_whole"] if d["npos_whole"] else float("nan"),
               R_known=tp / (tp + d["fn_known"]) if tp + d["fn_known"] else float("nan"), pos_unknown_share=d["pos_unknown"] / d["npos"] if d["npos"] else float("nan"),
               FPR_all=fp / d["nneg"] if d["nneg"] else float("nan"), FPR_known=fp / (fp + d["tn"]) if fp + d["tn"] else float("nan"),
               neg_unknown_share=d["neg_unknown"] / d["nneg"] if d["nneg"] else float("nan"), nneg=d["nneg"], neg_known=fp + d["tn"],
               interior_unknown_share=d["interior_unknown"] / d["interior_n"] if d["interior_n"] else float("nan"))
    fpw = d["fpw"]; Pm = tp / (tp + fpw) if tp + fpw > 0 else float("nan")
    out["P_matched50"] = Pm; out["F1_matched50"] = 2 * Pm * Rr / (Pm + Rr) if Pm == Pm and Rr == Rr and Pm + Rr > 0 else float("nan")
    fpr_ = fpw * scale; Pr = tp / (tp + fpr_) if tp + fpr_ > 0 else float("nan")
    out["P_matched_rawprev"] = Pr; out["F1_matched_rawprev"] = 2 * Pr * Rr / (Pr + Rr) if Pr == Pr and Rr == Rr and Pr + Rr > 0 else float("nan")
    return out

def boot(per, fn, n=2000, seed=11):
    rng = np.random.default_rng(seed); L = len(per); keys = per[0].keys(); v = []
    for _ in range(n):
        ix = rng.integers(0, L, L); t = {k: sum(per[j][k] for j in ix) for k in keys}; x = fn(t)
        if x == x: v.append(x)
    return (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)), len(v)) if len(v) >= 50 else (None, None, len(v))

def snoco_eval(R, key, lakes, m, negkind="strict", bootstrap=False):
    ni = 1 if negkind == "strict" else 2
    T = {nm: truth(R[f"snoco|{nm}"]) for nm in lakes}
    ph = np.zeros(NB); nh = np.zeros(NB)
    for nm in lakes:
        r = R[f"snoco|{nm}"]; b = binidx(r["dist"]); pos, ns, nbuf = T[nm]; neg = (ns, nbuf)[ni - 1]
        ph += np.bincount(b[pos & r["interior"]], minlength=NB)[:NB]; nh += np.bincount(b[neg], minlength=NB)[:NB]
    wb = np.where(nh > 0, ph / np.maximum(nh, 1), 0.0)
    scale = (nh[ph > 0].sum() / max(ph[nh > 0].sum(), 1)) if ph.sum() else 1.0
    per = []; perlake = {}
    for nm in lakes:
        r = R[f"snoco|{nm}"]; pos, ns, nbuf = T[nm]; neg = (ns, nbuf)[ni - 1]
        d = counts(r, key, m, pos, neg, wb[binidx(r["dist"])]); per.append(d); perlake[nm] = derive(d, scale)
        o = r["runs"][key]["obs"][m]
        perlake[nm].update(kind=o["kind"], persistence=o["persistence"], n_accepted=o["n_accepted"], presence=o["presence"][0], plant_cells=o["plant_cells"])
    tot = {k: sum(p[k] for p in per) for k in per[0]}; pooled = derive(tot, scale)
    if bootstrap:
        for nmx in ("F1_raw", "P_raw", "R_int", "FPR_all", "FPR_known"):
            pooled["ci_" + nmx] = boot(per, lambda t, nmx=nmx: derive(t, scale)[nmx])
    pooled["lakes_with_ge30_pos"] = [nm for nm, d in zip(lakes, per) if d["npos"] >= 30]; pooled["lakes_with_pos"] = [nm for nm, d in zip(lakes, per) if d["npos"] > 0]
    return dict(pooled=pooled, per_lake=perlake, per_counts=dict(zip(lakes, per)))

def fwc_recall(R, key, lakes, m):
    per = []; pl = {}
    for nm in lakes:
        r = R[f"fwc|{nm}"]; L = r["lab"]; fl, kn = flags(r, key, m); it = r["interior"]; el = r["eligible"]
        surf = ((L["floating"] > 0) | (L["emergent"] > 0)) & el
        d = dict(n_all=int(surf.sum()), tp_all=int((fl & surf).sum()), known_all=int((kn & surf).sum()), n_int=int((surf & it).sum()), tp_int=int((fl & surf & it).sum()), known_int=int((kn & surf & it).sum()))
        per.append(d); pl[nm] = dict(**d, R_all=d["tp_all"] / d["n_all"] if d["n_all"] else float("nan"), R_int=d["tp_int"] / d["n_int"] if d["n_int"] else float("nan"),
                                     presence=r["runs"][key]["obs"][m]["presence"][0], kind=r["runs"][key]["obs"][m]["kind"])
    tot = {k: sum(p[k] for p in per) for k in per[0]}
    pooled = dict(tot, R_all=tot["tp_all"] / tot["n_all"], R_int=tot["tp_int"] / tot["n_int"], R_all_known=tot["tp_all"] / max(1, tot["known_all"]), R_int_known=tot["tp_int"] / max(1, tot["known_int"]))
    pooled["ci_R_all"] = boot(per, lambda t: t["tp_all"] / t["n_all"] if t["n_all"] else float("nan"))
    pooled["ci_R_int"] = boot(per, lambda t: t["tp_int"] / t["n_int"] if t["n_int"] else float("nan"))
    return dict(pooled=pooled, per_lake=pl)
