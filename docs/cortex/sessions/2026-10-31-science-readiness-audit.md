# Science readiness audit, nine Brains (read-only): Session Record

```text
Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (clean), pack sector/engine (repository pin d5c8380, identical tree)
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/science-readiness-audit-2026-10-31 · Audited commit: ca669772 (origin/main) · Date: 2026-10-31
```

## 1. Scope
- **Request and mode:** overnight run (Sector_Ops issue 24, step 6). **Read-only audit**: for each of the nine target Brains, compare what the code does with its Cortex mission (`brain-architecture.md` / `.json`) and the 621-lake catalog, file a research issue in Sector_Ops for each gap, and note which Brains correctly return UNKNOWN when data is missing. No code changed; this record is the only change.
- **Inspected:** each `brains/<dir>/brain.json`, `research/CHARTER.json`, `research/GAPS.json` and test names; `control_manifest.json` scopes and activity; Cortex `mission-audit --repo`, `lake-audit --repo`, `ops-check --repo`; Wind `lakes.json`; the Water Clarity outlines file.
- **Not inspected:** production data (no credentials; not needed). Coverage figures for Lake come from `lake-audit`'s dated evidence (2026-10-27); the others come from repository scopes, not live counts.
- **Standing checks run:** `mission-audit --repo .`: 1 finding (`LEGACY_COMBINED`, expected). `ops-check --repo .`: 0 findings. `lake-audit --repo .`: table below.

## 2. Findings per target Brain
The four dimensions stay separate (core/release.md). Every Brain is runtime ready for its scope; none is domain validated or customer eligible. That is a valid operating state, not a failure.

| Target Brain | Deployed as | Mission vs code | Catalog coverage (of 621) | UNKNOWN when data is missing | Research issues |
|---|---|---|---|---|---|
| Water Clarity | `water-clarity` | clarity number computed (Engine models), no certified model; no class taxonomy | outlines 599; production run 2 pilot lakes; satellite pipeline PAUSED | **yes** (`test_freshness_unknown_unavailable_and_missing_evidence_are_honest`, `test_malformed_engine_payload_is_unavailable`, `test_missed_lake_keeps_state_and_ages_to_stale`) | Ops 25, 26 |
| Wind | `wind` | speed, direction, gusts, exposure, surface classes; strong-wind nights POD 0; assessment layer nonproduction | **4 lakes** | **yes** (`test_unknown_speed_is_none_not_zero`, `test_missing_gust_is_not_zero`, `test_unknown_bank_never_sheltered`) | Ops 27, 28, 29, 30 |
| Lake | `lake-brain` | level and trend partial; inflow (LB-08), releases (LB-09), outlooks (LB-18/19) and coverage assessment (LB-14) NOT_IMPLEMENTED; hypothesis guard LB-H3 violated | published **5**; accepted-reviewed 5; research-verified 412 | **yes** (Swift: `testNoReadingIsUnavailableAndUnboundNeverPublishesLevel`, `testAnArmWithNoSourceIsUnavailableAndSaysWhy`) | Ops 32, 33, 34 (+ decisions Ops 22) |
| Water Temperature | `water-temp` | surface temperature and forecast; seasonal bias; over-confident band; protected-truth gate not met | pilots | **yes** (Swift: `testMissingEnergyInputsDegradeInsteadOfGoingCold`, `testStaleSensorFallsBackToModelAndIsFlaggedNotHidden`) | Ops 31 |
| Depth | `depth` (PARKED, SHADOW-only) | effective depth unit-tested only; datum blocks most lakes; no approved release | none in production | **yes** (`test_absent_record_is_not_assessed_never_zero`, `test_low_coverage_is_unknown_not_none_and_fallback_is_flagged`) | Ops 37 |
| Vegetation | `vegetation` (PARKED, SHADOW) | surface observer failed held-out gates; no approved release | none in production | **yes** (`test_cloud_makes_unknown_not_no_plant`, `test_no_scene_is_empty_observation_and_unknown_presence`) | Ops 38 |
| Fish Brain | `biological-state` (combined) | species knowledge graded by public evidence only; none independently reviewed; capability publication INACTIVE | species knowledge fleet-wide by design; reviewed: none | **yes** (broadest abstention suite; unsupported rules abstain) | Ops 35 |
| Biological Brain | `biological-state` (combined) | behavioural state is an internal pilot on one lake; response bands ABSTAIN_NO_FIELD_VALIDATION; Depth and Vegetation inputs unpublished | 1 lake (pilot) | **yes**, by abstention (`responseBandOrSpawnWindow`) | Ops 36 (+ decisions Ops 20) |
| Sector Intelligence | `sector-intelligence` | synthesis runs on pilot lakes on unvalidated inputs; not validated; REQUIRED/OPTIONAL inconsistency and undeclared dependencies (engineering) | pilots | **yes** (`test_missing_and_stale_inputs_degrade_safely`, `test_consumed_brain_connects_and_degrades_when_stale`) | Ops 39 |

**UNKNOWN handling, summary:** all eight deployed packages, covering the nine target Brains, have tests showing that missing or stale inputs produce UNKNOWN, UNAVAILABLE, absence or abstention, never a fabricated value. No Brain was found predicting where data is missing. The gap is **coverage**: most of the 621 lakes have no supported state at all in Wind, Water Temp, Lake, Depth, Vegetation, the Biological pilot and Intelligence. Those lakes are absent or UNKNOWN, which is the honest answer.

## 3. Changes
None (read-only). 15 `type: research` issues were filed in Sector_Ops (25–39). Each records the gap, the question, the done condition and the evidence, and says that research is paused by the owner.

## 4. Verification
Commands above; no tests needed (no code change).

## 5–9
- **Decisions:** none new. The existing ones are Sector_Ops 18, 20 and 22.
- **Cortex gaps:** none.
- **Next step:** the owner prioritises the research issues once research resumes. Suggested first: Ops 27 (strong-wind nights, a safety-relevant miss), Ops 34 (Lake coverage, which caps every Brain that consumes Lake) and Ops 25 (clarity validation, the pilot Brain).
