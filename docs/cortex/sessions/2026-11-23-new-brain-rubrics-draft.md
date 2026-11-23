# Session record: draft score rubrics for Weather, Moon and Generation (not adopted)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with `git archive` into a scratch directory, so the briefing reports "uncommitted (no-git)"; the content is the pinned commit), pack sector/engine. Date: 2026-11-23. Branch: `draft/new-brain-rubrics-2026-11-23` off origin/main 8d421fe. Cloud session. Only actions covered by the standing approvals were taken: branch, commit, push the branch, open a PR. No merge.

## Scope
Michael asked for draft score rubrics for the three new Brains. Router row "Scoring" applies: scoring.md SC-01…SC-15; sources `jobs/brain-scores/`, `sector_brain_platform/scoring.py`, `docs/brains/scoring/`. Adopting a rubric and changing a score are gated (PROJECT.md §7), so both stay out of scope. Nothing here publishes or changes a score.

## Done
- `docs/brains/scoring/drafts/{weather,moon,generation}-score-v1.json` (moved to `drafts/` in the review follow-up below): status DRAFT, `adopted: false`.
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

## Review follow-up (same branch, after review of 31ec172)
The review found scorer output byte-identical, and made these content findings. All are fixed:
1. **PARTIAL no longer credits a FAILED criterion** (Weather, Generation; Moon aligned). PARTIAL now means some pre-registered criteria PASSED and the rest are NOT YET SCORED, with none FAILED. Any FAIL, and for Weather any INSUFFICIENT sample, gives NOT_VALIDATED. Each draft has a `newInThisDraft` note saying what the plans do not define. The doc now separates what comes from the plans from what is new.
2. **Adoption lists now include the Brain change for Moon and Generation.** Both runtimes write a constant NOT_VALIDATED to `/validation/{id}` on every run, and that has to change first.
3. **Moon UNSCORED is keyed on registry presence.** Moon nulls `lastSuccessfulRun` whenever any lake errors. Keeping the previous value is listed as an optional Brain change.
4. **Generation currency uses one population**, the fleet slots of supported lakes, clamped to [0, 10]. Registry `staleLakeCount` also counts errored lakes, so it is no longer used.
5. **Smaller fixes:**
   - Weather `fullStates` label now matches readiness CALIBRATION.
   - Weather `changeSignalEvaluable` now credits a `weatherChange.unknown` that is absent or empty.
   - Moon's coverage dimension is dropped: it is always 621/621. currentNight now has weight 30, and the illustration numbers are unchanged.
   - The not-loaded test now records every file opened and every directory listed while all scores, the Engine score and all explanations are computed. It asserts nothing under `drafts/` is opened and the scoring directory is never listed.
6. **Drafts moved to `docs/brains/scoring/drafts/`.**
   - `score_baseline.py` lists only top-level files, so the baseline fixture is restored to main's version and is no longer re-recorded.
   - `source_digest.py` covers the whole `docs/brains/scoring/` tree, so the engineering-status digest still moves with the drafts; it is regenerated.

Verification after the fixes, all passing:
- `jobs/brain-scores`: 42 passed
- `jobs/brain_platform`: 1011 passed, 2 skipped
- `jobs/brain-orchestrator`: 335 passed
- verification gates, `tools/architecture` and `tools/cortex_status`: 204 passed
- `score_baseline.py --check`: OK, with the fixture identical to main
- engineering-status digest `--check`: OK
