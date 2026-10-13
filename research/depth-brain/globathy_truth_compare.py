#!/usr/bin/env python3
"""Compare GLOBathy (matched via HydroLAKES) with independent agency truth. Outputs globathy_truth_comparison.csv + globathy_eval_summary.json
Truth files: Sector_Research_Data/depth-brain/globathy/truth/truth_*.json (collected from agency sources; see ledger)."""
import glob, json, os, numpy as np, pandas as pd
from scipy.stats import spearmanr, kendalltau
D = "/Users/mcather/Desktop/Development/"
DATA = D + "Sector_Research_Data/depth-brain/globathy/"
OUT = D + "Sector_Engine-depth-research/docs/research/depth-brain/data/"
rng = np.random.default_rng(7)
FT = 0.3048
m = pd.read_csv(OUT + "globathy_fleet_match.csv").set_index("id")
rs = pd.read_csv(OUT + "globathy_raster_stats.csv").set_index("hl_id")
T = []
for f in sorted(glob.glob(DATA + "truth/truth_*.json")):
    for r in json.load(open(f)):
        r["file"] = os.path.basename(f); T.append(r)
t = pd.DataFrame(T)
ovr = json.load(open(DATA + "truth_overrides.json")) if os.path.exists(DATA + "truth_overrides.json") else {}
t["truth_type_list"] = t.truth_type.apply(lambda x: x if isinstance(x, list) else [x])
def labels(r):
    L = set(str(x).strip() for x in r["truth_type_list"] for x in str(x).split("/") if x and str(x) != "nan")
    if pd.notna(r.get("max_depth_m")) and r["max_depth_m"] <= 8: L.add("shallow_lake")
    return sorted(L)
def rank_type(r):
    tl = [str(x) for x in r["truth_type_list"]]
    return tl[0] if tl else "unknown"
t["ttype"] = t.apply(rank_type, axis=1); t["labels"] = t.apply(labels, axis=1)
t["chain_group"] = t.get("chain_group")
t = t.drop_duplicates("id", keep="first").set_index("id")
for k, v in ovr.items():
    if k in t.index:
        for a, b in v.items(): t.loc[k, a] = b
j = t.join(m, how="left", rsuffix="_fleet")
j["has_truth_max"] = j.max_depth_m.notna()
j["glob_max"] = j.glob_dmax_m
j["rast_mean"] = j.hl_id.map(rs.rast_mean_m)
# shallow-fraction truth from hypsometry csv (share of pool-surface area shallower than d below normal pool)
def hypso_fracs(path, pool=None):
    if not isinstance(path, str) or not os.path.exists(path): return {}
    h = pd.read_csv(path).sort_values("elev_ft")
    if "elev_ft" not in h: return {}
    if len(h) < 8 or np.median(np.diff(h.elev_ft)) > 2.5: return {}   # published pertinent-data points / coarse tables are not a hypsometric curve
    p = h.elev_ft.max() if pool is None or pd.isna(pool) else pool
    A0 = np.interp(p, h.elev_ft, h.area_acres)
    out = {}
    for ft in (3, 6, 10):
        out[f"truth_frac_lt_{ft}ft"] = (A0 - np.interp(p - ft, h.elev_ft, h.area_acres, left=0)) / A0 if p - ft >= h.elev_ft.min() else np.nan
    return out
rows = []
for k, r in j.iterrows():
    pool = r.get("normal_pool_elev_ft", np.nan)
    if pd.isna(pool): pool = r.get("full_pool_elev_ft", np.nan)
    hf = hypso_fracs(r.get("hypso_csv"), pool)
    rows.append(hf)
H = pd.DataFrame(rows, index=j.index)
j = j.join(H)
for ft in (3, 6, 10):
    d = ft * FT
    j[f"glob_frac_lt_{ft}ft"] = 1 - np.clip(1 - d / j.glob_dmax_m, 0, 1) ** j.glob_b
    j[f"rast_frac_lt_{ft}ft"] = np.nan
# raster fracs at 3/6/10 ft need raw rasters; compute here
import rasterio
for k, r in j.iterrows():
    if pd.isna(r.hl_id): continue
    p = f"{DATA}rasters/{int(r.hl_id)}.tif"
    if not os.path.exists(p): continue
    s = rasterio.open(p); a = s.read(1).astype("float64"); ok = (a > 0) & (a != s.nodata)
    lat = s.bounds.top - (np.arange(a.shape[0]) + .5) * abs(s.res[1]); w = (np.cos(np.radians(lat))[:, None] * np.ones((1, a.shape[1])))[ok]; d_ = a[ok]
    for ft in (3, 6, 10): j.loc[k, f"rast_frac_lt_{ft}ft"] = w[d_ < ft * FT].sum() / w.sum()
j.to_csv("/tmp/_j.csv")
# ---------- metrics
def metrics(x, y):
    """x = truth, y = glob (m)"""
    x = np.asarray(x, float); y = np.asarray(y, float); n = len(x)
    if n < 3: return dict(n=n)
    lr = np.log(y / x)
    o = dict(n=n, bias_m=float(np.mean(y - x)), mae_m=float(np.mean(abs(y - x))), rmse_m=float(np.sqrt(np.mean((y - x) ** 2))),
             median_ratio=float(np.exp(np.median(lr))), geo_mean_ratio=float(np.exp(lr.mean())), log10_rmse=float(np.sqrt(np.mean((lr / np.log(10)) ** 2))),
             within_1p25=float(np.mean(abs(lr) <= np.log(1.25))), within_1p5=float(np.mean(abs(lr) <= np.log(1.5))), within_2=float(np.mean(abs(lr) <= np.log(2))),
             spearman=float(spearmanr(x, y)[0]), kendall=float(kendalltau(x, y)[0]), pearson_log=float(np.corrcoef(np.log(x), np.log(y))[0, 1]),
             pct_over=float(np.mean(y > x)))
    bs = []
    for _ in range(2000):
        i = rng.integers(0, n, n)
        if len(set(x[i])) > 2: bs.append(spearmanr(x[i], y[i])[0])
    o["spearman_ci95"] = [float(np.nanpercentile(bs, 2.5)), float(np.nanpercentile(bs, 97.5))]
    # baseline: constant guess = median truth
    o["baseline_const_mae_m"] = float(np.mean(abs(np.median(x) - x))); o["baseline_const_within_2"] = float(np.mean(abs(np.log(np.median(x) / x)) <= np.log(2)))
    return o
S = {}
ok = j[j.has_truth_max & j.glob_dmax_m.notna()].copy()
ok["conf_ok"] = ok.confidence.isin(["high", "medium"])
S["n_truth_rows"] = int(len(t)); S["n_truth_with_max_depth"] = int(t.max_depth_m.notna().sum()); S["n_with_glob_match"] = int(len(ok))
S["conf_counts"] = ok.confidence.value_counts().to_dict(); S["tier_counts"] = ok.match_tier.value_counts().to_dict()
S["glob_dmax_source_counts_among_truth"] = ok.glob_dmax_source.value_counts().to_dict()
S["dmax_SUPPLIED_observed_lakes_not_a_test"] = metrics(ok[(ok.glob_dmax_source=="supplied_observed")&ok.conf_ok].max_depth_m, ok[(ok.glob_dmax_source=="supplied_observed")&ok.conf_ok].glob_dmax_m)
S["dmax_estimated_incl_low_conf"] = metrics(ok[(ok.glob_dmax_source=="modeled_estimate")&ok.match_tier.isin(["verified","weak"])].max_depth_m, ok[(ok.glob_dmax_source=="modeled_estimate")&ok.match_tier.isin(["verified","weak"])].glob_dmax_m)
S["dmax_estimated_verified_match_only_hm"] = metrics(ok[(ok.glob_dmax_source=="modeled_estimate")&ok.conf_ok&(ok.match_tier=="verified")].max_depth_m, ok[(ok.glob_dmax_source=="modeled_estimate")&ok.conf_ok&(ok.match_tier=="verified")].glob_dmax_m)
prim = ok[ok.conf_ok & ok.match_tier.isin(["verified", "weak"]) & (ok.glob_dmax_source == "modeled_estimate")]
S["primary_n"] = int(len(prim))
S["dmax_primary_all"] = metrics(prim.max_depth_m, prim.glob_dmax_m)
S["dmax_primary_verified_only"] = metrics(prim[prim.match_tier == "verified"].max_depth_m, prim[prim.match_tier == "verified"].glob_dmax_m)
_e = ok[(ok.glob_dmax_source == "modeled_estimate") & ok.match_tier.isin(["verified", "weak"])]
S["dmax_estimated_high_conf_only"] = metrics(_e[_e.confidence == "high"].max_depth_m, _e[_e.confidence == "high"].glob_dmax_m)
S["dmax_estimated_all_conf_incl_suspect_match"] = metrics(ok[ok.glob_dmax_source == "modeled_estimate"].max_depth_m, ok[ok.glob_dmax_source == "modeled_estimate"].glob_dmax_m)
# by type
S["dmax_by_type"] = {}
for ty in ["natural", "storage_reservoir", "run_of_river", "complex_arm", "shallow_lake"]:
    g = prim[prim.labels.apply(lambda L: ty in L)]; S["dmax_by_type"][ty] = metrics(g.max_depth_m, g.glob_dmax_m)
# deep/shallow bins by truth
S["dmax_by_truth_bin"] = {}
for nm, lo, hi in [("lt8m", 0, 8), ("8to20m", 8, 20), ("20to40m", 20, 40), ("gt40m", 40, 1e9)]:
    g = prim[(prim.max_depth_m >= lo) & (prim.max_depth_m < hi)]; S["dmax_by_truth_bin"][nm] = metrics(g.max_depth_m, g.glob_dmax_m)
# tennessee chain dedup (collapse chain groups to one mean-log point)
P = prim.copy(); P["grp"] = P.chain_group.where(P.chain_group.notna() & (P.chain_group != "other"), P.index.to_series())
if "chain_group" in P:
    G = P.groupby("grp").apply(lambda g: pd.Series(dict(max_depth_m=np.exp(np.log(g.max_depth_m).mean()), glob_dmax_m=np.exp(np.log(g.glob_dmax_m).mean()), k=len(g))), include_groups=False)
    S["dmax_dedup_chain_groups"] = metrics(G.max_depth_m, G.glob_dmax_m); S["dedup_groups"] = int(len(G))
# ranking pairs: fraction of pairs ordered correctly (concordance) with truth difference > 1.5x
x = prim.max_depth_m.values; y = prim.glob_dmax_m.values; c = n_ = 0
for a in range(len(x)):
    for b in range(a + 1, len(x)):
        if max(x[a], x[b]) / min(x[a], x[b]) >= 1.5:
            n_ += 1; c += (x[a] - x[b]) * (y[a] - y[b]) > 0
S["pair_concordance_truth_ratio_ge_1p5"] = dict(pairs=n_, concordant=float(c / n_) if n_ else None)
# within-group ranking (same type)
# mean depth
mm = prim[prim.mean_depth_m.notna()]
S["meandepth_glob_VoverA"] = metrics(mm.mean_depth_m, mm.glob_mean_depth_m)
S["meandepth_glob_raster_mean"] = metrics(mm.mean_depth_m, mm.rast_mean)
# class accuracy: shallow (<=8 m max) vs mid vs deep (>=30 m)
def cls(v): return np.where(v < 8, "shallow<8", np.where(v < 25, "mid8-25", "deep>=25"))
if len(prim):
    ct = pd.crosstab(pd.Series(cls(prim.max_depth_m), index=prim.index, name="truth"), pd.Series(cls(prim.glob_dmax_m), index=prim.index, name="glob"))
    S["class3_accuracy"] = float((cls(prim.max_depth_m) == cls(prim.glob_dmax_m)).mean()); S["class3_confusion"] = ct.to_dict()
    S["class_shallow_lt8_recall"] = float(((cls(prim.max_depth_m) == "shallow<8") & (cls(prim.glob_dmax_m) == "shallow<8")).sum() / max(1, (cls(prim.max_depth_m) == "shallow<8").sum()))
    S["class_shallow_lt8_precision"] = float(((cls(prim.max_depth_m) == "shallow<8") & (cls(prim.glob_dmax_m) == "shallow<8")).sum() / max(1, (cls(prim.glob_dmax_m) == "shallow<8").sum()))
# shallow fraction vs hypsometry truth
S["shallow_fraction"] = {}
for ft in (3, 6, 10):
    g = j[j[f"truth_frac_lt_{ft}ft"].notna() & j.glob_dmax_m.notna()]
    if len(g) >= 4:
        tr = g[f"truth_frac_lt_{ft}ft"].values; gl = g[f"glob_frac_lt_{ft}ft"].values; ra = g[f"rast_frac_lt_{ft}ft"].values
        S["shallow_fraction"][f"lt_{ft}ft"] = dict(n=int(len(g)), truth_mean=float(tr.mean()), truth_range=[float(tr.min()), float(tr.max())], glob_mean=float(gl.mean()),
            bias=float((gl - tr).mean()), mae=float(abs(gl - tr).mean()), rmse=float(np.sqrt(((gl - tr) ** 2).mean())), spearman=float(spearmanr(tr, gl)[0]),
            spearman_raster=float(spearmanr(tr, ra, nan_policy="omit")[0]), mae_const_median=float(abs(np.median(tr) - tr).mean()), lakes=g.index.tolist(), truth=tr.round(4).tolist(), glob=gl.round(4).tolist())
from scipy.stats import mannwhitneyu
g = j[j["truth_frac_lt_6ft"].notna() & j.glob_dmax_m.notna()]
if len(g) >= 8:
    thr = g.truth_frac_lt_6ft.quantile(2 / 3); pos = g.truth_frac_lt_6ft >= thr
    def auc(sc): 
        a = sc[pos]; b = sc[~pos]; return float(mannwhitneyu(a, b).statistic / (len(a) * len(b)))
    S["broad_shallow_detection"] = dict(n=int(len(g)), threshold_truth_frac_lt_6ft=float(thr), n_pos=int(pos.sum()), auc_glob_frac_lt_6ft=auc(g.glob_frac_lt_6ft), auc_raster_frac=auc(g.rast_frac_lt_6ft),
        auc_neg_dmax=auc(-g.glob_dmax_m), auc_neg_mean_depth=auc(-g.glob_mean_depth_m))
# MN DNR / agency littoral share (nominally <15 ft) vs GLOBathy fraction <15 ft
lit = []
for k, r in j.iterrows():
    L = r.get("littoral_pct_or_shallow_pct")
    if isinstance(L, dict) and L.get("value") is not None and pd.notna(r.get("glob_dmax_m")) and r["confidence"] in ("high", "medium"):
        v = L["value"] / 100 if L["value"] > 1 else L["value"]
        lit.append(dict(id=k, truth=v, definition=L.get("definition"), glob15=1 - np.clip(1 - 15 * FT / r.glob_dmax_m, 0, 1) ** r.glob_b, src=r.glob_dmax_source, tier=r.match_tier))
lit = pd.DataFrame(lit)
if len(lit) >= 5:
    lit.round(4).to_csv(OUT + "globathy_littoral_check.csv", index=False)
    S["littoral_lt15ft"] = dict(n=int(len(lit)), spearman=float(spearmanr(lit.truth, lit.glob15)[0]), truth_mean=float(lit.truth.mean()), glob_mean=float(lit.glob15.mean()), mae=float(abs(lit.truth - lit.glob15).mean()), mae_const=float(abs(lit.truth - lit.truth.median()).mean()))
# CWMS rel_per_ft truth (area gained per ft near pool), n~33
hy = json.load(open(D + "Sector_Research_Data/lake-brain/context/hypso_truth.json"))
rows = []
for k, v in hy.items():
    f = v.get("fit") or {}
    if not f or f.get("r2", 0) < 0.9 or "rel_per_ft" not in f: continue
    lid = v["lake"]
    if lid in m.index and pd.notna(m.loc[lid, "glob_dmax_m"]):
        r = m.loc[lid]; rows.append(dict(id=lid, truth=f["rel_per_ft"], g1ft=1 - max(0, 1 - FT / r.glob_dmax_m) ** r.glob_b, tier=r.match_tier, dmax=r.glob_dmax_m))
cw = pd.DataFrame(rows).drop_duplicates("id")
if len(cw) > 3:
    cw.to_csv(OUT + "globathy_cwms_relperft.csv", index=False)
    S["cwms_rel_per_ft"] = dict(n=int(len(cw)), spearman=float(spearmanr(cw.truth, cw.g1ft)[0]), spearman_verified_weak=float(spearmanr(cw[cw.tier.isin(["verified","weak"])].truth, cw[cw.tier.isin(["verified","weak"])].g1ft)[0]),
        glob_mean_frac_1ft=float(cw.g1ft.mean()), truth_mean=float(cw.truth.mean()), within2=float(np.mean(abs(np.log(cw.g1ft / cw.truth)) <= np.log(2))))
# save comparison csv
cols = ["name", "glob_dmax_source", "ttype", "chain_group", "confidence", "match_tier", "match_flags", "hl_id", "hl_over_poly", "max_depth_m", "glob_dmax_m", "mean_depth_m", "glob_mean_depth_m", "rast_mean",
        "truth_frac_lt_3ft", "glob_frac_lt_3ft", "rast_frac_lt_3ft", "truth_frac_lt_6ft", "glob_frac_lt_6ft", "rast_frac_lt_6ft", "truth_frac_lt_10ft", "glob_frac_lt_10ft", "rast_frac_lt_10ft", "source_url", "depth_basis", "notes"]
c = j.copy(); c["name"] = c.get("name", pd.Series(index=c.index, dtype=object)); c["ratio_glob_over_truth"] = c.glob_dmax_m / c.max_depth_m
cols = [x for x in cols if x in c.columns] + ["ratio_glob_over_truth"]
c[cols].round(4).to_csv(OUT + "globathy_truth_comparison.csv")
json.dump(S, open(OUT + "globathy_eval_summary.json", "w"), indent=1, default=float)
print(json.dumps({k: v for k, v in S.items() if k in ("n_truth_rows", "n_truth_with_max_depth", "n_with_glob_match", "primary_n", "conf_counts", "tier_counts")}, indent=1))
print(json.dumps(S["dmax_primary_all"], indent=1))
