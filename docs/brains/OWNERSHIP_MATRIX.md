# Sector Ownership Matrix

**Owner:** Sector Engine. **Version:** 2026-10-12 (consolidation Phase 8). Principle: *Engine owns
truth, Ops owns presentation.* One canonical owner per scientific fact, model, rule and identifier;
everything else is an adapter, a documented exception, or a migration.

Status vocabulary: **RESOLVED** (one owner, duplicates removed or adapters in place) ·
**ADAPTER** (a second copy exists behind a documented compatibility shim or parity test) ·
**EXCEPTION** (a HIGH duplicate that Engine cannot resolve alone; migration owner and plan named) ·
**OPEN** (not yet addressed; not HIGH).

| Domain / asset | Canonical owner | Where it lives today | Status | Notes / migration |
|---|---|---|---|---|
| Lake identity (`"<name>|<state>"`, 621 lakes) | **Lake Registry** = Engine directory (`Support/LakeDirectory.swift`, `GET /lakes`) | Engine; Android bundles a copy (`LakeDirectory.kt`); iOS `LakeRegistry.swift` | **EXCEPTION** (clients) | Clients must read `GET /lakes`; directory copies drift. Owner of the migration: iOS/Android releases. |
| RTDB / bucket lake key | Lake Registry (`BrainPlatform.lakeKey` / `sector_brain_platform.lake_key`) | one algorithm, 2 implementations + Ops `lakeKey.ts`; **`ClarityStateLoader.slug` fixed** (was `\|`→`_` only, diverged for 565/621) | **RESOLVED** (Engine) · ADAPTER (Ops copy, fixture-tested by contract) | Conformance fixtures pin the cases. |
| Dam / tailwater rosters | Lake Registry (identity) + Lake Brain (bindings) | `Engine/Region/TailwaterRegistry.swift`, `Adapters/DamGeneration.swift`; `wip/gauge-context-2026-09-14` (`DamRoster`, NHDPlus reaches) | OPEN | Fold into Lake Brain source bindings when the gauge-context work is reviewed. |
| Water level, trend, flood pool, history, operator guide | **Lake Brain** | Lake Brain (`Sources/SectorEngine/LakeBrain`, 5 pilots); production `/conditions` computes level from `WaterLevelService` + `WaterLevelFactor` | ADAPTER | `/conditions` keeps its own level path until Phase 9 consumes Lake Brain state; parity = same sources, different fetch cadence. |
| **TVA "Midnight" rows** | Lake Brain's parser (correct: hour-ending) | production `TVAGenerationService.date` files them 24 h early | **EXCEPTION — decision D8** | Fixing production changes customer-visible generation timing; needs Michael's OK. Lake Brain parses correctly; no silent change made. |
| Lake → species presence | **Lake Brain** (`/lakes/{k}/speciesPresence`) | Lake Brain (5 pilots); Engine `RegionResolver` + `SpeciesDatabase.regions` (region presence for scoring); iOS `WaterbodySpecies`, `PresenceConfidence` | ADAPTER (Engine) · **EXCEPTION** (iOS) | Engine's region rule stays as the Conditions Score adapter until Intelligence consumes Lake Brain presence; iOS models migrate when Intelligence serves presence. |
| Water-temperature science (model, resolver, freshness) | **Water Temp Brain** | one Swift module (`WaterTemp/`, `Fetchers/WaterTemperatureService.swift`) used by both `/conditions` and the Brain — **one implementation** | RESOLVED (Engine) | Freshness constants: 72 h fetch window vs 6 h resolver window are *different* questions (candidate age vs shown-as-measured); documented in `WATER_TEMP_BRAIN.md`. |
| Water-temp model constant `k` | Water Temp Brain (`k = 0.09`, `surface-energy-balance-v2`) | Engine main 0.09; **iOS `Michael-Master` 0.20, Android `Michael-Master` 0.20** (iOS `fix/water-temp-calibration` has 0.09) | **EXCEPTION** (clients) | Clients should stop modelling and read `/conditions.waterTemp` (already shown = scored). Migration owner: iOS/Android. |
| Spawn temperatures / species knowledge | **Biological Brain** (`/species/{id}`, species-v2) | Engine `Config/SpeciesDatabase.swift` (18 rows, used by `SpawnFactor`); iOS FishIntel `SpeciesStateModels` (values disagree with Engine) | ADAPTER (Engine) · **EXCEPTION** (iOS) | Engine's table is the Conditions Score adapter until Intelligence consumes Biological knowledge; values to be reconciled against the species-v2 bundle (research decision, not Engine's). |
| Spawn regime / staging thresholds (60 / 70 °F) | Sector Intelligence (impact) + Biological (response) | `ConditionsConfig.Spawn` | ADAPTER | Unchanged; versioned by `scoreVersion`. |
| Legality / conservation gate | **Policy layer** | `Config/SpeciesLegality.swift` inside the scoring path; L7 conservation gate on `deploy/intel-guardrails-5a` + iOS `Policy/` | **EXCEPTION — decision D5** | Not merged (customer behavior). A `Policy/` module is the target home when D5 is decided. |
| Clarity science (visibility model, rain decay) | **Water Clarity Brain** | production `Hydrology/VisibilityModel.swift` + `ClarityFactor`; the Brain mirrors `/conditions` (documented, `inCustomerEstimate: false` for satellite) | ADAPTER | The Brain is the publisher of production clarity state, not a second model. R3.1 stays a candidate (D4/approval). Android `ClarityModel.kt` (floor 0.9 vs 1.1) is a client EXCEPTION. |
| Gin-clear rule (12 ft / ≤ 3 mph) | Conditions Score config (`ConditionsConfig.Clarity`) | **was hard-coded in `WhereToLookEngine` — now reads the config constants** | RESOLVED | Parity: same default values. |
| Wind science (surface physics, fetch) | **Wind Brain** | `jobs/wind-hourly/sector_wind` (Python); iOS `WindSurfacePhysics.swift` declared source-of-truth; production `/conditions` wind = Open-Meteo in-process | ADAPTER (Engine) · **EXCEPTION** (iOS mirror) | Production wind is unscored and stays until a deliberate migration (audit D-wind). Swift/Python mirror: one must become the reference — research decision. |
| Wind fetch-table geometry | **Lake Registry** (geometry) | generated in the iOS repo (`scripts/wind/build_fetch_tables.py`) and copied to GCS | **EXCEPTION** | Move the generator to Engine `scripts/` when Wind is next rebuilt. |
| Bank ranking / nearby alternatives | **Sector Intelligence** | `sector_wind/bowfishing.py` (`rank_banks_for_wind`, `nearby_alternatives`), iOS Huntability | OPEN (research-only; not published to customers) | Lift into Intelligence when Phase 9 synthesis consumes Wind state. |
| Wind thresholds (~11 sets) | Wind Brain (state bands) + Intelligence (impact) | Engine config + hard-coded notes/copy; **dead `BowfishingConditions.windScore` removed** | OPEN (values unchanged, now versioned) | Centralize when Intelligence consumes Wind state. |
| Conditions Score (factors, gates, bands) | **Sector Intelligence** (eventually) | `Engine/Aggregator`, `Engine/Factors` — the only customer path | ADAPTER | **Now versioned:** `ConditionsResponse.scoreVersion = conditions-score-v1`, `engineRevision`. |
| Conditions Score config overrides | Intelligence | Firebase Remote Config `conditions_config` | OPEN | Report the override hash in a future `configSource`. |
| Brain publishing (platform) | **Brain Platform** | `Sources/SectorEngine/Brain` (Swift) + `sector_brain_platform` (Python), one contract, one fixture suite; **Wind migrated off its adapter** | RESOLVED | |
| Shared fleet fields (`lastUpdatedAt`, `stale`, `issueCount`, `hasObservations`), snapshot `generatedAt`/`snapshotVersion` | **Brain Orchestrator** (rollup) | nobody writes them (contract §5) | RESOLVED (absent until the Orchestrator) | Ops derives from `slots/*` (Phase 10). |
| Source records / source health | the owning Brain (contract §6 table) | each Brain | RESOLVED | |
| Brain scores / Engine score | **Brain Platform** (`brain-platform` writer) | `/brains/{id}/score`, `/engine/score` | RESOLVED | Ops never computes. |
| Scheduling / recompute | **Brain Orchestrator** | per-brain `plan()` + `descriptor`; cron per job | OPEN (Phase 11) | |
| Presentation | **Sector Ops** | Ops; but Ops also computes staleness, health roll-ups, score choice in the browser | OPEN (Phase 10) | Engine publishes the rollups; Ops renders. |

## HIGH duplicates with an explicit exception (cannot be closed inside Engine)
1. Client-side water-temp model `k = 0.20` (iOS, Android default branches) — Engine is correct; clients must consume the Engine value.
2. Client-side lake directory copies (Android) — consume `GET /lakes`.
3. Spawn temperatures: Engine `SpeciesDatabase` vs iOS FishIntel vs Biological species-v2 — a research reconciliation, then Engine adapter update, then Intelligence consumption.
4. iOS presence models (`WaterbodySpecies` vs `PresenceConfidence`) contradict each other — Lake Brain presence is canonical; iOS migrates.
5. TVA midnight parser in production — decision D8 (customer-visible timing).
6. Wind physics Swift/Python mirror and iOS-generated fetch geometry — research/ownership decision.
7. L7 conservation gate — decision D5.

Everything else is RESOLVED, an ADAPTER with parity preserved, or OPEN at non-HIGH priority with its target phase named.
