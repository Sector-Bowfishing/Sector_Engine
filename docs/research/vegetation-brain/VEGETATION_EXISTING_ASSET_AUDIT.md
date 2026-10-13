# Vegetation Brain — Existing Asset Audit

**Status: RESEARCH ONLY. The Vegetation Brain is a NEW, PROPOSED Brain. Sector has no production Vegetation Brain.**
Audit date: 2026-10-13. Worktree `Sector_Engine-vegetation-research`, branch `docs/vegetation-brain-research`, based on `main` @ `e596a6bb` (not on any other Brain's research branch).

## 1. Bottom line

| Question | Answer |
|---|---|
| Is there a production Vegetation Brain? | **No.** |
| Is a slot reserved? | Yes — name only. `vegetation` is reserved in `BRAIN_PLATFORM_CONTRACT.md` §2 ("reserved") and in `BrainPlatform.swift:34` / `jobs/brain_platform/sector_brain_platform/keys.py:18` (slot `vegetation`, snapshot field `vegetation`, display "Vegetation"). No runtime, no job, no catalog entry, no score. |
| Any vegetation data shipped to customers today (engine)? | No vegetation layer in this repo's engine API. |
| Any vegetation survey data in repo? | **None.** No NWI, agency survey, or polygon ground truth anywhere in the repo or the research data directory. |
| Anything reusable? | Yes: (a) a Sentinel-2 *surface-grass* detector inside the Water Clarity pipeline; (b) a legacy iOS Sentinel-2 NDVI "vegetation" layer on Guntersville; (c) lake polygons for 599 of 621 lakes; (d) fleet directory with coordinates and states for all 621. |

## 2. Inventory

### 2.1 Reserved Brain slot (name only)
- `docs/brains/BRAIN_PLATFORM_CONTRACT.md:37` — `depth`, `vegetation` listed as "reserved".
- `Sources/SectorEngine/Brain/BrainPlatform.swift:34`, `jobs/brain_platform/sector_brain_platform/keys.py:18` — id→slot map entry.
- **Implication:** when built, the Vegetation Brain slots into the existing Brain platform contract (schema gate, health vocab, readiness slot) without a platform change. We are *not* registering it.

### 2.2 Water Clarity pipeline — surface-grass mask (the closest thing to a vegetation detector)
Files: `jobs/lake-surface/derive_water_surface.py`, `scripts/hydrology/sentinel_evidence.py`, `scripts/hydrology/arm_anchor.py`, `jobs/lake-surface/daily.py` (emits `grassPct`).
- Purpose: **exclude** plants from a clarity/thermal reading, not to map them. Grass is a nuisance mask.
- Rule: surface grass = plant spectrum, `GRASS_NDVI_MIN = 0.30` plus FAI gate (`FAI_MAX = 0.005`) and SWIR; weaker gate `NDVI_MAX = 0.10` for clean water. Haze over open water reached NDVI 0.12–0.19 (documented 20 Sep false positives: 36 % of the lake mis-read as grass before the plant-spectrum rule).
- Grass under cloud is borrowed from passes within `GRASS_BORROW_DAYS = 10` (up to 2 passes) — an existing, field-tuned cloud-gap approach worth reusing.
- Output code `3` = "grass bed (estimated)" in the clarity evidence raster; the Guntersville 20 Sep 2026 raster has 110,176 observed vs 305,038 estimated cells (grass is one of the estimated classes; the grass cell count is not broken out in the committed JSON).
- Known limits recorded by the pipeline authors: cannot tell vascular plant from cyanobacterial bloom; only **surface-reaching** vegetation; 25 m bank erosion destroys narrow arms.
- **Ownership caution:** this is Water Clarity's code. Vegetation Brain must *consume or fork the idea*, not modify Clarity.

### 2.3 Legacy iOS vegetation layer (separate repo `iOS/sector-intel-phase3`)
- `Sector/FishIntel/Lake/LakeRegistry.swift:111-133` — capability record: Sentinel-2 L2A via AWS Open Data, "NDVI over the littoral polygon, eroded 25 m from the bank", version `s2-ndvi-2026.09.20`, acquired 2026-09-20, **4,282 of 6,504 segments (65.8 %)** on Guntersville only.
- Limitations declared in code: surface-reaching only (topped-out hydrilla/milfoil, pads, emergent); cannot separate vascular plant from dense algal bloom; ~half the lake unread; unread segments refused rather than given a lake mean.
- `LakeRegistry.swift:396` — Wheeler: `.unavailable(.vegetation, reason: "No vegetation survey for Wheeler.")`.
- `FishIntelLayerManager.swift:113,322` — a `vegetation` map layer kind exists in the iOS app. (The task states Vegetation was removed from the customer layer set; this research does not change or re-add it.)
- `CLAUDE.md:265` — project doctrine: vegetation is surface-reaching only; unread segments are refused, not interpolated.
- **Net:** one lake, one date, no validation against survey data, no seasonality.

### 2.4 Consumers that already *expect* vegetation inputs (Biological Brain / Intelligence)
- `Sources/SectorEngine/Engine/Config/SpeciesDatabase.swift:160-179` — species spawn habitat strings: common carp "flooded & submerged grass and weedy 1–3 ft flats"; bigmouth buffalo "freshly flooded vegetated marsh grass"; smallmouth buffalo "submerged vegetation"; black buffalo "flooded vegetation"; alligator gar "overbank flooded terrestrial grass". **These are fish-preference facts (Biological Brain), correctly kept out of Vegetation.**
- iOS `BiologicalState.swift:24,92`, `StateDriverDomain.swift`, `Evidence.swift:189` — a `vegetationDensity` driver key is named in the biological-state model. **Today it has no data feeding it.**
- Species classes that matter: flooded terrestrial (gar, buffalo) and submerged (carp, smallmouth buffalo) — exactly the class split proposed here.

### 2.5 Geometry and lake directory (inputs, not vegetation)
- `Sector_Research_Data/lake-brain/directory_lakes_2026-10-13.json` — 621 lakes, 50 states (9–15 per state), lat/lon, `usgsGage`, `fullPoolFt`.
- `…/geometry/engine_polygons_599.geojson.gz` — polygons for 599 lakes (22 point-only) — enough to clip any raster to a water mask.
- `…/geometry/` also holds JRC GSW, DEM, HydroLakes, NHD/TDHP matches: reusable for water masks and shoreline definition.
- `docs/data/full_pool.csv` (425 rows) — full-pool elevation per lake: needed for Lake Brain level interaction.

### 2.6 Things searched for and **not** found
NWI, NLCD/C-CAP, LANDFIRE, NDAVI, red-edge indices, Sentinel-1, NAIP, JRC vegetation products, TVA/USACE/state aquatic plant surveys, agency habitat maps, sonar/BioBase maps, and any vegetation GIS polygons: **no datasets in Git or in `Sector_Research_Data/`** (keyword grep + filename search over repo and data dirs on 2026-10-13; the only hits in the data dir are incidental text mentions in scraped agency HTML/JSON, e.g. lake-brain species/binding pages). All are net-new research below.

## 3. What this means for the proposal
1. A tuned, field-tested *surface-reaching vegetation* detector already exists in a different Brain's code (Clarity). Reuse the logic (plant-spectrum gate, FAI, cloud borrowing), do not couple the code.
2. No ground truth exists in-house. The existing Guntersville layer has never been scored against a survey. Every vegetation accuracy claim today is **unvalidated**.
3. The Biological Brain already has the vocabulary (flooded vs submerged vs vegetated marsh) that the Vegetation Brain should output, so class design should mirror it.
4. The Brain platform slot is already reserved, so no platform work is a prerequisite.
