"""Read-only, cached, polite network access for the coordinate review pack builder.

Only GET/POST-query requests to public read-only endpoints:
  * the public Lake Registry bucket (gs://sector-lake-registry via https://storage.googleapis.com/sector-lake-registry)
  * the USGS National Hydrography Dataset waterbody layer (hydro.nationalmap.gov ArcGIS REST query, read-only)
Every response is cached on disk under --cache-dir (outside Git), so re-running the builder makes no requests. Requests are sequential
with a pause between them; a failure is recorded and never fatal (the lake just has less evidence).
"""
import gzip
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

REGISTRY_BASE = "https://storage.googleapis.com/sector-lake-registry"
INDEX_URL = REGISTRY_BASE + "/registry/lakes.v1.json"
NHD_URL = "https://hydro.nationalmap.gov/arcgis/rest/services/nhd/MapServer/12/query"
NHD_FIELDS = "OBJECTID,GNIS_NAME,GNIS_ID,AREASQKM,FTYPE,PERMANENT_IDENTIFIER"


def user_agent():
    ua = "Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)"
    contact = os.environ.get("SECTOR_CONTACT", "").strip()
    return ua + (f" {contact}" if contact else "")


def _get(url, params=None, timeout=90, retries=3, pause=1.0):
    data = None
    if params:
        data = urllib.parse.urlencode(params).encode()
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers={"User-Agent": user_agent(), "Accept-Encoding": "gzip"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
                    raw = gzip.decompress(raw)
                return json.loads(raw.decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as e:   # noqa: PERF203 - few retries by design
            last = e
            time.sleep(pause * (attempt + 1) * 2)
    raise RuntimeError(f"GET failed for {url}: {last}")


def _cache_path(cache_dir, sub, key):
    d = os.path.join(cache_dir, sub)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, hashlib.sha1(key.encode()).hexdigest()[:20] + ".json")


def cached_json(cache_dir, sub, key, fn, fetch=True):
    """Return (value, from_cache). When fetch is False and nothing is cached, return (None, False)."""
    p = _cache_path(cache_dir, sub, key)
    if os.path.exists(p):
        return json.load(open(p)), True
    if not fetch:
        return None, False
    try:
        v = fn()
    except RuntimeError as e:
        return {"error": str(e)}, False          # failures are never cached: a re-run retries them
    json.dump(v, open(p, "w"))
    time.sleep(0.6)
    return v, False


def fetch_index(cache_dir, fetch=True):
    p = os.path.join(cache_dir, "lakes.v1.json")
    if os.path.exists(p):
        return json.load(open(p))
    if not fetch:
        raise RuntimeError(f"registry index not cached at {p} (run with --fetch)")
    os.makedirs(cache_dir, exist_ok=True)
    d = _get(INDEX_URL)
    json.dump(d, open(p, "w"))
    return d


def fetch_geometry(cache_dir, lake, fetch=True):
    """Analysis polygon of a registry entry as a GeoJSON geometry dict (or None)."""
    g = (lake.get("geometry") or {})
    url = g.get("analysisUrl")
    if not url:
        return None
    v, _ = cached_json(cache_dir, "geometry", url, lambda: _get(url), fetch)
    if not v or v.get("error"):
        return None
    return v.get("geometry") or v


def _nhd_attrs(cache_dir, lat, lon, half_deg, min_area, fetch):
    """Attribute-only query (fast): NHD HR lakes/ponds/reservoirs whose extent meets a box of +-half_deg around the point.
    half_deg = 0 is a point query (the waters the pin sits in)."""
    if half_deg > 0:
        geom = f"{lon - half_deg:.5f},{lat - half_deg:.5f},{lon + half_deg:.5f},{lat + half_deg:.5f}"
        gtype = "esriGeometryEnvelope"
    else:
        geom, gtype = f"{lon},{lat}", "esriGeometryPoint"
    key = f"nhdattr|{geom}|{min_area}"
    params = {"geometry": geom, "geometryType": gtype, "inSR": 4326, "spatialRel": "esriSpatialRelIntersects",
              "where": f"FTYPE IN (390,436) AND AREASQKM>={min_area}", "outFields": NHD_FIELDS, "returnGeometry": "false", "f": "json"}
    if half_deg > 0:
        params.update({"orderByFields": "AREASQKM DESC", "resultRecordCount": 60})
    v, _ = cached_json(cache_dir, "nhd", key, lambda: _get(NHD_URL, params, timeout=60, retries=2), fetch)
    if v is None or v.get("error") or "features" not in v:
        return None
    return [f["attributes"] for f in v["features"]]


def _nhd_geoms(cache_dir, oids, fetch):
    """Simplified polygons of a few objects by OBJECTID (indexed lookup)."""
    if not oids:
        return {}
    ids = ",".join(str(i) for i in sorted(oids))
    key = f"nhdgeom|{ids}"
    params = {"objectIds": ids, "outFields": "OBJECTID", "returnGeometry": "true", "outSR": 4326, "maxAllowableOffset": 0.0003, "f": "geojson"}
    v, _ = cached_json(cache_dir, "nhd", key, lambda: _get(NHD_URL, params, timeout=90, retries=2), fetch)
    if v is None or v.get("error"):
        return None
    return {f["properties"]["OBJECTID"]: f.get("geometry") for f in v.get("features", [])}


def nhd_nearby(cache_dir, lat, lon, lake_name="", half_deg=0.055, min_area=0.02, fetch=True, name_match=None, max_geom=6):
    """NHD HR waterbodies near a pin: [{id, name, gnisId, areaKm2, geometry|None}] or None when the service could not be read.
    Step 1 attributes of everything in a box of about 6 km around the pin (cheap); step 2 polygons only for same-name waters and the largest few, plus the water
    the pin sits in (point query)."""
    attrs = _nhd_attrs(cache_dir, lat, lon, half_deg, min_area, fetch)
    if attrs is None:
        return None
    inside = _nhd_attrs(cache_dir, lat, lon, 0, 0.0, fetch)
    inside_ids = {a["OBJECTID"] for a in (inside or [])}
    want = []
    for a in attrs:
        nm_ok = bool(name_match and lake_name and name_match(lake_name, a.get("GNIS_NAME")) >= 0.5)
        if a["OBJECTID"] in inside_ids or nm_ok:
            want.append(a["OBJECTID"])
    for a in attrs:
        if len(want) >= max_geom:
            break
        if a["OBJECTID"] not in want:
            want.append(a["OBJECTID"])
    geoms = _nhd_geoms(cache_dir, want[:max_geom + 4], fetch)
    out = []
    for a in attrs:
        out.append({"id": str(a.get("PERMANENT_IDENTIFIER") or a["OBJECTID"]), "name": a.get("GNIS_NAME"), "gnisId": a.get("GNIS_ID"), "areaKm2": a.get("AREASQKM"),
                    "geometry": (geoms or {}).get(a["OBJECTID"]), "pinInside": a["OBJECTID"] in inside_ids})
    return out
