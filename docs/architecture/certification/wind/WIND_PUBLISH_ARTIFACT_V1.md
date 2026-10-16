# Wind Brain: publish artifact contract (now `publish-artifact-v2`, bundle `wind-publication-v1`)

**Status:** implemented as a builder, proven in Publisher **Gate P shadow** only. Code: `brains/wind/runtime/sector_wind/brain/artifact.py`; tests `brains/wind/tests/test_publish_artifact.py` (moved from `jobs/wind-hourly/` in Repository Phase 2; declaration `brains/wind/contracts/wind-publication-v1.json`). **Not wired into `wind-hourly`**; the deployed job is unchanged. This file keeps its original name; it supersedes the Publisher-V1 (five-artifact) version. Adoption result and equivalence: `WIND_PUBLISHER_V2_ADOPTION_REPORT.md`.

## 1. Shape
```
ONE Wind execution (executionId)
  -> ONE publish-artifact-v2  { envelope, lineage(brain-lineage-v1), sections[] }      lineage.artifactSchema = wind-publication-v1
       sections (each: artifactSchema, scope?, freshness?, mutations[SET|DELETE])
         wind-lake-state-v1 : lake-live        states, slots                      (hourly)
         wind-lake-state-v1 : lake-static      profiles, lake validation, modelVersions
         wind-lake-state-v1 : fleet-readiness  readiness (621 lakes)
         wind-registry-v1                      /brains/wind/{approved child}, /validation/wind, /health/brains/wind/{status,staleLakeCount}, own events, lastError DELETE
         wind-source-registry-v1               sources + source health (Wind is acquisition owner)
  -> Publisher validates the WHOLE artifact -> ONE deterministic atomic plan (+ Publisher-derived compatibility copies + ONE publication record) -> SHADOW, SKIP, or REJECT-all
```
Built by running the **unchanged** `publish()` against a recording writer and re-expressing its PATCHes; no scientific value is recomputed. The bundle is sealed with the Publisher's `seal_bundle`; Wind has no fingerprint, volatile or ownership logic of its own (a test asserts this). `artifactId` = `sha256` of the sealed envelope (unique per run, byte-stable for identical inputs).

## 2. Lineage and freshness
`brainId wind`; `codeVersion` = Wind's own commit; one `executionId`; `inputFingerprint` = digest of evidence times per lake + validation-evidence digest + model/Brain version; `outputFingerprint` computed by the Publisher algorithm `sector-semantic-fingerprint-v2` (bundle fingerprint over section fingerprints) and recomputed by the Publisher; `knowledgeRelease/manifestRef/manifestSha256` = `NONE` until a Wind release manifest exists; `lifecycle CALIBRATION`, `reviewStatus UNREVIEWED`, `validationStatus NOT_VALIDATED`.
Freshness (lake-state sections): `evidenceObservedAt` = newest `observationTime` (else forecast cycle time); `staleAfter` = earliest of `generatedAt + 90 min` and `NBM cycle + 3 h` (**existing thresholds, unchanged**); `freshnessStatus` FRESH / STALE / UNAVAILABLE / UNKNOWN. `expiresAt` omitted (no existing Wind expiry rule; open decision). A successful run with old evidence publishes STALE.

## 3. Authorised paths (decided by the Publisher registry)
`/lakes/{k}/states|profiles/wind`, `/lakes/{k}/validation/wind`, `/lakeFleet/{k}/slots|readiness|modelVersions/wind` (DERIVED_PROJECTION), `/brains/wind/{child}` for the approved children (identity, model, status groups), `/validation/wind`, `/health/brains/wind/status`, `/health/brains/wind/staleLakeCount`, `/activity/{event}` containing `-wind-`, `/sources/{id}` and `/health/sources/{id}` for Wind-acquired sources. `/scores/wind` is Platform's and is not a Wind family. Everything else is rejected: foreign domains (`CROSS_DOMAIN_PATH`), `publication`/`certification` (`RESERVED_PATH`), whole `/brains/wind` (`BRAIN_NODE_REPLACEMENT`), Publisher-derived targets (`PLATFORM_DERIVED_PATH`), unauthorised children (`PATH_NOT_AUTHORIZED`).

## 4. No longer authored by Wind (from `compat.LEGACY_PATH_TABLE`; reported by the builder as `dropped` with the row id)
| Path | Class | Mechanism / target owner |
|---|---|---|
| `/lakeFleet/{k}/lakeId`, `/snapshots/{k}/latest/lakeId` | PLATFORM_OWNED | STOP_WRITING / Platform Lake Registry |
| `/snapshots/{k}/latest/wind`, `/snapshots/{k}/latest/brainVersions/wind` | DERIVED_COMPATIBILITY_PROJECTION | PUBLISHER_DERIVED (copy of the state; value of `/brains/wind/version`), same plan, retirement gate = snapshot migration plan |
| `/health/jobs/wind-hourly` | PLATFORM_OWNED | ORCHESTRATOR_DERIVED |
| `/health/brains/wind/{lastRun,lastSuccess,durationMs,errorCount,latestError,deployedVersion,publishMode}` | LEGACY_READER_DEPENDENCY | ORCHESTRATOR_DERIVED |
| `/activity` pruning | PLATFORM_OWNED | STOP_WRITING / platform retention |
Transitional, still Wind-authored and volatile: `/brains/wind/updatedAt`, `/brains/wind/lastSuccessfulRun` (retire when Ops and the Orchestrator read the publication record / execution records). `/brains/wind/lastError`: Wind-authored, cleared by typed DELETE.

## 5. Null / unknown / delete
Null keys and empty containers are omitted (RTDB would drop them anyway; the stored node is unchanged) and **never** become a delete; a null inside a list is refused at build time. Deletes are typed and bounded: `lastError` (`OPTIONAL_CHILD_CLEARED`); lake nodes (`LAKE_LEFT_FLEET`, `EVIDENCE_REMOVED`) only from an explicit caller removal list. No other delete authority exists.

## 6. Volatile and SKIP
`wind-volatile-v1` is the Publisher's. Unchanged semantic content (all sections) ⇒ `SKIP`: no plan, no sink call, no head move, no heartbeat (`NO_REPUBLISH_HEARTBEAT`). A changed section publishes only itself (plus its derived copies and the one publication record); an older-than-baseline changed section rejects the whole artifact.

## 7. Open items
`expiresAt` decision; Wind release manifest; wiring into the job and the artifact store (cutover steps 2-5); Orchestrator compatibility for execution health and freshness (G1/G2); evidence digest is baked into the image (changes only on redeploy).
