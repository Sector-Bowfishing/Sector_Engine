"""DARKNESS_RULE_V1: stated in the contract before scoring; cloud is never assumed."""
import datetime as dt
import json
import os

import pytest

from moon_brain import darkness as D
from moon_brain import night

CONTRACT = json.load(open(os.path.join(os.path.dirname(__file__), "..", "contracts", "moon-night-light-v1.json"), encoding="utf-8"))
SKY = night.tonight(34.42, -86.26, dt.date(2026, 11, 22))       # ~97 % moon, up most of the window


def _hourly(pct, start=SKY["window"]["start"], end=SKY["window"]["end"]):
    s = dt.datetime.fromisoformat(start.replace("Z", "+00:00")).replace(minute=0, second=0)
    e = dt.datetime.fromisoformat(end.replace("Z", "+00:00"))
    rows = []
    while s <= e + dt.timedelta(hours=1):
        rows.append({"at": s.strftime("%Y-%m-%dT%H:%M:%SZ"), "cloudCoverPct": pct})
        s += dt.timedelta(hours=1)
    return {"contract": "moon-weather-cloud-input-v0", "source": "weather", "issuedAt": "2026-11-22T18:00:00Z", "hourly": rows}


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
    ({"hourly": []}, "NO_HOURLY_CLOUD_COVER"),
    ({"hourly": [{"at": "2026-11-23T03:00:00Z"}]}, "MALFORMED_HOURLY_ROW"),
    ({"hourly": [{"at": "2026-11-23T03:00:00Z", "cloudCoverPct": 140}]}, "CLOUD_COVER_OUT_OF_RANGE"),
    ({"hourly": [{"at": "2026-11-23T03:00:00Z", "cloudCoverPct": 90}]}, "INSUFFICIENT_COVERAGE"),
    ({"hourly": [{"at": "2026-11-20T03:00:00Z", "cloudCoverPct": 90}] * 20}, "INSUFFICIENT_COVERAGE"),
])
def test_unusable_cloud_input_is_reported_never_filled(weather, reason):
    d = D.assess(SKY, weather)
    assert d["basis"] == "MOON_ONLY" and d["cloudCover"]["status"] == "MISSING" and d["cloudCover"]["reason"] == reason


def test_null_hours_are_skipped_but_count_against_coverage():
    w = _hourly(100)
    for r in w["hourly"][::2]:
        r["cloudCoverPct"] = None
    d = D.assess(SKY, w)
    assert d["cloudCover"]["status"] == "MISSING" and d["cloudCover"]["reason"] == "INSUFFICIENT_COVERAGE"


def test_no_night_is_its_own_class():
    sky = night.tonight(70.6, -153.5, dt.date(2026, 6, 21))
    d = D.assess(sky, _hourly(0, "2026-06-21T20:00:00Z", "2026-06-22T08:00:00Z"))
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
