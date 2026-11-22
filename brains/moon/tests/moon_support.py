"""Shared support for the Moon tests: one REAL dry-run publish (unchanged `publish()`) over a fixed slice of the packaged lake directory into an
in-memory store, and the pinned artifact build context. Offline; nothing is published."""
import datetime as dt
import os
import uuid

import moon_brain  # noqa: F401
from moon_brain import lakes as L, publish_artifact as pa
from moon_brain.publish import publish
from moon_brain.writer import DryRunWriter

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
NOW = dt.datetime(2026, 11, 22, 19, 0, tzinfo=dt.timezone.utc)
NIGHT = dt.date(2026, 11, 22)
SLICE = ("Guntersville|AL", "Lake Martin|AL", "Iliamna|AK", "Teshekpuk|AK")
_D = {}


def directory(only=SLICE) -> dict:
    if "d" not in _D:
        _D["d"] = L.load()
    d = _D["d"]
    return {**d, "lakes": [r for r in d["lakes"] if only is None or r["lakeId"] in only]}


def uid(n):
    return str(uuid.UUID(int=n, version=4))


def run_updates(date=NIGHT, weather=None, only=SLICE) -> dict:
    w = DryRunWriter()
    rep = publish(directory(only), w, date, weather, now=NOW)
    assert rep["ok"], rep["errors"]
    flat = {}
    for p in w.patches:
        flat.update(p)
    return flat


def build(updates, *, n=1, generated_at="2026-11-22T19:00:00Z", consumed=None):
    ctx = pa.BuildContext(generated_at, uid(n), "test@1", lifecycle=pa.LIFECYCLE)
    return pa.build_artifact(updates, ctx, release_lineage=L.lineage(), consumed=consumed)


def weather_state(hourly, current=None, generated_at="2026-11-22T23:00:00Z"):
    """A Weather Brain state document (sector-brain-weather-state-v1) reduced to what the Moon Brain reads, in the producer's shape
    (brains/weather/runtime/sector_weather/state.py on PR #234): forecast.hourly[] rows {at, cloudCoverPct, ...} and sky.cloudCoverPct
    {value, at, origin, station}. hourly: [(iso, pct)]; current: (iso, pct, origin) or None."""
    return {"schema": "sector-brain-weather-state-v1", "brainId": "weather", "generatedAt": generated_at, "kind": "forecast",
            "sky": {"cloudCoverPct": None if current is None else {"value": current[1], "at": current[0], "origin": current[2], "station": None},
                    "word": None},
            "forecast": {"source": "NWS forecast grid (NBM-based NDFD)", "issuedAt": "2026-11-22T22:41:00Z",
                         "hourly": [{"at": at, "airTemperatureF": 50.0, "humidityPct": 80, "dewPointF": 44.0, "cloudCoverPct": pct,
                                     "precipProbabilityPct": 10} for at, pct in hourly]}}


def hourly_over(start_iso, end_iso, pct):
    """[(iso, pct)] at every top of hour from the hour of start to one hour past end."""
    s = dt.datetime.fromisoformat(start_iso.replace("Z", "+00:00")).replace(minute=0, second=0)
    e = dt.datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    out = []
    while s <= e + dt.timedelta(hours=1):
        out.append((s.strftime("%Y-%m-%dT%H:%M:%SZ"), pct))
        s += dt.timedelta(hours=1)
    return out
