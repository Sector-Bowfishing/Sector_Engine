"""Certification protocol section 3, SYKE part, bulk implementation of the same rules (blind: Arvo is never selected).
1) lake sites (YmpTyyppi_Id=10) -> lakes (J_Jarvi_Id, else the site); 2) every Secchi (YmpSuure_Id=4) and ice
(YmpSuure_Id=2) event ID from the first 2017-04-01 event on (IDs only); 3) event date, site and coordinates for the
Secchi events; eligible = lake site, 2017-04-01..2025-11-30, April-November, no ice record. 4) lakes in the seeded order
(seed 20261002, as build_syke_candidates.py), first 400 with an eligible event, up to 3 events per lake in distinct
months where possible (seeded). Writes syke_candidates.csv."""
import json, random, csv, time, urllib.request, urllib.parse, collections, concurrent.futures as cf
B = "https://rajapinnat.ymparisto.fi/api/vesla/2.0/odata"
def get(entity, params):
    url = f"{B}/{entity}?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    for i in range(8):
        try:
            with urllib.request.urlopen(url, timeout=45) as r: return json.load(r)["value"]
        except Exception:
            time.sleep(2 + i)
    raise RuntimeError(url[:300])
def page_all(entity, params, top=500, workers=8):
    out, skip, done = [], 0, False
    with cf.ThreadPoolExecutor(workers) as ex:
        while not done:
            futs = [ex.submit(get, entity, {**params, "$top": top, "$skip": skip + i * top}) for i in range(workers)]
            for f in futs:
                v = f.result(); out += v
                if len(v) < top: done = True
            skip += workers * top
    return out
sites = page_all("Paikka", {"$filter": "YmpTyyppi_Id eq 10", "$select": "Paikka_Id,J_Jarvi_Id,KoordErLat,KoordErLong", "$orderby": "Paikka_Id"})
sites = [s for s in sites if s.get("KoordErLat") and s.get("KoordErLong")]
site = {s["Paikka_Id"]: s for s in sites}
lakes = collections.defaultdict(list)
for s in sites: lakes[s.get("J_Jarvi_Id") or f"P{s['Paikka_Id']}"].append(s)
lake_of = {s["Paikka_Id"]: (s.get("J_Jarvi_Id") or f"P{s['Paikka_Id']}") for s in sites}
print("lake sites", len(sites), "lakes", len(lakes), flush=True)
x0 = get("Naytteenotto", {"$filter": "Aika ge datetime'2017-04-01T00:00:00'", "$select": "Naytteenotto_Id", "$orderby": "Naytteenotto_Id", "$top": 1})[0]["Naytteenotto_Id"]
print("first 2017-04 event id", x0, flush=True)
sec = {h["Naytteenotto_Id"] for h in page_all("YmpHavainto", {"$filter": f"YmpSuure_Id eq 4 and Naytteenotto_Id ge {x0}", "$select": "Naytteenotto_Id", "$orderby": "Naytteenotto_Id"})}
ice = {h["Naytteenotto_Id"] for h in page_all("YmpHavainto", {"$filter": f"YmpSuure_Id eq 2 and Naytteenotto_Id ge {x0}", "$select": "Naytteenotto_Id", "$orderby": "Naytteenotto_Id"})}
print("secchi events", len(sec), "ice events", len(ice), flush=True)
want = sec - ice
allev = page_all("Naytteenotto", {"$filter": f"Naytteenotto_Id ge {x0}", "$select": "Naytteenotto_Id,Paikka_Id,Aika,KoordErLat,KoordErLong", "$orderby": "Naytteenotto_Id"})
ev = [e for e in allev if e["Naytteenotto_Id"] in want]
print("events since cutoff", len(allev), "secchi without ice", len(ev), flush=True)
el = [e for e in ev if e["Paikka_Id"] in site and "2017-04-01" <= e["Aika"][:10] <= "2025-11-30" and 4 <= int(e["Aika"][5:7]) <= 11]
by = collections.defaultdict(list)
for e in el: by[lake_of[e["Paikka_Id"]]].append(e)
print("eligible events", len(el), "lakes with eligible events", len(by), flush=True)
order = sorted(lakes, key=str); random.Random(20261002).shuffle(order)
rng = random.Random(20261002); picked, found, tried = [], 0, 0
for lk in order:
    if found >= 400: break
    tried += 1; ok = by.get(lk)
    if not ok: continue
    found += 1
    ok = sorted(ok, key=lambda e: e["Naytteenotto_Id"]); rng.shuffle(ok)
    months, chosen = set(), []
    for e in ok:
        if e["Aika"][5:7] not in months: chosen.append(e); months.add(e["Aika"][5:7])
        if len(chosen) == 3: break
    for e in ok:
        if len(chosen) == 3: break
        if e not in chosen: chosen.append(e)
    for e in chosen:
        s = site[e["Paikka_Id"]]
        lat = float(e.get("KoordErLat") or s["KoordErLat"]); lon = float(e.get("KoordErLong") or s["KoordErLong"])
        picked.append({"id": f"SYKE:{e['Naytteenotto_Id']}", "lat": lat, "lon": lon, "date": e["Aika"][:10], "set": "SYKE", "src": "SYKE", "lake": f"FI-{lk}", "state": "FI"})
with open("syke_candidates.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id", "lat", "lon", "date", "set", "src", "lake", "state"]); w.writeheader(); w.writerows(picked)
print("done: lakes tried", tried, "lakes", found, "events", len(picked), dict(sorted(collections.Counter(p['date'][5:7] for p in picked).items())))
