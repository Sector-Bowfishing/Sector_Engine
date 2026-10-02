# Stage 9 pre-registration: a physically based Sentinel-2 Secchi challenger (P1)

Written 2026-09-29, before any P1 prediction was computed on any validation row.
Its sha256 is recorded in the report. Nothing below is changed after results are seen;
any deviation is listed in the report as a deviation.

C6 is frozen: no refit, no threshold, no new predictor. It is a benchmark only.

## 1. The model (P1): QAA with a 704 nm reference, Lee 2013 Kd, Lee 2015 Secchi

Zero parameters are fitted to any Sector, Guntersville, WQP or national data. Every
evaluation is therefore out of sample by construction.

Inputs are Sentinel-2 L2A (Earth Search C1) bottom-of-atmosphere reflectance ρ for
B02, B03, B04 and B05, at the band centres 492, 560, 665 and 704 nm. They are the
row's median over valid pixels, the same values C3 and C6 use.

1. **Rrs = ρ/π.** No sky-glint, glint or adjacency removal: Sen2Cor removes none over
   water, and there is no defensible spectral shape to subtract with these bands.
   The Stage 8 SWIR residual (median ρ(B11) ≈ 0.013 over water) exceeds red ρ in
   clear water, so it is not a flat glint term and is not subtracted.
2. **Below-surface:** rrs = Rrs / (0.52 + 1.7·Rrs) (Lee et al. 2002).
3. **u = bb/(a+bb):** u = (−g0 + √(g0² + 4·g1·rrs)) / (2·g1), with g0 = 0.089 and
   g1 = 0.1245 (QAA v6).
4. **Reference wavelength λ0 = 704 nm, where a(704) = aw(704).** This is the
   turbid/inland reference-band approach of Le et al. 2009 (QAA-710) and Gons (1999),
   who use aw(704) = 0.70 m⁻¹.
5. **bbp(704) = u(704)·aw(704)/(1 − u(704)) − bbw(704).**
6. **η = 2·(1 − 1.2·exp(−0.9·rrs(492)/rrs(560))).** This is QAA v6's formula with 492
   in place of 443 (B01 is 60 m and outside the permitted bands). It is the one
   adaptation here that is **not** a published, validated coefficient. Its effect is
   bounded and reported (§4).
7. **bbp(λ) = bbp(704)·(704/λ)^η;** bb = bbw + bbp.
8. **a(λ) = (1 − u(λ))·bb(λ)/u(λ)** at 492, 560 and 665.
9. **Kd(λ)** (Lee et al. 2013):
   Kd = (1 + 0.005·θs)·a + (1 − 0.265·bbw/bb)·4.259·(1 − 0.52·e^(−10.8·a))·bb,
   with θs = 90° − the scene's sun elevation.
10. **Secchi** (Lee et al. 2015): Z = ln(|0.14 − Rrs_t| / 0.013) / (2.5·Kd_t).
    Kd_t is the minimum Kd over 492, 560 and 665 (the visible domain; 704 is
    excluded), and Rrs_t is Rrs at that band. Feet = m × 3.28084.

**Physical constants (measured, not fitted):**
- **Pure-water absorption, aw.** Pope & Fry (1997), linearly interpolated to the band
  centres: aw(492) = 0.0161, aw(560) = 0.0619, aw(665) = 0.4245, aw(704) = 0.705 m⁻¹.
- **Pure freshwater backscattering, bbw.** bbw(λ) = 0.00111·(500/λ)^4.32 m⁻¹ (Morel
  1974). Freshwater is used rather than seawater: 1/1.30 of the value QAA uses for sea.

**Freshwater and inland adaptations, in full:**
1. The 704 reference in place of 555/670.
2. Freshwater bbw.
3. The 492/560 ratio in η.
4. Kd_min restricted to the visible bands available.

Nothing else is adapted.

**Known bias directions (stated a priori):**
- **Clear water may read too murky.** Any positive residual in ρ(704) (skylight,
  adjacency, aerosol error) becomes spurious particle backscatter. Kd rises, and
  Secchi comes out too short. This is strongest in clear water, where the real ρ(704)
  is smallest.
- **Algal water may read too clear.** Phytoplankton absorption at 704 makes the true
  a(704) exceed aw(704). bbp is then underestimated, Kd is too low, and Secchi comes
  out too long.
- **Stained (CDOM) water.** CDOM absorption is represented through a(λ) at 492, 560
  and 665, which a red-band model cannot do. This is the model's physical advantage.

## 2. Input-domain guards: refuse, never clamp

These are checked in this order. The first failure is the refusal reason. A refused
row has no P1 prediction. It is never clamped or filled.

- **R1: sun elevation ≥ 20°** (θs ≤ 70°, the Lee 2013 Kd domain).
- **R2: every band reflectance is valid.**
  - Raw (unfloored) ρ at B02, B03 and B04 must lie in [0.001, 0.15].
  - ρ(B05) must lie in [0.003, 0.15].
  - The 0.003 floor on B05 is the reference band's noise floor (Rrs ≈ 0.001 sr⁻¹,
    the order of the L2A residual over water). Below it, bbp(704) is noise. It is an
    a priori engineering bound, not fitted.
- **R3: blue/green ratio ρ(B02)/ρ(B03) in [0.25, 2.0].** This is the domain in which
  the η formula stays positive and physical.
- **R4: red/green ratio ρ(B04)/ρ(B03) in [0.10, 2.0].**
- **R5: NDCI in [−0.25, +0.20].**
  - Above +0.20 (chlorophyll roughly 40 µg/L or more), phytoplankton absorption at
    704 is plausibly more than 20% of aw(704). The reference assumption is then broken.
  - Below −0.25, the red edge is at noise.
- **R6: scum or emergent vegetation.** ρ(B05) > ρ(B03) is refused: a red-edge peak
  above the green peak indicates surface biomass.
- **R7: internal consistency.**
  - bbp(704) > 0.
  - 0 < u < 1 at every band.
  - a(λ) ≥ 0.9·aw(λ) at 492, 560 and 665. The 10% allowance covers band-averaging of
    aw; anything below it means the inversion is inconsistent.
  - η ≥ 0.
- **R8: output in the defensible range, 0.5 to 20 ft.**
  - Below 0.5 ft, the disk reading is dominated by surface and observer effects.
  - Above 20 ft, there is no signal at 704.
  - Outside the range the row is refused, not clamped.

**Pixel-level exclusions (unchanged, already applied to every row's medians):**
- SCL water only.
- Cloud standoff 60 m.
- Haze: SWIR > 0.02, and a haze edge at 0.010 within 400 m.
- Bank standoff 10 m; structure 100 m.
- SWIR ≤ 0.0215, FAI ≤ 0.005, NDVI ≤ 0.10.

Adjacency beyond the 10 m standoff cannot be corrected with these bands. It is
labelled by region kind (narrow arm against main stem), not removed.

**Row-level labels (unchanged from Stages 7 and 8):**
- **Vegetation-contaminated:** at least 20% of water pixels are dropped by NDVI/FAI.
- **Bottom-risk:** Secchi ≥ 0.5 × the station depth.
- Both are excluded from the headline and reported separately.
- No depth correction is attempted.

## 3. Evaluation

**Sets (unchanged):**
- **G:** the 72 clean Guntersville rows of Stages 7 and 8. Bottom-risk and
  vegetation-contaminated rows are reported separately.
- **N:** the Stage 7 national clean rows.
- **F:** the Stage 8 fresh national set (412), as context.

**The nine gates, unchanged.** They are computed on the G rows P1 answers:
1. Spearman ≥ 0.5.
2. Monotone calibration.
3. |station-balanced median signed| ≤ 0.75 ft.
4. Stained 2–3 ft median signed ≤ +1.0 ft.
5. Clear channel median signed ≥ −1.5 ft.
6. AUC (clear channel against stained arm) ≥ 0.8.
7. 4-class accuracy ≥ the constant guess + 0.10.
8. MAE and median absolute error both below the champion's **on the same rows**.
9. On N, median absolute error ≤ 1.1× and Alabama MAE ≤ 1.2× the champion's,
   **on the same rows**.

**How the schemes apply to P1.** P1 has nothing to fit, so its leave-one-year-out and
leave-one-station-out predictions are identical. The comparators use their own
held-out predictions:
- C3 and C6: leave-one-year-out and leave-one-station-out on G, and the Stage 7
  lake-grouped national CV on N;
- the champion: no fit.

Every comparison is paired on the rows P1 answers. The Stage 8 all-row numbers are
shown alongside.

**Coverage precondition** (added because P1 can refuse, which no earlier model could).
It is stricter, never looser. P1 must answer:
- ≥ 80% of the 72 clean G rows; **and**
- ≥ 80% of the clean stained 2–3 ft G rows.

Otherwise P1 is NOT READY, whatever the gates say. This stops a model passing by
refusing its hard cases.

**The verdict.** PHYSICAL CHALLENGER READY only if the coverage precondition and all
nine gates pass. Otherwise NOT READY.

**Pre-registered water-type subsets** (G, reported for every model on the same rows,
with P1 refusals counted):
- **dark algal water:** arm, and chlorophyll ≥ 15 µg/L (or, lacking chlorophyll,
  NDCI > 0). This is the Stage 7 "algal arms" subset.
- **stained arms:** arm, and Secchi ≤ 3 ft.
- **sediment-muddy:** (turbidity ≥ 8 or Secchi ≤ 3), and chlorophyll < 10. This is
  the Stage 7 subset.
- **very clear channel:** main stem, and Secchi ≥ 6 ft.
- **algae/sediment tug-of-war:** chlorophyll ≥ 15 **and** (turbidity ≥ 8 NTU or TSS
  ≥ 10 mg/L). Where chlorophyll is missing, the optical stand-in is NDCI > 0.03
  **and** champion FNU ≥ 8, reported separately.

**Also reported:**
- every stained 2–3 ft observation;
- the clear channel with and without bottom-risk rows;
- refusal counts by reason and by class, in G, N and F;
- every G row with |error| > 3 ft.

## 4. Sensitivity (context only)

These are never candidates, never gated, and never promoted:
- **η fixed at 0 and at 2:** the bound on the 492-for-443 adaptation.
- **A flat offset δ = 0.002 and 0.004** subtracted from all four bands. This shows how
  much of P1's error a spectrally flat atmospheric residual would explain. The
  guards are applied after the offset.

If P1 fails, no variant from this section may be declared the challenger. A variant
would need its own pre-registration and fresh data.

## 5. Stop rule

If a step turns out to need a coefficient that is not transferable (for example, a
local a(λ0) regression, a regional NDCI→chlorophyll curve, or a site-fitted η), it is
not invented. The report says so, and the model is stopped at that step.
