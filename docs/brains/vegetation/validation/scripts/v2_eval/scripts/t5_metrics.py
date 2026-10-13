"""All TEST metrics + gates + descriptive tables from out/test_raw.pkl, out/test_umn_sfwmd.pkl, out/desc_seasonal.pkl. Writes out/metrics_v02.json and out/tables_v02.md (no scoring, no tuning)."""
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent)); sys.path.insert(0, "{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments/adoption/nla/scripts")
from v2metrics import *
from v2jobs import DEV_SNOCO, TEST_SNOCO, SNOCO, FWC_IDS, nla_split
import pickle, collections
import n5_score as N5
install_guard()
T = pickle.load(open(OUT2 / "test_raw.pkl", "rb")); KEY = pair_key(*T["pair"]); SF = T["snoco_fwc"]; NL = T["nla"]
split = nla_split().set_index("lakeKey"); cls = N5.cls
SN = {f"snoco|{n}": SF[f"snoco|{n}"] for n in SNOCO.values()}
FW = list(FWC_IDS)
f3 = lambda x: "n/a" if x is None or x != x else f"{x:.3f}"
M = {}; L = []
def P(s=""): L.append(s)
# ---------------------------------------------------------------- Snohomish
for setname, lakes in (("TEST", TEST_SNOCO), ("DEV_under_frozen_pair", DEV_SNOCO), ("ALL5_descriptive", DEV_SNOCO + TEST_SNOCO)):
    for neg in ("strict", "buffered"):
        for m in "SAP":
            ev = snoco_eval(SF, KEY, lakes, m, neg, bootstrap=(neg == "strict"))
            M[f"snoco/{setname}/{neg}/{m}"] = ev
P("## Snohomish cell metrics (interior population, strict-none negatives, frozen pair %s)" % (T["pair"],))
for setname, lakes in (("TEST", TEST_SNOCO), ("DEV_under_frozen_pair", DEV_SNOCO), ("ALL5_descriptive", DEV_SNOCO + TEST_SNOCO)):
    P(f"\n### {setname}: {lakes}\n")
    P("| obs | negatives | TP | FP | FN(int) | interior pos | whole-lake pos | P raw | R interior (UNK=miss) | R known-only | R whole-lake | F1 raw | IoU | open-water FPR all | FPR known | neg cells | neg known | neg UNKNOWN share | F1 95% CI (lakes) |")
    P("|" + "---|" * 19)
    for neg in ("strict", "buffered"):
        for m in "SAP":
            p = M[f"snoco/{setname}/{neg}/{m}"]["pooled"]
            P(f"| {m} | {neg} | {p['TP']} | {p['FP']} | {p['FN']} | {p['npos_int']} | {p['npos_whole']} | {f3(p['P_raw'])} | {f3(p['R_int'])} | {f3(p['R_known'])} | {f3(p['R_whole'])} | {f3(p['F1_raw'])} | {f3(p['IoU_raw'])} | {f3(p['FPR_all'])} | {f3(p['FPR_known'])} | {p['nneg']} | {p['neg_known']} | {f3(p['neg_unknown_share'])} | {p.get('ci_F1_raw', 'n/a')} |")
P("\n### Snohomish per lake (strict negatives; observer A / P / S)\n")
P("| lake | split | obs | kind | persistence | acc scenes | TP | FN | interior pos | whole pos | tp whole | FP | neg known | plant cells | presence |")
P("|" + "---|" * 15)
for nm in DEV_SNOCO + TEST_SNOCO:
    ev_all = {m: snoco_eval(SF, KEY, [nm], m, "strict") for m in "SAP"}
    for m in "SAP":
        pl = ev_all[m]["per_lake"][nm]; c = ev_all[m]["per_counts"][nm]
        P(f"| {nm} | {'DEV' if nm in DEV_SNOCO else 'TEST'} | {m} | {pl['kind']} | {pl['persistence']} | {pl['n_accepted']} | {pl['TP']} | {pl['FN']} | {pl['npos_int']} | {pl['npos_whole']} | {c['tp_whole']} | {pl['FP']} | {pl['neg_known']} | {pl['plant_cells']} | {pl['presence']} |")
# ---------------------------------------------------------------- FWC
P("\n## FWC LTM points (recall only; 7 lakes, 1,205 surface-point cells in V1)\n")
P("| obs | n point-cells | recall (UNK=miss) | interior recall | known-only recall | 95% CI lakes | per lake (all-recall) |")
P("|---|---|---|---|---|---|---|")
for m in "SAP":
    r = fwc_recall(SF, KEY, FW, m); M[f"fwc/{m}"] = r; p = r["pooled"]
    P(f"| {m} | {p['n_all']} | {f3(p['R_all'])} | {f3(p['R_int'])} | {f3(p['R_all_known'])} | {p['ci_R_all'][:2]} | " + ", ".join(f"{k}:{f3(v['R_all'])}" for k, v in r["per_lake"].items()) + " |")
# ---------------------------------------------------------------- reachability and guards (cell-scene shares)
def guard_table(title, recs):
    """recs: list of run records with .sel"""
    tot = sum(r["sel"]["scene_eligible_cells_total"] for r in recs); g = {}
    for r in recs:
        for k, v in r["sel"]["scene_unknown_cells"].items(): g[k] = g.get(k, 0) + v
    unk = sum(g.values()); out = dict(title=title, cell_scenes=tot, known=(1 - unk / tot) if tot else None, **{k: v / tot for k, v in g.items()} if tot else {})
    return out
def reach(recs):
    n = len(recs); cov = [c for r in recs for c in r["sel"]["cov"]]
    return dict(lakes=n, with_scene=sum(r["sel"]["n_inwindow"] > 0 for r in recs), accepted=sum(r["sel"]["n_accepted"] >= 1 for r in recs), P_reachable=sum(r["sel"]["n_accepted"] >= 3 for r in recs),
                burst_lakes=sum(len(r["sel"]["bursts"]) > 0 for r in recs), burst_scenes=sum(len(r["sel"]["bursts"]) for r in recs), scenes=len(cov), share_ge50=(np.mean([c >= 0.5 for c in cov]) if cov else None),
                share_ge25=(np.mean([c >= 0.25 for c in cov]) if cov else None),
                fallback_only=sum(r["sel"]["n_accepted"] == 0 and any(c >= 0.25 for c in r["sel"]["cov"]) for r in recs))
sets = {}
sets["Snohomish TEST (3)"] = [SN[f"snoco|{n}"]["runs"][KEY] for n in TEST_SNOCO]
sets["Snohomish DEV (2)"] = [SN[f"snoco|{n}"]["runs"][KEY] for n in DEV_SNOCO]
sets["FWC (7)"] = [SF[f"fwc|{n}"]["runs"][KEY] for n in FW]
def nla_rows(tag, which):
    out = []
    for r in NL:
        if r["tag"] not in tag or "runs" not in r: continue
        sp = split.loc[r["lakeKey"], "split"]
        if which == "ALL" or sp == which: out.append(r)
    return out
for w in ("TEST", "DEV", "ALL"):
    sets[f"NLA 2017 primary {w}"] = [r["runs"][KEY] for r in nla_rows(["p2017"], w)]
sets["NLA secondary 2018+2019 TEST (scene-year records)"] = [r["runs"][KEY] for r in nla_rows(["s2018", "s2019"], "TEST")]
P("\n## Refusal shares by guard (share of eligible cell-scenes over every in-window scene; 'known' = cells with a plant/no-plant call) and accepted-pass reach\n")
cols = ["CLOUD", "SHADOW", "HAZE", "GLARE", "DARK_WATER", "SHORE_ADJACENT", "INSUFFICIENT_VALID_PIXELS", "ICE_OR_SNOW", "BLOOM_AMBIGUOUS"]
P("| set | cell-scenes | known | " + " | ".join(cols) + " |"); P("|" + "---|" * (3 + len(cols)))
for k, recs in sets.items():
    g = guard_table(k, recs); M["guards/" + k] = g
    P(f"| {k} | {g['cell_scenes']:,} | {f3(g['known'])} | " + " | ".join(f3(g.get(c_, 0.0)) for c_ in cols) + " |")
P("\n| set | lakes | with in-window scene | with accepted pass (>=50 %) | P-reachable (>=3 accepted) | fallback-only (25-50 %) | burst lakes / scenes | in-window scenes | share scenes >=50 % | share >=25 % |"); P("|" + "---|" * 10)
for k, recs in sets.items():
    r_ = reach(recs); M["reach/" + k] = r_
    P(f"| {k} | {r_['lakes']} | {r_['with_scene']} | {r_['accepted']} | {r_['P_reachable']} | {r_['fallback_only']} | {r_['burst_lakes']} / {r_['burst_scenes']} | {r_['scenes']} | {f3(r_['share_ge50'])} | {f3(r_['share_ge25'])} |")
# ---------------------------------------------------------------- NLA
def flat(r, m, key=KEY):
    d = dict(lakeKey=r["lakeKey"], tag=r["tag"], observer=m)
    run = r.get("runs", {}).get(key)
    if run is None:
        d.update(kind="NONE", why=r.get("why", "NO_SCENE"), belt_share=np.nan, n_accepted=0, n_inwindow=0, bursts=0, presence="UNKNOWN"); return d
    o = run["obs"][m]; d.update(n_inwindow=run["sel"]["n_inwindow"], n_accepted=run["sel"]["n_accepted"], bursts=len(run["sel"]["bursts"]))
    d.update(kind=o["kind"], persistence=o["persistence"], fallback=o["fallback"], presence=o["presence"], why=o.get("why"), gap=o.get("gap"), coverage=o["coverage"],
             belt_share=o.get("belt_share", np.nan), belt_plant=o.get("belt_plant", 0), belt_seen=o.get("belt_read", 0), lake_plant=o.get("lake_plant", 0), lake_seen=o.get("lake_read", 0))
    return d
def nla_eval(which, mode_name, m):
    tags = ["p2017"] if mode_name == "primary" else ["s2018", "s2019"]
    rows = [flat(r, m) for r in NL if r["tag"] in tags and (which == "ALL" or split.loc[r["lakeKey"], "split"] == which)]
    df = pd.DataFrame(rows)
    if mode_name == "secondary":
        df = df.groupby("lakeKey").agg(belt_share=("belt_share", "mean"), belt_plant=("belt_plant", "sum"), belt_seen=("belt_seen", "sum"), lake_plant=("lake_plant", "sum"), lake_seen=("lake_seen", "sum"), n_accepted=("n_accepted", "max")).reset_index()
    df2 = df.merge(cls[["name", "state", "epa_reg", "mean_ef", "cls"]], left_on="lakeKey", right_index=True)
    mm = N5.metrics(df2); mm["gate_c"], _ = N5.gates(mm)
    sc = df2.dropna(subset=["belt_share"]); neg = sc[sc.cls == "NEG"]
    mm["n_neg_scored"] = len(neg); mm["n_neg_in_set"] = int((df2.cls == "NEG").sum()); mm["neg_each_le_2pct"] = int((neg.belt_share <= 0.02).sum())
    mm["gate_d_each"] = "NOT_TESTABLE" if len(neg) == 0 else ("PASS" if (neg.belt_share <= 0.02).all() else "FAIL")
    mm["gate_d_mean"] = "NOT_TESTABLE" if len(neg) == 0 else ("PASS" if neg.belt_share.mean() <= 0.02 else "FAIL")
    mm["neg_detail"] = [(r_.lakeKey, (None if r_.belt_share != r_.belt_share else float(r_.belt_share)), int(r_.belt_seen)) for r_ in df2[df2.cls == "NEG"].itertuples()]
    mm["n_lakes_in_set"] = len(df2)
    if mode_name == "primary":
        mm["lakes_accepted"] = int((df.n_accepted > 0).sum()); mm["lakes_P_reach"] = int((df.n_accepted >= 3).sum()); mm["presence_counts"] = df.presence.value_counts().to_dict() if "presence" in df else {}
    df2.to_csv(OUT2 / f"nla_lakelevel_{which}_{mode_name}_{m}.csv", index=False)
    return mm
P("\n## NLA lake-level (belt = interior cells with centre 10-90 m from edge; lake scored if >= 10 read belt cells)\n")
P("| set | mode | obs | lakes scored | pos/neg/amb | regions | AUC (95% CI) | Spearman (95% CI) | gate c | neg lakes scored / in set | negatives each <=2% | neg mean | neg max | gate d (each) | gate d (mean) |"); P("|" + "---|" * 15)
for which, mode_name in (("TEST", "primary"), ("TEST", "secondary"), ("DEV", "primary"), ("ALL", "primary")):
    for m in "SAP":
        mm = nla_eval(which, mode_name, m); M[f"nla/{which}/{mode_name}/{m}"] = mm
        P(f"| {which}{' (DESCRIPTIVE, tuned-on)' if which == 'DEV' else (' (descriptive, mixed)' if which == 'ALL' else '')} | {mode_name} | {m} | {mm['n_scored']} | {mm['n_pos']}/{mm['n_neg']}/{mm['n_amb']} | {mm['n_regions']} | {f3(mm['auc'])} ({f3(mm['auc_ci95'][0])}-{f3(mm['auc_ci95'][1])}) | {f3(mm['spearman'])} ({f3(mm['spearman_ci95'][0])}..{f3(mm['spearman_ci95'][1])}) | {mm['gate_c']} | {mm['n_neg_scored']}/{mm['n_neg_in_set']} | {mm['neg_each_le_2pct']} | {f3(mm['neg_mean_belt_share'])} | {f3(mm['neg_max_belt_share'])} | {mm['gate_d_each']} | {mm['gate_d_mean']} |")
P("\n### NLA negatives (primary, observer A and P): lake, belt share, belt read cells\n")
for which in ("TEST", "DEV"):
    for m in "AP":
        P(f"- {which} {m}: " + "; ".join(f"{k}: {'unscored' if v is None else f'{v:.3f}'} (n={n})" for k, v, n in M[f"nla/{which}/primary/{m}"]["neg_detail"]))
P("\n### NLA per-lake table (primary, observer P; split, class, mean_ef, accepted scenes, kind, belt read, belt share, presence)\n")
P("| lake | split | cls | mean_ef | scenes | acc | kind | persistence | belt read | belt share | presence |"); P("|" + "---|" * 11)
dfp = pd.read_csv(OUT2 / "nla_lakelevel_ALL_primary_P.csv")
dfpA = pd.read_csv(OUT2 / "nla_lakelevel_ALL_primary_A.csv")
for r in dfp.sort_values(["cls", "mean_ef"], ascending=[True, False]).itertuples():
    P(f"| {r.name} {r.state} | {split.loc[r.lakeKey, 'split']} | {r.cls} | {r.mean_ef:.2f} | {r.n_inwindow if hasattr(r, 'n_inwindow') else ''} | {r.n_accepted} | {r.kind} | {getattr(r, 'persistence', '')} | {int(r.belt_seen) if r.belt_seen == r.belt_seen else 0} | {f3(r.belt_share)} | {r.presence} |")
# ---------------------------------------------------------------- UMN / SFWMD
U = pickle.load(open(OUT2 / "test_umn_sfwmd.pkl", "rb"))
P("\n## UMN points (recall only; scene year = labelled substitute except tier E)\n")
P("| lake | survey yr tier | scene yr | obs | points | recall (UNK/shore=miss) | recall interior-read-only (PLANT / read interior) | read interior | shore-adjacent/outside | UNKNOWN interior |"); P("|" + "---|" * 10)
um = collections.defaultdict(lambda: collections.Counter())
for lk, d in U["umn"].items():
    for r in d["rows"]:
        if r["strict"] != "1": continue
        k = (lk, r["tier"], r["sy"], r["obs"]); c = um[k]; c["n"] += 1
        if r["state"] == O.PLANT: c["plant"] += 1
        if r["interior"]:
            if r["state"] in (O.PLANT, O.NO_PLANT): c["read_int"] += 1
            else: c["unk_int"] += 1
        else: c["shore"] += 1
agg = collections.defaultdict(lambda: collections.Counter())
for (lk, tier, sy, o), c in sorted(um.items()):
    P(f"| {lk} | {tier} | {sy} | {o} | {c['n']} | {c['plant'] / c['n']:.3f} | {c['plant']}/{c['read_int']} | {c['read_int']} | {c['shore']} | {c['unk_int']} |")
    a = agg[(tier, o)]; a["n"] += c["n"]; a["plant"] += c["plant"]; a["read_int"] += c["read_int"]
P("\nPooled UMN surface_strict recall by tier / observer (tier E = exact year; A = adjacent year after an S2-era survey; N/F = near/far substitutes):\n")
P("| tier | obs | points (point x scene-year) | recall (UNK/shore=miss) | PLANT | read interior |"); P("|---|---|---|---|---|---|")
for (tier, o), a in sorted(agg.items()): P(f"| {tier} | {o} | {a['n']} | {a['plant'] / a['n']:.3f} | {a['plant']} | {a['read_int']} |")
M["umn_pooled"] = {f"{t}|{o}": dict(a) for (t, o), a in agg.items()}
P("\n## SFWMD littoral polygons (labelled SUBSTITUTE: polygons 2015/2016 vs scenes 2018/2019; supplementary)\n")
P("| lake | scene yr | obs | kind | acc scenes / in-window | pos whole | pos interior | TP int | recall int (UNK=miss) | recall known | FP | open-water neg known | FPR known | precision raw | neg UNKNOWN |"); P("|" + "---|" * 15)
for lk, d in U["sfwmd"].items():
    for k, r in d["recs"].items():
        sy, o = k.split("|"); kn = r["tp_int"] / max(1, r["known_pos_int"]); fpr = r["fp"] / max(1, r["fp"] + r["tn"]); prec = r["tp_int"] / (r["tp_int"] + r["fp"]) if r["tp_int"] + r["fp"] else float("nan")
        P(f"| {lk} | {sy} | {o} | {r['kind']} | {r['n_accepted_scenes']}/{r['n_inwin']} | {r['pos_whole']} | {r['pos_int']} | {r['tp_int']} | {f3(r['tp_int'] / max(1, r['pos_int']))} | {f3(kn)} | {r['fp']} | {r['fp'] + r['tn']} | {f3(fpr)} | {f3(prec)} | {r['neg_unknown']}/{r['neg_n']} |")
P("\nUMR Pool 5 / " + "; ".join(U["notrun"]) + " -> NOT_RUN")
# ---------------------------------------------------------------- descriptive: BLOOM_AMBIGUOUS and floors
P("\n## DESCRIPTIVE: adaptive NIR floor and BLOOM_AMBIGUOUS (not gate evidence)\n")
def floors(diags): return np.array([d["floor"] for d in diags])
def row(name, diags):
    fl = floors(diags); amb = np.mean([d["ambiguous"] for d in diags]) if diags else float("nan"); tails = np.array([d["tail"] for d in diags if d["tail"] is not None])
    return (f"| {name} | {len(diags)} | {np.mean(fl <= 0.0301):.3f} | {np.quantile(fl, .5):.4f} | {np.quantile(fl, .9):.4f} | {np.quantile(fl, .99):.4f} | {fl.max():.4f} | {len(tails)} | {amb:.3f} |", dict(n=len(diags), at_min=float(np.mean(fl <= 0.0301)), p50=float(np.quantile(fl, .5)), p90=float(np.quantile(fl, .9)), p99=float(np.quantile(fl, .99)), max=float(fl.max()), amb=float(amb)))
P("| set | scenes | share floor = 0.03 (tail <= 0.03 or too few open-water px) | median floor | p90 | p99 | max | scenes with tail computed | BLOOM_AMBIGUOUS share |"); P("|" + "---|" * 9)
D = {}
alln = [d for r in NL if r["tag"] == "p2017" and "runs" in r for d in r["runs"][KEY]["scene_diag"]]
for name, dg in (("NLA 2017 in-window scenes (47 lakes)", alln),
                 ("NLA secondary 2018/19 scenes", [d for r in NL if r["tag"] != "p2017" and "runs" in r for d in r["runs"][KEY]["scene_diag"]]),
                 ("Snohomish (5)", [d for k, v in SN.items() for d in v["runs"][KEY]["scene_diag"]]),
                 ("FWC (7)", [d for n in FW for d in SF[f"fwc|{n}"]["runs"][KEY]["scene_diag"]])):
    s, dd = row(name, dg); P(s); D[name] = dd
try:
    S = pickle.load(open(OUT2 / "desc_seasonal.pkl", "rb"))
    for lk in ("Lake_Hartwell_SC", "Leech_Lake_MN", "Guntersville_AL"):
        s, dd = row(f"seasonal cache {lk} (all cached scenes)", [d for d in S if d["lake"] == lk]); P(s); D[lk] = dd
    P("\nBLOOM_AMBIGUOUS share by month, seasonal caches (scenes; ambiguous):\n"); P("| lake | " + " | ".join(f"{m:02d}" for m in range(1, 13)) + " |"); P("|" + "---|" * 13)
    for lk in ("Lake_Hartwell_SC", "Leech_Lake_MN", "Guntersville_AL"):
        cells = []
        for mth in range(1, 13):
            dd = [d for d in S if d["lake"] == lk and int(d["when"][5:7]) == mth]
            cells.append(f"{sum(d['ambiguous'] for d in dd)}/{len(dd)}" if dd else "-")
        P(f"| {lk} | " + " | ".join(cells) + " |")
    P("\nMonthly median adaptive floor, seasonal caches:\n"); P("| lake | " + " | ".join(f"{m:02d}" for m in range(1, 13)) + " |"); P("|" + "---|" * 13)
    for lk in ("Lake_Hartwell_SC", "Leech_Lake_MN", "Guntersville_AL"):
        cells = []
        for mth in range(1, 13):
            dd = [d["floor"] for d in S if d["lake"] == lk and int(d["when"][5:7]) == mth]
            cells.append(f"{np.median(dd):.3f}" if dd else "-")
        P(f"| {lk} | " + " | ".join(cells) + " |")
    # snow scenes
    lkS = [d for d in S if d["lake"] == "Leech_Lake_MN"]
    P(f"\nLeech scenes with any SCL snow/ice in lake: {sum(d['n_snow'] > 0 for d in lkS)}/{len(lkS)}; of those BLOOM_AMBIGUOUS {sum(d['ambiguous'] for d in lkS if d['n_snow'] > 0)}")
except FileNotFoundError: P("(seasonal descriptive not yet run)")
P("\n### BLOOM_AMBIGUOUS share by NLA lake (2017 in-window scenes; all 47 lakes; DEV/TEST noted)\n")
P("| lake | split | cls | scenes | ambiguous | share | median floor | max floor | median tail |"); P("|---|---|---|---|---|---|---|---|---|")
bl = []
for r in sorted([r for r in NL if r["tag"] == "p2017" and "runs" in r], key=lambda r: r["lakeKey"]):
    dg = r["runs"][KEY]["scene_diag"]; fl = [d["floor"] for d in dg]; tl = [d["tail"] for d in dg if d["tail"] is not None]
    a = sum(d["ambiguous"] for d in dg); bl.append((r["lakeKey"], len(dg), a))
    if a > 0 or max(fl) > 0.031:
        P(f"| {r['lakeKey']} | {split.loc[r['lakeKey'], 'split']} | {cls.loc[r['lakeKey'], 'cls']} | {len(dg)} | {a} | {a / len(dg):.2f} | {np.median(fl):.3f} | {max(fl):.3f} | {(f'{np.median(tl):.4f}' if tl else 'n/a')} |")
P(f"\nLakes with at least one BLOOM_AMBIGUOUS scene: {sum(1 for _, n, a in bl if a > 0)} of {len(bl)}; scenes ambiguous {sum(a for _, n, a in bl)} of {sum(n for _, n, a in bl)}. Lakes with floor > 0.03 in some scene listed above; all others sit at the 0.03 minimum.")

P("\n### Is BLOOM_AMBIGUOUS a bloom detector or a haze/cloud/smoke detector? Ambiguity share by lake cloud fraction (SCL 3/8/9/10 share of lake pixels), descriptive\n")
P("| set | scenes | cloud <=1 % : n, ambiguous | 1-5 % : n, ambiguous | >5 % : n, ambiguous | snow-free & cloud <=1 % : n, ambiguous |"); P("|---|---|---|---|---|---|")
def cb(name, dd):
    def f_(lo, hi, extra=lambda d: True):
        x = [d for d in dd if lo < d["cloud_frac"] <= hi and extra(d)]; return f"{len(x)}, {sum(d['ambiguous'] for d in x)} ({(sum(d['ambiguous'] for d in x) / len(x)) if x else float('nan'):.2f})"
    P(f"| {name} | {len(dd)} | {f_(-1, 0.01)} | {f_(0.01, 0.05)} | {f_(0.05, 9)} | {f_(-1, 0.01, lambda d: d.get('n_snow', 0) == 0)} |")
try:
    cb("NLA 2017 in-window (47 lakes)", pickle.load(open(OUT2 / "desc_nla_cloud.pkl", "rb")))
    S2 = pickle.load(open(OUT2 / "desc_seasonal.pkl", "rb"))
    for lk in ("Lake_Hartwell_SC", "Leech_Lake_MN", "Guntersville_AL"): cb(lk, [d for d in S2 if d["lake"] == lk])
except Exception as e: P(f"(cloud table failed: {e!r})")
M["bloom_by_lake"] = bl; M["floors"] = D
json.dump(M, open(OUT2 / "metrics_v02.json", "w"), indent=1, default=lambda o: float(o) if isinstance(o, (np.floating, np.integer)) else (list(o) if isinstance(o, tuple) else str(o)))
open(OUT2 / "tables_v02.md", "w").write("\n".join(L) + "\n")
print("\n".join(L))
