"""Run-level behaviour, the state schema, the write set's ownership, and the DISABLED registration (merging changes nothing at runtime)."""
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from sector_brain_platform import DryRunStore, execution_control as EC, orchestration as O
from sector_brain_platform.ownership import path_allowed
from sector_brain_platform.publisher import registry as REG
from sector_weather import contract as C
from sector_weather.client import FetchError, NwsHttp, OutOfCoverage, PointCache
from sector_weather.publish import REGISTRY_CHILDREN, run
from weather_support import LAKES, RECORDED_NOW, REPO, FixtureSource

HERE = os.path.dirname(os.path.abspath(__file__))
SCHEMA = json.load(open(os.path.join(HERE, "..", "contracts", "weather-state-v1.schema.json")))


def _errors(v, s, root=SCHEMA, path="$"):
    """The JSON Schema subset the state schema uses (type incl. unions, const, enum, pattern, minimum, required, properties,
    additionalProperties false, items, maxItems, $ref)."""
    if "$ref" in s:
        node = root
        for part in s["$ref"][2:].split("/"):
            node = node[part]
        yield from _errors(v, node, root, path)
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
            yield from _errors(x, s.get("items", {}), root, f"{path}[{i}]")
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
                yield from _errors(v[k], sub, root, f"{path}.{k}")


def _run(now=RECORDED_NOW, published=None, src=None):
    return run(list(LAKES.values()), src or FixtureSource(), PointCache(None), published or {}, now)


def test_every_state_validates_against_the_published_schema():
    for now in (RECORDED_NOW, datetime(2026, 11, 6, 19, tzinfo=timezone.utc)):
        for lid, st in _run(now)["states"].items():
            assert list(_errors(st, SCHEMA)) == [], lid


def test_the_write_set_touches_only_weather_paths_and_the_publisher_registry_authorises_each():
    out = _run()
    store = DryRunStore({}, brain_id=C.BRAIN_ID)
    store.update(out["updates"])                                         # ownership + key checks of the live writer
    reg = REG.default_registry()
    specs = [reg.spec(s) for s in REG.WEATHER_SCHEMAS]
    for path, value in out["updates"].items():
        assert path_allowed("weather", path), path
        if value is None:
            assert any(reg.authorizing_family(sp, "/" + path, delete=True) for sp in specs), path
        else:
            assert any(reg.authorizing_family(sp, "/" + path) for sp in specs), path
        assert not path.startswith(("snapshots/", "health/", "sources/", "scores/")), path


def test_runtime_registry_children_equal_the_publisher_registration():
    assert REGISTRY_CHILDREN == REG.WEATHER_REGISTRY_CHILDREN


def test_planner_skips_lakes_that_are_not_due_and_fetches_shared_sources_once():
    first = _run()
    src = FixtureSource()
    second = _run(RECORDED_NOW + timedelta(minutes=30), published=first["states"], src=src)
    assert second["reasons"]["Champlain|VT"] == ["not due"]               # STEADY, nextCheckAt 2 h out
    assert "lakes/Champlain_VT/states/weather" not in second["updates"]
    assert second["reasons"]["Guntersville|AL"]                           # WATCH (stale observations): due every grant
    assert sum(1 for c in src.calls if c[0] == "grid") == 1


def test_out_of_coverage_lakes_are_blocked_with_no_state():
    class Outside(FixtureSource):
        def point(self, lat, lon):
            raise OutOfCoverage("404")
    out = _run(src=Outside())
    assert set(out["readiness"].values()) == {"BLOCKED"} and out["states"] == {}
    assert out["updates"]["lakeFleet/Guntersville_AL/readiness/weather"] == "BLOCKED"


def test_a_failed_station_fetch_degrades_that_lake_and_never_invents_values():
    class Down(FixtureSource):
        def observations(self, station, now):
            raise FetchError("HTTP 503")
    out = _run(src=Down())
    st = out["states"]["Champlain|VT"]
    assert st["pressure"] is None and st["kind"] == "forecast" and out["errors"]
    assert out["readiness"]["Champlain|VT"] == "DEGRADED"
    # a station failure is a PARTIAL run, said explicitly; lastSuccessfulRun is written, never null
    assert out["updates"]["brains/weather/lastRunOutcome"]["status"] == "PARTIAL"
    assert out["updates"]["brains/weather/lastSuccessfulRun"] == "2026-11-06T20:51:00Z"
    assert all(v is not None for k, v in out["updates"].items() if k != "brains/weather/lastError")


def test_a_run_that_computes_nothing_is_failed_and_keeps_the_previous_last_success():
    class Broken(FixtureSource):
        def point(self, lat, lon):
            raise RuntimeError("boom")
    out = _run(src=Broken())
    assert out["updates"]["brains/weather/lastRunOutcome"]["status"] == "FAILED"
    assert "brains/weather/lastSuccessfulRun" not in out["updates"]


def test_the_client_identifies_itself_refuses_other_hosts_and_maps_404():
    seen = []

    def opener(req, timeout):
        seen.append(req)
        if "/points/" in req.full_url:
            raise urllib.error.HTTPError(req.full_url, 404, "Not Found", {}, None)
        return io.BytesIO(b'{"ok": true}')
    http = NwsHttp(user_agent="Sector-WeatherBrain/test (contact)", pace_s=0, opener=opener)
    assert http.get("https://api.weather.gov/gridpoints/HUN/76,30") == {"ok": True}
    assert seen[0].get_header("User-agent") == "Sector-WeatherBrain/test (contact)"
    assert seen[0].get_header("Accept") == "application/geo+json"
    with pytest.raises(OutOfCoverage):
        http.get("https://api.weather.gov/points/0,0")
    with pytest.raises(FetchError):
        http.get("https://example.com/x")


def test_write_is_refused_by_the_cli():
    r = subprocess.run([sys.executable, "run.py", "--write"], cwd=os.path.join(HERE, "..", "runtime"), capture_output=True, text=True,
                       env={**os.environ, "PYTHONPATH": os.path.join(REPO, "jobs", "brain_platform")})
    assert r.returncode == 2 and "REFUSED" in r.stderr


def test_registered_disabled_parked_never_started_and_customer_publication_off():
    m = O.load_manifest()
    b = m["brains"]["weather"]
    assert b["activityState"] == "PARKED" and b["executionTarget"]["kind"] == "none" and b["executionTarget"]["startedByOrchestrator"] is False
    assert b["customerPublication"] is False and b["lifecycle"] == "CALIBRATION"
    ctx = {"manifest": m, "mode": "PRE_PRODUCTION", "now": RECORDED_NOW, "states": {}, "activity": O.effective_activity(m), "running": {}}
    assert O.decide_brain("weather", "SCHEDULE", ctx)["decision"] == "SKIP_PARKED"
    ok, _ = EC.gate(EC.parse({"schema": EC.SCHEMA, "state": "ENABLED", "approvalRef": "x", "brains": {"wind": {"enabled": True}}}),
                    "weather", "SCHEDULE", admin=None, starts_this_cycle=0, runs_today=0)
    assert not ok                                                         # absent from the execution control = disabled
    assert not any("weather" in (j.get("brainId") or "") for j in m["jobs"].values())   # no job registered: nothing to start
    brain = json.load(open(os.path.join(HERE, "..", "brain.json")))
    assert brain["lifecycle"] == "CALIBRATION" and brain["operations"]["customerPublication"]["status"] == "NOT_ELIGIBLE"
    assert O.due_after_hours(b) == C.DUE_AFTER_HOURS and b["freshness"]["staleAfterHours"] == C.STALE_AFTER_HOURS


def test_specialist_boundary_no_recommendation_or_score_fields():
    text = json.dumps(_run()["states"]).lower()
    for word in ("recommend", "score", "bite", "angler", "good night"):
        assert word not in text, word
