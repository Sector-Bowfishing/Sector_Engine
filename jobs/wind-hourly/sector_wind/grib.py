"""GRIB2 access for NOAA open-data buckets: .idx byte ranges, ecCodes decoding, and the two
traps Wind Stage 1 hit.

1. NBM GRIB2 uses boustrophedonic scanning (alternativeRowScanning = 1): every odd row is
   stored right-to-left. ecCodes' latitude/longitude arrays do NOT follow it, so the values
   must be re-ordered or every other grid row lands on the wrong place.
2. HRRR (and other Lambert products) may carry grid-relative U/V (uvRelativeToGrid = 1).
   They must be rotated to earth-relative before any direction is computed.

ecCodes handles are not thread-safe: every decode runs under one lock."""
from __future__ import annotations

import math
import threading
import time
import urllib.request
from dataclasses import dataclass

import eccodes
import numpy as np

UA = "SectorWind/1.0 (wind-hourly; github.com/Sector-Bowfishing)"
_LOCK = threading.Lock()


def fetch(url: str, rng: tuple[int, int | str] | None = None, timeout: int = 120, tries: int = 4) -> bytes:
    headers = {"User-Agent": UA}
    if rng is not None:
        headers["Range"] = f"bytes={rng[0]}-{rng[1]}"
    last = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
                return r.read()
        except Exception as e:  # network or 404: retry, then surface
            last = e
            if getattr(e, "code", None) == 404:
                break
            time.sleep(1.5 * (attempt + 1))
    raise FetchError(f"{url}: {last}")


class FetchError(RuntimeError):
    pass


class DecodeError(RuntimeError):
    pass


@dataclass(frozen=True)
class IdxEntry:
    n: int
    start: int
    end: int | str          # "" = to end of file
    var: str
    level: str
    step: str
    tail: str               # e.g. "" (deterministic), "ens std dev", "10% level"


def read_idx(url: str) -> list[IdxEntry]:
    lines = [ln for ln in fetch(url + ".idx").decode().strip().split("\n") if ln]
    out = []
    for i, ln in enumerate(lines):
        p = ln.split(":")
        nxt = int(lines[i + 1].split(":")[1]) - 1 if i + 1 < len(lines) else ""
        tail = ":".join(x for x in p[6:] if x) if len(p) > 6 else ""
        out.append(IdxEntry(int(p[0]), int(p[1]), nxt, p[3], p[4], p[5] if len(p) > 5 else "", tail))
    return out


def find(entries: list[IdxEntry], var: str, level: str, tail: str = "", step_contains: str | None = None) -> IdxEntry | None:
    """Exact match on variable, level and tail. A deterministic field has an empty tail."""
    for e in entries:
        if e.var == var and e.level == level and e.tail == tail and (step_contains is None or step_contains in e.step):
            return e
    return None


@dataclass
class Field:
    values: np.ndarray       # 1-D, aligned with the grid's lat/lon arrays (row-order fixed)
    grid_key: str
    short_name: str
    uv_relative_to_grid: bool
    alt_rows_fixed: bool
    lov_deg: float | None
    latin1_deg: float | None
    missing: np.ndarray      # bool mask


_GRIDS: dict[str, tuple[np.ndarray, np.ndarray]] = {}


def grid(grid_key: str) -> tuple[np.ndarray, np.ndarray]:
    return _GRIDS[grid_key]


def decode(blob: bytes) -> Field:
    with _LOCK:
        gid = eccodes.codes_new_from_message(blob)
        try:
            g = lambda k, d=None: eccodes.codes_get(gid, k) if eccodes.codes_is_defined(gid, k) else d
            nx, ny = g("Nx"), g("Ny")
            vals = np.array(eccodes.codes_get_values(gid), dtype=np.float64)
            missing_value = g("missingValue", 9999)
            alt = g("alternativeRowScanning", 0) == 1
            if alt:
                if not (nx and ny) or vals.size != nx * ny:
                    raise DecodeError("alternative row scanning on a grid without Nx/Ny")
                v2 = vals.reshape(ny, nx)
                v2[1::2] = v2[1::2, ::-1].copy()
                vals = v2.ravel()
            key = f"{g('gridType')}:{nx}x{ny}:{g('latitudeOfFirstGridPointInDegrees')}:{g('longitudeOfFirstGridPointInDegrees')}:{g('DxInMetres')}"
            if key not in _GRIDS:
                lat = np.array(eccodes.codes_get_array(gid, "latitudes"))
                lon = np.array(eccodes.codes_get_array(gid, "longitudes"))
                lon = np.where(lon > 180, lon - 360, lon)
                _GRIDS[key] = (lat, lon)
            lov = g("LoVInDegrees"); latin1 = g("Latin1InDegrees")
            if lov is not None and lov > 180:
                lov -= 360
            miss = vals == missing_value
            return Field(vals, key, g("shortName"), bool(g("uvRelativeToGrid", 0)), alt, lov, latin1, miss)
        finally:
            eccodes.codes_release(gid)


def rotate_to_earth(u: np.ndarray, v: np.ndarray, lon: np.ndarray, lov_deg: float, latin1_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Grid-relative -> earth-relative components on a Lambert conformal grid (one tangent latitude).
    angle = sin(latin1) * (lon - LoV); positive angle rotates grid x toward true north."""
    a = np.radians(math.sin(math.radians(latin1_deg)) * (lon - lov_deg))
    ue = np.cos(a) * u + np.sin(a) * v
    ve = -np.sin(a) * u + np.cos(a) * v
    return ue, ve


def speed_dir_from_uv(u: np.ndarray, v: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """u, v = motion TOWARD east/north. Returns speed and meteorological FROM direction."""
    spd = np.hypot(u, v)
    d = (np.degrees(np.arctan2(-u, -v)) + 360.0) % 360.0
    return spd, d


def uv_from_speed_dir(spd: np.ndarray, dir_from: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    r = np.radians(dir_from)
    return -spd * np.sin(r), -spd * np.cos(r)


def cells_in_bbox(grid_key: str, bbox: tuple[float, float, float, float]) -> np.ndarray:
    lat, lon = grid(grid_key)
    w, s, e, n = bbox
    return np.where((lon >= w) & (lon <= e) & (lat >= s) & (lat <= n))[0]


def row_scramble_ratio(values: np.ndarray, cells: np.ndarray, nx: int) -> float:
    """Decoder self-check. On a correctly ordered smooth field, neighbouring rows differ about as
    much as neighbouring columns. Boustrophedonic data decoded without the row fix makes the
    row-to-row differences far larger. Returns median|d_row| / median|d_col| over the cut-out."""
    pos = {divmod(int(k), nx): float(values[k]) for k in cells}
    dr, dc = [], []
    for (r, c), v in pos.items():
        if (r + 1, c) in pos: dr.append(abs(pos[(r + 1, c)] - v))
        if (r, c + 1) in pos: dc.append(abs(pos[(r, c + 1)] - v))
    if not dr or not dc:
        return float("nan")
    # Means plus a 0.05 m/s floor: a calm, quantised field has median differences of exactly 0,
    # which made the first version fail closed on a real calm morning (RTMA-RU 2026-10-04 12Z).
    eps = 0.05
    return (float(np.mean(dr)) + eps) / (float(np.mean(dc)) + eps)
