"""Certification protocol section 3, SYKE part (blind: Arvo is never selected). Lake sites (YmpTyyppi_Id=10); lakes
(J_Jarvi_Id, else the site) in seeded random order (seed 20261002); for each, sampling events 2017-04-01..2025-11-30 in
April-November; an event is eligible if it has a Secchi record (YmpSuure_Id=4) and no ice-thickness record
(YmpSuure_Id=2) - only Naytteenotto_Id and YmpSuure_Id are requested. Up to 3 events per lake, in distinct months where
possible (seeded); stop at 400 lakes with an eligible event. Writes syke_candidates.csv (extractor format)."""
import json, random, csv, time, urllib.request, urllib.parse, collections
B = "https://rajapinnat.ymparisto.fi/api/vesla/2.0/odata"
def get(entity, params):
    url = f"{B}/{entity}?" + urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    for i in range(8):
        try:
            with urllib.request.urlopen(url, timeout=120) as r: return json.load(r)["value"]
        except Exception:
            time.sleep(5 * (i + 1))
    raise RuntimeError(url)
def page(entity, params, top=500):
    out, skip = [], 0
    while True:
        v = get(entity, {**params, "$top": top, "$skip": skip}); out += v
        if len(v) < top: return out
        skip += top
sites = page("Paikka", {"$filter": "YmpTyyppi_Id eq 10", "$select": "Paikka_Id,J_Jarvi_Id,KoordErLat,KoordErLong"})
sites = [s for s in sites if s.get("KoordErLat") and s.get("KoordErLong")]
lakes = collections.defaultdict(list)
for s in sites: lakes[s.get("J_Jarvi_Id") or f"P{s['Paikka_Id']}"].append(s)
order = sorted(lakes, key=str); random.Random(20261002).shuffle(order)
print("lake sites", len(sites), "lakes", len(lakes), flush=True)
import concurrent.futures as cf
def eligible_events(lk):
    """Sites scanned in Paikka_Id order; stop once eligible events span 3 distinct months, or after 25 sites (big lakes)."""
    out = []
    for s in sorted(lakes[lk], key=lambda s: s["Paikka_Id"])[:25]:
        ev = page("Naytteenotto", {"$filter": f"Paikka_Id eq {s['Paikka_Id']} and Aika ge datetime'2017-04-01T00:00:00' and Aika le datetime'2025-11-30T23:59:59'",
                                   "$select": "Naytteenotto_Id,Paikka_Id,Aika,KoordErLat,KoordErLong"})
        ev = [e for e in ev if 4 <= int(e["Aika"][5:7]) <= 11]
        if not ev: continue
        has = collections.defaultdict(set); ids = [e["Naytteenotto_Id"] for e in ev]
        def keys(chunk):
            f = " or ".join(f"Naytteenotto_Id eq {x}" for x in chunk)
            try:
                return page("YmpHavainto", {"$filter": f"({f}) and (YmpSuure_Id eq 4 or YmpSuure_Id eq 2)", "$select": "Naytteenotto_Id,YmpSuure_Id"})
            except RuntimeError:
                if len(chunk) == 1: raise
                h = len(chunk) // 2
                return keys(chunk[:h]) + keys(chunk[h:])
        for i in range(0, len(ids), 20):
            for h in keys(ids[i:i + 20]):
                has[h["Naytteenotto_Id"]].add(h["YmpSuure_Id"])
        out += [e for e in ev if 4 in has[e["Naytteenotto_Id"]] and 2 not in has[e["Naytteenotto_Id"]]]
        if len({e["Aika"][5:7] for e in out}) >= 3: break
    return out
rng = random.Random(20261002); picked, tried, found = [], 0, 0
with cf.ThreadPoolExecutor(8) as ex:
    for b in range(0, len(order), 64):           # batches in the seeded order; results consumed in that order
        batch = order[b:b + 64]
        for lk, ok in zip(batch, ex.map(eligible_events, batch)):
            if found >= 400: break
            tried += 1
            if not ok: continue
            found += 1
            ok.sort(key=lambda e: e["Naytteenotto_Id"]); rng.shuffle(ok)
            months, chosen = set(), []
            for e in ok:                                   # distinct months first
                if e["Aika"][5:7] not in months: chosen.append(e); months.add(e["Aika"][5:7])
                if len(chosen) == 3: break
            for e in ok:
                if len(chosen) == 3: break
                if e not in chosen: chosen.append(e)
            site = {s["Paikka_Id"]: s for s in lakes[lk]}
            for e in chosen:
                s = site.get(e["Paikka_Id"], lakes[lk][0])
                lat = float(e.get("KoordErLat") or s["KoordErLat"]); lon = float(e.get("KoordErLong") or s["KoordErLong"])
                picked.append({"id": f"SYKE:{e['Naytteenotto_Id']}", "lat": lat, "lon": lon, "date": e["Aika"][:10], "set": "SYKE", "src": "SYKE", "lake": f"FI-{lk}", "state": "FI"})
        print(tried, "lakes tried,", found, "with eligible events,", len(picked), "events", flush=True)
        if found >= 400: break
with open("syke_candidates.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id", "lat", "lon", "date", "set", "src", "lake", "state"]); w.writeheader(); w.writerows(picked)
print("done: lakes tried", tried, "lakes", len({p['lake'] for p in picked}), "events", len(picked), dict(collections.Counter(p['date'][5:7] for p in picked)))
