# Biological Brain (`biological-state`, display name "Biological Brain")

Publishes **species knowledge**, i.e. "What does Sector know about this fish?", from the private canonical bundle (`gs://sector-biology-private/biology/v1`) to the Brain RTDB (`sector-brain`) as lightweight summaries.

**Internal pilot (not published, not LIVE):** per-lake **Biological State** ("What is this fish likely doing on this lake right now?") on Guntersville, built from researched machine rules and published specialist Brain states. The lifecycle is *derived* from verified capability (`capability.py`), never set by hand. See [`docs/brains/biological-adoption/BIOLOGICAL_RULES_AND_STATE_CONTRACT.md`](../../docs/brains/biological-adoption/BIOLOGICAL_RULES_AND_STATE_CONTRACT.md).

The contract is in [`docs/brains/BIOLOGICAL_BRAIN_INTEGRATION.md`](../../docs/brains/BIOLOGICAL_BRAIN_INTEGRATION.md).

| File | Role |
|---|---|
| `biological_brain.py` | Bundle loading, hash verification, fail-closed validation against the v2 rubric, and RTDB payload builders (no scoring) |
| `orchestration.py` | Dependencies, staleness and `plan()` for the future Brain Orchestrator (no scheduler) |
| `run.py` | CLI: `--plan`, `--dry-run`, `--write`, plus `--bundle DIR` and `--offline` |
| `features.py` | Condition-feature registry and evaluator (Biological meaning of `warmRise`, temperature bands, ...); missing input -> UNKNOWN |
| `rules.py` | Machine rule schema, evidence-discipline validator, applicability, response-band and habitat evaluation |
| `bio_state.py` | Internal pilot Biological State builder (pure; no live reads) |
| `capability.py` | Derives State lifecycle from verified rules / frozen register / pilot state; never LIVE or VALIDATED |
| `validation_log.py` | Frozen rule register, append-only prediction log, observation store and honest evaluation |
| `run_state.py` | Pilot runner: reads a **private** rules dir and live published inputs (GET only); writes local files only |
| `tools/` | `gen_schemas.py` (schemas generated from code) and `stage_bundle.py` (stage a private release locally, never uploads) |
| `brain_platform.py` | Shared Brain RTDB client, copied verbatim from the Water Clarity Brain |
| `schemas/` | JSON Schemas for the canonical bundle shapes (documentation and tooling) |
| `tests/` | stdlib unittest; synthetic species only |

```
python3 -m unittest discover -s tests -v
python3 run.py --dry-run --out out/
```

Rule **content** for real species is private and is never read from this repository; tests use synthetic species and a test fails if a rule file or private path appears here.

**Never commit proprietary biology here.** This repository is public. Detailed profiles, rules, evidence and history live only in the private bucket and Sector's private research repository.
