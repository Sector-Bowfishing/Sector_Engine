# Draft score rubrics: Weather, Moon and Night Light, Generation (2026-11-23)

**Why this matters for bowfishing.** These scores are meant to answer one plain question for each Brain: can a bowfisher trust what it says tonight?
- **Weather:** that means rain (which muddies the water and moves the lake level), cloud, temperature swings and a working "weather is changing" signal. Barometric pressure is shown in the app but earns almost nothing, because there is no evidence it moves target species.
- **Moon:** it means a darkness call that counts the cloud. Dark water makes the lights work, and cloud cancels a bright moon except near cities.
- **Generation:** it means knowing whether the dam is releasing right now and when that changes.

The rubrics are built for those decisions, not for research volume. Every check is something a bowfisher would notice on the water.

**Status: DRAFT, not adopted.** Michael asked for these on 2026-11-23. They live in `docs/brains/scoring/drafts/`; adoption moves a file up into `docs/brains/scoring/`. Adopting a rubric, or publishing or changing a score, is his approval (Cortex `sector/engine` PROJECT.md §7). This change publishes nothing and changes no live score.

| Brain | Draft rubric | Score today |
|---|---|---|
| Weather (`brains/weather`) | [`weather-score-v1.json`](weather-score-v1.json) | **UNSCORED**: nothing published |
| Moon and Night Light (`brains/moon`) | [`moon-score-v1.json`](moon-score-v1.json) | **UNSCORED**: nothing published |
| Generation (`brains/generation`) | [`generation-score-v1.json`](generation-score-v1.json) | **UNSCORED**: nothing published |

## What keeps them inert

- No scorer reads them. `jobs/brain-scores/score_brains.py` `UPSTREAM` is unchanged, and `sector_brain_platform/scoring.py` has no function for these Brains. The scorer does not discover rubric files by listing this directory; each rubric it applies is named in code.
- `jobs/brain-scores/test_draft_rubrics_not_loaded.py` checks five things:
  - each draft is `DRAFT`, unadopted, and kept under `drafts/`;
  - `compute()` returns exactly `UPSTREAM`;
  - no frozen score and no improvement-registry entry exist for these Brains;
  - no scorer, platform or orchestrator code names a draft `scoreVersion`;
  - computing every score, the Engine score and every explanation opens nothing under `drafts/` and never lists the scoring directory, so their output cannot depend on what that directory contains.
- **The improvement registry was not touched.** `score_improvements_v1.json` says it is "never an input to any score", and it does not change any score value. It is still read by the scorer: `score_explanation.registry()` loads it, `score_brains.py` calls that during every write, and it is copied into `/scores/{id}/explanation`. That fails the condition for adding entries, so each draft carries its improvement text in `improvementsDraft`, ready to copy when the rubric is adopted.
- **The score baseline is unchanged.** `verification/integration/score_baseline.py` hashes only the top-level JSON files of `docs/brains/scoring/`, so drafts in `drafts/` are not treated as rubrics, and `verification/fixtures/scores/score_baseline.json` is not re-recorded. The engineering-status source digest (`tools/cortex_status/source_digest.py`) covers the whole `docs/brains/scoring/` tree, so it moves with these files; that is expected and is regenerated with the digest sequence.

## Choices common to all three

- **Unknown counts against the Brain, everywhere.** This follows Michael's rule that nothing should show unknown. Each draft has an `unknownPolicy` that applies it in four places:
  - A lake, tile or field that is unknown, unavailable, blocked or abstained earns 0 and stays in every denominator.
  - **One fixed denominator per Brain.** Every per-lake share divides by all the lakes the Brain is meant to cover:
    - Weather: the 621-lake directory.
    - Moon: the directory, minus polar-day lakes for the cloud share only.
    - Generation: the 401 catalog dam lakes. Its schedule share uses the 39 schedule-posting lakes for both numerator and denominator.

    A lake with no state at all (blocked, never computed, errored) is in that denominator and earns 0.
  - A fact the Brain does not publish scores 0 and lowers completeness. Either way an unknown counts as 0; it is never excluded.
  - No dimension excludes unknowns to make a share look better.
  - Filling an unknown with an estimate is worse: it is an invented value, which validation fails. The only way to remove an unknown is real data.
- **Each dimension says, in one sentence (`why`), what it means for a bowfisher.**
- **Same shape as the computed rubrics** (`lake-brain-score-v1.json`), so adoption can follow the existing scoring pattern: a 0–10 linear weighted sum with weights totalling 100, `UNKNOWN` dimensions contributing 0 and lowering completeness (an unknown counts as 0, never as excluded), and gates that cap and never add. Each draft also has the following fields:
  - a `class` on every dimension (Cortex scoring.md SC-09). There is no ENG or VOL dimension.
  - `movableByPackagingOnly`
  - `unscoredWhen`
  - `validationStatusMeaning`
  - a `workedExample`
  - an `adoption` checklist
- **UNSCORED is not 0.** A Brain that has never published gets no score block. Weather and Generation key this on the registry and its `lastSuccessfulRun`, which both keep across a failed run. Moon keys it on the registry alone, because Moon writes `lastSuccessfulRun` null whenever any lake errors. All three are in that state today: each is PARKED, has no executor, job or execution-control entry, and `run.py --write` refuses.
- **Only published facts.** Every dimension reads one of three things: a registry child the Brain writes (`directoryLakeCount`, `knowledgeRelease`, `sourceAccess`, `fleet`, `health`), a per-lake state field in its schema (with its freshness timestamp), or `/validation/{id}.status`. There are two declared exceptions:
  - Weather's `/validation/weather` is in its publication contract, but the runtime does not write it yet, so that dimension stays UNKNOWN until it does.
  - Generation's real-response fixture gate reads repository evidence. Its lead asked for this gate (see below).
- **Validation: what comes from the plans and what is new.**
  - *From the plans:* the pass criteria, thresholds, windows and minimum samples (Weather plan §5, Generation plan §5). The rubrics do not restate or change them.
  - *New in these drafts, for owner approval:*
    - the three status meanings (`VALIDATED`, `PARTIAL`, `NOT_VALIDATED`);
    - the PARTIAL tier and its 7.0 cap. Neither plan defines a partial result: Generation says "PASS needs all", and Weather keeps a gap open on any failed criterion.
  - *VALIDATED:* every pre-registered criterion passed.
  - *PARTIAL:* some criteria passed and the rest are **not yet scored** (their windows are still running); **none failed**.
  - *NOT_VALIDATED:* anything else. **Any FAIL** (and, for Weather, any INSUFFICIENT sample) makes it NOT_VALIDATED. A failed criterion is never credited.
  - *Caps:* NOT_VALIDATED caps the score at 5.0, as Lake does; PARTIAL caps it at 7.0.
  - *Who sets the status:* the Brain's validation record, never the scorer.
  - *Moon:* has no pre-registration at all, so everything in its validation block beyond the MOON-VAL-001 stop condition is new.
- **Validation nodes the Brains overwrite.** Moon and Generation write a constant `NOT_VALIDATED` to `/validation/{id}` on every run (`publish.py`), and Weather does not write the node yet. Each therefore needs a Brain change before its validation dimension can ever move. These changes are listed in each adoption checklist.
- **Common gates.** Health FAILED/UNKNOWN caps at 2.0. For Weather and Generation, coverage below 10 % caps at 3.0, as Lake does.
- **One population per ratio, clamped to [0, 10].** Each share's numerator is a subset of its fixed denominator.
- **Freshness is judged when the scorer runs, not when the Brain published.** Every per-lake fact counts only if the lake's own state is current at scoring time, read from a timestamp in the published state (`freshness.freshUntil` for Weather and Generation; the state's `date` equal to the Brain's `evening_date` for Moon). A state that expired, because the Brain stopped updating it or the lake errored or became BLOCKED after an earlier publish, earns 0. Registry counts that describe only the last run (`readinessCounts`, `breakdowns`, `supportedLakeCount`, `staleLakeCount`) are not used for per-lake shares. All the needed timestamps are already published, so no runtime change is needed for this.
- **No permanently empty dimensions.** There are none for the pressure forecast (WX-003) or per-lake skyglow (MOON-INP-002). They would be 0 forever (SC-09) until the Brain publishes a fact for them.
- **Worked examples are hand arithmetic** (`TYPED_NOT_COMPUTED`, SC-11), labelled non-authoritative. Assumed shares are marked as assumptions.

## Weather (`weather-score-v1`)

**Gates:**
- health → 2.0
- coverage below 10 % → 3.0
- validation NOT_VALIDATED or absent → 5.0
- validation PARTIAL → 7.0

PARTIAL means at least one of §5.1–§5.3 passed, the others are still within their windows, and none failed or came back INSUFFICIENT. VALIDATED means all three passed. Any failure, including a §5.1 fidelity failure, is NOT_VALIDATED.

**Points:**

| Dimension | Weight | What earns points |
|---|---|---|
| validation | 30 | Independent stations confirm rain, temperature and the change signal (plan §5) |
| rainReadout | 20 | directory lakes (all 621) with a state fresh at scoring time and both rain in the last hour and rain expected in the next 6 h (a null in either counts against) |
| coverage | 15 | directory ladder; BLOCKED lakes count against |
| fullStates | 15 | directory lakes with a state fresh at scoring time, kind observation and nothing missing (cloud included) |
| changeSignalEvaluable | 15 | directory lakes with a fresh state whose rain-onset, front and air-temperature-swing rules could all be evaluated (`weatherChange.unknown` absent or empty) |
| pressureTrend | 5 | directory lakes with a fresh state that has a 3 h trend. A token weight: no evidence ties pressure to where target species are |

**Today:** UNSCORED. No dry-run shares have been recorded yet, so the draft gives no illustrative number.

**Lifted by:** enablement, then plan §5.1 and §5.2 passing (about 30 days, which reaches PARTIAL if nothing has failed), then §5.3 (60 days).

## Moon and Night Light (`moon-score-v1`)

**Gates:**
- health → 2.0
- knowledge release not APPROVED → 2.0. This is a guard; the writer already refuses without an approved release.
- cloud included on less than 50 % of night lakes → 4.0. On those nights the class is only a clear-sky bound.
- validation NOT_VALIDATED or absent → 5.0
- validation PARTIAL → 7.0

**Points:**

| Dimension | Weight | What earns points |
|---|---|---|
| validation (MOON-VAL-001) | 35 | A simple light reading shows the darkness class matches how dark the water is |
| cloudIntegration | 35 | lakes whose written state is for tonight with basis MOON_AND_CLOUD, over (directory − tonight's NO_NIGHT lakes). Cloud cancels the moon except near cities. MOON_ONLY, errored and not-written lakes count against |
| currentNight | 30 | lakes whose written state is for tonight (the state's `date` equals `evening_date(lat, lon, scoring time)`, the Brain's own rule including the sunrise rollover) over the directory. The registry `breakdowns` are not used: `publish.py` counts a lake before its state is written, so a failed write would still be counted |

There is no coverage dimension. Moon's `supportedLakeCount` is every lake in the run, errored ones included, so coverage would always read 621/621 and measure nothing.

The USNO cross-check is real accuracy evidence. It earns nothing here because the Brain does not publish it as a measurement.

**MOON-VAL-001 has no pre-registration yet. The draft keeps validation proportionate:**
- **Proxy:** a simple light reading on real nights. Use a sky-quality meter or a phone light-meter app pointed straight up, at one fleet lake (a bowfisher's own readings count) or at a public sky-quality station near one. No multi-site statistical campaign.
- **Proposed check:** about 12 nights at one site, covering dark and bright moon and clear and cloudy skies. It passes if both hold:
  - readings get brighter with each class step;
  - cloudy bright-moon nights read darker than clear ones.

  This is a proposal for Michael to accept, change or reject.
- **Write it down first:** the check is committed before any reading is looked at.

**Today:** UNSCORED.

**Illustration:** the recorded 2026-11-22 dry run (621 lakes, all MOON_ONLY) would give 3.0, earned only by currentNight. With Weather live it would reach 5.0 (uncapped 6.2), and 9.7 once validated, under an assumed 90 % cloud share.

## Generation (`generation-score-v1`)

Coverage uses the **401 dam lakes** as its denominator, not the 621-lake directory.

**Gates:**
- health → 2.0
- release not APPROVED (G-2) → 2.0
- **sourceAccess (D-G)** → 3.0. Fires when a provider is ACCESS_CHECK_REQUIRED (SWPA today) or the release is unapproved.
- **realResponseFixtures** → 3.0. Fires until each serving provider has a recorded live response. Today only hand-built fixtures exist.
- dam coverage below 10 % → 3.0. Nothing is published today.
- validation NOT_VALIDATED or absent → 5.0
- validation PARTIAL → 7.0

**Points:**

| Dimension | Weight | What earns points |
|---|---|---|
| validation | 30 | VALIDATED = all five plan §5 metrics pass over the pre-registered week. PARTIAL = some pass, the rest not yet scored, none failed. Any failed metric = NOT_VALIDATED. |
| releasingNow | 30 | **Is the dam releasing or generating right now?** Catalog dam lakes whose status is GENERATING, SPILLING, RELEASING or OFF, over all 401 dam lakes. UNKNOWN, unbound and errored dams count against |
| scheduleCoverage | 25 | **When does it change?** TVA, TVA_CUMBERLAND and SWPA_USACE lakes with a fresh state whose posted schedule still covers scoring time (`schedule.scheduleCoversUntil`), over those same 39 lakes. An ended schedule earns 0. Today these earn 0: TVA's robots.txt disallows automated access (reported by the #241 review; D-G not yet recorded), the Cumberland projects are read through the TVA API, and SWPA waits on its access check. No proxy schedule is used |
| damCoverage | 15 | dam lakes whose state has kind OBSERVED or SCHEDULE_ONLY and is fresh at scoring time (UNAVAILABLE and DOWNSTREAM_ONLY states do not count); a dam lake with none counts against. This absorbs the former currency dimension: with freshness judged at scoring time everywhere, a separate 'not stale' share would count the same thing twice |

Discharge, turbine and spill numbers are secondary detail. They are published but not scored on their own.

**Today:** UNSCORED.

**Illustration** (only if TVA access were permitted): the 17 TVA-API lakes, published and fully current, would give 1.4. With 150 dam lakes known and fresh, all 39 schedules posted and validation passed, it would give 7.4; the 251 dams without a known status still count against. With TVA access refused, as reported, the TVA lakes publish nothing.

D-I (the cross-Brain TVA read budget) blocks enablement, not the score.

**Known limit:** the TVA half of D-G is not in any published fact. The `openCheck` note stays in `source_access.json`, so the gate also requires the approved release, which the plan sequences after D-G.

## What Michael must approve to adopt one (per Brain)

1. **The rubric.** Weights, gates, caps and status meanings, as written or amended. A new rubric is approval-gated.
2. **Moon only.** Accept or replace the practical one-site light-meter check for MOON-VAL-001, then write it down before any reading.
3. **Generation only.** Whether the fixture gate may read repository evidence. Every other fact in these drafts is a published RTDB fact.
4. **Brain changes to the validation node.** Weather must start writing `/validation/weather` with these status meanings. Moon and Generation must stop overwriting `/validation/moon` and `/validation/generation` with a constant `NOT_VALIDATED` on every run. Optionally, Moon could keep its previous `lastSuccessfulRun` after a run with errors, as Weather and Generation do.
5. **Cortex.** A Cortex maintenance session (not this repository) to register the Brain and `/scores/{id}`. None of the three is a Cortex target Brain (BA-01; CG-3.1-19, CG-3.1-20).
6. **The scorer PR.** It adds:
   - a `score_<brain>()` function
   - the facts in `fetch_facts`
   - the Brain in `UPSTREAM`
   - the improvement entries
   - a recorded decision on whether the Brain enters the Engine score. Today none does; Moon is in `SHADOW_BRAINS`.

   The same PR moves the draft into `docs/brains/scoring/`, sets it to ADOPTED, updates `test_draft_rubrics_not_loaded.py` and re-records the score baseline.
7. **Publishing the first score.** This is a production score write and is gated separately.
