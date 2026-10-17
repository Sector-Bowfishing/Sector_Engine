# Orchestrator Control Plane — `orchestrator-control-v1`

**Owner:** Sector Engine / Brain Platform (platform writer `brain-platform`). **Status:** implemented and tested on `feat/brain-platform-model-v1`; **not deployed** (see §11). Sector Ops renders this; it computes none of it and builds no execution logic.

> The Orchestrator is the **traffic cop**. It decides *who runs, when, why, and who needs to know what changed.* It does no wind physics, fish biology, clarity modelling, depth or vegetation science. It understands **contracts, dependencies, execution metadata, material change, schedules and state**.

Code: `sector_brain_platform/{orchestration,control_state}.py`, manifest `sector_brain_platform/control_manifest.json`, glue `jobs/brain-orchestrator/{orchestrate,control_plane}.py`, audit `check_preproduction_schedules.py`. Tests: `jobs/brain_platform/tests/test_orchestration.py` (44), `jobs/brain-orchestrator/tests/{test_control_plane,test_preproduction_schedules}.py`.

## 1. Separation of ownership
| Orchestrator owns | Brains own | Sector Intelligence owns |
|---|---|---|
| schedule *intent*, routing, dependency graph, active/parked state, trigger evaluation, execution requests, material-change propagation, retry policy, execution + decision history, control state, pre-production execution policy | domain logic, provider interpretation, science, rules, state generation, confidence, refusal, domain fingerprints | synthesis into bowfisher meaning |
A Brain declares **how** to execute (target, inputs, outputs, fingerprint, dependencies, freshness need). The Orchestrator declares **when** — in one place: the execution manifest.

## 2. Engine mode
`engineMode ∈ PRE_PRODUCTION | PRODUCTION` (manifest, **protected**: changed only by a reviewed commit + deploy, never by a runtime request). **PRE_PRODUCTION (the only implemented mode):** recurring compute OFF by default; customer publication disabled (`publish_allowed` is false; the manifest validator rejects `customerPublication: true`); only approved validation exceptions run on a schedule; manual/on-demand allowed; dependency-driven execution allowed when policy permits; parked Brains never wake autonomously; no fleet-wide work without cause. **Any other mode fails closed** (`BLOCKED_POLICY / MODE_UNDEFINED`) until its policy is written.

## 3. Activity state (configuration, not code)
`ACTIVE` — eligible for approved scheduled, manual or dependency-driven work. `PARKED` — never executes automatically (SCHEDULE/INPUT/DEPENDENCY/RECOVERY → `SKIP_PARKED`); manual/admin allowed; **existing state stays readable; no data deleted**. `MAINTENANCE` — limited approved operations only (e.g. a validation capture); no automatic downstream expansion. Source: `control_manifest.json`; overridden by accepted PAUSE/RESUME requests (`/control/orchestratorV1/overrides`).
Current board: **ACTIVE** wind, biological-state, water-clarity · **MAINTENANCE** lake-brain (prospective ledger) · **PARKED** water-temp, depth, vegetation, sector-intelligence.

## 4. Execution manifest (`brain-execution-manifest-v1`)
Per Brain: `displayName, group (presentation only), lifecycle, activityState, executionTarget{kind, job, startedByOrchestrator, scoped}, allowedTriggers[], dependencies[{id, requirement, maxAgeHours, onStale, usesFields?, provisional}], schedule{class, owner, scheduler, cron, exception{gate, notReconstructable, maxMonthlyUsd, stop, approvedAt}}, freshness{staleAfterHours|stalenessModel}, fingerprint{outputSource, materialFields}, costClass, resources, timeoutSeconds, retry, scopes[], allowFleetRunNow, customerPublication`. Plus `jobs{}`: every known job with `classification ∈ ORCHESTRATOR_OWNED | LEGACY | VALIDATION_EXCEPTION | MANUAL | INPUT_DRIVEN | PAUSED`, scheduler name, purpose, validation-only and customer-impact flags, cost estimate. Irrelevant fields are simply absent. `provisional: true` freshness tolerances are pre-production defaults the Brain owner must confirm.
**Policy is code:** `schedule_policy()` — a recurring schedule in PRE_PRODUCTION requires `gate`, `notReconstructable`, `maxMonthlyUsd`, `stop`, `approvedAt`; otherwise `BLOCKED_POLICY / RECURRING_OFF_BY_DEFAULT`.

## 5. Triggers and decisions
Triggers: `SCHEDULE, MANUAL, INPUT_CHANGED, DEPENDENCY_CHANGED, VALIDATION, RECOVERY, ADMIN`. Every execution records its trigger and reason.
Decision values: `RUN, SKIP_UNCHANGED, SKIP_PARKED, SKIP_NOT_DUE, SKIP_LEGACY_OWNED, SKIP_UNKNOWN_CHANGE, BLOCKED_DEPENDENCY, BLOCKED_POLICY, WAITING, MANUAL_APPROVAL`.
Evaluation order (`decide_brain`): mode → single-flight → trigger allowed → (SCHEDULE) legacy-owned / recurring policy → active/parked/maintenance → material-change gating → due check → dependencies → **RUN**. A decision record: `decisionId, at, brainId, trigger, decision, reason, reasonCode, activityState, scheduleState, dependencyState[], inputFingerprint, scope?, requestedBy?, runDependencies?, publish:false`. *Why did this run / not run* is answerable for every Brain and trigger from `latestDecisions` and the bounded `decisions` log.

## 6. Dependencies: read vs run
Edges are `HARD` (REQUIRED) or `SOFT` (OPTIONAL), machine-readable at `/control/orchestratorV1/edges`; independent Brains run in parallel (`plan_waves`); cycles, unknown ids and self-edges **fail closed**; a Brain with no dependency metadata is a visible warning. **A consumer needing a Brain's existing state does not wake it**: fresh → `READ_EXISTING`; stale → the consumer's `onStale` policy (`DEPENDENCY_STALE`, `MANUAL_APPROVAL`, `RUN_DEPENDENCY`); `RUN_DEPENDENCY` still wakes only an **ACTIVE** dependency (a PARKED one is reported blocked). Unknown freshness is `UNKNOWN`, never "fresh". Optional stale dependencies are recorded, not blocking.

## 7. Material change
`classify_change(prev, new) → CHANGED | UNCHANGED | UNKNOWN`. Output fingerprint source, in order: the Brain's own (`registry:fingerprint`, e.g. Sector Intelligence — `BRAIN_OWNED`), else a hash of manifest-declared registry fields (`REGISTRY_PROJECTION`: contract-level, no domain knowledge; run time excluded), else `UNKNOWN`. A Brain running does **not** wake its consumers: only a material change does, and only for consumers that are ACTIVE, accept `DEPENDENCY_CHANGED`, and whose own input fingerprint differs from the last processed one; an edge may list `usesFields` so a change outside them is `FIELDS_NOT_USED`. No baseline yet ⇒ `UNKNOWN` (the first observation never cascades). `NO_MATERIAL_CHANGE` is recorded as a decision. Brains with their own plan (Biological `--plan` PUBLISH) raise `INPUT_CHANGED` for themselves; that signal enters the consumer's input fingerprint.

## 8. Published state — `/control/orchestratorV1/*` (platform-writer only)
Namespace: beside the existing `/control/overview` and `/control/orchestrator` (no parallel backend; Ops already reads `/control/*` under its read-only rules). Written as whole sections, **only sections whose content changed** (timestamps `lastEvaluatedAt` ignored), so an idle system does not churn. Unknown stays absent. No secrets, no research data. ≈ 60 KB at the cap.

| Section | Content | Retention |
|---|---|---|
| `summary` | `version, engineMode, status (IDLE/ACTIVE/DEGRADED/BLOCKED), policy, lastCycle{trigger, durationMs, decisionCounts, lastEvaluatedAt}, activeBrains, parkedBrains, maintenanceBrains, running, queued, blocked, nextDue, costToday{day, executions, usd?, basis, unknownExecutions, lowerBound}, recentDecision, graphValid, customerPublication` | current |
| `brains/{id}` | `displayName, group, health, lifecycle, legacyStatus, activityState, scoreRef{path, canonicalScore?, scoreStatus?}, productReadiness?, executionMode (VALIDATION_EXCEPTION/INPUT_DRIVEN/MANUAL/PAUSED/SCHEDULED), scheduleClass, exception (gate), lastRun, lastResult, nextDue?, freshness{staleAfterHours, ageHours?, stale?}, outputChanged (CHANGED/UNCHANGED/UNKNOWN), outputFingerprint?, outputFingerprintBasis, costToday, currentBlocker?, decisions{trigger → verdict}, customerPublication, costClass, retry?` | current |
| `edges/{from__to}` | `from, to, kind HARD/SOFT, maxAgeHours, onStale, usesFields?, provisional` | current |
| `jobs/{jobId}`, `schedules/{scheduler}` | one authoritative schedule model: `classification, schedule, enabled, validationOnly, customerImpact, lastStartedAt, lastCompletedAt, lastResult, durationMs, nextDue, costEstimate, owner` | current |
| `executions/{id}` | `executionId, brainId, jobId, trigger, reason, startedAt, endedAt, durationSeconds, status, scope?, inputFingerprint?, outputChanged, cost{usd?, basis}, downstream[{brainId, decision}], failureClass?` | **60 newest** |
| `decisions/{id}` | verdict **changes** (and every RUN) | **120 newest** |
| `latestDecisions/{brain__trigger}` | current verdict + `since` (stable until it changes) | current |
| `cost` | `today`, `enabledMonthlyEstimateUsd`, `basis: ESTIMATED` | current |
| `blockers`, `graph`, `health`, `overrides`, `requests` | blocked decisions; `{order, errors, warnings}`; graph errors + Brain health; accepted PAUSE/RESUME; last 30 control-request outcomes | current / 30 |
Freshness of the state itself: `summary.lastCycle.lastEvaluatedAt` (Ops treats an old value as an old control plane). Write authority: the orchestrator job only; Ops never writes these nodes. Vocabulary (closed, in `orchestration.py` and mirrored in `conformance/orchestrator_control_v1.json`): engine modes, activity states, triggers, decisions, schedule classes, cost classes, groups, edge kinds, failure classes, request actions/decisions, cost basis `MEASURED|ESTIMATED|UNKNOWN`. Execution `trigger` may additionally be `UNKNOWN` for executions the orchestrator did not start and could not attribute. Samples: `sample_control_state_live_2026-10-14.json` (computed from the **real** published state, read-only), `sample_control_request.json`.

## 9. Control requests (Ops → Engine)
Closed action set: `RUN_NOW, PAUSE, RESUME, SET_MANUAL`. Protected (fail closed, need `confirm{by == requestedBy, phrase = "CONFIRM <ACTION> <brainId|ENGINE>"}`): `SET_ENGINE_MODE, ACTIVATE_PRODUCTION, PUBLISH_CUSTOMER, CHANGE_PROTECTED_SCHEDULE, PROMOTE_LIFECYCLE, DISABLE_VALIDATION_CAPTURE` — pausing a Brain with a validation exception counts as the last one. Even when confirmed, mode change / production / customer publication / lifecycle promotion are **rejected at runtime** (they happen only through a reviewed manifest change and deploy).
`RUN_NOW` needs an explicit `scope` from the Brain's `scopes[]` (e.g. wind `current-live-lakes`; biological `guntersville`; clarity `guntersville`, `lake-hartwell`); `fleet`/`all` is refused unless `allowFleetRunNow`; it passes through `decide_brain(MANUAL)` so single-flight, dependency and trigger policy apply. Where the executor cannot pass a scope (Clarity needs `roles/run.developer` for an args override) the request is accepted with the exact `manualCommand` — it is never widened to the fleet. Outcome record: `requestId, requestedBy, action, brainId, scope, at, decision ACCEPTED|REJECTED|NEEDS_CONFIRMATION, reasons[], effect?, manualCommand?, decisionId?`.
**Channel (not enabled):** the orchestrator reads `/controlRequests/pending/{id}` each cycle. Ops cannot write there under today's rules (client writes denied everywhere except `opsPreferences`), so Ops needs either a narrowly validated rules change in the Ops repo or a small authenticated callable; until then requests can be filed by an operator. With the hourly schedule paused, requests are processed on the next manual cycle (`DECISION O-3`).

## 10. Concurrency, retry, cost, health
- **Single-flight** per `brain|scope` (lock with TTL and sequence; `acquire_lock`), live Cloud Run executions also count; a **stale execution cannot commit over a newer one** (`may_commit`).
- **Retry** by class, bounded, visible: `TRANSIENT_PROVIDER` and `TRANSIENT_RUNTIME` retry with 5/15/45 min backoff, max 3; `INVALID_INPUT`, `PERMANENT_CONFIG` never; `DEPENDENCY_BLOCKED` is re-evaluated when the dependency changes, not on a timer. `failureClass` is recorded on the execution.
- **Cost:** per execution `ESTIMATED` from job resources × measured duration at list prices, `UNKNOWN` (never zero) otherwise; `cost.today` is a lower bound when any execution is unknown. No billing API call anywhere on a page load; Ops reads the stored number.
- **Health** is shown beside, not derived from, exit codes: Brain `health` (from `/health/brains`), `freshness` (age vs the Brain's own expectation), dependency status, last result, failure class — separate from lifecycle/maturity.

## 11. Scheduling model and migration
**One source of truth** for what is scheduled / manual / paused / validation-only: `control_manifest.json › jobs` (+ `cost-freeze/schedule-policy.json` for what may be *enabled*). `check_preproduction_schedules.py` compares it with live Cloud Scheduler and fails on drift or an unmanaged (hidden) scheduler. Live (2026-10-14, verified): no drift, no unmanaged scheduler.

| Scheduler | Class | State |
|---|---|---|
| `wind-hourly` `5 * * * *` UTC | VALIDATION_EXCEPTION (legacy-owned) | ENABLED — preserved; no backfill; no gap created |
| `lake-brain-ledger-daily` `0 12 * * *` UTC | VALIDATION_EXCEPTION (legacy-owned) | ENABLED (confirmation C-2) |
| `brain-orchestrator` `50 * * * *` | PAUSED (the control plane runs when invoked manually) | PAUSED |
| `water-temp-tva-archive`, `lake-surface-dispatch` | PAUSED | PAUSED |
| `lake-surface-daily`, `hydrology-hourly`, `clarity-current-hourly`, `clarity-candidate-shadow` | PAUSED | PAUSED |
Indirect triggers: `lake-surface-dispatch → lake-surface-daily` (dispatcher, paused); the orchestrator → `lake-brain`, `water-temp-brain` (now gated by the decision model: not started in PRE_PRODUCTION); Biological/Intelligence in-process runs (only on an INPUT_CHANGED/MANUAL/DEPENDENCY decision). No duplicate scheduling paths remain.

Stages: **1 (done)** inventory + control schema + read-only graph. **2 (done, undeployed)** the decision model gates execution while legacy schedulers stay the execution source for Wind and the Lake ledger (`SKIP_LEGACY_OWNED`, observed not started). **3 (not started)** move eligible schedule ownership into the orchestrator — only for a Brain that gets an approved recurring exception and is not a validation capture; **Wind must never gap**, so it moves last, with an overlap period and a proof of no missing hour. **4 (not started)** retire redundant legacy scheduling after Stage 3 is proven. No flag-day rewrite.

## 12. Deployment and rollback
Deploy-ready, **not deployed** (needs Michael: the orchestrator is a shared production-adjacent job, and its scheduler is PAUSED so a deploy changes no recurring behaviour). `deploy-job.sh` runs the lineage preflight, the stale-artifact guard and leaves the scheduler PAUSED. After deploy, exercise it manually: `gcloud run jobs execute brain-orchestrator --region us-central1 --args=--dry-run --wait` (reads live, writes nothing), then a real cycle; confirm `/control/orchestratorV1/summary` and that nothing was started. **Rollback:** run `deploy-job.sh` from the previous commit `5fd727effa4a` (the preflight refuses a non-descendant, so this needs the recorded override `ALLOW_BACKWARD_LINEAGE=1`) and delete `/control/orchestratorV1` (Ops treats an absent node as "not published"); `--legacy-execution` restores the old start-what-is-stale behaviour without a redeploy.

## 13. Final product test
| Question | Where answered |
|---|---|
| What needs to run? Why? When? | `summary.queued`, `latestDecisions`, `brains/*.decisions`, `nextDue` |
| What input changed? Who depends on it? | `brains/*.outputChanged`, `edges` |
| Did the output materially change? Who actually needs to run next? What can be skipped? | `outputChanged`, `decisions` (`SKIP_UNCHANGED`/`NO_MATERIAL_CHANGE`) |
| What is parked? Blocked? | `summary.parkedBrains`, `summary.blocked`, `blockers` |
| What is costing money? | `cost`, `brains/*.costToday`, `jobs/*.costEstimate` |

## 14. For Sector Ops (no reverse-engineering of Engine internals)
- Read only `/control/orchestratorV1/*`; render unknown strings verbatim and missing fields as "not published". Never compute a score, freshness class, decision or cost in the browser.
- Status vocabulary (`summary.status`): `IDLE` (nothing to run), `ACTIVE` (RUN decisions queued), `DEGRADED` (a Brain reports FAILED/DEGRADED), `BLOCKED` (graph invalid). Brain `executionMode`: `VALIDATION_EXCEPTION | INPUT_DRIVEN | MANUAL | PAUSED | SCHEDULED`. Edge `kind`: `HARD | SOFT`. Decision values and triggers as in §5.
- Layout hint only: `brains/*.group` ∈ FOUNDATION, CURRENT_CONDITIONS, ENVIRONMENT, BIOLOGICAL, SYNTHESIS. It is presentation; it is **not** execution order (the graph order is `graph.order`).
- Top node = `summary`; Brain nodes = `brains`; expandable job nodes = `jobs` + `schedules`; history = `executions` and `decisions`; blockers panel = `blockers`.
- Fixture for UI work: `conformance/orchestrator_control_v1.json` (vocabularies, section names, retention) and the two sample payloads in this folder.

## 15. Health plane (added 2026-10-16, Orchestrator G1/G2 — `brain-health-v1`)
Beside `control/orchestratorV1`, the orchestrator can publish `control/healthV1/*` (opt-in: `orchestrate.py --publish-health`; review: `--emit-health-state FILE`): five health concepts per Brain (process, dependencies, freshness, domainValidation, publish) plus the declared dependency graph and the Signal Registry definitions. §10's "health is shown beside, not derived from" is now a published contract: `freshness` there is still the age of `lastSuccessfulRun` (process), while `control/healthV1` carries evidence freshness. Execution records gain additive lineage (`codeVersion`, `jobId`, `consumed[]`). Contract and migration table: `../ORCHESTRATOR_HEALTH_V1.md`. Sample (synthetic): `sample_health_state_synthetic_2026-10-16.json`.
