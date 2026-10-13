"""Stage 3D.1 §A: NDFD (NWS forecaster-edited, CONUS 2.5 km) issued forecasts from s3://noaa-ndfd-pds/wmo/ (archive since
2020-04-16). For each synoptic hour HH in the NBM v5.0 corpus window, the FIRST issuance in that hour is paired with the NBM
cycle Sector would hold at that moment (init HH-1, published ~HH:05). Only the leading bytes of each file are fetched
(messages are in valid-time order); values at the 8 frozen stations by nearest grid point.

  python research/ndfd_fetch.py [--workers 8]   -> historical/v50/ndfd/<YYYYMMDDHH>.json (station -> valid -> spd/dir/gust)"""
import io, json, os, re, struct, sys, time, urllib.request
from datetime import datetime, timedelta, timezone
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import eccodes
import numpy as np
from sector_wind.ingest import load_config
from sector_wind.grib import decode, grid, row_scramble_ratio

OUT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50/ndfd")
B = "https://noaa-ndfd-pds.s3.amazonaws.com"
EL = {"wspd": "YCUZ98", "wdir": "YBUZ98", "wgust": "YWUZ98"}
START, END = datetime(2026, 5, 6, tzinfo=timezone.utc), datetime(2026, 10, 6, 18, tzinfo=timezone.utc)
FIRST_BYTES = 30_000_000
_IDX = {}


def _get(url, rng=None, tries=4):
    for k in range(tries):
        try:
            h = {"User-Agent": "SectorWind research"}
            if rng: h["Range"] = f"bytes={rng[0]}-{rng[1]}"
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=180) as r:
                return r.read()
        except Exception as e:
            last = e; time.sleep(5 * (k + 1))
    raise last


def first_key(el, t):
    pre = f"wmo/{el}/{t:%Y/%m/%d}/{EL[el]}_KWBN_{t:%Y%m%d%H}"
    keys = re.findall(r"<Key>([^<]+)</Key>", _get(f"{B}/?list-type=2&prefix={pre}").decode())
    return sorted(keys)[0] if keys else None


def messages(buf):
    """Complete GRIB2 messages in a (possibly truncated) WMO bundle."""
    i = 0
    while True:
        j = buf.find(b"GRIB", i)
        if j < 0 or j + 16 > len(buf): return
        n = struct.unpack(">Q", buf[j + 8:j + 16])[0]
        if j + n > len(buf): return
        yield buf[j:j + n]; i = j + n


def one(t):
    p = os.path.join(OUT, f"{t:%Y%m%d%H}.json")
    if os.path.exists(p):
        return t, "skip"
    st = load_config()["stations"]; res = {"issue": {}, "values": {}}
    for el in EL:
        k = first_key(el, t)
        if not k:
            return t, f"missing {el}"
        res["issue"][el] = k.rsplit("_", 1)[1]
        buf = _get(f"{B}/{k}", (0, FIRST_BYTES))
        for m in messages(buf):
            h = eccodes.codes_new_from_message(m)
            try:
                vt = datetime.strptime(f"{eccodes.codes_get(h, 'validityDate')}{int(eccodes.codes_get(h, 'validityTime')):04d}", "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
                if vt.minute != 0 or vt > t + timedelta(hours=19):
                    continue
                # NDFD uses alternativeRowScanning=1: raw codes_get_values is row-scrambled. Decode with the project's
                # decoder (row order fixed + self-check), then index by the decoder's own lat/lon.
                f = decode(m)
                if f.grid_key not in _IDX:
                    lat, lon = grid(f.grid_key)
                    _IDX[f.grid_key] = {sid: int(np.argmin((lat - s["lat"]) ** 2 + ((lon - s["lon"]) * np.cos(np.radians(s["lat"]))) ** 2)) for sid, s in st.items()}
                    nx = int(f.grid_key.split(":")[1].split("x")[0]); i0 = next(iter(_IDX[f.grid_key].values()))
                    if not row_scramble_ratio(f.values, np.arange(max(0, i0 - 3000), i0 + 3000), nx) < 3.0:
                        raise RuntimeError("NDFD decoder self-check failed")
                for sid in st:
                    v = float(f.values[_IDX[f.grid_key][sid]])
                    res["values"].setdefault(sid, {}).setdefault(vt.strftime("%Y-%m-%dT%H:%M:%SZ"), {})[el] = None if v > 9000 else round(float(v), 2)
            finally:
                eccodes.codes_release(h)
    os.makedirs(OUT, exist_ok=True); json.dump(res, open(p, "w"))
    return t, "ok"


if __name__ == "__main__":
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 8
    ts = [START + timedelta(hours=h) for h in range(0, int((END - START).total_seconds() // 3600) + 1, 6)]
    n = 0
    with Pool(w) as pool:
        for t, s in pool.imap_unordered(one, ts):
            n += 1
            if s != "ok" or n % 50 == 0:
                print(f"{n}/{len(ts)} {t:%Y-%m-%dT%HZ} {s}", flush=True)
    print("NDFD DONE", flush=True)
