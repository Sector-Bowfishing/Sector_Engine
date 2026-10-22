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

## 4. Deployment and live evidence

Recorded in the completion record after deployment (§5 onward, appended in the follow-up records commit).
