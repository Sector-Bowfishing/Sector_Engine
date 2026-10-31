# Recurring Publisher job and identity-split plan: Session Record

```text
Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (clean), pack sector/engine (repository pin d5c8380, identical tree)
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/recurring-publisher-2026-10-31 · Start commit: ca669772 (origin/main) · Date: 2026-10-31
```

## 1. Scope
- **Request and mode:** overnight run (Sector_Ops issue 24, step 2; roadmap §2): plan and code the recurring Publisher service and the shared-writer identity split, with denied-write tests, ready for approval. **Not applied:** no deploy, no IAM change, no cloud run, no database access.
- **Inspected:** `publisher_live/` (LivePublisher, authorization, release resolver, RTDB client, security model), `publisher/storage.py` views, `publication_stage.py`, `publication_coordination.py`, `execution_control.py`, `jobs/brain-orchestrator/` (orchestrate, deploy, clarity pilot, IAM probe), `platform/security/`.
- **Not inspected:** live IAM bindings (no credentials; the plan's current state comes from the deploy scripts and the 2026-10-29 pilot report).

## 2. Findings
| ID | Finding | Status | Evidence |
|---|---|---|---|
| RP-1 | No recurring Publisher exists; the pilot ran the Publisher from a tool | FAIL (roadmap §2) | `orchestrate.build_live_publisher` returns None by design; pilot report |
| RP-2 | No hand-off contract exists from the Orchestrator to a separately-run Publisher; the coordinator only knows an in-process `live` object, which the Orchestrator may never construct | FAIL | `publication_coordination.request_publication` |
| RP-3 | The shared writer identity is used by the Orchestrator, Lake, Water Temp and the in-process Brains; Wind has its own admin identity | FAIL (FD-15 target) | `jobs/brain-orchestrator/deploy-job.sh` header; pilot report |

## 3. Plan and changes made
| Correction | Class | Finding | Files |
|---|---|---|---|
| Publication-request contract (`sector-publication-request-v1`) and the Publisher job's store view | safe (additive internal contract; not wired) | RP-2 | `jobs/brain_platform/sector_brain_platform/publication_requests.py` |
| `brain-publisher` job: one bounded pass, fail-closed execution control, cutover + approval check, digest check, LivePublisher per Brain, dry run by default | requested; not deployed | RP-1 | `jobs/brain-publisher/publish_job.py`, `Dockerfile`, `deploy-job.sh`, `pytest.ini`, `tests/` |
| CI runs the new job's tests | safe | — | `.github/workflows/python-jobs-tests.yml` |
| Identity-split plan as data, plus consistency tests | requested (plan only) | RP-3 | `platform/security/identity_split_plan.json`, `jobs/brain_platform/tests/test_identity_split_plan.py` |
| Plan document | safe (docs) | RP-1..3 | `docs/architecture/production/RECURRING_PUBLISHER_AND_IDENTITY_SPLIT_V1.md` |
| Orchestrator wiring (write requests, start the job) | **decision-required** (execution-plan change), not made | RP-2 | documented in the plan |

## 3a. Standing checks
| Check | Result | Evidence |
|---|---|---|
| Security (SEC-06 effective permissions, writer change) | repository half only: views and key guard deny every non-Publisher prefix and path (tested); real IAM NOT_VERIFIED (X16 LIVE_ONLY) | `tests/test_publish_job.py` denied-write tests |
| Data (FD-15 one writer) | the job writes `publishes/` and the producing Brain's families only; no new database family | key guard tests |
| Central execution control (PL-15/16) | the job has no schedule and refuses while PAUSED unless an admin reference is given | tests |
| Memory (BR-11 release verification) | the job verifies each CENTRAL Brain's packaged release in the staged image; require_approved=True | staged-image test |

## 4. Verification
| Check | Result |
|---|---|
| `cd jobs/brain-publisher && pytest -q` | 16 passed |
| `cd jobs/brain_platform && pytest -q` | all passed (adds 6 plan tests) |
| Full suite set (Kit, architecture, verification, research, orchestrator, all 8 Brains) | all passed; see the PR |
| `deploy-job.sh` without approval | exit 2, "Refusing" |

## 5. Open items
- **Production integration blocker:** Water Clarity's packaged release is not APPROVED, so live publication through this job is refused until Sector_Ops 18 D2 is decided. This is deliberate: the job has no exception flag.
- **Decision-required:** the Orchestrator wiring; decision O-ID (how the Orchestrator's platform-only writes are enforced).

## 6. Decisions required and approvals
| # | Item | Recommendation |
|---|---|---|
| 1 | Approve S1: deploy `brain-publisher` dry-run on the existing Publisher identity | approve after review; dry-run runs prove the pass against real storage without writing |
| 2 | The Orchestrator wiring (requests + start the job) | approve as a small follow-up PR, behind the existing `--coordinate-publication` flag |
| 3 | O-ID | option (b), non-admin auth for the Orchestrator so the rules apply |

## 6a. Cleanup
Worktree `Worktrees/Sector_Engine/overnight-publisher`; closeout in the Sector_Ops 24 closing comment.

## 7. Tested vs. intended
Tested offline with fake clients. Not tested: any real bucket, database, identity or Cloud Run deploy.

## 8. Cortex gaps
None new.

## 9. Next step
Owner decision on Sector_Ops 19 (S1).
