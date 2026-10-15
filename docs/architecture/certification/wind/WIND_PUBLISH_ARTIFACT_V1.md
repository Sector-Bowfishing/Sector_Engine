# Wind Brain: publish artifact V1 (IMPLEMENTED as a builder; proven in Publisher V1 SHADOW only)

**Status:** builder `jobs/wind-hourly/sector_wind/brain/artifact.py`, tests `jobs/wind-hourly/tests/test_publish_artifact.py` (32 tests). It is **not wired into `wind-hourly`**; the deployed job is unchanged. Conforms to Publisher V1 Shadow at `d090c428` (`docs/architecture/publisher/`). Supersedes the design-only draft from the first certification pass.

## 1. How the artifact is produced
Wind's existing `publish()` computes every payload. Run against a recording writer, it yields the exact PATCH dictionaries it would send today; the builder re-expresses them as `publish-artifact-v1` envelopes. Consequences: **no scientific value is recomputed or reshaped**, `publish.py` is unmodified, and equivalence with today's live output is a testable property (tested: every value in the artifact equals what the writer stores, modulo RTDB-dropped nulls/empties).

One run yields **five artifacts** (the Publisher's three Wind schemas; the lake-state schema is split into three baseline **scopes** by rate of change, which the envelope's optional `scope` supports; each (schema, scope) has its own baseline and SKIPs independently):
| Artifact (schema : scope) | Carries | Mutations (live-shaped run) | Bytes | Changes |
|---|---|---:|---:|---|
| `wind-lake-state-v1 : lake-live` | `/lakes/{k}/states/wind`, `/lakeFleet/{k}/slots/wind`, `/snapshots/{k}/latest/wind` (compatibility copy, same atomic plan as its source) | 12 | 41,806 | hourly |
| `wind-lake-state-v1 : lake-static` | `/lakes/{k}/profiles/wind` (74), `/lakes/{k}/validation/wind`, `/lakeFleet/{k}/modelVersions/wind` | 82 | 323,828 | rarely |
| `wind-lake-state-v1 : fleet-readiness` | `/lakeFleet/{k}/readiness/wind` (621 lakes) | 621 | 54,573 | only on a readiness change |
| `wind-registry-v1` | approved `/brains/wind/{child}` children, `/validation/wind`, `/health/brains/wind`, own `/activity/{event}` | 33 | 11,029 | hourly |
| `wind-source-registry-v1` | `/sources/{id}`, `/health/sources/{id}` for the three Wind-acquired sources | 6 | 2,812 | hourly |

Effect: a normal hour changes ~13 + ~34 + ~7 paths (not today's unconditional ~1,260), and a fully unchanged run is SKIP. Cost of the split: atomicity is per artifact (integration report F-2).

## 2. Envelope and lineage (as run)
`envelope: publish-artifact-v1`; `lineage` (`brain-lineage-v1`): `brainId=wind`, `artifactSchema`, `knowledgeRelease/manifestRef/manifestSha256 = NONE ×3` (no canonical Wind release exists yet: declared, not invented; the Publisher requires all three NONE or all declared), `codeVersion` = Wind's own commit sha12, `executionId` (UUIDv4 of the wind-hourly run, supplied by the caller), `inputFingerprint` = sha256 of the evidence times per lake (observation and forecast cycle), the frozen validation-evidence digest and the model/Brain versions, `outputFingerprint` computed with the **Publisher's own function** (Wind never re-implements it; tests also verify it with an independent re-hash), `artifactId` = content address `sha256:<canonical bytes>` (unique per run, identical for identical inputs), `generatedAt`, `lifecycle=CALIBRATION`, `reviewStatus=UNREVIEWED`, `validationStatus=NOT_VALIDATED`. `scope` is set for the lake-state artifacts (`lake-live`, `lake-static`, `fleet-readiness`); the registry and source artifacts use the default scope.

## 3. Freshness (lake-state artifact; required by its schema)
`evidenceObservedAt` = newest of `observationTime` (analysis) else `forecastGeneratedAt`; `staleAfter` = earliest of `generatedAt + 90 min` and `NBM cycle + 3 h` (**Wind's existing thresholds, unchanged**); `freshnessStatus` = `UNAVAILABLE` if every state is `unavailable`, `STALE` if any state is stale, else `FRESH`; empty input = `UNKNOWN`. `expiresAt` is omitted (open decision: Wind has no existing expiry rule). `inputGeneratedAt` is not applicable (Wind acquires its own primary data). A successful run with an old NBM cycle therefore publishes `STALE`.

## 4. Null, unknown and delete semantics
- The artifact contains **only `SET` mutations; no `DELETE` anywhere** (Wind's schemas permit none, and the builder never emits one).
- Null keys and empty containers are omitted. RTDB itself drops them on write, so the stored node is identical to today's. This is "absence semantics": a missing value never deletes anything else.
- A null **inside a list** cannot be omitted without shifting indices, so the builder refuses it (`ArtifactBuildError`); it must be encoded as an explicit value.
- A value the Publisher rejects (null, nested null, empty, NaN, wrong type) fails validation as a whole; nothing is published.

## 5. `/brains/wind` registry: child-level, ownership
Wind supplies only these children (identical to the Publisher's list; a test asserts equality): identity `brainId displayName domain question platform`; model `version schemaVersion stalenessModel dependsOn descriptor versions activeProductionModel researchCandidate scores readinessDefinitions stateKinds`; status `schedule enabled health status supportedLakeCount profiledLakeCount readinessCounts staleLakeCount staleAfterHours staleRule lastSuccessfulRun lastError deploymentVersion breakdowns runsPerMinute updatedAt publishMode`. Each child is replaced as a unit. **Never** the whole node; **never** `/brains/wind/publication` or `certification` (Publisher-owned; rejected in tests). Any child not on the list is reported as unsupported, not published.

**Ambiguous ownership flagged (not widened):** `scores` (the registry copy of 3.1/BWIS, a score mirror: see score reconciliation); `lastError` (today `None` → omitted; a *stale* `lastError` can persist after recovery because Wind may not delete; see integration report F-4); `deploymentVersion` (label drift: `main@<sha>`).

## 6. Authorized path families (anything else rejected by the Publisher)
`/lakes/{k}/states/wind`, `/lakes/{k}/profiles/wind`, `/lakes/{k}/validation/wind`, `/lakeFleet/{k}/{slots,readiness,modelVersions}/wind` (DERIVED_PROJECTION), `/snapshots/{k}/latest/wind` (**LEGACY_READER_PRESENT**, same atomic plan as its source), `/brains/wind/{approved child}`, `/validation/wind`, `/health/brains/wind`, `/activity/{event}` containing `-wind-`, `/sources/{noaa-nbm-v5|noaa-rtma-ru|iem-metar-wind}`, `/health/sources/{same}`. `/scores/wind` is **not** a Wind family (Platform-owned).

**Paths `wind-hourly` writes today that no Publisher Wind schema authorises** (the builder reports them in `dropped` and does not publish them): `/lakeFleet/{k}/lakeId`, `/snapshots/{k}/latest/lakeId`, `/snapshots/{k}/latest/brainVersions/wind`, `/health/jobs/wind-hourly`. Also unsupported: failure-path leaf writes under `/health/brains/wind/*`, and activity pruning (a delete). Each needs a decision (integration report F-5..F-7).

## 7. Volatile fields (excluded from `outputFingerprint`)
Shared defaults (`generatedAt publishedAt checkedAt ageHours durationMs`) plus Wind's: `inputAgeHours lastUpdatedAt updatedAt lastRun lastSuccess lastSuccessfulRun lastFetchAt latencyMs`. Evidence times (`observationTime`, `forecastGeneratedAt`, `latestObservationAt`, `latestIssuedAt`) are **material**: a new observation is a change. These must be registered in the Publisher's Wind registration at cutover (the tests inject them into a copy of the registry; the Publisher worktree is untouched).

## 8. Determinism
Same patches + same context ⇒ byte-identical canonical artifacts and identical deterministic plans (tested across two independent runs and two independent Publisher stacks).

## 9. Not claimed
No production behaviour changed. `knowledgeRelease` remains `NONE` until a Wind release manifest exists. The Publisher's shadow baseline is the last `SHADOW_READY`, not live state.
