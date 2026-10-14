# Platform Current State (verified 2026-10-14, read-only)

> **Update 05:15Z — COST FREEZE applied.** `brain-orchestrator`, `water-temp-tva-archive`, `lake-surface-dispatch` are now **PAUSED**; enabled Brain schedulers are only `wind-hourly` and the new `lake-brain-ledger-daily`. The scheduler table below is the *pre-freeze* state. See `cost-freeze/`.

Method: `git fetch --all --prune`; `gcloud run jobs/scheduler describe/list` (read-only); live RTDB GETs through the platform client; read-only dry runs of the real publisher. Older handoffs were **not** assumed to describe the present.

## Deployed orchestrator
| | |
|---|---|
| Cloud Run job | `brain-orchestrator`, us-central1, project `sector-9393c`, generation **8** |
| Deployed commit | **`5fd727effa4a`** (label `commit`, env `DEPLOYMENT_VERSION=brain-orchestrator@5fd727effa4a`) = tip of `feat/lake-opsvis-on-durability`, last modified 2026-10-14T04:28:18Z by mgcather07@gmail.com |
| Image | `…/brain-orchestrator@sha256:23ceb4d91d200acabf8b555ba410cf66b45e51038492619c2585c5f4f5b0a18f` |
| Resources | 1 vCPU / 512 Mi, task timeout 1800 s, 1 task, max-retries 0 |
| Env | `BRAIN_TOKEN_MODE=metadata`, `BRAIN_RTDB_URL=https://sector-brain.firebaseio.com`, `ENGINE_URL`, `LAKE_BRAIN_ARCHIVE=gs://sector-lake-brain`, `BIOLOGY_BUCKET=sector-biology-private`, `ORCHESTRATOR_SCOPE=pilots`, `WATER_TEMP_SCOPE=fleet` |
| Recent cycles | 02:50Z, 03:50Z, 04:28Z (manual redeploy run) all succeeded, ~70–80 s |

## Scheduler (us-central1, UTC)
| Job | Cron | State |
|---|---|---|
| brain-orchestrator | `50 * * * *` | ENABLED |
| wind-hourly | `5 * * * *` | ENABLED |
| water-temp-tva-archive | `20 * * * *` | ENABLED |
| lake-surface-dispatch | `0 3 * * *` | ENABLED |
| clarity-current-hourly, hydrology-hourly, lake-surface-daily, clarity-candidate-shadow | various | PAUSED |
Cloud Run jobs: brain-orchestrator, clarity-candidate-shadow, clarity-current-hourly, hydrology-hourly, lake-brain (image `brain-jobs:a9d1af8f749b`), lake-surface-daily, lake-surface-dispatch, water-temp-brain (`brain-jobs:e6a5026f5d0f`), water-temp-tva-archive, wind-hourly. Lake and Water Temp have **no** cron of their own; the orchestrator starts them when TIME-stale.

## Lineage
- `origin/main` = `e596a6bb` (2026-10-12). Main does **not** contain the deployed orchestrator work (40 commits ahead on the deployed branch).
- `feat/cost-efficient-scheduling` (48168baa) ⊂ `feat/orchestrator-wind-score-durability` (f7b6b066) ⊂ **`feat/lake-opsvis-on-durability` (5fd727ef, deployed)**. Verified with `git merge-base --is-ancestor`.
- Wind adoption, Biological adoption, Depth, Vegetation, Intelligence, Water Temp adoption branches are **not** in the deployed lineage (specialist work in flight).
- Platform branch: `feat/brain-platform-model-v1`, worktree `../Sector_Engine-brain-platform`, **base 5fd727ef** (the deployed commit itself). Chosen because it is the exact deployed lineage: it contains the stale-score guard, RTDB-key sanitising, content-aware publishing, cost scheduling and Lake ops-visibility fixes; the other candidates are strict ancestors (would drop deployed work). Specialist commits intentionally not imported: all of `feat/wind-brain-adoption`, `feat/biological-brain-adoption`, `feat/depth-brain-foundation`, `feat/vegetation-brain-foundation`, `feat/intelligence-evidence-layer`, `feat/water-temp-brain-adoption`, and the Lake research branches.

## Score publisher (as deployed)
`jobs/brain-scores/score_brains.py --write --if-changed`, run by the orchestrator only when a Brain's `lastSuccessfulRun` changed, something published, or a job record changed. Scores: Lake, Biological, Intelligence **computed** from published facts each run; Water Temp and Clarity **FROZEN** and Wind **generated** from the baked `frozen-scores.json`. Writes `/scores/{id}`, `/scores/engine` (+ `/engine/score` alias), `activity` (`score.changed` only when displayed value/version/basis change), `/control/overview`, `/control/fleet/*`, `/control/beta/*`. Content-aware (`_content` ignores timestamps and RTDB-dropped empties).

## Safeguards in the deployed lineage
1. Deploy-time stale-artifact guard (`check_score_artifacts.py`, manifest `score-artifact-sources.json` lists Wind) — `deploy-job.sh` refuses when a Brain branch holds a newer generated block.
2. `rtdb_safe()` key sanitising of frozen blocks (the 21:50Z Wind `Freshness/reliability` failure).
3. Content-aware score + control publication; `score.changed` durability (one event per displayed change).
4. Lake profile read covers all profiled lakes (no first-200 cap).
**Gap found:** nothing stopped a stale artifact from being *published at runtime* if it somehow got into an image, and nothing stopped a deploy from a lineage that lacks the deployed work. Both are closed on the platform branch (not deployed): `publication.apply_guard` in the publisher, `preflight_lineage.py` in `deploy-job.sh`.

## Live data checks (RTDB, 2026-10-14)
Scores: Lake 3.0, Water Temp 3.0, Clarity 8.0 (FROZEN research), Wind **3.3** (COMPUTED, rubric v1), Biological 4.6, Intelligence 4.8, Engine 7.1. Registry lifecycle `status`: lake/water-temp/wind/intelligence CALIBRATION, biological PROFILED, depth PROFILED (shadow version), clarity BETA; vegetation not registered. Orchestrator last cycle 03:51Z: published (`brain state changed: lake-brain, wind`), 627 of 628 control paths rewritten (see cost note).

## Control-plane publication path
Brain RTDB (`sector-brain.firebaseio.com`) → `/control/overview` + `/control/fleet/{k}` + `/control/beta/{k}` + `/control/orchestrator` + `/jobs/*`, written only by the platform writer `brain-platform` (service account `brain-writer`); Ops reads under authenticated `access/opsUsers/{uid}` read-only rules.

## Verification of the platform branch against live (read-only)
Real publisher dry run (current tree): 0 score changes, nothing held, Engine 7.1. With the old `main` frozen file: `HELD wind STALE`, Wind stays 3.3, Engine unchanged. Shared test suites: brain_platform 85, brain-scores 21, brain-orchestrator 8, sector-intelligence-brain 33, biological-brain 29 — all pass.
