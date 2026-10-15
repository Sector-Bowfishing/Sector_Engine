# Provider and Customer-Serving Inventory

Base `fab115e9`. Everything here is **CURRENT** unless headed TARGET.

## 1. Four classes that must stay distinct

| Class | Meaning | Today |
|---|---|---|
| **A. Customer-serving Engine** | what the apps get from `sector-engine` (`/conditions`, `/conditions/batch`, `/lakes`, clarity/hydrology state) | `Engine/`, `Forecast/`, `API/`, `Sources/SectorEngineServer` |
| **B. Brain candidate/runtime** | what a Brain computes and publishes to `sector-brain` | per-Brain code; **not customer-visible** (`jobs/README.md`: all Brain jobs INTERNAL; Ops displays) |
| **C. Shared provider acquisition** | clients/parsers for external sources | Swift `Fetchers/`, `Engine/Adapters/`; Python in `wind-hourly`, `hydrology-hourly`, `water-temp-tva-archive`, `lake-brain/review`, `lake-surface` |
| **D. Brain-derived customer outputs** | customer features served from Brain state | **do not exist yet** (only the Water Temp and Clarity science are shared in-process with the Engine; no endpoint reads `sector-brain`) |

Rule for migration: A stays A until a deliberate, versioned cutover to D. A file's class is set by *who consumes its output*, not by what it is about.

## 2. Open-Meteo and customer conditions (the specific question)

| Use | Where | Class | Notes |
|---|---|---|---|
| Customer weather (wind, cloud, precip, weather code, sun times) for `/conditions` | `Fetchers/WeatherService.swift` (two hosts: forecast + historical-forecast), `Forecast/ConditionsForecast.swift`, `Forecast/ConditionsSnapshot.swift`, `Engine/WeatherCode.swift`, `Engine/Factors/WindFactor.swift` | **A** consuming **C** | Production wind is Open-Meteo in-process. `contract.py` and `jobs/README.md` both state the Wind Brain candidate is not in this path. **Not Wind Brain code.** |
| Water Temp Brain forcing | `Brain/WaterTemperatureBrain*.swift` via shared `WeatherService`; source id `open-meteo-forecast` | **B** consuming **C** | Same client as A. |
| Local-date handling (`timezone=auto`) | `WaterTemp/LakeLocalDate.swift` | B | |
| Clarity rain fallback (48 h) | `clarity_brain.py` (`rainfallFallback:open-meteo-48h`; MRMS preferred) | B | Obtained through the Engine `/conditions` response, not by calling Open-Meteo. |
| Wind benchmark & research | `sector_wind/provider_bakeoff.py`, `research/openmeteo_runs.py`, `provider_eval.py`, `stage3d2_eval.py`; Wind `contract.py` records `open-meteo-best-match` as the *production baseline* identity | **B / R** | A Python Open-Meteo client exists only for science comparison. |
| Platform source ownership | `ownership.py`: `"open-meteo-forecast": "water-temp"` | PL | Records which Brain publishes the *source-health record*, not who may call the provider. |

**Conclusion.** Open-Meteo has one production client (Swift, class C used by A and Water Temp B). The Python usage is research. The Wind Brain does **not** use the customer weather path. Classification must therefore be by consumer: `WeatherService` is a *provider client*, `WindFactor`/`ConditionsForecast` are *Engine*, the Wind Brain's wind logic is *Brain*, and the Python bake-off belongs to Wind research (not a production client).

## 3. Provider × implementation matrix (CURRENT)

| Provider | Swift implementations | Python implementations | Consumers (A = Engine, B = Brain) | Duplication |
|---|---|---|---|---|
| **Open-Meteo** | `WeatherService`, `ConditionsForecast` fetch, snapshot | `provider_bakeoff`, `openmeteo_runs` (research) | A, B:water-temp, (B:wind research), (B:clarity via A) | 1 prod client; research client acceptable |
| **USGS NWIS/OGC** | `USGSWaterData` (new OGC), `WaterLevelService`, `WaterTemperatureService` | `hydrology-hourly/hourly.py`, `lake-brain/review/build_review_pack.py` | A, B:water-temp, B:lake, B:clarity | **≥3** |
| **TVA** | `TVAGenerationService`, `LakeLevelFeeds`, `LakeBrainProfiles` | `water-temp-tva-archive/archive.py`, `hydrology-hourly`, `review/build_review_pack` | A, B:lake, B:water-temp (archive), B:clarity | **4–6**, with a **known behavioral divergence** ("Midnight" rows: Lake correct, production files 24 h early; decision D8) |
| **USACE CWMS** | `CWMSObservedService`, WaterTemp sensors | — | A, B:water-temp, B:lake | 1–2 |
| **SWPA / Alabama Power / USBR** | `SWPAGenerationService`, `AlabamaPowerGenerationService`; `data.usbr.gov` in Lake feeds | — | A, B:lake | 1 each |
| **NWS alerts** | `WeatherAlertsService` | — | A | 1 |
| **NOAA MRMS / IEM** | `MrmsPrecipService` | `clarity_brain.py`, `hydrology-hourly` (names) | A, B:clarity | 2 |
| **NOAA water (NWM/api.water.noaa.gov), tides** | in `WaterLevelService`/feeds | `research/*` | A, B:lake | 1–2 |
| **NOAA NBM / RTMA-RU / HRRR / RRFS / MADIS** | — | `sector_wind/{ingest,grib,rrfs,live}`, `research/*` | B:wind only | none (Wind-specific; acquisition could move to providers later) |
| **Sentinel-2 / STAC (Planetary, AWS), NASA CMR/ICESat-2** | — | `lake-surface/*`, `wind research/atl13*` | B:clarity, B:wind research | none |
| **Firebase RTDB / GCS / Cloud Run / Scheduler APIs** | `BrainRTDBStore`, `RemoteConfigStore` | `sector_brain_platform.gcp/rtdb`, dispatcher, preflight | PL, A | platform I/O (not providers) |

## 4. Customer-serving Engine inventory

| Part | Path | Note |
|---|---|---|
| Entry & routes | `Sources/SectorEngineServer`, `API/SectorEngineAPI.swift` | endpoints in `README.md` |
| Score | `Engine/Aggregator`, `Engine/Factors` (10 factors), `ConditionsConfig`, `ConditionsScoreVersion` (`conditions-score-v1`), RemoteConfig overrides | the only customer scoring path; "eventually Sector Intelligence" |
| Where-to-look, forecast, snapshot | `Engine/WhereToLook`, `Forecast/` | |
| Species & policy adapters | `Engine/Config/SpeciesDatabase`, `SpeciesLegality` | copies/adapters of Fish and Policy truth; D5 pending |
| Water level & dams | `Fetchers/WaterLevelService`, `Engine/Adapters/*`, `Engine/Region/TailwaterRegistry` | Lake-owned truth computed in parallel (ADAPTER) |
| Clarity | `Engine/Factors/ClarityFactor`, `Hydrology/VisibilityModel`, `API/{Clarity,Hydrology}API` | Clarity science in customer path |
| Lake directory | `Support/LakeDirectory.swift`, `API/LakeDirectoryAPI.swift` | the registry as served; embedded generated source |
| Static data | `docs/data/full_pool.csv`, `temp_sensors.csv` | read at generation time |

## 5. TARGET provider organization (proposal)

```
providers/
  PROVIDERS.json                ← registry: providerId, acquisition owner, authorized consumers, license, rate/cost, raw-cache policy, health source id
  swift/Sources/SectorProviders/   ← one target; per provider: client + parser + typed model (no domain interpretation)
  python/sector_providers/         ← same ids, Python clients (Wind NBM/RTMA, satellite, TVA archive)
  fixtures/<providerId>/           ← recorded responses shared by Swift and Python parity tests
```

* **Acquisition ≠ interpretation.** Providers return typed observations/forecasts and source health. Gate, regime, "is TVA generating", "water-temp estimate", "wind field at a bank" are Brain or Engine logic.
* **One owner per provider id** (acquisition owner: Platform, or a named Brain for a Brain-exclusive source such as NBM/RTMA for Wind), plus an **authorized consumers** list in `PROVIDERS.json`. A CI check fails if code outside the listed consumers imports the provider module.
* **Never `brains/X/openmeteo.py`.** If Wind later wants Open-Meteo it imports `providers/…/openmeteo`.
* **Customer `/conditions` weather** stays on `providers/openmeteo` consumed by `engine/`; moving to Brain-backed outputs is a separate decision per factor, behind a feature flag and `scoreVersion` bump (class D), never an implicit side effect of moving files.
* **Cross-language duplication** (TVA, USGS) is closed by a **shared fixture parity suite** (the technique `conformance/` already uses) and, over time, by letting Python jobs call the single Swift behavior only where needed. Do not port working code merely to dedupe.
* **TVA divergence (D8)** must be resolved *before* consolidating TVA into one client, otherwise consolidation would silently change customer generation timing.
