"""The durable NWS /points cache (client.PointCache) and its revalidation in publish.run. Offline: recorded fixtures and hand-built answers."""
import json
import os
import subprocess
import sys
from datetime import timedelta

import pytest
from sector_weather.client import POINT_CACHE_ENV, POINT_CACHE_SCHEMA, Moved, NwsHttp, OutOfCoverage, PointCache, point_key
from sector_weather.publish import run
from weather_support import HERE, LAKES, RECORDED_NOW, REPO, FixtureSource

G = LAKES["Guntersville|AL"]


def _run(cache, src=None, lakes=("Guntersville|AL",), now=RECORDED_NOW):
    return run([LAKES[l] for l in lakes], src or FixtureSource(), cache, {}, now)


def _points(src):
    return [c for c in src.calls if c[0] in ("point", "stations")]


def test_miss_then_hit_across_runs_through_the_file(tmp_path):
    path = str(tmp_path / "ssd" / "weather" / "nws-points.json")         # the parent folder does not exist yet
    src1 = FixtureSource()
    c1 = PointCache(path)
    first = _run(c1, src1)
    c1.save()
    assert len(_points(src1)) == 2 and c1.stats["misses"] == 1
    doc = json.load(open(path))
    assert doc["schema"] == POINT_CACHE_SCHEMA and list(doc["entries"]) == [point_key(G)]
    assert point_key(G) == "Guntersville|AL@34.4200,-86.2600"

    src2 = FixtureSource()
    c2 = PointCache(path)
    second = _run(c2, src2)
    assert _points(src2) == [] and c2.stats["hits"] == 1                  # no /points and no station list on the second run
    assert first["updates"] == second["updates"]                           # behaviour unchanged by the cache


def test_a_moved_lake_coordinate_is_a_miss(tmp_path):
    c = PointCache(str(tmp_path / "p.json"))
    _run(c)
    moved = {**G, "lat": 34.4201}
    assert c.get(moved, RECORDED_NOW) is None and c.get(G, RECORDED_NOW) is not None


def test_entries_expire_after_the_ttl_and_a_future_stamp_is_not_trusted(tmp_path):
    c = PointCache(str(tmp_path / "p.json"))
    _run(c)
    assert c.get(G, RECORDED_NOW + timedelta(days=29, hours=23)) is not None
    assert c.get(G, RECORDED_NOW + timedelta(days=30)) is None
    assert c.get(G, RECORDED_NOW - timedelta(days=2)) is None
    assert c.stats["expired"] == 2
    src = FixtureSource()
    _run(c, src, now=RECORDED_NOW + timedelta(days=31))
    assert len(_points(src)) == 2                                          # expired: resolved again


@pytest.mark.parametrize("content", ["not json{", "[]", json.dumps({"Guntersville|AL": {"cachedAt": "2026-11-06T00:00:00Z"}}),
                                     json.dumps({"schema": "other", "entries": {}})])
def test_a_bad_or_foreign_file_is_ignored_and_rewritten(tmp_path, content):
    path = tmp_path / "p.json"
    path.write_text(content)
    c = PointCache(str(path))
    assert c.entries == {} and c.load_error
    src = FixtureSource()
    out = _run(c, src)
    assert not out["errors"] and len(_points(src)) == 2
    c.save()
    assert json.load(open(path))["schema"] == POINT_CACHE_SCHEMA


def test_a_malformed_entry_is_a_miss(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"schema": POINT_CACHE_SCHEMA, "entries": {point_key(G): {"cachedAt": "yesterday"}, "x": 3}}))
    c = PointCache(str(path))
    assert c.get(G, RECORDED_NOW) is None and "x" not in c.entries


def test_a_failed_save_never_fails_the_run(tmp_path, capsys):
    blocker = tmp_path / "file"
    blocker.write_text("x")
    c = PointCache(str(blocker / "p.json"))                               # parent is a file: cannot be created
    _run(c)
    c.save()
    assert "point cache not saved" in capsys.readouterr().err


class _GoneGrid(FixtureSource):
    """The cached grid URL is gone (404) or moved (301); /points now names another grid cell."""

    def __init__(self, exc):
        super().__init__()
        self.exc = exc

    def point(self, lat, lon):
        doc = super().point(lat, lon)
        doc = json.loads(json.dumps(doc))
        doc["properties"]["forecastGridData"] = doc["properties"]["forecastGridData"] + "?moved=1"
        return doc

    def grid(self, url):
        if "moved=1" not in url:
            self.calls.append(("grid", url))
            raise self.exc(url)
        return super().grid(url)


@pytest.mark.parametrize("exc", [lambda u: OutOfCoverage(u), lambda u: Moved(u, u + "x")])
def test_a_cached_grid_that_answers_404_or_301_is_revalidated_in_the_same_run(tmp_path, exc):
    path = str(tmp_path / "p.json")
    c = PointCache(path)
    _run(c)                                                               # caches the original grid URL
    c.save()
    src = _GoneGrid(exc)
    c2 = PointCache(path)
    out = _run(c2, src)
    assert not out["errors"], out["errors"]
    assert c2.stats["revalidated"] == 1 and ("point", G["lat"], G["lon"]) in src.calls
    assert c2.get(G, RECORDED_NOW)["forecastGridData"].endswith("?moved=1")


def test_a_fresh_resolution_keeps_todays_behaviour_on_a_grid_404():
    class Fresh404(FixtureSource):
        def grid(self, url):
            raise OutOfCoverage(url)
    src = Fresh404()
    out = _run(PointCache(None), src)
    assert any(e.startswith("grid ") for e in out["errors"]) and len(_points(src)) == 2


def test_a_cached_station_that_answers_404_is_revalidated_next_run_keeping_the_entry(tmp_path):
    c = PointCache(str(tmp_path / "p.json"))
    _run(c)

    class StationGone(FixtureSource):
        def observations(self, station, now):
            raise OutOfCoverage(station)
    _run(c, StationGone())
    assert c.get(G, RECORDED_NOW)["revalidate"] is True                    # kept, flagged
    src = FixtureSource()
    _run(c, src, now=RECORDED_NOW + timedelta(hours=2))
    assert ("point", G["lat"], G["lon"]) in src.calls and "revalidate" not in c.get(G, RECORDED_NOW)


class _Outage(FixtureSource):
    def point(self, lat, lon):
        self.calls.append(("point", lat, lon))
        raise OutOfCoverage("404 (outage)")


def test_an_outage_404_inside_the_us_is_not_cached_and_is_retried(tmp_path):
    path = str(tmp_path / "p.json")
    c = PointCache(path)
    out = _run(c, _Outage())
    c.save()
    assert out["readiness"]["Guntersville|AL"] == "DISCOVERED" and out["states"] == {}
    assert any("outage" in e for e in out["errors"])
    assert json.load(open(path))["entries"] == {}                         # nothing cached: no BLOCKED answer
    src = FixtureSource()
    out2 = _run(PointCache(path), src, now=RECORDED_NOW + timedelta(hours=1))
    assert not out2["errors"] and len(_points(src)) == 2                 # retried next run


def test_an_outage_keeps_the_last_state_while_it_is_fresh():
    first = _run(PointCache(None))["states"]["Guntersville|AL"]
    stale_now = RECORDED_NOW + timedelta(minutes=1)
    pub = {"Guntersville|AL": {**first, "freshness": {**first["freshness"], "nextCheckAt": first["generatedAt"],
                                                      "freshUntil": (RECORDED_NOW + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")}}}
    out = run([G], _Outage(), PointCache(None), pub, stale_now)
    assert out["states"]["Guntersville|AL"] == pub["Guntersville|AL"] and out["readiness"]["Guntersville|AL"] != "BLOCKED"
    assert "lakes/Guntersville_AL/states/weather" not in out["updates"]   # kept, not rewritten


def test_a_persistent_404_is_blocked_only_after_three_runs_over_24_h_and_only_for_24_h(tmp_path):
    c = PointCache(str(tmp_path / "p.json"))
    for h in (0, 1):
        assert _run(c, _Outage(), now=RECORDED_NOW + timedelta(hours=h))["readiness"]["Guntersville|AL"] != "BLOCKED"
    assert _run(c, _Outage(), now=RECORDED_NOW + timedelta(hours=23))["readiness"]["Guntersville|AL"] != "BLOCKED"   # 3 runs, < 24 h
    late = RECORDED_NOW + timedelta(hours=25)
    assert _run(c, _Outage(), now=late)["readiness"]["Guntersville|AL"] == "BLOCKED"
    assert c.get(G, late + timedelta(hours=23)) is not None and c.get(G, late + timedelta(hours=24)) is None


def test_a_real_out_of_us_point_is_blocked_at_once_and_cached_for_24_h_only(tmp_path):
    abroad = {"id": "Geneva|XX", "lat": 46.2, "lon": 6.15}
    c = PointCache(str(tmp_path / "p.json"))
    out = run([abroad], _Outage(), c, {}, RECORDED_NOW)
    assert out["readiness"] == {"Geneva|XX": "BLOCKED"}
    assert c.get(abroad, RECORDED_NOW + timedelta(hours=23))["outOfCoverage"] is True
    assert c.get(abroad, RECORDED_NOW + timedelta(hours=24)) is None


def test_a_revalidation_during_an_outage_keeps_the_old_grid_entry(tmp_path):
    c = PointCache(str(tmp_path / "p.json"))
    _run(c)
    before = dict(c.get(G, RECORDED_NOW))

    class GridGoneAndPointsDown(_Outage):
        def grid(self, url):
            raise OutOfCoverage(url)
    out = _run(c, GridGoneAndPointsDown(), now=RECORDED_NOW + timedelta(hours=1))
    assert any(e.startswith("revalidate ") for e in out["errors"])
    after = c.get(G, RECORDED_NOW + timedelta(hours=1))
    assert after["forecastGridData"] == before["forecastGridData"] and after["stations"] == before["stations"]


def test_a_lake_whose_coordinate_moves_prunes_its_old_entry(tmp_path):
    c = PointCache(str(tmp_path / "p.json"))
    _run(c)
    moved = {**G, "lat": 34.4201}
    c.put(moved, {**c.get(G, RECORDED_NOW)})
    assert list(c.entries) == [point_key(moved)]


def test_a_redirecting_grid_url_is_replaced_by_its_target(tmp_path):
    c = PointCache(str(tmp_path / "p.json"))
    _run(c)
    old = c.get(G, RECORDED_NOW)["forecastGridData"]

    class Redirects(FixtureSource):
        def grid(self, url):
            if "77,30" in url:
                return super().grid(url)
            raise Moved(url, "https://api.weather.gov/gridpoints/HUN/77,30", super().grid(url))
    src = Redirects()
    out = _run(c, src, now=RECORDED_NOW + timedelta(hours=1))
    assert not out["errors"], out["errors"]
    e = c.get(G, RECORDED_NOW + timedelta(hours=1))
    assert e["forecastGridData"].endswith("/77,30") and e["gridpoint"] == "HUN/77,30" and e["forecastGridData"] != old
    src2 = Redirects()
    _run(c, src2, now=RECORDED_NOW + timedelta(hours=3))
    assert [x for x in src2.calls if x[0] == "grid"] == [("grid", e["forecastGridData"])] and _points(src2) == []


def test_the_client_raises_moved_on_a_followed_redirect_with_the_body():
    class R:
        def __init__(self, url):
            self.url = url

        def read(self):
            return b'{"ok": 1}'

        def geturl(self):
            return self.url.replace("76,30", "77,30")

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False
    http = NwsHttp(user_agent="t", pace_s=0, opener=lambda req, timeout: R(req.full_url))
    with pytest.raises(Moved) as e:
        http.get("https://api.weather.gov/gridpoints/HUN/76,30", detect_moved=True)
    assert e.value.doc == {"ok": 1}
    assert http.get("https://api.weather.gov/gridpoints/HUN/76,30") == {"ok": 1}   # without detect_moved: unchanged


def _cli(args, env_extra):
    return subprocess.run([sys.executable, "run.py", *args], cwd=os.path.join(HERE, "..", "runtime"), capture_output=True, text=True,
                          env={**os.environ, "PYTHONPATH": os.path.join(REPO, "jobs", "brain_platform"), **env_extra})


def test_a_cache_inside_the_repository_is_refused(tmp_path):
    if not os.path.exists(os.path.join(REPO, ".git")):
        pytest.skip("not a checkout")
    directory = tmp_path / "lakes.json"
    directory.write_text(json.dumps({"lakes": []}))
    r = _cli(["--dry-run", str(tmp_path / "o.json"), "--directory", str(directory)], {POINT_CACHE_ENV: os.path.join(REPO, "nws-points.json")})
    assert r.returncode == 2 and "outside the repository" in r.stderr
    assert not os.path.exists(os.path.join(REPO, "nws-points.json"))
