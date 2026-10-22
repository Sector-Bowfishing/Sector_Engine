# Internal Brain operations V1 (2026-10-22)

Owner directive (2026-10-22): run all eight Brains internally, monitored and safe, while their science keeps improving. Customer
publication stays separately gated (`customerPublication: false` for every Brain; `engineMode` PRE_PRODUCTION). This applies Cortex 2.5.0
`operations.md` (IO-01…IO-12); each `brains/*/brain.json` declares its `operations` block (execution modes, knowledge loading, internal
publication families, customer status), checked by `cortex.py ops-check sector/engine --repo .`.

## Four independent dimensions per Brain

| Dimension | Meaning | Evidence |
|---|---|---|
| Runtime readiness | the Brain's runtime executes in the intended infrastructure (approved path, or SHADOW lane) | a real execution in Cloud Run / the orchestrator |
| Internal operation | `ACTIVE` = scheduler or trigger enabled **and** an execution observed within the expected interval; `SHADOW` = the INTERNAL-mode shadow lane runs (IO-08) | scheduler/orchestrator state, `/jobs`, `/control/healthV1`, last successful run |
| Scientific validation | the Brain's validation status (`/validation/{id}`) | unchanged by this mission |
| Customer eligibility | none in PRE_PRODUCTION | `customerPublication: false`, `orchestration.publish_allowed()` |

Scientific maturity or capability scores are **not** prerequisites for internal execution.

## Approved path (APPROVED_SCIENCE) vs SHADOW lane (INTERNAL mode)

- **Approved path (`APPROVED_SCIENCE` mode):** the Brain's normal writer. A Brain whose knowledge release is not APPROVED keeps refusing on this path (`BLOCKED_AWAITING_APPROVED_RELEASE`).
- **SHADOW lane** (`control_manifest` `brains[*].shadowLane`; `brain-orchestrator --run-shadow-lane`; `jobs/brain-orchestrator/shadow_run.py`):
  - **What it runs:** the Brain's own runtime and `publish()` against its CANDIDATE release, into the Brain's in-memory writer. Nothing is written to Brain-owned paths.
  - **What it publishes:** only `/control/shadowLaneV1/{brainId}` (`brain-shadow-lane-v1`, `lane: INTERNAL_EXPERIMENTAL`, `executionMode: INTERNAL`, `experimental: true`, `knowledgeState: CANDIDATE`, `authoritative: false`, `customerEligible: false`). The Cortex registry family is pending (CG-2.5-1).
  - **Summary contents:**
    - the candidate release id, digest and approval status;
    - the approved path's status (ABSTAIN + reason);
    - per-lake readiness/kind only (an allowlist);
    - counts, and a SHA-256 of the full in-memory output.
  - **Retention:** latest summary plus the last 10 runs.
  - **Forbidden consumers:** customer apps and the Engine API, Sector Intelligence, the scorer.
  - **Brains:** Depth (24 h cadence; live Lake states) and Vegetation (168 h; packaged knowledge only, no live observation feed).

## Internal schedules

The orchestrator (hourly, `50 * * * *`) is the only new Cloud Scheduler. It starts orchestrator-owned jobs **only when due** by their freshness rule:

| Brain | Execution | Due rule | Scope | Cost cap |
|---|---|---|---|---|
| Water Temp | `water-temp-brain` | 6 h | 5 pilot lakes | $2/mo |
| Water Clarity | `water-clarity-brain` (C1; the satellite pipeline stays PAUSED) | 26 h | 2 pilot lakes | $2/mo |
| Fish | in-process | input change (VERSION) | — | — |
| Intelligence | in-process | dependency change | pilot lakes | — |

Wind (`wind-hourly`) and Lake (`lake-brain-ledger-daily`) keep their validation-exception schedulers. All schedules are recorded in `docs/brains/platform/cost-freeze/schedule-policy.json` (gate, cap, stop, approval) and checked by `check_preproduction_schedules.py`.

## Disable and rollback

| Action | How |
|---|---|
| Pause everything internal | `gcloud scheduler jobs pause brain-orchestrator --location us-central1` (wind-hourly and lake-brain-ledger-daily are separate) |
| Park one Brain | set `activityState: PARKED` in `control_manifest.json` (or an accepted PAUSE override); its existing state stays readable |
| Stop the shadow lane | remove `--run-shadow-lane` from the orchestrator job arguments, or set `shadowLane.enabled: false` |
| Roll back the orchestrator | `gcloud run jobs update brain-orchestrator --image <previous digest>` with the matching `commit` label and `DEPLOYMENT_VERSION` |
| Water Temp scope | `gcloud run jobs update water-temp-brain --args=...` |
| Clarity job | redeploy the previous commit, or delete `water-clarity-brain` (no scheduler depends on it) |
