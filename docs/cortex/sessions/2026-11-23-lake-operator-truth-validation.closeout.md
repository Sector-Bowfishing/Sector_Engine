# Research Closeout — lake-brain — lake-operator-truth-validation-v1 (preparation)

```text
Standards: Rehtac Cortex 3.1.6 @ a785035, pack sector/engine
Task: Lake Brain validation gate ("Run a validation against operator truth (lifts the 5.0 cap)"), protocol lake-operator-truth-v1 · Folder: lake-brain · Date: 2026-11-23 · Manifest task status: OPEN (blocked: the run itself is for the Mac mini, 2026-11-24..30 UTC; the research home is not present in this cloud session)
```

## Preserved results
Superseded by v2 after review: `jobs/lake-brain/validation/operator_truth/PREREGISTRATION_v2.md` (sha256 in `PREREGISTRATION_v2.sha256`), frozen set `sample_v2.json`. The v1 record follows.
None yet. This session produced the pre-registration and the runner, which live in the Engine repository (not research data): `docs/brains/LAKE_BRAIN_OPERATOR_TRUTH_PREREGISTRATION.md` (sha256 7bc8d1df9f2bb319164a42791b5128ce3777953a0b4f6e59e40f1d9fbc5b07c0), `jobs/lake-brain/validation/operator_truth/sample_v1.json` (sha256 b6fe824b9f5aa9d0959014ed757c32110e53339db1e10d5806df22c39038684d), committed 469a15f before any fetch. The run's outputs are to go to `lake-brain/validation/operator-truth-v1-<run date>/` in the research home, retention ARCHIVAL (validation evidence).

## Manifests updated
None in this session: `research-path sector/engine lake-brain` resolves to a folder that does not exist in the cloud container (exists=False, manifest=False). The Mac mini request asks the helper to add the run folder to `lake-brain/manifest.json` with `collectionSha256` (sha256-tree-v1), source, provenance and retention.

## Candidate knowledge
None. A PASS verdict would only support a proposed `/validation/lake-brain` status `PARTIAL` (scope LB-04); publication stays an owner decision.

## Backups verified
None required (nothing retained outside Git).

## Deleted
Disposable only: the read-only Cortex extract and a base-tree extract under the session scratchpad.

## Worktrees
`/home/claude/se_wt_validation` (branch `research/lake-validation-operator-truth-2026-11-23`): kept until the PR merges; its commits are pushed.

## Blockers
The run (Mac mini, read-only, inside the pre-registered window). Publishing any result, and whether operator-truth agreement may define `PARTIAL`, are owner decisions.
