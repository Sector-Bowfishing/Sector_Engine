"""STEP 2a/b metrics from out/snoco_fwc_{TAG}.pkl. usage: s3_metrics_snoco_fwc.py TAG -> out/metrics_snoco_fwc_{TAG}.json + markdown on stdout"""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from v1lib import *
import pickle
TAG = sys.argv[1]
R = pickle.load(open(OUT / f"snoco_fwc_{TAG}.pkl", "rb"))
BINS = [0, 15, 30, 45, 60, 90, 150, 300]
SN = ["Serene", "Blackmans", "Storm", "Roesiger", "Bosworth"]; FW = ["Orange", "Griffin", "Apopka", "Harris", "Panasoffkee", "Yale", "Cypress"]
PLANT, UNK = O.PLANT, O.UNKNOWN
def flags(r, m):
    s = r["obs"][m]["state"]
    if s is None: z = np.zeros(r["eligible"].shape, bool); return z, z
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
    from scipy import ndimage
    nb = len(BINS)
    pos = (tfl >= 0.5) & r["eligible"]
    ns = (anyv < 0.05) & r["interior"]
    nbuf = (ndimage.distance_transform_edt(anyv < 0.05) > 2.0) & r["interior"]
    return pos, ns, nbuf
def counts(r, m, pos, neg, w):
    fl, kn = flags(r, m); it = r["interior"]
    p_i = pos & it; return dict(tp=int((fl & p_i).sum()), fn_known=int((~fl & kn & p_i).sum()), pos_unknown=int((~kn & p_i).sum()), npos=int(p_i.sum()), npos_whole=int(pos.sum()),
        tp_whole=int((fl & pos).sum()), fp=int((fl & neg).sum()), tn=int((~fl & kn & neg).sum()), neg_unknown=int((~kn & neg).sum()), nneg=int(neg.sum()),
        fpw=float((w * (fl & neg)).sum()), tnw=float((w * (~fl & kn & neg)).sum()), unkw=float((w * (~kn & neg)).sum()), flagged_all=int((fl & it).sum()))
def derive(d, scale=1.0):
    tp, fp = d["tp"], d["fp"]; fn = d["npos"] - tp
    P, Rr, F, I = prf(tp, fp, fn)
    out = dict(TP=tp, FP=fp, FN=fn, npos_int=d["npos"], npos_whole=d["npos_whole"], P_raw=P, R_int=Rr, F1_raw=F, IoU_raw=I, R_whole=d["tp_whole"] / d["npos_whole"] if d["npos_whole"] else float("nan"),
               R_known=tp / (tp + d["fn_known"]) if tp + d["fn_known"] else float("nan"), pos_unknown_share=d["pos_unknown"] / d["npos"] if d["npos"] else float("nan"),
               FPR_all=fp / d["nneg"] if d["nneg"] else float("nan"), FPR_known=fp / (fp + d["tn"]) if fp + d["tn"] else float("nan"), neg_unknown_share=d["neg_unknown"] / d["nneg"] if d["nneg"] else float("nan"), nneg=d["nneg"])
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
res = dict(tag=TAG, floor=R["snoco|Serene"]["info"]["floor"], snoco={}, fwc={}, lakes={})
nb = len(BINS)
T = {nm: truth(R[f"snoco|{nm}"]) for nm in SN}
for m in ("S", "A", "P"):
    for negname, ni in (("strict", 1), ("buffered", 2)):
        ph = np.zeros(nb); nh = np.zeros(nb)
        for nm in SN:
            r = R[f"snoco|{nm}"]; b = binidx(r["dist"]); pos, ns, nbuf = T[nm]; neg = (ns, nbuf)[ni - 1]
            ph += np.bincount(b[pos & r["interior"]], minlength=nb)[:nb]; nh += np.bincount(b[neg], minlength=nb)[:nb]
        wb = np.where(nh > 0, ph / np.maximum(nh, 1), 0.0)
        scale = (nh[ph > 0].sum() / max(ph[nh > 0].sum(), 1)) if ph.sum() else 1.0     # raw-prevalence: keep total negative weight
        per = []; perlake = {}
        for nm in SN:
            r = R[f"snoco|{nm}"]; pos, ns, nbuf = T[nm]; neg = (ns, nbuf)[ni - 1]
            d = counts(r, m, pos, neg, wb[binidx(r["dist"])]); per.append(d); perlake[nm] = derive(d, scale)
            o = r["obs"][m]; perlake[nm].update(kind=o["kind"], persistence=o["persistence"], n_accepted=o["n_accepted"], presence=o["presence"][0], plant_cells=o["plant_cells"])
        tot = {k: sum(p[k] for p in per) for k in per[0]}; pooled = derive(tot, scale)
        for nmx, fnx in (("F1_raw", lambda t: derive(t, scale)["F1_raw"]), ("P_raw", lambda t: derive(t, scale)["P_raw"]), ("R_int", lambda t: derive(t, scale)["R_int"]), ("FPR_all", lambda t: derive(t, scale)["FPR_all"]), ("F1_matched50", lambda t: derive(t, scale)["F1_matched50"])):
            pooled["ci_" + nmx] = boot(per, fnx)
        pooled["lakes_with_ge30_pos"] = [nm for nm, d in zip(SN, per) if d["npos"] >= 30]; pooled["lakes_with_pos"] = [nm for nm, d in zip(SN, per) if d["npos"] > 0]
        pooled["pos_hist"] = ph.tolist(); pooled["neg_hist"] = nh.tolist()
        res["snoco"][f"{m}|{negname}"] = dict(pooled=pooled, per_lake=perlake)
# lake-level reachability and guards
for nm in SN + FW:
    tag = "snoco" if nm in SN else "fwc"; r = R[f"{tag}|{nm}"]; i = r["info"]
    res["lakes"][f"{tag}|{nm}"] = dict(n_inwindow=i["n_inwindow"], n_accepted=i["n_accepted"], bursts=i["bursts"], cov=i["cov"], gaps=i["gaps"], n_interior=i["n_interior"], n_eligible=i["n_eligible"],
        scene_unknown_cells=i["scene_unknown_cells"], scene_eligible_cells_total=i["scene_eligible_cells_total"], **{f"obs_{m}": dict(kind=r["obs"][m]["kind"], persistence=r["obs"][m]["persistence"], presence=r["obs"][m]["presence"], plant=r["obs"][m]["plant_cells"], coverage=r["obs"][m]["coverage"], shares=r["obs"][m]["shares"], notes=r["obs"][m]["notes"]) for m in "SAP"})
# FWC recall (points)
for m in ("S", "A", "P"):
    per = []; pl = {}
    for nm in FW:
        r = R[f"fwc|{nm}"]; L = r["lab"]; fl, kn = flags(r, m); it = r["interior"]; el = r["eligible"]
        surf = ((L["floating"] > 0) | (L["emergent"] > 0)) & el; sub = (L["submersed"] > 0) & ~surf & el
        d = dict(n_all=int(surf.sum()), tp_all=int((fl & surf).sum()), known_all=int((kn & surf).sum()), n_int=int((surf & it).sum()), tp_int=int((fl & surf & it).sum()), known_int=int((kn & surf & it).sum()),
                 n_sub=int((sub & it).sum()), tp_sub=int((fl & sub & it).sum()))
        per.append(d); pl[nm] = dict(**d, R_all=d["tp_all"] / d["n_all"] if d["n_all"] else float("nan"), R_int=d["tp_int"] / d["n_int"] if d["n_int"] else float("nan"), presence=r["obs"][m]["presence"][0], kind=r["obs"][m]["kind"])
    tot = {k: sum(p[k] for p in per) for k in per[0]}
    pooled = dict(tot, R_all=tot["tp_all"] / tot["n_all"], R_int=tot["tp_int"] / tot["n_int"], R_all_known=tot["tp_all"] / max(1, tot["known_all"]), R_int_known=tot["tp_int"] / max(1, tot["known_int"]))
    pooled["ci_R_all"] = boot(per, lambda t: t["tp_all"] / t["n_all"] if t["n_all"] else float("nan")); pooled["ci_R_int"] = boot(per, lambda t: t["tp_int"] / t["n_int"] if t["n_int"] else float("nan"))
    res["fwc"][m] = dict(pooled=pooled, per_lake=pl)
json.dump(res, open(OUT / f"metrics_snoco_fwc_{TAG}.json", "w"), indent=1, default=float)
f = lambda x: "nan" if x is None or x != x else f"{x:.3f}"
print(f"## TAG {TAG}  floor {res['floor']}")
print("Snohomish pooled (strict-none negatives):  obs | TP FP FN(int) | P_raw R_int F1_raw IoU | P_m50 P_mraw F1_mraw | FPR_all FPR_known | R_whole | F1_raw CI | posUNK")
for m in "SAP":
    p = res["snoco"][f"{m}|strict"]["pooled"]
    print(m, p["TP"], p["FP"], p["FN"], "|", f(p["P_raw"]), f(p["R_int"]), f(p["F1_raw"]), f(p["IoU_raw"]), "|", f(p["P_matched50"]), f(p["P_matched_rawprev"]), f(p["F1_matched_rawprev"]), "|", f(p["FPR_all"]), f(p["FPR_known"]), "|", f(p["R_whole"]), "|", p["ci_F1_raw"], "|", f(p["pos_unknown_share"]), "lakes>=30pos", p["lakes_with_ge30_pos"])
print("FWC pooled recall:")
for m in "SAP":
    p = res["fwc"][m]["pooled"]; print(m, "n_all", p["n_all"], "R_all", f(p["R_all"]), "R_int", f(p["R_int"]), "known-only R_all", f(p["R_all_known"]), "ci", p["ci_R_all"])
