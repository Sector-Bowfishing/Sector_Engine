"""Fleet sampler hardening: edge cells, missing/NaN/calm cells, points outside the domain, partial cycles, determinism."""
import json
import numpy as np
from sector_wind import fleet_sampling as FSM

NX, NY = 12, 10


def grid():
    lat = np.array([30 + r * 0.025 for r in range(NY) for c in range(NX)]); lon = np.array([-90 + c * 0.03 for r in range(NY) for c in range(NX)])
    return lat, lon


def fields(speed=4.0, d=270.0):
    return np.full(NX * NY, speed), np.full(NX * NY, d)


def test_interior_edge_and_outside_points():
    lat, lon = grid()
    idx = FSM.build_point_index(lat, lon, NX, {"interior|XX": (30.1, -89.9), "corner|XX": (30.0, -90.0), "far|XX": (36.0, -80.0), "justOutside|XX": (30.0, -90.2)})
    L = idx["lakes"]
    assert L["interior|XX"]["method"] == "bilinear" and len(L["interior|XX"]["cells"]) == 4
    assert L["corner|XX"]["cells"] and L["corner|XX"]["method"] in ("bilinear", "nearest")        # grid corner: still resolvable
    assert L["far|XX"]["method"] == "outside" and L["far|XX"]["cells"] == []                      # hundreds of km away: never the nearest far cell
    assert L["justOutside|XX"]["method"] == "outside"                                              # ~17 km west of the western edge
    sp, dr = fields()
    out = FSM.sample_lead(idx, sp, dr)
    assert out["far|XX"]["speedMS"] is None and out["far|XX"]["dirFromDeg"] is None             # unknown, not 0
    assert out["interior|XX"]["speedMS"] == 4.0 and out["interior|XX"]["dirFromDeg"] == 270


def test_missing_and_nan_cells_follow_the_production_fallback():
    lat, lon = grid()
    idx = FSM.build_point_index(lat, lon, NX, {"A|XX": (30.113, -89.904)})
    cells = idx["lakes"]["A|XX"]["cells"]; w = idx["lakes"]["A|XX"]["w"]
    sp, dr = fields(); sp = sp.copy(); sp[cells[0]] = np.nan
    one_missing = FSM.sample_lead(idx, sp, dr)["A|XX"]
    heavy = cells[int(np.argmax([x if not np.isnan(sp[c]) else -1 for c, x in zip(cells, w)]))]
    assert one_missing["speedMS"] == round(float(sp[heavy]), 2)                                       # heaviest valid cell, like interp.blend
    sp2 = sp.copy(); sp2[cells] = np.nan
    assert FSM.sample_lead(idx, sp2, dr)["A|XX"]["speedMS"] is None                               # all four missing: unknown
    dr2 = dr.copy(); dr2[cells] = np.nan
    r = FSM.sample_lead(idx, sp, dr2)["A|XX"]
    assert r["speedMS"] is not None and r["dirFromDeg"] is None                                    # speed known, direction unknown stays unknown


def test_calm_cells_have_no_direction_and_mixed_cells_use_only_moving_air():
    lat, lon = grid()
    idx = FSM.build_point_index(lat, lon, NX, {"A|XX": (30.113, -89.904)})
    cells = idx["lakes"]["A|XX"]["cells"]
    sp, dr = fields(0.3, 123.0)
    assert FSM.sample_lead(idx, sp, dr)["A|XX"]["dirFromDeg"] is None
    sp, dr = fields(4.0, 270.0); sp = sp.copy(); dr = dr.copy(); sp[cells[0]] = 0.2; dr[cells[0]] = 90.0       # one calm cell pointing the opposite way must not drag the direction
    assert FSM.sample_lead(idx, sp, dr)["A|XX"]["dirFromDeg"] == 270


def test_circular_direction_across_north():
    lat, lon = grid()
    idx = FSM.build_point_index(lat, lon, NX, {"A|XX": (30.113, -89.904)})
    cells = idx["lakes"]["A|XX"]["cells"]
    sp, dr = fields(5.0, 350.0); dr = dr.copy(); dr[cells[0]] = 10.0; dr[cells[1]] = 10.0
    d = FSM.sample_lead(idx, sp, dr)["A|XX"]["dirFromDeg"]
    assert d >= 340 or d <= 20                                                                      # never the arithmetic mean (180)


def test_partial_cycle_is_labelled_not_filled():
    lat, lon = grid()
    idx = FSM.build_point_index(lat, lon, NX, {"A|XX": (30.113, -89.904), "far|XX": (36.0, -80.0)})
    good = {"speed": fields(5.0)[0], "dir": fields(5.0)[1]}
    cyc = FSM.sample_cycle(idx, "2026-09-01T12:00:00Z", "2026-09-01T13:05:00Z", {1: good, 3: None, 6: {"speed": np.array([1.0, 2.0]), "dir": np.array([0.0, 0.0])}, 12: good})
    assert cyc["status"] == "partial" and cyc["missingLeads"] == [3, 6] and cyc["outsideDomain"] == ["far|XX"]
    assert cyc["lakes"]["A|XX"]["speedMS"] == [5.0, None, None, 5.0]                               # null where the GRIB message was missing/malformed
    assert cyc["lakes"]["far|XX"]["speedMS"] == [None, None, None, None]
    full = FSM.sample_cycle(idx, "x", "y", {1: good, 3: good})
    assert full["status"] == "complete" and full["missingLeads"] == []


def test_determinism_and_serialisation():
    lat, lon = grid()
    pts = {"A|XX": (30.113, -89.904), "B|XX": (30.15, -89.8)}
    a, b = FSM.build_point_index(lat, lon, NX, pts), FSM.build_point_index(lat, lon, NX, dict(reversed(list(pts.items()))))
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)                         # input order does not matter
    sp, dr = fields()
    c1 = FSM.sample_cycle(a, "i", "r", {1: {"speed": sp, "dir": dr}}); c2 = FSM.sample_cycle(b, "i", "r", {1: {"speed": sp, "dir": dr}})
    assert json.dumps(c1, sort_keys=True) == json.dumps(c2, sort_keys=True)
