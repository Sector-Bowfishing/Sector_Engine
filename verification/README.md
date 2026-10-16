# verification/

**Owner:** Platform
**Purpose:** cross-domain / cross-component verification: the migration safety net. Replaces the proposed root `tests/` (which collides with SwiftPM `Tests/` on case-insensitive filesystems; decision lock §6).

| Path | What it holds |
|---|---|
| `integration/` | Python gates that look across components: conformance fixtures have one canonical home and unchanged hashes; score baseline matches the artifacts in the tree; the new foundation works from a clean copy with no Desktop path and no `docs/`. Run: `python -m pytest verification` |
| `fixtures/conditions/` | `aggregator_scenarios.golden.json` (scoring core over frozen inputs) and `response_contract.golden.json` (every key of `ConditionsResponse`). Checked by `Tests/SectorEngineTests/MigrationGoldenTests.swift` |
| `fixtures/lakes/` | `lakes_directory.golden.json` (version, count, ordered ids, field set, body size/hash of `GET /lakes`) |
| `fixtures/scores/` | `score_baseline.json` (values, versions, hashes of present score artifacts and rubrics) |
| `fixtures/conformance/` | `manifest.json`: SHA-256 of each conformance fixture as it was before the Phase 1B move |

`e2e/` is not created until it holds real tests.

**Belongs here:** gates that protect behavior across a move. **Does NOT belong here:** unit tests owned by one component (those live with their owner), raw data, live-value snapshots.

**Import / dependency rules:** reads anything, imported by nothing. Stdlib + pytest only.

**Normalization (what is and is not frozen):**
* `/conditions`: not byte-compared against live output (weather, gauges, timestamps are dynamic). Frozen: the pure scoring core with synthetic inputs and `ConditionsConfig.default` (no Remote Config, network or clock), doubles rounded to 6 places; plus the response contract (all keys/types) via a fully populated synthetic payload. NOT covered: the live fetch/assembly in `SectorEngineAPI.conditions` (not injectable without invasive change) and per-field value mapping of nested DTOs.
* `/lakes`: deterministic, compared exactly (no normalization).

**Intentional change procedure:** regenerate the golden in the same commit and record why. Swift goldens: `SECTOR_UPDATE_GOLDEN=1 swift test --filter MigrationGoldenTests`. Score baseline: `python3 verification/integration/score_baseline.py --update`.

**Migration status:** Phase 1B (created). Gate for every later migration phase.
