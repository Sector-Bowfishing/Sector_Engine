# Session record: Depth reference bases seriesMedian and lowWaterDatum

Standards: Rehtac Cortex 3.1.2 @ ecaef70, pack sector/engine. Date: 2026-11-22. Branch: `feat/depth-same-series-lwd-2026-11-22` (off main 669d492; does not need #223's datum verification records).

## Scope
Owner decision, Michael, 2026-11-22 (chat 06:48Z; Sector_Ops #51 comment 7075545102): (1) a same-series reference for natural lakes and stage-only gauges (today's reading vs the same gauge's seasonal median, no datum), (2) the Great Lakes Low Water Datum (IGLD 1985) as a reference. (3) A Depth knowledge release comes to Michael for approval: this change does not rebuild, re-release or approve anything.

## Done
- `contract.py`: `REFERENCE_BASES` (fullPool, seriesMedian, lowWaterDatum), the median window/minimums (+/-7 days, 10 years, 100 samples), `SIGMA_SERIES_MEDIAN`, `SIGMA_DATUM["SAME_SERIES"]`.
- `datum.py`: status SAME_SERIES (usable), IGLD 1985 aliases (a bare "IGLD" stays unknown).
- `shift.py`: seriesMedian reads Lake Brain `seasonalBand.p50` at run time with explicit refusals; lowWaterDatum needs an IGLD85 reference; neither runs Lake's difference-from-full-pool cross-check.
- `state.py`: reference meaning and median band in the state, basis-specific facts, zones withheld, fingerprint adds the band only for seriesMedian. fullPool states are byte-identical (golden fixtures unchanged).
- `candidates.py`: `alternative_reference` (reference-side blocks only; LWD > median > unchanged), coops `water_level_IGLD85` read as a verified IGLD85 level, rollout capped at MEDIUM_CONFIDENCE, zones/ratings withheld, `summary.referenceBasis`.
- `records/great_lakes_lwd.json`: LWD per lake (NOAA CO-OPS, CHS) and the 14 coops lake ids.
- BRAIN_SPEC "Reference bases" section with the change note; tests `tests/test_reference_bases.py`, `research/tools/tests/test_alternative_reference.py`.

## Findings (claims from #223's map checked against the code)
- `contracts/depth-publication-v1.json` has no `reference.basis` enum: it is generated from the Publisher registry (paths, not fields) and `--check` still passes unchanged. The semantic change is recorded in BRAIN_SPEC and `contract.REFERENCE_BASES`.
- The datum provider table (`datum_providers.json`, coops = PROJECT) is research data outside the repository; the IGLD85 rule is a series-name rule in `level_datum_for`, like the USGS parameter rule.
- Lake Brain has no coops bindings: the 14 LWD lakes become possible in the manifest but get no state until Lake publishes them.

## Counts (from the committed release 2026-10-14.6; a rebuild needs DEPTH_RESEARCH_DATA)
fullPool 225 (unchanged), lowWaterDatum 14, seriesMedian 132 (86 of them fullPool-basis reservoirs whose level datum is unknown), still blocked for history < 10 years 45. At run time a seriesMedian lake also needs a Lake band with >= 10 basis years.

## Verification
Depth tests: 307 passed, 9 skipped. `describe_contract.py --check` OK.

## Not done
No manifest rebuild, no new release id, no release approval. Brain version not bumped (keeps fullPool fingerprints and goldens identical); see the PR's open questions.
