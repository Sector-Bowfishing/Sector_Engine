"""Build CURRENT_CLARITY_STAGE15_FINAL_PRODUCT_SEMANTICS.md from the frozen Stage 15 JSONs."""
import json
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = json.load(open(f"{S}/stage15/analysis/dev15.json")); C = json.load(open(f"{S}/stage15/analysis/cert15.json"))
F = json.load(open(f"{S}/stage15/FREEZE_STAGE15.json")); SEM = json.load(open(f"{S}/stage15/engine/semantics15.json"))
C14 = json.load(open(f"{S}/stage14/analysis/cert14.json")); FD = json.load(open(f"{S}/stage15/analysis/floor_diag15.json"))
U = C["US"]; op = U["op"]; dv = D["final"]; CL = ["clear", "normal", "stained", "limited"]
f2 = lambda v: "–" if v is None else f"{v:.2f}"; pc = lambda v: "–" if v is None else f"{v:.0%}"; p1 = lambda v: f"{100 * v:.1f}%"
b = SEM["bands_ft"]
T = {}
T["freeze"] = ("| Step | UTC | What was fixed |\n|---|---|---|\n"
               f"| Pre-registration | {F['prereg_frozen_utc']} | Derivation rules for every new state, display and authority; the operational rubric; the readiness rule (`PREREGISTRATION_STAGE15.md`, `{F['files']['stage15/PREREGISTRATION_STAGE15.md'][:8]}…`) |\n"
               f"| Semantics | {F['semantics_frozen_utc']} | Parameters derived from development rows only (`engine/semantics15.json`, `{F['files']['stage15/engine/semantics15.json'][:8]}…`), before the re-score |\n"
               f"| Inputs | re-checked | Engine, certification sample, ACOLITE results and truth: all match their Stage 14 hashes |")
T["states"] = ("| State | Prediction range (ft) | Display | Authority |\n|---|---|---|---|\n"
               f"| Clear | ≥ {b['6ft'][1]:.2f} | exact feet + two-thirds interval | full |\n"
               f"| **Clear-to-Normal (new)** | {b['6ft'][0]:.2f} to {b['6ft'][1]:.2f} | exact feet + interval | full |\n"
               f"| Normal | {b['3ft'][1]:.2f} to {b['6ft'][0]:.2f} | exact feet + interval | full |\n"
               f"| Normal-to-Stained | {b['3ft'][0]:.2f} to {b['3ft'][1]:.2f} | exact feet + interval | full |\n"
               f"| Stained | {b['2ft'][1]:.2f} to {b['3ft'][0]:.2f} | exact feet + interval | full |\n"
               f"| Stained-to-Limited | {b['2ft'][0]:.2f} to {b['2ft'][1]:.2f} | exact feet + interval | full |\n"
               f"| Limited | < {b['2ft'][0]:.2f} | exact feet + interval | full |\n"
               "| Any state, NDCI > 0.03 | as above | \"~X ft\" + \"Algal water detected — elevated uncertainty\" | full |\n"
               "| Any state, Sentinel-2C | as above | state only (feet and interval withheld) | **lower** |\n"
               "| Tier 3 Clear (Sen2Cor-C3 ≥ 6 ft) | — | \"~X ft\" (lower confidence) | **lower** |\n"
               "| Unknown / Low Authority | any other tier-3 reading, or none | nothing | — |")
f6 = SEM["band6_fit"]
T["c2n"] = ("| Clear-to-Normal | Value |\n|---|---|\n"
            f"| Band (pooled development, 2:1 odds) | {b['6ft'][0]:.2f}–{b['6ft'][1]:.2f} ft (logistic α {f6['alpha']:.2f}, β {f6['beta']:.1f}, {f6['n']} rows within ±0.30) |\n"
            f"| Nested bands, 5 folds | " + "; ".join(f"{v[0]:.2f}–{v[1]:.2f}" for v in D["nested_b6_ft"].values()) + " ft |\n"
            f"| Adoption test (development, nested) | operational {D['c2n_without']['balanced']:.3f} → **{D['c2n_with']['balanced']:.3f}**; harmful {p1(D['c2n_without']['harmful_rate'])} → **{p1(D['c2n_with']['harmful_rate'])}** → **adopted** |\n"
            f"| Re-score: Clear-to-Normal answers | {C['clear_to_normal']['n']}, right {pc(C['clear_to_normal']['precision'])} (truth: " + ", ".join(f"{v} {k}" for k, v in C['clear_to_normal']['truth'].items()) + ") |\n"
            f"| … what Stage 14 had said for them | " + ", ".join(f"{k} {v}" for k, v in C['clear_to_normal']['stage14_state'].items()) + " |\n"
            f"| Plain \"Normal\" answers | Stage 14: {C14['US']['by_state']['Normal']['n']}, right {pc(C14['US']['by_state']['Normal']['precision'])} → Stage 15: {C['clear_to_normal']['normal_state_n']}, right {pc(C['clear_to_normal']['normal_state_precision'])} |")
fd = FD["pred_ge_T"]
T["floor"] = ("| Predicted ≥ | Development rows | Median \\|log\\| (trigger > 0.15) | Truth − prediction (median) | Truth ≥ that depth | Truth ≥ 6 ft |\n|---|---:|---:|---:|---:|---:|\n" +
              "\n".join(f"| {t} ft | {v['n']} | {v['median_abs_log']:.3f} | {v['median_true_minus_pred_ft']:+.2f} ft | {v['P(truth>=T)']:.0%} | {v['P(truth>=6)']:.0%} |" for t, v in fd.items()))
al = D["algal"]; ca = C["algal"]
T["algal"] = ("| NDCI level | Development rows | State right (development) | Behaviour (frozen rule) | Re-score rows | State right (re-score) | In-situ algal share (dev / re-score) |\n|---|---:|---:|---|---:|---:|---|\n" +
              "\n".join(f"| {lv} ({'0.03–0.10' if lv == 'moderate' else '> 0.10'}) | {al[lv]['n']} | {pc(al[lv]['decision_precision'])} | **{al[lv]['behaviour']}** | {ca[lv]['n']} | {pc(ca[lv]['state_precision'])} | {pc(al[lv]['share_insitu_algal'])} / {pc(ca[lv]['insitu_algal_share'])} |" for lv in ("moderate", "strong")))
s2 = C["s2c"]; sd = D["s2c_dev"]
T["s2c"] = ("| Sentinel-2C | Value |\n|---|---|\n"
            f"| Development S2C rows (tiers 1–2) | {sd['n']}; median signed log {sd['median_signed_log']:+.3f} (S2A/B {sd['others_median_signed_log']:+.3f}) |\n"
            f"| Certification S2C rows | {s2['n']} ({s2['share_us']:.0%} of the US core); {s2['lowered_from_full']} lowered from full authority; feet withheld on {s2['feet_withheld']} |\n"
            f"| Share of 2025-dated certification rows | **{s2['share_2025_rows']:.0%}** ({s2['n_2025']} rows) |\n"
            f"| Operational score of S2C rows | {s2['op_mean']:.2f}; harmful answers {s2['harmful']} |")
rows = []
for n in CL:
    c, d_ = op["per_class"][n], dv["per_class"][n]
    rows.append(f"| {n.capitalize()} | {d_['n']} | {d_['mean']:.3f} | {c['n']} | **{c['mean']:.3f}** |")
T["op"] = ("| True class | Development n | Development score | Re-score n | **Re-score score** |\n|---|---:|---:|---:|---:|\n" + "\n".join(rows) +
           f"\n| **Class-balanced → /10** | | {dv['balanced']:.3f} → **{dv['score_of_10']}/10** | | **{op['balanced']:.3f} → {op['score_of_10']}/10** |"
           f"\n| Harmful (bar ≤ 15%) | | {p1(dv['harmful_rate'])} | | **{p1(op['harmful_rate'])}** |\n| Severe (bar ≤ 2%) | | {p1(dv['severe_rate'])} | | {p1(op['severe_rate'])} |")
oc = op["outcomes"]; tot = sum(oc.values())
T["outcomes"] = ("| Outcome (re-score, US core) | Score | Rows | Share |\n|---|---:|---:|---:|\n" +
                 "\n".join(f"| {lab} | {sc} | {oc.get(k, 0)} | {oc.get(k, 0) / tot:.0%} |" for k, lab, sc in (("correct_single", "Correct single state", "1.0"), ("correct_boundary", "Correct boundary state", "0.9"),
                           ("floor_correct", "Correct very-clear floor", "1.0"), ("lower_correct", "Correct lower-authority answer", "0.75"), ("lower_wrong", "Wrong lower-authority answer", "0.25"),
                           ("unknown_appropriate", "Appropriate Unknown", "0.5"), ("unknown_missed_right", "Unknown that withheld a right answer", "0.25"), ("harmful", "**Harmful wrong answer**", "0"))))
st = D["steps"]
T["steps"] = ("| Semantics (development, nested) | Operational | Harmful | Severe |\n|---|---:|---:|---:|\n" +
              "\n".join(f"| {k} | {v['balanced']:.3f} ({v['score_of_10']}/10) | {p1(v['harmful_rate'])} | {p1(v['severe_rate'])} |" for k, v in st.items()))
r14 = C14["US"]
T["rubrics"] = ("| Rubric (certification set) | Stage 14 semantics | **Stage 15 semantics** |\n|---|---|---|\n"
                f"| Exact feet (Stage 12) | {r14['EXACT_FEET']['score_of_10']}/10 | **{U['EXACT_FEET']['score_of_10']}/10** |\n"
                f"| Original hard class | {r14['HARD_CLASS']['score_of_10']}/10 | **{U['HARD_CLASS']['score_of_10']}/10** (unchanged by design) |\n"
                f"| Boundary-aware product (Stage 14 section 8) | {r14['PRODUCT']['points_of_7']} / 7 → {r14['PRODUCT']['score_of_10']}/10 | **{U['PRODUCT']['points_of_7']} / 7 → {U['PRODUCT']['score_of_10']}/10** |\n"
                f"| Decision-balanced accuracy | {r14['decision_balanced']:.3f} | **{U['decision_balanced']:.3f}** |\n"
                f"| Operational (new) | — | **{op['score_of_10']}/10** |")
rows = []
for k in CL + ["algae", "sediment", "bottom-risk"]:
    p14, p15 = r14["product"][k], U["product"][k]; ef = U["exact_feet"][k]
    efs = ef["verdict"] + (f" ({ef['median_signed_ft']:+.1f} ft, coverage {ef['coverage']:.0%})" if ef.get("n_published") else "")
    def ps(p):
        if k in CL: return f"{p['verdict']} ({f2(p.get('decision_recall'))} / {f2(p.get('decision_precision'))})"
        if k == "bottom-risk": return "NOT"
        return f"{p['verdict']} ({f2(p.get('decision_acc'))} vs {f2(p.get('constant'))})"
    rows.append(f"| {k.capitalize()} | {efs} | {ps(p14)} | **{ps(p15)}** |")
T["caps"] = "| Capability (re-score) | Exact feet | Product, Stage 14 semantics | **Product, Stage 15 semantics** |\n|---|---|---|---|\n" + "\n".join(rows)
T["statesfreq"] = ("| Issued state (re-score) | n | Right | of which full authority |\n|---|---:|---:|---:|\n" +
                   "\n".join(f"| {s} | {v['n']} | {pc(v['precision'])} | {v['full_authority_n']} |" for s, v in U["states"].items() if v["n"]))
rows = []
for g, sub in C["breakdown"].items():
    for k, v in sub.items():
        o = v["op"]; db = v["decision_balanced"]
        rows.append(f"| {g} | {k} | {v['n']} | {o['balanced']:.3f} ({o['score_of_10']}/10) | {p1(o['harmful_rate'])} | {'–' if db != db else f'{db:.3f}'} | " + " · ".join(f"{o['per_class'][n]['mean']:.2f}" if o['per_class'][n]['mean'] is not None else "–" for n in CL) + " |")
T["breakdown"] = "| Split (US core) | Group | n | Operational | Harmful | Decision-balanced (full authority) | Operational by class: clear · normal · stained · limited |\n|---|---|---:|---:|---:|---:|---|\n" + "\n".join(rows)
ready = D["ready_dev"] and C["READY_cert"]
md = f"""# Current Clarity Stage 15: Final Product Semantics

**Diagnostic only.**
- The frozen engine is unchanged: C-gbm is not refitted, and every Stage 14 engine file matches its hash.
- Production is unchanged, and nothing was deployed.
- No Sector field observation was used, and Michael's Guntersville survey was not touched.
- Water Temperature was not started.

**This is a re-score, not a blind certification.**
- The Stage 14 certification set was already unsealed and scored in Stage 14, and its findings motivated this stage.
- Every new threshold here comes from development rows only, and was frozen before the re-score.
- The readiness decision requires the development rows to pass as well, so the re-score cannot carry it alone.

{T['freeze']}

## The answer

**The semantics make the product more useful, but not yet safe enough to freeze.**
- **Clear-to-Normal works.** On development it raised the operational score from 0.667 to 0.690 and cut harmful answers
  from 21.8% to 17.3%, so it was adopted. On the re-score its answers are right 90% of the time, and Normal moves from
  NOT to PARTIAL.
- **The very-clear floor did not trigger.** Predictions above 10–15 ft are as precise as any others in log terms. The
  deep-water error is water being under-read, and a floor on the prediction cannot reach it.
- **Algal water keeps its state.** Flagged water is still classified right 77–79% of the time on development, so the
  frozen rule is a warning modifier, not softening or withholding.
- **Sentinel-2C becomes lower authority.** That costs 4% of the certification rows, but 34% of the 2025-dated ones.

**The new operational rubric:**
- **Score:** 7/10 on both development (0.688) and the re-score (0.690).
- **Readiness to freeze is NO**, by the frozen rule, for two reasons:
  - harmful wrong answers are 15.6% on the re-score and 16.6% on development, against ≤ 15%;
  - stained water scores 0.598 and 0.563, against ≥ 0.60.

  Everything else passes.

## 1. The product the frozen engine now gives

{T['states']}

Exact feet are still authorised for every class. The numeric prediction behind every row is the Stage 14 prediction,
unchanged.

## 2. Clear-to-Normal

{T['c2n']}

- **How the band was set.** Exactly as for the other two: within 5.00–6.94 ft, neither side of 6 ft is twice as likely as
  the other on development predictions.
- **What it fixes.** It replaces 52 of the 127 Stage 14 "Normal" answers and 39 "Clear" answers. Most of them (51 of
  91) were clear water read low.
- **What it leaves.** The plain "Normal" answer is now confined to 3.80–5.00 ft. It is still the weakest state (45%
  right), but it is issued 40% less often.

## 3. The very-clear floor: not adopted

{T['floor']}

- **The frozen trigger was not met.** It asked whether exact feet get worse above 10, 12 or 15 ft, measured among rows
  predicted that deep. They do not: median |log| is 0.13 at every threshold, against the 0.15 trigger, and predictions
  there are calibrated (truth − prediction −0.6 to +0.2 ft).
- **The −2.3 ft clear bias comes from somewhere else.** Very clear water is predicted too low. Of the development rows
  ≥ 20 ft, 82% are predicted at 12 ft or more (median 15.5 ft), and the rest are predicted lower still.
- **A floor would make the clear exact feet worse, not better.** A 12 ft floor would hide the well-predicted high rows
  and leave the under-read ones published: the clear median moves from −1.75 to −2.21 ft (development).
- **A "12+ ft" display would still be honest,** and remains an optional UX choice for Michael. 69% of predictions
  ≥ 12 ft are truly ≥ 12 ft on development (78% on the re-score), and 94–96% are clear. It is a display choice, not
  something the accuracy evidence requires.

## 4. Algal water

{T['algal']}

**The detection.** It is the existing satellite flag, NDCI > 0.03, on the answering reflectance.
- On development it catches 70% of in-situ algal water (chlorophyll ≥ 15 µg/L), with 54% precision.
- On the re-score it catches 84%.

**The frozen rule chose "modifier" at both levels.** The states issued to flagged water are right 79% (moderate) and
77% (strong) of the time on development. So the product shows:

| What the bowfisher sees (example) |
|---|
| **Normal-to-Stained · ~2.8 ft visibility** |
| Algal water detected — elevated uncertainty |

**Why Stage 14's "algae NOT" stands.** That verdict measures in-situ algal water against a constant answer: the engine
is not *better* than always guessing "Stained-to-Limited" there. It is not wrong more often than elsewhere. The modifier
tells the bowfisher what kind of water it is, without claiming more.

## 5. Sentinel-2C: lower authority (temporary)

{T['s2c']}

- **The rule.** S2C answers keep their state and lose full authority, and their exact feet and interval are withheld. No
  bias correction was fitted.
- **The evidence.** Development S2C rows read only 0.05 log low (n 38), but independent certification rows read 0.19 low
  (n 23). Neither sample is large enough to calibrate from.
- **When it lifts.** At least 60 independent S2C certification rows with |median signed log| ≤ 0.05, and decision
  quality within 0.05 of S2A/S2B.
- **The cost.** Small on this historical set, but S2C is about a third of current-era scenes. Until the rule lifts, a
  third of today's answers would carry "lower authority".

## 6. Tier 3 (unchanged)

On the re-score, Sen2Cor-C3 issued a lower-authority "Clear" for 59 of the 116 tier-3 rows, right 78% of the time. The
other 57 were Unknown. 23 of those withheld an answer that would have been right; 34 withheld a wrong one or had nothing
to say. Coverage was not traded for correctness.

## 7. The operational rubric (frozen before the re-score)

**The question it answers:** would this output help a bowfisher make the right visibility decision, without claiming
more than the satellite supports?

{T['outcomes']}

{T['op']}

**Each layer's effect, on development:**

{T['steps']}

**Where the harmful answers come from** (re-score; development shows the same pattern):
- plain "Normal" (38; 21 of them truly clear);
- "Normal-to-Stained" on limited water (18);
- "Clear" on normal water (19);
- plain "Stained" (18).

**The tiers differ.** Tier-2 (relaxed-mask) answers are harmful 29% of the time, against 16% at tier 1.

## 8. The re-score, every rubric side by side

{T['rubrics']}

{T['caps']}

{T['statesfreq']}

**Splits:**

{T['breakdown']}

- **Cool-season water now scores better than warm** (0.75 against 0.66). Clear-to-Normal absorbs the cool-season
  clear-water under-read that Stage 14 found.
- **S2C and tier 3 score lower by construction.** Their answers are lower authority, or Unknown.
- **SYKE** (Finland, out of domain) scores {C['SYKE']['op']['balanced']:.3f} ({C['SYKE']['op']['score_of_10']}/10) and stays out of every verdict.

## 9. Ready to freeze?

**NO, by the frozen rule.**

| Criterion | Development | Re-score | Bar |
|---|---|---|---|
| Engine unchanged | yes | yes | yes |
| Operational capability | {dv['score_of_10']}/10 | {op['score_of_10']}/10 | ≥ 7/10 |
| Every class ≥ 0.60 | **no** (stained {dv['per_class']['stained']['mean']:.3f}) | **no** (stained {op['per_class']['stained']['mean']:.3f}) | ≥ 0.60 |
| Harmful rate | **{p1(dv['harmful_rate'])}** | **{p1(op['harmful_rate'])}** | ≤ 15% |
| Severe rate | {p1(dv['severe_rate'])} | {p1(op['severe_rate'])} | ≤ 2% |

- **How close it is.** The misses are narrow: 0.6 and 1.6 points of harmful rate, and 0.002 and 0.037 of stained
  score. All of it comes from the same place, plain single-class answers next to a boundary.
- **No further tuning here.** The obvious next rules, such as dropping the plain "Normal" and "Stained" states or
  lowering tier 2's authority, would have to be pre-registered on development data. They would then need a test on data
  no stage has seen. The Stage 14 set has now been used twice and can no longer certify anything.
- **What this does not change.** It does not move product readiness. That stays 2/10 as deployed, because production is
  unchanged.

## 10. Remaining blockers

1. **Harmful answers next to boundaries** (15.6% / 16.6%). Mostly plain "Normal" (3.80–5.00 ft), plain "Stained"
   (2.38–2.63 ft), and Clear/Normal confusions. Candidate rules (no plain single state inside a boundary zone; tier 2 at
   lower authority) need pre-registration and fresh data.
2. **Stained water** sits at 0.56–0.60 against the 0.60 bar. It is the retrieval-resolution limit found in Stage 13.
3. **No unseen certification data remains.** The P2 fresh pool, Michael's Guntersville survey, or a TVA/USACE records
   request are the only ways to test any further rule.
4. **Sentinel-2C** stays lower authority, about a third of current-era scenes, until ≥ 60 independent S2C rows pass.
5. **Michael's ship decision,** and the deep-water clear under-read, which is a retrieval limit no display rule fixes.
6. **Bottom-risk** still needs depth.

## Files

Everything is in `scratchpad/stage15/`:

| Path | Contents |
|---|---|
| `PREREGISTRATION_STAGE15.md`, `FREEZE_STAGE15.json` | The frozen rules and every hash |
| `engine/engine15.py`, `engine/semantics15.json` | The product layer over the unchanged Stage 14 engine |
| `analysis/lib15.py` | States, authority, display and the operational scorer |
| `analysis/dev15.py`, `dev15.json`, `floor_diag15.json` | The development derivation and evaluation |
| `analysis/cert15.py`, `cert15.json` | The re-score of the Stage 14 certification set |

---

FROZEN ENGINE CHANGED: NO
CLEAR-TO-NORMAL STATE ADOPTED: YES (band {b['6ft'][0]:.2f}–{b['6ft'][1]:.2f} ft from development 2:1 odds; development operational 0.667 → 0.690 and harmful 21.8% → 17.3%; re-score: right {pc(C['clear_to_normal']['precision'])} of {C['clear_to_normal']['n']} answers, normal NOT → PARTIAL)
VERY-CLEAR FLOOR: Not adopted. The frozen trigger (median |log| > 0.15 among predictions ≥ 10/12/15 ft) is not met: about 0.13 at every threshold. The deep-water error is under-reading, which a floor on the prediction cannot fix, and a 12 ft floor would worsen the clear exact feet (−1.75 → −2.21 ft). A "12+ ft" display would be honest (69% on development, 78% on the re-score) and remains an optional UX choice, not an accuracy rule
ALGAL PRODUCT BEHAVIOR: When NDCI > 0.03, the state is kept at full authority, visibility is shown as "~X ft", and "Algal water detected — elevated uncertainty" is attached. It is not softened or withheld, because flagged-water states are right 77–79% of the time on development (74–78% on the re-score)
S2C PRODUCT AUTHORITY: Lower authority. The state is shown; exact feet and the interval are withheld; there is no recalibration. It lifts once ≥ 60 independent S2C certification rows show |median signed log| ≤ 0.05. The cost is 4% of certification rows but 34% of 2025-dated rows
EXACT-FEET CERTIFIED CAPABILITY: {U['EXACT_FEET']['score_of_10']}/10 (re-score of the already-seen Stage 14 set; clear PARTIAL at −2.3 ft; normal, stained, limited and sediment SUPPORTED)
BOUNDARY-AWARE CERTIFIED CAPABILITY: {U['PRODUCT']['score_of_10']}/10 ({U['PRODUCT']['points_of_7']} of 7, up from 2.5: normal NOT → PARTIAL; decision-balanced 0.726 → {U['decision_balanced']:.3f}; re-score, not blind)
OPERATIONAL BOWFISHING CLARITY CAPABILITY: {op['score_of_10']}/10 (re-score {op['balanced']:.3f}, development {dv['balanced']:.3f}; harmful {p1(op['harmful_rate'])} / {p1(dv['harmful_rate'])}, severe {p1(op['severe_rate'])} / {p1(dv['severe_rate'])})
CURRENT CLARITY READY TO FREEZE AND MOVE TO WATER TEMP: {'YES' if ready else 'NO'} (frozen rule: harmful answers {p1(op['harmful_rate'])} on the re-score and {p1(dv['harmful_rate'])} on development, against ≤ 15%; stained {op['per_class']['stained']['mean']:.3f} / {dv['per_class']['stained']['mean']:.3f} against ≥ 0.60; every other criterion passes)
REMAINING BLOCKERS: (1) harmful answers next to boundaries, mostly plain "Normal" (3.80–5.00 ft), plain "Stained" and Clear/Normal confusions, plus 29% harmful at tier 2; candidate rules need pre-registration and unseen data; (2) stained water at the retrieval-resolution limit (0.56–0.60); (3) no unseen certification data remains: the P2 fresh pool, the Guntersville survey or a TVA/USACE request are needed; (4) Sentinel-2C at lower authority, about a third of current-era scenes, until ≥ 60 independent rows pass; (5) Michael's ship decision, and the deep-water clear under-read, which is a retrieval limit; (6) bottom-risk needs depth
"""
open(f"{S}/stage15/CURRENT_CLARITY_STAGE15_FINAL_PRODUCT_SEMANTICS.md", "w", encoding="utf-8").write(md)
head, sep, tail = md.rpartition("\n---\n")
open(f"{S}/stage15/_print.md", "w", encoding="utf-8").write(head + sep + "\n" + "\n\n".join(l for l in tail.strip().split("\n") if l.strip()) + "\n")
print("ok", len(md), "ready", ready)
