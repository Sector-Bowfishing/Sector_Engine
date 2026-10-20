# Compliance ledger — Sector Engine

Living ledger (Cortex `core/execution.md` §9). One row per requirement, one column per Brain discovered, plus **Platform**. A row is updated only when it is re-evaluated, with the date and session. `NOT_VERIFIED` means not checked or not checkable without production access; it is **not** a failure.

```text
Standards: Rehtac Cortex 2.0.1 @ fc56557 (clean), pack sector/engine
Evaluated: 2026-10-20 · sessions/2026-10-20-architecture-all-brains.md (first pass) and sessions/2026-10-20-architecture-completion.md (this re-evaluation;
  every row below re-checked on branch cortex/architecture-standardization-2026-10-20 at 6d7ae03a)
Discovered Brains (8): biological-state (brains/fish), wind (brains/wind), water-clarity (brains/water-clarity), sector-intelligence (brains/sector-intelligence),
  lake-brain (brains/lake; Swift), water-temp (brains/water-temperature; Swift), depth (branch only), vegetation (branch only)
Source: stable_brain_ids.json (6) = brains/*/brain.json (6); control_manifest.json brains (8) = keys.BRAINS = Swift BrainPlatform.brains (test_brain_identity_consistency.py)
```

Abbreviations: **CM** = `jobs/brain_platform/sector_brain_platform/control_manifest.json`; **JM** = `jobs.py` `MANIFEST`; **OC** = `BRAIN_OPERATING_CONTRACT.md`; **Kit** = Brain Certification Kit V1. Depth and Vegetation are assessed **against `main`**, where they have no code; their branches were inspected read-only (session record §5.2).

## Brain requirements (BR)

| Req | Fish | Wind | Clarity | Intelligence | Lake | Water Temp | Depth | Vegetation |
|---|---|---|---|---|---|---|---|---|
| BR-01 purpose | **PASS** OC §3; README | **PASS** | **PASS** | **PASS** OC §2–§3; README | **PASS** OC §3; README | **PASS** OC §3; README | FAIL — no code on main | FAIL — same |
| BR-02 inventory | **PASS** | **PASS** | **PASS** | **PASS** (was PARTIAL) | **PASS** (was PARTIAL) | **PASS** (was PARTIAL) | **PARTIAL** — CM + `keys.py`; no package (blocked) | **PARTIAL** — same |
| BR-03 specialist boundary | **PASS** `tests/test_publication_specialist_boundary.py` + assessment guard | **PASS** | **PASS** | **PASS** (Intelligence publishes no recommendation until an approved activation) `tests/test_publication_specialist_boundary.py`; evaluation schema has no score field | **PASS** (was PARTIAL) same guard over the real artifact | **PASS** (was PARTIAL) | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-04 Intelligence boundary | — | — | — | **PASS** (was PARTIAL) — reads only published Brain state; degrade/abstain tested (`test_evaluation.py`, `test_sector_intelligence_brain.py`); RTDB / `GET /lakes` failure aborts the run with an error and publishes nothing (explicit fail-closed, quality.md) | — | — | — | — |
| BR-05 package shape | **PASS** | **PASS** | **PASS** | **PASS** (was FAIL) Kit P01 | **PASS** (was FAIL) Kit P01; Swift targets in `runtime/` | **PASS** (was FAIL) Kit P01 | **FAIL** — blocked | **FAIL** — blocked |
| BR-06 operating contract | **PASS** | **PASS** | **PASS** | **PASS** Kit P04 | **PASS** Kit P04 | **PASS** Kit P04 | FAIL | FAIL |
| BR-07 stable identity | **PASS** | **PASS** | **PASS** | **PASS** (was PARTIAL) `brain.json`; identity test | **PASS** (was PARTIAL) | **PASS** (was PARTIAL) | **PARTIAL** — CM/keys only | **PARTIAL** |
| BR-08 one implementation | **PASS** P02 | **PASS** P02 | **PASS** P02 | **PASS** P02; `jobs/sector-intelligence-brain` pointer | **PASS** (was PARTIAL) own SwiftPM targets; P02 | **PASS** (was PARTIAL) | FAIL — none on main | FAIL |
| BR-09 declared vs observed | **PASS** (was PARTIAL) trigger `dependency` (`brain.json:13`) | **PASS** (was FAIL) `staleHours` 1.5 = CM = runtime 90 min; JM lists `GET /lakes` | **PARTIAL** (was FAIL) JM fixed; CM `executionTarget` is C2 (documented note; job-map entry is decision D-E) | **PASS** (was PARTIAL) `brain.json` consumes 5 Brains OPTIONAL = CM; catalog `plannedRole` is the planned design role | **PASS** (was PARTIAL) 8 providers declared = runtime fetchers (`PROVIDERS.json`, JM) | **PASS** (was PARTIAL) JM no longer declares the unread TVA archive | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-10 machine-local deps | **PASS** P16 | **PASS** | **PARTIAL** — repo-relative polygon fallback (staged in image) | **PASS** P16 | **PASS** P16 (Python) + arch inv 9 (Swift) | **PASS** | NOT_APPLICABLE on main (branch has `/Users/` data paths) | NOT_APPLICABLE |
| BR-11 research separation | **PASS** P17 | **PASS** | **PASS** | **PASS** P17 | **PASS** P17 | **PASS** P17 | NOT_APPLICABLE (branch reads docs data) | NOT_APPLICABLE (branch reads research evidence) |
| BR-12 privacy | **PASS** | **PASS** | **PASS** | **PASS** synthetic test species (`ea4577d3`) | **PASS** (was PARTIAL) synthetic presence examples (`ea4577d3`); history not rewritten | **PASS** | NOT_VERIFIED | NOT_VERIFIED |
| BR-13 versioned output contract | **PASS** | **PASS** | **PASS** | **PASS** (was FAIL) `intelligence-evaluation-v1.schema.json` validated on real output; publication contract | **PARTIAL** — publication contract `lake-publication-v1` (derived, checked); no JSON schema for LakeState | **PARTIAL** — same | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-14 evidence & provenance | **PASS** | **PASS** | **PASS** | **PASS** `provenance.brainVersion` now set (`c606f7d4`) | **PASS** | **PASS** | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-15 confidence & uncertainty | **PASS** | **PASS** | **PARTIAL** | **PARTIAL** | **PARTIAL** | **PASS** (none calibrated; tested absent) | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-16 unknown / abstain | **PASS** | **PASS** | **PASS** | **PASS** | **PASS** | **PASS** | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-17 freshness & consumability | **PASS** | **PASS** | **PASS** | **PASS** (was PARTIAL) `sourceObservationAt` = oldest input | **PASS** | **PASS** (was PARTIAL) published schedule strings true (`11f18c1e`) | NOT_APPLICABLE | NOT_APPLICABLE |
| BR-18 domain tests | **PASS** 395 | **PASS** 215 | **PASS** 127 | **PASS** 91 | **PASS** Swift 77 (`LakeBrainTests` target) + Python 49 | **PASS** Swift 18 + shared resolver tests + Python 50 | FAIL — none on main | FAIL |
| BR-19 structural certification | **PASS** P01–P19 | **PASS** P01–P19 | **PASS** P01–P19 | **PASS** (was FAIL) P01–P19 | **PASS** (was FAIL) P01–P13, P15–P19; P14 NOT_APPLICABLE (Swift writes) | **PASS** (was FAIL) same | FAIL | FAIL |
| BR-20 honest labels | **PASS** | **PARTIAL** — stale self-published score copy (Proposal B) | **PASS** | **PASS** (was PARTIAL) catalog `2026-10-20.1` | **PASS** | **PASS** (was PARTIAL) | NOT_VERIFIED | NOT_VERIFIED |

## Platform requirements (PL)

| Req | Status | Evidence |
|---|---|---|
| PL-01 dependency graph | **PARTIAL** | CM graph validated fail-closed; Intelligence's edges now declared in `brain.json` (dependency graph reads them; `DD.drift` empty); the legacy planner graph remains (documented as legacy); `lake-brain-ledger-daily` still not created by any script (obs.11) |
| PL-02 execution safety | **PASS** (was PARTIAL) | `orchestrate.run_scorer` isolates scorer timeouts; `in_process_timeout` honours CM `timeoutSeconds`; `orchestration.retry_gate` bounds automatic retries (`test_retry_gate.py`, `test_execution_safety.py`); idempotent writes unchanged |
| PL-03 fallback honesty | **PASS** (was PARTIAL) | Lake `sourceFallback` (DEGRADED_USABLE, primary kept, selected source + capability); flags and WARNING kept (`LakeBrainTests.testFallbackUsedWhenPrimaryStaleAndFlagged`). Production effect needs deploy (A-2) |
| PL-04 observability | **PASS** (repository) | unchanged; retry decisions carry `retry` and reason codes |
| PL-05 publication contract | **PASS** (was FAIL for 3 Brains) | six `*-publication-v1.json`, all `describe_contract.py --check` OK; Depth/Vegetation n/a (no code on main) |
| PL-06 single writer | **PARTIAL** | Python and Swift source ownership identical and tightened (Lake fleet sources); Wind's `/brains/wind/scores` copy remains (Proposal B) |
| PL-07 guarded flow | **PARTIAL** | Publisher LIVE stages implemented; not wired (obs.04); six Brains now have SHADOW registrations |
| PL-08 rules & IAM | **NOT_VERIFIED** | needs production read (A-3) |
| PL-09 lineage & rollback | **PARTIAL** | typed deletes (`lastError` OPTIONAL_CHILD_CLEARED for Lake/Water Temp), P08/P13 pass for six Brains; production rollback NOT_VERIFIED |
| PL-10 publication sequence | **PASS** (repository) | unchanged; no cutover |
| PL-11 registries | **PASS** (was PARTIAL) | one identity model enforced by `tools/architecture/tests/test_brain_identity_consistency.py`; water domains valid; providers catalog complete for all six Brains |
| PL-12 Ops observer | **NOT_VERIFIED** | Sector Ops project |
| PL-13 Pulse | **NOT_VERIFIED** | no Pulse code here |
| PL-14 no LLM | **PASS** | unchanged |

## Scoring requirements (SC)

| Req | Status | Evidence |
|---|---|---|
| SC-01 separation | **FAIL** (unchanged; proposal written) | one score type for five kinds; Proposal A in `docs/brains/platform/SCORE_MEASUREMENT_SEPARATION_PROPOSAL_V1.md` (needs Ops + approval) |
| SC-02 score shape | **PARTIAL** | unchanged |
| SC-03 domain rubrics | **PARTIAL** | unchanged |
| SC-04 scorer authority | **PARTIAL** | Wind self-published copy (Proposal B); Depth/Vegetation branches compute scores in-Brain (blocked) |
| SC-05 no unearned increases | **PASS** | Kit P19 passes for six Brains; no score input changed; score baseline values unchanged (`89445e5d`) |
| SC-06 Fish species integrity | **PASS** (repository) | unchanged |
| SC-07 honest health score | **NOT_VERIFIED** | production read |
| SC-08 baselines preserved | **PARTIAL** | Wind V2 6.7 (adopted, unpublished), Wind cert 3.3, BWIS 5.4, Fish TARGET 6.805781 / overall 3.770401, Fish maturity 5.1 — unchanged; `score_baseline.json` re-recorded hashes only; Engine score NOT_VERIFIED (runtime only) |

## Per-Brain evidence records (brains.md §8)

Items 12–14 are NOT_APPLICABLE for every Brain (no production-live, Ops-live or customer-recommendation claim).

| # | Item | Fish | Wind | Clarity | Intelligence | Lake | Water Temp | Depth / Vegetation |
|---|---|---|---|---|---|---|---|---|
| 1 | Identity & one implementation | PASS | PASS | PASS | PASS | PASS | PASS | branch only |
| 2 | Ownership & Intelligence boundary | PASS | PASS | PASS | PASS | PASS | PASS | n/a |
| 3 | Research separation & lineage | PASS | PASS | PASS | PASS | PASS | PASS | blocked (reads docs/research) |
| 4 | Declared vs observed inputs | PASS | PASS | PARTIAL | PASS | PASS | PASS | n/a |
| 5 | Versioned contracts, unknowns, freshness | PASS | PASS | PASS | PASS | PARTIAL (no state schema) | PARTIAL | n/a |
| 6 | Domain tests & Kit proofs | PASS / 19 | PASS / 19 | PASS / 19 | PASS / 19 | PASS / 18 + P14 N/A | PASS / 18 + P14 N/A | none on main |
| 7 | Rubric & scorer authority | PASS | PARTIAL (copy) | PASS | PASS | PASS | PASS | branch computes scores |
| 8 | Confidence vs readiness separate | PARTIAL (SC-01) | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PARTIAL | n/a |
| 9 | Orchestration, retry, fallback, health | PASS | PASS | PASS | PASS | PASS | PASS | `kind: none` |
| 10 | Publisher contract, ownership, rules/IAM | contract PASS; rules/IAM NOT_VERIFIED | same | same | same | same | same | none |
| 11 | Shadow tests, rollback, baseline export | shadow PASS (P11); rest NOT_VERIFIED | same | same | same | same | same | n/a |
| 15 | Release ids, digest, CI, rollback | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | NOT_VERIFIED | n/a |

## Structural status vs production status

| Brain | Structural (this branch) | Science | Production | Customer |
|---|---|---|---|---|
| Fish | Canonical, Kit 19/19 | NOT_VALIDATED | in-process via orchestrator (state NOT_VERIFIED) | none |
| Wind | Canonical, Kit 19/19 | NOT_VALIDATED | `wind-hourly` (NOT_VERIFIED) | none |
| Water Clarity | Canonical, Kit 19/19 | customer number not validated | MANUAL | none |
| Sector Intelligence | Canonical, Kit 19/19 | NOT_VALIDATED | PARKED, in-process (image layout unchanged) | none |
| Lake | Canonical (Swift targets), Kit 18/18 + P14 N/A | NOT_VALIDATED | job + hand-made ledger scheduler (NOT_VERIFIED); changes need A-2 | none |
| Water Temperature | Canonical (Swift targets), Kit 18/18 + P14 N/A | GLOBAL_HOLDOUT_ONLY | PARKED | none |
| Depth / Vegetation | Blocked (session record §5.2) | — | `kind: none` | none |
