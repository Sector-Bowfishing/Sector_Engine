"""Port of Sector's cell-level grass logic (jobs/lake-surface/derive_water_surface.py, READ ONLY, replicated here).
Per Sentinel-2 scene: 10 m gates -> 50 m web-mercator frame cell (Frame/to_grid, Resampling.average) -> cell vote gfrac >= 0.5.
Constants are copied verbatim from the Sector file. Research only; nothing imports from the repo.
Deviations (documented in note 05): window is lake bbox + ~200 m (Sector pads 1 km), so cloud/structure standoff distances are
truncated at the window edge; 'real cloud' size test uses 100 px at 10 m (= 25 px at 20 m); no tile blending (single tile)."""
import math, numpy as np, pyproj, rasterio
from rasterio.warp import reproject
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.ops import transform as shp_transform
from scipy import ndimage

WEB_MERCATOR = "EPSG:3857"; CELL = 50.0
GRASS_NDVI_MIN = 0.30; HAZE_SWIR = 0.02; HAZE_EDGE_M = 400.0; HAZE_EDGE_SWIR = 0.010
SWIR_MAX = 0.0215; FAI_MAX = 0.005; NDVI_MAX = 0.10; BRIGHT_SWIR = 0.05
SCL_WATER = 6; SCL_CLOUDY = {0, 1, 3, 8, 9, 10, 11}
S2_NATIVE_PX = 10.0; S2_BANK_STANDOFF_M = 10.0; S2_CLOUD_STANDOFF_M = 60.0; S2_STRUCTURE_STANDOFF_M = 100.0
S2_HAZE_STANDOFF_M = 100.0; S2_STRUCTURE_NDVI_MAX = 0.30; S2_MIN_CELL_FRAC = 0.25; S2_SCL_BANK = (2, 4, 5, 7)
S2_CLOUD_EDGE_M = 1500.0; S2_CLOUD_EDGE_SWIR = 0.012; S2_CLOUD_EDGE_OFFSHORE_M = 100.0; S2_REAL_CLOUD_MIN_PX20 = 25
S2_REAL_CLOUD_STANDOFF_M = 600.0
GRASS_TO_BANK_M = 90.0

def to_crs(geom, src, dst):
    return shp_transform(pyproj.Transformer.from_crs(src, dst, always_xy=True).transform, geom)

class Frame:
    def __init__(self, lake_wgs, cell=CELL):
        merc = to_crs(lake_wgs, "EPSG:4326", WEB_MERCATOR)
        minx, miny, maxx, maxy = merc.bounds; pad = 1000.0
        self.cell = cell
        self.left = math.floor((minx - pad) / cell) * cell; self.top = math.ceil((maxy + pad) / cell) * cell
        right = math.ceil((maxx + pad) / cell) * cell; bottom = math.floor((miny - pad) / cell) * cell
        self.width = int(round((right - self.left) / cell)); self.height = int(round((self.top - bottom) / cell))
        self.transform = from_origin(self.left, self.top, cell, cell); self.bounds = (self.left, bottom, right, self.top)
    def burn(self, g):
        return rasterize([(g, 1)], out_shape=(self.height, self.width), transform=self.transform, fill=0, dtype="uint8").astype(bool)
    def ground_m(self):
        l, b, r, t = self.bounds
        lat = pyproj.Transformer.from_crs(WEB_MERCATOR, "EPSG:4326", always_xy=True).transform((l + r) / 2, (b + t) / 2)[1]
        return self.cell * math.cos(math.radians(lat))

def to_grid(values, src_transform, src_crs, frame):
    out = np.full((frame.height, frame.width), np.nan, dtype="float32")
    reproject(source=values.astype("float32"), destination=out, src_transform=src_transform, src_crs=src_crs, src_nodata=np.nan,
              dst_transform=frame.transform, dst_crs=WEB_MERCATOR, dst_nodata=np.nan, resampling=Resampling.average)
    return out

def _edge_dist_px(mask):
    if not mask.any(): return np.full(mask.shape, np.inf, "float32")
    e = ndimage.distance_transform_edt(~mask).astype("float32") - 0.5; e[mask] = 0; return e

def native_fields(s):
    """s: cached scene dict (reflectance already offset-corrected, nan where DN==0; SCL uint8 at 10 m nearest from 20 m).
    Returns ok (turbidity-readable per 10 m pixel), gfrac (1 veg / 0 not, nan = not seen), readable (nan where scl==0), hidden."""
    r_red, r_nir, r_sw, scl = s["B04"], s["B8A"], s["B11"], s["SCL"]
    water = scl == SCL_WATER
    with np.errstate(invalid="ignore", divide="ignore"):
        fai = r_nir - (r_red + (r_sw - r_red) * (865 - 665) / (1610 - 665))
        ndvi = (r_nir - r_red) / np.maximum(1e-6, r_nir + r_red)
        bright = np.nan_to_num(r_sw, nan=0) > BRIGHT_SWIR
        veg = ndvi >= GRASS_NDVI_MIN
        haze_px = water & (r_sw > HAZE_SWIR) & ~veg
    structure = bright & (np.nan_to_num(ndvi, nan=1.0) < S2_STRUCTURE_NDVI_MAX) & ~water
    haze = bright & water
    bank = np.isin(scl, S2_SCL_BANK); px = S2_NATIVE_PX
    to_bank, to_structure = _edge_dist_px(bank), _edge_dist_px(structure)
    cloudy_classes = [c for c in SCL_CLOUDY if c != 0]
    to_cloud = _edge_dist_px(np.isin(scl, cloudy_classes)); clear = to_cloud >= S2_CLOUD_STANDOFF_M / px
    cl = np.isin(scl, cloudy_classes); lab, n = ndimage.label(cl)
    if n:
        sizes = ndimage.sum(cl, lab, index=np.arange(1, n + 1)); real = np.isin(lab, np.nonzero(sizes >= 4 * S2_REAL_CLOUD_MIN_PX20)[0] + 1)
    else: real = cl
    to_real = _edge_dist_px(real); near_cloud = to_real < S2_CLOUD_EDGE_M / px; under_cloud = to_real < S2_REAL_CLOUD_STANDOFF_M / px
    offshore = (to_bank >= S2_CLOUD_EDGE_OFFSHORE_M / px) & (to_structure >= S2_CLOUD_EDGE_OFFSHORE_M / px)
    with np.errstate(invalid="ignore"):
        cloud_edge = near_cloud & offshore & (r_sw > S2_CLOUD_EDGE_SWIR)
        haze_edge = (_edge_dist_px(haze_px) < HAZE_EDGE_M / px) & offshore & (r_sw > HAZE_EDGE_SWIR)
    beside_bright = _edge_dist_px(haze) < S2_HAZE_STANDOFF_M / px
    unhazed = ~beside_bright & ~cloud_edge & ~haze_edge
    ok = water & clear & ~under_cloud & unhazed
    ok &= to_bank >= S2_BANK_STANDOFF_M / px; ok &= to_structure >= S2_STRUCTURE_STANDOFF_M / px
    with np.errstate(invalid="ignore"):
        ok &= (r_sw <= SWIR_MAX) & (fai <= FAI_MAX) & (ndvi <= NDVI_MAX) & (r_red > 0)
    seen = (scl > 0) & clear
    gfrac = np.where(seen, veg.astype("float32"), np.nan).astype("float32")
    readable = np.where(scl > 0, ok.astype("float32"), np.nan).astype("float32")
    return ok, gfrac, readable

def scene_cells(s, frame, measurable):
    """-> gfrac_cell (nan = not seen), have (turbidity read in cell, i.e. blocks 'grass')."""
    ok, gfrac, readable = native_fields(s)
    rr = np.where(ok, 1.0, np.nan).astype("float32")           # presence of a reading (value irrelevant for the vote)
    g = to_grid(rr, s["transform"], s["crs"], frame)
    frac = to_grid(readable, s["transform"], s["crs"], frame)
    gcell = to_grid(gfrac, s["transform"], s["crs"], frame)
    have = ~np.isnan(g) & (np.nan_to_num(frac) >= S2_MIN_CELL_FRAC) & measurable
    return gcell, have

def lake_masks(lake_wgs, frame, utm_crs):
    lake_utm = to_crs(lake_wgs, "EPSG:4326", utm_crs)
    merc = lambda g: to_crs(g, utm_crs, WEB_MERCATOR)
    return {"lake": frame.burn(merc(lake_utm)), "clarity": frame.burn(merc(lake_utm.buffer(-40.0)))}

def grass_vote(gcell, have, clarity):
    return (np.nan_to_num(gcell) >= 0.5) & clarity & ~have

def to_bank_extension(grass, have, lake, clarity, frame):
    band = lake & ~clarity
    to_bed = ndimage.distance_transform_edt(~grass) * frame.ground_m()
    return grass | (band & ~have & (to_bed <= GRASS_TO_BANK_M))
