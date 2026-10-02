"""Colour every water cell of the lake from one Landsat pass.

Used by derive_water_surface.py. Chosen by scoring five fills against
held-out readings on the 3 Sep 2026 pass (near-shore band, narrow water,
leave-one-embayment-out, 2.5 km blocks); the scores are in
docs/fishintel/WATER_SURFACE_LAYERS.md ("Colouring the whole lake"). It is a
geometry trend plus a screened-Laplace residual, both carried through the
water only.

  value = trend(cell) + residual(cell)

  trend     b0 + b1 * offstem * (1 - exp(-gd_tube / 2 km)), fit by least squares
            on the measured cells of THIS pass that the caller passes in
            `fit_mask` (the pipeline: >= 300 m from any QA non-water, so the
            land and mats in the pixel do not steer it). gd_tube is the
            distance through the water from the main river channel ("tube":
            the union of the inscribed discs along the dam-to-dam centreline).
            Arms and bays read warmer the further they run from the channel,
            but the slope is not well pinned: on 3 Sep 2026 it was +1.01 F on
            every measured cell, +0.92 on cells >= 300 m from non-water (9 arms)
            and +0.55 at >= 600 m (3 arms, interval spanning zero). Side
            channels open to the main channel at both ends (the upper river's
            braids) count as channel, not backwater.
  residual  measured - trend at the measured cells, carried into the gaps by
            (L + (cell/screen_m)^2) r = 0 on the 4-neighbour water lattice:
            Dirichlet at measured cells, no flux through the shore, and relaxing
            to 0 (i.e. to the trend) over ~10 km with no reading. Nothing is
            carried across land.

There is deliberately NO distance-to-shore term: fitted, it reproduces the
land-in-the-pixel warming (its effect is carried by how hot the adjacent land
is), and extrapolated into the 0-200 m band it would paint that bias on.

Pieces of the lake that the 50 m centre-burn cuts off (the NHD polygon is ONE
polygon; every piece joins through a channel narrower than a cell) are joined
back through the all-touched burn, along the shortest touched path, so they get
the water at their mouth rather than a guess. Without `lake_touch` they get the
trend alone.
"""
import math
import numpy as np
from scipy import ndimage, sparse
from scipy.sparse import csgraph
from scipy.sparse.linalg import spsolve, splu
from scipy.spatial.distance import cdist

SCREEN_M = 10_000.0     # holdouts: 5 / 10 / 20 km within 0.02 F RMSE; 10 km best overall
# Held-out RMSE of an estimate by its through-water distance to a reading
# (near-shore band + leave-one-embayment-out + 2.5 km blocks, pooled; the
# shore-corrected 3 Sep 2026 pass; verify/holdouts_new.py). [up to m, °F];
# the last row is everything further. Re-run the holdouts on a new pass.
ERROR_BY_DISTANCE_F = [[250, 0.14], [500, 0.25], [1000, 0.35], [2000, 0.52],
                       [5000, 0.87], [None, 0.99]]
# A side channel open to the main channel at both ends, this far apart, and
# nowhere further from it through the water than a braid of that length
# would be (half its span, with slack), is channel. A bay reaches much
# further back than the width of its mouth.
FLOW_MIN_SPAN_M = 1_000.0
FLOW_REACH_PER_SPAN = 0.6
FLOW_REACH_SLACK_M = 500.0
ARM_SCALE_M = 2_000.0   # a priori; 1 and 4 km within 0.02 F RMSE on every holdout
TUBE_PAD = 1.15         # inscribed-disc radius multiplier for the main channel
GD_CAP_M = 20_000.0
MIN_ARM_CELLS = 500     # fewer measured off-stem cells than this: no trend, residual only


# The reach band (the 100 m past the lake's line the app's coast may draw as
# water) takes a Gaussian blend of the lake cells near it, not the single
# nearest one: where a road crosses an arm the two sides were filled apart,
# and a nearest copy drew their difference as a hard line across the road the
# app draws as water (1.9 °F across the Mud Creek crossing).
BAND_BLEND_SIGMA_CELLS = 1.5


def _fill_band(field, valued, band):
    """Give each `band` cell the Gaussian-weighted mean of the `valued` cells
    round it, or the nearest valued cell's value where none is close."""
    out = field.copy()
    if not band.any():
        return out
    v = np.where(valued, field, 0.0)
    num = ndimage.gaussian_filter(v, BAND_BLEND_SIGMA_CELLS, mode="constant")
    den = ndimage.gaussian_filter(valued.astype("float64"), BAND_BLEND_SIGMA_CELLS, mode="constant")
    blend = band & (den > 0.05)
    out[blend] = num[blend] / den[blend]
    rest = band & ~blend
    if rest.any():
        _, (ir, ic) = ndimage.distance_transform_edt(~valued, return_indices=True)
        out[rest] = field[ir[rest], ic[rest]]
    return out


def _index(mask):
    idx = -np.ones(mask.shape, np.int64)
    idx[mask] = np.arange(int(mask.sum()))
    return idx


def _lattice4(mask, idx):
    e = []
    for a, b in ((idx[:, :-1], idx[:, 1:]), (idx[:-1, :], idx[1:, :])):
        ok = (a >= 0) & (b >= 0)
        e.append((a[ok], b[ok]))
    i = np.concatenate([x for x, _ in e]); j = np.concatenate([y for _, y in e])
    n = int(mask.sum())
    A = sparse.coo_matrix((np.ones(i.size), (i, j)), shape=(n, n)).tocsr()
    return A + A.T


def _graph8(mask, idx, G):
    """Metric 8-neighbour graph; a diagonal only where an orthogonal neighbour
    is water, so a path never slips through a land corner."""
    H, W = mask.shape
    rows, cols, lens = [], [], []
    def add(dr, dc, L, need=None):
        sa = (slice(max(0, -dr), H - max(0, dr)), slice(max(0, -dc), W - max(0, dc)))
        sb = (slice(max(0, dr), H + min(0, dr)), slice(max(0, dc), W + min(0, dc)))
        ok = mask[sa] & mask[sb]
        if need is not None:
            ok &= need
        rows.append(idx[sa][ok]); cols.append(idx[sb][ok]); lens.append(np.full(int(ok.sum()), L))
    add(0, 1, G); add(1, 0, G)
    add(1, 1, G * math.sqrt(2), need=mask[:-1, 1:] | mask[1:, :-1])
    add(1, -1, G * math.sqrt(2), need=mask[:-1, :-1] | mask[1:, 1:])
    i = np.concatenate(rows); j = np.concatenate(cols); L = np.concatenate(lens)
    n = int(mask.sum())
    A = sparse.coo_matrix((L, (i, j)), shape=(n, n)).tocsr()
    return A + A.T


def _bridges(lake, lake_touch, anchored_lake):
    """Touched-but-not-centre cells on the shortest touched path from each
    cut-off piece of the lake to the water that has readings."""
    solve = lake | lake_touch
    idx = _index(solve)
    A = _lattice4(solve, idx)
    src = idx[anchored_lake]
    dist, pred, _ = csgraph.dijkstra(A, indices=src, min_only=True, return_predecessors=True)
    rr, cc = np.nonzero(solve)
    lab, n = ndimage.label(lake & ~anchored_lake)
    out = np.zeros(lake.shape, bool)
    if n == 0:
        return out
    d = np.full(lake.shape, np.inf); d[solve] = dist
    lab_idx = np.arange(1, n + 1)
    # each piece's cell nearest the anchored water
    best = ndimage.minimum_position(np.where(lab > 0, d, np.inf), labels=lab, index=lab_idx)
    for (r, c) in best:
        k = idx[r, c]
        if not np.isfinite(dist[k]):
            continue
        while k >= 0 and not anchored_lake[rr[k], cc[k]]:
            if not lake[rr[k], cc[k]]:
                out[rr[k], cc[k]] = True
            k = pred[k]
    return out


def lake_geometry(water, G, stem_ends, tube_pad=TUBE_PAD):
    """Shore distance, main-channel tube and through-water distance from it."""
    idx = _index(water)
    A8 = _graph8(water, idx, G)
    dt = np.where(water, ndimage.distance_transform_edt(water) * G - G / 2, 0.0)
    rr, cc = np.nonzero(water)
    def snap(p):
        k = np.argmin((rr - p[0]) ** 2 + (cc - p[1]) ** 2); return idx[rr[k], cc[k]]
    a, b = snap(stem_ends[0]), snap(stem_ends[1])
    C = A8.tocoo(); dtv = dt[water]
    w = C.data / np.maximum(0.5 * (dtv[C.row] + dtv[C.col]), G / 2) ** 2
    _, pred = csgraph.dijkstra(sparse.csr_matrix((w, (C.row, C.col)), shape=A8.shape),
                               indices=a, return_predecessors=True)
    stem = np.zeros(water.shape, bool)
    k = b
    while k >= 0:
        stem[rr[k], cc[k]] = True
        if k == a:
            break
        k = pred[k]
    if not stem[rr[a], cc[a]]:
        raise ValueError("stem ends are not connected through the water")
    # tube = union of the (padded) inscribed discs centred on the stem
    tube = np.zeros(water.shape, bool)
    pr, pc = np.nonzero(stem); q = np.round(dt[stem] / G * 2) / 2
    for R in np.unique(q):
        sel = np.zeros(water.shape, bool); sel[pr[q == R], pc[q == R]] = True
        tube |= ndimage.distance_transform_edt(~sel) <= R * tube_pad + 0.5
    tube &= water
    gd = csgraph.dijkstra(A8, indices=idx[tube], min_only=True)
    gd_tube = np.full(water.shape, np.inf, np.float32); gd_tube[water] = gd
    flow = flow_through_channels(water, tube, gd_tube, G)
    return {"dt": dt, "stem": stem, "tube": tube, "gd_tube": gd_tube, "idx": idx, "A8": A8,
            "flow": flow}


def flow_through_channels(water, tube, gd_tube, G):
    """Off-channel water that the main channel enters at two places at least
    FLOW_MIN_SPAN_M apart, and that runs no further from it than a braid of
    that span would: a channel round an island, which flows, not a bay."""
    cross = ndimage.generate_binary_structure(2, 1)
    off = water & ~tube
    lab, n = ndimage.label(off, structure=cross)
    flow = np.zeros(water.shape, bool)
    if n == 0:
        return flow
    contact = ndimage.binary_dilation(tube, structure=cross) & off
    clab, _ = ndimage.label(contact, structure=np.ones((3, 3)))
    reach = ndimage.maximum(np.where(np.isfinite(gd_tube), gd_tube, 1e12), lab,
                            index=np.arange(1, n + 1))
    touching = np.unique(lab[contact])
    for k in touching[touching > 0]:
        ids = np.unique(clab[(lab == k) & contact])
        ids = ids[ids > 0]
        if ids.size < 2:
            continue
        # The widest gap between two places the channel enters it: a bay whose
        # mouth an islet splits has two contacts a couple of hundred metres
        # apart; a braid's two ends are kilometres apart.
        pts = [np.argwhere((clab == i) & (lab == k)) for i in ids]
        span = max(cdist(pts[a], pts[b]).min()
                   for a in range(len(pts)) for b in range(a + 1, len(pts))) * G
        if (span >= FLOW_MIN_SPAN_M
                and reach[k - 1] <= FLOW_REACH_PER_SPAN * span + FLOW_REACH_SLACK_M):
            flow |= lab == k
    return flow


def fill_whole_lake(anomaly_f, lake_mask, *, cell_ground_m, stem_ends, lake_touch=None,
                    reach=None, fit_mask=None, screen_m=SCREEN_M, arm_scale_m=ARM_SCALE_M,
                    return_info=False):
    """Fill every lake cell of a °F anomaly field.

    anomaly_f     (H, W) float, °F above/below the scene median, NaN where not
                  read: the pipeline's field after smooth_known, before fill().
    lake_mask     (H, W) bool, the lake burned by cell centre (masks["lake"]).
    cell_ground_m ground size of one cell (50 mercator m * cos(lat) ~ 41.1 m).
    stem_ends     ((row, col), (row, col)): the two ends of the main channel
                  (for Guntersville: the dam and the Nickajack tailwater).
    lake_touch    optional (H, W) bool, the lake burned all_touched; only used
                  to rejoin pieces the centre-burn cuts off.
    reach         optional (H, W) bool (masks["reach"]); cells in it outside the
                  lake take the nearest lake cell's value, as today.
    fit_mask      optional (H, W) bool: only measured cells inside it fit the
                  trend (all of them still anchor the residual). Too few
                  off-channel cells in it and there is no trend at all.

    Returns (filled, measured): filled is float32, NaN outside lake (| reach);
    measured is True only where anomaly_f held a reading inside the lake.
    """
    G = float(cell_ground_m)
    lake = lake_mask.astype(bool)
    vals = np.where(lake, anomaly_f, np.nan).astype("float64")
    measured = lake & ~np.isnan(vals)
    if measured.sum() == 0:
        raise ValueError("no measured cells")

    # which lake pieces touch a reading (4-neighbour, centre-burn)
    lab, _ = ndimage.label(lake)
    anch_ids = np.unique(lab[measured])
    anchored = np.isin(lab, anch_ids) & lake
    bridges = np.zeros(lake.shape, bool)
    if lake_touch is not None and (lake & ~anchored).any():
        bridges = _bridges(lake, lake_touch.astype(bool), anchored)
    water = lake | bridges

    geo = lake_geometry(water, G, stem_ends)
    idx = geo["idx"]
    offstem = water & ~geo["tube"] & ~geo["flow"]
    armd = np.where(offstem, 1 - np.exp(-np.minimum(geo["gd_tube"], GD_CAP_M) / arm_scale_m), 0.0)

    # trend, fit on this pass's readings
    fit = measured if fit_mask is None else measured & fit_mask.astype(bool)
    y = vals[fit]
    if (fit & offstem).sum() >= MIN_ARM_CELLS:
        X = np.column_stack([np.ones(y.size), armd[fit]])
        beta = np.linalg.lstsq(X, y, rcond=None)[0]
    else:
        beta = np.array([float(np.mean(vals[measured])), 0.0])
    trend = beta[0] + beta[1] * armd

    # screened-Laplace residual on the 4-neighbour water lattice
    A = _lattice4(water, idx)
    deg = np.asarray(A.sum(1)).ravel()
    r = np.zeros(int(water.sum()))
    kn = measured[water]
    r[kn] = (vals - trend)[measured]
    ncomp, comp = csgraph.connected_components(A, directed=False)
    has = np.zeros(ncomp, bool); has[np.unique(comp[kn])] = True
    U = np.nonzero(~kn & has[comp])[0]; K = np.nonzero(kn)[0]
    if U.size:
        L = sparse.diags(deg[U] + (G / screen_m) ** 2) - A[U][:, U]
        r[U] = spsolve(L.tocsc(), A[U][:, K] @ r[K])
    field = np.full(lake.shape, np.nan)
    field[water] = trend[water] + r
    field[measured] = vals[measured]
    field[~lake] = np.nan

    if reach is not None:
        field = _fill_band(field, lake & ~np.isnan(field), reach.astype(bool) & ~lake)

    filled = field.astype(np.float32)
    if not return_info:
        return filled, measured
    info = {"trend_intercept_F": float(beta[0]), "trend_armdepth_F": float(beta[1]),
            "trend_fit_cells": int(fit.sum()),
            "flow_through_cells": int((geo["flow"] & lake).sum()),
            "bridge_cells": int(bridges.sum()), "tube_cells": int((geo["tube"] & lake).sum()),
            "unanchored_lake_cells": int((lake & ~has[comp][np.maximum(idx, 0)] ).sum()),
            "tube": geo["tube"], "stem": geo["stem"], "gd_tube": geo["gd_tube"],
            "flow": geo["flow"]}
    # through-water distance from each cell to the nearest reading (for a confidence tier)
    dist = csgraph.dijkstra(geo["A8"], indices=idx[measured], min_only=True)
    gdm = np.full(lake.shape, np.inf, np.float32); gdm[water] = dist
    info["dist_to_reading_m"] = np.where(lake, gdm, np.nan)
    return filled, measured, info


# ============================================================================
# Clarity (Sentinel-2, log10 FNU)
# ============================================================================
#
# Colour every open-water cell of the lake from one Sentinel-2 pass. Chosen by
# scoring fills against held-out readings on the 20 Sep 2026 pass (near-shore
# band, leave-one-embayment-out, 2.5 and 5 km blocks, water beside grass;
# scratchpad study clarfill/fill/). A screened-Laplace fill of the readings
# through the water only, relaxing to the pass's mean reading over ~10 km,
# with grass beds as a SOFT barrier.
#
#   value = b0 + r(cell)
#   b0  the mean log10 FNU of the readings. NO geometry trend: none of the
#       arm-depth term, distance from arm heads, position along an arm or
#       local width helped any holdout, and the arm-depth trend made
#       leave-one-embayment-out worse (0.118 vs 0.099 log10 RMSE). Arms read
#       like the water at their mouths (r = 0.82 over 23 arms).
#   r   reading - b0 at the measured cells, carried by (L_w + (cell/screen)^2)
#       r = 0 on the 4-neighbour water lattice, as for temperature.
#
# GRASS stays in the lattice as water of unknown clarity, but every edge
# touching it conducts 3%, so a value reaches water behind a bed round the
# open water when it can, and through the bed only when it cannot. On the
# 10 m reader it ties "through grass" within 0.001 log10 everywhere but the
# 5 km blocks (+0.003), and beats a hard barrier. Grass cells come back NaN:
# the map draws them as grass, never as a clarity.

# Held-out RMSE of an estimate by its through-water distance to a reading
# (near-shore band + leave-one-embayment-out + 2.5 km blocks, pooled), on the
# 10 m reader's readings of 20 Sep 2026 (clarfill/verify/holdouts_new.py).
# [up to m, value]; the last row is everything further. Beyond 5 km the
# estimates also lean ~0.8 ft too clear. Re-run the holdouts whenever the
# reader, its gates or the pass change.
CLARITY_ERROR_BY_DISTANCE_LOG10 = [[250, 0.032], [500, 0.046], [1000, 0.057], [2000, 0.075],
                                   [5000, 0.096], [None, 0.138]]
CLARITY_ERROR_BY_DISTANCE_FT = [[250, 0.32], [500, 0.45], [1000, 0.60], [2000, 0.78],
                                [5000, 0.94], [None, 1.11]]     # visibility, 4.84*FNU^-0.672 m
CLARITY_SCREEN_M = 10_000.0  # holdouts: 3 km and 30 km within 0.01 log10 RMSE; 10 km best on embayments
GRASS_CONDUCTANCE = 0.03   # 0 (hard barrier) and 1 (through) bracket it within 0.008 log10 RMSE


def _grass_from_water(field, water, grass, idx, b0, G, screen_m):
    """Grass cells re-solved from the water round them, the bed treated as open
    water; every other cell of `field` is left exactly as it was.

    A GRASS BED'S CLARITY IS THE WATER AROUND IT, CARRIED IN. The satellite sees
    the plants, not the water, so a bed has nothing to read (Michael,
    2026-09-26: the olive beds read as "missing a lot of map data"). The soft
    barrier's own grass values relax toward the lake mean inside a big bed, which
    would draw each bed as a blob of its own colour; solved as open water with
    the water outside held fixed, a bed continues the water it sits in and
    meets it without a seam.
    """
    A = _lattice4_soft(water, idx, grass, 1.0)
    deg = np.asarray(A.sum(1)).ravel()
    fw = field[water] - b0
    g = grass[water]
    K = np.nonzero(~g & ~np.isnan(fw))[0]
    ncomp, comp = csgraph.connected_components(A, directed=False)
    has = np.zeros(ncomp, bool)
    has[np.unique(comp[K])] = True
    U = np.nonzero(g & has[comp])[0]
    out = field.copy()
    if U.size:
        L = (sparse.diags(deg[U] + (G / screen_m) ** 2) - A[U][:, U]).tocsc()
        sol = splu(L).solve(A[U][:, K] @ fw[K])
        w = out[water]
        w[U] = b0 + sol
        out[water] = w
    return out


def _lattice4_soft(water, idx, soft, w):
    rows, cols, vals = [], [], []
    for sa, sb in (((slice(None), slice(None, -1)), (slice(None), slice(1, None))),
                   ((slice(None, -1), slice(None)), (slice(1, None), slice(None)))):
        a, b = idx[sa], idx[sb]
        ok = (a >= 0) & (b >= 0)
        rows.append(a[ok]); cols.append(b[ok])
        vals.append(np.where((soft[sa] | soft[sb])[ok], w, 1.0))
    i = np.concatenate(rows); j = np.concatenate(cols); v = np.concatenate(vals)
    n = int(water.sum())
    A = sparse.coo_matrix((v, (i, j)), shape=(n, n)).tocsr()
    return (A + A.T).tocsr()


def fill_clarity(logv, lake_mask, grass, *, cell_ground_m, lake_touch=None, reach=None,
                 screen_m=CLARITY_SCREEN_M, grass_conductance=GRASS_CONDUCTANCE,
                 cloud=None, classified=None, value_grass=False):
    """Fill every non-grass lake cell (and the reach band) of a log10 FNU field
    — and, with `value_grass`, the grass cells too.

    logv          (H, W) float, log10 FNU, NaN where not read: build_clarity's
                  field AFTER the muddy-speck removal and INSTEAD OF its small
                  fill(sigmas=(1, 1.5)).
    lake_mask     (H, W) bool, masks["lake"] (centre burn).
    grass         (H, W) bool, s2_pass's grass class.
    cell_ground_m one cell on the ground (36 mercator m * cos(lat) ~ 29.6 m).
    lake_touch    optional masks["lake_touch"]; rejoins pieces the centre burn
                  cuts off. Without it they get b0.
    reach         optional masks["reach"]; cells in it outside the lake take the
                  nearest lake cell's value (a grass cell's internal value if
                  that is nearest), so the app's coastline never meets an
                  empty cell.
    cloud         optional (H, W) bool, water the pass's cloud/shadow mask hid.
                  If given, info["source"] holds the measured-PNG codes:
                  255 measured, 2 estimated (cloud), 1 estimated (unreadable:
                  bank band, bridges/docks, narrow water), 0 no value (grass,
                  outside).
    classified    optional masks["clarity"] (the lake eroded 40 m, where
                  s2_pass can classify grass). If given, info["bank_behind_grass"]
                  marks bank-band cells whose nearest classified cell is grass.
    value_grass   give grass cells an estimate: the water round the bed carried
                  in as if the bed were open water (`_grass_from_water`). The
                  non-grass cells are exactly as without it.

    Returns (filled, measured, info). filled is float32 log10 FNU, NaN outside
    lake | reach, and on grass cells unless `value_grass`; measured is True only where logv held a
    reading on a non-grass lake cell; info["dist_to_reading_m"] is the
    through-water distance (grass counted as water) from each lake cell to the
    nearest reading, NaN outside the lake.
    """
    G = float(cell_ground_m)
    lake = lake_mask.astype(bool)
    grass = grass.astype(bool) & lake
    vals = np.where(lake & ~grass, logv, np.nan).astype("float64")
    measured = lake & ~np.isnan(vals)
    if not measured.any():
        raise ValueError("no measured cells")

    lab, _ = ndimage.label(lake)
    anchored = np.isin(lab, np.unique(lab[measured])) & lake
    bridges = np.zeros(lake.shape, bool)
    if lake_touch is not None and (lake & ~anchored).any():
        bridges = _bridges(lake, lake_touch.astype(bool), anchored)
    water = lake | bridges

    idx = _index(water)
    A = _lattice4_soft(water, idx, grass, float(grass_conductance))
    deg = np.asarray(A.sum(1)).ravel()
    b0 = float(np.mean(vals[measured]))
    kn = measured[water]
    r = np.zeros(int(water.sum()))
    r[kn] = vals[water][kn] - b0
    ncomp, comp = csgraph.connected_components(A, directed=False)
    has = np.zeros(ncomp, bool); has[np.unique(comp[kn])] = True
    U = np.nonzero(~kn & has[comp])[0]; K = np.nonzero(kn)[0]
    if U.size:
        L = (sparse.diags(deg[U] + (G / screen_m) ** 2) - A[U][:, U]).tocsc()
        r[U] = splu(L).solve(A[U][:, K] @ r[K])
    field = np.full(lake.shape, np.nan)
    field[water] = b0 + r          # pieces with no reading at all stay at b0
    field[measured] = vals[measured]
    if value_grass and (grass & water).any():
        field = _grass_from_water(field, water, grass, idx, b0, G, screen_m)
    field[~lake] = np.nan

    if reach is not None:
        field = _fill_band(field, lake & ~np.isnan(field), reach.astype(bool) & ~lake)

    filled = field.astype(np.float32)
    if not value_grass:
        filled[grass] = np.nan

    A8 = _graph8(water, idx, G)
    d = csgraph.dijkstra(A8, indices=idx[measured], min_only=True)
    dist = np.full(lake.shape, np.nan, np.float32); dist[water] = d
    dist[~lake] = np.nan
    anch = np.zeros(lake.shape, bool); anch[water] = has[comp]
    info = {"b0_log10": b0, "screen_m": float(screen_m),
            "grass_conductance": float(grass_conductance),
            "bridge_cells": int(bridges.sum()),
            "unanchored_lake_cells": int((lake & ~anch).sum()),
            "dist_to_reading_m": dist}
    if cloud is not None:
        src = np.zeros(lake.shape, np.uint8)
        src[~np.isnan(filled)] = 1
        src[lake & ~measured & ~grass & cloud.astype(bool) & ~np.isnan(filled)] = 2
        src[measured] = 255
        info["source"] = src
    if classified is not None:
        cm = classified.astype(bool)
        _, (ir, ic) = ndimage.distance_transform_edt(~cm, return_indices=True)
        info["bank_behind_grass"] = lake & ~cm & grass[ir, ic]
    return filled, measured, info
