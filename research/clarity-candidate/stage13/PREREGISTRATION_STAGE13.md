# Current Clarity Stage 13: pre-registration

Written 2026-09-30, before any Stage 13 feature, model or class metric was computed. Its sha256 goes into
`FREEZE_STAGE13.json`. Changes after the freeze are timestamped addenda, recorded before the data they govern is
examined.

**Out of bounds:**
- Michael's field observations (his Guntersville survey stays an acceptance test);
- the P2 fresh holdout;
- Water Temperature;
- production;
- deployment;
- a new atmospheric-correction search.

**Guntersville** (corpus set G, or the Stage 11 box) is excluded from every fit and selection, and reported apart.

## 0. The frozen foundation (Stage 12, unchanged)

- **Reflectance.** ACOLITE K4 with lake-elevation pressure and the Stage 12 S2C V-ρw harmonisation. The station samples
  are `stage12/analysis/rows12.json`.
- **Benchmark A.** C3 refitted on ACOLITE, exactly as Stage 12 `models12.py`.
- **Folds.** The Stage 11 whole-lake folds: md5(lake) mod 5, with inner folds md5(lake) mod 20 mod 4.
- **Evaluation rows (E13).** Non-Guntersville corpus rows with a valid ACOLITE disk and a Secchi value (1,206). Coverage
  is judged on every processed non-Guntersville row (1,582).
- **Classes.** Clear ≥ 6 ft, normal 3–6, stained 2–3, limited < 2.

## 1. The mechanism, with in-situ data (diagnostic)

**Covariates**, same day at corpus stations:
- in-situ turbidity and chlorophyll (the corpus);
- colour and CDOM, fetched from WQP after this freeze for corpus sites only: `True color`, `Color` and `Apparent color`
  (PCU), `Absorbance at 440 nm`, and `Organic carbon` with a dissolved fraction.

**Analysis.** On lake-held-out folds, log Secchi is modelled on log turbidity, log chlorophyll and log colour (or a440,
or DOC). The analysis runs on all rows and inside stained, limited, and stained ∪ limited. It reports:
- each component's Shapley share of held-out R²;
- which component dominates in each class.

**On the satellite side,** the analysis reports how much of log Secchi each feature explains within stained ∪ limited
water.

## 2. The feature set (fixed now; nothing else is tried)

ρ is ACOLITE ρw, floored at 1e-4 before any log.

| Feature | Definition | Physical meaning |
|---|---|---|
| F_red | log10 ρ(B04) | Particle backscatter and brightness (C3's core) |
| F_ndci | (ρ05 − ρ04)/(ρ05 + ρ04) | Chlorophyll red-edge response |
| F_bg | log10(ρ02/ρ03) | Blue/green absorption slope (CDOM and pigment absorb blue) |
| F_gr | log10(ρ03/ρ04) | Green/red visibility ratio |
| F_re | log10(ρ06/ρ04) | 740/665: particulate backscatter as red absorption rises in turbid water |
| F_bright | log10 mean(ρ02…ρ05) | Overall brightness |
| F_kd | log10 Kd(492) from model B | Attenuation proxy; missing where B refuses |

The CDOM-signal set is {F_bg}. NIR (B8A) enters only through the §3 switch.

## 3. The red/NIR turbidity switch (Dogliotti et al. 2015)

- **The two estimates.** T_red = 228.1·ρ665/(1 − ρ665/0.1641), and T_NIR = 3078.9·ρ865/(1 − ρ865/0.2112), using
  ACOLITE B04 and B8A.
- **The switch.** T = T_red for ρ665 < 0.05 and T_NIR for ρ665 > 0.07, with linear weighting between the two.

**Tests:**
1. The share of rows where the switch activates.
2. Median |e_T| against same-day in-situ turbidity, switch against red-only, in stained, limited and in-situ sediment
   rows (paired, lake bootstrap).
3. The champion form refitted on log T_switch against log T_red: stained and limited recall.

**RED/NIR TURBIDITY SWITCH USEFUL: YES** if median |e_T| improves by ≥ 10% in limited or sediment rows (CI excluding 0),
**and** stained or limited recall rises by ≥ 0.05. Otherwise **NO**.

## 4. Direct visibility and attenuation model B (QAA-switch, new; not P1)

- **The inversion.** QAA v6 (Lee et al. 2002, 2009), with bands 443/492/560/665/704/740 and S2A band-averaged pure-water
  absorption: 0.00715, 0.0212, 0.0632, 0.4156, 0.702 and 2.726 m⁻¹ (Pope & Fry 1997 to 727.5 nm, Kou et al. 1993
  beyond).
  - bbw = 0.00111·(500/λ)^4.32.
  - rrs = Rrs/(0.52 + 1.7·Rrs); u = (−0.089 + √(0.089² + 4·0.1245·rrs))/(2·0.1245).
- **The reference band switches with turbidity:**
  - Rrs(665) < 0.0015 sr⁻¹ → λ0 = 560, with a(560) = aw + 10^(−1.146 − 1.366χ − 0.469χ²) and
    χ = log10((rrs443 + rrs492)/(rrs560 + 5·rrs665²/rrs492));
  - otherwise, if Rrs(740) < 0.004 → λ0 = 665, with a(665) = aw + 0.39·(Rrs665/(Rrs443 + Rrs492))^1.14;
  - otherwise → λ0 = 740, with a(740) = aw(740). That is the turbid-water NIR-reference approach, where water
    absorption dominates.
- **Backscatter and absorption.**
  - bbp(λ0) = u·a/(1 − u) − bbw.
  - η = 2(1 − 1.2·exp(−0.9·rrs443/rrs560)).
  - bbp(λ) = bbp(λ0)·(λ0/λ)^η.
  - a(λ) = (1 − u)(bbw + bbp)/u.
- **Attenuation (Lee 2013):** Kd = (1 + 0.005θs)·a + 4.259·(1 − 0.265·bbw/bb)(1 − 0.52·e^(−10.8a))·bb.
- **Secchi depth (Lee 2015):** Zsd = ln(|0.14 − Rrs_tr|/0.013)/(2.5·Kd_tr), where tr is the minimum-Kd band among
  443/492/560/665. The result is converted to feet.
- **Refusals:**
  - the sun is below 20°;
  - Rrs ≤ 0 in a used band;
  - u is outside (0, 1);
  - bbp ≤ 0;
  - a < 0.9·aw;
  - Zsd is outside 0.2–25 ft.
- **Variants:**
  - **B-pure:** no fitted parameter.
  - **B-cal:** log S = a + b·log Zsd, fitted per fold.

**DIRECT ATTENUATION MODEL USEFUL: YES** if B-pure or B-cal meets both:
- coverage ≥ 85%;
- **and** either:
  - (mean of stained and limited recall) − A's is ≥ 0.05 with the CI excluding 0; or
  - overall median |log| is within +0.010 of A's (CI upper bound), with stained+limited recall improved by ≥ 0.05.

Otherwise **NO**.

## 5. The single continuous multicomponent model C

- **C-lin.** OLS of log10 S on F_red, F_ndci, F_bg, F_gr, F_re and F_bright, fitted per fold.
- **C-gbm.** The one flexible model allowed:
  - scikit-learn HistGradientBoostingRegressor on log10 S, with all seven features (NaN allowed);
  - max_leaf_nodes 8, learning_rate 0.05, max_iter 300, min_samples_leaf 30, l2_regularization 1.0;
  - early stopping on a 15% validation split of the training folds, random_state 12;
  - monotonic constraints: F_red −1, F_gr +1, F_kd −1, the others free.
- **Lake identity is never an input.** Routing by water type is not built.

## 6. The ordinal clarity-class models

- **O1.** Proportional-odds (cumulative-logit) regression on the standardised C-lin features, fitted per fold by
  maximum likelihood (scipy), with 3 ordered thresholds.
- **O2.** C-lin's continuous prediction with class cut-points learned per outer fold from inner-fold predictions,
  chosen to maximise macro recall. The cut-points must keep their order.
- **Every regression model** (A, B, C) also yields a class from its feet at 2/3/6 ft.
- **Metrics:** per-class recall and precision, balanced accuracy (macro recall), quadratic-weighted kappa, and the share
  of errors of ≥ 2 classes.

## 7. Success and BEST

**Benchmark A** on E13: stained recall/precision 0.295/0.321, and limited 0.324/0.812 (Stage 12).

**A candidate is a STAGE 13 SUCCESS if all of these hold:**
1. Stained recall ≥ 0.45 and stained precision ≥ 0.40.
2. Limited recall ≥ 0.50 and limited precision ≥ 0.60.
3. The gains over A in stained recall and in limited recall each have a lake-bootstrap 95% CI excluding 0.
4. Clear and normal recall and precision are each ≥ A's − 0.05.
5. **Region-held-out generalisation.** Refitted with 5 geographic folds (the US regions are fixed below), stained and
   limited recall are ≥ 0.8 × their lake-held-out values. The regions, by state:
   - Northeast: CT ME MA NH RI VT NY NJ PA DE MD DC;
   - Southeast: VA WV NC SC GA FL AL MS TN KY;
   - Midwest: OH IN IL MI WI MN IA MO;
   - Plains and South-Central: ND SD NE KS OK TX AR LA;
   - West: every other state.

**BEST ENGINE** is the simplest SUCCESS, in this order: A, B-pure, B-cal, C-lin, O1, O2, C-gbm. With no success, BEST is
the candidate with the highest balanced accuracy, labelled NOT A SUCCESS. A is kept unless that candidate beats A's
balanced accuracy by ≥ 0.03 (CI excluding 0).

**CDOM/ABSORPTION SIGNAL USEFUL: YES** if removing F_bg from C-lin or O1 lowers stained recall or balanced accuracy by
≥ 0.03, with the CI excluding 0. Otherwise **NO**. The in-situ colour result (§1) is reported as mechanism, not as this
verdict.

**PRIMARY CAUSE OF STAINED/LIMITED FAILURE** comes from §1 and the ablations. It is stated as whichever of these the
data support:
- particles;
- dissolved colour;
- pigment;
- a mixture;
- a satellite signal that does not separate them.

## 8. Coverage

- **Tier 1:** ACOLITE with the default L2W mask (Stage 12).
- **Tier 2: ACOLITE with relaxed masks,** only at stations where tier 1 has no valid disk.
  - **Rerun:** the same configuration on those crops with `l2w_mask=False`; the flags are still read.
  - **Variants:**
    - M1 ignores the negative-reflectance flag, but needs the disk medians of B02–B05 to be > 0;
    - M2 ignores the SWIR non-water flag for pixels with NDWI(B03, B08) > 0;
    - M3 is both.
  - Every other flag is kept, as is the rule of ≥ 5 valid pixels.
  - **Choice:** M3 is used, unless its tier-2 rows' median |log| (engine A) exceeds tier-1 rows' by > 0.05. Then the
    variant with the most coverage that passes is used, or none.
- **Tier 3: lower authority.** C3 refitted on Sen2Cor reflectance (per fold) where tiers 1 and 2 have nothing.
- **Reported:**
  - coverage by tier;
  - class metrics per tier and for the union;
  - "not materially worse", meaning the union's balanced accuracy is ≥ tier 1's − 0.03.
- **COVERAGE** is the covered share of all processed rows, with each tier's authority stated.

## 9. Class boundaries and the product footprint

- **Bands.** ±0.05 log10 (a factor of 1.12) around 2, 3 and 6 ft. The 2 ft band extends the brief, which asked for 3 and
  6 ft. An estimate inside a band is reported as the pair of adjacent classes.
- **The footprint tandem test:**
  - ACOLITE K4 (default pressure, as the Stage 12 tandem) is rerun on the 12 tandem pairs, keeping the L2W grids.
  - Disks of 60 m radius sit on a 300 m grid. Every pixel must be valid on both passes, NDWI > 0 on both, and ≥ 180 m
    from non-water.
  - The disk median ρw is used. S2C gets V-ρw with leave-one-pair-out coefficients, fitted on the other pairs' Stage 12
    tandem pixels.
- **Flips.** The engine's class (A, and BEST) is computed on S2A and on harmonised S2C. A flip means the two class sets
  are disjoint. Flip rates are reported with and without bands, with the median |Δft|.
- **PLATFORM-INVARIANT AT PRODUCT FOOTPRINT: YES** if, with bands, the mean flip rate over pairs is < 5% and the median
  |Δft| is ≤ 0.25 ft. Otherwise **NO**.
- **The cost of bands:** the share of corpus predictions that fall in a band.

## 10. Blind certification expansion

This is **`cert/CERT_ADDENDUM_2.md`**, frozen with this file before any new candidate is built.

## 11. Capabilities

The Stage 12 §5 rubrics apply unchanged (historical, lake-held-out, not readiness). They are applied to BEST with the §8
tiers, where tier 3 counts toward coverage but is labelled lower authority. Exact feet use the Stage 12 inner-fold
authorisation rule.
