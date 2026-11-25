# Weather states built by the Weather Brain (GENERATED, not hand-edited)

The Weather Brain's own `run()` (`brains/weather/runtime/sector_weather/publish.py`) wrote each file: first at main 1f52168, regenerated with 18 forecast hours on PR #255 (FORECAST_HOURS 12 → 18, owner decision 2026-11-24); only `forecast.hourly` changed. It ran over its recorded
NWS fixtures (`brains/weather/tests/fixtures/recorded/`, api.weather.gov responses recorded 2026-11-06 at about 20:51Z), using the
fixture source in `brains/weather/tests/weather_support.py`, one lake at a time, at the run time in the file name. The output is
`states[lakeId]`, written as `json.dump(state, indent=1, sort_keys=True)`. Every file validates against
`brains/weather/contracts/weather-state-v1.schema.json` (`tests/test_weather_input.py`).

The runs at 23:00Z and 01:00Z reuse the same recorded grid and observations. Their observations are older than 2 h, so Weather reports
`kind: forecast`, and only the forecast grid supplies cloud.

| file | lake | run time | sha256 |
|---|---|---|---|
| guntersville-2026-11-06T2051Z.json | Guntersville\|AL | 2026-11-06 20:51Z | 9c11ff79b569f1f63c088fdc9b96a616e85cf7d1d7267fff112d43442d62388d |
| guntersville-2026-11-07T0100Z.json | Guntersville\|AL | 2026-11-07 01:00Z | 9a5d380fd2db1b5bc6df008374d093672beec0223589b52ac69e4517880ae558 |
| champlain-2026-11-06T2051Z.json | Champlain\|VT | 2026-11-06 20:51Z | e6820ad775e6b63560c7c317f9fd2c2a7b453b807b0513d113b672266a334854 |
| champlain-2026-11-06T2300Z.json | Champlain\|VT | 2026-11-06 23:00Z | 2f7225456f698e3011965bd920349f72704721fbba551957b1bf002bce7e35ba |

Regenerate (from `brains/weather/tests`):

    PYTHONPATH=../runtime:.:../../../jobs/brain_platform python3 -c "import json; from datetime import datetime, timezone; \
      from weather_support import FixtureSource, LAKES; from sector_weather.publish import run; from sector_weather.client import PointCache; \
      st = run(list(LAKES.values()), FixtureSource(), PointCache(None), {}, datetime(2026,11,7,1,0,tzinfo=timezone.utc), lake_ids=['Guntersville|AL'])['states']['Guntersville|AL']; \
      print(json.dumps(st, indent=1, sort_keys=True))"
