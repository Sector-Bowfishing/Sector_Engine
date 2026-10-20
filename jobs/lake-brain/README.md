# jobs/lake-brain/ — Lake Brain offline tooling (not runtime)

The Lake Brain (`brainId: lake-brain`) lives in its canonical package [`brains/lake/`](../../brains/lake/README.md) since 2026-10-20 (Cortex architecture completion): runtime `brains/lake/runtime/LakeBrain` + `LakeBrainJob` (SwiftPM targets), Swift tests `brains/lake/tests/swift`, deploy `brains/lake/deploy/deploy-job.sh`.

What stays here is **offline tooling and its data**, never imported by the runtime:

| Path | What |
|---|---|
| `bindings/` | builds the proposed binding table (`data/bindings.proposed.v1.json`), the input of `scripts/generate-lake-bindings.py` |
| `data/` | generated binding tables; `accepted_batch.json` appears only after the binding review |
| `history/` | deep TVA history backfill and lifecycle checks |
| `ledger/` | prospective prediction-ledger scorer |
| `review/` | binding review pack builder and result ingestion |
| `validation/` | rules-v2 Python mirror and the pre-registered hold-out (results committed) |

Their suites run in CI's legacy job list. Moving this tooling into `brains/lake/research/tools/` needs the data files classified first (binding tables, hold-out results); that is recorded as an open structural item, not done here. Some tools default to developer-machine paths (tooling only; the runtime has none).
