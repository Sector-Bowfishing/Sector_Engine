"""score_brains --wind-measurements: additive only. The certification value/version/basis are untouched, no score.changed event is
emitted, and without the flag the wind block is exactly the frozen block (default OFF)."""
import datetime as dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_brains  # noqa: E402
from score_brains import UPSTREAM, plan_writes  # noqa: E402
from sector_brain_platform import frozen_score  # noqa: E402

NOW = dt.datetime(2026, 10, 19, 22, 0, tzinfo=dt.timezone.utc)
FROZEN = score_brains.rtdb_safe(json.load(open(score_brains.FROZEN)))


def scores():
    s = {b: {"value": 1.0, "scale": 10, "basis": "COMPUTED", "scoreVersion": "v1", "scoreBreakdown": {}, "scoreBlockers": []} for b in UPSTREAM}
    s["wind"] = frozen_score(FROZEN["wind"])
    return s


def test_attach_is_additive_and_eventless():
    old = scores()
    new = score_brains.attach_wind_measurements(scores(), {"health": {}}, NOW)
    w = new["wind"]
    assert {k: v for k, v in w.items() if k != "measurements"} == old["wind"]
    assert w["value"] == 3.3 and w["scoreVersion"] == "wind-certification-rubric-v1"
    m = w["measurements"]
    assert m["schema"] == "wind-score-measurements-v1" and m.get("consistency", []) == []      # stored form omits the empty list
    assert m["windCapability"]["scoreVersion"] == "wind-specialist-capability-v2"
    updates, changed = plan_writes(new, {b: {} for b in UPSTREAM}, NOW, old_scores=old)
    assert "scores/wind" in updates and not [k for k in updates if k.startswith("activity/")]      # rewrite, but no score.changed event


def test_flag_defaults_off():
    src = open(score_brains.__file__).read()
    assert '"--wind-measurements", action="store_true"' in src and "if a.wind_measurements:" in src
    assert "measurements" not in score_brains.compute.__code__.co_names


def _rtdb(o):
    if isinstance(o, dict):
        o = {k: _rtdb(v) for k, v in o.items() if v is not None}
        return {k: v for k, v in o.items() if v not in ({}, [])}
    return [_rtdb(v) for v in o] if isinstance(o, list) else o


def test_hourly_rerun_does_not_rewrite_wind():
    """Found by the 2026-10-19 production dry run: clock timestamps and nulls made every hourly run rewrite /scores/wind."""
    first = score_brains.attach_wind_measurements(scores(), {"health": {}}, NOW)
    published = {k: _rtdb(v) for k, v in first.items()}                       # what RTDB returns on the next read
    later = score_brains.attach_wind_measurements(scores(), {"health": {}}, NOW + dt.timedelta(hours=5))
    updates, _ = plan_writes(later, {b: {} for b in UPSTREAM}, NOW + dt.timedelta(hours=5), old_scores=published)
    assert "scores/wind" not in updates
    changed = score_brains.attach_wind_measurements(scores(), {"health": {"wind": {"status": "DEGRADED"}}}, NOW + dt.timedelta(hours=6))
    updates, _ = plan_writes(changed, {b: {} for b in UPSTREAM}, NOW, old_scores=published)
    assert "scores/wind" in updates and not [k for k in updates if k.startswith("activity/")]    # real change: rewrite, still no event
