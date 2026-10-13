#!/usr/bin/env python3
"""Track 5: upstream/downstream relationships between directory lakes, via the USGS NLDI (NHDPlus V2 network).
Start point = matched NID dam (nid_lat/nid_lon from external_join.json). For each start: snap to the NHDPlus comid (comid/position),
navigate downstream main (DM, 250 km path distance) and upstream main (UM, 120 km), and test which OTHER directory lake polygons
(simplified, +300 m) intersect the returned flowlines.  Output <DATA>/context/chain.json  (rebuildable).
~2 calls per lake, 0.4 s sleep; resumable."""
import gzip, json, sys, time
from pathlib import Path
import requests
from shapely.geometry import shape, LineString, Point
from shapely.strtree import STRtree
import shapely

DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
N = "https://api.water.usgs.gov/nldi/linked-data"


def get(url, params=None, tries=4):
    """GET json; on OVER_RATE_LIMIT (api.water.usgs.gov throttles per IP/hour) wait 2 min and retry up to 20 times; never converts a throttle into 'not found'"""
    rl = 0
    a = 0
    while a < tries:
        try:
            r = requests.get(url, params=params, timeout=90)
            if r.status_code == 200:
                j = r.json()
                if isinstance(j, dict) and j.get("error", {}) and "RATE" in str(j.get("error")).upper():
                    raise RuntimeError("rate")
                return j
            if r.status_code == 429 or "OVER_RATE_LIMIT" in r.text[:300]: raise RuntimeError("rate")
            if r.status_code in (400, 404): return None
        except RuntimeError:
            rl += 1
            if rl > 20: raise SystemExit("rate limited too long; rerun later (resumable)")
            time.sleep(120); continue
        except Exception: pass
        a += 1; time.sleep(3 * (a + 1))
    return None


def main():
    ej = json.load(open(DATA / "context/external_join.json"))
    pg = json.load(gzip.open(DATA / "geometry/engine_polygons_599.geojson.gz"))
    ids = [f["properties"]["id"] for f in pg["features"]]
    polys = [shape(f["geometry"]).simplify(0.0003).buffer(0.003) for f in pg["features"]]   # ~300 m
    tree = STRtree(polys)
    outp = DATA / "context/chain.json"
    out = json.load(open(outp)) if outp.exists() else {}
    todo = [k for k, v in ej.items() if v.get("nid_lat") and k not in out]
    dirl = {l["id"]: l for l in json.load(open(DATA / "directory_lakes_2026-10-13.json"))["lakes"]}
    todo.sort(key=lambda k: (k not in ("Pickwick Lake|TN", "Lake Hartwell|SC"), not (dirl[k]["cwmsOffice"] or dirl[k]["operatorName"] == "TVA"), k))   # pilots, then operator-feed lakes, then the rest
    print("todo", len(todo), flush=True)
    for i, k in enumerate(todo):
        v = ej[k]
        r = get(f"{N}/comid/position", {"coords": f"POINT({v['nid_lon']} {v['nid_lat']})"})
        if not r or not r.get("features"): out[k] = {"error": "no comid"}; outp.write_text(json.dumps(out)); continue
        comid = r["features"][0]["properties"]["comid"]; rec = {"comid": comid}
        for nav, dist in (("DM", 250),):          # UM dropped: direction comes from DM only (and it halves the NLDI quota use)
            fl = get(f"{N}/comid/{comid}/navigation/{nav}/flowlines", {"distance": dist, "f": "json"})
            time.sleep(0.4)
            if not fl: rec[nav] = None; continue
            geoms = [shape(f["geometry"]) for f in fl["features"] if f.get("geometry")]
            hit = set()
            for g in geoms:
                for ix in tree.query(g, predicate="intersects"): hit.add(int(ix))
            me = ids.index(k) if k in ids else -1
            hit.discard(me)
            sp = Point(v["nid_lon"], v["nid_lat"])
            rec[nav] = sorted([(ids[ix], round(polys[ix].distance(sp) * 111.0, 1)) for ix in hit], key=lambda t: t[1])
            rec[nav + "_n_flowlines"] = len(geoms)
        out[k] = rec
        outp.write_text(json.dumps(out)); print(i, k, [d[0] for d in (rec.get("DM") or [])][:4], flush=True)
    outp.write_text(json.dumps(out)); print("done", len(out))


if __name__ == "__main__":
    main()
