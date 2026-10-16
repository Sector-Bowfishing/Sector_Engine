# Repository Foundation V1 — Phase 1B implementation record

**Status: `REPOSITORY_FOUNDATION_PHASE_1B_COMPLETE`** (baseline CI, conformance relocation, golden customer gates, score baseline, architecture baseline). Base: Phase 1A `c2622c55`. Branch `feat/repository-foundation-v1`, local, not pushed.
Does NOT mean: Wind/Fish migrated, Publisher ready, any Brain certified, live cutover approved. No Brain migrated; no `brain.json` created; no runtime/customer behavior intentionally changed.

## Architecture amendment
Root `tests/` is replaced by `verification/` (case collision with SwiftPM `Tests/`): see decision lock §6, `TARGET_REPOSITORY_ARCHITECTURE_V1.md` tree and §7, RA-1, migration plan 1A/1B rows.

## CI (GitHub Actions; syntax-validated locally, NOT executed on GitHub from this session)
| Workflow / job | Enrolls |
|---|---|
| `foundation-verification.yml` / `foundation` | `tools/architecture` tests (foundation), `verification` gates (conformance home, score baseline, clean copy), architecture report REPORT-ONLY (`report.py`, `report.py --legacy --baseline`) |
| `swift-tests.yml` / `swift` (macos-15) | `swift build`, `swift test` (includes `MigrationGoldenTests`) |
| `python-jobs-tests.yml` / `platform` | `jobs/brain_platform`, `jobs/brain-orchestrator`, `jobs/brain-scores` (all tests; previously only `test_changed_control.py`) |
| `python-jobs-tests.yml` / `brains` | lake-surface-dispatch, water-clarity-brain, biological-brain, sector-intelligence-brain, water-temp-tva-archive, **lake-brain/{bindings,ledger,validation,review}** (new), wind-hourly (unchanged) |
| `python-jobs-tests.yml` / `lake-geometry` | **new**; `pip install -r jobs/lake-geometry/requirements.txt` |
The list is explicit because no Brain is migrated; it becomes `brain.json`-derived per Brain as each migrates. The Swift job's first real run on GitHub is unverified (macOS runner, Swift version differs from the author's local toolchain).

## lake-geometry dependency
`jobs/lake-geometry/requirements.txt` already declares `shapely>=2.0,<3`, `pyproj>=3.6`, `numpy>=1.26`, `pytest>=8`. CI installs through that canonical file; nothing invented. Phase 1A's failure was my temporary venv. With the file: 22 passed.

## Conformance relocation
`docs/brains/conformance/*.json` -> `contracts/conformance/` via `git mv` (11 files, renames detected), pointer README at the old path. References updated: 2 Swift tests (+1 comment in `BrainPlatform.swift`), 4 Python tests/modules (+ docstrings), `jobs/brain_platform/README.md`, workflow path filters; `jobs/brain-orchestrator/preflight_lineage.py` `SHARED_PATHS` gained `contracts/conformance` and keeps the old path so lineage diffs against pre-move deployed commits still work. SHA-256 before == after (manifest in `verification/fixtures/conformance/manifest.json`; gate `test_conformance_fixtures_are_byte_identical_to_pre_move_hashes`):
| fixture | sha256 |
|---|---|
| `event_ids.json` | `1d5e0f6ddaf3e459cab48a8cf80a3256d636434d67ecf6aff144d279585f3614` |
| `freshness.json` | `10a08d87bcbd87b8bc2711477327dfa64e0b21f1ea096bec46a263971e2c96b4` |
| `health.json` | `68eeeaabca85d265e410e61ab5573cd3dd304e08db420a9bfe0f3da7f421ad5c` |
| `lake_keys.json` | `3b65dcdfd2e5e96b2b3c86b9d43ef581160ff3e042b4d1888a241964db6f4b1e` |
| `lake_rules_v2.json` | `8be2ce3982719f44c0ca4cc64555f34b7ad80cb8190cbe4835608495a96556c8` |
| `model_v1.json` | `ce7daa9528bb535b1d6870adf8553fbad9afb4bc9dc7c2df6f33a6a84b6ab649` |
| `orchestrator_control_v1.json` | `6313b830238c6c0af71c9628301d219fdeb06caac33e6cb1a210035d2b4da6f5` |
| `ownership.json` | `ec45a857e685045812ba63b7388a02c299aec843f28eee91119fea62ff6ee66b` |
| `pruning.json` | `a0f9c0b1d1afc77127927c198c840ca710779331bb0d73bc2426c699dc5ea987` |
| `retry_policy.json` | `77a69a9734cd1949344abddf625cbafcd5932f1b31ed896e2af0124f93efa651` |
| `vocabularies.json` | `04b2b39677f9df65c14a3b4a0333a4ababbb6a343a61d8b7eb7ccd14cebbf51a` |

## Golden customer gates (`Tests/SectorEngineTests/MigrationGoldenTests.swift`, fixtures in `verification/fixtures/`)
* `/conditions` (dynamic): live byte-compare is not used. (1) `ConditionsAggregator.evaluate` over 14 frozen synthetic scenarios with `ConditionsConfig.default` (no Remote Config/network/clock) -> canonical JSON golden (score, band, regime, confidence, baseline, copy, factors incl. weights/contributions, dormant factors, gates, where-to-look); doubles rounded to 6 places; each scenario also asserted deterministic. (2) `ConditionsResponse` contract: a fully populated synthetic payload must decode and re-encode (server encoder settings) to identical JSON, and the type's top-level fields must equal the golden's keys (catches renames, removals, type changes, added fields). Mutation-checked: altering a score, a count and a key each failed the gate. **Limitation:** the live assembly in `SectorEngineAPI.conditions` (fetch -> DTO mapping) is not injectable without invasive change, so field-value mapping of nested DTOs from real inputs is not covered; nothing in Engine code was changed to force it.
* `/lakes` (static): exact compare of version (FNV-1a digest = ETag), count (621), ordered ids, field-key set, body size and body hash. No normalization.
* Intentional-change procedure documented in `verification/README.md`.

## Score baseline (`verification/fixtures/scores/score_baseline.json`, `verification/integration/score_baseline.py`)
Artifacts present: `docs/brains/scoring/frozen-scores.json` -> water-clarity 8.0/10 (FROZEN, `clarity-research-certification-r3.1`, candidate not deployed), water-temp 3.0/10 (FROZEN, `water-temp-level-ladder-v1`), wind 3.3/10 (COMPUTED, `wind-certification-rubric-v1`); per-block SHA-256, file SHA-256, and SHA-256 of 5 rubric files. Lake, biological-state, sector-intelligence and the provisional Engine aggregate are computed from live RTDB facts and are not baselinable offline (recorded as such). `scoreType` is a label assigned by the baseline (artifacts do not carry it). Nothing recomputed; CERT-6 untouched. A legitimate score update in another lane will fail this gate until the baseline is re-recorded in the same commit (intended).

## Architecture baseline
`tools/architecture/baseline/legacy_violations.json`: 20 known legacy entries (14 inv-8 `docs/` string references, 6 inv-9 absolute user paths) with owner, path, reason, planned migration phase. `report.py --baseline` labels KNOWN / NEW / RESOLVED (report-only; `--fail-on-new` is opt-in, unused in CI). The scan now ignores docstrings/comments (Phase 1A's 30 inv-8 heuristic hits included docstring mentions; the real string-literal references are 14). Output prints paths and counts, never content. Only conformance-driven `docs/` references were changed; the rest remain baseline debt.

## Large-file legacy exceptions
5 exact-path `LEGACY_BASELINE` entries in `tools/architecture/large_file_exceptions.json` (schema `contracts/schemas/large-file-exceptions.schema.json`; wildcards rejected): `jobs/lake-surface/polygons.geojson.gz`, four `docs/data/hydrology/guntersville/**` files. New unexcepted >= 1 MB files are reported as violations; stale entries are reported. Not an approval; nothing moved or deleted.

## Clean-copy / import gate
`verification/integration/test_verification_gates.py`: copies the foundation directories (no `docs/`, empty HOME, no PYTHONPATH) to a temp dir, runs `python -I report.py`, validates schemas/templates, and asserts no absolute user path in foundation sources.

## Results (local; before = Phase 1A HEAD, same tree)
| Suite | Result |
|---|---|
| `swift build` | PASS |
| `swift test` | PASS 274 tests, 0 failures (271 existing + 3 new golden) |
| foundation tests (`tools/architecture`) | PASS 61 (49 from Phase 1A + 12 new baseline/exception tests) |
| verification gates (`verification`) | PASS 8 |
| brain_platform 130, brain-orchestrator 24, brain-scores 21 | PASS |
| lake-brain bindings 13, ledger 23, validation 70, review 24 | PASS |
| lake-geometry 22 | PASS (declared requirements) |
| lake-surface-dispatch 11, water-clarity-brain 35, biological-brain 29, sector-intelligence-brain 33, water-temp-tva-archive 14 | PASS |
| wind-hourly | NOT_RUN locally (needs eccodes/network extras; unchanged by this phase; enrolled in CI as before) |
| GitHub Actions workflows | NOT_RUN (YAML parses; no actionlint available) |

## Deviations / notes
* `verification/e2e/` not created (no real e2e tests yet).
* Swift CI uses a macOS runner; Linux (`swift:6.1-jammy`) Swift test status is unknown and untested here.
* Phase 1A's `tests/` deviation is resolved by the amendment.

## CI portability fix pass (2026-10-15, after first real GitHub run on PR #18)
The first real CI run of `ffee00da` (PR #18) failed two required checks that had passed locally, because of this Mac's environment:
1. **`python-jobs-tests / brains`**: `jobs/lake-brain/bindings/test_build_bindings_table.py::TableTests::test_table_is_reproducible`. The skip guard constructed `Inputs()`, which raises `SystemExit` when any external research input is missing, so the test could never skip. Fix (test-only): the guard now checks `B.RESEARCH/verified_bindings_v2.csv` and the `B.DATA` directory directly and skips with `BLOCKED_DEPENDENCY: external research input unavailable`. When the inputs exist, the real `Inputs()` and `--check` path runs unchanged. **On CI this test is BLOCKED_DEPENDENCY (skipped), not executed**; on the author's Mac it still runs and passes. The inputs' Desktop defaults remain inv-9 baseline debt (Lake phase).
2. **`swift-tests / swift`**: `swift build` passed; `swift test` failed to compile `Tests/SectorEngineTests/ClarityStateTests.swift:344` on the runner's Apple Swift 6.1.2 (`cannot convert value of type 'Int' to expected element type 'Double'` for `rain(storms: [(4 * 24, 3 * 24, 1.2 / 24)])`); local Swift 6.3.3 accepted it. Fix (test-only literal typing): `[(4.0 * 24.0, 3.0 * 24.0, 1.2 / 24.0)]`, same values. CI is not pinned to a newer toolchain.
Because `set -e` stopped the `brains` job at the bindings failure, the remaining lake-brain suites and the wind-hourly step had not run on CI. Before pushing, every Python suite was rerun locally under a sandbox that denies reads of the Desktop research/data/iOS/handoff paths and `~/Library/Caches` (simulating a runner): all pass; lake-bindings 1 skipped (above), lake-geometry 1 skipped, wind-hourly 52 passed / 6 skipped / 16 network-deselected (with CI's `eccodes shapely pyproj` install).

