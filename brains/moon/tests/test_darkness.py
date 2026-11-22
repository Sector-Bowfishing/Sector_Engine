"""DARKNESS_RULE_V1: stated in the contract before scoring; cloud is never assumed."""
import datetime as dt
import json
import os

import pytest

import moon_support as S
from moon_brain import darkness as D
from moon_brain import night

CONTRACT = json.load(open(os.path.join(os.path.dirname(__file__), "..", "contracts", "moon-night-light-v1.json"), encoding="utf-8"))
SKY = night.tonight(34.42, -86.26, dt.date(2026, 11, 22))       # ~97 % moon, up most of the window


def _hourly(pct, run_at="2026-11-22T23:00:00Z"):
    return S.run_state(run_at, pct)


def test_contract_states_the_rule_the_code_runs():
    r = CONTRACT["darknessRule"]
    assert r["id"] == D.RULE_ID
    assert [c["class"] for c in r["classes"]] == [n for n, _ in D.CLASSES] + ["NO_NIGHT"]
    assert [c["when"] for c in r["classes"][:4]] == ["A < 0.15", "0.15 <= A < 0.35", "0.35 <= A < 0.60", "A >= 0.60"]
    assert "(cloudPct - 50) / 50" in r["cloudCancel"] and "0.8 * 0.3" in r["cloudCancel"]
    assert (D.CLOUD_KNEE_PCT, D.CLOUD_SPAN_PCT, D.DEFAULT_CITY_GLOW, D.CITY_GLOW_BLOCKING_WEIGHT) == (50, 50, 0.3, 0.8)


@pytest.mark.parametrize("a,cls", [(0.0, "DARK"), (0.1499, "DARK"), (0.15, "MOSTLY_DARK"), (0.3499, "MOSTLY_DARK"), (0.35, "SOME_MOONLIGHT"),
                                   (0.5999, "SOME_MOONLIGHT"), (0.60, "BRIGHT_MOON"), (1.0, "BRIGHT_MOON")])
def test_class_thresholds(a, cls):
    assert D.classify(a) == cls


def test_missing_cloud_gives_the_moon_only_answer_and_says_so():
    d = D.assess(SKY, None)
    assert d["basis"] == "MOON_ONLY" and d["cloudCover"] == {"status": "MISSING", "reason": "NO_WEATHER_INPUT"}
    assert d["cloudCancel"] is None
    assert d["moonlightIndex"] == round(SKY["moon"]["illumination"] * SKY["window"]["moonlight"]["presence"], 4)
    assert d["class"] == d["moonOnly"]["class"] and "No cloud value was assumed" in d["statement"]


def test_overcast_cancels_moonlight_and_clear_sky_equals_moon_only():
    clear = D.assess(SKY, _hourly(0))
    assert clear["basis"] == "MOON_AND_CLOUD" and clear["cloudCancel"] == 0 and clear["moonlightIndex"] == clear["moonOnly"]["moonlightIndex"]
    over = D.assess(SKY, _hourly(100))
    assert over["cloudCancel"] == pytest.approx(0.76)
    assert over["moonlightIndex"] == pytest.approx(clear["moonlightIndex"] * 0.24, abs=1e-3)
    assert over["class"] in ("DARK", "MOSTLY_DARK") and clear["class"] == "BRIGHT_MOON"
    assert D.assess(SKY, _hourly(50))["cloudCancel"] == 0                  # at the knee nothing is cancelled yet


@pytest.mark.parametrize("weather,reason", [
    (S.weather_state([]), "NO_HOURLY_CLOUD_COVER"),
    ({"hourly": [{"at": "2026-11-23T03:00:00Z", "cloudCoverPct": 90}]}, "UNSUPPORTED_WEATHER_INPUT"),     # the retired v0 shape
    ({**S.weather_state([]), "forecast": {"hourly": [{"cloudCoverPct": 50}]}}, "MALFORMED_HOURLY_ROW"),      # no "at"
    ({k: v for k, v in S.weather_state([]).items() if k != "generatedAt"}, "MALFORMED_HOURLY_ROW"),
    (S.weather_state([("2026-11-23T03:00:00Z", 140)]), "CLOUD_COVER_OUT_OF_RANGE"),
    (S.weather_state([("2026-11-23T03:00:00Z", 90)]), "INSUFFICIENT_COVERAGE"),
    (S.weather_state([("2026-11-20T03:00:00Z", 90)]), "INSUFFICIENT_COVERAGE"),
    (S.weather_state([("2026-11-23T03:00:00Z", 90), ("2026-11-23T03:00:00Z", 20)]), "CONFLICTING_HOURLY_VALUES"),
])
def test_unusable_cloud_input_is_reported_never_filled(weather, reason):
    d = D.assess(SKY, weather)
    assert d["basis"] == "MOON_ONLY" and d["cloudCover"]["status"] == "MISSING" and d["cloudCover"]["reason"] == reason


def test_one_reading_repeated_does_not_pass_the_coverage_floor():
    """#233 review: coverage counted rows, so one hour repeated 12x reached 12/13. It must count distinct hours."""
    w = S.weather_state([("2026-11-23T03:00:00Z", 90)] * 12)
    c = D.window_cloud(w, D._parse(SKY["window"]["start"]), D._parse(SKY["window"]["end"]))
    assert c["status"] == "MISSING" and c["reason"] == "INSUFFICIENT_COVERAGE" and c["hoursWithValue"] == 1
    same_hour_twice = S.weather_state([("2026-11-23T03:00:00Z", 90), ("2026-11-23T03:30:00Z", 90)])
    assert D.window_cloud(same_hour_twice, D._parse(SKY["window"]["start"]), D._parse(SKY["window"]["end"]))["hoursWithValue"] == 1


@pytest.mark.parametrize("at", ["2026-11-23T03:00:00", "2026-11-23 03:00", 1795316400])
def test_a_timestamp_without_an_explicit_offset_is_malformed_not_read_in_local_time(at):
    """#233 review: a naive timestamp was read in the host's local time. It is refused."""
    rows = S.night_rows("2026-11-22T23:00:00Z", 100)
    rows[3] = (at, 100)
    assert D.assess(SKY, S.weather_state(rows))["cloudCover"]["reason"] == "MALFORMED_HOURLY_ROW"


def test_explicit_non_utc_offsets_are_accepted():
    rows = [(dt.datetime.fromisoformat(a.replace("Z", "+00:00")).astimezone(dt.timezone(dt.timedelta(hours=-6))).isoformat(), v)
            for a, v in S.night_rows("2026-11-22T23:00:00Z", 100)]
    assert D.assess(SKY, S.weather_state(rows))["basis"] == "MOON_AND_CLOUD"


def test_the_weather_current_hour_counts_and_the_mean_is_over_distinct_hours():
    rows = S.night_rows("2026-11-22T23:00:00Z", 100)
    first, rest = rows[0], rows[1:]
    w = S.weather_state([(a, 0) for a, _ in rest], current=(first[0], 0, "forecastGrid"), generated_at="2026-11-23T00:10:00Z")
    c = D.assess(SKY, w)["cloudCover"]
    assert c["status"] == "AVAILABLE" and c["meanPct"] == 0 and c["origins"]["forecastGrid"] == c["hoursWithValue"]
    assert c["contract"] == "sector-brain-weather-state-v1" and c["issuedAt"] == w["forecast"]["issuedAt"]
    half = S.weather_state([(a, 100 if i % 2 else 0) for i, (a, _) in enumerate(rows)], generated_at="2026-11-22T23:00:00Z")
    assert D.assess(SKY, half)["cloudCover"]["meanPct"] == pytest.approx(50, abs=5)


def test_only_the_cloud_rows_enter_the_fingerprint():
    from moon_brain import state as ST
    lake = {"lakeId": "Guntersville|AL", "lat": 34.42, "lon": -86.26}
    a = _hourly(80)
    b = _hourly(80)
    b["forecast"]["hourly"][0]["airTemperatureF"] = 12.0                 # an unrelated Weather field
    b["generatedAt"] = "2026-11-22T23:30:00Z"
    assert ST.input_fingerprint(lake, dt.date(2026, 11, 22), a) == ST.input_fingerprint(lake, dt.date(2026, 11, 22), b)
    b["forecast"]["hourly"][0]["cloudCoverPct"] = 10
    assert ST.input_fingerprint(lake, dt.date(2026, 11, 22), a) != ST.input_fingerprint(lake, dt.date(2026, 11, 22), b)


def test_contract_names_the_divergences_from_the_app():
    dv = CONTRACT["divergences"]
    assert "local solar midnight" in dv["illuminationInstant"] and "0.3" in dv["cityGlow"]
    assert CONTRACT["weatherInput"]["schema"] == D.WEATHER_STATE_SCHEMA


def test_null_hours_are_skipped_but_count_against_coverage():
    w = _hourly(100)
    for r in w["forecast"]["hourly"][::2]:
        r["cloudCoverPct"] = None
    d = D.assess(SKY, w)
    assert d["cloudCover"]["status"] == "MISSING" and d["cloudCover"]["reason"] == "INSUFFICIENT_COVERAGE"


def test_no_night_is_its_own_class():
    sky = night.tonight(70.6, -153.5, dt.date(2026, 6, 21))
    d = D.assess(sky, _hourly(0, "2026-06-21T20:00:00Z"))
    assert d["class"] == "NO_NIGHT" and d["basis"] == "NO_NIGHT" and d["cloudCover"]["status"] == "NOT_APPLICABLE"


def test_labels_match_the_engine_darkness_factor():
    assert D.label("DARK", 0.97, 0.05) == "97% moon · moon down"
    assert D.label("DARK", 0.10, 0.80) == "10% moon · dark water"
    assert D.label("MOSTLY_DARK", 0.5, 0.5) == "50% moon · mostly dark"
    assert D.label("SOME_MOONLIGHT", 0.6, 0.8) == "60% moon · some glow"
    assert D.label("BRIGHT_MOON", 1.0, 0.9) == "100% moon · bright — moon up"


def test_copy_makes_no_fish_behaviour_claim():
    """iOS weather-metric-detail 'Copy accuracy (moon)': never 'spooky', 'hold deep', 'bite'."""
    rule = {k: v for k, v in CONTRACT["darknessRule"].items() if k != "notClaimed"}      # notClaimed names the forbidden claims in order to refuse them
    text = json.dumps(rule) + json.dumps([D.assess(SKY, None), D.assess(SKY, _hourly(100))])
    for banned in ("spooky", "spook,", "hold deep", "holding deep", "bite", "angler", "feeding"):
        assert banned not in text.lower()
