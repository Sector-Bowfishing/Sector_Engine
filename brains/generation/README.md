# Generation Brain (`generation`)

What the dam on a lake is releasing or generating now (units on, discharge, spill, MW) and the operator's published schedule, for the app's Generation tile. Official operator and agency data only. **CALIBRATION, registered DISABLED (PARKED, no execution target), NOT_VALIDATED, no score, customer publication off.**

| Path | What |
|---|---|
| `runtime/run.py` | The only publish entry (`--plan`, `--dry-run`, `--write`) |
| `runtime/generation_brain/` | Source readers (TVA, CWMS, SWPA, RISE, USGS), access-gated HTTP, assembly, adaptive freshness, state, publish, writer, Ops summary, knowledge loader, artifact builder |
| `runtime/knowledge/` | The versioned knowledge release: `dams.json` (401 dam lakes, operator group, sources, coverage reason) and `source_access.json`. Approval NOT_RECORDED, so the runtime abstains |
| `research/tools/generation_research/` | Offline catalog builder and release writer; never imported by the runtime |
| `contracts/` | `generation-publication-v1` (derived from the Publisher registry) and the `generation-dam-state-v1` schema |
| `tests/` | Parser, assembly, freshness, memory and Kit V1 tests on hand-built fixtures (`tests/fixtures/hand-built/`, labelled) |

Plan, coverage and rollout: `docs/brains/GENERATION_BRAIN_PLAN.md`. Sources and access: `docs/brains/GENERATION_BRAIN_PROVIDERS.md`.
Status layers are separate: structure and certification (this package) ≠ validation ≠ approved release ≠ operational readiness ≠ customer.
