# Weather Brain (`brainId: weather`)

**What it is.** The Weather Brain answers, per lake for every directory lake: *what is the weather doing here, and is it changing?* It
reads the National Weather Service only: station observations (ASOS/AWOS, the 3 nearest stations NWS lists for the lake's grid cell) and the
NWS forecast grid. It publishes the four app tiles (Sky, Barometric Pressure with its 3 h trend, Air Temperature, Humidity) with the exact
meaning the iOS app gives them, plus the **weather-change signal** (CHANGE / WATCH / STEADY) that Lake and Water Temp use to refresh early.
**Bowfisher decision (weather part):** is the weather turning before or during the trip. Lifecycle CALIBRATION, internal only,
customer publication off. **Registered DISABLED:** no cloud job, PARKED in the control manifest; the live writer is gated (approved release + `WEATHER_WRITE_APPROVED=1`).

Rules for every session: [`BRAIN_OPERATING_CONTRACT.md`](BRAIN_OPERATING_CONTRACT.md). Identity and edges: [`brain.json`](brain.json).
State contract: [`contracts/weather-state-v1.md`](contracts/weather-state-v1.md) (thresholds, cadence) and its schema. Plan and rollout:
`docs/brains/WEATHER_BRAIN_PLAN.md`. Provider terms: [`docs/NWS_PROVIDER.md`](docs/NWS_PROVIDER.md).

| Path | Holds |
|---|---|
| `runtime/` | `run.py` (entry point), `sector_weather/`: `nws.py` (decoders, the Engine adapter's rules), `client.py` (the only network code), `reading.py` (tiles), `signal.py` (weather change), `freshness.py` (cadence + planner), `state.py`, `publish.py` (write set) |
| `contracts/` | `weather-state-v1.md` + `.schema.json` (the lake state); `weather-publication-v1.json` (derived from the Publisher registry by `describe_contract.py --check`) |
| `tests/` | offline tests; `fixtures/recorded/` (real NWS responses, see PROVENANCE.md), `fixtures/hand_built/` (labelled HAND_BUILT) |
| `research/` | `GAPS.json`, `CHARTER.json`, README (no data in Git) |
| `docs/` | `NWS_PROVIDER.md` |

```bash
cd brains/weather
python3 -m pytest -q                                                   # offline tests (pytest.ini sets the import roots)
cd runtime && PYTHONPATH=../../../jobs/brain_platform python3 run.py --dry-run /tmp/weather.json --limit 5 --point-cache /tmp/wx-points.json
                                                                       # reads the public lake directory and NWS (read-only); writes nothing remote
python3 run.py --write                                                 # REFUSED: exit 2 while the release is NOT_RECORDED; exit 3 without WEATHER_WRITE_APPROVED=1
```
