# Session record: draft score rubrics for Weather, Moon and Generation (not adopted)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with `git archive` into a scratch directory, so the briefing reports "uncommitted (no-git)"; the content is the pinned commit), pack sector/engine. Date: 2026-11-23. Branch: `draft/new-brain-rubrics-2026-11-23` off origin/main 8d421fe. Cloud session. Only actions covered by the standing approvals were taken: branch, commit, push the branch, open a PR. No merge.

## Scope
Michael asked for draft score rubrics for the three new Brains. Router row "Scoring" applies: scoring.md SC-01…SC-15; sources `jobs/brain-scores/`, `sector_brain_platform/scoring.py`, `docs/brains/scoring/`. Adopting a rubric and changing a score are gated (PROJECT.md §7), so both stay out of scope. Nothing here publishes or changes a score.

## Done
- `docs/brains/scoring/drafts/{weather,moon,generation}-score-v1.json` (moved to `drafts/` in the review follow-up below): status DRAFT, `adopted: false`.
  - Each has gates, dimensions classed per SC-09 and read only from published facts, status meanings tied to the plan's pre-registered validation, a worked example, and an adoption checklist.
  - Worked examples are labelled `TYPED_NOT_COMPUTED` (SC-11).
- `docs/brains/scoring/drafts/NEW_BRAIN_RUBRICS_DRAFT_2026-11-23.md` (now under `drafts/`): the reasoning behind the choices and what the owner must approve.
- `jobs/brain-scores/test_draft_rubrics_not_loaded.py` (current state, after the second review): six tests. (1) The drafts are DRAFT, unadopted, under `drafts/`, with the bowfishing fields. (2) `compute()` scores exactly `UPSTREAM`. (3) There are no frozen-score or improvement-registry entries for them. (4) A static scan of scorer, platform, orchestrator, workflow and deploy files (code and config) finds no draft name and no `scoring/drafts` path. (5) A runtime recording of compute, the Engine score and the explanations shows nothing under `drafts/` is opened and the scoring directory is never listed. (6) The same recording over `score_brains.main()` (dry run, which calls `fetch_facts`) shows the Brains are not scored even when their registries exist.
- `verification/fixtures/scores/score_baseline.json`: re-recorded in the first commit, then REVERTED to main's version when the drafts moved to `drafts/` (the baseline lists only top-level files). It is identical to main.

## Findings
- **F1.** `score_improvements_v1.json` is read by the scorer's explanation step: `score_explanation.registry()` is called from `score_brains.py` on every write and is published in `/scores/{id}/explanation`. The task allowed entries only for a file no scorer reads, so no entries were added. The improvement text is kept in each draft's `improvementsDraft`.
- **F2.** The Weather runtime does not write `/validation/weather`, although its publication contract declares it. Until a Brain change writes it, the Weather validation dimension stays UNKNOWN.
- **F3.** MOON-VAL-001 has no pre-registration. After the alignment pass the draft proposes a practical check: one site, about 12 nights, a sky-quality meter or a phone light meter pointed up, class order plus cloudy versus clear. The check is written down before any reading. The earlier multi-site statistical proposal was dropped. The draft sets no threshold the owner has not seen.
- **F4.** The TVA half of decision D-G is not visible in Generation's published `sourceAccess`. The draft's gate also requires the approved release, which the plan sequences after D-G.
- **F5.** The real-response fixture gate reads repository evidence, not an RTDB fact. The owner must decide whether that is acceptable.

## Verification (initial commit 31ec172; later runs are in the sections below)
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

## Bowfishing alignment pass (owner condition for merging as drafts)
Michael approved merging the drafts as drafts, not adopted, on condition they serve bowfishing decisions rather than research volume.
- Each draft and the explainer doc open with a plain "why this matters for bowfishing" paragraph, and every dimension has a one-sentence `why`.
- Every draft has an `unknownPolicy`, following the owner rule that nothing should show unknown. Unknown outputs earn 0 and stay in every denominator. Estimates are never a way out, because validation fails invented values.
- **Weather:** the 3 h pressure trend drops 15 → 5, since there is no evidence pressure moves target species. A new `rainReadout` (20) credits rain in the last hour plus rain expected in the next 6 h; a null in either counts against. Coverage and fullStates each go from 20 to 15. The change signal stays at 15.
- **Moon:** validation is proportionate. The proxy is one site, about 12 nights, read with a sky-quality meter or a phone light meter pointed up. The proposed check is class order plus cloudy-versus-clear. This replaces the multi-site statistical proposal. Weights are now validation 35, cloud 35 and current night 30.
- **Generation:** a new `releasingNow` (30) asks whether the dam is releasing or generating now, with UNKNOWN counting against and every published slot in the denominator. Schedule ("when it changes") rises to 25. The `measuredRelease` dimension is removed, since flow detail is secondary. Dam coverage drops to 10 and currency to 5.
- The not-loaded test also requires `whyForBowfishing`, `unknownPolicy` and a `why` on every dimension.

## Second review follow-up (after review of 466aeb7, NOT CLEAN)
- **HIGH: Weather denominators.** Every per-lake share (rainReadout, fullStates, changeSignalEvaluable, pressureTrend) now divides by `/brains/weather.directoryLakeCount`. A BLOCKED, never-computed or errored lake has no state and earns 0. The policy was right; the formulas did not follow it, and now they do.
- **HIGH: Generation denominators.** releasingNow and currency now divide by all 401 catalog dam lakes, with unbound, permission-required and errored dams earning 0. The worked examples are recomputed: 17 lakes give 1.3 (only if TVA access were permitted), and 150 lakes plus full validation give 7.3, no longer 9.5.
- **MEDIUM: Generation scheduleCoverage.** The numerator and denominator are the same 39 schedule-posting lakes (TVA, TVA_CUMBERLAND, SWPA_USACE), and the clamp that hid the mismatch is gone. The review reported that TVA's robots.txt disallows all automated access. TVA and Cumberland schedules (both read through the TVA API) are therefore unobtainable today and earn 0. SWPA waits on its access check. No proxy is used. A new `accessNote` records the consequence for the 17 lakes "readable today". `source_access.json` is unchanged, because that belongs to D-G.
- **LOW, Moon:** cloudIntegration divides by the directory minus NO_NIGHT lakes, so errored lakes count 0. currentNight is now the number of lakes with a night state over the directory.
- **LOW, records:**
  - This record's Done and Findings sections are updated: the explainer location, the test contents, the baseline revert, and the F3 one-site check.
  - The explainer and `unknownPolicy` now both say an unknown lowers completeness and counts as 0, never excluded.
- **LOW, test:**
  - The static scan now covers config files (json, yml, sh, ini, toml, txt, Dockerfiles) in the scorer, platform and orchestrator folders, plus `.github/workflows`, `deploy/`, `deploy.sh` and the root Dockerfile. It also looks for `scoring/drafts` path globs.
  - A new runtime test runs `score_brains.main()` as a dry run, through `fetch_facts`, over a store in which all three Brains have published registries and VALIDATED nodes. None is scored, nothing is written, and nothing under `drafts/` is read.
- **Certification is re-collected, not only re-digested.** `collect_certification.py` re-runs every registered Brain's Cert Kit V1 suite (11 Brains, failing: none) and records the live source digest. The certification `sourceDigest`, the status report's `source.sourceDigest`, its `certificationDigest` and the live `source_digest()` are all equal (sha256:f4826c7d…, before the session-record edit, which is outside the digest roots). The same sequence ran before each earlier push.

Verification, all passing:
- `jobs/brain-scores`: 43 passed
- `jobs/brain_platform`: 1011 passed, 2 skipped
- `jobs/brain-orchestrator`: 339 passed
- verification gates, `tools/architecture` and `tools/cortex_status`: 204 passed
- `score_baseline.py --check`: OK, and the fixture is byte-identical to main
- engineering-status digest `--check`: OK

## Third review follow-up (after review of 23c2fd0, NOT CLEAN)
Only the rubric definitions changed. No Brain runtime code was touched.
- **MEDIUM, freshness at scoring time.** Every per-lake fact in all three drafts now counts only if the lake's state is current when the scorer runs. This is read from a timestamp already in the published state, so no runtime change is needed:
  - **Generation:** `freshness.freshUntil` later than scoring time. A dam that errors after an earlier publish keeps its old slot and state (`publish.py` rewrites the slot only for a lake published this run), and its state now expires to 0. `releasingNow` and `damCoverage` read the state, not the slot. The `currency` dimension is folded into `damCoverage` (now 15), because it measured the same thing once freshness applies everywhere. Examples recomputed: 1.4 (only if TVA were permitted) and 7.4.
  - **Weather:** `freshness.freshUntil` later than scoring time for every per-lake dimension, coverage included. `fullStates` is now per-lake (kind observation, nothing missing, fresh), not the last run's `readinessCounts`.
- **LOW items:**
  - Generation: removed "17 readable today / covered". Nothing is published today, and the 17 are unreadable if the TVA disallow is confirmed.
  - Weather validation "absent" now reads "scores 0 and lowers completeness". Moon and Generation gates in the explainer now say "or absent".
  - `asOf` updated to origin/main f5460aa.
- **LOW, Moon currentNight and cloudIntegration:** both now read the written `/lakes/{k}/states/moon` whose `date` is tonight at scoring time, not the registry `breakdowns`. `publish.py` counts a lake's basis before writing its state, so a failed write would still be counted. The draft notes that ordering and explains why reading the written state makes a runtime fix unnecessary for this definition.
- The not-loaded test also requires `freshnessAtScoringTime` in each draft.

Round-3 verification, run at 60b6070, all passing:
- `jobs/brain-scores`: 43 passed
- `jobs/brain_platform`: 1011 passed, 2 skipped
- `jobs/brain-orchestrator`: 339 passed
- verification gates, `tools/architecture` and `tools/cortex_status`: 204 passed
- `score_baseline.py --check`: OK, and the fixture is byte-identical to main
- Certification re-collected (all 11 Brains' Cert Kit suites, none failing)
- Engineering-status `--check`: OK
- No diff against main under `brains/` or `jobs/brain_platform/`
- CI green (7/7)

## Fourth review follow-up (after review of 60b6070, NOT CLEAN)
Only the rubric definitions changed. No Brain runtime code was touched.
- **MEDIUM, Moon "tonight".** "Tonight" is now `moon_brain.night.evening_date(lat, lon, scoring time)`, with its sunrise rollover. That is the noon-to-noon span containing scoring time, moved to the next evening once that night's sunrise has passed. It replaces the bare noon-to-noon wording in `cloudIntegration`, `currentNight`, the scope and the freshness block.
- **MEDIUM, Generation schedule.** `scheduleCoverage` now also requires `schedule.scheduleCoversUntil` (published by `assess.py`) to be later than scoring time, so an ended schedule earns 0.
- **LOW items:**
  - The explainer names the OBSERVED / SCHEDULE_ONLY kind restriction for `damCoverage`.
  - The Generation example now reads "0.42 x 30 = 12.7".
  - The Moon scope says polar-day lakes are removed from the cloud denominator only, matching the explainer.
  - This record now holds the round-3 and round-4 verification runs.

Round-4 verification, run before the push, all passing:
- `jobs/brain-scores`: 43 passed
- `jobs/brain_platform`: 1011 passed, 2 skipped
- `jobs/brain-orchestrator`: 339 passed
- verification gates, `tools/architecture` and `tools/cortex_status`: 204 passed
- `score_baseline.py --check`: OK, and the fixture is byte-identical to main
- Certification re-collected (all 11 Brains' Cert Kit suites, none failing)
- Engineering-status `--check`: OK
- No diff against main under `brains/` or `jobs/brain_platform/`

The current digest is sha256:fb0eea6260ddfcfa3f4002b3981649b1f9808be358dfbeefe1be6345532de0b8. The certification `sourceDigest`, the status report's `source.sourceDigest`, its `certificationDigest` and the live `source_digest()` all equal it. This session record is outside the digest roots.
