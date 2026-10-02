"""Markdown tables for the Stage 11 report, generated from the analysis JSON files."""
import json, os
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/stage11"
L = lambda p: json.load(open(p)) if os.path.exists(p) else None
A, DE, TS = L(f"{S}/analysis/part_a.json"), L(f"{S}/analysis/part_de.json"), L(f"{S}/tandem/tandem_summary.json")
BA, BR, FG = L(f"{S}/analysis/part_b_aeronet.json"), L(f"{S}/analysis/part_b_repr.json"), L(f"{S}/analysis/part_fg.json")
T = {}
f3 = lambda v: "–" if v is None else f"{v:+.3f}"
p1 = lambda v: "–" if v is None else f"{100 * v:.0f}%"
# ---------- A
if A:
    s = A["split_dt0"]; s1 = A["split_dt_le1"]
    T["a_split"] = ("| | Same-day satellite pass (primary) | Satellite ±1 day |\n|---|---:|---:|\n"
        f"| Rows / lakes | {s['n']} / {s['lakes']} | {s1['n']} / {s1['lakes']} |\n"
        f"| Var(e_S), log10² | {s['var_eS']:.3f} | {s1['var_eS']:.3f} |\n"
        f"| Radiometric share of Var(e_S) | **{p1(s['share_radiometric'])}** (lake-bootstrap 95% CI {p1(A['share_ci_dt0'][0])}–{p1(A['share_ci_dt0'][1])}) | {p1(s1['share_radiometric'])} |\n"
        f"| Conversion share of Var(e_S) | **{p1(s['share_conversion'])}** | {p1(s1['share_conversion'])} |\n"
        f"| Median \\|e_S\\| (champion) | {s['median_abs_eS']:.3f} (×{10 ** s['median_abs_eS']:.2f}) | {s1['median_abs_eS']:.3f} |\n"
        f"| … if satellite turbidity were perfect (conversion only) | {s['median_abs_if_perfect_turbidity']:.3f} (×{10 ** s['median_abs_if_perfect_turbidity']:.2f}) | {s1['median_abs_if_perfect_turbidity']:.3f} |\n"
        f"| … if the conversion were perfect (radiometry only) | {s['median_abs_if_perfect_conversion']:.3f} (×{10 ** s['median_abs_if_perfect_conversion']:.2f}) | {s1['median_abs_if_perfect_conversion']:.3f} |\n"
        f"| Median \\|e_T\\| (satellite FNU vs in-situ turbidity) | {s['median_abs_eT']:.3f} (×{10 ** s['median_abs_eT']:.2f}) | {s1['median_abs_eT']:.3f} |")
    cl = [("clear >=6", "Clear ≥ 6 ft"), ("normal 3-6", "Normal 3–6 ft"), ("stained 2-3", "Stained 2–3 ft"), ("limited <2", "Limited < 2 ft")]
    T["a_class"] = "| Secchi class | Rows (lakes) | Median e_T | Radiometric term (−0.637·e_T) | Conversion term e_C | Champion e_S |\n|---|---:|---:|---:|---:|---:|\n" + "\n".join(
        f"| {lab} | {A['by_secchi_class_dt0'][k]['n']} ({A['by_secchi_class_dt0'][k]['lakes']}) | {f3(A['by_secchi_class_dt0'][k]['median_eT'])} (×{10 ** A['by_secchi_class_dt0'][k]['median_eT']:.2f}) | {f3(-0.637 * A['by_secchi_class_dt0'][k]['median_eT'])} | {f3(A['by_secchi_class_dt0'][k]['median_eC'])} | {f3(A['by_secchi_class_dt0'][k]['median_eS'])} |" for k, lab in cl)
    T["a_attr"] = "| Source (block) | Share of Var(e_S) |\n|---|---:|\n" + "\n".join(f"| {k} | {p1(v)} |" for k, v in A["attribution_share_of_var_eS"].items())
    sh = A["shapley_eT_dt0"]; sc = A["shapley_eC_dt0"]
    T["a_shap"] = "| Block (satellite-observable) | Explains of e_T (held-out R²) | Explains of e_C (held-out R²) |\n|---|---:|---:|\n" + "\n".join(
        f"| {b} | {sh[b]:+.3f} | {sc[b]:+.3f} |" for b in ("AC/aerosol", "glint", "adjacency", "platform", "water type")) + f"\n| **All blocks together** | **{sh['_total_cv_R2']:+.3f}** | **{sc['_total_cv_R2']:+.3f}** |"
    bc = A["best_conversion"]
    T["a_conv"] = ("| Conversion (in-situ inputs) | Rows | Median \\|log error\\| (held-out lakes) | Champion formula, same rows |\n|---|---:|---:|---:|\n"
        f"| Refit on in-situ turbidity | {bc['turbidity_only']['n']} | {bc['turbidity_only']['median_abs_log']:.3f} | {bc['turbidity_only']['champion_formula_on_same_rows']:.3f} |\n"
        f"| Refit on in-situ turbidity + chlorophyll | {bc['turbidity_and_chl']['n']} | {bc['turbidity_and_chl']['median_abs_log']:.3f} | {bc['turbidity_and_chl']['champion_formula_on_same_rows']:.3f} |")
    def grp_table(key, lab):
        g = A[key]
        return f"| {lab} | Rows (lakes) | Median e_T | Median \\|e_T\\| | Median e_C | Median \\|e_S\\| |\n|---|---:|---:|---:|---:|---:|\n" + "\n".join(
            f"| {k} | {v['n']} ({v['lakes']}) | {f3(v['median_eT'])} | {v['median_abs_eT']:.3f} | {f3(v['median_eC'])} | {v['median_abs_eS']:.3f} |" for k, v in g.items())
    T["a_owt"] = grp_table("by_owt_dt0", "Satellite water type"); T["a_ins"] = grp_table("by_insitu_type_dt0", "In-situ water type")
    T["a_adj"] = grp_table("by_adjacency_dt0", "Distance to nearest non-water pixel"); T["a_plat"] = grp_table("by_platform_dt0", "Platform")
# ---------- C
if TS:
    B = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B11", "B12"]
    def c(b, k, fmt="{:.3f}"):
        v = TS["bands"][b].get(k)
        return "–" if not v else (fmt.format(v["median"]) + f" ({fmt.format(v['ci95'][0])}–{fmt.format(v['ci95'][1])})")
    T["c_bands"] = "| Band | TOA water C/A | TOA land C/A | TOA water C − A | Production L2A water C/A | ACOLITE water C/A |\n|---|---:|---:|---:|---:|---:|\n" + "\n".join(
        f"| {b} | {c(b, 'TOA water ratio C/A')} | {c(b, 'TOA land ratio C/A')} | {c(b, 'TOA water diff C-A', '{:+.4f}')} | {c(b, 'BOA (production L2A) water ratio C/A')} | {c(b, 'ACOLITE water ratio C/A')} |" for b in B)
    ch = TS["chain"]
    cc = lambda k, fmt="{:.3f}": "–" if not ch.get(k) else fmt.format(ch[k]["median"]) + f" ({fmt.format(ch[k]['ci95'][0])}–{fmt.format(ch[k]['ci95'][1])})"
    T["c_chain"] = ("| Downstream, pixel by pixel over tandem water | S2A | S2C | Difference / flip |\n|---|---:|---:|---:|\n"
        f"| P2 sends the pixel to P1 | {cc('P2 to P1 share, S2A', '{:.1%}')} | {cc('P2 to P1 share, S2C', '{:.1%}')} | route flips: **{cc('route_flip', '{:.1%}')}** |\n"
        f"| P2 residual sensitivity S (limit 0.20) | {cc('residual S median, S2A')} | {cc('residual S median, S2C')} | |\n"
        f"| P1 answers | {cc('P1 answers, S2A', '{:.1%}')} | {cc('P1 answers, S2C', '{:.1%}')} | |\n"
        f"| Champion (production) Secchi, C − A | | | **{cc('champ_dft', '{:+.3f}')} ft** |\n"
        f"| C3, C − A | | | {cc('c3_dft', '{:+.3f}')} ft |\n| P1, C − A | | | {cc('p1_dft', '{:+.3f}')} ft |\n| P2, C − A | | | {cc('p2_dft', '{:+.3f}')} ft |")
    b11 = TS["b11"]
    T["c_b11"] = (f"| Production L2A B11 over water (20 m) | S2A {b11['production L2A median, S2A']['median']:.4f} | S2C {b11['production L2A median, S2C']['median']:.4f} |\n|---|---:|---:|\n"
                  f"| B11 local 3×3 standard deviation (noise) | {b11['local std 20 m, S2A']['median']:.4f} | {b11['local std 20 m, S2C']['median']:.4f} |")
    pp = TS["chain"]["per pair"]
    T["c_pairs"] = "| Water, tile | Pixels | P2 route flips | Champion Δft | C3 Δft | P2 → P1 share (A / C) |\n|---|---:|---:|---:|---:|---:|\n" + "\n".join(
        f"| {k} | {v['n']} | {v['p2_route_flip']:.0%} | {v['champ_dft_median']:+.2f} | {v['c3_dft_median']:+.2f} | {v['p2_paths']['A'].get('P1', 0) / v['n']:.0%} / {v['p2_paths']['C'].get('P1', 0) / v['n']:.0%} |" for k, v in pp.items())
# ---------- D / E
if DE:
    D = DE["D"]; labs = ["clear", "algal", "sediment", "mixed"]
    T["d_conf"] = "| In-situ ↓ / satellite → | clear | algal | sediment | mixed | unsupported | Recall |\n|---|---:|---:|---:|---:|---:|---:|\n" + "\n".join(
        f"| **{a}** | " + " | ".join(str(D['confusion (rows = in-situ, cols = satellite)'][a][b]) for b in labs + ["unsupported"]) + f" | {D['recall'][a]:.2f} |" for a in labs) + \
        "\n| **Precision** | " + " | ".join(f"{D['precision'][b]:.2f}" for b in labs) + " | | |"
    st = ["clear", "algal", "sediment", "mixed", "unsupported"]; mods = ["champion", "P1", "P1-NIR", "C3", "C6"]
    def cell(v):
        if v.get("note"): return f"n {v['n']} (too few)"
        return f"{v['median_abs_log']:.3f} / {v['median_signed_ft']:+.2f} ft / {v['class_acc']:.2f}" + (f" ({v['coverage']:.0%} answered)" if v.get("coverage", 1) < 0.999 else "")
    T["e_state"] = "| Satellite water type (rows) | " + " | ".join(mods) + " |\n|---|" + "---|" * len(mods) + "\n" + "\n".join(
        f"| {s} ({DE['E_state_counts'].get(s, 0)}) | " + " | ".join(cell(DE["E_by_state"][s][m]) for m in mods) + " |" for s in st) + \
        "\n| **All** | " + " | ".join(cell(DE["E_all"][m]) for m in mods) + " |"
    ch = DE["E_routing_choices_by_fold"]
    T["e_route"] = "| Fold | clear | algal | sediment | mixed | unsupported |\n|---|---|---|---|---|---|\n" + "\n".join(
        f"| {k} | " + " | ".join(str(ch[k].get(s) or "refuse") for s in st) + " |" for k in sorted(ch))
    r = DE["E_routed"]; rv = DE["E_routed_vs_best_single_same_rows"]
    T["e_routed"] = ("| | Routed (nested) | Best single model (" + DE["E_best_single"] + ") |\n|---|---:|---:|\n"
        f"| Median \\|log error\\|, same rows | {rv['routed']:.3f} | {rv['best_single']:.3f} |\n"
        f"| Difference (lake-bootstrap 95% CI) | {rv['routed'] - rv['best_single']:+.3f} ({rv['diff_ci'][0]:+.3f} to {rv['diff_ci'][1]:+.3f}) | |\n"
        f"| Relative improvement | {(rv['best_single'] - rv['routed']) / rv['best_single']:.1%} (bar: ≥ 10%) | |\n"
        f"| Coverage (answered) | {DE['E_routed_coverage']:.0%} (bar: ≥ 70%) | 100% |\n"
        f"| Median signed error; class accuracy | {r['median_signed_ft']:+.2f} ft; {r['class_acc']:.2f} | {DE['E_all'][DE['E_best_single']]['median_signed_ft']:+.2f} ft; {DE['E_all'][DE['E_best_single']]['class_acc']:.2f} |")
# ---------- B
if BA:
    s = BA["summary"]; P = s["processors"]
    procs = ["Sen2Cor (production)", "ACOLITE (own mask)", "ACOLITE (water/cloud mask)", "C2RCC-Nets", "C2X-Nets"]
    bnd = lambda p, b: ("–" if P[p]["bands"][b]["median_abs_log"] is None else f"{P[p]['bands'][b]['median_abs_log']:.2f} ({P[p]['bands'][b]['median_log_bias']:+.2f}), n {P[p]['bands'][b]['n']}")
    T["b_aeronet"] = "| Processor | Valid | B02 | B03 | B04 | B05 | B02–B05 median \\|log\\| |\n|---|---:|---|---|---|---|---:|\n" + "\n".join(
        f"| {p} | {P[p]['valid_rate']:.0%} | " + " | ".join(bnd(p, b) for b in ("B02", "B03", "B04", "B05")) + f" | **{P[p]['B02-B05 median_abs_log']:.3f}** |" if P[p]['B02-B05 median_abs_log'] is not None else f"| {p} | {P[p]['valid_rate']:.0%} | – | – | – | – | – |" for p in procs)
    SITE = {"Lake_Erie": "Lake Erie", "Lake_Okeechobee": "Okeechobee", "Palgrunden": "Vänern (Palgrunden)", "Chesapeake_Bay": "Chesapeake Bay", "WaveCIS_Site_CSI_6": "WaveCIS (shelf)"}
    T["b_sites"] = "| Processor | " + " | ".join(SITE.get(k, k) for k in s["by_site"]) + " |\n|---|" + "---:|" * len(s["by_site"]) + "\n" + "\n".join(
        f"| {p} | " + " | ".join(("–" if P[p]['by_site'][k] != P[p]['by_site'][k] else f"{P[p]['by_site'][k]:.2f}") for k in s["by_site"]) + " |" for p in procs)
    pv = s["paired_vs_sen2cor"]
    T["b_paired"] = "| Processor vs Sen2Cor (same matchup-bands) | Pairs (matchups) | Processor | Sen2Cor | Relative improvement | Difference 95% CI |\n|---|---:|---:|---:|---:|---|\n" + "\n".join(
        f"| {p} | {v['n_pairs']} ({v['matchups']}) | {v['proc_median_abs_log']:.3f} | {v['sen2cor_median_abs_log']:.3f} | {v['relative_improvement']:+.0%} | {v['diff_ci95'][0]:+.3f} to {v['diff_ci95'][1]:+.3f} |" for p, v in pv.items() if v)
    if s.get("plausibility"):
        b11 = lambda v: "not reported" if v["median_B11"] is None else f"{v['median_B11']:.4f}"
        T["b_plaus"] = "| Processor | ρw values (B02–B05) | Share ≤ 0 | Median ρw(B11) |\n|---|---:|---:|---:|\n" + "\n".join(
            f"| {p} | {v['values']} | {v['share_non_positive']:.1%} | {b11(v)} |" for p, v in s["plausibility"].items())
if BR:
    P = BR["summary"]["processors"]
    T["b_repr"] = "| Processor | Stations valid | Median \\|e_T\\| (FNU vs in-situ turbidity) | Median e_T | Champion formula median \\|log\\| | P1 answers | P1 median \\|log\\| |\n|---|---:|---:|---:|---:|---:|---:|\n" + "\n".join(
        f"| {p} | {v['valid']} | {v['median_abs_eT'] if v['median_abs_eT'] is not None else '–'} | {v['median_eT'] if v['median_eT'] is not None else '–'} | {v['champion_formula median_abs_log'] if v['champion_formula median_abs_log'] is not None else '–'} | {v['P1 answers']} | {v['P1 median_abs_log'] if v['P1 median_abs_log'] is not None else '–'} |" for p, v in P.items())
    pw = BR["summary"].get("pairwise_vs_sen2cor") or {}
    T["b_repr_pair"] = "| Processor vs Sen2Cor (stations both answer) | Stations | Processor median \\|e_T\\| | Sen2Cor median \\|e_T\\| | Stations where the processor is closer |\n|---|---:|---:|---:|---:|\n" + "\n".join(
        f"| {p} | {v['n']} | {v['processor_median_abs_eT']} | {v['sen2cor_median_abs_eT']} | {v['processor_better_count']} of {v['n']} |" for p, v in pw.items() if v["n"])
# ---------- F / G
if FG:
    F = FG.get("F_landsat", {}); O = FG.get("F_olci", {}); G = FG.get("G", {})
    T["f_landsat"] = ("| Landsat 8/9 (±1 day) | Value |\n|---|---|\n" + f"| Rows with a valid read (lakes) | {F.get('rows_with_read')} ({F.get('lakes')}) |\n" +
        (f"| S2 vs Landsat FNU, median log ratio (median \\|log\\|) | {F['S2_vs_Landsat_log_ratio']['median']:+.3f} ({F['S2_vs_Landsat_log_ratio']['median_abs']:.3f}); rank correlation {F['S2_vs_Landsat_log_ratio']['spearman']:.2f} |\n" if F.get("S2_vs_Landsat_log_ratio") else "") +
        (f"| Sensors agree (\\|log ratio\\| ≤ 0.15): median \\|e_S\\| | {F['agree']['median_abs_eS']} (n {F['agree']['n']}) |\n| Sensors disagree: median \\|e_S\\| | {F['disagree']['median_abs_eS']} (n {F['disagree']['n']}) |\n" if F.get("agree") else "") +
        (f"| Agree − disagree, 95% CI | {F.get('agree_minus_disagree_ci')} (relative reduction {F.get('agree_relative_reduction')}) |\n" if F.get("agree_minus_disagree_ci") else "") +
        (f"| S2 alone / Landsat alone / fused: median \\|e_S\\| | {F['S2 alone median_abs_eS']} / {F['Landsat alone median_abs_eS']} / {F['fused median_abs_eS']} (fused − S2 CI {F['fused_minus_S2_ci']}) |\n" if F.get("fused median_abs_eS") is not None else "") +
        (f"| Against in-situ turbidity: S2 / Landsat / fused median \\|e_T\\| | {F['eT']['S2 median_abs_eT']} / {F['eT']['Landsat median_abs_eT']} / {F['eT']['fused median_abs_eT']} (n {F['eT']['n']}) |\n" if F.get("eT") else ""))
    T["f_olci"] = ("| Sentinel-3 OLCI WFR (stations ≥ 600 m from shore, ±1 day) | Value |\n|---|---|\n" + f"| Rows attempted / with a valid read (lakes) | {O.get('rows_attempted')} / {O.get('rows_with_read')} ({O.get('lakes')}) |\n" +
        (f"| TSM_NN vs S2 FNU: median log ratio (p10–p90) | {O['TSM_vs_S2_FNU_log_ratio']['median']:+.3f} ({O['TSM_vs_S2_FNU_log_ratio']['spread_p10_p90'][0]:+.2f} to {O['TSM_vs_S2_FNU_log_ratio']['spread_p10_p90'][1]:+.2f}) |\n" if O.get("TSM_vs_S2_FNU_log_ratio") else "") +
        (f"| Agree / disagree: median \\|e_S\\| | {O['agree (after median TSM/FNU offset)']['median_abs_eS']} (n {O['agree (after median TSM/FNU offset)']['n']}) / {O['disagree']['median_abs_eS']} (n {O['disagree']['n']}) |\n" if O.get("disagree") else "") +
        (f"| Rank correlation with in-situ turbidity: OLCI TSM / S2 FNU | {O['TSM_vs_insitu_turbidity']['spearman_rank']} / {O['TSM_vs_insitu_turbidity']['S2 FNU spearman_rank']} (n {O['TSM_vs_insitu_turbidity']['n']}) |\n" if O.get("TSM_vs_insitu_turbidity") else ""))
    T["g"] = ("| Temporal consistency (passes within ±10 days) | Value |\n|---|---|\n" + f"| Rows with ≥ 2 other passes | {G.get('rows_with_neighbors')} |\n| Flagged as radiometric outliers | {G.get('flagged')} ({G.get('flag_rate')}) |\n" +
        (f"| Median \\|e_S\\|: flagged / unflagged | {G['flagged median_abs_eS']} / {G['unflagged median_abs_eS']} (ratio {G['ratio']}) |\n| Flagged, after replacing with the neighbours' median | {G['flagged after replacement median_abs_eS']} ({-G['replacement_reduction']:+.0%}) |\n" if G.get("flagged median_abs_eS") is not None else "") +
        (f"| Exploratory: refusing flagged passes instead (all rows) | {G['exploratory_refuse']['all rows median_abs_eS']} → {G['exploratory_refuse']['after refusing flagged']} ({-G['exploratory_refuse']['relative_reduction']:+.0%}), keeping {G['exploratory_refuse']['coverage_kept']:.0%} of rows |\n" if G.get("exploratory_refuse") else ""))
json.dump(T, open(f"{S}/analysis/tables.json", "w"), indent=1)
print({k: len(v) for k, v in T.items()})
