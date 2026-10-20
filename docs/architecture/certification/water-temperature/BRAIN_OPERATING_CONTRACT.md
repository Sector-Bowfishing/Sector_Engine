# Water Temperature Brain — BRAIN OPERATING CONTRACT

> Standard Brain Package V1, 19 sections. Read this first in every Water Temperature session. It states rules and decisions, never evidence, findings, handoffs or run logs; platform rules are cited, not copied.
> Contract version **0.1.0 (DRAFT, descriptive)** — Cortex standardization, 2026-10-20. Water Temperature is **not migrated**: there is no `brains/water-temperature/` package and no `brain.json` (`tools/architecture` forbids one before migration), so per `STANDARD_BRAIN_PACKAGE_V1.md` §2 this contract lives here and moves with the Brain. It **restates** `docs/brains/WATER_TEMP_BRAIN.md` (read its "Current state on main" note), the Brain Platform contract and the code; it adds **no new policy and no science**. Undecided items say **NOT ESTABLISHED** and name who decides.

## 1. IDENTITY
`brainId` **`water-temp`** (stable machine id, never renamed; the Ops contract uses `water-temp`; the reserved directory name is `water-temperature`). Display name "Water Temperature", slot `waterTemp`, snapshot field `waterTemperature`. Domain: lake surface water temperature. Lifecycle **CALIBRATION** (every lake's readiness is `CALIBRATION`; the former PRODUCTION/BETA values are now `evidenceClass` `sensor` | `modeled`); activity state **PARKED**. Runtime: Swift — `Sources/SectorEngine/Brain/WaterTemperatureBrain.swift`, `WaterTemperatureBrainRunner.swift`, `Sources/SectorEngine/WaterTemp/`, and the `WaterTempBrainJob` executable. Owner: the Water Temp lane (Michael approves).

## 2. MISSION
Water Temperature answers: **what is the water temperature doing?** For every directory lake it restates the production measurement-or-model selection (lake sensor ≤ 6 h and ≤ 15 mi, else nearby USGS gauge, else the `surface-energy-balance-v2` model, else unavailable) as Brain state, profile, registry, validation and health, with provenance. The selection is restated from the customer path, not shared, and pinned by tests, so the Brain publishes exactly production's numbers.

## 3. BOWFISHER DECISION
Water Temperature tells the bowfisher how warm the water is, whether that is measured or modelled, and which way it is trending — an input to when fish move shallow and when spawning conditions arrive. It does **not** judge fish activity, species behaviour, fishing quality or any Intelligence score; Sector Intelligence makes the bowfishing recommendation.

## 4. OWNERSHIP
Per lake: `lakes/{k}/states/waterTemp`, `lakes/{k}/profiles/waterTemp`, the snapshot leaves `snapshots/{k}/latest/waterTemperature` (+ `brainVersions/water-temp`), the `lakeFleet/{k}` leaves `readiness/waterTemp`, `modelVersions/waterTemp`, `slots/waterTemp`. Fleet runs: `brains/water-temp`, `validation/water-temp` (+ the four protected lakes' validation nodes), `health/brains/water-temp`, `health/jobs/water-temp-brain`, source health for `open-meteo-forecast`, `usgs-nwis-00010`, `usace-cwms-water-temp`, and its own activity events (`{ms13}-water-temp-{nnn}`). The water-temperature vocabularies (state `kind`, health, stale rule). Exact families: `WATER_TEMP_BRAIN.md` and `ownership.py` / Swift `BrainOwnership`.

## 5. NON-OWNERSHIP
Water Temperature does **not** own: lake identity (Engine directory); the shared lake-level fleet fields `stale`, `issueCount`, `hasObservations`, `riverSystem`, `lakeType`; `/schemaVersion`, `/health/engine`, `/health/rtdb`, `/validationOps`; the customer `/conditions` temperature (the customer Engine computes it; this Brain restates the same path); the research V2 candidate's promotion; scores (`/scores/water-temp` is written by the platform scorer).

## 6. DEPENDENCIES
- Providers (observed): lake temperature sensors (USGS, CWMS), the nearest USGS gauge (≤ 10 mi), Open-Meteo forecast for the model.
- Declared in `jobs.py` (`water-temp-brain`): `usgs-nwis-00010`, `usace-cwms-water-temp`, `open-meteo-forecast` and the TVA archive. The TVA archive is **declared but not read** by this Brain (only the Lake Brain reads it); reconciling the declaration is an open item.
- Lake Registry: the Engine directory (`LakeDirectory`). Other Brains: none. Platform: shared Swift Brain platform.
- Shared library target: the code lives in the customer `SectorEngine` library target (`Package.swift`), so changes there can affect both `/conditions` and this Brain.

## 7. COMMUNICATION CONTRACTS
- Published: the state, profile and registry shapes in `WATER_TEMP_BRAIN.md` (Swift types in `Sources/SectorEngine/Brain/` and `WaterTemp/WaterTemperatureState.swift`). There is **no Publisher publication contract** and no versioned JSON schema.
- Consumers: Sector Ops (display) and Sector Intelligence (published states). The serving process never imports the Brain code.
- Allowed path today: providers → `WaterTempBrainJob` → direct, ownership-checked RTDB updates (one atomic update per 50 lakes; LEGACY until a Publisher cutover is approved).

## 8. RESEARCH WORKSPACE
Logical workspace id **`water-temperature`** (`BRAIN_RESEARCH_WORKSPACE_V1.md`). Physical roots are never recorded here. Research (protected-lake truth, the V2 Kalman candidate) stays in the workspace; the private iOS documentation referenced by the frozen score stays private.

## 9. RESEARCH INITIATION RULES
**NOT ESTABLISHED** as a gap register: no `research/GAPS.json` exists yet (created at migration). Until then research starts only from a named open item — today the score blocker *Level-4 protected-truth sufficiency* (`docs/brains/scoring/frozen-scores.json`, `water-temp`) — and is approved by Michael.

## 10. RESEARCH STOP RULES
Stop when more work no longer changes the temperature context a bowfisher gets, when it needs protected field truth (forebay profiles, Sector loggers), another Brain or the Platform, or Michael's approval (model promotion, scheduling, spending). A stop is recorded, not worked around.

## 11. EVIDENCE HIERARCHY
Highest to lowest: (1) an in-lake surface sensor reading ≤ 6 h old; (2) a nearby USGS lake gauge; (3) the validated-globally surface-energy-balance model; (4) research candidates (never published as production). `OBSERVED_MODEL_CORRECTED` is not emitted (no assimilation). There is **no confidence value**: none is calibrated, and none is invented.

## 12. CANONICALIZATION
The production model and selection rule are canonical in the customer Engine code; the Brain restates them. The registry lists versions (`CURRENT` production model, `RESEARCH` V2 candidate, `RETIRED` k = 0.20). Promotion of a candidate is a separate decision (Michael) and deployment; no code here promotes anything.

## 13. VALIDATION
Documented evidence only: global leave-one-lake-out on 17 USGS lakes, status `GLOBAL_HOLDOUT_ONLY`; per-lake records only for the 4 protected development lakes (`INSUFFICIENT_TRUTH`, not scored). Swift tests pin the resolver semantics and vocabularies (`Tests/SectorEngineTests/WaterTemp*`, `WaterTemperatureBrain*`). Architecture certification is separate and never implies validation.

## 14. PUBLISHING
Direct ownership-checked RTDB writes; full-fleet runs also write registry, health, sources and activity. Health: `FAILED` (write failed or no lakes), `DEGRADED` (> 25 % unavailable or model fetch failed), `WARNING` (> 5 %), else `HEALTHY`. Stale: `evidenceStale` when a configured sensor has no fresh reading; registry `staleAfterHours` 6. Execution: Cloud Run job `water-temp-brain` from the `brain-jobs` image (`jobs/water-temp-brain/deploy-job.sh`), **no scheduler**, started by the Brain Orchestrator only when due; PARKED. Known inconsistency (open decision): the registry still publishes `schedule = "every 3 h at :25 UTC"`. `customerIntegrationMode`: none.

## 15. PATH OWNERSHIP
The families in §4, enforced client-side by `ownership.py` / Swift `BrainOwnership`. The Brain never writes another Brain's slot or the shared lake-level fields. No Publisher registry entry exists for Water Temperature yet.

## 16. SCORING
Score type `ENGINE_READINESS_SCORE` at `/scores/water-temp`: a **frozen** score (`water-temp-level-ladder-v1`, basis FROZEN, `docs/brains/scoring/frozen-scores.json`) published verbatim by the platform scorer. Certification, migration and documentation never move it.

## 17. COST RULES
No scheduler; orchestrator-started only when stale; a fleet run takes about 4–5 minutes at 1 vCPU (`deploy-job.sh`). The TVA archive job is PAUSED. Cost-freeze rules in `docs/brains/platform/cost-freeze/` apply; no new scheduled cloud work without approval.

## 18. SECURITY
This repository is public: no secrets, service-account keys, IAM detail or private research. Writer identity `brain-writer`; the breadth of its database role (`roles/firebasedatabase.admin`, project-wide) is an open platform item. The code refuses app-database URLs.

## 19. SESSION CLOSEOUT FORMAT
Every Water Temperature session closes with: gap addressed; bowfisher decision affected; evidence; files changed; tests run with PASS/FAIL/NOT_RUN; score before/after (equal unless an approved scoring change); open gaps; field validation needed; confirmation of what was not changed (live systems, schedulers, customer `/conditions`, model, science).
