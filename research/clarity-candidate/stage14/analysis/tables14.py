"""Stage 14 report tables (markdown) from the result JSONs. Writes tables14.json."""
import json, os, math
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = f"{S}/stage14"
J = lambda p: json.load(open(f"{D}/{p}")) if os.path.exists(f"{D}/{p}") else None
T = {}
CL = ["clear", "normal", "stained", "limited"]
f2 = lambda v: "–" if v is None else f"{v:.2f}"
f3 = lambda v: "–" if v is None else f"{v:.3f}"
pc = lambda v: "–" if v is None else f"{v:.0%}"
fx = lambda v: "–" if v is None else f"×{10 ** v:.2f}"
F = J("FREEZE_STAGE14.json"); E = J("engine/frozen_engine.json"); DV = J("analysis/dev14.json"); CE = J("analysis/cert14.json")
BC = J("cert/blind_checks14.json"); PO = J("cert/wqp_pool.json"); DR = J("cert/wqp_draw.json")
if F:
    T["freeze"] = ("| Step | UTC | What was fixed |\n|---|---|---|\n"
                   f"| Certification protocol | {F['cert_protocol_frozen_utc']} | Eligible files, inclusion and exclusion, lake independence, sampling, matching, class minima (`cert/CERT_PROTOCOL_STAGE14.md`, sha256 `{F['files']['stage14/cert/CERT_PROTOCOL_STAGE14.md'][:8]}…`) |\n"
                   f"| Pre-registration | {F['prereg_frozen_utc']} | Product states, bands, decision metric, O2/C-gbm rule, tier-3 rule, clear-water tests, pass criteria (`PREREGISTRATION_STAGE14.md`, `{F['files']['stage14/PREREGISTRATION_STAGE14.md'][:8]}…`) |\n"
                   f"| Engine | {F['engine_frozen_utc']} | C-gbm fit, bands, feet authorisation, interval, tier-3 rule (`engine/`, `{F['files']['stage14/engine/frozen_engine.json'][:8]}…`) |\n"
                   + (f"| WQP sample | after matching | `cert/wqp_sample.csv` (`{F['files'].get('stage14/cert/wqp_sample.csv', '')[:8]}…`) |\n" if "stage14/cert/wqp_sample.csv" in F["files"] else "")
                   + (f"| Unsealed | {F['unsealed_utc']} | Secchi, chlorophyll and turbidity of the certification rows (`unseal/truth14.json`, `{F['files']['stage14/unseal/truth14.json'][:8]}…`) |" if "unsealed_utc" in F else ""))
if E:
    b = E["bands_ft"]
    T["states"] = ("| Product state | Prediction range (ft) | Feet shown | Authority |\n|---|---|---|---|\n"
                   f"| Clear | ≥ 6.0 | yes | ACOLITE (tiers 1–2) |\n| Normal | {b['3ft'][1]:.2f} to 6.0 | yes | ACOLITE |\n"
                   f"| **Normal-to-Stained** | {b['3ft'][0]:.2f} to {b['3ft'][1]:.2f} | yes | ACOLITE |\n| Stained | {b['2ft'][1]:.2f} to {b['3ft'][0]:.2f} | yes | ACOLITE |\n"
                   f"| **Stained-to-Limited** | {b['2ft'][0]:.2f} to {b['2ft'][1]:.2f} | yes | ACOLITE |\n| Limited | < {b['2ft'][0]:.2f} | yes | ACOLITE |\n"
                   f"| Clear (lower authority) | Sen2Cor-C3 ≥ 6.0 | lower-confidence feet | tier 3 |\n| Unknown / Low Authority | any other tier-3 reading, or no reading | no | — |")
    fb = E["band_fit"]
    T["bandfit"] = ("| Boundary | Logistic α | β (per log10) | Rows within ±0.30 | Lower edge | Upper edge |\n|---|---:|---:|---:|---:|---:|\n" +
                    "\n".join(f"| {k.replace('ft', ' ft')} | {v['alpha']:.2f} | {v['beta']:.1f} | {v['n']} | {E['bands_ft'][k][0]:.2f} ft ({v['d_lo']:+.3f}) | {E['bands_ft'][k][1]:.2f} ft ({v['d_hi']:+.3f}) |" for k, v in fb.items()))
if DV:
    c = DV["compare"]
    rows = []
    for m in ("C-gbm", "O2", "C-lin (reference)"):
        d = c[m]["decision"]; h = c[m]["hard"]
        rows.append(f"| {'**' + m + '**' if m == DV['SELECTED'] else m} | {d['balanced']:.3f} | {d['specificity']:.2f} | " + " | ".join(f"{d[n]['decision_recall']:.2f} / {d[n]['decision_precision']:.2f}" for n in CL) +
                    f" | {h['balanced']:.3f} | ×{c[m]['factor']:.2f} | {c[m]['inconsistency']:.1%} |")
    dd = c["O2_minus_Cgbm_decision_balanced"]
    T["compare"] = ("| Engine (development, tiers 1–2, nested lake-held-out) | Decision-balanced | Specificity | Clear decision R / P | Normal | Stained | Limited | Original balanced | Feet error | Feet outside the state |\n|---|---:|---:|---|---|---|---|---:|---:|---:|\n"
                    + "\n".join(rows) + f"\n\nO2 minus C-gbm, decision-balanced: **{dd['value']:+.3f}** (lake bootstrap 95% CI {dd['ci95'][0]:+.3f} to {dd['ci95'][1]:+.3f}).")
    H, HO = DV["historical"], DV["historical_other"]
    rows = []
    for k in CL + ["algae", "sediment", "bottom-risk"]:
        ef, hc, pr = H["exact_feet"][k], H["hard_class"][k], H["product"][k]
        efs = f"{ef['verdict']}" + (f" ({fx(ef['median_abs_log'])}, {ef['median_signed_ft']:+.1f} ft)" if ef.get("n_published") else "")
        if k in CL: hcs = f"{hc['verdict']} ({hc['recall']:.2f} / {hc['precision']:.2f})"; prs = f"{pr['verdict']} ({pr['decision_recall']:.2f} / {pr['decision_precision']:.2f})"
        elif k == "bottom-risk": hcs, prs = "NOT", "NOT"
        else: hcs = f"{hc['verdict']} ({hc['class_acc']:.2f} vs {hc['constant']:.2f})"; prs = f"{pr['verdict']} ({pr['decision_acc']:.2f} vs {pr['constant']:.2f})"
        rows.append(f"| {k.capitalize()} | {efs} | {hcs} | {prs} |")
    rows.append(f"| **Score (C-gbm)** | **{H['EXACT_FEET']['points_of_7']} / 7 → {H['EXACT_FEET']['score_of_10']}/10** | **{H['HARD_CLASS']['points_of_7']} / 7 → {H['HARD_CLASS']['score_of_10']}/10** | **{H['PRODUCT']['points_of_7']} / 7 → {H['PRODUCT']['score_of_10']}/10** |")
    rows.append(f"| Score (O2, for the record) | {HO['EXACT_FEET']['score_of_10']}/10 | {HO['HARD_CLASS']['score_of_10']}/10 | {HO['PRODUCT']['score_of_10']}/10 |")
    T["hist"] = "| Capability (development, historical) | Exact feet | Original hard class (R / P) | Boundary-aware product (decision R / P) |\n|---|---|---|---|\n" + "\n".join(rows)
    cl = DV["clear"]
    T["clear"] = ("| True Secchi (clear rows, tiers 1–2) | n | Median signed (ft) | Median signed (log) | Share of the total negative error |\n|---|---:|---:|---:|---:|\n" +
                  "\n".join(f"| {k.replace('-', '–') if not k.endswith('-') else '≥ ' + k[:-1]} ft | {v['n']} | {v['median_signed_ft']:+.2f} | {v['median_signed_log']:+.3f} | {v['share_of_negative_ft']:.0%} |" for k, v in cl["bins"].items())
                  + f"\n| **All clear** | {cl['n']} | **{cl['median_signed_ft']:+.2f}** | {cl['median_signed_log']:+.3f} | 100% |")
    t3 = DV["tier3"]
    T["tier3"] = ("| State Sen2Cor-C3 would issue (development tier-3 rows, nested bands) | n | Decision precision | Allowed (≥ 0.75, n ≥ 15) |\n|---|---:|---:|---|\n" +
                  "\n".join(f"| {s} | {v['n']} | {v['precision']:.2f} | {'**yes**' if s in t3['allowed_states'] else 'no'} |" for s, v in t3["decision_states"]["by_state"].items()))
if PO and DR:
    T["pool"] = ("| Step (value-blind) | Count |\n|---|---:|\n"
                 f"| WQP sites in the Stage 1 pull | 20,860 |\n| Eligible after the section 3 rules | {PO['sites']:,} sites, {PO['site_days']:,} site-days, {PO['lakes']:,} lakes, {PO['states']} states |\n"
                 f"| … October–April | {PO['cool_site_days']:,} site-days |\n| … on a lake with no Stage 1–4 site within 5 km (strict subset) | {PO['strict_subset_sites']:,} sites |\n"
                 f"| Seeded draw | {DR['drawn']:,} site-days |\n| Clear pass within ±1 day (prescreen) | {DR['passed']:,} ({DR['cool_passed']} cool-season) |"
                 + (f"\n| Matched (≥ 5 valid pixels) | {BC['wqp_matched_before_caps']:,} |\n| ≤ 3 per lake | {BC['wqp_after_lake_cap']:,} |\n| **Final WQP sample** (≤ 15% per state, ≤ 900) | **{BC['wqp_final']}** |" if BC else ""))
if BC:
    ck = BC["checks"]; ok = lambda b: "pass" if b else "**fail**"; e = BC["expected_per_class_us_core"]; m = BC["minima"]
    T["checks"] = ("| Blind check (before unsealing) | Value | Bar | |\n|---|---:|---:|---|\n"
                   f"| Observations | {BC['observations']} (NLA {BC['nla']}, WQP {BC['wqp']}, SYKE {BC['syke']}) | ≥ 400 | {ok(ck['observations>=400'])} |\n"
                   f"| Lakes | {BC['lakes']} | ≥ 100 | {ok(ck['lakes>=100'])} |\n| US states | {BC['us_states']} | ≥ 20 | {ok(ck['us_states>=20'])} |\n"
                   f"| Largest state share, US core | {BC['max_state_share_us']:.1%} | ≤ 15% | {ok(ck['no_state_over_15pct'])} |\n"
                   f"| October–April | {BC['cool_share']:.1%} ({BC['cool_lakes']} lakes; US core {BC['us_cool_share']:.1%}) | ≥ 15% across ≥ 20 lakes | {ok(ck['cool>=15%_across>=20_lakes'])} |\n"
                   + "\n".join(f"| Expected {k}, US core | {e[k]:.0f} | ≥ {m[k]} | {ok(e[k] >= m[k])} |" for k in m))
if CE:
    U = CE["US"]
    rows = []
    for n in CL:
        h = U["hard"][n]; d = U["decision"][n]; fb = U["feet_by_class"].get(n)
        rows.append(f"| {n.capitalize()} | {U['classes'].get(n, 0)} | {f2(h[0])} / {f2(h[1])} | **{f2(d[0])} / {f2(d[1])}** | {pc(d[2])} | " + (f"×{10 ** fb[0]:.2f}, {fb[1]:+.1f} ft (n {fb[2]})" if fb else "–") + " |")
    T["cert_class"] = ("| True class (US core) | n | Original hard R / P | **Decision R / P** | Answered at ACOLITE authority | Exact feet: error, median signed |\n|---|---:|---|---|---:|---|\n" + "\n".join(rows) +
                       f"\n| **All** | {U['n']} | balanced {U['hard']['balanced']:.3f} | **decision-balanced {U['decision_balanced']:.3f}** | specificity {U['specificity']:.2f} | {fx(U['feet_median_abs_log'])}; interval coverage {pc(U['interval_coverage'])} |")
    dvs = DV["compare"]["C-gbm"]["decision"]["by_state"] if DV else {}
    T["cert_states"] = ("| Issued state | Certification n | Certification precision | Development precision |\n|---|---:|---:|---:|\n" +
                        "\n".join(f"| {s} | {v['n']} | {v['precision']:.2f} | {dvs.get(s, {}).get('precision', 0):.2f} |" for s, v in U["by_state"].items()))
    rows = []
    for k in CL + ["algae", "sediment", "bottom-risk"]:
        ef, hc, pr = U["exact_feet"][k], U["hard_class_rubric"][k], U["product"][k]
        efs = ef["verdict"] + (f" ({fx(ef['median_abs_log'])}, {ef['median_signed_ft']:+.1f} ft)" if ef.get("n_published") else "")
        if k in CL: hcs = f"{hc['verdict']} ({f2(hc.get('recall'))} / {f2(hc.get('precision'))})"; prs = f"{pr['verdict']} ({f2(pr.get('decision_recall'))} / {f2(pr.get('decision_precision'))})"
        elif k == "bottom-risk": hcs, prs = "NOT", "NOT"
        else: hcs = f"{hc['verdict']} (n {hc.get('n', 0)})"; prs = f"{pr['verdict']} (n {pr.get('n', 0)}" + (f"; {pr['decision_acc']:.2f} vs {pr['constant']:.2f}" if pr.get("n") else "") + ")"
        rows.append(f"| {k.capitalize()} | {efs} | {hcs} | {prs} |")
    rows.append(f"| **Score** | **{U['EXACT_FEET']['score_of_10']}/10** | **{U['HARD_CLASS']['score_of_10']}/10** | **{U['PRODUCT']['score_of_10']}/10** |")
    T["cert_caps"] = "| Capability (certification, US core) | Exact feet | Original hard class | Boundary-aware product |\n|---|---|---|---|\n" + "\n".join(rows)
    L = CE["readiness_lines"]; mn = CE["counts_vs_minima"]
    T["lines"] = ("| Readiness line | Rubric | n (minimum) | Verdict |\n|---|---|---:|---|\n" +
                  "\n".join(f"| {k} | {r} | {mn[c][0]} ({mn[c][1]}) | **{L[k]}** |" for k, r, c in (("CLEAR FEET READY", "Exact feet, clear", "clear"), ("NORMAL READY", "Product, normal", "normal"),
                            ("STAINED READY", "Product, stained", "stained"), ("LIMITED READY", "Product, limited", "limited"), ("ALGAL READY", "Product, algae", "algae"), ("SEDIMENT READY", "Product, sediment", "sediment")))
                  + f"\n| **BLIND CERTIFICATION PASSED** | YES = all six YES; PARTIAL = ≥ 3 points | | **{CE['PASSED']}** ({CE['pass_points']} of 6) |")
    rows = []
    for g, sub in CE["breakdown"].items():
        for k, v in sub.items():
            if not v.get("n"): continue
            if v["decision_balanced"] != v["decision_balanced"]:
                rows.append(f"| {g} | {k} | {v['n']} | lower authority: Clear-or-Unknown (section 8) | – | – | {fx(v['feet_median_abs_log'])} | – |"); continue
            rows.append(f"| {g} | {k} | {v['n']} | {v['decision_balanced']:.3f} | " + " · ".join(f"{f2(v['decision'][n][0])}" for n in CL) + f" | {v['hard']['balanced']:.3f} | {fx(v['feet_median_abs_log'])} | {pc(v['interval_coverage'])} |")
    T["breakdown"] = "| Split (US core) | Group | n | Decision-balanced | Decision recall: clear · normal · stained · limited | Original balanced | Feet error | Interval coverage |\n|---|---|---:|---:|---|---:|---:|---:|\n" + "\n".join(rows)
    Y = CE["SYKE"]
    if Y.get("n"):
        T["syke"] = (f"| SYKE (Finland, out of domain) | Value |\n|---|---|\n| Observations | {Y['n']} at {Y['lakes']} lakes; tiers {Y['tiers']} |\n| Classes | {Y['classes']} |\n"
                     f"| Decision-balanced / specificity | {Y['decision_balanced']:.3f} / {Y['specificity']:.2f} |\n| Decision R / P by class | " + "; ".join(f"{n} {f2(Y['decision'][n][0])} / {f2(Y['decision'][n][1])}" for n in CL) + " |\n"
                     f"| Original balanced | {Y['hard']['balanced']:.3f} |\n| Feet error | {fx(Y['feet_median_abs_log'])}; by class " + "; ".join(f"{k} {10 ** v[0]:.2f}× {v[1]:+.1f} ft" for k, v in Y["feet_by_class"].items()) + " |\n"
                     f"| Rubric scores | exact feet {Y['EXACT_FEET']['score_of_10']}/10, hard class {Y['HARD_CLASS']['score_of_10']}/10, product {Y['PRODUCT']['score_of_10']}/10 |")
json.dump(T, open(f"{D}/analysis/tables14.json", "w"), indent=1); print({k: len(v) for k, v in T.items()})
