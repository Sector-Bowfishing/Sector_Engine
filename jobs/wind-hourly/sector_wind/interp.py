"""Bilinear interpolation from an archived lake cut-out to a point (pre-registration §2.1).

The cut-out stores full-grid indices k and the grid width nx, so (row, col) = divmod(k, nx).
A local affine basis from the nearest cell's row/column neighbours turns the point into
fractional grid coordinates, which works on any regular projected grid (Lambert NBM/RTMA)
without carrying projection parameters.

Speed and gust are blended as scalars; direction comes from blended u/v (never from
averaging degrees)."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class Weights:
    idx: list[int]            # positions within the cut-out arrays
    w: list[float]
    method: str               # "bilinear" | "nearest" | "none"


class CutoutIndex:
    def __init__(self, cells: list[int], lat: list[float], lon: list[float], nx: int):
        self.cells = np.asarray(cells); self.lat = np.asarray(lat); self.lon = np.asarray(lon); self.nx = nx
        self.pos = {divmod(int(k), nx): i for i, k in enumerate(self.cells)}
        self.coslat = math.cos(math.radians(float(np.mean(self.lat))))

    def _xy(self, i):
        return np.array([self.lon[i] * self.coslat, self.lat[i]])

    def weights(self, lat: float, lon: float) -> Weights:
        p = np.array([lon * self.coslat, lat])
        d2 = (self.lon * self.coslat - p[0]) ** 2 + (self.lat - p[1]) ** 2
        n0 = int(np.argmin(d2))
        r0, c0 = divmod(int(self.cells[n0]), self.nx)
        def at(r, c):
            return self.pos.get((r, c))
        ix, iy = at(r0, c0 + 1), at(r0 + 1, c0)
        sx, sy = 1, 1
        if ix is None: ix, sx = at(r0, c0 - 1), -1
        if iy is None: iy, sy = at(r0 - 1, c0), -1
        if ix is None or iy is None:
            return Weights([n0], [1.0], "nearest")
        o = self._xy(n0)
        ex, ey = (self._xy(ix) - o) * sx, (self._xy(iy) - o) * sy
        try:
            fx, fy = np.linalg.solve(np.column_stack([ex, ey]), p - o)
        except np.linalg.LinAlgError:
            return Weights([n0], [1.0], "nearest")
        rb, cb = r0 + math.floor(fy), c0 + math.floor(fx)
        tx, ty = fx - math.floor(fx), fy - math.floor(fy)
        quad = [at(rb, cb), at(rb, cb + 1), at(rb + 1, cb), at(rb + 1, cb + 1)]
        if any(q is None for q in quad):
            return Weights([n0], [1.0], "nearest")
        return Weights(quad, [(1 - tx) * (1 - ty), tx * (1 - ty), (1 - tx) * ty, tx * ty], "bilinear")


def blend(values, wt: Weights):
    """Scalar blend. Any missing (None/NaN) contributor -> fall back to the heaviest valid cell."""
    vals = [values[i] for i in wt.idx]
    ok = [v is not None and not (isinstance(v, float) and math.isnan(v)) for v in vals]
    if all(ok):
        return float(sum(v * w for v, w in zip(vals, wt.w)))
    good = [(w, v) for v, w, k in zip(vals, wt.w, ok) if k]
    return float(max(good)[1]) if good else None


def blend_wind(speed, dir_from, wt: Weights):
    """Returns (speed, dirFrom or None). Speed = scalar blend; direction = atan2 of blended u/v."""
    s = blend(speed, wt)
    if s is None:
        return None, None
    us, vs, ws = 0.0, 0.0, 0.0
    for i, w in zip(wt.idx, wt.w):
        sp, d = speed[i], dir_from[i]
        if sp is None or d is None or (isinstance(d, float) and math.isnan(d)):
            continue
        r = math.radians(d)
        us += w * -sp * math.sin(r); vs += w * -sp * math.cos(r); ws += w
    if ws == 0 or math.hypot(us, vs) < 1e-9:
        return s, None
    return s, (math.degrees(math.atan2(-us, -vs)) + 360.0) % 360.0
