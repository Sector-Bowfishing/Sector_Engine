# Depth research

Offline only. `tools/depth_research` builds the candidate manifest, reviews datum proposals, scores preregistered field validation and evaluates the research maturity rubric. It may import the runtime package; the runtime never imports it and it cannot publish.

Research datasets are not in this repository: point `DEPTH_RESEARCH_DATA` at the research snapshot (the former package `data/` layout, from branch `docs/depth-brain-research` / the research workspace). Rebuilding the manifest changes the knowledge release: regenerate `runtime/knowledge/knowledge-release.json` with a new release id. Approval is a separate, gated step.

`tools/depth_research/records/` holds two small research records: the field-validation preregistration and the maturity rubric inputs. `GAPS.json` lists open gaps.
