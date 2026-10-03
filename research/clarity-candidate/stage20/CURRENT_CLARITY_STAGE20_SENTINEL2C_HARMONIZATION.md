# Current Clarity Stage 20: Sentinel-2C Harmonization and Authority Recovery

**2026-10-02.** Why Sentinel-2C reads clarity differently from Sentinel-2A/B, whether a defensible correction exists, and whether S2C can earn full authority.

**What didn't change:**
- the C-gbm, which was not refit;
- the Stage 16 posterior gate.

**What was never used for fitting:**
- field reports;
- Stage 14/15 certification truth;
- Stage 16 fresh truth.

**Method:** pre-registered before any held-out pair or Secchi value was read (`PREREGISTRATION_STAGE20.md`, frozen 01:32 UTC). The correction choice was frozen next (`harm20.json`, hashed into `FREEZE_STAGE20.json`). Production is unchanged, and nothing was deployed.

**The answer: S2C's murky reading is made downstream, by Sector's own Stage 12 correction. Under it sits a real sensor offset that the after-ACOLITE corrections cannot remove.**

- **The Stage 12 correction makes the bias.** It was fitted on preliminary S2C products, whose visible top-of-atmosphere ran about 1.5% bright. On today's nominal S2C it brightens water too much: by about 10% (3–18% per band on the 2025–26 pairs).
  - On paired scenes, S2C reads 0.06 log10 murkier: −0.057 on the Stage 19 scenes, −0.064 in 2026.
  - Against Secchi it reads 0.104 murkier, while S2A/B reads −0.016.
  - This is the Stage 19 "−0.059".
- **The sensor effect underneath:**
  - S2C carries an additive dark-water offset in its NIR and shortwave-infrared bands at the top of the atmosphere: B8A about +0.001, B11 +0.0025–0.003, B12 +0.0014. It is in every processing baseline, including the 2026 nominal reprocessing.
  - ACOLITE's aerosol fit reads that offset as haze and over-corrects, so S2C water comes out too dark: up to 19% in dark winter water, 1–9% in summer.
  - So uncorrected S2C reads 0.02–0.06 clearer than S2A on the same water.
- **Band shape is real but harmless here.** B05 is centred at 707 nm against 704, which makes it 5–7% darker over water. Through C-gbm that nets to about 0 (+0.005).
- **No pre-registered correction met the frozen authority-lift bar on held-out pairs.** S2C stays at lower authority. Stage 19 stands at 7/10.
- **The fix belongs before ACOLITE.** An exploratory test (not pre-registered) removed the tandem-measured offset at the top of the atmosphere. That cut the darkening in B02–B05 by half to three-quarters.

## 1. The Stage 19 S2C finding, and what this stage had to explain

| Stage 19 S2C diagnostic | Value |
|---|---:|
| Development anchors that are S2C | 41 |
| With prior S2A/B scenes within 10 days | 21 |
| With both states | 15 |
| Share a class / contain the consensus state | 100% / 80% |
| S2C anchor minus prior S2A/B consensus | −0.059 log10 (IQR −0.116 to +0.010) |

**Stage 19 always applied the Stage 12 S2C correction.** This stage reproduces that offset from data that never touched Stage 19's truth:
- Stage 12 on the held-out Stage 19 S2C neighbour pairs: −0.057;
- Stage 12 on 2026 nominal pairs: −0.064;
- Stage 12 against Secchi: −0.104, against S2A/B's −0.016.

Without the correction, the same scenes read +0.042, +0.017 and +0.002.

**Stage 19's agreement figures (100% share a class) stay true.** The offset is small next to the class widths. It is still large enough to show in the numbers and to cost S2C full authority.

## 2. Data, and the tandem-access limit

| Track | What | Pairs | Valid both |
|---|---|---:|---:|
| A | Nominal reprocessed S2A/S2C tandem, 29 Oct – 19 Dec 2024, Sen2Cor level (Earth Search C1 L2A; S2C N0511 generated 2026), 27–32 s apart | 763 site-passes | 408 |
| B | Preliminary tandem, 12–19 Dec 2024, identical frozen ACOLITE path. Runs: S2A; S2C as distributed; S2C re-calibrated to nominal (MTD gain ratio) | 158 site-pairs, 20 datatakes | 84 |
| C25 | Operational nominal S2C N0511 vs S2A/B, 1–2 days apart, Apr–Oct 2025 | 80 | 62 |
| C26 | Operational nominal S2C N0512 (5 N0513) vs S2A/B, 1–2 days apart, Apr–Sep 2026 | 80 | 58 |
| H4 | Stage 19 neighbour pairs, S2C vs S2A/B, 1–2 days | 11 | 11 |
| Floor | Stage 19 neighbour pairs, S2A vs S2B, 1–2 days | 119 | 101 |
| D | Band-response physics: 1,521 synthetic inland-water spectra, 1,131 realistic | — | — |

**The deviation, stated plainly:**
- The nominal reprocessed S2C L1C for the tandem exists only in the requester-pays AWS bucket. No credentials or charges were used.
- The public Google bucket holds only the **preliminary** S2C L1C for 12–19 Dec 2024: N9905 (140 pairs) and N9906 (17). It has nothing earlier.
- **Workaround:** Track B re-calibrates the preliminary product to nominal by its own metadata gains (product ÷ nominal N0511). That fixes absolute gain only, not other reprocessing changes.
- Track A checks the result at Sen2Cor level on the genuine nominal products.

**Split** (pre-registered; by physical acquisition, whole datatakes):

| | Tandem (B) | 2025 (C25) | Held out entirely |
|---|---|---|---|
| Derivation | 78 site-pairs, 11 datatakes | 40, 24 datatakes | — |
| Held out | 80, 9 datatakes (70 US / 10 global) | 40, 22 datatakes | 2026 (C26) and Stage 19 (H4) |

## 3. Processing baselines

S2C metadata gains, relative to the operational N0511 (Jan 2025). Reflectance scales as 1/gain.

| S2C product | B02 | B04 | B05 | B8A | B11 | B12 |
|---|---:|---:|---:|---:|---:|---:|
| N9905 preliminary (Dec 2024; Stage 11/12 tandem) | 0.984 | 0.985 | 0.985 | 0.985 | 0.989 | 0.968 |
| N9906 preliminary (18 Dec 2024) | 1.001 | 1.002 | 1.002 | 1.002 | 1.003 | 1.018 |
| N0511 nominal reprocessing of the tandem (generated Apr 2026) | 1.000 | 1.001 | 1.001 | 1.000 | 1.002 | 1.002 |
| N0512 (2026 operational) | 0.998 | 0.998 | 0.997 | 0.998 | 1.004 | 1.002 |
| N0513 (from Sep 2026) | 0.998 | 0.997 | 0.997 | 0.998 | 1.003 | 1.002 |

**Other metadata:**
- Solar irradiance is identical across S2C baselines.
- The S2C band responses are byte-identical in N9905, N0511 and N0512. N0513 trims the tails only; centres agree within 0.05 nm.

**The four questions:**
- **Present in current nominal products?** Yes: the NIR/SWIR offset and the B05 band shape. Uncorrected nominal S2C reads +0.063 (2025) and +0.017 (2026) clearer on pairs.
- **Confined to an older baseline?** Only the visible gain error. N9905 ran about 1.5% bright; N9906 and nominal did not.
- **Reduced by newer calibration?** No. N0512/N0513 move gains by 0.3% at most.
- **Created downstream?** The murky bias, yes: by Stage 12. The clear bias comes from ACOLITE amplifying the sensor offset.

**Obsolete cached imagery:**
- The Stage 11/12 tandem L1C on Google Cloud is preliminary, so the Stage 12 correction came from obsolete processing.
- Every S2C scene Sector actually scores is nominal: 05.11 or 05.12 in the development, certification and fresh pools.

## 4. Band decomposition

**Nominal reprocessed tandem, Sen2Cor** (Track A, 408 pairs, production-gated 60 m disks):

| Band | S2C/S2A | C − A | Theil–Sen slope / intercept | Band-shape physics expects |
|---|---:|---:|---|---:|
| B02 | 0.981 | −0.0005 | 0.999 / −0.0005 | 0.950 |
| B03 | 1.010 | +0.0004 | 1.014 / −0.0001 | 1.005 |
| B04 | 1.000 | −0.0001 | 1.003 / 0.0000 | 0.965 |
| B05 | 0.945 | −0.0011 | 0.966 / −0.0002 | 0.926 |
| B08 | 1.077 | +0.0006 | 0.990 / +0.0006 | — |
| B8A | 1.138 | +0.0010 | 0.975 / +0.0011 | 0.993 |
| B11 | 2.096 | +0.0029 | 1.077 / +0.0030 | — |

**Reading it:**
- Nominal visible calibration is consistent: B02–B04 agree within 2%.
- B05 follows the band shape.
- NIR/SWIR shows a pure intercept: an additive dark-water offset, not a gain.
- Sen2Cor's aerosol optical thickness and the production FNU are identical between the two satellites (ratio 1.00), so Sen2Cor does not amplify the offset.
- Agreement holds within about 1–2% across the campaign (before 12 Dec vs 12–19 Dec), sun elevation, view angle and geography.
- Darker water shows slightly more deficit: B02 −4.2% in the darkest third against −1.2% in the brightest. That is consistent with a small additive term.

**Identical ACOLITE path, preliminary tandem** (Track B, 61 pairs with all three runs valid; S2C re-calibrated to nominal):

| Band | Top of atmosphere C/A | C − A | ACOLITE water C/A |
|---|---:|---:|---:|
| B02 | 1.016 | +0.0016 | 0.911 |
| B03 | 0.995 | −0.0004 | 0.942 |
| B04 | 0.990 | −0.0005 | 0.874 |
| B05 | 0.974 | −0.0012 | 0.810 |
| B06 | 1.016 | +0.0005 | 0.793 |
| B07 | 0.988 | −0.0004 | 0.699 |
| B8A | 1.039 | +0.0008 | 0.833 |
| B11 | 1.477 | +0.0024 | 2.008 |
| B12 | 1.370 | +0.0015 | 0.745 |

**Attribution:**
- **TOA radiometry:** at the top of the atmosphere the visible bands agree within 2.6%. The NIR/SWIR offset is there: B8A +0.0008, B11 +0.0024 and B12 +0.0015 on these 61 pairs. Stage 11 found +0.0012, +0.0019 and +0.0012 on its 12.
- **Atmospheric correction (ACOLITE):** after it, every water band from B02 to B8A is 9–30% darker. ACOLITE's dark-spectrum fit (400–900 nm, which includes B08 and B8A) reads the offset as aerosol.
- **Strongest where the signal is smallest.** B04 is −24% in the darkest third, −11% in the middle and −5% in the brightest. That is why the December tandem (low sun) reads worse than summer 2025.
- **Calibration emulation makes it worse, not better.** As distributed, the preliminary L2W is 2–5% brighter. Its extra 1.5% visible gain partly hides the offset, and Stage 12 was fitted on exactly that.
- **Masking:** the 60 m disks and masks are identical, so masking does not cause it.
- **Feature construction and the C-gbm response** pass it through as F_red −0.061, F_bright −0.052, F_kd −0.045 and F_ndci −0.035. These are the clearer-water directions.

## 5. Official band responses

| Band centre (nm) | S2A | S2B | S2C |
|---|---:|---:|---:|
| B02 | 492.7 | 492.3 | 489.0 |
| B04 | 664.6 | 665.0 | 666.5 |
| B05 | 704.1 | 703.8 | 707.1 |
| B06 | 740.5 | 739.1 | 741.1 |
| B8A | 864.7 | 864.0 | 865.6 |

**The synthetic-spectrum convolution:** pure water, phytoplankton, CDOM and minerals through the QAA forward model, solar-weighted.

What S2C's bands do to the same water:
- B02 −5%, B04 −3.5%, B05 −7.4%, B03/B06 about 0.
- Features: F_ndci −0.022, F_bg −0.025, F_red −0.015.
- **Net C-gbm effect: +0.005 log10** (median 0; 80% within −0.020 to +0.040). S2B against S2A: −0.0003.
- ACOLITE uses the official V4 response for S2C and the matching 2018 response for S2A. These agree with the product metadata within 0.3%.

**Physics band adjustment (C1)**, fitted only on synthetic spectra:

| Band | Gain | Extra term |
|---|---:|---|
| B02 | 1.056 | — |
| B04 | 1.048 | — |
| B05 | 1.033 | −0.040 × (B06 − B04) |

## 6. Corrections compared (derivation only)

| Correction | Tandem, derivation (n 34): Δp | B05 | 2025, derivation (n 28): Δp | B05 |
|---|---:|---:|---:|---:|
| C0 none | +0.072 | −19.7% | +0.012 | −17.4% |
| B Stage 12 | +0.012 | −3.1% | −0.035 | +15.2% |
| C1 physics band adjustment | +0.060 | −15.4% | +0.013 | −14.3% |
| C2 tandem gain only | +0.005 | 0.0% | −0.015 | +2.8% |
| C3 tandem gain + offset | −0.017 | +5.5% | −0.148 | +24.6% |

(Δp = S2C minus S2A, log10 feet.)

**Selection.**
- No candidate met every bar on derivation. Mainly that was the harm proxy: one two-class jump in 34 pairs is already 2.9%, above the 2% limit.
- By the frozen fallback rule, **C2** (smallest pooled derivation |Δp|) was carried forward.
- C2's gains: B01 1.185, B02 1.110, B03 1.060, B04 1.112, B05 1.245, B06 1.268.
- These are large because they must also absorb the aerosol over-correction, which depends on conditions.

## 7. Held out: the authority-lift bar

**Bars (frozen; never lowered):**

| | Spectral (B02–B05) | Visibility | State overlap | Harm proxy (class jump ≥ 2) |
|---|---|---|---|---|
| Tandem (H1) | ≤ 3% | ≤ 0.03 | ≥ 95% | ≤ 2% |
| 1–2 days apart (H2, H3, H4) | ≤ 5% | ≤ 0.03 | ≥ 95% | ≤ floor + 2 pp (4.0%) |

**Visibility difference, S2C minus S2A/B (log10):**

| Correction | Tandem (H1, n 50) | 2025 (H2, n 34) | 2026 (H3, n 58) | Stage 19 (H4, n 11) | Pooled (n 153) |
|---|---:|---:|---:|---:|---:|
| C0 none | +0.041 | +0.063 | +0.017 | +0.042 | +0.034 |
| B Stage 12 | 0.000 | −0.004 | −0.064 | −0.057 | −0.007 (mean −0.043) |
| C1 physics | +0.054 | +0.044 | +0.016 | −0.033 | +0.041 |
| **C2 selected** | **+0.011** | **−0.004** | **−0.036** | **−0.071** | **−0.003** |
| C3 | −0.007 | −0.075 | −0.191 | −0.177 | −0.063 |

**Selected C2, bar by bar:**

| Stratum | Spectral | Visibility | State overlap | Harm proxy | Passes |
|---|---|---|---|---|---|
| Tandem (H1) | B02 −1.1%, B03 −1.6%, **B04 −4.0%**, B05 +0.9% | +0.011 | 100% | **4.0%** | NO |
| 2025 (H2) | **+5% to +13%** | −0.004 | 96.9% | 2.9% | NO |
| 2026 (H3) | **+4% to +22%** | **−0.036** | **92.9%** | **13.8%** | NO |
| Stage 19 (H4, n 11, not gating) | +10% to +34% | −0.071 | 100% | 0% | — |

**The verdict, and the pattern behind it:**
- **Lift bar: FAILED.** All three gating strata fail.
- **Each fixed correction fits one regime and misses the next.**
  - Fitted on the dark December tandem, C2 over-brightens summer scenes.
  - Stage 12 is right on the preliminary products and too murky on nominal 2026.
  - Uncorrected S2C reads clearer everywhere.
- A correction made after ACOLITE cannot fix an error that ACOLITE's own aerosol step introduces in proportions that vary from scene to scene.

**Geographic breakdown (tandem, held out):**

| | n | C2 | Stage 12 | C0 |
|---|---:|---:|---:|---:|
| US | 43 | +0.011 | 0.000 | +0.042 |
| Global | 7 | −0.023 | 0.000 | +0.035 |

Posterior differences are small (|median| ≤ 0.05). Unknown shares match within 6 points.

## 8. The S2A/S2B floor

**S2B against S2A, 1–2 days apart** (101 pairs, the same frozen engine):
- visibility −0.004 (IQR −0.084 to +0.070);
- states always overlap (100%);
- class jumps 2.0%;
- bands B02 +1.8%, B03 +5.2%, B04 +6.9%, B05 +5.1%.

**Honest note: the floor itself would fail the operational spectral bar** (5% on B03–B05). That bar was stricter than natural 1–2-day change.

The conclusion does not rest on it. Without the spectral bar, no candidate passes visibility, state and harm in every gating stratum:
- C2 fails 2026 on all three;
- Stage 12 fails 2026 visibility;
- C0 and C1 fail tandem and 2025 visibility.

## 9. Secchi truth, after the freeze (validation only)

S2C was issued at full authority for this comparison. Every eligible S2C truth row was used:
- 38 development rows (outer folds; the Stage 12 path reproduces Stage 15 exactly, max difference 0.0);
- 54 certification rows;
- 45 fresh rows.

| 137 S2C rows | Operational | Clear | Normal | Stained | Limited | Signed bias | Harmful | Severe | ⅔-interval coverage | Median feet error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S2A/B reference (2,705 rows) | 0.715 | 0.89 | 0.68 | 0.60 | 0.70 | −0.016 | 14.8% | 2.0% | 64% | 1.45 |
| C0 none | 0.707 | 0.92 | 0.70 | 0.54 | 0.67 | +0.002 | 13.1% | 1.5% | 64% | 1.87 |
| B Stage 12 | 0.704 | 0.83 | 0.58 | 0.63 | 0.78 | **−0.104** | 17.5% | 2.2% | 55% | 1.64 |
| C1 physics | 0.721 | 0.92 | 0.68 | 0.63 | 0.65 | −0.015 | 12.4% | 1.5% | 61% | 1.71 |
| **C2 selected** | 0.710 | 0.90 | 0.55 | 0.63 | 0.76 | −0.047 | 16.1% | **2.2%** | 60% | 1.68 |
| Stage 12 as shipped (lower authority) | 0.626 | 0.69 | 0.55 | 0.60 | 0.67 | −0.104 | 0% | 0% | 55% | 1.64 |

S2C class sizes: clear 67, normal 48, **stained 10, limited 12**. The S2C stained and limited scores rest on very few rows.

**Full-authority checks for C2:**
- harmful ≤ reference + 5 pp: pass;
- bias within 0.05 of reference: pass (−0.047 vs −0.016);
- **severe ≤ 2%: fail (2.2%).**

**S2C full authority: NO.**

**What truth adds:**
- Stage 12 is the source of the murky bias.
- Uncorrected or physics-adjusted S2C sits at S2A/B parity against Secchi.
- That is a lead for the next stage, not a verdict here: those versions failed the frozen pair bars, and these 137 rows were not allowed to choose.

## 10. Current-era 2025–26 sample (value-blind)

2025 N0511 (H2) and 2026 N0512 (H3), against S2A/B 1–2 days apart:
- **State overlap:**
  - C2: 96.9% and 92.9%;
  - uncorrected: 100% and 92.9%;
  - Stage 12: 97% and 94.5%.
- **Visibility:** in section 7.
- **Features (C2, 2026):** F_kd +0.18, F_re +0.11. The gain-only correction over-lifts the red-edge and QAA inputs in summer.

**Authority and consensus compatibility:**
- No version reaches the bar.
- Under Stage 19's rule S2C stays out of consensus, so nothing changes in the live product.
- **N0513** (5 pairs, from Sep 2026) is radiometrically N0512. Any future correction should name N0511/N0512/N0513.

## 11. What trustworthy S2C would add (hypothetical; S2C not lifted)

Prior passes are counted exactly as Stage 19 counts them: a valid frozen-path sample within the window.

| No valid prior pass | All development events (1,582): before → with S2C | 2025–26 events (115): before → with S2C |
|---|---|---|
| Past 5 days | 67.6% → 66.8% | 71.3% → 59.1% |
| Past 10 days | 52.7% → 51.9% | 59.1% → 48.7% |
| Past 15 days | 42.0% → 41.1% | 52.2% → 39.1% |

**What that means:**
- **The development corpus mostly predates S2C,** so it barely moves there.
- **In the 2025–26 era, S2C would lift the chance of at least one independent recent prior view:**
  - past 5 days: 29% → 41%, ×1.43;
  - past 15 days: 48% → 61%.
- **It adds +46–53% more prior passes** within 10–15 days.
- **That is still the lever,** once S2C is trustworthy.

The Stage 19 consensus re-run with S2C at full authority (pre-registered `dev20.py`, windows 5/10/15) was **not run**, because the lift bar failed. Strong evidence is unchanged at 11.0% / 92.9%. No S2C scene counts toward Strong.

## 12. Exploratory: fixing it before ACOLITE (not pre-registered; no verdict)

**The test:**
- Take the tandem-derivation median offsets at the top of the atmosphere: B8A 0.0010, B11 0.00255, B12 0.00144.
- Subtract them from S2C's L1R (re-calibrated to nominal) before ACOLITE's atmospheric correction.
- ACOLITE's own `offsets_toa` multiplies instead of adding, so a wrapper did it.

| 84 tandem pairs | B02 | B03 | B04 | B05 | Δp |
|---|---:|---:|---:|---:|---:|
| Nominal gains only | 0.893 | 0.932 | 0.870 | 0.810 | +0.058 |
| + offset removed before ACOLITE | 0.949 | 0.983 | 0.963 | 0.907 | +0.032 |
| + physics band adjustment (C1) | 1.002 | 0.979 | 1.009 | 0.961 | +0.028 |

**What it shows:**
- Removing the offset cuts the ACOLITE darkening by half to three-quarters: B02 −11% → −5%, B03 −7% → −2%, B04 −13% → −4%, B05 −19% → −9%.
- With the band-shape adjustment on top, B02–B04 agree within 2%.
- About +0.03 remains. That is consistent with the B08 offset (+0.0004–0.0011), which the test left in place, and B05.
- It is held-out-consistent: the offsets are D1 +0.0010 / +0.0026 / +0.0014 against H1 +0.0008 / +0.0023 / +0.0015.
- It runs on emulated-nominal preliminary products. A real test needs the nominal L1C.

## 13. Decision

- **The S2C low-bias root cause is found:** Stage 12 on nominal products, on top of a NIR/SWIR dark-water offset that ACOLITE amplifies.
- **Stage 12 is not valid for current products.** It should be retired for nominal S2C in a future pre-registered change. It is unchanged in production now.
- **No pre-registered correction lifts S2C.** S2C stays at lower authority. Stage 19 (7/10) stands.
- **The shadow job is not updated.** Section 17 of the brief makes that conditional on the harmonisation passing.

## 14. Files (`research/clarity-candidate/stage20/`)

**Pre-registration and freeze:**
- `PREREGISTRATION_STAGE20.md`;
- `FREEZE_STAGE20.json`: hashes of the pre-registration, `srf20.json` and `harm20.json`.

**Metadata and band responses:**
- `meta20.py`, `meta20.json`, `meta20_N0513*.json`: gains, irradiance and responses by baseline;
- `srf20.py`, `srf20.json`: band-response physics and the C1 adjustment.

**Tandem and pair data:**
- `sites20.py`, `sites20.json`: 463 sites;
- `tandem20.py`, `tandem20_pairs.json`, `tandem20_readouts.json`, `tandemA20.py`, `tandemA20.json`: Track A;
- `build20.py`, `tasks20_prelim.json`, `tasks20_ops.json`, `ops20_pairs.json`, `elevations20.json`: task builders;
- `aco20_one.py`, `run_aco20.py`: the frozen ACOLITE path plus top-of-atmosphere and surface diagnostics;
- `res_prelim20/`, `res_ops20/`: results.

**Analysis:**
- `lib20.py`, `pairs20.py`, `pairs20.json`, `fit20.py`, `harm20.json`, `eval20.py`, `eval20.json`, `floor20.json`;
- `secchi20.py`, `secchi20.json`, `secchi20_rows.json`;
- `avail20.py`, `avail20.json`;
- `dev20.py`: the pre-registered full-authority re-run, written before results; not executed.

**Exploratory:** `aco20x_one.py`, `tasks20_x.json`, `res_x20/`, `explore20.py`, `explore20.json`.

`run_aco20.py` gained the exploratory `toa_sub` switch after the main runs had finished. It is a no-op for every other task.

## 15. Status

S2C LOW-BIAS ROOT CAUSE: Downstream, on top of a sensor offset.
- The Stage 12 V-ρw correction was fitted on preliminary N9905 products, whose visible top-of-atmosphere ran about 1.5% bright.
- On current nominal S2C it brightens water by about 10% too much (3–18% per band on the 2025–26 pairs). S2C then reads 0.06 log10 murkier on pairs (Stage 19 scenes −0.057, 2026 −0.064) and 0.10 murkier against Secchi.
- Beneath it, S2C has an additive NIR/SWIR dark-water offset at the top of the atmosphere (B8A +0.001, B11 +0.0025–0.003, B12 +0.0014), present in every baseline. ACOLITE's aerosol fit over-corrects for it, so S2C water reads up to 19% too dark and uncorrected S2C reads 0.02–0.06 clearer.
- The B05 band shape (707 against 704 nm) is real but nets about 0 through C-gbm.

CURRENT PROCESSING BASELINE AFFECTS BIAS: PARTIAL — the 1.5% visible gain error was confined to the preliminary N9905 baseline, and the Stage 12 coefficients inherit it. The NIR/SWIR offset and the B05 band shape are present in every baseline, including the 2026 nominal reprocessing; N0512/N0513 change gains by 0.3% at most.

STAGE 12 S2C CORRECTION VALID: NO — valid only on the preliminary December 2024 products it was fitted on (held-out tandem as distributed: +0.004). On current nominal S2C it fails the spectral bar in every stratum and reads −0.057 to −0.064 log10 (−0.104 against Secchi).

NEW S2C HARMONIZATION REQUIRED: YES — at the top of the atmosphere, before ACOLITE: NIR/SWIR offset removal plus the B05 band adjustment. No after-ACOLITE candidate met the bar.

S2C TANDEM PAIRS USED / HELD OUT:
- tandem: 158 site-pairs on 20 datatakes; 78 derivation (34 valid) / 80 held out (50 valid);
- also used: 2025 nominal pairs 40 derivation (28 valid) / 40 held out (34 valid); 2026 nominal 80 held out (58 valid); Stage 19 pairs 11 held out;
- the Sen2Cor nominal tandem (763; 408 valid) was descriptive only.

HELD-OUT S2C VS S2A REFLECTANCE AGREEMENT: Selected C2 on the held-out tandem: B02 −1.1%, B03 −1.6%, B04 −4.0%, B05 +0.9% (fails ±3% on B04). On nominal 2025/2026 pairs, C2 over-brightens by +4% to +22%. Uncorrected on the tandem: −7% to −19%.

HELD-OUT VISIBILITY BIAS:
- C2: tandem +0.011, 2025 −0.004, 2026 −0.036, Stage 19 pairs −0.071; pooled −0.003 log10 (n 153);
- uncorrected: pooled +0.034;
- Stage 12: pooled −0.007 (2026 −0.064).

HELD-OUT STATE AGREEMENT: C2 tandem 100%, 2025 96.9%, 2026 92.9% (bar 95%), Stage 19 pairs 100%.

S2C AUTHORITY LIFT BAR PASSED: NO

S2C FULL AUTHORITY: NO (the lift bar failed, and the Secchi check failed on severe, 2.2% > 2%)

BEST LIVE CONSENSUS WINDOW AFTER S2C: unchanged — causal, past 5 days (Stage 19). S2C was not lifted, so the pre-registered re-run was not run.

ZERO-PRIOR-VIEW RATE BEFORE / AFTER S2C: hypothetical, since S2C was not lifted.
- All development events: 67.6% → 66.8% (5 d), 52.7% → 51.9% (10 d), 42.0% → 41.1% (15 d).
- 2025–26 events: 71.3% → 59.1% (5 d), 59.1% → 48.7% (10 d), 52.2% → 39.1% (15 d).

CLEAR / NORMAL / STAINED / LIMITED / OPERATIONAL SCORE: 0.883 / 0.669 / 0.606 / 0.680 / 0.710 (unchanged from Stage 19 causal 5-day; Stage 16 0.880 / 0.643 / 0.571 / 0.676 / 0.693)

HARMFUL RATE, SEVERE RATE: 11.4%, 1.39% (unchanged)

EXACT-FEET CAPABILITY: 8/10 (unchanged)

STRONG EVIDENCE SHARE / ACCURACY: 11.0% of usable answers / 92.9% (unchanged; no S2C scene counts)

STAGE 16 FREEZE BARS PASSED: YES (Stage 19 causal 5-day, unchanged)

TRUE 9/10 DEVELOPMENT BAR PASSED: NO

CURRENT CLARITY SCORE RECOMMENDATION: 7/10 development (uncertified); certified none; deployed production 2/10

READY TO FREEZE CLARITY AND MOVE TO WATER TEMP: NO

NEXT BLOCKER: An S2C correction applied at the top of the atmosphere, before ACOLITE:
- remove the NIR/SWIR dark-water offset (B08/B8A/B11/B12) and add the B05 band adjustment;
- retire Stage 12 for nominal products;
- re-run S2C scenes through ACOLITE and test on a fresh pre-registration.

That needs either Michael's OK for requester-pays AWS access to the nominal reprocessed tandem L1C, or a Copernicus Data Space account. Without one, the gain emulation stays a labelled deviation.

Stop. Do not promote production.
