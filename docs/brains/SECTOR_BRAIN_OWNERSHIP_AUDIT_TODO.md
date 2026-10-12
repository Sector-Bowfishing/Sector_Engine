# Sector Brain Ownership Audit: TODO (recorded, not fixed)

**Started:** 2026-10-12, while connecting Sector Intelligence to Sector Ops.

**Purpose:** input for the upcoming **Sector Engine Brain Ownership Audit** and the **Boundary / Overlap Audit** after it.

Nothing listed here was changed. Overlaps are recorded so they can be cleaned up deliberately, not as drive-by fixes.

**Columns:**
- **Current owner:** where the logic lives now.
- **Proposed owner:** the canonical Brain or layer.
- **Severity:** architectural importance.
- **Prod impact:** whether customers are affected today.
- **Migration risk:** how likely a move is to change customer results.

Code references:
- **Engine:** `deployed/sector-engine-00072-way` (`bc9e09fb`).
- **iOS:** `Michael-Master` (`afc0095e`).

| ID | Current file | Current owner | Proposed owner | Severity | Prod impact | Migration risk | Note |
|---|---|---|---|---|---|---|---|
| O-01 | Engine `Sources/SectorEngine/Engine/Config/SpeciesDatabase.swift` | Conditions Score | Biological Brain (species knowledge); Engine policy layer (legality/tier) | HIGH | Yes: drives spawn regime, boost and species name | HIGH | 18 species with spawn °F, month windows, region presence and latitude caps. Conflicts with research are already published as DISC-004/005/006 |
| O-02 | iOS `Sector/FishIntel/BiologicalState/SpeciesStateModels.swift` | iOS FishIntel | Biological Brain | HIGH | Not released | MEDIUM | A third copy of spawn/season temperature windows |
| O-03 | iOS `Sector/FishIntel/Species/SpeciesKnowledgeBase.swift` | iOS FishIntel | Biological Brain canonical bundle | MEDIUM | Not released | LOW | Literature evidence for 7 species; predates the research (DISC-007) |
| O-04 | iOS `Sector/FishIntel/Species/WaterbodySpecies.swift` | iOS FishIntel | Lake Brain (lake-species presence) | HIGH | Not released | MEDIUM | Guntersville presence hardcoded; conflicts DISC-001/002/003 |
| O-05 | Engine `Engine/Aggregator/ConditionsAggregator.swift` (dormant text "No run — carp spawn Apr–Jun") | Conditions Score | Biological Brain (season) | LOW | Yes: customer copy | LOW | Hardcoded separately from the SpeciesDatabase windows |
| O-06 | `ConservationGate.swift` in iOS `Sector/FishIntel/Policy/` **and** Engine `Engine/Config/` (5A branches) | Two copies of one policy table | Engine policy layer (single table keyed by Biological Brain species IDs) | MEDIUM | Not deployed | MEDIUM | The Engine copy says it mirrors iOS; the Engine part changes spawn scoring |
| O-07 | Engine `Engine/Config/SpeciesLegality.swift` | Conditions Score | Engine policy layer | MEDIUM | Yes | LOW | A global denylist; no per-state legality |
| O-08 | Water-temperature thresholds in 4 places: `ConditionsConfig.WaterTemp` bands (50/60/68/82/88), cold-water gates (48/45 °F), `WhereToLook/WhereToLookEngine.swift:100,104` (58/86, hardcoded), SpeciesDatabase spawn minimums | Conditions Score | Water Temp Brain owns the value; Biological Brain owns fish responses; Intelligence owns scoring weights | MEDIUM | Yes | MEDIUM | Thresholds don't agree with each other |
| O-09 | Wind thresholds: `WindFactor` (4/7/11/15/20 mph), seeability `windCurve` (7/12/15/20/30), gate 20, `WhereToLookEngine` (4/11 hardcoded), Wind Brain `contract.py` (5/10/15/20, trend 2) | Conditions Score + Wind Brain | Wind Brain owns wind state and categories; Intelligence owns bowfishing impact | MEDIUM | Yes | MEDIUM | Five threshold sets |
| O-10 | Engine `Engine/Factors/WaterLevelFactor.swift` (0.5 ft "at full pool" hardcoded) + `ConditionsConfig.Level` (0.2/1.0/−1.0) | Conditions Score | Lake Brain owns the lake-specific level state (seasonal normal, percentiles); Intelligence owns the fish impact | MEDIUM | Yes | MEDIUM | See the Lake Brain audit (Intelligence 22): full pool vs seasonal guide curve, and the gauge-height proxy shown as "water" |
| O-11 | `WhereToLookEngine.swift:85,89` (2.5 ft / 12 ft clarity, hardcoded) vs config gate 1.0 ft, reservoir floor 1.1 ft, curve 0–4 ft | Conditions Score | Water Clarity Brain owns clarity classes; Intelligence owns impact | LOW | Yes | LOW | — |
| O-12 | `/conditions` fetches and computes temperature, clarity, wind, level and generation in-process (`Fetchers/`, `Engine/Adapters/`, `Hydrology/`) | Conditions Score | Each specialised Brain computes its state; Intelligence consumes the states | HIGH | Yes: all customer intelligence | HIGH | The root overlap. No Brain is consumed by any Intelligence implementation |
| O-13 | Conditions Score has no version constant; Remote Config overrides tuning without a version in the response | Conditions Score | Sector Intelligence (`intelligenceVersion`, `inputVersions`) | HIGH | Yes: results can't be traced to a version | LOW | Needed so "Sector said X last night" can be reconstructed |
| O-14 | Water Clarity Brain (`brain/water-clarity`, `jobs/water-clarity-brain/`) restates `/conditions.clarityVisibility` | Engine `/conditions` is the computer; the Brain is a mirror | Water Clarity Brain computes; Intelligence consumes | HIGH | No (brain output is portal-only) | HIGH | The dependency runs Engine → Brain, the reverse of the target |
| O-15 | Wind Brain writes `lakeFleet/{k}/modelVersions/wind = wind-candidate-…` while production wind is Open-Meteo Best Match | Wind Brain | Wind Brain (label production vs candidate explicitly per lake) | MEDIUM | No | LOW | A fleet consumer could read the candidate as the serving model |
| O-16 | iOS `Sector/SwiftData/Models/ConditionsEngine/ConditionsConfig.swift` (weights, spawn settings) still read by `MyLakes.swift:1641`; iOS `ConditionsEngine/Adapters/*` (CWMS, DamGeneration, TVA, SWPA) | iOS leftovers from the on-device engine | Engine (delete from iOS if dead) | MEDIUM | Unknown | LOW | iOS says "there's no on-device engine anymore" |
| O-17 | iOS `Sector/FishIntel/Huntability/` computes its own 0–100; clarity parsed from the Engine factor *label* (`Map.swift:1489-1496`) | iOS FishIntel | Sector Intelligence (Engine) consumes structured Water Clarity state | MEDIUM | Not released | MEDIUM | The code calls it "a bridge, and an ugly one" |
| O-18 | iOS FishIntel bundled Landsat water-temperature and Sentinel-2 clarity grids (`Assets.xcassets/FishIntel/*`, built by `scripts/fishintel/*.py`) | iOS FishIntel | Water Temp Brain / Water Clarity Brain (lake-surface job) | MEDIUM | Not released | LOW | Single dated passes, not live |
| O-19 | iOS `Sector/FishIntel/Lake/LakeRegistry.swift`, `LakeCapability.swift` (manifests) | iOS FishIntel | Engine directory + Lake Brain profile | MEDIUM | Not released | LOW | Uses canonical lake IDs already |
| O-20 | iOS FishIntel takes conditions for the dashboard location but always uses the Guntersville profile | iOS FishIntel | Sector Intelligence (lake-scoped input envelope) | MEDIUM | Not released | LOW | Possible location mismatch |
| O-21 | Sector Ops Intelligence page (before this branch): Engine `topReasons` labelled "Intelligence drivers"; a "Key conditions" panel assembled from Engine factors; a mock 8.6 rating | Sector Ops | Engine publishes; Ops renders | LOW | No (internal portal) | LOW | Corrected on Ops branch `feat/sector-intelligence-brain` (labels say "Engine Conditions Score"; mock rating removed) |
| O-22 | `brain_platform.py` copied in 3 Python jobs (clarity, biological, intelligence); Swift `BrainPlatform.swift` in `brain/water-temp` and `sector/lake-brain` | Each brain | One shared Brain platform module | MEDIUM | No | LOW | Two languages, four copies |
| O-23 | Lifecycle vocabularies differ: water-temp/wind `status`; clarity `status` + `lifecycle`; biological `status` + `responsibilities.*.status`; intelligence implementation lifecycles | Each brain | Platform-wide vocabulary | MEDIUM | No | LOW | Ops colours known values and shows the rest verbatim |
| O-24 | Lake → species presence path: Biological contract §10 proposes `/lakes/{k}/speciesPresence`; the Lake Brain audit proposed `/lakes/{k}/species` | Unratified | Lake Brain | MEDIUM | No | LOW | Reconcile before either is written |
| O-25 | Water Temp Brain is a one-time manual snapshot (`26d5ddaf+local`, 2026-10-12 06:40Z) with `staleAfterHours: 6`, so it reads STALE | Water Temp Brain | Brain Orchestrator (scheduling) | LOW | No | LOW | The Intelligence dependency view shows it as STALE |
