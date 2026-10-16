# Wind Brain × Publisher V1 Shadow: integration report

> **Historical (Phase 2).** Publisher Gate P (`7ebfca1c`) resolved F-1..F-9 at the shadow-contract level and Wind now publishes ONE v2 bundle; see `WIND_PUBLISHER_V2_ADOPTION_REPORT.md`. Findings below are kept as the record of what drove Gate P (the five-artifact design and the dropped-path list are superseded).

**Result: Wind's artifact builder passes Publisher V1 Shadow. No live system was touched.** Publisher commit `d090c428` (worktree clean, never modified). Not a cutover; not certification.

## 1. Integration strategy
`d090c428` is based on the same `fab115e9` as the Wind certification branch, so it was brought in with one **merge commit** (`--no-ff`, `9e5c2385`) on the local Wind certification branch. Publisher history is intact and attributable; no Publisher file was edited from the Wind side; the Publisher worktree was only read. Wind's additions are additive: `jobs/wind-hourly/sector_wind/brain/artifact.py` (builder, not imported by `main.py` or `publish.py`) and `jobs/wind-hourly/tests/test_publish_artifact.py`. No second Publisher exists: tests import the Publisher's own `local_shadow_stack`, `ArtifactWriter`, `OrchestratorApi`, `output_fingerprint`, and registry (with Wind's volatile fields injected into a *copy*, as the contract requires).

## 2. Test evidence (all local, in-memory/tmp directories, sockets never opened)
Wind: 58 existing + **32 new = 90 passed**. Publisher: **251 passed** (unchanged, incl. its own boundary lint). The real flow exercised for every proof: Wind artifact → create-only write to the Brain's own artifact namespace → authenticated `SUBMIT_ARTIFACT` carrying only a reference → Publisher loads, checks namespace, byte hash, bindings → stages 0-7 → SHADOW/SKIP/REJECTED.

| # | Required proof | Evidence (test) | Result |
|--:|---|---|---|
| 1 | valid Wind artifact accepted | `test_real_wind_output_is_accepted…` (5 artifacts, all `SHADOW_READY`, `live:false`) | PASS |
| 2 | brainId = wind verified | `test_identity_schema_and_lineage…` (another Brain's identity cannot be stored by Wind's writer; Publisher stage 1) | PASS |
| 3 | Wind schema verified | same (`UNKNOWN_SCHEMA`); schemas = the three registered | PASS |
| 4 | artifact hash/reference verified | `test_reference_hash_is_verified…` (`ARTIFACT_HASH_MISMATCH`; cross-Brain namespace refused) | PASS |
| 5 | lineage verified | `LINEAGE_INCOMPLETE` on a missing field; complete lineage test | PASS |
| 6 | output fingerprint independently verified | `test_output_fingerprint_independently_verified` (separate re-hash) + Publisher recompute + `FINGERPRINT_MISMATCH` on tamper | PASS |
| 7 | unchanged → SKIP | `test_unchanged_is_skip…` (volatile-only drift SKIPs; live-shaped re-submit SKIPs all 5) | PASS |
| 8 | changed → SHADOW | same: one state value changed ⇒ only `lake-live` is `SHADOW_READY`, plan ≈ 13 paths | PASS |
| 9 | authorized Wind child paths accepted | `test_plan_paths_are_exactly_the_authorised_wind_families` | PASS |
| 10 | whole `/brains/wind` rejected | `BRAIN_NODE_REPLACEMENT` | PASS |
| 11 | `/brains/wind/publication` from Wind rejected | `RESERVED_PATH`; also unapproved child `PATH_NOT_AUTHORIZED` | PASS |
| 12 | Fish/species path rejected | `/speciesProfiles/*`, `/species/*`, `/brains/biological-state/*` → `CROSS_DOMAIN_PATH` | PASS |
| 13 | Lake-owned `speciesPresence` rejected | `CROSS_DOMAIN_PATH` | PASS |
| 14 | Water Temp / Clarity / Depth (and Lake state) rejected | `states/waterTemp|waterClarity|depth|lake` → `CROSS_DOMAIN_PATH`; snapshot-field spelling `waterTemperature` also rejected | PASS |
| 15 | null / missing cannot delete | `test_null_or_empty_values_cannot_delete` (null, nested null, `{}`, `[]` → `FAILED_VALIDATION`; no `DELETE` mutation exists; builder refuses a null in a list) | PASS |
| 16 | deterministic atomic patch | byte-identical artifacts and plans across independent builds and stacks | PASS (atomic **per artifact**, see F-2) |
| 17 | no live RTDB mutation | `sink.live_mutations == 0`; plans live in the in-memory ShadowSink; Publisher boundary lint (no network/credential imports) | PASS |
| 18 | publication record correct | `status: SHADOW`, `live:false`, `mode: SHADOW`, no `publishedAt`, scope recorded | PASS |
| 19 | baseline comparison | per (schema, scope) head pointer advanced by `SHADOW_READY` only | PASS |
| 20 | `ARTIFACT_OLDER_THAN_BASELINE` | older, changed artifact rejected; head not moved | PASS |

**Live-shaped run (private, not committed):** the 74 profiles, 621 readiness rows, 4 states/slots/snapshots, registry, validation and sources currently in `sector-brain` were read once (GET), recast through the same builder, and run through the shadow stack: all 5 artifacts `SHADOW_READY`, then a re-submit `SKIP` ×5; **0 values omitted** (live data is already RTDB-normalised), 1 path reported as unauthorised. This confirms the Publisher accepts real Wind data at real size (largest artifact 324 KB, 621 mutations; limits are 8 MiB / 5,000).

## 3. Fixes made to the Wind artifact builder (the two Publisher-found incompatibilities)
1. **Null/None registry values** (`lastError`, version `date`, source `latestObservationAt`, `latencyMs`, …): omitted before publication; nothing is emitted as null. RTDB drops them on write today, so the stored node is unchanged. The unknown remains "absent", never a delete of anything else.
2. **Whole-node `/brains/wind`**: replaced by child-level SETs of the 33 approved children; `publication` is never present.

## 4. Findings for the Publisher / platform lane (Wind did not work around or redesign any of these)
| ID | Finding | Impact | Suggested handling |
|---|---|---|---|
| F-1 | Volatile stripping applies to dict **keys**; child-level scalar mutations `/brains/wind/updatedAt` and `/brains/wind/lastSuccessfulRun` are addressed by path and are never stripped | the registry artifact is never SKIP (it is `SHADOW_READY` every run, ~34 paths) | Publisher: strip a mutation whose final segment is volatile, or publish those two scalars inside a dict child |
| F-2 | Atomicity is per artifact; one run now yields 5 plans | readiness counts in the registry and `readiness/wind` rows (or states vs registry) can be visible out of step between plans | Publisher: an ordered artifact group applied as one atomic update, or accept ordered publication with a documented window |
| F-3 | Every plan carries `brains/wind/publication` | five plans overwrite the one record; it reflects whichever plan went last | Publisher: per-scope publication children, or one record per run group |
| F-4 | Wind schemas permit no `DELETE` | a **stale** child can persist (e.g. `lastError` after recovery; a lake that leaves the fleet keeps its rows) | Platform decision: scoped delete for named children, or an explicit-value convention (e.g. `lastError` object with `state: NONE`) |
| F-5 | `/lakeFleet/{k}/lakeId`, `/snapshots/{k}/latest/lakeId`, `/snapshots/{k}/latest/brainVersions/wind` are written today but not authorised for Wind | dropped from the artifact; those fields already exist from other writers/earlier runs, but `brainVersions.wind` would stop updating | decide ownership (shared identity fields) or register `brainVersions/wind` as part of the legacy snapshot family |
| F-6 | `/health/jobs/wind-hourly` is written today and is in no Wind schema (job records belong to the Orchestrator's `/jobs`) | Ops "health.jobs" card would go stale at cutover | Ops reads `/jobs/wind-hourly` (exists) or the platform registers the family |
| F-7 | Activity pruning is a delete; failure-path health is a leaf write | event pruning and failure-health cannot be expressed | Orchestrator-owned retention; define a whole-node `/health/brains/wind` failure artifact |
| F-8 | Wind's `volatile_extra` list is not in the Publisher's `wind_specs()` | without it, every run would be `SHADOW_READY` | register the list from `WIND_VOLATILE_EXTRA` (platform lane) |
| F-9 | Shadow baseline = last `SHADOW_READY`, not live state | first live publish must reconcile (Publisher cutover P4) | already in Publisher requirements |

## 5. Conformance statement
Wind conforms to the locked contract: `SHADOW` retained; `ARTIFACT_OLDER_THAN_BASELINE` exercised; no whole-node `/brains/wind`; child-level publication; `publication` untouched; artifact handoff by authenticated reference only; no arbitrary path/mutation API; hash and fingerprint verified; cross-domain fails closed; null/missing never deletes; shadow cannot write live. Items F-1..F-8 are limits of the current Publisher contract, recorded for the platform lane.
