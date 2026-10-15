# Source-of-truth boundaries

| Layer | Is | Holds |
|---|---|---|
| **GitHub** | how a Brain works | code, operating contract, schemas/contracts, tests, score definition, validation protocol, research rules/metadata (`GAPS.json`, `MANIFEST.json`), deploy/config declarations, small reproducibility tooling |
| **Research workspace** (logical id, e.g. `wind-brain`; physical root via `SECTOR_RESEARCH_ROOT`/config) | evidence and working research | raw/exploratory research, datasets, analyses, private or large evidence |
| **Canonical versioned storage** | durable accepted knowledge | canonical releases, publication artifacts, durable validation/history unsuitable for public Git |
| **`sector-brain` (RTDB)** | compact current published operational state | Publisher-written current state only |
| **Customer Engine / customer data** | separate product-serving layer | `engine/` and the customer database; reached by Brain output only through an approved `customerIntegrationMode` |

No layer impersonates another: a research CSV is not a canonical release; RTDB is not a research archive; the customer database is not Brain state; Git is not a data lake.

Flow: research workspace → (Brain canonicalization, evidence-gated) → canonical release → artifact builder → Publisher → `sector-brain`.

`customerIntegrationMode`: `none` (no customer path) · `embedded` (the customer Engine imports/executes an approved Brain-owned contract/library) · `published` (the customer product consumes an explicitly approved published Brain output). Direction is always Customer Engine → approved Brain contract, never Brain → customer Engine, and `embedded` never means a Brain writes the customer database or calls Engine internals.

Public-repo rule: this repository is public. No secrets, private IAM/security detail, customer data, RTDB exports, private observations, per-lake private species presence, or raw private research archives.

Full model: `docs/architecture/repository-audit-v1/STANDARD_BRAIN_PACKAGE_V1.md` §3a and `TARGET_REPOSITORY_ARCHITECTURE_V1.md`.
