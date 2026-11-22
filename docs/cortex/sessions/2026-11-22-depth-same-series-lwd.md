# Session record: Depth reference bases seriesMedian and lowWaterDatum

Standards: Rehtac Cortex 3.1.2 @ ecaef70, pack sector/engine. Date: 2026-11-22. Branch: `feat/depth-same-series-lwd-2026-11-22` (off main 669d492, then merged with main 8a7ba99 after #223; #223's verified same-source `pool_ft` (Percy Priest) and datum verification are kept, including in the rating hunk).

## Scope
Owner decision, Michael, 2026-11-22 (chat 06:48Z; Sector_Ops #51 comment 7075545102): (1) a same-series reference for natural lakes and stage-only gauges (today's reading vs the same gauge's seasonal median, no datum), (2) the Great Lakes Low Water Datum (IGLD 1985) as a reference. (3) A Depth knowledge release comes to Michael for approval: this change does not rebuild, re-release or approve anything.

## Done
- `contract.py`: `REFERENCE_BASES`, the median window/minimums (+/-7 days, 10 years, 100 samples), `SIGMA_SERIES_MEDIAN`, `SIGMA_DATUM["SAME_SERIES"]`, scope switch `SERIES_MEDIAN_ALLOW_FULL_POOL_RESERVOIRS` (default True, pending Michael).
- `datum.py`: status SAME_SERIES (usable), IGLD 1985 aliases (a bare "IGLD" stays unknown).
- `shift.py`: seriesMedian reads Lake Brain `seasonalBand.p50` at run time with explicit refusals; lowWaterDatum needs an IGLD85 reference and an IGLD85-stamped reading; neither runs Lake's full-pool cross-check or the relative-scale frame; confidence capped at MEDIUM; the median's sigma component is `reference`.
- `state.py`: seriesMedian facts are a level fact only and say they must not be applied to charted or contour depths; zones withheld; fingerprint adds the band only for seriesMedian. fullPool states are byte-identical (golden fixtures unchanged).
- `candidates.py`: `alternative_reference` (reference-side blocks only; LWD > median > unchanged) with the same-series guard `history_is_live_series` against Lake's binding (bindings.proposed.v1.json + the five pilots restated as data); coops `water_level_IGLD85` read as IGLD85; rollout capped at MEDIUM_CONFIDENCE; zones/ratings withheld; `summary.referenceBasis`.
- `records/great_lakes_lwd.json` (NOAA CO-OPS, CHS; quotes marked paraphrased). BRAIN_SPEC "Reference bases". Tests `tests/test_reference_bases.py`, `research/tools/tests/test_alternative_reference.py` (incl. Indian Lake|OH 62614 live vs 62615 history, blocked).

## Findings
- `contracts/depth-publication-v1.json` has no `reference.basis` enum (generated from the Publisher registry, paths only); `--check` passes unchanged. The semantic change is in BRAIN_SPEC and `contract.REFERENCE_BASES`.
- The datum provider table is research data outside the repository; the IGLD85 rule is a series-name rule.
- Lake Brain has no coops bindings: the 14 LWD lakes get no state until Lake binds them, and that binding must stamp the reading IGLD85.
- Independent review of #224 was NOT CLEAN; this record reflects the fixes.

## Counts (committed release 2026-10-14.6, 621 lakes; a rebuild needs DEPTH_RESEARCH_DATA)
fullPool 225 (unchanged), lowWaterDatum 14, seriesMedian 19 (all directory-fullPool reservoirs; 0 if the scope switch is turned off), blocked SERIES_HISTORY_NOT_LIVE_SERIES 113 (93 have no Lake binding), blocked SERIES_HISTORY_TOO_SHORT 45.

## Verification
Depth runtime and research-tool suites: 320 passed, 9 skipped. `describe_contract.py --check` OK.

## Not done / follow-ups
No manifest rebuild, release or approval. BRAIN_VERSION is bumped with the next release (asked of Michael). Fish's `normalize_depth` drops `referenceBasis` (brains/fish/runtime/contracts_in.py:65). Lake should publish `seasonalBand.sourceIds`.
