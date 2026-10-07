"""Stage 3C gust candidate C: HRRR surface GUST for the same inits/leads as the NBM v5.0 corpus (pre-registered).

  python research/hrrr_gust.py [--workers 6]

Writes hrrr/<lake>/<YYYYMMDDHH>.json.gz (steps: leadHours, validTime, gustMS) to the historical store, cut out with the
same lake boxes. HRRR CONUS wrfsfc from noaa-hrrr-bdp-pds. Diagnostic only: never read by the Candidate."""
import os, sys, time
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from sector_wind.store import LocalStore
from sector_wind.ingest import load_config, _ensure_grid_manifest, _round
from sector_wind.grib import read_idx, find, fetch, decode, FetchError, DecodeError
from sector_wind.sample import iso

ROOT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50")
URL = "https://noaa-hrrr-bdp-pds.s3.amazonaws.com/hrrr.{d}/conus/hrrr.t{h:02d}z.wrfsfcf{f:02d}.grib2"
START, END = datetime(2026, 5, 6, 0, tzinfo=timezone.utc), datetime(2026, 10, 6, 23, tzinfo=timezone.utc)
LEADS = [1, 3, 6, 12, 18]


def one(t):
    store, cfg = LocalStore(ROOT), load_config()
    if all(store.exists(f"hrrr/{lk}/{t:%Y%m%d%H}.json.gz") for lk in cfg["lakes"]):
        return t, "skip"
    per = {lk: [] for lk in cfg["lakes"]}; missing = []
    for f in LEADS:
        url = URL.format(d=f"{t:%Y%m%d}", h=t.hour, f=f)
        try:
            e = find(read_idx(url), "GUST", "surface", "", f"{f} hour fcst")
            if e is None:
                raise DecodeError("GUST surface not in idx")
            g = decode(fetch(url, (e.start, e.end)))
        except (FetchError, DecodeError) as ex:
            missing.append({"lead": f, "error": str(ex)[:160]}); continue
        for lk, lc in cfg["lakes"].items():
            cells = _ensure_grid_manifest(store, "hrrr", lk, lc["bbox"], g.grid_key, 3.0)
            per[lk].append({"leadHours": f, "validTime": iso(t + timedelta(hours=f)),
                            "gustMS": _round(np.where(g.missing[cells], np.nan, g.values[cells]), 2)})
    for lk, steps in per.items():
        if steps:
            store.put_json(f"hrrr/{lk}/{t:%Y%m%d%H}.json.gz", {"model": "HRRR", "initTime": iso(t), "grid": f"grids/hrrr/{lk}.json",
                                                               "source": URL.format(d=f"{t:%Y%m%d}", h=t.hour, f=0), "steps": steps, "missing": missing})
    return t, "ok" if not missing else f"partial {len(missing)}"


if __name__ == "__main__":
    from multiprocessing import Pool
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 6
    inits = [START + timedelta(hours=h) for h in range(int((END - START).total_seconds() // 3600) + 1)]
    n = 0
    with Pool(w) as p:
        for t, st in p.imap_unordered(one, inits, chunksize=4):
            n += 1
            if n % 200 == 0 or st.startswith("partial"):
                print(f"{n}/{len(inits)} {t:%Y-%m-%dT%HZ} {st}", flush=True)
    print("HRRR DONE", flush=True)
