#!/usr/bin/env python3
"""Water Temp Level-4 protected truth, protocol v2 (PT-L4-2026-11-23-v2, gap WATER-VAL-001): read-only runner.

v2 replaces short lakes with a count-only rule (docs/brains/water-temp-protected-truth-v2/PT-L4-2026-11-23-v2.protocol.json).
It reads public sources and writes local files in --out only. It never writes Firebase, never changes a score, binding or
schedule, and never opens a temperature value in step A.

Step A v2 (metadata only; no temperature value is parsed):
    verify          protocol sha256 == committed sidecar
    fetch-registry  Lake Registry v1 index + analysis polygons for the universe (public bucket)
    fetch-usgs      USGS OGC metadata: LK sites, 00010 series, and the M0 calibration sites (ids, types, coordinates)
    fetch-wqp       WQP Station + Activity metadata, and Result rows through the depth-column whitelist
    exclusions      M0_TUNING / RESOLVER_SENSOR / WT_SAT_1 / NO_GEOMETRY per candidate water
    stations        draft station classes (a reviewer may move UNCLASSIFIED rows before the census)
    census          qualifying casts per water (and the frozen lakes' 2026-06-30 window)
    select          retain/replace by counts only; writes selection.json (hash it and post it before step B)
Step B (opens values; refused unless SELECTED and --owner-request is given; a string check, not proof of approval):
    fetch-forcing   Open-Meteo archive forcing at the selected lakes' points
    fetch-results   WQP Result rows for each counted cast only (one site-date query each)
    compare         production M0 vs truth, pre-registered pass mark
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import gzip
import hashlib
import io
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import water_temp_protected_truth as V1  # noqa: E402  (shared helpers: hashing, depth/units, surface value, metrics, M0)

REPO = V1.REPO
PROTOCOL = os.path.join(REPO, "docs", "brains", "water-temp-protected-truth-v2", "PT-L4-2026-11-23-v2.protocol.json")
TEMP_SENSORS = os.path.join(REPO, "docs", "data", "temp_sensors.csv")
LABELS = V1.LABELS
PER_LAKE, TOTAL, SLOTS = 25, 150, 4
HOLDOUT_END = "2026-06-30"
MI10_KM = 16.0934
TOL_M = 100.0
REGISTRY = "https://storage.googleapis.com/sector-lake-registry/"
USGS = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/{c}/items"
ALLOWED = {"www.waterqualitydata.us": "/data/", "archive-api.open-meteo.com": "/v1/archive",
           "storage.googleapis.com": "/sector-lake-registry/", "api.waterdata.usgs.gov": "/ogcapi/v0/collections/"}

# The only Result columns step A may parse or store (protocol stepA.resultDepth). Nothing starting with ResultMeasure.
RESULT_DEPTH_COLUMNS = ("OrganizationIdentifier", "MonitoringLocationIdentifier", "ActivityIdentifier", "ActivityStartDate",
                        "CharacteristicName", "ResultStatusIdentifier",
                        "ActivityDepthHeightMeasure/MeasureValue", "ActivityDepthHeightMeasure/MeasureUnitCode",
                        "ResultDepthHeightMeasure/MeasureValue", "ResultDepthHeightMeasure/MeasureUnitCode")
TENR_RE = re.compile(r"\bTENR[-_ ]?(\d{2,3}(?:\.\d+)?)\b", re.I)


# ----------------------------------------------------------------------------------------------------------- protocol
def load_protocol(path: str = PROTOCOL) -> tuple[dict, str]:
    return V1.load_protocol(path)


def waters(p: dict) -> list[dict]:
    """Candidate waters: one per directory id, except sameWater groups, which become one water keyed by their first id."""
    by_id = {l["lakeId"]: l for l in p["universe"]["lakes"]}
    grouped, out = {}, []
    for g in p["universe"]["sameWater"]:
        for i in g:
            grouped[i] = g
    seen = set()
    for l in p["universe"]["lakes"]:
        g = grouped.get(l["lakeId"], [l["lakeId"]])
        if g[0] in seen:
            continue
        seen.add(g[0])
        head = by_id[g[0]]
        out.append({**head, "lakeId": g[0], "memberIds": list(g)})
    return out


def slug(lake_id: str) -> str:
    return V1.lake_slug(lake_id)


# ----------------------------------------------------------------------------------------------------------- geometry
def haversine_km(a: list, b: list) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _rings(geom: dict) -> list[list[list[list[float]]]]:
    if not geom:
        return []
    if geom.get("type") == "Feature":
        geom = geom.get("geometry") or {}
    if geom.get("type") == "Polygon":
        return [geom["coordinates"]]
    if geom.get("type") == "MultiPolygon":
        return list(geom["coordinates"])
    return []


def _in_ring(lon: float, lat: float, ring: list) -> bool:
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-300) + xi:
            inside = not inside
        j = i
    return inside


def _seg_dist_m(lon: float, lat: float, a: list, b: list) -> float:
    kx = 111320.0 * math.cos(math.radians(lat))
    ky = 110540.0
    ax, ay, bx, by = (a[0] - lon) * kx, (a[1] - lat) * ky, (b[0] - lon) * kx, (b[1] - lat) * ky
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx, ay + t * dy)


def in_polygon(lat: float, lon: float, geom: dict, tol_m: float = TOL_M) -> bool:
    """Inside the (multi)polygon (holes respected), or within tol_m of any ring edge."""
    for poly in _rings(geom):
        if poly and _in_ring(lon, lat, poly[0]) and not any(_in_ring(lon, lat, h) for h in poly[1:]):
            return True
    if tol_m > 0:
        for poly in _rings(geom):
            for ring in poly:
                for i in range(len(ring) - 1):
                    if _seg_dist_m(lon, lat, ring[i], ring[i + 1]) <= tol_m:
                        return True
    return False


def load_registry(reg_dir: str) -> dict:
    """{lakeId: {"bbox": [...], "geometry": GeoJSON or None}} from fetched registry files."""
    idx = json.load(open(os.path.join(reg_dir, "lakes.v1.json"), encoding="utf-8"))
    out = {}
    for e in idx.get("lakes", []):
        gp = os.path.join(reg_dir, f"{e.get('lakeKey') or slug(e['lakeId'])}.analysis.geojson")
        geom = json.load(open(gp, encoding="utf-8")) if os.path.exists(gp) else None
        out[e["lakeId"]] = {"bbox": e.get("bbox"), "geometry": geom}
    return out


# ----------------------------------------------------------------------------------------------------------- fetching
def _get_bytes(url: str, params: dict | None = None) -> bytes:
    u = urllib.parse.urlparse(url)
    prefix = ALLOWED.get(u.hostname or "")
    if prefix is None or not u.path.startswith(prefix) or u.scheme != "https":
        raise SystemExit(f"REFUSED: {u.scheme}://{u.hostname}{u.path} is not an allowlisted source")
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(full, headers={"User-Agent": "sector-research-readonly/1.0", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=300) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip" or body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
    return body


def _save(out: str, name: str, body: bytes, url: str, prov: list) -> str:
    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, name)
    with open(path, "wb") as fh:
        fh.write(body)
    prov.append({"url": url, "path": name, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                 "retrievedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    return path


def cmd_fetch_registry(p: dict, out: str) -> dict:
    prov = []
    idx = _get_bytes(REGISTRY + "registry/lakes.v1.json")
    _save(out, "lakes.v1.json", idx, REGISTRY + "registry/lakes.v1.json", prov)
    entries = {e["lakeId"]: e for e in json.loads(idx).get("lakes", [])}
    for l in p["universe"]["lakes"]:
        e = entries.get(l["lakeId"])
        if not e or not e.get("geometry"):
            continue
        key = e.get("lakeKey") or slug(l["lakeId"])
        url = REGISTRY + f"lakes/{key}/geometry.v1.analysis.geojson.gz"
        _save(out, f"{key}.analysis.geojson", _get_bytes(url), url, prov)
    V1.write_provenance(out, "registry.provenance.json", prov)
    return {"files": len(prov)}


def _wide_bbox(b: list, km: float) -> list:
    dlat = km / 111.0
    dlon = km / (111.0 * math.cos(math.radians((b[1] + b[3]) / 2)))
    return [round(b[0] - dlon, 5), round(b[1] - dlat, 5), round(b[2] + dlon, 5), round(b[3] + dlat, 5)]


def _features(body: bytes) -> list[dict]:
    try:
        return json.loads(body).get("features") or []
    except ValueError:
        return []


def calibration_sites(path: str) -> list[str]:
    rows = json.load(open(path, encoding="utf-8")).get("rows") or []
    return sorted({str(r.get("sensor", "")).split(":", 1)[-1] for r in rows if r.get("inM0CalibrationSet") and r.get("sensor")})


def cmd_fetch_usgs(p: dict, reg: dict, calibration: str, out: str) -> dict:
    """USGS metadata to sites.csv: site id, site type, coordinates, whether a 00010 series exists. No values."""
    prov, sites = [], {}
    for w in waters(p):
        b = (reg.get(w["lakeId"]) or {}).get("bbox")
        if not b:
            lat, lon = w["point"]
            b = [lon, lat, lon, lat]
        bb = ",".join(str(x) for x in _wide_bbox(b, MI10_KM))
        for coll, params in (("monitoring-locations", {"bbox": bb, "site_type_code": "LK", "f": "json", "limit": 10000}),
                             ("time-series-metadata", {"bbox": bb, "parameter_code": "00010", "f": "json", "limit": 10000})):
            url = USGS.format(c=coll)
            body = _get_bytes(url, params)
            _save(out, f"usgs/{slug(w['lakeId'])}.{coll}.json", body, url + "?" + urllib.parse.urlencode(params), prov)
            for f in _features(body):
                pr = f.get("properties") or {}
                sid = str(pr.get("monitoring_location_id") or f.get("id") or "").replace("USGS-", "")
                if not sid:
                    continue
                g = (f.get("geometry") or {}).get("coordinates") or [None, None]
                s = sites.setdefault(sid, {"site": sid, "siteType": "", "lat": None, "lon": None, "has00010": False})
                if coll == "monitoring-locations":
                    s.update(siteType=pr.get("site_type_code") or "LK", lon=g[0], lat=g[1])
                else:
                    s["has00010"] = True
                    if s["lat"] is None and g[0] is not None:
                        s.update(lon=g[0], lat=g[1])
    for sid in calibration_sites(calibration):
        if sid in sites and sites[sid]["lat"] is not None:
            sites[sid]["m0Calibration"] = True
            continue
        url = USGS.format(c="monitoring-locations") + f"/USGS-{sid}"
        body = _get_bytes(url, {"f": "json"})
        _save(out, f"usgs/calibration-{sid}.json", body, url, prov)
        f = json.loads(body)
        g = (f.get("geometry") or {}).get("coordinates") or [None, None]
        s = sites.setdefault(sid, {"site": sid, "siteType": (f.get("properties") or {}).get("site_type_code", ""), "lat": g[1], "lon": g[0], "has00010": True})
        s["m0Calibration"] = True
    with open(os.path.join(out, "sites.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["site", "siteType", "lat", "lon", "has00010", "m0Calibration"])
        w.writeheader()
        for s in sorted(sites.values(), key=lambda s: s["site"]):
            w.writerow({**s, "m0Calibration": bool(s.get("m0Calibration"))})
    V1.write_provenance(out, "usgs.provenance.json", prov)
    return {"sites": len(sites), "calibrationSites": len(calibration_sites(calibration))}


def strip_result_rows(rows, out_fh) -> int:
    """Write only RESULT_DEPTH_COLUMNS from an iterator of CSV rows (lists). Values are never indexed: each row is read only
    at the whitelisted positions. Returns the number of data rows written."""
    it = iter(rows)
    header = next(it, None)
    if header is None:
        return 0
    pos = {name: i for i, name in enumerate(header)}
    keep = [(name, pos[name]) for name in RESULT_DEPTH_COLUMNS if name in pos]
    w = csv.writer(out_fh)
    w.writerow([n for n, _ in keep])
    n = 0
    for row in it:
        w.writerow([row[i] if i < len(row) else "" for _, i in keep])
        n += 1
    return n


def cmd_fetch_wqp(p: dict, reg: dict, out: str) -> dict:
    prov, start = [], dt.date.fromisoformat("2021-01-01").strftime("%m-%d-%Y")
    for w in waters(p):
        b = (reg.get(w["lakeId"]) or {}).get("bbox")
        if not b:
            continue
        params = {"bBox": ",".join(str(x) for x in b), "siteType": V1.SITE_TYPE, "characteristicName": V1.CHARACTERISTIC,
                  "startDateLo": start, "mimeType": "csv", "zip": "no"}
        for kind in ("Station", "Activity"):
            url = V1.WQP.format(kind=kind)
            _save(out, f"wqp/{slug(w['lakeId'])}.{kind.lower()}.csv", _get_bytes(url, params), url + "?" + urllib.parse.urlencode(params), prov)
        url = V1.WQP.format(kind="Result")
        body = _get_bytes(url, params)                                   # parsed only through the whitelist below
        buf = io.StringIO()
        strip_result_rows(csv.reader(io.StringIO(body.decode("utf-8", errors="replace"))), buf)
        del body
        _save(out, f"wqp/{slug(w['lakeId'])}.resultdepth.csv", buf.getvalue().encode("utf-8"), url + "?" + urllib.parse.urlencode(params) + " (depth columns only)", prov)
    V1.write_provenance(out, "wqp.provenance.json", prov)
    return {"files": len(prov)}


# ----------------------------------------------------------------------------------------------------------- exclusions
def bound_lakes(path: str = TEMP_SENSORS) -> set:
    return {r["id"] for r in csv.DictReader(open(path, encoding="utf-8"))}


def exclusions(p: dict, reg: dict, sites: list[dict], calibration_lake_ids: set, bound: set, wtsat1: set) -> dict:
    out = {}
    for w in waters(p):
        why = []
        g = (reg.get(w["lakeId"]) or {}).get("geometry")
        members = set(w["memberIds"])
        if members & calibration_lake_ids:
            why.append("M0_TUNING: directory id in the M0 calibration set")
        if members & bound:
            why.append("RESOLVER_SENSOR: tempSensor binding")
        if members & wtsat1:
            why.append("WT_SAT_1: in the committed WT-SAT-1 list")
        for s in sites:
            lat, lon = V1._f(s.get("lat")), V1._f(s.get("lon"))
            if lat is None or lon is None:
                continue
            near = haversine_km(w["point"], [lat, lon]) <= MI10_KM
            inside = bool(g) and in_polygon(lat, lon, g, 0.0)
            is_lk = str(s.get("siteType", "")).upper().startswith("LK") and str(s.get("has00010")).lower() == "true"
            if str(s.get("m0Calibration")).lower() == "true" and (near or inside):
                why.append(f"M0_TUNING: calibration site {s['site']}")
            if is_lk and near:
                why.append(f"RESOLVER_SENSOR: USGS LK 00010 site {s['site']} within 10 mi")
            if is_lk and inside:
                why.append(f"WT_SAT_1: USGS LK 00010 site {s['site']} inside the polygon")
        if not g:
            why.append("NO_GEOMETRY")
        out[w["lakeId"]] = sorted(set(why))
    return out


def load_sites(path: str) -> list[dict]:
    return V1.read_csv(path)


def unresolved_calibration(sites: list[dict], calibration: str) -> list[str]:
    have = {s["site"] for s in sites if V1._f(s.get("lat")) is not None and str(s.get("m0Calibration")).lower() == "true"}
    return [s for s in calibration_sites(calibration) if s not in have]


# ----------------------------------------------------------------------------------------------------------- stations
def station_trm(name: str, sid: str):
    m = TENR_RE.search(sid or "") or TENR_RE.search(name or "")
    if m:
        return float(m.group(1))
    n = name or ""
    if re.search(r"tenn|\btrm\b", n, re.I):
        return V1.river_mile(n)
    return None


def classify(p: dict, reg: dict, sid: str, name: str, lat, lon) -> tuple[str, str | None, str]:
    if lat is None or lon is None:
        return "UNCLASSIFIED", None, "no coordinates"
    ws = waters(p)
    hits = [w for w in ws if (reg.get(w["lakeId"]) or {}).get("geometry") and in_polygon(lat, lon, reg[w["lakeId"]]["geometry"])]
    n = f" {(name or '').lower()} "
    trm = station_trm(name, sid)
    if not hits:
        return "OUTSIDE", None, "inside no candidate polygon (100 m tolerance)"
    if any(t in n for t in V1.TAILWATER_WORDS):
        return "TAILWATER", hits[0]["lakeId"] if len(hits) == 1 else None, "tailwater keyword in name"
    if len(hits) > 1:
        tr = [w for w in hits if trm is not None and w.get("tennesseeRiverMile")
              and w["tennesseeRiverMile"]["dam"] <= trm <= w["tennesseeRiverMile"]["upstreamDam"]]
        if len(tr) != 1:
            return "AMBIGUOUS", None, "inside two polygons, not resolved by river mile"
        hits = tr
    w = hits[0]
    lid = w["lakeId"]
    rm = w.get("tennesseeRiverMile")
    if rm and trm is not None:
        if trm < rm["dam"] or trm > rm["upstreamDam"]:
            return "OUTSIDE", None, f"river mile {trm} outside this lake"
        if trm > rm["upstreamDam"] - 2.0:
            return "TAILWATER", lid, f"river mile {trm} within 2.0 mi below the upstream dam"
        if any(t in n for t in V1.EMBAYMENT_WORDS):
            return "EMBAYMENT", lid, "embayment keyword in name"
        return "MAIN_BODY", lid, f"Tennessee River mile {trm}"
    if any(t in n for t in V1.EMBAYMENT_WORDS):
        return "EMBAYMENT", lid, "embayment keyword in name"
    other = re.search(r"\b([a-z]+) river\b", n)
    if other and other.group(1) not in ("tennessee", "tenn"):
        if rm:                                    # a Tennessee main-stem lake: another river is a tributary arm
            return "EMBAYMENT", lid, f"names the {other.group(1).title()} River"
        return "UNCLASSIFIED", lid, f"names the {other.group(1).title()} River: main stem or tributary arm? (review)"
    lake_word = re.sub(r"[^a-z ]", " ", lid.split("|")[0].lower()).replace(" lake", "").replace("lake ", "").strip()
    if any(t in n for t in V1.MAIN_WORDS) or (lake_word and lake_word in n and any(t in n for t in ("dam", "lake", "reservoir", "pool"))):
        return "MAIN_BODY", lid, "main-stem, forebay or lake-and-dam keyword in name"
    return "UNCLASSIFIED", lid, "no main-body, embayment or tailwater evidence in metadata"


def cmd_stations(p: dict, reg: dict, wqp: str, out_csv: str) -> dict:
    seen, rows = set(), []
    for w in waters(p):
        path = os.path.join(wqp, f"{slug(w['lakeId'])}.station.csv")
        if not os.path.exists(path):
            continue
        for r in V1.read_csv(path):
            sid = r.get("MonitoringLocationIdentifier")
            if not sid or sid in seen:
                continue
            seen.add(sid)
            lat, lon = V1._f(r.get("LatitudeMeasure")), V1._f(r.get("LongitudeMeasure"))
            cls, lid, why = classify(p, reg, sid, r.get("MonitoringLocationName", ""), lat, lon)
            rows.append({"MonitoringLocationIdentifier": sid, "OrganizationIdentifier": r.get("OrganizationIdentifier", ""),
                         "MonitoringLocationName": r.get("MonitoringLocationName", ""), "LatitudeMeasure": lat, "LongitudeMeasure": lon,
                         "lakeId": lid or "", "class": cls, "reason": why, "reviewNote": ""})
    rows.sort(key=lambda r: (r["lakeId"], r["class"], r["MonitoringLocationIdentifier"]))
    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=V1.STATION_FIELDS)
        wr.writeheader()
        wr.writerows(rows)
    counts = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    return {"stations": len(rows), "byClass": counts}


# ----------------------------------------------------------------------------------------------------------- census
def census(p: dict, activities: list[dict], depth_rows: list[dict], stations: dict, cutoff: str) -> dict:
    """Qualifying casts per water. Depth comes from activity metadata, else from whitelisted Result depth rows."""
    start = "2021-01-01"
    casts, excluded = {}, {"notMainBody": 0, "outsideWindow": 0, "otherCharacteristic": 0, "noDepth": 0}

    def add(r, depth_val, depth_unit):
        sid, d = r.get("MonitoringLocationIdentifier"), r.get("ActivityStartDate", "")
        s = stations.get(sid)
        if not s or s.get("class") != "MAIN_BODY" or not s.get("lakeId"):
            excluded["notMainBody"] += 1
            return
        if not V1._date_in_window(d, start, cutoff):
            excluded["outsideWindow"] += 1
            return
        dep = V1.depth_m(depth_val, depth_unit)
        if dep is None:
            excluded["noDepth"] += 1
            return
        c = casts.setdefault((s["lakeId"], sid, d), {"lakeId": s["lakeId"], "station": sid, "date": d, "readings": 0, "shallowest": dep})
        c["readings"] += 1
        c["shallowest"] = min(c["shallowest"], dep)

    for a in activities:
        add(a, a.get("ActivityDepthHeightMeasure/MeasureValue"), a.get("ActivityDepthHeightMeasure/MeasureUnitCode"))
    for r in depth_rows:
        if (r.get("CharacteristicName") or "").strip() != V1.CHARACTERISTIC:
            excluded["otherCharacteristic"] += 1
            continue
        if (r.get("ResultStatusIdentifier") or "").strip().lower() == "rejected":
            continue
        dv, du = r.get("ActivityDepthHeightMeasure/MeasureValue"), r.get("ActivityDepthHeightMeasure/MeasureUnitCode")
        if V1.depth_m(dv, du) is None:
            dv, du = r.get("ResultDepthHeightMeasure/MeasureValue"), r.get("ResultDepthHeightMeasure/MeasureUnitCode")
        add(r, dv, du)
    qual = V1._dedupe({k: c for k, c in casts.items() if c["shallowest"] <= 1.5}, stations)
    per = {}
    for w in waters(p):
        keys = sorted(k for k in qual if k[0] == w["lakeId"])
        per[w["lakeId"]] = {"qualifyingCasts": len(keys), "castKeys": ["|".join(k) for k in keys]}
        if w["lakeId"] in p["frozenLakes"]:
            per[w["lakeId"]]["qualifyingCastsToFrozenHoldoutEnd"] = sum(1 for k in keys if k[2] <= HOLDOUT_END)
    return {"waters": per, "excluded": excluded}


def cmd_census(p: dict, digest: str, wqp: str, stations_path: str, excl_path: str, cutoff: str, out: str) -> dict:
    stations = V1.load_stations(stations_path)
    acts, depth = [], []
    for w in waters(p):
        for kind, bucket in (("activity", acts), ("resultdepth", depth)):
            path = os.path.join(wqp, f"{slug(w['lakeId'])}.{kind}.csv")
            if os.path.exists(path):
                bucket += V1.read_csv(path)
    for r in depth:
        if any(k.startswith("ResultMeasure") for k in r):
            raise SystemExit("REFUSED: a result-depth file carries a ResultMeasure column; step A never stores values")
    res = census(p, acts, depth, stations, cutoff)
    rec = {"labels": LABELS, "protocolId": p["protocolId"], "protocolSha256": digest, "step": "A_census_v2", "valuesOpened": False,
           "cutoff": cutoff, "stationFileSha256": V1.sha256_file(stations_path), "exclusionsSha256": V1.sha256_file(excl_path),
           "authoritativeScoresUnchanged": True, **res}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    return rec


# ----------------------------------------------------------------------------------------------------------- selection
def select(p: dict, census_rec: dict, excl: dict) -> dict:
    """Count-only retain/replace rule (protocol selection). Uses no value of any kind."""
    counts = {lid: v["qualifyingCasts"] for lid, v in census_rec["waters"].items()}
    ok = lambda lid: not excl.get(lid) and counts.get(lid, 0) >= PER_LAKE
    retained = [lid for lid in p["frozenLakes"] if ok(lid)]
    pool = sorted((lid for lid in counts if lid not in p["frozenLakes"] and ok(lid)),
                  key=lambda lid: (-counts[lid], hashlib.sha256(lid.encode()).hexdigest()))
    chosen = retained + pool[: max(0, SLOTS - len(retained))]
    total = sum(counts[l] for l in chosen)
    outcome = "SELECTED" if len(chosen) == SLOTS and total >= TOTAL else "INSUFFICIENT_TRUTH"
    return {"outcome": outcome, "retained": retained, "replacements": [l for l in chosen if l not in retained],
            "lakes": [{"lakeId": l, "qualifyingCasts": counts[l], "castKeys": census_rec["waters"][l]["castKeys"]} for l in chosen],
            "total": total, "needed": {"perLake": PER_LAKE, "total": TOTAL, "lakes": SLOTS},
            "shortfall": None if outcome == "SELECTED" else {"lakesWith25": len(chosen), "total": total},
            "frozenLakeStatus": {l: ("EXCLUDED: " + "; ".join(excl[l])) if excl.get(l) else f"{counts.get(l, 0)} casts" for l in p["frozenLakes"]},
            "rankedPool": [{"lakeId": l, "qualifyingCasts": counts[l]} for l in pool]}


def cmd_select(p: dict, digest: str, census_path: str, excl_path: str, out: str) -> dict:
    c = json.load(open(census_path, encoding="utf-8"))
    if c.get("protocolSha256") != digest:
        raise SystemExit("REFUSED: census made under a different protocol")
    if V1.sha256_file(excl_path) != c.get("exclusionsSha256"):
        raise SystemExit("REFUSED: exclusions file changed after the census")
    excl = json.load(open(excl_path, encoding="utf-8"))["exclusions"]
    rec = {"labels": LABELS, "protocolId": p["protocolId"], "protocolSha256": digest, "step": "A_selection_v2", "valuesOpened": False,
           "censusSha256": V1.sha256_file(census_path), "stationFileSha256": c["stationFileSha256"], "exclusionsSha256": c["exclusionsSha256"],
           "authoritativeScoresUnchanged": True, **select(p, c, excl)}
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    return rec


# ----------------------------------------------------------------------------------------------------------- step B
def require_step_b(sel: dict, digest: str, owner_request: str | None) -> None:
    if not owner_request or not owner_request.startswith("Owner request (Michael, "):
        raise SystemExit("REFUSED: step B opens protected values and needs --owner-request 'Owner request (Michael, ...)' "
                         "(a string check; the request posted on Sector_Ops #51 is the control)")
    if sel.get("protocolSha256") != digest:
        raise SystemExit("REFUSED: selection made under a different protocol")
    if sel.get("outcome") != "SELECTED":
        raise SystemExit("REFUSED: selection is not SELECTED; protected values stay closed")


def counted_casts(sel: dict) -> list[tuple[str, str, str]]:
    return sorted(V1._split_key(k) for l in sel["lakes"] for k in l["castKeys"])


def result_queries(sel: dict) -> list[dict]:
    """One WQP Result query per counted cast: that site, that date, nothing else (protocol stepB.fetch)."""
    out = []
    for lid, sid, d in counted_casts(sel):
        day = dt.date.fromisoformat(d).strftime("%m-%d-%Y")
        out.append({"lakeId": lid, "siteid": sid, "date": d,
                    "params": {"siteid": sid, "characteristicName": V1.CHARACTERISTIC, "startDateLo": day, "startDateHi": day,
                               "mimeType": "csv", "zip": "no"}})
    return out


def cmd_fetch_results(p: dict, digest: str, sel_path: str, owner_request: str, out: str) -> dict:
    sel = json.load(open(sel_path, encoding="utf-8"))
    require_step_b(sel, digest, owner_request)
    prov, url = [], V1.WQP.format(kind="Result")
    for q in result_queries(sel):
        _save(out, f"results/{slug(q['lakeId'])}__{slug(q['siteid'])}__{q['date']}.csv", _get_bytes(url, q["params"]),
              url + "?" + urllib.parse.urlencode(q["params"]), prov)
    V1.write_provenance(out, "results.provenance.json", prov)
    return {"queries": len(prov)}


def cmd_fetch_forcing(p: dict, digest: str, sel_path: str, start: str, end: str, owner_request: str, out: str) -> dict:
    sel = json.load(open(sel_path, encoding="utf-8"))
    require_step_b(sel, digest, owner_request)
    pts = {w["lakeId"]: w["point"] for w in waters(p)}
    prov, fstart = [], (dt.date.fromisoformat(start) - dt.timedelta(days=46)).isoformat()
    for l in sel["lakes"]:
        lat, lon = pts[l["lakeId"]]
        params = {"latitude": lat, "longitude": lon, "start_date": fstart, "end_date": end, "timezone": "auto",
                  "daily": "temperature_2m_mean,shortwave_radiation_sum,wind_speed_10m_mean,relative_humidity_2m_mean"}
        _save(out, f"{slug(l['lakeId'])}.forcing.json", _get_bytes(V1.OPEN_METEO, params), V1.OPEN_METEO, prov)
    V1.write_provenance(out, "forcing.provenance.json", prov)
    return {"files": len(prov)}


def verdict(per_lake: dict) -> dict:
    if not all(v["n"] >= PER_LAKE for v in per_lake.values()) or sum(v["n"] for v in per_lake.values()) < TOTAL:
        return {"outcome": "INSUFFICIENT_PAIRED", "pooledEqualLakeRmseC": None}
    pooled = math.sqrt(sum(v["mseC2"] for v in per_lake.values()) / len(per_lake))
    lake_ok = {k: v["rmseC"] <= 2.5 for k, v in per_lake.items()}
    return {"outcome": "PASS" if pooled <= 2.5 and all(lake_ok.values()) else "FAIL", "pooledEqualLakeRmseC": round(pooled, 4), "perLakePass": lake_ok}


def compare(p: dict, sel: dict, results: list[dict], forcing: dict) -> dict:
    m0_daily, m0_for_date, m0_sha = V1.m0_functions()
    counted = set(counted_casts(sel))
    truth = V1.surface_values(results, counted)
    per = {}
    for l in sel["lakes"]:
        lid = l["lakeId"]
        forc = m0_daily(forcing[lid]["daily"]) if lid in forcing else {}
        pairs, unpaired = [], 0
        for k, t in sorted(truth.items()):
            if k[0] != lid:
                continue
            m = m0_for_date(forc, k[2])
            if m is None:
                unpaired += 1
                continue
            pairs.append((k[2], m, t))
        per[lid] = {**V1.lake_metrics(pairs), "unpaired": unpaired,
                    "noSurfaceValue": sum(1 for k in counted if k[0] == lid and k not in truth)}
    v = verdict(per)
    for x in per.values():
        x.pop("mseC2", None)
    return {"labels": LABELS, "protocolId": p["protocolId"], "step": "B_compare_v2", "valuesOpened": True, "model": "surface-energy-balance-v2 (M0, k = 0.09)",
            "m0ImplementationSha256": m0_sha, "perLake": per, **v, "authoritativeScoresUnchanged": True,
            "scoreImpact": "none: the frozen water-temp block changes only by an owner decision in a separate change"}


def cmd_compare(p: dict, digest: str, sel_path: str, results_dir: str, forcing_dir: str, owner_request: str, out: str) -> dict:
    sel = json.load(open(sel_path, encoding="utf-8"))
    require_step_b(sel, digest, owner_request)
    results, forcing = [], {}
    rdir = os.path.join(results_dir, "results")
    for name in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
        results += V1.read_csv(os.path.join(rdir, name))
    for l in sel["lakes"]:
        fp = os.path.join(forcing_dir, f"{slug(l['lakeId'])}.forcing.json")
        if os.path.exists(fp):
            forcing[l["lakeId"]] = json.load(open(fp, encoding="utf-8"))
    rec = compare(p, sel, results, forcing)
    rec.update({"protocolSha256": digest, "selectionSha256": V1.sha256_file(sel_path), "ownerRequest": owner_request})
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    return rec


# ----------------------------------------------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--protocol", default=PROTOCOL)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify")
    s = sub.add_parser("fetch-registry"); s.add_argument("--out", required=True)
    s = sub.add_parser("fetch-usgs"); s.add_argument("--registry", required=True); s.add_argument("--calibration", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("fetch-wqp"); s.add_argument("--registry", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("exclusions"); s.add_argument("--registry", required=True); s.add_argument("--sites", required=True)
    s.add_argument("--calibration", required=True); s.add_argument("--calibration-lakes", default=None, help="JSON list of directory ids in the M0 set, if the snapshot names lakes")
    s.add_argument("--wt-sat-1", default=None, help="committed WT-SAT-1 lake list (JSON list), once frozen"); s.add_argument("--out", required=True)
    s = sub.add_parser("stations"); s.add_argument("--registry", required=True); s.add_argument("--wqp", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("census"); s.add_argument("--wqp", required=True); s.add_argument("--stations", required=True); s.add_argument("--exclusions", required=True)
    s.add_argument("--cutoff", default=(dt.date.today() - dt.timedelta(days=1)).isoformat()); s.add_argument("--out", required=True)
    s = sub.add_parser("select"); s.add_argument("--census", required=True); s.add_argument("--exclusions", required=True); s.add_argument("--out", required=True)
    for name in ("fetch-forcing", "fetch-results", "compare"):
        s = sub.add_parser(name); s.add_argument("--selection", required=True); s.add_argument("--owner-request"); s.add_argument("--out", required=True)
        if name == "fetch-forcing":
            s.add_argument("--start", default="2021-01-01"); s.add_argument("--end", required=True)
        if name == "compare":
            s.add_argument("--results", required=True); s.add_argument("--forcing", required=True)
    a = ap.parse_args(argv)
    p, digest = load_protocol(a.protocol)
    if a.cmd == "verify":
        res = {"protocolId": p["protocolId"], "sha256": digest, "status": "OK"}
    elif a.cmd == "fetch-registry":
        res = cmd_fetch_registry(p, a.out)
    elif a.cmd == "fetch-usgs":
        res = cmd_fetch_usgs(p, load_registry(a.registry), a.calibration, a.out)
    elif a.cmd == "fetch-wqp":
        res = cmd_fetch_wqp(p, load_registry(a.registry), a.out)
    elif a.cmd == "exclusions":
        sites = load_sites(a.sites)
        missing = unresolved_calibration(sites, a.calibration)
        if missing:
            raise SystemExit(f"REFUSED: M0 calibration sites without coordinates: {missing}")
        cal_lakes = set(json.load(open(a.calibration_lakes))) if a.calibration_lakes else set()
        sat = set(json.load(open(a.wt_sat_1))) if a.wt_sat_1 else set()
        ex = exclusions(p, load_registry(a.registry), sites, cal_lakes, bound_lakes(), sat)
        rec = {"labels": LABELS, "protocolId": p["protocolId"], "protocolSha256": digest, "wtSat1List": "committed" if sat else "unfrozen: LK-in-polygon rule",
               "sitesSha256": V1.sha256_file(a.sites), "calibrationSha256": V1.sha256_file(a.calibration), "exclusions": ex}
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1)
        res = {"excluded": sum(1 for v in ex.values() if v), "eligible": sum(1 for v in ex.values() if not v)}
    elif a.cmd == "stations":
        res = cmd_stations(p, load_registry(a.registry), a.wqp, a.out)
    elif a.cmd == "census":
        r = cmd_census(p, digest, a.wqp, a.stations, a.exclusions, a.cutoff, a.out)
        res = {"waters": {k: {kk: vv for kk, vv in v.items() if kk != "castKeys"} for k, v in r["waters"].items()}, "excluded": r["excluded"]}
    elif a.cmd == "select":
        r = cmd_select(p, digest, a.census, a.exclusions, a.out)
        res = {"outcome": r["outcome"], "lakes": [(l["lakeId"], l["qualifyingCasts"]) for l in r["lakes"]], "total": r["total"],
               "selectionSha256": V1.sha256_file(a.out)}
    elif a.cmd == "fetch-forcing":
        res = cmd_fetch_forcing(p, digest, a.selection, a.start, a.end, a.owner_request, a.out)
    elif a.cmd == "fetch-results":
        res = cmd_fetch_results(p, digest, a.selection, a.owner_request, a.out)
    else:
        r = cmd_compare(p, digest, a.selection, a.results, a.forcing, a.owner_request, a.out)
        res = {k: r[k] for k in ("outcome", "pooledEqualLakeRmseC", "perLake")}
    print(json.dumps(res, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
