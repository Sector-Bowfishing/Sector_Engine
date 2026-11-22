# Lake Brain: level-source provider adapters

Status: implemented and exercised read-only against live data on 2026-10-13. Nothing here publishes to any RTDB or bucket; the live
exercise used `LakeBrainJob --dry-run DIR --include-candidates`, which writes local files only.
Code: `brains/lake/runtime/LakeBrain/LakeLevelFeeds.swift` (TVA, CWMS, USGS live), `LakeLevelFeedsFleet.swift` (Access2Water, RISE, NWPS, HADS, USGS history) and `LakeLevelFeedsCDEC.swift` (CDEC, section 4).
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
| `cdec` California DWR CDEC (reader only, no lake bound yet: section 4) | `https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet?Stations={ID}&SensorNums=6&dur_code={E\|H\|D}&Start=yyyy-MM-dd&End=yyyy-MM-dd` | none | ft (`units` `FEET`; sensor 6 only) | hourly `H`: 60 / 120 min suggested; daily `D`: 1440 / 1440 | California reservoir pool elevation; daily history (`cdecDaily`) |
| HADS (history only) IEM | `https://mesonet.agron.iastate.edu/cgi-bin/request/hads.py?stations=&sts=&ets=&what=txt&delim=comma` | none | ft | n/a | the NWS DCP archive of an NWPS location id, about 2010-12 onward |
| NWS forecast grid (rain signal only) | `https://api.weather.gov/points/{lat},{lon}` → its `forecastGridData`, layer `quantitativePrecipitation` | none, User-Agent required (`LakeFeedHTTP.userAgent`, the Sector-LakeBrain contact string) | mm (inches = mm / 25.4) | one gridpoint request per lake per run, spaced 0.25 s; the point → grid map is kept in the archive (`signals/nws-points.json`); usually 6 h periods | forecast rain in the next 12 h at the lake; sets the adaptive freshness window (`LakeLevelValidity`), never the level. Unknown (outside NWS coverage, outage) is treated conservatively |

All requests use `Sector-LakeBrain/1.0 (io.sector.co; read-only public data; contact ...)`, a 120 s read timeout (the engine's 8 s cap is for request-path fetches; a HADS chunk or an Access2Water listing is bigger) and never write anything.
Not implemented: **TWDB** (no strict-verified lake uses it) and **CO-OPS** (Great Lakes harbours only, not on the allow-list).

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
| CDEC sensor 15 is storage (acre-feet), sensor 1 a river stage | only sensor 6 (`RES ELE`, reservoir elevation) is read; any other sensor is refused before a request, and an answer whose `units` are not feet fails as a whole |
| CDEC `-9999` missing value is a number, not null (often a third of the rows); 0 is a mechanical error | values <= -9000 and exactly 0 dropped; a day with no reading stays missing, never filled |
| CDEC timestamps have no offset | read as Pacific wall-clock time (America/Los_Angeles, daylight saving applied); daily `D` rows keep the date in their stamp (section 4) |
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

## 4. CDEC (California DWR) reservoir elevation

Added 2026-11-22. **Reader only:** no lake is bound to CDEC (`LakeBrainCDECTests.testNoLakeIsBoundToCDEC`). Binding a California lake goes through the acceptance gate like every other binding (`LAKE_BRAIN_BINDING_REVIEW_PROTOCOL.md`), and `cdec` is not yet on the bindings-table allow-list (`jobs/lake-brain/bindings/build_bindings_table.py`, Almanor and Berryessa are excluded as `provider-not-allowed`).

- **Source.** California Department of Water Resources, California Data Exchange Center. Endpoint `JSONDataServlet` (above); answer: a JSON array, one object per reading: `stationId`, `durCode`, `SENSOR_NUM`, `sensorType`, `date` and `obsDate` (`yyyy-MM-dd HH:mm`, no offset), `value` (number), `dataFlag`, `units`. Station ids are short codes (`SHA` Shasta, `ORO` Oroville, `FOL` Folsom). No authentication; no published rate limit or quota.
- **Binding shape.** Live: `provider: cdec`, `station` = the CDEC id, `series` = `6` (hourly) or `6:H`, `6:E` (event, about 15 min), `6:D` (daily); `sourceId` `cdec:{ID}:{series}`. History: `cdecDaily(station, sensor, dur, offsetFt)`, in the generated table `{"kind": "cdecDaily", "station", "sensor", "dur", "offsetFt"}`.
- **Cadence.** Hourly (`H`) is the usual reservoir series; event (`E`) exists for some stations; daily (`D`) values go back decades for the large reservoirs. History is pulled newest first in windows of 10 years (`D`), 1 year (`H`) or 60 days (`E`), one request at a time; two empty windows in a row end the walk and any failed window fails the whole pull. A daily value is expected for yesterday (the default `expectedLatestDay`).
- **Time zone.** Stamps carry no offset and are read as Pacific wall-clock time with daylight saving (`LakeFleetClients.cdecTimeZone`). One third-party client documents exactly that (CDEC times "in Pacific Time and Daylight Savings adjustments are reflected"); CDEC's own statement could not be retrieved. If CDEC in fact stamps fixed PST all year, summer readings are read one hour **older** than they are, never fresher, so the freshness rule stays conservative. Confirm on the first live probe (compare a summer hourly stamp with the same reading on the station's CDEC page) before binding a lake.
- **Missing values.** `-9999` (a number) is dropped, as is anything <= -9000 and an exact 0. `dataFlag` is not interpreted; a station that writes a text flag into `value` yields no reading for that row.
- **Datum.** CDEC does not state the vertical datum per series; most projects report in their historical datum (typically NGVD29, not NAVD88). The binding review records the datum and sets `datumOffsetFt` (live) / `offsetFt` (history) when it differs from the lake's pool reference.
- **Health plane.** `cdec` is not yet a declared Lake input (`brain.json` providers, `providers/PROVIDERS.json`, the `lake-brain` job manifest, Swift `BrainOwnership`) and has no source-health record in `LakeBrainRunner.sourceRecords`; that registration belongs with the first accepted CDEC binding (operating contract section 10: new providers need the owner's approval).
- **Access note.** CDEC's `robots.txt` disallows automated crawling of `/dynamicapp/`; the Brain is not a crawler (it requests named series only, a few requests per lake per run), but the owner should confirm this use before a lake is bound.
- **Tests.** `brains/lake/tests/swift/LakeBrainCDECTests.swift` with `brains/lake/tests/fixtures/cdec/SHA_6_H.json` (shape of the JSONDataServlet answer with a `-9999` row; assembled from the documented format because the host was not reachable from the authoring session, to be replaced by a recorded answer). No test makes a network call.
