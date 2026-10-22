# Vegetation Brain (`vegetation`)

Surface-reaching aquatic vegetation presence from satellite passes. **SHADOW, PARKED, NOT_VALIDATED, no score, no live writer.**

| Path | What |
|---|---|
| `runtime/run.py` | The only run entry (`--plan`, `--dry-run OUT.json`) |
| `runtime/vegetation_brain/` | Runtime package (observer, shared-pass ingestion, state, language, agency, publish, writer, Ops summary, knowledge loader, artifact builder) |
| `runtime/knowledge/` | The versioned knowledge release (fleet manifest, Level-1 agency records). Approval: NOT_RECORDED, so the runtime abstains |
| `research/tools/vegetation_research/` | Offline research tooling; never imported by the runtime |
| `contracts/` | `vegetation-publication-v1` (SHADOW) |

Status layers are separate: structure and certification ≠ scientific validation ≠ approved release ≠ operational readiness ≠ production ≠ customer.
