#!/usr/bin/env python3
"""Write docs/research/depth-brain/ledger/contour.jsonl (source-use records with licences + findings) from the contour outputs."""
import json
from pathlib import Path
import pandas as pd
R = Path(__file__).resolve().parents[2] / "docs/research/depth-brain"
S = json.load(open(R / "data/contour_truth_summary.json"))
V = json.load(open(R / "data/contour_revalidation.json"))
M = json.load(open(R / "data/contour_method_check.json"))
SP = json.load(open(R / "data/contour_spatial_test.json"))["summary"]
src = {l_["id"]: l_ for l_ in map(json.loads, open(R / "ledger/sources.jsonl"))}
use = [("MN", "S-depth-002"), ("IN", "S-depth-003"), ("MT", "S-depth-004"), ("NE", "S-depth-005"), ("ND", "S-depth-006"), ("NH", "S-depth-007"), ("WA", "S-depth-008"), ("MI", "S-depth-009"),
       ("MA", "S-depth-010"), ("KS", "S-depth-011"), ("FL", "S-depth-012"), ("OK", "S-depth-013"), ("IL", "S-depth-014"), ("OH", "S-depth-015"), ("WV", "S-depth-017"), ("NJ", "S-depth-018"),
       ("CT", "S-depth-019"), ("TWDB", "S-depth-001"), ("UT", "S-depth-033"), ("PA", "S-depth-033"), ("WI", "S-depth-033")]
ab = S["by_source_tierAB"]; a = S["by_source_tierA"]; allv = S["matching"]["verified_lakes_by_source"]
rows = []
for i, (k, sid) in enumerate(use, 1):
    o = src[sid]
    note = {"FL": "DO NOT REDISTRIBUTE (FWC metadata: should not be distributed) - internal research use only; no raw contours or derived rasters may ship in the app or repo.",
            "TWDB": "TWDB states maps are not for navigation or fishing; only area-capacity-table shares are used here (no contours shipped).",
            "WI": "agency DRAFT 5-ft file; contours only to 10 ft -> excluded from validation (tier C).",
            "UT": "elevation contours converted with the Utah Lake compromise level 4489.045 ft: datum uncertain -> tier C.",
            "MI": "band polygons-as-lines (Min/Max) not interpretable as contours; only Min==Max lines used; most lakes partial -> tier C."}.get(k, "")
    rows.append({"kind": "source", "id": f"S-contour-{i:03d}", "scoutId": sid, "name": o["name"], "org": o["org"], "url": o["url"], "accessed": "2026-10-13", "license": o["license"], "redistribution": note or "no raw-contour redistribution implied; review licence before shipping to app users",
                 "decision": "USED_FOR_TRUTH", "verifiedFleetLakes": allv.get(k, 0), "tierA": a.get(k, 0), "tierAB": ab.get(k, 0), "reason": "normalised with contour_ingest.py; spatially matched with contour_match.py; truth in contour_truth_lakes.csv"})
for sid, nm, d in (("S-depth-039", "EPA NLA 2007 DEPTHMAX", "index-site depth: lower bound of max depth; used only as completeness anchor"), ("S-depth-021", "OWRB lake points depth_max", "regulator-reported max depth; anchor"),
                   ("S-depth-022", "MI IFR max-depth points", "agency max depth; anchor")):
    o = src[sid]; rows.append({"kind": "source", "id": "S-contour-A" + sid[-3:], "scoutId": sid, "name": nm, "license": o["license"], "decision": "USED_AS_ANCHOR", "reason": d, "accessed": "2026-10-13"})
f = []
m = S["matching"]
f.append(dict(question="How many fleet lakes can be matched to REAL contour data by geometry?", finding=f"{m['verified_distinct_fleet_lakes']} fleet lakes verified spatially (134 from 20 contour sources + 6 TWDB area-capacity tables); scout name candidates mostly confirmed, 3 rejected (polygon extent mismatch), 24 weak-overlap + 6 embedded-water-body pairs rejected; 59 name-only (index/catalog sources)",
              numbers=str(m["pairs_by_confidence"]), n="621 fleet lakes / 599 polygons", confidence="high"))
f.append(dict(question="How many verified lakes have adequate truth (data-quality flag)?", finding=f"137 truth rows: tier A {S['tier_counts']['A']}, tier B {S['tier_counts']['B']}, tier C {S['tier_counts']['C']} (partial lakes, >10 ft contour steps, datum/top truncation); analysis sets A (n={S['tier_counts']['A']}) and A+B (n={S['tier_counts']['A']+S['tier_counts']['B']})",
              numbers=str(S["by_source_tierAB"]), n=str(S["n_unique_lakes_excl_fleet_duplicates"]), confidence="high"))
tw = M["twdb_native"]; t5 = M["twdb_d5"]; t10 = M["twdb_d10"]
f.append(dict(question="Is the contour-to-shares method accurate? (real TWDB contours vs exact area-capacity tables, 18 lakes)", finding="native 1-2 ft ladders: MAE 0.010-0.013 share; 5-ft ladder MAE 0.015-0.026; 10-ft ladder MAE 0.020-0.070 with a +0.05-0.07 bias at <=6 ft (overstates shallow)",
              numbers=f"native s3/s6/s10 MAE {tw['s3']['mae']:.3f}/{tw['s6']['mae']:.3f}/{tw['s10']['mae']:.3f}; d5 {t5['s3']['mae']:.3f}/{t5['s6']['mae']:.3f}/{t5['s10']['mae']:.3f}; d10 {t10['s3']['mae']:.3f}/{t10['s6']['mae']:.3f}/{t10['s10']['mae']:.3f}", n="18", confidence="high"))
x = V["e_crosscheck_vs_terrain_mn"]
f.append(dict(question="Does this thread's contour method agree with the terrain thread's independent MN extraction?", finding="yes except Minnetonka (fleet polygon 55.6 km2 vs DNR pool 66.7 km2)", numbers=f"MAE share<6ft {x['mae_lt6']:.3f}, Spearman {x['spearman_lt6']:.2f}", n=str(x["n"]), confidence="high"))
d = V["a1_globathy_dmax_vs_contour_max"]["AB"]["contour_top_ge15ft_unconfirmed|verified+weak"]
f.append(dict(question="GLOBathy Dmax vs contour max depth (modeled-Dmax lakes only)", finding="no skill over a constant; regresses to the middle", numbers=f"n={d['n']} Spearman {d['spearman']:.2f} CI {d['spearman_ci'][0]:.2f}..{d['spearman_ci'][1]:.2f}; within 2x {d['within_2']:.2f} vs constant {d['const_within_2']:.2f}; median ratio {d['median_ratio']:.2f}", n=str(d["n"]), confidence="medium"))
g = V["a2_globathy_shallow_shares"]["AB"]["lt1.8m(5.9ft)|verified+weak"]
f.append(dict(question="GLOBathy A(h) share of area shallower than 1.8 m (5.9 ft) vs contour truth", finding="worse than constant; no ranking", numbers=f"n={g['n']} MAE {g['mae']:.3f} vs constant {g['mae_const']:.3f}; Spearman {g['spearman']:.2f} CI {g['spearman_ci'][0]:.2f}..{g['spearman_ci'][1]:.2f}; AUC top-third {g['auc_top_third_shallow']:.2f}", n=str(g["n"]), confidence="medium"))
c = V["c_proxies"]["A"]["single_predictors_vs_shr_lt6"]
f.append(dict(question="Which cheap proxy predicts broad-shallow lakes (top third of share <6 ft)?", finding="none reliably; best is HydroLAKES/NID mean depth (AUC 0.62, CI spans 0.5); polygon proxies 0.47-0.56; leave-one-state-out ridge models do not beat the constant",
              numbers="; ".join(f"{k}: AUC {v['auc_top_third']:.2f} [{v['auc_ci'][0]:.2f},{v['auc_ci'][1]:.2f}] rho {v['spearman']:.2f}" for k, v in c.items() if "ORACLE" not in k), n=str(V['c_proxies']['A']['n']), confidence="medium"))
o = [v for k, v in c.items() if "ORACLE contour mean" in k][0]
f.append(dict(question="Ceiling: would knowing mean depth exactly be enough?", finding="yes - true mean depth ranks broad-shallow lakes well, so any route to mean depth (not Dmax) is the lever", numbers=f"oracle mean depth AUC {o['auc_top_third']:.2f} [{o['auc_ci'][0]:.2f},{o['auc_ci'][1]:.2f}] rho {o['spearman']:.2f}; oracle Dmax AUC 0.79", n=str(o["n"]), confidence="medium"))
t1 = SP["T1_per_lake_spearman"]["sp_slope_10_60_vs_sh6"]; t2 = SP["T2_masks_le6ft"]
f.append(dict(question="Within-lake: do 3DEP shoreline slope + distance predict where the 0-6 ft zone is?", finding="slope is a real but modest within-lake signal; distance from shore does most of the work", numbers=f"per-lake rho(slope_10_60, share<=6ft in 100 m band) mean {t1['mean']:.2f} CI {t1['ci_mean'][0]:.2f}..{t1['ci_mean'][1]:.2f}, {t1['n_neg']}/{t1['n']} lakes negative; slope-aware mask IoU {t2['iou_slope_mean']:.3f} vs constant-width {t2['iou_const_mean']:.3f} (delta CI {t2['delta_iou_ci'][0]:.3f}..{t2['delta_iou_ci'][1]:.3f}); AUC dist {SP['T3_loo_auc']['d6']['auc_dist']['mean']:.3f} -> dist+slope {SP['T3_loo_auc']['d6']['auc_dist_plus_slope']['mean']:.3f}", n=str(SP["n_lakes"]), confidence="medium"))
for i, d_ in enumerate(f, 1): d_.update(kind="finding", id=f"F-contour-{i:03d}")
with open(R / "ledger/contour.jsonl", "w") as fh:
    for r in rows + f: fh.write(json.dumps(r) + "\n")
print(len(rows), "sources", len(f), "findings")
