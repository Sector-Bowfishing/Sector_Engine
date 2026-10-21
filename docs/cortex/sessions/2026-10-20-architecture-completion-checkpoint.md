# Architecture completion — mission checkpoint (resume file)

```text
Standards: Rehtac Cortex 2.0.1 @ fc56557 (clean), pack sector/engine
Branch: cortex/architecture-standardization-2026-10-20 (local only) · resumed at 93ee9c74 · origin/main 7dae7051 (unchanged)
Authorization: user, 2026-10-20, "Cortex coordinated architecture completion" — local, nonproduction implementation of D-1..D-14
(package migration, SwiftPM separation, brain.json, declared-input alignment, registry consistency, orchestrator timeout/retry,
fallback honesty, internal contract fixes, tests, Depth/Vegetation reconciliation, text-only scoring metadata, synthetic species
examples). NOT authorized: push, merge, deploy, production writes, schedules, Publisher LIVE, rules/IAM, score/rubric numbers,
breaking public contracts, renaming stable IDs, activating parked/shadow Brains, editing Cortex.
```

**Mission complete (2026-10-20).** Final record: `2026-10-20-architecture-completion.md`. A new session resumes from the first unchecked step. Each step lists its commit when done.

## Plan and status

| # | Step | Status | Commit |
|---|---|---|---|
| 0 | Resume branch, verify clean, read records | done | — |
| 1 | Intelligence: migrate `jobs/sector-intelligence-brain/` → `brains/sector-intelligence/` (runtime/tests/contracts/research), `brain.json`, operating contract moved, retirement pointer, orchestrator + deploy + CI references, migration gate updated | done | 163d95d6, 58967c9e, 11f18c1e |
| 2 | Intelligence: Publisher registry entry (shadow), `describe_contract.py`, `publish_artifact.py` builder, Kit V1 adoption | done | 163d95d6, 58967c9e, 11f18c1e |
| 3 | Intelligence: output fixes D-8 (catalog bump, provenance.brainVersion, evaluation freshness, read-failure isolation), versioned output schema | done | c606f7d4 |
| 4 | Lake + Water Temp: SwiftPM targets `LakeBrain`, `WaterTemperatureBrain` with sources in `brains/lake/runtime/`, `brains/water-temperature/runtime/`; test targets; Dockerfile/build references | done | 163d95d6, 58967c9e, 11f18c1e |
| 5 | Lake + Water Temp: package files (`brain.json`, contracts moved, README, research README), Kit V1 adoption (Publisher shadow registration + builder over the Swift dry-run update set) | done | 163d95d6, 58967c9e, 11f18c1e |
| 6 | Lake fallback honesty (D-4, additive), Water Temp schedule string (D-9) | done | 9c3df55a, 11f18c1e |
| 7 | Declared inputs/triggers alignment (D-2), JM strings (D-10), CM Depth note (D-11 part) | done | 05b04c89 |
| 8 | Registry consistency test with `stable_brain_ids.json` as the single identity model (D-3) | done | fdf9ae46 |
| 9 | Orchestrator: scorer timeout isolation, CM `timeoutSeconds`, bounded retry (D-7) | done | 57fcd26b |
| 10 | Depth + Vegetation: reconcile branch code into `brains/depth/`, `brains/vegetation/` (inactive), or record blockers (D-11) | BLOCKED (recorded: session record §5.2) | — |
| 11 | Scoring metadata text-only fixes (D-12); score-type and Wind score-copy proposals only (D-5, D-6) | done | 89445e5d, 05e780de |
| 12 | Synthetic species-presence example in Lake doc (D-13) | done | ea4577d3 |
| 13 | Full verification (Python per CI job, Swift), ledger, navigation refresh, gaps, final report | done | records commit |

## Notes for a resuming session
- Steps 1–5 landed as three commits: cert-kit harness (`163d95d6`), Publisher SHADOW registrations + shared flat builder (`58967c9e`), the migrations (`11f18c1e`).
- Swift fixtures: `SECTOR_WRITE_BRAIN_FIXTURES=1 swift test --filter LakePublicationFixtureTests` (and `WaterTemperaturePublicationFixtureTests`) regenerate `brains/<dir>/tests/golden/*_run_updates.json`; review the diff.
- Python test venv: create with `python3.12 -m venv` and CI's dependency set (see the standardization session record §4); run gate suites separately.
- Never move or delete `docs/brains/scoring/` files (runtime-loaded).

## Cortex 2.1 adoption and memory mission (2026-10-20) — status

Standards: Rehtac Cortex 2.1.0 @ 0f9ee75. Session record: `2026-10-20-cortex-2-1-memory.md`.

**Done (committed):**
- `b5a766e4`: adoption.
- `4ac482e6`, `78d55294`, `19e9824c`: memory releases and refusal.
- `1492f79b`: `knowledge` declarations and the standing gate.
- `44ad7121`: Lake bindings contract.
- `80c0c20a`: engineering-status-v1 and CI coverage.
- Records: COMPLIANCE standing-check matrix, CORTEX_GAPS CG-2.1-1…4, navigation refresh `2026-10-20-cortex-2-1-memory.md`.

**Open:**
- Decisions A-1…A-3, M-1…M-8, G-1, D-A/D-B, O-1 (session record §11).
- Depth and Vegetation stay branch-only.

**Resume notes:**
- Regenerate the status report after any input change with `python3 tools/cortex_status/build_engineering_status.py --write`.
- A content change to a packaged knowledge file needs `tools/knowledge/build_release_manifest.py <dir> --write --release-id <new id>`.
