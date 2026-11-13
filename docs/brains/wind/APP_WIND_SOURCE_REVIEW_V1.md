# Review: the app's wind source (`best_match`) and what switching to NBM would change

**Status:** review only (Sector_Ops #45 item 3b, 2026-11-02). No code changed. Any switch needs the owner's approval, a PR and a deploy.

## 1. What the app uses today, and why
- Every customer wind number comes from the Engine's Open-Meteo calls: `WeatherService.conditions(near:)` for current conditions and
  the trip window, and `ConditionsForecast.fetchForecastResponse` for tonight and the 7-night outlook.
- Neither call sets Open-Meteo's `models` parameter, so Open-Meteo answers with its default, **`best_match`**: a blend that picks a
  model per location and time. The repository records no decision to use it. It is the API default, not a choice.
- The Wind Brain does not feed the app. It runs NBM for the four live lakes in shadow and is paused.

## 2. What W1 measured (Sector_Ops #30, frozen pre-registration, scored once 2026-11-02)
W1 graded night wind speed about 24 h ahead, from November 2025 to September 2026, at the nearest airport station within 10 km of 150
random catalog lakes and of the four live lakes.

| Night speed | NBM (`ncep_nbm_conus`) | `best_match` (today's source) |
|---|---|---|
| Sample lakes passing (MAE ≤ 3.5 mph and \|bias\| ≤ 2.0 mph) | 142 of 150 (0.95) | 79 of 150 (0.53) |
| Pooled error (MAE) | 2.49 mph | 3.40 mph |
| Pooled bias | +0.34 mph | +1.73 mph (reads high) |
| Four live lakes, MAE | 2.07 to 2.31 mph | 2.92 to 3.00 mph |
| Strong-wind nights (≥ 15 mph) caught | 0.50 (false alarms 0.20) | 0.64 (false alarms 0.41) |
| Gusty hours (≥ 20 mph) caught | 0.75 (false alarms 0.57) | 0.86 (false alarms 0.73) |

Most `best_match` failures are bias, not scatter: 66 of its 71 failing lakes read more than 2 mph high.

## 3. What switching would change for a user
- **Calm nights score higher.** The wind score has breakpoints at 4 and 7 mph (`ConditionsConfig.Wind.bands`: 100 up to 4 mph, 68 up to
  7, 40 up to 11). A forecast that reads about 1.7 mph high pushes many truly calm nights from the top band into the next one. With
  NBM those nights would mostly stay prime.
- **The clarity ceiling relaxes slightly** on the same nights (`windCurve` starts to bite above 7 mph).
- **Fewer false "too windy" nights, but some missed windy ones.** NBM catches fewer strong-wind nights than `best_match` (0.50 against
  0.64), with half the false alarms. The NWS warning override (`WeatherAlertsService`) still applies either way and would remain the
  backstop for dangerous wind.
- **The 20 mph high-wind gate** would trip less often. That follows from the lower bias, and some of those trips were false alarms.

## 4. What W1 does not show
- **Land stations, not the water.** Over-water night wind is usually stronger than at an airport, so part of `best_match`'s high
  reading may be closer to lake-surface truth. W1 cannot say, because no over-water truth exists at these lakes.
- **One lead time.** About 24 h ahead. The app also shows current conditions (lead about 0 h) and a 7-night outlook (up to 8 days).
  Neither was graded by W1. **W1b (2026-11-05, frozen pre-registration, scored once) graded them:** NBM is not worse than `best_match`
  at 0 h and at days 3 to 7 (day 8: the archive serves no value). At 0 h the error is the same (2.40 mph) with half the bias. From day 3
  on, NBM's error is about 1 mph lower, and `best_match` reads about 1.5 mph high. NBM catches fewer strong-wind nights at every lead
  (0.12 against 0.38 at day 7). Results: Sector Research `wind-brain/research/w1b-app-leads-2026-11-02/W1B_RESULTS.md`.
- **Night speed only.** Daytime, direction and gust magnitude were not graded.
- **Coverage.** NBM is CONUS only, so Alaska and Hawaii lakes would need `best_match` as a fallback.
- **One season-year**, November 2025 to September 2026.

## 5. Options (owner)
1. **Switch the tonight and outlook wind to NBM** (`models=ncep_nbm_conus`, falling back to `best_match` outside CONUS or on error),
   keeping current conditions on `best_match` until a short-lead check exists. This is the change W1 supports most directly.
   *Recommended*, with a small pre-registered check of the 0 h and 3 to 8 day leads first. That check (W1b) is done, and it supports
   the switch at every graded lead. A default-off switch for this option is drafted (`WindForecastModel`, `SECTOR_WIND_FORECAST_MODEL`);
   its scoring review is `APP_WIND_SOURCE_SWITCH_SCORING_REVIEW_V1.md`.
2. Switch everything to NBM at once. Simpler, but it is ungraded at the leads users see most.
3. Keep `best_match` and correct its night bias. Not recommended: it is a fitted correction on one season-year.
4. Keep things as they are.

Any of 1 to 3 changes customer scores, so it needs a scoring review under Cortex `scoring.md`, a PR and a deploy, each approved
separately.
