# Current Clarity Stage 14: Blind Certification

**Diagnostic and certification only.**
- Production is unchanged, and nothing was deployed.
- No Sector field observation was used, and Michael's Guntersville survey was not touched.
- The P2 fresh holdout was not touched: every certification site has no 2026 record.
- Water Temperature was not started.
- No spectral model was searched for or retuned. The engine is Stage 13's C-gbm, fitted once on development rows.

**Freeze order** (sha256 values in `FREEZE_STAGE14.json`):

| Step | UTC | What was fixed |
|---|---|---|
| Certification protocol | 2026-10-01T03:19:55Z | Eligible files, inclusion and exclusion, lake independence, sampling, matching, class minima (`cert/CERT_PROTOCOL_STAGE14.md`, sha256 `d0a7ebaf…`) |
| Pre-registration | 2026-10-01T03:25:06Z | Product states, bands, decision metric, O2/C-gbm rule, tier-3 rule, clear-water tests, pass criteria (`PREREGISTRATION_STAGE14.md`, `6681db60…`) |
| Engine | 2026-10-01T03:30:20Z | C-gbm fit, bands, feet authorisation, interval, tier-3 rule (`engine/`, `71c511e1…`) |
| WQP sample | after matching | `cert/wqp_sample.csv` (`42756ae0…`) |
| Unsealed | 2026-10-01T10:42:04Z | Secchi, chlorophyll and turbidity of the certification rows (`unseal/truth14.json`, `88b46c63…`) |

**Four addenda.** Each was recorded and hashed before any certification value was read:

| Addendum | What it changed | Why it cannot bias the score |
|---|---|---|
| **A1** (I/O only) | The ACOLITE fetch skips the TCI preview image, about 19% of each download; ACOLITE never reads it | The six development validation scenes reproduce all 264 sampled values exactly |
| **A2** (draw) | Every event not yet extracted is prescreened at ≤ 20% scene cloud. The first draw matched only 11% of events: 31–32% at ≤ 20% cloud, 1–5% above. A second draw continues the frozen seeded order; it used up the eligible pool under the lake caps at 2,655 site-days | Cloud and draw order are independent of Secchi |
| **A3** (state cap) | The 15% state cap is applied over the combined US core, as the protocol's check requires. Minnesota was 15.7% once NLA was added; 7 Minnesota WQP rows were removed, last-selected first | Reads only states and the seeded order |
| **A4** (environment) | At 00:00 the operating system's temp-file cleanup deleted package files of the `geo` Python environment. Every later ACOLITE run failed explicitly. The environment was rebuilt at identical versions, and the 975 affected items were re-run unchanged | A refit reproduces the frozen engine exactly (max difference 0); the six validation scenes reproduce exactly |

**The pipeline itself** had been checked before any certification scene was run. On the six development scenes it
reproduces Stage 12's default-mask samples and Stage 13's M3 samples exactly.

## The answer

**The frozen engine certifies at the level development predicted. That level is not yet good enough to pass.**

- **The engine.** C-gbm, Stage 13's best exact-feet model, frozen as a single continuous engine. One prediction gives
  exact feet, a two-thirds interval (−37% / +51%) and a product state. The boundary bands sit where the odds across
  3 ft and 2 ft fall below 2:1.
- **O2 lost** the pre-registered comparison: it is worse on decision quality by 0.037, CI excludes 0.
- **The blind test.** The sealed WQP tier and the NLA rows give **825 US observations at 675 lakes in 46 states**, never
  used in any fit or selection.
- **Decision quality matched development:** decision-balanced accuracy 0.726 against 0.724, and the interval covered
  65% of truths against a two-thirds target.

| Rubric | Blind certification | Development |
|---|---|---|
| Exact feet | 7/10 | 8/10 |
| Original hard class (kept for comparison) | 4/10 | 5/10 |
| Boundary-aware product | 4/10 | 5/10 |

- **Boundary states rescue stained water as a decision.** True stained water gets a right answer 69% of the time
  (precision 0.74), against 33% hard recall.
- **The certification does not pass** (2.0 of 6 points). Clear feet, stained, limited and sediment are PARTIAL; normal
  and algae are NO.
  - **Normal fails** because a plain "Normal" answer is right only 41% of the time. Most of those errors are clear water
    read low.
  - **Algae fails** because in algal water the engine is no better than always answering the same state.
- **Two failures appear only on independent water:**
  - Sentinel-2C reads 0.19 log low (n 23);
  - cool-season clear water reads 0.15 log low.
- **The clear-water bias is a deep-water tail** (section 5), not a constant or proportional error.
- **Tier 3** is reduced to a lower-authority "Clear", right 78% of the time on certification.
- **Readiness.** Production is unchanged, so readiness stays 2/10 as deployed. The certified candidate would be 4/10 if
  deployed.

## 1. The frozen production candidate

| Component | Frozen as |
|---|---|
| Reflectance | ACOLITE 20260421.0 K4, lake-elevation pressure (USGS EPQS in the US, Copernicus GLO-30 in Finland), 60 m disk, ≥ 5 pixels |
| Sentinel-2C | V-ρw production coefficients (Stage 12) |
| Tier 1 | Default ACOLITE mask |
| Tier 2 | M3 relaxed mask, where tier 1 has no disk |
| Tier 3 | C3 on Sen2Cor reflectance, where tiers 1–2 have none; lower authority |
| Engine | **C-gbm**: the Stage 13 seven-feature constrained boosting, fitted once on the 1,206 E13 tier-1 development rows |
| Class / state | From C-gbm's own prediction: hard class at 6 / 3 / 2 ft, boundary states from frozen bands (section 2) |
| Exact feet | Authorised for every class (all four meet the Stage 12 bars on pooled lake-held-out predictions) |
| Interval | p plus the 1/6 and 5/6 quantiles of the lake-held-out residuals: −37% to +51% of the prediction |

O2 is not frozen, because it lost the pre-registered comparison (section 3).

## 2. The product output: states built on retrieval resolution

| Product state | Prediction range (ft) | Feet shown | Authority |
|---|---|---|---|
| Clear | ≥ 6.0 | yes | ACOLITE (tiers 1–2) |
| Normal | 3.80 to 6.0 | yes | ACOLITE |
| **Normal-to-Stained** | 2.63 to 3.80 | yes | ACOLITE |
| Stained | 2.38 to 2.63 | yes | ACOLITE |
| **Stained-to-Limited** | 1.70 to 2.38 | yes | ACOLITE |
| Limited | < 1.70 | yes | ACOLITE |
| Clear (lower authority) | Sen2Cor-C3 ≥ 6.0 | lower-confidence feet | tier 3 |
| Unknown / Low Authority | any other tier-3 reading, or no reading | no | — |

**How the bands were set.** At each boundary, a logistic fit of "truth above the boundary" against the engine's
lake-held-out prediction places each edge where the odds reach 2:1. Each edge is at least ±0.05 log from the boundary
(the Stage 13 ±12% platform band):

| Boundary | Logistic α | β (per log10) | Rows within ±0.30 | Lower edge | Upper edge |
|---|---:|---:|---:|---:|---:|
| 3 ft | -0.20 | 8.7 | 730 | 2.63 ft (-0.057) | 3.80 ft (+0.102) |
| 2 ft | -0.02 | 9.4 | 496 | 1.70 ft (-0.072) | 2.38 ft (+0.076) |

- **The bands come from the engine's own error, not from a label.** Near 3 ft, a prediction between 2.63 and 3.80 ft is
  not twice as likely to be on one side of 3 ft as the other. The same holds near 2 ft between 1.70 and 2.38 ft.
- **What "Stained" alone means.** The two bands leave only 2.38–2.63 ft for a plain "Stained", the Stage 13 resolution
  finding in product form. Most stained water is reported as Normal-to-Stained or Stained-to-Limited.
- **Feet stay visible when supported.**
  - **Tiers 1–2:** exact feet with every state, because every class passes the Stage 12 authorisation bars. The
    two-thirds interval goes with them.
  - **Tier 3:** feet only with a lower-authority Clear.
- **No Clear-to-Normal state.** The specification has none, so 6 ft stays a hard boundary.
- **Never mixed with the old rubric.** The original hard-class metrics still use C-gbm's hard class, and a boundary
  state is never counted as an exact hit there.

## 3. O2 against C-gbm (development data only)

| Engine (development, tiers 1–2, nested lake-held-out) | Decision-balanced | Specificity | Clear decision R / P | Normal | Stained | Limited | Original balanced | Feet error | Feet outside the state |
|---|---:|---:|---|---|---|---|---:|---:|---:|
| **C-gbm** | 0.724 | 0.74 | 0.82 / 0.86 | 0.72 / 0.64 | 0.64 / 0.76 | 0.72 / 0.81 | 0.581 | ×1.35 | 0.0% |
| O2 | 0.688 | 0.74 | 0.83 / 0.83 | 0.62 / 0.61 | 0.63 / 0.74 | 0.67 / 0.74 | 0.574 | ×1.37 | 3.0% |
| C-lin (reference) | 0.701 | 0.74 | 0.86 / 0.83 | 0.63 / 0.63 | 0.66 / 0.73 | 0.65 / 0.78 | 0.565 | ×1.37 | 0.0% |

O2 minus C-gbm, decision-balanced: **-0.037** (lake bootstrap 95% CI -0.063 to -0.010).

- **C-gbm is the frozen candidate on both counts:**
  - by the rule, because it produces exact feet, an interval and a product state from one prediction;
  - by the evidence, because O2 is *worse* on decision quality (−0.037, CI excludes 0). The pre-registered exception
    would have needed O2 to be better by 0.03.
- **Why O2 loses once boundary states exist.** Its learned cut-points (2.12 / 3.78 ft) bought stained recall by moving
  the hard boundaries. With boundary states, that trade costs normal decision recall (0.62 against 0.72). It also shows
  feet that contradict the state on 3% of rows.
- **What both engines share:**
  - specificity: 74% of answers are a single class;
  - decision recall of 0.64 for stained water, against 0.25–0.38 hard recall in Stage 13.

## 4. Historical capability of the frozen candidate (development, lake-held-out)

| Capability (development, historical) | Exact feet | Original hard class (R / P) | Boundary-aware product (decision R / P) |
|---|---|---|---|
| Clear | PARTIAL (×1.36, -1.7 ft) | SUPPORTED (0.79 / 0.86) | SUPPORTED (0.82 / 0.86) |
| Normal | SUPPORTED (×1.31, +0.3 ft) | PARTIAL (0.61 / 0.49) | PARTIAL (0.72 / 0.64) |
| Stained | SUPPORTED (×1.37, +0.6 ft) | NOT (0.26 / 0.36) | PARTIAL (0.64 / 0.76) |
| Limited | SUPPORTED (×1.45, +0.5 ft) | PARTIAL (0.50 / 0.71) | PARTIAL (0.72 / 0.81) |
| Algae | SUPPORTED (×1.36, +0.6 ft) | SUPPORTED (0.51 vs 0.37) | PARTIAL (0.71 vs 0.61) |
| Sediment | SUPPORTED (×1.33, +0.1 ft) | PARTIAL (0.52 vs 0.42) | PARTIAL (0.78 vs 0.83) |
| Bottom-risk | NOT | NOT | NOT |
| **Score (C-gbm)** | **5.5 / 7 → 8/10** | **3.5 / 7 → 5/10** | **3.5 / 7 → 5/10** |
| Score (O2, for the record) | 6/10 | 4/10 | 5/10 |

- **Exact feet: 8/10.**
  - Normal, stained, limited, algae and sediment are SUPPORTED.
  - Clear is PARTIAL at −1.7 ft (section 5). Feet are shown for 87% of rows.
- **Original hard class: 5/10, kept for comparison and not declared passed.**
  - Clear and algae are SUPPORTED.
  - Normal, limited and sediment are PARTIAL.
  - Stained is NOT (recall 0.26).
- **Boundary-aware product: 5/10.**
  - Clear is SUPPORTED.
  - The other five non-depth capabilities are PARTIAL. Stained decision recall rises to 0.64, but no class except clear
    reaches the 0.75 / 0.75 SUPPORTED bar.
  - The two scores land on the same number for different reasons: the product raises stained from NOT to PARTIAL, and
    its higher bar takes algae from SUPPORTED to PARTIAL.
- **One state is weak:** a plain "Stained" answer (2.38–2.63 ft) is right only 27% of the time on development rows
  (n 33). The two boundary states that cover stained water are right 79% and 83% of the time.

## 5. Clear water: where the bias comes from (development, diagnostic only)

| True Secchi (clear rows, tiers 1–2) | n | Median signed (ft) | Median signed (log) | Share of the total negative error |
|---|---:|---:|---:|---:|
| 6–8 ft | 141 | +0.04 | +0.003 | 7% |
| 8–10 ft | 109 | -0.29 | -0.013 | 7% |
| 10–13 ft | 159 | -1.82 | -0.080 | 17% |
| 13–20 ft | 137 | -3.03 | -0.086 | 22% |
| ≥ 20 ft | 88 | -10.72 | -0.219 | 48% |
| **All clear** | 634 | **-1.75** | -0.081 | 100% |

**The clear-water bias is a tail problem, concentrated in very deep water. It is neither a constant bias nor a
proportional one.**
- **Typical clear water is unbiased.** 6–8 ft reads +0.04 ft and 8–10 ft reads −0.3 ft.
- **The error grows only above 10 ft:** −1.8 ft at 10–13 ft, −3.0 ft at 13–20 ft and −10.7 ft at 20 ft or more. The
  ≥ 20 ft rows are 14% of clear water but carry 48% of the negative error.
- **Two of the four tests hold:** tail problem and concentrated in deep water. The bin medians span 10.8 ft and 0.22
  log, so the bias is neither constant nor proportional.
- **The cause is regression to the mean plus saturation, not a miscalibrated engine.**
  - Conditioned on its prediction, the engine is calibrated: when it predicts 6 ft or more, the median truth is only
    +0.2 ft away.
  - Conditioned on the truth, its error falls by 0.37 log per log of true Secchi.
  - Two reasons for that. Any estimator of E[y | p] shrinks extremes. And above about 15–20 ft the water-leaving signal
    approaches that of pure water, so the reflectance carries little information about how much clearer it is.
- **Product consequence, diagnostic only.** "Clear" is right 86% of the time, but an exact figure above about 12 ft is a
  floor rather than an estimate. Nothing was corrected.

## 6. Tier 3: what the Sen2Cor fallback may say

| State Sen2Cor-C3 would issue (development tier-3 rows, nested bands) | n | Decision precision | Allowed (≥ 0.75, n ≥ 15) |
|---|---:|---:|---|
| Clear | 75 | 0.89 | **yes** |
| Normal | 46 | 0.22 | no |
| Normal-to-Stained | 46 | 0.43 | no |
| Stained | 0 | 0.00 | no |
| Stained-to-Limited | 16 | 0.50 | no |
| Limited | 2 | 0.50 | no |

- **Only one state passes the precision bar.** "Clear", from the Sen2Cor C3 fallback, is right 89% of the time
  (n 75).
- **Every murky answer fails it.** Normal is 0.22, Normal-to-Stained 0.43 and Stained-to-Limited 0.50.
- **Its clear feet pass the PARTIAL bars:** ×1.54 and −1.5 ft.
- **The frozen behaviour:**
  - when Sen2Cor-C3 reads 6 ft or more: "Clear", lower authority, with lower-confidence feet;
  - otherwise: **Unknown / Low Authority**.
- **The cost is honest.** It gives up the 59% of tier-3 rows where the fallback is usually wrong in murky water.
  Coverage does not override the precision bar.

## 7. The sealed WQP tier

**What the sealed tier is.** The Stage 1 national WQP Secchi pull: 397,798 records at 20,860 sites, 2018–2026,
fetched 2026-09-27.

**Why most of it was not usable.**
- Development stages had drawn from it: about 11,800 of its sites appear in a Stage 1–13 sample, draw or readout file.
- So the protocol, frozen before any of its values were read:
  1. drops every site in a Stage 5–13 file, every lake within 5 km of a Stage 5–13 development station, and every
     Stage 1–4 record;
  2. drops any site with a 2026 record, so the P2 fresh pool is untouched;
  3. drops Guntersville, and anything within 5 km of the Stage 12/13 blind set.
- **The 5 km rule.** It follows the Stage 12 NLA precedent and applies to the corpora that fitted or selected the frozen
  engine (Stages 5–13). Stage 1–4 analysed only the production champion, so its records are excluded one by one.
- **The strict alternative**, which also drops every lake touched in Stage 1–4, would have left 1,901 sites, 87% of them
  in Minnesota. Rows that would survive that rule too are reported separately as the strict-independence subset.

| Step (value-blind) | Count |
|---|---:|
| WQP sites in the Stage 1 pull | 20,860 |
| Eligible after the section 3 rules | 5,427 sites, 77,324 site-days, 2,350 lakes, 47 states |
| … October–April | 15,935 site-days |
| … on a lake with no Stage 1–4 site within 5 km (strict subset) | 2,279 sites |
| Seeded draw | 7,000 site-days |
| Clear pass within ±1 day (prescreen) | 3,088 (639 cool-season) |
| Matched (≥ 5 valid pixels) | 830 |
| ≤ 3 per lake | 822 |
| **Final WQP sample** (≤ 15% per state, ≤ 900) | **671** |

**Blind checks on the whole certification set, before unsealing:**

| Blind check (before unsealing) | Value | Bar | |
|---|---:|---:|---|
| Observations | 1585 (NLA 165, WQP 671, SYKE 749) | ≥ 400 | pass |
| Lakes | 1344 | ≥ 100 | pass |
| US states | 46 | ≥ 20 | pass |
| Largest state share, US core | 15.0% | ≤ 15% | pass |
| October–April | 21.7% (305 lakes; US core 19.9%) | ≥ 15% across ≥ 20 lakes | pass |
| Expected clear, US core | 392 | ≥ 40 | pass |
| Expected normal, US core | 206 | ≥ 40 | pass |
| Expected stained, US core | 121 | ≥ 60 | pass |
| Expected algae, US core | 182 | ≥ 30 | pass |
| Expected sediment, US core | 65 | ≥ 20 | pass |
| Expected limited, US core | 117 | ≥ 25 | pass |

## 8. Certification: the frozen engine, scored once (US core: NLA + WQP)

| True class (US core) | n | Original hard R / P | **Decision R / P** | Answered at ACOLITE authority | Exact feet: error, median signed |
|---|---:|---|---|---:|---|
| Clear | 393 | 0.67 / 0.87 | **0.81 / 0.87** | 83% | ×1.39, -2.3 ft (n 372) |
| Normal | 177 | 0.50 / 0.46 | **0.66 / 0.56** | 86% | ×1.32, +0.0 ft (n 162) |
| Stained | 99 | 0.33 / 0.34 | **0.69 / 0.74** | 89% | ×1.28, +0.4 ft (n 90) |
| Limited | 156 | 0.57 / 0.78 | **0.73 / 0.88** | 92% | ×1.48, +0.6 ft (n 144) |
| **All** | 825 | balanced 0.520 | **decision-balanced 0.726** | specificity 0.76 | ×1.36; interval coverage 65% |

- **How the columns are counted.**
  - Original hard recall counts every row, with Unknown and tier-3 answers as misses.
  - Decision recall and precision count rows answered at ACOLITE authority. The share answered sits beside them.
- **Clear holds up.** Decision recall is 0.81 and precision 0.87; "Clear" answers are right 87% of the time, as in
  development.
- **Stained is the class the boundary states were built for.** 89% of stained water is answered, and 69% of those
  answers include stained. Only 43% of them are a single class, because the retrieval cannot resolve 2–3 ft.
- **Limited is right 88% of the time when named,** but its recall (0.73) is just under the 0.75 bar.
- **Normal is the weak class.** Its decision precision is 0.56. Of 127 plain "Normal" answers, 52 were actually clear
  and 23 stained or limited.
- **Feet are good where the water is not very clear:** ×1.28–1.48, with median signed −0.0 to +0.6 ft for normal,
  stained and limited. Clear reads −2.3 ft.

**How often each issued state was right:**

| Issued state | Certification n | Certification precision | Development precision |
|---|---:|---:|---:|
| Clear | 304 | 0.87 | 0.86 |
| Normal | 127 | 0.41 | 0.53 |
| Normal-to-Stained | 100 | 0.74 | 0.79 |
| Stained | 31 | 0.35 | 0.27 |
| Stained-to-Limited | 73 | 0.90 | 0.83 |
| Limited | 74 | 0.86 | 0.78 |

**The three rubrics side by side:**

| Capability (certification, US core) | Exact feet | Original hard class | Boundary-aware product |
|---|---|---|---|
| Clear | PARTIAL (×1.39, -2.3 ft) | SUPPORTED (0.79 / 0.86) | SUPPORTED (0.81 / 0.87) |
| Normal | SUPPORTED (×1.32, +0.0 ft) | PARTIAL (0.50 / 0.46) | NOT (0.66 / 0.56) |
| Stained | SUPPORTED (×1.29, +0.4 ft) | NOT (0.33 / 0.34) | PARTIAL (0.69 / 0.74) |
| Limited | SUPPORTED (×1.48, +0.6 ft) | PARTIAL (0.57 / 0.78) | PARTIAL (0.73 / 0.88) |
| Algae | PARTIAL (×1.44, +0.5 ft) | NOT (n 124) | NOT (n 106; 0.72 vs 0.74) |
| Sediment | SUPPORTED (×1.36, +0.3 ft) | PARTIAL (n 38) | PARTIAL (n 33; 0.85 vs 0.88) |
| Bottom-risk | NOT | NOT | NOT |
| **Score** | **7/10** | **4/10** | **4/10** |

**The readiness lines:**

| Readiness line | Rubric | n (minimum) | Verdict |
|---|---|---:|---|
| CLEAR FEET READY | Exact feet, clear | 393 (40) | **PARTIAL** |
| NORMAL READY | Product, normal | 177 (40) | **NO** |
| STAINED READY | Product, stained | 99 (60) | **PARTIAL** |
| LIMITED READY | Product, limited | 156 (25) | **PARTIAL** |
| ALGAL READY | Product, algae | 124 (30) | **NO** |
| SEDIMENT READY | Product, sediment | 38 (20) | **PARTIAL** |
| **BLIND CERTIFICATION PASSED** | YES = all six YES; PARTIAL = ≥ 3 points | | **NO** (2.0 of 6) |

**BLIND CERTIFICATION PASSED: NO.** Every class met its minimum, so every verdict is a real one, not INSUFFICIENT:

| Class | n | Minimum |
|---|---:|---:|
| Clear | 393 | 40 |
| Normal | 177 | 40 |
| Stained | 99 | 60 |
| Algal | 124 | 30 |
| Sediment | 38 | 20 |
| Limited | 156 | 25 |

**The six lines:**
- **CLEAR FEET: PARTIAL.** The median is −2.3 ft against the ±1.5 ft SUPPORTED bar. On certification the tail is the
  same shape as in development:
  - 6–13 ft reads about −1 ft;
  - 13–20 ft reads −3.9 ft;
  - ≥ 20 ft reads −9.3 ft.
- **NORMAL: NO.** Decision recall 0.66, precision 0.56 (the PARTIAL bar is 0.60).
- **STAINED: PARTIAL.** 0.69 / 0.74. Recall is short of the 0.75 SUPPORTED bar.
- **LIMITED: PARTIAL.** 0.73 / 0.88.
- **ALGAL: NO.** In algal water, decision accuracy is 0.72. Always answering one fixed state would score 0.74, because
  algal water here is mostly stained or limited.
- **SEDIMENT: PARTIAL.** No bright sediment (turbidity ≥ 20, n 18) was called Clear, but accuracy is 0.85 against a
  constant 0.88.

**Tier 3 on certification.** 116 US rows reached tier 3:
- "Clear" was issued 59 times and was right 78% of the time (0.89 in development), still above the 0.75 bar. Its feet:
  ×1.52, +1.3 ft.
- The other 57 rows became Unknown / Low Authority.
- The tier-3 rows were 58% clear water, so the precision-first rule cost little.

**Coverage.**
- 73% tier 1, 13% tier 2, 14% tier 3.
- 24 of 1,574 scored rows had no ACOLITE result (no L1C, or ACOLITE produced no L2W); they fell to tier 3 as designed.
- Feet were published for 93% of US rows.

## 9. Where it holds and where it breaks

| Split (US core) | Group | n | Decision-balanced | Decision recall: clear · normal · stained · limited | Original balanced | Feet error | Interval coverage |
|---|---|---:|---:|---|---:|---:|---:|
| source | NLA | 155 | 0.768 | 0.87 · 0.70 · 0.75 · 0.75 | 0.480 | ×1.42 | 61% |
| source | WQP | 670 | 0.718 | 0.80 · 0.66 · 0.69 · 0.73 | 0.528 | ×1.36 | 66% |
| tier | 1 | 599 | 0.744 | 0.81 · 0.64 · 0.71 · 0.81 | 0.619 | ×1.35 | 67% |
| tier | 2 | 110 | 0.660 | 0.82 · 0.76 · 0.61 · 0.45 | 0.529 | ×1.46 | 57% |
| tier | 3 | 116 | lower authority: Clear-or-Unknown (section 8) | – | – | ×1.52 | – |
| platform | sentinel-2a | 363 | 0.721 | 0.82 · 0.70 · 0.71 · 0.65 | 0.535 | ×1.35 | 66% |
| platform | sentinel-2b | 429 | 0.736 | 0.84 · 0.65 · 0.67 · 0.78 | 0.526 | ×1.36 | 67% |
| platform | sentinel-2c | 33 | 0.533 | 0.30 · 0.50 · – · 0.80 | 0.246 | ×1.62 | 30% |
| season | cool | 166 | 0.731 | 0.55 · 0.73 · 0.80 · 0.84 | 0.539 | ×1.38 | 68% |
| season | warm | 659 | 0.709 | 0.86 · 0.64 · 0.65 · 0.69 | 0.504 | ×1.36 | 65% |
| region | 0 | 81 | 0.545 | 0.91 · 0.67 · 0.60 · 0.00 | 0.387 | ×1.43 | 66% |
| region | 1 | 123 | 0.696 | 0.76 · 0.70 · 0.65 · 0.68 | 0.452 | ×1.33 | 73% |
| region | 2 | 333 | 0.692 | 0.84 · 0.64 · 0.70 · 0.59 | 0.502 | ×1.35 | 64% |
| region | 3 | 134 | 0.691 | 0.40 · 0.72 · 0.79 · 0.85 | 0.468 | ×1.39 | 64% |
| region | 4 | 154 | 0.671 | 0.83 · 0.62 · 0.40 · 0.83 | 0.595 | ×1.41 | 63% |
| strict_subset | strict WQP + NLA | 447 | 0.711 | 0.83 · 0.71 · 0.66 · 0.65 | 0.492 | ×1.40 | 64% |
| strict_subset | non-strict WQP | 378 | 0.732 | 0.79 · 0.62 · 0.72 · 0.81 | 0.540 | ×1.35 | 67% |

**What holds:**
- **NLA and WQP agree:** decision-balanced 0.77 and 0.72.
- **Independence does not change the result.** The strict-independence subset (lakes with no Stage 1–4 site within
  5 km) scores 0.71 against 0.73 for the rest.
- **The two-thirds interval** covers 61–73% of truths in every region.
- **Sentinel-2A and 2B agree:** 0.72 and 0.74.

**What breaks:**
- **Sentinel-2C.** 33 rows, only 23 of them at ACOLITE authority, all from 2025. They read 0.19 log low (×0.65); clear
  water reads 0.23 log low, and interval coverage is 30%.
  - Stage 13 found the class invariant on the 12 tandem pairs. That held on identical water, but not on these independent
    S2C scenes.
  - The sample is small and partly cool-season, so this is a warning rather than a measurement. It is a new failure.
- **Cool-season clear water.** It reads 0.15 log low, and only 55% of it is called Clear (warm season: 86%).
- **Tier-2 limited water.** The relaxed mask recovers rows, but limited decision recall there is 0.45.

**Out of domain (reported apart):**

| SYKE (Finland, out of domain) | Value |
|---|---|
| Observations | 749 at 658 lakes; tiers {'1': 608, '3': 104, '2': 37} |
| Classes | {'normal': 270, 'clear': 308, 'stained': 87, 'limited': 84} |
| Decision-balanced / specificity | 0.589 / 0.70 |
| Decision R / P by class | clear 0.49 / 0.65; normal 0.65 / 0.51; stained 0.65 / 0.59; limited 0.57 / 0.70 |
| Original balanced | 0.410 |
| Feet error | ×1.50; by class clear 1.56× -2.7 ft; normal 1.44× -0.2 ft; stained 1.38× +0.5 ft; limited 1.54× +0.8 ft |
| Rubric scores | exact feet 4/10, hard class 2/10, product 1/10 |

**SYKE is out of domain and stays out:** humic Finnish lakes score decision-balanced 0.59 and product 1/10. Clear water
reads −2.7 ft there. That fits the cool-season and dissolved-colour findings. It does not count toward any verdict.

## 10. Readiness

**CURRENT CLARITY PRODUCT READINESS: 2/10 as deployed.**
- **Why it doesn't move.** The Stage 10 rule scores the product as it runs, and production was not changed.
- **The candidate, as if deployed: 4/10.** It is scored on the blind certification with the boundary-aware product
  rubric:
  - clear SUPPORTED;
  - stained, limited and sediment PARTIAL;
  - normal, algae and bottom-risk NOT.
- **Against production.** Production was not run on the certification set, so there is no head-to-head certified
  comparison. The nearest comparison: Stage 12 measured production on development data at ×1.97 and −5.2 ft in clear
  water, against the candidate's certified ×1.39 and −2.3 ft.
- **What it would take.** Shipping it is a product decision, and readiness moves only with deployment.

## 11. Remaining work before Water Temperature

1. **Michael's ship decision.** The candidate (4/10 certified) against production (2/10). Ship it shadowed in the
   engine first; production stays unchanged until then.
2. **Clear water read low.** It drives both CLEAR FEET PARTIAL and NORMAL NO: 52 of 127 "Normal" answers were clear
   water. This needs a product rule, not a new model. Examples:
   - a "Clear-to-Normal" boundary state, which the specification does not have yet;
   - showing exact feet above about 12 ft as a floor ("12+ ft").
3. **Sentinel-2C on independent water.** S2C reads 0.19 log low (n 23). It needs more S2C tandem pairs and S2C
   certification rows before S2C answers can be trusted. Until then they could be marked lower authority. This is a new
   failure, so it is a legitimate reason to reopen harmonisation.
4. **Cool-season clear water** (−0.15 log), and **algal water**, where the engine is no better than a constant answer:
   the algae state or warning needs its own semantics.
5. **Fresh evidence:** Michael's Guntersville survey as the acceptance test, and P2. Under the Stage 10 rule, only these
   move readiness past the certified level.
6. **Bottom-risk** needs a depth layer.

## Files

Everything is in `scratchpad/stage14/`:

| Path | Contents |
|---|---|
| `PREREGISTRATION_STAGE14.md`, `FREEZE_STAGE14.json` | The frozen plan and every hash, in order |
| `cert/CERT_PROTOCOL_STAGE14.md`, `cert/ADDENDUM_A1_io.md` | The sealed-tier protocol and its one I/O addendum |
| `cert/` | Value-blind index, development footprint, pool, draw, prescreen, matches, `wqp_sample.csv`, blind checks, ACOLITE runs (`res_ns/`, `res_wqp/`) |
| `engine/` | `engine14.py`, `frozen_engine.json`, `frozen_gbm.pkl`: the frozen candidate |
| `analysis/` | `lib14.py`, `dev14.py` (sections 3–6 on development rows), `cert14.py` (the one-shot score), JSON results |
| `unseal/` | `unseal14.py`, `truth14.json`, and the agency files fetched at unsealing |

---

FROZEN PRODUCTION CANDIDATE: C-gbm single continuous engine (the Stage 13 seven-feature constrained boosting, fitted once on 1,206 development rows) on ACOLITE K4 with lake-elevation pressure, S2C V-ρw and the 60 m disk. Tier 2 is the M3 relaxed mask. Tier 3 is Sen2Cor-C3, Clear only. Boundary states come from frozen 2:1-odds bands: Normal-to-Stained 2.63–3.80 ft, Stained-to-Limited 1.70–2.38 ft. Exact feet are shown for every class with a two-thirds interval (−37% / +51%).

EXACT-FEET HISTORICAL CAPABILITY: 8/10 (development, lake-held-out); 7/10 on blind certification

ORIGINAL HARD-CLASS HISTORICAL CAPABILITY: 5/10 (development); 4/10 on blind certification (kept for comparison, not declared passed)

BOUNDARY-AWARE PRODUCT CAPABILITY: 5/10 historical (clear SUPPORTED; normal, stained, limited, algae and sediment PARTIAL); 4/10 on blind certification

BLIND CERTIFICATION SAMPLE SIZE: 825 scored US-core observations at 675 lakes in 46 states (NLA 155, sealed WQP tier 670; 19.9% October–April), plus 749 SYKE (Finland) reported apart. 1,574 of 1,585 drawn observations were scored

BLIND CERTIFICATION PASSED: NO (2.0 of 6 points: clear feet, stained, limited and sediment PARTIAL; normal and algae NO)

CLEAR FEET READY: PARTIAL (×1.39, median −2.3 ft; about −1 ft at 6–13 ft, −3.9 ft at 13–20 ft, −9.3 ft at 20 ft or more)

NORMAL READY: NO (decision recall 0.66, precision 0.56; a plain "Normal" answer is right 41% of the time, mostly because clear water is read low)

STAINED READY: PARTIAL (decision recall 0.69, precision 0.74, against 0.33 hard recall)

LIMITED READY: PARTIAL (decision recall 0.73, precision 0.88)

ALGAL READY: NO (decision accuracy 0.72 in algal water, against 0.74 for the best constant answer)

SEDIMENT READY: PARTIAL (no bright sediment called Clear; decision accuracy 0.85 against a constant 0.88)

TIER-3 PRODUCT BEHAVIOR: Clear only, at lower authority with lower-confidence feet, when Sen2Cor-C3 reads ≥ 6 ft (precision 0.89 in development, 0.78 on certification, n 59). Every other tier-3 reading is Unknown / Low Authority

CURRENT CLARITY PRODUCT READINESS: 2/10 as deployed (production unchanged); the certified candidate would score 4/10 if deployed

REMAINING WORK BEFORE WATER TEMPERATURE: (1) Michael's decision whether to ship the certified candidate, shadowed first; (2) a product rule for clear water read low in deep and cool-season water, which drives both CLEAR FEET PARTIAL and NORMAL NO; (3) Sentinel-2C on independent water reads 0.19 log low (n 23), which needs more S2C tandem and certification data; (4) algal-water semantics, since the engine is no better than a constant answer there; (5) fresh evidence: the Guntersville survey acceptance test and P2; (6) bottom-risk needs depth
