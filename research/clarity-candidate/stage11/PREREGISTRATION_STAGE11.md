# Current Clarity Stage 11: reflectance and sensor failure decomposition, pre-registration

**When it was written:** 2026-09-30, before any Stage 11 error was computed. It is hashed in `FREEZE_STAGE11.json`.

**What had been done before writing:**
- Only data discovery: what exists and where.
- The tandem-pair search and the downloads.
- Setting up the processors: ACOLITE, C2RCC/C2X, and the POLYMER licence check.

No error has been split by any factor defined here.

**Scope:**
- **Diagnostic only.** Production Current Clarity is not modified. No frozen Stage 10 file (P1, P2, C3, C6, the champion) changes.
- **No Sector field observations.** The Stage 10 fresh holdout is untouched:
  - no agency record dated 2026 or later enters any Stage 11 file;
  - the new national sites are chosen so that they cannot overlap the future P2 fresh national draw (§2.3).
- **POLYMER is not run.** Its licence counts use as acceptance and restricts the software to non-commercial research. That decision belongs to the product owner.

## 1. The retrieval chain and where truth enters

Production Current Clarity runs this chain:

TOA (L1C) → atmospheric correction (Sen2Cor L2A) → surface reflectance ρ(λ) → turbidity (Dogliotti FNU on B04, blended with B8A) → Secchi (champion: Ŝ = 11.123 · FNU^−0.637 ft)

Truth enters at three points:

| Truth | Source | What it can judge |
|---|---|---|
| Water-leaving reflectance (Lwn → ρw = π · Rrs) | AERONET-OC Level 2.0: Lake_Erie, Lake_Okeechobee, Palgrunden, Chesapeake_Bay, WaveCIS_Site_CSI_6 | Atmospheric correction, glint and adjacency, directly |
| In-situ turbidity (NTU/FNU), same day | Agency records (WQP) | Radiometry plus retrieval, separated from the Secchi conversion |
| Secchi depth | Agency records (WQP) | The whole chain |

## 2. Corpus (historical only; every date ≤ 2025-12-31)

1. **G:** the Guntersville historical matchups (Stage 6), all 87 Secchi rows. Bottom-risk and vegetation rows are kept, and labelled.
2. **N:** the Stage 7 national rows (669).
3. **F:** the Stage 8 fresh national rows (412), historical now.
4. **E: the expansion**, all dated 2017-01-01 to 2025-12-31.
   - **E-AL: ADEM** (WQP org 21AWIC). Every lake or reservoir Secchi record in Alabama.
   - **E-TVA: TVA's reservoir monitoring** records in WQP, under whichever organisation identifier the WQP organisation search returns for TVA.
   - **E-NAT: a new national draw** from the Stage 8 pool (`q9/wqp/secchi.csv`).
     - **Site eligibility:** sites in no earlier file, and with no Secchi record dated 2025-01-01 or later. This keeps them out of the P2 fresh national pool, which needs records dated 2026-04-01 or later.
     - **Draw rules:** seed 20261111, at most 3 rows per site, one per site-month, and no state above 12%.
     - **Priority:** rows with a same-day turbidity or chlorophyll record at the site are drawn first. Up to 4,000 station-days.
   - **Paired truth:** turbidity (NTU, FNU, JTU excluded) and chlorophyll a (µg/L; the Stage 7 unit rules) are fetched same-site, same-day for every matched row.
   - **Excluded:** Guntersville records dated 2026 or later are excluded everywhere.
5. **Read-out:** `stage6/extract.py --max-dt 1`, unchanged. It takes the best pass per observation, requires ≥ 5 valid pixels, and applies the production gates on the 60 m disk.
6. **Lake groups (for every held-out validation):** sites are joined by single linkage within 5 km. A group is one "lake". Folds are formed from whole groups (5 folds, `md5(groupId) % 5`).
7. **Minimum per reported cell:** n ≥ 10 rows from ≥ 3 lakes. Anything smaller reads INSUFFICIENT.

## 3. Part A: error decomposition (primary)

For the champion, with Ŝ = 11.123 · FNU^−0.637, the log error splits exactly:

  e_S = log10(Ŝ / S) = −0.637 · e_T + e_C

where:
- e_T = log10(FNU_sat / T_insitu) is the radiometric-and-retrieval error;
- e_C = log10(Ŝ(T_insitu) / S) is the conversion error: the champion's own formula applied to in-situ turbidity.

**Rows:** those with same-day in-situ turbidity. Primary: satellite Δt = 0; secondary: Δt ≤ 1.

**What is reported:**
1. Var(e_S) and its split: 0.637² · Var(e_T), Var(e_C), and −2 · 0.637 · Cov(e_T, e_C). Also the share of median |e_S| that remains when either term is set to 0.
2. **The best achievable conversion.** A lake-held-out refit of log S on log T_insitu, and log S on log T_insitu + log chl. This is the floor a perfect turbidity would still leave.
3. **Attribution inside e_T**, using satellite-observable covariates only:
   - **AC / aerosol:** the Sen2Cor AOT at the station.
   - **Glint:** the glint angle from solar and viewing geometry, and ρ(B11).
   - **Adjacency:** the distance from the station to the nearest non-water pixel of the scene's own SCL/NDVI mask, within 2 km.
   - **Platform:** S2A, S2B or S2C.
   - **Optical water type:** the §6 classes.
   - **Method:** the in-situ unit (NTU against FNU), for context.
   - **How:** Shapley R² over these blocks, lake-held-out, for e_T, e_C and e_S.
4. **The primary remaining error source** is the block with the largest Shapley share of Var(e_S). The blocks are radiometric (AC, glint, adjacency, platform), water type, conversion, and residual/match-up noise.
   - If the largest share is not at least 1.25 times the next, the line reads "shared between X and Y".

## 4. Part B: atmospheric-correction paths

**Processors compared:**
- Sen2Cor (production L2A, Earth Search C1);
- ACOLITE DSF (pinned release, glint correction on, no ancillary);
- C2RCC-Nets and C2X-Nets (SNAP, pinned version).

**Scenes:**
- **AERONET-OC matchups:**
  - S2 overpass within ±60 min of a Level 2.0 record, scene cloud ≤ 30%, and a valid Sen2Cor disk at the site;
  - up to 10 per site, newest first, 2017–2025.
- **Representative corpus scenes:** 3 per in-situ class:
  - clear: Secchi ≥ 2.5 m and chl < 5;
  - normal: 1–2.5 m;
  - stained: 0.6–0.9 m;
  - algal: chl ≥ 20 µg/L;
  - sediment: T ≥ 15 NTU and chl < 10;
  - selection: same-day turbidity required, distinct lakes, newest first;
  - plus Guntersville's own scenes that cover ≥ 3 stations.

**Metrics** (60 m disk median, the same pixels for every processor):
1. **Against AERONET-OC**, on the S2 bands the AERONET-OC bands resolve (B01–B05, nearest wavelength, with no band shifting beyond the nearest centre):
   - the median absolute log10 ratio;
   - the median bias;
   - the valid-retrieval rate.
2. **Against in-situ turbidity:** Dogliotti FNU computed with the same code from each processor's ρw at B04/B8A; median |e_T|.
3. **Against Secchi:** the frozen P1 run on each processor's ρw; median |log error|.
4. **Plausibility:** the share of negative ρw in B02–B05, and ρw(B11).

**Best-path rule:**
- A processor is BEST if both hold:
  - (a) its median absolute log error against AERONET-OC over B02–B05 is ≥ 20% lower than Sen2Cor's, with the station-block bootstrap 95% CI of the difference excluding 0;
  - (b) it is not worse than Sen2Cor on metric 2.
- If no processor qualifies, the path is "Sen2Cor (no processor demonstrably better)".
- With fewer than 15 AERONET-OC matchups in total, the line reads "UNRESOLVED (insufficient radiometric truth)".

## 5. Part C: the Sentinel-2A/2C tandem

**Data:** the 12 clear pairs of 12–18 December 2024, with S2C 27–32 s behind S2A on the same tile. S2A is N0511 L1C; S2C is the original commissioning products, N9905/N9906 (Google bucket). Earth Search C1 L2A for both is the production path; its S2C L2A is the 2026 operational reprocessing.

**Water pixels:**
- the Sen2Cor SCL water class on both passes;
- NDWI (B03, B08) > 0 on both;
- at least 3 pixels (60 m) from any non-water pixel;
- ρ(B11) < 0.03 at TOA on both;
- matched pixel by pixel on the tile grid.

**Measures, per band B01–B12:**
- median S2C/S2A ratio and median difference at TOA (L1C), and in BOA (C1 L2A);
- the same through ACOLITE on both L1C products (one AC applied to both, which isolates the sensor);
- noise: the robust standard deviation of B11 over homogeneous water, and the 3×3 local standard deviation.
- Bootstrap over scenes (resampling scenes) for 95% CIs.

**The downstream test.** Run the frozen P2 routing and the champion on both passes, pixel by pixel. Report the route-flip rate and the champion Δft.

**Harmonisation rule:**
- **REQUIRED = YES** if both hold:
  - (a) any of B02, B03, B04 or B05 has an S2C/S2A water ratio outside 0.97–1.03 at TOA or in production L2A (CI excluding the band), or B11 differs by > 0.001;
  - (b) the difference moves the champion by ≥ 0.5 ft median, or flips ≥ 10% of P2 routes, over tandem water.
- **NO** if neither (a) nor (b) holds.
- **UNKNOWN** if fewer than 4 usable pairs, or if (a) and (b) disagree.

**Attributing the Stage 10 S2C routing pattern:**
- **Sensor:** a TOA difference in tandem.
- **Processing baseline:** a difference between S2C N9905 L1C put through ACOLITE and the reprocessed C1 L2A, relative to S2A.
- **Atmospheric correction:** a Sen2Cor BOA difference that does not appear at TOA.
- **Downstream logic:** none of the above, while P2's route still flips between passes. For example, P2's B11 residual test reacting to noise or to day-to-day haze.

## 6. Part D: the optical-water-type classifier (satellite-only; no lake identity)

**Inputs:** from the production L2A disk:
- NDCI = (B05 − B04) / (B05 + B04);
- FNU (Dogliotti, production);
- ρ(B11);
- sun elevation;
- B02–B05.

**Classes, in this order:**
1. **unsupported:** sun elevation < 20°; or any of B02–B05 ≤ 0.001 or ≥ 0.15; or ρ(B11) > 0.02; or ρ(B05) < 0.003 while ρ(B04) > 0.02 (an inconsistent red edge).
2. **mixed algae/sediment:** NDCI > 0.03 and FNU ≥ 8.
3. **algal-dominant:** NDCI > 0.03 and FNU < 8.
4. **mineral/sediment-dominant:** NDCI ≤ 0.03 and FNU ≥ 8.
5. **clear/open (low constituent):** everything else.

The thresholds are the existing production NDCI threshold (0.03) and the Stage 7 sediment turbidity (8). Nothing is fitted here.

**Truth classes** (rows with same-day chlorophyll and turbidity): chl ≥ 15 µg/L and T ≥ 8 → mixed; chl ≥ 15 → algal; T ≥ 8 → sediment; otherwise clear.

**Reported:** the confusion matrix, per-class recall and precision, and the balanced accuracy against a constant-class baseline.

**The classifier is USEFUL** if balanced accuracy ≥ 0.50 and each of the algal, sediment and clear classes has recall ≥ 0.40.

## 7. Part E: models inside each optical state (held-out lakes)

**Models:**
- champion (fixed);
- P1 (frozen physics);
- C3 and C6 (refitted on training lakes only, in each fold, with their Stage 7 and Stage 8 feature definitions);
- **P1-NIR**, a new, physically justified variant for turbid water: the frozen P1 code with its QAA reference moved from 704 nm (B05) to 783 nm (B07).
  - **Why 783 nm:** pure water absorbs about three times more strongly there than at 704 nm. The assumption a(λ₀) ≈ a_w(λ₀) still holds in sediment-laden water, where it can fail at 704 nm.
  - **Constants:** a_w(783) is the value at 783 nm in the pure-water absorption table shipped with the pinned ACOLITE release. It is recorded in `FREEZE_STAGE11.json` addendum A before any P1-NIR output is computed. bbw is Morel 1974, as in P1.
  - **Everything else is P1's code and guards,** except that the reflectance floor applies to B07 (ρ ≥ 0.003) instead of B05.
  - **Coverage:** evaluated on every row that has B07; used by routing only if it wins a state.

**Held-out evaluation:**
- **Folds:** 5 lake-group folds over G + N + F + E.
- **Per state, per model:** median signed error (ft), MAE, median |log error|, and class accuracy.

**Routing:**
- **Selection:** within the training folds, for each state, choose the model with the lowest median |log error|, and apply it to the held-out fold. Nested, so no held-out row chooses its own model.
- **Refusal:** a state whose best training model has a median |log error| > 0.25 refuses (refusal is honest).
- **C3 in algal water:** C3 can serve algal water only if it wins there; it is never an automatic fallback.

**ROUTING SUPPORTED = YES** only if all hold:
- (a) the routed system's median |log error| on held-out lakes is ≥ 10% lower than the best single model's, with the lake-block bootstrap CI of the difference excluding 0;
- (b) the same model is chosen for each non-refused state in ≥ 4 of 5 folds;
- (c) coverage (non-refused share) ≥ 70%.

Otherwise NO.

## 8. Part F: multi-sensor evidence

**Landsat 8/9** (Collection 2 L2 surface reflectance, Planetary Computer):
- **Matchups:** same day as the S2 pass, or ±1 day; QA_PIXEL water; the 90 m disk (3×3 pixels).
- **Turbidity:** Dogliotti FNU from OLI B4 (655 nm) and B5 (865 nm), with the same coefficients as production.

**Sentinel-3 OLCI WFR L2** (Planetary Computer):
- **Where:** stations with ≥ 600 m of water in every direction (from the S2 mask); within ±1 day.
- **What:** WQSF-valid pixels. TSM_NN, CHL_NN, KD490_M07 and the Oa08 (665 nm) reflectance.

**Tests:**
1. Agreement between the S2 FNU and the second sensor's FNU (or OLCI's TSM), as a log ratio.
2. Whether rows where the two sensors agree (|log ratio| ≤ 0.15) have a lower median |e_S| than rows where they disagree.
3. Whether the mean of S2 and Landsat FNU gives a lower median |e_T| and |e_S| than S2 alone.

**WORTH PURSUING = YES** if either holds:
- (i) the agree set's median |e_S| is ≥ 25% lower than the disagree set's, with ≥ 30 rows in each and a bootstrap CI excluding 0;
- (ii) the fused estimate lowers median |e_S| by ≥ 10% (CI excluding 0) on ≥ 50 rows.

Otherwise NO.

## 9. Part G: temporal consistency

**Data:** for every corpus row, the production-gated FNU at the same 60 m disk on every pass within ±10 days (same extractor).

**The outlier rule.** A row is a radiometric outlier if all hold:
- ≥ 2 other valid passes;
- |log10 FNU_t − median(log10 FNU of the others)| > 0.30, a factor of 2;
- the others agree among themselves (median absolute deviation ≤ 0.15).

**Reported:**
- the flag rate;
- median |e_S| for flagged against unflagged rows;
- the change in error when a flagged value is replaced by the others' median.

**USEFUL** if the flagged median |e_S| is ≥ 1.5 times the unflagged, and replacement lowers it by ≥ 20%, on ≥ 20 flagged rows.

## 10. The closing lines (rules fixed now)

- **PRIMARY REMAINING ERROR SOURCE:** from §3.4.
- **BEST ATMOSPHERIC CORRECTION PATH:** from §4.
- **SENTINEL-2C HARMONIZATION REQUIRED:** from §5.
- **OPTICAL-REGIME ROUTING SUPPORTED:** from §7.
- **MULTI-SENSOR FUSION WORTH PURSUING:** from §8.
- **ESTIMATED PATH TO 9/10:** a plan, not a verdict.
  - Readiness stays at 2/10 under the Stage 10 rubric, because no fresh evidence exists.
  - The path names the capabilities, the evidence each needs, and the Stage 11 findings that change what to build.
