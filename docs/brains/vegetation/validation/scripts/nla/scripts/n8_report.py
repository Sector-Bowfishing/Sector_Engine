"""Assemble report tables (markdown) from out/*. Writes out/report_tables.md and the wide per-lake CSV."""
import json, glob, re, numpy as np, pandas as pd
from pathlib import Path
from scipy.stats import spearmanr
H = Path(__file__).resolve().parents[1]
cls = pd.read_csv(H/"out/nla_lake_classes.csv"); sc = pd.read_csv(H/"out/nla_lake_scores.csv"); M = json.load(open(H/"out/nla_metrics.json"))
O = []
def T(df, **k): O.append(df.to_markdown(**k) + "\n")
def H2(s): O.append(f"\n### {s}\n")
reg = json.load(open(H.parents[2]/"registry/lakes.v1.json"))["lakes"]
# --- eligible set
H2("A. Eligible set by EPA region")
e = cls.copy(); e["has_cover"] = e.n_stations > 0
g = e.groupby("epa_reg").agg(lakes_with_NLA_site=("lakeKey", "size"), lakes_with_cover_rows=("has_cover", "sum"),
    POS=("cls", lambda s: (s == "POS").sum()), NEG=("cls", lambda s: (s == "NEG").sum()), AMB=("cls", lambda s: (s == "AMB").sum())).reset_index()
tot = g.sum(numeric_only=True); tot["epa_reg"] = "TOTAL"; g = pd.concat([g, pd.DataFrame([tot])]); T(g, index=False)
H2("B. Eligible set by state")
g = e.groupby("state").agg(lakes_with_NLA_site=("lakeKey", "size"), lakes_with_cover_rows=("has_cover", "sum"),
    POS=("cls", lambda s: (s == "POS").sum()), NEG=("cls", lambda s: (s == "NEG").sum()), AMB=("cls", lambda s: (s == "AMB").sum())).reset_index(); T(g, index=False)
# --- scene availability (primary)
H2("C. 2017 scene search per lake (+-21 d of visit; both collections)")
rows = []
for k in cls.lakeKey[cls.n_stations > 0]:
    f = H/f"out/cells/{k}_status_both.json"
    if not f.exists(): rows.append(dict(lakeKey=k, c1_items=np.nan, l2a_items=np.nan, dates_any=np.nan, dates_cloud_lt90=np.nan, dates_read=np.nan)); continue
    s = json.load(open(f))["primary"]; se = s.get("_search", {})
    c1 = se.get("sentinel-2-c1-l2a", []); l2 = se.get("sentinel-2-l2a", [])
    dany = {d for d, _ in c1} | {d for d, _ in l2}
    dread = [d for d, v in s.items() if not d.startswith("_") and v is True]
    rows.append(dict(lakeKey=k, c1_items=len(c1), l2a_items=len(l2), dates_any=len(dany), dates_cloud_lt90=len(dread) , dates_read=len(dread)))
sa = pd.DataFrame(rows)
O.append(f"lakes searched: {len(sa)}; lakes with >=1 c1 item in window: {(sa.c1_items>0).sum()}; with >=1 sentinel-2-l2a item: {(sa.l2a_items>0).sum()}; with no item in either (NO_SCENE): {(sa.dates_any==0).sum()}; lakes with >=1 date with tile cloud < 90 %: {(sa.dates_read>0).sum()}\n")
O.append("distribution of distinct acquisition dates in window (any cloud): " + str(sa.dates_any.describe().round(1).to_dict()) + "\n")
# --- lake outcomes
def outcome(r):
    if r["why"] and isinstance(r["why"], str): return r["why"]
    return "SCORED"
sc["outcome"] = sc.apply(outcome, axis=1)
H2("D. Lake-level outcome per observer, primary 2017 (lakes with cover rows)")
p = sc[sc["mode"] == "primary"]
T(p.groupby(["observer", "outcome"]).size().unstack(fill_value=0).reset_index(), index=False)
H2("D2. Same, by NLA class (observer A)")
T(p[p.observer == "A"].groupby(["cls", "outcome"]).size().unstack(fill_value=0).reset_index(), index=False)
H2("D3. Secondary 2018+2019 (lake-year rows)")
s2 = sc[sc["mode"] == "secondary"]; T(s2.groupby(["observer", "outcome"]).size().unstack(fill_value=0).reset_index(), index=False)
# --- cell-level UNKNOWN shares per guard
H2("E. Belt-cell fate per observer (10-90 m belt, SHORE_ADJACENT excluded; lakes where the observer produced a map)")
rows = []
for mode in ("primary", "secondary"):
    for o in "SAP":
        x = sc[(sc["mode"] == mode) & (sc.observer == o) & sc.belt_cells.notna()]
        n = x.belt_cells.sum()
        rows.append(dict(mode=mode, observer=o, lake_maps=len(x), belt_cells=int(n), plant=x.belt_plant.sum() / n, open_water=x.belt_open.sum() / n, UNK_cloud_haze=x.unk_cloud.sum() / n,
                         UNK_dark=x.unk_dark.sum() / n, UNK_insufficient=x.unk_insuff.sum() / n, shore_adjacent_cells=int(x.shore_adj.sum())))
T(pd.DataFrame(rows).round(4), index=False)
H2("E2. Persistence status of observer P")
T(sc[sc.observer == "P"].groupby(["mode", "persistence"], dropna=False).size().reset_index(name="lake_rows"), index=False)
# --- metrics table
H2("F. Lake-level metrics and gates")
rows = []
for k, v in M.items():
    mode, o, *rest = k.split("/"); rows.append(dict(mode=mode, observer=o, score=rest[0] if rest else "belt_share(10-90m)", n_scored=v["n_scored"], pos=v["n_pos"], neg=v["n_neg"], amb=v["n_amb"], regions=v["n_regions"],
        spearman=v["spearman"], sp_ci=f"[{v['spearman_ci95'][0]:.2f},{v['spearman_ci95'][1]:.2f}]", auc=v["auc"], auc_ci=f"[{v['auc_ci95'][0]:.2f},{v['auc_ci95'][1]:.2f}]",
        neg_mean_share=v["neg_mean_belt_share"], neg_max=v["neg_max_belt_share"], neg_n_gt2pct=v["neg_n_over_2pct"], neg_pooled=v["neg_pooled_cell_share"], neg_whole_lake=v["neg_mean_whole_lake_share"], gate_c=v["gate_c"], gate_d=v["gate_d"]))
T(pd.DataFrame(rows).round(3), index=False)
# --- regions
H2("G. Per-EPA-region breakdown (observer A; belt_share 10-90 m)")
for mode in ("primary", "secondary"):
    d = pd.read_csv(H/f"out/nla_lakelevel_{mode}_A.csv").dropna(subset=["belt_share"])
    rows = []
    for r, g in d.groupby("epa_reg"):
        rows.append(dict(mode=mode, epa_reg=r, n_scored=len(g), pos=(g.cls == "POS").sum(), neg=(g.cls == "NEG").sum(), amb=(g.cls == "AMB").sum(),
                         med_share_pos=g[g.cls == "POS"].belt_share.median(), med_share_neg=g[g.cls == "NEG"].belt_share.median(), med_share_amb=g[g.cls == "AMB"].belt_share.median(),
                         spearman=spearmanr(g.belt_share, g.mean_ef)[0] if len(g) >= 6 and g.mean_ef.nunique() > 1 else np.nan))
    T(pd.DataFrame(rows).round(3), index=False)
# --- swir diagnostics
H2("H. Median water-pixel B11 / B04 reflectance per scene (diagnostic for collection / baseline effect)")
rows = []
for f in glob.glob(str(H/"out/cells/*.npz")):
    tag = re.search(r"_(p2017|s2018|s2019)_", f).group(1); z = np.load(f)
    rows.append(dict(tag=tag, swir=float(z["swir_med"]), red=float(z["red_med"])))
d = pd.DataFrame(rows).dropna(); T(d.groupby("tag").agg(scenes=("swir", "size"), swir_med=("swir", "median"), swir_p10=("swir", lambda s: s.quantile(.1)), swir_p90=("swir", lambda s: s.quantile(.9)),
    share_swir_gt_0215=("swir", lambda s: (s > 0.0215).mean()), red_med=("red", "median")).round(4).reset_index(), index=False)
# --- null geometry check
nb = [l["lakeKey"] for l in reg if l.get("geometry") is None]; O.append(f"\nnull-geometry lakes: {len(nb)}; with registry bbox: {sum(1 for l in reg if l.get('geometry') is None and l.get('bbox'))}\n")
open(H/"out/report_tables.md", "w").write("\n".join(O)); print("\n".join(O))
# wide per-lake csv
w = sc.pivot_table(index="lakeKey", columns=["mode", "observer"], values="belt_share", aggfunc="mean"); w.columns = [f"belt_share_{a}_{b}" for a, b in w.columns]
w = cls.set_index("lakeKey").join(w); w.to_csv(H/"out/nla_per_lake_wide.csv")
