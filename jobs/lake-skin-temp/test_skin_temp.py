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
        qa = np.full((1200, 1200), qa_fill, dtype=np.int64)
        vt = np.full((1200, 1200), 1.5)
        sl = (slice(w["r0"], w["r1"] + 1), slice(w["c0"], w["c1"] + 1))
        sub = lst[sl]
        sub[w["water"]] = lst_water
        tiles[w["tile"]] = {"lstK": lst, "qa": qa, "viewTimeH": vt}
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
    tiles[w["tile"]]["qa"][r, c] = S.QA_CLOUD
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


def test_qa_mandatory_bits():
    assert S.qa_mandatory(np.array([0b0, 0b1, 0b10, 0b11, 0b11100, 0b11110])).tolist() == [0, 1, 2, 3, 0, 2]


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
    names = ["VJ121A1N.A2026323.h10v05.002.1.h5", "VJ121A1N.A2026323.h20v05.002.1.h5"]
    seen = {}

    def fetch(url, token, dest=None):
        seen["url"], seen["token"] = url, token
        return _cmr_body(names)

    out = S.cmr_granules("VJ121A1N", dt.date(2026, 11, 19), {"h10v05"}, fetch=fetch)
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
    assert res["products"]["VJ121A1N"]["failedTiles"] == 1
    assert res["readings"] == []


def test_main_refuses_without_token_and_never_echoes_it(monkeypatch, tmp_path, capsys):
    monkeypatch.delenv("EARTHDATA_TOKEN", raising=False)
    rc = S.main(["--out", str(tmp_path / "o"), "--archive", str(tmp_path / "a"), "--cache", str(tmp_path / "c")])
    assert rc == 2
    assert "EARTHDATA_TOKEN is not set" in capsys.readouterr().err


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
        d = g.create_dataset("LST_1KM", data=lst)
        d.attrs["scale_factor"] = np.array([0.02])
        d.attrs["add_offset"] = np.array([0.0])
        d.attrs["_FillValue"] = np.array([0], dtype=np.uint16)
        qc = np.full((4, 4), 0b10, dtype=np.uint16)
        qc[1, 1] = 0b11100  # mandatory QA 00 with higher bits set
        g.create_dataset("QC", data=qc)
        vt = np.full((4, 4), 255, dtype=np.uint8)
        vt[1, 1] = 15  # 1.5 h at scale 0.1
        v = g.create_dataset("View_Time", data=vt)
        v.attrs["scale_factor"] = np.array([0.1])
        v.attrs["_FillValue"] = np.array([255], dtype=np.uint8)
    t = S.read_granule(str(p))
    assert t["lstK"][1, 1] == pytest.approx(290.0) and np.isnan(t["lstK"][0, 0])
    assert t["qa"][1, 1] == S.QA_GOOD and t["qa"][0, 0] == S.QA_CLOUD
    assert t["viewTimeH"][1, 1] == pytest.approx(1.5) and np.isnan(t["viewTimeH"][0, 0])
