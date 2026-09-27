"""Mixed-pixel correction for Landsat 8/9 C2 L2 surface temperature at a lake
shore (fitted on Guntersville, 3 Sep 2026 pass, native 30 m UTM grid).
Used by derive_water_surface.py; the fit and its checks are written up in
docs/fishintel/WATER_SURFACE_LAYERS.md ("Reading closer to the bank").

A thermal pixel near the bank is a PSF-weighted mix of the water and of hot
surfaces around it. "Hot" is QA_PIXEL non-water: land outside the NHD polygon
AND non-water inside it (topped-out grass, emergent beds, docks). The second
group is why the pipeline's 200 m NHD standoff still reads ~+1 C beside mats.

    R_obs = (1 - w) R_water + S,   w = G_sigma * H,   S = G_sigma * (H R_hot)
    R = eps B(T) + (1 - eps) Ld    (band-10 K1/K2 Planck, eps from the emis band)

R_hot ("demix", the default): each hot cell's own observed radiance with its
water share removed (only hot cells with water weight <= 0.5, spread over the
PSF); where a hot cell has no usable neighbour, land falls back to the local
land median (clear land >= 200 m from any water, 2 km box) and in-lake
non-water to the water level + DMAT_C. "landmed" uses the fallbacks only.
Invert for R_water and go back to C with the cell's own emissivity (w = 0 is
the identity). Trust only QA-water cells with w <= w_max.

    correct_water_temp(st, qa_pixel, cdist, st_qa, emis, lake) -> dict
      "T_water"  corrected water C, NaN where it should not be trusted
      "w"        hot-surface weight of every cell
      "T_obs"    the product's own C
      "trusted"  bool mask
Inputs are the raw C2 L2 arrays on one native grid (lwir11 DN, QA_PIXEL,
ST_CDIST, ST_QA, ST_EMIS as int16/uint16) and the lake polygon burned on it.
"""
import numpy as np
from scipy import ndimage

PX = 30.0
K1, K2 = 774.8853, 1321.0789          # Landsat 8 TIRS B10 (MTL K1/K2)
K_BY_PLATFORM = {"landsat-8": (774.8853, 1321.0789), "landsat-9": (799.0284, 1329.2405)}
ST_SCALE, ST_OFFSET = 0.00341802, 149.0
QA_BAD = 0b11111
QA_CLEAR, QA_WATER = 1 << 6, 1 << 7

SIGMA_M = 60.0      # effective Gaussian PSF sigma, fitted (N half 60, S half 65, whole lake 60)
DMAT_C = 3.0        # small in-lake non-water (mats too small to read), C above water level, fitted
LD = 4.0            # downwelling sky radiance W m-2 sr-1 um-1 (assumed; fit is flat 0-6)
EPS_WATER = 0.990
W_MAX = 0.10        # trust limit on the hot-surface weight, chosen from the data
W_UNKNOWN_MAX = 0.01
MIN_CLOUD_KM, MAX_STQA_K = 1.0, 4.5
COLD_OUTLIER_C = 1.5
WARM_OUTLIER_C = 3.0


def _planck(tk, k=(K1, K2)): return k[0] / (np.exp(k[1] / tk) - 1.0)
def _inv_planck(r, k=(K1, K2)): return k[1] / np.log(k[0] / np.maximum(r, 1e-6) + 1.0)


def moving_median(v, mask, half, lo, hi, bw, min_n=20):
    size = 2 * half + 1
    m = mask & ~np.isnan(v)
    tot = ndimage.uniform_filter(m.astype("float64"), size, mode="constant") * size * size
    out = np.full(v.shape, np.nan)
    prev = np.zeros(v.shape)
    for e in np.arange(lo, hi + bw, bw):
        c = ndimage.uniform_filter((m & (v <= e)).astype("float64"), size, mode="constant") * size * size
        hit = np.isnan(out) & (c >= 0.5 * tot) & (tot > 0)
        frac = np.clip((0.5 * tot - prev) / np.maximum(c - prev, 1e-9), 0, 1)
        out[hit] = (e - bw + frac * bw)[hit]
        prev = c
    out[tot < min_n] = np.nan
    return out


def reference_fields(T, valid, water, lake, gate, d_in, d_nw):
    """Local land temperature and a broad water level, both independent of the
    near-shore water being corrected."""
    land = gate & ~water & ~lake & (d_in >= 200)
    tl = moving_median(T, land, 33, 20.0, 65.0, 0.05)            # 2 km box
    tl4 = moving_median(T, land, 67, 20.0, 65.0, 0.1)            # 4 km fallback
    tl = np.where(np.isnan(tl), tl4, tl)
    tl = np.where(np.isnan(tl), np.nanmedian(T[land]), tl)
    lvl_mask = gate & water & lake & (d_nw >= 200)
    lake_med = float(np.nanmedian(T[gate & water & lake]))
    lvl_mask &= T >= lake_med - COLD_OUTLIER_C
    wl = moving_median(T, lvl_mask, 100, 28.0, 42.0, 0.05)       # 6 km box
    wl = np.where(np.isnan(wl), float(np.nanmedian(T[lvl_mask])), wl)
    return tl, wl, lake_med


def correct_water_temp(st, qa_pixel, cdist, st_qa, emis, lake, sigma_m=SIGMA_M, dmat=DMAT_C,
                       w_max=W_MAX, Ld=LD, refs=None, return_all=False, tail=None, hot="demix",
                       platform="landsat-8", drop_outliers=True):
    """tail = (fraction, sigma2_m) adds a wide second Gaussian to the PSF.
    drop_outliers=False leaves cells far from the lake median in "trusted", so
    a caller's own scene check can count them (undetected cloud reads cold).
    hot = "landmed": land at its local >= 200 m-inland median;
          "demix":   land (and large mats) at their own observed radiance, the
                     water share removed, smoothed over the PSF; falls back to
                     "landmed" where a hot cell has no usable neighbour."""
    lake = lake.astype(bool)
    T = np.where(st > 0, st.astype("float64") * ST_SCALE + ST_OFFSET - 273.15, np.nan)
    valid = (st > 0) & ((qa_pixel & QA_BAD) == 0)
    water = (qa_pixel & QA_WATER) != 0
    clear = (qa_pixel & QA_CLEAR) != 0
    cloudfar = (cdist != -9999) & (cdist * 0.01 >= MIN_CLOUD_KM)
    gate = (valid & clear & cloudfar & (st_qa != -9999) & (st_qa * 0.01 <= MAX_STQA_K))
    eps = np.where(emis > 0, emis * 1e-4, EPS_WATER)
    nonwater = valid & ~water
    anywater = lake | (valid & water)
    d_in = ndimage.distance_transform_edt(~anywater) * PX - PX / 2
    d_nw = ndimage.distance_transform_edt(~nonwater) * PX
    if refs is None:
        refs = reference_fields(T, valid, water, lake, gate, d_in, d_nw)
    tl, wl, lake_med = refs
    land_eps = float(np.nanmedian(eps[gate & ~water & ~lake & (d_in >= 200)]))

    kk = K_BY_PLATFORM[platform]
    def R(tc, e): return e * _planck(tc + 273.15, kk) + (1 - e) * Ld
    s = sigma_m / PX
    def psf(x):
        g = ndimage.gaussian_filter(x, s, mode="nearest", truncate=4.0)
        if tail is not None:
            f, s2 = tail
            g = (1 - f) * g + f * ndimage.gaussian_filter(x, s2 / PX, mode="nearest", truncate=4.0)
        return g
    H_land = (nonwater | ~valid) & ~lake       # unknown outside the lake: assume land
    H_mat = nonwater & lake
    H = (H_land | H_mat).astype("float64")
    R_obs = R(T, eps)
    R_land0 = R(tl, land_eps)
    R_mat0 = R(wl + dmat, land_eps)
    w = psf(H)
    if hot == "demix":
        ww = 1.0 - w
        usable = valid & clear & cloudfar & ~water & (ww <= 0.5)
        R_raw = (np.nan_to_num(R_obs) - ww * R(wl, EPS_WATER)) / np.maximum(1 - ww, 1e-3)
        def spread(cls, fallback):
            u = (usable & cls).astype("float64")
            num = ndimage.gaussian_filter(u * R_raw, s, mode="nearest", truncate=4.0)
            den = ndimage.gaussian_filter(u, s, mode="nearest", truncate=4.0)
            est = num / np.maximum(den, 1e-9)
            return np.where(den >= 0.1, est, fallback)
        R_land = spread(H_land, R_land0)
        R_mat = spread(H_mat, R_mat0)
    else:
        R_land, R_mat = R_land0, R_mat0
    R_hot = np.where(H_land, R_land, np.where(H_mat, R_mat, 0.0))
    S = psf(H * R_hot)
    w_unknown = psf((~valid).astype("float64"))
    R_w = (R_obs - S) / np.maximum(1 - w, 1e-3)
    # Back to temperature with the cell's own emissivity, so w = 0 is the identity.
    Tw = _inv_planck((R_w - (1 - eps) * Ld) / eps, kk) - 273.15
    # Where the geometry lets the water be read at all: QA water inside the
    # lake, little hot surface or unknown pixel in the PSF.
    readable = (valid & water & lake & (w <= w_max) & (w_unknown <= W_UNKNOWN_MAX))
    trusted = readable & gate & ~np.isnan(Tw)
    if drop_outliers:
        trusted &= (Tw >= lake_med - COLD_OUTLIER_C) & (Tw <= lake_med + WARM_OUTLIER_C)
    out = {"T_water": np.where(trusted, Tw, np.nan), "w": w, "T_obs": T, "trusted": trusted,
           "readable": readable}
    if return_all:
        out.update(Tw_all=Tw, S=S, R_obs=R_obs, gate=gate, water=water, valid=valid, d_nw=d_nw,
                   d_in=d_in, H_mat=H_mat, H_land=H_land, tl=tl, wl=wl, lake_med=lake_med, eps=eps,
                   w_unknown=w_unknown, R_hot=R_hot, w_mat=psf(H_mat.astype("float64")))
    return out
