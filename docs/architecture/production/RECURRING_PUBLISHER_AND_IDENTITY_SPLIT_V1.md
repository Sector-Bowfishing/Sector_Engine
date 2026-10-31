Standards: Rehtac Cortex 3.1.1 (pin per CLAUDE.md)

# Recurring Publisher service and identity split (prepared 2026-10-31; NOTHING here is deployed, armed or authorised)

The pilot published Water Clarity once, from the pilot tool under the Publisher identity. Every later Brain needs a recurring Publisher, and needs the shared writer identities split, so that "only the Publisher writes canonical Brain intelligence" can become true ([REMAINING_BRAIN_MIGRATIONS_V1.md](REMAINING_BRAIN_MIGRATIONS_V1.md), the shared blocker class). Identity names, current bindings and project details are in the private record (Sector_Ops 19), not here.

## 1. The recurring Publisher: `jobs/brain-publisher/`
| Item | Design |
|---|---|
| Shape | One Cloud Run job, one task, **one bounded pass per execution** (`publish_job.py`, at most `--max-artifacts` per pass, default 4). No service, no queue, no new framework |
| Trigger | **brain-orchestrator only** (PL-15 single scheduling authority). The job has no schedule; the deploy script creates none (tested) |
| Fail closed | `/control/executionControlV1` must be ENABLED, and the Brain enabled in it. Missing, unreadable or invalid = PAUSED, and nothing is published. An admin run names its approval with `--admin-ref` (PL-15) |
| What it publishes | Only Brains that the reviewed `publication-cutover.json` (the same file the Orchestrator stages) marks CENTRAL with an `approvalRef`, and only artifacts the Orchestrator **requested** |
| Hand-off | The Orchestrator writes `exports/orchestrator/publication-requests/{brain}/{artifactId}.json` (create-only, `sector-publication-request-v1`, a reference only). The job reads it, checks the artifact's stored digest, and publishes through the existing `LivePublisher`. The outcome is the Publisher's immutable history (`publishes/`), which the Orchestrator already imports (`import_publisher_history`). Neither side can write the other's prefix (tested) |
| Publisher | The existing `LivePublisher`, one per Brain: its own `LiveAuthorization` (from the cutover document), the shared validators, baseline reconciliation, per-Brain lock, key guard, atomic apply, readback, immutable record. Nothing re-implemented |
| Release | `PackagedReleaseResolver(require_approved=True)`. There is no exception flag, so a Brain whose packaged release is not APPROVED is refused (Water Clarity today: Sector_Ops 18 D2 is undecided) |
| Modes | Default **dry run**: the identical preparation, with a read-only database wrapper; nothing is written anywhere. `--live` arms the database client; the deploy passes it only with `PUBLISHER_MODE=live`, which needs its own approval |
| Writes | `publishes/` in the artifact store; in the database, the producing Brain's validated families only. Never `/scores`, `/control`, `/health`, `/jobs` (key guard, tested) |
| Deploy | `deploy-job.sh` refuses without `MICHAEL_APPROVED_BRAIN_PUBLISHER_DEPLOY=yes`, creates no identity, binds no role, and stages the cutover document plus each CENTRAL Brain's packaged release (`--stage-only` for review; tested) |
| Rollback | Delete the job or redeploy the previous commit. The Publisher's history and heads are never rewritten by a job rollback; `LivePublisher.rollback` is the data rollback |

### Not wired yet (decision-required)
`orchestrate.py` does not write requests or start the job. Doing so changes the Orchestrator's execution plan (PROJECT §6: decision-required). The change is small: in `publication_stage.run_stage`, for a CENTRAL Brain whose artifact passed shadow, call `publication_requests.write_request(...)`, then start `brain-publisher` within the cycle's start budget. Its test is a cycle with a fake job runner.

## 2. Identity split (plan; machine-readable in `platform/security/identity_split_plan.json`)
Separation is by identity, because Firebase Realtime Database IAM is project-wide (no path-level IAM) and admin identities bypass rules. Each step is approved on its own, and the next one starts only after a passing denial probe.

| Step | Change | Gate |
|---|---|---|
| S0 | Water Clarity job on its own read-only identity | done (pilot) |
| S1 | Deploy `brain-publisher` in dry-run mode on the existing Publisher identity (no new grant) | Sector_Ops 19 |
| S2 | `brain-publisher` live for Water Clarity; the Orchestrator writes requests and starts it | Sector_Ops 18 D1 + D2; the Orchestrator wiring decision |
| S3 | Wind's hourly job onto its own read-only identity at the Wind cutover | 7-day shadow equivalence + Wind cutover |
| S4 | Water Temperature off the shared writer | its cutover plan |
| S5 | Lake off the shared writer | its cutover plan + Sector_Ops 22 |
| S6 | Sector Intelligence stops writing in process; it emits an artifact | its cutover plan |
| S7 | The Orchestrator gets its own identity; the shared writer is left only with the frozen legacy combined package | owner, plus decision O-ID below |
| S8 | After the Fish/Biological split: the shared writer is deleted | M01-M03 and their cutovers |

**Decision O-ID (needed before S7).** An Orchestrator identity with database write can technically still write Brain paths, because IAM is project-wide. Options: (a) accept it, relying on code ownership tables, the key guard and an audit of the Orchestrator's own writes; (b) have the Orchestrator write through a non-admin Firebase auth token, so that the database rules restrict it to platform families. Recommendation: (b). It is the only option that makes the rules real for the Orchestrator, but it needs a rules change (gated) and emulator tests for each audience (SEC-08).

### Denied-write tests in this repository (fake clients; they never prove IAM)
- The Publisher job's view cannot create under `artifacts/`, the request prefix, `exports/orchestrator/` or `scores/`, and has no delete. The Orchestrator's view cannot write `publishes/` or heads.
- The Publisher key guard refuses `/scores`, `/control`, `/health/jobs`, `/jobs`, the scorer's field and another Brain's paths.
- The job arms the database client only with `--live`; a dry run's database wrapper refuses every write.
- The plan file: every registered Brain has a current and a target class; in the target only the Publisher writes Brain data (the legacy combined package is the one named exception, BA-04); the steps are ordered like `cutover_order.json`; and the file contains no account names or project details.

X16 (write denial under real rules **and** real IAM) stays LIVE_ONLY. Each step's real denial probe follows the pattern of `jobs/brain-orchestrator/iam_probe.py`.
