# research/intelligence

Research-only code for the Intelligence deep-research campaign (docs: `docs/research/intelligence/`). Nothing here ships, deploys or is imported by production.

| Path | What | Run |
|---|---|---|
| `probe/` | Separate Swift package with a path dependency on the unmodified engine; 9 experiments on `ConditionsAggregator` with synthetic inputs | `cd probe && swift build && .build/debug/probe > out/aggregator_probe_output.txt` |
| `prototype/synth.py` | Stdlib synthesis prototype (rules R1–R9). Species bands are TEST STUBS, not evidence | `cd prototype && python3 -I -m unittest discover -s tests` |
| `validation/power_sim.py` | Seeded power/confound simulation (synthetic) | `python3 -I validation/power_sim.py` |
| `tools/ladder_score.py`, `data/` | Pre-registered decision-readiness rubric, evidence strings, computed scores | `python3 -I tools/ladder_score.py` |

`probe/.build` is not committed (see `.gitignore`).
