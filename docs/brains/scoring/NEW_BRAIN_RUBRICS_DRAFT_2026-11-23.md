# Draft score rubrics: Weather, Moon and Night Light, Generation (2026-11-23)

**Status: DRAFT, not adopted.** Michael asked for these on 2026-11-23. Adopting a rubric, or publishing or changing a score, is his approval (Cortex `sector/engine` PROJECT.md §7). This change publishes nothing and changes no live score.

| Brain | Draft rubric | Score today |
|---|---|---|
| Weather (`brains/weather`) | [`weather-score-v1.json`](weather-score-v1.json) | **UNSCORED**: nothing published |
| Moon and Night Light (`brains/moon`) | [`moon-score-v1.json`](moon-score-v1.json) | **UNSCORED**: nothing published |
| Generation (`brains/generation`) | [`generation-score-v1.json`](generation-score-v1.json) | **UNSCORED**: nothing published |

## What keeps them inert

- No scorer reads them. `jobs/brain-scores/score_brains.py` `UPSTREAM` is unchanged, and `sector_brain_platform/scoring.py` has no function for these Brains. The scorer does not discover rubric files by listing this directory; each rubric it applies is named in code.
- `jobs/brain-scores/test_draft_rubrics_not_loaded.py` checks four things: each draft is `DRAFT` and unadopted; `compute()` returns exactly `UPSTREAM`; no frozen score and no improvement-registry entry exist for these Brains; and no scorer, platform or orchestrator code names a draft `scoreVersion`.
- **The improvement registry was not touched.** `score_improvements_v1.json` says it is "never an input to any score", and it does not change any score value. It is still read by the scorer: `score_explanation.registry()` loads it, `score_brains.py` calls that during every write, and it is copied into `/scores/{id}/explanation`. That fails the condition for adding entries, so each draft carries its improvement text in `improvementsDraft`, ready to copy when the rubric is adopted.
- `verification/fixtures/scores/score_baseline.json` was re-recorded. The baseline hashes every JSON file in this directory, so the three new files would otherwise fail `score_baseline.py --check`. The re-record adds three rubric hashes. No score block, value or existing hash changed. It also means any later edit to a draft shows up as drift.

## Choices common to all three

- **Same shape as the computed rubrics** (`lake-brain-score-v1.json`), so adoption can follow the existing scoring pattern: a 0–10 linear weighted sum with weights totalling 100, `UNKNOWN` dimensions contributing 0 and excluded from completeness, and gates that cap and never add. Each draft also has the following fields:
  - a `class` on every dimension (Cortex scoring.md SC-09). There is no ENG or VOL dimension.
  - `movableByPackagingOnly`
  - `unscoredWhen`
  - `validationStatusMeaning`
  - a `workedExample`
  - an `adoption` checklist
- **UNSCORED is not 0.** A Brain that has never published (no registry, no `lastSuccessfulRun`) gets no score block. All three are in that state today: each is PARKED, has no executor, job or execution-control entry, and `run.py --write` refuses.
- **Only published facts.** Every dimension reads one of three things: a registry child the Brain writes (`supportedLakeCount`, `readinessCounts`, `breakdowns`, `staleLakeCount`, `knowledgeRelease`, `sourceAccess`, `fleet`), a state field in its schema, or `/validation/{id}.status`. There are two declared exceptions:
  - Weather's `/validation/weather` is in its publication contract, but the runtime does not write it yet, so that dimension stays UNKNOWN until it does.
  - Generation's real-response fixture gate reads repository evidence. Its lead asked for this gate (see below).
- **Validation follows each plan's pre-registration.** The rubrics do not restate or set thresholds. They define what `PARTIAL` and `VALIDATED` must mean in terms of the plan's criteria, and they leave the status to the Brain's validation record, never to the scorer.
  - NOT_VALIDATED caps the score at 5.0, as Lake does.
  - PARTIAL caps it at 7.0.
- **Common gates.** Health FAILED/UNKNOWN caps at 2.0. Coverage below 10 % caps at 3.0, as Lake does.
- **No permanently empty dimensions.** There are none for the pressure forecast (WX-003) or per-lake skyglow (MOON-INP-002). They would be 0 forever (SC-09) until the Brain publishes a fact for them.
- **Worked examples are hand arithmetic** (`TYPED_NOT_COMPUTED`, SC-11), labelled non-authoritative. Assumed shares are marked as assumptions.

## Weather (`weather-score-v1`)

**Gates:**
- health → 2.0
- coverage below 10 % → 3.0
- validation NOT_VALIDATED or absent → 5.0
- validation PARTIAL → 7.0

PARTIAL means plan §5.1 (fidelity) passed and one of §5.2 or §5.3 passed. VALIDATED means all three passed, with INSUFFICIENT never counting as a pass. A §5.1 fidelity failure is always NOT_VALIDATED.

**Points:**

| Dimension | Weight | What earns points |
|---|---|---|
| validation | 30 | |
| coverage | 20 | directory ladder |
| fullStates | 20 | share of supported lakes at readiness CALIBRATION: fresh observation, all four tiles, not stale |
| changeSignalEvaluable | 15 | share of states with no unevaluable change rule |
| pressureTrend | 15 | share of states with a 3 h trend |

**Today:** UNSCORED. No dry-run shares have been recorded yet, so the draft gives no illustrative number.

**Lifted by:** enablement, then plan §5.1 and §5.2 (about 30 days, which reaches PARTIAL), then §5.3 (60 days).

## Moon and Night Light (`moon-score-v1`)

**Gates:**
- health → 2.0
- knowledge release not APPROVED → 2.0. This is a guard; the writer already refuses without an approved release.
- cloud included on less than 50 % of night lakes → 4.0. On those nights the class is only a clear-sky bound.
- validation NOT_VALIDATED → 5.0
- validation PARTIAL → 7.0

**Points:**

| Dimension | Weight | What earns points |
|---|---|---|
| validation (MOON-VAL-001) | 40 | |
| cloudIntegration | 30 | `breakdowns.basis.MOON_AND_CLOUD` share |
| coverage | 15 | marked movable by packaging alone, since the astronomy computes every lake |
| currentNight | 15 | |

The USNO cross-check is real accuracy evidence. It earns nothing here because the Brain does not publish it as a measurement.

**MOON-VAL-001 has no pre-registration yet.** The draft does three things about that:
- It states the proxy: public sky-quality-meter zenith sky-brightness records near fleet lakes stand in for measured on-water lux. Boat readings are optional.
- It requires a pre-registration committed before any data is read.
- It proposes, for Michael to accept, change or reject, a Spearman ρ ≥ 0.6 over at least 60 site-nights at 3 or more sites, plus monotone class medians. This is a proposal only.

**Today:** UNSCORED.

**Illustration:** the recorded 2026-11-22 dry run (621 lakes, all MOON_ONLY) would give 3.0, earned only by coverage and currency. With Weather live it would reach 5.0 (uncapped 5.7), and 9.7 once validated, under an assumed 90 % cloud share.

## Generation (`generation-score-v1`)

Coverage uses the **401 dam lakes** as its denominator, not the 621-lake directory.

**Gates:**
- health → 2.0
- release not APPROVED (G-2) → 2.0
- **sourceAccess (D-G)** → 3.0. Fires when a provider is ACCESS_CHECK_REQUIRED (SWPA today) or the release is unapproved.
- **realResponseFixtures** → 3.0. Fires until each serving provider has a recorded live response. Today only hand-built fixtures exist.
- dam coverage below 10 % → 3.0. Today 17 of 401 lakes are covered (4.2 %).
- validation NOT_VALIDATED → 5.0
- validation PARTIAL → 7.0

**Points:**

| Dimension | Weight | What earns points |
|---|---|---|
| validation | 30 | PARTIAL = plan §5 metrics 3–5 pass. VALIDATED = all five pass over the pre-registered week. An invented value is always NOT_VALIDATED. |
| damCoverage | 25 | |
| measuredRelease | 20 | OBSERVED share |
| scheduleCoverage | 15 | Denominator is the TVA, TVA_CUMBERLAND and SWPA_USACE lakes (where operators post schedules), so binding measured-only lakes never lowers it |
| currency | 10 | |

**Today:** UNSCORED.

**Illustration:** the 17 readable lakes, if published and fully current, would give uncapped 3.9. That is capped to 2.0 while the release is unapproved and to 3.0 afterwards.

D-I (the cross-Brain TVA read budget) blocks enablement, not the score.

**Known limit:** the TVA half of D-G is not in any published fact. The `openCheck` note stays in `source_access.json`, so the gate also requires the approved release, which the plan sequences after D-G.

## What Michael must approve to adopt one (per Brain)

1. **The rubric.** Weights, gates, caps and status meanings, as written or amended. A new rubric is approval-gated.
2. **Moon only.** Accept or replace the proxy and the proposed MOON-VAL-001 criteria, then commit the pre-registration before any data is read.
3. **Generation only.** Whether the fixture gate may read repository evidence. Every other fact in these drafts is a published RTDB fact.
4. **Weather only.** A Brain change so it writes `/validation/weather` with these status meanings.
5. **Cortex.** A Cortex maintenance session (not this repository) to register the Brain and `/scores/{id}`. None of the three is a Cortex target Brain (BA-01; CG-3.1-19, CG-3.1-20).
6. **The scorer PR.** It adds:
   - a `score_<brain>()` function
   - the facts in `fetch_facts`
   - the Brain in `UPSTREAM`
   - the improvement entries
   - a recorded decision on whether the Brain enters the Engine score. Today none does; Moon is in `SHADOW_BRAINS`.

   The same PR sets the draft to ADOPTED, updates `test_draft_rubrics_not_loaded.py` and re-records the score baseline.
7. **Publishing the first score.** This is a production score write and is gated separately.
