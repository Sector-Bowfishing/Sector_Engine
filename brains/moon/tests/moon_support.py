"""Shared support for the Moon tests: one REAL dry-run publish (unchanged `publish()`) over a fixed slice of the packaged lake directory into an
in-memory store, and the pinned artifact build context. Offline; nothing is published."""
import copy
import datetime as dt
import json
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


WEATHER_STATES = os.path.join(HERE, "fixtures", "weather_states")
WEATHER_SCHEMA = os.path.join(REPO, "brains", "weather", "contracts", "weather-state-v1.schema.json")
_TEMPLATE = "guntersville-2026-11-07T0100Z.json"


def real_weather_state(name):
    """A Weather state the Weather Brain itself built from its recorded NWS fixtures (tests/fixtures/weather_states/PROVENANCE.md)."""
    with open(os.path.join(WEATHER_STATES, name), encoding="utf-8") as fh:
        return json.load(fh)


def weather_state(hourly, current=None, generated_at="2026-11-22T23:00:00Z"):
    """A schema-valid Weather state (sector-brain-weather-state-v1): a real Weather Brain state used as the template, with the run time,
    the current hour's sky.cloudCoverPct and the forecast.hourly cloud values replaced. hourly: [(iso, pct)], at most 18 rows (the Weather
    schema's maxItems); current: (iso, pct, origin) or None."""
    assert len(hourly) <= 18, "a Weather state holds at most 18 forecast hours"
    doc = copy.deepcopy(real_weather_state(_TEMPLATE))
    tmpl = doc["forecast"]["hourly"][0]
    doc["generatedAt"] = generated_at
    doc["freshness"]["generatedAt"] = generated_at
    doc["sky"]["cloudCoverPct"] = None if current is None else {"value": current[1], "at": current[0], "origin": current[2], "station": None}
    doc["forecast"]["hourly"] = [{**tmpl, "at": at, "cloudCoverPct": pct} for at, pct in hourly]
    return doc


def night_rows(run_at, pct, hours=18):
    """The forecast rows a Weather run at `run_at` carries: the `hours` top-of-hour instants after the run hour (pct: a value or a list)."""
    h0 = dt.datetime.fromisoformat(run_at.replace("Z", "+00:00")).replace(minute=0, second=0)
    vals = pct if isinstance(pct, list) else [pct] * hours
    return [((h0 + dt.timedelta(hours=i + 1)).strftime("%Y-%m-%dT%H:%M:%SZ"), v) for i, v in enumerate(vals[:hours])]


def run_state(run_at, pct, origin="forecastGrid"):
    """A Weather run at `run_at` with every hour (current + 18 ahead) at `pct`."""
    h0 = dt.datetime.fromisoformat(run_at.replace("Z", "+00:00")).replace(minute=0, second=0).strftime("%Y-%m-%dT%H:%M:%SZ")
    return weather_state(night_rows(run_at, pct), current=(h0, pct if not isinstance(pct, list) else pct[0], origin), generated_at=run_at)
