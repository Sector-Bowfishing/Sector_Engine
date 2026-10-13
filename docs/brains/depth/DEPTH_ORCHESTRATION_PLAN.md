# Depth Brain internal job integration plan (PREPARED - disabled; not registered, scheduled or deployed)

> **Status 2026-10-14 (Michael: approved to PREPARE, not to schedule).** Implemented and tested but OFF: `jobs/depth-brain/run.py` (`--plan` / `--dry-run` / `--write`; `--write` refuses without `DEPTH_SHADOW_WRITE_APPROVED=1`), the in-process executor entry in `jobs/brain-orchestrator/orchestrate.py` (`build_executors`: present **only** when `DEPTH_ORCHESTRATION_ENABLED=1`, which is set nowhere), the orchestrator image staging of `jobs/depth-brain` (`deploy-job.sh`), and the brain-level `plan()` (`state.brain_plan`). With no executor a registered Depth is only ever SKIPped by the planner (test). A pilot-scope shadow write was performed manually once (`publish --yes-write-shadow --scope pilots`); the live `run.py --plan` now answers SKIP ("inputs unchanged"). Turning orchestration on needs a separate approval: set the env var in the orchestrator job, add the `/jobs` manifest row, and redeploy.

Approval gate: none of the steps below may happen without Michael's explicit approval. Today Depth is a CLI (`python -m depth_brain ...`) that works against a dry-run store; the only live interaction is GET-only reads of Lake Brain states.

## 1. Shape: in-process Brain inside `brain-orchestrator`, not its own Cloud Run job

Biological and Sector Intelligence already run in-process in `jobs/brain-orchestrator` (`orchestrate.py` BRAINS entries `{"kind": "in-process", "dir": ..., "jobId": ...}`; staged into the orchestrator image by its `deploy-job.sh`). Depth is the same kind of Brain: a pure, cheap function of other Brains' published state plus a static manifest. A separate job would add a scheduler, an image and a deploy for ~0.02 s of compute.

| Item | Plan |
|---|---|
| Job id | `depth-brain` (in-process; `/jobs/depth-brain`, `executionMode: ORCHESTRATOR`, `brainPublishInJob: true`, `owner: depth`) |
| Entry | `python -m depth_brain publish --lake-states rtdb:<brain> --rtdb <brain> --yes-write-shadow` (the orchestrator would call `publish()` directly) |
| Staleness model | `FINGERPRINT` (already declared in the registry node); `staleAfterHours` null; the orchestrator's own wake-up (`50 * * * *`) is the clock |
| Verdict | `state.brain_plan(published_fingerprints, manifest, lake_states, published_version)` -> PUBLISH/SKIP + reasons + targeted lake list (implemented and tested; not registered). Per-lake skip already in `publish()` |
| Trigger condition | PUBLISH when any evaluable lake's input fingerprint changed (new Lake Brain observation, reference, datum status, manifest or Depth version) or a pilot lacks a state. Page views never trigger |
| Dependency order | after `lake-brain` in `DEFAULT_ORDER` (registry `dependsOn: ["lake-brain"]`); if Lake Brain is stale/failed, Depth still runs and reports `evidenceStale` / `LEVEL_TOO_OLD` per lake (it never fabricates a level) |
| Targeting | lake-targeted runs (`--lake`) reuse `brain_plan.lakes` |

## 2. Inputs and freshness

| Input | Source | Freshness handling |
|---|---|---|
| `states/lake` for lakes with a live binding | Brain RTDB GET (currently 5 lakes; up to 92 defensible) | observation > 6 h -> `evidenceStale`; > 48 h -> `unavailable (LEVEL_TOO_OLD)`; Lake `freshness.stale` copied |
| Candidate manifest `candidates.json` (881 KB) | packaged with the job; rebuilt offline by `build-manifest` when evidence changes | `manifestVersion` is part of the fingerprint, so a manifest change republishes |
| Datum tables, CWMS/A2W location datums, overrides, licences | packaged data files | same |
| Directory (`GET /lakes`) | public Engine API | key-collision check at start (as Wind does) |

Read efficiency: one `GET /lakeFleet` (small) to find lakes whose `readiness.lake` is set, then GET only those states (not 92 blind GETs). Measured 2026-10-14: 92 sequential `states/lake` GETs = 15 s; with that prefilter and 8 parallel readers a fleet run is < 3 s.

## 3. Expected runtime, memory, cost (measured on this machine, GET-only dry run)

| Metric | Value |
|---|---|
| Compute for 92 lakes (publish incl. registry, readiness, activity) | **0.02 s** |
| Peak RSS | **43 MB** (process incl. manifest) |
| Lake-state reads | ~0.16 s each sequential; < 3 s with prefilter + parallel |
| Bytes written for 92 lakes | ~268 KB (about 2.9 KB per lake) + registry/validation/health (~10 KB) |
| Writes per run | one atomic update per evaluated lake + fleet rows + registry/validation + health (+ activity on change); <= 50-lake chunks per contract |
| Static contour cost | zero at runtime: shares are baked into the manifest; raw contour geometry stays outside Git and RTDB; rebuild is offline (CWMS-location lookup 94 GETs, A2W/USGS from cached records) |
| Orchestrator marginal cost | no new job/scheduler/image; adds < 1 s to an existing hourly wake-up; scale-to-zero inherited |
| Storage | RTDB ~0.3 MB steady state; the manifest and data files ~1 MB in the image |

## 4. Failure handling and scale-to-zero

* One lake failing never stops the run (per-lake `try`, `DEGRADED` readiness, error recorded); `publish()` never raises.
* Platform failure path (`failure_writes`, contract section 10), retry/backoff `5/15/45 min`, single-flight lock and invoker-only starts come from the orchestrator.
* No Lake state -> `kind: unavailable, LAKE_STATE_MISSING`; stale -> flagged; implausible/conflicting datum -> refusal with reason codes (never a number).
* No long-lived process, no polling loop; nothing runs between orchestrator wake-ups.

## 5. Exact integration steps (each a separate approval)

1. Add `depth` to the control-plane brain set as a **shadow** Brain that cannot affect health/conformance roll-ups (`DEPTH_OPS_VISIBILITY_GAP.md`).
2. Add the `depth-brain` entry to `orchestrate.py` BRAINS and stage `jobs/depth-brain` + `brain_platform` in the orchestrator image build.
3. Add the `/jobs` manifest row (`jobs.py`) with class `INTERNAL`, `executionMode ORCHESTRATOR`.
4. Wire `brain_plan` into the orchestrator's `decide()` input.
5. First live write: `--yes-write-shadow` for the 5 pilots only; verify in the live RTDB; watch two cycles; then widen as Lake Brain publishes more states.
6. Rollback: `null` patch of the depth-owned paths (`/brains/depth`, `/lakes/*/states/depth`, `lakeFleet/*/{readiness,slots,modelVersions}/depth`, `snapshots/*/latest/depth`); remove the orchestrator entry. No shared-field or schema change to undo.
