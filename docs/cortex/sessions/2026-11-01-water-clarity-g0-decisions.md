Standards: Rehtac Cortex 3.1.1 (pin per CLAUDE.md)

# Session record: Water Clarity G0 owner decisions 1 and 2 (Sector_Ops #40)

Owner decisions are recorded on Sector_Ops #40 (2026-11-01). Private research detail stays in the private research workspace and its backup,
not in this repository.

| Decision | What was done |
|---|---|
| 1. Record R3.1 as CANDIDATE / NOT_DEPLOYED with the G0 blocker (records-only) | The `water-clarity` blocker text in `docs/brains/scoring/frozen-scores.json` now reads "no Sector-domain evidence: no admitted matchups at the home lakes; reservoir bars failed". `nextScoreOpportunity` and the matching score-improvement entry no longer say "approve and deploy R3.1". The gate id (`deployment`), the value (8.0 / 10), the scale, the basis, the score version, `scoreUpdatedAt` and `appliesTo` are all unchanged, and the 8.0 stays labelled a research score. |
| 2. Baseline-first production clarity plan (scoping only) | A plan was written to the private research workspace for the owner to read. Nothing was run, built, scored or deployed. |

Pinned hashes that intentionally detect any change to this block were re-recorded in the same commit:
- the score baseline (`verification/integration/score_baseline.py --update`)
- the Water Clarity certification test's block hash
- the generated engineering status digests (`collect_certification.py`, then `build_engineering_status.py --write`)

**Verification:** every CI suite passed locally: foundation, platform, all eight Brains, score baseline, engineering status and release manifests.

**What does not change yet:** the live `/scores/water-clarity` text. It changes only when the orchestrator is next deployed, which is a gated
step that has not been done. Nothing was deployed, run in the cloud or written to any database, and there was no IAM, rules, schedule or
score-value change.
