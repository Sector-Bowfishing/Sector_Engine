"""Adaptive freshness (the Brain's own cadence) and the per-lake planner."""
from datetime import datetime, timedelta, timezone

from sector_weather import contract as C
from sector_weather.freshness import decide, due
from sector_weather.nws import parse_time

NOW = datetime(2026, 11, 20, 12, 50, tzinfo=timezone.utc)                 # an hourly Orchestrator grant at :50
OBS = NOW - timedelta(minutes=57)                                         # the :53 METAR of the previous hour


def _mins(iso, base=NOW):
    return (parse_time(iso) - base).total_seconds() / 60


def test_change_and_watch_recheck_every_grant_steady_skips_one():
    for lvl in ("CHANGE", "WATCH"):
        assert _mins(decide(lvl, OBS, NOW)["nextCheckAt"]) == C.RECHECK_MIN
    st = decide("STEADY", OBS, NOW)
    assert 70 < _mins(st["nextCheckAt"]) <= C.STEADY_RECHECK_MAX_MIN        # beyond the next grant (+60, 10 min tolerance)


def test_windows_follow_the_tier_and_never_pass_the_4h_ceiling():
    assert _mins(decide("CHANGE", OBS, NOW)["freshUntil"], OBS) == 57 + 75   # 90 min window, held to the run + 75 min floor
    assert _mins(decide("WATCH", OBS, NOW)["freshUntil"], OBS) == 150
    assert _mins(decide("STEADY", OBS, NOW)["freshUntil"], OBS) == 240
    old = NOW - timedelta(hours=5)
    d = decide("STEADY", old, NOW)
    assert _mins(d["freshUntil"], old) == C.CEILING_MIN and d["stale"] is True


def test_no_observation_is_never_current():
    d = decide("WATCH", None, NOW)
    assert d["stale"] is True and d["observedAt"] is None


def test_planner_reasons():
    st = {"brainVersion": C.BRAIN_VERSION, "thresholdsVersion": C.THRESHOLDS_VERSION, "generatedAt": C.iso(NOW),
          "freshness": {"stale": False, "nextCheckAt": C.iso(NOW + timedelta(minutes=108))}}
    assert due(st, NOW + timedelta(minutes=60)) == []                       # STEADY: the next grant is skipped
    assert due(st, NOW + timedelta(minutes=100)) != []                      # within the 10 min tolerance of nextCheckAt
    assert due(None, NOW) == ["nothing published yet"]
    assert any("thresholds" in r for r in due({**st, "thresholdsVersion": "old"}, NOW))
    assert any("older than" in r for r in due({**st, "freshness": {"stale": False, "nextCheckAt": C.iso(NOW + timedelta(hours=9))}},
                                              NOW + timedelta(hours=4)))
