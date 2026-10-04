"""Stage 23 part 1 (metadata only; no reflectance, no Secchi): candidate pair lists.
  FLOOR23  same UTC day S2A <-> S2B, |dt| <= 30 min, both <= 20% tile cloud, both sun elevation >= 25 deg, 2025-01-01 ..
           2026-10-03, at the Stage 20 inland-lake sites (L:) between 25 and 50 deg N. One observation per (site, UTC date):
           the S2A item and the S2B item with the lowest combined cloud (ties: item ids). Physical pass = (platform,
           UTC date, relative orbit); the two items are two different physical passes by construction.
  T2N      nominal N0513 S2C -> S2A same track: same relative orbit and MGRS tile, S2A sensed 48 +- 1 h after S2C, both
           <= 20% cloud, S2C baseline >= 05.13, S2C sun >= 25 deg, 2026-08-01 .. 2026-10-03, every Stage 20 site
           (25-50 N); one pair per (site, S2C physical pass), lowest combined cloud.
Writes pairs23_meta.json."""
import json, os, sys, datetime as dt, collections, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage6"); import extract as E6
T = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
REGION = {"Northeast": "ME NH VT MA RI CT NY NJ PA", "Southeast": "MD DE VA WV NC SC GA FL AL MS TN KY AR LA",
          "Midwest": "OH IN IL MI WI MN IA MO", "Plains": "ND SD NE KS OK TX", "West": "MT ID WY CO UT NV AZ NM CA OR WA"}
ST2R = {s: r for r, ss in REGION.items() for s in ss.split()}
sites = [s for s in json.load(open(f"{S}/stage20/sites20.json")) if s["site"].startswith("L:") and 25 <= s["lat"] <= 50 and s["site"].split("|")[-1] in ST2R]
for s in sites: s["region"] = ST2R[s["site"].split("|")[-1]]
prop = lambda i, k: i["properties"].get(k)
orbit = lambda i: (prop(i, "s2:product_uri") or "_____").split("_")[4]


def items(s, a, b, cloud):
    out = []
    for y in range(int(a[:4]), int(b[:4]) + 1):
        for m in range(1, 13):
            lo, hi = f"{y}-{m:02d}-01", (dt.date(y, m, 28) + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
            if hi.isoformat() < a or lo > b: continue
            for attempt in range(3):
                try:
                    f = E6.post(E6.ES_SEARCH, {"collections": ["sentinel-2-c1-l2a"], "intersects": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                                               "datetime": f"{max(lo, a)}T00:00:00Z/{min(hi.isoformat(), b)}T23:59:59Z", "limit": 100, "query": {"eo:cloud_cover": {"lte": cloud}}}).get("features", [])
                    break
                except Exception: f = None
            out += f or []
    return out


def rec(s, c, o, kind):
    return {"kind": kind, "site": s["site"], "region": s["region"], "lat": s["lat"], "lon": s["lon"], "c": c["id"], "o": o["id"], "c_platform": prop(c, "platform"), "o_platform": prop(o, "platform"),
            "c_time": prop(c, "datetime"), "o_time": prop(o, "datetime"), "dt_min": round((T(prop(c, "datetime")) - T(prop(o, "datetime"))).total_seconds() / 60, 1),
            "c_orbit": orbit(c), "o_orbit": orbit(o), "tile": prop(c, "grid:code"), "o_tile": prop(o, "grid:code"), "c_cloud": prop(c, "eo:cloud_cover"), "o_cloud": prop(o, "eo:cloud_cover"),
            "c_baseline": prop(c, "s2:processing_baseline"), "o_baseline": prop(o, "s2:processing_baseline"), "c_sun_elev": prop(c, "view:sun_elevation"), "o_sun_elev": prop(o, "view:sun_elevation"),
            "c_view_inc": prop(c, "view:incidence_angle"), "o_view_inc": prop(o, "view:incidence_angle"), "c_product": prop(c, "s2:product_uri"), "o_product": prop(o, "s2:product_uri"),
            "c_pass": f"{prop(c, 'platform')}|{prop(c, 'datetime')[:10]}|{orbit(c)}", "o_pass": f"{prop(o, 'platform')}|{prop(o, 'datetime')[:10]}|{orbit(o)}"}


def one(s):
    out = []
    f = items(s, "2025-01-01", "2026-10-03", 20)
    A_ = [i for i in f if prop(i, "platform") == "sentinel-2a"]; B_ = [i for i in f if prop(i, "platform") == "sentinel-2b"]; C = [i for i in f if prop(i, "platform") == "sentinel-2c"]
    sun_ok = lambda i: (prop(i, "view:sun_elevation") or 0) >= 25
    # FLOOR23: same-day S2A <-> S2B within 30 min ("c" = S2B, "o" = S2A, as Stage 22)
    best = {}
    for b_ in B_:
        for a_ in A_:
            if prop(a_, "datetime")[:10] != prop(b_, "datetime")[:10] or not (sun_ok(a_) and sun_ok(b_)): continue
            if abs((T(prop(a_, "datetime")) - T(prop(b_, "datetime"))).total_seconds()) / 60 > 30: continue
            k = prop(b_, "datetime")[:10]; key = (prop(a_, "eo:cloud_cover") + prop(b_, "eo:cloud_cover"), a_["id"], b_["id"])
            if k not in best or key < best[k][0]: best[k] = (key, rec(s, b_, a_, "FLOOR23"))
    out += [v[1] for v in best.values()]
    # T2N: N0513 S2C -> S2A, same track, 48 +- 1 h
    t2 = {}
    for c in C:
        if (prop(c, "s2:processing_baseline") or "0") < "05.13" or not sun_ok(c) or prop(c, "datetime")[:10] < "2026-08-01": continue
        for o in A_:
            if orbit(o) != orbit(c) or prop(o, "grid:code") != prop(c, "grid:code"): continue
            d = (T(prop(o, "datetime")) - T(prop(c, "datetime"))).total_seconds() / 3600
            if abs(d - 48) > 1: continue
            r = rec(s, c, o, "T2N"); key = (prop(c, "eo:cloud_cover") + prop(o, "eo:cloud_cover"), c["id"], o["id"])
            if r["c_pass"] not in t2 or key < t2[r["c_pass"]][0]: t2[r["c_pass"]] = (key, r)
    out += [v[1] for v in t2.values()]
    return out


if __name__ == "__main__":
    allp = []
    with cf.ThreadPoolExecutor(8) as ex:
        for i, r in enumerate(ex.map(one, sites), 1):
            allp += r
            if i % 50 == 0: print(i, "/", len(sites), "sites", len(allp), "pairs", flush=True)
    json.dump({"sites": sites, "pairs": allp}, open(f"{S}/stage23/pairs23_meta.json", "w"), indent=0)
    for k in ("FLOOR23", "T2N"):
        P = [p for p in allp if p["kind"] == k]
        print(k, len(P), "lakes", len({p["site"] for p in P}), "regions", dict(collections.Counter(p["region"] for p in P)),
              "| months", dict(sorted(collections.Counter(p["c_time"][:7] for p in P).items())), "| |dt| min", sorted({int(abs(p["dt_min"])) for p in P})[:8],
              "| baselines", dict(collections.Counter(p["c_baseline"] for p in P)))
