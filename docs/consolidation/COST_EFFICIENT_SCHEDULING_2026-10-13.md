# Cost-efficient jobs, scheduling & orchestration — implementation record (2026-10-13)

Branch `feat/cost-efficient-scheduling` (from `main` @ e596a6bb). Follows the read-only audit
`JOBS_SCHEDULES_COST_AUDIT_2026-10-13.md`. Customer boundary respected throughout: no `sector-engine`
revision, traffic, tag or minScale change; no candidate promotion; no 5A; no customer science or app change;
no private Clarity exposure; nothing deleted (schedulers paused, not removed).

## Schedule matrix — before → after

| Workload | Before (audit) | After | Class |
|---|---|---|---|
| `wind-hourly` | `5 * * * *` UTC, re-reads the newest NBM cycle every run | same cron; **NBM early exit** when the newest cycle is already archived complete for every lake; redeployed from main (`main@e6a5026f`, Brain publish on the contract code) | INTERNAL (science RESEARCH_CANDIDATE) |
| `water-temp-tva-archive` | `20 * * * *` UTC | unchanged (source retains ~24 h) — full `/jobs` record | INTERNAL |
| `hydrology-hourly` | `15 * * * *` UTC, ENABLED | **PAUSED** (kept) | RESEARCH |
| `clarity-current-hourly` | `40 * * * *` UTC, ENABLED | **PAUSED** (kept) | RESEARCH |
| `lake-surface-daily` | `0 3 * * *` CT: 8 tasks × 4 vCPU / 16 Gi for all 621 lakes, 74–87 min | **dispatcher-triggered** only for lakes with a newer pass, task count sized to the work; its scheduler PAUSED (kept); image untouched (D4 exception) | INTERNAL |
| `lake-surface-dispatch` (new) | — | `0 3 * * *` CT, single task 1 vCPU / 512 Mi, ~17 s discovery over 599 outlines; attempted-pass ledger so a rejected pass is never re-read | INTERNAL |
| `clarity-candidate-shadow` | PAUSED | PAUSED (stays) | SHADOW |
| `lake-brain` (new job) | manual `swift run`, state stale (last 2026-10-12 23:46) | scale-to-zero Cloud Run job, **orchestrator-triggered** (TIME, staleAfterHours 3), pilot 5 lakes, no cron | INTERNAL |
| `water-temp-brain` (new job) | never deployed (script would have created `25 */3 * * *`) | scale-to-zero Cloud Run job, **orchestrator-triggered** only when the 6-h rule requires, fleet, no cron | INTERNAL |
| `water-clarity-brain` | manual; its script would create a daily cron | **MANUAL by decision** (`docs/brains/WATER_CLARITY_BRAIN_SCHEDULING.md`); no longer writes other jobs' records | INTERNAL |
| `biological-brain` | manual | in-process in the orchestrator when its own `plan()` says PUBLISH (VERSION); no cron | INTERNAL |
| `sector-intelligence-brain` | manual | in-process when its `plan()` says PUBLISH (FINGERPRINT), pilot only; no cron | INTERNAL |
| `brain-scores` | manual | in-process after a Brain state change (`--if-changed`) | INTERNAL |
| `brain-orchestrator` (new) | design only (D10) | `50 * * * *` UTC wake-up, 1 vCPU / 512 Mi, scale-to-zero | INTERNAL |
| `sector-engine`, Cloud Functions | — | unchanged; classified PRODUCTION in `/jobs` | PRODUCTION |

## What was built
- **`/jobs/{jobId}` contract (jobs-v1)** — `docs/brains/JOBS_CONTRACT.md`; `sector_brain_platform/jobs.py` (+`gcp.py`).
  Cloud Scheduler authoritative for enabled/cron/timezone/nextScheduledAt; executions for runtime; manifest for
  design facts; cost metadata without dollars. Platform-only root (Python, Swift, conformance fixture + 4 cases).
  Published by the orchestrator (one canonical path). 21 records live.
- **Ops read access** — the Ops repo had already committed and deployed rules for `jobs`, `control`, `scores`,
  `engine` (verified live: opsUsers read-only, nothing public). Decision recorded in `OPS_CONTROL_PLANE_CONTRACT.md`:
  `/control/overview` is the Engine summary; no `/engine/summary` projection.
- **Compact fleet summary** — `/control/overview/fleet` (`fleet_summary()`): counts per slot/readiness, stale,
  evidence-stale, issues, newest update; Overview no longer needs 621 `/lakeFleet` rows. Plus `/control/overview/jobs`.
- **Orchestrator executor** — `jobs/brain-orchestrator` (design updated in `ORCHESTRATOR_DESIGN.md`).
- **Satellite dispatcher** — `jobs/lake-surface-dispatch` (least-privilege SA `lake-surface-dispatch`: custom role
  `jobRunnerWithOverrides` on `lake-surface-daily` only, `storage.objectUser` on the bucket).
- **Brain jobs image** — `jobs/brain-image-build.sh` builds the Engine Dockerfile (now also `LakeBrainJob`) to
  `brain-jobs:<commit>` with Cloud Build; `jobs/lake-brain` / `jobs/water-temp-brain` deploy jobs from it. SA
  `brain-writer` (`firebasedatabase.admin`, `run.viewer`, `cloudscheduler.viewer`, job-level `run.invoker`, bucket reads).
- **Warm-tag guard** — `ops/check_warm_tags.sh`, `deploy.sh --check-warm-tags`, post-promote report. Current state: ✓
  (no tagged 0 % revision with minScale ≥ 1; `00080-wes` carries minScale 1 and serves 100 %).
- **Optional CI** — `.github/workflows/python-jobs-tests.yml`, offline, no credentials.

## Measurements
- Wind: `run_hourly` itself 72–79 s; a full execution ≈ 3.8 min (≈ 1 min container start + ≈ 90 s Wind Brain publish
  after the ingest). The scheduled 05:05 run after a manual 04:59 run skipped the already-archived 04Z cycle:
  **110 s** vs 20-run average 202 s. In steady state every hourly run finds a new NBM cycle (posted ~:57), so the
  guard saves time only on extra/late runs; the Brain publish, not the ingest, is the larger fixed cost.
- Dispatcher discovery (cloud, 599 outlines, 8 workers): **17 s**; first work set 299 lakes (267 newer tile-level
  pass, 32 never published) — the heavy job rejects most of those once it reads the lake, which is why the
  attempted-pass ledger exists: each rejected pass is read once, not daily until the next revisit.
- Orchestrator live cycle: ~8 s + the in-process publishes (`/jobs` sync + plan + Intelligence publish ≈ 1 min).
- Estimated job compute after (from `/jobs` cost metadata, cron × avg runtime × resources): wind 1.35 vCPU-h/day,
  TVA archive 0.57, orchestrator ≈ 0.5 (first cycles 151 s incl. dry runs; expected < 1 min), dispatcher 0.05,
  lake-brain/water-temp-brain ≈ 0.2–0.4 (8 × 8 s + 4 × 4.4 min), lake-surface-daily now proportional to real work.
  Before: lake-surface-daily ≈ 9.6 vCPU-h/day (67 vCPU-h + 271 GiB-h per 7 d), hydrology 0.93, clarity-current 1.5.

## First live cycles (2026-10-13 05:28–05:45 UTC)
1. Cycle 1 (05:28): 21 `/jobs` records written; plan RUN lake-brain (5.7 h stale) + water-temp (22.8 h stale);
   starts failed with 403 `run.jobs.runWithOverrides` → fixed by starting jobs **without** overrides (args are baked
   into the job definitions; `roles/run.invoker` is enough). Intelligence published (upstream fingerprint changed);
   scores + 627 control paths written (first publish after the Intelligence republish of 621 states).
2. Cycle 2 (05:33): **`lake-brain-47lvs` started → 5 pilot lakes in 4.5 s (70 s execution), health WARNING
   (baselines INSUFFICIENT, as before); `water-temp-brain-p2g5c` started → 621 lakes in 270 s (5 m 37 s execution),
   HEALTHY, 32 measured / 586 modeled / 3 unavailable, 8 stale.** Intelligence deferred ("upstream started this
   cycle"). Both registries now carry `stalenessModel: TIME`, `deploymentVersion: e6a5026f5d0f`.
3. Cycle 3 (05:41): Intelligence re-evaluated the pilots on the fresh states; Lake / Water Temp reported WAIT
   because the Lake Brain registry publishes `schedule.running` as the **string** `"false"` → fixed in the planning
   core (`_truthy`), test added. `score_brains --if-changed` dry run afterwards: **5 of 628 control paths differ**
   (the 5 pilot Intelligence states) — the diff gate works; cycle 2's 627 writes were real (fleet-wide Water Temp).
4. Cycle 4 (05:47): Lake / Water Temp WAIT on the 15-min start lock from cycle 2 (expected; the lock is now released
   as soon as its execution has completed). Intelligence published **again** although nothing upstream changed:
   `build_updates` recomputed the stored fingerprint from the CONNECTED-upgraded dependency view while `--plan`
   computes it from the pre-run view, so every plan said "changed" (a pre-existing Intelligence bug that would have
   republished ~950 KB every hour). Fixed: the registry stores the planned fingerprint (test added).
5. Cycles 5–6 (after redeploy): one more Intelligence publish (the stored fingerprint switches to the planned
   formula), then **SKIP for every brain** — the quiet-hour cost of the orchestrator is the `/jobs` sync + two
   `--plan` subprocesses (≈ 30 s).

## Phase 20 — self-audit (25 checks, re-verified at close)

| # | Check | Result |
|---|---|---|
| 1 | No new customer-serving `sector-engine` revision | PASS — latest revision still `00080-wes` (2026-10-12 17:55) |
| 2 | Traffic allocation unchanged | PASS — `00080-wes` 100 % |
| 3 | Serving minScale unchanged | PASS — template minScale 1; `00080-wes` minScale 1 |
| 4 | Public tags unchanged | PASS — `clarity`→`00078-kuv`, `fusion`→`00079-zab`, `watertemp`→`00080-wes` |
| 5 | Warm-tag guard clean | PASS — `ops/check_warm_tags.sh` ✓ |
| 6 | No candidate promotion, no 5A, no R3.1 | PASS — nothing in `Sources/SectorEngine/{Engine,Forecast,API,Clarity}` touched (diff vs main: `Dockerfile`, `Package.swift`, `BrainContract.swift` +1 root, `deploy.sh` guard) |
| 7 | Customer Water Temp / Wind science unchanged | PASS — production paths untouched; `wind-hourly` remains candidate archive + Brain publish |
| 8 | iOS / Android behavior unchanged | PASS — no API or app change |
| 9 | Private Clarity research not exposed | PASS — `research/clarity-candidate` e8891326, `feat/clarity-candidate-shadow` 82515896, local `brain/water-clarity` 3c1d9736 unchanged and not on origin (origin holds only the public-safe `brain/water-clarity` 6220491b from consolidation) |
| 10 | Nothing deleted | PASS — schedulers paused, not deleted; no branch / worktree / bucket / job deleted; only a superseded IAM binding (objectCreator → objectUser) was replaced |
| 11 | No force-push / rewrite | PASS — `main == origin/main == e596a6bb`; branch is 9 linear commits ahead |
| 12 | Customer RTDBs untouched | PASS — every writer uses `sector_brain_platform.rtdb` / `RTDBRestStore`, which refuse `sector-9393c-default-rtdb` and `sector-dev-1f4d0` |
| 13 | `/jobs` reflects Cloud Scheduler | PASS — paused jobs show `enabled:false`, `PAUSED`; `lake-surface-daily` shows its paused legacy scheduler; one sync path (orchestrator) |
| 14 | No secrets / SA identities / env values / private paths in `/jobs` | PASS — test `test_nothing_secret_is_published`; records inspected live |
| 15 | Ops read access authenticated, never public | PASS — live rules: opsUsers read-only on `jobs`, `control`, `scores`, `engine`; root false |
| 16 | Wind cadence kept at :05, RTMA/METAR/catch-up preserved | PASS — tests `test_live_early_exit.py`; live run summaries show rtma + metar + bundles |
| 17 | TVA archive hourly kept | PASS |
| 18 | Satellite heavy job not redeployed; dispatcher starts it only with work | PASS — image `30420dc6…` unchanged; dry runs started nothing; `--lakes` + task-count overrides via the narrow custom role |
| 19 | Clarity Brain stays manual; no bad cron created | PASS |
| 20 | Lake Brain pilot only, orchestrator-conditional | PASS — `--scope pilots`; started only when stale; skipped when current |
| 21 | Water Temp no blind 3-h cron; runs on the 6-h rule | PASS — no scheduler exists for it; started once (22.9 h stale) |
| 22 | Biological / Intelligence no cron, plan()-driven; Intelligence pilot only | PASS — Biological SKIP every cycle (version unchanged); Intelligence ran on fingerprint change |
| 23 | Scores / control only after change | PASS — `--if-changed`; 5 of 628 on a quiet cycle |
| 24 | IAM least privilege | PASS — new SAs `brain-writer` (RTDB admin + read-only Run/Scheduler viewers + job-level invoker + bucket reads) and `lake-surface-dispatch` (custom role on one job + bucket objectUser); no Brain credentials in GitHub; CI is offline |
| 25 | Tests | PASS — Swift 217/217; Python 49 + 58 + 11 + 3 + 35 + 29 + 32 + 14 + 3 |

## Rollback (each step independent)
- Schedulers: `gcloud scheduler jobs resume hydrology-hourly|clarity-current-hourly|lake-surface-daily --location us-central1`;
  `gcloud scheduler jobs pause brain-orchestrator|lake-surface-dispatch --location us-central1`.
- Wind: `gcloud run jobs update wind-hourly --region us-central1 --image <previous image a90ea535…>` (the pre-migration image
  is still in Artifact Registry) — or redeploy from `brain/wind @ 4da234cb`.
- Brain jobs / orchestrator / dispatcher: pause their schedulers (above); deleting the jobs is optional and not needed.
- `/jobs`, `/control/orchestrator`: platform-owned nodes; harmless to leave; `score_brains.py --write` keeps working without them.
- Code: revert the branch; `main` is untouched.

## Open decisions for Michael
- D11 **Merge** `feat/cost-efficient-scheduling` → main (READY; see the handoff).
- D12 Retire the `wind-hourly` cron into the orchestrator once it has run cleanly for a few days (the Wind job
  would become orchestrator-triggered by NBM cycle id).
- D13 Clarity Brain follow-up (dispatcher-driven publish) — `WATER_CLARITY_BRAIN_SCHEDULING.md`.
- D14 Water Temp scope: fleet every 6 h (current, ≈ 4 × 4.5 min/day) vs pilots only (would blank the registry's fleet counts).
- D15 Intelligence republishes 621 `NOT_EVALUATED` states (~950 KB) on every fingerprint change — write only changed states.
- D16 Resume `hydrology-hourly` / `clarity-current-hourly` only when the Clarity research path needs them (or retire with D4).
- D17 Next approved customer deploy: switch `sector-engine` to service-level min-instances so tagged candidates never
  keep a warm instance (revision-level minScale is what bit in October).
