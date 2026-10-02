# Current Clarity Stage 12: pre-registration

Written 2026-09-30, before any Stage 12 value was computed. Its sha256, and those of `exp1/guard.json` and (when written)
`cert/CERT_PROTOCOL_STAGE12.md`, go into `FREEZE_STAGE12.json`. Anything changed after the freeze is logged there as a
timestamped addendum, with the reason, before the data it governs is examined.

**Out of bounds for the whole stage:**
- new Sector field observations of any kind (Michael's Guntersville survey stays an independent acceptance test);
- the P2 fresh holdout (2026 Guntersville agency values, the fresh national draw, field reports);
- Water Temperature;
- production Current Clarity (nothing is deployed);
- the Stage 11 dead ends, unless Stage 12 evidence changes a conclusion: C2RCC, C2X, P1-NIR, optical-regime routing
  as a goal in itself, Landsat or Sentinel-3 fusion, temporal median replacement, public-depth correction.

**Guntersville** means corpus set G, or any station inside the Stage 11 box (34.27–35.06 N, 86.42–85.60 W). It is used
for no selection in any part. Its rows are reported separately.

---

## 1. ACOLITE air–water interface experiment

**Candidates** (ACOLITE 20260421.0; everything not listed is identical to Stage 11's `BASE_SETTINGS`: DSF, `tiled`
with `fixed` fallback, residual glint correction on, 20 m, no ancillary data, default L2W mask, the same crop):

| Id | Setting |
|---|---|
| K0 | Stage 11 as run: `dsf_interface_reflectance=False` |
| K1 | `dsf_interface_reflectance=True`, `dsf_interface_option=default` (ACOLITE-RSKY-202102-82W, wind = ACOLITE default 2 m/s) |
| K2 | `dsf_interface_reflectance=True`, `dsf_interface_option=6sv` (the LUT's `romix+rsurf`) |
| K3 | `dsf_interface_reflectance=True`, `dsf_interface_option=ffss_toa` |
| K4 | `dsf_interface_reflectance=True`, `dsf_interface_option=ffss_boa` |

A candidate that fails to run on more than 20% of scenes is reported as not feasible.

**Data:**
- **Radiometric truth:** the Stage 11 AERONET-OC set, unchanged. That is 46 matchups at 5 sites (the first tile per job
  name), AERONET-OC Level 2.0 ρw on B01–B05 by nearest wavelength within 10 nm. K0 values are Stage 11's. Three scenes
  are rerun under K0 as a reproducibility check; if any band differs by more than 1e-4, K0 is rerun everywhere.
- **Inland turbidity guard:** `exp1/guard.json`, fixed before any Stage 12 run. It holds:
  - 60 corpus stations, one per lake, with a same-day pass and same-day in-situ turbidity, not Guntersville, drawn with
    seed 12;
  - plus the 11 non-Guntersville Stage 11 representative stations.
  Dogliotti FNU uses the production coefficients on each candidate's B04.

**Metrics per candidate:**
- per band B02–B05: median |log10(ρw_sat/ρw_AERONET)| and median bias;
- the pooled B02–B05 median |log|;
- valid-retrieval rate;
- share of ρw ≤ 0 in B02–B05;
- guard median |e_T|.

Paired comparisons with K0 use the same matchup-bands, with a matchup-block bootstrap (3,000 resamples, seed 12).

**Eligibility.** All of these must hold:
1. The B04 median |log| is lower than K0's, and the paired-difference CI excludes 0.
2. Each of B02, B03 and B05 has a median |log| ≤ K0's + 0.02.
3. The valid rate is ≥ K0's − 0.05.
4. The share of ρw ≤ 0 in B02–B05 is ≤ 2%.
5. The guard median |e_T| is ≤ K0's + 0.03.

**BEST** is the eligible candidate with the lowest pooled B02–B05 median |log|. Within 0.005 of each other, the
lower-numbered candidate wins. With none eligible, BEST is K0.

**RED-BAND RESIDUAL FIXED**, judged on BEST:
- **YES** if |B04 median bias| ≤ 0.05;
- **PARTIAL** if the B04 median bias is ≤ 0.7 × K0's (a reduction of at least 30%) but still > 0.05;
- **NO** otherwise.

Downstream Secchi is not computed for any candidate. Only BEST goes forward.

## 2. Sentinel-2C harmonisation

**Derivation data:** the Stage 11 tandem water pixels only (`stage11/tandem/tandem_pixels.npz`). That is 12 pairs, 27–32 s
apart. TOA comes from L1C (S2A N0511; S2C commissioning N9905/N9906), and BOA from C1 L2A (S2A; S2C in its 2026
operational reprocessing). Bands are B01–B12 without B10, with the Stage 11 §5 water mask. No Secchi, turbidity or
chlorophyll value enters.

**Model, per band b** (S2C → S2A-equivalent):

A_b = g_b · C_b + o_b, with an extra term + k · (C_B06 − C_B04) for B05 (the band-shape term).

- **Fit:** least squares, with every pair weighted equally (pixel weight 1/n_pair). Pixels with |A − C| more than 5
  robust SDs from the pair's median are excluded.
- **Two versions:**
  - **TOA**, for the ACOLITE path (applied to ACOLITE's L1R ρt; the harmonised S2C is then processed as S2A);
  - **BOA**, for the Sen2Cor production path.
- **Operational bands.** At TOA, only the bands whose Stage 11 production-L2A water ratio CI excluded 1 are applied
  operationally: B05, B08, B8A, B11 and B12. The commissioning visible-gain difference is not assumed to exist in
  operational L1C. At BOA (already the operational reprocessing), every fitted band is applied.
- **Production coefficients:** fitted on all 12 pairs. Validation coefficients: leave-one-pair-out.

**Validation (held-out pairs, leave-one-pair-out):**
- **Sen2Cor path.** The frozen P2 route (P1 / C3 / refused) on BOA pixels, S2A against BOA-harmonised S2C. Up to 4,000
  water pixels per pair (seed 12).
- **ACOLITE path.** BEST is run on S2A L1C, on raw S2C L1C, and on TOA-harmonised S2C L1R.
  - **Harmonisation modes.** V-full applies all bands, which emulates operational S2C by also removing the
    commissioning gain. V-op applies only the operational bands and is reported for context.
  - **Water.** A pixel counts if it is valid in both L2W outputs, has TOA NDWI > 0 on both, and is at least 180 m from
    anything that is not.
  - **Decisions compared.** The frozen P2 route on ACOLITE ρw, and (once Part 4 freezes) the Part 4 engine's class
    decision.
- **Flip rate:** the mean over pairs (equal weight) of the share of pixels whose decision differs. The per-pair median is
  also reported.
- **Residual band differences:** the median C/A ratio and C − A difference per band over held-out water pixels, on both
  paths.

**S2C HARMONIZED:**
- **YES** if the mean flip rate is < 5% on the Sen2Cor P2 route and on the ACOLITE-path P2 route (V-full), and the
  held-out median residual for B05, B8A, B11 and B12 is within ±3% (ratio) or ±0.0005 (difference), on both paths;
- **PARTIAL** if only one path is < 5%, or the flips pass but the residuals do not;
- **NO** otherwise.

**S2A/B/C PLATFORM-INVARIANT ENOUGH FOR CLARITY** is **YES** only if both hold:
- (a) the Part 4 engine's class decision flips on < 5% of held-out tandem pixels (ACOLITE path, V-full), with median
  |Δft| ≤ 0.25 ft;
- (b) in the corpus, for every platform with ≥ 30 rows, the held-out median signed log error differs from the other
  platforms' pooled median by ≤ 0.05, or its lake-bootstrap CI includes 0.

Otherwise it is **NO**.

## 3. The complete historical corpus

**Rows:** every Stage 11 corpus row dated ≤ 2025-12-31 (1,631 station-days, 1,015 lakes). Everything is computed on all
of them; Guntersville is reported apart and excluded from fitting and selection.

**Processing:**
- Rows are grouped by C1 item, and each item's L1C is found with the Stage 11 `l1c_for`.
- There is one ACOLITE run (BEST) per item and crop, where the crop is ±0.08° latitude and ±0.10° longitude around the
  item's first station. Stations of the same item inside that crop share the run.
- S2C scenes get the operational TOA harmonisation (production coefficients) and are processed as S2A. They are also
  processed raw, for the platform comparison.
- Sampling uses the Stage 11 ACOLITE sampler: the 60 m disk, ACOLITE's own L2W mask and at least 5 valid pixels.

**The reflectance is evaluated before any visibility metric exists.** `analysis/reflectance.py` writes
`reflectance.json`; the visibility scripts refuse to run until it exists.
- **R1:** the retrieval rate against Sen2Cor production.
- **R2:** e_T (Dogliotti on ACOLITE B04 against same-day in-situ turbidity), as median |e_T| and median e_T:
  - overall;
  - by Secchi class (clear ≥ 6 ft, normal 3–6, stained 2–3, limited < 2);
  - by in-situ type (clear, algal, sediment, mixed; the Stage 11 rules);
  - paired against Sen2Cor on common rows, with lake-bootstrap CIs.
- **R3:** the Stage 11 Part A split (radiometric against conversion share) with ACOLITE FNU.
- **R4:** median e_T by platform, raw and harmonised.

**Reflectance improved** if the paired median |e_T| is lower than Sen2Cor's with the CI excluding 0.

## 4. The simplest clarity model the new reflectance supports

**Inputs:** ACOLITE ρw (B02–B05, B11) and sun elevation. **Folds:** the Stage 11 five whole-lake folds (md5(lake) mod 5).
Every fitted model is fitted on training folds only.

**Candidates, in order of complexity:**

| # | Model | Fitted parameters |
|---|---|---|
| 1 | champion, frozen: 11.123 · FNU^−0.637 | 0 |
| 2 | P1, frozen physics | 0 |
| 3 | champion form refitted: log S = a + b · log FNU | 2 |
| 4 | N1: log S = a + b · log ρ665 | 2 |
| 5 | N2: log S = a + b · log ρ665 + c · log(ρ560/ρ665) | 3 |
| 6 | C3 form refitted (two branches on NDCI > 0) | 4 |
| 7 | C6 form refitted | 4 |
| 8 | P2 frozen (P1 / frozen C3 / refuse) | 0, but a router |
| 9 | Routed: the Stage 11 nested machinery | chosen per state |

The routed candidate takes each state's model from the inner folds, among 1–7, using the satellite §6 water types
computed from ACOLITE inputs. A state refuses if its best inner median |log| exceeds 0.25, and C3 serves algal water only
if it wins there.

**Selection:**
- **Primary metric:** held-out median |log10(Ŝ/S)| over non-Guntersville rows.
- **Eligible as a single engine:** coverage ≥ 90% of rows with a valid ACOLITE disk.
- **Best:** the lowest primary metric among eligible models.
- **Equivalence.** A simpler eligible model is equivalent to the best if the lake-bootstrap 95% CI (2,000 resamples,
  seed 12) of its median |log| minus the best's, on common rows, has an upper bound ≤ +0.010.
- **The engine is the simplest equivalent model.**
- **The C3 guard.** A C3-form engine is allowed only if, in satellite-algal water, its held-out median |log| is ≤ the best
  other model's + 0.01. Otherwise C3 is not eligible. C3 never becomes an unconditional algal fallback.
- **Routing is adopted only if** the routed system beats the engine by ≥ 10% (relative), with the lake-bootstrap CI of the
  difference excluding 0, coverage ≥ 70%, and every non-refusing state's choice stable in ≥ 4 of 5 folds.

**Errors reported per class for the chosen engine:**
- clear ≥ 6 ft, normal 3–6, stained 2–3, limited < 2;
- in-situ algal, sediment and mixed (the Stage 11 rules: chlorophyll ≥ 15 µg/L, turbidity ≥ 8 NTU/FNU);
- in each: median |log| (as a factor), median signed ft, coverage and n.

## 5. Exact feet against clarity class

**Classes:** Clear (≥ 6 ft), Normal (3–6), Stained (2–3), Severely limited (< 2), and Unknown (no valid ACOLITE disk,
or the engine refuses).

**When exact feet are shown.** The engine publishes feet only when the predicted class is authorised. Authorisation is
decided in the inner folds of each outer training set: class c is authorised if the inner-fold rows predicted as c have
median |log| ≤ 0.15 and |median signed| ≤ the class bar (clear 1.5 ft, normal 1.0, stained 0.75, limited 0.75).
Otherwise only the class is shown. The share of rows where feet are withheld but a class is given is reported.

**Two historical capability scores.** Each has seven capabilities, as in Stage 10: SUPPORTED 1, PARTIAL 0.5, NOT 0,
scaled to 10 and rounded. They are computed on lake-held-out historical rows. **They are not product readiness,** which
stays under the Stage 10 rule (fresh evidence only).

**Exact-feet capability** (rows in the true class where feet are published; coverage = published / all rows in the
class):

| Capability | SUPPORTED | PARTIAL |
|---|---|---|
| Clear | n ≥ 40; median signed in [−1.5, +1.5]; median \|log\| ≤ 0.15; coverage ≥ 70% | median signed in [−2.5, +2.5]; median \|log\| ≤ 0.20; coverage ≥ 50% |
| Normal | \|median signed\| ≤ 1.0; ≤ 0.15; coverage ≥ 70% | ≤ 1.5; ≤ 0.20; ≥ 50% |
| Stained | \|median signed\| ≤ 0.75; ≤ 0.15; coverage ≥ 70% | ≤ 1.0; ≤ 0.20; ≥ 50% |
| Limited | median signed in [−0.75, +0.75]; ≤ 0.20; coverage ≥ 70% | in [−1.0, +1.0]; ≤ 0.25; ≥ 50% |
| Algae (in-situ algal ∪ mixed) | \|median signed\| ≤ 1.0; ≤ 0.15; coverage ≥ 70% | ≤ 1.5; ≤ 0.20; ≥ 50% |
| Sediment (in-situ sediment) | \|median signed\| ≤ 1.0; ≤ 0.15; coverage ≥ 70% | ≤ 1.5; ≤ 0.20; ≥ 50% |
| Bottom-risk | NOT (no depth input) | |

**Clarity-class capability** (all rows in the true class; Unknown counts as a miss for recall):

| Capability | SUPPORTED | PARTIAL |
|---|---|---|
| Clear | recall ≥ 0.60; precision ≥ 0.75; Unknown ≤ 30% | recall ≥ 0.40; precision ≥ 0.60 |
| Normal | recall ≥ 0.60; precision ≥ 0.60 | recall ≥ 0.50; precision ≥ 0.40 |
| Stained | recall ≥ 0.60; precision ≥ 0.60 | recall ≥ 0.40; precision ≥ 0.40 |
| Limited | recall ≥ 0.60; precision ≥ 0.50; ≤ 10% called Clear | ≥ 60% called < 3 ft or Unknown; ≤ 10% called ≥ 4 ft |
| Algae | class accuracy ≥ constant + 0.10 in algal water; \|median signed\| ≤ 1.0 | class accuracy ≥ constant + 0.05 |
| Sediment | bright sediment called Clear ≤ 5%; class accuracy ≥ constant + 0.10 | called Clear ≤ 15% |
| Bottom-risk | NOT (no depth input) | |

Here "constant" is the accuracy of always predicting that water type's most common class, and "bright sediment" is
in-situ turbidity ≥ 20.

## 6. The blind external certification set

The protocol is written in `cert/CERT_PROTOCOL_STAGE12.md` and hashed into the freeze before any site or visit file is
fetched. It must fix:
- the sources;
- lake eligibility;
- the temporal and spatial matching;
- seasonal requirements;
- the per-class minimum counts (Stage 10's SUPPORTED minima: clear 40, normal 40, stained 60, algae 30, sediment 20,
  limited 25, for 215 in all);
- at least 100 distinct lakes;
- geographic diversity.

No Secchi value from any candidate source is read while the sample is built.

**READY WITHOUT USER SURVEY** is **YES** only if all of these hold:
- the protocol is hashed;
- a blind candidate sample exists, made of site-days with a valid production-gated Sentinel-2 pass whose Secchi values
  were never fetched;
- the blind-checkable minimums hold: ≥ 400 matched observations, ≥ 100 lakes, ≥ 20 states or provinces, and ≥ 15% of
  observations from October to April across ≥ 20 lakes;
- every class's expected count, using the Stage 11 corpus class shares as the planning prior, meets its minimum.

Otherwise it is **NO**, with what is missing.

## 7. The closing lines

Each comes from its section's rule:
- BEST WATER-REFLECTANCE CONFIGURATION: §1 BEST, plus the §2 harmonisation;
- RED-BAND RESIDUAL FIXED: §1;
- S2C HARMONIZED: §2;
- S2A/B/C PLATFORM-INVARIANT ENOUGH FOR CLARITY: §2;
- BEST CLARITY ENGINE AFTER CORRECTION: §4;
- the six per-class error lines: §4, for the chosen engine;
- EXACT-FEET CAPABILITY and CLARITY-CLASS CAPABILITY: §5, marked historical;
- BLIND EXTERNAL CERTIFICATION SET READY WITHOUT USER SURVEY: §6;
- CURRENT PATH TO 9/10: a plan, not a verdict. Product readiness stays under the Stage 10 rule.
