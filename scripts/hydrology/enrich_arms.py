"""Authoritative identities for each arm the graph builder found (Clarity
Fusion Stage 1), from public services, cached:

  NLDI (USGS Network-Linked Data Index, NHDPlus V2)
      comid at a probe ~300 m up the creek above the arm's head, its upstream
      drainage basin, its upstream mainstem length, every USGS site upstream
      on its network; the comid and basin just above the arm's mouth
  NWPS (NOAA National Water Prediction Service) reach metadata for that comid
      (the National Water Model's feature id is the NHDPlus V2 comid)
  WBD (USGS Watershed Boundary Dataset) HUC12 containing the head
  FCC Census area API county at the mouth (to tell same-named creeks apart)

usage: geo/bin/python enrich_arms.py <arms_raw.json> <out_dir>
"""
import os, sys, json, time, hashlib, urllib.request, urllib.parse
import pyproj
from shapely.geometry import shape

NLDI = "https://api.water.usgs.gov/nldi/linked-data"
NWPS = "https://api.water.noaa.gov/nwps/v1/reaches"
WBD = "https://hydro.nationalmap.gov/arcgis/rest/services/wbd/MapServer/6/query"
FCC = "https://geo.fcc.gov/api/census/area"
GEOD = pyproj.Geod(ellps="WGS84")


def slug(s):
    return "".join(ch if ch.isalnum() else "-" for ch in (s or "").lower()).strip("-")


def get(url, cache, tries=4):
    os.makedirs(cache, exist_ok=True)
    path = os.path.join(cache, hashlib.sha1(url.encode()).hexdigest() + ".json")
    if os.path.exists(path):
        return json.load(open(path))
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "sector-hydrology/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r:
                data = json.loads(r.read())
            json.dump(data, open(path, "w"))
            return data
        except urllib.error.HTTPError as e:
            if e.code in (400, 404):
                json.dump(None, open(path, "w"))
                return None
            time.sleep(3 * (i + 1))
        except Exception:
            time.sleep(3 * (i + 1))
    return None


def comid_at(lon, lat, cache):
    d = get(f"{NLDI}/comid/position?coords=" + urllib.parse.quote(f"POINT({lon} {lat})"), cache)
    try:
        return int(d["features"][0]["properties"]["comid"])
    except Exception:
        return None


def basin(comid, cache):
    d = get(f"{NLDI}/comid/{comid}/basin?simplified=false", cache)
    try:
        g = d["features"][0]["geometry"]
        return g, abs(GEOD.geometry_area_perimeter(shape(g))[0]) / 1e6
    except Exception:
        return None, None


def um_length_km(comid, cache):
    d = get(f"{NLDI}/comid/{comid}/navigation/UM/flowlines?distance=1000", cache)
    try:
        return sum(GEOD.geometry_length(shape(f["geometry"])) for f in d["features"]) / 1000
    except Exception:
        return None


def upstream_sites(comid, cache):
    d = get(f"{NLDI}/comid/{comid}/navigation/UT/nwissite?distance=1000", cache)
    out = []
    for f in (d or {}).get("features", []):
        p = f["properties"]
        out.append({"site": p["identifier"].replace("USGS-", ""), "name": p.get("name"),
                    "comid": int(p["comid"]) if p.get("comid") else None,
                    "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]})
    return out


def huc12(lon, lat, cache):
    q = urllib.parse.urlencode({"geometry": f"{lon},{lat}", "geometryType": "esriGeometryPoint", "inSR": 4326,
                                "spatialRel": "esriSpatialRelIntersects", "outFields": "huc12,name",
                                "returnGeometry": "false", "f": "json"})
    d = get(f"{WBD}?{q}", cache)
    try:
        a = d["features"][0]["attributes"]
        return a["huc12"], a["name"]
    except Exception:
        return None, None


def county(lon, lat, cache):
    d = get(f"{FCC}?lat={lat}&lon={lon}&format=json", cache)
    try:
        r = d["results"][0]
        return r["county_name"], r["state_code"]
    except Exception:
        return None, None


def main():
    arms = json.load(open(sys.argv[1]))["arms"]
    out = sys.argv[2]; cache = os.path.join(out, "cache")
    os.makedirs(os.path.join(out, "catchments"), exist_ok=True)
    res = {}
    for sid, a in arms.items():
        r = {"name": a["name"]}
        if a["mouth"]:
            r["mouthCounty"], r["mouthState"] = county(a["mouth"][0], a["mouth"][1], cache)
        if a["heads"]:
            r["huc12"], r["huc12Name"] = huc12(a["heads"][0][0], a["heads"][0][1], cache)
        # The first probe up the channel whose NHDPlus reach is THIS creek: its
        # NWM reach carries the creek's name and its basin is a creek's, not the
        # Tennessee's. None matching: flagged, never guessed.
        c = None; tried = []
        for pr in a.get("probes") or ([a["probe"]] if a.get("probe") else []):
            cc = comid_at(pr[0], pr[1], cache)
            if not cc:
                continue
            reach = get(f"{NWPS}/{cc}", cache) or {}
            _, area = basin(cc, cache)
            tried.append({"comid": cc, "nwmName": reach.get("name"), "basinKm2": round(area, 1) if area else None})
            if reach.get("name") and slug(reach["name"]) == slug(a["name"]) and area and area < 5_000:
                c = cc; break
        r["probeAttempts"] = tried
        if a.get("probes") or a.get("probe"):
            r["headComid"] = c
            if c:
                g, km2 = basin(c, cache)
                r["headBasinKm2"] = round(km2, 2) if km2 else None
                if g:
                    json.dump({"type": "Feature", "geometry": g, "properties": {"arm": sid, "name": a["name"], "comid": c, "kind": "aboveHead"}},
                              open(os.path.join(out, "catchments", f"{sid}.head.geojson"), "w"))
                r["upstreamMainstemKm"] = round(um_length_km(c, cache) or 0, 2)
                r["upstreamSites"] = upstream_sites(c, cache)
                reach = get(f"{NWPS}/{c}", cache)
                r["nwpsReach"] = ({"reachId": reach.get("reachId"), "name": reach.get("name"),
                                   "series": reach.get("streamflow")} if reach else None)
        if a.get("mouthProbe"):
            c = comid_at(a["mouthProbe"][0], a["mouthProbe"][1], cache)
            # the reach just above the mouth must be THIS creek's: a probe in
            # a short arm snaps to the stream it flows into (Slaton Branch got
            # Crow Creek's 623 km2), whose basin is not this arm's drainage
            reach = (get(f"{NWPS}/{c}", cache) or {}) if c else {}
            r["mouthNwmName"] = reach.get("name")      # finalize_graph decides whether to trust it
            r["mouthComid"] = c
            if c:
                g, km2 = basin(c, cache)
                r["mouthBasinKm2"] = round(km2, 2) if km2 else None
                if g and km2 and km2 < 20_000:
                    json.dump({"type": "Feature", "geometry": g, "properties": {"arm": sid, "name": a["name"], "comid": c, "kind": "atMouth"}},
                              open(os.path.join(out, "catchments", f"{sid}.mouth.geojson"), "w"))
        res[sid] = r
        print(sid, a["name"], {k: v for k, v in r.items() if k not in ("upstreamSites",)}, "sites:", len(r.get("upstreamSites", [])), flush=True)
    json.dump(res, open(os.path.join(out, "enrichment.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
