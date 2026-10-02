@@ p1_text
**BEST, by the frozen rule, is K4:** ACOLITE with its FFSS sky-dome interface correction applied after the atmospheric
correction. It is the only candidate that meets every condition:
- **Red error.** 0.222 against 0.251 for K0 on the same matchups, and the CI excludes 0.
- **All bands (B02–B05).** 0.168 against 0.209.
- **Valid rate.** 93%, above the 91% floor.
- **No negative water reflectance.**
- **Inland turbidity guard.** 0.302, within K0's 0.279 + 0.03.

**K1 and K2 would have fixed far more of the red band, but they lose retrievals.**
- **The gain.** They cut the red error to 0.15 and the red bias from +0.25 to +0.15. Their B02–B05 error of 0.14–0.15
  is the lowest of any candidate.
- **The cost.** Their valid rate is 87% and 89% on AERONET-OC, against a floor of 91%. They also keep only 40–42 of the
  guard stations, against K0's 52.
- **The likely reason:** the sky-reflection term they subtract pushes clear, dark water below zero, where ACOLITE masks it. This is inferred from where the losses fall; the flags were not broken down.
- **So the pre-registered valid-rate rule rules them out.**

**K3 (FFSS at top of atmosphere)** returns NaN on every scene. That is a failure inside ACOLITE: not feasible.

**K0 reproduces Stage 11 exactly** on the 3 check scenes.

**RED-BAND RESIDUAL FIXED: NO.**
- K4's red bias is +0.222 against K0's +0.254, a 13% cut; the bar for PARTIAL was 30%.
- **What the experiment does show:** subtracting sky reflection explains roughly 40% of the red over-brightness (K1/K2).
  The rest is presumably aerosol or adjacency error, which no interface option addresses.

@@ p2_text
**Sen2Cor production path: the bands are fixed, but P2's decisions still flip.**
- **The bands.** Harmonisation brings every band's held-out median within 2%: B05 1.010, B8A 1.001, B11 0.993, B12 0.981.
- **The decisions.** P2 still flips on **8.1%** of identical-water pixels, down from 24.1%. The flips concentrate in
  turbid pairs (Pontchartrain, Mobile Bay 11–18%).
- **Most likely why:** P2's residual test reacts to the pixel-level scatter between two sensors, which harmonising band
  medians cannot remove.

**ACOLITE path: the adopted method (V-ρw) brings flips under the bar.**
- **Flips.** P2's decisions on ACOLITE reflectance flip on **3.9%** of held-out pixels, down from 22.3% raw.
- **Residuals.** B02–B05 and B8A are within 1.5%.
- **The TOA method (V-op) is worse** at 8.8% (Tampa Bay 62%). It aligns the band medians, but not the dark pixels that
  ACOLITE's aerosol step reads.
- **The residual that misses:** B11, at −0.0006 against a ±0.0005 bar. ACOLITE sets water B11 to about zero, so the
  band carries little for water.
- **Coverage.** Two pairs, Lake Volta and Lake Nasser, have no water pixel valid in every run, so 10 of 12 pairs are
  scored.

**S2C HARMONIZED: PARTIAL, by the frozen rule.** Only one path is under 5%, and one ACOLITE residual (B11) misses its
bar.

**The caveat that matters.**
- **Only the commissioning tandem is public.** V-ρw raises S2C's visible water reflectance by about 0.002, because
  commissioning S2C read darker through ACOLITE. Operational S2C may not need that.
- **Where it gets tested.** The corpus platform test (section 6) checks it on 2025 S2C.
