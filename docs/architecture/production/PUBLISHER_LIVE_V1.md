# PUBLISHER LIVE V1 — production publication door (repository implementation; NOTHING ENABLED)

**Status: `PUBLISHER_LIVE_V1_READY_FOR_REVIEW` (repository + fake-client tests).** No production mutation, no deploy, no IAM/rules/scheduler change, no legacy writer retired, no Brain cut over. Governing audit: `PRODUCTION_ARCHITECTURE_COMPLETION_AUDIT.md`; plans: `PRODUCTION_CUTOVER_PLANS_V1.md`; gate: `PRODUCTION_EXIT_GATE_V1.md`.

## Where it lives
`jobs/brain_platform/sector_brain_platform/publisher_live/` — a SIBLING of the SHADOW package `publisher/`, which is unchanged (its no-live-I/O import lint, `PublisherMode` without a live member and `Result` without PUBLISHED all still pass). The live package reuses the shadow validators, planner, registry and fingerprints (run in `DRY_RUN`, which persists nothing). Nothing imports it (a test pins that; the platform `__init__`, the shadow package and the Orchestrator do not), and no module reads the environment.

## P-item mapping (definitions: `PUBLISHER_V1_CUTOVER_REQUIREMENTS.md` section 1)
| P | Definition | Status | Where |
|---|---|---|---|
| P1 | live sink + live mode in a separate module | **REPO_DONE (fake-tested)** | `publisher.py` `LivePublisher` (the sink: apply + verify + record), `rtdb_client.py` `RtdbRestPublisherClient` (production RTDB adapter, **refuses to construct unless `armed=True`**; nothing passes it), `authorization.py` (per-Brain allow-list, empty by default) |
| P2 | GCS artifact/history ObjectStore adapter | **REPO_DONE (fake-tested); bucket creation NOT done** | `gcs_store.py` `GcsObjectStore` (same contract as the memory store, no delete method, `from_bucket_name` refuses unless armed) |
| P3 | atomic live update + manifest-last | **REPO_DONE** | `apply.py`: one multi-location update; oversize plans chunked data-first with the publication marker alone in the LAST write and a `publication/pending` marker before |
| P4 | baseline reconciliation from live | **REPO_DONE** | `baseline.py` + `LivePublisher.baseline_diff / acknowledge_baseline`: GET-only diff, deliberate acknowledgement with an approval reference; shadow-era heads are invisible to live comparison (`_LiveHistory`) so an artifact is never SKIPPED against a never-live baseline |
| P5 | rollback execution | **REPO_DONE** | `LivePublisher.rollback`: re-applies the previous immutable artifact in full + typed deletes for paths only the rolled-back release wrote; readback-verified; clears a quarantine only when verified |
| P6 | release resolver | **REPO_DONE; production reader not wired** | `release_resolver.py` `ManifestReleaseResolver(reader)` (hash + release identity, fail closed) |
| P7 | Orchestrator API service | **NOT DONE (deployment/identity work)**; reference flow is the only input of `LivePublisher.publish(ArtifactRef)` | existing `publisher/api.py`, `handoff.py` |
| P8 | Brain artifact handoff | **repo contract unchanged; Brain-side emission still per-Brain work** (Wind/Clarity build artifacts, Fish only in `--dry-run`) | |
| P9 | schema registrations | already done (Wind, Fish, Clarity) | |
| P10 | certification record write | NOT DONE (reserved child stays unwritten; tested to survive) | |
| P11 | monitoring/cost | NOT DONE (needs a deployed service) | |
| P12 | transactional baseline | **mitigated, not removed**: heads advance only after a verified live apply, under a per-Brain apply lock (generation-matched create/overwrite), compare-and-swap per head; a lost race QUARANTINES the Brain instead of leaving a mixed baseline silently | `locks.py`, `publisher.py` |
| S1 | publication-triggered scoring | **REPO_DONE** | `publication_trigger.py` + one additive line in `jobs/brain-orchestrator/orchestrate.py` |
| SEC-1 | write-security gate | **REPO_READY only** (`LIVE_SECURITY_VERIFIED` = no) | `security_model.py`, `platform/security/*` |
| SEC-2 | multi-writer collisions | **inventory pinned + Publisher never writes them**; legacy ownership table deliberately UNCHANGED (would break the working legacy writers) | `security_model.py` |

## LivePublisher flow (fail closed at every step)
authorization → quarantine → shared validation (DRY_RUN) → SKIP on unchanged → baseline reconciled → per-Brain apply lock → live precondition (live `publication.artifactId` == the baseline's) → publisher key guard → apply (single or manifest-last) → authoritative readback → immutable record + head advance (generation-matched) → S1 score signal.
* **Ownership.** `security_model.publisher_key_allowed` independently refuses `/scores`, `/control`, `/engine`, `/jobs`, `/access`, `/schemaVersion`, `/controlRequests`, `health/jobs|engine|rtdb`, `brains/<id>/score`, lake-identity fields, Orchestrator health fields and any other Brain's paths.
* **Idempotency.** Same artifact again → SKIP. A verified apply whose process died before the head moved → `RECOVERED` (no second write, finished under the original publishId).
* **Ambiguous outcomes** (lost response) are never assumed: readback decides. A readback mismatch quarantines the Brain; only a verified rollback releases it.
* **Atomicity honesty.** RTDB has no multi-location compare-and-set. Serialisation is the per-Brain lock in the versioned store plus the pre-apply precondition read; the race window between that read and the update is closed only against writers that go through the Publisher. A legacy writer that does not is DETECTED (publication marker mismatch → `PRECONDITION_FAILED`), not prevented: prevention is exit-gate X14/X16 (retire the writer; deny it under rules/IAM).
* **Rollback of a Brain's FIRST live publication** has no artifact to restore (the previous state is the legacy writer's); that recovery is the private pre-cutover RTDB export, by design (`NoRollbackTarget`).
* **Findings.** (1) The publication record carries `knowledgeRelease` but not the manifest ref/hash (manifest identity lives in Fish's registry children and is checked by the resolver). (2) `updateSha256` in a live record hashes the data update (the record cannot contain its own hash). (3) `LivePublisher` records a per-attempt `publishId`, so dry-run and live differ only in that id.

## Test tiers
`REPO_READY` = proven here against fake clients. `LIVE_SECURITY_VERIFIED`, real readback and a real rollback rehearsal = LIVE_ONLY (`PRODUCTION_EXIT_GATE_V1.md`).
