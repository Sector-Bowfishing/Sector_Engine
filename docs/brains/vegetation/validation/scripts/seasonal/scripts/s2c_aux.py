"""Aux data: (1) Open-Meteo archive daily mean air temperature (labelled GDD PROXY only; Water Temp Brain will own temperature),
(2) processing baseline per STAC date/source (cheap STAC-only queries). Outputs out/airtemp_{lake}.json, out/baselines_{lake}.json"""
import json, math, requests, warnings, time, collections
warnings.filterwarnings("ignore")
from pystac_client import Client
from common import *
import s2lib as S
W = json.load(open(H/"out/windows.json"))
cat = Client.open(S.STAC)
for lk, w in W.items():
    x0, y0, x1, y1 = w["window"]; la, lo = (y0+y1)/2, (x0+x1)/2
    f = H/f"out/airtemp_{lk}.json"
    if not f.exists():
        for _ in range(5):
            r = requests.get("https://archive-api.open-meteo.com/v1/archive", params=dict(latitude=round(la, 3), longitude=round(lo, 3), start_date="2016-01-01", end_date="2025-12-31", daily="temperature_2m_mean", timezone="UTC"), timeout=90)
            if r.status_code == 200: break
            time.sleep(10)
        r.raise_for_status(); d = r.json()["daily"]; json.dump(dict(time=d["time"], t=d["temperature_2m_mean"]), open(f, "w"))
    f2 = H/f"out/baselines_{lk}.json"
    if not f2.exists():
        BB = [x0, y0, x1, y1]; out = collections.defaultdict(dict)
        for coll, tag in (("sentinel-2-c1-l2a", "c1"), ("sentinel-2-l2a", "l2a")):
            for k in range(6):
                try: its = list(cat.search(collections=[coll], bbox=BB, datetime="2017-01-01/2025-12-31", query={"eo:cloud_cover": {"lt": 85}}, max_items=6000).item_collection()); break
                except Exception: time.sleep(4)
            for i in its: out[i.datetime.date().isoformat()].setdefault(tag, []).append(i.properties.get("s2:processing_baseline"))
        json.dump(out, open(f2, "w"))
    print(lk, "ok", flush=True)
