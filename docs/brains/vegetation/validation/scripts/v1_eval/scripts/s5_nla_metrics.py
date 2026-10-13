"""NLA lake-level metrics (prereg s4/s5 c,d) from out/nla_{TAG}_both.json. Metric code (Spearman, AUC, bootstrap over lakes) reused from the earlier NLA harness (n5_score.py) unchanged.
usage: s5_nla_metrics.py TAG"""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent)); sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/nla/scripts")
sys.dont_write_bytecode = True
import json, numpy as np, pandas as pd
from pathlib import Path
import n5_score as N5
OUT = Path(__file__).resolve().parents[1] / "out"
TAG = sys.argv[1]
rows = json.load(open(OUT / f"nla_{TAG}_both.json"))
cls = N5.cls
def flat(r, m):
    d = dict(lakeKey=r["lakeKey"], tag=r["tag"], observer=m, n_inwindow=r.get("n_inwindow", 0), n_accepted=r.get("n_accepted", 0), bursts=len(r.get("bursts", []) or []))
    o = r.get(m)
    if not o: d.update(kind="NONE", why=r.get("why", "NO_SCENE"), belt_share=np.nan); return d
    d.update(kind=o["kind"], persistence=o["persistence"], fallback=o["fallback"], presence=o["presence"], why=o.get("why"), gap=o.get("gap"), coverage=o["coverage"],
             belt_share=o.get("belt_share", np.nan), belt_plant=o.get("belt_plant", 0), belt_seen=o.get("belt_read", 0), lake_plant=o.get("lake_plant", 0), lake_seen=o.get("lake_read", 0),
             **{f"b{i}_{k}": o.get(f"b{i}_{'read' if k == 'seen' else k}", 0) for i in (1, 2, 3) for k in ("plant", "seen")}, b40_plant=o.get("b40_plant", 0), b40_seen=o.get("b40_read", 0))
    return d
res = {}; tabs = {}
for mode, tags in (("primary", ["p2017"]), ("secondary", ["s2018", "s2019"])):
    for m in "SAP":
        df = pd.DataFrame([flat(r, m) for r in rows if r["tag"] in tags])
        if mode == "secondary":
            g = df.groupby("lakeKey").agg(belt_share=("belt_share", "mean"), belt_plant=("belt_plant", "sum"), belt_seen=("belt_seen", "sum"), lake_plant=("lake_plant", "sum"), lake_seen=("lake_seen", "sum"),
                                          n_accepted=("n_accepted", "max")).reset_index()
            df2 = g
        else: df2 = df
        df2 = df2.merge(cls[["name", "state", "epa_reg", "mean_ef", "cls"]], left_on="lakeKey", right_index=True)
        mm = N5.metrics(df2); mm["gate_c_raw"], mm["gate_d_mean"] = N5.gates(mm)
        sc = df2.dropna(subset=["belt_share"]); neg = sc[sc.cls == "NEG"]
        mm["n_negatives_total"] = int((cls.loc[cls.n_stations > 0].cls == "NEG").sum()); mm["n_neg_scored"] = len(neg)
        mm["neg_each_le_2pct"] = int((neg.belt_share <= 0.02).sum()); mm["neg_each_gt_2pct"] = int((neg.belt_share > 0.02).sum())
        mm["gate_d_strict_each"] = "NOT_TESTABLE" if len(neg) == 0 else ("PASS" if (neg.belt_share <= 0.02).all() else "FAIL")
        pos = sc[sc.cls == "POS"]; mm["n_pos_total"] = int((cls.loc[cls.n_stations > 0].cls == "POS").sum()); mm["pos_median_share"] = float(pos.belt_share.median()) if len(pos) else None
        # lake-level accounting (all eligible lakes incl unscored)
        if mode == "primary":
            d0 = df.copy(); mm["lakes_eligible"] = int(len(cls.loc[cls.n_stations > 0])); mm["lakes_in_run"] = len(d0)
            mm["lakes_with_accepted_pass"] = int((d0.n_accepted > 0).sum()); mm["lakes_P_reachable_ge3"] = int((d0.n_accepted >= 3).sum())
            mm["lakes_no_scene"] = int((d0.n_inwindow == 0).sum()); mm["lakes_burst_excluded"] = int((d0.bursts > 0).sum())
            mm["lakes_scored_fallback_only"] = int(((d0.n_accepted == 0) & d0.belt_share.notna()).sum())
            mm["presence_counts"] = d0.presence.value_counts().to_dict() if "presence" in d0 else {}
        res[f"{mode}/{m}"] = mm
        tabs[f"{mode}/{m}"] = df2
        df2.to_csv(OUT / f"nla_lakelevel_{TAG}_{mode}_{m}.csv", index=False)
json.dump(res, open(OUT / f"metrics_nla_{TAG}.json", "w"), indent=1, default=float)
f = lambda x: "nan" if x is None or x != x else f"{x:.3f}"
print(f"## NLA TAG {TAG}")
for k, v in res.items():
    print(k, "n", v["n_scored"], "pos/neg/amb", v["n_pos"], v["n_neg"], v["n_amb"], "regions", v["n_regions"], "AUC", f(v["auc"]), v["auc_ci95"], "rho", f(v["spearman"]), v["spearman_ci95"],
          "| neg mean", f(v["neg_mean_belt_share"]), "max", f(v["neg_max_belt_share"]), "neg<=2%:", v["neg_each_le_2pct"], "of", v["n_neg_scored"], "| gates c", v["gate_c_raw"], "d(mean)", v["gate_d_mean"], "d(each)", v["gate_d_strict_each"],
          *( ["| acc lakes", v["lakes_with_accepted_pass"], "P>=3", v["lakes_P_reachable_ge3"], "noscene", v["lakes_no_scene"], "burst", v["lakes_burst_excluded"], "fallback-only scored", v["lakes_scored_fallback_only"]] if "lakes_eligible" in v else []))
