"""Discovery decides work from STAC metadata + the published date; the heavy job is started only with work,
only for the work set, with a task count sized to it. No network."""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import dispatch  # noqa: E402

UNTIL = dt.datetime(2026, 10, 13, 8, 0)
GEOM = {"type": "Polygon", "coordinates": [[[-86.4, 34.3], [-85.6, 34.3], [-85.6, 35.0], [-86.4, 35.0], [-86.4, 34.3]]]}


def stac(features):
    def post(url, body):
        assert body["collections"] == ["sentinel-2-c1-l2a"] and "fields" in body and body["bbox"] == [-86.4, 34.3, -85.6, 35.0]
        return {"features": [{"properties": {"datetime": d + "T16:34:00Z", "platform": "sentinel-2b", "eo:cloud_cover": cc}} for d, cc in features]}
    return post


def published(date):
    return lambda url: ({"summary": {"date": date}} if date else None)


def test_bbox_and_slug():
    assert dispatch.bbox_of(GEOM) == [-86.4, 34.3, -85.6, 35.0]
    assert dispatch.slug("Guntersville|AL") == "Guntersville_AL"


def test_newer_clear_pass_is_work():
    d = dispatch.decide("Guntersville|AL", GEOM, UNTIL, stac([("2026-10-12", 12.0), ("2026-10-10", 99.0)]), published("2026-10-07"))
    assert d["work"] is True and d["newestPass"] == "2026-10-12" and d["why"] == "newer pass"


def test_cloudy_or_old_passes_are_not_work():
    d = dispatch.decide("Guntersville|AL", GEOM, UNTIL, stac([("2026-10-12", 95.0), ("2026-09-20", 5.0)]), published("2026-10-07"))
    assert d["work"] is False and d["why"] == "no usable pass in the window"
    d = dispatch.decide("Guntersville|AL", GEOM, UNTIL, stac([("2026-10-07", 10.0)]), published("2026-10-07"))
    assert d["work"] is False and d["why"] == "up to date"


def test_already_dispatched_pass_is_not_work_until_a_newer_one():
    att = {"Guntersville|AL": {"pass": "2026-10-12", "dispatchedAt": "t"}}
    d = dispatch.decide("Guntersville|AL", GEOM, UNTIL, stac([("2026-10-12", 12.0)]), published("2026-10-07"), att)
    assert d["work"] is False and d["why"] == "already dispatched for this pass"
    d = dispatch.decide("Guntersville|AL", GEOM, UNTIL, stac([("2026-10-13", 12.0), ("2026-10-12", 12.0)]), published("2026-10-07"), att)
    assert d["work"] is True and d["newestPass"] == "2026-10-13"


def test_geometry_collections_and_multipolygons():
    mp = {"type": "MultiPolygon", "coordinates": [GEOM["coordinates"], [[[-90, 40], [-89, 40], [-89, 41], [-90, 41], [-90, 40]]]]}
    assert dispatch.bbox_of(mp) == [-90, 34.3, -85.6, 41]
    gc = {"type": "GeometryCollection", "geometries": [GEOM, mp]}
    assert dispatch.bbox_of(gc) == [-90, 34.3, -85.6, 41]


def test_unpublished_lake_with_a_pass_is_work():
    d = dispatch.decide("New|XX", GEOM, UNTIL, stac([("2026-10-11", 20.0)]), published(None))
    assert d["work"] is True and d["why"] == "nothing published yet"


def test_discover_isolates_errors():
    def post(url, body):
        raise RuntimeError("stac down")
    r = dispatch.discover({"A|XX": GEOM, "B|XX": GEOM}, UNTIL, workers=2, post=post, get=published(None))
    assert set(r["errors"]) == {"A|XX", "B|XX"} and r["decisions"] == {}


def test_task_count_scales_with_work():
    assert dispatch.task_count(1) == 1 and dispatch.task_count(12) == 1 and dispatch.task_count(13) == 2
    assert dispatch.task_count(500) == dispatch.MAX_TASKS


def test_dry_run_never_starts_the_heavy_job(monkeypatch, capsys):
    monkeypatch.setattr(dispatch, "load_polygons", lambda path=None: {"A|XX": GEOM})
    monkeypatch.setattr(dispatch, "_post", stac([("2026-10-12", 1.0)]))
    monkeypatch.setattr(dispatch, "_get_json", published(None))
    started = []
    monkeypatch.setattr(dispatch, "run_job", lambda *a, **k: started.append((a, k)) or {"metadata": {"name": "x"}})
    assert dispatch.main(["--dry-run", "--until", "2026-10-13T08:00:00", "--no-summary"]) == 0
    assert started == []
    out = capsys.readouterr().out
    assert "work set: A|XX" in out and '"workCount": 1' in out


def test_live_run_starts_the_heavy_job_for_the_work_set_only(monkeypatch):
    monkeypatch.setattr(dispatch, "load_polygons", lambda path=None: {"A|XX": GEOM, "B|XX": GEOM, "C|XX": GEOM})
    monkeypatch.setattr(dispatch, "_post", stac([("2026-10-12", 1.0)]))
    monkeypatch.setattr(dispatch, "_get_json", lambda url: {"summary": {"date": "2026-10-12"}} if "B_XX" in url else None)
    started = []
    monkeypatch.setattr(dispatch, "run_job", lambda tokens, job, args=None, task_count=None: started.append((job, args, task_count)) or {"metadata": {"name": "ex-1"}})
    monkeypatch.setattr(dispatch, "TokenProvider", lambda: None)
    puts = []
    monkeypatch.setattr(dispatch, "_put_json", lambda name, obj: puts.append((name, obj)))
    assert dispatch.main(["--until", "2026-10-13T08:00:00"]) == 0
    assert started == [("lake-surface-daily", ["--lakes", "A|XX,C|XX"], 1)]
    ledger = dict(puts)["dispatch/attempted.json"]
    assert set(ledger) == {"A|XX", "C|XX"} and ledger["A|XX"]["pass"] == "2026-10-12"


def test_no_work_starts_nothing(monkeypatch):
    monkeypatch.setattr(dispatch, "load_polygons", lambda path=None: {"A|XX": GEOM})
    monkeypatch.setattr(dispatch, "_post", stac([("2026-10-12", 1.0)]))
    monkeypatch.setattr(dispatch, "_get_json", published("2026-10-12"))
    started = []
    monkeypatch.setattr(dispatch, "run_job", lambda *a, **k: started.append(1))
    assert dispatch.main(["--until", "2026-10-13T08:00:00", "--no-summary"]) == 0 and started == []
