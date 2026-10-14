# Lake Brain: per-lake 3DEP shoreline slope (scoping note)

**What this is: SHORELINE MORPHOLOGY CONTEXT.** A static, per-lake description of the bank beside the water, from the USGS 3DEP elevation model. It says how steep the shore is, so that a level change can be read as a small or a large horizontal shift of the waterline. **It is not bathymetry and not depth truth.** It sees the bank above the waterline (the DEM stores a flat water surface). **The Depth Brain owns depth**, effective depth and anything below the waterline. Lake Brain publishes this only as lake context, always labelled a proxy.

Written 2026-10-13. Scoping only: nothing was downloaded or computed from 3DEP in this task, no profile was changed, no code was written.

## 1. What exists in the repo and in the research

| Item | Where | State |
|---|---|---|
| Method and script | `research/lake-brain/context_shore_dem.py` (main checkout, research branch `docs/lake-brain-research`) | Samples the 3DEP seamless DEM `ImageServer/getSamples` at outward offsets 10, 30, 60, 100 m from the polygon shoreline, about 700 points per lake. Per lake: median and quartile slope (degrees) from 10 to 60 m, share flatter than 2 degrees, share steeper than 8 degrees, median horizontal run per vertical foot, bank rise at 30 m. Polite: 1 request per second, at most 1000 points per request. |
| Results (not in Git) | `Sector_Research_Data/lake-brain/context/shore_dem.json` (5 pilots), `shore_dem_val_a.json` (26 lakes), `shore_dem_val_b.json` (25 lakes) | 56 distinct lakes in total, 31,870 bytes in all (about 570 bytes per lake). Rebuildable. |
| Validation truth (not in Git) | `context/hypso_truth.json` (53 USACE projects with storage and pool series; 41 usable fits, 33 after quality filters) | The share of lake surface gained per foot of pool ("stage-area slope") from CWMS storage against pool level. |
| Research write-up | `docs/research/lake-brain/LAKE_BRAIN_CONTEXT_RESEARCH.md` section 4.2 to 4.4 (research branch) | Recommends it as a static feature. |
| In the product (pilots only) | `/lakes/{k}/brain/characteristics/context/shorelineSlope` `{medianSlopeDeg, shareUnder2Deg, runPerVerticalFtMedian, quality, source}` published for the 5 pilots; carried in `Sources/SectorEngine/LakeBrain/LakeSourceBindingsGenerated.swift` and typed at `LakeBindingTypes.swift` (`ShorelineSlope`). `quality` reads "proxy (Spearman 0.76 vs CWMS stage-area slope, 33 lakes)"; `source` reads "USGS 3DEP DEM, shore band 10-60 m (research context_shore_dem.py; pilots only)". | Live, descriptive context; consumed by nothing yet. |

Pilot values (live profiles and research): Guntersville 1.28 degrees median slope, 58.8 % of shore under 2 degrees, run 44.9 ft per vertical foot; Wheeler 1.11, 61.7 %, 51.6; Pickwick 3.90, 40.9 %, 14.7; Hartwell 6.30, 16.8 %, 9.1; Wilson 7.96, 20.8 %, 7.1.

## 2. What it is worth (validated, with limits)

Against stage-area slope from CWMS storage and pool series for 33 reservoirs (`LAKE_BRAIN_CONTEXT_RESEARCH.md` 4.3):

| Predictor of "share of surface gained per foot of pool" | Spearman | log10 RMSE | within a factor of 2 |
|---|---|---|---|
| shape only (perimeter over area) | -0.16 | n/a | n/a |
| **3DEP shoreline slope (perimeter x run per foot / area)** | **0.76** | **0.22** | **82 %** |
| GLOBathy | 0.33 | 0.41 | 48 % |
| a constant (median of the truth) | n/a | 0.33 | 76 % |

It ranks lakes correctly (steep western reservoirs apart from flat plains lakes; Hartwell predicted 0.0174 per ft against 0.0166 measured) and beats a constant on error. Failure cases are flat wetland beside the polygon (Enid, Caddo), Sardis OK and Texoma. Limits that must travel with any published value: the DEM shows the bank above the waterline only, so it predicts the response to a rise and to a small drawdown, not the bottom profile in a deep drawdown; 7 to 25 % of outward slopes in the pilots are negative (polygon-edge or lidar-water artefacts; medians are used); the truth sample is USACE reservoirs (no TVA lake has truth because TVA publishes no storage series); it is a proxy and says nothing about whether fish use the flats.

## 3. Where a start should be (pilots and the validation fleet)

- **Pilots (5): done.** Published as context.
- **Validation fleet (`LAKE_BRAIN_REPRESENTATIVE_VALIDATION_FLEET.md`, 18 lakes):** slope cached already for **5** (Guntersville, Lake Hartwell, West Point, Grenada Lake, Don Pedro). Missing for **13**: Bankhead, Lake Murray (SC), Bluestone Lake, Carlyle Lake, Table Rock Lake, Lake Winnebago, Indian Lake NY, Lake Livingston, Cheney Reservoir, Pueblo Reservoir, Abiquiu Lake, Keyhole Reservoir, Flathead Lake (key match against the three cached files, 2026-10-13). Stage-area truth exists for **Hartwell, Grenada and Don Pedro**, so those three can check the proxy inside the fleet; the other 15 cannot.
- Across the 109 history-qualified accepted lakes, the research cache covers 16 (Allatoona, Arkabutla, DeGray, Don Pedro, Enid, Grenada, Guntersville, Hartwell, Lake Tahoe, Okatibbee, Ouachita, Pickwick, Sardis, West Point, Wheeler, Wilson); 9 of them also have stage-area truth (Arkabutla, DeGray, Don Pedro, Enid, Grenada, Hartwell, Lake Tahoe, Ouachita, Sardis).

## 4. Data volume, licence and feasibility

| Question | Answer |
|---|---|
| Data volume per lake | About 700 shore points x 4 offsets, roughly 2,800 point samples returned as numbers (no raster is downloaded). Stored result about 0.6 KB per lake. |
| Time | About 1 minute per lake at 1 request per second (research). The 13 missing fleet lakes: about 15 minutes. The whole 599-lake fleet: about 10 hours, or 3 hours with three workers. |
| Input needed | The lake outline. The Lake Registry geometry contract (`LAKE_REGISTRY_GEOMETRY_CONTRACT.md`) provides it; the registry index is public (`https://storage.googleapis.com/sector-lake-registry/registry/lakes.v1.json`, checked 2026-10-13: HTTP 200). `analysis` variant (25 m) is the intended size. Lakes with a flagged coordinate or no polygon (22 polygon-less in the research) are skipped. |
| Licence | USGS 3DEP is US Government data. The research source ledger records it as **public domain** (`S-context-012`, `S-geometry-014`). Keep the USGS credit in the `source` string. Confirm the exact attribution wording before any customer-facing use. |
| Is any computation feasible read-only now? | **Yes, in two small ways, neither run here.** (a) A join of the cached results to the 196 or to the 18 (done in section 3 by key match): no network. (b) Filling the 13 missing fleet lakes: about 36,000 point queries (13 x 2,800) to a public elevation service. That is not a large download, but the brief says not to run 3DEP work in this task, so it is a follow-up for the lead or Michael. |
| Where results would go | A static `shorelineSlope` entry in the lake's profile context (already typed and published for pilots) via the generated-bindings pipeline, plus optional `relPerFt` (predicted share of surface per foot). Nothing about depth. |

## 5. Risks, and the rules for use

- A bank-slope number must never be presented or consumed as depth. Depth Brain's `effectiveDepth` is its own; Water Temp, Water Clarity and Vegetation read depth from Depth, not from this field.
- Quality stays `proxy` with the 33-lake validation numbers attached. A lake whose DEM beside the polygon is flat water-meadow (Enid, Caddo pattern) should be flagged low quality when negative-slope share is high (the cached results carry `frac_neg`).
- The cache is outside Git and the key match was done by exact lake id; recheck it against the file in use before quoting a count externally.
- This feature does not affect any score dimension, the rubric, or validation status.
