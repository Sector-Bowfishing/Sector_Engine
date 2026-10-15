# Brain Repository Inventory

Base `fab115e9`. "Base" = this tree. "Branch-only" = reachable only from named branches (no copy in base). Branch notes are provenance, not instructions to merge. Research workspace names follow `BRAIN_RESEARCH_WORKSPACE_V1`; no absolute paths are used here on purpose. Per-lake species data is private and is not described.

Human names: `biological-state` = **Fish Brain** (machine id unchanged).

---
## wind
| | |
|---|---|
| Brain ID / name | `wind` / Wind Brain |
| Code (base) | `jobs/wind-hourly/main.py` (hourly job), `sector_wind/` (22 modules: ingest, grib, interp, field, validate, store, live, monitor, scoreboard, overwater, rrfs, bowfishing…), `sector_wind/brain/` (contract, profile, state, publish, writer, lakes, `validation_evidence.json`), `read_service/` (Cloud Run read service for 3 master UIDs), `research/` (28 scripts), `lakes.json` |
| Docs (base) | `jobs/wind-hourly/{BRAIN,README,SESSION_CLOSEOUT}.md`; `OWNERSHIP_MATRIX` rows; `jobs/README.md` |
| Schemas | none as files; state/descriptor built in `brain/contract.py`, `state.py`, `publish.py` |
| Tests | `jobs/wind-hourly/tests` (8 files, network tests deselected via `pytest.ini`); CI runs them |
| Scoring | `bowfishing_score.py` (candidate score), `scoreboard.py`/`validate.py` (science), platform readiness via `frozen-scores.json` (no Wind rubric file) |
| Runtime jobs | `wind-hourly` (Scheduler, NBM early exit), `wind-candidate-read` (service) |
| Providers | NOAA NBM (NODD), RTMA-RU, HRRR, RRFS (nomads), MADIS, METAR, ICESat-2/ATL13 research; Open-Meteo only as bake-off/benchmark and as the *production-wind baseline label* in `contract.py` |
| External deps | `gs://sector-wind-candidate`; Brain RTDB wind slot; iOS-repo assets (`FishIntel/Wind` tables, `scripts/wind`) read from Desktop paths |
| Cross-Brain deps | Lake (via `lakes.json`, a **copy** of lake ids/coords); Lake geometry fetch tables generated in the iOS repo and copied to GCS (OWNERSHIP exception) |
| Branch-only | `feat/wind-brain-adoption` ⊂ `deploy/wind-internal-validation`: `docs/brains/wind/` (91–92 files: spec, preregs, rubric v2, field packs, decisions), +17 `sector_wind` modules, +18 research scripts, +12 tests, `data/`, `field_packets/`, `field_tools/`; `cert/wind-architecture-v1`: `sector_wind/brain/artifact.py`, `test_publish_artifact.py`, 13 certification docs, Publisher shadow (also on `feat/publisher-v1-shadow`); `docs/wind-brain-research` (`docs/wind-research`, `research/wind-brain`); `brain/wind`, `intelligence/wind` = older lineage |
| Research workspace | `wind-brain` |
| Published/runtime paths | RTDB wind slot (`/lakes/{k}/states/wind`, registry, profile); `gs://sector-wind-candidate/wind/v1/*` |
| Structural problems | research scripts + hard-coded iOS/Handoff paths in runtime package (`bowfishing.py:ASSETS`, `bowfishing_score.py:DOCS`, `fieldops.py`); job name ≠ Brain name; Brain docs inside job dir; own `lakes.json` duplicates Lake registry; writer `sys.path` import of platform; the most important spec corpus is branch-only; **production wind is NOT this Brain** (Open-Meteo in-process) |
| **Recommended home** | `brains/wind/` (first migration; see `STANDARD_BRAIN_PACKAGE_V1` §Wind) |

## biological-state (Fish Brain)
| | |
|---|---|
| Code (base) | `jobs/biological-brain/{biological_brain,orchestration,run}.py` (bundle loader + publisher, 789 lines), 3 shims |
| Docs / schemas | `docs/brains/BIOLOGICAL_BRAIN_INTEGRATION.md`; `schemas/*.schema.json` (4: manifest, latest_pointer, species_profile, species_summary): the only Brain with JSON Schemas in base |
| Tests | `tests/test_biological_brain.py` (CI) |
| Scoring | `docs/brains/scoring/biological-state-score-v1.json` (rubric) |
| Runtime | in-process in `brain-orchestrator` when `plan()` says PUBLISH (version-triggered) |
| Providers | none (consumes a canonical bundle) |
| External deps | canonical release bundle (private storage); research bundle; Lake presence overrides flow *into* Lake via this release |
| Cross-Brain | Lake presence validator consumes Fish canonical overrides; Intelligence consumes Fish state; Engine `SpeciesDatabase` is an **adapter copy** of spawn knowledge |
| Branch-only | `feat/biological-brain-adoption`: rules, features, movement_outlook, capability, bands, target_readiness, validation_log, species_profile, 11 schemas, 10 tools, 16 tests, 36 adoption docs; `docs/biological-brain-research` (18 docs); `feat/biological-score-v2` |
| Research workspace | `fish-brain` |
| Published paths | `/species/{id}`, `/brains/biological-state` (CERT-5: serving path deferred) |
| Problems | the real Brain is branch-only; shim `brain_platform.py` triplicated; orchestrator imports its `run` in-process; species identity (Registry) vs species intelligence (Fish) not separated in code |
| **Recommended home** | `brains/fish/` (dir name human-friendly; `brainId` stays `biological-state` in `brain.json`) |

## lake-brain
| | |
|---|---|
| Code (base) | Swift: `Sources/SectorEngine/LakeBrain/` (Contract, Orchestration, Runner, Profiles, Archive, LevelBaseline/Classifier/Feeds/FeedsFleet, SourceBindings + 425 KB generated, GeneratedBindings, PredictionLedger, SpeciesPresence, BindingTypes), `Sources/LakeBrainJob`; registry `Support/LakeDirectory.swift` (190 KB, 621 lakes) + `LakeDirectorySearch`, `API/LakeDirectoryAPI`; Python tooling `jobs/lake-brain/{bindings,history,ledger,review,validation,data}` (5.1 k lines, no runtime); `jobs/lake-geometry/` (geometry build, 1.8 k); `scripts/generate-lake-{directory,bindings}.py`; `docs/data/{Sector_Lakes_APIs_2.xlsx,full_pool.csv,temp_sensors.csv,FULL_POOL.md}` |
| Docs | 11 `docs/brains/LAKE_*` (flat) + `LAKE_REGISTRY_GEOMETRY_CONTRACT` |
| Schemas | `LakeBrainContract.swift`, `LakeBindingTypes.swift`; `conformance/lake_keys.json`, `lake_rules_v2.json` |
| Tests | Swift: 7 Lake files; Python: `holdout_v2`, `rules_v2`, `build_bindings_table`, `score_predictions`, review `ingest`, `lake_geometry`: **not in CI** |
| Scoring | `lake-brain-score-v1.json`; prediction ledger scorer; rules-v2 prereg + results |
| Runtime | `lake-brain` Cloud Run job (orchestrator-triggered, pilot 5 lakes) from the shared brain-jobs image |
| Providers | TVA REST, USGS NWIS/OGC, USACE CWMS, USBR, SWPA/Alabama Power (through Engine adapters), NOAA water |
| External deps | `gs://sector-lake-brain` (presence bundle, history), private research data |
| Cross-Brain | consumes Engine `TVAGenerationService` + production parsers; Fish canonical release; **is the dependency for Wind (`lakes.json`), Water Temp (lake gauges), Clarity (lake list via `/lakes`)**, Intelligence |
| Branch-only | `feat/lake-consolidated` (superset of ~14 slice branches: readiness, +20 history files, +17 review files, +17 docs, fixtures); `docs/lake-brain-research` (55 research docs + ~100 `research/lake-brain` tool files); `feat/lake-brain-ledger`, `-rules-v2`, `-bindings`, `-fleet-*`, `-surface-job`, `-environment-snapshot` (slices) |
| Research workspace | `lake-brain` |
| Published paths | `/lakes/{k}/states/lake`, `/lakes/{k}/speciesPresence/{speciesId}`, lake fleet; `gs://sector-lake-brain` |
| Problems | code in 3 languages-places; **registry has no home** (lives in `Support/` + xlsx in `docs/data`); customer `/lakes` and Lake Brain registry are the same data with different owners on paper; hard-coded legacy research paths (≈12 sites); generated bindings checked in as 425 KB Swift; Python tooling under `jobs/` is not CI-tested; reads customer parser |
| **Recommended home** | `brains/lake/` with `runtime` (Swift, `path:` target), `registry/` (source xlsx → versioned `lake-registry` contract), `tools/` (Python), `validation/`, `ledger/`; geometry under `brains/lake/geometry/` |

## water-temp
| | |
|---|---|
| Code (base) | Swift: `Brain/WaterTemperatureBrain.swift`, `WaterTemperatureBrainRunner.swift`, `WaterTemp/{WaterTemperatureState,LakeLocalDate}.swift`, `Fetchers/{WaterTemperatureService,WaterLevelService,LakeTempSensorService,USGSWaterData}.swift`, `Engine/Factors/WaterTempFactor.swift`; `Sources/WaterTempBrainJob`; `jobs/water-temp-brain/deploy-job.sh` (only file); archive `jobs/water-temp-tva-archive/` |
| Docs | `docs/brains/WATER_TEMP_BRAIN.md` |
| Tests | Swift ×8 (`WaterTemp*`, `WaterTemperatureBrain*`), Python archive test (CI) |
| Scoring | `frozen-scores.json` (no rubric file) |
| Runtime | `water-temp-brain` job (fleet, 621 lakes) + hourly TVA archive job |
| Providers | USGS 00010, USACE CWMS, Open-Meteo forcing, TVA discharge archive |
| Cross-Brain | **same Swift implementation serves customer `/conditions`** (documented "one implementation"); reads Lake gauges via bindings; Fish temperature response consumers |
| Branch-only | `docs/water-temp-brain-research` + `feat/water-temp-brain-adoption` (183 research docs under `docs/research/water-temp`, 4 more `WaterTemp` Swift files), `brain/water-temp`, `intelligence/water-temp` (large old-lineage payload), `fix/water-temp-*` (calibration, lake-gauges, shown-scored) |
| Research workspace | `water-temperature` |
| Published paths | `/lakes/{k}/states/water-temp`; `open-meteo-forecast` source record |
| Problems | a Brain whose runtime is the customer's: no seam between model and `/conditions` consumption; `jobs/water-temp-brain` is a one-file dir; research is 183 docs in branches; client `k` constant exception (`OWNERSHIP_MATRIX`) |
| **Recommended home** | `brains/water-temperature/` (library target `SectorWaterTemp` that Engine may link as a declared embedded adapter; job target + archive acquisition under `providers/tva`) |

## water-clarity
| | |
|---|---|
| Code (base) | `jobs/water-clarity-brain/` (publisher `clarity_brain.py`, `run.py`, `catalog.json`, fixtures, Dockerfile); Swift `Hydrology/` (graph, gauge, history, state, loader, visibility model, rainfall, 103 KB generated) + `Engine/Factors/ClarityFactor` + `API/{Clarity,Hydrology}API`; satellite `jobs/lake-surface{,-dispatch}`, `jobs/hydrology-hourly`, `Sources/ClarityReplay`, `scripts/hydrology/*`, `docs/data/hydrology` |
| Docs | 4 `WATER_CLARITY_*`, `docs/clarity/*` (2 handoffs), `jobs/lake-surface/LINEAGE.md` |
| Schemas | `catalog.json` (model catalog), private overlay (`catalog.private.json`, gitignored) |
| Tests | `test_water_clarity_brain.py` (CI) + 6 fixtures; Swift Clarity ×3; `lake-surface-dispatch` tests (CI) |
| Scoring | `frozen-scores.json` |
| Runtime | `water-clarity-brain` MANUAL by decision; `lake-surface-daily` (dispatcher-triggered; **live source off-main**), `lake-surface-dispatch`, `hydrology-hourly` (paused), `clarity-current-hourly` (paused, off-main), `clarity-candidate-shadow` (private) |
| Providers | NOAA MRMS, Open-Meteo rain fallback, USGS turbidity/discharge, Sentinel-2 (STAC/Planetary Computer/AWS), IEM |
| Cross-Brain | **consumes the customer Engine `GET /conditions` and `/lakes` over HTTP**; reads `gs://sector-lake-surface`; Lake registry |
| Branch-only | `feat/clarity-algal-warning` (fusion; live source), `-fusion-stage1`, `-production`, `-current-estimate`, `-candidate-shadow` (15 k files; private), `research/clarity-candidate`, `campaign/clarity-readiness`, `brain/water-clarity{,-public}` |
| Research workspace | `water-clarity` |
| Problems | most fragmented Brain; live job source off-main (D4); Brain depends on customer API; 12 MB evidence + 7.5 MB polygon blob in repo; research scripts with iOS paths |
| **Recommended home** | `brains/water-clarity/` with `runtime` (publisher), `science/` (Swift Hydrology library), `acquisition` jobs declared in `brain.json` and clients in `providers/` |

## depth
| | |
|---|---|
| Code (base) | **none** |
| Branch-only | `feat/depth-brain-foundation`: `jobs/depth-brain/{depth_brain/ (52 files), tests/ (26), run.py, BRAIN.md, BRAIN_SPEC.md}`, `docs/brains/depth/` (82), `research/depth/` (59 scripts); `docs/depth-brain-research` (60 docs + 39 tools) |
| Research workspace | `depth` |
| Problems | only copy of the code is a branch; research scripts are in Git while the workspace standard says outside; no CI; no registry entry beyond docs |
| **Recommended home** | `brains/depth/` (adopt branch at Depth's turn; **preserve the branch until then**) |

## vegetation
| | |
|---|---|
| Code (base) | **none** |
| Branch-only | `feat/vegetation-brain-foundation`: `jobs/vegetation-brain/{vegetation_brain/ (19), tests/ (9), tools/ (4), BRAIN.md}`, `docs/brains/vegetation/` (103); `docs/vegetation-brain-research` (55) |
| Research workspace | `vegetation` |
| Problems | as Depth. Recorded state: surface-only shadow V1, NOT_VALIDATED |
| **Recommended home** | `brains/vegetation/` |

## sector-intelligence
| | |
|---|---|
| Code (base) | `jobs/sector-intelligence-brain/{sector_intelligence_brain,evaluation,orchestration,run}.py` (1.4 k lines), `catalog.json`, 3 shims |
| Docs | `SECTOR_INTELLIGENCE_BRAIN_{INTEGRATION,STATUS}.md` |
| Tests | 2 files (CI) |
| Scoring | `sector-intelligence-score-v1.json` |
| Runtime | in-process in orchestrator (FINGERPRINT-triggered; pilot lakes only) |
| Cross-Brain | **reads upstream states from RTDB** (lake-brain, water-temp, water-clarity, wind, biological-state) with `DEPENDENCY_ORDER` hard-coded in code; evaluates nothing yet |
| Branch-only | `feat/intelligence-evidence-layer` (contracts ×2, tests ×6), `docs/intelligence-deep-research` (32) |
| Research workspace | `sector-intelligence` |
| Problems | dependency list hard-coded in code and catalog (should derive from each Brain's `brain.json`); runs in orchestrator image |
| **Recommended home** | `brains/sector-intelligence/` (certified last) |

---
## Cross-cutting: where each current location lands

| Today | Brain(s) |
|---|---|
| `Sources/SectorEngine/Brain/BrainPlatform|BrainContract|BrainRTDBStore.swift` | Platform (Swift) |
| `Support/LakeDirectory*.swift`, `API/LakeDirectoryAPI.swift`, xlsx, generators | Lake registry |
| `Engine/Config/SpeciesDatabase`, `SpeciesLegality` | Engine adapters (Fish / Policy owned) |
| `Hydrology/VisibilityModel`, `ClarityFactor` | Clarity science consumed by Engine |
| `Fetchers/*`, `Engine/Adapters/*` | providers |
| `docs/brains/scoring/*` | per-Brain rubrics + platform scoring |
