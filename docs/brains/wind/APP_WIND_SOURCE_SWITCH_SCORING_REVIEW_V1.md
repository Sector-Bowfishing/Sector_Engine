# Scoring review (DRAFT): switching the forecast wind to NBM

**Status:** DRAFT for the owner (Sector_Ops #50). Nothing is switched. The code switch `SECTOR_WIND_FORECAST_MODEL` is off by default. Merging it, turning it on and deploying are each separate owner approvals (Cortex `scoring.md` Gates; `PROJECT.md` §7).

## 1. What changes when the switch is on
- **Changes:** the hourly `wind_speed_10m` and daily `wind_speed_10m_max` that feed the **7-night outlook's future nights** (`ConditionsForecast`). Tonight stays on `best_match` (WS-5).
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
- **Band changes, measured offline (2026-11-05, Sector_Ops #50).** The count used the W1b cache and its ASOS observations, 154 lakes, 51,436 lake-nights per lead. It applies the app's rule: the night mean from about 18:00 to 06:00, this switch's overlay, and the bands at 4 / 7 / 11 / 15 / 20 mph.

  | lead | nights that change band | calmer / windier | band matches the observed night: `best_match` → NBM |
  |---|---|---|---|
  | 0 h (tonight) | 33.2% | 48% / 52% | **0.701 → 0.679** |
  | days 3–7 (outlook) | 51.4–57.2% | about 3 : 1 calmer | 0.36–0.43 → **0.51–0.62** |

  The 20 mph gate flips on 0.5–0.8% of nights at each lead. So the outlook gains clearly, but **tonight's band gets slightly worse**: W1b's "not worse" MAE reading at 0 h does not carry over to the band. Days 1–2 and day 8 are not graded.

## 4. Limits
- **Measurement:** land stations, not the water; night speed only; one season-year. Over-water wind is usually stronger, so part of `best_match`'s high reading may be nearer lake-surface truth.
- **0 h:** this is the archive's shortest lead, not the app's `current=` call. That is why current conditions are left on `best_match`.

## 5. Owner decisions
- **WS-1:** approve the scoring review (this document). The band-change count is now done (§3).
- **WS-2:** merge the default-off switch (code only).
- **WS-3:** turn it on and deploy. This is customer-visible.
- **WS-4:** current conditions: stay on `best_match` (recommended) or follow W1b's 0 h result.
- **WS-5 (built, owner-approved 2026-11-05):** the switch now changes the outlook's **future nights only**. Every hour before noon of the location's local tomorrow, and today's and earlier daily values, keep `best_match`. That covers all of tonight: tonight's window, the outlook's tonight row, and the rest of tonight after midnight. The switch is still off by default.
  - **Independent review fix:** tonight's window is computed in the process time zone, which is UTC on a server. For western and non-contiguous US zones late in the evening (Hawaii, Alaska, Pacific, Mountain), that window can run to 06:00 of the day after tomorrow. The cutoff is therefore the later of noon tomorrow (local) and the hour after the window ends.
  - **Trade-off:** in those hours the first future night also stays on `best_match`. That is the safe direction, and the window overrun itself is an existing quirk in `buildTonight`.
  - **Tests:** every hour of the day is checked for UTC−4 to UTC−10, with the process in UTC, in Central time and in the lake's own zone.
