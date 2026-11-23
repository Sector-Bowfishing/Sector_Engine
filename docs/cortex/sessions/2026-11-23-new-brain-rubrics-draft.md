# Session record: draft score rubrics for Weather, Moon and Generation (not adopted)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with `git archive` into a scratch directory, so the briefing reports "uncommitted (no-git)"; the content is the pinned commit), pack sector/engine. Date: 2026-11-23. Branch: `draft/new-brain-rubrics-2026-11-23` off origin/main 8d421fe. Cloud session. Only actions covered by the standing approvals were taken: branch, commit, push the branch, open a PR. No merge.

## Scope
Michael asked for draft score rubrics for the three new Brains. Router row "Scoring" applies: scoring.md SC-01…SC-15; sources `jobs/brain-scores/`, `sector_brain_platform/scoring.py`, `docs/brains/scoring/`. Adopting a rubric and changing a score are gated (PROJECT.md §7), so both stay out of scope. Nothing here publishes or changes a score.

## Done
- `docs/brains/scoring/{weather,moon,generation}-score-v1.json`: status DRAFT, `adopted: false`.
  - Each has gates, dimensions classed per SC-09 and read only from published facts, status meanings tied to the plan's pre-registered validation, a worked example, and an adoption checklist.
  - Worked examples are labelled `TYPED_NOT_COMPUTED` (SC-11).
- `docs/brains/scoring/NEW_BRAIN_RUBRICS_DRAFT_2026-11-23.md`: the reasoning behind the choices and what the owner must approve.
- `jobs/brain-scores/test_draft_rubrics_not_loaded.py`: the drafts are DRAFT and unadopted; `compute()` scores exactly `UPSTREAM`; there are no frozen-score or improvement-registry entries for them; and no scorer, platform or orchestrator code names a draft.
- `verification/fixtures/scores/score_baseline.json` re-recorded. The re-record adds three rubric hashes and changes no score block and no existing hash. Without it, `score_baseline.py --check` fails on the added files.

## Findings
- **F1.** `score_improvements_v1.json` is read by the scorer's explanation step: `score_explanation.registry()` is called from `score_brains.py` on every write and is published in `/scores/{id}/explanation`. The task allowed entries only for a file no scorer reads, so no entries were added. The improvement text is kept in each draft's `improvementsDraft`.
- **F2.** The Weather runtime does not write `/validation/weather`, although its publication contract declares it. Until a Brain change writes it, the Weather validation dimension stays UNKNOWN.
- **F3.** MOON-VAL-001 has no pre-registration. The draft states a proxy (public sky-quality-meter records) and proposes criteria for the owner to decide on. It sets no thresholds.
- **F4.** The TVA half of decision D-G is not visible in Generation's published `sourceAccess`. The draft's gate also requires the approved release, which the plan sequences after D-G.
- **F5.** The real-response fixture gate reads repository evidence, not an RTDB fact. The owner must decide whether that is acceptable.

## Verification
- Test suites, all passing:
  - `jobs/brain-scores`: 41 passed
  - `jobs/brain_platform`: 1011 passed, 2 skipped
  - `jobs/brain-orchestrator`: 335 passed
  - `verification/integration/test_verification_gates.py`: 8 passed
  - `tools/architecture` and `tools/cortex_status`: 196 passed
- `score_baseline.py --check`: OK after the re-record.
- Cortex checks:
  - `data-check`: 541 findings, the same count as base; none in the new files.
  - `ops-check`: 0.
  - `research-check`: 0 information.
- Engineering-status digest regenerated; `--check` passes.

## Standing checks
- Memory checks: not applicable. No Brain runtime, knowledge loader, release, deploy configuration or data access changed.
- Data checks: run because the task touches score contracts. No new paths and no writers.
- Mission audit: not applicable. No `brain.json`, charter or output contract changed.

## Closeout (DEV-08)
- One worktree was created: `/home/claude/sector_engine_wt_rubrics`. It is kept until the PR merges; its commits are pushed.
- The extracted Cortex in the session scratchpad is disposable.
- No research data was created.
- `worktree-check` lists `/home/claude/se_wt_wind` as REMOVABLE_MERGED. It was not created by this session and was left untouched.
