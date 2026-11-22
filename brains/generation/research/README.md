# Generation research

Offline only. `tools/generation_research` builds the dam catalog (`build_catalog.py`: the lake directory, Lake Brain's reviewed bindings and the evidence records in `records/`) and writes the candidate knowledge release (`release.py`). It may import the runtime package; the runtime never imports it and it cannot publish.

`records/tva_locations.json` lists the TVA LocationIDs whose lake identity is evidenced in this repository; `records/swpa_projects.json` maps SWPA schedule columns to directory lakes. Every entry names its evidence. Rebuilding the catalog changes the knowledge release: write a new release id. Approval is a separate, gated step (Michael).

Open work is in `GAPS.json`: binding the pending sources (CWMS release series, RISE release items, TVA LocationIDs, USGS tailwater gauges), the TVA and SWPA access checks, and the pre-registered week-long schedule comparison.
