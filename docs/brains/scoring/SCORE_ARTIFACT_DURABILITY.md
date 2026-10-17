# Score artifact durability — why a legitimate score can silently revert, and how to stop it

Written 2026-10-14 after the Wind 3.1 → 3.3 reconciliation. Scope: documentation, a deterministic pre-deploy guard, a checklist. No redesign.

## 1. Current model
```
Brain's own scorer (e.g. Wind: sector_wind.scoreboard, frozen rubric v1)
   → GENERATED score block committed on the Brain's branch  (docs/brains/scoring/frozen-scores.json, one key per Brain)
      → baked into the brain-orchestrator IMAGE at deploy time  (jobs/brain-orchestrator/deploy-job.sh copies the file into stage/)
         → hourly orchestrator (:50 UTC) runs  score_brains.py --write --if-changed
            → canonical RTDB  /scores/{id}, /control/overview/brains/{id}.score, /scores/engine, activity score.changed
```
Brains whose score is *frozen outside this system* (Water Temp, Water Clarity) and Brains scored *by the platform from published facts* (Lake, Biological, Intelligence) have no such artifact problem for the second group (computed live every cycle). The first group — and any Brain whose scorer runs on its own cadence outside the orchestrator (Wind) — depends on the baked file.

## 2. The failure mode (observed 2026-10-13)
Wind's scorer legitimately moved 3.1 → 3.3 (dimension 8 grows with valid live days) and the generated block was committed on `feat/wind-brain-adoption`. The deployed orchestrator image still contained the old `frozen-scores.json`, and it republishes after any Brain state change (Wind changes hourly), so any one-off publish of 3.3 would have been **reverted to 3.1 within the hour**. Nothing failed; the orchestrator did exactly what its stale input said. A newer legitimate result is silently replaced by an older baked value.

Related finding in the same incident: the deployed lineage could not simply take the Wind branch — it lacks the content-aware publishing fix (`9f3cc8f5`) and its tests. Carrying a whole branch to obtain a score is itself a regression risk; **carry the generated block, not the branch.**

## 3. What was changed (small, deterministic)
1. **Guard** `jobs/brain-scores/check_score_artifacts.py` + manifest `docs/brains/scoring/score-artifact-sources.json` (Brain → `ref:path:key` of the Brain's generated block). It fails (exit 1) when a source ref holds a *newer* generated block whose value/version/uncapped/basis differ from the baked one; "baked newer than branch" is a warning (`AHEAD`); a source ref that cannot be read is reported `MISSING / NOT CHECKED`, never silently passed. Local git only, no network. Tests: `jobs/brain-scores/test_score_artifacts.py` (the Wind incident is a test case).
2. **Deploy hook:** `jobs/brain-orchestrator/deploy-job.sh` runs the guard before staging and refuses to deploy a stale artifact unless `ALLOW_STALE_SCORES=1` (a recorded decision).
3. **No-op rewrite fix:** the content comparison in `score_brains.py` treated an RTDB read-back (which drops empty objects) as a change, so frozen blocks (`scoreBreakdown: {}`) and the Engine block were rewritten on every cycle. `_content` now ignores None / `{}` / `[]`. Test added. The `score.changed` event rule is unchanged (only when displayed value / version / basis change).

## 4. Pre-deploy checklist (orchestrator, any branch)
1. `git fetch`; record `origin/main`, the shared branch tip, and the deployed `commit` label of `brain-orchestrator`.
2. Build from the **deployed lineage** (the branch containing the deployed commit), not an older base: `git merge-base --is-ancestor <deployed-commit> HEAD` must hold, and `git diff <deployed-commit> HEAD -- jobs/brain-orchestrator jobs/brain-scores jobs/brain_platform docs/brains/scoring` must show only what you intend.
3. Run `python3 jobs/brain-scores/check_score_artifacts.py` (the deploy script does too). For every STALE source, regenerate on the Brain's branch with its generator, then carry **only** the generated block: `git show <ref>:docs/brains/scoring/frozen-scores.json` → splice that key; assert every other key is byte-identical.
4. Run the tests: `jobs/brain_platform`, `jobs/brain-scores`, `jobs/brain-orchestrator`, `jobs/sector-intelligence-brain`, `brains/fish`.
5. Dry-run the real publisher (`score_brains.py --if-changed`, no `--write`): the change list must contain only the intended Brain(s). Unrelated displayed-value changes ⇒ stop and investigate.
6. Deploy; confirm the scheduler is unchanged (`50 * * * *`, UTC, ENABLED) and the job's cpu/memory/timeout/env equal the previous revision.
7. Verify publication **across at least one full orchestrator cycle** (the next :50/:51 run), not just immediately after deploy.

## 5. Options for a durable future workflow (not implemented — needs approval)
| | Idea | Pros | Cons |
|---|---|---|---|
| A | Reconcile generated artifacts explicitly before every orchestrator build (the checklist above, enforced by the guard) | what is now in place; cheap | human step; depends on remembering to fetch the Brain branch |
| B | Canonical generated score artifacts live in one authoritative shared branch (or a `scores/` build input) that every Brain's scorer commits to | one place to read; trivially auditable | cross-lane write permissions; merge ordering |
| C | The orchestrator reads generated score artifacts from a **durable runtime store** (e.g. a GCS object per Brain written by the Brain's scorer) instead of a baked file | no redeploy to refresh a score; removes the failure mode | new moving part; needs write ownership rules, staleness (`scoreUpdatedAt`) policy and a fallback |
| D | CI check: for each source in the manifest, fail the shared branch if its baked block is older than the Brain branch's | catches drift before a deploy | needs the Brain refs available in CI (network/clone) |
Recommendation: keep A+guard now; plan C (with the guard retained as the fallback check) as the proper fix, because it also lets the Wind score keep moving with live days without any redeploy.

## 6. Competing score truths (Wind registry vs canonical score)
`/brains/wind.scores.{windCertificationScore, bowfishingWindIntelligenceScore}` is written by `wind-hourly` (`sector_wind/brain/publish.py` lines 95 and 249) from `validation_evidence.json` baked into the **wind-hourly** image (frozen 2026-10-12: 3.1 / 5.4). `/scores/wind` and `/control/overview/brains/wind.score` are the canonical block. Two numbers will coexist until one owner is removed.
Principle: **the canonical score block owns score truth; runtime Brain state must not carry a competing certification number.**
Fix (documented, not applied — it needs the blocked Wind deployment):
1. *Wind (follow-up deploy, after the prerequisite branch resolves):* stop publishing `scores.windCertificationScore` (and the BWIS number) from `validation_evidence.json`; publish `scores.canonicalRef: "/scores/wind"` instead. BWIS is already in the canonical block (`secondary`).
2. *Ops (separate lane, no edit here):* `src/lib/brainScore.ts` (`windCertificationScore` first) and `src/components/windBrain.tsx` (lines ~208–215) should read the canonical block (`control.brains[id].score`, `/scores/{id}`), keeping the registry field only as a labelled fallback. The Overview tile already prefers `control.brains.wind.score`.
3. Until then the Wind page card shows the registry's 3.1 next to the canonical 3.3 (documented in the Wind handoff).

## 7. Superseded in part by the runtime guard (2026-10-14)
The recommended Option C is realised more simply: `/scores/{id}` in RTDB is the durable store and `publication.apply_guard` (wired into `score_brains.py`) holds any candidate older than what is published. The deploy-time guard above stays as the second layer. See `docs/brains/platform/SCORING_SEMANTICS.md` section 6.
