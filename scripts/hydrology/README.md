# scripts/hydrology — Clarity Fusion Stage 1

Build the lake's hydrologic arm graph and its input-association data. The
Python venv needs rasterio, numpy, scipy, shapely, pyproj, pillow and
scikit-learn. Inputs are the iOS lake-profile cache and assets
(`Sector-mapbox/.fishintel-cache/guntersville`, `…/Assets.xcassets/FishIntel`).

| Step | Script | What it does |
|---|---|---|
| 1 | `build_arm_graph.py --out RAW` | Builds the NHD flow network, splits same-named creeks, and allocates water through the lattice. |
| 2 | `enrich_arms.py RAW/arms_raw.json ENRICH` | Looks up each arm in NLDI (comid, basin, upstream length, gauges), NWPS (the NWM reach), WBD (HUC12) and FCC (county). Cached. |
| 3 | `finalize_graph.py --raw RAW --enrich ENRICH --out FINAL` | Assigns ids and the tree, main-stem regions and gauges. Writes the graph, the diff and the registry audit. |
| 4 | `membership_audit.py --raw RAW --final FINAL` | Finds which old associations crossed land. |
| 5 | `catchment_rain.py weights FINAL/guntersville.hydrology.json ENRICH/catchments FINAL/guntersville.mrms_weights.json` | Builds each basin's MRMS cell weights. |
| 6 | `catchment_rain.py rain WEIGHTS YYYY-MM-DDTHH OUT.json` | Computes basin rain at an hour. This is the future hourly job. |
| 7 | `embed_swift.py FINAL ../../Sources/SectorEngine/Hydrology/HydrologyData.swift` | Writes the engine's embedded graph. |
| 8 | `repaired_profile.py FINAL OUT` | Writes candidate lake-profile assets. These are not applied to the app. |
| 9 | `scenario_association.py FINAL scenario.json OUT.json` | Runs the storms against the association layer. |
| 10 | `visibility_validation.py Q9 OUT.json` | Validates the turbidity-to-visibility candidates. Needs the WQP pulls. |
| 11 | `sentinel_evidence.py OUT.json`, then `export_evidence.py PREFIX FINAL OUT.json` | Writes per-cell Sentinel evidence. |

The outputs are in `docs/data/hydrology/guntersville/`. The hand-off is at `docs/clarity/CLARITY_FUSION_STAGE_1_HANDOFF.md`.

## Stage 2 — per-arm current clarity state

Outputs are in `docs/data/hydrology/guntersville/stage2/`. The hand-off is at
`docs/clarity/CLARITY_FUSION_STAGE_2_HANDOFF.md`. `PASSES` is a directory of
per-pass files; the history runs from 2025-02-20 (rain, flow) or 2025-03-01
(passes) to 2026-09-27.

| Step | Script | What it does |
|---|---|---|
| 1 | Earth Search STAC (`sentinel-2-c1-l2a`), the lake's bbox, 60-day windows | Lists candidate passes; keeps those with a tile at or under 40% cloud → `pass_candidates.json` (164). |
| 2 | `pass_history.py pass_candidates.json ../../docs/data/hydrology/guntersville/guntersville.arm_cells.json PASSES [--worker k --workers n]` | Reads each pass with the production gates and drops, then writes each arm's observed cells and FNU (no fill). About 90 s a pass. |
| 3 | `rain_history.py WEIGHTS LAKE.geojson 2025-02-20 END rain_daily.json` | Computes daily basin-mean MRMS 24 h Pass 2 (valid 17Z) per arm and over the lake surface. |
| 4 | USGS IV `00060` for 03572900 and 03572690, `startDT=2025-02-20` | Pulls measured discharge history → `usgs_iv_history.json.gz`. |
| 5 | `nwm_history.py HYDROLOGY.json 2025-02-20 END nwm_daily16z.json` | Reads the NWM analysis at 16Z every day from `gs://national-water-model` for every arm reach. |
| 6 | `nwm_vs_usgs.py usgs_iv_history.json nwm_daily16z.json nwm_vs_usgs.json` | Compares modeled and measured flow at the two gauged arms on every day both exist. |
| 7 | `pass_pairs.py PASSES rain_daily.json usgs_iv_history.json nwm_daily16z.json HYDROLOGY.json pass_pairs.json` | Calibration: consecutive pass pairs, the event anomalies against each arm's dry baseline, and the noise floors. |
| 8 | `plume_diagnostic.py ARM_CELLS OUT.json DATE:PLATFORM …` | Checks whether Sen2Cor or the gates hide muddy water. |
| 9 | `arm_anchor.py PRODUCT_PREFIX DATE ARM_CELLS OUT.json` | Writes per-arm satellite anchors from a published Water Clarity product. The engine reads `lakes/<slug>/clarity/arms/latest.json`. |
| 10 | `swift run -c release ClarityReplay PASSES rain_daily.json usgs_iv_history.json nwm_daily16z.json WEIGHTS replay.json [arm …]` | Runs the historical replay through the engine's own state logic, with no look-ahead. |

The hourly job (`jobs/hydrology-hourly`) publishes the live rain feed and the
hourly record the engine's state loader reads.
