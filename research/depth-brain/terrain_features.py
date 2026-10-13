#!/usr/bin/env python3
"""Depth Brain / terrain: lake-level and segment-level features from the extended 3DEP shoreline profile (terrain_dem_profile.py npz).
Offsets (m): 5 10 20 30 45 60 80 100 150 200.  z = DEM elevation (m, NAVD88) at each offset outside the polygon edge.
Slope between offsets a,b = atan((z_b - z_a)/(b - a)).  Negative slopes (DEM beside the edge lower than at the edge) are a polygon-edge / lidar-water artefact."""
import numpy as np

OFFS = [5, 10, 20, 30, 45, 60, 80, 100, 150, 200]
IX = {o: i for i, o in enumerate(OFFS)}


def slope_deg(z, a, b, ix=None):
    ix = ix or IX
    return np.degrees(np.arctan((z[:, ix[b]] - z[:, ix[a]]) / (b - a)))


def _ix(d):
    return {int(o): i for i, o in enumerate(d["offs"])} if "offs" in d else IX


def clean(d):
    z = d["z"].copy()
    ok = np.isfinite(z).all(axis=1) & (z > -100).all(axis=1)
    return z, ok


def lake_features(d, area_km2=None):
    IX = _ix(d)
    z, ok = clean(d)
    z = z[ok]
    if len(z) < 50:
        return None
    perim_km = None
    f = {}
    f["n_pts"] = int(len(z)); f["frac_valid"] = float(ok.mean())
    s_in = slope_deg(z, 10, 60, IX); s_mid = slope_deg(z, 30, 100, IX); s_far = slope_deg(z, 60, 200, IX)
    f["slope_10_60_med"] = float(np.median(s_in)); f["slope_30_100_med"] = float(np.median(s_mid)); f["slope_60_200_med"] = float(np.median(s_far))
    f["frac_lt1"] = float((s_in < 1).mean()); f["frac_lt2"] = float((s_in < 2).mean()); f["frac_gt8"] = float((s_in >= 8).mean())
    f["rise_100_med_m"] = float(np.median(z[:, IX[100]] - z[:, IX[5]])); f["rise_200_med_m"] = float(np.median(z[:, IX[200]] - z[:, IX[5]]))
    f["frac_rise200_lt2m"] = float(((z[:, IX[200]] - z[:, IX[5]]) < 2).mean())
    f["frac_neg"] = float((s_in < 0).mean())
    tanb = np.tan(np.radians(np.clip(s_in, 0.2, 89)))
    f["run_per_ft_med"] = float(np.median(np.clip(1 / tanb, 0, 500)))          # horizontal ft per vertical ft (as in context_shore_dem.py)
    tanm = np.tan(np.radians(np.clip(s_mid, 0.2, 89)))
    f["run_per_ft_med_30_100"] = float(np.median(np.clip(1 / tanm, 0, 500)))
    # rise to 200 m over mean slope: robust overall gradient
    r200 = np.clip(z[:, IX[200]] - z[:, IX[5]], 0.05, None)
    f["run_per_ft_200"] = float(np.median(200 * 3.28084 / (r200 * 3.28084)))      # (200 m horizontal)/(rise) ratio, ft per ft
    return f


def segment_features(d, seg_len_m=500.0):
    IX = _ix(d)
    """Split the shoreline into arc-length segments of ~seg_len_m (per ring); return per-point segment id and per-segment medians."""
    z, ok = clean(d)
    ring, s = d["ring"], d["s"]
    seg = np.full(len(z), -1)
    nseg = 0
    for r in np.unique(ring):
        m = (ring == r) & ok
        if m.sum() == 0: continue
        k = np.floor(s[m] / seg_len_m).astype(int)
        u, inv = np.unique(k, return_inverse=True)
        seg[np.where(m)[0]] = nseg + inv; nseg += len(u)
    out = []
    for g in range(nseg):
        m = seg == g
        if m.sum() < 3: continue
        zz = z[m]
        row = dict(seg=g, n=int(m.sum()), x=float(np.mean(d["x"][m])), y=float(np.mean(d["y"][m])),
                   slope_10_60=float(np.median(slope_deg(zz, 10, 60, IX))), slope_30_100=float(np.median(slope_deg(zz, 30, 100, IX))), slope_60_200=float(np.median(slope_deg(zz, 60, 200, IX))),
                   slope_5_20=float(np.median(slope_deg(zz, 5, 20, IX))),
                   rise200=float(np.median(zz[:, IX[200]] - zz[:, IX[5]])), rise100=float(np.median(zz[:, IX[100]] - zz[:, IX[5]])))
        out.append(row)
    return out, seg


def geom_features(geom):
    """polygon geometry features (EPSG:4326 in); metres in a local azimuthal equal-area projection.
    area_km2, perim_km, frac_within_{50,100,200}m = share of surface within that distance of shore (inward buffer), frac_narrow_300m = share of area removed by
    an opening of 150 m (arms/coves narrower than 300 m), shape_idx = perimeter / (2 sqrt(pi A))."""
    import shapely
    from pyproj import Transformer
    c = geom.centroid
    prj = f"+proj=laea +lat_0={c.y} +lon_0={c.x} +datum=WGS84 +units=m"
    fw = Transformer.from_crs("EPSG:4326", prj, always_xy=True)
    g = shapely.transform(geom, lambda a: np.column_stack(fw.transform(a[:, 0], a[:, 1]))).buffer(0)
    gs = g.simplify(10)
    A = g.area; P = g.length
    f = dict(area_km2=A / 1e6, perim_km=P / 1e3, shape_idx=P / (2 * np.sqrt(np.pi * A)))
    for d in (50, 100, 200):
        f[f"frac_within_{d}m"] = float(1 - gs.buffer(-d, quad_segs=2).area / gs.area)
    op = gs.buffer(-150, quad_segs=2).buffer(150, quad_segs=2)
    f["frac_narrow_300m"] = float(1 - op.area / gs.area)
    return f
