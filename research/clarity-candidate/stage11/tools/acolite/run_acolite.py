#!/usr/bin/env python
"""Run ACOLITE (DSF) on a Sentinel-2 L1C SAFE for a lat/lon box.

    run(safe_path, limit, outdir, tag) -> path of the L2W NetCDF
    python run_acolite.py SAFE S W N E OUTDIR TAG

limit = [S, W, N, E] in degrees. Outputs go to OUTDIR/TAG/ (L1R, L2R, L2W
NetCDF + ACOLITE logs + run_info.json with settings, runtime and version).

Environment: use tools/acolite/venv/bin/python. GDAL's Python bindings are
not installable here, so the ctypes shim in tools/acolite/osgeo_shim (over
rasterio's bundled libgdal 3.12.4) is put on sys.path before ACOLITE loads.
"""
import json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'src')
SHIM = os.path.join(HERE, 'osgeo_shim')
for p in (SRC, SHIM):
    if p not in sys.path:
        sys.path.insert(0, p)

import acolite as ac  # noqa: E402

# Settings shared by every run (anything not listed = ACOLITE default,
# including the Sentinel-2 sensor defaults in src/config/defaults/S2?_MSI.txt).
BASE_SETTINGS = {
    'aerosol_correction': 'dark_spectrum',   # DSF (ACOLITE default)
    'dsf_aot_estimate': 'tiled',             # retried with 'fixed' if tiled fails
    'dsf_residual_glint_correction': True,
    's2_target_res': 20,
    'ancillary_data': False,                 # no NASA OBPG/Earthdata: default pressure/ozone/water vapour/wind
    'l2w_parameters': ['rhow_*', 'Rrs_*'],
    'l2w_mask': True,                        # default L2W masking
    'dsf_write_aot_550': True,               # per-pixel AOT(550) in the L2R, sampled by sample.py
    'l1r_delete_netcdf': False,
    'l2r_delete_netcdf': False,              # keep L2R (rhos)
    'rgb_rhot': False, 'rgb_rhos': False,    # skip quicklook PNGs
    'verbosity': 2,
}


def acolite_version():
    commit = None
    try:
        commit = subprocess.run(['git', '-C', SRC, 'rev-parse', 'HEAD'], capture_output=True,
                                text=True, check=True).stdout.strip()
        tag = subprocess.run(['git', '-C', SRC, 'describe', '--tags', '--exact-match'],
                             capture_output=True, text=True).stdout.strip() or None
    except Exception:
        tag = None
    return {'acolite_version_string': getattr(ac, 'version', None), 'acolite_tag': tag, 'commit': commit}


def _l2w_from(processed):
    for k in processed:
        for f in processed[k].get('l2w', []):
            if os.path.exists(f):
                return f
    return None


def _l2r_from(processed):
    for k in processed:
        for f in processed[k].get('l2r', []):
            if os.path.exists(f):
                return f
    return None


def run(safe_path, limit, outdir, tag):
    safe_path = os.path.abspath(safe_path)
    out = os.path.abspath(os.path.join(outdir, tag))
    os.makedirs(out, exist_ok=True)
    S, W, N, E = [float(v) for v in limit]

    attempts = []
    l2w = None
    for estimate in ('tiled', 'fixed'):
        settings = dict(BASE_SETTINGS)
        settings.update({'inputfile': safe_path, 'output': out, 'limit': [S, W, N, E],
                         'region_name': tag, 'dsf_aot_estimate': estimate})
        t0 = time.time()
        err = None
        processed = {}
        try:
            ret = ac.acolite.acolite_run(settings=settings)
            processed = ret[0] if isinstance(ret, tuple) else ret
            if not isinstance(processed, dict):
                processed = {}
        except Exception as e:  # tiled DSF can fail on small/odd crops -> retry fixed
            err = '{}: {}'.format(type(e).__name__, e)
        dt = time.time() - t0
        l2w = _l2w_from(processed)
        attempts.append({'dsf_aot_estimate': estimate, 'runtime_s': round(dt, 1), 'error': err,
                         'l2w': l2w, 'l2r': _l2r_from(processed),
                         'l1r': [f for k in processed for f in processed[k].get('l1r', [])]})
        if l2w is not None:
            break

    info = {'safe': safe_path, 'limit_SWNE': [S, W, N, E], 'tag': tag,
            'settings': {k: v for k, v in BASE_SETTINGS.items()},
            'dsf_aot_estimate_used': attempts[-1]['dsf_aot_estimate'] if l2w else None,
            'attempts': attempts, **acolite_version()}
    with open(os.path.join(out, 'run_info.json'), 'w') as f:
        json.dump(info, f, indent=2, default=str)
    if l2w is None:
        raise RuntimeError('ACOLITE produced no L2W for {} (see {}/run_info.json and ACOLITE logs)'.format(
            safe_path, out))
    return l2w


if __name__ == '__main__':
    if len(sys.argv) != 8:
        sys.exit('usage: python run_acolite.py SAFE S W N E OUTDIR TAG')
    safe, s, w, n, e, outdir, tag = sys.argv[1:]
    t0 = time.time()
    path = run(safe, [s, w, n, e], outdir, tag)
    print('L2W: {}'.format(path))
    print('wall time: {:.1f} s'.format(time.time() - t0))
