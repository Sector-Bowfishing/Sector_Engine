# Session record: Lake Brain operator-truth validation v1 (pre-registered; runner ready; not run, not published)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with `git archive` into a scratch directory, so the briefing reports "uncommitted (no-git)"; content is the pinned commit), pack sector/engine. Date: 2026-11-23. Branch: `research/lake-validation-operator-truth-2026-11-23` off origin/main 8d421fe. Cloud session; only standing-approval actions (branch, commit, push, PR).

## Scope
Prepare the work that can lift the Lake Brain validation gate (`gate:validation`, cap 5.0 while `/validation/lake-brain` is `NOT_VALIDATED`): read what the rubric requires, pre-register a protocol before any fetch, write a read-only runner with fixture tests, define how a result would be published, and draft the Mac mini request. Not done: any fetch of level data, any run, any database or binding write, any publication, any rubric change.

## Findings
- F1: the rubric (`lake-brain-score-v1`) and the scorer (`score_lake`) read only `/validation/lake-brain.status`; `PARTIAL` already lifts the gate. Neither defines a truth source, sample size, metric or pass mark; the pre-registration defines them.
- F2: every Lake run writes `/validation/lake-brain` from `LakeBrainRunner.validationSummary`, hard-coded `NOT_VALIDATED`. A manual RTDB write would be overwritten; publishing needs an approved code change (prereg §8).
- F3 (decision for the owner): `LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md` (proposal, not adopted) defines `PARTIAL` from other evidence. Whether an operator-truth PASS may set `PARTIAL` (scope LB-04) is Michael's call.
- F4: only committed metadata may choose truth before a fetch, so every truth series is bound to the lake in some role. 106 of 289 lakes are excluded (same series only, no second series, or TVA primary whose 48 h feed cannot cover the window). No accepted lake has a CDEC or CO-OPS series. A discovery-first v2 (unbound operator series found, frozen, then run) would widen coverage of USGS- and NWPS-primary lakes.

## Verification
Offline suite `jobs/lake-brain/validation`: 90 passed (21 new). `build_sample.py --check` and `run_operator_truth.py --verify-only` pass. `research-check --repo .`: 85 findings, none in the new files (unchanged). `data-check`: 541, same as the main checkout. `ops-check`: 0. `worktree-check`: the new worktree is KEEP_ACTIVE/KEEP_UNIQUE until pushed and merged.

## Closeout (DEV-08)
[2026-11-23-lake-operator-truth-validation.closeout.md](2026-11-23-lake-operator-truth-validation.closeout.md). The research home is not present in this cloud session; the closeout is kept here and the Mac mini request adds the run to the `lake-brain` manifest.
