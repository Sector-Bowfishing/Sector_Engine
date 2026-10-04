"""Stage 22 part 1 (metadata only; no reflectance, no Secchi): candidate pair lists.
  S     warm-season SAME-DAY S2C <-> S2A/S2B: same UTC date, |dt| <= 180 min, both <= 30% cloud, 15 Apr - 15 Oct 2025/2026,
        at the 463 Stage 20 sites + 38 high-latitude lakes; one pair per (site, S2C pass).
  T2    warm-season SAME-TRACK 2-day S2C -> S2A: same relative orbit and MGRS tile, S2A sensed 2 days (+-1 h) after S2C
        (S2A's 2025-26 extended-campaign orbit trails S2C's track by 2 days: identical viewing geometry), both <= 20% cloud,
        Apr-Oct 2025 / Apr-Sep 2026, Stage 20 sites; per site and year the pair with the lowest combined cloud.
  FLOOR same-day S2A <-> S2B at the high-latitude lakes (two full-authority sensors ~10 min apart), Jun-Sep, both <= 20% cloud.
Writes pairs22_meta.json. Physical pass = (platform, UTC date, relative orbit)."""
import json, os, sys, datetime as dt, collections, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage6"); import extract as E6
T = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
HL = {"Inari FI": (68.95, 27.75), "Tornetrask SE": (68.36, 19.10), "Kemijarvi FI": (66.70, 27.45), "Oulujarvi FI": (64.33, 27.20), "Pielinen FI": (63.30, 29.60),
      "Saimaa FI": (61.25, 28.40), "Paijanne FI": (61.60, 25.50), "Storsjon SE": (63.20, 14.55), "Hornavan SE": (66.20, 17.60), "Siljan SE": (60.88, 14.75),
      "Vanern SE": (58.95, 13.20), "Mjosa NO": (60.80, 10.80), "Ladoga RU": (61.00, 31.50), "Onega RU": (61.80, 35.40), "Imandra RU": (67.60, 33.00),
      "Peipus EE": (58.70, 27.50), "Myvatn IS": (65.60, -17.00), "Thingvallavatn IS": (64.18, -21.15), "Great Bear CA": (65.90, -121.00), "Great Slave CA": (61.60, -114.00),
      "Athabasca CA": (59.20, -109.00), "Baker Lake CA": (64.15, -95.50), "Nettilling CA": (66.50, -70.50), "Lac la Ronge CA": (55.10, -105.00), "Iliamna US-AK": (59.60, -155.00),
      "Tustumena US-AK": (60.20, -150.90), "Becharof US-AK": (57.90, -156.40), "Harding US-AK": (64.42, -146.85), "Lake of the Woods": (49.30, -94.80), "Winnipeg CA": (52.10, -97.40),
      "Teshekpuk US-AK": (70.58, -153.55), "Tuktoyaktuk CA": (69.40, -132.90), "Taymyr RU": (74.50, 102.50), "Hazen CA": (81.80, -71.30), "Kangerlussuaq GL": (67.00, -50.60),
      "Iesjavri NO": (69.65, 24.20), "Inarijarvi-S FI": (68.80, 27.60), "Lake Peyto CA": (51.70, -116.50)}
sites = [{"site": s["site"], "lat": s["lat"], "lon": s["lon"]} for s in json.load(open(f"{S}/stage20/sites20.json"))] + [{"site": f"H:{k}", "lat": v[0], "lon": v[1]} for k, v in HL.items()]
prop = lambda i, k: i["properties"].get(k)
orbit = lambda i: (prop(i, "s2:product_uri") or "_____").split("_")[4]


def items(s, a, b, cloud):
    out = []
    for y in range(int(a[:4]), int(b[:4]) + 1):
        for m in range(1, 13):
            lo, hi = f"{y}-{m:02d}-01", (dt.date(y, m, 28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
            if hi.isoformat() < a or lo > b: continue
            try:
                f = E6.post(E6.ES_SEARCH, {"collections": ["sentinel-2-c1-l2a"], "intersects": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                                           "datetime": f"{max(lo, a)}T00:00:00Z/{min(hi.isoformat(), b)}T23:59:59Z", "limit": 100, "query": {"eo:cloud_cover": {"lte": cloud}}}).get("features", [])
            except Exception: f = []
            out += f
    return out


def rec(s, c, o, kind):
    return {"kind": kind, "site": s["site"], "lat": s["lat"], "lon": s["lon"], "c": c["id"], "o": o["id"], "c_platform": prop(c, "platform"), "o_platform": prop(o, "platform"),
            "c_time": prop(c, "datetime"), "o_time": prop(o, "datetime"), "dt_min": round((T(prop(c, "datetime")) - T(prop(o, "datetime"))).total_seconds() / 60, 1),
            "c_orbit": orbit(c), "o_orbit": orbit(o), "tile": prop(c, "grid:code"), "o_tile": prop(o, "grid:code"), "c_cloud": prop(c, "eo:cloud_cover"), "o_cloud": prop(o, "eo:cloud_cover"),
            "c_baseline": prop(c, "s2:processing_baseline"), "o_baseline": prop(o, "s2:processing_baseline"), "c_sun_elev": prop(c, "view:sun_elevation"), "o_sun_elev": prop(o, "view:sun_elevation"),
            "c_view_inc": prop(c, "view:incidence_angle"), "o_view_inc": prop(o, "view:incidence_angle"), "c_product": prop(c, "s2:product_uri"), "o_product": prop(o, "s2:product_uri"),
            "c_pass": f"{prop(c, 'platform')}|{prop(c, 'datetime')[:10]}|{orbit(c)}", "o_pass": f"{prop(o, 'platform')}|{prop(o, 'datetime')[:10]}|{orbit(o)}"}


def one(s):
    out = []
    for a, b in (("2025-04-01", "2025-10-31"), ("2026-04-01", "2026-09-30")):
        f = items(s, a, b, 30)
        C = [i for i in f if prop(i, "platform") == "sentinel-2c"]; A_ = [i for i in f if prop(i, "platform") == "sentinel-2a"]; B_ = [i for i in f if prop(i, "platform") == "sentinel-2b"]
        warm = lambda i: f"{prop(i, 'datetime')[:4]}-04-15" <= prop(i, "datetime")[:10] <= f"{prop(i, 'datetime')[:4]}-10-15"
        # S: same-day S2C <-> S2A/B
        best = {}
        for c in C:
            if not warm(c): continue
            for o in A_ + B_:
                d = abs((T(prop(c, "datetime")) - T(prop(o, "datetime"))).total_seconds()) / 60
                if prop(c, "datetime")[:10] == prop(o, "datetime")[:10] and d <= 180:
                    k = rec(s, c, o, "S")["c_pass"]; cl = prop(c, "eo:cloud_cover") + prop(o, "eo:cloud_cover")
                    if k not in best or cl < best[k][0]: best[k] = (cl, rec(s, c, o, "S"))
        out += [v[1] for v in best.values()]
        # T2: same track, S2A 2 days after S2C
        cand = []
        for c in C:
            if prop(c, "eo:cloud_cover") > 20: continue
            for o in A_:
                if prop(o, "eo:cloud_cover") > 20 or orbit(o) != orbit(c) or prop(o, "grid:code") != prop(c, "grid:code"): continue
                d = (T(prop(o, "datetime")) - T(prop(c, "datetime"))).total_seconds() / 3600
                if abs(d - 48) <= 1: cand.append((prop(c, "eo:cloud_cover") + prop(o, "eo:cloud_cover"), c["id"], rec(s, c, o, "T2")))
        if cand and not s["site"].startswith("H:"): out.append(sorted(cand, key=lambda x: (x[0], x[1]))[0][2])
        # FLOOR: same-day S2A <-> S2B at the high-latitude lakes, Jun-Sep
        if s["site"].startswith("H:"):
            fl = {}
            for a_ in A_:
                for b_ in B_:
                    if prop(a_, "datetime")[:10] != prop(b_, "datetime")[:10] or not ("-06-01" <= prop(a_, "datetime")[4:10] <= "-09-30"): continue
                    if prop(a_, "eo:cloud_cover") > 20 or prop(b_, "eo:cloud_cover") > 20: continue
                    if abs((T(prop(a_, "datetime")) - T(prop(b_, "datetime"))).total_seconds()) / 60 > 180: continue
                    k = prop(a_, "datetime")[:10]; cl = prop(a_, "eo:cloud_cover") + prop(b_, "eo:cloud_cover")
                    r = rec(s, b_, a_, "FLOOR")                     # "c" = S2B, "o" = S2A
                    if k not in fl or cl < fl[k][0]: fl[k] = (cl, r)
            out += [v[1] for v in fl.values()]
    return out


if __name__ == "__main__":
    allp = []
    with cf.ThreadPoolExecutor(8) as ex:
        for i, r in enumerate(ex.map(one, sites), 1):
            allp += r
            if i % 100 == 0: print(i, "sites", len(allp), "pairs", flush=True)
    json.dump(allp, open(f"{S}/stage22/pairs22_meta.json", "w"), indent=0)
    c = collections.Counter(p["kind"] for p in allp); print("pairs by kind", dict(c))
    for k in ("S", "T2", "FLOOR"):
        P = [p for p in allp if p["kind"] == k]
        if not P: continue
        print(k, "sites", len({p["site"] for p in P}), "| months", dict(sorted(collections.Counter(p["c_time"][5:7] for p in P).items())), "| |dt| min", sorted({int(abs(p["dt_min"])) for p in P})[:6], "| lat", min(p["lat"] for p in P), max(p["lat"] for p in P),
              "| baselines", dict(collections.Counter(p["c_baseline"] for p in P)), "| years", dict(collections.Counter(p["c_time"][:4] for p in P)))
