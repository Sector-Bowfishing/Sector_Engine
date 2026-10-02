# Current Clarity Stage 15: Final Product Semantics

**Diagnostic only.**
- The frozen engine is unchanged: C-gbm is not refitted, and every Stage 14 engine file matches its hash.
- Production is unchanged, and nothing was deployed.
- No Sector field observation was used, and Michael's Guntersville survey was not touched.
- Water Temperature was not started.

**This is a re-score, not a blind certification.**
- The Stage 14 certification set was already unsealed and scored in Stage 14, and its findings motivated this stage.
- Every new threshold here comes from development rows only, and was frozen before the re-score.
- The readiness decision requires the development rows to pass as well, so the re-score cannot carry it alone.

| Step | UTC | What was fixed |
|---|---|---|
| Pre-registration | 2026-10-01T17:04:40Z | Derivation rules for every new state, display and authority; the operational rubric; the readiness rule (`PREREGISTRATION_STAGE15.md`, `8265b7a8…`) |
| Semantics | 2026-10-01T17:08:04Z | Parameters derived from development rows only (`engine/semantics15.json`, `a5d6da8d…`), before the re-score |
| Inputs | re-checked | Engine, certification sample, ACOLITE results and truth: all match their Stage 14 hashes |

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

| State | Prediction range (ft) | Display | Authority |
|---|---|---|---|
| Clear | ≥ 6.94 | exact feet + two-thirds interval | full |
| **Clear-to-Normal (new)** | 5.00 to 6.94 | exact feet + interval | full |
| Normal | 3.80 to 5.00 | exact feet + interval | full |
| Normal-to-Stained | 2.63 to 3.80 | exact feet + interval | full |
| Stained | 2.38 to 2.63 | exact feet + interval | full |
| Stained-to-Limited | 1.70 to 2.38 | exact feet + interval | full |
| Limited | < 1.70 | exact feet + interval | full |
| Any state, NDCI > 0.03 | as above | "~X ft" + "Algal water detected — elevated uncertainty" | full |
| Any state, Sentinel-2C | as above | state only (feet and interval withheld) | **lower** |
| Tier 3 Clear (Sen2Cor-C3 ≥ 6 ft) | — | "~X ft" (lower confidence) | **lower** |
| Unknown / Low Authority | any other tier-3 reading, or none | nothing | — |

Exact feet are still authorised for every class. The numeric prediction behind every row is the Stage 14 prediction,
unchanged.

## 2. Clear-to-Normal

| Clear-to-Normal | Value |
|---|---|
| Band (pooled development, 2:1 odds) | 5.00–6.94 ft (logistic α 0.08, β 9.7, 823 rows within ±0.30) |
| Nested bands, 5 folds | 5.07–7.28; 4.90–6.96; 5.01–6.97; 4.87–6.99; 4.98–7.12 ft |
| Adoption test (development, nested) | operational 0.667 → **0.690**; harmful 21.8% → **17.3%** → **adopted** |
| Re-score: Clear-to-Normal answers | 91, right 90% (truth: 51 clear, 31 normal, 8 stained, 1 limited) |
| … what Stage 14 had said for them | Clear 39, Normal 52 |
| Plain "Normal" answers | Stage 14: 127, right 41% → Stage 15: 75, right 45% |

- **How the band was set.** Exactly as for the other two: within 5.00–6.94 ft, neither side of 6 ft is twice as likely as
  the other on development predictions.
- **What it fixes.** It replaces 52 of the 127 Stage 14 "Normal" answers and 39 "Clear" answers. Most of them (51 of
  91) were clear water read low.
- **What it leaves.** The plain "Normal" answer is now confined to 3.80–5.00 ft. It is still the weakest state (45%
  right), but it is issued 40% less often.

## 3. The very-clear floor: not adopted

| Predicted ≥ | Development rows | Median \|log\| (trigger > 0.15) | Truth − prediction (median) | Truth ≥ that depth | Truth ≥ 6 ft |
|---|---:|---:|---:|---:|---:|
| 10 ft | 343 | 0.130 | -0.62 ft | 72% | 92% |
| 12 ft | 251 | 0.135 | -0.23 ft | 68% | 94% |
| 15 ft | 114 | 0.129 | +0.19 ft | 70% | 94% |

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

| NDCI level | Development rows | State right (development) | Behaviour (frozen rule) | Re-score rows | State right (re-score) | In-situ algal share (dev / re-score) |
|---|---:|---:|---|---:|---:|---|
| moderate (0.03–0.10) | 264 | 79% | **modifier** | 117 | 74% | 53% / 50% |
| strong (> 0.10) | 501 | 77% | **modifier** | 302 | 78% | 55% / 72% |

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

| Sentinel-2C | Value |
|---|---|
| Development S2C rows (tiers 1–2) | 38; median signed log -0.050 (S2A/B +0.007) |
| Certification S2C rows | 33 (4% of the US core); 23 lowered from full authority; feet withheld on 27 |
| Share of 2025-dated certification rows | **34%** (85 rows) |
| Operational score of S2C rows | 0.57; harmful answers 0 |

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

| Outcome (re-score, US core) | Score | Rows | Share |
|---|---:|---:|---:|
| Correct single state | 1.0 | 346 | 42% |
| Correct boundary state | 0.9 | 211 | 26% |
| Correct very-clear floor | 1.0 | 0 | 0% |
| Correct lower-authority answer | 0.75 | 62 | 8% |
| Wrong lower-authority answer | 0.25 | 20 | 2% |
| Appropriate Unknown | 0.5 | 34 | 4% |
| Unknown that withheld a right answer | 0.25 | 23 | 3% |
| **Harmful wrong answer** | 0 | 129 | 16% |

| True class | Development n | Development score | Re-score n | **Re-score score** |
|---|---:|---:|---:|---:|
| Clear | 745 | 0.848 | 393 | **0.846** |
| Normal | 381 | 0.690 | 177 | **0.633** |
| Stained | 227 | 0.563 | 99 | **0.598** |
| Limited | 229 | 0.652 | 156 | **0.682** |
| **Class-balanced → /10** | | 0.688 → **7/10** | | **0.690 → 7/10** |
| Harmful (bar ≤ 15%) | | 16.6% | | **15.6%** |
| Severe (bar ≤ 2%) | | 2.0% | | 1.9% |

**Each layer's effect, on development:**

| Semantics (development, nested) | Operational | Harmful | Severe |
|---|---:|---:|---:|
| Stage 14 states | 0.667 (7/10) | 21.8% | 2.3% |
| + floor | 0.667 (7/10) | 21.8% | 2.3% |
| + Clear-to-Normal | 0.690 (7/10) | 17.3% | 2.0% |
| + algal | 0.690 (7/10) | 17.3% | 2.0% |
| + S2C lower authority (final) | 0.688 (7/10) | 16.6% | 2.0% |

**Where the harmful answers come from** (re-score; development shows the same pattern):
- plain "Normal" (38; 21 of them truly clear);
- "Normal-to-Stained" on limited water (18);
- "Clear" on normal water (19);
- plain "Stained" (18).

**The tiers differ.** Tier-2 (relaxed-mask) answers are harmful 29% of the time, against 16% at tier 1.

## 8. The re-score, every rubric side by side

| Rubric (certification set) | Stage 14 semantics | **Stage 15 semantics** |
|---|---|---|
| Exact feet (Stage 12) | 7/10 | **7/10** |
| Original hard class | 4/10 | **4/10** (unchanged by design) |
| Boundary-aware product (Stage 14 section 8) | 2.5 / 7 → 4/10 | **3.0 / 7 → 4/10** |
| Decision-balanced accuracy | 0.726 | **0.772** |
| Operational (new) | — | **7/10** |

| Capability (re-score) | Exact feet | Product, Stage 14 semantics | **Product, Stage 15 semantics** |
|---|---|---|---|
| Clear | PARTIAL (-2.2 ft, coverage 91%) | SUPPORTED (0.81 / 0.87) | **SUPPORTED (0.91 / 0.91)** |
| Normal | SUPPORTED (+0.0 ft, coverage 86%) | NOT (0.66 / 0.56) | **PARTIAL (0.76 / 0.71)** |
| Stained | SUPPORTED (+0.4 ft, coverage 91%) | PARTIAL (0.69 / 0.74) | **PARTIAL (0.69 / 0.75)** |
| Limited | SUPPORTED (+0.6 ft, coverage 89%) | PARTIAL (0.73 / 0.88) | **PARTIAL (0.73 / 0.89)** |
| Algae | PARTIAL (+0.5 ft, coverage 87%) | NOT (0.72 vs 0.74) | **NOT (0.73 vs 0.74)** |
| Sediment | SUPPORTED (+0.3 ft, coverage 87%) | PARTIAL (0.85 vs 0.88) | **PARTIAL (0.85 vs 0.88)** |
| Bottom-risk | NOT | NOT | **NOT** |

| Issued state (re-score) | n | Right | of which full authority |
|---|---:|---:|---:|
| Clear | 324 | 89% | 264 |
| Clear-to-Normal | 91 | 90% | 83 |
| Normal | 75 | 45% | 70 |
| Normal-to-Stained | 100 | 74% | 98 |
| Stained | 31 | 35% | 29 |
| Stained-to-Limited | 73 | 90% | 71 |
| Limited | 74 | 86% | 71 |
| Unknown / Low Authority | 57 | – | 0 |

**Splits:**

| Split (US core) | Group | n | Operational | Harmful | Decision-balanced (full authority) | Operational by class: clear · normal · stained · limited |
|---|---|---:|---:|---:|---:|---|
| platform | sentinel-2a | 363 | 0.692 (7/10) | 14.6% | 0.771 | 0.88 · 0.67 · 0.61 · 0.62 |
| platform | sentinel-2b | 429 | 0.695 (7/10) | 17.7% | 0.767 | 0.83 · 0.62 · 0.59 · 0.73 |
| platform | sentinel-2c | 33 | 0.560 (6/10) | 0.0% | – | 0.62 · 0.50 · – · 0.56 |
| season | cool | 166 | 0.750 (8/10) | 15.1% | 0.829 | 0.77 · 0.75 · 0.70 · 0.78 |
| season | warm | 659 | 0.664 (7/10) | 15.8% | 0.745 | 0.86 · 0.60 · 0.56 · 0.64 |
| tier | 1 | 599 | 0.749 (7/10) | 16.2% | 0.793 | 0.88 · 0.68 · 0.65 · 0.78 |
| tier | 2 | 110 | 0.655 (7/10) | 29.1% | 0.695 | 0.87 · 0.75 · 0.57 · 0.44 |
| tier | 3 | 116 | 0.420 (4/10) | 0.0% | – | 0.67 · 0.25 · 0.30 · 0.46 |
| source | NLA | 155 | 0.690 (7/10) | 15.5% | 0.781 | 0.85 · 0.63 · 0.60 · 0.69 |
| source | WQP | 670 | 0.690 (7/10) | 15.7% | 0.771 | 0.85 · 0.63 · 0.60 · 0.68 |

- **Cool-season water now scores better than warm** (0.75 against 0.66). Clear-to-Normal absorbs the cool-season
  clear-water under-read that Stage 14 found.
- **S2C and tier 3 score lower by construction.** Their answers are lower authority, or Unknown.
- **SYKE** (Finland, out of domain) scores 0.557 (6/10) and stays out of every verdict.

## 9. Ready to freeze?

**NO, by the frozen rule.**

| Criterion | Development | Re-score | Bar |
|---|---|---|---|
| Engine unchanged | yes | yes | yes |
| Operational capability | 7/10 | 7/10 | ≥ 7/10 |
| Every class ≥ 0.60 | **no** (stained 0.563) | **no** (stained 0.598) | ≥ 0.60 |
| Harmful rate | **16.6%** | **15.6%** | ≤ 15% |
| Severe rate | 2.0% | 1.9% | ≤ 2% |

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
CLEAR-TO-NORMAL STATE ADOPTED: YES (band 5.00–6.94 ft from development 2:1 odds; development operational 0.667 → 0.690 and harmful 21.8% → 17.3%; re-score: right 90% of 91 answers, normal NOT → PARTIAL)
VERY-CLEAR FLOOR: Not adopted. The frozen trigger (median |log| > 0.15 among predictions ≥ 10/12/15 ft) is not met: about 0.13 at every threshold. The deep-water error is under-reading, which a floor on the prediction cannot fix, and a 12 ft floor would worsen the clear exact feet (−1.75 → −2.21 ft). A "12+ ft" display would be honest (69% on development, 78% on the re-score) and remains an optional UX choice, not an accuracy rule
ALGAL PRODUCT BEHAVIOR: When NDCI > 0.03, the state is kept at full authority, visibility is shown as "~X ft", and "Algal water detected — elevated uncertainty" is attached. It is not softened or withheld, because flagged-water states are right 77–79% of the time on development (74–78% on the re-score)
S2C PRODUCT AUTHORITY: Lower authority. The state is shown; exact feet and the interval are withheld; there is no recalibration. It lifts once ≥ 60 independent S2C certification rows show |median signed log| ≤ 0.05. The cost is 4% of certification rows but 34% of 2025-dated rows
EXACT-FEET CERTIFIED CAPABILITY: 7/10 (re-score of the already-seen Stage 14 set; clear PARTIAL at −2.3 ft; normal, stained, limited and sediment SUPPORTED)
BOUNDARY-AWARE CERTIFIED CAPABILITY: 4/10 (3.0 of 7, up from 2.5: normal NOT → PARTIAL; decision-balanced 0.726 → 0.772; re-score, not blind)
OPERATIONAL BOWFISHING CLARITY CAPABILITY: 7/10 (re-score 0.690, development 0.688; harmful 15.6% / 16.6%, severe 1.9% / 2.0%)
CURRENT CLARITY READY TO FREEZE AND MOVE TO WATER TEMP: NO (frozen rule: harmful answers 15.6% on the re-score and 16.6% on development, against ≤ 15%; stained 0.598 / 0.563 against ≥ 0.60; every other criterion passes)
REMAINING BLOCKERS: (1) harmful answers next to boundaries, mostly plain "Normal" (3.80–5.00 ft), plain "Stained" and Clear/Normal confusions, plus 29% harmful at tier 2; candidate rules need pre-registration and unseen data; (2) stained water at the retrieval-resolution limit (0.56–0.60); (3) no unseen certification data remains: the P2 fresh pool, the Guntersville survey or a TVA/USACE request are needed; (4) Sentinel-2C at lower authority, about a third of current-era scenes, until ≥ 60 independent rows pass; (5) Michael's ship decision, and the deep-water clear under-read, which is a retrieval limit; (6) bottom-risk needs depth
