# Wind Brain: RTDB ownership matrix (step 4, exit D)

Live counts captured 2026-10-15 (read-only). Legend: **W** = `wind-hourly` publisher. **Orch** = orchestrator. **Score** = Brain Score Publisher. Statuses per `BRAIN_PATH_OWNERSHIP_V1.md` §2. "Target" assumes the Publisher exists (not built; see `WIND_CERTIFICATION_STATUS.md`).

| Path | Owner (target) | Current writer | Current readers | Class | Canonical / derived / dup / legacy | Lifecycle | Future target | Migration action |
|---|---|---|---|---|---|---|---|---|
| `/brains/wind` (registry; 4.4 KB; whole-node write each run) | `wind` | W | Ops (whole `/brains`), SI, orchestrator (fingerprint over 6 fields), score publisher | RUNTIME | CANONICAL registry. Embedded `scores{}` = **duplicate/stale** (3.1) and BWIS copy | current | Publisher writes; `scores{}` removed or relabelled | drop `scores{}` from artifact after Ops stops reading it (Ops `brainScore.ts`/`windBrain.tsx` read it today) |
| `/brains/wind/publication`, `/certification` | Orchestrator | none yet | none | RUNTIME | new | — | Publisher | create at cutover |
| `/scores/wind` | Platform (scoring) | Score (from baked `frozen-scores.json`) | Ops, orchestrator, Engine score | RUNTIME | CANONICAL `ENGINE_READINESS_SCORE` = 3.3. `secondary` (BWIS) violates "one authoritative score per node" | current | Platform | move BWIS out of `/scores/wind`, label in Wind artifact (after reader check) |
| `/validation/wind` (4.7 KB) | `wind` | W (whole node; embedded `scores`, `liveValidation`, `modelHistory`) | Ops, SI (`status`) | RUNTIME (summary of OBSERVATION_VALIDATION) | CANONICAL summary; `scores` = duplicate | current | Publisher | strip duplicate scores; baked into image from `validation_evidence.json` (changes only on redeploy; HISTORY of the frozen evidence lives in git) |
| `/lakes/{k}/states/wind` (4 lakes, 5.4 KB each) | `wind` | W (PATCH per lake) | **none** found (Ops and SI read the snapshot copy) | RUNTIME | CANONICAL state | hourly | Publisher | move readers to this path, then retire snapshot |
| `/lakes/{k}/profiles/wind` (74; ~4.4 KB each) | `wind` | W (4 dev lakes each run; 70 national only when fetch-table sha changes) | none direct | RUNTIME (profile compiled from DERIVED fetch tables) | CANONICAL profile | slow | Publisher | skip when fingerprint unchanged |
| `/lakes/{k}/validation/wind` (4) | `wind` | W (`null` on evidence miss) | none direct | RUNTIME | derived from frozen evidence | frozen | Publisher | replace null-on-miss with explicit `UNKNOWN`/omit-without-delete rule |
| `/lakeFleet/{k}/slots/wind` (4) | `wind` | W | Ops fleet | RUNTIME | DERIVED_PROJECTION of the state | hourly | Publisher, same atomic publish as the state | keep |
| `/lakeFleet/{k}/readiness/wind` (621) | `wind` | W (all 621 rewritten **every run**) | Ops, SI (`lakeFleet/{k}`), orchestrator | RUNTIME | DERIVED_PROJECTION (readiness ladder) | changes rarely | Publisher | write only on change (fingerprint) |
| `/lakeFleet/{k}/modelVersions/wind` (4) | `wind` | W | Ops | RUNTIME | DERIVED_PROJECTION | rare | Publisher | keep |
| `/lakeFleet/{k}/lakeId` | shared | any Brain | — | RUNTIME | duplicate identity field (open to every Brain today) | — | Lake Brain / registry | outside Wind scope; flag to platform |
| `/snapshots/{k}/latest/wind` (4) | `wind` (legacy) | W (state written twice) | **Ops (`/snapshots/{k}/latest`), Sector Intelligence (reads `snapshots/{k}/latest` and its `wind` field)** | RUNTIME | **exact duplicate** of `/lakes/{k}/states/wind` (verified byte-equal for all 4) | legacy | none | status **`LEGACY_READER_PRESENT`**. W keeps writing it in the same atomic publish until readers move (14-step retirement). **Not retired here** |
| `/snapshots/{k}/latest/{lakeId, brainVersions/wind}` | `wind` (own `brainVersions.wind`) | W | Ops, SI | RUNTIME | legacy | legacy | none | same as above |
| `/health/brains/wind` | `wind` | W | Ops, SI | RUNTIME | process health, not evidence freshness | each run | Publisher | add distinct evidence-freshness fields (see artifact §5) |
| `/health/jobs/wind-hourly` | `wind` job record | W | Ops | RUNTIME | duplicate of parts of `/jobs/wind-hourly` | each run | Orchestrator | keep until Ops reads `/jobs` only |
| `/jobs/wind-hourly` | Orchestrator | Orch | Ops | RUNTIME | CANONICAL job record; `outputs[]`/`statePaths[]` are a **subset** of what Wind writes (claims, not truth) | each orchestrator pass | Orchestrator via Publisher | reconcile the declaration with this matrix |
| `/sources/{noaa-nbm-v5, noaa-rtma-ru, iem-metar-wind}` | `wind` (acquisition owner) | W (whole node, includes `brains:{wind:true}`) | Ops | RUNTIME | CANONICAL; `ownerBrainId = wind` present, `authorizedConsumers[]` **missing** | each run | Publisher | add `acquisitionOwnerBrainId` + `authorizedConsumers` (empty today; Fish/SI consume only via Wind's published contract) |
| `/health/sources/{same 3}` | `wind` | W | Ops | RUNTIME | health | each run | Publisher | keep |
| `/activity/{ms}-wind-{n}` (4 wind events of 51) | `wind` | W (+ prune: reads the whole `/activity` node) | Ops (last 50) | RUNTIME/HISTORY | events; score events are written by the platform | bounded | Publisher | keep |
| `/control/fleet/{k}/readiness/wind` (621) | Platform | Score | Ops | RUNTIME | **duplicate** of `/lakeFleet` readiness | each score pass | Platform | outside Wind's scope; record only |
| `/control/overview/brains/wind` | Platform | Score | Ops | RUNTIME | DERIVED projection (score, blockers, dimensions) | | Platform | none |
| `/control/orchestratorV1/brains/wind` (+ edges, decisions, executions) | Orchestrator | Orch | Ops | RUNTIME | DERIVED; `outputFingerprintBasis = REGISTRY_PROJECTION` (6 registry fields only: does not cover the lake states) | | Orchestrator | the orchestrator never fingerprints Wind's lake state, only the registry projection |
| `/control/orchestrator`, `/control/beta` Wind mentions | Platform | Orch / Score | Ops | RUNTIME | legacy / derived | | Platform | none |
| `/scores/engine` and `/engine/score` (Wind contributes 3.3) | Platform | Score | Ops | RUNTIME | exact duplicates of each other | | Platform | out of Wind scope |

## Observations
1. Wind writes **~1,260 paths per run unconditionally** (all 621 `readiness/wind` rows + states, profiles, registry...), though only 4 lakes carry live state. Steady state = 7 PATCH requests per run; each PATCH is atomic, the run as a whole is not.
2. Everything in `/lakes/{k}/states/wind` has **no reader** today; consumers read the duplicate snapshot copy. This makes the snapshot the de-facto serving path; migrating readers is the gating step for retiring it.
3. Not written by Wind (verified in code and by the writer's ownership table): `/schemaVersion`, `/health/engine`, `/health/rtdb`, `/access`, `/validationOps`, `/scores`, `/jobs`, `/control`, `/engine`.
