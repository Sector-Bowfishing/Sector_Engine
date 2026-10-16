# Repository Dependency Map

**Status:** `REPOSITORY_ARCHITECTURE_V1_APPROVED_FOR_PHASE_1`. Section 1 is CURRENT fact. Section 2 is the LOCKED TARGET (not implemented). Locked refinements: entity identity comes from the **platform Lake and Species Registries**, not from Lake or Fish Brain; `customerIntegrationMode` direction is Customer Engine → approved Brain contract/library; Clarity's customer-API dependency is a defect to remove in the Clarity phase (blocked by D4 for migration).

Legend: **→** "depends on / consumes". **Evidence** cites a file or doc at base `fab115e9`. **CURRENT** is observed; **TARGET** is the proposed rule and is *not* implemented.

## 1. CURRENT dependencies

### 1.1 Provider → Engine / Brain
| Edge | Evidence |
|---|---|
| Open-Meteo → Engine (`/conditions`, forecast, snapshot) | `Fetchers/WeatherService.swift`, `Forecast/*` |
| Open-Meteo → Water Temp Brain | `Fetchers/WaterTemperatureService.swift` calls `WeatherService.fetchForecastData`; source `open-meteo-forecast` in `WaterTemperatureBrainRunner` |
| Open-Meteo → Clarity (fallback rain) | via Engine `/conditions` response (`clarity_brain.py`) |
| Open-Meteo → Wind (**research only**) | `provider_bakeoff.py`, `research/openmeteo_runs.py` |
| USGS → Engine, Water Temp, Lake, Clarity | `USGSWaterData.swift`, `WaterLevelService.swift`; `hydrology-hourly`, `review/build_review_pack.py` |
| TVA → Engine, Lake, Water Temp (archive), Clarity | `TVAGenerationService.swift`, `LakeLevelFeeds.swift`, `archive.py`, `hourly.py` |
| USACE CWMS → Engine, Water Temp, Lake | `CWMSObservedService.swift` |
| NOAA NBM/RTMA/HRRR/RRFS/MADIS → Wind | `sector_wind/{ingest,grib,rrfs,live}` |
| NOAA MRMS/IEM → Engine, Clarity | `MrmsPrecipService.swift`, `clarity_brain.py` |
| Sentinel-2/STAC → Clarity | `jobs/lake-surface/*` |
| NWS alerts → Engine | `WeatherAlertsService.swift` |

### 1.2 Lake → other Brains / Engine
| Edge | Evidence |
|---|---|
| Lake registry → Engine (`/lakes`, lake keys) | `Support/LakeDirectory.swift`, `API/LakeDirectoryAPI.swift` |
| Lake registry (de facto) → Wind | **copy**: `jobs/wind-hourly/lakes.json` (no registry contract exists yet) |
| Lake registry → Clarity | HTTP `GET {ENGINE}/lakes` in `water-clarity-brain/run.py` (via the *customer* API) |
| Lake registry/bindings → Water Temp | lake gauges (`fix/water-temp-lake-gauges`, bindings tables) |
| Lake Brain state → Sector Intelligence | RTDB state read, `DEPENDENCY_ORDER` in `sector_intelligence_brain.py` |
| Lake geometry/fetch tables → Wind | built in iOS repo, copied to GCS (OWNERSHIP exception) |
| Lake presence ← Fish canonical release | `LakeSpeciesPresence.swift` (overrides recorded as discrepancy ids) |

### 1.3 Brains → Sector Intelligence (all via RTDB published state)
`lake-brain`, `water-temp`, `water-clarity`, `wind`, `biological-state` → `sector-intelligence`. Intelligence evaluates nothing yet (NOT_EVALUATED per lake; pilot only). Depth and Vegetation are not in `DEPENDENCY_ORDER` (not on main).

Brain-to-Brain edges beyond Intelligence: Water Temp → Fish/Intelligence (temperature response) is conceptual, not coded; Clarity ↔ Water Temp/Wind: none in code.

### 1.4 Brain → Publisher → sector-brain → Ops
| Edge | Evidence |
|---|---|
| Brain → `sector-brain` RTDB (direct, shared `brain-writer`) | `sector_brain_platform/rtdb.py`, `BrainRTDBStore.swift`, `run.py` of every Python Brain, Wind `writer.py` |
| Brain → Publisher | **absent on base**; shadow on `feat/publisher-v1-shadow`; Wind artifact builder on `cert/wind-architecture-v1` |
| Orchestrator → Brains (starts jobs; imports Fish and Intelligence) | `orchestrate.py` |
| Orchestrator/platform → `/scores`, `/control`, `/jobs` | `brain-scores`, `control_plane.py` |
| `sector-brain` → Ops (read/display) | `OPS_CONTROL_PLANE_CONTRACT.md`; Ops repo not in scope |
| Customer apps → Engine only (never `sector-brain`) | README, Certification lock #4 |

### 1.5 Direct implementation imports / coupling
| Edge | Kind |
|---|---|
| Lake Brain → `TVAGenerationService` (Engine adapter) | **Brain → customer code** |
| Water Temp Brain ↔ Engine `Fetchers` (one implementation) | intentional shared implementation |
| Engine `ClarityFactor` → `Hydrology` (Clarity science) | Engine → Brain science, in-process |
| Clarity Brain → Engine HTTP API `/conditions` | **Brain → customer API** |
| Orchestrator → `biological-brain`, `sector-intelligence-brain` code | platform → Brain implementation |
| Brain jobs → `brain_platform.py` shim → `../brain_platform` via `sys.path` | packaging |
| `scripts/hydrology/*` → `jobs/lake-surface/*` | research → runtime |
| `sector_wind/bowfishing*.py` → iOS-repo asset/doc paths | runtime → external repo layout |
| `docs/` → runtime (scoring JSON, conformance, xlsx, hydrology) | docs as code |

### 1.6 Cycles
No import cycle found. **Conceptual cycle risk:** Engine → Water Temp/Clarity science ⇄ those Brains consume Engine outputs (Clarity via `/conditions`). A change to customer `/conditions` can change a Brain's input.

### 1.7 Diagram (CURRENT)
```
 providers (in-line) ──► Engine ──────────────► apps
        │                  ▲  ▲
        │         shared   │  │ HTTP /conditions,/lakes
        ├──► Water Temp ───┘  └─── Clarity
        ├──► Lake  ─(TVA parser import from Engine)
        ├──► Wind (own Python clients)           all Brains ─► sector-brain (direct, shared writer)
        └──► Clarity (own satellite jobs)                          │
                                       Intelligence ◄── RTDB state ┘    Ops ◄── sector-brain
```

## 2. TARGET dependencies (proposed; not implemented)

```
providers ───────────────────────────────────────────┐
   ▲  (typed observations only)                       │
   │                                                  ▼
 brains/<id>/runtime ──► platform libs        engine/serving ──► apps
   │  reads only other Brains'                    ▲
   │  brains/<id>/contracts/ (published)          │ reads Brain-derived outputs ONLY via
   ▼                                              │ approved published contracts (class D, versioned cutover)
 brains/<id>/artifact ──► [Publisher] ──► sector-brain ──► Ops (read-only)
                              ▲
                  platform/orchestrator (Runner interface from brain.json; no sibling-dir imports)
```

| TARGET rule | Replaces |
|---|---|
| `providers` import nothing domain-specific; every provider has an owner and authorized consumers (`PROVIDERS.json`) | per-job and per-Brain clients |
| `engine/serving` → `providers`, `platform/contracts`; **no** `brains/*/runtime`. Exception only via declared *embedded adapter* libraries (Water Temp, Clarity science) declared as `customerIntegrationMode: embedded` in `brain.json` and reviewed | Lake↔Engine parser import, `Hydrology` in Engine |
| `brains/X` → `providers`, `platform`, and **other Brains' `contracts/` only** | Clarity→`/conditions`, Wind `lakes.json`, Lake→`TVAGenerationService` |
| `platform` → no Brain imports; Brains register through `brain.json` | orchestrator in-process dirs |
| **Lake Registry** (`platform/registries/lakes`, Platform-owned) is the dependency for lake **identity**; Lake Brain contracts (`brains/lake/contracts/`: hydrology, level, bindings, presence) are the dependency for lake **intelligence**. Consumers neither copy registry data nor depend on Lake Brain to resolve a lake | `lakes.json`, Clarity `/lakes` HTTP |
| Sector Intelligence dependencies derive from each Brain's `brain.json` (`publishes`, `consumes`) | `DEPENDENCY_ORDER` constants |
| Fish provides species intelligence; **Species Registry (`platform/registries/species`) provides identity**; Lake provides presence; Policy provides legality (ownership model preserved) | `SpeciesDatabase`/`SpeciesLegality` copies in Engine |
| Brain → Publisher only | direct writes (steady state) |
| `docs/` holds no runtime input | rubrics, fixtures, xlsx, evidence under `docs/` |

### Target dependency table (consumer → provider-of-contract; illustrative, each Brain's certification confirms its own list)
| Consumer | Consumes (published contract) |
|---|---|
| Wind | Lake Registry (identity, geometry reference); Lake Brain only if Wind needs lake intelligence |
| Fish | Species Registry; Lake (presence, environment) ; Water Temp (temperature state) — as available |
| Water Temp | Lake Registry (identity); Lake Brain (gauge bindings); providers (USGS, CWMS, Open-Meteo, TVA archive) |
| Water Clarity | Lake Registry (identity, geometry reference); **no customer `/conditions` or `/lakes`**; Water Temp / Wind optionally (context); providers (MRMS, Sentinel, USGS) |
| Depth | Lake Registry (identity); Lake Brain (level/pool); providers (CWMS, USGS) |
| Vegetation | Lake Registry (identity, geometry reference); Lake Brain (level); Clarity (light/clarity context) ; providers (satellite) |
| Sector Intelligence | every other Brain's published state, last in sequence |
| Engine/serving | providers; platform contracts; later Brain contracts per approved cutover |
| Ops | `sector-brain` read-only; Orchestrator API for requests |

### Target ownership of the three registry concepts
| Concept | Path | Generated from | Consumers |
|---|---|---|---|
| Brain Registry | `platform/registries/brains/` | `brains/*/brain.json` | Orchestrator, Publisher (path ownership), CI, Sector Intelligence dependency order |
| Lake Registry | `platform/registries/lakes/` | canonical lake source (Git identity table + released geometry) | Engine (`/lakes`), Lake Brain, Wind, Clarity, Water Temp, Fish, Depth, Vegetation |
| Species Registry | `platform/registries/species/` | canonical species release (CERT-8) | Fish Brain, Engine adapter, Lake presence validator |

### Publisher-related edges (TARGET, gated)
Brain → artifact → Publisher → `sector-brain` is gated by Gate P (findings F-1…F-9) and by the Publisher production-security question (certification/security lane; no private detail here). Legacy Wind paths without authorization under the new ownership model are classified **platform-owned / derived compatibility projection / legacy reader dependency** (F-5); Ops legacy health/job reads are preserved until a replacement contract exists (F-6).
