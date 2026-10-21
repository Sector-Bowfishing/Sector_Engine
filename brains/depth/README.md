# Depth Brain (`depth`)

Effective-depth shift from published Lake Brain levels, plus depth bands where real evidence exists. **PROFILED / SHADOW, PARKED, NOT_VALIDATED, no score.**

| Path | What |
|---|---|
| `runtime/run.py` | The only publish entry (`--plan`, `--dry-run`, `--write`) |
| `runtime/depth_brain/` | Runtime package (shift, datum, zones, rating, state, publish, writer, Ops summary, knowledge loader, artifact builder) |
| `runtime/knowledge/` | The versioned knowledge release (`knowledge-release.json` + candidate manifest, claim levels, stage-area ratings). Approval: NOT_RECORDED, so the runtime abstains |
| `research/tools/depth_research/` | Offline research tooling; never imported by the runtime |
| `contracts/` | `depth-publication-v1` (SHADOW), derived from the Publisher registry |
| `tests/`, `research/tools/tests/` | Domain, memory and Kit V1 tests; research-data tests skip without `$DEPTH_RESEARCH_DATA` |

Status layers are separate: structure and certification (this package) ≠ scientific validation ≠ approved release ≠ operational readiness ≠ production ≠ customer.
