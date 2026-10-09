"""Stage 3D.1 §A: Open-Meteo Single Runs API (issued model runs archived since 2026-04-02) at the 8 frozen stations, synoptic
inits of the NBM v5.0 corpus window. Paced at ~1 request/s (free tier, research only; licensing caveat recorded in the report).
  python research/openmeteo_runs.py   -> historical/v50/openmeteo/<model>/<YYYYMMDDHH>.json (raw response, immutable)"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sector_wind.ingest import load_config
OUT = os.path.expanduser("~/Library/Caches/sector-wind/historical/v50/openmeteo")
MODELS = ["ecmwf_ifs", "gfs_global", "icon_global", "ukmo_global_deterministic_10km", "ncep_nbm_conus"]
START, END = datetime(2026, 5, 6, tzinfo=timezone.utc), datetime(2026, 10, 6, 18, tzinfo=timezone.utc)
st = load_config()["stations"]; ids = list(st)
lat = ",".join(str(st[s]["lat"]) for s in ids); lon = ",".join(str(st[s]["lon"]) for s in ids)
def job(tm):
    t, m = tm
    p = os.path.join(OUT, m, f"{t:%Y%m%d%H}.json")
    if os.path.exists(p):
        return 0
    if True:
        q = {"latitude": lat, "longitude": lon, "models": m, "run": f"{t:%Y-%m-%dT%H:00}", "hourly": "wind_speed_10m,wind_direction_10m,wind_gusts_10m",
             "wind_speed_unit": "ms", "timezone": "GMT", "forecast_hours": 25}
        url = "https://single-runs-api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q)
        for k in range(4):
            try:
                body = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SectorWind research"}), timeout=60).read(); break
            except Exception as e:
                body = None; time.sleep(10 * (k + 1))
        if body is None:
            print("FAILED", m, t, flush=True); return 0
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "wb").write(body); os.chmod(p, 0o444)
        time.sleep(0.5)
        return 1


from concurrent.futures import ThreadPoolExecutor
tasks = [(START + timedelta(hours=6 * k), m) for k in range(int((END - START).total_seconds() // 21600) + 1) for m in MODELS]
with ThreadPoolExecutor(4) as ex:
    n = sum(ex.map(job, tasks))
print("OPENMETEO DONE", n, flush=True)
