#!/usr/bin/env python3
"""Track 7 validation: does a cheap terrain/DEM proxy predict the real stage-area behaviour of a reservoir?
Truth: for USACE lakes whose CWMS project publishes BOTH daily pool elevation (Elev*) and daily storage (Stor), area(z) = dStorage/dz.
We fit Stor ~ quadratic(Elev) over the top 15 ft below the 95th-percentile pool level and report
  A_ref_ac (area at reference pool), dA_dz_ac_per_ft, rel_per_ft = dA/dz / A_ref   (fraction of surface area gained per foot of rise).
Step 1 (this script): catalog -> pairs -> matched to directory lakes by location (CWMS project lat/lon within 12 km of the polygon) -> truth table.
Output <DATA>/context/hypso_truth.json (rebuildable).  Polite: 1 call / 0.7 s."""
import gzip, json, sys, time, collections
from pathlib import Path
import numpy as np, requests
from shapely.geometry import shape, Point
DATA = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain")
B = "https://cwms-data.usace.army.mil/cwms-data"
H = {"Accept": "application/json;version=2"}
OFFICES = ["SWT", "LRL", "SAM", "SAS", "SPK", "NAB", "LRN", "MVK", "SPL"]


def get(path, params):
    for a in range(4):
        try:
            r = requests.get(f"{B}/{path}", params=params, headers=H, timeout=240)
            if r.status_code == 200: return r.json()
            if r.status_code in (400, 404): return None
        except Exception: pass
        time.sleep(3 * (a + 1))
    return None


def pairs_for(office):
    ents = (get("catalog/TIMESERIES", {"office": office, "like": r".*\.(Stor|Elev|Elev-Pool)\.[^.]*\.(1Day|~1Day|1Hour)\..*", "page-size": 20000}) or {}).get("entries", [])
    by = collections.defaultdict(lambda: collections.defaultdict(list))
    for e in ents:
        loc, par = e["name"].split(".")[0:2]
        if par == "Elev-Pool": par = "ElevPool"       # preferred over plain 'Elev' (SAS publishes both; plain Elev is not the pool)
        ex = (e.get("extents") or [{}])[0]
        by[loc][par].append((e["name"], ex.get("earliest-time"), ex.get("latest-time")))
    out = {}
    for loc, d in by.items():
        if "Stor" in d and ("Elev" in d or "ElevPool" in d):
            out[loc] = {"Stor": d["Stor"], "Elev": d["ElevPool"] if "ElevPool" in d else d["Elev"]}
    return out


def pick(cands):
    """prefer long daily series; ranking by span then interval"""
    def span(c):
        try: return (np.datetime64(c[2][:10]) - np.datetime64(c[1][:10])).astype(int)
        except Exception: return -1
    ok = [c for c in cands if c[1] and c[2] and "1Day" in c[0]] or [c for c in cands if c[1] and c[2]]
    return max(ok, key=span) if ok else None


def main():
    pg = json.load(gzip.open(DATA / "geometry/engine_polygons_599.geojson.gz"))
    polys = {f["properties"]["id"]: shape(f["geometry"]).simplify(0.0005) for f in pg["features"]}
    dirl = {l["id"]: l for l in json.load(open(DATA / "directory_lakes_2026-10-13.json"))["lakes"]}
    out = []
    for o in OFFICES:
        prs = pairs_for(o); time.sleep(0.7)
        locs = get("catalog/LOCATIONS", {"office": o, "page-size": 5000}) or {}
        info = {}
        for blk in locs.get("entries", []):
            if isinstance(blk, dict) and "entries" in blk:
                for e in blk["entries"]: info[e["name"]] = e
            elif isinstance(blk, dict): info[blk.get("name")] = blk
        for loc, d in prs.items():
            e = info.get(loc) or info.get(loc.split("-")[0])
            if not e or e.get("latitude") is None: continue
            p = Point(e["longitude"], e["latitude"])
            best = min(polys.items(), key=lambda kv: kv[1].distance(p))
            dist_km = best[1].distance(p) * 111
            if dist_km > 12: continue
            s, z = pick(d["Stor"]), pick(d["Elev"])
            if not s or not z: continue
            out.append(dict(office=o, loc=loc, public_name=e.get("public-name"), lake=best[0], dist_km=round(dist_km, 2), stor=s, elev=z))
        print(o, len(prs), "pairs;", sum(1 for r in out if r["office"] == o), "matched", flush=True)
    (DATA / "context/hypso_pairs.json").write_text(json.dumps(out, indent=1))
    print(len(out), "matched pairs;", len({r["lake"] for r in out}), "lakes")


if __name__ == "__main__":
    main()
