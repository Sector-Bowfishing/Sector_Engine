"""National Water Model analysis streamflow for every arm reach, one value a
day at a fixed hour, from the public operational archive
(gs://national-water-model, analysis_assim channel_rt tm00) -- the modeled
side of the NWM-vs-USGS comparison and the replay's modeled discharge.

Each file is the whole CONUS channel network (~14 MB, one gzip chunk), so it
is downloaded, the arm reaches read, and deleted.

usage: geo/bin/python nwm_history.py <hydrology.json> <start YYYY-MM-DD> <end> <out.json> [--hour 16] [--threads 4]
"""
import os, sys, json, argparse, tempfile, datetime as dt, urllib.request, time, concurrent.futures as cf
import numpy as np, h5py

BASE = "https://storage.googleapis.com/national-water-model"
CFS = 35.3146667

ap = argparse.ArgumentParser()
ap.add_argument("graph"); ap.add_argument("start"); ap.add_argument("end"); ap.add_argument("out")
ap.add_argument("--hour", type=int, default=16); ap.add_argument("--threads", type=int, default=4)
a = ap.parse_args()
arms = [x for x in json.load(open(a.graph))["arms"] if x.get("nwmFeatureId")]
reaches = sorted({int(x["nwmFeatureId"]) for x in arms})
res = json.load(open(a.out)) if os.path.exists(a.out) else {
    "source": f"NWM analysis_assim channel_rt tm00 at {a.hour:02d}Z ({BASE})", "units": "ft3/s",
    "reachToArms": {str(r): [x["id"] for x in arms if int(x["nwmFeatureId"]) == r] for r in reaches}, "days": {}}
tmp = tempfile.mkdtemp()


def one(day):
    url = f"{BASE}/nwm.{day:%Y%m%d}/analysis_assim/nwm.t{a.hour:02d}z.analysis_assim.channel_rt.tm00.conus.nc"
    path = os.path.join(tmp, f"{day:%Y%m%d}.nc")
    for i in range(3):
        try:
            urllib.request.urlretrieve(url, path); break
        except Exception:
            time.sleep(3 * (i + 1))
    else:
        return day, None
    try:
        with h5py.File(path) as f:
            fid = f["feature_id"][:]; s = f["streamflow"]; scale = float(s.attrs["scale_factor"][0])
            idx = np.searchsorted(fid, reaches)
            vals = s[:]
            out = {}
            for r, i in zip(reaches, idx):
                if i < len(fid) and fid[i] == r and vals[i] > -9000:
                    out[str(r)] = round(float(vals[i]) * scale * CFS, 3)
            return day, out
    except Exception:
        return day, None
    finally:
        os.remove(path)


days = []
d = dt.date.fromisoformat(a.start)
while d <= dt.date.fromisoformat(a.end):
    if d.isoformat() not in res["days"]:
        days.append(d)
    d += dt.timedelta(days=1)
with cf.ThreadPoolExecutor(a.threads) as ex:
    for n, (day, out) in enumerate(ex.map(one, days), 1):
        res["days"][day.isoformat()] = out
        if n % 20 == 0:
            json.dump(res, open(a.out, "w")); print(day, flush=True)
json.dump(res, open(a.out, "w"))
print("done", len(res["days"]))
