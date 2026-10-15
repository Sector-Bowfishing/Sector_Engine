# Repository Foundation V1 — Phase 1A implementation record

**Status: `REPOSITORY_FOUNDATION_PHASE_1A_COMPLETE`** (additive skeleton + machine schemas + report-only architecture tooling).
This does NOT mean: repository migrated, Wind/Fish migrated, Publisher ready, any Brain certified, or live cutover approved. No existing file under `Sources/`, `Tests/`, `jobs/`, `scripts/`, `ops/`, `.github/`, or any deploy path was modified. Base: `e07c01d7`. Branch `feat/repository-foundation-v1` (local, not pushed).

## Created paths
| Path | Content |
|---|---|
| `engine/ providers/ platform/ contracts/ brains/ deploy/ tools/ docs/platform/ docs/history/` | `README.md` each: owner, purpose, belongs / does-not-belong, import rules, migration status |
| `platform/{python,swift,orchestrator,publisher,scoring,lineage,ops}/`, `platform/registries/{,brains,lakes,species}/` | `README.md` each (destinations only; no code copied) |
| `contracts/schemas/` | seven JSON Schemas (below) + README |
| `contracts/conformance/` | README only — destination (see deviations) |
| `providers/PROVIDERS.json` | catalog format, `providers: []` |
| `brains/_template/` | `README.md`, `BRAIN_OPERATING_CONTRACT.template.md` (19 sections), `brain.template.json`, `BRAIN_PACKAGE_CHECKLIST.md`, `research/{GAPS,MANIFEST}.template.json` |
| `tools/architecture/` | `report.py`, `jsonschema_lite.py`, `stable_brain_ids.json`, `large_file_exceptions.json`, `pytest.ini`, `tests/test_foundation.py` |
| `docs/architecture/repository-foundation-v1/` | this record, `LARGE_AND_GENERATED_DATA_POLICY.md`, `SOURCE_OF_TRUTH_BOUNDARIES.md` |

No `brains/<name>` directory exists for any real Brain (no ceremonial stubs; Wind is not migrated).

## Schemas (all JSON Schema 2020-12, `schemaVersion` / contract `1.0.0`)
`brain.schema.json` (includes `customerIntegrationMode` enum `none|embedded|published`; research workspace is a logical id), `providers.schema.json` (separate `acquisitionOwner`, `healthOwner`, `authorizedConsumers`, `costClass`, `licenseRef`; no vague `owner`), `research-gaps.schema.json`, `research-manifest.schema.json`, `registry-brains.schema.json`, `registry-lakes.schema.json`, `registry-species.schema.json`.

## Architecture report (REPORT-ONLY)
`python3 tools/architecture/report.py [--legacy] [--json] [--strict]` evaluates all 16 invariants. It exits 0 unless `--strict` (never used by CI in 1A). It is not wired into CI (Phase 1B). With zero registered Brains, invariants 1–7, 10–14 pass vacuously; the report prints the Brain count.

## Baseline violations discovered (not fixed; report-only)
* Invariant 15 — 5 tracked files ≥ 1 MB without an exception: `jobs/lake-surface/polygons.geojson.gz` (7.5 MB), four files under `docs/data/hydrology/guntersville/`.
* `--legacy` heuristic scan: 30 legacy Python files reference `docs/brains|data` (inv 8; mostly platform/orchestrator reading conformance and model files) and 6 contain absolute `/Users/...` paths (inv 9: lake-brain bindings/review/validation, lake-geometry, …). These are heuristic baseline debt owned by each module's migration phase.

## Deviations from the approved proposal
1. **`tests/architecture/` not created; tooling placed at `tools/architecture/`.** `tests/` collides with the existing `Tests/` (Swift) on case-insensitive filesystems (macOS default; `core.ignorecase=true`): creating `tests/` would merge into `Tests/`. Resolving the cross-cutting test location (e.g. moving Swift tests under `engine/Tests`, per the target tree) is a Phase 1B decision. Needs Michael's confirmation.
2. **Validator is stdlib-only (`jsonschema_lite.py`)**, a documented JSON Schema subset, because the platform stdlib-only rule means no `jsonschema` dependency. Schemas stay standard 2020-12 so a full validator can replace it.
3. `contracts/conformance/` holds only a README; the fixtures stay at `docs/brains/conformance` (single source of truth) until the 1B relocation.
4. `providers/PROVIDERS.json` is intentionally empty.
5. The template is named `brain.template.json` (not `brain.json`) so it is never mistaken for a registered Brain.
6. `stable_brain_ids.json` locks the six machine ids verified live in the repo (`wind`, `biological-state`, `lake-brain`, `water-temp`, `water-clarity`, `sector-intelligence`); Depth and Vegetation ids are added at their certification turn.

## Not done (by design)
No runtime move, import change, Cloud Run/Firebase/RTDB/IAM change, deploy, score change, CI change, research move, or branch/worktree touched (Publisher and Wind worktrees untouched; Gate P F-1…F-9 untouched; Clarity D4 and TVA D8 untouched).
