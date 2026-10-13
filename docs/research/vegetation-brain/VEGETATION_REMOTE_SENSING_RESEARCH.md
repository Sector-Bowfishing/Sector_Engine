# Vegetation Brain — Remote Sensing Research

**RESEARCH ONLY. Proposed Brain.** Two evidence streams: (1) a literature review whose grades are **[V]** snippet-level, **[B]** background, **[U]** extrapolation (the reviewing agent read search summaries, not full papers); (2) an **empirical test run in this campaign** against real survey data (`Sector_Research_Data/vegetation-brain/notes/04_empirical_sentinel2_test.md`, reproducible scripts). **Where they disagree, the empirical result wins.**

## 1. Bottom line
1. Sentinel-2 maps **plants that reach or float on the surface** well in clear water, and does **not** map plants below the surface in any test we ran.
2. NDVI/NDAVI/FAI are **surface-canopy** indices. NIR is absorbed within centimetres of water [B], so these indices cannot see submerged canopy — consistent with the empirical failure.
3. The existing Sector surface-grass rule (`NDVI ≥ 0.30`, from Clarity) is a good *recall* detector for surface mats but has a **9.9 % per-pixel false-positive rate on open water** at single date. The cell-level re-score (note 05) shows the shipped-style cell vote plus pass acceptance gives precision 0.92 / F1 0.96 on Snohomish (only 60 positive cells, 54 in one lake) — but cell recall on Florida surface points is only **0.32** single date.
4. Cross-lake and cross-region performance is heterogeneous (PNW polygons AUC 0.98; Florida points AUC 0.65 shore-matched), so plan per-regime calibration.

## 2. Empirical results (this campaign)

Ground truth: **Snohomish County WA** dated field polygons (5 small clear/mesotrophic lakes, Jul–Aug 2023, Roesiger 2021) and **FL FWC LTM** plant point intercepts (7 lakes, presence-only). Sentinel-2 via Earth Search STAC `sentinel-2-c1-l2a` (2022 lakes fall back to `sentinel-2-l2a`; offset trap documented in the note). Primary metrics use **shore-distance matched** negatives because shoreline adjacency flatters every index (unmatched NIR alone reached AUC 0.998 in the PNW).

| Class (region) | Best index | AUC (shore-matched) | Other |
|---|---|---|---|
| Floating-leaf beds (PNW) | NDAVI | **0.995** | FAI 0.992, NDVI 0.982; best-threshold F1 0.96–0.97, IoU 0.92–0.95; leave-one-lake-out F1 0.94–0.97 |
| Surface floating + emergent (FL) | FAI | 0.67 | NDVI 0.66; recall at Sector rule 0.60 (single date), 0.74 (3-mo max composite) |
| Submerged (PNW mixed assemblages) | NDAVI | 0.77 | best-threshold F1 0.74 vs 0.667 no-skill |
| Submerged (FL submersed-only points) | FAI | 0.68 | below chance (AUC <0.5) in several lake/depth strata |

**Sector rule `NDVI ≥ 0.30` (exact Clarity arithmetic):**
- PNW floating-leaf: recall 0.993; false-positive rate on open water 9.9 % (single date), 31.7 % (3-month max composite); precision 0.49 at raw prevalence, 0.73 when negatives are shore-matched.
- Florida: recall 0.60 floating, 0.60 emergent, **0.045 pure submersed**; recall falls with distance from shore (0.85 within 30 m → 0.35 beyond 120 m) and with depth (submerged recall 9.6 % → 0.5 % from 0.6–1.2 m to >3 m).
- Recall is genuine only for the **surface-reaching** canopy; the 0.585 "submerged" recall in the PNW comes from mixed assemblages that include floating-leaf species.

**Composite vs single date:** a 3-month max composite does not improve ranking (AUC 0.982 → 0.960) and roughly triples false positives, though it raises recall (FL 0.60 → 0.74). Use composites only when a good same-week scene is unavailable; test median/persistence instead (in progress).

**Learned upper bound:** a gradient-boosted model on 12 spectral features, leave-one-lake-out, gets PNW surface AUC 0.71–0.998 (4/5 lakes >0.98), FL surface 0.57–0.72, and **does not rescue submerged** (FL 0.41–0.79; most lakes at chance).

**Limits of the test:** 5 small PNW lakes + 7 FL lakes; FWC presence-only (precision/FPR on FL not meaningful); survey–image gaps 1–18 days; no Secchi, so clarity effects are confounded with label type and region; autocorrelated pixels so no confidence intervals. Read the full limitation list in the note before quoting numbers.

### 2b. Cell-level re-score and sonar lake-level test (note 05; replica of Clarity's code, truncated window, some post-filters missing)

| Test | Result |
|---|---|
| Snohomish, 50 m cells, `gfrac ≥ 0.5`, closest clear date | recall 1.00, precision 0.54, F1 0.70, IoU 0.54 (one bad scene — Storm 2023-08-18 — gives 39 false cells) |
| Same, Sector-style pass acceptance (scene must read ≥50 % of non-grass water) | precision **0.92**, F1 **0.96**, IoU 0.92 |
| Same, median of N clear dates ≥0.5 | precision 1.00, F1 1.00 (zero false cells; tiny positive sample) |
| Votes ≥2 of N / second-highest / max | precision 0.40 / 0.40 / 0.21 — weak filters |
| Sector 40 m shore erosion | leaves 49 % of whole-lake truth unreachable; the bed-to-bank strip recovers it (whole-lake F1 0.92) |
| FL points, cell recall on surface points | **0.32** single date; 0.43 median, 0.48 votes≥2, 0.54 max (background flag rate 0.4–0.6 %); submersed-only cells 3–8 % |
| FWC **lake-level sonar** (PAC/PVI, 130 lake-years, 50 lakes) | cell grass fraction Spearman **0.43 with PVI**, 0.35 with PAC; AUC for PVI ≥20 vs <5: **0.79** (cell), 0.84 (pixel NDVI share, FAI q90); PAC ≥50 vs <20: 0.65 |
| Canopy/water-column proxy | grass cells as share of lake: 1.5 % (mean biovolume 0.15–0.25), 2.8 % (0.25–0.4), 10.2 % (0.4–0.6), 12.6 % (0.6–1.0): Sentinel-2 + rule sees beds whose mean canopy reaches ≳40 % of the water column (lake-level proxy, not a pixel threshold) |

**Takeaways:** (1) the cell vote + pass acceptance + temporal persistence clean the false positives of the pixel rule on clear-water lily beds; (2) persistence needs median-style rules, not "≥2 of N"; (3) recall on Florida emergent/floating points is poor at 50 m cells (a point is one pixel in a ~44 m cell); (4) the rule tracks sonar *volume* moderately (ρ≈0.4–0.5) and *area* weakly; (5) the FWC pixel-level BioVolume ImageServers (2015–2023) are listed but **every request hangs** — pixel × depth sonar truth could not be obtained.

## 3. Literature findings (graded)

| Topic | Finding | Grade |
|---|---|---|
| Class ranking | Emergent > floating-leaved > submerged in every multi-class study; 4-lake Chinese Sentinel-2 Res-U-Net, point-validated: emergent 91 %, floating-leaved 78 %, submerged 59 % | [V] |
| Floating mats | Hyacinth / primrose RF class accuracy 79–95 %, OA ~90 % | [V] |
| Species | Multispectral bands could not separate Eurasian watermilfoil from other SAV; hyperspectral could; drone 6-band EWM OA 76.7 % | [V] |
| Detection depth | One WASI-2D Sentinel-2 study: reliable to ~2.5 m at Secchi 4.2 m | [V] one lake |
| NIR physics | Water absorbs NIR within ~10–15 cm; red-edge ~20–60 cm; SWIR mm–cm; so NIR/SWIR indices see only surface canopy; blue/green carry bottom signal | [B] |
| NDAVI / WAVI | NDAVI best at low density (FC <40–50 %), WAVI above — both rely on NIR | [V] |
| Atmospheric correction | Over inland water errors can exceed 100 % in red and 1000 % in NIR; Polymer and C2RCC best | [V] Warren 2019 |
| Radar | L-band PALSAR 83–84 % vs C-band 61–62 % for flooded marsh; open-water SAV and floating-leaved essentially invisible to SAR | [V]/[B] |
| NAIP | 1 m 4-band, 2–3 yr cycle; no aquatic-vegetation validation paper found | [B]/negative |
| Transfer | Cross-site classifier accuracy dropped (90 % vs 84 %), aquatic veg hardest | [V] wetland |
| Bloom vs plant | FAI/NIR high for both; no validated discriminator | negative |
| Hydrilla in Florida | 2025 Remote Sensing 17(11):1894 introduces a Sentinel-2 hydrilla index — **not read** | lead |

## 4. Index guide (what to use for what)

| Index | Use | Evidence |
|---|---|---|
| NDAVI (B8−B2)/(B8+B2) | surface-reaching floating/emergent presence | best on PNW floating-leaf (0.995) |
| FAI (B8 − baseline B4→B11) | mats and topped-out canopy; best FL surface/submerged AUC (0.67/0.68) | works, but also flags blooms |
| NDVI | continuity with Clarity; hazard: dark-water false positives | 0.982; 9.9 % FPR at 0.30 |
| Red-edge NDRE | weak in tests (0.81 PNW surface; 0.61 submerged); keep as bloom-vs-plant discriminator candidate | tested weak |
| Lyzenga depth-invariant, WASI inversions | only route toward bottom-visible SAV; not yet tested here | [B] |
| NDWI/MNDWI | water mask, haze rejection | — |
| Sentinel-1 VV/VH, JRC seasonality | emergent/flooded-terrestrial candidate zones, cloud-free | [V] |

## 5. Practical gotchas confirmed in testing or code
- **Reflectance offset trap:** `sentinel-2-c1-l2a` COGs need `DN×1e-4 − 0.1`; `sentinel-2-l2a` already has it removed — applying it twice silently doubled values and ruined the first test pass. `sentinel-2-c1-l2a` has no 2022 scenes (queried 2026-10-13).
- **Dark water:** red/NIR reflectance ≈0.005 makes NDVI unstable; Clarity's rule has a `max(1e-6, …)` denominator, not a floor — add a dark-water guard and keep the pass-acceptance logic.
- **Shore contamination:** 0–30 m band is contaminated by land adjacency; always shore-match when validating.
- **Survey–image timing:** floating mats move in days; hydrilla changes in weeks; hold survey–image gap ≤7 d for scoring.

## 6. Recommended v1 observer (surface-reaching only)
1. Water mask from polygons + JRC; 1-pixel shore erosion by lake class; refuse narrow arms (<30 m) as `TOO_NARROW`.
2. Per-scene: SCL mask (cloud, shadow, cirrus, snow); NDAVI + FAI + NDVI + SWIR gate; dark-water guard.
3. Cell vote at ~50 m (fraction of plant-flagged pixels), not pixel labels.
4. Cloud robustness: persistence (≥2 of N dates) or median composite over 30–45 d — max composite only as a recall fallback, flagged.
5. Bloom ambiguity flag where FAI high and red-edge/NDCI pattern or phenology favours cyanobacteria.
6. Calibrate thresholds per regime against NLA/FWC/survey; ship uncalibrated lakes with capped confidence.

## 7. What remains unknown
Bottom-visible SAV mapping with depth-invariant indices (untested); clarity stratification (no Secchi data in test); turbid reservoirs (no ground-truth polygon test yet); cell-level precision on turbid/Southern lakes (Snohomish has only 60 positive cells); pixel-level sonar × depth truth (FWC BioVolume services hung); winter/dormant emergents; ice.
