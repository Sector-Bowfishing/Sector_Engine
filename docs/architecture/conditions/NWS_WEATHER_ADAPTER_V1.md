# NWS/NBM weather adapter V1

Sector_Ops #53, conditions consolidation spec V1 §1 (tiles Humidity, Barometric Pressure, Temperature, Sky, Wind; source id `nws-nbm`).

**Status:** adapter only. Nothing in `/conditions` calls it. The tile flags and the shadow helper land in a separate foundation PR; the wiring comes after both merge, with every flag `off` (spec §0 rule 7).

Code:
- `Sources/SectorEngine/Fetchers/NWSWeatherService.swift`: the service, the decoders, the pure `assemble`, and `NWSCondition` (the icon to WMO map).
- `Sources/SectorEngine/Fetchers/NWSWeatherParity.swift`: the pure per-tile comparator and the `[tile-shadow]` line.
- `Tests/SectorEngineTests/NWSWeatherServiceTests.swift` and `Fixtures/NWS/`: real responses recorded on 2026-11-06 at about 20:51Z.

## 1. Sources

| Step | Request | Use | Cache |
|---|---|---|---|
| 1 | `GET /points/{lat},{lon}` (rounded to 0.01°) | `forecastGridData` (the NDFD gridpoint) and the `observationStations` URL | 24 h per 0.01° key, together with step 2; at most 5,000 entries, least recently used evicted |
| 2 | `GET {observationStations}` | station ids, nearest first; the first 3 are kept | with step 1; an empty list is never cached |
| 3 | `GET /stations/{id}/observations?start=now−49h&limit=500`, for 3 stations in parallel | "now", the past 48 h of the hourly series, and the pressure trend | none |
| 4 | `GET {forecastGridData}`, in parallel with steps 2–3 | the NBM-based NDFD grid: the current hour and the next 24 h | none |

- Every request sends `User-Agent: Sector/1.0 (io.sector.co)`, the same as `WeatherAlertsService`, plus `Accept: application/geo+json`. It goes through `HTTP.get`, so each call writes an `[http]` upstream log line.
- Each request has its own 2.5 s timeout (`requestTimeout`). The three sequential stages (points; then stations → observations, with the grid alongside) fit inside the 8 s budget for the whole reading (`withDeadline`).
- A slow grid does not lose fresh observations, and a slow, failed or empty station list degrades to a grid-only reading instead of `nil`.
- The result is `nil` only for a failed points lookup (including a point outside NWS coverage), the 8 s deadline, or a reading with no value at all. Failed lookups are not cached.

## 2. Rules

- **Provenance.** Every value is an `NWSValue` with `value`, `observedAt`, `origin` (`observation` or `nbmGrid`) and `stationId`. For a grid value, `observedAt` is the start of the grid hour it is valid for.
- **Stale rule and station choice.** An observation older than **2 h** (`observationMaxAge`) is never used as "now". For each field, the newest observation carrying it across the stations wins if it is at most **75 min** old (`preferredMaxAge`; ties go to the nearer station). Only when no station has one that recent does the adapter take the nearest station's newest observation, up to the 2 h limit.
- **Fallback.** When no station has a fresh observation, temperature, humidity and wind fall back to the grid's current hour, with `origin = nbmGrid`. `weatherCode` falls back to the sky code (0–3) of the grid's cover, also `nbmGrid`; present weather (rain, fog, storms) is never taken from the grid. Pressure has no grid fallback and stays `nil`.
- **Never invented.** A value nobody reported stays `nil`. A trend with no past sample less than 90 min from its target stays `nil` (the same `<` as WeatherService); WeatherService would report steady/0 in that case. QC flags `X` (rejected) and `B` (bad) drop the value. An unknown unit gives `nil`. QPF periods longer than one hour are not split into hourly rates.
- **Wind.** Speed and direction always come from the same observation. Calm (speed 0) has no direction, and a null direction (variable) stays `nil`.

## 3. Units and meaning checks for each tile

| Tile | Build 28 field (Open-Meteo, WeatherService) | NWS/NBM source | Meaning check |
|---|---|---|---|
| Temperature | `temperature`, °F, model `temperature_2m` at the current 15 min step | station `temperature` (°C → °F) | Observed 2 m air temperature against modelled. Same quantity, same unit. |
| Humidity | `humidity`, Int %, model `relative_humidity_2m` | station `relativeHumidity` (computed by NWS from temperature and dew point), rounded like WeatherService | Same quantity. |
| Barometric Pressure | `pressure`, hPa, **`pressure_msl`** (mean sea level) | the altimeter setting (`barometricPressure`, Pa → hPa) **converted to MSL** with the station's own SLP − altimeter offset; see §3.1 | Converted to the same quantity when an offset exists; otherwise labelled `altimeter`. |
| Pressure trend | `pressureTrend` / `pressureChange`: **12 h** lookback, closest sample, steady within ±1.5 hPa. `displayPressureTrend`: **3 h**, ±0.02 inHg | `pressureTrend` / `pressureChange` with the same 12 h rule; `pressureTrend3h` / `pressureChange3h` with the 3 h rule | Same definitions. Computed on the raw altimeter series of one station, so the offset never enters a trend. |
| Sky | `cloudCover` 0–100 (model total cloud); `weatherCode` (WMO, sanitized); `conditionSymbol` and `conditionDescription` from `WeatherService.condition(forCode:)` | `cloudCover` = grid `skyCover` for the current hour (total cloud, NBM). `weatherCode` comes from the fresh observation's icon and text; see §3.2 | The label and symbol use the same function and vocabulary. Cloud % is model against model; ASOS cloud layers stop at 12,000 ft, so they are used only when the grid hour is missing. |
| Wind | `windSpeed` mph, `windDirection` Int degrees, 10 m | station `windSpeed` (km/h → mph, 2 min mean, 10 m) and `windDirection` | Same height and unit. Gusts are only in the hourly series. |

### 3.1 Pressure: why it is converted

- WeatherService requests `pressure_msl`. It does **not** use `surface_pressure`, which is station-level pressure and is hundreds of hPa lower at altitude. The served `pressure` field has always meant mean sea-level pressure.
- The NWS API has two sea-level reductions:
  - `seaLevelPressure`, the METAR SLP group, which is the same quantity as `pressure_msl`. The API fills it in **hours late**: in the recordings the newest SLP was about 3 h old at every station, and AWOS stations (KBFZ, K4A6, KHII) never send it.
  - `barometricPressure`, the altimeter setting. It comes with almost every observation, but it is reduced with the standard atmosphere and differs from MSL. In the recordings the difference was about 0.1 hPa at KBTV (Burlington) and **1.9 hPa at KEED** (Needles, hot desert).
- So the adapter takes the newest fresh altimeter value and adds `seaLevelOffset`, which is SLP − altimeter on that station's newest observation carrying both, within 6 h. The result is labelled `pressureKind = seaLevel`.
- With no such pair (an AWOS station), the altimeter value is served unchanged and labelled `pressureKind = altimeter`. That case can be off by about 1–2 hPa in hot, high places. The shadow log line carries `pressureKindNew`, so the parity check shows it.
- The charted `pressureHistory` is the altimeter series plus the same offset, so its last point equals `pressure`.

### 3.2 Sky: icon and text to WMO

- The output is limited to the codes WeatherService emits, because build 28 apps map exactly those. The description and SF Symbol come from `WeatherService.condition(forCode:)`.
- WeatherService has **no day/night symbol rule**: a clear night is `sun.max.fill`. The adapter keeps that and ignores the `day`/`night` part of the icon URL. A night variant would be a change to app-visible behaviour, so it would need its own decision.
- **Order:** a weather icon (and its text) wins. Otherwise the code comes from the grid's total cloud %, then from the sky icon, then from the text. Present weather needs a fresh observation; the grid's `weather` layer is a probability ("chance"), not an occurrence, so it is not used. With no fresh observation the code is the grid cover's sky code (0–3), marked `nbmGrid`.
- **Cloud %:** NWS octa categories. Under 12.5 % is 0 (clear). Under 37.5 % is 1 (mainly clear). Under 87.5 % is 2 (partly cloudy; NWS "mostly cloudy" included). From 87.5 % it is 3 (overcast).
- **Intensity** comes from the text ("Light …" and "Heavy …"). "Drizzle" turns a `rain` icon into 51/53/55. "Hail" turns a thunderstorm into 96.

| NWS icon(s) | WMO (moderate) | light / heavy |
|---|---|---|
| `skc`, `few`, `sct`, `bkn`, `ovc` (and `wind_*`) | 0, 1, 2, 2, 3, overridden by the cloud % when it is known | – |
| `rain` | 63 | 61 / 65 (drizzle 51/53/55; freezing drizzle 56/57) |
| `rain_showers`, `rain_showers_hi` | 81 | 80 / 82 |
| `snow`, `rain_snow`, `snow_sleet` | 73 (snow showers 85) | 71 / 75 (86) |
| `fzra`, `rain_fzra`, `snow_fzra`, `sleet`, `rain_sleet` | 66 | 66 / 67 |
| `blizzard` | 75 | – |
| `tsra`, `tsra_sct`, `tsra_hi`, `tornado`, `hurricane`, `tropical_storm` | 95 (96 with hail) | – |
| `fog` | 45 | – |
| `dust`, `smoke`, `haze`, `hot`, `cold` | no weather code; the sky code comes from the cloud % | – |

Ice pellets (`sleet`) have no Open-Meteo code, so they map to freezing rain (66/67, `cloud.sleet.fill`). Mixed rain and snow maps to snow.

## 4. Hourly series

- `hourlyConditions` has the same `ConditionsHourly` shape as WeatherService.
  - **Past 48 h:** one observation per clock hour (the latest in that hour) from the temperature station, with real timestamps. Cloud % comes from the grid hour where the grid covers it.
  - **Next 24 h:** the grid, at the top of each hour.
- `pressureHistory` covers the **past 48 h only**. The NDFD `pressure` layer is empty for these offices, so the forecast half of the pressure chart is lost, and `expectedPressureChangeInHg` would be `nil`. This is a known gap.

## 5. Parity comparator

- `NWSWeatherParity.compare(old: WeatherReading, new: NWSWeatherReading?) -> [NWSTileParity]` returns one entry per tile: `humidity`, `pressure`, `temperature`, `sky`, `wind`.
- Each entry has `old`, `new` and `delta` (new − old, rounded to 0.01) for the tile's primary number, always present and `null` when missing:
  - Humidity: %.
  - Pressure: hPa.
  - Temperature: °F.
  - Sky: cloud %.
  - Wind: mph.
- Each entry also has `newObservedAt`, `newOrigin`, `newStation` and `detail`:
  - Pressure: the 12 h and 3 h trends, the changes and `pressureKindNew`.
  - Sky: the codes, symbols and whether they match.
  - Wind: the directions and the signed shortest-turn `dirDelta`.
- `NWSWeatherParity.logLine(_:lakeId:latR:lonR:)` writes `[tile-shadow] {…}` with sorted keys and ISO 8601 seconds, matching spec §6.

## 6. What NWS cannot give that Open-Meteo did

- **Anywhere outside the US.** `/points` returns 404, so the reading is `nil` and the tile must stay on Open-Meteo (spec §0 rule 2).
- **History beyond about 7 days.** The station observations API keeps only recent data, and there is no reanalysis or archive. Trip-window weather (`WeatherService.windowConditions`, past nights) cannot move.
- **Forecast pressure.** See §4.
- **A guaranteed fresh "now".** Some stations lag about 2 h in the API, or never report. When that happens, temperature, humidity, wind and the sky code are NBM forecast values for the current hour, and pressure is `nil`.
- **Precipitation in the WeatherReading meaning.** The adapter does not produce `precipitation` (now) or `recentRainfall`. Those stay on Open-Meteo or MRMS.

## 7. Open-Meteo uses that remain after the five tiles move

| Use | Code | Why it stays |
|---|---|---|
| 7-night outlook (wind, cloud, precip, weather code, sun times; wind model per `SECTOR_WIND_FORECAST_MODEL` / `windOutlookModel`) | `Forecast/ConditionsForecast.swift` | Multi-day hourly and daily outlook; a separate tile (`windOutlookModel`) |
| Water-temp model history (air-temperature history that drives the modelled water temperature) | `Fetchers/WaterTemperatureService.swift` (`WeatherService.fetchForecastData`) | Needs a past-days daily series; NWS has no archive |
| Clarity rain (today's rain so far, plus the 48 h fallback when MRMS/IEM is down; `recentRainfall`) | `Fetchers/MrmsPrecipService.swift`, `WeatherService.conditions` | Daily accumulations; not one of the five tiles |
| Trip-window weather (past nights) | `WeatherService.windowConditions` | History |
| Fallback for every tile | `WeatherService.conditions` | Spec §0 rule 2: old path stays while used (rule 5) |

## 8. Not verified

- The adapter has not been run against live traffic or in Cloud Run. The fixtures are one moment, at three points.
- These are untested choices for the shadow parity window to confirm or change:
  - the 2 h stale threshold and the 75 min newest-wins window
  - the 2.5 s per-request timeout
  - the 6 h SLP-offset window
  - the octa cloud thresholds against Open-Meteo's own code thresholds
