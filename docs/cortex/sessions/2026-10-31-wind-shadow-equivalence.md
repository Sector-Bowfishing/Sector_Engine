# Wind 7-day shadow equivalence, prepared: Session Record

```text
Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (clean), pack sector/engine (repository pin d5c8380, identical tree)
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/wind-shadow-equivalence-2026-10-31 · Start commit: ca669772 (origin/main) · Date: 2026-10-31
```

## 1. Scope
Overnight run (Sector_Ops issue 24, step 4): prepare the 7-day shadow-equivalence run (configuration + verification script) so it can start when approved. **Not started:** no deploy, no IAM grant, no execution. Inspected: `brains/wind/runtime/main.py`, `sector_wind/brain/{publish,writer,artifact}.py`, `publisher/equivalence.py`, `brains/wind/deploy/deploy-job.sh`, the Wind rows of `PRODUCTION_CUTOVER_PLANS_V1.md`.

## 2. Findings
| ID | Finding | Status | Evidence |
|---|---|---|---|
| WS-1 | The equivalence evaluator and the shadow builder existed, but nothing in wind-hourly produced per-run evidence, and nothing aggregated a 7-day window | FAIL | `artifact.py` "NOT wired into wind-hourly"; no aggregation tool |

## 3. Changes
| Correction | Class | Files |
|---|---|---|
| Per-run evidence module (recording writer, readback, evaluator, digest-only create-only record, never raises) | requested; additive; OFF by default | `runtime/sector_wind/brain/shadow_equivalence.py` |
| Opt-in hook in wind-hourly after the legacy publish (flag + bucket both required; exit code unchanged) | requested; runtime change only behind the flag | `runtime/main.py` |
| Deploy flag pass-through (default off; binds nothing) | requested; the deploy itself stays gated | `deploy/deploy-job.sh` |
| 7-day config and window verifier | requested | `deploy/shadow-equivalence/` |
| Runbook | docs | `docs/WIND_SHADOW_EQUIVALENCE_RUN.md` |
| Tests | safe | `tests/test_shadow_equivalence.py` (10) |

## 3a. Standing checks
- Memory (BR-10/11/16, PL-13): knowledge loading untouched; Wind knowledge tests pass.
- Data (FD): no new database write; the readback is GET only; the evidence is object storage only, digest-only (SEC-01: no values leave the database).
- Security: one new grant is needed to start (create-only evidence prefix). It is listed, not made.
- Operations: with the flag off (the default), runtime behaviour is unchanged (tested statically and by the full Wind suite).

## 4. Verification
Wind suite 242 passed (232 before + 10 new); the full suite set is unchanged elsewhere; Kit V1 re-collected; engineering status regenerated.

## 5–9
Approvals to start: the IAM grant, the wind-hourly redeploy with the flag, and execution control for Wind (resuming is gated). Cortex gaps: none. Next step: owner approval of the three start actions once Water Clarity is done.
