# Current Clarity Stage 24: Geometry-Aware Consensus and N0513 Baseline Recovery

**2026-10-04.** This stage attacks the two physical causes Stage 23 found:
- **Viewing geometry:** passes seen from opposite sides of a scene disagree.
- **N0513 over-correction:** C3 probably over-corrects the newest S2C processing baseline.

It asks whether fixing them improves the live consensus without touching the Clarity model.

**What didn't change:**
- the C-gbm, which was not refit;
- the Stage 16 posterior gate;
- the Stage 19 consensus code (only the pre-registered patches);
- ACOLITE K4;
- C3 for N0511/N0512;
- the Strong definition;
- every bar.

**Constraints held:**
- Stage 12 stays retired;
- nothing was fitted to field reports or Secchi;
- no future observation was used.

**Method:**
- Pre-registered before any Stage 24 reflectance, geometry-disagreement relation or consensus score: `PREREGISTRATION_STAGE24.md`, SHA-256 `b9179365…`.
- The derived values (N2 offsets, the geometry variance term) were frozen in `derived24.json` before validation or scoring.

Public production is unchanged.

**The answer: N0513 is fixed on the internal path; geometry is real but not the lever. No consensus candidate is adopted, and the score stays 7/10.**
- **N0513: raw wins and validates.**
  - On 41 new N0513 pairs, raw S2C reads +0.020 against S2A, while C3 reads −0.035.
  - The internal shadow now answers nominal N0513 S2C on the raw path. N0511/N0512 keep C3, and S2C stays at lower authority.
  - A caveat: C3 over-corrects September–October 2025 N0511 pairs just as much (−0.063), so part of the "N0513" problem is autumn, not only the baseline.
- **Geometry is confirmed, and the best signal is the glint angle.**
  - Opposite-side views disagree more than identical ones (visibility 0.070 against 0.039; class jumps 12% against 0%).
  - The angle to the specular direction predicts disagreement twice as well as "same track / different track" (|ρ| 0.43 against 0.22).
  - The same effect appears, truth-free, in the development consensus inputs.
- **Geometry-aware consensus is not useful enough to adopt.**
  - Weighting (G1) and refusal (G2) change almost nothing.
  - Geometry matching (G3) at 15 days gains +0.020 operational and +0.045 stained, but harmful (+0.5 pts) and severe (+0.2 pts) are not shown non-worse.
  - Most of the gain comes from the 15-day window, not from geometry: no-geometry consensus at 15 days reaches 0.728.
- **The error modes are not geometric.**
  - Murky water read too clear stays at 16–18% of murky rows under every candidate.
  - Strong answers that include an opposite-side pass are as accurate as compatible-only ones.

## PART A — N0513

## 1. Data

| Set | What | Valid pairs | Role |
|---|---|---|---|
| **T2N** | Stage 23's N0513 2-day S2C → S2A pairs (**reused, already seen**) | 53–56 | Derivation |
| **T24N** | **New**: N0513 S2C → S2A, same track, 48 h, Aug–Oct 2026, 76 new lakes and scenes (inland, coastal and pilot lakes), no item pair shared with T2N | **41** (80 processed; 8 produced no water product) | Validation |
| **Seasonal control** | Stage 22's Sep–Oct 2025 N0511 2-day pairs | 34–35 | Descriptive |
| **N0513 Secchi** | — | **none exist** (the truth corpus predates N0513) | — |

## 2. Candidate paths

**N0 — raw:** frozen ACOLITE K4 with no offsets.

**N1 — C3:** historical.

**N2 — an N0513-specific correction,** created by the pre-registered rule from T2N top-of-atmosphere evidence:

| Band | S2C − S2A median | 95% CI | Qualifies |
|---|---|---|---|
| B11 | +0.00105 | +0.00095 to +0.0015 | yes |
| B12 | +0.00055 | +0.00025 to +0.0007 | yes |
| B08 | — | — | no |
| B8A | — | — | no |

So N2 removes B11/B12 by those constants, then applies the B05 adjustment.

## 3. Selection (T2N) and validation (T24N, new)

| Path | T2N visibility | T2N bands B02/B03/B04/B05 | **T24N visibility** | T24N bands | T24N state | T24N jumps |
|---|---:|---|---:|---|---:|---:|
| **N0 raw** | +0.007 | 0.73 / 0.83 / 0.76 / 0.75 | **+0.020** | 0.86 / 0.88 / 0.88 / 0.83 | 92.3% | 4.9% |
| N1 C3 | −0.051 | 0.79 / 0.89 / 0.89 / 0.91 | −0.035 | 0.88 / 0.97 / 0.91 / 0.93 | 92.1% | 7.3% |
| N2 | −0.003 | 0.77 / 0.86 / 0.85 / 0.86 | −0.011 | 0.88 / 0.93 / 0.91 / 0.88 | 92.1% | 7.3% |

Visibility is the median Δp against S2A; bands are S2C/S2A ratios.

**Selection (J):**
- N2 has the lowest |Δp| on T2N (0.003).
- Raw's 0.007 is within the pre-registered 0.005 tie margin, so the simpler path wins: **N0**.

**Validation on T24N:**
- |+0.020| ≤ 0.03: pass;
- closer than C3 (0.035): pass;
- **the path is updated.**

On the new pairs N2 happened to be closest (−0.011). The rule's choice of the simpler path stands.

**By region (raw / C3):**

| Region | Raw | C3 |
|---|---:|---:|
| West | +0.024 | −0.031 |
| Southeast | +0.025 | +0.024 |
| Northeast | +0.054 | −0.076 |
| Plains | −0.034 | −0.064 |
| Coastal/global | −0.034 | −0.042 |
| Pilot | −0.028 | −0.078 |

**Seasonal control** (Sep–Oct 2025, N0511): raw −0.020, C3 **−0.063**. C3's autumn over-correction is not unique to N0513. The N0513 TOA offset is smaller (Stage 23), but the season also matters, and this stage cannot fully separate the two.

**Authority:** S2C stays lower authority, as pre-registered. The low-sun < 25° rule and baseline provenance are kept. Changing the lower-authority path does not grant authority.

## PART B — GEOMETRY

## 4. Geometry per pass

All 5,306 scenes the consensus and the Stage 23 corpus use have live STAC geometry:
- sun zenith and azimuth;
- mean view zenith and azimuth;
- relative orbit;
- time;
- glint angle ψ, the angle to the specular direction.

The STAC view zenith matches ACOLITE's per-point value to a median of 0.014°.

## 5. The geometry effect (Stage 23 floor, satellite-to-satellite only)

| Group | Pairs | Median \|Δvisibility\| | Systematic Δvisibility | State disagreement | Class jumps | Median \|Δ\| B02 / B04 / B05 |
|---|---:|---:|---:|---:|---:|---|
| Identical geometry (tandem) | 43 | 0.039 | 0.000 | 0% | 0% | 0.04 / 0.03 / 0.03 |
| Opposite side | 103 | 0.070 | +0.050 | 8.7% | 11.7% | 0.11 / 0.14 / 0.17 |
| — opposite, small glint-angle difference | 51 | 0.054 | +0.028 | 2.0% | 2.0% | 0.07 / 0.08 / 0.10 |
| — opposite, large glint-angle difference | 52 | 0.079 | +0.078 | 15.4% | 21.2% | 0.19 / 0.27 / 0.37 |

**Which variable predicts disagreement** (Spearman ρ with |Δp|):

| Variable | Pooled | Within opposite-side pairs |
|---|---:|---:|
| Opposite-side indicator | 0.22 | — |
| \|Δ view zenith\| | 0.18 | −0.03 |
| \|Δ glint angle\| | 0.34 | 0.30 |
| **min glint angle** | **−0.43** | **−0.48** |
| ACOLITE glint-reference difference | 0.09 | 0.03 |

**The continuous signal is better.** The glint angle of the view nearer the specular direction predicts disagreement best, beating the binary side rule by 0.21. The pre-registered rule therefore reports it as the better signal, while this stage's consensus still uses the frozen binary rule.

ACOLITE's own glint-reference difference does not predict disagreement.

**Truth-free check on the development inputs** (anchor against prior pass, median |Δp|):

| Prior-pass age | Same side | Opposite side |
|---|---:|---:|
| ≤ 5 days | 0.081 | 0.090 |
| 6–10 days | 0.092 | 0.130 |
| 11–15 days | 0.090 | 0.114 |

Opposite-side priors disagree more at every age. The geometry effect is present in the live evidence: 29% of used prior passes are opposite-side.

## 6. Compatibility rule and weight (frozen)

**The rule:**
- **Compatible** = same side;
- **Conflicted** = opposite side (wrapped view-azimuth difference > 90°), judged against the reference pass.

**The weight:** γ = 0.0088, from the visibility spread of opposite-side pairs (0.112) against identical ones (0.061). It is added to a conflicted pass's variance.

**Physical-pass independence is unchanged.**

## PART C — CONSENSUS

## 7. Candidates (causal, anchor plus ≤ 3 prior passes)

| Candidate | Window | Operational | Clear | Normal | Stained | Limited | Harmful | Severe | Unknown | Strong / accuracy | Feet shown / error / coverage | Passes | Murky too clear |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|
| **G0 = R0** | 5 | **0.710** | 0.884 | 0.671 | 0.606 | 0.680 | 11.44% | 1.39% | 9.9% | 10.9% / 92.9% | 84.8% / 1.34× / 68% | 1.36 | 17.5% |
| G0 | 10 | 0.719 | 0.889 | 0.680 | 0.616 | 0.692 | 11.57% | 1.20% | 8.7% | 16.2% / 93.6% | 86.5% / 1.33× / 69% | 1.68 | 17.8% |
| G0 | 15 | 0.728 | 0.889 | 0.686 | 0.644 | 0.693 | 12.26% | 1.33% | 7.1% | 20.6% / 94.7% | 88.9% / 1.34× / 68% | 1.96 | 18.4% |
| G1 weighted | 5 / 10 / 15 | 0.711 / 0.719 / 0.729 | | | 0.613 / 0.616 / 0.644 | | 11.4 / 11.6 / 12.3% | 1.39 / 1.20 / 1.39% | 9.9 / 8.7 / 7.0% | 10.8 / 16.0 / 20.5% | | | 17.3 / 17.5 / 18.4% |
| G2 refusal | 5 / 10 / 15 | 0.711 / 0.719 / 0.729 | | | 0.609 / 0.616 / 0.648 | | 11.4 / 11.6 / 12.2% | 1.39 / 1.20 / 1.26% | 9.9 / 8.7 / 7.1% | 11.2 / 16.3 / 20.7% | | | 17.5 / 17.8 / 18.2% |
| G3 matched | 5 | 0.714 | 0.884 | 0.669 | 0.620 | 0.683 | **11.19%** | 1.45% | 10.0% | 8.8% / 92.1% | 84.8% / 1.34× / 68% | 1.25 | **16.5%** |
| G3 matched | 10 | 0.723 | 0.884 | 0.686 | 0.619 | 0.702 | 11.31% | 1.52% | 8.8% | 12.8% / 93.5% | 86.3% / 1.34× / 68% | 1.47 | **16.5%** |
| **G3 matched** | **15** | **0.731** | 0.892 | 0.683 | **0.651** | 0.697 | 11.95% | 1.58% | 7.2% | 16.8% / 93.9% | 88.8% / 1.34× / 68% | 1.66 | 17.5% |

**Selected windows (Stage 19 rule):** 15 days for every candidate. The best Stage 24 candidate is **G3 at 15 days**.

**G3 at 15 days against R0** (whole-lake bootstrap, 95% CI):

| Measure | Δ | 95% CI | Criterion |
|---|---:|---|---|
| Operational | +0.020 | +0.009 to +0.033 | material: **pass** |
| Stained | +0.045 | +0.012 to +0.081 | pass |
| Limited | +0.017 | −0.007 to +0.041 | pass |
| Harmful | +0.005 | −0.004 to +0.015 | upper bound > 0.01: **fail** |
| Severe | +0.0019 | −0.002 to +0.006 | upper bound > 0.003: **fail** |

Every other criterion passes:
- Stage 16 bars;
- Strong accuracy 93.9%;
- exact feet 8/10;
- coverage, no future scene.

**Not adopted.** The final candidate stays **R0** (G0, 5 days).

**What the table shows:**
- **Geometry weighting (G1) and refusal (G2) barely move anything.** The γ term is small next to the existing tier and age variance, and genuine geometry-driven state conflicts are rare.
- **Geometry matching (G3) trades.** It removes conflicted passes, which lowers the murky-read-too-clear rate at 5–10 days (16.5% against 17.5%). It also costs Strong coverage (8.8% against 10.9% at 5 days) and adds severe errors.
- **The 15-day window is where the gain is,** with or without geometry. It also raises harmful answers, which is why no 15-day configuration passes the bar. Stage 19 found the same.

## PART D — ERROR MODES

## 8. Murky water read too clear (456 stained or limited rows, all ≤ 3 ft)

| | R0 | G0 at 15 d | G3 at 15 d |
|---|---:|---:|---:|
| Read too clear | 17.5% | 18.4% | 17.5% |
| Harmful | 19.3% | 20.2% | 19.5% |
| Severe | 4.2% | 3.5% | 4.0% |
| Operational | 0.643 | 0.669 | 0.674 |
| Feet bias | +0.129 | +0.131 | +0.127 |
| Feet error | 0.150 | 0.150 | 0.149 |
| Unknown | 15.4% | 10.8% | 10.8% |
| Mean posterior | 0.81 | 0.82 | 0.82 |
| Supporting passes | 1.34 | 1.93 | 1.68 |
| Opposite-side share of used priors | 28.7% | 26.1% | 0% |

**Geometry is not driving the false-clear failure.** Removing every conflicted pass leaves the too-clear rate where it was. The feet bias for murky water (+0.13 log10) is the same in every system: a property of the single-scene prediction, not of how scenes are combined.

## 9. Single-scene risk

**More evidence does not remove the false-clear risk.** Even when compatible evidence is added (G3), the too-clear rate holds.

**Counterfactual (not pre-registered as a candidate, reported only):**
- There are 155 lone Moderate plain-state answers below posterior 0.90; 29 are harmful.
- Widening each to its best adjacent pair would make 26 of the 29 correct, at the cost of turning the other 126 correct plain answers into boundary answers.
- It removes **no** severe error.

This is the strongest lead for a pre-registered decision-semantics stage.

## 10. Boundary states (R0)

| | Boundary | Plain |
|---|---|---|
| **All** | 15.4% of 812 | 10.6% of 530 |
| Clear truth | 13.7% of 219 | 0% of 420 |
| Normal truth | 9.0% of 289 | 100% of 37 |
| Stained truth | 18.1% of 171 | 100% of 17 |
| Limited truth | **28.6%** of 133 | 3.6% of 56 |
| One scene | 14.3% | 12.0% |
| Multi-scene | 17.4% | 7.7% |
| Compatible | 16.6% | 9.5% |
| Conflicted | 18.9% | 4.6% |

Each cell is the harmful rate among full-authority answers.

**Boundary states are the hard middle, not a cause.**
- A plain answer for normal or stained truth is always harmful, because those classes are almost never issued plainly. The boundary state is the correct expression of that uncertainty.
- The risk sits at the ends: a limited water body answered with a clearer boundary state is harmful 28.6% of the time.
- Geometry conflict raises boundary-state harm only slightly (18.9% against 16.6%).

**Boundary states were not removed.**

## 11. High-confidence wrong answers (R0, posterior ≥ 0.90)

There are 34 harmful answers among 522 high-posterior full-authority answers (6.5%).

| Trait | Harmful high-posterior answers | All high-posterior answers |
|---|---:|---:|
| Read too clear | **88%** | 6% |
| Truth class | normal 15, stained 13, limited 5, clear 1 | 76% clear truth |
| One scene | 59% | 63% |
| With an opposite-side pass | 18% | 14% |
| S2B | 65% | 54% |
| Anchor glint angle (median) | 34.2° | 34.9° |

**The pattern is optical, not geometric.** The confident wrong answers are murky water that the model scores as clear with high confidence, and they barely differ in geometry from confident right answers. Raising the posterior threshold would mostly remove correct clear-water answers. It was not done.

## PART E — STAINED, LIMITED, STRONG

## 12. Stained and limited

| System | Stained op | Truth in answer | Harmful | Severe | Unknown | Feet bias | Strong share | Limited op | Limited harmful | Limited severe | Limited feet bias |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Stage 16 (single scene) | 0.571 | 71.9% | 22.0% | 4.0% | 19.8% | +0.117 | 2.2% | 0.676 | 15.7% | 4.8% | +0.139 |
| **R0** | **0.606** | 74.5% | 21.1% | 4.0% | 15.9% | +0.113 | 3.1% | **0.680** | 17.5% | 4.4% | +0.150 |
| G0 at 15 d | 0.644 | 76.4% | 21.1% | 2.6% | 10.1% | +0.106 | 4.9% | 0.693 | 19.2% | 4.4% | +0.170 |
| G3 at 15 d | 0.651 | 77.0% | 20.7% | 3.1% | 9.7% | +0.112 | 4.4% | 0.697 | 18.3% | 4.8% | +0.164 |

**Against Stage 16:**
- R0 stained +0.034 (CI +0.007 to +0.063);
- G3 at 15 days stained +0.045 against R0 (CI +0.012 to +0.081).

The stained gains come with fewer Unknowns and no rise in stained harm. **Limited** reads +0.15 to +0.17 log10 too clear in every system, and longer windows make limited water's harm slightly worse.

## 13. Strong (frozen definition)

| | Strong answers | With an opposite-side pass | Accuracy, compatible only | Accuracy, with opposite-side |
|---|---:|---:|---:|---:|
| R0 | 156 | 61 | 92.6% | 93.4% |
| G0 at 15 d | 303 | 132 | 93.6% | 96.2% |
| G3 at 15 d | 246 | 0 (all compatible) | 93.9% | — |

**Strong by class (G3 at 15 d):**

| Class | Strong share | Accuracy |
|---|---:|---:|
| Clear | 26% | 100% |
| Normal | 7% | 65% |
| Stained | 4% | 33% |
| Limited | 13% | 96% |

**Geometry doesn't hurt Strong.** Strong built with an opposite-side pass is as accurate as compatible-only Strong.

**The geometry-strict alternative changes nothing.** SG (Strong also needs ≥ 2 agreeing compatible passes) gives the same 16.8% at 93.9% on G3. Strong for stained water stays rare and unreliable everywhere.

## 14. Exact feet

Capability is **8/10** for R0 and for G3 at 15 days.

**Across all candidates:**
- multiplicative error 1.33–1.34×;
- signed bias within ±0.005;
- coverage 68–69%;
- feet shown on 85–89% of rows.

Nothing regresses.

## 15. Checkpoints (final candidate R0)

| Check | Result |
|---|---|
| Stage 16 freeze bars | pass |
| 8/10 checkpoint | **fail**: op 0.710, weakest class 0.606, harmful 11.4%, severe 1.39%, Strong 10.9% |
| True 9/10 | fail |

**The best non-adopted configuration** (G3 at 15 days: 0.731, 0.651, 11.95%, 1.58%, 16.8%) would also fail 8/10.

## 16. Internal map

**The shadow** (`Sector_Engine` `feat/clarity-candidate-shadow`, local commit `4b54625`):
- nominal N0513+ S2C is answered on the raw path (`stage24-n0513-raw`, provenance v3 with the Stage 24 hashes);
- the Stage 12 answer is kept beside it for comparison, at lower authority;
- N0511/N0512 keep C3;
- the stored N0513 scenes were re-answered by a Mac run.

**The app** (`Sector-mapbox`, local): the candidate card's source line now shows satellite, processing baseline and path, for example "Sentinel-2C, N0513, raw path", beside the existing Candidate status, observation time, age and evidence.

**Public users are unchanged.** No consensus change is surfaced, because nothing was adopted.

## 17. Provenance

**`dev24_final_provenance.json`.** For every R0 answer, each contributing pass records:
- item, satellite and age;
- tier and its state;
- sun and view geometry;
- compatibility (same or opposite side);
- base variance, geometry variance and final normalised weight.

A future audit can see exactly why each pass influenced an answer.

## 18. Status of the evidence

**Every truth pool has been seen before;** none is blind.

| Track | Score |
|---|---|
| Development | 7/10 |
| Certified | none |
| Deployed production | 2/10 |

## 19. Files (`research/clarity-candidate/stage24/`)

**Pre-registration and freeze:**
- `PREREGISTRATION_STAGE24.md`;
- `FREEZE_STAGE24.json`. It was restored once after a variable-shadowing bug overwrote it with Stage 23's record. It was re-hashed from the unchanged files, and the note is in the file.

**Geometry and pairs:**
- `geom24_meta.py` → `geom24_items.json`;
- `build24_pairs.py` → `pairs24_meta.json`;
- `build24_tasks.py`.

**Derivation and analysis:**
- `derive24.py` → `derived24.json`;
- `geom24.py` → `geom24.json`;
- `anal24.py` → `eval24_n0513.json`;
- `dev24.py` + `report24_block.py` → `dev24_report.json`, `dev24_final_rows.json`, `dev24_final_provenance.json`.

**Results:** `res24_T24N/`, `res24_T2N_N2/`.

## 20. Status

N0513 BEST PATH: RAW

N0513 SENSOR-RELATIVE VISIBILITY BIAS:
- +0.020 on 41 new pairs; C3 −0.035, N2 −0.011.
- +0.007 on the Stage 23 derivation pairs.

N0513 SECCHI BIAS: not measurable. No N0513 truth row exists; the truth corpus predates N0513.

N0513 LOWER-AUTHORITY PATH UPDATED: YES
- The internal shadow answers nominal N0513 S2C raw; N0511/N0512 keep C3.
- Authority stays lower.
- Caveat: C3 also over-corrects Sep–Oct 2025 N0511 pairs (−0.063), so season contributes.

VIEWING-GEOMETRY EFFECT CONFIRMED: YES
- Opposite-side against identical views: visibility 0.070 against 0.039; class jumps 11.7% against 0%.
- Also in the development inputs at every prior-pass age.

BEST GEOMETRY COMPATIBILITY SIGNAL: the minimum glint angle of the pair (angle to the specular direction).
- Spearman −0.43 pooled and −0.48 within opposite-side pairs, against 0.22 for the same/opposite-side rule.
- ACOLITE's glint-reference difference does not predict (0.09).

GEOMETRY-AWARE CONSENSUS USEFUL: NO
- G1 weighting and G2 refusal change almost nothing.
- G3 matching at 15 days gains operational +0.020 (CI +0.009 to +0.033) and stained +0.045, but harmful (+0.005, CI to +0.015) and severe (+0.0019, CI to +0.006) fail the non-worse bar.
- No-geometry 15-day consensus reaches 0.728.

BEST LIVE CONSENSUS METHOD: G0 = R0 (Stage 19 inverse-uncertainty causal consensus, C3/raw S2C at lower authority; no geometry treatment adopted)

BEST LIVE WINDOW: causal, past 5 days (R0; every candidate's selected window was 15 days, none adoptable)

ANSWER COVERAGE / UNKNOWN SHARE: 90.1% answered / 9.9% Unknown.
- Feet shown on 84.8% of rows.
- 1.36 passes per answer.

CLEAR SCORE: 0.884

NORMAL SCORE: 0.671

STAINED SCORE: 0.606

LIMITED SCORE: 0.680

MURKY-WATER-READ-TOO-CLEAR RATE: 17.5% of stained/limited truth rows (80 of 456).
- G3 at 5–10 days 16.5%; 15-day systems 17.5–18.4%.

HARMFUL RATE: 11.44%

SEVERE RATE: 1.39%

EXACT-FEET CAPABILITY: 8/10 (1.34×, bias +0.001, coverage 68%, feet on 85%)

STRONG EVIDENCE SHARE / ACCURACY: 10.9% / 92.9%
- Clear 17% at 100%; normal 5% at 53%; stained 3% at 50%; limited 6% at 100%.

STAGE 16 FREEZE BARS PASSED: YES

8/10 DEVELOPMENT CHECKPOINT PASSED: NO

TRUE 9/10 DEVELOPMENT BAR PASSED: NO

CURRENT CLARITY SCORE RECOMMENDATION: 7/10 development (uncertified); certified none; deployed production 2/10

REMAINING TECHNICAL LIMITATIONS:
- **The false-clear failure is in the single-scene prediction, not in consensus geometry.** Murky water reads +0.13 log10 too clear, and limited water +0.15, under every combination rule. Confident-wrong answers are 88% false-clear, with geometry like correct ones.
- **The pre-registered binary geometry rule was weaker than the glint-angle signal found** (|ρ| 0.22 against 0.43). Even so, removing conflicted passes entirely (G3) did not reduce severe errors. A glint-angle weighting would need its own pre-registration and is unlikely to be the main lever.
- **Longer windows help stained water and Strong coverage but raise harmful answers.** No configuration meets the harm/severe bar.
- **The single-scene widening counterfactual** (26 of 29 harmful lone answers would become correct boundary answers) is the most promising untested decision-semantics change. It needs a fresh pre-registration and touches no severe error.
- **The N0513 fix rests on 2-day pairs and cannot be separated from season;** C3 also over-corrects autumn N0511. No N0513 truth exists yet.
- **Stained Strong is rare and unreliable;** Strong for stained water needs evidence the corpus does not have.
- **Every truth pool has been seen;** no blind data.

Stop.
Do not promote public production.
