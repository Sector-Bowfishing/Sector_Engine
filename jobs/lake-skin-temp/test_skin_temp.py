"""Offline tests for skin_temp.py: synthetic rasters only, no network, no h5py."""
import datetime as dt
import json
import os

import numpy as np
import pytest

import skin_temp as S


def square(lat0, lon0, half_deg):
    ring = np.array([[lon0 - half_deg, lat0 - half_deg], [lon0 + half_deg, lat0 - half_deg],
                     [lon0 + half_deg, lat0 + half_deg], [lon0 - half_deg, lat0 + half_deg],
                     [lon0 - half_deg, lat0 - half_deg]])
    return [[ring]]


def test_grid_round_trip_lands_in_the_same_cell():
    rng = np.random.default_rng(1)
    lat = rng.uniform(18, 70, 2000)
    lon = rng.uniform(-170, -60, 2000)
    h, v, r, c = S.latlon_to_grid(lat, lon)
    lat_c, lon_c = S.grid_to_latlon(h, v, r, c)
    h2, v2, r2, c2 = S.latlon_to_grid(lat_c, lon_c)
    assert (h == h2).all() and (v == v2).all() and (r == r2).all() and (c == c2).all()
    assert ((r >= 0) & (r < 1200) & (c >= 0) & (c < 1200)).all()


def test_known_tiles():
    h, v, _, _ = S.latlon_to_grid(34.4, -86.2)  # Guntersville, AL
    assert S.tile_id(int(h), int(v)) == "h10v05"
    h, v, _, _ = S.latlon_to_grid(39.1, -120.0)  # Lake Tahoe
    assert S.tile_id(int(h), int(v)) == "h08v05"


def test_polygon_with_hole():
    outer = np.array([[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]], float)
    hole = np.array([[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]], float)
    lon = np.array([1.0, 5.0, 11.0])
    lat = np.array([1.0, 5.0, 5.0])
    assert S.polygons_contain([[outer, hole]], lon, lat).tolist() == [True, False, False]


def test_geometry_collection_and_multipolygon_parse(tmp_path):
    ring = [[-86.3, 34.3], [-86.1, 34.3], [-86.1, 34.5], [-86.3, 34.5], [-86.3, 34.3]]
    fc = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "properties": {"id": "A|AL"}, "geometry": {"type": "Polygon", "coordinates": [ring]}},
        {"type": "Feature", "properties": {"id": "B|AL"}, "geometry": {"type": "MultiPolygon", "coordinates": [[ring], [ring]]}},
        {"type": "Feature", "properties": {"id": "C|ND"}, "geometry": {"type": "GeometryCollection", "geometries": [
            {"type": "Polygon", "coordinates": [ring]}, {"type": "LineString", "coordinates": ring}]}},
    ]}
    p = tmp_path / "p.geojson"
    p.write_text(json.dumps(fc))
    polys = S.load_polygons(str(p))
    assert sorted(polys) == ["A|AL", "B|AL", "C|ND"]
    assert len(polys["B|AL"]) == 2 and len(polys["C|ND"]) == 1


def test_committed_outlines_load():
    polys = S.load_polygons(only={"Guntersville|AL", "Devils Lake|ND"})
    assert set(polys) == {"Guntersville|AL", "Devils Lake|ND"}


def _tiles_for(windows, lst_water=290.0, lst_land=300.0, qa_fill=S.QA_GOOD):
    tiles = {}
    for w in windows:
        lst = np.full((1200, 1200), lst_land)
        qc = np.full((1200, 1200), qa_fill, dtype=np.int64)
        vt = np.full((1200, 1200), 1.5)
        sl = (slice(w["r0"], w["r1"] + 1), slice(w["c0"], w["c1"] + 1))
        sub = lst[sl]
        sub[w["water"]] = lst_water
        tiles[w["tile"]] = {"lstK": lst, "qc": qc, "viewTimeH": vt}
    return tiles


def test_pure_water_reading_ignores_land_and_converts_units():
    polys = square(34.4, -86.2, 0.08)  # ~15 km square
    ws = S.lake_windows(polys)
    assert ws and sum(int(w["water"].sum()) for w in ws) > 50
    # the pure-water mask never includes a cell whose centre is outside
    for w in ws:
        assert int(w["water"].sum()) < w["insideCells"]
    rec = S.extract_lake(ws, _tiles_for(ws))
    assert rec["status"] == "OK"
    assert rec["skinTempK"] == pytest.approx(290.0)
    assert rec["skinTempF"] == pytest.approx(62.3, abs=0.05)
    assert rec["goodFraction"] == 1.0 and rec["possibleIce"] is False
    assert rec["viewTimeLocalSolarH"] == pytest.approx(1.5)


def test_cloud_buffer_drops_cells_next_to_cloud():
    polys = square(34.4, -86.2, 0.08)
    ws = S.lake_windows(polys)
    tiles = _tiles_for(ws)
    w = ws[0]
    deep = S._erode(w["water"], 2)  # a water cell whose whole 5x5 neighbourhood is water
    rows, cols = np.nonzero(deep)
    assert len(rows)
    r, c = w["r0"] + rows[0], w["c0"] + cols[0]
    tiles[w["tile"]]["qc"][r, c] = S.QA_CLOUD
    full = S.extract_lake(ws, _tiles_for(ws), cloud_buffer_px=2)
    clouded = S.extract_lake(ws, tiles, cloud_buffer_px=2)
    # the cloudy cell and its 5x5 neighbourhood are gone
    assert full["goodCells"] - clouded["goodCells"] == 25
    no_buffer = S.extract_lake(ws, tiles, cloud_buffer_px=0)
    assert full["goodCells"] - no_buffer["goodCells"] == 1


def test_bad_quality_and_sparse_and_missing_tile():
    polys = square(34.4, -86.2, 0.08)
    ws = S.lake_windows(polys)
    assert S.extract_lake(ws, _tiles_for(ws, qa_fill=S.QA_OTHER))["status"] == "CLOUDY_OR_SPARSE"
    assert S.extract_lake(ws, _tiles_for(ws, qa_fill=S.QA_CLOUD))["status"] == "CLOUDY_OR_SPARSE"
    assert S.extract_lake(ws, {})["status"] == "NO_TILE"
    tiny = S.lake_windows(square(34.4, -86.2, 0.004))  # under 1 km: no pure-water cell
    assert tiny == []


def test_missing_lst_counts_as_no_reading():
    polys = square(34.4, -86.2, 0.08)
    ws = S.lake_windows(polys)
    tiles = _tiles_for(ws)
    for t in tiles.values():
        t["lstK"][:] = np.nan
    assert S.extract_lake(ws, tiles)["status"] == "CLOUDY_OR_SPARSE"


def test_ice_flag():
    ws = S.lake_windows(square(46.0, -94.0, 0.08))
    assert S.extract_lake(ws, _tiles_for(ws, lst_water=268.0))["possibleIce"] is True


def test_qa_bits():
    qc = np.array([0b0, 0b1, 0b10, 0b11, 0b11100, 0b11110, 0b1000])
    assert S.qa_mandatory(qc).tolist() == [0, 1, 2, 3, 0, 2, 0]
    assert S.qa_cloud_flag(qc).tolist() == [0, 0, 0, 0, 1, 1, 0]
    # good = mandatory 00 AND cloud flag 00; bits 2-3 / 6+ don't matter
    assert S.qa_good(qc).tolist() == [True, False, False, False, False, False, True]
    assert S.qa_cloudy(qc).tolist() == [False, False, True, True, True, True, False]


def test_cloud_flag_alone_excludes_and_buffers():
    ws = S.lake_windows(square(34.4, -86.2, 0.08))
    assert S.extract_lake(ws, _tiles_for(ws, qa_fill=0b10000))["status"] == "CLOUDY_OR_SPARSE"


def test_granule_tile_name():
    assert S.granule_tile("VJ121A1N.A2026323.h10v05.002.2026325123456.h5") == "h10v05"
    assert S.granule_tile("no-tile-here.h5") is None


def test_token_only_goes_to_earthdata_https_hosts():
    assert S._token_allowed("https://data.lpdaac.earthdatacloud.nasa.gov/x.h5")
    assert S._token_allowed("https://urs.earthdata.nasa.gov/oauth")
    assert not S._token_allowed("http://data.lpdaac.earthdatacloud.nasa.gov/x.h5")
    assert not S._token_allowed("https://lp-prod-protected.s3.us-west-2.amazonaws.com/x.h5?X-Amz-Signature=1")
    assert not S._token_allowed("https://earthdata.nasa.gov.evil.example/x")


def _cmr_body(names):
    return json.dumps({"feed": {"entry": [
        {"producer_granule_id": n, "links": [
            {"href": f"https://data.lpdaac.earthdatacloud.nasa.gov/lp-prod-protected/VJ121A1N.002/{n}"},
            {"href": "https://data.lpdaac.earthdatacloud.nasa.gov/s3credentials"},
            {"href": f"s3://lp-prod-protected/{n}"}]} for n in names]}}).encode()


def test_cmr_filters_to_needed_tiles_and_https_files():
    names = ["VJ121A1N.A2026323.h10v05.002.1.h5", "VJ121A1N.A2026323.h20v05.002.1.h5",
             "VJ121A1N.A2026322.h10v05.002.1.h5"]   # the day before: CMR's temporal window can overlap
    seen = {}

    def fetch(url, token, dest=None):
        seen["url"], seen["token"] = url, token
        return _cmr_body(names)

    out = S.cmr_granules("VJ121A1N", dt.date(2026, 11, 19), {"h10v05"}, fetch=fetch)   # 2026-11-19 = day 323
    assert [g["tile"] for g in out] == ["h10v05"]
    assert out[0]["url"].startswith("https://") and out[0]["url"].endswith(".h5")
    assert seen["token"] is None  # CMR search is public: never send the token there
    assert "short_name=VJ121A1N" in seen["url"] and "version=002" in seen["url"]


def test_run_day_end_to_end_with_fakes(tmp_path):
    polys = {"Square|AL": square(34.4, -86.2, 0.08)}
    lw = {k: S.lake_windows(v) for k, v in polys.items()}
    tile = lw["Square|AL"][0]["tile"]
    name = f"VJ121A1N.A2026323.{tile}.002.1.h5"
    downloads = []

    def fetch(url, token, dest=None):
        if dest is None:
            return _cmr_body([name])
        downloads.append((url, token))
        open(dest, "wb").write(b"x")
        return None

    def reader(path):
        return _tiles_for(lw["Square|AL"])[tile]

    res = S.run_day(dt.date(2026, 11, 19), ["VJ121A1N"], lw, str(tmp_path), "tok", 2, 3, keep=False,
                    search_only=False, fetch=fetch, reader=reader)
    assert len(downloads) == 1 and downloads[0][1] == "tok"
    assert os.listdir(tmp_path) == []  # download deleted after extraction
    (r,) = res["readings"]
    assert r["status"] == "OK" and r["lakeId"] == "Square|AL" and r["product"] == "VJ121A1N"
    assert r["skinTempK"] == pytest.approx(290.0)


def test_one_bad_tile_does_not_sink_the_run(tmp_path):
    polys = {"Square|AL": square(34.4, -86.2, 0.08)}
    lw = {k: S.lake_windows(v) for k, v in polys.items()}
    tile = lw["Square|AL"][0]["tile"]

    def fetch(url, token, dest=None):
        if dest is None:
            return _cmr_body([f"VJ121A1N.A2026323.{tile}.002.1.h5"])
        raise RuntimeError("download failed from host")

    res = S.run_day(dt.date(2026, 11, 19), ["VJ121A1N"], lw, str(tmp_path), "tok", 2, 3, False, False, fetch=fetch)
    info = res["products"]["VJ121A1N"]
    assert info["failedTiles"] == 1 and info["tilesLoaded"] == 0 and info["complete"] is False
    assert res["readings"] == []


def test_main_refuses_without_token_and_never_echoes_it(monkeypatch, tmp_path, capsys):
    for k in ("EARTHDATA_TOKEN", "EARTHDATA_USERNAME", "EARTHDATA_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    rc = S.main(["--out", str(tmp_path / "o"), "--archive", str(tmp_path / "a"), "--cache", str(tmp_path / "c")])
    assert rc == 2
    assert "no Earthdata credential" in capsys.readouterr().err


def test_http_get_error_message_never_contains_the_token(monkeypatch):
    secret = "SECRET-TOKEN-VALUE-123456"

    class Boom:
        def open(self, req, timeout=0):
            raise S.urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(S.urllib.request, "build_opener", lambda *a: Boom())
    with pytest.raises(RuntimeError) as e:
        S.http_get("https://data.lpdaac.earthdatacloud.nasa.gov/x.h5", secret, tries=2)
    assert secret not in str(e.value)


def test_partial_days_are_retried_complete_days_skipped(tmp_path):
    full = tmp_path / "full.json"
    part = tmp_path / "part.json"
    full.write_text(json.dumps({"complete": True}))
    part.write_text(json.dumps({"complete": False}))
    assert S._day_complete(str(full)) is True
    assert S._day_complete(str(part)) is False
    assert S._day_complete(str(tmp_path / "missing.json")) is False


def test_read_granule_hdf5_layout(tmp_path):
    h5py = pytest.importorskip("h5py")
    p = tmp_path / "VJ121A1N.A2026314.h10v05.002.1.h5"
    with h5py.File(p, "w") as f:
        g = f.create_group("HDFEOS/GRIDS/VIIRS_Grid_1km_2D/Data Fields")
        lst = np.zeros((4, 4), dtype=np.uint16)
        lst[1, 1] = 14500  # 290.00 K at scale 0.02
        lst[2, 2] = 7000   # below the valid floor (7500 = 150 K)
        d = g.create_dataset("LST_1KM", data=lst)
        d.attrs["scale_factor"] = np.array([0.02])
        d.attrs["add_offset"] = np.array([0.0])
        d.attrs["_FillValue"] = np.array([0], dtype=np.uint16)
        qc = np.full((4, 4), 0b10, dtype=np.uint16)
        qc[1, 1] = 0b11100  # mandatory QA 00 but cloud flag 01: not good
        qc[3, 3] = 0b01100  # mandatory QA 00, cloud flag 00, other bits set: good
        g.create_dataset("QC", data=qc)
        vt = np.full((4, 4), 255, dtype=np.uint8)
        vt[1, 1] = 15  # 1.5 h at scale 0.1
        v = g.create_dataset("View_Time", data=vt)
        v.attrs["scale_factor"] = np.array([0.1])
        v.attrs["_FillValue"] = np.array([255], dtype=np.uint8)
    t = S.read_granule(str(p))
    assert t["lstK"][1, 1] == pytest.approx(290.0) and np.isnan(t["lstK"][0, 0]) and np.isnan(t["lstK"][2, 2])
    good = S.qa_good(t["qc"])
    assert not good[1, 1] and good[3, 3] and not good[0, 0]
    assert t["viewTimeH"][1, 1] == pytest.approx(1.5) and np.isnan(t["viewTimeH"][0, 0])


# ---------------------------------------------------------------- Earthdata token acquisition
TODAY = dt.date(2026, 11, 20)
USER, PW = "angler-test", "PASSWORD-VALUE-987654"


def _fake_urs(tokens=None, created=None, log=None):
    def call(method, path, user, pw):
        assert (user, pw) == (USER, PW)
        (log if log is not None else []).append((method, path))
        if method == "GET":
            return tokens or []
        return created
    return call


def test_env_token_override_wins_and_makes_no_call():
    def call(*a):
        raise AssertionError("no Earthdata Login call when EARTHDATA_TOKEN is set")
    env = {"EARTHDATA_TOKEN": "OVERRIDE", "EARTHDATA_USERNAME": USER, "EARTHDATA_PASSWORD": PW}
    assert S.earthdata_token(env, TODAY, call=call) == "OVERRIDE"


def test_reuses_a_valid_token_and_ignores_expiring_ones():
    log = []
    tokens = [{"access_token": "OLD", "expiration_date": "11/21/2026"},   # expires tomorrow: too close
              {"access_token": "GOOD", "expiration_date": "01/10/2027"}]
    tok = S.earthdata_token({"EARTHDATA_USERNAME": USER, "EARTHDATA_PASSWORD": PW}, TODAY, call=_fake_urs(tokens, log=log))
    assert tok == "GOOD" and log == [("GET", "/api/users/tokens")]


def test_creates_a_token_when_none_or_all_expired():
    log = []
    tokens = [{"access_token": "DEAD", "expiration_date": "11/01/2026"}]
    tok = S.earthdata_token({"EARTHDATA_USERNAME": USER, "EARTHDATA_PASSWORD": PW}, TODAY,
                            call=_fake_urs(tokens, {"access_token": "NEW", "expiration_date": "01/19/2027"}, log))
    assert tok == "NEW" and log == [("GET", "/api/users/tokens"), ("POST", "/api/users/token")]
    log = []
    assert S.earthdata_token({"EARTHDATA_USERNAME": USER, "EARTHDATA_PASSWORD": PW}, TODAY,
                             call=_fake_urs([], {"access_token": "NEW2"}, log)) == "NEW2"


def test_no_credentials_returns_none_and_failed_create_raises():
    assert S.earthdata_token({}, TODAY) is None
    with pytest.raises(RuntimeError, match="no token"):
        S.earthdata_token({"EARTHDATA_USERNAME": USER, "EARTHDATA_PASSWORD": PW}, TODAY, call=_fake_urs([], {}))


def test_basic_auth_only_to_urs_over_https():
    assert S._basic_allowed("https://urs.earthdata.nasa.gov/api/users/tokens")
    assert not S._basic_allowed("http://urs.earthdata.nasa.gov/api/users/tokens")
    assert not S._basic_allowed("https://data.lpdaac.earthdatacloud.nasa.gov/x")
    assert not S._basic_allowed("https://urs.earthdata.nasa.gov.evil.example/api")


def test_urs_call_sends_basic_auth_to_urs_and_never_follows_redirects(monkeypatch):
    seen = []

    class Resp:
        def read(self):
            return b'[{"access_token": "T", "expiration_date": "01/01/2027"}]'

    class Opener:
        def open(self, req, timeout=0):
            seen.append((req.full_url, req.get_method(), req.unredirected_hdrs.get("Authorization", "")))
            return Resp()

    out = S._urs_call("GET", "/api/users/tokens", USER, PW, opener=Opener())
    assert out[0]["access_token"] == "T"
    (url, method, auth) = seen[0]
    assert url == "https://urs.earthdata.nasa.gov/api/users/tokens" and method == "GET" and auth.startswith("Basic ")

    class Redirecting:
        def open(self, req, timeout=0):
            raise S.urllib.error.HTTPError(req.full_url, 302, "Found", {"Location": "https://elsewhere.example/"}, None)

    with pytest.raises(RuntimeError) as e:
        S._urs_call("GET", "/api/users/tokens", USER, PW, opener=Redirecting())
    assert PW not in str(e.value) and USER not in str(e.value)


def test_main_never_prints_token_or_password(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    monkeypatch.setenv("EARTHDATA_USERNAME", USER)
    monkeypatch.setenv("EARTHDATA_PASSWORD", PW)
    monkeypatch.setattr(S, "_urs_call", _fake_urs([], {"access_token": "BEARER-SECRET-123456"}))
    monkeypatch.setattr(S, "run_day", lambda day, *a, **k: {"date": day.isoformat(), "products": {}, "readings": []})
    monkeypatch.setattr(S, "load_polygons", lambda *a, **k: {"Square|AL": square(34.4, -86.2, 0.08)})
    rc = S.main(["--out", str(tmp_path / "o"), "--archive", str(tmp_path / "a"), "--cache", str(tmp_path / "c"),
                 "--today", "2026-11-20", "--days-back", "1"])
    assert rc == 0
    cap = capsys.readouterr()
    blob = cap.out + cap.err + (tmp_path / "o" / "lake-skin-temp.json").read_text()
    for secret in ("BEARER-SECRET-123456", PW):
        assert secret not in blob


def test_main_reports_earthdata_failure_without_secrets(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    monkeypatch.setenv("EARTHDATA_USERNAME", USER)
    monkeypatch.setenv("EARTHDATA_PASSWORD", PW)

    def boom(*a):
        raise RuntimeError("Earthdata Login GET /api/users/tokens: HTTP 401")
    monkeypatch.setattr(S, "_urs_call", boom)
    rc = S.main(["--out", str(tmp_path / "o"), "--archive", str(tmp_path / "a"), "--cache", str(tmp_path / "c")])
    assert rc == 3
    assert PW not in capsys.readouterr().err


def test_granule_day():
    assert S.granule_day("VJ121A1N.A2026323.h10v05.002.1.h5") == dt.date(2026, 11, 19)
    assert S.granule_day("VJ121A1N.A2024366.h10v05.002.1.h5") == dt.date(2024, 12, 31)
    assert S.granule_day("nothing") is None


def _lw():
    return {"Square|AL": S.lake_windows(square(34.4, -86.2, 0.08))}


def test_search_failure_marks_product_incomplete_and_keeps_going(tmp_path):
    lw = _lw()
    tile = lw["Square|AL"][0]["tile"]
    calls = []

    def fetch(url, token, dest=None):
        if dest is None:
            calls.append(url)
            if "VNP21A1N" in url:
                raise RuntimeError("CMR 503")
            return _cmr_body([f"VJ121A1N.A2026323.{tile}.002.1.h5"])
        open(dest, "wb").write(b"x")

    res = S.run_day(dt.date(2026, 11, 19), ["VNP21A1N", "VJ121A1N"], lw, str(tmp_path), "tok", 2, 3, False, False,
                    fetch=fetch, reader=lambda p: _tiles_for(lw["Square|AL"])[tile])
    assert res["products"]["VNP21A1N"]["searchFailed"] is True and res["products"]["VNP21A1N"]["complete"] is False
    assert res["products"]["VJ121A1N"]["complete"] is True
    assert [r["product"] for r in res["readings"]] == ["VJ121A1N"]


def test_complete_products_are_skipped_on_rerun(tmp_path):
    lw = _lw()

    def fetch(url, token, dest=None):
        raise AssertionError("a complete product must not be searched or downloaded again")

    res = S.run_day(dt.date(2026, 11, 19), ["VJ121A1N"], lw, str(tmp_path), "tok", 2, 3, False, False,
                    fetch=fetch, skip={"VJ121A1N"})
    assert res["products"] == {} and res["readings"] == []
    assert S._complete_products({"products": {"A": {"complete": True}, "B": {"complete": False}}}) == {"A"}


def test_merge_keeps_the_better_partial_result():
    old = {"products": {"P": {"tilesLoaded": 10, "complete": False}, "Q": {"tilesLoaded": 17, "complete": True}},
           "readings": [{"lakeId": "A", "product": "P", "status": "OK"}, {"lakeId": "A", "product": "Q", "status": "OK"}]}
    worse = {"date": "2026-11-19", "products": {"P": {"tilesLoaded": 4, "complete": False}},
             "readings": [{"lakeId": "B", "product": "P", "status": "OK"}]}
    m = S.merge_day(old, worse)
    assert m["products"]["P"]["tilesLoaded"] == 10
    assert {(r["lakeId"], r["product"]) for r in m["readings"]} == {("A", "P"), ("A", "Q")}
    better = {"date": "2026-11-19", "products": {"P": {"tilesLoaded": 17, "complete": True}},
              "readings": [{"lakeId": "C", "product": "P", "status": "OK"}]}
    m = S.merge_day(old, better)
    assert m["products"]["P"]["complete"] is True and m["products"]["Q"]["complete"] is True
    assert {(r["lakeId"], r["product"]) for r in m["readings"]} == {("C", "P"), ("A", "Q")}
    assert S.merge_day(None, better)["products"] == better["products"]


def test_failed_download_leaves_no_part_file(tmp_path, monkeypatch):
    class Resp:
        def __init__(self):
            self.n = 0

        def read(self, k=-1):
            self.n += 1
            if self.n > 1:
                raise OSError("connection reset")
            return b"partial"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    class Opener:
        def open(self, req, timeout=0):
            return Resp()

    monkeypatch.setattr(S.urllib.request, "build_opener", lambda *a: Opener())
    monkeypatch.setattr(S.time, "sleep", lambda s: None)
    dest = tmp_path / "g.h5"
    with pytest.raises(RuntimeError):
        S.http_get("https://data.lpdaac.earthdatacloud.nasa.gov/g.h5", "tok", dest=str(dest), tries=2)
    assert os.listdir(tmp_path) == []


def test_backfill_range_and_archive_merge(tmp_path, monkeypatch):
    seen = []

    def fake_run_day(day, products, lw, cache, token, cb, mp, keep, so, skip=None, **k):
        seen.append((day, set(skip or ())))
        return {"date": day.isoformat(), "products": {"VJ121A1N": {"tilesLoaded": 1, "tilesNeeded": 1, "complete": True}},
                "readings": [{"lakeId": "Square|AL", "product": "VJ121A1N", "status": "OK"}]}

    monkeypatch.setenv("EARTHDATA_TOKEN", "tok")
    monkeypatch.setattr(S, "run_day", fake_run_day)
    monkeypatch.setattr(S, "load_polygons", lambda *a, **k: {"Square|AL": square(34.4, -86.2, 0.08)})
    args = ["--out", str(tmp_path / "o"), "--archive", str(tmp_path / "a"), "--cache", str(tmp_path / "c"),
            "--products", "VJ121A1N", "--start", "2018-01-30", "--end", "2018-02-01"]
    assert S.main(args) == 0
    assert [d for d, _ in seen] == [dt.date(2018, 1, 30), dt.date(2018, 1, 31), dt.date(2018, 2, 1)]
    doc = json.loads((tmp_path / "a" / "2018" / "2018-01-31.json").read_text())
    assert doc["complete"] is True and doc["readings"][0]["product"] == "VJ121A1N"
    seen.clear()
    assert S.main(args) == 0            # every day now complete: nothing re-run
    assert seen == []
    assert S.main(args[:-4] + ["--start", "2018-01-30"]) == 2   # --start without --end
