"""Import the PRODUCTION surface-grass code and drive it from cached reflectance windows.

IMPORTED, not re-implemented (read-only repo, bytecode writing disabled):
  {HOME}/Desktop/Development/Sector_Engine-vegetation-adoption/jobs/lake-surface/derive_water_surface.py
Production functions CALLED unchanged:
  dws.Frame, dws.lake_masks, dws.to_grid, dws._s2_native_fields (all 10 m gates, NDVI>=0.30 plant rule, SCL, standoffs),
  dws.s2_pass (tile blend, per-cell gfrac, grass = gfrac>=0.5 & clarity mask & isnan(acc)), dws.match_tiles,
  dws.build_clarity (end-to-end, pass acceptance + borrow + to-bank strip) in 35_e2e.py.
STUBBED (network / storage only):
  dws._read_s2_native  -> returns the same dict of uint16 DN arrays (scl/nir08/swir16 at 20 m, red at 10 m) rebuilt from cached windows
  dws.passes           -> (build_clarity only) returns cached candidate passes instead of querying Earth Search
  daily.py (GCS Store, STAC search, memory budget) is NOT used: only dws is imported.
"""
import sys, os
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
PROD = "{HOME}/Desktop/Development/Sector_Engine-vegetation-adoption/jobs/lake-surface"
sys.path.insert(0, PROD)
import numpy as np, rasterio
import derive_water_surface as dws

_STUB = {}      # item id -> tile dict (what _read_s2_native would have returned)
_DIAG = {}      # item id -> diagnostics computed from the SAME arrays the production function saw

def refl_to_dn(r):
    """Cached float reflectance (offset already removed, NaN = DN 0) -> the DN that sentinel-2-c1-l2a would deliver
    (reflectance = DN*1e-4 - 0.1), so production decodes it back to the same reflectance."""
    dn = np.rint((r + 0.1) / 1e-4)
    dn = np.clip(dn, 1, 65534)
    dn[~np.isfinite(r)] = 0
    return dn.astype("uint16")

def raw_to_dn(raw, off):
    """lean cache (uint16 DN as read from the COG) -> c1-convention DN. sentinel-2-l2a COGs are offset-free: add 1000."""
    dn = raw.astype("int32")
    if off == 0.0:
        dn = np.where(raw == 0, 0, dn + 1000)
    return np.clip(dn, 0, 65535).astype("uint16")

def build_tile(red_dn, nir_dn, sw_dn, scl, transform, crs):
    """10 m cached arrays (20 m bands nearest-upsampled) -> production tile dict (20 m scl/nir08/swir16, 10 m red, nested windows)."""
    x0, y0 = transform.c, transform.f
    sx = int(round((x0 % 20.0) / 10.0)) % 2
    sy = int(round(((-y0) % 20.0) / 10.0)) % 2
    h = (red_dn.shape[0] - sy) // 2 * 2
    w = (red_dn.shape[1] - sx) // 2 * 2
    sl = (slice(sy, sy + h), slice(sx, sx + w))
    red = red_dn[sl]
    d20 = lambda a: a[sl][::2, ::2]
    tr10 = rasterio.Affine(transform.a, 0, x0 + sx * 10.0, 0, transform.e, y0 - sy * 10.0)
    tr20 = rasterio.Affine(20.0, 0, tr10.c, 0, -20.0, tr10.f)
    return {"scl": d20(scl), "nir08": d20(nir_dn), "swir16": d20(sw_dn), "red": red, "tr20": tr20, "tr10": tr10, "crs": crs}

def block_consistency(a10, sx_sy_tr):
    """sanity: share of 2x2 blocks that are constant in a nearest-upsampled 10 m array after phase alignment"""
    x0, y0 = sx_sy_tr.c, sx_sy_tr.f
    sx = int(round((x0 % 20.0) / 10.0)) % 2; sy = int(round(((-y0) % 20.0) / 10.0)) % 2
    h = (a10.shape[0] - sy) // 2 * 2; w = (a10.shape[1] - sx) // 2 * 2
    b = a10[sy:sy + h, sx:sx + w].reshape(h // 2, 2, w // 2, 2)
    return float(((b == b[:, :1, :, :1]).all(axis=(1, 3))).mean())

# ---- stubs -----------------------------------------------------------------
def _stub_read(item, frame_bounds):
    return dict(_STUB[item["id"]])      # production deletes t["red"] in place, so hand out a copy each call

REAL_READ = dws._read_s2_native      # production reader (network), kept for the Guntersville pilot
_orig_fields = dws._s2_native_fields
def _fields_with_diag(t):
    out = _orig_fields(t)
    fnu, gfrac, readable, hidden, near = out
    h, w = t["red"].shape
    up = lambda x: np.repeat(np.repeat(x, 2, axis=0), 2, axis=1)[:h, :w]
    dec = lambda dn: np.where((dn == 0) | (dn == 65535), np.nan, dn.astype("float32") * dws.S2_SCALE + dws.S2_OFFSET)
    r_red = dec(t["red"]); r_nir = up(dec(t["nir08"])); r_sw = up(dec(t["swir16"])); scl = up(t["scl"])
    seen = ~np.isnan(gfrac)
    with np.errstate(invalid="ignore"):
        dark = (r_red < 0.01) & (r_nir < 0.01) & seen
        veg = gfrac == 1.0
        water = scl == dws.SCL_WATER
        glare = water & ~veg & (r_sw > dws.SWIR_MAX) & seen
        cloudpx = np.isin(scl, [3, 8, 9, 10, 11, 1]) 
    ctx = _DIAG.setdefault("_cur", {})
    ctx["pix"] = {
        "seen": (scl > 0).astype("float32") * 0 + seen.astype("float32"),     # 1 where seen (clear + data), else 0 (never NaN)
        "nodata": (scl == 0).astype("float32"),
        "cloudscl": cloudpx.astype("float32"),
        "veg_valid": np.where(seen & ~dark, veg.astype("float32"), np.nan).astype("float32"),
        "dark": np.where(seen, dark.astype("float32"), np.nan).astype("float32"),
        "glare": np.where(seen, glare.astype("float32"), np.nan).astype("float32"),
        "tr10": t["tr10"], "crs": t["crs"],
    }
    return out
# Sensitivity only (NOT production): disable s2_pass's whole-scene "SWIR DN over water" sanity gate. The gate is
# `if swir_check and not (900 <= np.median(swir_check) <= 1500): raise PassRejected`; the only np.median call on a python
# list inside s2_pass is that one, so a numpy proxy that answers 1000.0 for a list turns it off and nothing else.
import numpy as _np
class _NPProxy:
    gate_off = False
    def __getattr__(self, k): return getattr(_np, k)
    def median(self, a, *args, **kw):
        if self.gate_off and isinstance(a, list): return 1000.0
        return _np.median(a, *args, **kw)
_proxy = _NPProxy()
dws.np = _proxy
dws._read_s2_native = _stub_read
dws._s2_native_fields = _fields_with_diag

def run_scene(item_id, tile, frame, masks, utm_crs, gate=True):
    """One production pass on one cached scene. Returns per-cell arrays. gate=False: sensitivity run without the SWIR-DN scene gate."""
    dws.UTM = utm_crs
    _proxy.gate_off = not gate
    _STUB[item_id] = dict(tile)   # production does `del t["red"]` on its tile
    _DIAG["_cur"] = {}
    try:
        acc, grass, aux = dws.s2_pass([{"id": item_id}], frame, masks["lake"], masks["clarity"])
    finally:
        _proxy.gate_off = False
    p = _DIAG["_cur"]["pix"]
    g = lambda a: dws.to_grid(a, p["tr10"], p["crs"], frame)
    res = {
        "read": ~np.isnan(acc),
        "grass_prod": grass,
        "gfrac": aux["gfrac"].astype("float32"),
        "hidden": aux["hidden"].astype("float32"),
        "near": aux["near"].astype("float32"),
        "seen_share": g(p["seen"]),
        "nodata_share": g(p["nodata"]),
        "cloudscl_share": g(p["cloudscl"]),
        "gfrac_v1": g(p["veg_valid"]),
        "dark_share": g(p["dark"]),
        "glare_share": g(p["glare"]),
    }
    _STUB.pop(item_id, None)
    return res

def sha256(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()
