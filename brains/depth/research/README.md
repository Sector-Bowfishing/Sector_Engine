# Depth research

Offline only. `tools/depth_research` builds the candidate manifest, reviews datum proposals, scores preregistered field validation and evaluates the research maturity rubric. It may import the runtime package; the runtime never imports it and it cannot publish.

Research datasets are not in this repository: point `DEPTH_RESEARCH_DATA` at the research snapshot (the former package `data/` layout, from branch `docs/depth-brain-research` / the research workspace). Rebuilding the manifest changes the knowledge release: regenerate `runtime/knowledge/knowledge-release.json` with a new release id. Approval is a separate, gated step.

`tools/depth_research/records/` holds three small research records: the field-validation preregistration, the maturity rubric inputs and `datum_verification.json`. `GAPS.json` lists open gaps.

## Datum verification records

`records/datum_verification.json` (schema `depth-datum-verification-v1`) holds one record per lake with a `level` side and a `reference` side (series, datum, gauge zero, source offset, NOAA VDatum check, evidence with publisher, URL, quote and retrieval date) and a `status` of `VERIFIED`, `SINGLE_SOURCE`, `CONFLICT` or `NONE`. The rule is the Depth datum plan's two-source rule: a side is `VERIFIED` only when two independent publishers name the same datum (or the series' parameter definition names it and an empirical cross-gauge check passes); a conversion needs the source offset within 0.10 ft of VDatum at the gauge; at most two research passes per lake. `verification_problems()` in `candidates.py` enforces this and `tests/test_datum_verification.py` asserts every committed record passes.

`candidates.build` reads the file and converts an NGVD29/NAVD88 pair (status `CONVERTED`) only for a `VERIFIED` record whose relationship is `CONVERTED` and whose datums match the manifest's verified datums. Every other status changes nothing. The runtime never reads this file: it reaches a release only through a manifest rebuild (`refresh`, needs `DEPTH_RESEARCH_DATA`), a new release id, and Michael's approval.
