# Current Clarity Stage 12: Water Reflectance Engine

**Diagnostic only.**
- Production Current Clarity is unchanged, and nothing was deployed.
- No Sector field observation was used, and the P2 fresh holdout was not touched.
- Water Temperature was not started.
- Michael's Guntersville survey stays an independent acceptance test.

**Erratum (reissued 2026-09-30).**
- **The bug.** In the first issue, the clear-water row and the CLEAR WATER ERROR line reported the in-situ "clear"
  water type (low turbidity and chlorophyll, 268 rows). A key collision in `models12.py` had overwritten the Secchi
  class clear ≥ 6 ft.
- **The corrected Secchi-clear figures** (574 rows at 412 lakes): ×1.56 and −3.3 ft for the engine, against ×1.97 and
  −5.2 ft for production.
- **Nothing else changed:** the engine, every fit and every other row are the same.

**Freeze.** The pre-registration was hashed at **2026-09-30T14:45:17Z** (sha256 `474a8cd1…`), before any Stage 12 value
existed. The certification protocol was hashed at 15:04:45Z (`1e8040b9…`), before any certification site or visit
file was fetched. Five addenda, A–D and B2, were each hashed before the data they govern was examined (section 2).

## The answer

**The new reflectance improves the clarity estimate wherever it can read the water. It reads only three stations in
four, and it does not fix the red band.**
- **The configuration.** ACOLITE with the FFSS sky-dome interface correction (K4), surface pressure from each lake's
  elevation, and S2C harmonised at the water-reflectance level.
- **The gain.** C3 refitted on this reflectance is the best model, and no simpler one is equivalent: held-out error **×1.47**,
  against **×1.66** for today's production on the same 1,206 rows at 792 lakes.
  - **The reflectance itself buys most of it.** The same C3 on Sen2Cor scores ×1.58 on those rows (difference −0.031,
    CI −0.045 to −0.016).
  - **Clear water is where it shows:** ×1.56 against ×1.97, and a median error of −3.3 ft against −5.2 ft for production.
    Routing adds nothing (0.8%).
- **What it does not fix:**
  - **Coverage.** ACOLITE gives a valid disk at only **76%** of stations. Sen2Cor has one at all of them.
  - **The red band.** No interface option cut the red bias enough (K4 +0.22 against +0.25). The two that cut it to +0.15
    lost too many retrievals.
  - **Turbidity.** It is not better overall: better in clear water, worse in murky water.
  - **Sentinel-2C.** It is only partly harmonised, and the engine's class still flips on 11% of identical S2A/S2C pixels.
- **Capability, historical and strict:**
  - exact feet **0/10**;
  - clarity class **1/10** (clear and sediment PARTIAL).
  - **Stained and limited water are the weakest classes on every input tested** (recall 0.2–0.3).
- **The blind certification set** was built without reading a single Secchi value: 289 observations, 272 lakes, 39
  states. It is **not ready**: short of 400 observations, of stained, sediment and limited water, and of the cool season.

## 1. What was done

| | |
|---|---|
| Interface experiment | 5 frozen ACOLITE configurations against **46 AERONET-OC matchups** at 5 sites, with a 60-lake inland-turbidity guard (Guntersville excluded) |
| Harmonisation | Derived from the 12 Stage 11 Sentinel-2A/2C tandem pairs only, and validated leave-one-pair-out on both paths (Sen2Cor production and ACOLITE) |
| Corpus | **1,631 station-days** (1,015 lakes) through the new reflectance: 1,343 L1C scenes and 1,504 crops, of which 1,478 ran and 100 used the angle-grid fallback. Guntersville is kept apart (45 rows). |
| Models | 9 candidates, fitted on training lake-folds only (5 whole-lake folds), with Guntersville excluded from every fit and selection |
| Capabilities | Exact feet and clarity class, scored separately on historical lake-held-out rows |
| Certification | A blind external protocol and sample, built without reading any Secchi value |
| Not pursued | C2RCC, C2X, P1-NIR, routing for its own sake, Landsat and OLCI fusion, temporal replacement, and public depth. No Stage 12 evidence reopened them. |

## 2. Deviations and addenda

- **A (harmonisation, 15:04Z).** A technical check on one pair showed that TOA harmonisation does not carry through
  ACOLITE's dark-spectrum aerosol step. The addendum added a water-reflectance-level method (V-ρw). It also made the
  ACOLITE-path verdict use the method that would be adopted operationally, not the V-full emulation.
- **B and B2 (certification matching, 15:31Z and 16:32Z).**
  - Earth Search's production collection has **no scenes at all for 2017 or 2022**, which are the two NLA survey years.
  - Matching for those years uses Earth Search's older `sentinel-2-l2a` collection.
  - B's first reading of that collection's offset flag was wrong: it double-subtracted 0.1 from 2022. B2 corrected it
    before any match was counted.
- **C (surface pressure, 15:59Z).**
  - At a 2,318 m lake, every pixel was flagged negative, because ACOLITE had used sea-level pressure.
  - Every corpus crop now sets its elevation from USGS 3DEP. ACOLITE converts it to pressure.
  - The 59 rows already processed were discarded.
  - AERONET sites sit at 0–174 m, so Part 1 is unaffected. At Lake Erie, B04 changes by +2% and the pooled error by
    +0.013.
- **D (viewing geometry, 17:23Z).** Older L1C baselines keep detector footprints as GML, which the GDAL stand-in cannot
  read. Those crops fall back to ACOLITE's angle-grid geometry.
- **Smaller notes.**
  - The NLA 2022 site file writes the sampled flag as `YES`, not `Y`.
  - SYKE was queried in bulk rather than lake by lake, under the same rules.
  - A candidate that "fails to run" means an ACOLITE error or an all-NaN output. Losing valid station pixels is judged
    by criterion 3, not as a failure to run.

## 3. Part 1: ACOLITE's air–water interface options

| | Setting | Valid | B02 | B03 | B04 | B05 | B02–B05 | Guard \|e_T\| | Verdict |
|---|---|---:|---|---|---|---|---:|---:|---|
| K0 | Stage 11 (no interface term) | 96% | 0.271 (+0.271) | 0.174 (+0.174) | 0.254 (+0.254) | 0.109 (+0.109) | **0.210** | 0.279 | baseline |
| K1 | interface: default (RSKY LUT, wind 2 m/s) | 87% | 0.208 (+0.208) | 0.121 (+0.118) | 0.152 (+0.152) | 0.116 (-0.033) | **0.148** | 0.305 | not eligible: valid rate |
| K2 | interface: 6SV rough surface | 89% | 0.190 (+0.179) | 0.110 (+0.095) | 0.150 (+0.150) | 0.114 (-0.041) | **0.140** | 0.296 | not eligible: valid rate |
| K3 | interface: FFSS at TOA | 0% | – (–) | – (–) | – (–) | – (–) | **–** | – | not feasible: all-NaN output |
| K4 | interface: FFSS after AC (BOA) | 93% | 0.229 (+0.229) | 0.140 (+0.140) | 0.222 (+0.222) | 0.079 (+0.015) | **0.168** | 0.302 | **eligible** |

Each cell reads median |log10 error| (median bias) against AERONET-OC Level 2.0.

**Paired against K0** (matchup-block bootstrap):

| Candidate vs K0 | Matchups | Red (B04) | Red difference (95% CI) | B02–B05 | B02–B05 difference (95% CI) |
|---|---:|---|---|---|---|
| K1 | 40 | 0.152 vs 0.247 | -0.095 (-0.138 to -0.037) | 0.148 vs 0.209 | -0.061 (-0.089 to -0.038) |
| K2 | 41 | 0.150 vs 0.251 | -0.101 (-0.152 to -0.046) | 0.140 vs 0.213 | -0.073 (-0.108 to -0.042) |
| K4 | 43 | 0.222 vs 0.251 | -0.029 (-0.051 to -0.018) | 0.168 vs 0.209 | -0.041 (-0.052 to -0.021) |

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

## 4. Part 2: harmonising Sentinel-2C

**Coefficients** (all 12 pairs; S2C → S2A-equivalent; k is the B05 band-shape term on B06 − B04):

| Band | TOA: gain, offset (ACOLITE path) | Applied to operational TOA | BOA: gain, offset (Sen2Cor path) |
|---|---|---|---|
| B02 | 0.994, -0.0026 | no | 0.992, +0.0007 |
| B04 | 0.983, +0.0003 | no | 0.993, +0.0003 |
| B05 | 0.979, +0.0002; k -0.059 | yes | 1.000, +0.0007; k -0.045 |
| B08 | 0.987, -0.0005 | yes | 0.992, -0.0005 |
| B8A | 0.982, -0.0008 | yes | 0.992, -0.0008 |
| B11 | 0.832, -0.0006 | yes | 0.829, -0.0010 |
| B12 | 0.827, -0.0002 | yes | 0.847, -0.0005 |

**P2 route flips on identical water, held-out pairs:**

| Tandem pair (held out) | Sen2Cor path: raw → harmonised | ACOLITE raw | ACOLITE V-full | ACOLITE V-op | ACOLITE V-ρw |
|---|---|---:|---:|---:|---:|
| Chapala (13QFC) | 3% → 0% | 4% | 3% | 3% | 3% |
| Chapala (13QGC) | 7% → 1% | 5% | 3% | 3% | 2% |
| Pontchartrain (15RYP) | 19% → 11% | 0% | 0% | 0% | 0% |
| Pontchartrain (16RBU) | 56% → 15% | 0% | 0% | 0% | 0% |
| Mobile Bay (16RCU) | 40% → 14% | 1% | 0% | 0% | 0% |
| Mobile Bay (16RDU) | 26% → 18% | 4% | 0% | 1% | 0% |
| Tampa Bay (17RLL) | 6% → 4% | 75% | 19% | 62% | 11% |
| Volta (30NZP) | 12% → 8% | – | – | – | – |
| Kariba (35KNB) | 0% → 0% | 29% | 1% | 2% | 4% |
| Kariba (35KPB) | 0% → 0% | 90% | 3% | 6% | 9% |
| Nasser (36QUJ) | 100% → 13% | – | – | – | – |
| Van (38SLH) | 21% → 11% | 14% | 10% | 10% | 10% |
| **Mean over pairs** | **24% → 8%** | **22%** | **4%** | **9%** | **4%** |

**Residual band differences** (median over held-out pairs):

| Band | Sen2Cor raw C/A (C − A) | Sen2Cor harmonised | ACOLITE raw | ACOLITE V-ρw |
|---|---|---|---|---|
| B02 | 0.989 (-0.0006) | 0.992 (-0.0004) | 0.978 (-0.0010) | 1.000 (-0.0000) |
| B04 | 1.001 (+0.0001) | 1.003 (+0.0001) | 0.950 (-0.0005) | 0.995 (-0.0003) |
| B05 | 0.953 (-0.0014) | 1.010 (+0.0003) | 0.873 (-0.0030) | 1.001 (-0.0000) |
| B8A | 1.076 (+0.0009) | 1.001 (-0.0000) | 0.768 (-0.0010) | 1.015 (+0.0001) |
| B11 | 1.458 (+0.0021) | 0.993 (-0.0000) | 0.428 (-0.0001) | 0.174 (-0.0006) |
| B12 | 1.276 (+0.0012) | 0.981 (-0.0001) | 0.321 (-0.0007) | 0.313 (-0.0005) |

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

## 5. Part 3: the corpus through the new reflectance

**Retrieval rate (R1).**

| | ACOLITE valid 60 m disk | Sen2Cor production |
|---|---:|---:|
| All corpus rows (not Guntersville, 1,582) | **76%** | 100% (by construction) |
| Clear | 77% | 100% |
| Normal | 75% | 100% |
| Stained | 76% | 100% |
| Limited | 76% | 100% |

- **ACOLITE loses a quarter of the stations, evenly across classes.** Of the 379 stations without a valid disk:
  - **289** have every disk pixel flagged by ACOLITE's water mask;
  - **64** keep fewer than 5 valid pixels;
  - **24** crops produced no output, because the aerosol fit failed;
  - **2** scenes have no L1C.
- **Which flag.** The flag type was not recorded per station. At the one station inspected it was the
  negative-reflectance flag.
- **Sen2Cor production answers everywhere,** because every corpus row was selected on a valid Sen2Cor read.
- **Unknown in Part 5 is these stations.**

**Turbidity from each path's red band (R2)**, as median |e_T| (bias), with the paired difference:

| Rows | n (lakes) | ACOLITE median \|e_T\| (bias) | Sen2Cor median \|e_T\| (bias) | ACOLITE − Sen2Cor (95% CI) |
|---|---:|---|---|---|
| **All, same-day pass** | 200 (158) | 0.258 (-0.116) | 0.245 (+0.083) | +0.013 (-0.033 to +0.062) |
| All, pass within ±1 day | 524 (337) | 0.251 (-0.134) | 0.210 (+0.042) | +0.041 (+0.004 to +0.076) |
| Secchi class: clear | 66 (55) | 0.259 (+0.183) | 0.391 (+0.376) | -0.132 (-0.207 to -0.074) |
| Secchi class: normal | 59 (51) | 0.190 (-0.139) | 0.174 (+0.026) | +0.015 (-0.086 to +0.093) |
| Secchi class: stained | 35 (33) | 0.235 (-0.208) | 0.134 (-0.002) | +0.101 (+0.028 to +0.166) |
| Secchi class: limited | 40 (35) | 0.325 (-0.312) | 0.230 (-0.177) | +0.095 (+0.028 to +0.217) |
| In-situ type: clear | 108 (91) | 0.224 (-0.022) | 0.276 (+0.203) | -0.052 (-0.130 to -0.005) |
| In-situ type: algal | 20 (18) | 0.293 (-0.279) | 0.175 (-0.082) | +0.118 (-0.020 to +0.224) |
| In-situ type: sediment | 18 (16) | 0.256 (-0.229) | 0.148 (-0.028) | +0.108 |
| In-situ type: mixed | 27 (25) | 0.332 (-0.330) | 0.204 (-0.181) | +0.128 (+0.045 to +0.201) |

- **Reflectance improved: NO by the frozen rule.** On same-day rows ACOLITE is +0.013 (CI includes 0); within ±1 day it
  is worse, +0.041 (CI excludes 0).
- **The pattern matters more than the total:**
  - **Clear water:** ACOLITE removes most of Sen2Cor's over-read (bias +0.18 against +0.38; error 0.26 against 0.39).
  - **Stained, limited, algal and mixed water:** ACOLITE reads turbidity lower than Sen2Cor (bias −0.21 to −0.33).
  - **Why this matters:** Sen2Cor's extra brightness was partly cancelling the turbid-water under-read that every
    processor shares.
- **Across the corpus ACOLITE's water reflectance is 17–33% darker than Sen2Cor's.** Blue is ×0.67, green ×0.83, red
  ×0.70 and 704 nm ×0.76. That fits Sen2Cor's AERONET-OC over-read.

**The Part A split (R3), through the frozen champion:**

| Same-day rows with turbidity | ACOLITE FNU | Sen2Cor FNU |
|---|---:|---:|
| Radiometric share of Var(e_S) | 60% | 65% |
| Conversion share | 40% | 35% |
| Frozen champion median \|e_S\| | 0.219 | 0.177 |

The frozen champion was fitted on Sen2Cor, so on ACOLITE it is worse (0.219 against 0.177). That is why Part 4 refits
every empirical form.

**By platform (R4):**

| Platform (turbidity rows ±1 day) | n | ACOLITE median e_T | Sen2Cor median e_T |
|---|---:|---:|---:|
| sentinel-2b | 307 | -0.120 | +0.032 |
| sentinel-2a | 204 | -0.139 | +0.062 |
| sentinel-2c | 13 | -0.259 | -0.169 |

## 6. Part 4: the simplest clarity engine

**All candidates, held out by whole lakes** (1,206 rows at 792 lakes with a valid ACOLITE disk, Guntersville excluded):

| Candidate (on ACOLITE ρw) | Coverage | Median \|log\| (factor) | Median signed ft | Class accuracy | Eligible |
|---|---:|---|---:|---:|---|
| 1 champion, frozen | 100% | 0.190 (×1.55) | +0.66 | 0.56 | yes |
| 2 P1, frozen | 76% | 0.185 (×1.53) | -1.34 | 0.47 | no (coverage) |
| 3 champion form, refitted | 100% | 0.186 (×1.53) | -0.01 | 0.54 | yes |
| 4 N1 (red) | 100% | 0.186 (×1.53) | +0.02 | 0.54 | yes |
| 5 N2 (red + green/red) | 100% | 0.178 (×1.51) | +0.07 | 0.56 | yes |
| 6 C3 form, refitted | 100% | **0.169 (×1.47)** | -0.03 | 0.60 | yes |
| 7 C6 form, refitted | 100% | 0.170 (×1.48) | +0.08 | 0.60 | yes |
| 8 P2, frozen | 75% | 0.169 (×1.48) | -0.92 | 0.49 | no (coverage) |
| 9 routed (nested) | 99% | 0.168 (×1.47) | +0.22 | 0.60 | router |
| *Production today: champion on Sen2Cor, same rows* | 100% | *0.219 (×1.66)* | *-0.75* | *0.46* | reference |

**Equivalence to the best, C3** (the lake-bootstrap CI's upper bound must be ≤ +0.010):

| Simpler than the best (C3) | Difference in median \|log\| | 95% CI | Equivalent (upper ≤ +0.010) |
|---|---:|---|---|
| 1 champion, frozen | +0.0216 | +0.0060 to +0.0399 | no |
| 3 champion form, refitted | +0.0169 | +0.0070 to +0.0304 | no |
| 4 N1 (red) | +0.0172 | +0.0053 to +0.0285 | no |
| 5 N2 (red + green/red) | +0.0095 | -0.0025 to +0.0238 | no |

**Routing**, judged against the engine:

| | Routed | Engine (C3) |
|---|---:|---:|
| Median \|log\|, same rows | 0.1677 | 0.1691 |
| Relative gain | +0.8% (bar ≥ 10%) | |
| Difference 95% CI | -0.0108 to +0.0070 | |
| Coverage | 99% | 100% |

**The engine is C3, refitted on ACOLITE reflectance: one model, no routing.**
- **It is the best model,** and no simpler model is statistically equivalent. N2 comes closest, at +0.0095 with an upper
  bound of +0.024.
- **It passes the C3 guard in algal water:** 0.189, against 0.184 for N2, the best other model there (the bar is +0.01).
  So C3 is not an unconditional algal fallback.
- **Routing gains 0.8%** (CI includes 0), well short of the 10% bar, so the improved input does not need a router.
- **P1 and P2 score well on the rows they answer,** but answer only 75–76% of them, below the 90% needed for a single
  engine.

**Where the gain comes from** (exploratory, not pre-registered):

| Same 1,206 rows, same folds | C3 on Sen2Cor | C3 on ACOLITE | Difference (95% CI) |
|---|---:|---:|---|
| Median \|log\| | 0.200 | **0.169** | -0.031 (-0.045 to -0.016) |

On identical rows and folds, the reflectance change alone lowers C3's error by 0.031 log (16%).

**Per class, held out, against production on the same rows:**

| True class / type | Rows (lakes) | ACOLITE C3 engine: error; signed; class accuracy | Production today, same rows |
|---|---:|---|---|
| Clear ≥ 6 ft | 574 (412) | **×1.56** (0.192); -3.3 ft; 0.75 | ×1.97 (0.295); -5.2 ft; 0.47 |
| Normal 3–6 ft | 286 (208) | **×1.27** (0.104); +0.3 ft; 0.64 | ×1.31 (0.119); +0.2 ft; 0.67 |
| Stained 2–3 ft | 173 (151) | **×1.38** (0.140); +0.9 ft; 0.29 | ×1.40 (0.147); +0.9 ft; 0.25 |
| Limited < 2 ft | 173 (137) | **×1.81** (0.257); +1.0 ft; 0.32 | ×1.98 (0.297); +1.3 ft; 0.29 |
| In-situ algal | 94 (77) | **×1.51** (0.178); +1.0 ft; 0.45 | ×1.57 (0.196); +1.2 ft; 0.43 |
| In-situ sediment | 64 (54) | **×1.37** (0.136); +0.6 ft; 0.48 | ×1.27 (0.104); -0.0 ft; 0.55 |
| In-situ mixed | 83 (61) | **×1.56** (0.194); +0.6 ft; 0.45 | ×1.62 (0.209); +0.9 ft; 0.33 |
| *Guntersville (reported apart; no selection)* | 42 (10) | ×1.34 (0.128); -0.7 ft | ×1.72 (0.236); -1.5 ft |

- **Better** in clear water (×1.56 against ×1.97; the under-read shrinks from −5.2 to −3.3 ft), limited, algal and mixed
  water.
- **About the same** in normal and stained water.
- **Worse in sediment water** (×1.37 against ×1.27), consistent with ACOLITE's darker red.
- **Guntersville** (42 historical agency rows at 10 station groups, never used for selection): ×1.34 against ×1.72. This
  is historical only. Michael's survey remains the acceptance test.

**Platform** (condition b, held-out signed error of one platform minus the others):

| Platform | Rows | Median signed log error minus the others' | 95% CI |
|---|---:|---:|---|
| sentinel-2a | 501 | +0.016 | -0.020 to +0.060 |
| sentinel-2b | 674 | -0.009 | -0.049 to +0.034 |
| sentinel-2c | 31 | -0.103 | -0.155 to +0.041 |

S2C reads 0.10 log low, but on 31 rows the CI includes 0, so condition (b) passes.

**Condition (a) fails.** On identical tandem water, the engine's class flips on 11.2% of pixels (bar 5%). The median
change is only 0.16 ft:

| Engine class decision on identical tandem water | Raw | V-full | V-op | **V-ρw (adopted)** |
|---|---:|---:|---:|---:|
| Mean class-flip rate (10 pairs) | 12.1% | 8.5% | 10.0% | **11.2%** |
| Median \|Δft\| | 0.19 | 0.10 | 0.11 | **0.16** |

- **Harmonisation barely moves the class flips** (12.1% raw).
- **They most likely come from pixel-level scatter near the class boundaries** and near C3's NDCI = 0 branch switch,
  not from the S2C band bias, since harmonisation leaves them almost unchanged.
- **The tandem test is per pixel at 20 m,** while production reads a 60 m disk of about 28 pixels. So this flip rate probably
  overstates what a user would see. That was not tested, and the frozen rule still applies.

**S2A/B/C PLATFORM-INVARIANT ENOUGH FOR CLARITY: NO.**

## 7. Part 5: exact feet against clarity class

**What a user would get**, with exact feet shown only for classes the inner folds authorise:

| What a user would get | Share of corpus rows |
|---|---:|
| Exact feet (and the class) | 15% |
| Class only (feet withheld) | 61% |
| Unknown (no valid ACOLITE disk) | 24% |

- **Which classes get feet.** The inner folds authorised limited water in every fold and stained water in three.
  Normal was authorised once, and clear never; clear's predicted rows miss the ×1.41 and ±1.5 ft bars.
- **So most answers are a class, not a number:** 61% of rows get only a class, and 24% are Unknown.

**The two historical capability scores** (lake-held-out, Stage 10 bars; **not product readiness**):

| Capability | Exact feet (published rows) | Feet verdict | Clarity class | Class verdict |
|---|---|---|---|---|
| Clear | 37 published (5%); ×2.19; -4.4 ft | **NOT** | recall 0.58, precision 0.80, Unknown 23% | **PARTIAL** |
| Normal | 47 published (12%); ×1.39; -0.8 ft | **NOT** | recall 0.48, precision 0.41, Unknown 25% | **NOT** |
| Stained | 42 published (18%); ×1.17; -0.0 ft | **NOT** | recall 0.23, precision 0.32, Unknown 24% | **NOT** |
| Limited | 113 published (49%); ×1.60; +0.8 ft | **NOT** | recall 0.24, precision 0.81, Unknown 24% | **NOT** |
| Algae | 71 published (30%); ×1.53; +0.5 ft | **NOT** | class accuracy 0.33 vs constant 0.37 | **NOT** |
| Sediment | 33 published (36%); ×1.50; +0.5 ft | **NOT** | bright sediment called clear 0% (n 25); accuracy 0.34 vs 0.42 | **PARTIAL** |
| Bottom-risk | – | **NOT** | no depth input | **NOT** |
| **Score** | | **0.0 / 7 → 0/10** | | **1.0 / 7 → 1/10** |

- **EXACT-FEET CAPABILITY: 0/10.**
  - Feet are published too rarely: under 50% coverage in every class.
  - Where they are published for true clear water, it is because the model called it stained or limited. Those answers
    are badly wrong (−4.4 ft).
- **CLARITY-CLASS CAPABILITY: 1/10.**
  - **Clear is PARTIAL.** Precision is 0.80, but recall is 0.58 once the 23% Unknown counts as a miss. On retrieved
    rows alone it is 0.75.
  - **Sediment is PARTIAL:** no bright-sediment station is called clear.
  - **Stained and limited fail on recall** (0.23 and 0.24).

**The same rubric on other inputs** (exploratory; answered rows, and Unknown where noted):

| Input and rows (exploratory) | Rows | Unknown | Median \|log\| (answered) | Class accuracy (answered) | Clear recall / precision | Normal | Stained | Limited |
|---|---:|---:|---:|---:|---|---|---|---|
| Production today (champion on Sen2Cor), all rows | 1,582 | 0% | 0.225 | 0.45 | 0.46 / 0.77 | 0.68 / 0.31 | 0.24 / 0.26 | 0.26 / 0.67 |
| C3 on Sen2Cor, all rows | 1,582 | 0% | 0.198 | 0.52 | 0.69 / 0.75 | 0.57 / 0.32 | 0.19 / 0.25 | 0.17 / 0.78 |
| C3 on Sen2Cor, the ACOLITE rows | 1,206 | 0% | 0.200 | 0.53 | 0.71 / 0.74 | 0.55 / 0.32 | 0.22 / 0.32 | 0.23 / 0.81 |
| **C3 on ACOLITE, the ACOLITE rows** | 1,206 | 0% | 0.169 | 0.60 | 0.75 / 0.80 | 0.64 / 0.41 | 0.29 / 0.32 | 0.32 / 0.81 |
| C3 on ACOLITE, all rows (Unknown where no disk) | 1,582 | 24% | 0.169 | 0.60 | 0.58 / 0.80 | 0.48 / 0.41 | 0.23 / 0.32 | 0.24 / 0.81 |

- **Coverage is one limit.** With a disk at every station, C3 on ACOLITE would clear the clear-class SUPPORTED bar
  (recall 0.75, precision 0.80).
- **Stained and limited water are the real capability gap.** They sit at recall 0.17–0.32 on every input, whether
  Sen2Cor or ACOLITE, champion or C3.

## 8. Part 6: the blind external certification set

**The protocol** was written and hashed before any site or visit file was fetched (`cert/CERT_PROTOCOL_STAGE12.md`,
15:04:45Z).
- **Sources:**
  - **US core:** EPA National Lakes Assessment 2022 and 2017, from EPA's own files. Neither is in the 2018–2026 WQP pull
    used for development.
  - **Cool-season stress test:** Finland's SYKE Vesla open data.
- **Eligibility and matching:**
  - lakes within 5 km of any development station are excluded, as is Guntersville;
  - NLA visits duplicated in the WQP pull are dropped;
  - each visit needs a production-gated Sentinel-2 pass within ±1 day;
  - at most 3 observations per lake;
  - every date is ≤ 2025-12-31, so the set is disjoint from P2's fresh holdout.
- **Blindness.**
  - Only site, visit and event-key tables were fetched.
  - No NLA Secchi file was downloaded.
  - SYKE queries never selected the value field.
  - `cert/blind_sample.csv` (sha256 `111cff44…`) lists IDs, dates and satellite items only.

**Blind checks:**

| Blind check | Value | Bar | |
|---|---:|---:|---|
| Matched observations | 289 (NLA 2017 52, NLA 2022 113, SYKE 124) | ≥ 400 | **fail** |
| Distinct lakes | 272 | ≥ 100 | pass |
| US states (US core) | 39 | ≥ 20 | pass |
| Largest state share (US core) | 9.7% | ≤ 15% | pass |
| October–April observations | 4.2% (12 lakes) | ≥ 15% across ≥ 20 lakes | **fail** |
| Expected clear (US core, planning prior) | 77 | ≥ 40 | pass |
| Expected normal (US core, planning prior) | 41 | ≥ 40 | pass |
| Expected stained (US core, planning prior) | 24 | ≥ 60 | **fail** |
| Expected algae (US core, planning prior) | 36 | ≥ 30 | pass |
| Expected sediment (US core, planning prior) | 13 | ≥ 20 | **fail** |
| Expected limited (US core, planning prior) | 23 | ≥ 25 | **fail** |

**BLIND EXTERNAL CERTIFICATION SET READY WITHOUT USER SURVEY: NO.**
- **What passes:** geography and lake count. There are 272 lakes in 39 states plus Finland, with no state above 10%.
- **What fails:**
  - **Total:** 289 matched observations against the 400 bar.
  - **Match rate.** Only 11% of NLA visits have a clear pass within a day that survives the production gates, and 2017 is
    thin before Sentinel-2B.
  - **Cool season:** 4% (NLA samples only in summer, and Finnish October and November are cloudy).
  - **Expected stained, sediment and limited counts.**
- **What would complete it,** in order of independence:
  - SYKE extended from 400 lakes to all 3,705 with eligible events (cool season and humic stained water, but out of
    domain);
  - a request to TVA or USACE districts for their cool-season reservoir records;
  - a pre-registered, sealed tier of WQP records that were downloaded in Stage 1 but never analysed. That is your call,
    because those values already sit on this Mac.

## 9. The path to 9/10

**Product readiness stays 2/10.** Under the Stage 10 rule only fresh evidence moves a capability.

| Step | The Stage 12 finding it rests on | What it would move |
|---|---|---|
| 1. Recover the 24% of lost retrievals | ACOLITE gives a valid disk at 76% of stations. Its water mask flags whole disks at 289 stations and most of the disk at 64 more, and the aerosol fit fails on 24 crops | Clear to SUPPORTED on the class rubric. On retrieved rows its recall is already 0.75 |
| 2. Give the class decision an uncertainty band at the 3 and 6 ft boundaries, and re-test S2A/S2C on disk-averaged pixels | 11% of pixels flip class on identical water, with a median change of only 0.16 ft | Platform invariance |
| 3. Find a signal for stained and limited water | Recall 0.17–0.32 on every input and model; routing and refits do not help | Stained and limited, the capabilities that separate 4/10 from 9/10 |
| 4. Complete the blind set | 289 observations; stained, sediment, limited and cool season short | Certification without anyone surveying |
| 5. Certify once, on the blind set and on P2's fresh data | The Stage 10 bars, unchanged | Readiness |

- **Step 1 options, to pre-register:** ACOLITE mask variants, or a hybrid. The hybrid uses ACOLITE where it reads the
  water, and C3 on Sen2Cor elsewhere, flagged as lower authority. C3 on Sen2Cor is ×1.58 against production's ×1.68 on
  every row.
- **What 9/10 needs:** clear, normal, stained, algae, sediment and limited all SUPPORTED on fresh data. Bottom-risk stays
  NOT until a depth layer exists (the Navionics track).

## Files

Everything is in `scratchpad/stage12/`:

| Path | Contents |
|---|---|
| `PREREGISTRATION_STAGE12.md`, `FREEZE_STAGE12.json`, `ADDENDUM_*.md` | The frozen plan, its hashes and the addenda |
| `exp1/` | The interface experiment: guard sample, runner, per-scene results, `score.json` |
| `harm/` | The harmonisation fit, leave-one-pair-out validation, ACOLITE tandem runs, `score_tandem.json` |
| `corpus/` | The corpus driver, elevations, per-scene ACOLITE samples |
| `analysis/` | `reflectance.py`, `models12.py`, `classes12.py`, tables and JSON |
| `cert/` | The certification protocol, candidate builders, matching, `blind_sample.csv` and its hash |
| `tools/` | The ACOLITE runner with overrides, and the L1R harmoniser |

---

BEST WATER-REFLECTANCE CONFIGURATION: ACOLITE 20260421.0 (DSF, residual-glint correction, the FFSS sky-dome interface correction after AC; candidate K4) with surface pressure from each lake's USGS elevation, 20 m, and Sentinel-2C harmonised at the water-reflectance level (V-ρw)
RED-BAND RESIDUAL FIXED: NO
S2C HARMONIZED: PARTIAL
S2A/B/C PLATFORM-INVARIANT ENOUGH FOR CLARITY: NO
BEST CLARITY ENGINE AFTER CORRECTION: C3 refitted on ACOLITE reflectance (two red-band branches split on NDCI > 0), a single model with no routing: held-out ×1.47 (median |log| 0.169) against ×1.66 for today's production on the same rows, but only at the 76% of stations where ACOLITE retrieves water
CLEAR WATER ERROR: ×1.56 (median |log| 0.192), median −3.3 ft, class accuracy 0.75 (n 574; production ×1.97, −5.2 ft)
NORMAL WATER ERROR: ×1.27 (0.104), median +0.3 ft, class accuracy 0.64 (n 286; production ×1.31, +0.2 ft)
STAINED WATER ERROR: ×1.38 (0.140), median +0.9 ft, class accuracy 0.29 (n 173; production ×1.40, +0.9 ft)
LIMITED WATER ERROR: ×1.81 (0.257), median +1.0 ft, class accuracy 0.32 (n 173; production ×1.98, +1.3 ft)
ALGAL WATER ERROR: ×1.51 (0.178), median +1.0 ft (n 94, in-situ algal; production ×1.57, +1.2 ft)
SEDIMENT WATER ERROR: ×1.37 (0.136), median +0.6 ft (n 64, in-situ sediment; production ×1.27, −0.0 ft, so worse than production)
EXACT-FEET CAPABILITY: 0/10 (historical lake-held-out; feet are authorised for 15% of rows, and no class reaches 50% published coverage)
CLARITY-CLASS CAPABILITY: 1/10 (historical; clear and sediment PARTIAL; 24% Unknown; stained and limited recall 0.23–0.24)
BLIND EXTERNAL CERTIFICATION SET READY WITHOUT USER SURVEY: NO
CURRENT PATH TO 9/10: Readiness stays 2/10. First recover ACOLITE's 24% lost retrievals (pre-registered mask variants or a Sen2Cor-C3 fallback). Add a class-boundary uncertainty band so S2A/S2C scatter stops flipping classes. Find a signal for stained and limited water, the weakest classes on every input. Complete the blind set (≥ 400 observations, stained and cool-season water) from SYKE's full lake list plus agency records or a sealed never-analysed WQP tier. Then certify once, on that set and on P2's fresh data, against the Stage 10 bars.
