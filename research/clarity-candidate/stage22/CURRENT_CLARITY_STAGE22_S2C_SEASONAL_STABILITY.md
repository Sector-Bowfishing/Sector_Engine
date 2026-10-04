# Current Clarity Stage 22: S2C Seasonal Stability and a Sensor-Invariant ACOLITE Path

**2026-10-04.** This stage asks why Sentinel-2C reads water differently in winter and summer, and whether a correction that leaves ACOLITE's path alone can fix it. It also decides, separately, whether Stage 12 should keep correcting nominal S2C.

**What didn't change:**
- the C-gbm, which was not refit;
- the Stage 16 posterior gate;
- the Stage 19 consensus code;
- the frozen ACOLITE K4 path;
- the Stage 20/21 authority-lift bars, unchanged and not lowered;
- the Stage 16 freeze bars and the true 9/10 bar.

**What was never used for fitting:** field reports and Secchi truth.

**What was preserved:** Stages 16, 19, 20 and 21 are kept as they are. Stage 21's K0, K1 and K2 and Stage 12 remain named references.

**Method:**
- Pre-registered before any Stage 22 reflectance, pair outcome or Secchi value was read: `PREREGISTRATION_STAGE22.md`, SHA-256 `32e9a547…`, frozen 01:38 UTC.
- The candidate was chosen on derivation pairs only and frozen as `cand22.json` (SHA-256 `73d94f01…`, 04:05 UTC), before any held-out pair or Secchi value was read.
- No threshold was changed after an outcome was seen.

Public production is unchanged.

**The answer: the winter/summer difference is real. Its main mechanism is ACOLITE's residual-glint step, not aerosol path switching, though low sun adds an effect that is not yet explained. A narrower correction (C3) fixes winter S2C against S2A and retires Stage 12, but S2C still does not earn full authority.**
- **Where the difference comes from.** ACOLITE uses the SWIR bands as its glint reference. S2C carries a small additive dark-water offset in B11/B12. ACOLITE reads that offset as glint and subtracts it, scaled, from every visible band, so S2C water comes out darker and therefore clearer.
  - **The evidence is an intervention.** Removing just the B11/B12 offsets removes 65–83% of the winter bias; removing the NIR offsets removes none.
  - **The size of the bias:** **+0.061 in winter against +0.018 in the warm season**. It rises steadily as the sun gets lower (+0.019, +0.050, +0.110 below 25°).
  - **What isn't explained.** The amount of glint transferred is not consistently larger in winter: it is on the held-out pairs, but not on the derivation pairs.
  - **Low sun.** At sun elevations of 25° and above, C3 brings S2C within ±0.005 of S2A. Below 25°, it still reads +0.076 to +0.087 clearer.
- **Path switching is common but is not the cause.** ACOLITE picks a different aerosol model or band for S2C in 46–74% of pairs. That lines up with a bias gap only in the winter derivation set and does not replicate held out. Removing the NIR offsets changes the path in 18–33% of scenes and moves visibility by **0.000**.
- **C3** removes only the frozen B11/B12 top-of-atmosphere offsets before ACOLITE, then applies the B05 band adjustment. On the held-out winter tandem it cuts raw S2C's +0.061 to **+0.007**, with 100% state agreement and 1.1% class jumps.
- **Full authority: NO.**
  - The warm-season same-day stratum cannot gate: only 5 valid pairs at one Arctic lake.
  - The spectral bar fails.
  - Against Secchi, C3 reads 0.051 murkier than the S2A/B reference (limit 0.05).
- **Stage 12 retired: YES** for nominal S2C (N0511, N0512, N0513 and newer). C3 passed all seven pre-registered criteria; S2C stays at lower authority.
- **Scores:** Stage 19 stands at **7/10**. Retiring Stage 12 changes 22 answers and moves operational from 0.7096 to 0.7103.
- **One finding the decision rule did not have to weigh.** On warm-season Secchi rows, **raw S2C is the least biased path** (+0.007 against C3's −0.063). C3 brings S2C closer to S2A; raw S2C is closer to truth in summer. This is the open problem for the next stage.

## 1. Data

| Set | What | Count | Role |
|---|---|---|---|
| **TD / TH** | Stage 21 real-nominal tandem: S2A (Google Cloud) and S2C (AWS, lazy windowed reads), ~30 s apart, 29 Oct – 18 Dec 2024. Stage 21 datatake split. | 92 derivation / 89 held-out site-pairs | TD derivation; TH held out (winter) |
| **S** | Same UTC day S2C ↔ S2A/B, \|Δt\| ≤ 180 min, warm season (open-water window 15 Jul – 15 Sep) | 84 candidates → 25 in window → 15 processed → **5 valid** | Held out; can gate only with ≥ 15 pairs from ≥ 3 sites |
| **T2** | Warm same-track 2-day S2C → S2A: same relative orbit and tile, 48 ± 1 h, 2025 and 2026 | 764 candidates; 160 processed; 66 derivation (T2D) / 68 held out (T2H) valid | Secondary: **not the same water** |
| **FLOOR** | Same-day S2A ↔ S2B at high-latitude lakes, Jun–Sep, 10–90 min apart | 136 candidates at 23 lakes; 59 processed; **30 valid** | The measured natural two-sensor floor (descriptive) |
| **Secchi** | Every eligible S2C truth row, re-run through every path after the freeze | 136 (38 dev, 53 cert, 45 fresh) | Validation only |

**Same-day pairs barely exist.** In 2025–26, S2A flies S2C's exact ground track two days later and S2B five days later. Mid-latitude S2C ↔ S2A/B pairs on the same day therefore do not exist. The only ones are where swaths overlap near the pole:
- all 84 candidates are at **Lake Hazen (81.8°N)**, 40–60 minutes apart, at sun elevations of 10–30°;
- after the ice and snow screen and the validity rule, **5 pairs from 1 site** remain.

This corrects Stage 21, which said the high-latitude overlaps were "about 100 minutes apart". Same-day S2C pairs are 40–60 minutes apart, and same-day S2A ↔ S2B pairs are 10–90 minutes apart.

**Checked over Guntersville, July–October 2026.** Its two tracks are R040 (16:33 UTC) and R083 (16:43 UTC). Counting days mod 10:
- S2C passes on days {0, 3};
- S2A on {2, 5};
- S2B on {5, 8}.

So S2C never shares a day with S2A or S2B there. S2A and S2B do: they pass about 10 minutes apart on adjacent overlapping tracks, for example on 30 Sep 2026. The pre-registered floor used the high-latitude lakes, but a mid-latitude two-sensor floor is available for a later stage.

**Remote reads.** The S2C tandem was read with requester-pays windowed reads (about 11% of each SAFE):
- Stage 22 used **13.9 GB**;
- the running total for Stages 21–22 is **79.1 GB**, against the 95 GB cap;
- no further data was needed.

## 2. Inside ACOLITE: what differs between S2C and S2A

ACOLITE was run with three recording lines added: the per-tile DSF band order and per-band AOT for each aerosol model, the per-tile model, and the selected model. Its output-only glint switches were also on. Neither changes the computation; the L2W samples were verified identical.

**Decomposition**, S2C minus S2A, median over the disk:

| Set | Season | Δ glint reference | Δ glint subtracted (B04) | Δ rhos (B04) | Δ AOT 550 | Raw Δ visibility |
|---|---|---:|---:|---:|---:|---:|
| TD | winter | +0.0015 | **+0.0014** | −0.0017 | +0.006 | +0.039 |
| TH | winter | +0.0013 | **+0.0012** | −0.0022 | +0.007 | **+0.061** |
| T2D | warm | +0.0020 | +0.0018 | −0.0014 | +0.000 | +0.007 |
| T2H | warm | +0.0003 | **+0.0004** | −0.0015 | +0.014 | +0.014 |

On the winter tandem, much of S2C's darker visible reflectance after correction (Δ rhos) is extra glint removed (Δ rhog): about 80% in TD and 55% in TH. In the 2-day warm pairs the share is not stable (T2H about 25%, T2D more than all of it), which is expected when the two scenes are two days apart.

**By season and sun, derivation and held out.**
- Raw S2C; "C1" removes only the B11/B12 offsets.
- "Glint" is the extra B04 glint subtracted for S2C, with its share of the reference water signal (B04 rhos) in brackets.
- Held out uses the pre-registered strata (`eval22.json`). The C1 column uses pairs with diagnostics on both sides, so TH's C1 here (+0.021) differs slightly from section 4's +0.020.
- The shares come from the report-only check `_rel22.py` (`rel22.json`).

| Stratum | Deriv. n | Raw Δ vis. | After C1 | Glint (share) | Held-out n | Raw Δ vis. | After C1 | Glint (share) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Winter | 92 | +0.040 | +0.007 | +0.0014 (9%) | 89 | **+0.061** | +0.021 | +0.0012 (7%) |
| Warm | 66 | +0.007 | +0.001 | **+0.0018 (16%)** | 70 | **+0.018** | +0.006 | +0.0004 (2%) |
| Sun < 25° | 6 | +0.173 | **+0.096** | +0.0015 (15%) | 16 | +0.110 | **+0.089** | +0.0009 (7%) |
| Sun 25–40° | 85 | +0.034 | +0.005 | +0.0015 (9%) | 75 | +0.050 | +0.015 | +0.0013 (7%) |
| Sun ≥ 40° | 67 | +0.015 | 0.000 | +0.0016 (14%) | 68 | +0.019 | +0.007 | +0.0005 (3%) |

What holds in both sets:
- removing the SWIR offsets removes most of the bias except at very low sun;
- the bias rises as the sun gets lower.

What does not hold in both sets: that more glint is transferred in winter. On the derivation pairs the warm season gets more (+0.0018, 16%) yet shows almost no bias. The 2-day warm pairs are not the same water, so their glint difference also carries two days of real change.

**C3 by sun elevation** (report-only, `_lowsun22.py`):

| Sun elevation | Derivation n | Raw | C3 | Held-out n | Raw | C3 |
|---|---:|---:|---:|---:|---:|---:|
| < 25° | 6 | +0.173 | **+0.087** | 16 | +0.110 | **+0.076** |
| 25–40° | 85 | +0.034 | 0.000 | 75 | +0.050 | +0.005 |
| ≥ 40° | 67 | +0.015 | 0.000 | 68 | +0.019 | −0.004 |

C3 fixes S2C against S2A at 25° and above, in both sets. Below 25° it removes about half of the bias, and S2C still reads clearer. That cut-off was found after the freeze; it is a lead for a new pre-registration, not a rule here.

**Path switching**, where a switch means a different selected model or a different modal lowest-AOT band (b1):

| Set | Switch share | Δ vis., switched | Δ vis., not switched | Gap | Model differs | b1 differs | Path change from removing NIR offsets (C2) | Δ vis. change from C2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TD | 46% | +0.094 | +0.023 | **0.071** | 34% | 30% | 32% | 0.000 |
| TH | 60% | +0.057 | +0.065 | −0.008 | 37% | 36% | 33% | 0.000 |
| T2D | 74% | +0.006 | +0.015 | −0.009 | 39% | 59% | 18% | 0.000 |
| T2H | 74% | +0.015 | +0.010 | 0.005 | 45% | 52% | 22% | 0.000 |

**Effect sizes** (Theil–Sen, held out):
- TH: Δ visibility on Δ glint (B04) has slope −0.0, CI −11.0…+10.0;
- TH: Δ visibility on Δ AOT has slope +0.61, CI −0.11…+1.47.

**Verdicts by the pre-registered rules:**
- **Seasonal difference: YES.** Winter +0.061 against warm +0.018. It grows steadily as the sun gets lower, in both sets.
- **Path switching: PARTIAL.** Switches occur in more than 20% of pairs everywhere. The switch/no-switch gap reaches 0.02 only in TD and does not replicate in TH, T2D or T2H. Forcing a path change (C2) moves visibility by zero, so switching is a symptom, not the cause.
- **Root cause, mostly established.** The residual-glint step turns S2C's SWIR dark offset into a visible-band subtraction. Removing that offset alone removes 65–83% of the winter bias.
- **What remains open.** Why winter and low sun are hit harder is only partly explained. The transferred glint is larger in winter on held-out pairs, not on derivation pairs. Below 25° sun a residual of +0.076 to +0.087 survives C3, so something else in the low-sun retrieval also acts.

## 3. Candidates (derivation pairs only)

| Candidate | Definition | J | TD Δ vis. | TD state | TD jumps | T2D Δ vis. |
|---|---|---:|---:|---:|---:|---:|
| A | Raw nominal S2C, no Stage 12 | 0.0395 | +0.0395 | 98.8% | 0.0% | +0.0066 |
| B | Stage 21 K2 (reference, not eligible) | 0.0007 | +0.0001 | 100% | 0.0% | −0.0007 |
| C1 | Remove only the B11/B12 offsets (glint-invariant) | 0.0067 | +0.0067 | 100% | 0.0% | +0.0006 |
| C2 | Remove only the B08/B8A offsets (aerosol-invariant) | 0.0385 | +0.0385 | 100% | 0.0% | +0.0066 |
| **C3** | **C1 + B05 band adjustment** | **0.0000** | **0.0000** | **100%** | **0.0%** | **0.0000** |
| D | Conditional on one scene-level variable | not eligible | | | | |

Here J = max(|median Δ visibility| on TD, on T2D).

**Exact zeros.** C3's medians are exactly 0.000 because the C-gbm is a tree ensemble with piecewise-constant output: 12 of 92 TD pairs and 4 of 66 T2D pairs land in identical leaves, and one of them is the median. The interquartile ranges are ordinary: −0.035…+0.034 and −0.075…+0.052.

**D was not eligible.** None of the four allowed variables — S2C sun elevation, the K0 glint reference, the K0 AOT, the tile's B11 — reached |Spearman| ≥ 0.4 against the difference between any two members. The strongest was AOT for A against C1, |ρ| = 0.35, on 121 pairs. Sun elevation was never strong enough to switch between paths.

**Selected: C3.** The lowest J; no other eligible candidate was within 0.005. It meets the TD constraints (state ≥ 95%, jumps ≤ 2%).

C3 is runnable from the S2C scene alone:
1. Remove B11 = 0.00173 + 0.00445 × the tile's own clear-pixel B11 median, and B12 = 0.0011, from the top-of-atmosphere reflectance.
2. Run the frozen ACOLITE K4 path.
3. Apply B05′ = 1.0332·B05 − 0.0397·(B06 − B04).
4. Run the frozen C-gbm and Stage 16 gate, without Stage 12.

## 4. Held out, with the original bars reported exactly

Bars, unchanged from Stages 20–21:
- spectral within 3%;
- visibility ≤ 0.03;
- state overlap ≥ 95%;
- class jumps ≤ 2%.

The B02–B05 columns are S2C/reference reflectance ratios.

| Set | Path | n | Δ vis. | State | Jumps | B02 | B03 | B04 | B05 | Bars |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **TH** (winter, same water) | Raw A | 89 | +0.061 | 100% | 1.1% | 0.919 | 0.945 | 0.871 | 0.825 | no |
| | K2 (B) | 88 | +0.009 | 100% | 1.1% | 0.971 | 0.990 | 0.962 | 0.966 | no (spectral) |
| | C1 | 89 | +0.020 | 100% | 1.1% | 0.942 | 0.980 | 0.940 | 0.887 | no |
| | **C3** | 89 | **+0.007** | **100%** | **1.1%** | 0.942 | **0.980** | 0.940 | 0.943 | **no (spectral)** |
| | Stage 12 | 89 | 0.000 | 100% | 1.1% | 0.964 | 0.979 | 0.971 | 0.977 | no |
| **S** (Hazen, same day) | Raw A | 5 | +0.174 | 100% | 0% | 0.900 | 0.866 | 0.584 | 0.507 | no |
| | **C3** | 5 | **+0.168** | 100% | 0% | 0.913 | 0.887 | 0.677 | 0.651 | no |
| | Stage 12 | 5 | +0.156 | 100% | 0% | 0.920 | 0.895 | 0.756 | 0.777 | no |
| **T2H** (warm, 2 days, secondary) | Raw A | 65 | +0.014 | 95.3% | 7.7% | 0.907 | 0.916 | 0.888 | 0.846 | no |
| | K2 (B) | 68 | −0.009 | 93.8% | 4.4% | 0.954 | 0.967 | 0.946 | 0.994 | no |
| | **C3** | 68 | **−0.009** | **93.8%** | **4.4%** | 0.941 | 0.956 | 0.935 | 0.975 | no |
| | Stage 12 | 65 | −0.040 | 92.2% | 4.6% | 0.977 | 1.014 | 1.045 | 1.077 | no |
| **FLOOR** (S2A ↔ S2B, same day) | Two full-authority sensors | 30 | −0.027 | 100% | 0% | 0.937 | 0.957 | 1.029 | 1.012 | no (spectral) |

**Against the measured floor.** Two full-authority satellites, read the same day over the same high-latitude water, differ by:
- −0.027 in visibility, IQR −0.157…+0.011;
- 6.3% in B02 and 4.3% in B03.

So the 3% spectral bar is stricter than what two certified sensors achieve against each other. The bar is reported unchanged. Relative to the floor:
- C3's held-out winter visibility bias (+0.007) is a quarter of the floor's;
- its state agreement (100%) and class jumps (1.1%) are within the floor's;
- B02/B03 sit inside the floor's spread;
- B04/B05 (−6%) are outside the floor's +3%/+1%.

The floor is Arctic summer and the tandem is temperate winter, so this comparison describes the bar; it is not a substitute for it.

**Hazen is not representative.** All five same-day warm pairs keep a large bias under every path (+0.16 to +0.17): sun 10–30°, Arctic water, one lake. It confirms that low sun is where S2C departs most. It cannot certify, and could not have gated, by the pre-registered rule.

## 5. Decision A: full authority

| Requirement | Result |
|---|---|
| TH bars | **fail** (spectral); visibility +0.007, state 100% and jumps 1.1% pass |
| At least one warm same-day stratum gating (≥ 15 valid pairs, ≥ 3 sites) | **fail**: 5 pairs, 1 site. **This is the blocking condition.** |
| Pooled \|median Δ visibility\| ≤ 0.03 over gating strata | pass (+0.007, TH only) |
| Secchi: harmful ≤ reference + 0.05 | pass (14.0% against 14.8% + 5%) |
| Secchi: severe ≤ 2% | pass (1.5%) |
| Secchi: \|bias − reference bias\| ≤ 0.05 | **fail**: −0.067 against −0.016, 0.051 apart |

**S2C FULL AUTHORITY: NO.** The 5/10/15-day causal consensus re-run was therefore not executed, as pre-registered.

## 6. Secchi truth (after the freeze; validation only)

Every eligible S2C truth row was re-run through each path. The pools are reported separately; all were seen in earlier stages, so this is validation, not blind certification.

| 136 S2C rows | Operational | Clear | Normal | Stained | Limited | Bias | Harmful | Severe | ⅔ coverage | Median feet error |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| S2A/B reference (2,705) | 0.715 | 0.89 | 0.68 | 0.60 | 0.70 | −0.016 | 14.8% | 2.0% | 64% | 1.45 |
| Raw A | 0.706 | 0.92 | 0.70 | 0.54 | 0.67 | **+0.002** | 13.2% | 1.5% | 65% | 1.87 |
| Stage 12 | 0.704 | 0.83 | 0.58 | 0.63 | 0.78 | −0.101 | 17.6% | 2.2% | 55% | 1.62 |
| K2 (Stage 21) | 0.688 | 0.89 | 0.61 | 0.54 | 0.72 | −0.071 | 13.2% | 1.5% | 60% | 1.56 |
| C1 | 0.700 | 0.89 | 0.66 | 0.54 | 0.72 | −0.067 | 13.2% | 1.5% | 62% | 1.58 |
| **C3** | **0.687** | 0.89 | 0.61 | 0.54 | 0.72 | **−0.067** | **14.0%** | **1.5%** | **62%** | **1.56** |

**By pool** (bias / harmful):

| Pool | n | Reference | Raw A | Stage 12 | C3 |
|---|---:|---|---|---|---|
| dev | 38 | +0.007 / 12.4% | +0.014 / 15.8% | −0.050 / 21.1% | +0.012 / 15.8% |
| cert | 53 | −0.034 / 17.8% | +0.002 / 17.0% | −0.174 / 18.9% | −0.091 / 17.0% |
| fresh | 45 | −0.054 / 2.2% | −0.002 / 6.7% | −0.092 / 13.3% | −0.071 / 8.9% |

**By S2C season:**

| Season | n | Raw A | C3 | Stage 12 | C3 − A |
|---|---:|---:|---:|---:|---:|
| Warm (Apr–Oct) | 130 | **+0.007** | −0.063 | −0.097 | −0.038 |
| Winter (Nov–Mar) | 6 | −0.085 | −0.190 | −0.193 | −0.131 |

**The tension, stated plainly.**
- Against S2A on the same water, C3 is right and raw S2C is too clear: winter +0.061.
- Against Secchi in summer, raw S2C is unbiased and C3 is 0.06 too murky.

These are different scenes, so they don't strictly contradict. They do mean an always-on correction is not proven right in summer. The pre-registered rule tests C3 first and C3 passed, so the decision stands. Raw A was not tested as the replacement, because the rule only falls back to A when C3 fails.

**Notes:**
- **A missing row.** Stage 21 had 137 rows. One cert row (SYKE:1665935, 10 Sep 2025, Finland) lost its kept L1R in a worker collision, so C1/C2 never ran for it, and the pre-registered script drops rows missing a path. It was re-run after the decision; the result does not change (section 7).
- **Reproduction check.** Re-running the 38 dev rows through the instrumented path reproduced Stage 15's Stage 12 answers to within 0.064 log10 at most.

## 7. Decision B: Stage 12 retirement (independent of authority)

**Scope:** nominal operational S2C baselines N0511, N0512, N0513 and newer nominal equivalents. Preliminary N9905/N9906 research products are untouched.

**Rule:** Stage 12 is retired if the replacement R = C3 meets every criterion.

| # | Criterion | C3 | Stage 12 | Limit | Pass |
|---|---|---:|---:|---|---|
| 1 | \|median signed error\| | 0.067 | 0.101 | ≤ 0.081 | yes |
| 2 | Harmful | 14.0% | 17.6% | ≤ 17.6% | yes |
| 3 | Severe | 1.5% | 2.2% | ≤ 2.2% | yes |
| 4 | Operational | 0.6873 | 0.7040 | ≥ 0.6840 | yes |
| 5 | ⅔ coverage | 61.8% | 55.1% | ≥ 53.1% | yes |
| 6 | State overlap, TH / T2H | 100% / 93.8% | 100% / 92.2% | ≥ 97% / ≥ 89.2% | yes |
| 7 | Per pool: \|bias\| ≤ \|bias₁₂\| + 0.03 and harmful ≤ harmful₁₂ + 5% | dev / cert / fresh all pass | | | yes |
| 7 | \|median Δ vis.\| ≤ 0.05 on TH and T2H | 0.007 / 0.009 | | | yes |

**STAGE 12 RETIREMENT BAR PASSED: YES.** Stage 12 is retired from the nominal-S2C lower-authority path and replaced by C3. **S2C stays at lower authority.** Retirement does not imply full authority.

**Sensitivity: 137 rows.** The missing cert row (SYKE:1665935) was re-run after the decision, in a separate output (`_res_syke/`, `secchi22_137.json`, `decide22_137.json`); the frozen 136-row files are byte-identical. Its K0 and K1 samples reproduced exactly. With it:
- C3: bias −0.071, harmful 13.9%, severe 1.5%, operational 0.6874, coverage 61.3%;
- Stage 12: bias −0.104, harmful 17.5%, severe 2.2%, operational 0.7043, coverage 54.7%.

**All seven criteria still pass**, and Stage 12 is still retired. Criterion 4 is the closest, by 0.003 (0.6874 against 0.6843). The full-authority Secchi bias check still fails: −0.071 against −0.016.

**Effect on the development scores.** In the Stage 19 anchors, 22 S2C rows were recomputed with C3:

| | Operational | Clear | Normal | Stained | Limited | Harmful | Severe | Unknown | Strong share / accuracy |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Stage 19 | 0.7096 | 0.883 | 0.669 | 0.606 | 0.680 | 11.44% | 1.39% | 10.1% | 11.0% / 92.9% |
| **Stage 19, Stage 12 retired** | **0.7103** | **0.884** | **0.671** | **0.606** | **0.680** | **11.44%** | **1.39%** | **9.9%** | **10.9% / 92.9%** |

## 8. Consensus window and coverage

Full authority failed, so the 5/10/15-day causal consensus re-run (the `stage21/dev21.py` pattern) was not executed. The best live window is unchanged: **causal, past 5 days** (Stage 19).

**Zero-prior-view rate:**
- **Live:** 66.8% (5 d), unchanged; lower-authority S2C does not count as a prior view.
- **If S2C were trustworthy:** Stage 21's count (not re-run), for 2025–26 events, would be 71.3% → 59.1% (5 d), 59.1% → 47.8% (10 d), 52.2% → 38.3% (15 d).

## 9. Internal map surface (brief section 18)

Stage 12's retirement creates a new candidate path, so the candidate is now visible on the normal Sector Mapbox map for internal accounts. There is no separate developer map.

**Shadow job** (`Sector_Engine` branch `feat/clarity-candidate-shadow`, local):
- every new nominal S2C pass over the 17 pilot lakes runs the C3 path, and stored nominal-S2C scenes are re-answered on it;
- each answer is stored beside the old Stage 12 answer (`stage16_stage12`) with full provenance (section 10);
- **Two Mac runs on 2026-10-04, window 21 Sep – 4 Oct, all 17 pilot lakes:**
  - `mac-20261004T050650` processed 82 scenes. 7 S2C scenes failed when the Mac ran out of disk; they were retried.
  - `mac-20261004T055847` added provenance v2 and retried those scenes: 68 scenes, **0 errors**.
- **Result:** all 68 stored S2C scenes (every one baseline 05.13) are on the C3 path at provenance v2.
  - 396 of their 578 points carry the per-point diagnostic state: every point with an ACOLITE sample. The rest are cloud or outside the crop.
  - 183 points have a usable C3 answer.

**App** (`Sector-mapbox`, branch `feat/clarity-production`, commit `22d479d7`, local):
- **Master accounts** see the candidate by default on the same Water Clarity layer: each pilot point is a small diamond in the layer's own clear-to-muddy colours.
- **The key** carries a quiet source tag (**Production**, or **Beta** where the Current Clarity beta is drawing) and a **Candidate** line, e.g. "Clear to normal · ~4.1 ft · pass Sep 30, 4 days old".
- **Tapping a diamond** opens "Water Clarity · Candidate":
  - state, feet, evidence, satellite and S2C path;
  - "Observed Sep 30, 11:38 AM CDT · 4 days old";
  - a note that the candidate is internal and uncertified;
  - no reporting from it.
- **The production tap card** now states when the satellite saw that water ("Observed Sep 30, 11:44 AM CDT · 4 days old"), from the scene its region was read from.
- **Public users** receive the approved production source, unchanged. This is an internal testing surface, not a promotion.

The change was verified on the iPhone 17 Pro simulator at Guntersville: the key, a candidate card and the production card.

## 10. Provenance kept per S2C result (brief section 19)

**Research runs** (`res22_*`, per scene and variant):
- satellite, product id and processing baseline;
- the physical pass (platform, UTC date, relative orbit) and acquisition time;
- ACOLITE commit `f73cbe7` and the K4 configuration;
- the path variant and the `cand22.json` hash;
- the TOA offsets applied and m_C;
- the DSF state per aerosol model (band order, per-band AOT per tile), the per-tile and selected model, and the mean AOT;
- the disk rhot, rhos, aot_550, glint reference and per-band rhog;
- raw and corrected L2W samples;
- features, visibility, state and authority.

**Shadow job** (each nominal S2C scene):

| Level | What is stored |
|---|---|
| Scene `meta` | product id, baseline, pass time and date, sun and view geometry, `s2c_path: stage22-c3` |
| `meta.c3` | `prov: 2`; the ACOLITE commit, frozen K4 overrides and runner; TOA offsets; m_C; per-crop DSF state (selected model, mean AOT, per-tile model, modal b1/b2 per aerosol model); hashes of `corr21.json`, `cand22.json`, the pre-registration and the instrumented runner; `stage12_retired: true`; `authority: lower` |
| Each point | raw inputs (`inputs`); corrected inputs (`inputs_c3`) with the point's diagnostic state (rhot, rhos, aot_550, glint reference, rhog, ac_model, geometry); the C3 answer (`stage16`: tier, state, display, authority, p, interval, evidence, `s2c_path`); the retired Stage 12 answer (`stage16_stage12`) |

**Provenance version 2.** Diagnostics were added after the first C3 pass. Scenes stored without them are re-run once by the next shadow run, and that has been done (section 9). The C3 crop run uses the instrumented runner, which only records values; its output was verified identical. Its hash is stored with the others.

## 11. Files (`research/clarity-candidate/stage22/`)

**Pre-registration and freeze:**
- `PREREGISTRATION_STAGE22.md`;
- `FREEZE_STAGE22.json`: hashes of the pre-registration, pair metadata, `corr21.json` and `cand22.json`.

**Pairs and tasks:**
- `build22_pairs.py` → `pairs22_meta.json`;
- `build22_tasks.py` → `tasks22_{TD,TH,T2,S,FL,truth}.json`.

**Processing:**
- `lazy22.py`: lazy SAFE from AWS;
- `aco22_one.py`: the instrumented frozen ACOLITE path;
- `run_aco22.py`: driver; one remote read, every variant from the kept L1R;
- `res22_{TD,TH,T2,S,FL,truth}/`.

**Analysis:**
- `anal22.py` → `derive22.json`, `cand22.json` (frozen), `eval22.json`;
- `secchi22.py` → `secchi22.json`, `secchi22_rows.json`;
- `decide22.py` → `decide22.json`;
- `retire22_scores.json`.

**Engine (shadow):** `jobs/clarity-candidate/s2c22.py` and `shadow.py`.

**Environment.** Stage 21 had installed boto3 and six dependencies into the frozen `geo` environment. They were removed (`ENV_OK` is true again), because the shadow self-check requires the frozen environment. Later AWS work loads boto3 from a separate folder on the path, never the frozen environment.

## 12. Status

WARM-SEASON SAME-DAY PAIRS FOUND: 5 valid (of 84 candidates), all at one site, Lake Hazen (81.8°N).
- The pairs are 40–60 minutes apart, at sun elevation 10–30°.
- The gate needs ≥ 15 pairs from ≥ 3 sites.
- Mid-latitude same-day S2C ↔ S2A/B pairs do not exist in 2025–26: S2A trails S2C's track by 2 days, S2B by 5.

S2C SEASONAL DIFFERENCE CONFIRMED: YES
- Raw S2C visibility bias is +0.061 in winter (n 89) against +0.018 in the warm season (n 70).
- By sun elevation: +0.110 below 25°, +0.050 at 25–40°, +0.019 at 40° and above.

ACOLITE PATH SWITCHING CONFIRMED: PARTIAL
- Switches occur in 46–74% of pairs.
- The switch/no-switch gap reaches ≥ 0.02 only in the winter derivation set (0.071), not held out (TH −0.008, T2H +0.005).
- Forcing path changes (C2) moves visibility by 0.000.

ROOT CAUSE OF WINTER/SUMMER DIFFERENCE:
- ACOLITE's residual-glint correction uses the SWIR bands as its glint reference. S2C's additive B11/B12 dark-water offset is read as glint and subtracted, scaled, from every visible band, so S2C reads clearer.
- Removing only those offsets removes 65–83% of the winter bias; removing the NIR offsets removes none. It is not aerosol path switching.
- The bias grows as the sun gets lower: +0.019 (≥ 40°), +0.050 (25–40°), +0.110 (< 25°).
- Why low sun is hit harder is not fully explained:
  - the transferred glint is larger in winter on held-out pairs (+0.0012 against +0.0004) but not on derivation pairs (+0.0014 against +0.0018);
  - C3 is within ±0.005 of S2A at 25° sun and above, but +0.076 to +0.087 below 25°.

BEST S2C PROCESSING PATH: C3
- Remove only the frozen B11/B12 TOA offsets before ACOLITE: B11 = 0.00173 + 0.00445 × the tile's own clear-pixel B11; B12 = 0.0011.
- Run frozen ACOLITE K4, then B05′ = 1.0332·B05 − 0.0397·(B06 − B04).
- No Stage 12; lower authority.
- It is runnable from the S2C scene alone.
- It matches S2A within ±0.005 at sun elevations of 25° and above; below 25° it still reads +0.076 to +0.087 clearer.
- Caveat: on warm-season Secchi rows raw S2C is less biased (+0.007 against −0.063).

WINTER HELD-OUT VISIBILITY BIAS: +0.007 log10 (C3, TH, n 89). Raw is +0.061, K2 +0.009, Stage 12 0.000.

WARM-SEASON HELD-OUT VISIBILITY BIAS:
- Same-day (Hazen, n 5, cannot gate): C3 +0.168 against raw +0.174.
- Same-track 2-day (T2H, n 68, secondary): C3 −0.009 against raw +0.014 and Stage 12 −0.040.

HELD-OUT STATE AGREEMENT:
- TH 100%;
- Hazen 100% (n 5);
- T2H 93.8% (Stage 12 92.2%);
- measured S2A ↔ S2B floor 100% (n 30).

HELD-OUT HARM / CLASS-JUMP RATE:
- TH 1.1%;
- Hazen 0%;
- T2H 4.4% (raw 7.7%, Stage 12 4.6%);
- floor 0%.

SECCHI SIGNED BIAS: C3 −0.067 (136 rows). The S2A/B reference is −0.016, raw +0.002 and Stage 12 −0.101.
- By pool: dev +0.012, cert −0.091, fresh −0.071.
- Warm-season rows: −0.063 against raw +0.007.

S2C FULL AUTHORITY: NO
- The warm same-day stratum cannot gate.
- The TH spectral bar fails.
- The Secchi bias is 0.051 from the reference (limit 0.05).

STAGE 12 RETIREMENT BAR PASSED: YES (all seven criteria)

STAGE 12 NOMINAL S2C CORRECTION RETIRED: YES. Replaced by C3 for N0511, N0512, N0513 and newer nominal baselines; N9905/N9906 untouched.

NOMINAL S2C AUTHORITY AFTER STAGE 22: LOWER

BEST LIVE CONSENSUS WINDOW: causal, past 5 days (Stage 19, unchanged; no re-run, because full authority failed)

ZERO-PRIOR-VIEW RATE: live 66.8% (5 d), unchanged.
- Hypothetical with trustworthy S2C, 2025–26 events (Stage 21 count): 59.1% (5 d), 47.8% (10 d), 38.3% (15 d).

CLEAR SCORE: 0.884

NORMAL SCORE: 0.671

STAINED SCORE: 0.606

LIMITED SCORE: 0.680

OPERATIONAL SCORE: 0.710 (7/10)

HARMFUL RATE: 11.4%

SEVERE RATE: 1.39%

EXACT-FEET CAPABILITY: 8/10

STRONG EVIDENCE SHARE / ACCURACY: 10.9% of usable answers / 92.9%

STAGE 16 FREEZE BARS PASSED: YES (7/10; every class ≥ 0.60; harmful 11.4% ≤ 15%; severe 1.39% ≤ 2%)

TRUE 9/10 DEVELOPMENT BAR PASSED: NO (operational 0.710 against 0.85; weakest class 0.606 against 0.80; harmful 11.4% against 5%; Strong 10.9% against 50%)

CURRENT CLARITY SCORE RECOMMENDATION: 7/10 development (uncertified); certified none; deployed production 2/10

REMAINING TECHNICAL LIMITATIONS:
- **No warm same-day S2C reference at usable latitudes** while S2A and S2B trail S2C's track; only an Arctic lake has same-day pairs. S2C's warm-season behaviour can be checked only against 2-day pairs (not the same water) or truth.
- **Raw S2C is the best summer path on Secchi**, while C3 is best against S2A. A season- or sun-aware choice between them needs a discriminator stronger than any tested (best |ρ| 0.35) and a fresh pre-registration.
- **The 3% spectral bar is stricter than two certified satellites manage** against each other the same day (B02 6.3%, B03 4.3%). It is unchanged here and should be revisited openly, not silently. Mid-latitude same-day S2A ↔ S2B pairs (adjacent tracks, about 10 minutes apart) would give a floor measured under the conditions the bar is applied to.
- **A low-sun residual survives C3.** Below 25° sun, S2C still reads +0.076 to +0.087 clearer than S2A after C3 (n 16 held out, 6 derivation). The glint step does not explain it; it needs its own diagnosis. Until then, low-sun S2C scenes are the least trustworthy, and a sun-elevation cut-off is the obvious candidate for a fresh pre-registration.
- **Stage 21's B11/B12 TOA residuals** (0.00036 / 0.00035) remain above ±0.0003.
- **Every truth pool has been seen;** no blind data is left.
- **Stained sits at the 0.60 floor** (0.606).
- **Strong evidence covers 10.9%** of answers against the 50% target.

Stop. Do not promote public production.
