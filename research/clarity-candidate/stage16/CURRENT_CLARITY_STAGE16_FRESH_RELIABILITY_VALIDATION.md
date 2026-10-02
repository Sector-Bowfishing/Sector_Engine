# Current Clarity Stage 16: Fresh Reliability Validation

**Diagnostic only.**
- The frozen engine is unchanged: no refit, every Stage 14/15 file matches its hash, and no model coefficient changed.
- Production is unchanged, and nothing was deployed.
- Excluded from every step:
  - Michael's Guntersville survey and Sector field reports;
  - the Stage 14/15 certification set.
- Water Temperature stays paused.

**Freeze order** (sha256 values in `FREEZE_STAGE16.json`):

| Step | UTC | What was fixed |
|---|---|---|
| Pre-registration | 2026-10-01T17:26:53Z | Gate method, tier-2 options, selection rule, fresh-test protocol, minima, scores, bars (`PREREGISTRATION_STAGE16.md`, `cf7a8d91…`) |
| Gate and tier-2 rule | 2026-10-01T17:28:55Z | Thresholds and posteriors from development rows only (`engine/rule16.json`, `ed1142fb…`) |
| Fresh sample | 2026-10-01T17:42:14Z | `fresh/fresh_sample.csv` (`02fbe25f…`), built value-blind |
| ACOLITE results | 2026-10-01T17:54:56Z | `fresh/aco_manifest_fresh.txt` |
| Unsealed | 2026-10-01T17:55:32Z | Fresh Secchi, turbidity and chlorophyll (`fresh/truth16.json`, `3b77ffe9…`) |

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
- **The fallback rule** (the best score with harmful ≤ 15% and severe ≤ 2%) chose **τ₁ = τ₂ = 0.70** with
  tier-2 option **T2-D**.

| Development (nested lake-held-out) | Stage 15 semantics | **Stage 16 gate** |
|---|---:|---:|
| Operational (class-balanced) | 0.688 | **0.693** (7/10) |
| Harmful | 16.6% | **10.6%** |
| Severe | 2.0% | **1.5%** |
| Clear | 0.848 | **0.880** |
| Normal | 0.690 | **0.643** |
| Stained | 0.563 | **0.571** |
| Limited | 0.652 | **0.676** |

**What the frozen rule issues at tier 1:**

| Prediction (tier 1) | Issued state |
|---|---|
| 0.50 ft to 1.55 ft | Limited |
| 1.55 ft to 2.43 ft | Stained-to-Limited |
| 2.43 ft to 2.57 ft | Unknown (Stained-to-Limited) |
| 2.57 ft to 2.80 ft | Unknown (Normal-to-Stained) |
| 2.80 ft to 4.11 ft | Normal-to-Stained |
| 4.11 ft to 7.40 ft | Clear-to-Normal |
| 7.40 ft and up | Clear |

| State issued (development) | n | Right |
|---|---:|---:|
| Clear | 531 | 89% |
| Clear-to-Normal | 397 | 89% |
| Normal-to-Stained | 215 | 78% |
| Unknown / Low Authority | 203 | – |
| Stained-to-Limited | 179 | 84% |
| Limited | 57 | 88% |

- **Plain states left.** The only plain states it ever issues are Clear (above 7.40 ft) and Limited (below 1.55 ft).
- **Where it says Unknown.** Between 2.43 and 2.80 ft, where neither boundary pair reaches 70%. That is 93 tier-1
  development answers (6%); with tier 3's Unknowns, Unknown is 13% of all answers.

## 2. Tier-2 authority (development only)

| Tier-2 option (at τ₁ = τ₂ = 0.70, development) | Operational | Overall harmful | Tier-2 harmful |
|---|---:|---:|---:|
| T2-A: Full authority, tier-1 posteriors | 0.683 | 10.7% | 8.4% |
| T2-B: Full authority, tier-2 posteriors | 0.692 | 11.0% | 10.5% |
| T2-C: Lower authority | 0.669 | 9.7% | 0.0% |
| **T2-D: Boundary states only (tier-2 posteriors), else Unknown** | 0.693 | 10.6% | 7.3% |

**The selected option is boundary-only.** Tier-2 answers get posteriors calibrated on tier-2 rows, issue only boundary
states, and are Unknown below 70%.
- **The effect.** Tier-2 harmful on development falls from 12% (Stage 15 semantics) to 7%, at the best operational
  score of the four options.
- **The alternative.** Making tier 2 "lower authority" would remove its harm entirely but lower the score. The
  pre-registered rule preferred correctness through calibration, not flags.

## 3. Sentinel-2C (unchanged)

The temporary lower-authority rule stays, with no recalibration. The fresh holdout adds independent S2C evidence:
- **Fresh rows.** 45 S2C rows at tiers 1–2, median signed log **-0.092** against
  -0.054 for S2A/S2B in the same months.
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

| Fresh pool step (value-blind) | Count |
|---|---:|
| WQP Secchi rows dated 2026, fetched 2026-10-01 | 4,773 |
| … at sites in an earlier development/certification file (excluded) | 3,278 |
| Eligible site-days | 1,486 |
| One per site-month | 1,111 (419 sites, 265 lakes; Wisconsin 926) |
| Clear pass within ±1 day (≤ 20% cloud) | 305 |
| Matched (≥ 5 valid pixels) | 126 |
| **Fresh sample (≤ 3 per lake)** | **108** at 80 lakes |
| … Wisconsin | 95 (88%) |
| … Sentinel-2C | 57 (53%) |
| … lake-independent (strict) | 22 |

| Core class | Fresh n | Minimum (pre-registered) | |
|---|---:|---:|---|
| Clear | 74 | 40 | met |
| Normal | 19 | 40 | **INSUFFICIENT** |
| Stained | 9 | 60 | **INSUFFICIENT** |
| Limited | 6 | 25 | **INSUFFICIENT** |
| Scored rows | 108 | 200 | **INSUFFICIENT** |

**The verdict is INSUFFICIENT.** The minima were fixed before any value was read and are not lowered. Everything below
the minima table is reported as information only.

## 5. What the fresh rows show (information; not verdict-bearing for the short classes)

| Fresh holdout (one scoring) | Stage 15 semantics (comparison) | **Stage 16 product** |
|---|---:|---:|
| Operational (class-balanced) | 0.667 | **0.709** (7/10) |
| Harmful | 4.6% | **0.9%** |
| Severe | 0.0% | **0.0%** |
| Clear (n 74) | 0.809 | **0.826** |
| Normal (n 19) | 0.576 | **0.529** |
| Stained (n 9) | 0.506 | **0.706** |
| Limited (n 6) | 0.775 | **0.775** |

| Outcome (fresh) | Rows | Share |
|---|---:|---:|
| Correct single state | 27 | 25% |
| Correct boundary state | 16 | 15% |
| Correct lower-authority answer | 47 | 44% |
| Wrong lower-authority answer | 8 | 7% |
| Appropriate Unknown | 5 | 5% |
| Unknown that withheld a right answer | 4 | 4% |
| **Harmful wrong answer** | 1 | 1% |

| State issued (fresh) | n | Right |
|---|---:|---:|
| Clear | 51 | 96% |
| Clear-to-Normal | 23 | 100% |
| Normal-to-Stained | 11 | 82% |
| Stained-to-Limited | 9 | 67% |
| Unknown / Low Authority | 9 | – |
| Limited | 5 | 60% |

| Split (fresh) | Group | n | Operational | Harmful | Classes |
|---|---|---:|---:|---:|---|
| platform | sentinel-2b | 43 | 0.691 | 2.3% | clear 32, limited 3, normal 5, stained 3 |
| platform | sentinel-2c | 57 | 0.657 | 0.0% | clear 38, normal 14, limited 1, stained 4 |
| tier | 1 | 86 | 0.776 | 0.0% | clear 58, limited 4, normal 17, stained 7 |
| tier | 3 | 17 | 0.387 | 0.0% | clear 14, stained 1, normal 2 |
| strict | same-lake | 86 | 0.689 | 1.2% | clear 65, limited 4, normal 12, stained 5 |
| strict | strict | 22 | 0.746 | 0.0% | clear 9, stained 4, limited 2, normal 7 |
| wisconsin | WI | 95 | 0.743 | 0.0% | clear 63, normal 19, limited 4, stained 9 |
| wisconsin | outside WI | 13 | 0.661 | 7.7% | clear 11, limited 2 |
| season | cool | 10 | 0.633 | 10.0% | clear 5, limited 2, stained 2, normal 1 |
| season | warm | 98 | 0.732 | 0.0% | clear 69, normal 18, limited 4, stained 7 |

- **Where the gate helps.** On the same rows, the Stage 15 semantics gave 4.6% harmful. The gate gives 0.9%, the single
  harmful answer being a tier-2 Normal-to-Stained on 1.6 ft water.
- **Why it is not a clean test.** 53% of the rows are Sentinel-2C, at lower authority, so they can never be harmful; and
  88% are Wisconsin, mostly clear water.
- **The strict lake-independent subset** (22 rows) scores 0.746 with no harmful answer.

## 6. Exact feet

| Exact feet (Stage 12 rubric) | Fresh: published (coverage), signed | Fresh verdict | Development verdict (Stage 16 semantics) |
|---|---|---|---|
| Clear | 34 (46%), -2.1 ft | NOT | PARTIAL |
| Normal | 3 (16%), +0.3 ft | NOT | SUPPORTED |
| Stained | 5 (56%), +0.8 ft | PARTIAL | PARTIAL |
| Limited | 5 (83%), +0.4 ft | SUPPORTED | SUPPORTED |
| Algae | – | NOT | SUPPORTED |
| Sediment | – | NOT | SUPPORTED |
| Bottom-risk | – | NOT | NOT |
| **Score** | | **2/10** | **7/10** |

- **Feet accuracy is not the problem.** The fresh 2/10 comes from coverage. Exact feet are withheld on Sentinel-2C
  (53% of fresh rows), and three classes are short. Where feet are shown (non-S2C), the error is ×1.32 with a median
  −0.6 ft.
- **On development,** under the same semantics, exact feet score 7/10. That is one point lower than Stage 14, because
  Unknown now withholds feet.

## 7. Sector Intelligence suitability

| Sector Intelligence evidence | Rule | Development share / truth in answer | Fresh n / share / truth in answer | Bar | Fresh verdict |
|---|---|---|---|---:|---|
| **Strong** | full authority, tier 1, not S2C, no algal flag, posterior ≥ 0.90 | 10% / 97% | 5 / 5% / 100% | 0.90 | INSUFFICIENT (n < 30) |
| **Moderate** | other full-authority answers | 70% / 85% | 39 / 36% / 97% | 0.80 | met |
| **Weak** | lower authority (tier 3, S2C) | 7% / 85% | 55 / 51% / 85% | 0.65 | met |
| **Unavailable** | Unknown | 13% / – | 9 / 8% / – | – | – |

**SAFE FOR SECTOR INTELLIGENCE: NO**, by the pre-registered rule: the strong level has only
5 fresh answers, against 30 needed. On the rows available:
- moderate evidence was right 97% of the time;
- weak evidence was right 85% of the time.

Development shows the shape a feed would have: strong 10% (right 97%), moderate 70% (85%), weak 7% (85%), unavailable
13%.

## 8. Ready to freeze?

| Criterion (unchanged from Stage 15) | Development | Fresh | Bar |
|---|---|---|---|
| Core minima met | n/a | **no** (normal, stained, limited, total) | all |
| Operational | 7/10 | 7/10 | ≥ 7/10 |
| Every core class ≥ 0.60 | **no** (stained 0.571) | (normal 0.529; short classes insufficient) | ≥ 0.60 |
| Harmful | 10.6% | 0.9% | ≤ 15% |
| Severe | 1.5% | 0.0% | ≤ 2% |

**READY TO FREEZE CLARITY AND START WATER TEMPERATURE: NO.**
- **What it now meets.** On development the gate meets the harmful and severe bars for the first time: 10.6% and 1.5%.
- **What still fails:**
  - stained water stays at 0.571;
  - the fresh holdout cannot certify anything until it is about twice as large overall, and several times larger in
    stained and limited water.

## 9. Stretch target: a true 9/10 product

| Stretch target (true 9/10) | Development | Fresh | Target |
|---|---|---|---|
| Operational | 0.693 | 0.709 | ≥ 0.85 |
| Weakest class | 0.571 | 0.529 | ≥ 0.80 |
| Harmful | 10.6% | 0.9% | ≤ 5% |
| Severe | 1.5% | 0.0% | ≤ 0.5% |
| Strong evidence | 10% | 5% | ≥ 50% |

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
SINGLE-STATE RELIABILITY GATE: Posterior gate. A single state needs a ≥ 70% calibrated posterior and a boundary pair ≥ 70%; otherwise Unknown. It was fitted on development only. It never issues plain Normal or Stained (zones: Limited < 1.55 ft, Stained-to-Limited, Unknown 2.43–2.80 ft, Normal-to-Stained, Clear-to-Normal 4.11–7.40 ft, Clear above). Development harmful 16.6% → 10.6%, severe 2.0% → 1.5%
TIER-2 AUTHORITY RULE: Boundary states only, with tier-2-calibrated posteriors; Unknown below 70%. Tier-2 harmful on development 12% → 7% (the Stage 15 re-score had shown 29%)
FRESH HOLDOUT SAMPLE SIZE: 108 observations at 80 lakes (88% Wisconsin, 57 Sentinel-2C). INSUFFICIENT: normal 19/40, stained 9/60, limited 6/25, total 108/200 (clear 74/40 met)
HARMFUL RATE: 0.9% on the fresh holdout (1 of 108; insufficient, and S2C rows are lower authority so cannot be harmful); 10.6% on development
SEVERE RATE: 0.0% on the fresh holdout; 1.5% on development
CLEAR SCORE: 0.826 fresh (n 74); 0.880 development
NORMAL SCORE: 0.529 fresh (n 19, insufficient); 0.643 development
STAINED SCORE: 0.706 fresh (n 9, insufficient); 0.571 development (below 0.60)
LIMITED SCORE: 0.775 fresh (n 6, insufficient); 0.676 development
EXACT-FEET CAPABILITY: 2/10 on the fresh holdout (S2C feet withheld on 53% of rows; three classes insufficient; where shown, ×1.32 and −0.6 ft); 7/10 on development under Stage 16 semantics
OPERATIONAL BOWFISHING CLARITY: 7/10 on the fresh holdout (0.709; insufficient for normal, stained and limited); 7/10 on development (0.693)
SAFE FOR SECTOR INTELLIGENCE: NO (only 5 strong-evidence answers against the 30 needed; moderate evidence 97% and weak 85% right on the rows available)
READY TO FREEZE CLARITY AND START WATER TEMPERATURE: NO (fresh minima not met; development stained 0.571 < 0.60; harmful and severe now pass on development)
PATH FROM CURRENT SCORE TO TRUE 9/10: (1) Certify first: a fresh holdout of ≥ 200 rows with ≥ 60 stained and ≥ 25 limited, from a WQP re-pull around April 2027 (2026 uploads) or direct TVA/USACE and state reservoir requests, under this frozen protocol. (2) Resolution: stained water is narrower than the ×1.36 retrieval error, so a 9/10 needs more information per answer (multi-scene consensus or field-report assimilation), which means reopening model work with a new pre-registration. (3) Authority: Sentinel-2C (a third of current scenes) must pass its lift criterion; it still reads low on both independent sets (−0.19 and −0.09 log), so it needs re-derived harmonisation from more tandem pairs. (4) Raise strong evidence from 5–10% toward half of all answers. Today: 0.69–0.71 class-balanced, against the 0.85 a 9/10 needs
