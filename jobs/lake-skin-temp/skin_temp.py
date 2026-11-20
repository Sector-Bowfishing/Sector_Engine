"""Lake skin temperature from NASA VIIRS night-time land surface temperature (research lane, Mac mini / Sector Pulse).

Owner direction (Michael, 2026-11-20, Sector_Ops #51): Brain values come from real observations, not estimates. This job
collects the observation: each lake's night-time surface ("skin") temperature from the VIIRS daily 1 km night LST grids
(VNP21A1N from Suomi NPP, VJ121A1N from NOAA-20, VJ221A1N from NOAA-21; collection 002, NASA LP DAAC). Night readings
avoid the daytime solar warm layer that sank the Landsat daytime offset in WT-NOW-4 (Sector_Ops #51, 2026-11-14).

RESEARCH ONLY. It writes local files ({--archive} per day, {--out} per run) and nothing else: no database write, no upload,
no customer path. Wiring a reading into the Water Temp Brain is a later Swift change plus a knowledge release, after the
pre-registered check WT-SAT-1 (docs/brains/WATER_TEMP_SAT_1_PREREGISTRATION_DRAFT.md) passes.

Per lake and per granule (one satellite, one night):
  * pixels: 1 km sinusoidal grid cells whose whole footprint (centre and all four corners) lies inside the lake outline
    (jobs/lake-surface/polygons.geojson.gz): no mixed land/water shore pixel;
  * quality: mandatory QA bits 0-1 == 00 ("good") only;
  * cloud distance: a pixel within --cloud-buffer-px cells of a cloudy or not-produced cell (QA 10 / 11) is dropped
    (missed cloud edges read cold);
  * the lake's reading is the median of the remaining pixels, only when at least --min-pixels remain.

Credentials: an Earthdata Login user token in the environment variable EARTHDATA_TOKEN (Pulse passes it from its Keychain
item `earthdata-token`). The token is sent only to *.earthdata.nasa.gov and *.earthdatacloud.nasa.gov hosts, never printed,
logged or written. Granule search (NASA CMR) is public and needs no token.

usage:
  skin_temp.py --out DIR --archive DIR --cache DIR [--date YYYY-MM-DD | --days-back N] [--products VNP21A1N,VJ121A1N]
               [--lakes "Guntersville|AL,..."] [--polygons FILE] [--cloud-buffer-px 2] [--min-pixels 3] [--keep-downloads]
               [--search-only]
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import numpy as np

SCHEMA = "lake-skin-temp-v1"
HERE = os.path.dirname(os.path.abspath(__file__))
POLYGONS = os.path.normpath(os.path.join(HERE, "..", "lake-surface", "polygons.geojson.gz"))

CMR = "https://cmr.earthdata.nasa.gov/search/granules.json"
DEFAULT_PRODUCTS = ("VNP21A1N", "VJ121A1N", "VJ221A1N")
VERSION = "002"
# Continental US, Alaska and Hawaii: the directory's extent (CMR bounding box west,south,east,north).
SEARCH_BOX = "-180,15,-60,72"
TOKEN_HOSTS = (".earthdata.nasa.gov", ".earthdatacloud.nasa.gov")
USER_AGENT = "SectorPulse-lake-skin-temp/1 (research; contact via Sector Bowfishing)"

# MODIS/VIIRS sinusoidal grid (identical for the 1 km VIIRS L3 tiles): 36 x 18 tiles of 1200 x 1200 cells.
R_EARTH = 6371007.181
TILE_M = 1111950.5196666666
TILE_PX = 1200
PIX_M = TILE_M / TILE_PX

QA_GOOD, QA_OTHER, QA_CLOUD, QA_NOT_PRODUCED = 0, 1, 2, 3
LST_SCALE, LST_FILL = 0.02, 0
FREEZE_K = 273.15


# ----------------------------------------------------------------------------------------------- grid geometry
def latlon_to_grid(lat: np.ndarray | float, lon: np.ndarray | float):
    """Return (h, v, row, col) of the 1 km sinusoidal cell containing each point."""
    lat_r = np.radians(lat)
    lon_r = np.radians(lon)
    x = R_EARTH * lon_r * np.cos(lat_r)
    y = R_EARTH * lat_r
    gx = x + 18 * TILE_M
    gy = 9 * TILE_M - y
    h = np.floor(gx / TILE_M).astype(int)
    v = np.floor(gy / TILE_M).astype(int)
    col = np.floor((gx - h * TILE_M) / PIX_M).astype(int)
    row = np.floor((gy - v * TILE_M) / PIX_M).astype(int)
    return h, v, row, col


def grid_to_latlon(h: int, v: int, row: np.ndarray, col: np.ndarray):
    """Centre (lat, lon) of cells (row, col) of tile (h, v)."""
    x = h * TILE_M + (np.asarray(col) + 0.5) * PIX_M - 18 * TILE_M
    y = 9 * TILE_M - (v * TILE_M + (np.asarray(row) + 0.5) * PIX_M)
    lat = np.degrees(y / R_EARTH)
    with np.errstate(divide="ignore", invalid="ignore"):
        lon = np.degrees(x / (R_EARTH * np.cos(np.radians(lat))))
    return lat, lon


def tile_id(h: int, v: int) -> str:
    return f"h{h:02d}v{v:02d}"


# ----------------------------------------------------------------------------------------------- polygons
def load_polygons(path: str = POLYGONS, only: set[str] | None = None) -> dict[str, list[list[np.ndarray]]]:
    """{lakeId: [polygon rings...]}; each polygon is [exterior, hole, hole...] as (N, 2) lon/lat arrays."""
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt") as f:
        fc = json.load(f)
    out: dict[str, list[list[np.ndarray]]] = {}
    for feat in fc["features"]:
        lake = feat["properties"]["id"]
        if only is not None and lake not in only:
            continue
        polys = _polygon_coords(feat["geometry"])
        if polys:
            out[lake] = [[np.asarray(ring, dtype=float)[:, :2] for ring in poly] for poly in polys]
    return out


def _polygon_coords(geom: dict) -> list:
    """Polygon coordinate lists from Polygon, MultiPolygon or GeometryCollection (other members ignored)."""
    t = geom.get("type")
    if t == "Polygon":
        return [geom["coordinates"]]
    if t == "MultiPolygon":
        return list(geom["coordinates"])
    if t == "GeometryCollection":
        out: list = []
        for g in geom.get("geometries", []):
            out.extend(_polygon_coords(g))
        return out
    return []


def _ring_contains(ring: np.ndarray, lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    """Even-odd ray casting, vectorised over the query points."""
    x, y = ring[:, 0], ring[:, 1]
    x2, y2 = np.roll(x, -1), np.roll(y, -1)
    inside = np.zeros(lon.shape, dtype=bool)
    for xa, ya, xb, yb in zip(x, y, x2, y2):
        if ya == yb:
            continue
        cond = (ya > lat) != (yb > lat)
        xint = xa + (lat - ya) * (xb - xa) / (yb - ya)
        inside ^= cond & (lon < xint)
    return inside


def polygons_contain(polys: list[list[np.ndarray]], lon: np.ndarray, lat: np.ndarray) -> np.ndarray:
    inside = np.zeros(lon.shape, dtype=bool)
    for poly in polys:
        p = _ring_contains(poly[0], lon, lat)
        for hole in poly[1:]:
            p &= ~_ring_contains(hole, lon, lat)
        inside |= p
    return inside


def bbox(polys: list[list[np.ndarray]]):
    ext = np.concatenate([poly[0] for poly in polys])
    return ext[:, 0].min(), ext[:, 1].min(), ext[:, 0].max(), ext[:, 1].max()


def _erode(mask: np.ndarray, px: int = 1) -> np.ndarray:
    """A cell survives only if every cell within px (8-neighbourhood) is also set; outside the array counts as unset."""
    out = mask.copy()
    if px <= 0:
        return out
    p = np.pad(mask, px, constant_values=False)
    n_r, n_c = mask.shape
    for dr in range(-px, px + 1):
        for dc in range(-px, px + 1):
            out &= p[px + dr: px + dr + n_r, px + dc: px + dc + n_c]
    return out


def _dilate(mask: np.ndarray, px: int) -> np.ndarray:
    out = mask.copy()
    if px <= 0:
        return out
    p = np.pad(mask, px, constant_values=False)
    n_r, n_c = mask.shape
    for dr in range(-px, px + 1):
        for dc in range(-px, px + 1):
            out |= p[px + dr: px + dr + n_r, px + dc: px + dc + n_c]
    return out


def _pure_water(polys, h: int, v: int, r0: int, r1: int, c0: int, c1: int):
    """(water, inside) masks for the cell window: `inside` = cell centre inside the outline; `water` = the centre AND all four
    cell corners inside, i.e. the whole 1 km footprint is water (no mixed shore pixel)."""
    rr, cc = np.mgrid[r0:r1 + 1, c0:c1 + 1]
    lat_c, lon_c = grid_to_latlon(h, v, rr, cc)
    inside = polygons_contain(polys, lon_c, lat_c)
    # corners: a (rows+1, cols+1) lattice offset by half a cell
    kr, kc = np.mgrid[r0:r1 + 2, c0:c1 + 2]
    lat_k, lon_k = grid_to_latlon(h, v, kr - 0.5, kc - 0.5)
    corner = polygons_contain(polys, lon_k, lat_k)
    water = inside & corner[:-1, :-1] & corner[1:, :-1] & corner[:-1, 1:] & corner[1:, 1:]
    return water, inside


def lake_windows(polys: list[list[np.ndarray]]) -> list[dict]:
    """The tile windows covering a lake, each with its pure-water cell mask.

    The window is padded by two cells beyond the outline's extent so the cloud distance can look at neighbours. A lake
    split across tile edges yields one window per tile."""
    # Every outline vertex plus the lon/lat box corners, in GLOBAL grid cells (row/col counted across all tiles). The image
    # of the outline bounds the image of the lake, so the global cell box of these points contains every lake cell.
    pts = np.concatenate([ring for poly in polys for ring in poly])
    w, s, e, n = bbox(polys)
    lons = np.concatenate([pts[:, 0], [w, e, w, e]])
    lats = np.concatenate([pts[:, 1], [s, s, n, n]])
    h, v, row, col = latlon_to_grid(lats, lons)
    grow, gcol = v * TILE_PX + row, h * TILE_PX + col
    gr0, gr1, gc0, gc1 = int(grow.min()) - 2, int(grow.max()) + 2, int(gcol.min()) - 2, int(gcol.max()) + 2
    windows = []
    for vv in range(gr0 // TILE_PX, gr1 // TILE_PX + 1):
        for hh in range(gc0 // TILE_PX, gc1 // TILE_PX + 1):
            r0 = max(gr0 - vv * TILE_PX, 0)
            r1 = min(gr1 - vv * TILE_PX, TILE_PX - 1)
            c0 = max(gc0 - hh * TILE_PX, 0)
            c1 = min(gc1 - hh * TILE_PX, TILE_PX - 1)
            if r0 > r1 or c0 > c1:
                continue
            water, inside = _pure_water(polys, hh, vv, r0, r1, c0, c1)
            if water.any():
                windows.append({"tile": tile_id(hh, vv), "h": hh, "v": vv, "r0": r0, "r1": r1, "c0": c0, "c1": c1,
                                "water": water, "insideCells": int(inside.sum())})
    return windows


# ----------------------------------------------------------------------------------------------- extraction
def qa_mandatory(qc: np.ndarray) -> np.ndarray:
    return np.asarray(qc).astype(np.int64) & 0b11


def k_to_f(k: float) -> float:
    return (k - FREEZE_K) * 9.0 / 5.0 + 32.0


def extract_lake(windows: list[dict], tiles: dict[str, dict], cloud_buffer_px: int = 2, min_pixels: int = 3) -> dict:
    """Combine one granule's tiles into one reading for one lake.

    tiles: {tileId: {"lstK": float array (NaN where missing), "qa": int array, "viewTimeH": float array or None}}
    """
    values, times = [], []
    water_cells = good_cells = 0
    seen_tile = False
    for w in windows:
        t = tiles.get(w["tile"])
        if t is None:
            continue
        seen_tile = True
        sl = (slice(w["r0"], w["r1"] + 1), slice(w["c0"], w["c1"] + 1))
        lst = t["lstK"][sl]
        qa = t["qa"][sl]
        cloud = (qa == QA_CLOUD) | (qa == QA_NOT_PRODUCED)
        near_cloud = _dilate(cloud, cloud_buffer_px)
        water = w["water"]
        ok = water & (qa == QA_GOOD) & ~near_cloud & np.isfinite(lst)
        water_cells += int(water.sum())
        good_cells += int(ok.sum())
        values.extend(lst[ok].tolist())
        vt = t.get("viewTimeH")
        if vt is not None:
            times.extend([x for x in vt[sl][ok].tolist() if math.isfinite(x)])
    rec: dict = {"waterCells": water_cells, "goodCells": good_cells}
    if not seen_tile:
        rec["status"] = "NO_TILE"
        return rec
    if good_cells < min_pixels:
        rec["status"] = "CLOUDY_OR_SPARSE" if water_cells else "NO_WATER_CELLS"
        return rec
    med = statistics.median(values)
    q1, q3 = np.percentile(values, [25, 75])
    rec.update({
        "status": "OK",
        "skinTempK": round(med, 2),
        "skinTempF": round(k_to_f(med), 1),
        "iqrK": round(float(q3 - q1), 2),
        "goodFraction": round(good_cells / water_cells, 3) if water_cells else 0.0,
        "possibleIce": bool(med <= FREEZE_K),
    })
    if times:
        rec["viewTimeLocalSolarH"] = round(statistics.median(times), 2)
    return rec


# ----------------------------------------------------------------------------------------------- HDF5 granules
def read_granule(path: str) -> dict:
    """Read LST_1KM, QC and View_Time from a VIIRS L3 1 km LST HDF5 tile. h5py is imported here only (tests don't need it)."""
    import h5py  # noqa: PLC0415

    found: dict[str, object] = {}

    def visit(name, obj):
        if isinstance(obj, h5py.Dataset):
            leaf = name.rsplit("/", 1)[-1].lower()
            if leaf in ("lst_1km", "qc", "view_time") and leaf not in found:
                found[leaf] = obj

    with h5py.File(path, "r") as f:
        f.visititems(visit)
        if "lst_1km" not in found or "qc" not in found:
            raise ValueError(f"{os.path.basename(path)}: LST_1KM/QC not found")
        lst_ds = found["lst_1km"]
        raw = lst_ds[()].astype(np.float64)
        scale = float(np.ravel(lst_ds.attrs.get("scale_factor", [LST_SCALE]))[0])
        offset = float(np.ravel(lst_ds.attrs.get("add_offset", [0.0]))[0])
        fill = np.ravel(lst_ds.attrs.get("_FillValue", [LST_FILL]))[0]
        lst = np.where(raw == fill, np.nan, raw * scale + offset)
        qa = qa_mandatory(found["qc"][()])
        vt = None
        if "view_time" in found:
            vds = found["view_time"]
            vraw = vds[()].astype(np.float64)
            vscale = float(np.ravel(vds.attrs.get("scale_factor", [0.1]))[0])
            vfill = np.ravel(vds.attrs.get("_FillValue", [255]))[0]
            vt = np.where(vraw == vfill, np.nan, vraw * vscale)
    return {"lstK": lst, "qa": qa, "viewTimeH": vt}


GRANULE_TILE = re.compile(r"\.(h\d{2}v\d{2})\.")


def granule_tile(name: str) -> str | None:
    m = GRANULE_TILE.search(name)
    return m.group(1) if m else None


# ----------------------------------------------------------------------------------------------- network
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        return None


def _token_allowed(url: str) -> bool:
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return urllib.parse.urlparse(url).scheme == "https" and any(host.endswith(h) or host == h.lstrip(".") for h in TOKEN_HOSTS)


def http_get(url: str, token: str | None, dest: str | None = None, tries: int = 3, timeout: int = 120) -> bytes | None:
    """GET following redirects by hand: the Earthdata token goes only to Earthdata hosts, never to the signed S3 URL."""
    opener = urllib.request.build_opener(_NoRedirect)
    last_err: Exception | None = None
    for attempt in range(tries):
        cur = url
        try:
            for _hop in range(8):
                req = urllib.request.Request(cur, headers={"User-Agent": USER_AGENT})
                if token and _token_allowed(cur):
                    req.add_unredirected_header("Authorization", f"Bearer {token}")
                try:
                    resp = opener.open(req, timeout=timeout)
                except urllib.error.HTTPError as e:
                    if e.code in (301, 302, 303, 307, 308) and e.headers.get("Location"):
                        cur = urllib.parse.urljoin(cur, e.headers["Location"])
                        continue
                    raise
                if dest is None:
                    return resp.read()
                tmp = dest + ".part"
                with open(tmp, "wb") as out:
                    while True:
                        chunk = resp.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                os.replace(tmp, dest)
                return None
            raise RuntimeError("too many redirects")
        except (urllib.error.URLError, TimeoutError, RuntimeError, OSError) as e:
            last_err = e
            code = getattr(e, "code", None)
            if code in (401, 403):
                break  # credential problem: retrying won't help
            time.sleep(2 * (attempt + 1))
    # never include the token: the message carries only the status/reason and the host
    host = urllib.parse.urlparse(url).hostname
    raise RuntimeError(f"download failed from {host}: {type(last_err).__name__} {getattr(last_err, 'code', '')}".strip())


def cmr_granules(product: str, day: dt.date, tiles: set[str], fetch=http_get) -> list[dict]:
    """Public CMR search for one product and one day, filtered to the tiles the lakes need."""
    q = {"short_name": product, "version": VERSION, "page_size": "2000",
         "temporal": f"{day.isoformat()}T00:00:00Z,{day.isoformat()}T23:59:59Z", "bounding_box": SEARCH_BOX}
    body = fetch(CMR + "?" + urllib.parse.urlencode(q), None)
    entries = json.loads(body)["feed"].get("entry", [])
    out = []
    for e in entries:
        tile = granule_tile(e.get("producer_granule_id") or e.get("title") or "")
        if tile is None or tile not in tiles:
            continue
        href = next((l["href"] for l in e.get("links", [])
                     if l.get("href", "").startswith("https://") and l.get("href", "").endswith((".h5", ".hdf"))
                     and "s3credentials" not in l["href"]), None)
        if href:
            out.append({"product": product, "tile": tile, "url": href, "name": href.rsplit("/", 1)[-1]})
    return out


# ----------------------------------------------------------------------------------------------- run
def run_day(day: dt.date, products: list[str], lake_windows_map: dict[str, list[dict]], cache: str, token: str | None,
            cloud_buffer_px: int, min_pixels: int, keep: bool, search_only: bool, fetch=http_get, reader=read_granule) -> dict:
    tiles_needed = {w["tile"] for ws in lake_windows_map.values() for w in ws}
    readings: list[dict] = []
    products_seen: dict[str, dict] = {}
    for product in products:
        granules = cmr_granules(product, day, tiles_needed, fetch=fetch)
        products_seen[product] = {"granules": len(granules), "tilesNeeded": len(tiles_needed)}
        if search_only or not granules:
            continue
        loaded: dict[str, dict] = {}
        failed = 0
        for g in granules:
            path = os.path.join(cache, g["name"])
            try:
                if not os.path.exists(path):
                    fetch(g["url"], token, dest=path)
                loaded[g["tile"]] = reader(path)
            except Exception as e:  # one bad tile must not sink the night
                failed += 1
                print(f"[skin-temp] {product} {g['tile']}: {e}", file=sys.stderr)
            finally:
                if not keep and os.path.exists(path):
                    os.remove(path)
        products_seen[product]["failedTiles"] = failed
        for lake, ws in lake_windows_map.items():
            rec = extract_lake(ws, loaded, cloud_buffer_px=cloud_buffer_px, min_pixels=min_pixels)
            if rec["status"] == "NO_TILE":
                continue
            rec.update({"lakeId": lake, "date": day.isoformat(), "product": product})
            readings.append(rec)
    return {"date": day.isoformat(), "products": products_seen, "readings": readings}


def _day_complete(path: str) -> bool:
    """A day is skipped only once every product delivered every needed tile; a partial day is re-run on the next night."""
    try:
        with open(path) as f:
            return bool(json.load(f).get("complete"))
    except (OSError, ValueError):
        return False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="per-run summary directory")
    ap.add_argument("--archive", required=True, help="durable per-day files: {archive}/YYYY/YYYY-MM-DD.json")
    ap.add_argument("--cache", required=True, help="download scratch (deleted after extraction unless --keep-downloads)")
    ap.add_argument("--date", help="one UTC date (YYYY-MM-DD); default: catch up --days-back days not yet archived")
    ap.add_argument("--days-back", type=int, default=14, help="catch-up window ending yesterday (UTC); the daily grids land about 6-10 days late")
    ap.add_argument("--products", default=",".join(DEFAULT_PRODUCTS))
    ap.add_argument("--lakes", default="", help="comma-separated lake ids (default: every lake with an outline)")
    ap.add_argument("--polygons", default=POLYGONS)
    ap.add_argument("--cloud-buffer-px", type=int, default=2)
    ap.add_argument("--min-pixels", type=int, default=3)
    ap.add_argument("--keep-downloads", action="store_true")
    ap.add_argument("--search-only", action="store_true", help="CMR search only: count granules, download nothing")
    ap.add_argument("--today", help=argparse.SUPPRESS)
    a = ap.parse_args(argv)

    token = os.environ.get("EARTHDATA_TOKEN") or None
    if not token and not a.search_only:
        print("EARTHDATA_TOKEN is not set (Pulse passes it from the Keychain item 'earthdata-token')", file=sys.stderr)
        return 2
    only = {x.strip() for x in a.lakes.split(",") if x.strip()} or None
    polys = load_polygons(a.polygons, only)
    lake_windows_map = {lake: lake_windows(p) for lake, p in polys.items()}
    no_cells = sorted(l for l, ws in lake_windows_map.items() if not ws)
    lake_windows_map = {l: ws for l, ws in lake_windows_map.items() if ws}

    today = dt.date.fromisoformat(a.today) if a.today else dt.datetime.now(dt.timezone.utc).date()
    if a.date:
        days = [dt.date.fromisoformat(a.date)]
    else:
        days = [today - dt.timedelta(days=k) for k in range(a.days_back, 0, -1)]
        days = [d for d in days if not _day_complete(os.path.join(a.archive, str(d.year), f"{d.isoformat()}.json"))]
    for d in (a.out, a.archive, a.cache):
        os.makedirs(d, exist_ok=True)

    started = time.time()
    summary = {"schema": SCHEMA, "startedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               "lakes": len(lake_windows_map), "lakesWithoutWaterCells": no_cells, "days": []}
    products = [p.strip() for p in a.products.split(",") if p.strip()]
    for day in days:
        res = run_day(day, products, lake_windows_map, a.cache, token, a.cloud_buffer_px, a.min_pixels,
                      a.keep_downloads, a.search_only)
        ok = sum(1 for r in res["readings"] if r["status"] == "OK")
        lakes_ok = len({r["lakeId"] for r in res["readings"] if r["status"] == "OK"})
        summary["days"].append({"date": res["date"], "products": res["products"], "okReadings": ok, "lakesWithReading": lakes_ok})
        if not a.search_only and any(v.get("granules") for v in res["products"].values()):
            ydir = os.path.join(a.archive, str(day.year))
            os.makedirs(ydir, exist_ok=True)
            complete = all(v.get("granules", 0) >= v.get("tilesNeeded", 0) and not v.get("failedTiles")
                           for v in res["products"].values())
            doc = {"schema": SCHEMA, "date": res["date"], "complete": complete, "products": res["products"],
                   "readings": res["readings"],
                   "rules": {"qa": "mandatory QA 00 only", "shore": "whole 1 km footprint inside the outline", "cloudBufferPx": a.cloud_buffer_px,
                             "minPixels": a.min_pixels, "statistic": "median"}}
            tmp = os.path.join(ydir, f".{res['date']}.json.part")
            with open(tmp, "w") as f:
                json.dump(doc, f, separators=(",", ":"))
            os.replace(tmp, os.path.join(ydir, f"{res['date']}.json"))
        print(f"[skin-temp] {res['date']}: {lakes_ok} lakes with a reading "
              f"({', '.join(f'{p}:{v.get('granules', 0)}' for p, v in res['products'].items())} granules)")
    summary["seconds"] = round(time.time() - started, 1)
    with open(os.path.join(a.out, "lake-skin-temp.json"), "w") as f:
        json.dump(summary, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
