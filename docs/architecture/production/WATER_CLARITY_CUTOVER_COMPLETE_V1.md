Standards: Rehtac Cortex 3.1.1 (pin per CLAUDE.md)

# Water Clarity: `CUTOVER_COMPLETE` flip, prepared (2026-10-31; NOT applied, NOT authorised)

This is the last step of the Water Clarity pilot ([REMAINING_BRAIN_MIGRATIONS_V1.md](REMAINING_BRAIN_MIGRATIONS_V1.md), common gate 8 "Retire"). The code half is done on branch `cortex/water-clarity-cutover-finish-2026-10-31`. The status flip is prepared here and waits for evidence that only an approved cutover can produce.

## What the branch already changes (code only)
| Item | State | Proof |
|---|---|---|
| `run.py` RTDB write sites (`write()` and the abort-path health write) | **removed**; `--legacy-direct-write` is an unknown option | `test_clarity_central_mode.py`, Kit P14 with `allowed_write_sites=frozenset()` |
| Whole-node keys `/brains/water-clarity`, `/health/brains/water-clarity` | **gone** from the runtime; the run reads and emits children only; the builder refuses a whole-node key | `exit_gate.legacy_write_sites(...) == {"writeSites": [], "wholeNodeKeys": []}` (`test_water_clarity_legacy_writer_is_retired_in_code`), `test_a_whole_brain_node_key_fails_the_build` |
| Test harness | drives the REAL `run.main` in CENTRAL mode and captures the payload it seals (it used to drive the direct writer) | `clarity_support.real_run_updates` |
| Output equivalence | the sealed artifact is **byte-identical** to the one the old harness produced, for a first run and for a run with previous Brain state (pinned clock and build context) | session record `docs/cortex/sessions/2026-10-31-overnight-engine-readiness.md` |
| Flip readiness | with the REAL runtime, `CUTOVER_COMPLETE` passes `cutover_guard` once a complete exit record exists, and is refused without one | `test_water_clarity_cutover_complete_waits_only_for_the_exit_record` |
| `brain.json` `publisherRequired.cutoverStatus` | **stays `SHADOW`** | `test_current_brains_are_shadow_and_the_gate_is_not_yet_claimable` |

X14 ("legacy writer cannot re-enter") is now provable offline for Water Clarity. The other 15 exit checks are not changed by this branch.

## The flip itself (one change, applied only after approval)
1. Add `brains/water-clarity/contracts/production-exit-evidence.json`. Every check must be `PASS` with an `evidenceRef` that points at a **private** record. Raw IAM, identity and database detail stays out of this public repository (PRODUCTION_EXIT_GATE_V1).
   ```json
   {"standard": "production-exit-gate-v1", "brainId": "water-clarity",
    "checks": {"X01": {"status": "PASS", "mode": "OFFLINE", "evidenceRef": "<private ref>"},
               "X07": {"status": "PASS", "mode": "LIVE", "evidenceRef": "<private ref>"},
               "...": "X01-X16, all sixteen"}}
   ```
2. `brain.json`: `"publisherRequired": {"required": true, "cutoverStatus": "CUTOVER_COMPLETE"}`.
3. `tools/brain_certification/tests/test_exit_gate.py`: drop `water-clarity` from `BRAINS` in `test_current_brains_are_shadow_and_the_gate_is_not_yet_claimable` (that test exists to stop an early claim), and keep `test_water_clarity_cutover_complete_waits_only_for_the_exit_record`.
4. Regenerate `docs/cortex/engineering-status/` (collect certification, then `build_engineering_status.py --write`).

`cutover_guard` refuses step 2 without step 1, so the two cannot drift apart.

## What must exist before step 1 (none of it is done; each needs its own approval)
| Need | Exit checks | Status |
|---|---|---|
| First real CENTRAL-mode run of the deployed job (Sector_Ops #18) | X07, X10, X15 | NOT_RUN: a cloud job execution needs approval |
| Real readback of every planned path, and an unchanged score and health | X08, X11, X12, X15 | NOT_RUN |
| Rollback rehearsal against a non-production database | X09, X13 | NOT_RUN |
| Write-denial proof with real rules and real IAM | X16 | NOT_RUN: the shared writer identities still hold database admin (Sector_Ops #19) |
| Release approval for `water-clarity-knowledge-2026-10-20.1` | lifecycle; not an exit check | UNDECIDED. The pilot used the calibration-lane exception; this plan does not depend on that decision, but publishing beyond CALIBRATION does |
| Merge this branch and deploy the job from `main` | X14 in production | not approved |

## Rollback
The flip is a repository change: revert the commit. The code retirement on this branch is also a plain revert, which restores the `--legacy-direct-write` path. Do not use it: the job identity is read-only for the database, so that path could not write anyway.
