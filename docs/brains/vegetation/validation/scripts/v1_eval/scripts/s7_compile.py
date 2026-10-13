"""Assemble tables for note 11 from out/*.json|pkl. Writes out/tables.md and prints it."""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent)); sys.dont_write_bytecode = True
import json, pickle, numpy as np, pandas as pd
from pathlib import Path
OUT = Path(__file__).resolve().parents[1] / "out"
f = lambda x, n=3: "n/a" if x is None or (isinstance(x, float) and x != x) else (f"{x:.{n}f}" if isinstance(x, float) else str(x))
L = []
def p(s=""): L.append(s)
cal = json.load(open(OUT / "calibration.json"))
p("### T1 calibration"); p(f"pooled P99.5 = {cal['percentile_all']:.4f}; per lake: " + "; ".join(f"{k}: P99.5 {v['p995']:.4f}, P99 {v['p99']:.4f}, median {v['p50']:.4f}, {v['accepted']}/{v['scenes']} scenes accepted, {v['n_pixels']:,} px" for k, v in cal["per_lake"].items()) + f"; seen-pixel-only variant P99.5 {cal['sensitivity_seen_pixels_only_p995']:.4f}; NIR_PLANT_MIN = {cal['NIR_PLANT_MIN']}")
SN = ["Serene", "Blackmans", "Storm", "Roesiger", "Bosworth"]
for TAG in ("frozen", "prov", "frozen_nohaze", "prov_nohaze"):
    M = json.load(open(OUT / f"metrics_snoco_fwc_{TAG}.json")); p(); p(f"### T2[{TAG}] Snohomish (floor {M['floor']}), strict-none negatives, interior population")
    p("| obs | TP | FP | FN | P_raw | R_int | F1_raw | IoU | P_m50 | F1_m50 | FPR(all-neg) | FPR(known) | neg UNKNOWN | R_whole | pos UNKNOWN | F1_raw CI |"); p("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
    for m in "SAP":
        q = M["snoco"][f"{m}|strict"]["pooled"]
        p(f"| {m} | {q['TP']} | {q['FP']} | {q['FN']} | {f(q['P_raw'])} | {f(q['R_int'])} | {f(q['F1_raw'])} | {f(q['IoU_raw'])} | {f(q['P_matched50'])} | {f(q['F1_matched50'])} | {f(q['FPR_all'])} | {f(q['FPR_known'])} | {f(q['neg_unknown_share'])} | {f(q['R_whole'])} | {f(q['pos_unknown_share'])} | {q['ci_F1_raw'][:2]} |")
    q = M["snoco"]["P|strict"]["pooled"]; p(f"(positives interior {q['npos_int']} / whole-lake {q['npos_whole']}; open-water negatives {q['nneg']}; lakes with >=30 interior positives: {q['lakes_with_ge30_pos']}; lakes with any: {q['lakes_with_pos']})")
    p("per lake (P): " + "; ".join(f"{nm}: {d['kind']}/{d['persistence']} nacc {d['n_accepted']} presence {d['presence']} npos {d['npos_int']} TP {d['TP']} FP {d['FP']} nneg {d['nneg']}" for nm, d in M["snoco"]["P|strict"]["per_lake"].items()))
    p(); p(f"### T3[{TAG}] FWC points recall (7 lakes, surface-point cells)"); p("| obs | n cells (whole) | R_all (UNK=miss) | R_int | R_all known-only | R_all CI |"); p("|---|---|---|---|---|---|")
    for m in "SAP":
        q = M["fwc"][m]["pooled"]; p(f"| {m} | {q['n_all']} | {f(q['R_all'])} | {f(q['R_int'])} | {f(q['R_all_known'])} | {q['ci_R_all'][:2]} |")
    p("per lake P: " + "; ".join(f"{nm}: n {d['n_all']} R {f(d['R_all'])} {d['presence']}/{d['kind']}" for nm, d in M["fwc"]["P"]["per_lake"].items()))
for TAG in ("frozen", "prov", "frozen_nohaze", "prov_nohaze"):
    M = json.load(open(OUT / f"metrics_nla_{TAG}.json")); p(); p(f"### T4[{TAG}] NLA lake-level")
    p("| set/obs | scored | pos/neg/amb | regions | AUC (CI) | Spearman (CI) | neg mean | neg max | neg <=2% | gate c | gate d (each lake) | gate d (mean) |"); p("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for k, v in M.items():
        p(f"| {k} | {v['n_scored']} | {v['n_pos']}/{v['n_neg']}/{v['n_amb']} | {v['n_regions']} | {f(v['auc'], 2)} ({f(v['auc_ci95'][0], 2)}-{f(v['auc_ci95'][1], 2)}) | {f(v['spearman'], 2)} ({f(v['spearman_ci95'][0], 2)}..{f(v['spearman_ci95'][1], 2)}) | {f(v['neg_mean_belt_share'])} | {f(v['neg_max_belt_share'])} | {v['neg_each_le_2pct']}/{v['n_neg_scored']} of {v['n_negatives_total']} | {v['gate_c_raw']} | {v['gate_d_strict_each']} | {v['gate_d_mean']} |")
    v = M["primary/P"]; p(f"reachability (primary): eligible {v['lakes_eligible']}, with accepted pass {v['lakes_with_accepted_pass']}, P-reachable (>=3 accepted) {v['lakes_P_reachable_ge3']}, NO_SCENE {v['lakes_no_scene']}, lakes with burst exclusion {v['lakes_burst_excluded']}, scored on fallback only {v['lakes_scored_fallback_only']}; P presence counts {v['presence_counts']}")
# per-lake NLA table (frozen primary P)
d = pd.read_csv(OUT / "nla_lakelevel_frozen_primary_P.csv"); rows = json.load(open(OUT / "nla_frozen_both.json")); rp = {r["lakeKey"]: r for r in rows if r["tag"] == "p2017"}
d = d.sort_values(["cls", "mean_ef"], ascending=[True, False])
p(); p("### T5 NLA per-lake (frozen floor, primary 2017, observer P). cls, mean(emergent,floating) code, in-window scenes, accepted, evidence kind, belt read cells, belt share, presence")
p("| lake | st | cls | mean_ef | scenes | acc | kind | belt read | belt share | presence |"); p("|---|---|---|---|---|---|---|---|---|---|")
for _, r in d.iterrows():
    rr = rp.get(r.lakeKey, {}); pp = rr.get("P", {})
    p(f"| {r['name']} | {r.state} | {r.cls} | {f(r.mean_ef, 2)} | {rr.get('n_inwindow', 0)} | {rr.get('n_accepted', 0)} | {pp.get('kind', 'NONE')}{'(fallback)' if pp.get('fallback') else ''} | {int(r.belt_seen) if r.belt_seen == r.belt_seen else 0} | {f(r.belt_share)} | {pp.get('presence', 'UNKNOWN')} |")
# guard shares
def shares(rows_, key="scene_unknown_cells", tot="scene_eligible_cells_total"):
    s = {}; T = 0
    for r in rows_:
        if tot not in r: continue
        T += r[tot]
        for k, v in r[key].items(): s[k] = s.get(k, 0) + v
    known = 1 - sum(s.values()) / max(T, 1)
    return {k: v / max(T, 1) for k, v in sorted(s.items(), key=lambda kv: -kv[1])}, known, T
R = pickle.load(open(OUT / "snoco_fwc_frozen.pkl", "rb"))
sets = {"Snohomish (5 lakes, scenes +-21 d)": [r["info"] for k, r in R.items() if k.startswith("snoco")], "FWC points (7 lakes)": [r["info"] for k, r in R.items() if k.startswith("fwc")], "NLA 2017 primary (47 lakes)": [r for r in rows if r["tag"] == "p2017"]}
p(); p("### T6 per-guard UNKNOWN share of ELIGIBLE cells, pooled over all in-window scenes (frozen floor; cell-weighted). 'known' = cells with a plant/no-plant call")
for nm, rs in sets.items():
    s, known, T = shares(rs); p(f"- {nm}: known {known:.3f}; " + ", ".join(f"{k} {v:.3f}" for k, v in s.items()) + f"  (eligible cell-scenes {T:,})")
for TAG in ("frozen_nohaze",):
    rows2 = json.load(open(OUT / f"nla_{TAG}_both.json")); s, known, T = shares([r for r in rows2 if r["tag"] == "p2017"]); p(f"- DIAGNOSTIC NLA 2017, {TAG}: known {known:.3f}; " + ", ".join(f"{k} {v:.3f}" for k, v in s.items()))
    R2 = pickle.load(open(OUT / f"snoco_fwc_{TAG}.pkl", "rb")); s, known, T = shares([r["info"] for k, r in R2.items() if k.startswith("snoco")]); p(f"- DIAGNOSTIC Snohomish, {TAG}: known {known:.3f}; " + ", ".join(f"{k} {v:.3f}" for k, v in s.items()))
# reachability across sets
p(); p("### T7 reachability and bursts (frozen)")
for nm, rs in sets.items():
    inw = [r for r in rs if r.get("n_inwindow") is not None]; acc = [r for r in inw if r["n_accepted"] > 0]; p3 = [r for r in inw if r["n_accepted"] >= 3]; bu = [r for r in inw if r.get("bursts")]
    p(f"- {nm}: lakes {len(inw)}; with >=1 scene in window {sum(1 for r in inw if r['n_inwindow'] > 0)}; with an accepted (>=50%) pass {len(acc)}; P-reachable (>=3 accepted) {len(p3)}; burst exclusion lakes {len(bu)} {[ (r.get('lakeKey') or r.get('nm'), r['bursts']) for r in bu]}")
# secondary frozen per-observer already in T4. Per-guard on the P observation level (NLA primary)
p(); p("### T8 observation-level (observer P) refusal shares, NLA primary frozen, eligible-cell weighted")
s = {}; T = 0; pres = {}
for r in sets["NLA 2017 primary (47 lakes)"]:
    if "P" not in r: continue
    T += r["n_eligible"]; pres[r["P"]["presence"]] = pres.get(r["P"]["presence"], 0) + 1
    for k, v in r["P"]["shares"].items(): s[k] = s.get(k, 0) + v * r["n_eligible"]
p(", ".join(f"{k} {v / T:.3f}" for k, v in sorted(s.items(), key=lambda kv: -kv[1])) + f"; lake presence {pres}")
open(OUT / "tables.md", "w").write("\n".join(L)); print("\n".join(L))
