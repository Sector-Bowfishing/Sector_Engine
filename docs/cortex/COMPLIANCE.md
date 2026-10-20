# Compliance ledger — Sector Engine

Living ledger (Cortex `core/execution.md` §9). One row per requirement, one column per Brain discovered, plus **Platform**. A row is updated only when it is re-evaluated, with the date and session. `NOT_VERIFIED` means not checked or not checkable without production access; it is **not** a failure.

```text
Standards: Rehtac Cortex 2.0.1 @ fc56557 (clean), pack sector/engine
Evaluated: 2026-10-20 · session sessions/2026-10-20-architecture-all-brains.md · Engine HEAD after changes on cortex/architecture-standardization-2026-10-20
Discovered Brains (8): biological-state (brains/fish), wind (brains/wind), water-clarity (brains/water-clarity),
  lake-brain (Swift Sources/SectorEngine/LakeBrain + jobs/lake-brain), water-temp (Swift Sources/SectorEngine/Brain/WaterTemperatureBrain*),
  sector-intelligence (jobs/sector-intelligence-brain), depth (branch only), vegetation (branch only)
Source: jobs/brain_platform/sector_brain_platform/control_manifest.json `brains` (8) + brains/*/brain.json (3) + tools/architecture/stable_brain_ids.json (6)
```

Abbreviations: **CM** = `jobs/brain_platform/sector_brain_platform/control_manifest.json`; **JM** = `jobs/brain_platform/sector_brain_platform/jobs.py` `MANIFEST`; **OC** = the Brain's `BRAIN_OPERATING_CONTRACT.md`; **certdoc/** = `docs/architecture/certification/`; **SI** = `jobs/sector-intelligence-brain/`. Depth and Vegetation are assessed **against `main`**, where they have no code (`git ls-files` finds no `brains/depth`, `brains/vegetation`, `jobs/*depth*`, `jobs/*vegetation*`); their branches were inspected read-only (`feat/depth-brain-foundation` 40 ahead / 178 behind `origin/main`; `feat/vegetation-brain-foundation` 19 / 178).

## Brain requirements (BR)

| Req | Fish | Wind | Clarity | Lake | Water Temp | Intelligence | Depth | Vegetation |
|---|---|---|---|---|---|---|---|---|
| BR-01 purpose | **PASS** OC §3 `brains/fish/BRAIN_OPERATING_CONTRACT.md:14-15`; README now states decision + consumers (commit `4cffb28b`) | **PASS** `brains/wind/README.md:3`, OC §3 | **PASS** OC §3 `:12-13`; README fixed (`4cffb28b`) | **PASS** (was FAIL) `certdoc/lake/BRAIN_OPERATING_CONTRACT.md` §3 (`e622a10f`) | **PASS** (was FAIL) `certdoc/water-temperature/…` §3 (`e622a10f`) | **PASS** (was PARTIAL) `certdoc/sector-intelligence/…` §2–§3 (`e622a10f`) | FAIL — no code or contract on main | FAIL — same |
| BR-02 inventory | **PASS** | **PASS** | **PASS** | **PARTIAL** — registered in CM, JM, `ownership.py`, stable ids; no `brains/lake/` | **PARTIAL** — same; no `brains/water-temperature/` | **PARTIAL** — same; no `brains/sector-intelligence/` | **PARTIAL** — in CM (`:54-62`) and `keys.py:17`; not in stable ids; no code on main | **PARTIAL** — in CM (`:63-71`), `keys.py:18`; not in stable ids |
| BR-03 specialist boundary | **PASS** (was PARTIAL) assessment guard `biological_assessment.py:29-30` + publication guard `brains/fish/tests/test_publication_specialist_boundary.py` (`da1e43df`) | **PASS** (was PARTIAL) `assessment/schema.py:36-37` + `brains/wind/tests/test_publication_specialist_boundary.py` | **PASS** (was NOT_VERIFIED) `brains/water-clarity/tests/test_publication_specialist_boundary.py` | **PARTIAL** — no recommendation fields (`LakeLevelClassifier.swift:157` "no fish wording"; integration doc §1) but no rejection test | **PARTIAL** — none emitted (`WATER_TEMP_BRAIN.md:18`), no rejection test | n/a (row BR-04) | NOT_APPLICABLE — no output on main | NOT_APPLICABLE |
| BR-04 Intelligence boundary | — | — | — | — | — | **PARTIAL** — reads only published Brain state (`run.py:67-72,94-123`), no specialist logic copied (`evaluation.py:56-71`), explicit degrade/abstain tested (`test_evaluation.py:72,83,95,100`; `test_sector_intelligence_brain.py:76,91,112`); gaps: an RTDB read or `GET /lakes` failure aborts the run (`run.py:94-95,122`), no test | — | — |
| BR-05 package shape | **PASS** — required entries present; `find -type d -empty` none | **PASS** — same; `deploy/` justified (`wind-hourly`, read service) | **PASS** — same | **FAIL** — no canonical package (migration is decision D-1) | **FAIL** — same | **FAIL** — same | **FAIL** — not on main | **FAIL** — not on main |
| BR-06 operating contract | **PASS** 19 sections (arch report inv 4) | **PASS** (stale §9 GAPS line fixed `4cffb28b`) | **PASS** | **PASS** (was FAIL) DRAFT 0.1.0, guarded by `tools/architecture/tests/test_unmigrated_brain_contracts.py` | **PASS** (was FAIL) same | **PASS** (was FAIL) same | FAIL | FAIL |
| BR-07 stable identity | **PASS** `brain.json:3` = stable ids `:6` = CM `:17` | **PASS** | **PASS** | **PARTIAL** — ID consistent in stable ids/CM/JM/`LakeBrainContract.swift:21`; no `brain.json` (forbidden pre-migration by `tools/architecture/tests/test_foundation.py` `test_real_repo_registers_only_migrated_brains`) | **PARTIAL** — same (`WaterTemperatureBrain.swift:30`) | **PARTIAL** — same (`sector_intelligence_brain.py:26`) | **PARTIAL** — CM + `keys.py` only | **PARTIAL** — same |
| BR-08 one implementation | **PASS** P02; `jobs/biological-brain/` is a pointer | **PASS** P02; `jobs/wind-hourly/` pointer | **PASS** P02; `jobs/water-clarity-brain/` pointer | **PARTIAL** — one Brain runtime, but it shares the customer `SectorEngine` library target (`Package.swift:24-44`, obs.12) | **PARTIAL** — same; selection restated (not shared) from `/conditions` | **PASS** — one runtime; `catalog.json` catalogs the other implementations | **FAIL** — none on main | **FAIL** — none on main |
| BR-09 declared vs observed inputs | **PARTIAL** — `brain.json:13` trigger `manual` vs CM `:20-22` `INPUT_DRIVEN`; CM `scopes ["guntersville"]` for a species Brain | **FAIL** — `brain.json:13` `staleHours 6` vs CM `:14` `staleAfterHours 1.5` (runtime `contract.py:47-48` = 90 min) (obs.03 still true); JM `:68` omits `GET /lakes` | **FAIL** — CM `:28` executionTarget is C2 `lake-surface-dispatch` (+ HEAVY resources `:33`) while `brain.json:10-13` is the C1 job `water-clarity-brain`; CM `jobs` lacks `water-clarity-brain`; JM `:144` omits `GET /lakes` | **PARTIAL** — JM `:122-130` omits five fetchers (`LakeLevelFeedsFleet.swift:130-134`); CM `:35-37` vs JM `:124` trigger | **PARTIAL** — JM `:135` declares the TVA archive the Brain never reads; CM `:45-47` PARKED/MANUAL vs JM `:133` "orchestrator, 4/day" | **PARTIAL** — `catalog.json:128-166` deps `REQUIRED` vs CM `:77-81` `OPTIONAL` | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-10 no machine-local runtime deps | **PASS** `test_fish_certification.py:225`; P16 | **PASS** runtime; research tools use `~/Desktop`/`~/Library/Caches` (outside runtime) | **PARTIAL** — repo-relative fallback to `jobs/lake-surface/polygons.geojson.gz` (`run.py:41-45`); staged in image | **PASS** runtime; tooling hard-codes `/Users/…/Desktop` (`jobs/lake-brain/review/build_review_pack.py:56-58`, `validation/holdout_data.py:18-19`) | **PASS** | **PASS** | NOT_APPLICABLE on main (branch data JSON embeds `/Users/` paths) | NOT_APPLICABLE |
| BR-11 research/runtime separation | **PASS** hash-verified release (`biological_brain.py`), P17 | **PASS** P17 | **PASS** P17; private overlay at run time | **PASS** — presence via validated private bundle (integration doc §8) | **PASS** — no research read | **PASS** | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-12 privacy | **PASS** synthetic-only tests (`brains/fish/README.md:12,24`) | **PASS** | **PASS** `test_water_clarity_brain.py:207-211` | **PARTIAL** — `docs/brains/LAKE_BRAIN_INTEGRATION.md` §8 example and rules name a real lake's species presence state (decision D-13) | **PASS** | **PASS** — presence read at run time, never committed | NOT_VERIFIED | NOT_VERIFIED |
| BR-13 versioned output contract | **PASS** `fish-publication-v1.json`, `fish-biological-assessment-v1.json`; describe `--check` OK | **PASS** 3 contracts; describe OK | **PASS** describe OK | **PARTIAL** — Swift types + `contracts/conformance/lake_keys.json`, `lake_rules_v2.json`; no versioned JSON schema | **PARTIAL** — Swift types only | **FAIL** — contracts are PROPOSED prose (`catalog.json:248-251`) | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-14 evidence & provenance | **PASS** P07, `test_fish_certification.py:195,272` | **PASS** `test_publish_artifact.py:98,339,413` | **PASS** `test_clarity_certification.py:228,238` | **PASS** `provenance` in LakeState (integration doc §4) | **PASS** `provenance` (`WATER_TEMP_BRAIN.md` state table) | **PASS** `evaluation.py:194-197` (but `brainVersion` always absent, D-8) | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-15 confidence & uncertainty | **PASS** `test_rules_state_validation.py:134` | **PASS** `test_wind_exposure_assessment.py:242` | **PARTIAL** — readiness/qualityFlags/`confidenceLabel`, no uncertainty value | **PARTIAL** — explicit tiers/flags, no confidence on LakeState | **PASS** — deliberately none ("none is calibrated", test `WaterTemperatureBrainTests.swift:83-85`) | **PARTIAL** — degraded inputs explicit; no uncertainty | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-16 unknown / abstain | **PASS** `test_rules_state_validation.py:229,240` | **PASS** `test_wind_exposure_assessment.py:184,231` | **PASS** `test_clarity_certification.py:200` | **PASS** `LakeBrainTests.swift:149-192` | **PASS** `WaterTemperatureBrainTests.swift:65-122` | **PASS** `test_evaluation.py:83,95` (assertions made explicit `5155e769`) | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-17 freshness & consumability | **PASS** version-driven by design `test_fish_certification.py:311` | **PASS** `test_publish_artifact.py:126,212` | **PASS** `test_clarity_certification.py:193,209` | **PASS** freshness envelope (integration doc §10) | **PARTIAL** — evidence stale flag OK; published `schedule` string false (`WaterTemperatureBrain.swift:37`, D-9) | **PARTIAL** — evaluation freshness computed from its own time (`evaluation.py:199`, D-8) | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-18 domain tests | **PASS** 395 passed, 2 skipped | **PASS** 215 passed | **PASS** 127 passed | **PASS** Swift 313 XCTests pass (all targets); Python lake-brain suites 13/23/70/24 pass | **PASS** Swift suite (above) | **PASS** 33 passed | FAIL — none on main | FAIL — none on main |
| BR-19 structural certification | **PASS** Kit V1 P01–P19 all pass (51 cases) | **PASS** P01–P19 all pass (51) | **PASS** P01–P19 all pass (52) | **FAIL** — kit not adopted (needs a package, D-1) | **FAIL** — same | **FAIL** — same | FAIL | FAIL |
| BR-20 honest labels | **PASS** PROFILED / NOT_VALIDATED / publication INACTIVE (`fish-capability-publication.json:5`) | **PARTIAL** — job still writes a stale copy `/brains/wind/scores` (3.1) beside `/scores/wind` (3.3) (`publish.py:249,271`; obs.14) | **PASS** | **PASS** NOT_VALIDATED; docs now state the live scheduler (`f900ec52`) | **PARTIAL** — published schedule string contradicts reality (D-9) | **PARTIAL** — `catalog.json:176-184,250,253` still say "no evaluation" while pilots publish (D-8) | NOT_VERIFIED | NOT_VERIFIED |

## Platform requirements (PL) — Platform column unless a Brain is named

| Req | Status | Evidence |
|---|---|---|
| PL-01 dependency graph | **PARTIAL** | Declared in CM, validated fail-closed (`orchestration.py:92-121`); also a legacy graph (`orchestrator.py:19,26-44`) and `dependency_declarations.py`; scheduled vs ad-hoc distinguished (`orchestration.py:24-26`, `orchestrate.py:215-218,310`). `lake-brain-ledger-daily` is not created by any repo script (obs.11 still true) |
| PL-02 execution safety | **PARTIAL** | Timeouts hard-coded (`orchestrate.py:106-124,334`); CM `timeoutSeconds`/`defaults.retry` unread; bounded retry only on `--legacy-execution` (`orchestrate.py:221,271`); scorer timeout at `:334` not caught (inferred: aborts the cycle). Idempotent writes via `changed_paths` and `--if-changed` |
| PL-03 fallback honesty | **PARTIAL** | Lake CWMS→USGS fallback flagged (`LakeLevelClassifier.swift:190,211-218`, health WARNING `LakeBrainRunner.swift:232-235`) but readiness not DEGRADED and source capability/datum taken from the binding (`LakeLevelClassifier.swift:148-155,181`); fix branch `fix/lake-brain-cwms-retry` (`125ddae4`) unmerged; failed `--plan` → UNKNOWN (`orchestrate.py:107-116`) |
| PL-04 observability | **PASS** (repository) | History/health/freshness sections (`control_state.py:15`, `orchestration.py:449-474`); `control/healthV1` only with `--publish-health` (off in `deploy-job.sh`). Live state NOT_VERIFIED |
| PL-05 publication contract | Fish/Wind/Clarity **PASS** (describe `--check` match); Lake/Water Temp/Intelligence **FAIL** | No `*-publication-v1.json`; `publisher/registry.py:396-398` covers three Brains |
| PL-06 single writer | **PARTIAL** | Client-side ownership `ownership.py:24` = Swift `BrainContract.swift:139`; `BrainRtdb(brain_id=None)` skips the check (`score_brains.py:299`); shared-any paths `ownership.py:57-58,97-98`; Wind writes `/brains/wind/scores` (obs.14) |
| PL-07 guarded flow | **PARTIAL** | All stages implemented in `publisher_live/publisher.py:108-271` (authorization is an allow-list, `:108-110`); **not wired**: only tests and tooling import `publisher_live` (obs.04 still true; `test_publisher_live_boundary.py:16-33`) |
| PL-08 rules & IAM | **NOT_VERIFIED** | Target rules `platform/security/rtdb.rules.target.json` REPO_READY (`publisher_security_plan.json:117`, `liveSecurityVerified: false` `:13`); writer SA has `roles/firebasedatabase.admin` (`jobs/brain-orchestrator/deploy-job.sh:39`); deployed rules live in Sector Ops (verify.02) |
| PL-09 lineage & rollback | **PARTIAL** | Typed deletes and semantic SKIP in Publisher (P13, P08 pass for 3 Brains); production rollback NOT_VERIFIED |
| PL-10 publication sequence | **PASS** (repository) | `docs/architecture/production/PRODUCTION_CUTOVER_PLANS_V1.md:4` "Water Clarity -> Fish -> Wind"; no cutover performed |
| PL-11 registries | **PARTIAL** | Species water domains valid (FRESHWATER/BRACKISH/MARINE; DIADROMOUS banned `brains/fish/runtime/water_domain.py:5`); Brain identity in ≥ 6 hand-kept registries with ID sets 8/8/6/5/3 (obs.02 still true); `platform/registries/brains/`, `lakes/` README-only |
| PL-12 Ops observer | **NOT_VERIFIED** | Engine side: scores only from scorer (SC-04); Ops internals belong to the Sector Ops project (verify.05) |
| PL-13 Pulse | **NOT_VERIFIED** | No Pulse code in this repository (verify.04); declared deterministic entry points exist (`brains/fish/runtime/capability_run.py`, `brains/wind/contracts/wind-validation-entrypoints-v1.json`) |
| PL-14 no LLM | **PASS** | No ollama/openai/anthropic usage in `jobs/` or `brains/`; banned-import test `brains/fish/tests/test_capability_v2.py:359` |

## Scoring requirements (SC) — Platform

| Req | Status | Evidence |
|---|---|---|
| SC-01 separation | **FAIL** | Every `brain.json` and the template declare `ENGINE_READINESS_SCORE` (`brains/wind/brain.json:37`, `fish:32`, `water-clarity:34`) for computed readiness rubrics, a frozen level ladder (`frozen-scores.json:3-5`) and a frozen research score; `score_engine` averages them (`scoring.py:232-236`) (obs.09 still true; D-6) |
| SC-02 score shape | **PARTIAL** | Dimensions, gates, `nextScoreOpportunity` (`scoring.py:40-58`), explanations (`score_explanation.py`); Fish/Wind capability rubrics versioned; no change log for computed rubrics in repo |
| SC-03 domain rubrics | **PARTIAL** | Domain-specific rubrics exist; Lake/biological/Intelligence/Engine rubric files are named only, weights hard-coded in `scoring.py:110,171,213,280,290` |
| SC-04 scorer authority | **PARTIAL** | Scorer computes `/scores/*`; Wind runtime publishes its own score copy (`publish.py:249`, values hard-coded `brains/wind/research/tools/brain_validation_evidence.py:82-83`) |
| SC-05 no unearned increases | **PASS** | Kit proof P19 `score_and_lifecycle` passes for Fish, Wind, Clarity; this session changed no score input |
| SC-06 Fish species integrity | **PASS** (repository) | Rubric 2.1.0, cohorts v2 frozen, per-species (`docs/brains/scoring/FISH_BIOLOGICAL_CAPABILITY_V2.md:143-146`) |
| SC-07 honest health score | **NOT_VERIFIED** | `score_engine` derives from inputs (`scoring.py:232-291`); live value needs production read |
| SC-08 baselines preserved | **PARTIAL** | Wind Specialist Capability V2 **6.7** adopted, not published (`wind-specialist-capability-v2.json:265-271`); Wind certification **3.3**, BWIS **5.4** (`:12-14`, `frozen-scores.json:26-28`); Fish TARGET **6.805781**, overall **3.770401** (`FISH_BIOLOGICAL_CAPABILITY_V2.md:145-146`), publication INACTIVE; Fish maturity `biological-state-score-v1` **5.1** (`FISH_BIOLOGICAL_CAPABILITY_V2.md:15`); Engine score: **NOT_VERIFIED** (computed at runtime; no repository value) |

## Per-Brain evidence records (brains.md §8; blueprint §10)

Items 12–14 are `NOT_APPLICABLE` for every Brain: no Brain claims production-live through the Publisher, Ops-live verification belongs to Sector Ops, and no customer recommendation is claimed.

| # | Item | Fish | Wind | Clarity | Lake | Water Temp | Intelligence | Depth / Vegetation |
|---|---|---|---|---|---|---|---|---|
| 1 | Identity & one implementation | BR-07/08 PASS | PASS | PASS | PARTIAL (no brain.json; shared target) | PARTIAL (same) | PARTIAL (no brain.json) | branch only |
| 2 | Ownership & Intelligence boundary | BR-03 PASS | PASS | PASS | PARTIAL | PARTIAL | BR-04 PARTIAL | n/a on main |
| 3 | Research separation & knowledge lineage | PASS (hash-verified release) | PASS | PASS | PASS | PASS | PASS | n/a |
| 4 | Declared vs observed inputs | PARTIAL | FAIL | FAIL | PARTIAL | PARTIAL | PARTIAL | n/a |
| 5 | Versioned contracts, unknowns, freshness | PASS | PASS | PASS | PARTIAL | PARTIAL | FAIL (prose contracts) | n/a |
| 6 | Domain tests & certification proofs | PASS / P01–P19 PASS | PASS / PASS | PASS / PASS | tests PASS / kit not adopted | tests PASS / kit not adopted | tests PASS / kit not adopted | none on main |
| 7 | Capability rubric & scorer authority | Capability V2 (2.1.0, cohorts v2) + maturity v1 | Capability v2 6.7 (adopted, unpublished); stale self-published copy | frozen research 8.0 | `lake-brain-score-v1` (scorer) | frozen ladder 3.0 | `sector-intelligence-score-v1` (scorer) | none |
| 8 | Scientific confidence vs production readiness separate | PARTIAL (one score type label, SC-01) | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | n/a |
| 9 | Orchestration, retries, fallback, idempotency, health | in-process; PL-02 PARTIAL | own scheduler `wind-hourly` | MANUAL | job + ledger scheduler; PL-03 PARTIAL | orchestrator when stale; PARKED | in-process; PARKED | `executionTarget.kind: none` |
| 10 | Publisher contract, write ownership, rules/IAM | contract PASS; Publisher shadow; rules/IAM NOT_VERIFIED | same | same | no contract; direct writes | no contract; direct writes | no contract; direct writes | none |
| 11 | Shadow tests, rollback rehearsal, baseline export | shadow PASS (P11); rollback/export NOT_VERIFIED | same | same | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | n/a |
| 15 | Release IDs, digest, CI, blockers, rollback | NOT_VERIFIED (production lineage not read; obs.07 unverified at HEAD) | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | n/a |

## Structural completion status (separate from science, production and customer status)

| Brain | Structural | Science validation | Production | Customer |
|---|---|---|---|---|
| Fish | Canonical package; Kit V1 P01–P19 pass; BR-09 PARTIAL | NOT_VALIDATED | in-process via orchestrator (scheduler state NOT_VERIFIED) | none |
| Wind | Canonical package; P01–P19 pass; BR-09 FAIL (stale threshold) | NOT_VALIDATED | `wind-hourly` (state NOT_VERIFIED) | none (customer wind is Open-Meteo) |
| Water Clarity | Canonical package; P01–P19 pass; BR-09 FAIL (CM describes C2) | customer number not validated | MANUAL | none |
| Lake | Not packaged; operating contract DRAFT; kit not adopted | NOT_VALIDATED (hold-out H-C failed) | job + hand-made ledger scheduler (NOT_VERIFIED live) | none |
| Water Temp | Not packaged; operating contract DRAFT; kit not adopted | GLOBAL_HOLDOUT_ONLY | PARKED | none (same numbers as `/conditions`, which does not read the Brain) |
| Intelligence | Not packaged; operating contract DRAFT; kit not adopted | NOT_VALIDATED | PARKED, in-process | none |
| Depth / Vegetation | No code on main | — | `kind: none` | none |
