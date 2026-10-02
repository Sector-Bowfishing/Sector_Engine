"""Stage 17 section 3: Open-Meteo ERA5 daily precipitation (mm) at each development event site, date-11..date+11
(NASA POWER PRECTOTCORR if Open-Meteo fails). Used only for compatibility. Writes rain17.json."""
import json, time, datetime as dt, urllib.request, concurrent.futures as cf, os
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = f"{S}/stage17/scenes"
corp = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
sel = json.load(open(f"{D}/neighbors.json"))
out = json.load(open(f"{D}/rain17.json")) if os.path.exists(f"{D}/rain17.json") else {}
def get(cid):
    x = corp[cid]; d0 = dt.date.fromisoformat(x["date"]); a, b = (d0 - dt.timedelta(days=11)).isoformat(), (d0 + dt.timedelta(days=11)).isoformat()
    for i in range(4):
        try:
            u = f"https://archive-api.open-meteo.com/v1/archive?latitude={x['lat']}&longitude={x['lon']}&start_date={a}&end_date={b}&daily=precipitation_sum"
            with urllib.request.urlopen(u, timeout=60) as r: j = json.load(r)
            return cid, {"src": "open-meteo-era5", "rain": dict(zip(j["daily"]["time"], j["daily"]["precipitation_sum"]))}
        except Exception: time.sleep(3 * (i + 1))
    try:
        u = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR&community=AG&longitude={x['lon']}&latitude={x['lat']}&start={a.replace('-', '')}&end={b.replace('-', '')}&format=JSON"
        with urllib.request.urlopen(u, timeout=60) as r: j = json.load(r)
        v = j["properties"]["parameter"]["PRECTOTCORR"]
        return cid, {"src": "nasa-power", "rain": {f"{k[:4]}-{k[4:6]}-{k[6:]}": (None if val < 0 else val) for k, val in v.items()}}
    except Exception as e:
        return cid, {"src": None, "error": str(e)[:100]}
todo = [c for c, v in sel.items() if v and c not in out]
with cf.ThreadPoolExecutor(4) as ex:
    for n, (cid, v) in enumerate(ex.map(get, todo), 1):
        out[cid] = v
        if n % 200 == 0: json.dump(out, open(f"{D}/rain17.json", "w")); print(n, len(todo), flush=True)
json.dump(out, open(f"{D}/rain17.json", "w"))
import collections; print("done", len(out), collections.Counter(v.get("src") for v in out.values()))
