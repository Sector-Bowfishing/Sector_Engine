# Brain package template (Standard Brain Package V1)

Copy this directory to `brains/<dir>/` when a Brain is migrated at its own certification turn. **Phase 1A migrates no Brain**; this is the destination shape only.

| File | Mandatory | Purpose |
|---|---|---|
| `README.md` (the Brain's own, ≤ 1 page) | yes | what the Brain is, the bowfisher decision, where things are |
| `BRAIN_OPERATING_CONTRACT.md` (from `BRAIN_OPERATING_CONTRACT.template.md`) | yes | all 19 sections; the first file a session reads |
| `brain.json` (from `brain.template.json`) | yes | structured identity and edges; validated by `contracts/schemas/brain.schema.json` |
| `contracts/`, `runtime/`, `tests/` | yes, **created with real files only** | published contracts / code / tests; no empty ceremonial directories |
| `artifact/`, `scoring/`, `validation/`, `research/`, `config/`, `docs/`, `deploy/` | when triggered | see `docs/architecture/repository-audit-v1/STANDARD_BRAIN_PACKAGE_V1.md` §1 |
| `research/GAPS.json`, `research/MANIFEST.json` | with research | from `research/*.template.json`; metadata only, no data |

Rules: `brainId` is a stable machine id and never changes with the directory name (`brains/fish` has `brainId` `biological-state`). Workspace is a logical id; no absolute path anywhere. Use `BRAIN_PACKAGE_CHECKLIST.md` at migration.

Import rules: a Brain may import `providers/`, `platform/` (incl. registry contracts) and other Brains' `contracts/` only.
Files here ending in `.template.*` are templates and are ignored by the architecture report.
