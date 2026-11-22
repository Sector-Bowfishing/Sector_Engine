# Hand-built fixtures (HAND_BUILT, not recordings)

Built 2026-11-22 for the Weather Brain tests in the api.weather.gov observation shape (units as NWS sends them: °C, Pa, km/h, mm). Each file
carries a `_provenance` field saying so. They exercise the weather-change rules on textbook cases; they are not evidence about any real
station. Other hand-built cases are generated in code by `tests/weather_support.py` (`obs_feature`, `hourly`). Recorded fixtures are in
`../recorded/` (see its PROVENANCE.md).

| file | scenario | built at |
|---|---|---|
| front_passage_KTST.json | pressure trough, wind veers 180°→320°, 8 °C temperature and 9 °C dew point drop over 8 h | newest observation 2026-11-20T01:53Z |
| rain_onset_KTST.json | 4 dry overcast hours, then light rain with 0.6 mm in the last hour | newest observation 2026-11-20T01:53Z |
