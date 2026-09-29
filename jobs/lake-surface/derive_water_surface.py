"""Satellite water-surface fields for one lake: temperature and clarity.

Two maps Michael asked for (2026-09-26): "Water Temp" and "Water Clarity",
drawn across the whole lake the way Sector Intelligence is. Every constant
below was checked against the product documentation and the pixels themselves
on 2026-09-26; the findings are in docs/fishintel/WATER_SURFACE_LAYERS.md.

TEMPERATURE — Landsat 8/9 Collection 2 Level-2 Surface Temperature (ST_B10,
the `lwir11` asset), via Microsoft Planetary Computer. The only free thermal
imagery fine enough for creek arms: 100 m native, delivered at 30 m. MODIS and
Sentinel-3 are 1 km, wider than most of Guntersville. Path 020 row 036 covers
the whole lake; path 021 covers none of it.

  WHAT IT IS: one daytime pass (~11:18 CDT), the SKIN of the water, drawn as
  warmer or cooler than the rest of the lake that day. The app sets the level
  to tonight's lake-wide estimate and says the pattern is from that pass.

  WHAT IT IS NOT: tonight's temperature map. Landsat measures no surface
  temperature at night. Across six clear passes from June to September the
  warm and cool spots did not repeat from one pass to the next (500 m anomaly
  rank correlation -0.65 to +0.53), although undetected cloud on some passes
  confounds that test. The map therefore carries its date.

  ONE PASS, NEVER STITCHED: two afternoons' patterns side by side would draw
  a seam between two different days.

  THE SHORE IS CORRECTED, THEN THE REST IS FILLED. A thermal pixel is 100 m
  across and at 11 am the land (and topped-out grass inside the lake) is
  hotter than the water, so pixels near either read warm: +3.1 °C at 0-30 m
  from the NHD line on 3 Sep. thermal_shore.py removes the hot surfaces'
  share of each pixel (a fitted 60 m Gaussian PSF over Landsat's own
  non-water cells) and reads water down to a hot-surface weight of 0.10,
  about 95 m from them; it was checked to ±0.1 °C on held-out halves of the
  lake. Water it still cannot read (the bank band, grass beds, arms narrower
  than ~200 m, water under cloud) is filled by fill_lake.py through the water
  only, and the grid ships a second PNG saying which cells were measured.

  CLOUD THE MASK MISSES IS THE REAL ENEMY. On 11 Sep, pixels QA scored as
  clear read 4-10 °C cold at 2-6.6 km from any flagged cloud. The QA water
  bit is required (0 means "land OR cloud"), cloud distance must be >= 1 km,
  pixels far below the lake median are dropped, and a pass whose surviving
  open water still varies too much is rejected whole.

CLARITY — Sentinel-2 L2A, collection `sentinel-2-c1-l2a` on Element84 Earth
Search, where reflectance = DN * 0.0001 - 0.1. (The older `sentinel-2-l2a`
collection's COGs already have that offset removed although their metadata
still lists it; applying it there subtracts 0.1 twice and every water pixel
goes negative.) Turbidity from the red band with Dogliotti et al. (2015):
T = 228.1 * rho / (1 - rho / 0.1641) FNU. The NIR branch is NOT used: Sen2Cor
leaves a positive NIR bias over water and it read ~48 FNU against ~4.6 from
red on 20 Sep. Surface grass is left out (SCL water only, SWIR, FAI and NDVI
tests) and NOT filled from open water beside it — its clarity is unknown.

OUTPUT (each file ships in its own .xcassets data set)
  <out>.png   8-bit grayscale over an EPSG:3857 grid; 0 = no value,
              1..255 = the value, decoded with the JSON's `encoding`.
  <out>.json  the frame's corners, the encoding, the pass used, coverage and
              statistics.
  both fields also:
  <out>.measured.png  per cell: 255 measured, 2 estimated (cloud hid it),
              1 estimated (the satellite cannot read water there), 0 none
              (and, for clarity, grass).
  <out>.distance.png  per estimated cell: 1 + through-water metres to a
              measured cell / 100 (254 = beyond); 0 elsewhere.

usage:
  python derive_water_surface.py <waterbody.geojson> <outdir> [--lake Guntersville]
"""
import os, sys, json, time, math, urllib.request, argparse, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif,.TIF")

import numpy as np
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import reproject, transform_bounds
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import shape, mapping
from shapely.ops import transform as shp_transform, unary_union
import pyproj
from scipy import ndimage
from PIL import Image

import thermal_shore
import fill_lake

PC_SEARCH = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
PC_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token/landsat-c2-l2"
ES_SEARCH = "https://earth-search.aws.element84.com/v1/search"

WEB_MERCATOR = "EPSG:3857"
UTM = "EPSG:32616"          # Guntersville is in UTM 16N; metres for buffers.
CELL = 50.0                 # grid cell, web-mercator metres (~41 m on the ground here)
# Clarity is read at 10 m, so its grid is finer: 36 mercator m is ~30 m on
# the ground at this latitude, enough to show a plume's edge.
CLARITY_CELL = 36.0
LOOKBACK_DAYS = 40

# ---- temperature -----------------------------------------------------------
# A pass must read at least half of the open water (>= 300 m from the bank),
# the part no shore effect reaches, to be chosen.
OPEN_WATER_M = 300.0
# The main river channel for the whole-lake fill: its two ends, lon/lat.
LAKE_STEMS = {"Guntersville": ((-86.3931, 34.4236),    # Guntersville Dam
                               (-85.6203, 35.0021))}   # Nickajack Dam
ST_SCALE, ST_OFFSET = 0.00341802, 149.0     # lwir11 DN -> kelvin; DN 0 = nodata
QA_BAD = 0b11111            # fill, dilated cloud, cirrus, cloud, cloud shadow
QA_CLEAR, QA_WATER = 1 << 6, 1 << 7
# `cdist` (int16 x 0.01 km) and `qa` (ST_QA, int16 x 0.01 K). THE SCENE CHECK
# BELOW IS THE GUARD, NOT THESE. Popcorn cumulus sits near the lake on nearly
# every summer pass: 3 km kept 35% of the water on 3 Sep, 1 km kept 83%. Swept
# on the clean 3 Sep pass, 1 / 1.5 / 2 km all gave the same median (34.1 °C)
# and spread (0.53 °C), and none let in a single cold cell (its 0.3-0.4%
# outliers were all WARM water beside grass mats). On the contaminated 11 Sep
# pass every setting failed the scene check (8.5-10.5% of the water far below
# the median), which is what rejects it. The shore correction applies the
# same two gates as thermal_shore.MIN_CLOUD_KM / MAX_STQA_K; the asserts below
# keep the copies equal.
MIN_CLOUD_DIST_KM = 1.0
MAX_ST_UNCERTAINTY_K = 4.5  # clear water here reads 2.9-4.8 K (5th-95th)
assert MIN_CLOUD_DIST_KM == thermal_shore.MIN_CLOUD_KM
assert MAX_ST_UNCERTAINTY_K == thermal_shore.MAX_STQA_K
COLD_OUTLIER_C = 1.5        # below the lake median: undetected cloud, not water
WARM_OUTLIER_C = 3.0
SCENE_MAX_SD_C = 1.0        # a clean late-summer pass varies ~0.6 °C; more is cloud
SCENE_MAX_DROPPED = 0.05
# The scene check reads the product as delivered (no shore correction) over
# the lake eroded this far, the set its limits were tuned on (3 Sep kept,
# 11 Sep rejected). Run on the corrected, whole-lake read instead, the near-
# shore cells it adds dilute a cloud that sits over open water: a synthetic
# 6.3%-cold pass the old check rejected came out at 4.7% and was chosen.
SCENE_GUARD_STANDOFF_M = 200.0
# The fill's arm-warmth trend is fitted only on cells this far from any QA
# non-water: nearer, the trend partly learns the land and mats in the pixel
# (the slope fell from +1.01 to +0.92 °F with them left out; verify/trend.py).
FIT_FAR_FROM_NONWATER_M = 300.0
# A measured patch this small whose every cell sits near the hot-surface
# limit is as likely leftover bank in the pixel as warm water, and it would
# set the colour of the whole arm mouth around it.
MARGINAL_PATCH_CELLS = 100
MARGINAL_PATCH_MIN_W = 0.05
TEMP_SMOOTH_CELLS = 3       # ~300 m: three thermal pixels

# ---- clarity ---------------------------------------------------------------
S2_COLLECTION = "sentinel-2-c1-l2a"
S2_SCALE, S2_OFFSET = 0.0001, -0.1          # C1 only; see the module docstring
SCL_WATER = 6
SCL_CLOUDY = {0, 1, 3, 8, 9, 10, 11}        # no data, defective, shadow, cloud, cirrus, snow
S2_CLOUD_GROW_PX = 3                         # 60 m halo at 20 m
S2_SHORE_ERODE_PX = 2                        # 40 m off any non-water pixel
SWIR_MAX = 0.0215                            # ACOLITE's non-water / glint limit on B11
FAI_MAX = 0.005                              # floating algae index: surface grass above this
NDVI_MAX = 0.10
# SURFACE GRASS IS A PLANT'S SPECTRUM, NOT A THRESHOLD CROSSING. The two gates
# above keep a pixel out of the turbidity reading, and they used to CALL it
# grass too — which made haze and thin cloud over open water "grass": on
# 20 Sep hazy water ran NDVI 0.12-0.19 with SWIR 3-10x clean water's, the mats
# 0.47-0.60, and 36% of the lake came out grass with no clarity drawn on it.
GRASS_NDVI_MIN = 0.30
# Open water this bright in the SWIR that is not a plant is haze or thin cloud
# Sen2Cor did not flag (clean water sits near 0.008): hidden, like cloud,
# rather than "cannot be read here".
HAZE_SWIR = 0.02
# ...and the water at a haze's fringe reads muddy through it, the way the lit
# side of a cloud does: on 20 Sep, readings with SWIR above 0.010 ran 5.7-8.0
# FNU against 4.2 below 0.008, and 96-100% of them sat within 400 m of haze.
# Filled from, they coloured every hazy patch a muddy green.
HAZE_EDGE_M = 400.0
HAZE_EDGE_SWIR = 0.010
TURB_A, TURB_C = 228.1, 0.1641               # Dogliotti 2015, red
MIN_PASS_COVERAGE = 0.25                     # of the non-grass water 40 m in, for any pass to stand
TURB_SATURATED = 0.5 * TURB_C                # ACOLITE's validity limit on rho
TURB_SATURATED_FNU = 200.0                   # drawn at the muddy end, not dropped
BRIGHT_SWIR = 0.05                           # concrete, roofs, hulls — not water
BRIGHT_GROW_PX = 2                           # and 40 m round them
# A patch this much muddier than the water around it and this small is a
# structure or a boat's wake, not a plume: real plumes run hundreds of metres.
SPECK_LOG10 = 0.35                           # 2.2x the surrounding turbidity
SPECK_MAX_CELLS = 40                         # ~0.04 km2 at 30 m
GRASS_TO_BANK_M = 90.0                       # the 40 m strip behind a bed, and the ring beside it
# A MUDDY POCKET BESIDE A BED is the bed in the pixel — stems, a wake, stirred
# bottom — not the water. The muddiest readings of 20 Sep were all small
# patches touching grass (13 cells at 11.4 FNU, 11 at 9.7, 5 at 8.0, a third or
# more of each rim grass, against a lake median of 4.2), while pockets mostly
# ringed by grass read CLEARER than open water (median 2.4-2.8). The speck
# rule cannot see them: a pocket has no read water round it to compare with.
POCKET_MAX_CELLS = 40
POCKET_RIM_GRASS = 0.25
POCKET_LOG10 = 0.25                          # 1.8x the lake's median reading
GRASS_BORROW_DAYS = 10                       # grass under cloud from a pass this close
GRASS_BORROW_PASSES = 2


# ============================================================================
# Frame and masks
# ============================================================================

def to_crs(geom, src, dst):
    t = pyproj.Transformer.from_crs(src, dst, always_xy=True).transform
    return shp_transform(t, geom)


class Frame:
    """The EPSG:3857 grid every field is written on."""

    def __init__(self, lake_wgs, cell=CELL):
        merc = to_crs(lake_wgs, "EPSG:4326", WEB_MERCATOR)
        minx, miny, maxx, maxy = merc.bounds
        pad = 1_000.0
        self.cell = cell
        self.left = math.floor((minx - pad) / cell) * cell
        self.top = math.ceil((maxy + pad) / cell) * cell
        right = math.ceil((maxx + pad) / cell) * cell
        bottom = math.floor((miny - pad) / cell) * cell
        self.width = int(round((right - self.left) / cell))
        self.height = int(round((self.top - bottom) / cell))
        self.transform = from_origin(self.left, self.top, cell, cell)
        self.bounds = (self.left, bottom, right, self.top)

    def corners(self):
        """Top-left, top-right, bottom-right, bottom-left as [lon, lat] — the
        order Mapbox's ImageSource takes."""
        t = pyproj.Transformer.from_crs(WEB_MERCATOR, "EPSG:4326", always_xy=True).transform
        l, b, r, tp = self.bounds
        return [list(t(l, tp)), list(t(r, tp)), list(t(r, b)), list(t(l, b))]

    def burn(self, geom_merc, all_touched=False):
        return rasterize([(mapping(geom_merc), 1)], out_shape=(self.height, self.width),
                         transform=self.transform, fill=0, dtype="uint8",
                         all_touched=all_touched).astype(bool)

    def cell_of(self, lon, lat):
        x, y = pyproj.Transformer.from_crs("EPSG:4326", WEB_MERCATOR,
                                           always_xy=True).transform(lon, lat)
        return int((self.top - y) // self.cell), int((x - self.left) // self.cell)

    def cell_ground_m(self):
        """One cell's size on the ground: mercator metres shrink by cos(lat)."""
        l, b, r, t = self.bounds
        lat = pyproj.Transformer.from_crs(WEB_MERCATOR, "EPSG:4326",
                                          always_xy=True).transform((l + r) / 2, (b + t) / 2)[1]
        return self.cell * math.cos(math.radians(lat))


def lake_masks(lake_wgs, frame):
    lake_utm = to_crs(lake_wgs, "EPSG:4326", UTM)
    def merc(g): return to_crs(g, UTM, WEB_MERCATOR)
    return {
        "lake": frame.burn(merc(lake_utm)),
        # Where a value may be FILLED: the lake and a little past its line, so
        # the app's own coastline never meets an empty cell beside read water.
        "reach": frame.burn(merc(lake_utm.buffer(100.0))),
        # Every cell the polygon touches: rejoins the pieces a centre burn cuts
        # off through channels narrower than a cell.
        "lake_touch": frame.burn(merc(lake_utm), all_touched=True),
        "open": frame.burn(merc(lake_utm.buffer(-OPEN_WATER_M))),
        "guard": frame.burn(merc(lake_utm.buffer(-SCENE_GUARD_STANDOFF_M))),
        "clarity": frame.burn(merc(lake_utm.buffer(-40.0))),
    }


# ============================================================================
# Catalog
# ============================================================================

def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))


def passes(search_url, collection, bbox, until, max_cloud):
    since = (until - dt.timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT00:00:00Z")
    body = {"collections": [collection], "bbox": bbox,
            "datetime": f"{since}/{until.strftime('%Y-%m-%dT23:59:59Z')}",
            "limit": 200, "sortby": [{"field": "properties.datetime", "direction": "desc"}]}
    by = {}
    for f in post(search_url, body)["features"]:
        # One PASS is one satellite on one day: Sentinel-2's tiles, or
        # Landsat's rows on one path, are one look at the lake.
        key = (f["properties"]["datetime"][:10], f["properties"].get("platform", ""))
        by.setdefault(key, []).append(f)
    out = []
    for k in sorted(by, key=lambda k: k[0], reverse=True):
        cc = [i["properties"].get("eo:cloud_cover", 0) for i in by[k]]
        if min(cc) <= max_cloud:
            out.append((k, by[k]))
    return out


_token = {"t": None, "at": 0}
def pc_sign(href):
    # Anonymous Planetary Computer tokens last 45 minutes.
    if _token["t"] is None or time.time() - _token["at"] > 1_500:
        _token["t"] = json.load(urllib.request.urlopen(PC_TOKEN, timeout=60))["token"]
        _token["at"] = time.time()
    return href + ("&" if "?" in href else "?") + _token["t"]


# ============================================================================
# Reading
# ============================================================================

def read_window(href, frame_bounds_merc, out_shape_div=1):
    """The part of a COG under the lake's frame, in the COG's own CRS."""
    src = rasterio.open(href)
    b = transform_bounds(WEB_MERCATOR, src.crs, *frame_bounds_merc, densify_pts=21)
    win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
    win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
    if out_shape_div > 1:
        shp = (max(1, int(win.height // out_shape_div)), max(1, int(win.width // out_shape_div)))
        arr = src.read(1, window=win, out_shape=shp, resampling=Resampling.average)
        tr = src.window_transform(win) * rasterio.Affine.scale(win.width / shp[1],
                                                               win.height / shp[0])
        return src, arr, tr
    return src, src.read(1, window=win), src.window_transform(win)


def to_grid(values, src_transform, src_crs, frame):
    out = np.full((frame.height, frame.width), np.nan, dtype="float32")
    reproject(source=values.astype("float32"), destination=out,
              src_transform=src_transform, src_crs=src_crs, src_nodata=np.nan,
              dst_transform=frame.transform, dst_crs=WEB_MERCATOR, dst_nodata=np.nan,
              resampling=Resampling.average)
    return out


def grow(mask, px):
    return ndimage.binary_dilation(mask, iterations=px) if px > 0 else mask


def scene_check(raw, guard):
    """Undetected-cloud guard on the UNCORRECTED product over `guard`."""
    raw = np.where(guard, raw, np.nan)
    known = ~np.isnan(raw)
    if known.sum() < 1_000:
        return {"ok": False, "why": f"{known.sum()} clean open-water cells for the scene check"}
    med = float(np.median(raw[known]))
    cold = known & (raw < med - COLD_OUTLIER_C)
    warm = known & (raw > med + WARM_OUTLIER_C)
    dropped = (cold | warm).sum() / known.sum()
    sd = float(np.nanstd(np.where(cold | warm, np.nan, raw)))
    v = {"ok": bool(sd <= SCENE_MAX_SD_C and dropped <= SCENE_MAX_DROPPED),
         "medianC": round(med, 2), "sdC": round(sd, 2),
         "droppedPct": round(100 * float(dropped), 1),
         "coldPct": round(100 * float(cold.sum() / known.sum()), 1),
         "warmPct": round(100 * float(warm.sum() / known.sum()), 1),
         "on": f"uncorrected product, lake eroded {SCENE_GUARD_STANDOFF_M:g} m"}
    if not v["ok"]:
        v["why"] = (f"open water varies {sd:.2f} °C (limit {SCENE_MAX_SD_C}) after dropping "
                    f"{100 * dropped:.1f}% (limit {100 * SCENE_MAX_DROPPED:.0f}%; "
                    f"{v['coldPct']}% cold, {v['warmPct']}% warm)")
    return v


def landsat_pass(items, frame, measurable, lake_wgs, guard):
    """One Landsat pass on the grid, °C with the shore's hot share removed, NaN
    where not clean water; per-cell fields the fill needs (`aux`); and the
    scene check's verdict, which is taken on the product as delivered, not on
    the correction.

    aux["hidden"]  share of the cell's lake that the geometry would let be
                   read (little hot surface in the PSF, not non-water) but
                   cloud or the QA gates hid — "cloud hid it", not "can't read"
    aux["w"]       mean hot-surface weight of the cell's lake
    aux["far"]     share of the cell's lake >= 300 m from any QA non-water"""
    shape = (frame.height, frame.width)
    acc = np.full(shape, np.nan, dtype="float32")
    raw = np.full(shape, np.nan, dtype="float32")
    aux = {k: np.full(shape, np.nan, dtype="float32") for k in ("hidden", "w", "far")}
    for it in items:
        a = it["assets"]
        try:
            src, st, tr = read_window(pc_sign(a["lwir11"]["href"]), frame.bounds)
            _, qa, _ = read_window(pc_sign(a["qa_pixel"]["href"]), frame.bounds)
            _, cdist, _ = read_window(pc_sign(a["cdist"]["href"]), frame.bounds)
            _, stqa, _ = read_window(pc_sign(a["qa"]["href"]), frame.bounds)
            _, emis, _ = read_window(pc_sign(a["emis"]["href"]), frame.bounds)
        except Exception as e:      # a failed scene is a gap, not a crash
            print(f"    ! {it['id']}: {e}")
            continue
        if st.size == 0:
            continue
        lake_native = rasterize([(mapping(to_crs(lake_wgs, "EPSG:4326", str(src.crs))), 1)],
                                out_shape=st.shape, transform=tr, fill=0,
                                dtype="uint8").astype(bool)
        if not (lake_native & (st > 0)).any():     # a neighbouring path's edge
            continue
        # The scene check's input: clear QA water, the same cloud-distance and
        # ST-uncertainty gates, and nothing else done to it.
        ok = ((st > 0) & ((qa & QA_BAD) == 0) & ((qa & QA_CLEAR) != 0) & ((qa & QA_WATER) != 0)
              & (cdist != -9999) & (cdist * 0.01 >= MIN_CLOUD_DIST_KM)
              & (stqa != -9999) & (stqa * 0.01 <= MAX_ST_UNCERTAINTY_K))
        c_raw = np.where(ok, st.astype("float32") * ST_SCALE + ST_OFFSET - 273.15, np.nan)
        raw = np.where(np.isnan(raw), to_grid(c_raw, tr, src.crs, frame), raw)
        corr = thermal_shore.correct_water_temp(
            st, qa, cdist, stqa, emis, lake_native, return_all=True,
            platform=it["properties"].get("platform", "landsat-8"), drop_outliers=False)
        print(f"    {it['id']}: shore-corrected, {int(corr['trusted'].sum()):,} native cells read")
        c = corr["T_water"].astype("float32")
        g = to_grid(c, tr, src.crs, frame)
        acc = np.where(np.isnan(acc), g, acc)
        # Hidden = readable by geometry alone: in the lake, not QA non-water
        # (land, grass), little hot surface in the PSF. A cloud pixel is
        # invalid rather than non-water, so water under cloud counts here.
        nonwater = corr["valid"] & ~corr["water"]
        geo_ok = lake_native & ~nonwater & (corr["w"] <= thermal_shore.W_MAX)
        fields = {"hidden": geo_ok & ~corr["trusted"], "w": corr["w"],
                  "far": corr["d_nw"] >= FIT_FAR_FROM_NONWATER_M}
        for k, f in fields.items():
            src_v = np.where(lake_native, f.astype("float32"), np.nan)
            aux[k] = np.where(np.isnan(aux[k]), to_grid(src_v, tr, src.crs, frame), aux[k])
    acc[~measurable] = np.nan
    verdict = scene_check(raw, guard)
    known = ~np.isnan(acc)
    if known.sum() == 0:
        return acc, aux, verdict
    # The map still loses corrected cells far from the corrected median
    # (cloud the guard tolerated, or a shore cell the correction missed).
    med = float(np.median(acc[known]))
    cold = known & (acc < med - COLD_OUTLIER_C)
    bad = cold | (known & (acc > med + WARM_OUTLIER_C))
    verdict["mapDroppedPct"] = round(100 * float(bad.sum() / known.sum()), 1)
    acc[bad] = np.nan
    # Cells dropped as too cold are undetected cloud: hidden, not unreadable.
    # A warm outlier is a dock, a boat or a mat, and stays "can't read".
    aux["hidden"][cold] = 1.0
    return acc, aux, verdict


TILE_FEATHER_M = 2_000.0    # tiles blend across their overlap, not at a line

# Clarity is read at Sentinel-2's NATIVE 10 m red, each gate applied per 10 m
# pixel, then averaged onto the frame (scratchpad study clarfill/shore/, 20 Sep
# 2026). Against the old 20 m read it reads LESS of the lake (40% vs 48%)
# and drops what read muddy for the wrong reason: water beside bridges and
# marinas, and beside cloud Sen2Cor missed, read +4% (p90 1.34x) above its
# surroundings.
S2_NATIVE_PX = 10.0
S2_BANK_STANDOFF_M = 10.0       # only the pixel touching an SCL bank pixel is dropped
S2_CLOUD_STANDOFF_M = 60.0      # from SCL cloud / shadow / cirrus / no data
S2_STRUCTURE_STANDOFF_M = 100.0 # from bright non-vegetated land: concrete, roofs, decks
S2_HAZE_STANDOFF_M = 100.0      # from bright "water": hulls, and cloud SCL missed
S2_STRUCTURE_NDVI_MAX = 0.30
S2_MIN_CELL_FRAC = 0.25         # of a frame cell's 10 m pixels readable, or no reading
S2_SCL_BANK = (2, 4, 5, 7)      # dark area, vegetation, bare, unclassified
# Water near cloud reflects shortwave it should not (SWIR16 0.013 within
# 150 m of SCL cloud against 0.007 3-10 km out) and reads muddier with it
# (r = 0.55): thin cloud and haze at the cloud's edge. The mid-lake gap on
# 20 Sep filled from those edges came out 7.8 FNU; without them, 5.7.
S2_CLOUD_EDGE_M = 1_500.0
S2_CLOUD_EDGE_SWIR = 0.012
# ...but only out on open water, where the land's own shortwave glow (it
# lifts water SWIR above 0.012 within ~100 m of a bank) cannot pass for haze,
# and only near a real cloud: a handful of stray SCL cloud pixels (11 of them
# over downtown Guntersville on 20 Sep) must not switch the gate on for 1.5 km.
S2_CLOUD_EDGE_OFFSHORE_M = 100.0
S2_REAL_CLOUD_MIN_PX20 = 25     # 1 ha of 20 m SCL cloud/shadow
# Water this close to a REAL cloud is not a reading at all, on either side:
# the lit side reads muddy through haze (the mid-lake gap filled at 6.7 FNU
# from its edges against 4.8 in the clear water 1.2-5 km out), and the shadow
# side reads too clear (every measured cell under 2 FNU sat within 1.5 km of
# cloud or shadow, 42% within 600 m, against 7% of all readings).
S2_REAL_CLOUD_STANDOFF_M = 600.0
# ...and within the 1.5 km beyond it, a patch this much CLEARER than the
# water round it is shadow, the way a muddy speck is a structure.
S2_SHADOW_SPECK_LOG10 = 0.15
# Readings of fewer than this many cells anchor nothing: one or two cells in
# a grass mat coloured whole creek networks (2,648 cells from a 2-cell read).
S2_MIN_PATCH_CELLS = 5
# Sen2Cor sets each tile's aerosol on its own (20 Sep: AOT 0.28 on SED, 0.20
# on SEC and SFD), so the same water reads 1.36x and 1.74x apart in two
# tiles. Each tile is put on the level of the tile that reads most of the
# lake, from the water both read, before they are blended.
S2_TILE_MATCH_MIN_CELLS = 200
S2_TILE_OFFSET_WARN_LOG10 = 0.04    # 10%


def _edge_dist_px(mask):
    """Pixels from each pixel centre to the nearest EDGE of a mask pixel
    (adjacent = 0.5, second = 1.5); 0 on the mask; +inf if the mask is empty."""
    if not mask.any():
        return np.full(mask.shape, np.inf, "float32")
    e = ndimage.distance_transform_edt(~mask).astype("float32")
    e -= 0.5
    e[mask] = 0
    return e


def _read_s2_native(item, frame_bounds, rededge=False):
    """The tile under the frame: SCL/B8A/B11 at 20 m and B04 at 10 m on
    exactly nested windows (the 10 m window is the 20 m one doubled).
    rededge: also B05 at 20 m, for the algal-water check (Stage 8)."""
    a = item["assets"]
    src = rasterio.open(a["scl"]["href"])
    b = transform_bounds(WEB_MERCATOR, src.crs, *frame_bounds, densify_pts=21)
    win = from_bounds(*b, transform=src.transform).round_offsets().round_lengths()
    win = win.intersection(rasterio.windows.Window(0, 0, src.width, src.height))
    scl = src.read(1, window=win)
    tr20 = src.window_transform(win)
    n8a = rasterio.open(a["nir08"]["href"]).read(1, window=win)
    sw = rasterio.open(a["swir16"]["href"]).read(1, window=win)
    rs = rasterio.open(a["red"]["href"])
    w10 = rasterio.windows.Window(2 * win.col_off, 2 * win.row_off, 2 * win.width, 2 * win.height)
    red = rs.read(1, window=w10)
    # B05 (705 nm) for the algal-water check (NDCI); it never touches turbidity.
    re1 = rasterio.open(a["rededge1"]["href"]).read(1, window=win) if rededge and "rededge1" in a else None
    return {"scl": scl, "nir08": n8a, "swir16": sw, "red": red, "rededge1": re1, "tr20": tr20,
            "tr10": rs.window_transform(w10), "crs": src.crs}


def _s2_native_fields(t):
    """On the tile's 10 m grid: turbidity (FNU, NaN = not read), the grass
    indicator and the cloud-hidden indicator (NaN where not seen), and the
    readable indicator (NaN off the tile)."""
    h, w = t["red"].shape
    up = lambda x: np.repeat(np.repeat(x, 2, axis=0), 2, axis=1)[:h, :w]
    def rho(dn):
        r = dn.astype("float32") * S2_SCALE + S2_OFFSET
        r[(dn == 0) | (dn == 65535)] = np.nan
        return r
    scl = up(t["scl"])
    r_red = rho(t["red"])
    r_nir, r_sw = up(rho(t["nir08"])), up(rho(t["swir16"]))
    water = scl == SCL_WATER
    with np.errstate(invalid="ignore", divide="ignore"):
        fai = r_nir - (r_red + (r_sw - r_red) * (865 - 665) / (1610 - 665))
        ndvi = (r_nir - r_red) / np.maximum(1e-6, r_nir + r_red)
        bright = np.nan_to_num(r_sw, nan=0) > BRIGHT_SWIR
        veg = ndvi >= GRASS_NDVI_MIN
        haze_px = water & (r_sw > HAZE_SWIR) & ~veg
    structure = bright & (np.nan_to_num(ndvi, nan=1.0) < S2_STRUCTURE_NDVI_MAX) & ~water
    haze = bright & water
    bank = np.isin(scl, S2_SCL_BANK)
    px = S2_NATIVE_PX
    to_bank, to_structure = _edge_dist_px(bank), _edge_dist_px(structure)
    # No data (a swath edge) is "not seen", not cloud.
    cloudy_classes = [c for c in SCL_CLOUDY if c != 0]
    to_cloud = _edge_dist_px(np.isin(scl, cloudy_classes))
    clear = to_cloud >= S2_CLOUD_STANDOFF_M / px
    # Real cloud, for "near cloud": SCL cloud/shadow patches of at least a
    # hectare, found on the 20 m grid and brought up to 10 m.
    cl20 = np.isin(t["scl"], cloudy_classes)
    lab, n = ndimage.label(cl20)
    if n:
        sizes = ndimage.sum(cl20, lab, index=np.arange(1, n + 1))
        real20 = np.isin(lab, np.nonzero(sizes >= S2_REAL_CLOUD_MIN_PX20)[0] + 1)
    else:
        real20 = cl20
    to_real = _edge_dist_px(up(real20))
    near_cloud = to_real < S2_CLOUD_EDGE_M / px
    under_cloud = to_real < S2_REAL_CLOUD_STANDOFF_M / px
    offshore = ((to_bank >= S2_CLOUD_EDGE_OFFSHORE_M / px)
                & (to_structure >= S2_CLOUD_EDGE_OFFSHORE_M / px))
    with np.errstate(invalid="ignore"):
        cloud_edge = near_cloud & offshore & (r_sw > S2_CLOUD_EDGE_SWIR)
        haze_edge = ((_edge_dist_px(haze_px) < HAZE_EDGE_M / px) & offshore
                     & (r_sw > HAZE_EDGE_SWIR))
    beside_bright = _edge_dist_px(haze) < S2_HAZE_STANDOFF_M / px
    unhazed = ~beside_bright & ~cloud_edge & ~haze_edge
    ok = water & clear & ~under_cloud & unhazed
    ok &= to_bank >= S2_BANK_STANDOFF_M / px
    ok &= to_structure >= S2_STRUCTURE_STANDOFF_M / px
    with np.errstate(invalid="ignore"):
        ok &= (r_sw <= SWIR_MAX) & (fai <= FAI_MAX) & (ndvi <= NDVI_MAX) & (r_red > 0)
    rr = np.clip(np.nan_to_num(r_red, nan=0), 0, None)
    fnu = np.where(rr >= TURB_SATURATED, TURB_SATURATED_FNU,
                   TURB_A * rr / np.maximum(1e-6, 1 - rr / TURB_C)).astype("float32")
    fnu[~ok] = np.nan
    seen = (scl > 0) & clear
    gfrac = np.where(seen, veg.astype("float32"), np.nan).astype("float32")
    readable = np.where(scl > 0, ok.astype("float32"), np.nan).astype("float32")
    # Hidden by cloud: a real cloud and its standoff, the hazy cloud edge,
    # bright "water" near a real cloud (cloud SCL missed), and hazy open water
    # anywhere (`HAZE_SWIR`) — as a share of what is not bank. Stray SCL "cloud" pixels (roofs, hulls) and bright "water"
    # away from cloud are structures: that water is unreadable, not hidden.
    hidden = np.where((scl > 0) & ~bank,
                      (under_cloud | cloud_edge | (beside_bright & near_cloud)
                       | ((haze_px | haze_edge) & offshore)).astype("float32"),
                      np.nan).astype("float32")
    near = np.where(scl > 0, near_cloud.astype("float32"), np.nan).astype("float32")
    return fnu, gfrac, readable, hidden, near


def _cell_ndci(t, fnu, frame):
    """NDCI = (B05 - B04) / (B05 + B04) on the frame's cells, from the mean
    reflectance of the SAME 10 m pixels the turbidity read (NaN where none).
    None when the item has no red-edge band. Clarity Stage 8: the algal-water
    reliability warning (NDCI > 0.03) reads this; turbidity never does."""
    if t.get("rededge1") is None:
        return None
    h, w = t["red"].shape
    ok = np.isfinite(fnu)
    def rho(dn):
        r = dn.astype("float32") * S2_SCALE + S2_OFFSET
        r[(dn == 0) | (dn == 65535)] = np.nan
        return r
    red = rho(t["red"]); red[~ok] = np.nan
    g_red = to_grid(red, t["tr10"], t["crs"], frame)
    del red
    re1 = np.repeat(np.repeat(rho(t["rededge1"]), 2, axis=0), 2, axis=1)[:h, :w]
    re1[~ok] = np.nan
    g_re = to_grid(re1, t["tr10"], t["crs"], frame)
    del re1
    with np.errstate(invalid="ignore", divide="ignore"):
        s = g_re + g_red
        nd = np.where(s > 1e-6, (g_re - g_red) / s, np.nan).astype("float32")
    return nd


# The algal-water product: NDCI per cell, 0 = none, else 1 + (NDCI + 0.30) / 0.0025
# (0.0025 steps, -0.30 .. +0.3325; the 0.03 rule sits exactly on code 133).
NDCI_LO, NDCI_STEP = -0.30, 0.0025
NDCI_CARRY_M = 500.0     # an estimated cell takes its nearest reading's NDCI this close


def write_ndci(path, nd, measured, dist_to_reading_m, lake, cell_m):
    """Measured cells keep their own NDCI; an estimated cell of the lake takes
    the NDCI of the nearest measured cell when that reading is within
    NDCI_CARRY_M both in a straight line and through the water. Everything
    else has none (0). Returns (measured cells with NDCI, cells carried)."""
    have = measured & np.isfinite(nd)
    out = np.full(nd.shape, np.nan, dtype="float32")
    out[have] = nd[have]
    carried = np.zeros(nd.shape, dtype=bool)
    if have.any():
        edt, (ir, ic) = ndimage.distance_transform_edt(~have, return_indices=True)
        with np.errstate(invalid="ignore"):
            carried = (lake & ~have & (edt * cell_m <= NDCI_CARRY_M)
                       & (np.nan_to_num(dist_to_reading_m, nan=np.inf) <= NDCI_CARRY_M))
        out[carried] = nd[ir[carried], ic[carried]]
    q = np.zeros(nd.shape, dtype="uint8")
    ok = np.isfinite(out)
    q[ok] = np.clip(np.round((out[ok] - NDCI_LO) / NDCI_STEP) + 1, 1, 254).astype("uint8")
    Image.fromarray(q, mode="L").save(path, optimize=True)
    return int(have.sum()), int(carried.sum())


class PassRejected(Exception):
    """A pass that cannot be read: skip it, keep going."""


def s2_pass(items, frame, measurable, grass_mask, ndci=False):
    """One Sentinel-2 pass on the frame: FNU (NaN = not read), the grass class
    (bool), and `aux` — per-cell "gfrac" (share of seen pixels that are plant)
    and "hidden" (share of non-bank pixels cloud hid).

    measurable  frame cells that may carry a turbidity: the whole lake (the
                shore standoff happens per 10 m pixel).
    grass_mask  frame cells that may be called grass (the lake eroded 40 m).

    TILES ARE BLENDED, NOT STACKED. Sen2Cor corrects each 110 km tile on its
    own aerosol estimate, so the same water reads a little differently in two
    overlapping tiles. Taking one tile wherever it had data drew a straight
    seam across the lake at every tile edge (20 Sep: one along a row
    boundary, one along the UTM 600 km line). Each tile's reading is weighted
    by its distance in from its own edge, so a tile fades out across the
    overlap instead of stopping at a line.
    """
    H, W = frame.height, frame.width
    z = lambda: np.zeros((H, W))
    gnum, gden, hnum, hden, nnum, nden = z(), z(), z(), z(), z(), z()
    ndnum, ndden = z(), z()
    swir_check = []
    tiles = []      # (id, log10 FNU where read, feather weight)
    for it in items:
        try:
            t = _read_s2_native(it, frame.bounds, rededge=ndci)
        except Exception as e:      # a failed scene is a gap, not a crash
            print(f"    ! {it['id']}: {e}")
            continue
        if t["red"].size == 0 or t["scl"].size == 0:
            continue
        water20 = t["scl"] == SCL_WATER
        if water20.sum() > 1_000:
            swir_check.append(float(np.median(t["swir16"][water20])))
        fnu, gfrac, readable, hidden, near = _s2_native_fields(t)
        g = to_grid(fnu, t["tr10"], t["crs"], frame)            # mean over readable pixels
        frac = to_grid(readable, t["tr10"], t["crs"], frame)    # readable share of the cell
        shares = [to_grid(f, t["tr10"], t["crs"], frame) for f in (gfrac, hidden, near)]
        nd_cells = _cell_ndci(t, fnu, frame) if ndci else None
        del fnu, gfrac, readable, hidden, near, t["red"]
        foot = to_grid(np.where(t["scl"] > 0, 1.0, np.nan).astype("float32"),
                       t["tr20"], t["crs"], frame)
        inside = ~np.isnan(foot)
        wgt = np.clip(ndimage.distance_transform_edt(inside) * frame.cell / TILE_FEATHER_M, 0, 1)
        with np.errstate(invalid="ignore"):
            have = ~np.isnan(g) & (np.nan_to_num(frac) >= S2_MIN_CELL_FRAC) & measurable
        # In log space: turbidity blends evenly there.
        glog = np.where(have, np.log10(np.maximum(g, 0.05)), np.nan).astype("float32")
        tiles.append((it["id"], glog, wgt))
        for f, n_, d_ in zip(shares, (gnum, hnum, nnum), (gden, hden, nden)):
            fh = ~np.isnan(f)
            n_[fh] += wgt[fh] * f[fh]
            d_[fh] += wgt[fh]
        if nd_cells is not None:
            nh = have & ~np.isnan(nd_cells)
            ndnum[nh] += wgt[nh] * nd_cells[nh]
            ndden[nh] += wgt[nh]
    offsets = match_tiles(tiles)
    num, den = z(), z()
    for (tid, glog, wgt) in tiles:
        have = ~np.isnan(glog)
        num[have] += wgt[have] * (glog[have] + offsets[tid]["log10"])
        den[have] += wgt[have]
    acc = np.full((H, W), np.nan, dtype="float32")
    ok_w = den > 1e-6
    acc[ok_w] = (10 ** (num[ok_w] / den[ok_w])).astype("float32")
    # Fail loudly if the collection's offset convention ever changes: open
    # water's SWIR is ~0 reflectance, so its median DN sits just above 1000.
    if swir_check and not (900 <= np.median(swir_check) <= 1_500):
        # One glinty or hazy pass can read this bright; a changed convention
        # would fail EVERY pass, which the caller sees as no usable pass.
        raise PassRejected(f"SWIR DN over water is {np.median(swir_check):.0f}; expected "
                           f"~1000-1100 for {S2_COLLECTION}")
    acc[~measurable] = np.nan
    share = lambda n_, d_: np.where(d_ > 1e-6, n_ / np.maximum(d_, 1e-9), np.nan).astype("float32")
    aux = {"gfrac": share(gnum, gden), "hidden": share(hnum, hden),
           "near": share(nnum, nden), "tileOffsets": offsets}
    # NDCI where the turbidity was read, tiles feathered the same way (no level
    # matching: it is a band ratio, and the offsets are turbidity's).
    if ndci:
        nd = share(ndnum, ndden)
        nd[np.isnan(acc)] = np.nan
        aux["ndci"] = nd
    grass = (np.nan_to_num(aux["gfrac"]) >= 0.5) & grass_mask & np.isnan(acc)
    return acc, grass, aux


def match_tiles(tiles):
    """A log10 offset per tile that puts it on the level of the tile reading
    the most of the lake, fitted on the frame cells both read (median of the
    difference), and chained through the tiles already placed. A tile that
    shares no water with a placed one keeps its own level, and says so."""
    if not tiles:
        return {}
    counts = {tid: int((~np.isnan(g)).sum()) for tid, g, _ in tiles}
    ref = max(counts, key=counts.get)
    off = {ref: {"log10": 0.0, "cells": 0, "against": None}}
    todo = [t for t in tiles if t[0] != ref]
    placed = [t for t in tiles if t[0] == ref]
    while todo:
        best = None
        for tid, g, _ in todo:
            for pid, pg, _ in placed:
                both = ~np.isnan(g) & ~np.isnan(pg)
                n = int(both.sum())
                if n >= S2_TILE_MATCH_MIN_CELLS and (best is None or n > best[3]):
                    d = float(np.median((pg + off[pid]["log10"])[both] - g[both]))
                    best = (tid, pid, d, n)
        if best is None:
            for tid, _, _ in todo:
                off[tid] = {"log10": 0.0, "cells": 0, "against": None,
                            "note": "no water shared with the other tiles; own level kept"}
            break
        tid, pid, d, n = best
        off[tid] = {"log10": round(d, 4), "cells": n, "against": pid}
        warn = "  (!) more than 10%" if abs(d) > S2_TILE_OFFSET_WARN_LOG10 else ""
        print(f"    tile {tid}: x{10 ** d:.3f} to match {pid} on {n:,} shared cells{warn}")
        placed += [t for t in todo if t[0] == tid]
        todo = [t for t in todo if t[0] != tid]
    return off


# ============================================================================
# Fill, encode, write
# ============================================================================

def smooth_known(v, sigma):
    """Gaussian smoothing that ignores the gaps rather than pulling toward 0."""
    known = ~np.isnan(v)
    vs = ndimage.gaussian_filter(np.where(known, v, 0).astype("float64"), sigma)
    ws = ndimage.gaussian_filter(known.astype("float64"), sigma)
    out = np.where(known, vs / np.maximum(ws, 1e-9), np.nan)
    return out.astype("float32")


def drop_specks(values, min_cells):
    """Read patches too small to stand for any water but themselves — a few
    cells between two clouds. Filled outward they became round blobs of one
    reading painted over water nobody read."""
    known = ~np.isnan(values)
    lab, n = ndimage.label(known)
    if n == 0:
        return values
    sizes = ndimage.sum(known, lab, index=np.arange(1, n + 1))
    small = np.isin(lab, np.nonzero(sizes < min_cells)[0] + 1)
    out = values.copy()
    out[small] = np.nan
    print(f"    specks dropped: {int(small.sum()):,} cells in {int((sizes < min_cells).sum())} patches")
    return out


def fill(values, reach, sigmas, min_weight=0.05):
    """Normalized convolution, finest first: each gap takes the read water
    nearest it, and nothing is filled further out than the largest kernel."""
    out = values.copy()
    known = ~np.isnan(out)
    for s in sigmas:
        v = np.where(known, out, 0).astype("float64")
        w = known.astype("float64")
        vs = ndimage.gaussian_filter(v, s, mode="constant")
        ws = ndimage.gaussian_filter(w, s, mode="constant")
        new = (~known) & reach & (ws > min_weight)
        out[new] = (vs[new] / ws[new]).astype("float32")
        known |= new
    return out


def drop_marginal_patches(values, w):
    """Small measured patches whose every cell sits near the hot-surface
    limit: as likely leftover bank or mat in the pixel as warm water, and the
    fill would carry one such patch across a whole arm mouth."""
    known = ~np.isnan(values)
    lab, n = ndimage.label(known)
    if n == 0:
        return values
    idx = np.arange(1, n + 1)
    sizes = ndimage.sum(known, lab, index=idx)
    wmin = ndimage.minimum(np.nan_to_num(w, nan=1.0), lab, index=idx)
    bad = idx[(sizes < MARGINAL_PATCH_CELLS) & (wmin > MARGINAL_PATCH_MIN_W)]
    out = values.copy()
    drop = np.isin(lab, bad)
    out[drop] = np.nan
    print(f"    marginal patches dropped: {int(drop.sum()):,} cells in {bad.size} patches")
    return out


DISTANCE_STEP_M = 100.0     # the distance PNG: code 1 + d / step, 254 = beyond


def write_distance(path, dist_lake, masks, source):
    """How far, THROUGH THE WATER, each estimated cell is from a measured one —
    the distance the fill actually carried a value. 0 = not estimated (or no
    value); 1 + d / DISTANCE_STEP_M; 254 = further than 25 km or no path."""
    lake = masks["lake"]
    d = np.where(lake, dist_lake, np.nan)
    band = masks["reach"] & ~lake
    if band.any():      # the reach band takes its nearest lake cell's, as the value does
        _, (ir, ic) = ndimage.distance_transform_edt(~lake, return_indices=True)
        d[band] = d[ir[band], ic[band]]
    est = (source > 0) & (source < 255)
    code = np.zeros(d.shape, dtype="uint8")
    dd = np.where(np.isfinite(d), d, np.inf)
    code[est] = np.clip(1 + np.round(dd[est] / DISTANCE_STEP_M), 1, 254).astype("uint8")
    Image.fromarray(code, mode="L").save(path, optimize=True)
    print(f"  wrote {os.path.basename(path)} ({os.path.getsize(path) / 1024:.0f} KB)")


def encode(values, lo, hi, top=255):
    """0 = no reading, 1..top = the value. Codes above `top` are classes."""
    q = np.zeros(values.shape, dtype="uint8")
    ok = ~np.isnan(values)
    t = np.clip((values[ok] - lo) / (hi - lo), 0, 1)
    q[ok] = (1 + np.round(t * (top - 1))).astype("uint8")
    return q


def write(out, q, meta):
    Image.fromarray(q, mode="L").save(f"{out}.png", optimize=True)
    json.dump(meta, open(f"{out}.json", "w"), indent=2)
    print(f"  wrote {out}.png ({os.path.getsize(out + '.png') / 1024:.0f} KB) and {out}.json")


def pct(mask, of):
    return round(100 * float((mask & of).sum()) / max(1, int(of.sum())), 1)


def stats(v):
    v = v[~np.isnan(v)]
    if v.size == 0:
        return {}
    p = np.percentile(v, [1, 5, 25, 50, 75, 95, 99])
    return {k: round(float(x), 3) for k, x in zip(["p1", "p5", "p25", "p50", "p75", "p95", "p99"], p)}


def pass_record(date, platform, items):
    return {"date": date, "platform": platform, "sceneIds": [i["id"] for i in items],
            "time": items[0]["properties"]["datetime"]}


# ============================================================================

def build_temperature(frame, masks, bbox, until, out, lake_wgs, lake_name):
    print("TEMPERATURE — Landsat C2 L2 surface temperature")
    candidates = passes(PC_SEARCH, "landsat-c2-l2", bbox, until, max_cloud=60)
    chosen = None
    for (date, platform), items in candidates:
        if platform not in ("landsat-8", "landsat-9"):
            continue
        print(f"  pass {date} {platform} ({len(items)} scene(s))", flush=True)
        v, hidden, verdict = landsat_pass(items, frame, masks["lake"], lake_wgs, masks["guard"])
        read = ~np.isnan(v)
        cov = (read & masks["open"]).sum() / max(1, masks["open"].sum())
        print(f"    reads {100 * cov:.1f}% of the open water, "
              f"{pct(read, masks['lake'])}% of the lake; {verdict}")
        # The newest pass that is clean and sees most of the open water.
        # Newest first, so the first that qualifies wins.
        if verdict["ok"] and cov >= 0.5:
            chosen = (date, platform, items, v, hidden, verdict, cov)
            break
    if chosen is None:
        raise SystemExit("no clean Landsat pass in the window")
    date, platform, items, v, aux, verdict, cov = chosen
    med = float(np.nanmedian(v))
    read_before = ~np.isnan(v)
    v = drop_specks(v, min_cells=30)
    specked = read_before & np.isnan(v)
    v = drop_marginal_patches(v, aux["w"])
    anomaly_f = smooth_known((v - med) * 9 / 5, TEMP_SMOOTH_CELLS)

    # Every cell of the lake, and the 100 m past its line the app's coast may
    # reach, gets a value: measured cells keep theirs, the rest are filled
    # through the water from them.
    stem = LAKE_STEMS[lake_name]
    ends = (frame.cell_of(*stem[0]), frame.cell_of(*stem[1]))
    fit = np.nan_to_num(aux["far"]) >= 0.99
    filled, measured, info = fill_lake.fill_whole_lake(
        anomaly_f, masks["lake"], cell_ground_m=frame.cell_ground_m(), stem_ends=ends,
        lake_touch=masks["lake_touch"], reach=masks["reach"], fit_mask=fit, return_info=True)
    lo, hi = -6.0, 6.0
    q = encode(filled, lo, hi)
    unvalued = masks["reach"] & (q == 0)
    if unvalued.any():
        raise SystemExit(f"{int(unvalued.sum())} cells of the lake's reach have no value")

    # Which cells were measured: 255 measured; 2 estimated, cloud hid water
    # that could otherwise have been read; 1 estimated, water the satellite
    # cannot read here (near the bank, in grass, narrow arms).
    source = np.zeros(q.shape, dtype="uint8")
    source[q > 0] = 1
    cloud = masks["lake"] & ~measured & ((np.nan_to_num(aux["hidden"]) >= 0.5) | specked)
    source[cloud & (q > 0)] = 2
    source[measured] = 255
    Image.fromarray(source, mode="L").save(f"{out}.measured.png", optimize=True)
    print(f"  wrote {out}.measured.png ({os.path.getsize(out + '.measured.png') / 1024:.0f} KB)")
    write_distance(f"{out}.distance.png", info["dist_to_reading_m"], masks, source)

    lake = masks["lake"]
    dist = info["dist_to_reading_m"][lake & ~measured]
    dist = dist[np.isfinite(dist)]
    meta = {
        "field": "waterTemperature", "unit": "degF-anomaly",
        "encoding": {"kind": "linear", "lo": lo, "hi": hi},
        "pass": pass_record(date, platform, items),
        "sceneMedianSkinF": round(med * 9 / 5 + 32, 2),
        "sceneCheck": verdict,
        # The pattern the satellite measured, and the whole lake as drawn.
        "anomalyStatsF": stats(np.where(measured, filled, np.nan)),
        "filledStatsF": stats(np.where(lake, filled, np.nan)),
        "openWaterReadPct": round(100 * float(cov), 1),
        # readPct is now the share of the LAKE measured (it was the share of
        # the 200 m-eroded water read); openWaterReadPct is what picks a pass.
        "readPct": pct(measured, lake),
        "measuredPct": pct(measured, lake),
        "coveredPct": pct(~np.isnan(filled), lake),
        "measured": {"file": f"{os.path.basename(out)}.measured.png",
                     "cells": int(measured.sum()),
                     "codes": {"255": "measured",
                               "2": "estimated: cloud hid this water on the pass",
                               "1": "estimated: the satellite cannot read water here "
                                    "(near the bank, in grass, or a narrow arm)"},
                     "distanceFile": f"{os.path.basename(out)}.distance.png",
                     "distanceStepM": DISTANCE_STEP_M},
        "fill": {"method": "arm-depth trend + screened Laplace residual through the water",
                 "trendInterceptF": round(info["trend_intercept_F"], 3),
                 "trendArmDepthF": round(info["trend_armdepth_F"], 3),
                 "trendFitCells": info["trend_fit_cells"],
                 "flowThroughChannelCells": info["flow_through_cells"],
                 "screenM": fill_lake.SCREEN_M, "armScaleM": fill_lake.ARM_SCALE_M,
                 "bridgeCells": info["bridge_cells"],
                 # Held-out error of an estimate by its through-water distance
                 # to a reading: [up to metres, RMSE]; null = beyond.
                 "errorByDistance": fill_lake.ERROR_BY_DISTANCE_F,
                 "errorUnit": "degF",
                 "estimatedDistanceToReadingM": {
                     k: round(float(x)) for k, x in zip(
                         ["p50", "p90", "max"],
                         np.percentile(dist, [50, 90, 100]) if dist.size else [0, 0, 0])}},
        "source": "USGS Landsat 8/9 Collection 2 Level-2 Surface Temperature (ST_B10), "
                  "Microsoft Planetary Computer",
        "method": (f"one daytime pass; QA_PIXEL clear water only, cloud distance >= "
                   f"{thermal_shore.MIN_CLOUD_KM:g} km, ST uncertainty <= "
                   f"{thermal_shore.MAX_STQA_K:g} K; the share of each pixel from hot "
                   f"non-water (land, topped-out grass) removed with a "
                   f"{thermal_shore.SIGMA_M:g} m Gaussian PSF and water read down to a "
                   f"hot-surface weight of {thermal_shore.W_MAX:g}; pass rejected if, on the "
                   f"uncorrected product over the lake eroded {SCENE_GUARD_STANDOFF_M:g} m, "
                   f"more than {100 * SCENE_MAX_DROPPED:g}% of the water sits more than "
                   f"{COLD_OUTLIER_C} °C below or {WARM_OUTLIER_C} °C above its median (cold = "
                   f"undetected cloud) or the rest varies more than {SCENE_MAX_SD_C} °C; on the "
                   f"map the same outliers are dropped from the corrected read; stored as °F "
                   f"above or below the scene median, smoothed over ~300 m; the rest of the "
                   f"lake filled through the water from the measured cells (an arm-warmth "
                   f"trend fitted on water >= {FIT_FAR_FROM_NONWATER_M:g} m from non-water, "
                   f"plus a screened-Laplace residual)"),
        "caveats": ["Daytime skin temperature (~11:18 CDT) from one pass. Warm and cool "
                    "spots can move from day to day.",
                    "The level shown is the app's lake-wide estimate for tonight; only "
                    "the warmer/cooler pattern comes from the satellite.",
                    f"Only {pct(measured, lake)}% of the lake was measured. The rest (the "
                    "bank band, grass beds, narrow arms, water under cloud) is estimated: "
                    "carried through the water from measured cells, with a fitted "
                    "arm-warmth trend where it is far from any. The measured PNG says "
                    "which cells, and the distance PNG how far each estimate is carried.",
                    "Corrected readings near the bank keep about +0.2 °F of warmth that "
                    "may be real shallow water or leftover bank in the pixel; one pass "
                    "cannot tell them apart."],
    }
    write(out, q, meta)


def build_clarity(frame, masks, bbox, until, out, after=None, floor=0.0, ndci=False):
    """after  only passes newer than this date may be the base (the daily job:
              the pass already published); older ones still lend grass.
    floor     the fallback pass must read at least this share of the open
              water (the daily job: 80% of what the published pass read).
    ndci      also write the pass's NDCI product (<out>.ndci.png), for lakes
              whose Current Clarity reads the algal-water warning (Stage 8)."""
    print("CLARITY — Sentinel-2 L2A (C1) red-band turbidity, read at 10 m")
    candidates = passes(ES_SEARCH, S2_COLLECTION, bbox, until, max_cloud=40)
    base = None
    tried = []
    for (date, platform), items in candidates:
        if after and date <= after:
            break
        print(f"  pass {date} {platform} ({len(items)} tile(s))", flush=True)
        try:
            v, grass, aux = s2_pass(items, frame, masks["lake"], masks["clarity"], ndci=ndci)
        except PassRejected as e:
            print(f"    skipped: {e}")
            continue
        read = ~np.isnan(v)
        # Of the open water 40 m in from the bank that is not grass — grass
        # is never read, so it cannot count against a pass.
        water = masks["clarity"] & ~grass
        cov = (read & water).sum() / max(1, water.sum())
        print(f"    reads {100 * cov:.1f}% of the non-grass water 40 m in from the bank, "
              f"{pct(read, masks['lake'])}% of the whole lake")
        if cov >= 0.5:
            base = (date, platform, items, v, grass, aux)
            break
        # Only a pass that could still be the fallback is kept (a pass's
        # arrays run to hundreds of MB on a big lake): one no better than a
        # newer kept pass never wins, and a kept one drops out once the best
        # reads more than 1.25x it.
        if not tried or cov > tried[-1][0]:
            tried = [t for t in tried if t[0] >= 0.8 * cov] + [(cov, (date, platform, items, v, grass, aux))]
    # A lake that never reads half its open water (narrow, steep, dendritic
    # reservoirs: Beaver's clearest passes read 45-49%) takes its newest pass
    # within 80% of its best, provided that reads at least a quarter.
    if base is None and tried:
        best = max(c for c, _ in tried)
        if best >= max(MIN_PASS_COVERAGE, floor):
            cov, base = next((c, b) for c, b in tried if c >= 0.8 * best)
            print(f"    no pass read half the water; using {base[0]} ({100 * cov:.1f}%, best {100 * best:.1f}%)")
    if base is None:
        raise SystemExit("no clear Sentinel-2 pass in the window"
                         + (f" newer than {after}" if after else ""))
    date, platform, items, v, grass, aux = base
    tried.clear()
    lake = masks["lake"]
    base_day = dt.date.fromisoformat(date)
    others = [(d_, p_, it_) for (d_, p_), it_ in candidates
              if d_ != date and abs((dt.date.fromisoformat(d_) - base_day).days) <= GRASS_BORROW_DAYS]
    logv = np.where(v > 0, np.log10(np.maximum(v, 0.05)), np.nan).astype("float32")
    # Small hot specks, removed: much muddier than the ~500 m round them and
    # too small to be a plume.
    local = smooth_known(logv, 14)
    hot = ~np.isnan(logv) & ((logv - local) > SPECK_LOG10)
    lab, n = ndimage.label(hot)
    specked = np.zeros(logv.shape, dtype=bool)
    if n:
        sizes = ndimage.sum(hot, lab, index=np.arange(1, n + 1))
        specked = np.isin(lab, np.nonzero(sizes <= SPECK_MAX_CELLS)[0] + 1)
        logv[specked] = np.nan
        print(f"    muddy specks dropped: {int(specked.sum()):,} cells in "
              f"{int((sizes <= SPECK_MAX_CELLS).sum())} patches")
    # Shadow: near a real cloud, a patch much CLEARER than the water round it.
    near = np.nan_to_num(aux["near"]) >= 0.5
    dark = ~np.isnan(logv) & near & ((logv - local) < -S2_SHADOW_SPECK_LOG10)
    lab, n = ndimage.label(dark)
    shadowed = np.zeros(logv.shape, dtype=bool)
    if n:
        sizes = ndimage.sum(dark, lab, index=np.arange(1, n + 1))
        shadowed = np.isin(lab, np.nonzero(sizes <= SPECK_MAX_CELLS)[0] + 1)
        logv[shadowed] = np.nan
        print(f"    shadowed patches near cloud dropped: {int(shadowed.sum()):,} cells")
    # Readings too small to stand for any water but themselves.
    lab, n = ndimage.label(~np.isnan(logv))
    tiny = np.zeros(logv.shape, dtype=bool)
    if n:
        sizes = ndimage.sum(~np.isnan(logv), lab, index=np.arange(1, n + 1))
        tiny = np.isin(lab, np.nonzero(sizes < S2_MIN_PATCH_CELLS)[0] + 1)
        logv[tiny] = np.nan
        print(f"    readings under {S2_MIN_PATCH_CELLS} cells dropped: {int(tiny.sum()):,} cells")
    # GRASS UNDER CLOUD, from the passes either side. A bed the cloud hid
    # would otherwise be painted as open water with a clarity. Where a pass
    # within GRASS_BORROW_DAYS saw the cell clear and saw plants, it is grass.
    hidden_here = lake & np.isnan(logv) & ~grass & (np.nan_to_num(aux["hidden"]) >= 0.5)
    borrowed = np.zeros(lake.shape, dtype=bool)
    for d_, p_, it_ in others[:GRASS_BORROW_PASSES]:
        if not (hidden_here & ~borrowed).any():
            break
        print(f"    grass under cloud: reading {d_} {p_}", flush=True)
        try:
            _, g2, aux2 = s2_pass(it_, frame, lake, masks["clarity"])
        except PassRejected as e:
            print(f"      skipped: {e}")
            continue
        seen2 = np.nan_to_num(aux2["hidden"], nan=1.0) < 0.5
        got = hidden_here & seen2 & g2
        borrowed |= got
        print(f"      {pct(got, lake)}% of the lake is grass that cloud hid on {date}")
    grass = grass | borrowed
    # GRASS THAT RUNS TO THE BANK. Grass is only claimed 40 m in from the
    # polygon, so a bed that reaches the shore drew a strip of water colour
    # between the olive and the land. The unread strip right behind a bed is
    # drawn with it. This is proximity, not a reading: the satellite sees
    # plants there (mats, or bank vegetation under the lake's outline), not
    # open water, and the tap card says so.
    band = lake & ~masks["clarity"]
    to_bed = ndimage.distance_transform_edt(~grass) * frame.cell_ground_m()
    to_bank = band & np.isnan(logv) & (to_bed <= GRASS_TO_BANK_M)
    grass = grass | to_bank
    print(f"    grass beds: {pct(grass, lake)}% of the lake "
          f"({pct(to_bank, lake)}% of the lake is the bed run to the bank)")
    # Muddy pockets beside beds, dropped (see POCKET_*). Once the beds are
    # filled from the water round them, each one coloured its whole bed.
    read = ~np.isnan(logv)
    lab, n = ndimage.label(read)
    if n:
        ids = np.arange(1, n + 1)
        sizes = ndimage.sum(read, lab, ids)
        med = ndimage.median(np.where(read, logv, 0), lab, ids)
        dil = ndimage.grey_dilation(lab, size=3)
        rim = np.where((dil > 0) & ~read, dil, 0)
        rim_n = ndimage.sum(rim > 0, rim, ids)
        rim_g = ndimage.sum((rim > 0) & grass, rim, ids)
        with np.errstate(invalid="ignore", divide="ignore"):
            rim_frac = np.where(rim_n > 0, rim_g / np.maximum(rim_n, 1), 0)
        lake_med = float(np.nanmedian(logv))
        bad = ((sizes <= POCKET_MAX_CELLS) & (rim_frac >= POCKET_RIM_GRASS)
               & (med - lake_med > POCKET_LOG10))
        pocket = np.isin(lab, ids[bad])
        logv[pocket] = np.nan
        print(f"    muddy pockets beside beds dropped: {int(pocket.sum()):,} cells in "
              f"{int(bad.sum())} patches")

    # EVERY cell of the lake, and the 100 m past its line, gets a clarity:
    # measured cells keep theirs, the rest are filled through the water from
    # them — grass beds too, carried in from the water round each bed
    # (Michael, 2026-09-26: the olive beds read as "missing a lot of map
    # data"). A bed is still marked, as an estimate of its own kind.
    filled, measured, info = fill_lake.fill_clarity(
        logv, lake, grass, cell_ground_m=frame.cell_ground_m(),
        lake_touch=masks["lake_touch"], reach=masks["reach"], value_grass=True)
    lo, hi = math.log10(0.5), math.log10(200.0)
    q = encode(filled, lo, hi, top=254)
    unvalued = masks["reach"] & (q == 0)
    if unvalued.any():
        raise SystemExit(f"{int(unvalued.sum())} cells of the lake's reach have no value")
    valued = (q > 0) & (q <= 254)

    # 255 measured; 3 estimated, a grass bed (the reach band beside one takes
    # the bed's); 2 estimated, cloud or haze hid water that could otherwise
    # have been read; 1 estimated, water the satellite cannot read (the bank
    # band, beside bridges and docks, narrow creeks); 0 off the lake.
    source = np.zeros(q.shape, dtype="uint8")
    source[valued] = 1
    # A muddy speck is a structure or a wake, not cloud: it stays "can't read".
    cloud = lake & ~measured & ((np.nan_to_num(aux["hidden"]) >= 0.5) | shadowed)
    source[valued & cloud] = 2
    band_out = masks["reach"] & ~lake
    _, (ir, ic) = ndimage.distance_transform_edt(~lake, return_indices=True)
    bed = (lake & grass) | (band_out & grass[ir, ic])
    source[valued & bed] = 3
    source[measured] = 255
    Image.fromarray(source, mode="L").save(f"{out}.measured.png", optimize=True)
    print(f"  wrote {out}.measured.png ({os.path.getsize(out + '.measured.png') / 1024:.0f} KB)")
    write_distance(f"{out}.distance.png", info["dist_to_reading_m"], masks, source)

    dist = info["dist_to_reading_m"][lake & ~measured]
    dist = dist[np.isfinite(dist)]
    meta = {
        "field": "turbidity", "unit": "FNU",
        "encoding": {"kind": "log10", "lo": lo, "hi": hi, "top": 254},
        # No classes: every cell is a value. Grass is code 3 of the measured PNG.
        "classes": {},
        "grassPct": pct(grass, lake),
        "pass": pass_record(date, platform, items),
        "measuredStatsFNU": stats(np.where(measured, 10 ** filled, np.nan)),
        "filledStatsFNU": stats(np.where(lake & ~grass, 10 ** filled, np.nan)),
        "grassStatsFNU": stats(np.where(lake & grass, 10 ** filled, np.nan)),
        "openWaterReadPct": round(100 * float(cov), 1),
        # readPct / measuredPct: the share of the LAKE measured. coveredPct is
        # the share with a clarity value — the whole lake, grass beds included.
        "readPct": pct(measured, lake),
        "measuredPct": pct(measured, lake),
        "coveredPct": pct(valued, lake),
        "measured": {"file": f"{os.path.basename(out)}.measured.png",
                     "cells": int(measured.sum()),
                     "codes": {"255": "measured",
                               "3": "estimated: a grass bed — the satellite sees the "
                                    "plants, not the water; carried in from the water "
                                    "round the bed",
                               "2": "estimated: cloud or haze hid this water on the pass",
                               "1": "estimated: the satellite cannot read water here "
                                    "(the bank band, beside bridges and docks, or a "
                                    "narrow creek)",
                               "0": "off the lake"},
                     "distanceFile": f"{os.path.basename(out)}.distance.png",
                     "distanceStepM": DISTANCE_STEP_M},
        "fill": {"method": "screened Laplace through the water from the readings, grass "
                           "a soft barrier, no geometry trend; grass beds then solved "
                           "from the water round them as open water",
                 "b0Log10": round(info["b0_log10"], 4),
                 "screenM": info["screen_m"], "grassConductance": info["grass_conductance"],
                 "bridgeCells": info["bridge_cells"],
                 "grassToBankPct": pct(to_bank, lake),
                 "grassUnderCloudPct": pct(borrowed, lake),
                 "tileOffsetsLog10": aux["tileOffsets"],
                 # Held-out error of an estimate by its through-water distance
                 # to a reading, in feet of visibility; null = beyond.
                 "errorByDistance": fill_lake.CLARITY_ERROR_BY_DISTANCE_FT,
                 "errorUnit": "ft",
                 "estimatedDistanceToReadingM": {
                     k: round(float(x)) for k, x in zip(
                         ["p50", "p90", "max"],
                         np.percentile(dist, [50, 90, 100]) if dist.size else [0, 0, 0])}},
        "source": "Copernicus Sentinel-2 L2A (Collection 1), Element84 Earth Search",
        "algorithm": {"name": "Dogliotti et al. 2015, red band",
                      "formula": "T = A*rho/(1 - rho/C)", "A": TURB_A, "C": TURB_C,
                      "band": "B04 (665 nm), native 10 m",
                      "citation": "Remote Sensing of Environment 156:157-168; "
                                  "coefficients as in ACOLITE's defaults"},
        "method": (f"red read at {S2_NATIVE_PX:g} m, every gate per pixel: SCL water, "
                   f"{S2_BANK_STANDOFF_M:g} m from SCL bank, {S2_CLOUD_STANDOFF_M:g} m from "
                   f"SCL cloud/shadow, {S2_STRUCTURE_STANDOFF_M:g} m from bright non-vegetated "
                   f"land, {S2_HAZE_STANDOFF_M:g} m from bright water (hulls, missed cloud), "
                   f"not SWIR16 > {S2_CLOUD_EDGE_SWIR:g} on open water within {S2_CLOUD_EDGE_M:g} m "
                   f"of a real (>= 1 ha) cloud, "
                   f"SWIR <= {SWIR_MAX}, FAI <= {FAI_MAX}, NDVI <= {NDVI_MAX}; a cell needs "
                   f"{100 * S2_MIN_CELL_FRAC:g}% of its 10 m pixels read; ~{frame.cell * 0.83:.0f} m "
                   f"cells; surface grass (NDVI >= {GRASS_NDVI_MIN:g}) is never read, and "
                   f"hazy open water (SWIR > {HAZE_SWIR:g}, and SWIR > {HAZE_EDGE_SWIR:g} "
                   f"within {HAZE_EDGE_M:g} m of it) counts as hidden; the rest of "
                   f"the lake, grass beds included, filled through the water from the "
                   f"readings"),
        "caveats": ["Turbidity from reflectance, not a Secchi reading.",
                    "Surface grass beds are never read — their colour is the plant, not "
                    "the water. Their clarity is the water round the bed carried in, "
                    "and the measured PNG marks them (3).",
                    f"Only {pct(measured, lake)}% of the lake was measured. The rest "
                    "(the bank band, beside bridges and docks, narrow creeks, water "
                    "under cloud or haze, grass beds) is estimated through the water "
                    "from the readings; the "
                    "measured PNG says which cells, the distance PNG how far each "
                    "estimate was carried.",
                    "Unvalidated against same-day measurements; ADEM's Aug-Oct "
                    "median for the lake is 5.3 NTU.",
                    "Sen2Cor corrected each tile for haze on its own; the tiles are put on "
                    "the level of the one that reads most of the lake (tileOffsetsLog10). "
                    "Which tile's level is right is unknown.",
                    "Grass includes the unread strip right behind a bed (bank plants "
                    "under the lake's outline as well as mats) and beds cloud hid, taken "
                    "from a clear pass within ten days."],
    }
    nd = aux.get("ndci")
    if nd is not None:
        n_meas, n_carry = write_ndci(f"{out}.ndci.png", nd, measured, info["dist_to_reading_m"], lake,
                                     frame.cell_ground_m())
        meta["ndci"] = {
            "file": f"{os.path.basename(out)}.ndci.png",
            "index": "NDCI = (B05 - B04) / (B05 + B04), mean reflectance of the pixels the turbidity read",
            "encoding": {"kind": "linear", "lo": NDCI_LO, "step": NDCI_STEP, "top": 254, "none": 0},
            "measuredCells": n_meas, "carriedCells": n_carry, "carryM": NDCI_CARRY_M,
            "use": "algal-water reliability warning only (NDCI > 0.03, Sentinel-2): never a clarity value",
        }
        print(f"  wrote {out}.ndci.png ({n_meas:,} measured cells, {n_carry:,} carried within {NDCI_CARRY_M:g} m)")
    write(out, q, meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("waterbody")
    ap.add_argument("outdir")
    ap.add_argument("--lake", default="Guntersville")
    ap.add_argument("--lake-id", default="Guntersville|AL")
    ap.add_argument("--until", default=dt.date.today().isoformat())
    ap.add_argument("--only", choices=["temp", "clarity"], default=None)
    a = ap.parse_args()

    gj = json.load(open(a.waterbody))
    lake = unary_union([shape(f["geometry"]) for f in gj["features"]])
    frame = Frame(lake)
    masks = lake_masks(lake, frame)
    cframe = Frame(lake, cell=CLARITY_CELL)
    cmasks = lake_masks(lake, cframe)
    bbox = list(lake.bounds)
    until = dt.datetime.fromisoformat(a.until)
    os.makedirs(a.outdir, exist_ok=True)
    print(f"frame {frame.width}x{frame.height} @ {CELL:.0f} m (mercator); "
          f"lake {masks['lake'].sum():,} cells")
    def run(fn, name, fr, ms):
        fn(fr, ms, bbox, until, os.path.join(a.outdir, f"{a.lake}.{name}"))
        path = os.path.join(a.outdir, f"{a.lake}.{name}.json")
        m = json.load(open(path))
        common = {"lakeId": a.lake_id, "projection": WEB_MERCATOR,
                  "coordinates": fr.corners(), "pixelWidth": fr.width,
                  "pixelHeight": fr.height, "cellMetresMercator": fr.cell,
                  "generatedOn": dt.date.today().isoformat()}
        json.dump({**common, **m}, open(path, "w"), indent=2)

    if a.only in (None, "temp"):
        run(lambda fr, ms, bb, un, o: build_temperature(fr, ms, bb, un, o, lake, a.lake),
            "watertemp", frame, masks)
    if a.only in (None, "clarity"):
        run(build_clarity, "clarity", cframe, cmasks)


if __name__ == "__main__":
    main()
