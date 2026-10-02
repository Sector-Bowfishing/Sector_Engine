# Stage 10 pre-registration: P2 (physics-routed hybrid) and the SWIR-residual experiment

This was written 2026-09-29 before any fresh validation data existed. Its hash, and the hashes of every
frozen file, are in `frozen_manifest.json`. `FREEZE.json` records the freeze time. Nothing listed in the
manifest may change after the freeze. A later change is a deviation and must be reported as one.

## 0. What the designer had already seen (disclosed so the reader can judge)

**Seen before this was written:**
- **Stage 9 results.**
  - P1 by class: stained +0.11, clear channel −4.43, and the rest.
  - Row-level input medians by class:
    - clear channel: ρ(B05) 0.016, ρ(B11) 0.009;
    - stained arms: ρ(B05) 0.020, ρ(B11) 0.005;
    - normal: ρ(B05) 0.022, ρ(B11) 0.008.
  - The flat offset that would make P1 match the disk: channel 0.011, arms −0.002.
- **A pipeline dry run of `frozen/fresh_eval.py` on historical Guntersville rows.** It was run after
  `frozen/p2.py` was written, to test that the code runs. Its console line included the rounded historical
  readiness each system would score (champion 2, P2 3, C3 3, C6 2, P1 1). No frozen file was changed after it.

**Not seen: any fresh validation data.**
- No Sector field report from any phone, and none from the dev database (the dev `clarityReports` path
  was empty in Stage 9).
- No 2026 agency Secchi value. Stage 8's `g2026_secchi.csv` was fetched and its organisation and date
  columns printed; its 7 values were never read. Those 7 records are excluded from the fresh set anyway.
- No fresh national draw.
- The only field report that exists is a synthetic simulator test entry, on land, in the dev store.

## 1. Frozen benchmarks (no retuning)

| Model | Frozen as | File |
|---|---|---|
| Champion | 11.123·FNU^−0.637 ft on the production-gated Dogliotti turbidity | `frozen/models.py` |
| C3 | Stage 7 two-branch red-band form, fitted once on all 715 historical clean rows (643 national + 72 Guntersville) | `frozen/c3_frozen.json` |
| C6 | Stage 8 `c6_model.json`, unchanged (Guntersville offsets used on Guntersville rows) | `frozen/c6_model.json` |
| P1 | Stage 9 model block, byte-identical: constants, guards and order | `frozen/p1.py` (block sha256 `ed0dcfe9…`; Stage 9 pre-registration `4cc30221…`) |

- **Changes: none.** No physical constant, guard or threshold was changed, and no empirical constant was added to P1.
- **Metrics:** verbatim copies of Stage 7's `evaluate()` and Stage 8's `gates()` (`frozen/metrics.py`).

## 2. The image residual at 704 nm, estimated from the scene alone

**What the residual is.** Sen2Cor L2A bottom-of-atmosphere reflectance over water still contains light that did not
come out of the water. Its sources behave differently across wavelengths:

| Source | At 704 nm compared with B11 (1610 nm) |
|---|---|
| Sun glint (Fresnel reflection of the sun) | spectrally flat: equal |
| Sky glint (Fresnel reflection of the sky) | larger at 704 (sky radiance relative to irradiance falls with wavelength) |
| Adjacency (light from the banks scattered into water pixels) | land is brighter at 1610, but scattering is roughly 3× stronger at 704 (aerosol optical depth scales about λ^−1.3). Net: comparable or larger at 704 |
| Aerosol-correction error | larger at 704 |
| Instrument noise | B05 about 0.001–0.002 per 20 m pixel, reduced by the median over the valid pixels |

**Water-leaving reflectance at 1610 nm is essentially zero** for any water in this study. So **ρ(B11)
over water is the scene's own, pixel-local, truth-free measurement of the residual.** At 704 it is
approximately equal to the residual for sun glint, and a lower bound for sky glint, adjacency and aerosol error.

**Candidates considered:**
- **(a) Pixel ρ(B11), applied flat to all four bands. CHOSEN.**
  - It is available for every historical row and every future cell.
  - It is measured at the same pixels.
  - It involves no Secchi value.
- **(b) A scene-level open-water B11 floor**, the lake's open water more than 300 m from shore. It would separate glint
  from adjacency, but it cannot be computed for the historical rows and needs its own validation. **Deferred.**
- **(c) B12 against B11 flatness.** A diagnostic of the residual's spectral shape, not a rule. **Not used.**
- **(d) A detection ratio ρ(B05)/ρ(B11) ≥ 3.** **Rejected**, for two reasons:
  - it is a detection criterion (is the signal present?), not a quantification criterion (is the number right?);
  - the designer knows from Stage 9 that the stained arms (ratio ≈ 4) and the channel (≈ 1.8) fall on
    opposite sides of 3. Choosing it would be choosing with knowledge of where P1 happens to be right.
- **(e) P1's own B05 noise floor of 0.003.** **Retained unchanged**, as P1's R2 guard.

## 3. P2: the exact rule (implemented verbatim in `frozen/p2.py`)

**Inputs** per observation or cell:
- the raw valid-pixel medians of B02, B03, B04, B05 and B11;
- the sun elevation.

No Secchi value, label or outcome enters any step.

**Residual sensitivity:** S = |Z_P1(ρ − r) / Z_P1(ρ) − 1|, with r = max(ρ(B11), 0) subtracted from all four bands.
- Z_P1 is P1 with all of its guards.
- If P1 refuses after r is removed, S = ∞.

**Tolerance: S_MAX = 0.20.** It is set by the product, not fitted. 0.20 is the half-width of the 2–3 ft stained class
relative to its centre (0.5 / 2.5). If removing the scene's own residual estimate would move P1's answer by more than
a class half-width, P1's number is not a measurement of the water.

**Valid range.** S is defined when P1 answers and B11 is present. B11 ≤ 0.0215 already holds for every valid pixel
(the production gate).

**Decision tree:**

| Step | Condition | Result |
|---|---|---|
| A | P1 answers (R1–R8 pass) and S ≤ 0.20 | **P1**, authority capped at Moderate, provenance "physical (P1)" |
| B1 | P1 answers but S > 0.20, S = ∞, or B11 missing | residual-limited → go to C |
| B2 | P1 refuses at R2 only because ρ(B05) < 0.003, with B02–B04 in [0.001, 0.15] | "704 below the noise floor" → go to C |
| B3 | P1 refuses at R7 (inconsistent inversion, typically glint) | → go to C |
| — | P1 refuses at R1, R2 otherwise, R3, R4, R5 (NDCI > 0.20), R6 (scum/vegetation) or R8 | **REFUSE** (P1's reason kept) |
| C | the frozen C3 is inside its validated domain, and its output is in [0.5, 20] ft | **C3**, authority capped at Low, provenance "empirical (C3)", reason kept |
| — | otherwise | **REFUSE** ("C3 outside its validated domain") |

**C3's validated domain** (`c3_frozen.json`) is the 1st–99th percentile of its training *inputs*:
- log10 R(B04) in [−2.775, −1.107] when NDCI ≤ 0, and [−2.359, −0.996] when NDCI > 0;
- NDCI in [−0.461, +0.361].

**Rules that apply to every path:**
- Nothing is clamped.
- The NDCI algal warning (Stage 8, unchanged) is layered on top by the product and caps any path at Low.
- Vegetation-contaminated and bottom-risk observations are labels for evaluation, never routing inputs.
- The production pixel gates remove vegetation, scum, cloud and haze before any of this.

## 4. Predictions and expected failure modes (written before any P2 historical number was computed)

**Predictions:**
- **Stained, algal arms: routed to C3.** ρ(B05)/ρ(B11) ≈ 4, so removing r lowers bbp(704) by about 23% and raises Z
  by about 30%, giving S ≈ 0.3. **The designer therefore predicts that P2 will not preserve P1's stained-water
  result on the historical corpus; P2 will be near C3 there, about +1.5 ft.**
- **Clear channel: routed to C3** (S ≈ 1). P2 will be near C3 there, about −1.9 ft.
- **Bright sediment: stays on P1.** ρ(B05) is large against the residual.
- **Very clear water: C3.** ρ(B05) < 0.003.
- **Dense bloom or scum: refused.**

**Physical interpretation stated in advance.** P1's unbiased stained-arm result may be two opposing biases cancelling:
- the residual makes P1 read too murky;
- chlorophyll absorption at 704 (a_ph(704) of about 0.1–0.25 m⁻¹ at 20–50 µg/L) makes it read too clear.

If so, it will not generalise to arms with a different chlorophyll-to-residual balance. The fresh data tests this
(two diagnostics, §9).

**Expected failure modes:**
1. **Adjacency-dominated arms.** If B11 overstates the 704 residual there, P1 is routed away where it was right.
2. **Sky glint or aerosol error larger at 704 than at B11.** The residual is understated, so P1 is kept where it is
   still biased murky.
3. **The C3 path inherits C3's weaknesses:** it reads stained water too clear (+1.7 ft historically), and bright
   sediment is misread wherever it becomes residual-limited.
4. **Refusals concentrate in dense algae.** Coverage of water under 2 ft will be low.

## 5. The SWIR-residual experiment (P1S): separate from P2

**Definition.** P1S = P1 on (ρ − r), with r = max(ρ(B11), 0) subtracted from all four bands and every P1 guard applied.
- r is measured per observation; nothing is fitted.
- There is no scale factor.
- It is not part of P2 unless it passes on its own.

**Criteria** (development check, and later the fresh verdict):

| # | Criterion |
|---|---|
| (i) | Clear-channel median signed ≥ −1.5 ft (gate 5), **and** at least 1.5 ft closer to zero than P1 on the same rows |
| (ii) | Stained 2–3 ft \|median signed\| ≤ 1.0 ft, **and** no more than 0.5 ft worse than P1 on the same rows |
| (iii) | Dark algal water \|median signed\| ≤ 1.0 ft |
| (iv) | Arms and channel reported separately; coverage ≥ 80% of clean rows and of stained rows |
| (v) | The nine gates |

A historical pass only nominates P1S for the fresh test. Only a fresh pass, under its own verdict, could make it a
candidate for a later, separately pre-registered P2 revision.

**Prediction:** (i) improves the channel to about −1 to −2 ft, and (ii) fails, with arms reading about 0.5–1.5 ft too clear.

## 6. Development-only historical check (NOT certification)

**Sets:** G (72 clean Guntersville rows; bottom-risk and vegetation reported apart), N (Stage 7 national) and F (Stage 8 fresh national).

**Comparators:** their held-out predictions, as published.
- **G:** C3 and C6 leave-one-year-out and leave-one-station-out. P2's C3 path uses C3's held-out prediction; the
  routing decision itself is unchanged.
- **N:** lake-grouped cross-validation.
- **F:** national fits.

**PROMISING** if and only if all of these hold on the G rows P2 answers (paired):
1. stained 2–3 ft median signed ≤ +1.0 **and** within 0.5 ft of P1's on the same rows;
2. dark algal water \|median signed\| ≤ 1.0;
3. clear-channel median signed ≥ C3's − 0.5 ft on the same rows;
4. normal 3–6 ft \|median signed\| ≤ 1.0;
5. P2 answers ≥ 80% of clean rows and ≥ 80% of stained rows.

Otherwise **NOT PROMISING**.

**Neither outcome counts toward readiness.** P2 is not retuned after seeing it.

## 7. Fresh held-out validation (the only source of a P2 verdict)

**What counts as fresh:**
1. Sector field reports with `observedAt` ≥ the freeze time.
2. Agency Secchi (WQP "Depth, Secchi disk depth") on Guntersville dated 2026-01-01 or later, never fetched before the
   freeze, excluding the 7 Stage 8 records. That includes ADEM's and TVA's 2026 warm season when it is published.
3. A fresh national draw for gate 9, following the Stage 8 draw protocol with:
   - seed 20261001;
   - WQP Secchi dated 2026-04-01 or later;
   - sites in no earlier file.

**Procedure, frozen:**
1. `frozen/build_observations.py` (exports and agency CSVs → observations).
2. `stage6/extract.py --max-dt 1`, unchanged: the production gates and the 60 m disk. It takes the best pass per
   observation (smallest |Δt|, then most valid pixels), requires ≥ 5 valid pixels, and dedupes to one row per
   site-cell, scene-day and tier.
3. `frozen/fresh_eval.py`.

**Truth tiers:**

| Tier | Source | Use |
|---|---|---|
| `agencySecchi` | agency | Secchi-grade |
| `secchiDisk` | field: daylight, exact feet, "Measured with a Secchi disk" = Yes | Secchi-grade |
| `visualDay` | field: daylight, exact feet, no disk | scored separately; never pooled with Secchi-grade |
| `bandDay` | field: daylight, band only | scored separately |
| `night` | field: under lights | scored separately; never pooled with Secchi-grade |

**Labels:**
- **Arm, main stem, arm name:** the engine's arm grid.
- **Algal:** NDCI > 0.03 at the pixels, or chlorophyll ≥ 15 µg/L.
- **Sediment-driven:** NDCI ≤ 0, and (turbidity ≥ 8 NTU or a muddy/brown colour note).
- **Warm season:** May–September.
- **Vegetation:** ≥ 20% of water pixels dropped by NDVI/FAI, or "vegetation here" = Yes. Excluded from the headline.
- **Bottom-risk:** "bottom visible" = Yes, or the disk depth ≥ half the water depth. Excluded from the headline.

**One-shot rule.** The evaluation is run once per declared data batch. Its results can never change P2. A successor
(P3) must be pre-registered and tested only on data collected after its own freeze.

## 8. Minimum coverage before any class is judged (clean, Secchi-grade)

| Class | Observations | Scene-days | Arms |
|---|---:|---:|---:|
| Clear channel (main stem, ≥ 6 ft) | 20 | 5 | — |
| Normal 3–6 ft | 25 | 5 | — |
| Stained 2–3 ft | 30 | 5 | 4 |
| Badly limited < 2 ft | 10 | 3 | — |
| Warm-season arms | 20 | 4 | 4 |
| Algal (NDCI > 0.03 or chlorophyll ≥ 15) | 20 | 4 | — |
| Sediment-driven | 12 | 3 | — |

- **A class below its minimum is INSUFFICIENT:** no verdict and no score change.
- **The P2 verdict** requires the clear, normal and stained minima, the coverage precondition (≥ 80% of clean rows and
  of stained rows) and all nine gates, with gate 9 on the fresh national set. Otherwise: **INSUFFICIENT DATA** or
  **P2 NOT READY**.

## 9. Diagnostics (reported, not gated)

- Spearman of P1's signed error against NDCI, in arms (the chlorophyll-at-704 hypothesis predicts a positive slope:
  more NDCI, reads clearer).
- Spearman of P1's signed error against ρ(B05)/ρ(B11), in arms (the residual hypothesis predicts a positive slope: a
  lower ratio reads murkier).

## 10. Readiness

**The rubric is unchanged:** seven capabilities; SUPPORTED 1, PARTIAL 0.5, NOT 0; the total out of 7 scaled to 10 and rounded.

**How the score may move:**
- The score is for **the product as it runs**. A candidate's fresh evidence is reported "as if deployed", and moves
  the score only when that candidate is deployed.
- Only fresh held-out evidence moves a capability. INSUFFICIENT keeps the prior verdict.
- Downgrades apply when fresh evidence contradicts the prior verdict.
- Bottom-risk needs a depth input the product does not have (bathymetry is out of scope), so it cannot be earned in this track.

**The capability criteria** (exactly as coded in `frozen/fresh_eval.py`):

| Capability | PARTIAL requires | SUPPORTED requires |
|---|---|---|
| **Clear channel** (main stem, ≥ 6 ft) | minimum met; median signed ≥ −2.5 ft; recall of "clear" ≥ 0.40; precision ≥ 0.60 | n ≥ 40 on ≥ 8 scene-days; median signed in [−1.5, +1.5]; recall ≥ 0.60; precision ≥ 0.75; refusals ≤ 30% |
| **Normal 3–6 ft** | minimum met; \|median signed\| ≤ 1.5; recall ≥ 0.50 | n ≥ 40 on ≥ 8 scene-days; \|median signed\| ≤ 1.0; recall and precision ≥ 0.60; monotone calibration |
| **Stained 2–3 ft** | minimum met; \|median signed\| ≤ 1.0; recall and precision ≥ 0.40 | n ≥ 60 on ≥ 10 scene-days in ≥ 6 arms, both seasons; \|median signed\| ≤ 0.75; recall and precision ≥ 0.60 |
| **Algae-affected** | minimum met; fresh warning PPV ≥ 0.25 | n ≥ 30 on ≥ 5 scene-days; PPV ≥ 0.40; \|median signed\| ≤ 1.0 in algal water; class accuracy ≥ constant + 0.10 there |
| **Sediment-muddy** | minimum met; \|median signed\| ≤ 2.0; bright-sediment-as-clear ≤ 15% | n ≥ 20 on ≥ 4 scene-days; \|median signed\| ≤ 1.0; bright-sediment-as-clear ≤ 5% |
| **Badly limited < 2 ft** | minimum met; ≤ 10% called ≥ 4 ft; ≥ 60% called < 3 ft or refused | n ≥ 25 on ≥ 5 scene-days; recall ≥ 0.60; precision ≥ 0.50; median signed ≤ +0.75 |
| **Bottom-risk / shallow clear** | a bottom-risk flag on ≥ 60% of bottom-visible reports, with ≤ 30% false flags (n ≥ 15) | ≥ 80% flagged, ≤ 15% false flags (n ≥ 30) |

**Downgrades.** A capability whose minimum is met but which fails its PARTIAL criteria on fresh data becomes NOT,
even if it is PARTIAL today.

**The algal-warning PPV.** Computed only when at least 20 Secchi-grade rows are flagged, with Stage 8's definition:
a flagged row is a hit when the champion reads ≥ 1.5× the Secchi. Below 20 flagged rows, the capability is INSUFFICIENT.
