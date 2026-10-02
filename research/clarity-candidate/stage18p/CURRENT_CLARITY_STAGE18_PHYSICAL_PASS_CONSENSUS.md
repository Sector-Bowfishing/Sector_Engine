# Current Clarity Stage 18: Physical-Pass Consensus Rebuild

**2026-10-02.** Stage 17's multi-scene consensus was rebuilt so that every neighbouring observation is a separate physical satellite pass.

**What didn't change:**
- the frozen C-gbm, which was not refit;
- the Stage 16 anchor and products.

**What was never used:**
- field reports;
- Stage 14/15 certification truth;
- Stage 16 fresh truth.

**Method:**
- pre-registered before scoring (`PREREGISTRATION_STAGE18P.md`, frozen 19:02 UTC);
- whole-lake-held-out development only.

Production is unchanged, and nothing was deployed.

**The answer:** the Stage 17 gain survives true pass independence. Stained rises from 0.571 to 0.668 (95% CI of the gain +0.055 to +0.141). The rebuilt consensus passes every Stage 16 freeze bar, so it is adopted as the new development candidate. It is still uncertified and far from the 9/10 bar.

| | Stage 16 | Stage 17 as reported (with duplicates) | **Stage 18 adopted (independent passes)** |
|---|---:|---:|---:|
| Operational (class-balanced) | 0.693 | 0.743 | **0.737** |
| Clear | 0.880 | 0.893 | **0.893** |
| Normal | 0.643 | 0.701 | **0.685** |
| Stained | 0.571 | 0.667 | **0.668** |
| Limited | 0.676 | 0.710 | **0.703** |
| Harmful | 10.6% | 11.6% | **11.6%** |
| Severe | 1.52% | 1.33% | **1.26%** |
| Unknown share | 12.8% | — | **6.7%** |
| Strong share / truth-in-answer | 11.3% / 96.8% | 23.3% / 95.4% | **22.9% / 94.7%** |

## 1. A canonical physical pass

**The identity.** A physical pass is (platform, UTC sensing date).
- A Sentinel-2 satellite images a site at most once a day: one descending daytime pass.
- Consecutive orbits only overlap beyond about 84° latitude.
- So every Earth Search item of one platform on one day over a site is one observation. That covers overlapping MGRS tiles, datastrip twins and duplicate representations.
- Item ids cannot serve: datastrip twins carry ids several minutes apart (9–11 minutes in the examples checked), while their sensing times differ by seconds.

**Validation, before any scoring:**
- **Against L1C datatakes.** 6,544 pairs of items whose L1C datatake (satellite + datatake sensing start) is known were checked. The pass key and the datatake agree in all 6,544: 944 same-pass pairs and 5,600 different-pass pairs, 0 disagreements.
- **Sensing time.** Items within one pass are at most 18.7 s apart. Two passes of one platform at one site are at least 72 hours apart.
- **Manual review.** 20 duplicate groups were reviewed: 8 anchor + overlapping tile, 4 anchor + same tile, 8 neighbour + neighbour. Every group is one datatake, with the same satellite, datatake start and relative orbit. The same-tile pairs share the very same L1C file. Example: `S2B_T14SPB_20210223T172435` and `…T171310` are both `S2B_MSIL1C_20210223T171309_N0500_R112_T14SPB`.

**How much of Stage 17 disappears:**

| Stage 17 neighbour observations | Count | Events |
|---|---:|---:|
| All | 2,487 | 1,215 |
| The anchor's own pass, through an overlapping tile | 453 | — |
| The anchor's own pass, same tile (datastrip twin) | 4 | — |
| A repeat of another neighbour's pass | 271 | 268 |
| **Removed** | **728 (29.3%)** | 399 with an anchor duplicate |

## 2. The rebuilt temporal dataset

**Neighbours:**
- **Eligible passes:** within ±10 days, with a valid production-gated Sen2Cor disk, never the anchor's pass.
- **One representative item per pass:** the most valid pixels, then the lowest cloud, then the item id.
- **Which passes:** the 3 nearest by |dt|.
- **Stage 17's no-replacement rule stands:** a representative with no valid ACOLITE tier contributes nothing.

**Data volume:**
- 1,106 events have at least one independent candidate pass.
- 255 representatives were new and went through the frozen ACOLITE path (274 stations). 4 had no L1C in the bucket.
- Usable independent neighbour scenes: 1,812, over 1,035 events.
- By window: ±3 days 329, ±5 days 873, ±7 days 1,252, ±10 days 1,812.
- No physical pass contributes twice. An assertion checks every event, the anchor's pass included.

**Hydrology was context only.** The Stage 17 rain rule would have excluded 422 of the 1,765 contributing S2A/B neighbours (23.9%).

## 3. Consensus methods

There were 16 variants: 4 methods × 4 windows, with S2C off.

**The variance model:** scene variance = σ²_tier + κ·|Δt|, refit per fold on inner folds from independent passes only.

**Calibration:** n = 1 uses the Stage 16 posteriors. n = 2 and n ≥ 3 use nested posteriors.

| Variant | Operational | Harmful | Severe | Stained | Limited | Strong / accuracy | Freeze bars |
|---|---:|---:|---:|---:|---:|---:|---|
| Agreement only, all windows | 0.693 | 10.6% | 1.52% | 0.571 | 0.676 | 6–19% / 95–96% | no (stained) |
| Inverse-uncertainty, ±3 days | 0.685 | 11.4% | 1.64% | 0.529 | 0.681 | 7% / 96% | no |
| Inverse-uncertainty, ±5 days | 0.712 | 11.6% | 1.39% | 0.602 | 0.682 | 15% / 96% | yes |
| Inverse-uncertainty, ±7 days | 0.721 | 11.8% | 1.33% | 0.625 | 0.696 | 20% / 96% | yes |
| **Inverse-uncertainty, ±10 days** | **0.737** | **11.6%** | **1.26%** | **0.668** | **0.703** | **23% / 95%** | **yes** |
| Robust, ±10 days | 0.738 | 11.6% | 1.26% | 0.668 | 0.703 | 23% / 95% | yes |
| Bayesian, ±10 days | 0.739 | 11.6% | 1.26% | 0.672 | 0.706 | 23% / 95% | yes |

**Robust and Bayesian combining are not materially distinct.** They stay within 0.01 of inverse-uncertainty weighting at every window (+0.001 and +0.002 at ±10 days), so weighting represents them.

**The selected variant:** inverse-uncertainty ±10 days, the highest operational score among the variants that pass the bars. The pre-registered rule chooses the same variant that Stage 17's challenger used.

**Why ±10 days wins.** With independent passes, the time penalty almost vanishes. The pooled κ is 0.00012 a day, against 0.0018 in Stage 17.
- Stage 17's same-day duplicates agreed with the anchor almost perfectly, which made scenes look as if they drift apart with time.
- Within ±10 days, independent passes disagree with the anchor by about the same amount whatever their separation (σ ≈ 0.20 log10 for tier 1).
- So a pass 9 days away is nearly as informative as a pass 2 days away. The wider window wins because it finds more passes.

## 4. Primary target: stained water (227 development events)

| Stained | Stage 16 | Adopted | Change |
|---|---:|---:|---:|
| Operational score | 0.571 | 0.668 | **+0.097** (95% CI +0.055 to +0.141) |
| Truth-in-answer (full authority) | 71.9% | 78.9% | +7.0 points |
| Harmful rate | 22.0% | 18.9% | −3.1 points |
| Exact-feet error (same 176 rows) | ×1.42 | ×1.39 | better |
| Mean posterior confidence | 0.791 | 0.802 | +0.011 |
| Unknown rate | 19.8% | 9.3% | −10.5 points |

**The Stage 17 gain survives: +0.097 here, against +0.096 reported.**

**Why the duplicates hardly mattered.**
- In Stage 17, a duplicate of the anchor added no information, but it pulled the consensus toward the anchor and used up a neighbour slot.
- With duplicates removed, those slots go to genuinely independent passes: 255 new scenes.
- The independent information ends up about the same. Stage 17 had 1,759 distinct-pass neighbour observations before tier checks; the rebuild has 1,812 usable.

## 5. Core product metrics (1,582 development events)

| | Stage 16 | Adopted | Change |
|---|---:|---:|---:|
| Operational (class-balanced) | 0.693 | 0.737 | +0.045 (CI +0.030 to +0.060) |
| Clear | 0.880 | 0.893 | +0.013 |
| Normal | 0.643 | 0.685 | +0.042 |
| Stained | 0.571 | 0.668 | +0.097 |
| Limited | 0.676 | 0.703 | +0.027 |
| Harmful | 10.6% | 11.6% | +1.0 point (CI −0.1 to +2.1) |
| Severe | 1.52% | 1.26% | −0.26 point (CI −0.70 to +0.19) |
| Exact-feet error (same 1,265 rows) | ×1.35 | ×1.32 | better |
| Exact-feet capability | 7/10 | 8/10 | +1 |
| Unknown share | 12.8% | 6.7% | −6.1 points |

**Where the extra harm comes from:**
- **Per class:** stained harmful falls (22.0% → 18.9%), but clear (3.1% → 4.7%), normal (15.5% → 17.6%) and limited (15.7% → 17.0%) rise.
- **Rows:** 49 answers become harmful and 33 stop being harmful.
- **The cause:** 23 of the 49 are events where Stage 16 had said Unknown. As in Stage 17, consensus answers more, and some of those answers are wrong.
- **Severe** falls in stained (4.0% → 3.5%) and limited (4.8% → 3.5%).

## 6. Strong evidence

**The rule:** at least 2 compatible full-authority scenes from different physical passes, none disjoint, posterior ≥ 0.90. An overlapping tile or datastrip twin cannot satisfy it.

**The result:**
- Strong covers 22.9% of usable answers (338), at 94.7% truth-in-answer.
- Stage 16 had 11.3% at 96.8%.
- The accuracy bar (≥ 90%) holds. The 50% share target does not.

## 7. Sentinel-2C (descriptive, for Stage 19)

S2C stayed at lower authority and never contributed. 57 independent S2C neighbour scenes sat beside an S2A/B consensus:
- **96.5%** had their own state share a class with the consensus state;
- **80.7%** had a state that contains the consensus state.

S2C harmonisation was not fitted or changed. These figures are for designing Stage 19 only.

## 8. Decision

**Adoption** (the pre-registered rule, on the selected variant):

| Requirement | Result |
|---|---|
| Every Stage 16 freeze bar | **Pass:** operational 7/10 (0.737), weakest class 0.668, harmful 11.6%, severe 1.26% |
| Stained improves materially (≥ 0.05) with the CI above 0 | **Pass:** +0.097 (CI +0.055 to +0.141) |
| Severe ≤ 2% | **Pass:** 1.26% |
| Harmful ≤ 15% | **Pass:** 11.6% |
| Genuinely independent physical passes | **Pass:** asserted for every event |

**Adopted as the new development candidate:** physical-pass consensus.

**The frozen parameters** are in `engine/candidate18p.json`, pooled from development only:
- σ is 0.199 for tier 1 and 0.172 for tier 2;
- κ is 0.00012 a day;
- the n = 2 and n ≥ 3 posteriors come from 470 and 495 calibration rows.

**Still true:**
- It is **uncertified**, and **not deployed**.
- The live shadow still runs the item-based Stage 17 rule. Its `stage17_one_per_pass` diagnostic is close to, but not the same as, this candidate.

**The true 9/10 development bar fails on every part:**

| Bar | Need | Adopted |
|---|---|---:|
| Operational | ≥ 0.85 | 0.737 |
| Weakest core class | ≥ 0.80 | 0.668 (stained) |
| Harmful | ≤ 5% | 11.6% |
| Severe | ≤ 0.5% | 1.26% |
| Strong share at ≥ 90% accuracy | ≥ 50% | 22.9% at 94.7% |

## 9. What this does not show

- **This is development, not certification.** Every number is whole-lake held out on the development set. No blind data was used, and none is left: the Stage 14 set, the sealed WQP tier and the P2 pool are all spent.
- **Harm is not lower overall.** Harmful rises by about 1 point. The adoption rule allows that (≤ 15%), but it is a real trade: more answers, a little more harm.
- **Live use is one-sided.** At a live pass, only earlier passes exist. The development windows were two-sided around the observation date.

## Files

All in `research/clarity-candidate/stage18p/`:

| File | Contents |
|---|---|
| `passes18.py`, `validation18.json`, `contamination18.json` | Pass identity, validation and the contamination count |
| `neighbors18.json`, `tasks_nb18.json`, `res_nb18/` | The rebuilt selection and the 255 new ACOLITE samples |
| `PREREGISTRATION_STAGE18P.md`, `FREEZE_STAGE18P.json` | The pre-registration and its hashes |
| `dev18p.py`, `dev18p.json`, `dev18p_rows.json`, `post18p.py`, `post18p.json` | Scoring |
| `freeze18p.py`, `engine/candidate18p.json` | The adopted candidate's frozen parameters |

DUPLICATE-PASS CONTAMINATION REMOVED: YES

STAGE 17 GAIN SURVIVES: YES

BEST CONSENSUS METHOD: inverse-uncertainty weighting over ±10 days of up to 3 physically independent passes, S2C off, no rain rule (robust and Bayesian not materially distinct)

STAINED SCORE: 0.668 (Stage 16 0.571; gain +0.097, CI +0.055 to +0.141)

LIMITED SCORE: 0.703 (Stage 16 0.676)

OPERATIONAL SCORE: 0.737 — 7/10 (Stage 16 0.693)

HARMFUL RATE: 11.6% (Stage 16 10.6%)

SEVERE RATE: 1.26% (Stage 16 1.52%)

STRONG EVIDENCE SHARE / ACCURACY: 22.9% of usable answers / 94.7%

STAGE 16 FREEZE BARS PASSED: YES

TRUE 9/10 DEVELOPMENT BAR PASSED: NO

CURRENT CLARITY SCORE RECOMMENDATION: 7/10 (development capability, uncertified; 0.737, up from 0.693)

NEXT BLOCKER: An unseen certification pool, which none of the existing data can provide. Requests are needed to TCEQ, OWRB, and TVA/USACE, or a WQP re-pull around April 2027. After that, normal water (0.685) and the harmful rate (11.6%) are what keep it from 9/10.
