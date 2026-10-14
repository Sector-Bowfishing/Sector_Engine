# Lake Brain: level-source provider adapters

Status: implemented and exercised read-only against live data on 2026-10-13. Nothing here publishes to any RTDB or bucket; the live
exercise used `LakeBrainJob --dry-run DIR --include-candidates`, which writes local files only.
Code: `Sources/SectorEngine/LakeBrain/LakeLevelFeeds.swift` (TVA, CWMS, USGS live) and `LakeLevelFeedsFleet.swift` (everything below).
Bindings: `docs/brains/LAKE_BRAIN_INTEGRATION.md` section 5.

## 1. Provider table

| Provider (`LevelSeriesRef.Provider`) | Endpoint | Auth | Units | Cadence / lag (as bound) | Role |
|---|---|---|---|---|---|
| `tva` | `https://www.tva.com/RestApi/observed-data-48-hours/{LID}`; guide `/operating-guide/{LID}` | none (the existing client's UA works; plain curl gets HTML) | ft | 60 / 60 min | live pool; guide curve + zone; 2-year history |
| `cwms` | `https://cwms-data.usace.army.mil/cwms-data/timeseries?office=&name=&unit=EN` | none | ft (asked in English units; a response in metres is converted) | series interval, never finer than hourly / 120 min (daily series 1440 / 1440) | live pool; decades of daily history |
| `usgs` | `https://waterservices.usgs.gov/nwis/iv/` (live), `/dv/` and `/iv/` (history) | none | ft | 60 / 60 min | on-lake gauge; parameters 62614, 62615, 62616, 00062, 72020, 72022 only |
| `a2w` USACE Access2Water | `https://water.usace.army.mil/cda/reporting/providers/{district}/locations` (ONE GET per district, shared by every lake in it and by the operator-level reads) | none | ft | series interval (floored at 60) / 120 min | latest value + 24 h change per series; operator `levels[]` |
| `rise` USBR RISE | `https://data.usbr.gov/rise/api/result?itemId=&dateTime[after]=&itemsPerPage=2000` (`Accept: application/vnd.api+json`) | none | ft | 1440 / 2880 min (about 48 h latency) | daily lake/reservoir elevation; decades of history |
| `nwps` NWS NWPS | `https://api.water.noaa.gov/nwps/v1/gauges/{LID}/stageflow/observed` | none, User-Agent required | ft | 60 / 120 min | about 30 days of hourly pool elevation (`HP…`) |
| `twdb` TWDB Water Data for Texas (GATED OFF, section 4) | `https://www.waterdatafortexas.org/reservoirs/individual/{slug}[-30day\|-1year].csv` | none | ft (the file declares unit and vertical datum) | 1440 / 1440 min (estimated daily average, polled about every 6 h) | relay of the lake's gauge (USGS / USACE / USBR / IBWC / LCRA): backup live series and decades of daily history; never independent corroboration |
| HADS (history only) IEM | `https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py?stations=&sts=&ets=&what=txt&delim=comma` | none | ft | n/a | the NWS DCP archive of an NWPS location id, about 2010-12 onward |

All requests use `Sector-LakeBrain/1.0 (io.sector.co; read-only public data; contact ...)`, a 120 s read timeout (the engine's 8 s cap is for request-path fetches; a HADS chunk or an Access2Water listing is bigger) and never write anything.
Not implemented: **CO-OPS** (Great Lakes harbours only, not on the allow-list). **TWDB** is implemented and tested but its live transport is closed by default (section 4): no strict-eligible lake uses it as a primary source, and the host's robots.txt disallows the `.csv` files it needs.

## 2. Traps the adapters enforce

| Trap | Handling |
|---|---|
| USGS `00065` is a gage height in a local datum, not an elevation | refused as a live series; as a history only with an explicit datum offset (gage height + site altitude, Lake Winnebago) |
| USGS `-999999` no-data sentinel (a sensor outage today at Buckeye Lake) | dropped; the lake falls back and says so (`primarySourceStale`, `fallbackSource`) |
| CWMS defaults to SI units | requested with `unit=EN`; a response that still says metres is multiplied by 3.28084 |
| CWMS dense series (15 min) overflow the page budget | request window shrinks with the series interval (5 years daily/hourly, about 1 year at 15 min); hitting the 20-page limit is an error, never a silent truncation |
| Sub-daily history series | reduced to the median of each lake-local day (identical to the reading itself for a daily series) |
| Access2Water plain `Elev` on tailwater locations looks like a pool | bindings carry the exact tsid; the tailwater sibling is a different tsid and is never read |
| Access2Water is latest-only | the reading is the latest value and, from `delta24hr`, the value 24 h earlier: enough for the 24 h trend, 1 h / 6 h / 3 d / 7 d changes stay unknown |
| RISE writes 0.0 for a missing day; results can be modeled | `result <= 0` and any `resultType` other than `observed` dropped; the history day is the UTC date of the stamp (as in the research) |
| NWPS `HG` stage vs `HP` pool; `-999` sentinels; flow units | the gauge's `pedts` must start with the binding's pe code; units must be ft; sentinels dropped |
| IEM HADS rate limit (HTTP 429 above about one request per 15 s) | one process-wide gate (15 s between requests), 3-year chunks newest first, 429 backs off 60 s and doubles; any failed chunk fails the whole pull (no silent hole), the walk stops at the first empty chunk |
| A research history that is a different series from the live level | every run compares the median of the seeded history of the last 365 days with the live level; more than 15 ft sets `historyLiveMismatch:<delta>ft` and an error. The 14 lakes the rules-v2 QA found are held out of the table |

## 3. Live exercise (2026-10-13, `--dry-run --include-candidates`, read-only)

"Probe" is the research probe of the same morning (`bindings.proposed.v1.json` `verification.probe`, roughly 5 to 10 h earlier). "Level" is the dry-run state's `currentElevationFt`; "age" its source age. Baseline = complete years behind the seeded history (the Brain keeps the most recent 30). No lake was mismatched against its history (`historyLiveMismatch` never fired). All 14 states shown are `dryRunCandidate`; none was written outside the local dry-run directory.

| Provider | Lake | Level (ft) / age | Probe level / age | Seeded history | Baseline / readiness | Plan / flood evidence in the state |
|---|---|---|---|---|---|---|
| a2w | Greers Ferry\|AR | 455.67 / 0.4 h | 455.67 / 1.4 h | CWMS daily 1962-01-02 .. today, 23,639 days | SUFFICIENT (30 y) / BETA | zone 435.00 - 462.04 (A2W `Bottom of Normal` .. `Top of Conservation`, seasonal), flood-pool bottom 462.04: IN_ZONE, flood NORMAL |
| a2w | Abiquiu Lake\|NM | 6200.44 / 0.9 h | 6200.45 / 1.9 h | CWMS daily 2011-01-02 .., 5,762 days | SUFFICIENT (15 y) / BETA | static zone 6080 - 6230, flood-pool bottom 6230: IN_ZONE, flood NORMAL |
| a2w | Table Rock Lake\|MO | 910.95 / 0.5 h | 910.93 / 1.4 h | CWMS daily 1956-09-02 .., 25,606 days | SUFFICIENT (30 y) / BETA | zone 881 - 917, flood-pool bottom (seasonal): IN_ZONE, flood NORMAL |
| rise | Havasu\|AZ | 448.74 / 33.4 h (latest day 2026-10-12) | 448.85 (10-11) / 47.5 h | RISE daily 1938-11-15 .., 30,588 days | SUFFICIENT (30 y) / CALIBRATION (no operator plan) | none; flag `fallbackDatumDisagreement:-0.66ft` (NWPS `LKHC1` vs the RISE daily value) |
| rise | Alcova Reservoir\|WY | 5494.89 / 34.4 h | 5495.24 / 48.5 h | RISE daily 1945-10-01 .., 29,597 days | SUFFICIENT (30 y) / CALIBRATION | none; flag `fallbackDatumDisagreement:-0.36ft` |
| nwps | Canton Lake\|OK | 1610.73 / 1.5 h | 1610.72 / 1.4 h | IEM HADS `CNLO2` 2010-12-07 .., 5,765 days | SUFFICIENT (15 y) / BETA | static zone 1596.5 - 1615.4 (A2W SWT `CANT`), flood-pool bottom 1615.4: IN_ZONE, flood NORMAL |
| nwps | Lewis and Clark Lake\|SD | 1207.51 / 1.5 h | 1207.50 / 1.4 h | IEM HADS `GPDN1` 2019-09-28 .., 2,565 days | SUFFICIENT (6 y) / CALIBRATION | none (research: no plan evidence) |
| usgs | Eagle Creek Reservoir\|IN | 788.56 / 0.4 h | 788.56 / 0.4 h | USGS daily values 1989-10-02 .., 12,910 days | SUFFICIENT (30 y) / CALIBRATION | none |
| usgs | Lake Greenwood\|SC | 438.88 / 0.7 h | 438.89 / 0.6 h | USGS daily values 1983-10-01 .., 12,396 days | SUFFICIENT (30 y) / CALIBRATION | none |
| usgs | Lake Winnebago\|WI | 746.75 / 0.5 h | 746.80 / 0.7 h | USGS `00065` daily values + datum offset 743.91 ft, 1900-01-01 .., 46,294 days (the gage height is a history only because of the explicit offset; the live series is `62615`) | SUFFICIENT (30 y) / CALIBRATION | none |
| usgs | Buckeye Lake\|OH | 889.82 (NWPS fallback `BCLO1`) / 0.9 h | 891.48 / 0.9 h | USGS instantaneous values reduced to a daily median, 2019-03-01 .., 2,760 days | SUFFICIENT (6 y) / CALIBRATION | none; the USGS series started returning the `-999999` no-data sentinel after 2026-10-07 15:00Z, was dropped, and the lake ran on the fallback with `primarySourceStale` + `fallbackSource` + `fallbackDatumDisagreement:-0.32ft` |
| cwms | Bankhead\|AL | 254.86 / 0.8 h | 254.82 / 1.0 h | CWMS daily 1963-07-01 .., 23,072 days | SUFFICIENT (30 y) / BETA | static zone 252 - 255 (Bottom/Top of Normal): IN_ZONE |
| cwms | Lake Martin\|AL | 486.64 / 1.4 h | 486.64 / 1.5 h | CWMS hourly reduced to daily medians 2004-03-03 .., 7,985 days | SUFFICIENT (19 y) / BETA | seasonal `Elev-Guide Curve` series 486.99 ft (diff -0.35), flood-pool bottom 490.00 from the CWMS `Top of Conservation` level (seasonal): flood NORMAL; no zone, so the level state stays UNKNOWN |
| tva | Fort Loudoun Lake\|TN | 812.31 / 0.4 h | 812.44 / 0.4 h | TVA operating guide 2025-01-01 .., 651 days | INSUFFICIENT (1 y) / CALIBRATION | TVA guide curve 812.75, zone 812 - 813: IN_ZONE |

What the exercise found and fixed:
- **HADS multi-column archive (bug, fixed):** the first run of the two NWPS lakes read only the first `HPIR…` column of each 3-year chunk and lost 2021-10 .. 2023 (Canton 12 y, Lewis and Clark 3.4 y, INSUFFICIENT). A gauge can move its pool between `HPIRGZZ` and `HPIRZZZ`; the parser now takes the first non-empty `HPIR…` column per row (unit test added). Re-run: 15 y and 6 y, matching the research counts.
- **RISE host outage:** `data.usbr.gov` timed out for several minutes during the first attempt (curl too). The adapter returned an error, the run degraded to the verified NWPS fallback and said so (`sourceError`, `primarySourceStale`, `fallbackSource`, a history error); the re-run a few minutes later was clean.
- **Guide series that stopped:** the research catalog lists CWMS `Elev-Guide Curve` series whose extent ended in 2021 or 2022 (Lake Martin `1Hour`, Okatibbee). Only series whose catalog extent reaches today are claimed: Okatibbee and Wappapello lose their guide evidence, and Lake Martin uses the live `15Minutes` series.
- A2W lakes at LRL / MVP report 20 to 25 h old (Brookville, Barren River, Cave Run, ...): inside the research window (R6, 72 h) but beyond the 5 h stale threshold, so those candidates will run as `sourceStale` until the district feed catches up.
- No full fleet run was made; about 20 requests per host per lake at most, HADS at one request per 15 s.

Reproduce one lake (local files only): `swift build --product LakeBrainJob && .build/debug/LakeBrainJob --dry-run /tmp/lb --include-candidates --lake "Canton Lake|OK"`.

## 4. TWDB Water Data for Texas (adapter built, transport GATED OFF)

Status 2026-10-13: the adapter, the history source `twdbDaily`, the generator/table support and the tests exist; **no request is made unless `SECTOR_TWDB_TERMS_OK=1`** and **no TWDB row exists in any table**. Code: `Sources/SectorEngine/LakeBrain/LakeLevelFeedsTWDB.swift`. Tooling and dry run: `jobs/lake-brain/bindings/twdb_dryrun.py` -> `twdb_dryrun.v1.json` / `.csv`. Fixtures (real responses): `Tests/SectorEngineTests/Fixtures/TWDB`.

### 4.1 Contract as researched

| Item | Finding |
|---|---|
| Endpoints (documented by TWDB at `/reservoirs/download`) | `GET /reservoirs/individual/{slug}.csv` (full daily record, 0.3 to 2.4 MB, 0.5 to 13 s), `{slug}-1year.csv` (23 KB), `{slug}-30day.csv` (4.9 KB, 0.2 s); `GET /reservoirs/recent-conditions.json` and `.csv` (all 122 reservoirs, 73 KB, current level, conservation and dead pool, timestamp as a date). Slug = hyphenated reservoir name (`cedar-creek`, `possum-kingdom`). An unknown slug is HTTP 404 with a 604-byte HTML page; `individual/{slug}.json` is 404; `/reservoirs` redirects 302 to `/reservoirs/statewide`. No auth, no key. |
| Parameter and unit | `water_level`, header line `water_level: feet above vertical datum`. Also surface area (acres) and storages (acre-feet). |
| Datum | Declared in each file under `# Vertical datum(s) used:`. Of the 16 matched lakes: `NGVD29` for 13, **`NAVD88 +0.26` (Buchanan), `NAVD88 +0.6` (Travis), `NGVD29 -43.3` (Elephant Butte)**. The labels are carried verbatim and never interpreted: in the dry run all three agree with the lake's primary series (CWMS, USGS) within 0.03 ft in median, so the label is not a conversion the Brain should apply. The binding names the label it was verified against (`series` = `water_level@<label>`) and the adapter refuses a file that says anything else. FAQ: TWDB "adjusted all the historical data to the same vertical datum"; current values should match the source website. |
| Cadence and freshness | "Estimated daily average": one value per date, TWDB polls the providers about every 6 h, so today's value is the average so far. In `recent-conditions.json` of 2026-10-13T20:07Z, 121 of 122 reservoirs were dated 2026-10-13 and one (Sam Rayburn) 2026-10-12. The adapter stamps a value at 12:00 America/Chicago of its date and the binding is cadence 1440 / lag 1440 min (stale after 4 days, the same envelope as a daily CWMS series). |
| History depth | Per lake from 1915 (Elephant Butte) / 1937 (Buchanan) / 1940 (Travis) / 1953 (Falcon) / 1968 (Amistad) to 1996 or later; blank `water_level` rows before the first gauge reading. |
| Origin | A relay. TWDB names USGS, IBWC (Amistad, Falcon), USACE (Caddo, Pat Mayse, Texoma), USBR (Elephant Butte) and LCRA (Buchanan, Inks, Travis, Austin, LBJ). Amistad and Falcon are IBWC-derived estimates ("official versions ... should be obtained directly from them"). Some files carry "Data from ... is marked as provisional by the USGS". A TWDB reading is never counted as independent corroboration of its own origin (research rule R9). |
| Terms | TWDB publishes a no-warranty Disclaimer and Site Policies (privacy, security; unauthorised access prohibited). It states **no licence and no rate limit**. **`/robots.txt` has `User-agent: *`, `Disallow: *.csv`, `Disallow: /reservoirs/api/*`, `Disallow: /*?output_format=*`**, while `/reservoirs/download` publishes the `.csv` links for download. `recent-conditions.json` is not disallowed but carries no datum label and no history. Contact on the site: `waterdatafortexas@twdb.texas.gov`. |
| Rate limiting observed | None: roughly 90 requests in about 40 minutes, at 2 s spacing or slower, no 429 or 503, no `Retry-After`. The 13 s generation time of the big files suggests they are built per request. |
| Identity | `Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)`, plus ` contact: <SECTOR_CONTACT>` if that env var is set. No mailbox is embedded. **Michael must supply a role mailbox** before any contact with TWDB. (The older `LakeFeedHTTP.userAgent` for the other providers still embeds a personal address; not changed here.) |

**Verdict.** The data contract (endpoint, unit, datum, cadence, history) is documented and verifiable. The terms are not settled: the machine-readable robots.txt disallows the `.csv` files that are the only source of history and of the datum label, against the page that advertises them. The research fetches (on the order of 90 GETs to waterdatafortexas.org, read only, mostly 2 s or more apart) happened before robots.txt was read. Unattended scheduled use is therefore **not** defensible today, and the transport is closed: `TWDBTransport.live()` makes no request, `twdb_dryrun.py --fetch` refuses, and a read returns the named error `TWDB disabled: robots.txt disallows *.csv ...`. Open it with `SECTOR_TWDB_TERMS_OK=1` only after TWDB (or Michael) clears it. BLOCKER CATEGORY: TERMS / DECISION.

### 4.2 Traps found in the real files (the adapter enforces each; all have recorded fixtures)

| Trap | Handling |
|---|---|
| Blank `water_level` (storage only; Canyon 1962-1988, Livingston, Texoma ...) and `0.00` placeholders (Sam Rayburn 1988) | dropped |
| One to three day glitches among stable values: Amistad 790.09 ft on 2008-11-30 (neighbours 1118), Elephant Butte 3 206 / 3 148 / 3 964 ft on 2026-09-08..10 (neighbours 4 276), Caddo 150.91 on 2012-10-22 (neighbours 167), Travis 1965-01-16 (+33 ft for one day), Amistad 2023-09-28 | a run of up to 3 consecutive days whose every value is more than 15 ft from BOTH the day before and the day after, when those two agree within 15 ft, is dropped (15 ft = the runner's history/live mismatch figure). Real one-way ramps (Travis +56 ft in a day, 1952) are kept. |
| A trailing jump that cannot be confirmed yet | held back up to 3 days; a persistent jump is accepted the next day |
| Possum Kingdom's full file returned **without its `#` comment block** (no datum, no unit) minutes after the same URL had it; the `-30day` and `-1year` files still had it | a live read refuses it; a history pull accepts the rows only if the `-1year` file declares the binding's datum and agrees with at least 99 % of at least 200 shared days |
| 200 with HTML, 404 HTML, 429 / 503 | named errors; 429 / 503 back off 30 s doubling, honour `Retry-After`, cap 120 s, 4 attempts; a failed pull is an error, never a silent hole |
| A different unit or several datums in the header | refused |
| Sam Rayburn before 1988-10: a 55-62 ft series (a depth, not an elevation) then 155 ft | not detectable by the glitch rule; irrelevant to the baseline (the most recent 30 years) and not needed (Sam Rayburn has a 60-year CWMS history); a `twdbDaily` source for it should not be proposed |
| Baseline sensitivity | the Brain's rate-of-change baseline uses day-to-day differences; an unfiltered 20 to 30 ft one-day spike would put a false p95 into it. This is why the filter is part of the adapter and not of the dry run. |

### 4.3 Dry run (offline, reproducible: `python3 jobs/lake-brain/bindings/twdb_dryrun.py --check`)

Method: recent-conditions (122 reservoirs) matched to the 621-lake directory by normalised name and gauge within 30 km; each matched file parsed, de-spiked and compared with an independent origin (USGS 62614/00062 first, else NWPS, else CWMS) over the last 7 full lake-local days, with the lake's published table position (`bindings.proposed.v1.json`, `.excluded.json`), the TWDB conservation pool against the directory `fullPoolFt`, and the median of the last 365 history days against the live level (the runner's 15 ft rule). Thresholds were fixed before the run: live agreement median |diff| <= 0.25 ft, pool agreement <= 2 ft, level between dead pool and conservation pool + 25 ft, continuity <= 15 ft, complete year >= 90 % of days. Inputs and their sha256 are in the JSON. Raw files: `Sector_Research_Data/lake-brain/twdb/2026-10-13/` (outside Git).

| Lake | slug | File datum | Level (ft) / date | Conservation pool / directory full pool | Level - pool | Independent origin, median abs diff (ft) | Median 365 d - live (ft) | History from, complete years, glitch days dropped | Table position today |
|---|---|---|---|---|---|---|---|---|---|
| Amistad Reservoir\|TX | amistad | NGVD29 | 1059.79 / 10-13 | 1117.0 / 1117 | -57.21 | nwps AMIT2 0.049 | -6.47 | 1968, 57 y, 2 | excluded: post-hoc (VERIFIED_ENVELOPE), flagged-wave1 |
| Falcon Lake\|TX | falcon | NGVD29 | 261.42 / 10-13 | 301.2 / 301.2 | -39.78 | nwps FALT2 0.002 | -3.87 | 1953, 72 y, 0 | excluded: post-hoc (VERIFIED_ENVELOPE), flagged-wave1 |
| Caddo Lake\|TX | caddo | NGVD29 | 167.48 / 10-13 | 168.5 / 168.5 | -1.02 | nwps LCOL1 0.050 | 1.35 | 2012, 9 y, 1 | excluded: coordinate-flag |
| Canyon Lake\|TX | canyon | NGVD29 | 907.88 / 10-13 | 909.0 / 909 | -1.12 | usgs 08167700 0.002 | **-19.40** | 1988, 35 y, 0 | excluded: history-live-mismatch |
| Toledo Bend Reservoir\|TX | toledo-bend | NGVD29 | 167.99 / 10-13 | 172.0 / 172 | -4.01 | usgs 312914093422701 0.171 | 0.63 | 1986, 39 y, 0 | excluded: coordinate-flag |
| Elephant Butte Reservoir\|NM | elephant-butte | NGVD29 -43.3 | 4295.62 / 10-13 | 4406.30 / 4407 | -110.68 | cwms SPA 0.026 | 10.02 | 1915, 109 y, 3 | excluded: coordinate-flag |
| Cedar Creek Reservoir\|TX | cedar-creek | NGVD29 | 316.45 / 10-13 | 322.0 / 322 | -5.55 | usgs 08063010 0.002 | 2.15 | 1996, 29 y, 0 | proposed (a2w, history 29 y) |
| Lake Conroe\|TX | conroe | NGVD29 | 199.72 / 10-13 | 201.0 / 201 | -1.28 | usgs 08067600 0.002 | 0.26 | 1996, 29 y, 0 | proposed (usgs, 29 y) |
| Lake Fork Reservoir\|TX | fork | NGVD29 | 398.37 / 10-13 | 403.0 / 403 | -4.63 | usgs 08018800 0.002 | 1.85 | 1988, 35 y, 0 | proposed (usgs, 35 y) |
| Lake Livingston\|TX | livingston | NGVD29 | 129.55 / 10-13 | 131.0 / 131 | -1.45 | usgs 08066190 0.006 | 1.44 | 1996, 20 y, 0 | proposed (usgs, 27 y) |
| Lake Tawakoni\|TX | tawakoni | NGVD29 | 435.30 / 10-13 | 437.5 / 437.5 | -2.20 | usgs 08017400 0.004 | 0.94 | 1995, 30 y, 0 | proposed (usgs, 30 y) |
| Possum Kingdom Lake\|TX | possum-kingdom | NGVD29 | 994.31 / 10-13 | 999.0 / 999 | -4.69 | usgs 08088500 0.003 | 2.29 | 1947, 76 y, 0 | proposed (cwms, 35 y) |
| Sam Rayburn Reservoir\|TX | sam-rayburn | NGVD29 | 153.68 / 10-12 | 164.4 / 164.4 | -10.72 | usgs 08039300 0.006 | 1.99 | 1988, 37 y, 0 | proposed (a2w, 60 y) |
| Lake Buchanan\|TX | buchanan | NAVD88 +0.26 | 1018.52 / 10-13 | 1020.0 / 1020 | -1.48 | usgs 08148000 0.004 | 0.06 | 1937, 83 y, 0 | proposed (cwms, **8 y**) |
| Lake Texoma\|TX | texoma | NGVD29 | 614.97 / 10-13 | 617.0 / 617 | -2.03 | nwps DSNT2 0.003 | 1.82 | 1994, 30 y, 0 | proposed (a2w, **8 y**) |
| Lake Travis\|TX | travis | NAVD88 +0.6 | 677.86 / 10-13 | 681.0 / 681 | -3.14 | usgs 08154500 0.002 | -9.49 | 1940, 83 y, 3 | proposed (a2w, **8 y**) |

Results:
- **16 directory lakes match TWDB: 15 of the 15 Texas directory lakes plus Elephant Butte|NM.** (Cross Lake|LA and Caballo Lake|NM are within 30 km of a TWDB gauge but are different lakes; the name rule rejects them.) Every file header names the same reservoir as recent-conditions; `recent-conditions.json` equals the file's last value for all 16.
- **New TWDB-primary CANDIDATE rows under the unchanged eligibility rules: 0.** The only two research rows whose provider is TWDB (Amistad, Falcon) are `VERIFIED_ENVELOPE` / wave-1 flagged and stay excluded by Michael's decisions; TWDB cures none of the other exclusions (coordinate flags, the Canyon history/live hold) because it is a relay of the same gauges. The 10 other Texas lakes in the published table already have an independent primary.
- Where TWDB could still help, as an opt-in overlay only (`proposedAdditions` in the JSON, nothing written to the table): a relay live fallback on 10 already-proposed lakes (Cedar Creek, Buchanan, Conroe, Fork, Livingston, Tawakoni, Texoma, Travis, Possum Kingdom, Sam Rayburn) and a history source `twdbDaily` on 3 of them whose history is 8 years today (Buchanan 83 y, Texoma 30 y, Travis 83 y of TWDB record against the 30-year baseline cap): PROVISIONAL (5 to 9 basis years) -> FULL (>= 15). Over 2024 the TWDB daily value differs from the lake's existing CWMS history by a median 0.023 / 0.010 / 0.012 ft (p95 0.114 / 0.075 / 0.059 ft).
- Pool sanity: all 16 levels sit between dead pool and the conservation pool (the lowest relative to it: Elephant Butte -110.7 ft, Amistad -57.2 ft, Falcon -39.8 ft, all real drawdowns); TWDB conservation pool equals the directory `fullPoolFt` within 2 ft for all 16.
- Live agreement with an independent origin: median |diff| 0.002 to 0.171 ft over 6 or 7 full days; 16 of 16 pass 0.25 ft.
- Checks that did not pass: datum label is not NGVD29 for Buchanan, Travis and Elephant Butte (carried verbatim, see 4.1); **Canyon Lake: median of the last 365 days is 19.4 ft below the live level**, so the runner's 15 ft rule would flag it. The same lake is held for a history/live mismatch with its CWMS history. The TWDB record agrees with USGS today within 0.002 ft and shows a 10.2 ft one-day rise on 2026-07-16, so for Canyon the rule may be firing on genuine recovery rather than a series mismatch; this is reported, not acted on (no threshold changed, Canyon stays excluded).
- Live age: 15 of 16 current (2026-10-13), Sam Rayburn one day old (inside the 4-day envelope).

### 4.4 Coverage ladder (PROJECTION ONLY, nothing is published)

The coverage dimension is `profiled / 621` on the ladder `> 0 -> 1; >= 5 % -> 2; 10 % -> 3; 25 % -> 5; 50 % -> 7; ...` (`sector_brain_platform.scoring.ladder`). TWDB changes the numerator by **0** under the current eligibility rules (every Texas lake it could back is already proposed on another provider or excluded for a reason it does not cure), so no rung moves. If Michael ever decided to admit the two post-hoc TWDB-primary rows, the upper bound is +2 lakes (Amistad, Falcon), +0.32 percentage points of 621, still no rung. TWDB's real contribution is depth, not breadth: three Texas lakes from a PROVISIONAL to a FULL historical tier. It could cover at most 16 directory lakes (15 Texas + Elephant Butte) and all are covered or excluded by other means.

### 4.5 Decisions for Michael

1. Clear or refuse the `.csv` robots.txt disallow (write to TWDB from a role mailbox, or decide that downloading the advertised links at 2 s spacing is acceptable). Until then the gate stays closed and the overlay is inert.
2. Whether a datum label such as `NAVD88 +0.6` (Travis) may be carried verbatim, given that the values equal the NGVD29 series of the primary source.
3. Whether the Canyon Lake history/live hold (15 ft rule) should be revisited with the evidence above.
4. Provide a real role mailbox for `SECTOR_CONTACT`.

### 4.6 Reproduce

`swift test --filter LakeBrainTWDBTests` (26 tests, recorded fixtures, no network); `python3 -m pytest jobs/lake-brain/bindings -q` (30 tests); `python3 jobs/lake-brain/bindings/twdb_dryrun.py --check` (offline rebuild must equal the committed JSON and CSV); `python3 jobs/lake-brain/bindings/build_bindings_table.py --check` and `python3 scripts/generate-lake-bindings.py --check` (the published table and the generated Swift are byte-identical to before).
