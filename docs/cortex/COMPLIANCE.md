# Compliance ledger — Sector Engine

Living ledger (Cortex `core/execution.md` §9). One row per requirement, one column per Brain discovered, plus **Platform**. A row is updated only when it is re-evaluated, with the date and session. `NOT_VERIFIED` means not checked or not checkable without production access; it is **not** a failure.

```text
Standards: Rehtac Cortex 2.1.0 @ 0f9ee75 (historical; the pin is now 3.1.0 @ 9562274, see sessions/2026-10-28-orchestrator-cortex-3-1.md) (clean), pack sector/engine
Evaluated: 2026-10-20 · sessions/2026-10-20-architecture-all-brains.md (first pass), sessions/2026-10-20-architecture-completion.md (re-evaluation),
  sessions/2026-10-20-cortex-2-1-memory.md (standing memory checks) and sessions/2026-10-20-cortex-2-1-structural-completion.md (this re-evaluation:
  Depth and Vegetation migrated and certified; every Depth/Vegetation cell, BR-10/11/16/18/19 and the standing checks re-checked)
  and sessions/2026-10-20-cortex-2-1-final-verification.md (final verification: all rows re-verified by running the suites, Kit V1, the
  standing-memory, Swift ownership/boundary/state-schema and cross-Brain coupling gates; Linux CI made portable; no row regressed)
Discovered Brains (8), all in canonical packages: biological-state (brains/fish), wind, water-clarity, sector-intelligence, lake-brain (brains/lake; Swift),
  water-temp (brains/water-temperature; Swift), depth (brains/depth), vegetation (brains/vegetation)
Source: stable_brain_ids.json (8) = brains/*/brain.json (8) = control_manifest.json brains (8) = keys.BRAINS = Swift BrainPlatform.brains (test_brain_identity_consistency.py)
```

Abbreviations: **CM** = `jobs/brain_platform/sector_brain_platform/control_manifest.json`; **JM** = `jobs.py` `MANIFEST`; **OC** = `BRAIN_OPERATING_CONTRACT.md`; **Kit** = Brain Certification Kit V1. Depth and Vegetation were assessed against `main` until 2026-10-20; they now have canonical packages on this branch (session `2026-10-20-cortex-2-1-structural-completion.md`).

## Brain requirements (BR)

| Req | Fish | Wind | Clarity | Intelligence | Lake | Water Temp | Depth | Vegetation |
|---|---|---|---|---|---|---|---|---|
| BR-01 purpose | **PASS** OC §3; README | **PASS** | **PASS** | **PASS** OC §2–§3; README | **PASS** OC §3; README | **PASS** OC §3; README | **PASS** OC §2–§3; README | **PASS** OC §2–§3; README |
| BR-02 inventory | **PASS** | **PASS** | **PASS** | **PASS** (was PARTIAL) | **PASS** (was PARTIAL) | **PASS** (was PARTIAL) | **PASS** brain.json + CM | **PASS** brain.json + CM |
| BR-03 specialist boundary | **PASS** `tests/test_publication_specialist_boundary.py` + assessment guard | **PASS** | **PASS** | **PASS** (Intelligence publishes no recommendation until an approved activation) `tests/test_publication_specialist_boundary.py`; evaluation schema has no score field | **PASS** (was PARTIAL) same guard over the real artifact | **PASS** (was PARTIAL) | **PASS** no recommendation fields; no score (Kit P19, has_score=False) | **PASS** same |
| BR-04 Intelligence boundary | — | — | — | **PASS** (was PARTIAL) — reads only published Brain state; degrade/abstain tested (`test_evaluation.py`, `test_sector_intelligence_brain.py`); RTDB / `GET /lakes` failure aborts the run with an error and publishes nothing (explicit fail-closed, quality.md) | — | — | — | — |
| BR-05 package shape | **PASS** | **PASS** | **PASS** | **PASS** (was FAIL) Kit P01 | **PASS** (was FAIL) Kit P01; Swift targets in `runtime/` | **PASS** (was FAIL) Kit P01 | **PASS** Kit P01 | **PASS** Kit P01 |
| BR-06 operating contract | **PASS** | **PASS** | **PASS** | **PASS** Kit P04 | **PASS** Kit P04 | **PASS** Kit P04 | **PASS** Kit P04 | **PASS** Kit P04 |
| BR-07 stable identity | **PASS** | **PASS** | **PASS** | **PASS** (was PARTIAL) `brain.json`; identity test | **PASS** (was PARTIAL) | **PASS** (was PARTIAL) | **PASS** id locked (`stable_brain_ids.json`) | **PASS** id locked |
| BR-08 one implementation | **PASS** P02 | **PASS** P02 | **PASS** P02 | **PASS** P02; `jobs/sector-intelligence-brain` pointer | **PASS** (was PARTIAL) own SwiftPM targets; P02 | **PASS** (was PARTIAL) | **PASS** P02; branch `jobs/depth-brain` untouched (not on main) | **PASS** P02; branch untouched |
| BR-09 declared vs observed | **PASS** (was PARTIAL) trigger `dependency` (`brain.json:13`) | **PASS** (was FAIL) `staleHours` 1.5 = CM = runtime 90 min; JM lists `GET /lakes` | **PARTIAL** (was FAIL) JM fixed; CM `executionTarget` is C2 (documented note; job-map entry is decision D-E) | **PASS** (was PARTIAL) `brain.json` consumes 5 Brains OPTIONAL = CM; catalog `plannedRole` is the planned design role | **PASS** (was PARTIAL) 8 providers declared = runtime fetchers (`PROVIDERS.json`, JM) | **PASS** (was PARTIAL) JM no longer declares the unread TVA archive | **PASS** consumes lake-brain (REQUIRED) + lakes registry = CM (P06) | **PASS** lake-brain OPTIONAL = CM provisional edge (P06) |
| BR-10 machine-local deps | **PASS** P16 + standing scan | **PASS** | **PARTIAL** — repo-relative polygon fallback outside the image (decision M-6) | **PASS** P16 | **PASS** standing scan incl. Swift sources | **PASS** | **PASS** P16 + standing scan; Lake contract replaces Swift-source parsing | **PASS** P16 + standing scan |
| BR-11 approved memory (2.1) | **PARTIAL** — verified bundle chain; approval NOT_RECORDED (M-3) | **PARTIAL** — packaged release verified on load (branch); approval NOT_RECORDED; production FAIL until deploy | **PARTIAL** — same as Wind | **PARTIAL** — same as Wind | **PARTIAL** — FNV fingerprint (M-7); approval NOT_RECORDED | **NOT_APPLICABLE** — no knowledge store (compiled model, live inputs) | **PARTIAL** candidate release verified on load; approval NOT_RECORDED → abstains (G-1) | **PARTIAL** same (G-1) |
| BR-12 privacy | **PASS** | **PASS** | **PASS** | **PASS** synthetic test species (`ea4577d3`) | **PASS** (was PARTIAL) synthetic presence examples (`ea4577d3`); history not rewritten | **PASS** | **PASS** no per-lake private data beyond the release | **PARTIAL** agency block internalOnly with species labels (V-1) |
| BR-13 versioned output contract | **PASS** | **PASS** | **PASS** | **PASS** (was FAIL) `intelligence-evaluation-v1.schema.json` validated on real output; publication contract | **PASS** (was PARTIAL) publication contract + `lake-state-v1` generated from the Swift record, validated on the recorded states | **PASS** (was PARTIAL) same: `water-temp-state-v1` | **PASS** `depth-publication-v1` + `depth-state-v1` | **PASS** `vegetation-publication-v1` + state contract |
| BR-14 evidence & provenance | **PASS** | **PASS** | **PASS** | **PASS** `provenance.brainVersion` now set (`c606f7d4`) | **PASS** | **PASS** | **PASS** provenance + release lineage | **PASS** |
| BR-15 confidence & uncertainty | **PASS** | **PASS** | **PARTIAL** | **PARTIAL** | **PARTIAL** | **PASS** (none calibrated; tested absent) | **PASS** sigma-based confidence; NOT_VALIDATED caps | **PASS** confidence capped under NOT_VALIDATED |
| BR-16 unknown / abstain | **PASS** + missing memory refuses (exit 2) | **PASS** + missing release refuses | **PASS** + missing release refuses; overlay degrades explicitly | **PASS** + missing release refuses | **PASS** + missing/refused presence writes nothing | **PASS** | **PASS** unknown datum/level → UNAVAILABLE; missing release → refuse | **PASS** submerged NOT_OBSERVABLE; missing release → refuse |
| BR-17 freshness & consumability | **PASS** | **PASS** | **PASS** | **PASS** (was PARTIAL) `sourceObservationAt` = oldest input | **PASS** | **PASS** (was PARTIAL) published schedule strings true (`11f18c1e`) | **PASS** fingerprint freshness | **PASS** |
| BR-18 domain + memory tests | **PASS** 400 (+5 memory) | **PASS** 220 (+5 memory) | **PASS** 131 (+4 memory) | **PASS** 96 (+5 memory) | **PASS** Swift (+7 memory, +2 bindings export) + Python 49 | **PASS** Swift + Python 50 | **PASS** 277 (+9 research-data tests skip without the snapshot; 298 pass with it) | **PASS** 171 |
| BR-19 structural certification | **PASS** P01–P19 | **PASS** P01–P19 | **PASS** P01–P19 | **PASS** (was FAIL) P01–P19 | **PASS** (was FAIL) P01–P13, P15–P19; P14 NOT_APPLICABLE (Swift writes) | **PASS** (was FAIL) same | **PASS** Kit P01–P19 | **PASS** Kit P01–P19 |
| BR-20 honest labels | **PASS** | **PARTIAL** — stale self-published score copy (Proposal B) | **PASS** | **PASS** (was PARTIAL) catalog `2026-10-20.1` | **PASS** | **PASS** (was PARTIAL) | **PASS** no score; research maturity not published | **PASS** no score; research maturity not published |

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
| PL-13 Pulse | **PASS (static)**; production NOT_VERIFIED | 2026-10-20 (Cortex 2.1): the standing scan finds no Sector Pulse, Mac or localhost execution target in Brain runtime/deploy code, the platform, the orchestrator or `Sources/SectorEngine` (`tools/architecture/tests/test_knowledge_memory_standing.py`); every production Brain runs as a Cloud Run job or in-process in the orchestrator. Live execution hosts need the read-only production check A-3 |
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

## Standing memory checks (Cortex 2.1, brains.md §5)

Source of truth: `docs/cortex/engineering-status/inputs/memory-standing-checks.json` (rendered here and into `engineering-status.json`). Each cell is **branch / production**. Production columns are judged from the code at the recorded deployed commit 7dae7051 (orchestrator image sha256:cb2e6922) or marked NOT_VERIFIED; no live image or bucket was inspected. The deployed lake-brain image (brain-jobs:a6622f99) is from feat/lake-consolidated, not main, so Lake production is NOT_VERIFIED.

| Check | Fish | Wind | Clarity | Intelligence | Lake | Water Temp | Depth | Vegetation |
|---|---|---|---|---|---|---|---|---|
| store-owner — Knowledge store and owner declared; research data never a runtime fallback | PASS / NOT_VERIFIED | PASS / FAIL | PASS / FAIL | PASS / FAIL | PASS / NOT_VERIFIED | PASS / PASS | PASS / NOT_APPLICABLE | PASS / NOT_APPLICABLE |
| developer-machine — No developer-machine, private research root or Claude session path in runtime or deploy code | PASS / PASS | PASS / PASS | PARTIAL / PASS | PASS / PASS | PASS / NOT_VERIFIED | PASS / NOT_VERIFIED | PASS / NOT_APPLICABLE | PASS / NOT_APPLICABLE |
| release-identity — Release id and digest verified on load and recorded in lineage | PASS / PASS | PARTIAL / FAIL | PARTIAL / FAIL | PARTIAL / FAIL | PARTIAL / NOT_VERIFIED | NOT_APPLICABLE / NOT_APPLICABLE | PARTIAL / NOT_APPLICABLE | PARTIAL / NOT_APPLICABLE |
| memory-unavailable — Missing or corrupt memory fails safe, degrades explicitly or abstains, with a test | PASS / PARTIAL | PASS / FAIL | PASS / FAIL | PASS / FAIL | PASS / NOT_VERIFIED | NOT_APPLICABLE / NOT_APPLICABLE | PASS / NOT_APPLICABLE | PASS / NOT_APPLICABLE |
| separation-approval — Research, operational state and publication separated; release approval record | PARTIAL / PARTIAL | PARTIAL / PARTIAL | PARTIAL / PARTIAL | PARTIAL / PARTIAL | PARTIAL / NOT_VERIFIED | PASS / PASS | PARTIAL / NOT_APPLICABLE | PARTIAL / NOT_APPLICABLE |
| pulse-independence — Runtime does not depend on Sector Pulse, a Mac or localhost | PASS / PASS | PASS / PASS | PASS / PASS | PASS / PASS | PASS / NOT_VERIFIED | PASS / NOT_VERIFIED | PASS / NOT_APPLICABLE | PASS / NOT_APPLICABLE |

Evidence per cell is in the JSON and in `engineering-status.json`.

## Per-Brain evidence records (brains.md §8)

Items 12–14 are NOT_APPLICABLE for every Brain (no production-live, Ops-live or customer-recommendation claim).

| # | Item | Fish | Wind | Clarity | Intelligence | Lake | Water Temp | Depth / Vegetation |
|---|---|---|---|---|---|---|---|---|
| 1 | Identity & one implementation | PASS | PASS | PASS | PASS | PASS | PASS | PASS / PASS |
| 2 | Ownership & Intelligence boundary | PASS | PASS | PASS | PASS | PASS | PASS | n/a |
| 3 | Research separation & lineage | PASS | PASS | PASS | PASS | PASS | PASS | blocked (reads docs/research) |
| 4 | Declared vs observed inputs | PASS | PASS | PARTIAL | PASS | PASS | PASS | n/a |
| 5 | Versioned contracts, unknowns, freshness | PASS | PASS | PASS | PASS | PASS (state schema generated) | PASS (state schema generated) | n/a |
| 6 | Domain tests & Kit proofs | PASS / 19 | PASS / 19 | PASS / 19 | PASS / 19 | PASS / 18 + P14 N/A (Swift write gate) | PASS / 18 + P14 N/A (Swift write gate) | PASS / 19 each |
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
| Depth | Canonical, Kit 19/19 | NOT_VALIDATED; candidate release unapproved (G-1) | PROFILED, PARKED, `kind: none`; abstains | none |
| Vegetation | Canonical, Kit 19/19 | NOT_VALIDATED (gates failed); candidate release unapproved (G-1) | SHADOW, PARKED, no live writer | none |

## Firebase data requirements (FD, Cortex 2.2.0 @ ae59e2d)

- **Evaluated:** 2026-10-21 (audit) and re-evaluated 2026-10-21 (remediation, code at `3e8a3857`) in `sessions/2026-10-21-cortex-2-2-firebase-data-audit.md` §10.
- **Evidence:** the production export (never committed), narrow read-only live reads, source, and the RTDB emulator.
- **Scope:** the rows are platform-wide, because the RTDB is shared.

| FD | Requirement | Status | Evidence / remaining |
|---|---|---|---|
| 01 | Registered contracts | PASS (Engine) / PARTIAL (Cortex registry) | Every production family is classified (`verification/firebase/tests/path_families.json`). Every Brain's `brain.json` declares its full runtime write set (`legacyDirectWrites`; per-Brain `test_declared_write_set.py`). Cortex registry corrections are proposed (`docs/cortex/firebase/REGISTRY_CORRECTION_PROPOSAL.md`) |
| 02 | Stable Brain keys | PASS | Stable ids everywhere. No `/brains/fish` and no alias (export, live, tests, emulator) |
| 03 | One authoritative writer | PASS with LEGACY | Ownership equals the classification. The scorer is the only `/scores` writer (tested). LEGACY copies are labelled or switchable: Wind frozen evidence (`authoritative:false`), `/engine/score` (same object). `/jobs` ledger record owned |
| 04 | Declared read-only consumers | PARTIAL | Ops is read-only (rules plus emulator). Ops reader changes OPS-1 to OPS-4 are handed off (`docs/cortex/firebase/OPS_CONSUMER_HANDOFF.md`) |
| 05 | Versioned schemas | PARTIAL | `brain.schema.json` gains additive `legacyDirectWrites`. The Lake registry contract accepts the deployed fields. Old production Clarity states predate `freshness{}` |
| 06 | Compatible evolution | PASS (source) | All remediation changes are additive or switch-guarded. NOT_VERIFIED in production |
| 07 | Provenance and freshness | PASS (source) / NOT_VERIFIED (production) | The platform rollup derives staleness by FLAG or policy AGE (`staleSlots`, `staleRule`). `healthBasis` and `healthCurrent` added. Observation, publication and projection times are distinct. Production shows it after an orchestrator deploy (A-2) |
| 08 | Honest absence | PASS | Vegetation INACTIVE_EXPECTED, engineeringStatusV1 PUBLICATION_INACTIVE, `/brains/fish` NOT_REGISTERED (tested) |
| 09 | Separate measurements | PASS (source) | The Wind copy is labelled `FROZEN_VALIDATION_EVIDENCE` and points to `/scores/wind`. Values unchanged; retirement gated (C-1) |
| 10 | Data placement | PASS | RTDB holds references and digests only |
| 11 | Access and classification | **DECISION REQUIRED** | PRIVATE `speciesPresence` is readable by every allowlisted Ops user (emulator). A least-privilege proposal is emulator-tested. The owner decides; the rules change is gated. IAM NOT_VERIFIED |
| 12 | Idempotent, ordered publication | PASS (source) / NOT_VERIFIED (production) | Unchanged. Orphaned parents deprecated, with a deletion plan |
| 13 | Honest publication state | PASS | O-1 off; nothing published by CI or merge |
| 14 | Verification | PASS (tests) / PARTIAL (data-check) | 23 Firebase tests (3 need the emulator), per-Brain write-set tests, architecture gate. All suites green at `3e8a3857`. `data-check`: 495 findings = registry gaps plus scanner limits (CG-2.2-3); 0 new code defects |

## Internal Brain operations (IO, Cortex 2.5.0 @ c9f6467)

Evaluated 2026-10-22 · `sessions/2026-10-22-internal-activation.md`. The status document is `operations/brain-operations-status-2026-10-22.json` (ops-check validated).

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| IO-01 | Four independent dimensions | **PARTIAL** | Reported separately in the status document. The legacy `operationalReadiness` label in `engineering-status-ops-v1` stays BLOCKED for Depth and Vegetation on scientific approval, so `ops-check` reports CONFLATED_READINESS ×2. Redefining that consumer-read label is decision-required: D-IA-2 |
| IO-02 | Declared modes, INTERNAL required | PASS | `brain.json` `operations.executionModes` in all 8; Depth/Vegetation INTERNAL (shadow) + APPROVED_SCIENCE (refuses) |
| IO-03 | Knowledge states separated | PASS | Candidate releases are packaged, digest-verified artifacts, never loaded as approved. Shadow output carries `knowledgeState: CANDIDATE` and the candidate id and digest |
| IO-04 | Refusal preserved | PASS | `run.py --write` of Depth/Vegetation still refuses (BLOCKED_AWAITING_APPROVED_RELEASE); shadow summaries record `approvedPath: ABSTAIN` |
| IO-05 | Marked outputs, never to customer / pointers / scores | PASS | `lane: INTERNAL_EXPERIMENTAL`, `experimental: true`. `shadow_lane.problems()` refuses mislabelled or APPROVED documents. Scorer and Intelligence never read `/control/shadowLaneV1` |
| IO-06 | Isolated internal publication | **PARTIAL** | Every family is INTERNAL lane. `/control/shadowLaneV1` is not yet in the Cortex registry (CG-2.5-1) |
| IO-07 | Honest partial capability | PASS | Vegetation: 0 observed lakes, all `unavailable`, no invented observations. Depth: DEGRADED, no invented contours. Intelligence marks stale inputs and gives no recommendation |
| IO-08 | ACTIVE = enabled trigger + observed execution | PASS | Executions observed for all 6 ACTIVE and both SHADOW Brains (session §5); orchestrator scheduler ENABLED 06:48Z, scheduled cycle 06:50Z |
| IO-09 | Separate measurements; activation never raises a score | **DECISION REQUIRED** | Brain capability scores unchanged. Engine score 7.0 → 7.2 through `engine-score-v1` `platformHealth` (operational conformance), not overridden: D-IA-1 |
| IO-10 | Customer eligibility | PASS | NOT_ELIGIBLE for all 8; `customerPublication: false`; PRE_PRODUCTION |
| IO-11 | Ops displays, never approves | PARTIAL (Ops project) | Rules unchanged; Ops is read-only. The four dimensions and the shadow lane are not yet displayed in Ops (Ops follow-up) |
| IO-12 | `operations` block in every `brain.json` | PASS | `ops-check --repo`: 0 findings |

### IO re-evaluation (Cortex 2.6.0 @ 7293d01, 2026-10-22 · `sessions/2026-10-22-final-operational-integration.md`)

| ID | Status | Evidence |
|---|---|---|
| IO-01 | PASS | engineering-status-ops-v1 1.2.0: every Brain carries `operations` {runtimeReadiness, internalOperation (live), scientificValidation, customerEligibility}; the legacy `operationalReadiness` layer is kept and documented as RELEASE_READINESS (D-IA-2 Option B); `ops-check --status` on the converted live document: 0 findings |
| IO-06 | PASS | `/control/shadowLaneV1` registered as `fam.control-shadow-lane` (Cortex 2.6.0; CG-2.5-1 closed) |
| IO-08 | PASS | ACTIVE only with an enabled trigger and a successful execution within 1.5 x the interval (input/dependency-driven Brains: the runtime's own hourly plan check, labelled PLAN_CHECK, with the last full run beside it); SHADOW only with a shadow run within its cadence (`sector_brain_platform/brain_operations.py`, tests) |
| IO-09 | PASS | D-IA-1 Option A: `/scores/engine` classified ENGINEERING_SCORE (not capability); Brain `/scores/{id}.value` SCIENTIFIC_MATURITY; Wind `windCapability` DOMAIN_CAPABILITY; no score changed by this work |
| IO-11 | see Sector Ops | four-dimension display shipped in Sector Ops (same mission) |

## Central Brain scheduling (Cortex 2.7.0 @ ebc7fb9, 2026-10-23 · `sessions/2026-10-23-central-scheduling.md`)

| ID | Status | Evidence |
|---|---|---|
| PL-15 | PASS | `brain-orchestrator` is the only scheduler in the execution manifest and the schedule policy; Wind and Lake are orchestrator-started (`wind-hourly`, `lake-brain` jobs); their schedulers are deprecated and PAUSED; all 8 Brains registered (test_central_scheduling) |
| PL-16 | PASS | `/control/executionControlV1` (owner CLI); absent / unreadable / invalid / ENABLED-without-approvalRef = PAUSED; PAUSED stops workers, plan checks and the shadow lane; status shows PAUSED |
| PL-17 | PASS | single-flight, no overlapping cycles, maxStartsPerCycle (no catch-up burst), maxRunsPerDay, maxCostPerDay, bounded retries (tests, mutation-checked) |
| PL-18 | PASS | no deploy script creates or resumes a scheduler; the orchestrator deploy always pauses its trigger and fails otherwise; resuming only via `tools/ops/resume-orchestrator.sh` with an owner approvalRef |
| BR-21 | PASS | `operations.execution` in all 8 `brain.json`; `ops-check --repo` 0 findings |
