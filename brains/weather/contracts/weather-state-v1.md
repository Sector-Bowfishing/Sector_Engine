# Weather state contract v1 (`sector-brain-weather-state-v1`)

Written at `/lakes/{k}/states/weather` (one document per lake; schema: [`weather-state-v1.schema.json`](weather-state-v1.schema.json)).
Producer: the Weather Brain (`brainId: weather`). Status: **CALIBRATION, internal only, customer publication off**. Thresholds version
**`weather-change-thresholds-v1`, pre-stated 2026-11-22** before any result was computed (owner decision on Sector_Ops #51: real measured or
official forecast data only, never invented estimates).

## 1. Sources and the one rule about gaps

| Data | Source | Label in the state |
|---|---|---|
| Pressure, air temperature, humidity, dew point, present weather, last-hour precipitation | NWS station observations (ASOS/AWOS) from the 3 nearest stations NWS lists for the lake's grid cell (`/stations/{id}/observations`) | `origin: "observation"`, `station`, `at` = observation time |
| Total cloud %, the next 12 h of temperature / humidity / dew point / cloud / precipitation probability, forecast rain | NWS forecast grid (`/gridpoints/{wfo}/{x},{y}`, the NBM-based NDFD) | `origin: "forecastGrid"`, `at` = the start of the grid hour |

A value that no station and no forecast reported is `null`, and the tile is listed in `missing`. Pressure has **no** forecast fallback (the
NWS grid has no pressure layer), so without a fresh observation `pressure` is `null`. Nothing is modelled, interpolated or carried forward.

The selection rules are the Engine's NWS adapter, ported value for value (`docs/architecture/conditions/NWS_WEATHER_ADAPTER_V1.md` §2-§3):
an observation older than 2 h is never "now"; across the 3 stations the newest reading within 75 min wins (ties to the nearer station),
else the nearest station's newest reading up to 2 h; QC flags X and B drop a value; unknown units give `null`.

## 2. Tiles (exact meaning, matched to the iOS app)

| Tile | Field | Meaning | iOS source of truth |
|---|---|---|---|
| Sky | `sky.cloudCoverPct` | total cloud %, forecast grid current hour (the observation's cloud layers only when the grid has no hour) | Sky tile value = cloud cover % (`FavoriteConditions.swift`) |
| Sky | `sky.word` | `clear` < 25 %, `broken cloud` < 60 %, else `overcast` | `cloudWord` (`MetricSheets.swift`) |
| Sky | `sky.weatherCode`, `sky.description` | WMO code from the observation's icon/text (the adapter's NWSCondition table), else the grid cover's sky code; the label is `WeatherService.condition(forCode:)` | `WeatherService.condition(forCode:)` |
| Sky | `sky.rain` | last-hour observed precipitation; forecast liquid precipitation next 6 h / 12 h (a period that partly overlaps counts in proportion, the Lake Brain's rule) | — |
| Barometric Pressure | `pressure.inHg`, `pressure.hPa` | newest fresh altimeter setting, converted to sea-level pressure with the station's own SLP − altimeter offset (within 6 h); `kind: "altimeter"` when the station never sends SLP (AWOS) | `pressureInHg` of `pressure_msl` |
| Barometric Pressure | `pressure.trend3h` | **the tile trend**: change from the sample nearest 3 h earlier (strictly within 90 min), `rising` > +0.02 inHg, `falling` < −0.02 inHg, else `steady`; computed on one station's raw series | `displayPressureTrend` (`WeatherService.swift`) |
| Barometric Pressure | `pressure.trend12h` | the 12 h rule, ±1.5 hPa (kept for parity; not the tile trend) | `pressureTrend` |
| Air Temperature | `airTemperatureF` | 2 m air temperature, °F | `temperature` |
| Humidity | `humidityPct`, `dewPointF` | relative humidity % (rounded), dew point °F | `humidity`, `dewPointF` |

## 3. State kinds and readiness

`kind`: `observation` (pressure and air temperature from a fresh station observation), `forecast` (no fresh observation: temperature and
humidity are the grid's current hour, pressure null), `unavailable` (nothing). Lake readiness (`/lakeFleet/{k}/readiness/weather`):
`CALIBRATION` (observation kind, current, no tile missing), `DEGRADED`, `BLOCKED` (outside NWS coverage: `/points` 404), `DISCOVERED`.

## 4. The weather-change signal (`weatherChange`)

Evaluated every run over the last 3 h of measured observations and the next 6 h of the official forecast. **Thresholds (v1, pre-stated, not
tuned to results):**

| Event | Basis | Rule | Why this value |
|---|---|---|---|
| `PRESSURE_FALLING_FAST` / `PRESSURE_RISING_FAST` | OBSERVED | 3 h pressure change ≤ −0.06 / ≥ +0.06 inHg (2.03 hPa), the `trend3h` series | 3× the app's ±0.02 inHg steady band (the smallest change the app calls a trend), and above the 1.5 hPa the app's 12 h rule needs, reached in a quarter of the time |
| `AIR_TEMP_SWING` | OBSERVED | \|air temperature change over 3 h\| ≥ 8 °F, the temperature station | the app's temperature sheet treats an 8 °F slide as the size worth naming |
| `FRONT_PASSAGE` | OBSERVED | the wind turns ≥ 90° between the readings 3 h apart (both with sustained wind ≥ 5 mph) **and** at least one of: a pressure trough in the window (a fall ≥ 0.02 inHg then a rise ≥ 0.02 inHg), a temperature drop ≥ 5 °F, a dew point drop ≥ 5 °F | 90° is the app's wind-shift rule ("a quarter-turn is what rides with a frontal passage"); 5 mph keeps calm/variable directions out; 0.02 inHg is the app's band; a 5 °F drop is the conventional surface signature of a front, required together with the turn so a sea-breeze or a sunset cooling alone does not fire |
| `RAIN_ONSET` | OBSERVED | the newest observation (≤ 75 min old) reports precipitation (a WMO code ≥ 51 from its icon/text, or ≥ 0.01 in last hour) and no observation of that station between 3 h and 1 h earlier did | 0.01 in is NWS "measurable"; 3 h matches the other windows |
| `RAIN_EXPECTED` | FORECAST | forecast liquid precipitation ≥ 0.10 in within the next 6 h, and it is not already raining | 0.10 in is the NWS "wetting rain" amount; 6 h is the Water Temp minimum refresh interval |

`level`: **CHANGE** when any OBSERVED event fired; **WATCH** when no observed event fired but rain is expected, or the 3 h pressure or
air-temperature rule could not be evaluated (unknown is never treated as "no change"); **STEADY** otherwise. `unknown` lists every rule that
could not be evaluated and why. `inputs` carries the measured changes the rules used. `signature` (16 hex) changes whenever the level, the
event kinds or the observation they rest on change: a consumer refreshes when it differs from the one it last acted on.

## 5. Freshness and the Brain's own cadence (`freshness`)

The Lake Brain's adaptive-freshness shape (#216), with the tier from `weatherChange.level`:

    freshUntil  = min(observedAt + 240 min, max(observedAt + window, now + 75 min))      window: CHANGE 90, WATCH 150, STEADY 240 min
    nextCheckAt = CHANGE / WATCH: now + 45 min (every hourly Orchestrator grant)
                  STEADY:         max(now + 45, min(now + 120, freshUntil − 75)) min       (at most every second grant)

The 240 min ceiling means no observation older than 4 h is ever current. `stale` is true once `freshUntil` has passed. The per-lake planner
recomputes a lake when `nextCheckAt` is reached (10 min tolerance), the state is stale or older than 3 h, or the brain or thresholds version
changed.

## 6. What this contract does not contain

No score, no recommendation, no fishing or species language, no wind (the Wind Brain owns wind), no pressure forecast, no history beyond
13 h of observations. Consumers: Lake and Water Temp read `weatherChange` (plan §4); Sector Intelligence and Ops may read the state. No
customer surface reads it in this version.
