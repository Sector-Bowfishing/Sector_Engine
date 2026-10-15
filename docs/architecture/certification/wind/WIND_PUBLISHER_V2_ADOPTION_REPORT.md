# Wind Brain: Publisher V2 adoption + equivalence gate (Wind-side contract adoption)

**Result: `WIND_PUBLISHER_V2_ADOPTION_READY`.** Wind's artifact/publication contract conforms to Publisher Gate P (`PUBLISHER_GATE_P_SHADOW_READY`, Publisher `7ebfca1c`) and the real-state equivalence evaluation contains only expected, understood migration differences. This is **not** Wind production cutover, scientific validation, full architecture certification, Publisher production-security approval, or a completed repository migration. Production write security remains `PRODUCTION_WRITE_SECURITY_GATE_OPEN`.

## 1. Lineage
The Wind certification branch had integrated Publisher `d090c428`; the Publisher branch advanced linearly through `c3c9bccc`, `3ae7f71c`, `7ebfca1c`. Ancestry check: `d090c428` is a direct ancestor of `7ebfca1c` (3 commits ahead, no divergence). Integrated with one history-preserving merge commit (`--no-ff`); no file copied by hand; the Publisher worktree was read-only (clean at `7ebfca1c`); `git diff 7ebfca1c -- jobs/brain_platform docs/architecture/publisher` on the Wind branch is empty (no Publisher semantics changed locally).

## 2. Old vs new Wind artifact behaviour
| | Phase 2 (Publisher V1 shadow) | Now (Publisher V2 / Gate P) |
|---|---|---|
| Artifacts per run | 5 independent v1 artifacts | **1** `publish-artifact-v2`, bundle `wind-publication-v1`, 5 sections |
| Plans / records per run | 5 plans, 5 publication writes (last wins) | **1 plan, 1 sink call, 1 publication record** |
| Validation | per artifact | whole bundle (all sections, all violations) before any plan |
| Fingerprint | per artifact | per section + bundle (`sector-semantic-fingerprint-v2`), recomputed by the Publisher |
| Volatile handling | Wind injected a key list into a registry copy; scalar children never stripped | Publisher's registered `wind-volatile-v1` (keys *and* paths) |
| Snapshot copies, `brainVersions` | Wind authored | **Publisher-derived** compatibility projections |
| Lake identity, generic job/process health, activity pruning | Wind wrote or reported as dropped | Wind **does not author**; classified by `compat.LEGACY_PATH_TABLE` |
| Removal | impossible (stale children persisted) | typed `DELETE` + closed reason vocabulary |
| Ownership logic | Wind-side lists | **none**: routing is decided by the Publisher registry and the legacy table |

## 3. Bundle and section contract (verified against `registry.py`)
`artifactSchema = wind-publication-v1`; allowed sections: `wind-lake-state-v1`, `wind-registry-v1`, `wind-source-registry-v1`. Wind emits five sections (the lake-state schema is split into three baseline **scopes**, each with its own baseline so slow parts SKIP while the hourly state changes):
| Section (schema : scope) | Mutations the builder authors |
|---|---|
| `wind-lake-state-v1 : lake-live` | `/lakes/{k}/states/wind`, `/lakeFleet/{k}/slots/wind` |
| `wind-lake-state-v1 : lake-static` | `/lakes/{k}/profiles/wind`, `/lakes/{k}/validation/wind`, `/lakeFleet/{k}/modelVersions/wind` |
| `wind-lake-state-v1 : fleet-readiness` | `/lakeFleet/{k}/readiness/wind` |
| `wind-registry-v1` | approved `/brains/wind/{child}` children, `/validation/wind`, `/health/brains/wind/{status,staleLakeCount}`, own `/activity/{event}` (`-wind-`), the typed `lastError` DELETE |
| `wind-source-registry-v1` | `/sources/{id}`, `/health/sources/{id}` for the three Wind-acquired sources |
`lineage`: standard `brain-lineage-v1`; one `executionId` for the whole artifact; `artifactId` = content address of the sealed envelope; `knowledgeRelease/manifestRef/manifestSha256 = NONE` (no canonical Wind release yet; declared, not invented); `lifecycle CALIBRATION`, `reviewStatus UNREVIEWED`, `validationStatus NOT_VALIDATED`. Freshness (required by the lake-state schema) is derived from the existing Wind thresholds, unchanged.

## 4. Ownership after adaptation
**Wind-owned (authored):** lake states, profiles, per-lake validation, fleet slots/readiness/modelVersions; `/validation/wind`; `/brains/wind/*` approved children (identity, model, status groups; `updatedAt` and `lastSuccessfulRun` are *transitional* Wind-authored); `/health/brains/wind/status`, `/health/brains/wind/staleLakeCount` (domain health facts only); own append-only `/activity` events; the three source records and their health.
**Stopped authoring** (all from `compat.LEGACY_PATH_TABLE`, none of Wind's ownership widened): `/lakeFleet/{k}/lakeId` (Platform Lake Registry; existing rows persist), `/snapshots/{k}/latest/lakeId` (same), `/snapshots/{k}/latest/wind` and `/snapshots/{k}/latest/brainVersions/wind` (Publisher-derived from the authorised source, same plan), `/health/jobs/wind-hourly` and `/health/brains/wind/{lastRun,lastSuccess,durationMs,errorCount,latestError,deployedVersion,publishMode}` (Orchestrator-derived execution/process health), `/activity` pruning (platform retention). Publisher-owned: `/brains/wind/publication`, `certification`.

## 5. Explicit delete semantics
Null, missing and empty NEVER mean delete. Typed `{"op":"DELETE","path","reason"}` only: registry `lastError` (`OPTIONAL_CHILD_CLEARED`; emitted idempotently while the legacy node reports no error, which SKIPs run to run); lake nodes `states profiles validation slots readiness modelVersions` (`LAKE_LEFT_FLEET`, `EVIDENCE_REMOVED`), produced **only** from an explicit caller-supplied removal list. The builder rejects out-of-vocabulary reasons and non-delete paths; the Publisher independently rejects both (parent nodes, whole lake, `/brains/wind`, `publication`, sources, foreign paths, derived targets). Deleting a source also deletes its Publisher-derived snapshot copy in the same plan.

## 6. Volatile contract, fingerprint, no heartbeat (G5)
`wind-volatile-v1` (from Publisher code): keys `inputAgeHours lastFetchAt latencyMs`; transitional paths `/brains/wind/updatedAt`, `/brains/wind/lastSuccessfulRun`; plus shared defaults (`generatedAt publishedAt checkedAt ageHours durationMs`). Evidence times (`observationTime`, `forecastGeneratedAt`, `latestObservationAt`, `latestIssuedAt`) stay material (tested: a new observation time republishes, only its section). Algorithm `sector-semantic-fingerprint-v2`: computed by the Publisher; Wind calls `seal_bundle` and has no fingerprint code (a test asserts it). Three identities kept distinct: artifact byte-integrity hash (API reference), semantic fingerprint, publication metadata. `NO_REPUBLISH_HEARTBEAT`: nothing is injected to defeat SKIP.

## 7. Tests
- Wind: **105 passed** (58 original domain/science tests untouched + 47 Publisher V2 tests); **16 NOT_RUN** (`-m network` provider-download tests in `test_decoder.py`, excluded by the project's default marker; no dependency was missing).
- Shared/Publisher (from this worktree): `jobs/brain_platform` **452 passed** (Gate P, Wind integration, equivalence, boundary lint); `jobs/brain-scores` **21 passed**; `jobs/brain-orchestrator` **24 passed**.
- Required Wind proofs (all covered): one run → one v2 bundle · sections · stable identity · no snapshot copies · no lake identity · no job/process health · approved health facts valid · unchanged → SKIP · volatile metadata does not publish · material evidence time does · explicit DELETE generated · null/missing is not DELETE · invalid delete reason rejected (builder and Publisher) · Brain cannot author publication metadata · invalid section rejects the whole bundle · older changed section rejects the whole bundle · zero live write and no socket opened · Wind science tests unchanged.

## 8. Equivalence gate
Evaluator `wind-shadow-equivalence-v1` (`render_target` + `evaluate_equivalence`, digest-only output).
1. **Producer-level (public, in the test suite):** the unchanged Wind producer's own legacy output tree (RTDB-normalised) vs the plan the Publisher would produce from the builder's bundle: `EQUIVALENT_WITH_EXPECTED_DIFFS`, 0 SEMANTIC_MISMATCH, 0 UNKNOWN, 0 TARGET_ONLY; negative controls (a changed value, an unaccounted field) correctly yield `NOT_EQUIVALENT`.
2. **Real-state capture (private):** a fresh read-only (GET-only) capture of the Wind scope of the live database on 2026-10-15 (the earlier session scratch capture was partial and untracked; the Phase 1 mandate already authorised read-only inspection of these paths) re-expressed through the same builder and evaluated against the capture. Counts: **MATCH 8,444 · EXPECTED_MIGRATION_DIFF 1,299 · LEGACY_ONLY 13 · VOLATILE_ONLY 2 · SEMANTIC_MISMATCH 0 · UNKNOWN 0 · TARGET_ONLY 0**. Verdict **`EQUIVALENT_WITH_EXPECTED_DIFFS`**.
| Class | Count | Why | Owner | Action before migration |
|---|---:|---|---|---|
| EXPECTED: `lakefleet-lakeid` | 621 | Wind stops writing; rows persist | Platform Lake Registry (G4) | none for Wind Phase 2 (existing rows untouched); G4 needed for new lakes |
| EXPECTED: `snapshot-lakeid` | 621 | same | same | same |
| EXPECTED: `PUBLISHER_METADATA` | 57 | one publication record | Publisher | none |
| LEGACY_ONLY: `health-jobs-wind-hourly` / `health-brains-wind-process` | 8 / 5 | Ops still reads these under `/health`; Wind no longer authors them | Orchestrator (G1/G2) | **required before cutover**: Orchestrator compatibility record (or Ops reads `/jobs`) |
| VOLATILE_ONLY | 2 | `durationMs` (shared default) | n/a | none |
Caveat, stated plainly: the real-capture evaluation proves representation, ownership, normalisation, derivations and explicit-delete behaviour on real-sized real data; because the target is built from the same instant, it is **not** a time-aligned comparison of two independent producer runs. That is cutover plan step 6 (hourly parallel run).

## 9. Remaining blockers (none block Wind-side adoption or Repository Phase 2 physical move; they block cutover)
1. **Production write security gate open** (`PRODUCTION_WRITE_SECURITY_GATE_OPEN`); Publisher production mode P1-P11 not built; Wind's direct write capability unchanged by design.
2. **G1/G2** Orchestrator execution/job health compatibility (13 LEGACY_ONLY rows); **G4** Platform Lake Registry identity publisher; platform retention job for `/activity`.
3. **Stale freshness on SKIP (cutover-critical):** `/brains/wind/lastSuccessfulRun` is volatile-excluded and, under no-heartbeat, will not refresh on SKIP, yet the Orchestrator reads it today for Wind's dependency freshness (optional, 6 h, Fish and Sector Intelligence). The Orchestrator must read its own execution records before cutover.
4. **P12** (transactional baseline index) is Publisher/cutover work; not solved or compensated here.
5. The builder is not wired into `wind-hourly`; wiring, the artifact bucket and the deployed Publisher are separate approvals (cutover plan steps 2-5).
6. `knowledgeRelease` NONE (no Wind release manifest); research backup (Phase 2 plan) still open; the provider collector was re-checked (running, untouched).
7. Reader migration for the snapshot compatibility copy (Ops, Intelligence) per the snapshot plan; Ops move to `/jobs`.
Architecture readiness and scientific maturity stay separate: Wind remains SHADOW / CALIBRATION / `NOT_VALIDATED`; no score or science changed (3.3 / 3.1 mirror / BWIS 5.4 untouched).
