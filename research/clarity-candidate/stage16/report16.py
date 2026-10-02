"""Build CURRENT_CLARITY_STAGE16_FRESH_RELIABILITY_VALIDATION.md from the frozen Stage 16 JSONs."""
import json
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = json.load(open(f"{S}/stage16/analysis/dev16.json")); O = json.load(open(f"{S}/stage16/analysis/score16.json"))
F = json.load(open(f"{S}/stage16/FREEZE_STAGE16.json")); R = json.load(open(f"{S}/stage16/engine/rule16.json"))
PO = json.load(open(f"{S}/stage16/fresh/fresh_pool.json")); FS = json.load(open(f"{S}/stage16/fresh/fresh_sample.json")); DF = json.load(open(f"{S}/stage16/analysis/dev16_feet.json"))
A = O["ALL"]; op = A["op"]; dv = D["final"]; s15 = D["stage15"]; CL = ["clear", "normal", "stained", "limited"]
p1 = lambda v: f"{100 * v:.1f}%"; f3 = lambda v: "–" if v is None else f"{v:.3f}"; pc = lambda v: "–" if v is None else f"{v:.0%}"
T = {}
T["freeze"] = ("| Step | UTC | What was fixed |\n|---|---|---|\n"
               f"| Pre-registration | {F['prereg_frozen_utc']} | Gate method, tier-2 options, selection rule, fresh-test protocol, minima, scores, bars (`PREREGISTRATION_STAGE16.md`, `{F['files']['stage16/PREREGISTRATION_STAGE16.md'][:8]}…`) |\n"
               f"| Gate and tier-2 rule | {F['rule_frozen_utc']} | Thresholds and posteriors from development rows only (`engine/rule16.json`, `{F['files']['stage16/engine/rule16.json'][:8]}…`) |\n"
               f"| Fresh sample | {F['fresh_sample_frozen_utc']} | `fresh/fresh_sample.csv` (`{F['files']['stage16/fresh/fresh_sample.csv'][:8]}…`), built value-blind |\n"
               f"| ACOLITE results | {F['aco_results_frozen_utc']} | `fresh/aco_manifest_fresh.txt` |\n"
               f"| Unsealed | {F['unsealed_utc']} | Fresh Secchi, turbidity and chlorophyll (`fresh/truth16.json`, `{F['files']['stage16/fresh/truth16.json'][:8]}…`) |")
T["zones"] = "| Prediction (tier 1) | Issued state |\n|---|---|\n" + "\n".join(
    f"| {z[0]:.2f} ft{(' to ' + format(D['zones_tier1_ft'][i + 1][0], '.2f') + ' ft') if i + 1 < len(D['zones_tier1_ft']) else ' and up'} | {z[1]} |" for i, z in enumerate(D["zones_tier1_ft"]))
T["gate"] = ("| Development (nested lake-held-out) | Stage 15 semantics | **Stage 16 gate** |\n|---|---:|---:|\n"
             f"| Operational (class-balanced) | {s15['bal']:.3f} | **{dv['balanced']:.3f}** ({dv['score_of_10']}/10) |\n"
             f"| Harmful | {p1(s15['harm'])} | **{p1(dv['harmful_rate'])}** |\n| Severe | {p1(s15['sev'])} | **{p1(dv['severe_rate'])}** |\n" +
             "\n".join(f"| {n.capitalize()} | {s15['per_class'][n]:.3f} | **{dv['per_class'][n]['mean']:.3f}** |" for n in CL))
T["devstates"] = "| State issued (development) | n | Right |\n|---|---:|---:|\n" + "\n".join(f"| {s} | {n} | {pc(D['state_precision'].get(s))} |" for s, n in sorted(D["state_counts"].items(), key=lambda kv: -kv[1]))
t2 = D["tier2_options"]; lab = {"T2-A": "Full authority, tier-1 posteriors", "T2-B": "Full authority, tier-2 posteriors", "T2-C": "Lower authority", "T2-D": "Boundary states only (tier-2 posteriors), else Unknown"}
T["tier2"] = ("| Tier-2 option (at τ₁ = τ₂ = 0.70, development) | Operational | Overall harmful | Tier-2 harmful |\n|---|---:|---:|---:|\n" +
              "\n".join(f"| {'**' if o == R['t2opt'] else ''}{o}: {lab[o]}{'**' if o == R['t2opt'] else ''} | {g['bal']:.3f} | {p1(g['harm'])} | {p1(g['tier2_harm'])} |" for o, g in t2.items()))
T["pool"] = ("| Fresh pool step (value-blind) | Count |\n|---|---:|\n"
             f"| WQP Secchi rows dated 2026, fetched 2026-10-01 | {PO['rows_read']:,} |\n| … at sites in an earlier development/certification file (excluded) | {PO['excluded'].get('site in an earlier file', 0):,} |\n"
             f"| Eligible site-days | {PO['eligible_site_days']:,} |\n| One per site-month | {PO['events_after_site_month']:,} ({PO['sites']} sites, {PO['lakes']} lakes; Wisconsin {PO['states'].get('WI', 0)}) |\n"
             f"| Clear pass within ±1 day (≤ 20% cloud) | {PO['prescreen_passed']} |\n| Matched (≥ 5 valid pixels) | {FS['matched']} |\n| **Fresh sample (≤ 3 per lake)** | **{FS['after_lake_cap']}** at {FS['lakes']} lakes |\n"
             f"| … Wisconsin | {FS['states'].get('WI', 0)} ({FS['wisconsin_share']:.0%}) |\n| … Sentinel-2C | {FS['platforms'].get('sentinel-2c', 0)} ({FS['platforms'].get('sentinel-2c', 0) / FS['after_lake_cap']:.0%}) |\n| … lake-independent (strict) | {FS['strict']} |")
cnt = A["classes"]; MIN = O["minima"]
T["minima"] = ("| Core class | Fresh n | Minimum (pre-registered) | |\n|---|---:|---:|---|\n" +
               "\n".join(f"| {k.capitalize()} | {cnt.get(k, 0)} | {v} | {'met' if cnt.get(k, 0) >= v else '**INSUFFICIENT**'} |" for k, v in MIN.items()) +
               f"\n| Scored rows | {O['n_scored']} | 200 | {'met' if O['n_scored'] >= 200 else '**INSUFFICIENT**'} |")
s15f = A["stage15_semantics"]
T["fresh"] = ("| Fresh holdout (one scoring) | Stage 15 semantics (comparison) | **Stage 16 product** |\n|---|---:|---:|\n"
              f"| Operational (class-balanced) | {s15f['balanced']:.3f} | **{op['balanced']:.3f}** ({op['score_of_10']}/10) |\n"
              f"| Harmful | {p1(s15f['harmful_rate'])} | **{p1(op['harmful_rate'])}** |\n| Severe | {p1(s15f['severe_rate'])} | **{p1(op['severe_rate'])}** |\n" +
              "\n".join(f"| {n.capitalize()} (n {op['per_class'][n]['n']}) | {f3(s15f['per_class'][n]['mean'])} | **{f3(op['per_class'][n]['mean'])}** |" for n in CL))
oc = op["outcomes"]; tot = sum(oc.values())
T["outcomes"] = "| Outcome (fresh) | Rows | Share |\n|---|---:|---:|\n" + "\n".join(f"| {l} | {oc.get(k, 0)} | {oc.get(k, 0) / tot:.0%} |" for k, l in (
    ("correct_single", "Correct single state"), ("correct_boundary", "Correct boundary state"), ("lower_correct", "Correct lower-authority answer"), ("lower_wrong", "Wrong lower-authority answer"),
    ("unknown_appropriate", "Appropriate Unknown"), ("unknown_missed_right", "Unknown that withheld a right answer"), ("harmful", "**Harmful wrong answer**")))
T["freshstates"] = "| State issued (fresh) | n | Right |\n|---|---:|---:|\n" + "\n".join(f"| {s} | {v['n']} | {pc(v['right'])} |" for s, v in sorted(A["states"].items(), key=lambda kv: -kv[1]["n"]))
rows = []
for g, sub in O["breakdown"].items():
    for k, v in sub.items():
        rows.append(f"| {g} | {k} | {v['n']} | {v['op']['balanced']:.3f} | {p1(v['op']['harmful_rate'])} | " + ", ".join(f"{c} {n}" for c, n in v["classes"].items()) + " |")
T["breakdown"] = "| Split (fresh) | Group | n | Operational | Harmful | Classes |\n|---|---|---:|---:|---:|---|\n" + "\n".join(rows)
ef = A["exact_feet"]; dfe = DF["exact_feet"]
T["feet"] = ("| Exact feet (Stage 12 rubric) | Fresh: published (coverage), signed | Fresh verdict | Development verdict (Stage 16 semantics) |\n|---|---|---|---|\n" +
             "\n".join(f"| {k.capitalize()} | " + (f"{ef[k]['n_published']} ({ef[k]['coverage']:.0%}), {ef[k]['median_signed_ft']:+.1f} ft" if ef[k].get("n_published") else "–") + f" | {ef[k]['verdict']} | {dfe[k]['verdict']} |" for k in CL + ["algae", "sediment", "bottom-risk"]) +
             f"\n| **Score** | | **{A['EXACT_FEET']['score_of_10']}/10** | **{DF['EXACT_FEET']['score_of_10']}/10** |")
ev, devv = A["evidence"], D["evidence"]
bars = {"strong": 0.90, "moderate": 0.80, "weak": 0.65}
T["si"] = ("| Sector Intelligence evidence | Rule | Development share / truth in answer | Fresh n / share / truth in answer | Bar | Fresh verdict |\n|---|---|---|---|---:|---|\n" +
           "\n".join(f"| **{e.capitalize()}** | {rule} | {pc(devv.get(e, {}).get('share'))} / {pc(devv.get(e, {}).get('containment'))} | {ev.get(e, {}).get('n', 0)} / {pc(ev.get(e, {}).get('share'))} / {pc(ev.get(e, {}).get('containment'))} | "
                     + (f"{bars[e]:.2f}" if e in bars else "–") + " | " + ("–" if e not in bars else ("INSUFFICIENT (n < 30)" if ev.get(e, {}).get("n", 0) < 30 else ("met" if ev[e]["containment"] >= bars[e] else "**missed**"))) + " |"
                     for e, rule in (("strong", "full authority, tier 1, not S2C, no algal flag, posterior ≥ 0.90"), ("moderate", "other full-authority answers"),
                                     ("weak", "lower authority (tier 3, S2C)"), ("unavailable", "Unknown"))))
st = O["stretch"]
T["stretch"] = ("| Stretch target (true 9/10) | Development | Fresh | Target |\n|---|---|---|---|\n"
                f"| Operational | {dv['balanced']:.3f} | {op['balanced']:.3f} | ≥ 0.85 |\n| Weakest class | {min(v['mean'] for v in dv['per_class'].values()):.3f} | {min(v['mean'] for v in op['per_class'].values()):.3f} | ≥ 0.80 |\n"
                f"| Harmful | {p1(dv['harmful_rate'])} | {p1(op['harmful_rate'])} | ≤ 5% |\n| Severe | {p1(dv['severe_rate'])} | {p1(op['severe_rate'])} | ≤ 0.5% |\n"
                f"| Strong evidence | {pc(devv['strong']['share'])} | {pc(ev.get('strong', {}).get('share'))} | ≥ 50% |")
se = O["s2c_evidence"]
md = f"""# Current Clarity Stage 16: Fresh Reliability Validation

**Diagnostic only.**
- The frozen engine is unchanged: no refit, every Stage 14/15 file matches its hash, and no model coefficient changed.
- Production is unchanged, and nothing was deployed.
- Excluded from every step:
  - Michael's Guntersville survey and Sector field reports;
  - the Stage 14/15 certification set.
- Water Temperature stays paused.

**Freeze order** (sha256 values in `FREEZE_STAGE16.json`):

{T['freeze']}

## The answer

**The reliability gate removes most of the harmful answers. The fresh holdout is too small to certify it.**

- **On development, the gate cuts harmful answers.** A state is issued only when its calibrated posterior is at least
  70%. That takes harmful answers from 16.6% to **10.6%** and severe ones from 2.0% to 1.5%, with the operational score
  steady at 7/10.
- **The gate never issues a plain "Normal" or "Stained".** Neither ever reaches 70% confidence, so the evidence removed
  them, not a hand-written rule.
- **Tier 2 is now boundary states only.** Its harmful rate on development falls from 12% (Stage 15) to 7%. The Stage 15
  re-score had shown 29%.
- **Stained water still scores 0.571 on development,** below the 0.60 bar. No threshold choice fixes it, because it is
  the retrieval-resolution limit.

**The fresh holdout is all of the P2 pool that exists today.** It is 2026 WQP data at sites no stage has touched, and
it yields only **108 observations**:
- 88% of them are from Wisconsin, 53% are Sentinel-2C and 69% are clear water;
- normal (19 of 40), stained (9 of 60), limited (6 of 25) and the total (108 of 200) are all **INSUFFICIENT**.

**What the 108 rows show:**
- **Score.** 7/10 operational, with one harmful answer (0.9%). The Stage 15 semantics on the same rows had 4.6%
  harmful.
- **Why harm is so low.** Half the rows are Sentinel-2C at lower authority, and those cannot be harmful by
  construction.

**The verdicts:**
- **Exact feet** score 2/10 on the fresh set, mostly because S2C feet are withheld.
- **Sector Intelligence: NO.** Only 5 answers qualify as strong evidence (30 needed).
- **Readiness to freeze is NO** for two reasons:
  - the fresh minima are not met;
  - development stained misses 0.60.

## 1. The single-state reliability gate (development only)

**The posterior model.**
- **The fits.** Three monotone logistics give P(truth ≥ 6, 3, 2 ft | prediction).
- **The class posteriors** follow from their differences.
- **Fitting.** Nested in folds for evaluation; on all development lake-held-out predictions for production.

**The rule.** A single state requires a posterior ≥ τ₁; otherwise the best adjacent pair requires ≥ τ₂; otherwise
Unknown.
- **The search.** A pre-registered grid of 128 τ₁ × τ₂ × tier-2 combinations.
- **No combination met the primary constraints** (harmful ≤ 12%, severe ≤ 1.5%, every class ≥ 0.60), because stained
  stays below 0.60 everywhere.
- **The fallback rule** (the best score with harmful ≤ 15% and severe ≤ 2%) chose **τ₁ = τ₂ = {R['t1']:.2f}** with
  tier-2 option **{R['t2opt']}**.

{T['gate']}

**What the frozen rule issues at tier 1:**

{T['zones']}

{T['devstates']}

- **Plain states left.** The only plain states it ever issues are Clear (above 7.40 ft) and Limited (below 1.55 ft).
- **Where it says Unknown.** Between 2.43 and 2.80 ft, where neither boundary pair reaches 70%. That is 93 tier-1
  development answers (6%); with tier 3's Unknowns, Unknown is 13% of all answers.

## 2. Tier-2 authority (development only)

{T['tier2']}

**The selected option is boundary-only.** Tier-2 answers get posteriors calibrated on tier-2 rows, issue only boundary
states, and are Unknown below 70%.
- **The effect.** Tier-2 harmful on development falls from 12% (Stage 15 semantics) to 7%, at the best operational
  score of the four options.
- **The alternative.** Making tier 2 "lower authority" would remove its harm entirely but lower the score. The
  pre-registered rule preferred correctness through calibration, not flags.

## 3. Sentinel-2C (unchanged)

The temporary lower-authority rule stays, with no recalibration. The fresh holdout adds independent S2C evidence:
- **Fresh rows.** {se['n_tiers12']} S2C rows at tiers 1–2, median signed log **{se['median_signed_log']:+.3f}** against
  {se['s2ab_median_signed_log']:+.3f} for S2A/S2B in the same months.
- **Combined.** With Stage 14's 23 certification rows (−0.19), that makes 68 independent S2C rows.
- **The lift criterion is not met:** ≥ 60 rows with |median signed log| ≤ 0.05. S2C still reads low, by about 0.04 log
  more than S2A/S2B on fresh water.

## 4. The fresh holdout

**Sources.**
- **The pull.** WQP "Depth, Secchi disk depth" at lake, reservoir and impoundment sites, dated 2026-01-01 to
  2026-09-28. It was re-fetched on 2026-10-01 with the unchanged Stage 1 downloader and cleaning; only the start date
  changed.
- **WQP had published nothing new since 27 September:** 4,773 rows both times.

**Exclusions.**
- Any site in an earlier development or certification file;
- the Guntersville box;
- censored readings.

**The lake rule.** It is the Stage 10 P2 definition: sites in no earlier file. The strict lake-independent subset is
reported apart.

{T['pool']}

{T['minima']}

**The verdict is INSUFFICIENT.** The minima were fixed before any value was read and are not lowered. Everything below
the minima table is reported as information only.

## 5. What the fresh rows show (information; not verdict-bearing for the short classes)

{T['fresh']}

{T['outcomes']}

{T['freshstates']}

{T['breakdown']}

- **Where the gate helps.** On the same rows, the Stage 15 semantics gave 4.6% harmful. The gate gives 0.9%, the single
  harmful answer being a tier-2 Normal-to-Stained on 1.6 ft water.
- **Why it is not a clean test.** 53% of the rows are Sentinel-2C, at lower authority, so they can never be harmful; and
  88% are Wisconsin, mostly clear water.
- **The strict lake-independent subset** (22 rows) scores 0.746 with no harmful answer.

## 6. Exact feet

{T['feet']}

- **Feet accuracy is not the problem.** The fresh 2/10 comes from coverage. Exact feet are withheld on Sentinel-2C
  (53% of fresh rows), and three classes are short. Where feet are shown (non-S2C), the error is ×1.32 with a median
  −0.6 ft.
- **On development,** under the same semantics, exact feet score 7/10. That is one point lower than Stage 14, because
  Unknown now withholds feet.

## 7. Sector Intelligence suitability

{T['si']}

**SAFE FOR SECTOR INTELLIGENCE: {O['SAFE_SI']}**, by the pre-registered rule: the strong level has only
{ev.get('strong', {}).get('n', 0)} fresh answers, against 30 needed. On the rows available:
- moderate evidence was right 97% of the time;
- weak evidence was right 85% of the time.

Development shows the shape a feed would have: strong 10% (right 97%), moderate 70% (85%), weak 7% (85%), unavailable
13%.

## 8. Ready to freeze?

| Criterion (unchanged from Stage 15) | Development | Fresh | Bar |
|---|---|---|---|
| Core minima met | n/a | **no** (normal, stained, limited, total) | all |
| Operational | {dv['score_of_10']}/10 | {op['score_of_10']}/10 | ≥ 7/10 |
| Every core class ≥ 0.60 | **no** (stained {dv['per_class']['stained']['mean']:.3f}) | (normal {op['per_class']['normal']['mean']:.3f}; short classes insufficient) | ≥ 0.60 |
| Harmful | {p1(dv['harmful_rate'])} | {p1(op['harmful_rate'])} | ≤ 15% |
| Severe | {p1(dv['severe_rate'])} | {p1(op['severe_rate'])} | ≤ 2% |

**READY TO FREEZE CLARITY AND START WATER TEMPERATURE: NO.**
- **What it now meets.** On development the gate meets the harmful and severe bars for the first time: 10.6% and 1.5%.
- **What still fails:**
  - stained water stays at 0.571;
  - the fresh holdout cannot certify anything until it is about twice as large overall, and several times larger in
    stained and limited water.

## 9. Stretch target: a true 9/10 product

{T['stretch']}

## 10. The shortage, and the sources that would complete it

**The size of the gap.**
- **The pool.** All 2026 WQP data at untouched sites gives 1,111 events, but only 108 matched observations. Of those,
  9 are stained and 6 limited, against minima of 60 and 25.
- **What would close it.** At this yield (about 10% of events match, and 8% of matches are stained), 60 stained rows
  need about 7,500 eligible events, roughly 7× today's pool, in murkier water than Wisconsin's.

**Independent sources that would close it**, all before anyone looks at the values:
1. **The 2026 agency data not yet in WQP.** Many states upload a season's data the following spring: FL LAKEWATCH,
   MN PCA, TCEQ, ADEM, Iowa DNR. A re-pull in about April 2027, under this same frozen protocol, is the cheapest route.
2. **Southern reservoir agencies, by direct request.** TVA Reservoir Ecological Health monitoring, and USACE district
   water-quality programs (Nashville, Mobile, Vicksburg, Tulsa, Fort Worth). This is where stained and limited water
   lives.
3. **State reservoir programs with their own portals:** Oklahoma OWRB BUMP, Missouri LMVP, Texas SWQMIS, Iowa AQuIA,
   Illinois VLMP.

## 11. Path from the current score to a true 9/10

**The arithmetic.** A product whose every answer is a correct boundary state scores 0.90, so 9/10 (≥ 0.85
class-balanced) needs about 90% of every class answered correctly at full authority. Today that is 0.69–0.71. Four
things stand in the way:
1. **Resolution.** Stained water (2–3 ft) is narrower than the retrieval error (×1.36), so stained answers are mostly
   boundary states or Unknown (0.57 development). A 9/10 needs more information per answer than one scene can give,
   such as multi-scene consensus or a later design that assimilates field reports. That means reopening model work
   with a new pre-registration.
2. **Authority.** Lower-authority answers cap at 0.75 and Unknown at 0.5. Sentinel-2C is a third of current scenes (53%
   of 2026 matches), and it needs to pass its lift criterion: more tandem pairs, and S2C harmonisation re-derived
   against the low bias now seen on both independent sets.
3. **Evidence.** A fresh holdout of ≥ 200 rows with ≥ 60 stained (section 10) is needed to certify any of this.
4. **Strong evidence** is 5–10% of answers. Sector Intelligence would need most answers at that level.

## Files

Everything is in `scratchpad/stage16/`:

| Path | Contents |
|---|---|
| `PREREGISTRATION_STAGE16.md`, `FREEZE_STAGE16.json` | The frozen plan and every hash, in order |
| `engine/engine16.py`, `engine/rule16.json` | The gate and tier-2 rule over the unchanged engine |
| `analysis/lib16.py`, `dev16.py`, `dev16.json` | The posterior gate and its development derivation |
| `fresh/` | The fresh WQP pull (`wqp/`), value-blind index, prescreen, matches, `fresh_sample.csv`, ACOLITE results, `truth16.json` |
| `analysis/score16.py`, `score16.json` | The one-time fresh score |

---

FROZEN ENGINE CHANGED: NO
SINGLE-STATE RELIABILITY GATE: Posterior gate. A single state needs a ≥ {R['t1']:.0%} calibrated posterior and a boundary pair ≥ {R['t2']:.0%}; otherwise Unknown. It was fitted on development only. It never issues plain Normal or Stained (zones: Limited < 1.55 ft, Stained-to-Limited, Unknown 2.43–2.80 ft, Normal-to-Stained, Clear-to-Normal 4.11–7.40 ft, Clear above). Development harmful 16.6% → 10.6%, severe 2.0% → 1.5%
TIER-2 AUTHORITY RULE: Boundary states only, with tier-2-calibrated posteriors; Unknown below 70%. Tier-2 harmful on development 12% → 7% (the Stage 15 re-score had shown 29%)
FRESH HOLDOUT SAMPLE SIZE: {O['n_scored']} observations at {FS['lakes']} lakes ({FS['wisconsin_share']:.0%} Wisconsin, {FS['platforms'].get('sentinel-2c', 0)} Sentinel-2C). INSUFFICIENT: normal {cnt.get('normal', 0)}/40, stained {cnt.get('stained', 0)}/60, limited {cnt.get('limited', 0)}/25, total {O['n_scored']}/200 (clear {cnt.get('clear', 0)}/40 met)
HARMFUL RATE: {p1(op['harmful_rate'])} on the fresh holdout (1 of {O['n_scored']}; insufficient, and S2C rows are lower authority so cannot be harmful); {p1(dv['harmful_rate'])} on development
SEVERE RATE: {p1(op['severe_rate'])} on the fresh holdout; {p1(dv['severe_rate'])} on development
CLEAR SCORE: {op['per_class']['clear']['mean']:.3f} fresh (n {op['per_class']['clear']['n']}); {dv['per_class']['clear']['mean']:.3f} development
NORMAL SCORE: {op['per_class']['normal']['mean']:.3f} fresh (n {op['per_class']['normal']['n']}, insufficient); {dv['per_class']['normal']['mean']:.3f} development
STAINED SCORE: {op['per_class']['stained']['mean']:.3f} fresh (n {op['per_class']['stained']['n']}, insufficient); {dv['per_class']['stained']['mean']:.3f} development (below 0.60)
LIMITED SCORE: {op['per_class']['limited']['mean']:.3f} fresh (n {op['per_class']['limited']['n']}, insufficient); {dv['per_class']['limited']['mean']:.3f} development
EXACT-FEET CAPABILITY: {A['EXACT_FEET']['score_of_10']}/10 on the fresh holdout (S2C feet withheld on 53% of rows; three classes insufficient; where shown, ×1.32 and −0.6 ft); {DF['EXACT_FEET']['score_of_10']}/10 on development under Stage 16 semantics
OPERATIONAL BOWFISHING CLARITY: {op['score_of_10']}/10 on the fresh holdout ({op['balanced']:.3f}; insufficient for normal, stained and limited); {dv['score_of_10']}/10 on development ({dv['balanced']:.3f})
SAFE FOR SECTOR INTELLIGENCE: {O['SAFE_SI']} (only {ev.get('strong', {}).get('n', 0)} strong-evidence answers against the 30 needed; moderate evidence 97% and weak 85% right on the rows available)
READY TO FREEZE CLARITY AND START WATER TEMPERATURE: NO (fresh minima not met; development stained {dv['per_class']['stained']['mean']:.3f} < 0.60; harmful and severe now pass on development)
PATH FROM CURRENT SCORE TO TRUE 9/10: (1) Certify first: a fresh holdout of ≥ 200 rows with ≥ 60 stained and ≥ 25 limited, from a WQP re-pull around April 2027 (2026 uploads) or direct TVA/USACE and state reservoir requests, under this frozen protocol. (2) Resolution: stained water is narrower than the ×1.36 retrieval error, so a 9/10 needs more information per answer (multi-scene consensus or field-report assimilation), which means reopening model work with a new pre-registration. (3) Authority: Sentinel-2C (a third of current scenes) must pass its lift criterion; it still reads low on both independent sets (−0.19 and −0.09 log), so it needs re-derived harmonisation from more tandem pairs. (4) Raise strong evidence from 5–10% toward half of all answers. Today: 0.69–0.71 class-balanced, against the 0.85 a 9/10 needs
"""
open(f"{S}/stage16/CURRENT_CLARITY_STAGE16_FRESH_RELIABILITY_VALIDATION.md", "w", encoding="utf-8").write(md)
head, sep, tail = md.rpartition("\n---\n")
open(f"{S}/stage16/_print.md", "w", encoding="utf-8").write(head + sep + "\n" + "\n\n".join(l for l in tail.strip().split("\n") if l.strip()) + "\n")
print("ok", len(md))
