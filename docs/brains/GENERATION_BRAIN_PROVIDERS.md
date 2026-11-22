# Generation Brain: release and generation source providers

Status: readers implemented and tested on labelled hand-built fixtures (`brains/generation/tests/fixtures/hand-built/`). None has been exercised against the live service: the session that wrote them could not reach any agency host (sandbox proxy). Nothing here publishes anywhere. Code: `brains/generation/runtime/generation_brain/sources/`. Access list: `brains/generation/runtime/knowledge/source_access.json` (part of the knowledge release; the runtime refuses any provider that is not ALLOWED there, before a request is made).

Owner source-access rule (Michael, 2026-11-22 08:00Z, Sector_Ops #51 comment 7076252747): official agency data services documented for public programmatic use are allowed, at most hourly, with the agency named; pages or undocumented endpoints whose robots.txt or terms forbid automated use need the operator's permission first.

## 1. Provider table

| Provider | Agency | Endpoint | Kind | Access status | What it gives | Cadence / lag used |
|---|---|---|---|---|---|---|
| `tva` | Tennessee Valley Authority | `https://www.tva.com/RestApi/generation-releases/{LocationID}`, `/observed-data-48-hours/{LocationID}` (`Accept: application/json`) | undocumented public endpoint behind tva.com Lake Levels | ALLOWED, with an open check (section 3) | unit schedule as stated by TVA (`Generators`, "N or more" = floor); hourly average discharge (cfs) and tailwater (ft), hour-ending | 60 / 60 min |
| `cwms` | U.S. Army Corps of Engineers | `https://cwms-data.usace.army.mil/cwms-data/timeseries?office=&name=&unit=EN&begin=&end=` | documented data service | ALLOWED | project outflow, turbine and spill flow, generation (MW), tailwater, for the exact series ids a binding names | series interval (>= 60) / max(120, interval) |
| `swpa` | Southwestern Power Administration (DOE) | `https://www.energy.gov/swpa/{mon..sun}.htm` | web page | ACCESS_CHECK_REQUIRED (not read) | projected MW per project per hour (hour-ending, US Central); no units, no discharge | 1440 / 0 |
| `rise` | Bureau of Reclamation | `https://data.usbr.gov/rise/api/result?itemId=&dateTime[after]=` | documented data service | ALLOWED | a reservoir's release item (cfs), observed results only | daily: 1440 / 2880 |
| `usgs` | U.S. Geological Survey | `https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items?monitoring_location_id=USGS-{site}&parameter_code=00060` | documented data service | ALLOWED | discharge at a gauge below a dam, labelled `downstreamGauge` (the river, not the dam's release) | 60 / 60 |

Every request: `User-Agent: Sector-GenerationBrain/0.1 (io.sector.co; read-only public data)`, GET only, 30 s timeout, at most 3 attempts on transient failures (timeout, connection, HTTP 408/429/500/502/503/504) with 2 s then 4 s jittered backoff, Retry-After honoured up to 30 s, permanent statuses never retried, and each URL read at most once per run (`generation_brain/http.py`). The adaptive cadence (`freshness.py`) re-reads a dam at most hourly.

## 2. Traps the readers enforce

| Trap | Handling | Test |
|---|---|---|
| TVA answers 200 with an HTML API explorer when `Accept: application/json` is missing | the header is always sent; a non-JSON body is refused | `test_tva_html_explorer_page_is_refused_not_parsed`, `test_tva_without_the_json_accept_header_gets_the_explorer_and_fails` |
| TVA observed rows are hour-ENDING; "Midnight" closes the day | Midnight = 00:00 of the next day (as Lake Brain and the TVA archive read it; the old Engine/iOS parser put it 24 h early) | `test_tva_observed_rows_are_hour_ending_and_midnight_is_the_next_day` |
| TVA schedule windows ending "Midnight" | end at 24:00 of the window's day | `test_tva_schedule_windows_carry_the_dams_own_zone_and_end_midnight_on_the_next_day` |
| TVA zone varies by dam (EDT/EST/CDT/CST on each row) | the row's own abbreviation, never the device's zone | same |
| TVA numbers are comma-grouped strings; blanks | parsed; blank = missing, zero kept as published | `test_tva_blank_discharge_stays_missing_and_pool_elevation_is_never_read` |
| TVA rows also carry ReservoirElevation | never read: pool level is Lake Brain's | same |
| CWMS defaults to SI; districts differ | `unit=EN`; `cms` -> cfs, `m` -> ft converted; any other unit refused | `test_cwms_reads_bound_series_and_converts_si`, `test_cwms_refuses_an_unknown_unit_and_a_modeled_version` |
| CWMS null values; forecast / modeled versions | nulls dropped (never zero-filled); a series id that looks modeled is refused before a request | same |
| SWPA publishes megawatts, not units | windows carry `generationMw` only; units and cfs are never derived (the old Engine derived both) | `test_swpa_publishes_megawatts_never_units_or_cfs` |
| SWPA pages are keyed by weekday; last week's page stays at the URL | used only when the page states today's date | `test_swpa_refuses_a_page_that_does_not_state_todays_date` |
| RISE writes 0.0 for a missing value; modeled results | 0.0 dropped as missing (a RISE-only dam is UNKNOWN, never OFF); only `observed` results | `test_rise_drops_zero_placeholders_and_modeled_results` |
| USGS several series for one site and parameter; another site's answer; -999999 | refused, never merged; sentinel dropped | `test_usgs_reads_one_series_and_refuses_several` |

## 3. Open access checks (decision D-G)

- **TVA.** tva.com legal notices restrict only logos, trademarks and copyrighted material (TVA lake-levels research, 2026-11-20). The Lake Brain already reads the same REST API hourly under the owner's TVA decisions. Not done: reading `www.tva.com/robots.txt` (this session could not reach tva.com), and reconciling the iOS conditions spec (2026-07-16, item 25), which says "TVA blocks automated access". Do both before enabling; if either forbids automated use, set `tva` to PERMISSION_REQUIRED in a new release and ask TVA (the 2026-11-05 tvainfo@tva.gov thread).
- **SWPA.** A web page, not a documented service. `www.energy.gov/robots.txt` and the DOE terms were not read (unreachable here). The reader is built and tested; the runtime refuses it until a new release records the check as ALLOWED.

## 4. Not built (permission first, or no documented service)

| Operator | Why |
|---|---|
| Alabama Power (apcshorelines.com; the old Engine read it) | operator web pages, no documented data service: permission first |
| Duke Energy, Georgia Power, Dominion / SCE&G, Santee Cooper, Entergy, Ameren, Brookfield, Cube Hydro, FirstLight, Idaho Power, Seattle City Light, Tacoma Power, SRP, Xcel, LCRA, GRDA and other utilities and power authorities (73 lakes) | operator lake / generation pages only: permission first. Where USACE CWMS publishes the project (11 such lakes, e.g. Bankhead, Lake Martin) it is used instead |
| Reclamation Hydromet (PN `/pn-bin`, GP `/gp-bin`) | robots.txt disallows both (Lake Brain session 2026-11-22). The owner approved GP Hydromet use on 2026-11-22 19:34Z (GP publishes an automated-retrieval guide): a GP release reader is a follow-up; RISE comes first |
| California DWR CDEC | robots.txt forbids automated use; DWR permission pending (Lake Brain) |
