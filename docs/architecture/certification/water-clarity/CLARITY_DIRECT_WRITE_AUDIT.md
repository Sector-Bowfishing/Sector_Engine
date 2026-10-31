# Water Clarity — direct-write audit

**Scope:** every database/storage write door of the Clarity components. **Result (updated 2026-10-31, branch `cortex/water-clarity-cutover-finish-2026-10-31`):** C1 has **ZERO** RTDB write sites. The two former LEGACY / RETIREMENT_CANDIDATE sites are **RETIRED** in code, and the AST pin (Kit P14, `allowed_write_sites=frozenset()`) and the exit-gate guard (X14: no write site, no whole-node key) enforce it. The run produces one sealed artifact (CENTRAL mode) or local files (`--dry-run`); the central Publisher is the only writer. `publisherRequired.cutoverStatus` stays `SHADOW` until an approved cutover records a complete `production-exit-evidence.json` (the LIVE checks). Vocabulary: CANONICAL_PLATFORM, LEGACY, SHADOW, RETIREMENT_CANDIDATE, RETIRED, BLOCKER.

## C1 write sites (`brains/water-clarity/runtime/run.py`)
| Site | What it writes | Class | Notes |
|---|---|---|---|
| `write()` → `rtdb.update(updates)` (the `--legacy-direct-write` path) | per-lake batches and the fleet record set (below) | **RETIRED** | removed with the flag; `collect()` only gathers the payload; the flag is now an unknown option (argparse exit 2) |
| `main()` → `rtdb.update({...FAILED...})` | abort path: `/health/brains/water-clarity/{status,lastRun,latestError}` | **RETIRED** | process facts are Orchestrator-derived; an aborted run stores nothing |
| CENTRAL mode → `ArtifactWriter.write` | ONE sealed `clarity-publication-v1` artifact, create-only, private artifact bucket | **CANONICAL_PLATFORM** | the Orchestrator verifies it and the central Publisher writes the database |
| `publish_artifact.build_artifact` + `--dry-run` | local files only (`payload.json`, `artifact.json`, `shadow_verdict.json`, `run_report.json`); in-memory SHADOW evaluation | **SHADOW** | zero database writes (tested) |

The run still READS the Brain RTDB (schema check, `brains/water-clarity/{version,lastSuccessfulRun}` child reads, `lakeFleet`, `activity`). It never addresses the whole Brain node, and the builder refuses a whole-node key (`test_a_whole_brain_node_key_fails_the_build`).

## The real write set (the payload an actual `run.main` execution seals, network edges faked) and its disposition at cutover
| Row / path | Class | Disposition |
|---|---|---|
| `/lakes/{k}/states/waterClarity`, `/lakes/{k}/profiles/waterClarity` | domain truth | authored by `clarity-lake-state-v1` |
| `/lakeFleet/{k}/slots/waterClarity` (and children `stale`, `lastError`, `lastErrorAt` on an Engine miss), `/readiness/waterClarity`, `/modelVersions/waterClarity` | domain projections of the state | authored in the same atomic publish |
| `/brains/water-clarity/{child}` (the retired writer replaced the **whole node**) | domain truth + status | emitted and authored child-by-child; the whole-node replace (which would erase Publisher-owned `publication` / `certification`) is retired in code and refused by the builder |
| `/validation/water-clarity`, `/sources/{id}`, `/activity/{event}` | domain truth | authored by the registry / source schemas |
| `/health/sources/{id}` | operational source health | row `health-sources`: **PLATFORM_OWNED → ORCHESTRATOR_DERIVED** (Cortex 3.1: the Publisher writes no `/health/*`; the Orchestrator derives it from the published `/sources/{id}`) |
| `/health/brains/water-clarity/{child}` (the retired writer replaced the whole node) | **no longer authored by the artifact (owner decision 2026-10-29, Cortex 3.1 FD-15)**: `status`, `staleLakeCount` are derived by the Orchestrator from the published `/brains/water-clarity/status`; `lastRun`, `lastSuccess`, `durationMs`, `errorCount`, `latestError`, `deployedVersion`, `brainVersion`, `engineRevision`, `publisherDeployment`, `lakesAttempted`, `lakesPublished`, `lakeSurfaceRun` are process facts | row `health-brains`: **PLATFORM_OWNED → ORCHESTRATOR_DERIVED** (not authored by the artifact) |
| `/health/jobs/water-clarity-brain` | job record | row `health-jobs`: **PLATFORM_OWNED → ORCHESTRATOR_DERIVED** |
| `/lakeFleet/{k}/lakeId` | lake identity | row `lakefleet-lakeid`: **PLATFORM_OWNED → STOP_WRITING** (Lake Registry) |
| `/snapshots/{k}/latest/lakeId` | lake identity | row `snapshot-lakeid`: **PLATFORM_OWNED → STOP_WRITING** |
| `/snapshots/{k}/latest/waterClarity` | compatibility copy | projection `clarity-snapshot-copy-v1`: **DERIVED_COMPATIBILITY_PROJECTION → PUBLISHER_DERIVED** (verified reader: Sector Intelligence) |
| `/snapshots/{k}/latest/brainVersions/water-clarity` | compatibility value | projection `clarity-snapshot-brainversion-v1`: **PUBLISHER_DERIVED** |
| `/activity/*` deletes by age (pruning) | retention | row `activity-retention`: **PLATFORM_OWNED → STOP_WRITING** (a Brain's artifact never deletes events) |
| `/brains/water-clarity/lastError` cleared with a null | optional child | typed `DELETE` (`OPTIONAL_CHILD_CLEARED`) — the single inferred removal |

No path of the real write set is unclassified; the builder fails closed on any new one (`test_legacy_write_set_classification_is_complete`, `test_unmapped_paths_fail_closed_…`). Note: the legacy path table in `publisher/compat.py` is Wind-named (debt D-11); Clarity keeps its classification as data in `publish_artifact.NOT_AUTHORED` rather than widening that platform table — extract a per-Brain table after Brain #3.

## GCS writes (C2–C4) — `GCS_WRITE_SEMANTICS_PLATFORM_DEBT`
`lake-surface-daily` / `lake-surface-dispatch` / `hydrology-hourly` (C2), `clarity-current-hourly` / `ClarityPrecompute` (C3) write to `gs://sector-lake-surface` (LEGACY); `clarity-candidate-shadow` (C4) writes a private bucket (SHADOW, private). The Publisher's path families are RTDB-only; the platform has no storage-write semantics. These writes are **not** forced through the Publisher, **not** changed, and not part of the C1 contract. Item recorded for the platform lane: decide whether Brain-owned storage products get a Publisher model or stay Orchestrator-managed jobs. No Firebase write exists in C2–C4.

## Verdict
No BLOCKER. No RTDB door left in C1 (both RETIRED, rtdb.update gone; pinned), GCS doors outside the Publisher model (debt). `publisherRequired.cutoverStatus` stays `SHADOW`: flipping it to `CUTOVER_COMPLETE` needs the exit record of an approved cutover (see `docs/architecture/production/WATER_CLARITY_CUTOVER_COMPLETE_V1.md`).
