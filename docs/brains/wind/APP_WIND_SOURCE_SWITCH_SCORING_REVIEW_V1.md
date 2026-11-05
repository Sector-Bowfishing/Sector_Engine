# Scoring review (DRAFT): switching the forecast wind to NBM

**Status:** DRAFT for the owner (Sector_Ops #50). Nothing is switched. The code switch `SECTOR_WIND_FORECAST_MODEL` is off by default. Merging it, turning it on and deploying are each separate owner approvals (Cortex `scoring.md` Gates; `PROJECT.md` §7).

## 1. What changes when the switch is on
- **Changes:** the hourly `wind_speed_10m` and daily `wind_speed_10m_max` that feed **tonight's window** and the **7-night outlook** (`ConditionsForecast`).
  - They come from `models=ncep_nbm_conus` in a second, wind-only request.
  - Wherever NBM has no value (outside CONUS, beyond its range) or the request fails, the value stays `best_match`.
- **Unchanged:**
  - **current conditions** (`WeatherService.conditions`);
  - cloud, precipitation, weather codes, humidity and sun times;
  - every rubric, band and breakpoint (`ConditionsConfig.Wind.bands` 4 / 7 / 11 mph, `windCurve`, the 20 mph high-wind gate);
  - the NWS warning override.
- **No rubric changes.** The scoring rules stay as they are; only the input source of one variable changes. This is not a re-baseline. No Brain capability score is touched (SC-04, SC-05).

## 2. Evidence (frozen, scored once)
| Check | Result |
|---|---|
| W1, about 24 h (#30) | NBM SUPPORTED: 142 of 150 lakes pass, MAE 2.49, bias +0.34. `best_match` would fail: 79 of 150, MAE 3.40, bias +1.73 |
| W1b, 0 h and days 3–7 (#47, #50) | NBM not worse at every graded lead. Day 3–7 MAE about 1 mph lower, bias about +0.3 against `best_match`'s +1.5. Day 8 not available |

## 3. Expected effect on customer scores (direction, not measured)
- **Calm nights score higher.** `best_match` reads about 1.5–1.7 mph high, which pushes truly calm nights across the 4 and 7 mph breakpoints.
- **Fewer false "too windy" nights, and more missed windy ones.** At day 7 NBM catches 0.12 of strong-wind nights against 0.38, with about half the false alarms. The NWS warning override remains the backstop for dangerous wind.
- **Not measured yet:** how many customer nights change band. That can be computed offline from the W1b cache (no cloud, no live write), as a follow-up before any switch.

## 4. Limits
- **Measurement:** land stations, not the water; night speed only; one season-year. Over-water wind is usually stronger, so part of `best_match`'s high reading may be nearer lake-surface truth.
- **0 h:** this is the archive's shortest lead, not the app's `current=` call. That is why current conditions are left on `best_match`.

## 5. Owner decisions
- **WS-1:** approve the scoring review (this document) as written, or ask for the offline band-change count first. *Recommended:* the count first.
- **WS-2:** merge the default-off switch (code only).
- **WS-3:** turn it on and deploy. This is customer-visible.
- **WS-4:** current conditions: stay on `best_match` (recommended) or follow W1b's 0 h result.
