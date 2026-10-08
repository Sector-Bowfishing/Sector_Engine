"""Stage 3D new fields (pre-registered: stage3d/WIND_FORCING_CORRECTION_PREREG.md §1).

  python research/forcing_fetch.py qmd  [--workers 8]   # synoptic inits: NBM qmd WIND/GUST exceedance + percentile levels
  python research/forcing_fetch.py hrrr [--workers 8]   # all inits: HRRR 10 m UGRD/VGRD
Writes qmdx/<lake>/<init>.json.gz and hrrruv/<lake>/<init>.json.gz to the historical v50 store (lake cut-outs only)."""
import os, sys, time
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config, _ensure_grid_manifest, _round, NBM_QMD
from sector_wind.grib import read_idx, find, fetch, decode, FetchError, DecodeError
from sector_wind.sample import iso

ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
HRRR = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.{d}/conus/hrrr.t{h:02d}z.wrfsfcf{f:02d}.grib2"
START, END = datetime(2026, 5, 6, 0, tzinfo=timezone.utc), datetime(2026, 10, 6, 23, tzinfo=timezone.utc)
LEADS = [1, 3, 6, 12, 18]
QMD_FIELDS = [("windProbGt3.6011", "WIND", "prob >3.6011:prob fcst 255/255"), ("windProbGt5.6588", "WIND", "prob >5.6588:prob fcst 255/255"),
              ("windProbGt8.7456", "WIND", "prob >8.7456:prob fcst 255/255"), ("windProbGt11.3178", "WIND", "prob >11.3178:prob fcst 255/255"),
              ("windP75", "WIND", "75% level"),
              ("gustProbGt8.7456", "GUST", "prob >8.7456:prob fcst 255/255"), ("gustProbGt11.3178", "GUST", "prob >11.3178:prob fcst 255/255"),
              ("gustProbGt15.4333", "GUST", "prob >15.4333:prob fcst 255/255"), ("gustP50", "GUST", "50% level"), ("gustP75", "GUST", "75% level")]


def _put(store, cfg, kind, t, per, prod, spacing, src, missing):
    for lk, steps in per.items():
        if steps:
            store.put_json(f"{kind}/{lk}/{t:%Y%m%d%H}.json.gz", {"initTime": iso(t), "grid": f"grids/{prod}/{lk}.json", "source": src,
                                                                  "steps": steps, "missing": missing})


def one_qmd(t):
    store, cfg = LocalStore(ROOT), load_config()
    if all(store.exists(f"qmdx/{lk}/{t:%Y%m%d%H}.json.gz") for lk in cfg["lakes"]):
        return t, "skip"
    per = {lk: [] for lk in cfg["lakes"]}; missing = []
    for f in LEADS:
        url = NBM_QMD.format(d=f"{t:%Y%m%d}", h=t.hour, f=f)
        try:
            ent = read_idx(url); vals = {}
            for name, var, tail in QMD_FIELDS:
                e = find(ent, var, "10 m above ground", tail, f"{f} hour fcst")
                if e is None and tail.startswith("prob >"):     # label rounding differs by release (11.3177 vs 11.3178): match numerically
                    thr = float(tail[6:].split(":")[0])
                    e = next((x for x in ent if x.var == var and x.level == "10 m above ground" and f"{f} hour fcst" in x.step
                              and x.tail.startswith("prob >") and abs(float(x.tail[6:].split(":")[0]) - thr) < 0.001), None)
                if e is None:
                    raise DecodeError(f"{var} {tail} missing")
                vals[name] = decode(fetch(url, (e.start, e.end)))
        except (FetchError, DecodeError) as ex:
            missing.append({"lead": f, "error": str(ex)[:160]}); continue
        g0 = next(iter(vals.values()))
        for lk, lc in cfg["lakes"].items():
            cells = _ensure_grid_manifest(store, "nbm", lk, lc["bbox"], g0.grid_key, 2.5)
            per[lk].append({"leadHours": f, "validTime": iso(t + timedelta(hours=f)),
                            **{k: _round(np.where(v.missing[cells], np.nan, v.values[cells]), 2) for k, v in vals.items()}})
    _put(store, cfg, "qmdx", t, per, "nbm", 2.5, NBM_QMD.format(d=f"{t:%Y%m%d}", h=t.hour, f=0), missing)
    return t, "ok" if not missing else f"partial {missing[:1]}"


def one_hrrr(t):
    store, cfg = LocalStore(ROOT), load_config()
    if all(store.exists(f"hrrruv/{lk}/{t:%Y%m%d%H}.json.gz") for lk in cfg["lakes"]):
        return t, "skip"
    per = {lk: [] for lk in cfg["lakes"]}; missing = []
    for f in LEADS:
        url = HRRR.format(d=f"{t:%Y%m%d}", h=t.hour, f=f)
        try:
            ent = read_idx(url)
            eu = find(ent, "UGRD", "10 m above ground", "", f"{f} hour fcst"); ev = find(ent, "VGRD", "10 m above ground", "", f"{f} hour fcst")
            if eu is None or ev is None:
                raise DecodeError("UGRD/VGRD 10 m missing")
            u = decode(fetch(url, (eu.start, eu.end))); v = decode(fetch(url, (ev.start, ev.end)))
        except (FetchError, DecodeError) as ex:
            missing.append({"lead": f, "error": str(ex)[:160]}); continue
        for lk, lc in cfg["lakes"].items():
            cells = _ensure_grid_manifest(store, "hrrr", lk, lc["bbox"], u.grid_key, 3.0)
            per[lk].append({"leadHours": f, "validTime": iso(t + timedelta(hours=f)),
                            "u": _round(np.where(u.missing[cells], np.nan, u.values[cells]), 2),
                            "v": _round(np.where(v.missing[cells], np.nan, v.values[cells]), 2)})
    _put(store, cfg, "hrrruv", t, per, "hrrr", 3.0, HRRR.format(d=f"{t:%Y%m%d}", h=t.hour, f=0), missing)
    return t, "ok" if not missing else f"partial {missing[:1]}"


if __name__ == "__main__":
    from multiprocessing import Pool
    kind = sys.argv[1]; w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 8
    inits = [START + timedelta(hours=h) for h in range(int((END - START).total_seconds() // 3600) + 1)]
    if kind == "qmd":
        inits = [t for t in inits if t.hour % 6 == 0]
    fn = one_qmd if kind == "qmd" else one_hrrr
    n = 0
    with Pool(w) as p:
        for t, st in p.imap_unordered(fn, inits, chunksize=2):
            n += 1
            if n % 200 == 0 or st.startswith("partial"):
                print(f"{n}/{len(inits)} {t:%Y-%m-%dT%HZ} {st}", flush=True)
    print(f"{kind.upper()} DONE", flush=True)
