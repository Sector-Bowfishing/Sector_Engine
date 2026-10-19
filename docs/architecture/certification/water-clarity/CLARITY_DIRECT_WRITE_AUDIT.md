# Water Clarity — direct-write audit

**Scope:** every database/storage write door of the Clarity components. **Result:** C1 has exactly TWO RTDB write sites, both **LEGACY / RETIREMENT_CANDIDATE**, pinned by an AST test (`test_no_unauthorized_production_write_in_the_clarity_runtime`); the artifact path writes nothing. No door was removed or added; cutover is a separate approved task. Vocabulary: CANONICAL_PLATFORM, LEGACY, SHADOW, RETIREMENT_CANDIDATE, BLOCKER.

## C1 write sites (`brains/water-clarity/runtime/run.py`)
| Site | What it writes | Class | Notes |
|---|---|---|---|
| `write()` → `rtdb.update(updates)` | per-lake batches and the fleet record set (below) via the ownership-checked platform client (`BrainRtdb`, refuses app databases) | **LEGACY / RETIREMENT_CANDIDATE** | retires at the approved Publisher cutover; MANUAL execution only (no scheduler) |
| `main()` → `rtdb.update({...FAILED...})` | abort path: `/health/brains/water-clarity/{status,lastRun,latestError}` | **LEGACY / RETIREMENT_CANDIDATE** | process facts: Orchestrator-owned at cutover |
| `publish_artifact.build_artifact` + `--dry-run` | local files only (`payload.json`, `artifact.json`, `shadow_verdict.json`, `run_report.json`); in-memory SHADOW evaluation | **SHADOW** | zero database writes (tested) |

## The real write set (captured from an actual `run.main` execution with network edges faked) and its disposition at cutover
| Row / path | Class | Disposition |
|---|---|---|
| `/lakes/{k}/states/waterClarity`, `/lakes/{k}/profiles/waterClarity` | domain truth | authored by `clarity-lake-state-v1` |
| `/lakeFleet/{k}/slots/waterClarity` (and children `stale`, `lastError`, `lastErrorAt` on an Engine miss), `/readiness/waterClarity`, `/modelVersions/waterClarity` | domain projections of the state | authored in the same atomic publish |
| `/brains/water-clarity` (legacy: the **whole node is replaced**) | domain truth + status | authored child-by-child; **cutover precondition:** the legacy whole-node replace would erase Publisher-owned `publication` / `certification` children, so the legacy writer must be retired at (not after) Publisher production mode — invariant 10 enforces this once `cutoverStatus` is `CUTOVER_COMPLETE` |
| `/validation/water-clarity`, `/sources/{id}`, `/health/sources/{id}`, `/activity/{event}` | domain truth | authored by the registry / source schemas |
| `/health/brains/water-clarity` (legacy: whole node) | `status`, `staleLakeCount` are domain facts (authored); `lastRun`, `lastSuccess`, `durationMs`, `errorCount`, `latestError`, `deployedVersion`, `brainVersion`, `engineRevision`, `publisherDeployment`, `lakesAttempted`, `lakesPublished`, `lakeSurfaceRun` are process facts | row `health-brains-process`: **LEGACY_READER_DEPENDENCY → ORCHESTRATOR_DERIVED** (not authored by the artifact) |
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
No BLOCKER. Two LEGACY / RETIREMENT_CANDIDATE RTDB doors (C1), GCS doors outside the Publisher model (debt), a documented cutover precondition (whole-node replace). `publisherRequired.cutoverStatus` stays `SHADOW`.
