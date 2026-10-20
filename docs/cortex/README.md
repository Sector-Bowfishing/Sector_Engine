# docs/cortex/

This folder holds the engineering records required by **Rehtac Cortex**, the engineering-standards repository that governs development sessions in Sector Engine (pack `sector/engine`; see `CLAUDE.md`).

Cortex defines the standards and navigation guidance; Sector Engine holds the implementation. The Engine runtime never depends on Cortex, and nothing in this folder is loaded at runtime.

| Path | What it holds |
|---|---|
| `sessions/<YYYY-MM-DD>-<slug>.md` | One session record per assignment that changed code or ran an audit (Cortex `templates/REPORT_TEMPLATE.md`) |
| `COMPLIANCE.md` | Living compliance ledger. Created when the first requirement is evaluated. Rows are updated only when re-evaluated |
| `navigation-refresh/<YYYY-MM-DD>-<slug>.md` | Navigation refresh artifacts, written when the architecture differs from the Cortex snapshot |
| `CORTEX_GAPS.md` | Running log of missing, ambiguous or contradictory standards, for review in a Cortex maintenance session |

Records are committed on the work branch together with the changes they describe. Cortex itself is never edited from this repository.
