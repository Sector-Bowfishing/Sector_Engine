# `/jobs/{jobId}` — the Engine-owned Jobs & Schedules contract (jobs-v1)

**Owner:** Sector Engine, platform writer `brain-platform`. **Published by:** `jobs/brain-orchestrator`
(hourly) — the **one canonical sync path**; `orchestrate.py --sync-jobs-only` republishes on demand.
**Implementation:** `jobs/brain_platform/sector_brain_platform/jobs.py` (pure) + `gcp.py` (reads).
**Introduced:** 2026-10-13 (cost-efficient scheduling work). Sector Ops reads it verbatim
(`Sector-Ops/src/types/jobs.ts`, `src/data/jobs.ts` prefer `/jobs` over the `/health/jobs` fallback).

## Truth sources (never guessed by Ops, never owned by a Brain)

| Fact | Source | Notes |
|---|---|---|
| `enabled`, `cron`, `timezone`, `schedule`, `nextScheduledAt`, `schedulerState`, `lastScheduledAttemptAt` | **Cloud Scheduler** (authoritative) | a PAUSED scheduler → `enabled:false`, `executionMode:"DISABLED"`, `runtimeStatus:"PAUSED"`, no `nextScheduledAt` |
| `running`, `lastStartedAt`, `lastCompletedAt`, `lastSuccessfulAt`, `lastFailedAt`, `durationMs`, `failureCount`, `lastError`, `lastErrorAt` | **Cloud Run Jobs executions** (last 20) | `lastError` = the Completed=False condition message of the most recent failed execution |
| `resources{cpu, memoryGi, tasks, parallelism, taskTimeoutS}`, `sourceVersion` | Cloud Run Job spec / `commit` label | `sourceVersion` only when the job carries a `commit` label |
| `revision`, `runtimeStatus` (services) | Cloud Run Service | `sector-engine`, `wind-candidate-read` |
| in-process brains (`biological-brain`, `sector-intelligence-brain`, `water-clarity-brain` when not deployed) | `/health/brains/{owner}` | the publish is the run |
| `owner`, `purpose`, `classification`, `environment`, `kind`, `trigger`, `inputs`, `outputs`, `brainDependencies`, `statePaths`, `brainPublishInJob`, `retryPolicy`, `freshnessPolicy`, `scienceStatus`, `sourceLineage`, `triggeredBy`, `triggers`, `consumers` | the manifest in `jobs.py` (`MANIFEST`) | design facts, reviewed in code |
| `cost{expectedRunsPerDay, expectedRunsBasis, recentAverageRuntimeMs, recentRuns, resourceProfile, estimatedVcpuHoursPerDay, estimatedGibHoursPerDay, note}` | derived | runs/day from the cron (`cron`), an estimate for orchestrator-conditional jobs (`estimate …`), `0` when paused; **never a dollar figure** |

Record envelope: `contractVersion:"jobs-v1"`, `syncedAt`, `syncedBy`, `jobId`, `displayName`, `deploymentStatus`
(`DEPLOYED` / `NOT_DEPLOYED`), optional `warnings[]` (e.g. "legacy Cloud Scheduler job still ENABLED",
"unmanifested workload", "no Cloud Scheduler job of this name"). Absent = not known; nothing is invented.

## Vocabularies
- `classification`: `PRODUCTION` (customer path) · `INTERNAL` (feeds Brains/Ops, no customer path) · `RESEARCH`
  (research lineage only) · `SHADOW` (candidate shadow run).
- `executionMode`: `SCHEDULED` · `MANUAL` · `EVENT_DRIVEN` (orchestrator / dispatcher / request) · `DISABLED`.
- `runtimeStatus`: `HEALTHY` · `RUNNING` · `WARNING` · `FAILED` · `STALE` · `DISABLED` · `PAUSED` · `UNKNOWN`.
- `trigger`: `scheduler` · `orchestrator` · `dispatcher` · `manual` · `request`.

## Classification matrix (2026-10-13)

| jobId | kind | classification | trigger | schedule / rule |
|---|---|---|---|---|
| `sector-engine` | Cloud Run service | **PRODUCTION** | request | serving revision (tagged main) |
| `conditions`, `appstorenotifications`, `adminlistusers`, `tournamentpage`, `playnotifications` | Cloud Function | **PRODUCTION** | request | scale-to-zero |
| `wind-hourly` | Cloud Run job | **INTERNAL** (science `RESEARCH_CANDIDATE`) | scheduler | `5 * * * *` UTC; NBM early exit |
| `water-temp-tva-archive` | Cloud Run job | **INTERNAL** | scheduler | `20 * * * *` UTC (source retention ~24 h) |
| `wind-candidate-read` | Cloud Run service | INTERNAL | request | master-only |
| `lake-surface-dispatch` | Cloud Run job | **INTERNAL** | scheduler | `0 3 * * *` America/Chicago |
| `lake-surface-daily` | Cloud Run job | **INTERNAL** | dispatcher | only with work; legacy scheduler PAUSED |
| `hydrology-hourly` | Cloud Run job | **RESEARCH** | scheduler | **PAUSED** 2026-10-13 |
| `clarity-current-hourly` | Cloud Run job | **RESEARCH** | scheduler | **PAUSED** 2026-10-13 |
| `clarity-candidate-shadow` | Cloud Run job | **SHADOW** | scheduler | PAUSED (stays) |
| `lake-brain` | Cloud Run job | INTERNAL | orchestrator | TIME, staleAfterHours 3, pilot 5 lakes |
| `water-temp-brain` | Cloud Run job | INTERNAL | orchestrator | TIME, staleAfterHours 6, fleet |
| `water-clarity-brain` | Cloud Run job (not deployed) | INTERNAL | **manual** | `WATER_CLARITY_BRAIN_SCHEDULING.md` |
| `biological-brain` | in-process (orchestrator) | INTERNAL | orchestrator | VERSION (own plan()) |
| `sector-intelligence-brain` | in-process (orchestrator) | INTERNAL | orchestrator | FINGERPRINT (own plan()), pilot only |
| `brain-scores` | in-process (orchestrator) | INTERNAL | orchestrator | after a state change (`--if-changed`) |
| `brain-orchestrator` | Cloud Run job | INTERNAL | scheduler | `50 * * * *` UTC |

## What is never published
Tokens, service-account identities, env var values, image references/digests, private bucket paths (`gs://…`),
secrets, private research. Outputs are named logically (`archive:wind-candidate (private)`), tests assert it
(`tests/test_jobs.py::test_nothing_secret_is_published`).

## Ownership and rules
- `/jobs` is a **platform-only** root (`ownership.py PLATFORM_ONLY`, Swift `BrainOwnership.platformOnly`,
  fixture `conformance/ownership.json`). A Brain may still write **its own** `/health/jobs/{jobId}` (Wind does);
  the Clarity Brain no longer writes records for jobs it does not own.
- Brain RTDB rules (`Sector-Ops/database.rules.json`, deployed): authenticated `access/opsUsers/{uid}` read-only on
  `/jobs`, `/control`, `/scores`, `/engine`; root `.read/.write: false`. Never public.
- Ops shows `syncedAt`; a record older than ~2 h means the orchestrator wake-up is not running (its own record is
  `jobs/brain-orchestrator`).
