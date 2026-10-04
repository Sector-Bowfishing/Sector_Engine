# Stage 24 pre-registration — geometry-aware consensus and N0513 baseline recovery

Written and frozen before any Stage 24 reflectance is read, before any relation between geometry and disagreement is computed, and before any Stage 24 consensus is scored. `FREEZE_STAGE24.json` holds this file's SHA-256. Values derived later by the rules below (N2 offsets, the geometry variance term) are frozen as `derived24.json`, with their hash added before any validation or consensus scoring.

## 0. Already known when writing

**From earlier stages:**
- every Stage 16–23 result, including Stage 23's N0513 numbers:
  - T2N: C3 −0.051 against raw +0.007;
  - top-of-atmosphere offsets B11 +0.00105 and B12 +0.00055 against N0511's +0.0030 and +0.0016;
- Stage 23's floor aggregates: tandem within 0.5%; adjacent tracks differ 20–28%, visibility +0.048.

**Stage 24 metadata only:**
- `geom24_items.json`: STAC geometry for 5,306 scenes;
- `pairs24_meta.json`: 80 new N0513 candidate pairs at 76 lakes;
- distributions of geometry differences, with no reflectance or visibility attached:
  - floor tandem pairs: view azimuth difference about 1°, glint difference about 0.1°;
  - floor adjacent pairs: about 178° and about 10°;
  - development priors against their anchor: 1,156 same orbit and same side, 508 different orbit and opposite side, 18 other.

## 1. Unchanged and preserved

**Not changed:**
- the C-gbm (not refit);
- the Stage 16 posterior gate;
- the Stage 19 consensus code (only the patches in section 9);
- ACOLITE K4 and the instrumented runner;
- C3 for N0511/N0512;
- the Strong definition (section 10 adds a reported alternative, never a silent change);
- the Stage 16 freeze bars, the Stage 23 8/10 checkpoint and the true 9/10 bar.

**Not done:**
- Stage 12 is not restored;
- no fitting to field reports or Secchi;
- no future observation is used.

**Preserved, separately and unchanged:** R0, Stage 16, Stage 18, the Stage 23 corpus and C3.

**S2C authority stays lower in Stage 24.** Stage 23's floor was unusable and no new floor is built, so no S2C authority test is re-run. The low-sun (< 25°) restriction and baseline provenance are kept.

## PART A — N0513

## 2. Sets

| Set | What | Role |
|---|---|---|
| **T2N** | Stage 23's N0513 2-day pairs (reused, already seen) | Derivation |
| **T24N** | **New**: N0513 S2C → S2A, same relative orbit and tile, 48 ± 1 h, S2C sun ≥ 25°, both ≤ 40% tile cloud, Aug–Oct 2026, one per (site, S2C pass); no item pair shared with T2N; Stage 20 sites (any latitude, inland and coastal) plus one point per pilot lake | Validation, never used to derive |
| **Seasonal control** | Stage 22's Sep–Oct 2025 T2 pairs (N0511) | Descriptive: is the N0513 failure seasonal? |

**Validity and the ice screen** as Stage 23, with S2C sun ≥ 25°.

## 3. N0513 candidate paths

| Path | Definition |
|---|---|
| **N0** | Raw nominal N0513: frozen ACOLITE K4, no TOA offset, no B05 adjustment, no Stage 12 |
| **N1** | C3 (the Stage 21 B11/B12 offsets, then the B05 adjustment); historical |
| **N2** | An N0513-specific physical correction, created only if the T2N top-of-atmosphere evidence supports it (below) |

**N2 rule:**
- For each of B08, B8A, B11 and B12, take the per-pair S2C − S2A disk-median TOA reflectance difference on valid T2N pairs.
- If the pair-bootstrap 95% CI of the median (B = 2000, seed 24) excludes 0, that band's offset is the median; otherwise 0.
- N2 removes those constant offsets before ACOLITE, then applies the B05 adjustment.
- If no band qualifies, N2 is not created.

## 4. Selection and validation

**Selection, on T2N only:**
- J = |median Δp| against S2A.
- The lowest J wins; ties within 0.005 go to the simpler path, in the order N0 < N1 < N2.

**Validation, on T24N:** the winner passes if both hold:
- |median Δp| ≤ 0.03;
- |median Δp(winner)| < |median Δp(N1)|.

**Also reported:** band ratios, state overlap, class jumps and regions.

**Path update.** The nominal-N0513 lower-authority path changes to the winner only if the winner is not N1 and validation passes. Otherwise C3 stays.

**Secchi.** Any N0513 S2C truth rows are reported for N0, N1 and N2 as validation only. They never select.

## PART B — GEOMETRY

## 5. Geometry per pass (live scene metadata)

**From the STAC item:**
- θs = 90° − sun elevation, and the sun azimuth φs;
- θv = mean view incidence, and the view azimuth φv;
- relative orbit, acquisition time, platform and tile.

**Glint angle:** ψ = arccos(cos θs cos θv − sin θs sin θv cos(φs − φv)). The corpus already uses this form; smaller ψ means nearer the specular direction.

**ACOLITE glint diagnostics** (glint reference, rhog, per-point vza/raa) are recorded wherever the instrumented runner ran. For FL23 and T2N they are reported against the metadata geometry.

## 6. Pair geometry and the compatibility rule

**Variables for a pair (a, b):**
- same relative orbit;
- side = **opposite** if the wrapped |φv,a − φv,b| > 90°, else same;
- |Δθv|, |Δψ| and min ψ;
- (FL23 only) |Δ glint reference| and |Δ rhog B04|.

**Groups reported:**
- identical (same orbit, < 1 h apart: the FL23 tandem);
- opposite side (FL23 adjacent);
- for development anchor–prior pairs, which are truth-free: same orbit / same side by age (≤ 5, 6–10, 11–15 days), opposite side by age, and the remainder.

**Outcome measures (truth-free):**
- |d_b|;
- |Δp|;
- state disagreement;
- class jumps;
- posterior difference.

**The signal.** On pooled valid FL23 pairs:
- Spearman ρ of |Δp| against each metadata variable (opposite-side indicator, |Δθv|, |Δψ|, min ψ);
- within the opposite-side group, ρ of each continuous variable;
- the ACOLITE glint-reference difference, reported beside them.

**The compatibility rule is the binary side rule:**
- **Compatible** = same side;
- **Conflicted** = opposite side.

This is the simplest model, and the consensus inputs are bimodal. A continuous variable is reported as better only if it beats the indicator's pooled |ρ| by ≥ 0.05. Even then, it is not used in this stage's consensus.

**The variance term, frozen in `derived24.json`.** γ = σ²(opposite) − σ²(identical), where σ = 1.4826 × MAD of Δp on FL23 valid pairs (floored at 0). The systematic opposite-side shift is reported, not used.

**Truth-free check on development pairs.** The median |p_anchor − p_prior| (outer predictions), same side against opposite, within each age bin.

**Independence is unchanged.** Physical-pass deduplication stays exactly as Stage 19; compatibility is a separate dimension.

## PART C — CONSENSUS

## 7. Candidates (each at windows 5, 10 and 15 days; causal; anchor plus ≤ 3 independent prior passes)

**The reference pass** is the anchor when it has a valid sample, otherwise the newest used prior. Conflict is always judged against the reference.

| Candidate | Definition |
|---|---|
| **G0** | R0: Stage 19 inverse-uncertainty consensus, C3 lower-authority S2C, no geometry |
| **G1** | Weights 1 / (σ_tier² + κ·age + γ·conflicted) |
| **G2** | G0's consensus, but if any used conflicted scene's own state is disjoint from the issued state, the answer reverts to the anchor's Stage 16 single-scene product (consensus off, so never Strong) |
| **G3** | Only compatible passes (the reference plus priors compatible with it) are combined |

**Each candidate's** n2/n3 calibration is fitted on its own inner folds, exactly as Stage 19 does for its method.

**Window per candidate,** by Stage 19's rule:
1. the configuration passes the Stage 16 bars;
2. take the highest operational score;
3. choose the smallest window whose operational and stained lake-bootstrap CIs against the best both include 0.

**Best Stage 24 candidate:** among G1–G3, the selected configuration with the highest operational score that meets the coverage floor:
- Unknown ≤ R0's + 0.05;
- feet availability ≥ R0's − 0.05.

## 8. Adoption bar (against R0 = G0 at 5 days)

**Every one of these:**
- the Stage 16 freeze bars pass;
- operational Δ ≥ +0.02, with lake-bootstrap 95% CI lower bound > 0;
- harmful Δ ≤ 0, or its 95% CI upper bound ≤ +0.01;
- severe Δ ≤ 0, or its 95% CI upper bound ≤ +0.003;
- stained Δ ≥ −0.01;
- limited Δ ≥ −0.02;
- Strong accuracy ≥ 0.90;
- exact-feet capability ≥ 8/10;
- the coverage floor holds;
- no future scene.

**Bootstrap:** whole-lake, B = 2000, seed 24. If any part fails, Stage 24 is not adopted.

## 9. dev24.py

**`stage23/dev23.py`'s R0 patches** (C3 samples, S2C lower authority, base23), plus:
- pass geometry carried in the scene list;
- a method switch for G0–G3 inside `build()` and `combine()`;
- the geometry-composition and weight provenance dump.

**Windows** are 5, 10 and 15 for every candidate.

## 10. Strong

**The frozen definition for every candidate:** posterior ≥ 0.90, ≥ 2 agreeing full-authority passes, no disjoint state.

**Reported:**
- the share of Strong answers built only from compatible passes, against those including a conflicted pass;
- Strong share and accuracy by class.

**SG (reported, not adoptable here):** Strong additionally requires ≥ 2 agreeing *compatible* passes. It is compared against the frozen definition on the best candidate.

## PART D — ERROR MODES (diagnostic; nothing tuned on them)

## 11. Murky water read too clear

**Murky rows:** truth Secchi ≤ 3 ft, or truth class stained/limited (both reported).

**Per candidate:**
- operational, harmful and severe;
- feet bias and error;
- Unknown share and mean posterior;
- supporting passes and the share of geometry-conflicted support;
- the **murky-read-too-clear rate**: harmful answers on stained/limited truth whose answer classes are all clearer than the truth, divided by all stained/limited truth rows.

## 12. Single-scene caution

**Not justified as a candidate.** Stage 23's severe errors carried posteriors of 0.72–0.98, half ≥ 0.93, so a posterior-based caution cannot target them without large coverage loss.

**Reported as a counterfactual only:** how many harmful/severe lone Moderate answers would become boundary states if a plain state below posterior 0.90 were widened to its best adjacent pair, and the effect on coverage.

## 13. Boundary states and confident-but-wrong answers

**Boundary states.** Harmful rate for boundary against plain states, conditional on truth class, one-scene against multi-scene, and compatible against conflicted.

**Confident but wrong** (posterior ≥ 0.90, harmful). Their composition by:
- one scene or several;
- side geometry and glint angle (ψ);
- satellite;
- truth class;
- direction.

## 14. Stained, limited and exact feet

**For Stage 16, R0 and each candidate:**
- operational and truth-in-answer;
- harmful, severe and Unknown;
- feet bias and error;
- mean posterior and Strong share.

**Bootstrap** (whole lake) of the best candidate against R0 and Stage 16, for stained and limited.

**Exact feet per candidate:**
- median multiplicative error and signed bias;
- coverage and availability;
- capability.

## 15. Checkpoints (unchanged)

**8/10 (Stage 23):**
- operational ≥ 0.75;
- weakest class ≥ 0.65;
- harmful ≤ 10%;
- severe ≤ 1.0%;
- Strong share ≥ 25% at accuracy ≥ 90%;
- exact feet ≥ 8/10.

**9/10:**
- operational ≥ 0.85;
- weakest class ≥ 0.80;
- harmful ≤ 5%;
- severe ≤ 0.5%;
- Strong share ≥ 50% at accuracy ≥ 90%.

## 16. Internal map and provenance

**If the N0513 path is updated (section 4):**
- the shadow's nominal-N0513 S2C answers move to the winner, and stored N0513 scenes are re-answered;
- the Water Clarity layer and candidate card show the processing baseline and S2C path, beside the existing candidate status, observation time, age, evidence and satellite.

**If Stage 24 is adopted,** the candidate consensus is surfaced the same way.

**Public users are unchanged.**

**Per-answer provenance (`dev24_*_provenance.json`):** for each contributing pass:
- satellite, relative orbit and acquisition time;
- θs, φs, θv, φv and ψ;
- compatibility;
- base uncertainty weight, geometry weight and final weight.

## 17. Status

Every truth pool has been seen before. Stage 24 is development research: development, certified and deployed stay separate.
