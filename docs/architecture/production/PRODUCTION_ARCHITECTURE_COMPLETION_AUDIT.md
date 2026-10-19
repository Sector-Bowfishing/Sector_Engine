# PRODUCTION ARCHITECTURE COMPLETION AUDIT (V1)

**Baseline:** `origin/main` = `a26febb8d3c7c249e8bddcfee0ed9b4c6ce5cb29` (fetched; no drift from the handoff). **Mode:** read-only audit + repo preparation. **Nothing was deployed, run against production, or mutated.** Public-safe: no identity names, bucket names, IAM detail or per-lake species presence (those stay in the private handoff).
**Method:** code is truth; docs are claims. Findings come from three independent code readings (Publisher; Wind+Fish; Water Clarity+platform) with file:line citations kept in the private session notes. Deployed behaviour was NOT observable from the repo; where a statement concerns live state it is labelled DOC-CLAIM. Tests were run with a minimal local pytest shim because `pytest` is not installed on this machine; counts below are shim-derived and must be re-confirmed by CI.

## 0. Verdict
| Question | Answer |
|---|---|
| Is the Publisher technically ready for production cutover (Wind / Fish / Water Clarity)? | **NO, for all three.** It is SHADOW-only: `PublisherMode` has `SHADOW` and `DRY_RUN` only; the only sink is the in-memory `ShadowSink` (`live_mutations` is a constant 0, enforced by import lint and boundary tests); no live sink, no GCS adapter, no atomic live apply, no rollback executor, no release resolver. |
| Is the shadow Publisher *correct* as far as it goes? | Yes. Registration for all three Brains, validators, path ownership (`/scores`, `/control`, `/jobs`, `/engine`, `/brains/*/publication|certification` blocked), semantic fingerprint v2, SKIP, ordering, immutable artifact ids, optimistic head advance: implemented and tested (335 publisher tests pass under the shim). |
| Is the Brain architecture finished enough to focus on domain knowledge / scores? | **YES for the Brain-side structure** (canonical package, contract, artifact builder, registration, kit proofs, AST write pins). **NO for production publication**: all three Brains still publish through their legacy direct writers and will keep doing so until a Publisher LIVE build exists. Score work does not need that to proceed: the legacy writers are working (Fish 5.1 proved it). |
| `ARCHITECTURE_CERTIFIED_V1` available? | **No, for any Brain.** See section 7. |
| One shared change that unlocks all three? | **Yes: a Publisher LIVE build (P1, P3, P4, P5, P6, P12 + P2 adapter) plus the write-security gate (exit evidence F).** Wind and Water Clarity additionally need the Orchestrator items G1/G2 (see 5.3). Everything else is per-Brain, small. |

## 1. Per-Brain matrix (the 20 requested facts)
| # | Fact | Wind | Fish (`biological-state`) | Water Clarity |
|---|---|---|---|---|
| 1 | canonical runtime | `brains/wind/runtime` | `brains/fish/runtime` (`run.py`) | `brains/water-clarity/runtime` (`run.py`, C1) |
| 2 | canonical artifact | `wind-publication-v1` (builder `artifact.py`, NOT wired to `main.py`) | `fish-publication-v1` (`publish_artifact.py`; built only in `--dry-run`) | `clarity-publication-v1` (`publish_artifact.py`; built in memory beside direct writes) |
| 3 | Publisher registration | registered | registered | registered (tested only through its own brain suite; no dedicated platform test file) |
| 4 | Publisher mode | SHADOW | SHADOW | SHADOW |
| 5 | production writer | hourly scheduled job (legacy) -> one multi-path PATCH per call | orchestrator in-process `run.py --write` (legacy; scheduler normally paused, so effectively manual) | `run.py` C1, MANUAL; nothing schedules C1 |
| 6 | direct-write sites | RTDB: one `update` call site pinned (`writer.py`); ~8 logical write groups (lake state/profile/validation, snapshot copies, fleet readiness/ids, whole-node `brains/wind`, `validation/wind`, `sources`, `health/*`, activity + prune). GCS archive writes | RTDB: exactly one (`run.py` `rtdb.update`): `/species/*` (incl. deletes), `/brains/biological-state` (whole node), `/validation/..`, `/health/brains/..` (whole node), activity. No GCS writes in repo (release bucket written out of band) | RTDB: 2 sites in `run.py` (batch write; abort path), incl. whole-node `/brains/water-clarity`, `/health/brains/water-clarity`, `/health/jobs/..`. C2-C4 write GCS only |
| 7 | path ownership | see 3 | see 3 | see 3 |
| 8 | health ownership | legacy self-authored + healthV1 | legacy self-authored + healthV1 | legacy self-authored + healthV1 |
| 9 | score ownership | scorer (frozen score doc) | scorer computes from live published facts | scorer (research score 8.0, FROZEN) |
| 10 | lifecycle ownership | brain.json CALIBRATION; Publisher rejects PRODUCTION without approval | PROFILED | CALIBRATION |
| 11 | actual-consumption lineage | NONE recorded by the legacy writer (no recorder attached); real reads: Engine `/lakes` over HTTP, providers, own GCS, RTDB `/activity` | RTDB own/platform nodes only (recorder ignores own nodes); GCS bundle read via raw HTTP, outside recorder | NOT_RECORDED (HTTP Engine reads, GCS, Cloud Run API, local catalog) |
| 12 | declared-consumption lineage | registry:lakes + 3 providers | `consumes: []` (the pilot `run_state.py` reads `snapshots/*/latest` undeclared; unscheduled) | `registry:lakes` only |
| 13 | freshness ownership | Wind-authored (`lastSuccessfulRun`, `staleAfterHours`); target = Publisher freshness + Orchestrator execution freshness (G5 closed: no republish heartbeat) | version-driven (`plan()` reads published `researchVersion`/`manifestSha256`/`version`/`health`) | manual run; cadence `NOT_EXPECTED`; Brain-authored `lastSuccessfulRun` is read by the Orchestrator (scoring trigger) |
| 14 | rollback | none for RTDB (redeploy prior image; state self-heals hourly) | repoint release pointer to previous release (object-versioned bucket) then republish; under the Publisher this is rejected as `ARTIFACT_OLDER_THAN_BASELINE` until P5 | none |
| 15 | readback | none (PATCH is `print=silent`) | next `--plan` compares published release to pointer; `--write` prints counts only | none |
| 16 | legacy seams | `/snapshots/*/latest/wind`, `brainVersions/wind`, `lakeId` fields, `readiness/wind` (621 rows/run), `health/jobs/wind-hourly`, `lastSuccessfulRun`, registry `scores` mirror | whole `/species` root (incl. deletes), `/health/brains/..` process fields, `lastSuccessfulRun` | snapshot projection (reader inventory unverified), whole-node `brains`/`health`, `lastSuccessfulRun` |
| 17 | deploy/scheduler relation | own scheduler job at :05 (approved VALIDATION_EXCEPTION, re-decide ~2026-11-08); deployed image is older than HEAD (DOC-CLAIM) | orchestrator hourly job, scheduler PAUSED (DOC-CLAIM) | jobs PAUSED; C1 unscheduled |
| 18 | if legacy writer retired (no Publisher) | all Wind state/Ops/SI snapshot freeze; stale within 1.5-6 h | no new releases reach RTDB; `--plan` would loop PUBLISH if the orchestrator still calls the write | nothing reaches RTDB (Brain is CALIBRATION, manual; low impact) |
| 19 | if Publisher became production as-is | process health + `health/jobs` vanish (G1); `lastSuccessfulRun` stale on SKIP (G2); no new-lake `lakeId` (G4); no activity prune (G3); first publish after unreconciled baseline = full-rewrite risk (P4/P12) | process health fields vanish (orchestrator exec records cover in-process runs); stale-child clearing only via typed DELETE; older-release rollback blocked (P5) | process fields vanish (G1); stale children persist unless typed DELETE; artifact size vs `max_bytes` for 621 lakes unchecked |
| 20 | exact blocker to production cutover | P1-P6, P12 (no live Publisher) + write-security gate + G1-G4 + producer not wired + 8 MiB artifact limit vs fleet scale (needs manifest-last P3) | P1-P6, P12 + write-security gate + no artifact emission path in `run.py` + shared writer identity cannot be removed by IAM alone + decisions D-1, D-3 | P1-P6, P12 + write-security gate + G1 + retire whole-node writer in the SAME change as go-live + nothing schedules C1 |

## 2. Publisher readiness (proof, by area)
`IMPL+TEST` = implemented and tested in shadow. `MISSING` = not in the repository.
| Area | State |
|---|---|
| registry / schemas (P9) | IMPL+TEST for all three Brains; builders import their bundle/schema constants from the registry (match by construction) |
| validators, planner, path ownership | IMPL+TEST; validation completes before any plan exists |
| fingerprint / SKIP / ordering / idempotency | IMPL+TEST (`sector-semantic-fingerprint-v2`; SKIP compares against the last SHADOW_READY, **not** live state) |
| lifecycle | IMPL+TEST; PRODUCTION lifecycles rejected without `approvalRef`; none authorised |
| publication metadata | planned in the plan dict, never applied; live statuses `COMPLETE`/`PARTIAL` do not exist |
| atomicity | MISSING (plan is one multi-location dict but only rendered); manifest-last for oversize: MISSING (artifacts over 8 MiB are rejected) |
| baseline | per-section head advance in a loop (P12 open: mixed baseline possible on a lost race); live reconciliation (P4) MISSING |
| rollback | MISSING (`rollback_reference` returns identifiers only; no validator path accepts an older artifact) |
| release resolver (P6) | MISSING (parameter plumbed, nothing implements it; Fish release check is well-formedness only) |
| storage | `MemoryObjectStore`, `LocalDirObjectStore` only; GCS adapter (P2) MISSING |
| health integration | reader exists; no live producer; publish health is UNKNOWN until a publication record exists |
| score interaction | none by design: `/scores` is blocked to the Publisher |
| API / handoff (P7/P8) | partial: contract + in-memory handoff; no authenticator, allowlist, dispatcher, deployment |
| P1-P12 | done: P9. partial: P7, P8. open: P1-P6, P10, P11, P12 |

## 3. Production write ownership
Taxonomy: SPEC=SPECIALIST_DOMAIN_TRUTH, PROJ=PUBLISHER_PROJECTION, PLAT=PLATFORM_OWNED, ORCH=ORCHESTRATOR_OWNED, SCORE=SCORE_SYSTEM_OWNED, HEALTH=HEALTH_SYSTEM_OWNED, LEG=LEGACY_TRANSITIONAL.
| Path family | Wind | Fish | Clarity | Class / collision |
|---|---|---|---|---|
| `/lakes/{k}/states|profiles|validation/<brain>` | W | - | - | SPEC. validation null-delete on lookup miss (Publisher uses typed DELETE) |
| `/lakeFleet/{k}/readiness|slots|modelVersions/<brain>` | W | - | W | PROJ (Brain-authored today) |
| `/lakeFleet/{k}/lakeId`, `/snapshots/{k}/latest/lakeId` | W | - | W | **PLAT but writable by any Brain (`ownership.py`): multi-writer COLLISION** |
| `/snapshots/{k}/latest/<brain>`, `brainVersions/<brain>` | W | - | W (projection) | PROJ -> LEG (readers: Ops, Sector Intelligence, Fish pilot) |
| `/brains/<id>` whole node | W | F | C | SPEC registry, **whole-node write clobbers reserved `publication`/`certification`**; embeds process facts (LEG) and a `scores` mirror (duplicate) |
| `/validation/<id>` | W | F | - | SPEC (Wind embeds duplicate scores) |
| `/species/{id}` | - | F | - | SPEC knowledge; **species identity belongs to the (empty) Species Registry; whole `/species` root incl. deletes is open to Fish** |
| `/sources/*`, `/health/sources/*` | W | - | - | SPEC (Wind is acquisition owner) |
| `/health/brains/<id>/{status,staleLakeCount}` | W | F | C | HEALTH domain facts, Brain-authored child-level (target) |
| `/health/brains/<id>/{lastRun,lastSuccess,durationMs,errorCount,latestError,deployedVersion,publishMode}` | W | F | C | **LEG -> ORCH (COLLISION with the health plane)** |
| `/health/jobs/<id>` | W | - | C | **LEG -> ORCH; duplicate of `/jobs/<id>`; any Brain may write any id** |
| `/activity/*` | W (+prune) | F | - | SPEC events; prune = PLAT (G3) |
| `/jobs/*`, `/control/*` (incl. `healthV1`), `/engine/*` | - | - | - | ORCH / PLAT; never Brain writes |
| `/scores/*` | - | - | - | SCORE (platform scorer only) |
| `/brains/<id>/score` | - | - | - | **SCORE cross-owner delete by the scorer with the ownership check disabled** |
| `/brains/<id>/publication|certification` | - | - | - | PUBLISHER/ORCH reserved; written by nobody today |
| GCS: Wind archive, Clarity C2-C4 artifacts, Fish release bucket | W | out-of-band | C2-C4 | SPEC (Brain-owned storage), see 6.8 |
No path has an UNKNOWN owner. Two-owner collisions: `lakeId` fields, `/health/jobs/*`, Brain process-health fields, whole-node `/brains/*` vs reserved children, `/species` identity, scorer delete into `/brains/*/score`, `lastSuccessfulRun` (Brain-authored, used by Orchestrator scoring trigger and legacy freshness).

## 4. Legacy writer retirement (exact)
Rule common to all three: **retire a writer only in the same PR that flips `cutoverStatus`, deletes the write site and removes its AST pin** (invariant 10 + `allowed_write_sites`), and only after the production exit gate (`PRODUCTION_EXIT_GATE_V1.md`) is PASS. Never delete first.
* **Fish:** one site (`run.py` `rtdb.update`). Retire after: Publisher LIVE + baseline from live; Fish artifact emission added beside `--write` (P8 Brain-side); parallel run (forced re-run) with zero unexplained diffs; decisions D-1/D-3; shared writer identity addressed (Orchestrator submits through the Publisher; IAM deletion alone cannot work). `--plan` stays (read-only).
* **Water Clarity:** whole-node replacement is the hazard. It must be replaced by child-level writes of the approved `/brains/water-clarity/{child}` set + `/health/brains/water-clarity/{status,staleLakeCount}` + typed DELETE for `lastError`, with `publication` written in the same atomic update. **The legacy `run.py` write must be removed at the moment the Publisher goes live for Clarity; running both would erase `publication`.** Because C1 is manual and unscheduled, this is a single-operator step.
* **Wind:** `RtdbWriter.patch` via `safe_publish` in `main.py`. Wire `artifact.py` additively after `safe_publish` in SHADOW first (no exit-code change), compare >= 7 days, land G1-G4, then flip in one PR. Snapshot/legacy path retirement is a separate 14-step procedure (reader migration), NOT required for cutover.

## 5. Score, health, lineage, debts
### 5.1 Score ownership (decision recorded)
**The scorer stays intentionally separate from the Publisher.** Publisher never touches `/scores`; the scorer (platform identity, `PLATFORM_ONLY` root, `guard_scores`) writes `/scores`, `/control`, `/engine/score`. It is run by the Orchestrator (`--write --if-changed`) when Brain registry `lastSuccessfulRun` changed, an in-process Brain published, or job records changed. **Design gap (PLATFORM_BLOCKING for Wind/Clarity cutover):** the Publisher leaves `lastSuccessfulRun` alone on SKIP and may not touch it on change, so a Publisher publish would not trigger scoring. Fix: trigger the scorer on a change of `/brains/<id>/publication.artifactId` (Orchestrator change, additive). Fish 5.1 publication used `run.py --write` then `score_brains.py --write` and must stay untouched until that trigger exists. Fish's score is computed from live published facts, so cutover must prove byte-equal registry/species/validation (golden baseline exists) or a score move is a regression.
### 5.2 Health ownership
healthV1 (Orchestrator `--health-only`, `control/healthV1`, Ops read-only) is the truth. Legacy Brain-self-authored `/health/brains/*` and `/health/jobs/*` are LEGACY_TRANSITIONAL and can become wrongly authoritative via: synthetic execution from a Brain-reported record (`from_health_record`), `lastSuccessfulRun` as legacy freshness, `control/overview` reading Brain-reported status, and Clarity's manual-run HEALTHY persisting indefinitely. Retirement plan: after G1 compat records, Brains stop authoring process fields (already true in the shadow artifacts); only `{status, staleLakeCount}` stay Brain-authored child-level.
### 5.3 Platform items required by cutover
G1 Orchestrator job/execution health compat records; G2 execution freshness from Orchestrator records (not `lastSuccessfulRun`); G3 activity retention; G4 Lake Registry `lakeId` publisher; S1 scorer trigger on publication (new, section 5.1). G5/G6 closed.
### 5.4 Debt classification (every remaining item has exactly one class)
| ID | Item | Class |
|---|---|---|
| PUB-1 | Publisher LIVE: P1 LiveSink/mode, P3 atomic apply + manifest-last, P4 baseline reconciliation, P5 rollback executor, P6 release resolver, P12 transactional baseline | **PLATFORM_BLOCKING** |
| PUB-2 | P2 GCS ObjectStore adapter (needs bucket approval) | **PLATFORM_BLOCKING** |
| PUB-3 | P7 authenticated Orchestrator API + P8 reference handoff completion | **PLATFORM_BLOCKING** (the door cannot be sole writer without it) |
| SEC-1 | Write-security gate: rules + IAM write denial, tested (exit evidence F); shared Brain writer identity split | **PLATFORM_BLOCKING** (for `ARCHITECTURE_CERTIFIED_V1`; not for first live cutover of one Brain, which needs only Michael's approval) |
| SEC-2 | `ownership.py` lets any Brain write `lakeId` fields and `/health/jobs/*`; scorer deletes `/brains/*/score` with ownership off | **SHARED_PLATFORM_DEBT** (must close before SEC-1 test X04/X16) |
| PLAT-1 | G1, G2, G3, G4, S1 | **PLATFORM_BLOCKING** for Wind and Clarity; G1 only partly for Fish (exec records exist in-process) |
| WIND-1 | Wire `artifact.py` into `main.py` additively (shadow submission) | **BRAIN_BLOCKING** |
| WIND-2 | 621-lake artifact vs 8 MiB `max_bytes`: choose granularity or rely on manifest-last | **BRAIN_BLOCKING** |
| WIND-3 | Deployed image older than HEAD; reconcile before any change (shared-orchestrator lineage rule) | **BRAIN_BLOCKING** (gate item, not a code task) |
| WIND-4 | `wind-hourly` VALIDATION_EXCEPTION re-decision ~2026-11-08 | **NON_BLOCKING_DEBT** (dated decision) |
| FISH-1 | No artifact emission path in `run.py` beyond `--dry-run` | **BRAIN_BLOCKING** |
| FISH-2 | Decisions D-1 (pilot input declarations) and D-3 (cutover) | **BRAIN_BLOCKING** (decisions, Michael) |
| FISH-3 | Species identity boundary (Species Registry empty) | **PARKED_BY_DESIGN** (Fish keeps `/species` summary; identity move is a later registry task) |
| FISH-4 | Fish pilot reads `snapshots/*/latest` undeclared | **NON_BLOCKING_DEBT** (pilot is unscheduled) |
| FISH-5 | `BIOLOGICAL_BRAIN_INTEGRATION.md` says "no scheduled job" (orchestrator runs it when enabled) | **NON_BLOCKING_DEBT** (doc fix) |
| FISH-6 | Registry `discrepancies` publishes per-lake fields to private RTDB; confirm none enters the public repo | **NON_BLOCKING_DEBT** (check before any export) |
| CLAR-1 | Retire whole-node writer at Publisher go-live; child-level replacement | **BRAIN_BLOCKING** |
| CLAR-2 | Nothing schedules C1 (manual) | **PARKED_BY_DESIGN** (CALIBRATION) |
| CLAR-3 | Snapshot-projection reader inventory unverified | **NON_BLOCKING_DEBT** (gates only projection retirement) |
| CLAR-4 | No dedicated platform-side Clarity Publisher test | **NON_BLOCKING_DEBT** |
| LIN-1 | GCS/HTTP actual-consumption capture | **SHARED_PLATFORM_DEBT** (see 6.6) |
| RA-20 | Clarity reads Engine `/lakes`, `/conditions` through the customer API | **SHARED_PLATFORM_DEBT** (see 6.7) |
| GCS-1 | Clarity C2-C4 GCS artifact writes | **PARKED_BY_DESIGN** (see 6.8) |
| VER-1 | Shadow baseline is last SHADOW_READY, not live (P4) | folded into PUB-1 |
| ENV-1 | `pytest` not installed on the developer machine | **NON_BLOCKING_DEBT** (CI installs it) |

## 6. Key questions: firm answers
1. **Publisher readiness:** not ready; section 2.
2. **Write ownership:** section 3; no UNKNOWN; collisions listed.
3. **Legacy retirement:** section 4; nothing is deleted by this work.
4. **Score ownership:** separate; add publication-triggered scoring (S1); section 5.1.
5. **Health ownership:** healthV1 is authoritative; legacy Brain health is LEGACY_TRANSITIONAL; section 5.2.
6. **GCS/HTTP actual-consumption lineage: does NOT block production architecture** (SHARED_PLATFORM_DEBT). The Publisher excludes `consumed` from the fingerprint; Wind already runs without it; absent/`NOT_RECORDED`/`UNKNOWN` are honest states. **Standing rule: never publish `consumed: []` alongside HTTP/GCS inputs** (empty means "nothing consumed", absent means "unknown"); Clarity passes `None`. It is a precondition for claiming *actual* lineage complete, not for cutover.
7. **RA-20:** A) does NOT block Water Clarity production Publisher cutover (not in P1-P12; the Brain stays CALIBRATION). B) is **not part of exit evidence A-J**, so it does not formally block `ARCHITECTURE_CERTIFIED_V1`; it is a recorded ownership violation, so **Michael must decide: waive with an expiry, or require removal first**. C) Non-blocking shared debt in class terms. D) **Not required before Brain #4**; required before Clarity leaves CALIBRATION or serves anything customer-adjacent. Not implemented here.
8. **GCS write semantics:** C2-C4 are legitimate specialist-pipeline storage (Brain-owned classes). **Keep them outside the RTDB Publisher** (PARKED_BY_DESIGN). They need Publisher *metadata only*: a reference/fingerprint of the evidence restated in the artifact lineage, and `/jobs` records. An RTDB rollback does not roll GCS back; the exit-gate rollback check is therefore scoped to Publisher-owned RTDB paths. (C3/C4 source is not on this branch; their internals are DOC-CLAIM.)

## 7. `ARCHITECTURE_CERTIFIED_V1` (existing definition; nothing invented)
Source: `docs/architecture/certification/BRAIN_CERTIFICATION_V1.md` s4/s6: status requires **all exit evidence A-J present and reviewed by Michael**; D-12 (`ARCHITECTURE_AUDIT_1_REPORT.md`) reserves the name until **a live Publisher and exit evidence F** exist; `BRAIN_FACTORY_V1.md` s9 adds: tested write-denial under rules AND IAM, reader migration, and a rollback exercise.
**Exit evidence F** = "tested denials: specialist write denied; Ops write denied; cross-domain write denied. Tested success: Publisher authorized write. Both rules and IAM covered." (details private; repo records pass/fail). **G** = valid artifact succeeds, same fingerprint SKIPs, invalid schema rejected, cross-domain path rejected, stale input represented correctly, partial publish impossible (or manifest-last proven), rollback verified end to end.
| Evidence | Wind | Fish | Clarity | Remaining |
|---|---|---|---|---|
| A identity, B-C inventories, D matrix, E code trace | per each Brain's certification record (not re-verified here) | same | same | none identified by this audit; B backup approvals (CERT-3/4) pending for Wind |
| F security | FAIL | not achieved | not achieved | SEC-1, SEC-2, PUB-3 |
| G publication tests | offline/shadow only | offline/shadow only | offline/shadow only | live atomic publish + rollback (PUB-1) |
| H score before/after | n/a until cutover | must be byte-equal | n/a | per Brain at cutover |
| I downstream regression | n/a | n/a | n/a | at cutover (`/conditions` diff = none, Ops, SI) |
| J Michael review | n/a | n/a | n/a | after F, G |
The reusable gate that makes F, G, H, I checkable per Brain is `PRODUCTION_EXIT_GATE_V1.md` (kit module `exit_gate.py`).

## 8. Recommended sequence
1. **Publisher LIVE V1 (Platform lane, repo-only, offline-testable with fake RTDB/GCS clients):** P12 transactional baseline -> P5 rollback path -> P3 atomic apply + manifest-last -> P6 release resolver -> P1 LiveSink in a separate module + P2 GCS adapter (adapter bucket creation needs approval). Add S1 (publication-triggered scoring) and close SEC-2 in the same lane.
2. Orchestrator items G1-G4.
3. Security gate SEC-1 design -> Michael approval -> rules/IAM (private).
4. Per-Brain, in this order (recommendation): **Water Clarity** (manual, CALIBRATION, lowest blast radius, clean pilot), **Fish** (single write site, rare version-driven publishes, release-pointer rollback), **Wind** (hourly, 621 lakes, most seams; last). Each cutover = its own approved runbook (`PRODUCTION_CUTOVER_PLANS_V1.md`).
5. `ARCHITECTURE_CERTIFIED_V1` per Brain after the exit gate PASSes and Michael reviews.
**Can score work proceed in parallel now? Yes.** Nothing above changes domain truth, and legacy writers are working.

## 9. What this change set contains
`tools/brain_certification/brain_cert_kit/exit_gate.py` + `tests/test_exit_gate.py` (data + pure evaluator; no I/O; not part of the 19 structural proofs); these three documents. No runtime, contract, artifact, score or deploy change. No production access.
