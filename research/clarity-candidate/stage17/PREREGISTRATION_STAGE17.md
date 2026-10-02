# Stage 17 pre-registration: the multi-scene consensus engine

**Timing.** Written 2026-10-01, before any neighbouring-scene prediction, rainfall value or consensus number existed.

**What has been looked at** (value-blind): only the count of Stage 11 production-gated neighbour passes (valid Sen2Cor
disks) per development event and window.

**What is not used:**
- the Stage 16 fresh holdout;
- the Stage 14/15 certification set;
- Sector field reports.

This file's sha256 goes into `FREEZE_STAGE17.json`.

## 1. The frozen single-scene engine (unchanged)

**What every scene goes through:**
- the frozen ACOLITE path (`run_cert_aco_a1.py`, K4, EPQS elevation, M0/M3 sampling, the 60 m disk);
- C-gbm.

**Fold models.** For whole-lake-held-out evaluation, an event's scenes are predicted by the outer-fold C-gbm fitted
without that event's lake, exactly as in Stages 14–16. Calibration uses the inner folds. The production pickle is not
changed.

**The baseline is Stage 16 unchanged:**
- the anchor scene, which is the matched pass;
- its tier and S2C rules;
- the posterior gate (τ₁ = τ₂ = 0.70);
- tier-2 boundary-only.

## 2. The temporal evidence window

**Which scenes.** For each development event, the neighbours are the Stage 11 passes with a valid Sen2Cor disk
(≥ 5 pixels, the production gates), excluding the anchor item. The **3 nearest by |Δt|** (then lowest scene cloud)
within ±10 days are run through the frozen path. The actual Δt is kept for every scene.

**Windows evaluated:** ±3, ±5, ±7 and ±10 days, each a subset of the same scenes.

**What a scene contributes.** Only tier-1 or tier-2 scene outputs (frozen ACOLITE plus C-gbm). Tier-3 scenes are not
combined, because Sen2Cor-C3 is a different, lower-authority predictor.

## 3. Hydrologic compatibility

**The data.** Open-Meteo ERA5 daily precipitation at the event site (NASA POWER if unavailable). It is used only to
decide compatibility, never to estimate clarity.

**The rule.** A neighbour is **incompatible** with the truth date if, over the days from the earlier of the two dates to
the later (inclusive of the later date):
- total precipitation ≥ 20 mm; **or**
- any single day has ≥ 12.7 mm (0.5 in).

**Two variants are evaluated:**
- **H1**, with the rule;
- **H0**, without it. H0 is kept only to measure whether the rule matters.

**Scene quality and spectral change** are handled by tier, and by the robust method's down-weighting (section 4). No
scene is dropped for disagreeing, which would repeat Stage 11's median replacement.

## 4. Consensus methods

Each contributing scene i gives a prediction pᵢ (log10 ft), a tier, a platform and |Δtᵢ|. Its variance is
σᵢ² = σ²_tier + κ·|Δtᵢ|:
- σ_tier is the lake-held-out residual SD of tier-1 and tier-2 scenes;
- κ is the growth in pairwise prediction-difference variance per day of separation.

Both are fitted on training lakes.

| Method | How the scenes are combined |
|---|---|
| **M-agree** (agreement only) | The prediction stays the anchor's. Neighbours change only the evidence level (section 6) |
| **M-iuw** (inverse uncertainty) | p_c = Σ pᵢ/σᵢ² / Σ 1/σᵢ² |
| **M-robust** (robust weighted likelihood) | Huber M-estimate with weights 1/σᵢ² and c = 1.5 (iteratively reweighted). A scene far from the others is down-weighted, not replaced |
| **M-bayes** (latent state) | A Gaussian prior on the true log Secchi (the training-lake mean and variance), updated by every scene as a measurement with variance σᵢ² |

**Calibration and states.**
- The class posteriors for p_c are refitted (nested) separately by the number of contributing full-authority scenes:
  1, 2, and ≥ 3.
- The Stage 16 gate thresholds stay at 0.70 / 0.70.
- If no scene contributes, the event falls back to Stage 16 (anchor only).
- If every contributor is tier 2, the answer is boundary-only (the Stage 16 tier-2 rule).

## 5. Sentinel-2C

**Two variants:**
- **S-off:** S2C scenes never contribute.
- **S-agree:** an S2C scene contributes only if:
  - at least one S2A/B full-authority scene also contributes;
  - its own gate state shares a class with the S2A/B consensus state;
  - it is hydrologically compatible.

  An answer whose only full-authority scenes are S2C stays lower authority, as in Stage 16.

**S2C AGREEMENT CAN UPGRADE AUTHORITY: YES** only if, under S-agree, two things hold against S-off:
- the answers whose evidence level was raised by an agreeing S2C scene are right ≥ 90% of the time (n ≥ 30);
- the harmful rate does not rise.

## 6. Strong evidence (agreement rule, fixed here)

An answer is **Strong** only if all of these hold:
1. it is at full authority;
2. the posterior of the issued state is ≥ 0.90;
3. at least **2 compatible full-authority scenes** (counting the anchor) have individual gate states that contain the
   issued state;
4. no compatible full-authority scene has a state disjoint from it.

**The other levels:**
- **Moderate:** any other full-authority answer.
- **Weak:** lower authority.
- **Unavailable:** Unknown.

## 7. Selection (development only, whole-lake held out)

**What is evaluated.** All 4 methods × 4 windows × H0/H1 × S-off/S-agree.

**Choosing the window and method:**
- **The candidates.** Variants whose harmful and severe rates are not above Stage 16's.
- **The winner.** Among those, the highest class-balanced operational score.
- **Ties.** Any variant within 0.01 of that score counts as tied, and the simplest wins. Simplicity order:
  - methods M-agree < M-iuw < M-robust < M-bayes;
  - windows smaller < larger;
  - H1 before H0;
  - S-off before S-agree.

**MULTI-SCENE CONSENSUS USEFUL: YES** only if all of these hold for the selected variant against Stage 16:
- the stained operational score rises by ≥ 0.05, with the lake-bootstrap 95% CI of the difference above 0 (2,000
  resamples, seed 17);
- the harmful and severe rates do not rise;
- the class-balanced operational score does not fall.

## 8. Bars (fixed here, never lowered)

**The Stage 16 freeze bars:**
- operational ≥ 7/10;
- every core class ≥ 0.60;
- harmful ≤ 15%;
- severe ≤ 2%.

**The true 9/10 development bar.** All of these:
- operational ≥ 0.85;
- weakest core class ≥ 0.80;
- harmful ≤ 5%;
- severe ≤ 0.5%;
- Strong ≥ 50% of usable (non-Unknown) answers;
- Strong truth-in-answer ≥ 90%.

**DEVELOPMENT CAPABILITY:** round(10 × the class-balanced operational score) on development.

**READY TO MOVE TO WATER TEMPERATURE: YES** only if both:
- the true 9/10 bar is passed on development;
- or the Stage 16 freeze bars are met on development **and** a future unseen certification pool exists.

A Stage 17 design is never certified by Stage 17's own data.
