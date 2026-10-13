#!/usr/bin/env python3
"""Depth Brain / contour truth, step 5: RE-VALIDATE GLOBathy and the cheap proxies against the contour-derived truth.

Truth  : data/contour_truth_lakes.csv (one best source per lake; fleet duplicates dropped). Primary set = tier A; sensitivity = tier A+B.
         Shares at GLOBathy's thresholds (1.2 / 1.8 / 3.0 m = 3.94 / 5.91 / 9.84 ft) are recomputed from the saved depth rasters (TWDB tables: S4 / S6 / S10).
Tests  : (a) GLOBathy Dmax and A(h) shallow shares; (b) HydroLAKES / NID storage-area mean depth; (c) polygon proxies, 3DEP shoreline-slope proxies (subset),
         combined models with leave-one-STATE-out (LOSO); broad-shallow class = top third of the share < 6 ft.
Statistics: lake-level bootstrap (2000) 95 % CIs; constant baseline = leave-one-state-out mean/median of the truth; no lake is dropped except where a predictor is undefined (n shown).
Output data/contour_revalidation.json (+ data/contour_revalidation_lakes.csv)."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy import stats

REPO = Path(__file__).resolve().parents[2]
D = REPO / "docs/research/depth-brain/data"
RAW = Path("/Users/mcather/Desktop/Development/Sector_Research_Data")
GR = RAW / "depth-brain/contour/grids"
FT = 3.28084
RNG = np.random.default_rng(7)
TH_FT = (1.2 * FT, 1.8 * FT, 3.0 * FT)


def safe(s): return "".join(ch if ch.isalnum() else "_" for ch in s)


def grid_shares(lid, src):
    f = GR / f"{safe(lid)}__{src}.npz"
    if not f.exists(): return [np.nan] * 3
    d = np.load(f)["depth_ft"].astype(np.float32); v = d[np.isfinite(d)]
    return [float((v < t).mean()) for t in TH_FT]


def auc(score, pos):
    pos = np.asarray(pos, bool); s = np.asarray(score, float); ok = np.isfinite(s)
    s, pos = s[ok], pos[ok]
    if pos.sum() < 2 or (~pos).sum() < 2: return np.nan
    r = stats.rankdata(s); return float((r[pos].sum() - pos.sum() * (pos.sum() + 1) / 2) / (pos.sum() * (~pos).sum()))


def boot(fn, n, B=2000, **arrs):
    """bootstrap CI of fn(**resampled arrays)"""
    out = []
    for _ in range(B):
        i = RNG.integers(0, n, n)
        try: v = fn(**{k: a[i] for k, a in arrs.items()})
        except Exception: v = np.nan
        out.append(v)
    out = np.array(out, float); out = out[np.isfinite(out)]
    return [float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))] if len(out) > 50 else [np.nan, np.nan]


def sp(x, y):
    if len(x) < 4 or np.std(x) == 0 or np.std(y) == 0: return np.nan
    return float(stats.spearmanr(x, y)[0])


def share_metrics(pred, truth, base):
    """pred, truth, base: arrays (same lakes). MAE/bias/RMSE/Spearman + skill vs constant baseline"""
    e = pred - truth; eb = base - truth
    r = dict(n=int(len(truth)), mae=float(np.abs(e).mean()), bias=float(e.mean()), rmse=float(np.sqrt((e ** 2).mean())), spearman=sp(pred, truth),
             mae_const=float(np.abs(eb).mean()), skill_vs_const=float(1 - np.abs(e).mean() / np.abs(eb).mean()))
    r["mae_ci"] = boot(lambda p, t: np.abs(p - t).mean(), len(truth), p=pred, t=truth)
    r["spearman_ci"] = boot(lambda p, t: sp(p, t), len(truth), p=pred, t=truth)
    r["skill_ci"] = boot(lambda p, t, b: 1 - np.abs(p - t).mean() / np.abs(b - t).mean(), len(truth), p=pred, t=truth, b=base)
    return r


def terciles(x):
    q = np.quantile(x, [1 / 3, 2 / 3]); return np.digitize(x, q)


def loso_baseline(y, groups, fn=np.mean):
    out = np.empty(len(y))
    for g in np.unique(groups):
        m = groups == g
        out[m] = fn(y[~m]) if (~m).sum() else fn(y)
    return out


def ridge_fit(X, y, lam=1.0):
    mu, sd = X.mean(0), X.std(0) + 1e-9; Z = (X - mu) / sd
    A = Z.T @ Z + lam * np.eye(Z.shape[1]); w = np.linalg.solve(A, Z.T @ (y - y.mean()))
    return lambda Q: y.mean() + ((Q - mu) / sd) @ w


def loso_model(X, y, groups, lam=3.0):
    pred = np.empty(len(y))
    for g in np.unique(groups):
        m = groups == g
        if (~m).sum() < 8: pred[m] = y[~m].mean() if (~m).any() else y.mean(); continue
        f = ridge_fit(X[~m], y[~m], lam); pred[m] = f(X[m])
    return np.clip(pred, 0, 1)


def classacc(pred, truth_cls):
    return float((terciles(pred) == truth_cls).mean())


def main():
    t = pd.read_csv(D / "contour_truth_lakes.csv")
    t = t[t.is_duplicate == 0].copy()
    sh = [grid_shares(r.lakeId, r.src) if r.method == "contour_interp" else [r.S4 if hasattr(r, "S4") else np.nan, np.nan, np.nan] for r in t.itertuples()]
    t["t_lt1p2m"], t["t_lt1p8m"], t["t_lt3p0m"] = np.array(sh).T
    tw = pd.read_csv(D / "contour_twdb_truth.csv").set_index("lakeId")
    for lid in tw.index:
        if lid in set(t.lakeId):
            i = t.index[t.lakeId == lid][0]
            t.loc[i, ["t_lt1p2m", "t_lt1p8m", "t_lt3p0m"]] = [tw.loc[lid, "S4"], tw.loc[lid, "shr_0_3"] + tw.loc[lid, "shr_3_6"], 1 - tw.loc[lid, "shr_gt10"]]
    g = pd.read_csv(D / "globathy_fleet_match.csv")
    gcols = ["id", "glob_dmax_source", "match_tier", "glob_dmax_m", "glob_mean_depth_m", "glob_shallow_frac_1p2m", "glob_shallow_frac_1p8m", "glob_shallow_frac_3p0m", "hl_id", "hl_over_poly", "storage_src"]
    t = t.merge(g[gcols].rename(columns={"id": "lakeId"}), on="lakeId", how="left", suffixes=("", "_g"))
    rs = pd.read_csv(D / "globathy_raster_stats.csv")[["hl_id", "rast_frac_lt_1p2m", "rast_frac_lt_1p8m", "rast_frac_lt_3m"]]
    t = t.merge(rs, on="hl_id", how="left")
    f = pd.read_csv("/Users/mcather/Desktop/Development/Sector_Engine/docs/research/lake-brain/data/lake_features.csv")[["id", "mean_depth_m", "storage_mcm", "nid_height_ft", "dendritic", "perim_km", "n_islands", "size", "depth_class"]].rename(columns={"id": "lakeId"})
    t = t.merge(f, on="lakeId", how="left", suffixes=("", "_f"))
    gt = pd.read_csv(D / "globathy_truth_comparison.csv")[["id", "max_depth_m", "mean_depth_m"]].rename(columns={"id": "lakeId", "max_depth_m": "sup_max_m", "mean_depth_m": "sup_mean_m"})
    t = t.merge(gt, on="lakeId", how="left")
    t["state"] = t.state1
    t["log_area"] = np.log10(t.area_km2.clip(lower=1e-3))
    out = {"meta": dict(n_truth_rows=int(len(t)), tiers=t.tier.value_counts().to_dict(),
                        note="thresholds: GLOBathy 1.2/1.8/3.0 m = 3.94/5.91/9.84 ft; truth recomputed from rasters (TWDB: S4/S6/S10 tables)")}
    sets = {"A": t[t.tier == "A"], "AB": t[t.tier.isin(["A", "B"])]}

    # ---------- (a1) GLOBathy Dmax vs contour max depth -------------------------------------------------
    def dmax_block(df, label):
        d = df[(df.glob_dmax_source == "modeled_estimate") & df.glob_dmax_m.notna()].copy()
        res = {}
        for name, cond in (("believable_vs_nonNLA_reference", (d.max_depth_check == "consistent") & d.ref_max_ft.notna() & d.max_ratio_ref.between(0.75, 1.33) & (d.method == "contour_interp") & (d.anchor_src != "EPA_NLA2007_DEPTHMAX")),
                           ("believable_plus_TWDB", ((d.max_depth_check == "consistent") & d.ref_max_ft.notna() & d.max_ratio_ref.between(0.75, 1.33) & (d.anchor_src != "EPA_NLA2007_DEPTHMAX")) | (d.method == "area_capacity_table")),
                           ("contour_top_ge15ft_unconfirmed", (d.valid_gt10 == 1) & (d.max_contour_ft >= 15))):
            for mt in ("verified", "verified+weak"):
                dd = d[cond & (d.match_tier.isin(["verified"]) if mt == "verified" else d.match_tier.isin(["verified", "weak"]))]
                if len(dd) < 5: res[f"{name}|{mt}"] = dict(n=int(len(dd))); continue
                truth = dd.max_contour_ft.values / FT; pred = dd.glob_dmax_m.values
                base = loso_baseline(truth, dd.state.values, np.median)
                ratio = pred / truth
                res[f"{name}|{mt}"] = dict(n=int(len(dd)), median_ratio=float(np.median(ratio)), ratio_iqr=[float(np.percentile(ratio, 25)), float(np.percentile(ratio, 75))],
                                           within_1p25=float(((ratio > 0.8) & (ratio < 1.25)).mean()), within_1p5=float(((ratio > 1 / 1.5) & (ratio < 1.5)).mean()), within_2=float(((ratio > .5) & (ratio < 2)).mean()),
                                           const_within_2=float((((base / truth) > .5) & ((base / truth) < 2)).mean()), const_within_1p5=float((((base / truth) > 1 / 1.5) & ((base / truth) < 1.5)).mean()),
                                           mae_m=float(np.abs(pred - truth).mean()), mae_const_m=float(np.abs(base - truth).mean()), spearman=sp(pred, truth),
                                           spearman_ci=boot(lambda p, t_: sp(p, t_), len(truth), p=pred, t_=truth), median_truth_m=float(np.median(truth)), pred_range_m=[float(pred.min()), float(pred.max())],
                                           log10_ratio_sd=float(np.log10(ratio).std()), over_3x=int((ratio > 3).sum()), under_third=int((ratio < 1 / 3).sum()))
        return res
    out["a1_globathy_dmax_vs_contour_max"] = {k: dmax_block(v, k) for k, v in sets.items()}
    # supplied-observed lakes are a pass-through check only
    d = t[(t.glob_dmax_source == "supplied_observed") & (t.valid_gt10 == 1) & (t.max_depth_check == "consistent")]
    out["a1_supplied_observed_passthrough"] = dict(n=int(len(d)), median_ratio=float(np.median(d.glob_dmax_m / (d.max_contour_ft / FT))) if len(d) else None)

    # ---------- (a2) GLOBathy A(h) shallow shares vs truth ------------------------------------------------
    def shares_block(df):
        res = {}
        for tier_label, dd0 in (("tier", df),):
            for mt in ("verified", "verified+weak", "all_matched"):
                sel = {"verified": df.match_tier.isin(["verified"]), "verified+weak": df.match_tier.isin(["verified", "weak"]), "all_matched": df.match_tier.isin(["verified", "weak", "suspect"])}[mt]
                for tag, tcol, pcol, rcol in (("lt1.2m(3.9ft)", "t_lt1p2m", "glob_shallow_frac_1p2m", "rast_frac_lt_1p2m"), ("lt1.8m(5.9ft)", "t_lt1p8m", "glob_shallow_frac_1p8m", "rast_frac_lt_1p8m"),
                                              ("lt3.0m(9.8ft)", "t_lt3p0m", "glob_shallow_frac_3p0m", "rast_frac_lt_3m")):
                    dd = df[sel & df[tcol].notna() & df[pcol].notna() & (df.glob_dmax_source == "modeled_estimate")]
                    if len(dd) < 6: res[f"{tag}|{mt}"] = dict(n=int(len(dd))); continue
                    truth, pred = dd[tcol].values, dd[pcol].values
                    base = loso_baseline(truth, dd.state.values, np.mean)
                    r = share_metrics(pred, truth, base)
                    cls = terciles(truth)
                    r["tercile_acc"] = classacc(pred, cls); r["tercile_acc_const"] = float(np.mean(np.bincount(cls) / len(cls)).round(3)) if False else float(np.bincount(cls).max() / len(cls))
                    top = truth >= np.quantile(truth, 2 / 3)
                    r["auc_top_third_shallow"] = auc(pred, top); r["auc_ci"] = boot(lambda p, tp: auc(p, tp), len(truth), p=pred, tp=top)
                    r["truth_mean"] = float(truth.mean()); r["pred_mean"] = float(pred.mean())
                    res[f"{tag}|{mt}"] = r
        return res
    out["a2_globathy_shallow_shares"] = {k: shares_block(v) for k, v in sets.items()}

    # ---------- (b) mean depth ------------------------------------------------------------------------------
    def md_block(df):
        res = {}
        ok = df[(df.method == "contour_interp") & (df.max_depth_check == "consistent") & df.ref_max_ft.notna() & df.max_ratio_ref.between(0.85, 1.2) & df.mean_depth_ft.notna() & (df.anchor_src != "EPA_NLA2007_DEPTHMAX")]
        for label, col in (("lake_features.mean_depth_m (HydroLAKES/NID storage/area)", "mean_depth_m"), ("GLOBathy mean depth", "glob_mean_depth_m")):
            dd = ok[ok[col].notna()]
            if len(dd) < 5: res[label] = dict(n=int(len(dd))); continue
            truth = dd.mean_depth_ft.values / FT; pred = dd[col].values; base = loso_baseline(truth, dd.state.values, np.median); ratio = pred / truth
            res[label] = dict(n=int(len(dd)), median_ratio=float(np.median(ratio)), within_1p5=float(((ratio > 1 / 1.5) & (ratio < 1.5)).mean()), const_within_1p5=float((((base / truth) > 1 / 1.5) & ((base / truth) < 1.5)).mean()),
                              mae_m=float(np.abs(pred - truth).mean()), mae_const_m=float(np.abs(base - truth).mean()), spearman=sp(pred, truth), spearman_ci=boot(lambda p, t_: sp(p, t_), len(truth), p=pred, t_=truth),
                              note="contour mean depth is a lower bound (deepest face set to top ring + half interval); only lakes whose contour max is 0.85-1.2 of an agency/supplied max")
        # larger-n check against SUPPLIED observed mean depth (non-contour truth from the GLOBathy thread)
        dd = df[df.sup_mean_m.notna() & df.mean_depth_m.notna()]
        if len(dd) >= 5:
            truth, pred = dd.sup_mean_m.values, dd.mean_depth_m.values; base = loso_baseline(truth, dd.state.values, np.median); ratio = pred / truth
            res["lake_features.mean_depth_m vs supplied observed mean depth"] = dict(n=int(len(dd)), median_ratio=float(np.median(ratio)), within_1p5=float(((ratio > 1 / 1.5) & (ratio < 1.5)).mean()),
                                                                                    const_within_1p5=float((((base / truth) > 1 / 1.5) & ((base / truth) < 1.5)).mean()), spearman=sp(pred, truth), spearman_ci=boot(lambda p, t_: sp(p, t_), len(truth), p=pred, t_=truth))
        # as a shallow-lake detector
        dd = df[df.mean_depth_m.notna()]
        truth = dd.shr_lt6.values; top = truth >= np.quantile(truth, 2 / 3)
        res["mean_depth_m -> broad-shallow (top third of share<6ft)"] = dict(n=int(len(dd)), auc=auc(-dd.mean_depth_m.values, top), auc_ci=boot(lambda p, tp: auc(p, tp), len(dd), p=-dd.mean_depth_m.values, tp=top),
                                                                                spearman_vs_shr_lt6=sp(-dd.mean_depth_m.values, truth))
        return res
    out["b_mean_depth"] = {k: md_block(v) for k, v in sets.items()}

    # ---------- (c) proxies for broad-shallow lakes ------------------------------------------------------------
    def proxy_block(df, label):
        res = {}
        base_df = df[df.shr_lt6.notna()].copy()
        base_df["oracle_max"] = np.where(base_df.valid_gt10 == 1, base_df.max_contour_ft, np.nan)
        base_df["oracle_mean"] = np.where((base_df.valid_gt10 == 1) & (base_df.max_depth_check != "contours_end_above_reference_max") & (base_df.method == "contour_interp"), base_df.mean_depth_ft, np.nan)
        y = base_df.shr_lt6.values; top = y >= np.quantile(y, 2 / 3); cls = terciles(y)
        res["n"] = int(len(base_df)); res["truth_shr_lt6"] = dict(mean=float(y.mean()), sd=float(y.std()), q=np.quantile(y, [.1, .33, .5, .67, .9]).round(3).tolist(), top_third_cut=float(np.quantile(y, 2 / 3)))
        single = {"frac_within_100m (+)": "frac_within_100m", "frac_narrow_300m (+)": "frac_narrow_300m", "sdi_ext (+)": "sdi_ext", "solidity (-)": "solidity", "log10 area (-)": "log_area",
                  "GLOBathy shallow frac <1.8 m (+)": "glob_shallow_frac_1p8m", "GLOBathy Dmax (-)": "glob_dmax_m", "HL/NID mean depth (-)": "mean_depth_m", "nid_height_ft (-)": "nid_height_ft",
                  "ORACLE contour max depth (-) [ceiling for any Dmax model]": "oracle_max", "ORACLE contour mean depth (-) [ceiling for any mean-depth model]": "oracle_mean"}
        sign = {"frac_within_100m (+)": 1, "frac_narrow_300m (+)": 1, "sdi_ext (+)": 1, "solidity (-)": -1, "log10 area (-)": -1, "GLOBathy shallow frac <1.8 m (+)": 1, "GLOBathy Dmax (-)": -1, "HL/NID mean depth (-)": -1, "nid_height_ft (-)": -1,
                "ORACLE contour max depth (-) [ceiling for any Dmax model]": -1, "ORACLE contour mean depth (-) [ceiling for any mean-depth model]": -1}
        rows = {}
        for nm, col in single.items():
            dd = base_df[base_df[col].notna()]
            if col.startswith("glob_"): dd = dd[(dd.glob_dmax_source == "modeled_estimate") & dd.match_tier.isin(["verified", "weak"])]
            if len(dd) < 8: rows[nm] = dict(n=int(len(dd))); continue
            s = sign[nm] * dd[col].values; yy = dd.shr_lt6.values; tp = yy >= np.quantile(yy, 2 / 3)
            rows[nm] = dict(n=int(len(dd)), spearman=sp(s, yy), spearman_ci=boot(lambda a, b: sp(a, b), len(dd), a=s, b=yy), auc_top_third=auc(s, tp), auc_ci=boot(lambda a, b: auc(a, b), len(dd), a=s, b=tp))
        res["single_predictors_vs_shr_lt6"] = rows
        rob = {}
        for tgt in ("shr_0_3", "shr_gt10", "flat200_share_of_surveyed", "shore_to_6ft_med_m", "flat100_share_of_surveyed"):
            rr = {}
            for nm, col in list(single.items())[:8]:
                dd = base_df[base_df[col].notna() & base_df[tgt].notna()]
                if col.startswith("glob_"): dd = dd[(dd.glob_dmax_source == "modeled_estimate") & dd.match_tier.isin(["verified", "weak"])]
                if len(dd) < 8: continue
                sgn = 1 if tgt in ("shr_0_3", "flat200_share_of_surveyed", "flat100_share_of_surveyed", "shore_to_6ft_med_m") else -1       # larger predictor score should mean "more shallow"
                rr[nm] = dict(n=int(len(dd)), spearman=sp(sign[nm] * dd[col].values * sgn, dd[tgt].values), spearman_ci=boot(lambda a, b: sp(a, b), len(dd), a=sign[nm] * dd[col].values * sgn, b=dd[tgt].values))
            rob[tgt] = rr
        res["robustness_other_targets_spearman(score = 'more shallow'; shr_gt10 inverted)"] = rob
        # reduced-n comparison on the common set, LOSO ridge models
        feats = {"poly": ["frac_within_100m", "frac_narrow_300m", "log_area", "sdi_ext", "solidity"], "glob": ["glob_shallow_frac_1p8m", "glob_dmax_m"], "meandepth": ["mean_depth_m"],
                 "poly+meandepth": ["frac_within_100m", "frac_narrow_300m", "log_area", "sdi_ext", "solidity", "mean_depth_m"], "all": ["frac_within_100m", "frac_narrow_300m", "log_area", "sdi_ext", "solidity", "mean_depth_m", "glob_shallow_frac_1p8m", "glob_dmax_m"]}
        cs = base_df.dropna(subset=feats["all"]).copy()
        cs = cs[(cs.glob_dmax_source == "modeled_estimate") & cs.match_tier.isin(["verified", "weak"])]
        yc = cs.shr_lt6.values; st = cs.state.values; topc = yc >= np.quantile(yc, 2 / 3); clsc = terciles(yc)
        mod = {}
        basec = loso_baseline(yc, st, np.mean)
        mod["constant (LOSO mean)"] = dict(n=int(len(cs)), mae=float(np.abs(basec - yc).mean()), spearman=np.nan, auc_top_third=0.5, tercile_acc=float(np.bincount(clsc).max() / len(clsc)))
        # class-mean by lake_class
        cm = np.empty(len(cs))
        for g_ in np.unique(st):
            m = st == g_
            tr = cs[~m]; cmean = tr.groupby("lake_class").shr_lt6.mean(); gm = tr.shr_lt6.mean()
            cm[m] = cs[m].lake_class.map(cmean).fillna(gm).values
        mod["lake_class mean (LOSO)"] = dict(n=int(len(cs)), mae=float(np.abs(cm - yc).mean()), spearman=sp(cm, yc), auc_top_third=auc(cm, topc), tercile_acc=classacc(cm, clsc))
        for nm, cols in feats.items():
            p = loso_model(cs[cols].values.astype(float), yc, st)
            mod[f"ridge[{nm}] LOSO"] = dict(n=int(len(cs)), mae=float(np.abs(p - yc).mean()), mae_ci=boot(lambda a, b: np.abs(a - b).mean(), len(cs), a=p, b=yc), skill_vs_const=float(1 - np.abs(p - yc).mean() / np.abs(basec - yc).mean()),
                                            skill_ci=boot(lambda a, b, c_: 1 - np.abs(a - b).mean() / np.abs(c_ - b).mean(), len(cs), a=p, b=yc, c_=basec), spearman=sp(p, yc), spearman_ci=boot(lambda a, b: sp(a, b), len(cs), a=p, b=yc),
                                            auc_top_third=auc(p, topc), auc_ci=boot(lambda a, b: auc(a, b), len(cs), a=p, b=topc), tercile_acc=classacc(p, clsc))
        res["common_set_models_loso"] = mod
        res["common_set_n_states"] = int(len(np.unique(st)))
        # raw GLOBathy share used directly (no calibration) on the same set
        gp = cs.glob_shallow_frac_1p8m.values
        res["globathy_shallow_frac_1p8m_direct_on_common_set"] = dict(mae=float(np.abs(gp - cs.t_lt1p8m.values).mean()), bias=float((gp - cs.t_lt1p8m.values).mean()), spearman=sp(gp, yc), auc_top_third=auc(gp, topc))
        # states count info
        res["state_counts"] = base_df.state.value_counts().to_dict()
        return res
    out["c_proxies"] = {k: proxy_block(v, k) for k, v in sets.items()}

    # ---------- (c2) 3DEP shoreline-slope proxies on the overlap with the terrain thread's table -------------------
    sp3 = pd.read_csv(D / "shallow_proxy_lake_table.csv")
    mn_map = {"MN_Gull": "Gull Lake|MN", "MN_Bemidji": "Lake Bemidji|MN", "MN_Minnetonka": "Lake Minnetonka|MN", "MN_Winnibigoshish": "Lake Winnibigoshish|MN", "MN_Leech": "Leech Lake|MN",
              "MN_Mille_Lacs": "Mille Lacs Lake|MN", "MN_Otter_Tail": "Otter Tail Lake|MN", "MN_White_Bear": "White Bear Lake|MN", "MN_Pepin": "Lake Pepin|MN"}
    twk = pd.read_csv(D / "contour_twdb_truth.csv").set_index("twdbKey").lakeId.to_dict()
    def lid_of(r):
        if r.set == "MN": return mn_map.get(r.lake)
        if r.set == "TWDB": return twk.get(r.lake)
        return r.lake
    sp3["lakeId"] = [lid_of(r) for r in sp3.itertuples()]
    sp3 = sp3[sp3.lakeId.notna()].drop_duplicates("lakeId")
    slope_cols = ["slope_10_60_med", "slope_30_100_med", "slope_60_200_med", "rise_100_med_m", "rise_200_med_m", "frac_lt2", "frac_rise200_lt2m", "run_per_ft_med", "run_per_ft_200"]
    m3 = t[t.tier.isin(["A", "B"])].merge(sp3[["lakeId"] + slope_cols + ["set"]], on="lakeId", how="inner")
    r3 = dict(n_overlap=int(len(m3)), sets=m3.set.value_counts().to_dict(), lakes=m3.lakeId.tolist(), rows={})
    if len(m3) >= 8:
        yy = m3.shr_lt6.values; tp = yy >= np.quantile(yy, 2 / 3)
        for c, sgn in (("slope_10_60_med", -1), ("slope_30_100_med", -1), ("slope_60_200_med", -1), ("rise_100_med_m", -1), ("rise_200_med_m", -1), ("frac_lt2", 1), ("frac_rise200_lt2m", 1), ("run_per_ft_med", 1), ("run_per_ft_200", 1)):
            s = sgn * m3[c].values.astype(float); r3["rows"][c] = dict(spearman=sp(s, yy), spearman_ci=boot(lambda a, b: sp(a, b), len(m3), a=s, b=yy), auc_top_third=auc(s, tp), auc_ci=boot(lambda a, b: auc(a, b), len(m3), a=s, b=tp))
        for c, sgn in (("frac_within_100m", 1), ("frac_narrow_300m", 1), ("log_area", -1), ("mean_depth_m", -1), ("glob_shallow_frac_1p8m", 1)):
            d_ = m3[m3[c].notna()]; s = sgn * d_[c].values.astype(float); y_ = d_.shr_lt6.values; tp_ = y_ >= np.quantile(y_, 2 / 3)
            r3["rows"][c + " (same overlap)"] = dict(n=int(len(d_)), spearman=sp(s, y_), spearman_ci=boot(lambda a, b: sp(a, b), len(d_), a=s, b=y_), auc_top_third=auc(s, tp_))
    out["c2_3dep_slope_proxies_overlap"] = r3

    # ---------- (e) cross-check of this thread's contour method against the terrain thread's independent MN extraction (read-only)
    mnt = json.load(open(D / "mn_dnr_truth.json"))
    rows = []
    for k, lid in mn_map.items():
        nm = k[3:].replace("_", " ")
        key = nm if nm in mnt else k[3:]
        if key not in mnt: continue
        r_ = t[(t.lakeId == lid)]
        if not len(r_): continue
        r_ = r_.iloc[0]
        rows.append(dict(lakeId=lid, mine_lt3=r_.shr_0_3, terrain_S3=mnt[key]["S3"], mine_lt6=r_.shr_lt6, terrain_S6=mnt[key]["S6"], mine_cov_hull=r_.cov_hull, mine_poly_km2=r_.poly_area_km2, terrain_area_km2=mnt[key]["area_ac"] * 0.00404686))
    X = pd.DataFrame(rows)
    if len(X):
        out["e_crosscheck_vs_terrain_mn"] = dict(n=int(len(X)), mae_lt3=float((X.mine_lt3 - X.terrain_S3).abs().mean()), mae_lt6=float((X.mine_lt6 - X.terrain_S6).abs().mean()), bias_lt6=float((X.mine_lt6 - X.terrain_S6).mean()),
                                                 spearman_lt6=sp(X.mine_lt6.values, X.terrain_S6.values), max_abs_lt6=float((X.mine_lt6 - X.terrain_S6).abs().max()), rows=X.round(4).to_dict("records"))
    # ---------- failure cases: biggest GLOBathy / proxy errors ---------------------------------------------------
    d = sets["AB"]
    d = d[(d.glob_dmax_source == "modeled_estimate") & d.glob_shallow_frac_1p8m.notna() & d.t_lt1p8m.notna() & d.match_tier.isin(["verified"])].copy()
    d["err"] = d.glob_shallow_frac_1p8m - d.t_lt1p8m
    out["failure_cases_globathy_share_lt1p8m_verified"] = d.reindex(d.err.abs().sort_values(ascending=False).index).head(10)[["lakeId", "src", "tier", "t_lt1p8m", "glob_shallow_frac_1p8m", "err", "max_contour_ft", "glob_dmax_m"]].round(3).to_dict("records")
    t.to_csv(D / "contour_revalidation_lakes.csv", index=False, float_format="%.4f")
    json.dump(out, open(D / "contour_revalidation.json", "w"), indent=1, default=lambda o: None if (isinstance(o, float) and not np.isfinite(o)) else (float(o) if isinstance(o, (np.floating, np.integer)) else str(o)))
    print(json.dumps(out, indent=1, default=float)[:12000])


if __name__ == "__main__":
    main()
