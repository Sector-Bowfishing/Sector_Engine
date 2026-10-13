#!/usr/bin/env python3
"""Depth Brain / contour truth: contour lines -> depth-below-surface raster inside a fleet polygon, plus bowfishing metrics.

METHOD ('face interpolation', documented in DEPTH_BRAIN_CONTOUR_TRUTH_REPORT.md)
 1. Rasterise the polygon (EPSG:5070) at `cell` m; burn every contour line (all_touched) with its level index; the polygon edge is level 0.
 2. Label the water cells that are not on a line (4-connectivity) = 'faces'. Each face is bounded by contour levels; collect the set S_f of levels
    touching the face (non-water neighbours count as level 0).
 3. Face with >=2 levels: for each cell, a = nearest level of S_f, b = nearer of a's neighbours in S_f; depth = La + (Lb-La)*Da/(Da+Db)
    (distance-ratio interpolation between the two bracketing contours; exact bracket for the usual 2-level face).
 4. Face with one level L>0 (innermost ring or a shoal): look across the line at the neighbouring face; if the neighbour has a lower level m the
    face is deeper than L -> depth = L + (L-m)/2 (a constant; true depth unknown below the deepest contour); if a higher level -> L - (m-L)/2.
 5. Faces touching only level 0 (no contour inside the surveyed band) and unresolvable faces are 'unsurveyed' (NaN) and excluded from shares.
Shares are fractions of SURVEYED area; coverage = surveyed cells / polygon cells."""
import numpy as np
from scipy import ndimage
from rasterio.features import rasterize
from rasterio.transform import from_origin
import shapely

THRESH = (3.0, 6.0, 10.0)


def pick_cell(area_m2, bounds, lo=5.0, hi=30.0, maxcells=2.5e7):
    c = float(np.clip(np.sqrt(area_m2 / 1.0e6), lo, hi))
    w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
    while (w / c) * (h / c) > maxcells: c *= 1.2
    return c


def build_depth(poly, lines, cell):
    """poly: shapely (m), lines: list of (depth_ft, geom) in same CRS. returns dict(depth, water, transform, cell, stats)."""
    minx, miny, maxx, maxy = poly.bounds
    pad = 3 * cell
    W = int(np.ceil((maxx - minx + 2 * pad) / cell)); H = int(np.ceil((maxy - miny + 2 * pad) / cell))
    tr = from_origin(minx - pad, maxy + pad, cell, cell)
    water = rasterize([(poly, 1)], out_shape=(H, W), transform=tr, fill=0, dtype="uint8").astype(bool)
    levels = sorted({0.0} | {float(d) for d, _ in lines if d is not None and np.isfinite(d)})
    lv = np.array(levels); K = len(lv); kid = {v: i for i, v in enumerate(levels)}
    lab = np.full((H, W), -1, np.int32)
    shapes = [(g, kid[float(d)]) for d, g in sorted(lines, key=lambda t: -t[0]) if g is not None and not g.is_empty]
    if shapes:
        lab = rasterize(shapes, out_shape=(H, W), transform=tr, fill=-1, dtype="int32", all_touched=True)
    lab[~water] = -1
    free = water & (lab < 0)
    face, nf = ndimage.label(free)                     # 4-connectivity
    depth = np.full((H, W), np.nan, np.float32)
    online = water & (lab >= 0)
    depth[online] = lv[lab[online]]
    if nf == 0:
        return dict(depth=depth, water=water, tr=tr, cell=cell, levels=lv, nfaces=0)
    # face <-> level adjacency
    pairs = []
    P = np.pad(lab, 1, constant_values=-1); Wp = np.pad(water, 1, constant_values=False); F = np.pad(face, 1, constant_values=0)
    ys, xs = np.nonzero(free)
    fid = face[ys, xs]
    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        nl = P[ys + 1 + dy, xs + 1 + dx]; nw = Wp[ys + 1 + dy, xs + 1 + dx]
        lvl = np.where(nl >= 0, nl, np.where(~nw, kid[0.0], -1))
        ok = lvl >= 0
        pairs.append(fid[ok].astype(np.int64) * K + lvl[ok])
    pairs = np.unique(np.concatenate(pairs)) if pairs else np.array([], np.int64)
    pf, pk = pairs // K, pairs % K
    M = np.zeros((nf + 1, K), bool); M[pf, pk] = True
    nlev = M.sum(1)
    # neighbour faces across a line (for single-level faces)
    single = np.nonzero((nlev == 1) & (np.arange(nf + 1) > 0))[0]
    prevK = np.full((nf + 1, K), -1, np.int32); nextK = np.full((nf + 1, K), -1, np.int32)
    multi = np.nonzero(nlev >= 2)[0]
    for f in multi:
        ks = np.nonzero(M[f])[0]
        prevK[f, ks[1:]] = ks[:-1]; nextK[f, ks[:-1]] = ks[1:]
    # single-level resolution
    sdepth = {}
    if len(single):
        sset = np.zeros(nf + 1, bool); sset[single] = True
        nb = {}
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ln = P[ys + 1 + dy, xs + 1 + dx]
            # 2-step neighbour (guard against pad overflow)
            yy = np.clip(ys + 1 + 2 * dy, 0, F.shape[0] - 1); xx = np.clip(xs + 1 + 2 * dx, 0, F.shape[1] - 1)
            beyond = F[yy, xx]
            ok = (ln >= 0) & (beyond > 0) & (beyond != fid) & sset[fid]
            for a, b in zip(fid[ok], beyond[ok]): nb.setdefault(int(a), set()).add(int(b))
        for f in single:
            L = int(np.nonzero(M[f])[0][0]); Lv = lv[L]
            lower = []; higher = []
            for g in nb.get(int(f), ()):
                for m in np.nonzero(M[g])[0]:
                    if m == L: continue
                    (lower if lv[m] < Lv else higher).append(lv[m])
            if Lv > 0 and lower and not higher: sdepth[int(f)] = Lv + (Lv - max(lower)) / 2.0
            elif Lv > 0 and higher and not lower: sdepth[int(f)] = max(Lv - (min(higher) - Lv) / 2.0, 0.1)
    for f, d in sdepth.items(): depth[face == f] = d
    # multi-level faces
    cm = np.isin(face, multi) & free
    cy, cx = np.nonzero(cm)
    if len(cy):
        cf = face[cy, cx]
        bestD = np.full(len(cy), np.inf, np.float32); bestK = np.full(len(cy), -1, np.int32)
        used = np.nonzero(M[multi].any(0))[0]
        def dmap(k):
            if k == kid[0.0]:   # shoreline = non-water cells + any level-0 lines
                return ndimage.distance_transform_edt(water & (lab != k)) * cell
            return ndimage.distance_transform_edt(lab != k) * cell
        for k in used:
            Dk = dmap(k)[cy, cx]
            ok = M[cf, k] & (Dk < bestD)
            bestD[ok] = Dk[ok]; bestK[ok] = k
        Dp = np.full(len(cy), np.inf, np.float32); Dn = np.full(len(cy), np.inf, np.float32)
        pk_cell = prevK[cf, bestK]; nk_cell = nextK[cf, bestK]
        for k in used:
            need = (pk_cell == k) | (nk_cell == k)
            if not need.any(): continue
            Dk = dmap(k)[cy, cx]
            m = pk_cell == k; Dp[m] = Dk[m]
            m = nk_cell == k; Dn[m] = Dk[m]
        useprev = Dp < Dn
        Db = np.where(useprev, Dp, Dn); kb = np.where(useprev, pk_cell, nk_cell)
        La = lv[bestK]; Lb = np.where(kb >= 0, lv[np.clip(kb, 0, K - 1)], np.nan)
        denom = bestD + Db
        w = np.where(denom > 0, bestD / np.where(denom > 0, denom, 1), 0.0)
        d = La + (Lb - La) * w
        d = np.where(np.isfinite(d), d, np.nan)
        depth[cy, cx] = d
    depth[~water] = np.nan
    return dict(depth=depth, water=water, tr=tr, cell=cell, levels=lv, nfaces=int(nf), n_single=int(len(single)), n_single_resolved=len(sdepth), n_multi=int(len(multi)))


def edt_open(mask, r_cells):
    """binary opening of mask with a disk of radius r_cells, via EDT (erode then dilate)."""
    if r_cells < 1: return mask.copy()
    er = ndimage.distance_transform_edt(mask) >= r_cells
    return ndimage.distance_transform_edt(~er) <= r_cells


def metrics(g, poly_area_m2=None):
    depth, water, cell = g["depth"], g["water"], g["cell"]
    nw = int(water.sum()); sv = np.isfinite(depth); ns = int(sv.sum())
    out = dict(cell_m=cell, cov_raster=ns / nw if nw else np.nan, n_water_cells=nw)
    if ns == 0: return out
    d = depth[sv]
    out["shr_0_3"] = float((d < 3).mean()); out["shr_3_6"] = float(((d >= 3) & (d < 6)).mean())
    out["shr_6_10"] = float(((d >= 6) & (d < 10)).mean()); out["shr_gt10"] = float((d >= 10).mean())
    out["mean_depth_ft"] = float(d.mean()); out["p95_depth_ft"] = float(np.percentile(d, 95))
    lv = g["levels"]; out["max_contour_ft"] = float(lv.max())
    # shoreline distances
    er = ndimage.binary_erosion(water, border_value=0)
    shore = water & ~er & sv
    out["n_shore_cells"] = int(shore.sum())
    for T, tag in ((3.0, "3"), (6.0, "6")):
        deep = sv & (depth >= T)
        if shore.sum() == 0: continue
        if deep.any():
            dist = ndimage.distance_transform_edt(~deep) * cell
            ds = dist[shore]
            out[f"shore_to_{tag}ft_med_m"] = float(np.median(ds)); out[f"shore_to_{tag}ft_p25_m"] = float(np.percentile(ds, 25)); out[f"shore_to_{tag}ft_p75_m"] = float(np.percentile(ds, 75))
            out[f"shore_to_{tag}ft_p90_m"] = float(np.percentile(ds, 90))
            if tag == "6": out["steep_share_6ft_30m"] = float((ds <= 30).mean()); out["shore_6ft_gt100m_share"] = float((ds > 100).mean())
        else:
            out[f"shore_to_{tag}ft_med_m"] = np.nan; out[f"n_no_cells_ge{tag}ft"] = 1
    # flats: contiguous depth<6 ft zones at least 100 / 200 m wide (inscribed-disk test), patches >= 1 ha
    shal = sv & (depth < 6)
    for wm in (100, 200):
        r = (wm / 2.0) / cell
        key = f"flat{wm}"
        if r < 0.9:
            out[f"{key}_n"] = np.nan; out[f"{key}_ha"] = np.nan; continue
        op = edt_open(shal, r)
        lab, n = ndimage.label(op, structure=np.ones((3, 3)))
        if n:
            ar = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1)) * cell * cell
            keep = ar >= 10000
            out[f"{key}_n"] = int(keep.sum()); out[f"{key}_ha"] = float(ar[keep].sum() / 1e4); out[f"{key}_max_ha"] = float(ar.max() / 1e4) if keep.any() else 0.0
            out[f"{key}_share_of_surveyed"] = float(ar[keep].sum() / (ns * cell * cell))
        else:
            out[f"{key}_n"] = 0; out[f"{key}_ha"] = 0.0; out[f"{key}_max_ha"] = 0.0; out[f"{key}_share_of_surveyed"] = 0.0
    out["surveyed_area_km2"] = ns * cell * cell / 1e6
    return out
