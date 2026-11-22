# Depth research

Offline only. `tools/depth_research` builds the candidate manifest, reviews datum proposals, scores preregistered field validation and evaluates the research maturity rubric. It may import the runtime package; the runtime never imports it and it cannot publish.

Research datasets are not in this repository: point `DEPTH_RESEARCH_DATA` at the research snapshot (the former package `data/` layout, from branch `docs/depth-brain-research` / the research workspace). Rebuilding the manifest changes the knowledge release: regenerate `runtime/knowledge/knowledge-release.json` with a new release id. Approval is a separate, gated step.

`tools/depth_research/records/` holds small research records: the field-validation preregistration, the maturity rubric inputs, and `great_lakes_lwd.json` (Great Lakes Low Water Datum per lake, IGLD 1985, NOAA CO-OPS and CHS; the `lowWaterDatum` reference basis, owner decision 2026-11-22, Sector_Ops #51 comment 7075545102). `GAPS.json` lists open gaps.
