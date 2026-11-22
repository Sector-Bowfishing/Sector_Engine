# Weather states built by the Weather Brain (GENERATED, not hand-edited)

The Weather Brain's own `run()` (`brains/weather/runtime/sector_weather/publish.py`, main 1f52168) wrote each file. It ran over its recorded
NWS fixtures (`brains/weather/tests/fixtures/recorded/`, api.weather.gov responses recorded 2026-11-06 at about 20:51Z), using the
fixture source in `brains/weather/tests/weather_support.py`, one lake at a time, at the run time in the file name. The output is
`states[lakeId]`, written as `json.dump(state, indent=1, sort_keys=True)`. Every file validates against
`brains/weather/contracts/weather-state-v1.schema.json` (`tests/test_weather_input.py`).

The runs at 23:00Z and 01:00Z reuse the same recorded grid and observations. Their observations are older than 2 h, so Weather reports
`kind: forecast`, and only the forecast grid supplies cloud.

| file | lake | run time | sha256 |
|---|---|---|---|
| guntersville-2026-11-06T2051Z.json | Guntersville\|AL | 2026-11-06 20:51Z | e18b7ef83e494849fd9c8493011a1f16545f72f5f7f50832e71bf415042322ba |
| guntersville-2026-11-07T0100Z.json | Guntersville\|AL | 2026-11-07 01:00Z | 8d8e1f11b4cb05ded4a6a280ff9bc477c02109765e17d30ccbf184d9165fdb1e |
| champlain-2026-11-06T2051Z.json | Champlain\|VT | 2026-11-06 20:51Z | 6cf94ca1fe7211590314141556621d54d54902f06698262504639d364a67ac71 |
| champlain-2026-11-06T2300Z.json | Champlain\|VT | 2026-11-06 23:00Z | 07e9a88855df6170f0e8b5f7474f42a2af7d43e214a446ee2dd2b12cbd2fced6 |

Regenerate (from `brains/weather/tests`):

    PYTHONPATH=../runtime:.:../../../jobs/brain_platform python3 -c "import json; from datetime import datetime, timezone; \
      from weather_support import FixtureSource, LAKES; from sector_weather.publish import run; from sector_weather.client import PointCache; \
      st = run(list(LAKES.values()), FixtureSource(), PointCache(None), {}, datetime(2026,11,7,1,0,tzinfo=timezone.utc), lake_ids=['Guntersville|AL'])['states']['Guntersville|AL']; \
      print(json.dumps(st, indent=1, sort_keys=True))"
