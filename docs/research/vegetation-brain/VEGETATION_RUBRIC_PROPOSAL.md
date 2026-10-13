# Vegetation Brain — Proposed Maturity Rubric

**RESEARCH-ONLY. No official Vegetation Brain score exists and none is published here.** The numbers below are a *proposed-maturity estimate* for planning, derived from artifacts in this campaign. They must not be written into any score history, Ops screen, or customer surface.

**Production philosophy:** overall ≥ **8.0** and every **critical** dimension ≥ **7.5**. Score ladder: `VEGETATION_SCORE_LADDER.md`.

## 1. Dimensions, weights and criticality

| # | Dimension | Weight | Critical? | What "7.5+" means |
|---|---|---|---|---|
| 1 | **Coverage** — share of fleet lakes with a current usable vegetation output | 1.0 | No (rollout metric) | ≥ ~85 % of lakes with polygons produce outputs with explicit refusals for the rest |
| 2 | **Source authority** — provenance quality of observations & truth | 1.0 | **Yes** | Observer rests on a documented open sensor with a validated method; authoritative surveys ingested per region |
| 3 | **Spatial accuracy** — cell registration, shoreline handling, resolution fit | 1.0 | **Yes** | Cell-level localisation error measured and acceptable; narrow arms and shoreline handled; geometry flags honoured |
| 4 | **Vegetation presence accuracy** | 1.5 | **Yes** | Pre-registered precision/recall/IoU on independent truth across ≥5 regions; low open-water false positives |
| 5 | **Density accuracy** | 1.0 | **Yes** | 4-class weighted-kappa and within-one agreement against NLA/FWC/polygons per regime |
| 6 | **Seasonality** — onset/peak/dieback + cloud-gap expectations | 1.0 | No | Prior beats naive climatology by a pre-registered margin per management regime |
| 7 | **Submerged detection** | 1.0 | **No, only while no observed-submerged claims are made; becomes Yes if any are** | Observed submerged restricted to a validated clarity/depth envelope; potential zone calibrated against sonar/survey |
| 8 | **Validation** — independence, breadth, pre-registration | 1.5 | **Yes** | Independent truth, leave-one-lake/region-out, calibrated confidence, negative controls |
| 9 | **Confidence & provenance** — evidence tier, age, refusal reasons on every cell | 1.0 | **Yes** | All outputs tiered, dated, refusal-coded; weakest-upstream confidence propagation |
| 10 | **Fleet scalability** — cost, automation, geometry, clarity inputs | 1.0 | No | Daily/weekly fleet run on open data within budget; clarity/depth inputs available |

Overall = weighted mean (sum of weights 11.0).

## 2. Proposed current maturity (2026-10-13, research only)

| # | Dimension | Est. | Basis |
|---|---|---|---|
| 1 | Coverage | **1.0** | No lake yields vegetation output; polygons exist for 599/621; observer pattern exists in Clarity |
| 2 | Source authority | **3.5** | Open sensor + authoritative truth identified and downloaded (NLA 2017, FWC LTM, Snohomish); no operational authoritative feed; reliance on request-only agencies for big reservoirs |
| 3 | Spatial accuracy | **2.0** | 50 m cell design only; shoreline contamination observed (0–30 m band); no localisation test; 22 lakes lack polygons; 3 suspect polygons |
| 4 | Presence accuracy | **3.0** | Strong in clear PNW floating-leaf (AUC 0.98–0.995, F1 0.94–0.97 LOLO; cell precision 0.92 with pass acceptance) but 5 small lakes / 60 positive cells; FL surface AUC 0.65–0.67 matched, pixel recall 0.60, **cell recall 0.32**; 9.9 % pixel open-water FPR for Clarity's rule; lake-level sonar ρ 0.43 |
| 5 | Density accuracy | **1.0** | Not measured; design and cutoffs are estimates |
| 6 | Seasonality | **2.0** | Priors from literature (partly verified); seasonal-prior accuracy of 65–75 % is a hypothesis; no back-test; no US NDVI phenology curves |
| 7 | Submerged detection | **1.0** | Tested: not detectable with Sentinel-2 indices or a learned model; potential-habitat design only (Canfield-based, wide CI); sonar test pending |
| 8 | Validation | **3.0** | Two independent datasets, one reproducible cross-region test with honest limits; no pre-registration, no density/seasonal validation, no turbid-reservoir truth |
| 9 | Confidence & provenance | **3.0** | Tier/refusal model designed and aligned with Sector doctrine; nothing implemented |
| 10 | Fleet scalability | **4.0** | Open STAC data proven by Clarity; polygons for 599; compute modest; clarity and depth inputs absent |

**Weighted overall ≈ 2.4 / 10** (Σ = 26.5 / 11). Critical dimensions (2, 3, 4, 5, 8, 9) range 1.0–3.5; **minimum 1.0 (density)** — all far below the 7.5 gate. If an observed-submerged claim were added, dimension 7 (1.0) would also become critical.

## 3. What moves each number (shortest path to the gate)

| Dimension | Next artifact | Expected effect |
|---|---|---|
| Presence (4) | Cell-level re-score of the shipped rule; NLA-2017 × S2 across 47 lakes + 17 negative controls; persistence composite | 3 → 5 |
| Density (5) | Calibrate cover fractions vs NLA codes and Snohomish density polygons | 1 → 4 |
| Validation (8) | Pre-registered V1–V3 (see Validation Strategy), leave-region-out | 3 → 6 |
| Spatial (3) | Localisation test, shoreline/narrow-arm refusal, geometry fixes | 2 → 5 |
| Provenance (9) | Implement tier/refusal schema in an offline prototype | 3 → 6 |
| Seasonality (6) | S2/Landsat 2017–2025 back-test of the GDD prior | 2 → 5–6 |
| Submerged (7) | Sonar-truth envelope; potential-habitat calibration | 1 → 3–5 (never 8 without sonar/survey ingestion) |
| Coverage / scalability (1, 10) | Fleet shadow run; Clarity-input wiring | 1 → 6, 4 → 6 |

## 4. Anti-gaming rules
- Scores are computed by script from artifacts; no hand edits.
- A capability the Brain declines to provide scores as built (1), not as "N/A = high".
- Fleet-wide numbers use lake-level bootstrap, not pooled pixels.
- No dimension may be credited from satellite-vs-satellite comparisons.
- Any non-research publication needs a separate sign-off outside this campaign.
