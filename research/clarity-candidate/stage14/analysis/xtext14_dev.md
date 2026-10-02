@@ addenda
**Four addenda.** Each was recorded and hashed before any certification value was read:

| Addendum | What it changed | Why it cannot bias the score |
|---|---|---|
| **A1** (I/O only) | The ACOLITE fetch skips the TCI preview image, about 19% of each download; ACOLITE never reads it | The six development validation scenes reproduce all 264 sampled values exactly |
| **A2** (draw) | Every event not yet extracted is prescreened at ≤ 20% scene cloud. The first draw matched only 11% of events: 31–32% at ≤ 20% cloud, 1–5% above. A second draw continues the frozen seeded order; it used up the eligible pool under the lake caps at 2,655 site-days | Cloud and draw order are independent of Secchi |
| **A3** (state cap) | The 15% state cap is applied over the combined US core, as the protocol's check requires. Minnesota was 15.7% once NLA was added; 7 Minnesota WQP rows were removed, last-selected first | Reads only states and the seeded order |
| **A4** (environment) | At 00:00 the operating system's temp-file cleanup deleted package files of the `geo` Python environment. Every later ACOLITE run failed explicitly. The environment was rebuilt at identical versions, and the 975 affected items were re-run unchanged | A refit reproduces the frozen engine exactly (max difference 0); the six validation scenes reproduce exactly |

**The pipeline itself** had been checked before any certification scene was run. On the six development scenes it
reproduces Stage 12's default-mask samples and Stage 13's M3 samples exactly.

@@ frozen_text
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

@@ states_text
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

@@ compare_text
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

@@ hist_text
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

@@ clear_text
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

@@ tier3_text
- **Only one state passes the precision bar.** "Clear", from the Sen2Cor C3 fallback, is right 89% of the time
  (n 75).
- **Every murky answer fails it.** Normal is 0.22, Normal-to-Stained 0.43 and Stained-to-Limited 0.50.
- **Its clear feet pass the PARTIAL bars:** ×1.54 and −1.5 ft.
- **The frozen behaviour:**
  - when Sen2Cor-C3 reads 6 ft or more: "Clear", lower authority, with lower-confidence feet;
  - otherwise: **Unknown / Low Authority**.
- **The cost is honest.** It gives up the 59% of tier-3 rows where the fallback is usually wrong in murky water.
  Coverage does not override the precision bar.

@@ wqp_text
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
