# Stage 20 pre-registration — Sentinel-2C harmonization and authority recovery

Written and frozen before any held-out pair is evaluated and before any Secchi value is read in Stage 20. The freeze file
`FREEZE_STAGE20.json` holds this file's SHA-256 and the time it was frozen.

**Already seen before writing this:**
- satellite metadata (gains, solar irradiance, band responses);
- the band-response physics run (`srf20.json`, no satellite pairs);
- one preliminary-tandem datatake, `20241215|R056` (Lake Sammamish and Lake Crescent, used to debug the ACOLITE driver). That datatake is assigned to derivation.

No other pair has been read.

## 1. Unchanged

- **C-gbm:** the frozen model and fold recipe. Fold models are trained exactly as in Stage 19, including the Stage-12-harmonised S2C training rows. Corrections change S2C inputs only when a prediction is made.
- **Stage 16 posterior gate:** `rule16.json`.
- **Stage 19 causal consensus code.**
- **The true 9/10 targets and the Stage 16 freeze bars.**
- **Excluded data:** no field reports, and no Secchi value is used for any fit or selection.

## 2. Data, all value-blind

| Track | Data |
|---|---|
| **A** | Nominal reprocessed S2A/S2C tandem, 29 Oct – 19 Dec 2024, at Sen2Cor level (Earth Search C1 L2A), every site-pass pair. Descriptive only. |
| **B** | Preliminary tandem, 12–19 Dec 2024, through the identical frozen ACOLITE path (Google Cloud L1C: S2A N0511, S2C N9905/N9906). Three runs per pair. |
| **C** | Operational nominal S2C against S2A/S2B, 1–2 days apart, both ≤ 20% cloud. 2025: S2C N0511, Apr–Oct. 2026: S2C N0512, Apr–Sep. Identical frozen ACOLITE path. |
| **H4** | Stage 19 neighbour scenes: S2C and S2A/S2B passes of the same development event, 1–2 days apart. Already processed by the frozen path. |
| **Floor** | Stage 19 neighbour pairs S2A vs S2B, 1–2 days apart (the normal two-satellite disagreement). |

The three Track B runs per pair:
- **A:** S2A.
- **C:** S2C as distributed.
- **E:** S2C re-calibrated to nominal. The TOA gains are rescaled by MTD `PHYSICAL_GAINS`, product ÷ nominal N0511. **This is labelled a deviation:** the nominal reprocessed L1C sits only in requester-pays AWS storage and was not accessed.

## 3. Splits (by physical acquisition)

**Tandem (Track B).** The unit is the datatake: UTC date plus relative orbit. A datatake goes wholly to one side.
- `20241215|R056` goes to derivation first.
- The rest are sorted by `md5("stage20|"+key)`. Each is assigned in turn to whichever split has fewer site-pairs so far; on a tie it goes to derivation.
- **Held-out H1:** the held-out datatakes. Reported by US / global stratum as a geographic breakdown.

**Operational 2025 (Track C).**
- The unit is the S2C datatake (date plus relative orbit). Same rule, run separately.
- **D2:** the derivation half. **H2:** the held-out half.

**Fully held out:**
- **H3:** operational 2026, N0512 (temporal and baseline holdout).
- **H4:** the Stage 19 S2C neighbour pairs.

## 4. Pair quantities

For each site-pair, every scene is read as the engine would read it:
- tier 1 if M0 is valid, else tier 2 (M3);
- sun elevation = 90 − ACOLITE sza for that scene.

Quantities:
- **Band log ratio:** `r_b = log10(ρ_S2C,b / ρ_ref,b)` for B02–B05. Only when both values are > 0.001.
- **Visibility difference:** `Δp = p_S2C − p_ref`, using the frozen production C-gbm `stage14/engine/frozen_gbm.pkl`.
- **States:** the Stage 16 gate (`rule16.json`, tier 2 boundary-only), with S2C treated at full authority for the comparison.
- **State overlap:** the two states share a class.
- **Harm proxy:** the hard class differs by 2 or more.

## 5. Correction candidates, in order of simplicity

| | Candidate | How it is set |
|---|---|---|
| **C0** | None | Raw S2C. |
| **C1** | Physics SBAF | `srf20.json` `sbaf_S2C_to_S2A`, frozen now: per-band gain, B05 with a B06 − B04 term. Fitted only on synthetic spectra through the official band responses. |
| **C2** | Empirical gain only, no offset | B01–B06. `g_b = 10^(−median r_b)` on the derivation tandem pairs, E vs A. |
| **C3** | Empirical gain + offset | B01–B06. Theil–Sen on derivation E vs A. B05 additionally gets a B06 − B04 term by OLS on the Theil–Sen residual. |

**Comparators in every table:**
- **B (Stage 12 V-ρw):** `lib14.harm`, kept as a comparator only.
- **E-raw diagnostics.**

**Selection.** The selected Stage 20 correction is the simplest candidate that meets every authority-lift bar (section 6), using tandem thresholds on D1 and operational thresholds on D2. If none qualifies, the candidate with the smallest pooled derivation |median Δp| is carried forward, and the failure is reported.

## 6. Authority-lift bars (frozen; never lowered)

Each held-out stratum is evaluated separately: H1, H2, H3 and H4. A stratum gates only if it has ≥ 15 pairs with both scenes valid. At least two strata must gate, and H1 must be one of them.

| Bar | H1 (near-simultaneous) | H2, H3, H4 (1–2 days apart) |
|---|---|---|
| Spectral: \|median r_b\|, each of B02, B03, B04, B05 | ≤ 0.0128 (3%) | ≤ 0.0212 (5%) |
| Visibility: \|median Δp\| | ≤ 0.03 | ≤ 0.03 |
| State overlap | ≥ 0.95 | ≥ min(0.95, floor overlap − 0.03) |
| Harm proxy rate | ≤ 0.02 | ≤ floor rate + 0.02 |

**Pooled.** Across all held-out pairs, |median Δp| must be ≤ 0.03. Values ≤ 0.02 are reported as preferred.

**Pass condition.** The bar passes only if every gating stratum passes every row of the table. The floor is computed from the Floor pairs with the same frozen engine.

## 7. Secchi validation (after the freeze; never used to choose)

**Rows:**
- every eligible S2C truth row: development S2C anchors (outer-fold predictions), Stage 14/15 certification S2C rows and Stage 16 fresh S2C rows (production model);
- the S2A/B rows of the same pools, as reference.

**Compared:** C0, B (Stage 12), the selected Stage 20 correction, and the S2A/B reference.

**Reported:** feet error, signed bias, per-class scores, operational score, two-thirds interval coverage and sample sizes.

**Full authority** requires the lift bar to pass **and**, for S2C rows under the selected correction:
- harmful rate ≤ S2A/B reference harmful rate + 0.05;
- severe rate ≤ 0.02;
- |median signed log10 error − the S2A/B reference median signed error| ≤ 0.05.

## 8. If full authority: Stage 19 causal consensus re-run

**Code.** The Stage 19 `dev19.py` causal M-iuw code, with these changes only:
- **(a)** S2C anchors and S2C prior passes are predicted from raw ACOLITE plus the selected correction (fold models unchanged);
- **(b)** S2C scenes count as full-authority platforms in the consensus;
- **(c)** S2C anchors' Stage 16 product is issued without the S2C lower-authority line.

**Baseline coverage.** The correction is applied only to S2C N0511 and N0512. An S2C scene on any other baseline stays excluded.

**Windows and selection.**
- Windows: previous 5, 10 and 15 days.
- Candidates are the windows passing the Stage 16 freeze bars; take the best balanced score.
- The selected window is the smallest one whose balanced and stained differences from the best have lake-bootstrap CIs (B = 2000, seed 19) containing 0.

**Reported:**
- every class and operational score, harmful, severe, Unknown share, Strong share and accuracy, and exact feet;
- events with 0, 1, 2 or 3 or more prior full-authority passes, before (S2A/B only) and after (with S2C);
- P(at least one valid independent prior pass within W), before and after.

**Strong** keeps the Stage 19 rule: posterior ≥ 0.90, at least 2 agreeing scenes, none disjoint. An S2C scene counts only if it is full-authority reflectance (tier 1 or 2) on a covered baseline and is an independent physical pass.

## 9. If the lift bar or the Secchi validation fails

- S2C stays at lower authority.
- The Stage 19 result stands.
- The section 8 counts are reported as hypothetical availability only.
