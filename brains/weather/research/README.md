# Weather research

`GAPS.json` lists the open gaps; `CHARTER.json` is the bowfishing charter. The validation that closes WX-001 and WX-002 is pre-registered in
`docs/brains/WEATHER_BRAIN_PLAN.md` §5 (repository docs, never read at runtime). Its data (paired station observations) goes to the research
workspace `weather-brain`, never to Git.

Retrospective grading of the same criteria on a past window (plan §5.4) is pre-registered in
[`docs/brains/weather-retro-validation/`](../../../docs/brains/weather-retro-validation/) (protocol `WX-RETRO-2026-11-23`, hashed before any
data was fetched) with a draft Mac mini request. Its runner is `tools/research/weather_retro_validation.py`; the runtime never reads either.
