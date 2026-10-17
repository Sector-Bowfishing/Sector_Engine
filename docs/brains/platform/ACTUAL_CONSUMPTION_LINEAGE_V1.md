# Actual Consumption Lineage V1 (`consumption-lineage-v1`)

**Owner:** Sector Engine / Brain Platform. **Status:** ACTUAL_CONSUMPTION_LINEAGE_V1_READY_FOR_REVIEW (2026-10-16) — implemented and tested on `feat/actual-consumption-lineage-v1` (base: `main` after PR #21, `4a14e17f`). **Not deployed; health plane not published; nothing live changed.** Not Architecture Certified.

> A Brain **declares** what it is designed to consume (`brain.json`). An execution **records** what it actually read. Ops invents neither. DECLARED ≠ ACTUAL; `lastSuccessfulRun` ≠ evidence freshness; process ≠ dependency ≠ freshness ≠ domain validation ≠ publish health; unknown stays UNKNOWN.

Code: `sector_brain_platform/consumption.py` (recorder, classification, validation, deterministic merge) · hooks in `rtdb.py` (`BrainRtdb(..., recorder=)`, `DryRunStore(..., recorder=)`, `.consumed()`) · `orchestration.execution_record(consumed=)` (canonicalised) · `control_state.merge_execution` (immutability) · Publisher envelope slot `consumed` (`publisher/{validate,artifact,publisher,handoff,model}.py`) · orchestrator `orchestrate.run_in_process` / `json_output` · runners `jobs/{biological-brain,sector-intelligence-brain}/run.py` · Wind reference `brains/wind/runtime/sector_wind/brain/artifact.py` (`consumed_from_states`, `consumed_lake_directory`, `build_artifacts(consumed=)`).
Tests: `jobs/brain_platform/tests/test_consumption.py`, `test_publisher_consumed.py`; `jobs/brain-orchestrator/tests/test_consumption_lineage.py`; `brains/wind/tests/test_publish_artifact.py` (lineage block). Samples: `orchestrator/sample_health_state_consumption_lineage_synthetic_2026-10-16.json`.

## 1. The record (unchanged G1/G2 contract)
One entry per dependency actually consumed, keys exactly `execution_health.CONSUMED_KEYS` (== `consumption.CONSUMED_KEYS`):
`dependencyId` (`brain:|signal:|provider:|registry:<id>`), `dependencyType` (from the prefix), `ref` (the path/reference read), `stateVersion`, `fingerprint`, `artifactId`, `generatedAt`, `evidenceObservedAt`, `publishedAt`, `consumedAt`, `freshnessStatus`, `staleAfter`, `expiresAt`. Everything but `dependencyId` is optional and **absent when the read did not yield it**. `validate_consumed` / `finalize` reject anything else (unknown keys, bad ids, type/prefix mismatch, unparseable times, duplicate dependency) — never repaired silently. Sorted by `dependencyId`; the same set of reads serialises identically regardless of read order (`merge_reads`: newest `generatedAt/evidenceObservedAt/publishedAt/consumedAt`, earliest `staleAfter/expiresAt`, worst `freshnessStatus`, first identity in sorted order).

## 2. Where ACTUAL consumption is captured
| Producer | Capture point | Why it is actual use |
|---|---|---|
| In-process Brains (Biological, Sector Intelligence, any future `run.py`) | `ConsumptionRecorder` on the platform RTDB client: every successful `get()` is classified by the **ownership contract** (who may write that path: `keys.BRAINS` slots, `ownership.path_allowed`, `SOURCE_OWNERS`) | the Brain's only way to read shared state is this client; an entry exists because a GET returned data. Own nodes, absent nodes, platform roots (`jobs/control/scores/…`) and `health/jobs` are never dependencies. Unknown roots are listed in `recorder.unclassified`, never guessed |
| Orchestrator | `run_in_process` reads the Brain's printed JSON summary; a `consumed` list is validated and stored on the execution record; an invalid one becomes `consumptionIssue` on the record; absence stays absence | the Brain reports its own recorder; the orchestrator never copies declarations |
| Wind (reference external producer, SHADOW builder only) | `consumed_from_states`: the `provenance.sources[]` each lake state already records (NBM cycle `issuedAt`, RTMA `analysisTime`, METAR `observedAt`) → one `provider:*` entry per provider some state really used, with Wind's **existing** thresholds as `staleAfter`; `consumed_lake_directory`: content fingerprint of the Engine lake directory the run verified against (no version exists, none invented) | these records are what the run computed from; Wind's declared providers are never consulted. States without sources yield nothing |
| Cloud Run executions observed from the API (Wind hourly job today) | none | no producer-side record exists → `consumed` absent, `CURRENT_STATE` |

Prohibited and tested: `for d in manifest.consumes: consumed.append(d)`.

## 3. Historical truth
`dependency_health.evaluate_dependency(declared, observed, now, consumed=entry)` judges the row **at `consumedAt` against the consumed state only** (`evaluationBasis: RECORDED_CONSUMPTION`, `ageHoursAtConsumption`, `lineageRef`); the current observation is not consulted. Stale-at-consumption stays STALE after the upstream refreshes; fresh-at-consumption stays FRESH after it goes stale. Rows the execution did not record fall back to `CURRENT_STATE`. `control_state.merge_execution`: a `consumed[]` once in the ledger is never dropped by a lineage-free re-observation and never replaced by a different one (`lineageConflict: true` instead). The ledger is bounded (60 executions): older history leaves the control plane; the Publisher's publication history keeps artifact-level lineage.

## 4. Publisher safety
`consumed` is an **optional top-level envelope key** (v1 and v2; `seal_artifact`/`seal_bundle(consumed=)`), validated as stage 5c (`CONSUMED_INVALID` → FAILED_VALIDATION, nothing planned) and carried into the publication record (history and `/brains/{id}/publication`). The semantic fingerprint is `canonical.material()` over **mutations only**; `consumed`, `lineage`, `freshness` never enter it. Proven: same state + different `consumedAt/executionId/stateVersion` → same `outputFingerprint` → **SKIP**; the SKIP record still says what was consumed; a real state change still publishes. Wind: sections and freshness are byte-identical with and without lineage; `artifactId` (content address of the sealed envelope) is per run, as before.

## 5. Declared vs actual (now real)
`dependency_health.reconcile_consumption` on a recorded execution yields real `declaredAndConsumed`, `declaredNotConsumed` (declared but never read — e.g. Biological's legacy-manifest optional dependencies) and `consumedNotDeclared` (read but undeclared — contract drift; never suppressed). The health plane shows `RECORDED_CONSUMPTION` where lineage exists and `CURRENT_STATE` elsewhere, both at once during migration.

## 6. Backward compatibility
`execution_record` old signature unchanged (consumed canonicalised only when given); executions without `consumed` normalise to `consumptionRecorded: false`; `BrainRtdb`/`DryRunStore` default `recorder=None` (no behaviour change); Publisher artifacts without `consumed` unchanged; `/jobs` untouched; no historical record rewritten.

## 7. Known gaps / deferred producers
1. Wind's **running** job does not emit lineage: the Publisher V2 builder is shadow-only (not wired into `wind-hourly`), so Wind lineage exists in tests and the artifact path only. Wiring is the Publisher cutover's job.
2. Cloud Run executions observed from the API carry no lineage (no producer record).
3. Sector Intelligence's `GET /lakes` (Engine HTTP) and Biological's private research bundle are read outside the platform client → not recorded (would need a producer-side `consumed` entry; not invented).
4. Signals remain DECLARED-only; platform registries publish no version (`registry:lakes` carries a content fingerprint from Wind only).
5. In-process runner `main()`s are not exercised end to end in CI (they need tokens/network); the recorder and the orchestrator parsing are.
6. Consumption of a whole `brains` node by a Brain is recorded per Brain present (registry read), which can be many entries; acceptable, bounded by the Brain count.
