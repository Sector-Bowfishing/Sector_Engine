# Water Clarity research (rules and metadata only — no data)

Research rules are in [`../BRAIN_OPERATING_CONTRACT.md`](../BRAIN_OPERATING_CONTRACT.md) §8–§12. The evidence itself lives in the private research workspace **`water-clarity`** (logical id; the physical root is never recorded in this public repo) and its private backup. This directory holds only code-adjacent metadata.

| Path | Holds |
|---|---|
| `GAPS.json` | Research Gaps (schema `contracts/schemas/research-gaps.schema.json`). Research starts from an OPEN gap here |

Never here: the research branch corpus, certification thresholds or populations, raw evidence, provider datasets, agency request material, private catalog detail. The runtime reads an optional private catalog overlay (`CLARITY_PRIVATE_CATALOG`) that is supplied at run time and never committed.
