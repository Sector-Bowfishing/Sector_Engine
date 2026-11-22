# Session record: Lake Brain readers for NOAA CO-OPS and USGS gage height + site altitude

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine (briefing run by hand from the local Cortex checkout; `CORTEX_HOME` unset). Date: 2026-11-22. Branch: `feat/lake-readers-coops-usgsstage-2026-11-22` (on `feat/lake-cdec-reader-2026-11-22` f3857672, itself off main 669d4928). Cloud session.

## Scope
Owner decision (Michael, chat 2026-11-22): build Lake Brain level readers for lakes that passed the binding checks but need a reader
the Engine does not have. This branch (stacked on the CDEC branch): NOAA CO-OPS Great Lakes water levels and USGS gage height (00065) + the site's published
altitude. The California CDEC reader is a parallel branch (`feat/lake-cdec-reader-2026-11-22`); this one mirrors its shape (reader
only, no binding, provider doc section, approval record for the packaged knowledge release, health-plane registration deferred).
Not in scope and not done: binding any lake, the bindings-table allow-list, provider registration (brain.json providers,
PROVIDERS.json, jobs manifest, ownership), source-health records, deploys, rules, IAM.

## Done
- `LakeLevelFeedsCOOPS.swift`: live `water_level` (6-min, IGLD, feet, GMT, `application=Sector_LakeBrain`, 1 s request gate);
  `hourly_height` / `daily_mean` refused as live (verified-only, weeks of lag); history = verified `daily_mean` + preliminary tail
  reduced to lake-local daily medians; error JSON, flags, wrong-station answers handled.
- `LakeLevelFeedsUSGSStage.swift`: site service RDB → `alt_va` / `alt_datum_cd`; refuses no altitude, no datum, a datum other
  than the binding's, non-feet stage; live and history (`usgsStageDaily`, via the existing USGS daily reader with the altitude as offset).
- Provider kinds `coops`, `usgsStage`; history kinds `coopsDaily`, `usgsStageDaily` (also decodable from the generated table).
- Knowledge release: folded into the CDEC branch's pending `lake-knowledge-2026-11-22.1` (one release, one owner approval; digest recomputed, bindings unchanged). This branch is stacked on `feat/lake-cdec-reader-2026-11-22`.
- Provider doc sections 5 and 6; tests with fixtures, no network.

## Evidence
- CO-OPS API documentation and live answers read 2026-11-22 (Calumet Harbor 9087044): `daily_mean` and `hourly_height` ended 2026-10-31;
  `water_level` latest 2026-11-22 06:30Z. IGLD (2020) expected in the US by 2027 (NOAA IGLD FAQ).
- USGS site service read 2026-11-22: 04082500 `alt_va` 743.91, `alt_datum_cd` NAVD88 (matches the existing Winnebago history offset).
- USGS WaterServices permanently shut down on 2027-02-22, slowdowns and outages from January 2027 (WaterServices home page).

- Owner access rule (terms / robots.txt): robots.txt for api.tidesandcurrents.noaa.gov, tidesandcurrents.noaa.gov and
  waterservices.usgs.gov could not be retrieved from this session; NOS disclaimer and USGS copyright page state public domain and
  nothing against automated access. Nothing found forbids either source; quoted in the provider doc.

## Verification
- No Swift toolchain in this container: Swift build and tests run in CI (`swift-tests.yml`, macOS + Linux) on the PR.
- Python: brains/lake, jobs/brain_platform, jobs/brain-publisher, jobs/lake-brain/* suites pass; knowledge manifest `--check` OK.
  `tools/research` has 2 failures that also fail on main in this container (read-only-folder tests run as root).

## Closeout (operating contract section 19)
Gap: no reader for Great Lakes stations or stage-only lake gauges. Bowfisher decision: none yet (no lake bound). Score unchanged.
Not changed: live systems, schedulers, bindings, validation status, science, rules, IAM.
Open: owner approval of the knowledge release; provider/health-plane registration with the first binding; USGS legacy host retirement.
