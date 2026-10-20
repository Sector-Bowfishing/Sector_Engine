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

A new session resumes from the first unchecked step. Each step lists its commit when done.

## Plan and status

| # | Step | Status | Commit |
|---|---|---|---|
| 0 | Resume branch, verify clean, read records | done | — |
| 1 | Intelligence: migrate `jobs/sector-intelligence-brain/` → `brains/sector-intelligence/` (runtime/tests/contracts/research), `brain.json`, operating contract moved, retirement pointer, orchestrator + deploy + CI references, migration gate updated | done | 163d95d6, 58967c9e, 11f18c1e |
| 2 | Intelligence: Publisher registry entry (shadow), `describe_contract.py`, `publish_artifact.py` builder, Kit V1 adoption | done | 163d95d6, 58967c9e, 11f18c1e |
| 3 | Intelligence: output fixes D-8 (catalog bump, provenance.brainVersion, evaluation freshness, read-failure isolation), versioned output schema | pending | |
| 4 | Lake + Water Temp: SwiftPM targets `LakeBrain`, `WaterTemperatureBrain` with sources in `brains/lake/runtime/`, `brains/water-temperature/runtime/`; test targets; Dockerfile/build references | done | 163d95d6, 58967c9e, 11f18c1e |
| 5 | Lake + Water Temp: package files (`brain.json`, contracts moved, README, research README), Kit V1 adoption (Publisher shadow registration + builder over the Swift dry-run update set) | done | 163d95d6, 58967c9e, 11f18c1e |
| 6 | Lake fallback honesty (D-4, additive), Water Temp schedule string (D-9) | D-9 done (11f18c1e); D-4 pending | |
| 7 | Declared inputs/triggers alignment (D-2), JM strings (D-10), CM Depth note (D-11 part) | pending | |
| 8 | Registry consistency test with `stable_brain_ids.json` as the single identity model (D-3) | pending | |
| 9 | Orchestrator: scorer timeout isolation, CM `timeoutSeconds`, bounded retry (D-7) | pending | |
| 10 | Depth + Vegetation: reconcile branch code into `brains/depth/`, `brains/vegetation/` (inactive), or record blockers (D-11) | pending | |
| 11 | Scoring metadata text-only fixes (D-12); score-type and Wind score-copy proposals only (D-5, D-6) | pending | |
| 12 | Synthetic species-presence example in Lake doc (D-13) | pending | |
| 13 | Full verification (Python per CI job, Swift), ledger, navigation refresh, gaps, final report | pending | |

## Notes for a resuming session
- Steps 1–5 landed as three commits: cert-kit harness (`163d95d6`), Publisher SHADOW registrations + shared flat builder (`58967c9e`), the migrations (`11f18c1e`).
- Swift fixtures: `SECTOR_WRITE_BRAIN_FIXTURES=1 swift test --filter LakePublicationFixtureTests` (and `WaterTemperaturePublicationFixtureTests`) regenerate `brains/<dir>/tests/golden/*_run_updates.json`; review the diff.
- Python test venv: create with `python3.12 -m venv` and CI's dependency set (see the standardization session record §4); run gate suites separately.
- Never move or delete `docs/brains/scoring/` files (runtime-loaded).
