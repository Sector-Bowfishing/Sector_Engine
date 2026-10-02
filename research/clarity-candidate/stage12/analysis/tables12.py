"""Stage 12 report tables (markdown) from the result JSONs; each section only if its file exists. Writes tables12.json."""
import json, os, math
D = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/stage12"
J = lambda p: json.load(open(f"{D}/{p}")) if os.path.exists(f"{D}/{p}") else None
T = {}
f3 = lambda v: "–" if v is None else f"{v:.3f}"
sg = lambda v: "–" if v is None else f"{v:+.3f}"
pct = lambda v: "–" if v is None else f"{v:.0%}"
# ---------------- Part 1
E = J("exp1/score.json")
if E:
    SET = {"K0": "Stage 11 (no interface term)", "K1": "interface: default (RSKY LUT, wind 2 m/s)", "K2": "interface: 6SV rough surface",
           "K3": "interface: FFSS at TOA", "K4": "interface: FFSS after AC (BOA)"}
    rows = []
    for k in ("K0", "K1", "K2", "K3", "K4"):
        a = E["aeronet"][k]; b = a["bands"]
        cells = [f"{f3(b[x]['median_abs_log'])} ({sg(b[x]['median_bias'])})" for x in ("B02", "B03", "B04", "B05")]
        el = E["eligibility"].get(k)
        why = "baseline" if k == "K0" else ("**eligible**" if el["eligible"] else "not feasible: all-NaN output" if not el["feasible"] else "not eligible: " + ", ".join(
            {"feasible": "fails to run", "1_B04_better_CI": "red not better", "2_no_degradation": "degrades a band", "3_valid_rate": "valid rate",
             "4_nonpositive": "negative ρw", "5_guard": "inland turbidity"}[c] for c, v in el.items() if c != "eligible" and not v))
        rows.append(f"| {k} | {SET[k]} | {pct(a['valid_rate'])} | " + " | ".join(cells) + f" | **{f3(a['pooled_median_abs_log'])}** | {f3(E['guard'][k]['median_abs_eT'])} | {why} |")
    T["p1"] = ("| | Setting | Valid | B02 | B03 | B04 | B05 | B02–B05 | Guard \\|e_T\\| | Verdict |\n|---|---|---:|---|---|---|---|---:|---:|---|\n" + "\n".join(rows))
    pr = []
    for k in ("K1", "K2", "K4"):
        a, b = E["paired_B04_vs_K0"][k], E["paired_pooled_vs_K0"][k]
        pr.append(f"| {k} | {a['n']} | {a['cand']:.3f} vs {a['K0']:.3f} | {a['diff']:+.3f} ({a['ci95'][0]:+.3f} to {a['ci95'][1]:+.3f}) | {b['cand']:.3f} vs {b['K0']:.3f} | {b['diff']:+.3f} ({b['ci95'][0]:+.3f} to {b['ci95'][1]:+.3f}) |")
    T["p1_paired"] = "| Candidate vs K0 | Matchups | Red (B04) | Red difference (95% CI) | B02–B05 | B02–B05 difference (95% CI) |\n|---|---:|---|---|---|---|\n" + "\n".join(pr)
# ---------------- Part 2
V = J("harm/validate_npz.json"); A = J("harm/score_tandem.json"); H = J("harm/harm_prod.json")
if H:
    rows = []
    for b in ("B02", "B04", "B05", "B08", "B8A", "B11", "B12"):
        t, o = H["coef"]["toa"][b], H["coef"]["boa"][b]
        k = lambda c: f"; k {c['k']:+.3f}" if "k" in c else ""
        rows.append(f"| {b} | {t['g']:.3f}, {t['o']:+.4f}{k(t)} | {'yes' if b in H['operational_toa_bands'] else 'no'} | {o['g']:.3f}, {o['o']:+.4f}{k(o)} |")
    T["p2_coef"] = "| Band | TOA: gain, offset (ACOLITE path) | Applied to operational TOA | BOA: gain, offset (Sen2Cor path) |\n|---|---|---|---|\n" + "\n".join(rows)
if V and A:
    names = {"13QFC": "Chapala (13QFC)", "13QGC": "Chapala (13QGC)", "15RYP": "Pontchartrain (15RYP)", "16RBU": "Pontchartrain (16RBU)", "16RCU": "Mobile Bay (16RCU)",
             "16RDU": "Mobile Bay (16RDU)", "17RLL": "Tampa Bay (17RLL)", "30NZP": "Volta (30NZP)", "35KNB": "Kariba (35KNB)", "35KPB": "Kariba (35KPB)",
             "36QUJ": "Nasser (36QUJ)", "38SLH": "Van (38SLH)"}
    rows = []
    for p in sorted(V["pairs"]):
        v = V["pairs"][p]; a = A["pairs"].get(p, {}).get("flip", {})
        rows.append(f"| {names.get(p[:5], p)} | {pct(v['p2_flip_raw'])} → {pct(v['p2_flip_harmonised'])} | " + " | ".join(pct(a.get(t)) for t in ("raw", "vfull", "vop", "vrhow")) + " |")
    rows.append(f"| **Mean over pairs** | **{pct(V['p2_flip_mean_raw'])} → {pct(V['p2_flip_mean_harmonised'])}** | " + " | ".join(f"**{pct(A['mean_flip_' + t])}**" for t in ("raw", "vfull", "vop", "vrhow")) + " |")
    T["p2_flips"] = ("| Tandem pair (held out) | Sen2Cor path: raw → harmonised | ACOLITE raw | ACOLITE V-full | ACOLITE V-op | ACOLITE V-ρw |\n|---|---|---:|---:|---:|---:|\n" + "\n".join(rows))
    rows = []
    for b in ("B02", "B04", "B05", "B8A", "B11", "B12"):
        s0, s1 = V["residual"]["boa_raw"].get(b), V["residual"]["boa_h"].get(b)
        a0, a1 = A["resid_raw"].get(b), A["resid_vrhow"].get(b)
        c = lambda r: "–" if r is None else f"{r['ratio_median_over_pairs'] if 'ratio_median_over_pairs' in r else r['ratio']:.3f} ({(r['diff_median_over_pairs'] if 'diff_median_over_pairs' in r else r['diff']):+.4f})"
        rows.append(f"| {b} | {c(s0)} | {c(s1)} | {c(a0)} | {c(a1)} |")
    T["p2_resid"] = ("| Band | Sen2Cor raw C/A (C − A) | Sen2Cor harmonised | ACOLITE raw | ACOLITE V-ρw |\n|---|---|---|---|---|\n" + "\n".join(rows))
json.dump(T, open(f"{D}/analysis/tables12.json", "w"), indent=1)
print({k: len(v) for k, v in T.items()})
# ---------------- Part 3
Rf = J("analysis/reflectance.json")
if Rf:
    r1 = Rf["R1"]
    T["p3_r1"] = ("| | ACOLITE valid 60 m disk | Sen2Cor production |\n|---|---:|---:|\n" + f"| All corpus rows (not Guntersville, {r1['rows_processed']:,}) | **{r1['aco_valid_rate']:.0%}** | 100% (by construction) |\n" +
                  "\n".join(f"| {c.capitalize()} | {v:.0%} | 100% |" for c, v in r1["by_class"].items()))
    def rr(lab, d):
        ci = d.get("diff_ci"); return f"| {lab} | {d['n']} ({d['lakes']}) | {d['aco_median_abs_eT']:.3f} ({d['aco_median_eT']:+.3f}) | {d['s2c_median_abs_eT']:.3f} ({d['s2c_median_eT']:+.3f}) | {d['diff']:+.3f}" + (f" ({ci[0]:+.3f} to {ci[1]:+.3f})" if ci else "") + " |"
    R2 = Rf["R2"]; rows = [rr("**All, same-day pass**", R2["same_day"]), rr("All, pass within ±1 day", R2["within_1_day"])]
    rows += [rr(f"Secchi class: {c}", v) for c, v in R2["by_class_same_day"].items()] + [rr(f"In-situ type: {t}", v) for t, v in R2["by_insitu_type_same_day"].items()]
    T["p3_r2"] = "| Rows | n (lakes) | ACOLITE median \\|e_T\\| (bias) | Sen2Cor median \\|e_T\\| (bias) | ACOLITE − Sen2Cor (95% CI) |\n|---|---:|---|---|---|\n" + "\n".join(rows)
    a, b = Rf["R3"]["acolite"], Rf["R3"]["sen2cor"]
    T["p3_r3"] = ("| Same-day rows with turbidity | ACOLITE FNU | Sen2Cor FNU |\n|---|---:|---:|\n" + f"| Radiometric share of Var(e_S) | {a['share_radiometric']:.0%} | {b['share_radiometric']:.0%} |\n"
                  f"| Conversion share | {a['share_conversion']:.0%} | {b['share_conversion']:.0%} |\n| Frozen champion median \\|e_S\\| | {a['median_abs_eS']:.3f} | {b['median_abs_eS']:.3f} |")
    R4 = Rf["R4"]
    T["p3_r4"] = ("| Platform (turbidity rows ±1 day) | n | ACOLITE median e_T | Sen2Cor median e_T |\n|---|---:|---:|---:|\n" +
                  "\n".join(f"| {p} | {v['n']} | {v['aco_median_eT']:+.3f} | {v['s2c_median_eT']:+.3f} |" for p, v in R4.items() if p.startswith("sentinel")))
# ---------------- Part 4
Mo = J("analysis/models12.json")
if Mo:
    fx = lambda v: f"×{10 ** v:.2f}"
    NAMES = {"champion": "1 champion, frozen", "P1": "2 P1, frozen", "champion_refit": "3 champion form, refitted", "N1": "4 N1 (red)", "N2": "5 N2 (red + green/red)",
             "C3": "6 C3 form, refitted", "C6": "7 C6 form, refitted", "P2": "8 P2, frozen"}
    rows = []
    for m, lab in NAMES.items():
        v = Mo["all"][m]; el = m in Mo["eligible"]
        rows.append(f"| {lab} | {v['coverage']:.0%} | {'**' if m == Mo['final_engine'] else ''}{v['median_abs_log']:.3f} ({fx(v['median_abs_log'])}){'**' if m == Mo['final_engine'] else ''} | {v['median_signed_ft']:+.2f} | {v['class_acc']:.2f} | {'yes' if el else 'no (coverage)'} |")
    rt = Mo["routed"]; rows.append(f"| 9 routed (nested) | {rt['coverage']:.0%} | {rt['median_abs_log']:.3f} ({fx(rt['median_abs_log'])}) | {rt['median_signed_ft']:+.2f} | {rt['class_acc']:.2f} | router |")
    p = Mo["production_sen2cor_champion_same_rows"]
    rows.append(f"| *Production today: champion on Sen2Cor, same rows* | {p['coverage']:.0%} | *{p['median_abs_log']:.3f} ({fx(p['median_abs_log'])})* | *{p['median_signed_ft']:+.2f}* | *{p['class_acc']:.2f}* | reference |")
    T["p4_models"] = f"| Candidate (on ACOLITE ρw) | Coverage | Median \\|log\\| (factor) | Median signed ft | Class accuracy | Eligible |\n|---|---:|---|---:|---:|---|\n" + "\n".join(rows)
    T["p4_equiv"] = "| Simpler than the best (C3) | Difference in median \\|log\\| | 95% CI | Equivalent (upper ≤ +0.010) |\n|---|---:|---|---|\n" + "\n".join(
        f"| {NAMES[m]} | {v['diff']:+.4f} | {v['ci95'][0]:+.4f} to {v['ci95'][1]:+.4f} | {'yes' if v['equivalent'] else 'no'} |" for m, v in Mo["equivalence_vs_best"].items())
    rtst = Mo["routing_test"]
    T["p4_routing"] = (f"| | Routed | Engine (C3) |\n|---|---:|---:|\n| Median \\|log\\|, same rows | {rtst['routed_same_rows']:.4f} | {rtst['engine_same_rows']:.4f} |\n"
                       f"| Relative gain | {rtst['relative_gain']:+.1%} (bar ≥ 10%) | |\n| Difference 95% CI | {rtst['diff_ci95'][0]:+.4f} to {rtst['diff_ci95'][1]:+.4f} | |\n| Coverage | {rtst['coverage']:.0%} | 100% |")
    LAB = {"clear": "Clear ≥ 6 ft", "normal": "Normal 3–6 ft", "stained": "Stained 2–3 ft", "limited": "Limited < 2 ft", "algal": "In-situ algal", "sediment": "In-situ sediment", "mixed": "In-situ mixed"}
    rows = []
    for g in ("clear", "normal", "stained", "limited", "algal", "sediment", "mixed"):
        e, q = Mo["per_class"][g]["engine"], Mo["per_class"][g]["production"]
        rows.append(f"| {LAB[g]} | {e['n']} ({e['lakes']}) | **{fx(e['median_abs_log'])}** ({e['median_abs_log']:.3f}); {e['median_signed_ft']:+.1f} ft; {e['class_acc']:.2f} | {fx(q['median_abs_log'])} ({q['median_abs_log']:.3f}); {q['median_signed_ft']:+.1f} ft; {q['class_acc']:.2f} |")
    g = Mo["guntersville"]
    rows.append(f"| *Guntersville (reported apart; no selection)* | {g['engine']['n']} ({g['engine']['lakes']}) | {fx(g['engine']['median_abs_log'])} ({g['engine']['median_abs_log']:.3f}); {g['engine']['median_signed_ft']:+.1f} ft | {fx(g['production']['median_abs_log'])} ({g['production']['median_abs_log']:.3f}); {g['production']['median_signed_ft']:+.1f} ft |")
    T["p4_perclass"] = "| True class / type | Rows (lakes) | ACOLITE C3 engine: error; signed; class accuracy | Production today, same rows |\n|---|---:|---|---|\n" + "\n".join(rows)
    pl = Mo["platform"]
    T["p4_platform"] = "| Platform | Rows | Median signed log error minus the others' | 95% CI |\n|---|---:|---:|---|\n" + "\n".join(
        f"| {p} | {v['n']} | {v.get('diff', 0):+.3f} | {v['ci95'][0]:+.3f} to {v['ci95'][1]:+.3f} |" if v.get("ci95") else f"| {p} | {v['n']} | – | – |" for p, v in pl.items())
Te = J("harm/score_tandem_engine.json")
if Te:
    T["p2_engine"] = ("| Engine class decision on identical tandem water | Raw | V-full | V-op | **V-ρw (adopted)** |\n|---|---:|---:|---:|---:|\n" +
                      f"| Mean class-flip rate (10 pairs) | {Te['engine_mean_flip_raw']:.1%} | {Te['engine_mean_flip_vfull']:.1%} | {Te['engine_mean_flip_vop']:.1%} | **{Te['engine_mean_flip_vrhow']:.1%}** |\n" +
                      f"| Median \\|Δft\\| | {Te['engine_median_abs_dft_raw']:.2f} | {Te['engine_median_abs_dft_vfull']:.2f} | {Te['engine_median_abs_dft_vop']:.2f} | **{Te['engine_median_abs_dft_vrhow']:.2f}** |")
Ex = J("analysis/explore12.json")
if Ex:
    lab = {"A_production_all_rows": "Production today (champion on Sen2Cor), all rows", "B_C3_on_Sen2Cor_all_rows": "C3 on Sen2Cor, all rows",
           "C_C3_on_Sen2Cor_same_rows_as_ACOLITE": "C3 on Sen2Cor, the ACOLITE rows", "D_ACOLITE_C3_valid_rows_only": "**C3 on ACOLITE, the ACOLITE rows**",
           "E_ACOLITE_C3_all_rows (Unknown where no disk)": "C3 on ACOLITE, all rows (Unknown where no disk)"}
    rows = []
    for k, l in lab.items():
        v = Ex[k]; cr = v["class_recall_precision"]
        rows.append(f"| {l} | {v['rows']:,} | {v['unknown']:.0%} | {v['median_abs_log_all']:.3f} | {v['class_accuracy_answered']:.2f} | " + " | ".join(f"{cr[c][0]:.2f} / {cr[c][1]:.2f}" for c in ("clear", "normal", "stained", "limited")) + " |")
    T["p5_explore"] = ("| Input and rows (exploratory) | Rows | Unknown | Median \\|log\\| (answered) | Class accuracy (answered) | Clear recall / precision | Normal | Stained | Limited |\n|---|---:|---:|---:|---:|---|---|---|---|\n" + "\n".join(rows))
    a = Ex.get("attribution_same_rows")
    if a: T["p4_attrib"] = f"| Same {a['n']:,} rows, same folds | C3 on Sen2Cor | C3 on ACOLITE | Difference (95% CI) |\n|---|---:|---:|---|\n| Median \\|log\\| | {a['s2c_c3']:.3f} | **{a['aco_c3']:.3f}** | {a['diff']:+.3f} ({a['ci95'][0]:+.3f} to {a['ci95'][1]:+.3f}) |"
# ---------------- Part 5
Cl = J("analysis/classes12.json")
if Cl:
    sh = Cl["shares"]
    T["p5_shares"] = (f"| What a user would get | Share of corpus rows |\n|---|---:|\n| Exact feet (and the class) | {sh['feet_published']:.0%} |\n| Class only (feet withheld) | {sh['class_only_feet_withheld']:.0%} |\n| Unknown (no valid ACOLITE disk) | {sh['unknown']:.0%} |")
    rows = []
    for c in ("clear", "normal", "stained", "limited", "algae", "sediment", "bottom-risk"):
        f, k = Cl["exact_feet"][c], Cl["clarity_class"][c]
        fs = "–" if not f.get("n_published") else f"{f['n_published']} published ({f['coverage']:.0%}); ×{10 ** f['median_abs_log']:.2f}; {f['median_signed_ft']:+.1f} ft"
        if c in ("clear", "normal", "stained", "limited"): ks = f"recall {k['recall']:.2f}, precision {k['precision']:.2f}, Unknown {k['unknown']:.0%}"
        elif c == "algae": ks = f"class accuracy {k['class_acc']:.2f} vs constant {k['constant']:.2f}"
        elif c == "sediment": ks = f"bright sediment called clear {k['bright_called_clear']:.0%} (n {k['bright_n']}); accuracy {k['class_acc']:.2f} vs {k['constant']:.2f}"
        else: ks = "no depth input"
        rows.append(f"| {c.capitalize()} | {fs} | **{f['verdict']}** | {ks} | **{k['verdict']}** |")
    ef, cc = Cl["EXACT_FEET_CAPABILITY"], Cl["CLARITY_CLASS_CAPABILITY"]
    rows.append(f"| **Score** | | **{ef['points_of_7']} / 7 → {ef['score_of_10']}/10** | | **{cc['points_of_7']} / 7 → {cc['score_of_10']}/10** |")
    T["p5_caps"] = "| Capability | Exact feet (published rows) | Feet verdict | Clarity class | Class verdict |\n|---|---|---|---|---|\n" + "\n".join(rows)
# ---------------- Part 6
Ck = J("cert/blind_checks.json")
if Ck:
    ok = lambda b: "pass" if b else "**fail**"; c = Ck["checks"]; e = Ck["expected_per_class_us_core (Stage 11 shares)"]; m = Ck["minima"]
    T["p6_checks"] = ("| Blind check | Value | Bar | |\n|---|---:|---:|---|\n" +
        f"| Matched observations | {Ck['matched_observations']} (NLA 2017 {Ck['by_source']['NLA17']}, NLA 2022 {Ck['by_source']['NLA22']}, SYKE {Ck['by_source']['SYKE']}) | ≥ 400 | {ok(c['observations>=400'])} |\n"
        f"| Distinct lakes | {Ck['lakes']} | ≥ 100 | {ok(c['lakes>=100'])} |\n| US states (US core) | {Ck['us_states']} | ≥ 20 | {ok(c['us_states>=20'])} |\n"
        f"| Largest state share (US core) | {Ck['max_state_share_us']:.1%} | ≤ 15% | {ok(c['no_state_over_15pct'])} |\n"
        f"| October–April observations | {Ck['cool_season_share']:.1%} ({Ck['cool_season_lakes']} lakes) | ≥ 15% across ≥ 20 lakes | {ok(c['cool_season>=15%_across>=20_lakes'])} |\n" +
        "\n".join(f"| Expected {k} (US core, planning prior) | {e[k]:.0f} | ≥ {m[k]} | {ok(e[k] >= m[k])} |" for k in m))
json.dump(T, open(f"{D}/analysis/tables12.json", "w"), indent=1)
print({k: len(v) for k, v in T.items()})
