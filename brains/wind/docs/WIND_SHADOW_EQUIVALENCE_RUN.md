# Wind 7-day shadow equivalence: runbook (PREPARED 2026-10-31, NOT STARTED)

The Wind cutover (step 2 of `cutover_order.json`) needs at least 7 days of evidence that the central Publisher's plan equals what the legacy `wind-hourly` writer actually stored. This prepares that run so it can start the moment it is approved. Nothing here has been deployed or run. Identity and bucket names are in the private tracker, not here.

## What runs (per wind-hourly execution, only when the flag is deployed)
1. `RecordingWriter` wraps the real writer and copies each PATCH after it was sent. The legacy write itself does not change.
2. The existing SHADOW builder (`sector_wind/brain/artifact.py`) seals those patches; the Publisher renders its plan in DRY_RUN (nothing persisted).
3. The stored value of every written key is read back (GET only) and the Publisher's equivalence evaluator (`wind-shadow-equivalence-v1`) compares stored values with the plan.
4. One **digest-only** evidence record (`wind-shadow-equivalence-run-v1`) is created under `exports/shadow-equivalence/wind/` in the evidence bucket. It holds paths, difference classes and SHA-256 digests, never values.

It never raises into the job and never changes the exit code. A failure is an `ERROR` record, which fails the window.

## Pass criteria (`deploy/shadow-equivalence/shadow-equivalence-7day.json`)
At least 168 continuous hours; at least 90 % of hours covered; no gap over 6 h; every run `EQUIVALENT_WITH_EXPECTED_DIFFS` (or `NO_LEGACY_WRITE`); zero `NOT_EQUIVALENT`; zero `ERROR`. The only open compatibility rules allowed are `health-jobs-wind-hourly` and `health-brains-wind-process`, which the Orchestrator must provide at cutover.

## To start (each line needs the owner's approval)
1. Grant the Wind job identity create-only on `exports/shadow-equivalence/wind/` of the private artifact bucket (IAM change).
2. Redeploy wind-hourly with `MICHAEL_APPROVED_WIND_DEPLOY=yes WIND_SHADOW_EQUIVALENCE=on WIND_SHADOW_EVIDENCE_BUCKET=<bucket> brains/wind/deploy/deploy-job.sh`.
3. Executions keep coming only from brain-orchestrator while `/control/executionControlV1` is ENABLED for Wind. With the control PAUSED, no evidence accumulates; resuming is its own gated decision.
4. Record the approval reference in `shadow-equivalence-7day.json` (`approvalRef`, `status: RUNNING`).

## To verify
`python brains/wind/deploy/shadow-equivalence/verify_shadow_equivalence.py --bucket <bucket>` (read-only identity), or `--evidence DIR` on a downloaded copy. It exits 0 only on `PASS`; otherwise it prints `FAIL` (with the runs) or `INSUFFICIENT` (with what is short).

## To stop / roll back
Redeploy without the flag (`WIND_SHADOW_EQUIVALENCE=off`, the default). Evidence records stay (create-only; deleting them is a separate gated action).
