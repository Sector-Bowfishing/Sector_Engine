# Orchestrator G1/G2 — Execution Health and Dependency/Freshness Health (`brain-health-v1`)

**Owner:** Sector Engine / Brain Platform (platform writer `brain-platform`). **Status:** merged to `main` (PR #21 `4a14e17f`, PR #22 `2da861f6`); publication phase on `feat/health-plane-publication-v1` (§10: HEALTH_PLANE_V1 publication, `orchestrate.py --health-only`). The health plane stays opt-in: no default cycle publishes it. Not Architecture Certified.

> Engine owns truth, Ops owns presentation. A Brain owns its domain truth; the Orchestrator owns execution coordination and execution / dependency health; the Publisher owns the production doorway. **Process health is not evidence freshness.** `lastSuccessfulRun` is process history. Unknown is `UNKNOWN` (Ops renders `—`), never zero, never green.

Code: `jobs/brain_platform/sector_brain_platform/{execution_health,dependency_health,dependency_declarations,signals,brain_health}.py` · glue `jobs/brain-orchestrator/control_plane.py` (`build_health_state`, `observe_dependencies`, `expected_interval_hours`) · registry `platform/registries/signals/signals.json` · schemas `contracts/schemas/{brain,registry-signals}.schema.json` · fixture `contracts/conformance/health_v1.json` · sample `orchestrator/sample_health_state_synthetic_2026-10-16.json` · tests `jobs/brain_platform/tests/test_{execution_health,dependency_health,dependency_declarations,brain_health}.py`, `jobs/brain-orchestrator/tests/test_health_plane.py`, `tools/architecture/tests/test_foundation.py` (invariant 17).

## 1. Five health concepts, published side by side
| Concept | Question | Vocabulary | Source (G1/G2) |
|---|---|---|---|
| **process** (G1) | did the job execute, when, did it succeed, is it running, was it skipped and why, which code, is the cadence itself late | `processHealth` = contract HEALTH (`HEALTHY WARNING DEGRADED FAILED UNKNOWN NOT_CONFIGURED`); per execution `executionStatus` ∈ `RUNNING SUCCEEDED FAILED SKIPPED DEGRADED UNKNOWN`; `cadence.status` ∈ `ON_CADENCE OVERDUE NOT_EXPECTED UNKNOWN` | execution records (`orchestration.execution_record`, Cloud Run executions, `/health/brains/{id}` for in-process Brains) |
| **dependencies** (G2) | were the declared dependencies available and the requirement satisfied | `dependencyStatus` ∈ `SATISFIED DEGRADED UNSATISFIED UNKNOWN` (model v1 words + UNKNOWN); `availability` ∈ `AVAILABLE MISSING UNKNOWN` | declared rows (`brain.json`) × observations (registry, `/sources`, Signal Registry) or the execution's **recorded consumption** |
| **freshness** (G2) | was the evidence behind the REQUIRED dependencies current when consumed | `freshnessStatus` ∈ `FRESH STALE EXPIRED UNAVAILABLE UNKNOWN` (the Publisher's words, `enums.FRESHNESS_STATUS`) | owner verdict / owner rule / consumer rule (`freshnessAuthority`) |
| **domainValidation** | does the Brain trust its scientific result | model v1 `VALIDATION_STATUS` + `UNKNOWN` | pass-through from the Brain (`validationStatus` / `/validation/{id}.status`); never computed by the platform |
| **publish** | did the Publisher accept / publish | `REJECTED SHADOW SKIPPED_UNCHANGED PUBLISHED NOT_APPLICABLE UNKNOWN` | pass-through of the Publisher's publication record; `UNKNOWN` until wired |

`aggregate` is an **operational** presentation helper only: worst *known* component among process, dependencies, freshness, publish, with one floor (an UNKNOWN process ⇒ UNKNOWN: nothing is healthy while nobody knows whether it ran). Unknown components are always listed in `unknownComponents`. Domain validation is never folded in.

## 2. Published node — `control/healthV1/*` (platform writer only; opt-in)
| Section | Content |
|---|---|
| `summary` | `version, asOf, engineMode, brainCount, aggregateCounts, unknownDeclarations[], graphWarnings[], note` |
| `brains/{id}` | `process{processHealth, processHealthReasons[], running?, lastExecution, lastSuccessful?, lastSuccessfulAt?, lastFailed?, lastError?, consecutiveFailures?, codeVersions?, brainReportedHealth?, cadence{...}}`, `dependencies{dependencyHealth, freshnessHealth, declared, counts, rows[], declaredVsActual{consumptionRecorded, declaredAndConsumed, declaredNotConsumed, consumedNotDeclared}, basis RECORDED_CONSUMPTION|CURRENT_STATE}`, `freshness{status, basis}`, `domainValidation{status, source}`, `publish{status,…}`, `aggregate{status, worstComponent?, unknownComponents?, inputs}` |
| `dependencies` | the **declared graph** Ops renders: `brains/{id}{source, declarationsKnown, legacy?, rows[]}`, `edges[{from, to, dependencyType, requirement?, legacy?}]`, `warnings[]` |
| `signals` | Signal Registry definitions (`signalId, displayName, status, unit?, producer?`) — never consumers |

Written as whole sections, only when content changed (timestamps `asOf/evaluatedAt/ageHours…` ignored; `brain_health.changed_paths`). Ops reads it under the existing read-only `/control` rules; it computes nothing. Canvas learns *Brain A depends on Signal B* from `dependencies.edges`, *execution XYZ consumed state ABC* from `brains/A.dependencies.rows[].lineageRef` + `declaredVsActual`, *Signal B fresh/stale/unknown* from `rows[].freshnessStatus`, *execution healthy/degraded/failed* from `process`. **No table of Brain dependencies may exist in Ops/Canvas source.**

## 3. Dependency declarations — ONE Brain-owned source
A Brain declares what it consumes in its own `brain.json` (`contracts/schemas/brain.schema.json`, additive change):
- `consumes[]`: `kind ∈ brain | registry | signal` (new: `signal` + `signalId`, defined in the Signal Registry); optional `requirement ∈ REQUIRED | OPTIONAL`; optional `freshness {maxAgeHours, reason}` (the consumer's own, stricter need; a reason is mandatory — FRESHNESS_MODEL.md). `contractId`/`minVersion` stay required for `brain`/`registry`.
- `providers[]`: optional `requirement`, `freshness` on each provider entry.
- Absent `requirement` = *not declared*: reported as `requirementDeclared: false` and treated as REQUIRED (fail closed), with the reason stated. Never defaulted silently.

Dependency types (closed): `BRAIN`, `ENVIRONMENTAL_SIGNAL`, `PROVIDER_DATA`, `PLATFORM_REGISTRY`. Dependency ids: `brain:<id>`, `signal:<id>`, `provider:<id>`, `registry:<name>`. `dependency_declarations.declared_dependencies()` / `resolve()` / `dependency_graph()` discover and resolve them against the Brain set, the Signal Registry and `providers/PROVIDERS.json`. **The platform never writes a relationship in code** (tested: no Brain/signal/provider id string in any health module; invariant 17 fails closed when a platform manifest claims an edge a registered Brain does not declare).

### Shared Signal Registry (`platform/registries/signals/signals.json`)
Platform-owned **definitions** of shared environmental signals (barometric pressure, pressure trend, precipitation, air temperature, humidity, cloud cover, moon phase). It never says who consumes a signal and holds no interpretation. All entries are `DECLARED` (no producer): a declared consumption evaluates `UNAVAILABLE` until a producer registers (`status: AVAILABLE`, `producer`) by a reviewed change to the file.

### Declared vs actual
An execution record may carry `consumed[]` (`execution_health.CONSUMED_KEYS`: `dependencyId, dependencyType, ref, stateVersion, fingerprint, artifactId, generatedAt, evidenceObservedAt, publishedAt, consumedAt, freshnessStatus, staleAfter, expiresAt`) — what it **actually** consumed, with the owner's freshness verdict/rule as of consumption. When present, dependency rows are judged at `consumedAt` against the consumed state (`evaluationBasis: RECORDED_CONSUMPTION`) and `declaredVsActual` reconciles the sets. When absent, `consumptionRecorded: false` and rows are judged against the current observation (`CURRENT_STATE`). **No producer records `consumed[]` yet** (gap, §7); nothing is fabricated.

## 4. Freshness rules (unchanged authority, now generic)
Observed per dependency type: BRAIN → `/brains/{id}` (`freshness.*`, `freshnessStatus`, `stale`/`evidenceStale`, `staleAfter`/`expiresAt`, `staleAfterHours` + `generatedAt`/`sourceObservationAt`); PROVIDER_DATA → `/sources/{id}` (`latestObservationAt`/`latestIssuedAt`, the owner's `staleThresholdHours`) + `/health/sources/{id}`; ENVIRONMENTAL_SIGNAL → Signal Registry availability only (no runtime signal publication exists); PLATFORM_REGISTRY → not versioned yet (UNKNOWN).
Order of authority (`freshnessAuthority`): the owner's **verdict** (`freshnessStatus`, `stale`/`evidenceStale`) → the owner's **rule** (`expiresAt`, `staleAfter`, `staleAfterHours` × an evidence/generated timestamp) → UNKNOWN. A consumer `freshness.maxAgeHours` can only make FRESH/UNKNOWN **stricter** (`CONSUMER_RULE`, reason recorded), never loosen a STALE. A record offering only `lastSuccessfulRun` is UNKNOWN with the reason "process history, not evidence freshness" (tested). Aggregates: `dependencyHealth` = worst requirement verdict; `freshnessHealth` = worst `freshnessStatus` over REQUIRED rows (an unknown required input is never promoted to FRESH; no declared/REQUIRED dependency ⇒ UNKNOWN, not vacuously FRESH).

## 5. Backward compatibility (OLD → NEW → migration → removal gate)
| OLD | NEW | Migration path | Removal gate |
|---|---|---|---|
| `jobs.MANIFEST[jid].brainDependencies` (hand-maintained, `/jobs` record field) | `brain.json consumes[kind=brain]` → `control/healthV1/dependencies` | `/jobs` unchanged; `test_dependency_declarations.py` asserts equality for every registered Brain; `dependency_declarations.drift()` reports divergence | all job owners registered (brain.json) **and** Sector Ops reads `control/healthV1/dependencies` instead of `/jobs.brainDependencies` |
| `control_manifest.json brains.*.dependencies` (platform-authored Brain→Brain) | `brain.json` for registered Brains | legacy rows published with `legacy: true` for unregistered Brains only; invariant 17 + `drift()` fail closed if the manifest claims an edge a registered Brain does not declare | per Brain at migration; the manifest keeps only execution intent (`onStale`, `usesFields`) once every Brain registers |
| RTDB registry `dependsOn[]` (read by the legacy planner `orchestrator.py`) | same | untouched this phase | legacy planner retirement (ORCHESTRATOR_CONTROL_V1 stage 4) |
| `orchestration.dep_status()` and `control_state.brains.*.freshness` derive FRESH/STALE from `lastSuccessfulRun` | `dependency_health` (evidence timestamps / owner verdicts) | unchanged decision behaviour this phase (no execution change); the new rows are published beside it | when observations carry evidence timestamps for every dependency type the decision model needs (then `dep_status` reads `dependency_health` rows) |
| execution record `status` `STARTED` | `RUNNING` (normalised by `execution_health.normalize_status`; producers unchanged) | `LEGACY_EXECUTION_STATUS` map, conformance cases | none needed |
| `execution_record()` call signature | additive kwargs `code_version`, `consumed`, `job_id` | old calls unchanged (tested) | — |

`/jobs` (jobs-v1) is **not** changed: no new fields, no rewrite of records. Implication: `brainDependencies` is now a legacy mirror of a Brain-owned declaration; Ops should prefer the health plane once published.

## 6. Cost and runtime
No new service, no new scheduler, no provider. The health plane is computed only when `--emit-health-state` or `--publish-health` is passed (two extra read-only GETs: `/sources`, `/health/sources`); publication is content-aware. `deploy-job.sh` stages `brains/*/brain.json`, `platform/registries/signals/signals.json` and `providers/PROVIDERS.json` as read-only inputs; without them the plane reports declarations UNKNOWN (never invents). Nothing was deployed by this phase.

## 7. Known gaps (stated, not papered over)
1. **Actual consumption lineage is not produced yet.** No Brain or the orchestrator writes `consumed[]`; every row is `CURRENT_STATE`. Wind's Publisher artifact already carries per-section freshness; the next step is for producers to emit `consumed[]` (orchestrator for in-process Brains from their `--plan`/`--write` output; Wind from its artifact builder).
2. **Brain-level evidence freshness is UNKNOWN for most Brains**: registries publish `lastSuccessfulRun` and `staleAfterHours` but no `freshness` block / `evidenceObservedAt`; the per-lake state envelopes do (contract §4) but are not aggregated to Brain level here. Wind's `/sources/*` do carry evidence timestamps + the owner's threshold, so Wind's provider rows evaluate.
3. **Signals**: definitions only; no producer, no runtime observation.
4. **Platform registries** (`lakes`/`species`/`brains`) publish no contract version → `UNKNOWN`.
5. **Publish health**: pass-through only; the Publisher is not wired into any job.
6. **Domain validation**: pass-through of `validationStatus` when a Brain publishes one in the model v1 vocabulary; most do not.
7. Legacy planner tie-break list `orchestrator.DEFAULT_ORDER` still names Brain ids (ordering only, not dependencies) — left for the legacy planner's retirement.
8. Swift tests were not run (no Swift source changed; the new conformance fixture is loaded by name only in Swift).

## 8. Gates
- Invariant **17** (`tools/architecture/report.py`, report-only like the rest): signal dependencies exist in the Signal Registry (and are not RETIRED), a consumed Brain lists the consumer in `authorizedConsumers`, `freshness` needs `maxAgeHours` + `reason`, and no `control_manifest.json` edge exists for a registered Brain that its `brain.json` does not declare.
- `test_no_brain_or_signal_or_provider_id_is_hardcoded_in_the_health_modules` (platform), `test_jobs_manifest_brain_dependencies_are_legacy_and_consistent_with_declarations`, `test_legacy_manifest_rows_only_for_unregistered_brains_and_drift_fails_closed`.
- `test_package_is_not_imported_by_the_platform_package…` still holds: the health modules import nothing from the Publisher; `enums.FRESHNESS_STATUS` is tested equal to `publisher.model.FRESHNESS_STATUSES`.
- Conformance: `contracts/conformance/health_v1.json` (vocabularies + cases) mirrored by `test_brain_health.py`; hash pinned in `verification/fixtures/conformance/manifest.json`.

## 9. Update 2026-10-16 — actual consumption lineage (consumption-lineage-v1)
Gap 1 of §7 is closed for in-process Brains (platform RTDB client recorder → `run.py` summary → orchestrator execution record) and for Wind's shadow artifact (`provenance.sources[]` → `consumed[]` on the Publisher envelope). Rows evaluate `RECORDED_CONSUMPTION` where lineage exists, `CURRENT_STATE` elsewhere; recorded lineage is immutable in the ledger. Contract: `ACTUAL_CONSUMPTION_LINEAGE_V1.md`.

## 10. Update 2026-10-17 — Health Plane Publication V1 (`feat/health-plane-publication-v1`)
Audit of the merged implementation against live state (read-only `--dry-run --control-only --emit-health-state`) before the first publication found and fixed three things; the model (§1–§5) is unchanged.
| Finding | Fix | Test |
|---|---|---|
| Unchanged world still rewrote `brains` on every evaluation: cadence and freshness **reasons embedded the age** ("last success 77.88 h ago", "age 0.43 h") so `changed_paths` saw a change | reasons carry no volatile number; ages live only in `lastSuccessAgeHours` / `ageHoursAtConsumption` (both VOLATILE) | `test_snapshot_identity_and_no_rewrite_when_only_time_moves`, cadence case in `test_execution_health` |
| A Brain whose only execution evidence is `/health/brains/{id}` was stamped with the **orchestrator's** `DEPLOYMENT_VERSION` as `codeVersion` (a 2026-10-13 run attributed to the 2026-10-16 image) | `from_health_record` uses the record's own `deployedVersion` or nothing; the orchestrator's version identifies the snapshot only | `test_health_record_is_the_run_for_in_process_brains` |
| `--publish-health` ran inside the full cycle: `--control-only --publish-health` would also have written nine `control/orchestratorV1` sections | **`--health-only`**: implies `--control-only --publish-health`, writes **no** `control/orchestratorV1`, asks no Brain for a `--plan`; exact write set = `control/healthV1/*` in ONE multi-location PATCH | `test_health_only_writes_exactly_the_health_node_and_nothing_else` |

**Snapshot identity** (`summary`, additive): `asOf` (generated), `codeVersion` (the Orchestrator image, `DEPLOYMENT_VERSION`; absent when unknown), `source {controlState, executions, newestExecutionStartedAt}` (the execution ledger the snapshot reflects — in `--health-only` the ledger is the live `control/orchestratorV1/executions` merged in memory with the Cloud Run executions observed now; `control/orchestratorV1` itself is not rewritten), `contentFingerprint` (16-hex over the three content sections with VOLATILE stripped; same world ⇒ same fingerprint). No UUID. **Heartbeat:** an unchanged plane writes nothing, except `summary` alone every `HEARTBEAT_HOURS` (6) so `asOf` says when the world was last evaluated (same convention as `control_state`).

**Atomicity:** `BrainRtdb.update` sends one `PATCH /.json` with up to four `control/healthV1/<section>` keys: RTDB applies a multi-location update atomically, so a reader sees the previous snapshot or the new one, never a half-updated graph. Write ownership: `ownership.path_allowed("brain-platform", "control/...")` is the only route; the writer refuses anything else.

**Measured against live state (2026-10-17T03:28Z, read-only):** 8 Brains, 15 dependency rows (15 `CURRENT_STATE`, 0 `RECORDED_CONSUMPTION` — no live execution carries `consumed[]` yet: the merged lineage code is deployed by this phase and records on the next in-process run), 15 declared edges (11 legacy Brain→Brain from `control_manifest.json`, 3 provider + 1 registry from Wind's `brain.json`), 7 signals all `DECLARED`/no producer (no signal edge: no Brain declares a signal), freshness rows 12 UNKNOWN + 3 FRESH (Wind's providers, `OWNER_RULE` from `/sources/*.latestObservationAt` × `staleThresholdHours`), availability 14 AVAILABLE + 1 UNKNOWN (`registry:lakes`), `lastSuccessfulRun` appears in no row, compact JSON ≈ 35 KB (pretty ≈ 45 KB; `brains` 26.5 KB, `dependencies` 7.6 KB, `signals` 0.8 KB, `summary` 0.5 KB). If it were scheduled hourly the worst case is ≈ 35 KB × 24 ≈ 0.85 MB/day; the heartbeat alone is ≈ 0.5 KB × 4/day. Sample: `orchestrator/sample_health_state_live_dryrun_2026-10-17.json`.

**Truth notes for the consumer (see `HEALTH_PLANE_OPS_CONSUMER_CONTRACT_V1.md`):** `aggregate.status = HEALTHY` with `unknownComponents` non-empty means "the known components are healthy; these are unknown" (6 of 8 Brains today) and must be rendered with the unknowns; an unregistered Brain whose platform-manifest dependency list is empty reports `dependencyHealth: SATISFIED, declared: 0` — a vacuous verdict over Brain→Brain declarations only (its provider inputs are not declared anywhere yet); `/jobs.brain-orchestrator.schedulerState` can lag Cloud Scheduler (the plane uses the live scheduler state read this evaluation).
