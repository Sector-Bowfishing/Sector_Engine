"""Stage 13 report tables (markdown) from the result JSONs; each only if its file exists. Writes tables13.json."""
import json, os
D = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/stage13"
J = lambda p: json.load(open(f"{D}/{p}")) if os.path.exists(f"{D}/{p}") else None
T = {}
fx = lambda v: f"×{10 ** v:.2f}"
rp = lambda c, n: f"{c[n]['recall']:.2f} / {(c[n]['precision'] or 0):.2f}"
M = J("analysis/models13.json")
if M:
    NAMES = {"A": "A: C3 on ACOLITE (benchmark)", "B-pure": "B-pure: QAA-switch Secchi, no fit", "B-cal": "B-cal: QAA-switch, calibrated", "C-lin": "C-lin: 6-feature linear",
             "C-gbm": "C-gbm: constrained boosting (7 features)", "O1": "O1: ordinal logit", "O2": "O2: C-lin with learned class cut-points",
             "champ-Tred": "Champion form on red turbidity", "champ-Tswitch": "Champion form on red/NIR-switched turbidity"}
    rows = []
    for m, lab in NAMES.items():
        c = M["class"][m]; r = M["regression"].get(m)
        err = f"{r['median_abs_log']:.3f} ({fx(r['median_abs_log'])})" if r else "class only"
        cov = f"{r['coverage']:.0%}" if r else "100%"
        b = "**" if m == M["BEST"] else ""
        rows.append(f"| {b}{lab}{b} | {cov} | {err} | {rp(c, 'clear')} | {rp(c, 'normal')} | **{rp(c, 'stained')}** | **{rp(c, 'limited')}** | {c['balanced_accuracy']:.3f} | {c.get('qwk', 0):.2f} |")
    T["models"] = ("| Candidate (held out by whole lakes, 1,206 rows at 792 lakes) | Answers | Median \\|log\\| (factor) | Clear R / P | Normal R / P | Stained R / P | Limited R / P | Balanced accuracy | Ordinal κ |\n"
                   "|---|---:|---|---|---|---|---|---:|---:|\n" + "\n".join(rows))
    rows = []
    for m in ("B-pure", "C-lin", "C-gbm", "O1", "O2"):
        v = M["vs_A"][m]; ci = lambda k: f"{v[k][0]:+.2f} to {v[k][1]:+.2f}" if v.get(k) else "–"
        rows.append(f"| {NAMES[m].split(':')[0]} | {v['stained_recall_diff']:+.2f} ({ci('stained_recall_ci')}) | {v['limited_recall_diff']:+.2f} ({ci('limited_recall_ci')}) | {v['balanced_diff']:+.3f} ({ci('balanced_ci')}) |")
    T["vs_A"] = "| Against A (lake bootstrap 95% CI) | Stained recall | Limited recall | Balanced accuracy |\n|---|---|---|---|\n" + "\n".join(rows)
    rows = []
    for m, s in M["success_1to4"].items():
        rows.append(f"| {NAMES[m].split(':')[0]} | " + " | ".join("pass" if s[k] else "**fail**" for k in ("1_stained", "2_limited", "3_ci", "4_clear_normal")) + " |")
    T["success"] = "| Candidate | 1. Stained ≥ 0.45 / 0.40 | 2. Limited ≥ 0.50 / 0.60 | 3. Both gains' CI > 0 | 4. Clear and normal kept |\n|---|---|---|---|---|\n" + "\n".join(rows)
    rh = M["region_heldout"]
    T["region"] = "| Region-held-out (5 US regions) | Clear | Normal | Stained | Limited | Stained ratio | Limited ratio |\n|---|---:|---:|---:|---:|---:|---:|\n" + "\n".join(
        f"| {m} | {v['clear']:.2f} | {v['normal']:.2f} | {v['stained']:.2f} | {v['limited']:.2f} | {v['ratio_stained']:.2f} | {v['ratio_limited']:.2f} |" for m, v in rh.items())
    sw = M["switch"]
    rows = [f"| Rows where the switch activates (ρ665 > 0.05) | {sw['activation_share']:.1%} (fully NIR {sw['full_nir_share']:.1%}) |"]
    for n in ("stained", "limited", "sediment"):
        v = sw[n]; ci = v.get("diff_ci")
        rows.append(f"| {n.capitalize()}, same-day turbidity (n {v['n']}) | red {v['red_only']:.3f} → switch {v['switch']:.3f} ({v['rel_improvement']:+.0%}; CI of the difference {ci[0]:+.3f} to {ci[1]:+.3f}) |" if ci else f"| {n} | n {v['n']} |")
    rows.append(f"| Champion form, switched against red: recall change | stained {sw['recall_gain']['stained']:+.2f}, limited {sw['recall_gain']['limited']:+.2f} |")
    T["switch"] = "| Red/NIR switch (Dogliotti 2015) | Value |\n|---|---|\n" + "\n".join(rows)
    B = M["B"]
    T["qaa"] = ("| QAA-switch diagnostics | Value |\n|---|---|\n" +
                f"| Reference band used | 560 nm {B['qaa_reference_band'].get('B03', 0)}, 665 nm {B['qaa_reference_band'].get('B04', 0)}, 740 nm {B['qaa_reference_band'].get('B06', 0)} rows |\n"
                f"| Refusals | {', '.join(f'{k} {v}' for k, v in B['qaa_refusals'].items() if k != 'ok')}; answered {B['qaa_refusals'].get('ok', 0)} |\n"
                f"| B-pure: coverage; stained+limited recall gain (CI) | {B['B-pure']['coverage']:.0%}; {B['B-pure']['stained_limited_gain']:+.3f} ({B['B-pure']['gain_ci'][0]:+.3f} to {B['B-pure']['gain_ci'][1]:+.3f}) |\n"
                f"| B-pure: median \\|log\\| minus A's (CI) | {B['B-pure']['median_log_diff_ci_vs_A'][0]:+.3f} to {B['B-pure']['median_log_diff_ci_vs_A'][1]:+.3f} |")
    cd = M["cdom_ablation"]
    T["cdom"] = "| Removing F_bg (blue/green) from | Stained recall change (CI) | Balanced accuracy change (CI) |\n|---|---|---|\n" + "\n".join(
        f"| {m} | {-v['stained_recall_drop']:+.3f} ({-v['stained_recall_ci'][1]:+.3f} to {-v['stained_recall_ci'][0]:+.3f}) | {-v['balanced_drop']:+.3f} ({-v['balanced_ci'][1]:+.3f} to {-v['balanced_ci'][0]:+.3f}) |" for m, v in cd.items())
Mc = J("analysis/mechanism13.json")
if Mc:
    def sh(d):
        return "; ".join(f"{k} {v:.2f}" for k, v in d.items() if not k.startswith("_")) + f" (total {d['_total']:.2f})"
    rows = [f"| In-situ turbidity + chlorophyll, all rows (n {Mc['insitu_turb_chl']['n']}) | {sh(Mc['insitu_turb_chl']['all'])} |",
            f"| … stained + limited | {sh(Mc['insitu_turb_chl']['stained+limited'])} |"]
    d = Mc["insitu_with_ldoc"]; rows += [f"| With DOC/TOC, all rows (n {d['n']}, {d['lakes']} lakes) | {sh(d['all'])} |", f"| … stained + limited (n {d['n_stained_limited']}) | {sh(d['stained+limited'])} |"]
    d = Mc["insitu_with_lcol"]; rows += [f"| With true colour, all rows (n {d['n']}, {d['lakes']} lakes) | {sh(d['all'])} |", f"| … stained + limited (n {d['n_stained_limited']}) | {sh(d['stained+limited'])} |"]
    g = Mc["satellite_groups"]; rows += [f"| Satellite feature groups (C-lin), all rows | {sh(g['all'])} |", f"| … stained + limited | {sh(g['stained+limited'])} |"]
    T["mech"] = "| Held-out R² of log Secchi, Shapley shares | Components |\n|---|---|\n" + "\n".join(rows)
    ic = Mc["insitu_class_recall_turb_chl"]; rc = Mc["resolution_ceiling_recall (true value + C-gbm held-out error)"]
    T["ceiling"] = ("| Recall (precision) | Clear | Normal | Stained | Limited |\n|---|---:|---:|---:|---:|\n" +
                    f"| A perfect in-situ retrieval: turbidity + chlorophyll known, held out | {ic['clear'][0]:.2f} ({ic['clear'][1]:.2f}) | {ic['normal'][0]:.2f} ({ic['normal'][1]:.2f}) | {ic['stained'][0]:.2f} ({ic['stained'][1]:.2f}) | {ic['limited'][0]:.2f} ({ic['limited'][1]:.2f}) |\n"
                    f"| An unbiased retrieval with C-gbm's error spread | {rc['clear']:.2f} | {rc['normal']:.2f} | {rc['stained']:.2f} | {rc['limited']:.2f} |\n"
                    f"| Class width (log10) | open | {Mc['class_width_log10']['normal']} | {Mc['class_width_log10']['stained']} | open |")
F = J("tandem/footprint13.json")
if F:
    mm = F["mean"]; md = F["median_over_pairs_dft"]
    T["footprint"] = ("| Engine, 60 m disks on identical tandem water (10 pairs) | Raw S2C, hard | Harmonised, hard | **Harmonised, with bands** | Median \\|Δft\\| | Corpus predictions in a band |\n|---|---:|---:|---:|---:|---:|\n" +
                      "\n".join(f"| {m} | {mm[f'{m}|raw|hard']:.1%} | {mm[f'{m}|harm|hard']:.1%} | **{mm[f'{m}|harm|band']:.1%}** | {md[m]:.2f} ft | {F['band_share_of_corpus_predictions'][m]:.0%} |" for m in ("A", "C-lin", "C-gbm", "O2")))
Cv = J("analysis/coverage13.json")
if Cv:
    v = Cv["variants"]
    T["variants"] = "| Relaxed-mask variant (tier 2) | Stations recovered | Their median \\|log\\| (A) | Tier-1 median \\|log\\| (A) | Passes |\n|---|---:|---:|---:|---|\n" + "\n".join(
        f"| {k} | {x.get('n', 0)} | {x.get('tier2_median_abs_log_A', 0):.3f} | {x.get('tier1_median_abs_log_A', 0):.3f} | {'yes' if x.get('passes') else 'no'} |" for k, x in v.items())
    def tier_rows(key, lab):
        b = Cv[key]; c = b["coverage"]
        rows = [f"| {lab}: coverage | tier 1 {c['tier1']:.0%} · tier 2 {c['tier2']:.0%} · tier 3 {c['tier3']:.0%} · unknown {c['unknown']:.0%} |"]
        for t, l in (("tier1_only", "Tier 1 only"), ("tiers1-2", "Tiers 1–2"), ("tiers1-3", "Tiers 1–3 (tier 3 lower authority)")):
            x = b[t]; rows.append(f"| {lab}, {l} | balanced {x['balanced']:.3f}; " + "; ".join(f"{n} {x[n][0]:.2f}/{x[n][1]:.2f}" for n in ("clear", "normal", "stained", "limited")) + " |")
        for t in (2, 3):
            if f"tier{t}_own_rows" in b:
                x = b[f"tier{t}_own_rows"]; rows.append(f"| {lab}, tier {t} rows only (n {x['n']}) | balanced {x['balanced']:.3f}; " + "; ".join(f"{n} {x[n][0]:.2f}/{x[n][1]:.2f}" for n in ("clear", "normal", "stained", "limited")) + " |")
        return rows
    T["tiers"] = "| Coverage tiers (all 1,582 processed rows; recall/precision, Unknown = miss) | Value |\n|---|---|\n" + "\n".join(tier_rows("best", Cv["BEST"]) + tier_rows("A", "A"))
Cp = J("analysis/capability13.json")
if Cp:
    rows = []
    for c in ("clear", "normal", "stained", "limited", "algae", "sediment", "bottom-risk"):
        f_, k = Cp["exact_feet"][c], Cp["clarity_class"][c]
        fs = "–" if not f_.get("n_published") else f"{f_['n_published']} published ({f_['coverage']:.0%}); ×{10 ** f_['median_abs_log']:.2f}; {f_['median_signed_ft']:+.1f} ft"
        if c in ("clear", "normal", "stained", "limited"): ks = f"recall {k['recall']:.2f}, precision {k['precision']:.2f}, Unknown {k['unknown']:.0%}"
        elif c == "algae": ks = f"class accuracy {k['class_acc']:.2f} vs constant {k['constant']:.2f}"
        elif c == "sediment": ks = f"bright sediment called clear {k['bright_called_clear']:.0%} (n {k['bright_n']}); accuracy {k['class_acc']:.2f} vs {k['constant']:.2f}"
        else: ks = "no depth input"
        rows.append(f"| {c.capitalize()} | {fs} | **{f_['verdict']}** | {ks} | **{k['verdict']}** |")
    ef, cc = Cp["EXACT_FEET_CAPABILITY"], Cp["CLARITY_CLASS_CAPABILITY"]
    rows.append(f"| **Score** | | **{ef['points_of_7']} / 7 → {ef['score_of_10']}/10** | | **{cc['points_of_7']} / 7 → {cc['score_of_10']}/10** |")
    T["caps"] = "| Capability | Exact feet (published rows) | Feet verdict | Clarity class | Class verdict |\n|---|---|---|---|---|\n" + "\n".join(rows)
    sh = Cp["shares"]
    T["shares"] = f"| What a user would get (BEST, tiers 1–3) | Share |\n|---|---:|\n| Exact feet (and the class) | {sh['feet_published']:.0%} |\n| Class only | {sh['class_only_feet_withheld']:.0%} |\n| Unknown | {sh['unknown']:.0%} |"
G = J("analysis/gunt13.json")
if G:
    T["gunt"] = "| Guntersville, 42 historical rows at 10 station groups (reported apart) | Error | Median signed | Class accuracy |\n|---|---:|---:|---:|\n" + "\n".join(
        f"| {m} | {fx(G[m]['median_abs_log'])} ({G[m]['median_abs_log']:.3f}) | {G[m]['median_signed_ft']:+.1f} ft | {G[m]['class_accuracy']:.2f} |" for m in ("A", "C-lin", "C-gbm", "O2"))
Ck = J("cert/blind_checks13.json")
if Ck:
    ok = lambda b: "pass" if b else "**fail**"; c = Ck["checks"]; e = Ck["expected_per_class_us_core"]; m = Ck["minima"]
    T["cert"] = ("| Blind check (Stage 12 rule) | Value | Bar | |\n|---|---:|---:|---|\n" +
                 f"| Matched observations | {Ck['matched_observations']} (NLA {Ck['us_core']}, SYKE {Ck['syke']}) | ≥ 400 | {ok(c['observations>=400'])} |\n"
                 f"| Distinct lakes | {Ck['lakes']} | ≥ 100 | {ok(c['lakes>=100'])} |\n| US states (US core) | {Ck['us_states']} | ≥ 20 | {ok(c['us_states>=20'])} |\n"
                 f"| Largest state share (US core) | {Ck['max_state_share_us']:.1%} | ≤ 15% | {ok(c['no_state_over_15pct'])} |\n"
                 f"| October–April observations | {Ck['cool_season_share']:.1%} ({Ck['cool_season_lakes']} lakes) | ≥ 15% across ≥ 20 lakes | {ok(c['cool_season>=15%_across>=20_lakes'])} |\n" +
                 "\n".join(f"| Expected {k} (US core) | {e[k]:.0f} | ≥ {m[k]} | {ok(e[k] >= m[k])} |" for k in m))
json.dump(T, open(f"{D}/analysis/tables13.json", "w"), indent=1); print({k: len(v) for k, v in T.items()})
