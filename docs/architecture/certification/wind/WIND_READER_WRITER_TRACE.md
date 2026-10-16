# Wind Brain: reader / writer trace (step 5, exit E) — public-safe architecture view

Code is truth. Traced at `fab115e9`; the deployed `wind-hourly` code (label `e6a5026f5d0f`) is byte-identical to `jobs/wind-hourly` here. A newer, **different** Wind publisher lives on `feat/wind-brain-adoption` (fleet rewrite only on change, tonight/exposure/field modules, score entry script). It is **not deployed and not in this lineage**. Credential, IAM and rule detail is deliberately omitted (private handoff).

## 1. Writers
| Writer | Code | Writes | Wind-owned? |
|---|---|---|---|
| `wind-hourly` job, in-process publisher | `jobs/wind-hourly/main.py`, `sector_wind/brain/publish.py` | all Wind paths (matrix) | **yes: the only scheduled specialist writer** |
| WindBrain CLI (`python -m sector_wind.brain publish`) | `sector_wind/brain/__main__.py` | same publisher; needs exactly one of `--dry-run OUT.json` (in-memory, no remote write) or `--rtdb URL` (live) | yes (operator tool; not scheduled) |
| Brain Score Publisher (orchestrator job) | `jobs/brain-scores/score_brains.py` | `/scores/wind`, engine score, control projections, `score.changed` activity, and deletes legacy `/brains/{b}/score` mirrors | no (platform; projects Wind) |
| Orchestrator | `jobs/brain-orchestrator/orchestrate.py` | `/jobs/wind-hourly`, `/control/orchestratorV1` Wind projections | no (platform; never starts Wind) |
| GCS archive step | `sector_wind/{live,ingest,store}.py` | `runs/`, `nbm/`, `rtma/`, `metar/`, `grids/`, `latest/`, `ledger/` in the private bucket | yes (private storage; not RTDB) |
| Other Brains | Sector Intelligence, Fish | **read** Wind only | no |

No other location in the repo writes a Wind path. Research scripts contain no RTDB writer.

### Writes per `wind-hourly` run (exact)
All RTDB writes are root-level multi-path **PATCH** (`null` = delete); no PUT/DELETE verb. Steady state = **7 requests**: 4 per-lake (state, profile, lake validation, snapshot copy, `brainVersions.wind`) + 1 fleet (~1,260 paths: all 621 `readiness/wind`, plus slot/modelVersions for 4 lakes) + 1 registry/validation/sources/source-health + 1 health. Plus 1 profile PATCH when a national fetch-table sha changed; plus activity (1 PATCH; and a GET of the entire `/activity` node to prune) only when an event fires. Order: lakes → profiles → fleet → registry → health → activity → private `last_publish.json` (GCS) last.

**Atomicity:** each PATCH is atomic, the run is not. If the fleet or registry PATCH fails after the lake PATCHes succeed, state and registry diverge (partial publication). Failures are collected, never raised; the job exit code is driven only by the archive step.

### Known defects, confirmed in code
1. **Null-on-miss:** `lakes/{k}/validation/wind` is written as `val_lakes.get(lid)`; a missing evidence entry deletes the node. All 4 lakes have entries today.
2. **Partial publication** across the 7 requests (above).
3. **Second source of truth:** `last_publish.json` in the private bucket gates national-profile rewrites, activity events, and `lastSuccessfulRun` carry-forward. It does not gate state/fleet/registry/health, which are unconditional every run.
4. **Unconditional fleet rewrite** (~1,260 paths every run).
5. **Evidence baked into the image:** `validation_evidence.json` (and therefore `/brains/wind.scores` = 3.1 and `/validation/wind`) changes only when the job image is rebuilt.
6. **Ownership enforced client-side only** (writer library). See private handoff for the server-side situation.
7. **Doc drift** in `jobs/wind-hourly/BRAIN.md`: activity "bounded to 500" (code keeps 80 newest, 30 days; the 500 constant is unused); it lists `snapshotVersion`/`lastUpdatedAt` writes the ownership table forbids.
8. **Label drift:** the deploy script hard-codes `main@<sha>` in `deploymentVersion` regardless of branch (a material fingerprint field).
9. `/jobs/wind-hourly` declarations list a **subset** of Wind outputs (omit `/validation/wind`, `/sources/*`, `/health/sources/*`, per-lake profile/validation, fleet readiness/modelVersions, `/activity`).

### Gating
`SECTOR_WIND_BRAIN_RTDB_URL` unset → no Brain publish. `SECTOR_WIND_GCS_APPROVED=yes` required for any `gs://` store; shared production buckets are refused by name. An environment variable *does* enable live writing today (target state forbids this: BRAIN_READ_WRITE_SECURITY_V1 §5, Code).

## 2. Scheduler / deploy
Cloud Scheduler HTTP job → Cloud Run Job `wind-hourly`, `5 * * * *` UTC, **ENABLED**, retry policy 5 s → 1 h; job retries 1; 900 s timeout. Deployed by `jobs/wind-hourly/deploy-job.sh` (approval-gated; vendors the shared platform package into the image). A dedicated per-job service-account class is used (not the shared platform writer). Companion `wind-candidate-read` is a read-only service over the private archive.

## 3. Readers
| Reader | What it reads | Notes |
|---|---|---|
| **Sector Ops** | `/snapshots/{k}/latest` (`.wind`), `/brains` (registry **including `scores`: 3.1/5.4**), `/lakeFleet`, `/validation`, `/health`, `/sources`, `/jobs`, `/scores`, `/engine/score`, `/control/*`, `/activity` (last 50) | Ops never reads `/lakes/{k}/states|profiles|validation/wind`. Whole-node listeners (cost, not security). Also shows production wind live from Engine `/conditions` beside Wind state |
| **Sector Intelligence** (PARKED, pilot) | `snapshots/{k}/latest` and its `wind` field, `brains/wind`, `health/brains/wind`, `validation/wind/status`, `lakeFleet/{k}` | never reads `states/wind`. Wind dependency optional, 6 h |
| **Orchestrator** | `/brains/wind` fields `version, deploymentVersion, readinessCounts, staleLakeCount, supportedLakeCount, profiledLakeCount` (fingerprint), `lastSuccessfulRun` (dependency freshness) | no edge declares `usesFields`; the fingerprint does not cover lake states |
| **Score publisher** | `brains`, `health`, `validation`, `lakeFleet`, `sources`, `jobs`; Wind score from `frozen-scores.json` (image) | |
| **Fish (`biological-state`)** | declared optional dependency edge only | |
| **Research tools** | `research/run_cycle.py`-style scripts GET `/scores/wind` | read-only |

## 4. Customer boundary (regression gate)
Customer `/conditions` wind: `ConditionsSnapshot` → `WeatherService` → Open-Meteo `/v1/forecast` (`wind_speed_10m`, `wind_gusts_10m`, `wind_direction_10m`) → `WindFactor`. The Engine's Brain RTDB store is used only by the Lake and Water Temperature jobs. iOS, Android and the customer website use their own Open-Meteo calls or Engine `/conditions`, and only the app databases; none references `sector-brain`, `states/wind`, `snapshots` or `lakeFleet`. The Wind registry itself records `brainOutput:false`. **No customer path consumes Wind Brain state, and this session changes nothing there.**

## 5. Security posture (public pass/fail)
| Exit-F item | Today |
|---|---|
| Specialist identity has no production DB write | **FAIL** (it currently holds write capability) |
| Ops has no domain write | PASS by rules (all client writes denied); Ops browser code not audited in this session |
| Cross-domain write denied | **PARTIAL**: denied by the writer library only, not server-side |
| Publisher authorized write | **N/A** (no Publisher) |
Details are private.
