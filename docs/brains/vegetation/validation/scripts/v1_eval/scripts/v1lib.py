"""Adapter: cached reflectance windows -> arrays for the SHIPPED vegetation_brain.observer (imported, not re-implemented).
OFFLINE: a socket guard makes any network attempt raise, so measured network bytes are exactly 0 (see net_guard)."""
import sys, os, json, gzip, datetime as dt, socket
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
REPO_JOB = "{HOME}/Desktop/Development/Sector_Engine-vegetation-adoption/jobs/vegetation-brain"
sys.path.insert(0, REPO_JOB)
import numpy as np, rasterio, pyproj
from rasterio.features import rasterize
from shapely.geometry import shape
from shapely.ops import transform as shp_t
from scipy import ndimage
from pathlib import Path
from vegetation_brain import observer as O, contract as C

HERE = Path(__file__).resolve().parents[1]                     # .../adoption/v1_eval
ROOT = HERE.parents[1]                                         # .../experiments
OUT = HERE / "out"
NET_BYTES = 0                                                  # measured S2 network bytes (adapter has no reader; guard enforces it)

def net_guard():
    def _deny(*a, **k): raise RuntimeError("NETWORK DISABLED: v1_eval is cache-only (S2 byte cap 1 GB; this run uses 0)")
    socket.socket.connect = _deny; socket.create_connection = _deny; socket.getaddrinfo = _deny

def frozen_floor():
    return json.load(open(OUT / "calibration.json"))["NIR_PLANT_MIN"]

def freeze_floor(v=None):
    O.NIR_PLANT_MIN = float(frozen_floor() if v is None else v)
    return O.NIR_PLANT_MIN

def load_poly(path):
    b = Path(path).read_bytes()
    g = json.loads(gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b)
    if g.get("type") == "FeatureCollection": return shape(g["features"][0]["geometry"])
    return shape(g.get("geometry", g))

def rasterize_lake(poly_ll, crs, tr, shp_):
    """canonical polygon (EPSG:4326) -> bool lake mask on the scene's 10 m grid (pixel-centre rule)."""
    f = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    return rasterize([(shp_t(f, poly_ll), 1)], out_shape=shp_, transform=tr, fill=0, dtype="uint8").astype(bool)

def dist_to_edge_m(lake):
    """metres from each lake pixel centre to the nearest non-lake pixel centre; array border counted as non-lake (conservative)."""
    p = np.pad(lake, 1, constant_values=False)
    return ndimage.distance_transform_edt(p)[1:-1, 1:-1] * C.PX_M

def refl_to_dn(r, collection):
    """Cached TRUE reflectance -> raw DN of the stated collection (so observer.reflectance() owns the offset convention)."""
    off = C.S2_OFFSET_C1 if collection == "sentinel-2-c1-l2a" else 0.0
    dn = np.round((np.nan_to_num(r, nan=-1e9) - off) / C.S2_SCALE)
    dn = np.where(np.isfinite(r), np.clip(dn, 1, 65534), 0)
    return dn.astype("uint16")

def make_scene(sid, when, collection, dn_red, dn_nir, dn_swir, scl, lake):
    red = O.reflectance(dn_red, collection); nir = O.reflectance(dn_nir, collection); swir = O.reflectance(dn_swir, collection)
    fields = O.scene_fields(scl, red, nir, swir, lake)
    cells = O.to_cells(fields)
    return O.Scene(sid, when, cells, collection), fields, nir

def cell_center_dist(dist_px, cell_px=C.CELL_PX):
    h, w = (dist_px.shape[0] // cell_px) * cell_px, (dist_px.shape[1] // cell_px) * cell_px
    c = cell_px // 2
    return dist_px[:h, :w].reshape(h // cell_px, cell_px, w // cell_px, cell_px)[:, c, :, c]

def block_mean(a, k=C.CELL_PX):
    h, w = (a.shape[0] // k) * k, (a.shape[1] // k) * k
    return a[:h, :w].astype("float32").reshape(h // k, k, w // k, k).mean(axis=(1, 3))

def d2(s): return dt.date.fromisoformat(str(s)[:10])
