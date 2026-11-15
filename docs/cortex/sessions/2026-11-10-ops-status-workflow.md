# Session record: read-only `ops-status.yml` and the `deploy-engine.yml` cycle preflight (Sector_Engine#160)

Standards: Rehtac Cortex unavailable in this cloud session (`CORTEX_HOME` unset); repo CLAUDE.md rules followed directly, pack sector/engine, pin ecaef70. Date: 2026-11-10. Branch: `cortex/ops-status-workflow-2026-11-10` (off main fa8f4f9). Session: scheduled approved-work runner.

## Scope
Owner request (Michael, 2026-11-10 17:24Z) on Sector_Ops #51: build Sector_Engine#160 and merge it under the standing approvals; post the
one-paste IAM block on #51; do not apply IAM.

## Done
- `tools/deploy/ops_status.py` (stdlib only): `report` and `gate`. GET requests only, plus the Logging `entries:list` query. Leak-free output.
- `.github/workflows/ops-status.yml`: `workflow_dispatch` and `workflow_call`; WIF as `GCP_SA_OPS_STATUS`; no dependency install in the
  job that holds the token.
- `deploy-engine.yml`: a `preflight` job calls `ops-status.yml` with `gate: true` before `build`; `skip_cycle_preflight` (default false) is
  the owner-only bypass. `deploy` now states its condition explicitly so a skipped preflight does not skip it.
- `DEPLOY_WORKFLOWS_V1.md` §3a, §4 (grants S) and §5; `tools/deploy/tests/test_ops_status.py` (16 tests).
- Certification digest re-recorded (`.github/workflows/` is a digest root): `failing: none`; engineering status rewritten and `--check` OK.

## Decisions (reversible)
- **One trust binding:** `deploy-engine.yml` calls `ops-status.yml` as a reusable workflow, whose `job_workflow_ref` is `ops-status.yml`,
  so the status account trusts one workflow file. The deployer account gets no read roles.
- **The gate refuses when unsure:** an execution whose container args are not visible is never assumed real.
- **Watchdog latch:** object read conditioned on the one latch object, not the whole artifact bucket.
- **Execution control (RTDB) is optional:** the only RTDB read role is project-wide over every instance, including the customer
  database, and the gate does not need it.
- **Behaviour change:** until the status account exists, `deploy-engine.yml` refuses at the preflight unless `skip_cycle_preflight` is set.

## Unverified until the first run
- That Cloud Run v2 executions expose `template.containers[].args` with the `--dry-run` override. Review finding: if they showed the job's
  normal args instead, a dry run would look real. Hardened: a cycle counts as real only with no `--dry-run` **and** a `createTime` at the
  schedule minute (:50/:51 UTC); anything else is `manual` and never passes. If `args` are absent entirely, the gate refuses (`unknown`).
- That the RTDB read accepts the scoped access token (optional path only).

## Verification
- `tools/deploy`: 63 passed. Independent review: CLEAN (2 MEDIUM, both addressed: dry-run hardening above; the secrets-vs-variables note is in the IAM block on #51). `tools/architecture`: 187 passed. `verification`: 48 passed, 3 skipped.
- Nothing ran against Google Cloud or the database. No deploy, IAM, rules or flag change.
