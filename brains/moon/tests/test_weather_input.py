"""The cloud input against the Weather Brain's real state: every Weather fixture here is schema-valid, real states built by the Weather
Brain from its recorded NWS fixtures give the expected class and basis, and a mid-night run judges the hours still ahead (#236 review)."""
import datetime as dt
import json
import os
import re

import pytest

import moon_support as S
from moon_brain import darkness as D
from moon_brain import night

SCHEMA = json.load(open(S.WEATHER_SCHEMA, encoding="utf-8"))
REAL = sorted(f for f in os.listdir(S.WEATHER_STATES) if f.endswith(".json"))


def schema_errors(v, s, root=SCHEMA, path="$"):
    """The JSON Schema subset the Weather state schema uses (the same subset brains/weather/tests checks it with): type incl. unions, const,
    enum, pattern, minimum, required, properties, additionalProperties false, items, maxItems, $ref."""
    if "$ref" in s:
        node = root
        for part in s["$ref"][2:].split("/"):
            node = node[part]
        yield from schema_errors(v, node, root, path)
    types = s.get("type")
    if types is not None:
        types = types if isinstance(types, list) else [types]
        py = {"object": dict, "array": list, "string": str, "boolean": bool, "null": type(None), "number": (int, float), "integer": int}
        if not any(isinstance(v, py[t]) and not (t in ("number", "integer") and isinstance(v, bool)) for t in types):
            yield f"{path}: {type(v).__name__} not {types}"
            return
    if "const" in s and v != s["const"]:
        yield f"{path}: != {s['const']!r}"
    if "enum" in s and v not in s["enum"]:
        yield f"{path}: {v!r} not in enum"
    if isinstance(v, str) and "pattern" in s and not re.search(s["pattern"], v):
        yield f"{path}: pattern"
    if isinstance(v, (int, float)) and "minimum" in s and v < s["minimum"]:
        yield f"{path}: below minimum"
    if isinstance(v, list):
        if "maxItems" in s and len(v) > s["maxItems"]:
            yield f"{path}: too many items"
        for i, x in enumerate(v):
            yield from schema_errors(x, s.get("items", {}), root, f"{path}[{i}]")
    if isinstance(v, dict):
        for k in s.get("required", []):
            if k not in v:
                yield f"{path}: missing {k}"
        props = s.get("properties", {})
        if s.get("additionalProperties") is False:
            for k in v:
                if k not in props:
                    yield f"{path}: unexpected {k}"
        for k, sub in props.items():
            if k in v:
                yield from schema_errors(v[k], sub, root, f"{path}.{k}")


def _sky(lat, lon, date):
    return night.tonight(lat, lon, date)


def test_the_checker_catches_a_schema_violation():
    bad = S.real_weather_state(REAL[0])
    bad["forecast"]["hourly"] = bad["forecast"]["hourly"] * 2                # 24 rows: over maxItems 12
    assert any("too many items" in e for e in schema_errors(bad, SCHEMA))


@pytest.mark.parametrize("name", REAL)
def test_every_recorded_weather_state_is_schema_valid(name):
    assert list(schema_errors(S.real_weather_state(name), SCHEMA)) == []


@pytest.mark.parametrize("doc", [S.run_state("2026-11-22T23:00:00Z", 80), S.weather_state([]), S.run_state("2026-11-23T03:00:00Z", 40, "observation"),
                                 S.weather_state(S.night_rows("2026-11-22T23:00:00Z", [None, 10, 20]))], ids=["evening", "empty", "observation", "nulls"])
def test_every_hand_built_weather_state_is_schema_valid(doc):
    assert list(schema_errors(doc, SCHEMA)) == []


GUN, CHAMP = (34.42, -86.26), (44.47, -73.3)
NIGHT = dt.date(2026, 11, 6)


@pytest.mark.parametrize("name,where,status,basis,cls,full", [
    # an afternoon run (20:51Z) reaches only 08Z: 9 of the night's 13 hours, below 75 %: moon only, said so
    ("guntersville-2026-11-06T2051Z.json", GUN, "MISSING", "MOON_ONLY", "DARK", None),
    # an evening run (01:00Z, astronomical dusk ~00:15Z) covers the rest of the night: low cloud, cancels nothing, a dark waning crescent
    ("guntersville-2026-11-07T0100Z.json", GUN, "AVAILABLE", "MOON_AND_CLOUD", "DARK", False),
    ("champlain-2026-11-06T2051Z.json", CHAMP, "MISSING", "MOON_ONLY", "DARK", None),
    ("champlain-2026-11-06T2300Z.json", CHAMP, "AVAILABLE", "MOON_AND_CLOUD", "DARK", True),
])
def test_real_weather_states_give_the_expected_class_and_basis(name, where, status, basis, cls, full):
    sky = _sky(*where, NIGHT)
    d = D.assess(sky, S.real_weather_state(name))
    assert (d["cloudCover"]["status"], d["basis"], d["class"]) == (status, basis, cls), d["cloudCover"]
    if status == "MISSING":
        assert d["cloudCover"]["reason"] == "INSUFFICIENT_COVERAGE" and "No cloud value was assumed" in d["statement"]
    else:
        assert d["cloudCover"]["span"]["fullWindow"] is full
        assert "NWS forecast grid" in d["statement"] and d["cloudCover"]["origins"] == {"forecastGrid": d["cloudCover"]["hoursWithValue"]}


def test_real_champlain_evening_cloud_is_the_mean_of_its_forecast_hours():
    sky = _sky(*CHAMP, NIGHT)
    st = S.real_weather_state("champlain-2026-11-06T2300Z.json")
    c = D.assess(sky, st)["cloudCover"]
    s, e = (D._parse(sky["window"][k]) for k in ("start", "end"))
    vals = {int(D._parse(r["at"]) // 3600) * 3600: r["cloudCoverPct"] for r in st["forecast"]["hourly"]}
    vals[int(D._parse(st["sky"]["cloudCoverPct"]["at"]) // 3600) * 3600] = st["sky"]["cloudCoverPct"]["value"]
    used = [v for h, v in vals.items() if s - 1800 <= h <= e + 1800 and v is not None]
    assert c["meanPct"] == round(sum(used) / len(used), 1) and c["hoursWithValue"] == len(used)


SKY = night.tonight(34.42, -86.26, dt.date(2026, 11, 22))                  # window ~00:05Z -> ~12:26Z on the 23rd


@pytest.mark.parametrize("run_at", ["2026-11-23T03:00:00Z", "2026-11-23T06:30:00Z", "2026-11-23T09:00:00Z"])
def test_a_mid_night_weather_run_judges_the_hours_still_ahead(run_at):
    """H1: a real state cannot hold hours before its run. A mid-night run must still give MOON_AND_CLOUD, over the rest of the window."""
    d = D.assess(SKY, S.run_state(run_at, 100))
    c = d["cloudCover"]
    assert d["basis"] == "MOON_AND_CLOUD" and c["span"]["fullWindow"] is False
    assert c["span"]["start"] == run_at[:13] + ":00Z" and c["span"]["end"] == SKY["window"]["end"][:16] + "Z"
    assert "the rest of the fishing window" in d["statement"]


def test_a_weather_run_after_the_window_is_refused():
    d = D.assess(SKY, S.run_state("2026-11-23T13:00:00Z", 100))
    assert d["basis"] == "MOON_ONLY" and d["cloudCover"]["reason"] == "WEATHER_AFTER_WINDOW"


def test_an_observed_current_hour_is_named_in_the_statement():
    d = D.assess(SKY, S.run_state("2026-11-23T02:00:00Z", 90, origin="observation"))
    assert d["cloudCover"]["origins"]["observation"] == 1
    assert "NWS forecast grid" in d["statement"] and "the current hour is an NWS station observation" in d["statement"]


def test_a_row_without_cloud_cover_is_a_null_value():
    """M1: the Weather schema requires only `at` in a forecast row."""
    w = S.run_state("2026-11-22T23:00:00Z", 60)
    for r in w["forecast"]["hourly"][::6]:
        del r["cloudCoverPct"]
    assert list(schema_errors(w, SCHEMA)) == []
    c = D.assess(SKY, w)["cloudCover"]
    assert c["status"] == "AVAILABLE" and c["hoursWithValue"] == 12 - 2 and c["windowHours"] == 13   # 00-11Z rows, 2 without a value; 12Z not forecast


def test_values_outside_the_cloud_span_are_not_checked():
    """LOW: a bad value for an hour outside the span does not refuse the hours inside it."""
    w = S.run_state("2026-11-23T03:00:00Z", 70)
    w["forecast"]["hourly"][-1]["cloudCoverPct"] = 140                     # 15Z: after the window
    assert D.assess(SKY, w)["basis"] == "MOON_AND_CLOUD"
    w["forecast"]["hourly"][0]["cloudCoverPct"] = 140                      # 04Z: inside it
    assert D.assess(SKY, w)["cloudCover"]["reason"] == "CLOUD_COVER_OUT_OF_RANGE"


def test_evening_date_refuses_a_naive_now():
    with pytest.raises(ValueError):
        night.evening_date(34.42, -86.26, dt.datetime(2026, 11, 22, 20, 0))
