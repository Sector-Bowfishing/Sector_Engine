"""ESTIMATED fetch geometry from a lake polygon (offline build tool; NOT part of the hourly job image).

Produces an object with the same shape as the audited NHD fetch tables (`banks` with anchor/standoff, `tableBase64`
= 120 bearings x uint16 decametres, row = bank, column = FROM-bearing index, 0 = N clockwise, 3 deg) so the Brain's
state code uses it unchanged. It is labelled `geometryTier: ESTIMATED`:

  * research (docs/wind-research/WIND_FETCH_RESEARCH.md): magnitude agreed with the audited tables (about -6% on open
    lakes) but the registered direction-rank agreement FAILED (rho 0.56, dominant direction 51%) -> NOT audited, NOT validated;
  * different polygon source and bank sampling than the NHD pipeline;
  * 20 m raster cells (up to 3000 px); banks narrower than that are belowResolution (Unknown), never Protected.

Requires shapely, Pillow, scipy (see requirements-fleet.txt). Deterministic: same polygon -> same bytes."""
from __future__ import annotations

import base64
import hashlib
import math
import struct

import numpy as np

SCHEMA = "sector-wind-fetch-v1"
TIER = "ESTIMATED"
NB, STEP_DEG = 120, 3.0
MAXM = 30000.0
MIN_RES_M, MAX_PIX, MAX_BANKS = 20.0, 3000, 400
GENERATOR = "sector_wind.brain.estimate 1.0.0 (polygon raster ray-march; research G2 FAILED the direction-rank gate)"


def _deps():
    from PIL import Image, ImageDraw
    from scipy import ndimage
    from shapely.geometry import MultiPolygon, Polygon
    return Image, ImageDraw, ndimage, MultiPolygon, Polygon


def rasterize(geom, max_pix=MAX_PIX, min_res=MIN_RES_M):
    """(mask[bool, True = water], res_m, (lon0, lat1, kx, ky)) ; islands/holes are land."""
    Image, ImageDraw, _, MultiPolygon, _ = _deps()
    lon0, lat0, lon1, lat1 = geom.bounds
    latm = math.radians((lat0 + lat1) / 2)
    kx, ky = 111320.0 * math.cos(latm), 110574.0
    w, h = (lon1 - lon0) * kx, (lat1 - lat0) * ky
    res = max(min_res, max(w, h) / max_pix)
    nx, ny = int(w / res) + 3, int(h / res) + 3
    img = Image.new("L", (nx, ny), 0)
    d = ImageDraw.Draw(img)
    tr = lambda ring: [((x - lon0) * kx / res + 1, (lat1 - y) * ky / res + 1) for x, y in ring.coords]
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for p in polys:
        d.polygon(tr(p.exterior), fill=1)
    for p in polys:
        for r in p.interiors:
            d.polygon(tr(r), fill=0)
    return np.array(img, dtype=bool), res, (lon0, lat1, kx, ky)


def clean_geometry(geom):
    """Largest valid polygonal part set; GeometryCollections reduced to their polygons. None when nothing usable."""
    from shapely.geometry import MultiPolygon, Polygon
    if geom is None or geom.is_empty:
        return None
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.geom_type == "GeometryCollection":
        parts = [g for g in geom.geoms if g.geom_type in ("Polygon", "MultiPolygon")]
        if not parts:
            return None
        from shapely.ops import unary_union
        geom = unary_union(parts)
    return geom if geom.geom_type in ("Polygon", "MultiPolygon") else None


def ray_distances(mask, res, xs, ys, bearing_deg):
    """Open-water distance (m) from each cell toward `bearing_deg` (the wind-FROM bearing, i.e. looking INTO the wind)."""
    th = math.radians(bearing_deg)
    dx, dy = math.sin(th), -math.cos(th)          # image y grows southward
    H, W = mask.shape
    dist = np.full(len(xs), MAXM)
    alive = np.ones(len(xs), bool)
    for k in range(1, int(MAXM / res) + 1):
        px = np.rint(xs + dx * k).astype(int)
        py = np.rint(ys + dy * k).astype(int)
        inb = (px >= 0) & (px < W) & (py >= 0) & (py < H)
        wet = np.zeros(len(xs), bool)
        wet[inb] = mask[py[inb], px[inb]]
        hit = alive & ~wet
        dist[hit] = k * res
        alive &= wet
        if not alive.any():
            break
    return dist


def _latlon(x, y, ref, res):
    lon0, lat1, kx, ky = ref
    return round(lat1 - (y - 1) * res / ky, 6), round(lon0 + (x - 1) * res / kx, 6)


def build_estimated_table(geom, lake_id: str | None = None, nmax: int = MAX_BANKS) -> dict | None:
    """Estimated fetch object for one lake polygon (lon/lat). None if the polygon yields fewer than 20 shoreline cells."""
    _, _, ndimage, _, _ = _deps()
    geom = clean_geometry(geom)
    if geom is None:
        return None
    mask, res, ref = rasterize(geom)
    edge = mask & ~ndimage.binary_erosion(mask, iterations=1)
    ys, xs = np.nonzero(edge)                       # row-major order: deterministic
    if len(xs) < 20:
        return None
    stride = max(1, len(xs) // nmax)
    xs, ys = xs[::stride].astype(float), ys[::stride].astype(float)
    # facing = direction of increasing water density (smoothed mask gradient), pointing from land toward water
    sm = ndimage.gaussian_filter(mask.astype(float), sigma=3.0)
    gy, gx = np.gradient(sm)
    table = np.zeros((len(xs), NB))
    for j in range(NB):
        table[:, j] = ray_distances(mask, res, xs, ys, j * STEP_DEG)
    banks = []
    for i, (x, y) in enumerate(zip(xs, ys)):
        xi, yi = int(x), int(y)
        nx_, ny_ = gx[yi, xi], -gy[yi, xi]          # (east, north) components of the water-ward normal
        norm = math.hypot(nx_, ny_)
        win = mask[max(0, yi - 2):yi + 3, max(0, xi - 2):xi + 3]
        sliver = int(win.sum()) < 6
        b = {"id": f"E-{i:04d}", "belowResolution": bool(sliver or norm < 1e-6), "region": "estimated"}
        if norm >= 1e-6:
            ux, uy = nx_ / norm, ny_ / norm
            b["anchor"] = list(_latlon(x - ux * 0.5, y + uy * 0.5, ref, res))
            b["standoff"] = list(_latlon(x + ux * 1.5, y - uy * 1.5, ref, res))
        else:
            b["anchor"] = b["standoff"] = list(_latlon(x, y, ref, res))
        banks.append(b)
    dam = np.clip(np.rint(table / 10.0), 0, 65535).astype("<u2")
    raw = dam.tobytes()
    return {"schema": SCHEMA, "geometryTier": TIER, "estimated": True, "validated": False, "lakeId": lake_id,
            "generator": GENERATOR,
            "params": {"rasterM": round(res, 1), "maxM": MAXM, "bearings": NB, "bearingStepDeg": STEP_DEG, "units": "decametres",
                       "convention": "row = bank, column = FROM-bearing index (0 = N, clockwise, 3 deg); ray looks INTO the wind",
                       "banksSampled": len(banks), "maxBanks": nmax},
            "banks": banks, "tableSha256": hashlib.sha256(raw).hexdigest(), "tableBase64": base64.b64encode(raw).decode()}
