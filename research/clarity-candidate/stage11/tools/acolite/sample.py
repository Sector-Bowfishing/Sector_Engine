#!/usr/bin/env python
"""Sample an ACOLITE L2W NetCDF around a point.

    sample(nc_path, lat, lon, radius_m=60) -> dict
    python sample.py L2W.nc LAT LON [RADIUS_M]

Returned dict:
  'B01'..'B12' (those present): MEDIAN rhow (= pi * Rrs) over valid pixels
      whose centre lies within radius_m of (lat, lon). Valid = finite in every
      returned band (ACOLITE sets L2W-masked pixels to NaN), so all bands use
      the same pixel set.
  'n'        : number of valid pixels used
  'n_radius' : pixels within the radius before masking
  'n_flagged': pixels within the radius with a non-zero l2_flags value
  'aot'      : processor aerosol info from the file attributes (ac_* etc.)
               plus 'aot_550_median' sampled from the per-pixel aot_550
               (L2W, or the sibling L2R) when present
  'bands'    : {band: ACOLITE variable name, e.g. 'B02': 'rhow_492'}
  'sensor', 'isodate', 'file'
Band mapping: ACOLITE names variables by the RSR-weighted centre wavelength,
which differs between S2A/S2B/S2C (e.g. rhow_492 vs rhow_489). The file's own
'<band>_name' / '<band>_wave' attributes are used when present; otherwise each
variable is matched to the nearest RSR-weighted centre of its sensor, computed
from ACOLITE's own RSR files (src/data/RSR).
"""
import os, sys
import numpy as np
from netCDF4 import Dataset

BANDS = ['B01', 'B02', 'B03', 'B04', 'B05', 'B06', 'B07', 'B08', 'B8A', 'B11', 'B12']

RSR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src', 'data', 'RSR')
# RSR file ACOLITE uses by default per sensor (config/defaults/<sensor>.txt rsr_version)
RSR_FILES = {'S2A_MSI': 'S2A_MSI.txt', 'S2B_MSI': 'S2B_MSI.txt', 'S2C_MSI': 'S2C_MSI_V4.txt'}
_CENTRES = {}


def band_centres(sensor):
    """RSR-weighted centre wavelength (nm) per band, from ACOLITE's own RSR file
    (same parsing rules as acolite.shared.rsr_read; 1 nm grid like rsr_convolute_dict)."""
    sensor = sensor if sensor in RSR_FILES else 'S2A_MSI'
    if sensor in _CENTRES:
        return _CENTRES[sensor]
    data, cur = {}, None
    with open(os.path.join(RSR_DIR, RSR_FILES[sensor]), encoding='utf-8') as f:
        for line in f:
            if line[:1] in ('#', ';'):
                if '/' in line:
                    continue
                if 'Band' in line or 'BAND' in line:
                    cur = line.split()[-1]
                    data[cur] = ([], [])
            elif line.strip() and cur is not None:
                a = line.split()
                wl = float(a[0]); wl = wl if wl > 100 else wl * 1000
                data[cur][0].append(wl); data[cur][1].append(float(a[1]))
    grid = np.arange(250, 2500, dtype=float)
    out = {}
    for b, (w, r) in data.items():
        ri = np.interp(grid, w, r, left=0, right=0)
        name = 'B8A' if b.upper() == '8A' else 'B{:02d}'.format(int(b))
        out[name] = float((grid * ri).sum() / ri.sum())
    _CENTRES[sensor] = out
    return out


AOT_ATTS = ['ac_aot_550', 'ac_aot_550_mean', 'ac_model', 'ac_fit', 'ac_bands', 'ac_nbands_fit',
            'ac_band1', 'ac_band2', 'dsf_aot_estimate', 'pressure', 'uoz', 'uwv', 'wind']


def _att_py(v):
    if isinstance(v, np.ndarray):
        return v.tolist() if v.size > 1 else v.item()
    if isinstance(v, np.generic):
        return v.item()
    return v


def _band_map(nc, prefix='rhow_'):
    """{'B02': 'rhow_492', ...} for the variables present."""
    gatts = {k: nc.getncattr(k) for k in nc.ncattrs()}
    names = [v for v in nc.variables if v.startswith(prefix)]
    out = {}
    # 1) exact: ACOLITE stores '<rsr band>_name' (wave name used in the variable) per band
    for k, v in gatts.items():
        if not k.endswith('_name'):
            continue
        rb = k[:-5]
        if not (rb.isdigit() or rb.upper() == '8A'):
            continue
        band = 'B8A' if rb.upper() == '8A' else 'B{:02d}'.format(int(rb))
        var = prefix + str(v)
        if var in names:
            out[band] = var
    if out:
        return out
    # 2) fallback: nearest RSR-weighted centre for the sensor
    table = band_centres(str(gatts.get('sensor', 'S2A_MSI')))
    for var in names:
        try:
            wl = float(nc.variables[var].getncattr('wavelength'))
        except Exception:
            wl = float(var[len(prefix):])
        band = min(table, key=lambda b: abs(table[b] - wl))
        out[band] = var
    return out


def _haversine(lat1, lon1, lat2, lon2):
    r = 6371008.8
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = p2 - p1
    dl = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def _window(lat2d, lon2d, lat, lon, radius_m):
    d = _haversine(lat, lon, lat2d, lon2d)
    i, j = np.unravel_index(np.nanargmin(d), d.shape)
    if d[i, j] > radius_m + 50:
        return None
    # pixel size estimate from neighbours
    return i, j, d


def sample(nc_path, lat, lon, radius_m=60):
    out = {'file': nc_path}
    with Dataset(nc_path) as nc:
        nc.set_auto_mask(False)
        gatts = {k: nc.getncattr(k) for k in nc.ncattrs()}
        out['sensor'] = _att_py(gatts.get('sensor'))
        out['isodate'] = _att_py(gatts.get('isodate'))
        lat2d = nc.variables['lat'][:]
        lon2d = nc.variables['lon'][:]
        w = _window(lat2d, lon2d, lat, lon, radius_m)
        bmap = _band_map(nc)
        bands = [b for b in BANDS if b in bmap]
        out['bands'] = {b: bmap[b] for b in bands}
        aot = {k: _att_py(gatts[k]) for k in AOT_ATTS if k in gatts}
        if w is None:
            out.update({b: float('nan') for b in bands})
            out.update({'n': 0, 'n_radius': 0, 'n_flagged': 0, 'aot': aot,
                        'note': 'point outside the processed extent'})
            return out
        _, _, d = w
        sel = d <= radius_m
        out['n_radius'] = int(sel.sum())
        vals = {b: np.asarray(nc.variables[bmap[b]][:][sel], dtype=np.float64) for b in bands}
        for b in bands:  # honour _FillValue explicitly (auto-mask is off)
            fv = getattr(nc.variables[bmap[b]], '_FillValue', None)
            if fv is not None:
                vals[b][vals[b] == fv] = np.nan
        valid = np.ones(out['n_radius'], dtype=bool)
        for b in bands:
            valid &= np.isfinite(vals[b])
        if 'l2_flags' in nc.variables:
            fl = nc.variables['l2_flags'][:][sel]
            out['n_flagged'] = int((fl != 0).sum())
        out['n'] = int(valid.sum())
        for b in bands:
            out[b] = float(np.median(vals[b][valid])) if out['n'] > 0 else float('nan')

        # per-pixel AOT(550): L2W if copied, else the sibling L2R (same grid)
        aot_arr = None
        if 'aot_550' in nc.variables:
            aot_arr = np.asarray(nc.variables['aot_550'][:][sel], dtype=np.float64)
    if aot_arr is None and nc_path.endswith('_L2W.nc'):
        l2r = nc_path[:-len('_L2W.nc')] + '_L2R.nc'
        try:
            with Dataset(l2r) as r:
                r.set_auto_mask(False)
                if 'aot_550' in r.variables and r.variables['aot_550'].shape == sel.shape:
                    aot_arr = np.asarray(r.variables['aot_550'][:][sel], dtype=np.float64)
                    aot['aot_550_source'] = 'L2R'
                for k in AOT_ATTS:
                    if k not in aot and k in r.ncattrs():
                        aot[k] = _att_py(r.getncattr(k))
        except (OSError, FileNotFoundError):
            pass
    if aot_arr is not None:
        f = np.isfinite(aot_arr)
        aot['aot_550_median'] = float(np.median(aot_arr[f])) if f.any() else float('nan')
    out['aot'] = aot
    return out


if __name__ == '__main__':
    import json
    if len(sys.argv) not in (4, 5):
        sys.exit('usage: python sample.py L2W.nc LAT LON [RADIUS_M]')
    r = float(sys.argv[4]) if len(sys.argv) == 5 else 60
    print(json.dumps(sample(sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), r), indent=2))
