# Wind internal-validation deployment package (PREPARED; NOT DEPLOYED; needs Michael's explicit approval)

Purpose: get the internal validation code running BEFORE the 30-day prospective gate (≈ 2026-11-07), without losing a single prospective hour. Customer behavior, canonical score, main and shared infrastructure are untouched.

## What is in the package
Branch `deploy/wind-internal-validation` @ 343b1414 = shared lineage `feat/orchestrator-wind-score-durability` @ f7b6b066 (newest compatible: content-aware score publishing, stale-score guard, RTDB-key fix) + ONLY `jobs/wind-hourly` and `docs/brains/wind` from `feat/wind-brain-adoption` @ c6f6232e.
Carries: `reliability_gate.py` (automatic 30-day evaluation), reduced fleet writes, input-fingerprint skip, registry `canonicalRef` (no more stale 3.1), quick-observation / acceptance / customer-output code (inactive: nothing imports the customer output).

## Pre-deploy verification (all done 2026-10-14)
| Check | Result |
|---|---|
| Shared paths (`brain_platform`, `brain-scores`, `brain-orchestrator`, `docs/brains/scoring`) identical to the newest shared lineage | YES; no orchestrator rollback, stale-score guard files present, `check_score_artifacts.py` reports wind OK |
| Wind paths identical to `feat/wind-brain-adoption` | YES |
| Anything changed outside Wind paths | NONE |
| Vendored platform (copied into the image by the script) older than live? | No: newer. Live build `main@e6a5026f5d0f` -> package differs by two orchestrator-only bugfixes (`jobs.py`, `orchestrator.py`) that `wind-hourly` never calls |
| Tests from the deploy tree | wind 156 passed; shared (brain-scores + brain_platform + brain-orchestrator) 69 passed |
| Target correct | job `wind-hourly`, `us-central1`, scheduler `5 * * * *` UTC ENABLED (unchanged by the script when it already exists) |
| Settings the script would set vs live (gen 4) | identical: 1 task, retries 1, timeout 900, 1 cpu / 2Gi, SA `wind-hourly-job`, args `hourly --store gs://sector-wind-candidate/wind/v1`, same three env vars |
| Prospective ledger | `gs://sector-wind-candidate/wind/v1/ledger/` 187 objects, newest run 2026-10-14T18:08Z. The script never deletes objects; it only ensures bucket/IAM exist (idempotent). Archive keeps accruing during and after deploy |
| H2 | sealed; nothing in the package reads it |
| Previous image (recorded) | `us-central1-docker.pkg.dev/sector-9393c/cloud-run-source-deploy/wind-hourly@sha256:410e7c46c57b98f3f8ce9a2a3bee1f8694587d9122020ba375dd7126854a2746` (generation 4, label commit e6a5026f5d0f); confirmed to exist in Artifact Registry |

## Exact deploy command (run only after approval)
```bash
cd /Users/mcather/Desktop/Development/Sector_Engine-wind-deploy && MICHAEL_APPROVED_WIND_DEPLOY=yes bash jobs/wind-hourly/deploy-job.sh
```
(The build label will read `main@<commit>` because the script hardcodes `main@`; the commit is the deploy branch's.)

## Verify after the next :05 run
1. `gcloud run jobs executions list --job wind-hourly --region us-central1 --limit 2` -> new execution succeeded.
2. Log line `windbrain {"ok": true ...}` with `fleetPathsWritten` 16 after the first (full-refresh) run.
3. `/scores/wind` still 3.3 COMPUTED; registry `brains/wind/scores` now has `canonicalRef` and no `windCertificationScore`.
4. A new object appears in `ledger/runs/` for the hour (prospective record continuous).
## Rollback (documented; deploy not authorised so it has not been exercised; target image existence verified)
```bash
gcloud run jobs update wind-hourly --region us-central1 --image us-central1-docker.pkg.dev/sector-9393c/cloud-run-source-deploy/wind-hourly@sha256:410e7c46c57b98f3f8ce9a2a3bee1f8694587d9122020ba375dd7126854a2746
```
Scheduler, bucket and ledger are untouched by rollback.
