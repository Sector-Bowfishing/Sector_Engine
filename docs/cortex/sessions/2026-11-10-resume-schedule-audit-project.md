# Session record: `resume-orchestrator.sh` step 2 passes the project to the schedule audit

Standards: Rehtac Cortex unavailable in this cloud session (`CORTEX_HOME` unset); repo CLAUDE.md rules followed directly, pack sector/engine, pin ecaef70. Date: 2026-11-10. Branch: `cortex/resume-schedule-audit-project-2026-11-10` (off main 475975f). Session: scheduled approved-work runner.

## Scope
Owner action (Michael, 2026-11-10 ~05:35Z) on Sector_Ops #51: in a fresh Cloud Shell with no default project, step 2 of
`tools/ops/resume-orchestrator.sh` failed (`gcloud.scheduler.jobs.list ... Failed to find attribute [project]`), because
`jobs/brain-orchestrator/check_preproduction_schedules.py` calls `gcloud scheduler jobs list` without `--project`. Every other
gcloud call in the script already passes `--project`/`--location`.

## Done
- `tools/ops/resume-orchestrator.sh` step 2 runs the audit with `CLOUDSDK_CORE_PROJECT="$PROJECT_ID" REGION="$REGION"`, so the
  audit's `gcloud scheduler jobs list` uses the script's project and region (gcloud reads `CLOUDSDK_CORE_PROJECT` as `--project`).

## Decision (reversible)
- Fixed at the call site, not inside `check_preproduction_schedules.py`: `jobs/brain-orchestrator/` is in the certification
  `source_digest` roots and in the orchestrator image, so a change there would move the certification digest and the image for a
  tooling-only fix. The audit's own behaviour, output and exit codes are unchanged.

## Verification
- `bash -n` clean.
- With a stub `gcloud` that refuses `scheduler jobs list` without a project: the old call exits 2 with
  `Failed to find attribute [project]`; the new call gets the job list and runs the audit.
- Nothing ran against Google Cloud or the database. No deploy, IAM, rules or flag change.
