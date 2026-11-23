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

## Review follow-up: v2 pre-registration (same branch, before 2026-11-24T00:00Z, no data fetched)
The independent review of PR #243 @ fc9982f was NOT CLEAN: v1 would mostly measure its own selection. v1 is superseded (banner on its protocol; rule
and sample kept; runner in 38272fc). `lake-operator-truth-v2` (`jobs/lake-brain/validation/operator_truth/PREREGISTRATION_v2.md`, beside the runner so
no legacy code references `docs/`, which fixed the architecture invariant 8 CI failure):
- SAME_SERIES across district/division offices and for -raw/-rev of one feed; new SAME_SENSOR_SUSPECTED (other version/interval/type at one CWMS
  location; CWMS `…USGS-*` or NWS-id decodes vs USGS; every truth of an NWPS-primary lake), report-only.
- Verdict truths must be history series (fallback live series were pre-filtered by dry-run check (b)), offset 0, no known datum mismatch, and a2w
  only with its CWMS office evidenced in committed metadata (A1; 32 a2w lakes not evaluable).
- Fleet criteria must hold for the whole verdict set and for the independent cross-agency subset on its own; V1 failing on either is INCONCLUSIVE.
- Brain-value age reported per night and gated at the Brain's staleness limit (cadence + lag).
- Integrity chain: lock file → protocol → pinned sha256 of the set, the rule and the runner; the output records the runner sha256 and commit.
- Result: 7 verdict-eligible lakes (4 independent) of 289. **A fleet verdict is not reachable under v2** (V1 needs 45); stated in the protocol before
  data. Next: a discovery-first v3 (unbound operator reports, identity-checked, frozen before values).
Verification: `jobs/lake-brain/validation` 92 passed (22 v2 tests); `--verify-only` and `build_sample_v2.py --check` pass; architecture
`test_foundation.py` 94 passed and the depth kit P18 gate passes locally.
