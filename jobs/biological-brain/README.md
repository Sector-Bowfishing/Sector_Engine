# Biological Brain (`biological-state`, display name "Biological Brain")

Publishes **species knowledge**, i.e. "What does Sector know about this fish?", from the private canonical bundle (`gs://sector-biology-private/biology/v1`) to the Brain RTDB (`sector-brain`) as lightweight summaries.

**Not built yet:** per-lake **Biological State** ("What is this fish likely doing on this lake right now?"). That needs separate approval.

The contract is in [`docs/brains/BIOLOGICAL_BRAIN_INTEGRATION.md`](../../docs/brains/BIOLOGICAL_BRAIN_INTEGRATION.md).

| File | Role |
|---|---|
| `biological_brain.py` | Bundle loading, hash verification, fail-closed validation against the v2 rubric, and RTDB payload builders (no scoring) |
| `orchestration.py` | Dependencies, staleness and `plan()` for the future Brain Orchestrator (no scheduler) |
| `run.py` | CLI: `--plan`, `--dry-run`, `--write`, plus `--bundle DIR` and `--offline` |
| `brain_platform.py` | Shared Brain RTDB client, copied verbatim from the Water Clarity Brain |
| `schemas/` | JSON Schemas for the canonical bundle shapes (documentation and tooling) |
| `tests/` | stdlib unittest; synthetic species only |

```
python3 -m unittest discover -s tests -v
python3 run.py --dry-run --out out/
```

**Never commit proprietary biology here.** This repository is public. Detailed profiles, rules, evidence and history live only in the private bucket and Sector's private research repository.
