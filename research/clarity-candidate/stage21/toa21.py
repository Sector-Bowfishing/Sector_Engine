"""Stage 21 section 3a: pixel-paired top-of-atmosphere statistics for one S2A/S2C tandem tile (same MGRS grid, ~30 s
apart). 20 m grid: B05/B8A/B11/B12 native, B08 2x2 mean of 10 m, B02/B03 read at 20 m (JPEG2000 resolution level, masks
only), B10 repeated 3x3. rho = (DN + RADIO_ADD_OFFSET) / QUANTIFICATION_VALUE from each product's own metadata.
Water pixels (pre-registered): S2A NDWI(B03,B8A) > 0.2, S2A B11 < 0.03, both B10 < 0.002, |C/A(B05) - 1| < 0.10, both valid.
Returns per band: delta_tile (median C - A over water), n_water, m_C (S2C clear-pixel median), the decile gain diagnostic
and delta by S2C detector (if the footprint mask is present)."""
import os, glob, math
import numpy as np
import rasterio
from rasterio.enums import Resampling
import xml.etree.ElementTree as ET
BANDS = ["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10", "B11", "B12"]
CORR = ("B08", "B8A", "B11", "B12")


def meta(safe):
    root = ET.parse(os.path.join(safe, "MTD_MSIL1C.xml")).getroot()
    q = float(root.find(".//QUANTIFICATION_VALUE").text)
    off = {BANDS[int(o.get("band_id"))]: float(o.text) for o in root.iter("RADIO_ADD_OFFSET")}
    return q, off


def path(safe, b):
    f = glob.glob(os.path.join(safe, "GRANULE", "*", "IMG_DATA", f"*_{b}.jp2")); return f[0] if f else None


def read(safe, b, q, off, mode):
    """mode: 'native20' | 'mean10' (10 m -> exact 2x2 mean) | 'level20' (10 m read at 20 m) | 'rep60' (60 m x3)"""
    with rasterio.open(path(safe, b)) as ds:
        if mode == "native20": dn = ds.read(1).astype("float32")
        elif mode == "level20": dn = ds.read(1, out_shape=(ds.height // 2, ds.width // 2), resampling=Resampling.average).astype("float32")
        elif mode == "rep60": dn = np.repeat(np.repeat(ds.read(1).astype("float32"), 3, 0), 3, 1)
        else:
            a = ds.read(1).astype("float32"); a[a == 0] = np.nan
            dn = a.reshape(a.shape[0] // 2, 2, a.shape[1] // 2, 2).mean(axis=(1, 3))
    dn[dn == 0] = np.nan
    return (dn + off.get(b, 0.0)) / q


def stats(safeA, safeC, delta=None):
    qa, oa = meta(safeA); qc, oc = meta(safeC)
    M = {"B05": "native20", "B8A": "native20", "B11": "native20", "B12": "native20", "B08": "mean10", "B02": "level20", "B03": "level20", "B10": "rep60"}
    A = {b: read(safeA, b, qa, oa, m) for b, m in M.items()}
    C = {b: read(safeC, b, qc, oc, m) for b, m in M.items() if b != "B03"}
    if delta:                                     # held-out check: S2C after the frozen correction
        for b, d in delta.items(): C[b] = C[b] - d
    with np.errstate(invalid="ignore", divide="ignore"):
        ndwi = (A["B03"] - A["B8A"]) / (A["B03"] + A["B8A"])
        cl = (A["B10"] < 0.002) & (C["B10"] < 0.002) & (np.abs(C["B05"] / A["B05"] - 1) < 0.10)
        water = cl & (ndwi > 0.2) & (A["B11"] < 0.03) & np.all([np.isfinite(A[b]) & np.isfinite(C[b]) for b in CORR], axis=0)
        clearC = (C["B10"] < 0.002) & (C["B02"] < 0.3)
        clearAC = cl & (A["B02"] < 0.3)
    out = {"n_water": int(water.sum()), "bands": {}}
    det = None
    dm = glob.glob(os.path.join(safeC, "GRANULE", "*", "QI_DATA", "*MSK_DETFOO_B11.jp2"))
    if dm:
        with rasterio.open(dm[0]) as ds: det = ds.read(1)
        if det.shape != water.shape: det = None
    for b in CORR + ("B05",):
        d = (C[b] - A[b])[water]
        rec = {"delta_tile": float(np.median(d)) if d.size else None, "delta_iqr": [float(np.percentile(d, 25)), float(np.percentile(d, 75))] if d.size else None,
               "A_water_median": float(np.median(A[b][water])) if d.size else None, "m_C": float(np.nanmedian(C[b][clearC])) if clearC.any() else None}
        x = A[b][clearAC]; y = C[b][clearAC]; ok = np.isfinite(x) & np.isfinite(y); x, y = x[ok], y[ok]
        if x.size > 1000:
            qs = np.percentile(x, np.arange(0, 101, 10)); dec = []
            for lo, hi in zip(qs[:-1], qs[1:]):
                m = (x >= lo) & (x < hi)
                if m.sum() > 50: dec.append([float(np.median(x[m])), float(np.median(y[m] - x[m]))])
            rec["deciles"] = dec
        if det is not None and d.size:
            dd = det[water]; rec["by_detector"] = {int(k): float(np.median(d[dd == k])) for k in np.unique(dd) if k > 0 and (dd == k).sum() >= 100}
        out["bands"][b] = rec
    return out
