# Sector Engine — final architecture merge, Firebase remediation and controlled release — Session Record

```text
Standards: Rehtac Cortex 2.2.0 @ ae59e2d, pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · main @ 1bff61c9 · Date: 2026-10-22
```

The owner authorized:
- reviews and compatible fixes;
- merging the ready Engine PRs in dependency order;
- safe deployment of approved Engine infrastructure;
- controlled publication of `/control/engineeringStatusV1`;
- read-only production checks.

The owner did not authorize knowledge promotion, model activation, score or rubric changes, Publisher LIVE, Depth/Vegetation activation, unrelated schedules, destructive cleanup, or unrelated IAM or rules changes.

## Merges (merge commits; all CI green)

| PR | Merge commit | Notes |
|---|---|---|
| #40 eight-Brain structural standardization | `aa12ba2e` | 9/9 checks on head `a1e709ce`. `main` CI green (Python, foundation, macOS + Linux Swift) |
| #41 Cortex 2.2 Firebase remediation | `0f1ec680` | Retargeted to `main`. The merged tree is byte-identical to the CI-tested head `9d2adc41` |
| #42 retire `/engine/score` alias writes | `fae33b35` | Ops reads `/scores/engine` (Ops #11, hosting release 2026-10-22T01:36Z). The node is preserved |
| #43 Lake slot age exemption | `1bff61c9` | **Defect found by post-deploy read-back and fixed:** Lake's fleet slot `lastUpdatedAt` is its profile time, so the age rule falsely marked the 5 pilot lakes stale |

## Deployment (`brain-orchestrator` only)

**Lineage preflight** (deployed `7dae7051` is an ancestor) and the **stale-score guard** both passed before each deploy. The IAM bindings and scheduler settings the script re-applies already existed, so those steps were no-ops.

| Field | Before | After |
|---|---|---|
| Commit label | `7dae7051825f` | `1bff61c92908` |
| Image | `sha256:cb2e6922…` | `sha256:6ad1c1bdfcfba8138ec1976b9d001ea2e08661b9cc1b32a03559803359c12f17` |
| Args | none | `--publish-engineering-status` (O-1) |
| Env | `WIND_MEASUREMENTS=on` | unchanged |
| Service account | `brain-writer` | unchanged |
| Scheduler | PAUSED | **PAUSED** |

**Rollback:** `gcloud run jobs update brain-orchestrator --image …@sha256:cb2e6922e514d28454226d7450da9a253e8bf9421eb440d6de85376129d80697 --update-labels commit=7dae7051825f --update-env-vars DEPLOYMENT_VERSION=brain-orchestrator@7dae7051825f --args=` (empty args = O-1 off).

**Not redeployed:**
- **wind-hourly** (`e6a5026f`, ENABLED): the remediation's Wind changes only matter when the legacy copy is retired, which would delete a record (not authorized).
- **lake-brain** (`a6622f99`): off-main lineage; needs the Lake owner.
- Every other Brain job is unchanged.

**Pre-deploy scorer dry-run (read-only):** every displayed score equals production. Wind is HELD by the stale-score guard; that is pre-existing.

**ADMIN cycles** (`--no-execute --trigger ADMIN --publish-engineering-status`): 0 Brains executed, 3 deferred.

## Engineering status (`/control/engineeringStatusV1`)

**Read-back:**
- AVAILABLE, `engineering-status-ops-v1` 1.1.0;
- `sourceCommit` `1bff61c92908…`, `MAIN_COMMIT`, branch `main`, `certificationCurrent` true;
- `publishedBy` `brain-orchestrator@1bff61c92908`;
- 8 Brains; sanitizer reports no problems.

**Sector Ops reader** (`validateEngineeringStatus` / `engineeringView` from Ops `main`, run against the live document): valid, 0 quarantined, READY. One accurate warning: the deploy-staged projection carries no CI result.

**Production activation layer:** NOT_VERIFIED for the 6 active Brains and NOT_APPLICABLE for Depth and Vegetation, never PASS from repository evidence.

## Firebase live verification (read-only)

| Check | Result |
|---|---|
| Brain keys | 7 stable ids (Fish = `biological-state`). No `fish`, `biological-brain` or `vegetation` (Vegetation INACTIVE_EXPECTED) |
| Scores | unchanged: Fish 5.1, Engine 7.0, Lake 3.0, Intelligence 4.8, Clarity 8.0, Water Temp 3.0, Wind 3.3 |
| `/engine/score` | preserved and frozen at its 2026-10-20 value; no longer written |
| `/brains/wind/scores` | preserved (3.1); still written by the deployed Wind image |
| Freshness | `/control/fleet/{k}` uses `SLOT_FLAG_OR_POLICY_AGE`; Clarity (621) and Water Temp (621) slots are stale by FLAG or AGE; Lake is not falsely aged |
| `/jobs/lake-brain-ledger-daily` | owner lake-brain, DEPLOYED, SCHEDULED, no warning |
| Orphaned rollup parents | preserved (deprecated; no deletes) |
| Rules | live = Sector Ops `main` (#14) = the Engine least-privilege proposal, byte-for-byte. The emulator passes all 19 least-privilege checks on the live rules. Engine backends use the admin service account, which rules don't restrict |
| Schedulers | unchanged: wind-hourly and lake-brain-ledger-daily ENABLED; all others PAUSED |

## Left inactive (deliberately)

- G-1 knowledge approvals.
- Depth and Vegetation science (abstain).
- Fish capability v2 publication.
- Publisher LIVE.
- Rubric or score changes.
- Legacy deletions (C-1 to C-4).
- The Wind legacy copy switch: `PUBLISH_LEGACY_SCORE_COPY` stays True, because retiring it deletes `/brains/wind/scores` on Wind's next run.
- Brain schedules.
