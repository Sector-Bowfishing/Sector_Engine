# Sector Engine — all eight Brains internal production activation — Session Record

```text
Standards: Rehtac Cortex 2.5.0 @ c9f6467 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · main @ cc8a2c74 (start) · Branch: feat/internal-activation-2026-10-22 · Date: 2026-10-22
```

**Owner directive (2026-10-22):** activate all eight Brains for safe, monitored internal production operation, independently of customer
release. Authorized: verified code integration, infrastructure configuration, deployment, scheduling, observability, internal-only
publication and necessary compatible corrections. Not authorized: customer exposure, promotion of unapproved knowledge, score changes,
activating all 621 lakes, Ops write access, customer-app changes.

**Cortex.** The session started at 2.4.0 (054131f). Cortex **2.5.0** (c9f6467) was released during the session. It adds the Internal Brain
Operations standard (`operations.md`, IO-01…IO-12), which governs exactly this work, so it was adopted. A gap first recorded for 2.4.0 ("no
internal-operations standard") was withdrawn before commit.

## 1. Design (one orchestrator, no parallel system)

| Brain | Mode (IO-02) | Internal execution | Due rule | Scope | Output lane / families |
|---|---|---|---|---|---|
| Wind | INTERNAL | `wind-hourly` (unchanged) | hourly | fleet (existing) | INTERNAL families (`brain.json` operations) |
| Lake | INTERNAL | `lake-brain-ledger-daily` (unchanged; off-main image `a6622f99`, Lake owner lineage) | daily 12:00 UTC | pilots | INTERNAL families |
| Water Temp | INTERNAL | `water-temp-brain` started by the orchestrator | 6 h stale | 5 pilot lakes (job args) | INTERNAL families |
| Water Clarity | INTERNAL | **new** `water-clarity-brain` job (C1), started by the orchestrator; the satellite pipeline stays PAUSED | 26 h stale | Guntersville AL, Lake Hartwell SC | INTERNAL families |
| Fish | INTERNAL | in-process in the orchestrator | input change (VERSION) | species knowledge | INTERNAL families |
| Intelligence | INTERNAL | in-process in the orchestrator | dependency change | pilot lakes | INTERNAL families (input assembly only) |
| Depth | INTERNAL (shadow) + APPROVED_SCIENCE (refuses) | **SHADOW lane** in the orchestrator | 24 h | 5 pilots, live Lake states (GET) | `/control/shadowLaneV1/depth` (INTERNAL_EXPERIMENTAL) |
| Vegetation | INTERNAL (shadow) + APPROVED_SCIENCE (refuses) | **SHADOW lane** in the orchestrator | 168 h | packaged fleet (no live observation feed) | `/control/shadowLaneV1/vegetation` (INTERNAL_EXPERIMENTAL) |

The orchestrator's hourly scheduler (`50 * * * *`) is the only new Cloud Scheduler enablement. It starts a job only when that job is due
by its freshness rule. "Daily active" is not forced (no unnecessary runs). Cost caps and stops are recorded in `schedule-policy.json` and
`control_manifest.json`.

## 2. Changes (branch `feat/internal-activation-2026-10-22`)

- **Shadow lane** (`sector_brain_platform/shadow_lane.py`, `jobs/brain-orchestrator/shadow_run.py`, orchestrator stage 5d, `--run-shadow-lane`, `--force-shadow-lane`).
  - It runs the Brain's own runtime and `publish()` against its CANDIDATE release into its in-memory writer.
  - It publishes only an allowlisted summary, marked `lane: INTERNAL_EXPERIMENTAL`, `executionMode: INTERNAL`, `experimental: true`, `authoritative: false` and `customerEligible: false`.
  - It refuses mislabelled documents, and documents that cite an APPROVED release.
  - A failure is recorded at `{node}/lastFailure` and never breaks the cycle.
- **`control_manifest.json`:**
  - Water Temp, Water Clarity, Fish and Intelligence are set ACTIVE.
  - Water Clarity's execution target is the scoped `water-clarity-brain` job, and Water Temp's is scoped to the pilots.
  - ORCHESTRATOR_OWNED schedule exceptions record their gate, cap, stop and approval.
  - Depth and Vegetation gain `shadowLane` blocks.
  - The jobs map gains `water-clarity-brain`.
- **`schedule-policy.json`:** `brain-orchestrator` is added to `allowEnabled`, with its gate, a $3/month cap, its stop and its approval.
- **`jobs.py`:** Clarity is triggered by the orchestrator, once a day.
- **Orchestrator image:**
  - The Dockerfile adds numpy 2.3.4, which Vegetation needs.
  - `deploy-job.sh` stages the Depth and Vegetation runtimes, and grants the invoker role on `water-clarity-brain`.
- **`brains/water-clarity/deploy/deploy-job.sh`:**
  - It deploys the job only, with no scheduler.
  - It uses the existing `brain-writer` service account, with no service-account creation and no project IAM change.
  - `--lakes` is baked in, along with the commit label and rollback text.
- **CI:** the image verification imports Depth and Vegetation, with their candidate releases, inside the orchestrator image.
- **Cortex 2.5.0 adoption:**
  - Every `brain.json` gains an `operations` block (IO-12), and `contracts/schemas/brain.schema.json` gains the matching additive property. `ops-check --repo` reports 0 findings.
  - CLAUDE.md is pinned to c9f6467.
  - The engineering-status `cortexVersion` is now 2.5.0.
- **Records:**
  - `docs/brains/platform/INTERNAL_OPERATIONS_V1.md`
  - `path_families.json`: `/control/shadowLaneV1/{brain}`
  - the resolved architecture-baseline entry: the orchestrator no longer references `docs/brains/WATER_CLARITY_BRAIN_SCHEDULING.md`
  - Cortex gaps CG-2.5-1 and CG-2.5-2
- **Tests:**
  - A frozen pre-activation manifest fixture, plus a conftest, keeps the scenario tests on their original board.
  - The live-manifest tests assert the new board: due-only starts, shadow isolation (no writes to `lakes/`, `lakeFleet/`, `snapshots/`, `brains/depth|vegetation`, `scores/` or `species/`), cadence and force, refusal of an approved release, failure recording, a dry run that writes nothing, and no scheduler drift.

## 3. Verification before merge

- All offline suites pass, including platform, orchestrator, brain-scores, the legacy job suites, all eight Brains, architecture, verification, certification kit and the Wind package.
- Knowledge release manifests: `--check` OK for all five packaged releases.
- The orchestrator staging block was run locally:
  - The Depth and Vegetation runtimes import in the staged layout.
  - `run_shadow` returned `ok` for both: Depth 1.4 s, 9 patches; Vegetation 0.2 s, 54 patches.
- `ops-check --repo`: 0 findings.
- `data-check`: the only new findings are three UNREGISTERED_PATH entries for `/control/shadowLaneV1` (CG-2.5-1).

## 4. Merges and deployments (all from merged `main`, detached worktree checkout)

| Step | Result |
|---|---|
| PR #51 (activation) | CI 9/9 pass, `gh pr checks` rc=0 → merged `cfddec57` |
| `water-clarity-brain` | deployed `cfddec572036` (`brain-writer`, `--lakes Guntersville|AL,Lake Hartwell|SC`, no scheduler); orchestrator granted `run.invoker` on the job |
| `water-temp-brain` | arguments scoped to the 5 pilot lakes via `jobs replace` (image `e6a5026f` unchanged; gcloud refuses a repeated flag in `--args`) |
| `brain-orchestrator` | deployed `cfddec572036`, then `7b2a80110868` (lineage preflight and stale-score guard passed; engineering status staged MAIN_COMMIT); args `--publish-engineering-status --publish-health --run-shadow-lane`; env `WIND_MEASUREMENTS=on`, `WATER_TEMP_SCOPE=pilots` |
| PR #52 (fix, below) | CI 7/7 pass, rc=0 → merged `7b2a8011` |
| Cloud Scheduler `brain-orchestrator` | **ENABLED** 2026-10-22T06:48:16Z (`50 * * * *`); `check_preproduction_schedules.py`: every enabled scheduler is gated (wind-hourly, brain-orchestrator, lake-brain-ledger-daily) |

## 5. Live execution evidence (2026-10-22, UTC)

| Time | Execution | Trigger | Result |
|---|---|---|---|
| 06:25 | `brain-orchestrator-wgkg7` (`--dry-run --force-shadow-lane`) | ADMIN | in Cloud Run: both shadow runtimes COMPUTED (Depth 5 pilots DEGRADED; Vegetation 51 lakes); Water Temp and Clarity due; nothing written |
| 06:27 | `brain-orchestrator-49796` | ADMIN (SCHEDULE decisions) | started `water-temp-brain-l96t8` and `water-clarity-brain-fmjb8`; shadow summaries PUBLISHED; health plane and engineering status AVAILABLE |
| 06:29–06:30 | `water-temp-brain-l96t8` | orchestrator | SUCCEEDED 88 s: 5 lakes, HEALTHY, 0 model failures, readiness CALIBRATION 5 |
| 06:29–06:30 | `water-clarity-brain-fmjb8` | orchestrator | SUCCEEDED 98 s: 2 lakes published, HEALTHY |
| 06:31 | `brain-orchestrator-zk6gq` | ADMIN | Sector Intelligence DEPENDENCY_CHANGED → RUN, published (pilot lakes) |
| 06:46 | `brain-orchestrator-xkdmg` (`--run-now biological-state --scope guntersville`) | ADMIN | Fish MANUAL → RUN, executed: state matches upstream, nothing to republish (honest no-op); Water Temp and Clarity SKIP_NOT_DUE (fix verified live) |
| **06:50** | `brain-orchestrator-n8z9b` | **Cloud Scheduler** (HTTP 200) | first scheduled cycle SUCCEEDED (38 s): nothing due, nothing started, shadow lanes NOT_DUE |

Per-lake readback (Guntersville AL): Water Temp state `provenance.generatedAt` 2026-10-22T06:30:25Z; Clarity `generatedAt` 06:30:35Z, fresh until 2026-10-23T08:30Z.

`/control/shadowLaneV1/{depth,vegetation}` read back:
- lane INTERNAL_EXPERIMENTAL, mode INTERNAL, experimental true, knowledgeState CANDIDATE, authoritative false, customerEligible false.
- Each carries its candidate release id and digest, approval NOT_RECORDED, and approvedPath ABSTAIN (G-1).
- Lake rows hold only readiness and kind.

## 6. Defect found and fixed during activation (PR #52)

A scoped `water-temp-brain` run refreshes its 5 lakes but does not restate the 621-lake registry. `/brains/water-temp.lastSuccessfulRun` therefore stayed at 2026-10-14. Once the start lock expired, `due()` would have started the job on every hourly cycle, an unnecessary recurring cost. The scheduler was still paused, so no extra run happened.

**Fix:** for scoped Cloud Run jobs that the orchestrator starts, `/jobs/{job}.lastSuccessfulAt` also counts:
- the later timestamp wins, and nothing is invented;
- the decision context and the control plane both use the merged state, so they agree;
- `lastSuccessfulRunBasis` is added to the control plane, labelling a scoped refresh;
- a mutation check confirmed that the regression test fails without the fix.

## 7. Isolation, scores and Ops compatibility

| Check | Evidence |
|---|---|
| Brain-owned Depth/Vegetation paths untouched | `/brains/depth` and `/lakes/*/states/depth` last written 2026-10-14T04:25Z; `/brains/vegetation` absent |
| RTDB rules | live rules (sha256 `72f321bd…`) identical to Sector Ops `main` `database.rules.json`; this mission deployed no rules. `/control` is readable only by `access/opsUsers`, and `.write: false` |
| Customer apps / Engine API | not changed and not redeployed; no customer path reads `/control` |
| Brain capability scores | `/scores/{brain}.value` identical before and after for all 7 scored Brains (Fish 5.1, Lake 3.0, Intelligence 4.8, Clarity 8.0, Water Temp 3.0, Wind 3.3) |
| **Engine score** | **7.0 → 7.2** at 06:32Z. Only the `platformHealth` dimension moved (5/6 → 6/6 conformant), after Sector Intelligence re-published its registry in the dependency run. This is the approved `engine-score-v1` rubric applied to real operational evidence. Cortex 2.5.0 SC-05/IO-09 says internal activation never raises a score, while also keeping existing rubrics authoritative until a change is approved. Not overridden; **decision D-IA-1** |
| Ops compatibility | `/control/orchestratorV1` gains one optional field; Ops reads it through TypeScript types only (no runtime schema rejection). `/control/shadowLaneV1` has no Ops consumer yet |
| `ops-check --status` | `docs/cortex/operations/brain-operations-status-2026-10-22.json` gives 2 findings: CONFLATED_READINESS for Depth and Vegetation. The legacy `operationalReadiness` label is BLOCKED on scientific approval for SHADOW Brains. Redefining a consumer-read label is decision-required: **D-IA-2** |

## 8. Costs (estimates from measured durations; Cloud Run us-central1 list prices, before free tier)

| Component | Basis | Estimate |
|---|---|---|
| `brain-orchestrator` | 720 cycles/month × ~40–90 s × (1 vCPU, 0.5 GiB) | ≈ $0.6–1.2/month (cap $3) |
| `water-temp-brain` | ≤ 4 runs/day × 88 s × (1 vCPU, 1 GiB) | ≈ $0.2/month (cap $2) |
| `water-clarity-brain` | ≤ 1 run/day × 98 s × (1 vCPU, 2 GiB) | ≈ $0.07/month (cap $2) |
| Shadow lane | runs inside the orchestrator (Depth ~1.4 s/day, Vegetation ~0.2 s/week) | negligible |
| Cloud Scheduler | an existing job was resumed; no new scheduler job | none new |

## 9. Rollback and disable

See `docs/brains/platform/INTERNAL_OPERATIONS_V1.md` (Disable and rollback). Previous versions:

| Component | Previous version |
|---|---|
| `brain-orchestrator` | image `sha256:202e4a08…`, commit label `817d2f909b69`, args `--publish-engineering-status --publish-health`, scheduler PAUSED |
| `water-temp-brain` | args `--rtdb https://sector-brain.firebaseio.com` (fleet) |
| `water-clarity-brain` | did not exist |

## 10. Worktree and local data closeout (DEV-08)

- Worktree `~/Desktop/Development/Worktrees/Sector_Engine/internal-activation`:
  - registered ACTIVE at the start and COMPLETED at the end;
  - all its commits are on `origin`;
  - it is removed with `git worktree remove` after the records PR merges.
- No research data was created or downloaded; Sector Research was not touched.
- Scratch evidence (pre-activation job specs, score baselines, rules fingerprint) is in the session scratchpad. It is DISPOSABLE, and its facts are recorded here.
