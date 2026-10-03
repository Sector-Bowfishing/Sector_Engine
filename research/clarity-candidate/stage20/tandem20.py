"""Stage 20 track A (value-blind): the NOMINAL reprocessed S2A/S2C tandem (29 Oct - 19 Dec 2024) at Sen2Cor level.

Earth Search collection sentinel-2-c1-l2a holds the reprocessed nominal products of both satellites (S2C N0511 regenerated
in 2026). Pairs: same MGRS tile, same day, S2A and S2C sensing within 180 s (the tandem flew S2C ~30 s behind S2A), both
scenes <= 60% cloud. Each site of sites20.json is read on both scenes with the frozen Stage 6 extractor (identical 60 m
disk, identical production gates). One record per (site, physical pass). Writes tandem20_pairs.json and
tandem20_readouts.json. No Secchi value is read."""
import json, os, sys, datetime as dt, concurrent.futures as cf
S = os.environ["CLARITY_RESEARCH_ROOT"]
sys.path.insert(0, f"{S}/stage6")
import extract as E6
sites = json.load(open(f"{S}/stage20/sites20.json"))
T = lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def pairs_at(s):
    body = {"collections": ["sentinel-2-c1-l2a"], "intersects": {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
            "datetime": "2024-10-29T00:00:00Z/2024-12-19T23:59:59Z", "limit": 200}
    try:
        f = E6.post(E6.ES_SEARCH, body).get("features", [])
    except Exception as e:
        return s, [], str(e)[:80]
    A = [i for i in f if i["properties"]["platform"] == "sentinel-2a" and (i["properties"].get("eo:cloud_cover") or 100) <= 60]
    C = [i for i in f if i["properties"]["platform"] == "sentinel-2c" and (i["properties"].get("eo:cloud_cover") or 100) <= 60]
    out = []
    for c in C:
        for a in A:
            if c["properties"].get("grid:code") != a["properties"].get("grid:code"): continue
            d = (T(c["properties"]["datetime"]) - T(a["properties"]["datetime"])).total_seconds()
            if abs(d) < 180: out.append((a, c, d))
    # one record per physical pass (date): keep the tile pair with the lowest combined cloud
    best = {}
    for a, c, d in out:
        k = c["properties"]["datetime"][:10]; cl = a["properties"]["eo:cloud_cover"] + c["properties"]["eo:cloud_cover"]
        if k not in best or cl < best[k][3]: best[k] = (a, c, d, cl)
    return s, list(best.values()), None


def read(job):
    s, (a, c, d, cl) = job
    rec = {"site": s["site"], "lat": s["lat"], "lon": s["lon"], "date": c["properties"]["datetime"][:10], "tile": c["properties"].get("grid:code"), "dt_s": round(d, 1),
           "s2a": a["id"], "s2c": c["id"], "s2a_product": a["properties"].get("s2:product_uri"), "s2c_product": c["properties"].get("s2:product_uri"),
           "s2a_baseline": a["properties"].get("s2:processing_baseline"), "s2c_baseline": c["properties"].get("s2:processing_baseline"),
           "rel_orbit": a["properties"].get("sat:relative_orbit"), "sun_elev": a["properties"].get("view:sun_elevation"), "sun_az": a["properties"].get("view:sun_azimuth"),
           "view_inc_a": a["properties"].get("view:incidence_angle"), "view_inc_c": c["properties"].get("view:incidence_angle"),
           "cloud_a": a["properties"].get("eo:cloud_cover"), "cloud_c": c["properties"].get("eo:cloud_cover")}
    for tag, it in (("a", a), ("c", c)):
        try:
            rec[tag] = E6.sample(it, s["lat"], s["lon"])
        except Exception as e:
            rec[tag] = {"error": str(e)[:120]}
    return rec


if __name__ == "__main__":
    jobs = []
    with cf.ThreadPoolExecutor(8) as ex:
        for s, pr, err in ex.map(pairs_at, sites):
            jobs += [(s, p) for p in pr]
    json.dump([{"site": s["site"], "s2a": p[0]["id"], "s2c": p[1]["id"], "dt_s": p[2]} for s, p in jobs], open(f"{S}/stage20/tandem20_pairs.json", "w"))
    print(len(jobs), "site-pass pairs", flush=True)
    out = []
    with cf.ThreadPoolExecutor(8) as ex:
        for i, r in enumerate(ex.map(read, jobs), 1):
            out.append(r)
            if i % 100 == 0: print(i, flush=True)
    json.dump(out, open(f"{S}/stage20/tandem20_readouts.json", "w"), default=str)
    print("TANDEM20_DONE", len(out), flush=True)
