# Stage 14 pre-registration: product semantics, engine choice and blind certification

**Timing.** Written 2026-10-01:
- before any band, comparison, tier-3 or clear-water number in sections 2–6 was computed;
- before any Secchi value of the certification set was read.

**What exists already:**
- the certification protocol `cert/CERT_PROTOCOL_STAGE14.md`, frozen at 03:19:55Z;
- its value-blind sample build, now running.

**Freezing.** This file's sha256 goes into `FREEZE_STAGE14.json`. Development computations follow it. The engine
manifest (`engine/`) is then frozen and hashed, and only after that are the certification values unsealed. Nothing
learned from certification changes the engine.

## 1. The frozen candidates (Stage 13, no retuning)

**The common path:**
- ACOLITE 20260421.0 K4 with lake-elevation pressure;
- S2C V-ρw production coefficients (`stage12/harm/score_tandem.json`);
- 60 m disk, at least 5 valid pixels.

**Tiers:**

| Tier | Source | Authority |
|---|---|---|
| 1 | The default ACOLITE mask | ACOLITE |
| 2 | M3, the relaxed mask, where tier 1 has no disk | ACOLITE |
| 3 | C3 on Sen2Cor reflectance, where tiers 1–2 have none | Lower authority |
| Unknown | None of the above | — |

**Models.** Both are fitted on all 1,206 E13 tier-1 rows. Guntersville and certification rows are excluded.
- **C-gbm:** the Stage 13 seven-feature constrained boosting, with the same hyperparameters and seed.
- **O2:** C-lin, the six-feature OLS, with its class cut-points learned on inner-fold predictions (the Stage 13 rule).

**Applying them:**
- Tier-2 rows use the same tier-1 fits on M3 reflectance.
- The tier-3 C3-Sen2Cor coefficients are fitted on all 1,582 processed development rows.

## 2. The product output

**Seven states:** Clear, Normal, Normal-to-Stained, Stained, Stained-to-Limited, Limited, Unknown / Low Authority. The
specification has no Clear-to-Normal state, so the 6 ft boundary stays a hard boundary.

**Boundary bands (frozen uncertainty, not labels).** Each band is fitted for the 3 ft and the 2 ft boundary b, with
every quantity in log10 ft:
- **The predictor.** p is the engine's continuous prediction, d = p − b, and y is the true log Secchi.
- **The fit.** A logistic model P(y ≥ b | d) = σ(α + βd) is fitted on development lake-held-out predictions with
  |d| ≤ 0.30, pooling tiers 1–2.
- **The edges.** The band runs from d⁻ to d⁺:
  - P = 1/3 at d⁻ = (−ln 2 − α)/β;
  - P = 2/3 at d⁺ = (ln 2 − α)/β.

  Inside the band, neither side of the boundary is twice as likely as the other. 2:1 odds is the IPCC "likely" level.
- **Two floors:**
  - each edge lies at least 0.05 from b. That is the Stage 13 ±12% platform band, the smallest band at which S2A and
    S2C stop flipping;
  - the band always contains b, so the displayed feet never contradict the state.

**State from p, at tiers 1–2:**
- p inside the 3 ft band → **Normal-to-Stained**;
- p inside the 2 ft band → **Stained-to-Limited**;
- p inside both → the band whose boundary is nearer;
- otherwise, the hard class of p (6/3/2 ft; O2 uses its own learned cut-points).

**Feet.**
- **When exact feet show.** Alongside the state, whenever the hard class of p is authorised.
- **The authorisation rule** is the Stage 12 rule on pooled development lake-held-out predictions of that class
  (n ≥ 10):
  - median |log| ≤ 0.15;
  - |median signed| at most 1.5 ft (clear), 1.0 (normal) or 0.75 (stained, limited).
- **The uncertainty interval:** p plus the 1/6 and 5/6 quantiles of the pooled development residuals y − p (tiers 1–2),
  a central two-thirds interval.

**Tier 3.** Its behaviour is set by section 6. Anything that section disallows becomes Unknown / Low Authority.

**Fitting rules.** For development evaluation, every band, authorisation and tier-3 rule is fitted inside training
folds (nested: inner lake-folds of the outer training lakes) and applied to the held-out fold. The production values are
fitted on all development rows.

## 3. Metrics

**Original hard-class metrics.**
- These are unchanged from Stage 13: recall, precision, balanced accuracy and κ on the hard class of p.
- A boundary state never enters them.
- They are reported for tiers 1–2, and for tiers 1–3 with tier 3's hard class.

**Decision quality (new).** On rows answered at ACOLITE authority (tiers 1–2):
- **Correct:**
  - the state is the true class;
  - or it is Normal-to-Stained and the truth is normal or stained;
  - or it is Stained-to-Limited and the truth is stained or limited.
- **Wrong:** anything else.

**Reported:**
- per true class: decision recall, i.e. the correct share of that class's answered rows;
- per class c: decision precision, i.e. among rows whose state includes c, the share whose truth is in the state;
- per issued state: its precision;
- specificity: the share of answers that are a single class;
- decision-balanced accuracy: the mean of the four decision recalls.

**Kept apart:** Unknown, and tier-3 (lower-authority) answers, are reported separately and never pooled into decision
quality.

**Feet:** median |log|, median signed ft by class, and the coverage of the two-thirds interval.

## 4. O2 against C-gbm (development data only)

**What is compared.** Both engines on development tier-1–2 rows: lake-held-out predictions, nested bands, and each
engine's own hard rule outside the bands.

**The criteria:**
- **Primary:** decision-balanced accuracy.
- **Also reported:**
  - specificity;
  - original balanced accuracy;
  - feet error;
  - the inconsistency rate: the share of rows whose displayed feet fall outside the classes their state names. O2 shows
    C-lin feet with learned cut-points.

**The rule.** C-gbm produces exact feet, an uncertainty interval and a product state from a single prediction, so it is
the frozen production candidate. The one exception: if O2's decision-balanced accuracy beats C-gbm's by ≥ 0.03, with the
lake-bootstrap 95% CI of the difference above 0 (2,000 resamples, seed 14), O2 is chosen. C-lin with standard cuts is
reported for reference only.

## 5. Clear water: where the −2.3 ft comes from (development, diagnostic only)

**The data:** clear development rows (true ≥ 6 ft, tiers 1–2, lake-held-out) of the frozen candidate.

**The breakdown,** by true-Secchi bin (6–8, 8–10, 10–13, 13–20, ≥ 20 ft):
- median signed ft;
- median signed log;
- each bin's share of the total signed ft.

**Calibration by prediction:** the median of (true − predicted) for rows predicted at 6 ft or more.

**The tests:**
- **Tail problem:** the 6–10 ft bins have |median signed| ≤ 1.5 ft, and the ≥ 13 ft bins have median signed ≤ −3 ft.
- **Concentrated in very deep or very clear water:** ≥ 13 ft rows carry > 50% of the total negative signed ft.
- **Constant bias:** the bin medians in ft span ≤ 1.0 ft, with an overall |median| > 1.0 ft.
- **Proportional:** the bin medians in log span ≤ 0.05, while the ft medians span > 1.0 ft.

More than one test may hold. **Regression to the mean** is checked too: an estimator calibrated for E[y | p] is
necessarily biased low, conditional on a high truth. Nothing is corrected.

## 6. Tier-3 behaviour (development tier-3 rows only)

**The predictions.** Tier-3 rows get lake-held-out C3-Sen2Cor predictions, and tier-3 bands come from the section 2 rule
fitted on tier-3 rows (nested).

**The options:**
- lower-confidence feet;
- class only;
- a broad boundary state only;
- Unknown.

**The rule, precision first:**
1. **States.** A state is allowed at tier 3 only if its development decision precision is ≥ 0.75, over n ≥ 15 rows.
2. **Disallowed states** become Unknown / Low Authority.
3. **Feet.** Allowed single-class states also show lower-confidence feet, but only if that class's tier-3 feet meet the
   Stage 12 PARTIAL bars: median |log| ≤ 0.20, and |median signed| at most 2.5 ft (clear), 1.5 (normal) or 1.0
   (stained, limited).
4. **The behaviour reported** is the combination that results. Coverage never overrides the precision bar.

## 7. Certification scoring (once)

**Rows.** The frozen engine is scored on the US core: NLA plus the WQP tier.

**Breakdowns:**
- by source;
- by tier;
- by platform (S2A / S2B / S2C, where n ≥ 20);
- warm (May–September) against cool (October–April);
- by the 5 Stage 13 regions;
- the strict-independence subset.

SYKE is scored the same way and reported apart.

**What is reported:**
- exact feet;
- the original hard classes;
- the product states;
- clear, normal, stained and limited;
- algae and sediment.

**Readiness lines** (class minima from the protocol; a class below its minimum is NO, insufficient):

| Line | Rubric | YES | PARTIAL |
|---|---|---|---|
| CLEAR FEET READY | Exact feet, clear (the Stage 12 rubric as coded in `capscore13.py`) | SUPPORTED | PARTIAL |
| NORMAL / STAINED / LIMITED READY | Boundary-aware product rubric (section 8), for that class | SUPPORTED | PARTIAL |
| ALGAL / SEDIMENT READY | Product rubric, algae and sediment | SUPPORTED | PARTIAL |

**BLIND CERTIFICATION PASSED** scores each of the six lines YES = 1, PARTIAL = 0.5, NO = 0:
- **YES** if all six are YES;
- **PARTIAL** if the total is ≥ 3;
- **NO** otherwise.

## 8. Rubrics

- **Exact feet, and the original hard class:** the Stage 12 section 5 rubrics, exactly as coded in
  `stage13/analysis/capscore13.py`.
- **Boundary-aware product** (new; seven capabilities; SUPPORTED 1, PARTIAL 0.5; the total out of 7 scaled to 10 and
  rounded):

| Capability | SUPPORTED | PARTIAL |
|---|---|---|
| Clear / normal / stained / limited | Decision recall ≥ 0.75, decision precision ≥ 0.75, and ≥ 70% of the class's rows answered at ACOLITE authority | Decision recall ≥ 0.60, decision precision ≥ 0.60, and ≥ 50% answered at authority |
| Algae | Decision accuracy in algal water ≥ the best constant state + 0.10, and \|median signed ft\| ≤ 1.0 | Decision accuracy ≥ constant + 0.05 |
| Sediment | Bright sediment (turbidity ≥ 20) given Clear ≤ 5%, and decision accuracy ≥ constant + 0.10 | Bright sediment given Clear ≤ 15% |
| Bottom-risk | — | — (no depth input; NOT) |

The 0.60 product PARTIAL bar is the hard-class SUPPORTED bar: a boundary state is easier to get right, so its bars sit
higher.

## 9. Capability and readiness lines

- **EXACT-FEET and ORIGINAL HARD-CLASS HISTORICAL CAPABILITY:** the frozen candidate on development rows, tiers 1–3,
  with the Stage 13 procedure (inner-fold feet authorisation).
- **BOUNDARY-AWARE PRODUCT CAPABILITY:** the section 8 product rubric on development rows (historical). The
  certification score is reported beside it.
- **CURRENT CLARITY PRODUCT READINESS:**
  - The Stage 10 rule scores the product as it runs. Production is unchanged, so this stays as deployed.
  - The certified candidate's score is reported "as if deployed": the section 8 product rubric on the certification US
    core.
