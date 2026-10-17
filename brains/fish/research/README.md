# Fish research (rules and metadata only — no data)

Research rules are in [`../BRAIN_OPERATING_CONTRACT.md`](../BRAIN_OPERATING_CONTRACT.md) §8–§12. The evidence itself lives in the private research workspace **`fish-brain`** (logical id; physical root never recorded in this public repo) and its private backup. This directory holds only code-adjacent metadata.

| Path | Holds |
|---|---|
| `GAPS.json` | Research Gaps (schema `contracts/schemas/research-gaps.schema.json`). Research starts from an OPEN gap here |

Workspace layout (created and owned by the research operator; the Engine repo only fixes the shape): `sources/ datasets/ research/ analysis/ candidates/ validation/ releases/ manifest.json README.md`.

The research tooling that touches bundle files (review packets, card adoption, bundle staging, observation intake, schema generation) lives with the runtime it validates against in `../runtime/tools/` — it reads and writes **workspace/bundle paths given on the command line**, never a hard-coded Desktop path (enforced by tests). A research session changes bundle content and, after review, cuts a new release; it does not change this package's structure.
