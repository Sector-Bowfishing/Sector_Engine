# Current Clarity Stage 21: Pre-ACOLITE S2C Radiometric Correction

**2026-10-03.** Sentinel-2C's NIR/SWIR dark-water offset was corrected at the top of the atmosphere, using the real nominal reprocessed S2A/S2C tandem L1C, before the frozen ACOLITE K4 pipeline.

**What didn't change:**
- the C-gbm, which was not refit;
- the Stage 16 gate;
- the Stage 19 consensus code;
- the Stage 20 authority-lift bars, unchanged and not lowered.

**What was never used for fitting:** field reports and Secchi truth.

**Method:**
- Pre-registered before any nominal S2C pixel was read (`PREREGISTRATION_STAGE21.md`, frozen 03:23 UTC).
- The correction was frozen from derivation tiles only (`corr21.json`, 22:13 UTC), before any held-out pair or Secchi value was read.

Production is unchanged.

**The answer: the correction fixes S2C against S2A on the same water, but not against truth, so S2C does not earn full authority.**
- **On the held-out tandem** (real nominal, near-simultaneous), raw S2C reads 0.061 log10 clearer than S2A. The correction cuts that to **+0.009**: 100% state agreement, 1.1% class jumps. The pooled visibility bias across all 219 gating pairs is **+0.0001**.
- **It is not fully valid at the top of the atmosphere.** It removes 76–89% of each band's offset, but the held-out tiles carry slightly larger B11/B12 offsets than the derivation tiles. The residuals, 0.00036 and 0.00035, exceed the ±0.0003 tolerance.
- **Against Secchi the correction overshoots.** Raw S2C is already unbiased (+0.002 against S2A/B's −0.016). Corrected S2C reads **0.071 murkier**, failing the 0.05 bias check by 0.005.
- **The pattern is seasonal.** The only tandem is November–December. In summer 2025, raw S2C already agrees with S2A/B (B02–B04 within about 3%). The winter-derived correction then over-brightens B03/B04 by 8–10%.
- **Stage 12 remains the worst option:** −0.104 against Secchi and 17.5% harmful. By the brief's rule it is retired only if S2C earns full authority, so it stays for now.
- **Stage 19 stands at 7/10.** The S2C consensus re-run was pre-registered (`dev21.py`) but not run.

## 1. Data

| | What | Count |
|---|---|---|
| Tandem, real nominal | S2A (Google Cloud N0511 2024) and S2C (AWS N0511 generated 2026), 29 Oct – 18 Dec 2024, ~30 s apart, split by datatake | 150 tile-dates on 79 datatakes: 77 derivation (75 used) / 73 held out (70 usable at TOA, 88 site-pairs through ACOLITE) |
| F25 / F26 | Fresh S2C vs S2A/B, 1–2 days apart, at sites Stage 20 never used | 69 / 62 valid pairs |
| Secondary | Stage 20's C25/C26 and the Stage 19 S2C neighbours (H4) | 64 / 61 / 11 |
| Secchi | Every eligible S2C truth row, re-run through the corrected path | 137 (38 dev, 54 cert, 45 fresh) |

**AWS:** 65.1 GB downloaded (requester pays), inside the 100 GB monthly free transfer tier. Every byte is logged in `aws_bytes.log`.

**S2A** came free from Google Cloud: the reprocessed collection reuses the 2024 N0511 S2A products.

## 2. The frozen correction (derivation tiles only)

**How it was measured.** Pixel-paired top-of-atmosphere water reflectance, S2C − S2A, on the shared 20 m grid. Water pixels: S2A NDWI > 0.2, B11 < 0.03, no cirrus, no moving cloud. Median per tile, then median over tiles.

| Band | Model | Offset removed before ACOLITE | Tile IQR |
|---|---|---|---|
| B08 | constant | 0.00040 | 0.00020–0.00065 |
| B8A | constant | 0.00080 | 0.00050–0.00110 |
| B11 | **brightness-dependent** (pre-registered test passed: Spearman 0.52, scatter −40%) | 0.00173 + 0.00445 × the S2C tile's own clear-pixel B11 | 0.00175–0.00275 |
| B12 | constant | 0.00110 | 0.00080–0.00150 |

**After ACOLITE,** B05 gets the frozen band-shape adjustment: B05′ = 1.0332·B05 − 0.0397·(B06 − B04).

**What the offset is.** Over bright land, S2C's B11 reads 1–3% *below* S2A, yet over water it reads above. So it is an additive term at the dark end, not a gain. Its growth with scene brightness in B11 suggests stray light.

## 3. Held out: top of atmosphere (70 tiles)

| Band | Raw S2C − S2A | After correction | IQR after | Within ±0.0003 |
|---|---:|---:|---|---|
| B08 | +0.00049 | +0.00009 | −0.00027…+0.00032 | yes |
| B8A | +0.00090 | +0.00010 | −0.00020…+0.00037 | yes |
| B11 | +0.00280 | **+0.00036** | −0.00009…+0.00082 | **no** |
| B12 | +0.00145 | **+0.00035** | +0.00010…+0.00070 | **no** |

**The held-out tiles carry larger offsets than the derivation tiles** (B11 +0.0028 against +0.0024; B12 +0.00145 against +0.0011). The correction removes 87% (B11) and 76% (B12), but not all.

## 4. Held out: after ACOLITE

Visibility difference is S2C minus S2A/B, in log10 feet. Bands are S2C/S2A ratios.

| Stratum | Version | n | Visibility | State overlap | Class jumps | B02 | B03 | B04 | B05 | All bars |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **Tandem (TH)** | Raw K0 | 89 | +0.061 | 100% | 1.1% | 0.919 | 0.945 | 0.871 | 0.825 | no |
| | Offsets K1 | 88 | +0.023 | 100% | 1.1% | 0.971 | 0.990 | 0.962 | 0.913 | no |
| | **K2 (Stage 21)** | 88 | **+0.009** | **100%** | **1.1%** | 0.971 | 0.990 | **0.962** | 0.966 | **no** (B04) |
| | Stage 12 | 89 | 0.000 | 100% | 1.1% | 0.964 | 0.979 | 0.971 | 0.977 | no |
| **2025 fresh (F25)** | Raw | 69 | +0.016 | 97.0% | 2.9% | 0.995 | 1.031 | 0.994 | 0.938 | no |
| | **K2** | 69 | **−0.019** | 98.5% | 2.9% | 1.050 | **1.084** | **1.096** | 1.051 | **no** (spectral) |
| | Stage 12 | 69 | −0.046 | 97.0% | 2.9% | 1.083 | 1.077 | 1.118 | 1.162 | no |
| **2026 fresh (F26)** | Raw | 62 | +0.017 | 96.7% | **8.1%** | 0.978 | 0.967 | 0.931 | 0.893 | no |
| | **K2** | 62 | **−0.003** | **93.3%** | **8.1%** | 1.049 | 1.021 | 1.052 | 1.074 | **no** |
| | Stage 12 | 62 | −0.024 | 93.3% | 8.1% | 1.055 | 1.043 | 1.086 | 1.117 | no |

**Pooled K2 visibility over the 219 gating pairs: +0.0001.**

**Secondary strata** (seen in Stage 20; not gating):

| | Raw | K2 | Stage 12 | Notes |
|---|---:|---:|---:|---|
| Stage 20 2025 pairs | +0.042 | −0.004 | −0.006 | K1 alone met every bar there |
| Stage 20 2026 pairs | +0.017 | −0.038 | −0.064 | |
| Stage 19 S2C neighbours (n 11) | +0.042 | −0.034 | −0.057 | |
| Tandem, global sites (n 10) | | +0.006 | | K2 met every bar, B04 0.999 |
| Tandem, before 12 Dec (n 72) | | +0.007 | | |

**Reading it:**
- **The tandem fix works where it was derived.** In winter, near-simultaneous, the correction closes most of the gap. Visibility, state and harm pass. Spectral fails only on B04, −3.8% against 3%.
- **In summer the correction over-brightens.** Raw S2C is already close to S2A/B (B02–B04 within about 3%), and removing the winter-measured offset lifts B03/B04 8–10%.
- **Why it depends on season (a likely reason, not yet tested).** ACOLITE's aerosol fit is driven by the darkest bands. Removing the NIR/SWIR offset can change which band drives it from scene to scene, so the same additive fix can act differently by season.
- **2026 fails on noise.** The class-jump rate (8.1%) fails for every version, raw included. That points to the 2026 pair sample, not the correction.
- **The 1–2-day spectral bar is still stricter than nature:** S2B differs from S2A by 2–7% on such pairs (Stage 20). Without that row the lift bar still fails, because 2026 fails state and harm.

## 5. Verdicts by the frozen rules

| Verdict | Requirement | Result |
|---|---|---|
| PRE-ACOLITE CORRECTION VALID | TOA residual within ±0.0003 on held-out tiles, **and** tandem visibility, state and harm | **NO**: TOA fails on B11 (0.00036) and B12 (0.00035); the tandem bars pass |
| Authority-lift bar | Every bar in tandem, F25 and F26, plus pooled | **NO**: spectral fails everywhere; F26 fails state and harm |

## 6. Secchi truth (after the freeze; validation only)

| 137 S2C rows | Operational | Clear | Normal | Stained | Limited | Bias | Harmful | Severe | ⅔ coverage | Median feet error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S2A/B reference (2,705) | 0.715 | 0.89 | 0.68 | 0.60 | 0.70 | −0.016 | 14.8% | 2.0% | 64% | 1.45 |
| Raw S2C (K0) | 0.707 | 0.92 | 0.70 | 0.54 | 0.67 | **+0.002** | 13.1% | 1.5% | 64% | 1.87 |
| Offsets only (K1) | 0.697 | 0.89 | 0.64 | 0.54 | 0.72 | −0.071 | 13.1% | 1.5% | 59% | 1.59 |
| **K2 (Stage 21)** | 0.688 | 0.89 | 0.61 | 0.54 | 0.72 | **−0.071** | 13.1% | 1.5% | 59% | 1.56 |
| Stage 12 | 0.704 | 0.83 | 0.58 | 0.63 | 0.78 | −0.104 | 17.5% | 2.2% | 55% | 1.64 |

S2C class sizes: clear 67, normal 48, stained 10, limited 12. The stained and limited S2C scores rest on very few rows.

**Full-authority checks for K2:**
- harmful ≤ reference + 5 pp: **pass**;
- severe ≤ 2%: **pass** (1.5%);
- bias within 0.05 of reference: **fail** (−0.071 against −0.016; 0.055 apart).

**S2C FULL AUTHORITY: NO.**

**What truth says, as a lead rather than a verdict:**
- In the season the truth rows come from (mostly summer), raw S2C is as good as S2A/B.
- Stage 12 is worse than raw everywhere.
- The winter-derived correction overshoots.

## 7. What S2C would add (hypothetical; not run)

The causal re-run with S2C at full authority was pre-registered (`dev21.py`, all 16 patches verified) and **not executed**, as the brief requires when the bars fail. Strong evidence is therefore unchanged.

**Availability**, counted from valid corrected S2C scenes:

| No valid earlier view | All development events (1,582) | 2025–26 events (115) |
|---|---|---|
| Past 5 days | 67.6% → 66.8% | 71.3% → 59.1% |
| Past 10 days | 52.7% → 51.8% | 59.1% → 47.8% |
| Past 15 days | 42.0% → 41.0% | 52.2% → 38.3% |

Trustworthy S2C would materially lower the zero-prior-view rate in the 2025–26 era: by 11–14 points, with 38–54% more prior passes. It would barely move the older development corpus.

## 8. Decision

- **Correction.** The pre-ACOLITE correction is the right physics for the winter tandem, but not yet valid by the frozen rules.
- **S2C** stays at lower authority.
- **Stage 12** is not retired (the brief's rule), though every stage since Stage 20 shows it is the worst option on nominal products.
- **Stage 19 (7/10)** stands, and production is unchanged.

## 9. Files (`research/clarity-candidate/stage21/`)

**Pre-registration and freeze:**
- `PREREGISTRATION_STAGE21.md`;
- `FREEZE_STAGE21.json`: hashes of the pre-registration, the selection and the correction, plus the AWS GB at the freeze.

**Selection and data access:**
- `select21.py`, `select21.json`: tiles and split;
- `fetch21.py`: AWS SAFE rebuild (requester pays, 95 GB cap, byte log `aws_bytes.log`).

**Derivation:**
- `toa21.py`, `derive21.py`, `toa21_D/`, `corr21.json`.

**Processing runs:**
- `th21.py`, `toa21_H/`, `res_tandem21/`: held-out tandem;
- `aco21_one.py`, `run_aco21.py`: the frozen ACOLITE path plus the additive TOA wrapper;
- `build21_ops.py`, `ops21_pairs.json`, `res_ops21/`, `res_ops21c/`, `res_ops20c/`: current-era pairs;
- `build21_s2c.py`, `res_s2c21/`: S2C truth and prior-pass re-runs.

**Analysis:**
- `eval21.py`, `eval21.json`;
- `secchi21.py`, `secchi21.json`, `secchi21_rows.json`;
- `avail21.json`;
- `dev21.py`: the pre-registered re-run, not executed.

## 10. Status

PRE-ACOLITE S2C CORRECTION VALID: NO
- Fails on the top-of-atmosphere residual: B11 0.00036 and B12 0.00035 against ±0.0003. It removes 87% and 76% of those offsets.
- It passes the held-out tandem visibility (+0.009), state (100%) and harm (1.1%) bars.
- Against Secchi it over-corrects summer scenes (−0.071).

S2C FULL AUTHORITY: NO (the lift bar failed; the Secchi bias check failed, −0.071 against −0.016)

STAGE 12 NOMINAL S2C CORRECTION RETIRED: NO (the pre-registered rule requires full authority; Stage 12 is still the worst option, −0.104 against Secchi and 17.5% harmful)

BEST LIVE WINDOW: causal, past 5 days (Stage 19, unchanged; the S2C re-run was not executed)

ZERO-PRIOR-VIEW RATE: unchanged at 66.8% (5 d) in the live product, since S2C was not lifted.
- Hypothetical with corrected S2C, 2025–26 events: 71.3% → 59.1% (5 d), 59.1% → 47.8% (10 d), 52.2% → 38.3% (15 d).
- All events: 67.6% → 66.8% (5 d).

CLEAR SCORE: 0.883

NORMAL SCORE: 0.669

STAINED SCORE: 0.606

LIMITED SCORE: 0.680

OPERATIONAL SCORE: 0.710 (7/10)

HARMFUL RATE: 11.4%

SEVERE RATE: 1.39%

EXACT-FEET CAPABILITY: 8/10

STRONG EVIDENCE SHARE / ACCURACY: 11.0% of usable answers / 92.9% (unchanged; no S2C scene counts)

CURRENT CLARITY SCORE RECOMMENDATION: 7/10 development (uncertified); certified none; deployed production 2/10

NEXT BLOCKER: The S2C correction has to hold across seasons. The only near-simultaneous S2A/S2C tandem is November–December 2024. It fixes winter, but over-brightens summer scenes, where raw S2C already agrees with S2A/B and with Secchi. The next step needs summer same-day S2C–S2A/B pairs:
- the high-latitude swath overlaps, about 100 minutes apart;
- or a correction that keeps ACOLITE's aerosol-band choice identical for both satellites.

That gives a season-aware correction, re-tested on a fresh pre-registration.

Production remains unchanged.
