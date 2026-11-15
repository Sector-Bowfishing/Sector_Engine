# Session record: Engine dedicated runtime service account in deploy-engine (Sector_Ops #53)

Standards: Rehtac Cortex unavailable in this cloud session (`CORTEX_HOME` unset); repo CLAUDE.md rules followed directly, pack sector/engine, pin ecaef70. Date: 2026-11-08. Branch: `ci/engine-runtime-sa-2026-11-08` (off main 8487479, after #150).

## Scope
Follow-up requested by the conditions consolidation design session, carrying the owner decision of 2026-11-08: the Engine runs as its own
runtime account `sector-engine-runtime`, and the 11-10 deploy switches to it. The IAM (Sector_Ops `WIF_DEPLOY_IAM_V1.md` step 4E-R) is
applied by the owner. Nothing was deployed, no `gcloud` / production call was made, and no IAM was changed.

## Done
- `deploy-engine.yml`:
  - Reads `GCP_SA_ENGINE_RUNTIME` (secret or variable; never printed).
  - Both jobs stop before building or deploying when it is unset, unless `keep_current_identity` (new boolean input, default false) is checked.
  - Post-promote check: the serving revision's `spec.serviceAccountName` must equal the runtime account. A mismatch fails the job, which
    rolls back.
  - The step summary carries the manual `[remote-config]` log check.
- `deploy.sh` (IMAGE mode only):
  - `RUNTIME_SA` adds `--service-account`. A candidate not running as it is never promoted.
  - The email is never printed, and `RUNTIME_SA` is refused on the `--source` path. The default path is unchanged.
- `RemoteConfigREST.fetchDefaults`:
  - Before this change, nothing was logged on a refresh. Every failure fell back silently, so the smoke tests and `capture.py` passed
    with built-in weights.
  - It now logs ONE `[remote-config] refresh outcome=… status=…` line per template fetch, with status and counts only. The line is built
    by a pure function, with a Swift test.
- `DEPLOY_WORKFLOWS_V1.md`: runtime identity, the manual log check in the runbook, and the 4E-R grants in the permissions table.

## Verification
- `tools/deploy`: 44 passed (8 new). actionlint and shellcheck are clean on `deploy-engine.yml`.
- Swift: no toolchain in this container. CI `swift-tests` covers the new test.
- Certification digests re-recorded (separate commit).
