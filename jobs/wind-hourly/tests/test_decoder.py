"""Decoder traps from Stage 1 are hard tests: a decoding error silently puts the wrong wind on
the wrong bank."""
import json, math, os
from datetime import datetime, timedelta, timezone
import eccodes, numpy as np, pytest
from sector_wind import grib

def _synthetic(nx, ny, values, alt):
    gid = eccodes.codes_grib_new_from_samples("GRIB2")
    eccodes.codes_set(gid, "Ni", nx); eccodes.codes_set(gid, "Nj", ny)
    eccodes.codes_set(gid, "latitudeOfFirstGridPointInDegrees", 30.0); eccodes.codes_set(gid, "latitudeOfLastGridPointInDegrees", 30.0 + ny - 1)
    eccodes.codes_set(gid, "longitudeOfFirstGridPointInDegrees", 260.0); eccodes.codes_set(gid, "longitudeOfLastGridPointInDegrees", 260.0 + nx - 1)
    eccodes.codes_set(gid, "iDirectionIncrementInDegrees", 1.0); eccodes.codes_set(gid, "jDirectionIncrementInDegrees", 1.0)
    eccodes.codes_set(gid, "jScansPositively", 1)
    eccodes.codes_set(gid, "alternativeRowScanning", 1 if alt else 0)
    eccodes.codes_set_values(gid, np.asarray(values, dtype=float))
    msg = eccodes.codes_get_message(gid); eccodes.codes_release(gid)
    return msg

def test_alternative_row_scanning_is_reordered():
    nx, ny = 4, 3
    truth = np.arange(nx * ny, dtype=float).reshape(ny, nx)   # value = row*4 + col
    stored = truth.copy(); stored[1::2] = stored[1::2, ::-1]  # boustrophedon on disk
    f = grib.decode(_synthetic(nx, ny, stored.ravel(), alt=True))
    assert f.alt_rows_fixed
    np.testing.assert_allclose(f.values, truth.ravel())
    lat, lon = grib.grid(f.grid_key)
    k = int(np.where((np.isclose(lat, 31.0)) & (np.isclose(lon, -99.0)))[0][0])  # row 1, col 1
    assert f.values[k] == truth[1, 1]

def test_plain_scanning_untouched():
    nx, ny = 4, 3
    v = np.arange(12, dtype=float)
    f = grib.decode(_synthetic(nx, ny, v, alt=False))
    assert not f.alt_rows_fixed
    np.testing.assert_allclose(f.values, v)

def test_row_scramble_selfcheck_catches_unfixed_rows():
    nx, ny = 40, 30
    yy, xx = np.mgrid[0:ny, 0:nx]
    smooth = (np.sin(xx / 7.0) + np.cos(yy / 5.0)).ravel()
    cells = np.arange(nx * ny)
    assert grib.row_scramble_ratio(smooth, cells, nx) < 3.0
    bad = smooth.reshape(ny, nx).copy(); bad[1::2] = bad[1::2, ::-1]
    assert grib.row_scramble_ratio(bad.ravel(), cells, nx) > 3.0

def test_selfcheck_does_not_fail_a_calm_quantised_field():
    nx, ny = 30, 30
    calm = np.zeros(nx * ny); calm[::97] = 0.1          # nearly all zero, a few quantised blips
    assert grib.row_scramble_ratio(calm, np.arange(nx * ny), nx) < 3.0

def test_hrrr_rotation_geometry():
    lon = np.array([-97.5, -86.27])
    u = np.array([1.0, 1.0]); v = np.array([0.0, 0.0])
    ue, ve = grib.rotate_to_earth(u, v, lon, -97.5, 38.5)
    assert ue[0] == pytest.approx(1.0) and ve[0] == pytest.approx(0.0)        # on the central meridian
    a = math.radians(math.sin(math.radians(38.5)) * (-86.27 + 97.5))           # ~6.99 deg at Guntersville
    assert math.degrees(a) == pytest.approx(6.99, abs=0.02)
    assert ue[1] == pytest.approx(math.cos(a)) and ve[1] == pytest.approx(-math.sin(a))
    assert np.hypot(ue, ve) == pytest.approx(np.hypot(u, v))                    # rotation keeps speed

def test_uv_direction_convention():
    spd, d = grib.speed_dir_from_uv(np.array([5.0, 0.0, -3.0]), np.array([0.0, -4.0, 0.0]))
    # air moving toward east = wind FROM west (270); toward south = FROM north (0); toward west = FROM east (90)
    np.testing.assert_allclose(d, [270.0, 0.0, 90.0])
    u, v = grib.uv_from_speed_dir(np.array([5.0]), np.array([270.0]))
    assert u[0] == pytest.approx(5.0) and v[0] == pytest.approx(0.0, abs=1e-9)

GOLD = json.load(open(os.path.join(os.path.dirname(__file__), "fixtures", "golden_stage1.json")))

@pytest.mark.network
@pytest.mark.parametrize("cell", GOLD["cells"], ids=lambda c: f"{c['model']}-{c['station']}-{c['init']}")
def test_golden_cells_match_independent_reference(cell):
    init = datetime.strptime(cell["init"], "%Y%m%d%H").replace(tzinfo=timezone.utc)
    if cell["model"] == "nbm":
        from sector_wind.ingest import NBM_CORE
        url = NBM_CORE.format(d=f"{init:%Y%m%d}", h=init.hour, f=cell["lead"])
        ent = grib.read_idx(url); step = f"{cell['lead']} hour fcst"
        s = grib.decode(grib.fetch(url, (lambda e: (e.start, e.end))(grib.find(ent, "WIND", "10 m above ground", "", step))))
        d = grib.decode(grib.fetch(url, (lambda e: (e.start, e.end))(grib.find(ent, "WDIR", "10 m above ground", "", step))))
        lat, lon = grib.grid(s.grid_key)
        k = int(np.argmin((lat - cell["grid_lat"]) ** 2 + (lon - cell["grid_lon"]) ** 2))
        spd, dirn = s.values[k], d.values[k]
    else:
        url = f"https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.{init:%Y%m%d}/conus/hrrr.t{init:%H}z.wrfsfcf{cell['lead']:02d}.grib2"
        ent = grib.read_idx(url)
        lt = "anl" if cell["lead"] == 0 else f"{cell['lead']} hour fcst"
        fu = grib.decode(grib.fetch(url, (lambda e: (e.start, e.end))(grib.find(ent, "UGRD", "10 m above ground", "", lt))))
        fv = grib.decode(grib.fetch(url, (lambda e: (e.start, e.end))(grib.find(ent, "VGRD", "10 m above ground", "", lt))))
        lat, lon = grib.grid(fu.grid_key)
        k = int(np.argmin((lat - cell["grid_lat"]) ** 2 + (lon - cell["grid_lon"]) ** 2))
        u, v = np.array([fu.values[k]]), np.array([fv.values[k]])
        assert fu.uv_relative_to_grid
        u, v = grib.rotate_to_earth(u, v, np.array([lon[k]]), fu.lov_deg, fu.latin1_deg)
        sp, dd = grib.speed_dir_from_uv(u, v); spd, dirn = sp[0], dd[0]
    ref = cell["openMeteo"]
    assert spd == pytest.approx(ref["speedMS"], abs=0.15)
    assert abs((dirn - ref["dirFromDeg"] + 180) % 360 - 180) <= 5.0
