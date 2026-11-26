#!/usr/bin/env python3
"""Water Temp Level-4 protected truth, protocol v6 (PT-L4-2026-11-23-v6, gap WATER-VAL-001): read-only runner.

Protocol: docs/brains/water-temp-protected-truth-v6/PT-L4-2026-11-23-v6.protocol.json. The runner refuses any other protocol,
including the superseded v2 to v5. It reads public sources and writes local files in --out only. Every step is recorded in the
shared run ledger (tools/research/protocol_run_ledger.py, Ledger.for_brain('water-temp', ...)) in the folder Cortex research-path
returns, anchored by a public 'Run anchor:' comment on Sector_Ops #51 that must exist before ANY step. It never writes Firebase,
never changes a score, binding or schedule, and never indexes a temperature value in step A.

Result steps (RESULT_STEPS): select and compare. Each posts a 'Run start:' record on #51 and confirms it before computing, and a
'Run result:' record after completing. Keys are fixed by the protocol (STEP_KEYS). Comments are posted as research records by the
session that runs the step (with --post through gh, or by hand while the runner waits); "not listed yet" means wait and retry,
never repost; nobody edits them.

    verify          protocol id and sha256 == committed sidecar
    anchor          open the ledger and write (or, with --post, post) its Run anchor text; then check-anchor
    check-anchor    require_external_anchor(): the earliest Run anchor for this protocol id is this ledger's
Step A v6 (counts only; census cutoff fixed by the protocol):
    fetch-registry  Lake Registry v1 index + analysis polygons for the universe (public bucket)
    fetch-usgs      USGS OGC metadata, stored as whitelisted properties (ids, site type, parameter, geometry)
    fetch-wqp       WQP Station / Activity metadata and Result-depth rows (with the unit code), as whitelisted columns only
    exclusions      ledger step (key all); M0_TUNING / RESOLVER_SENSOR / WT_SAT_1 / NO_GEOMETRY per candidate water
    stations        draft station classes; a reviewer may reclassify the draft's UNCLASSIFIED rows only, with a reviewNote
    census          ledger step (key all); bound to the posted draft and reviewed hashes and the recorded exclusions
    select          RESULT step (key all); retain/replace by counts only
Step B (opens values; every command needs the ledger's counted selection, the reviewed station file and --owner-request, which
is a string check and not proof of approval: the request posted on Sector_Ops #51 is the control):
    fetch-forcing   ledger step (key selection); the window the selection implies; files bound in the ledger
    fetch-results   ledger step (key selection); one WQP Result query per counted cast; files bound in the ledger
    compare         RESULT step (key selection); files checked against the ledger and the provenance; unknowns count against
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
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import water_temp_protected_truth as V1  # noqa: E402  (shared helpers: hashing, classes, units, metrics, the M0 implementation)
import protocol_run_ledger as RL  # noqa: E402  (the shared Engine run ledger, PR #251)

REPO = V1.REPO
PROTOCOL_ID = "PT-L4-2026-11-23-v6"
PROTOCOL = os.path.join(REPO, "docs", "brains", "water-temp-protected-truth-v6", f"{PROTOCOL_ID}.protocol.json")
TEMP_SENSORS = os.path.join(REPO, "docs", "data", "temp_sensors.csv")
LABELS = V1.LABELS
PER_LAKE, TOTAL, SLOTS = 25, 150, 4
HOLDOUT_END = "2026-06-30"
BRAIN = "water-temp"
RESULT_STEPS = frozenset({"select", "compare"})            # protocol runLedger.resultSteps; recorded in the genesis and the anchor
STEP_KEYS = {"exclusions": "all", "census": "all", "select": "all",
             "fetch-forcing": "selection", "fetch-results": "selection", "compare": "selection"}   # protocol runLedger.keys
CUTOFF = "2026-11-22"
WINDOW_START = "2021-01-01"
SPIN_UP_DAYS = 46
MI10_KM = 16.0934
TOL_M = 100.0
RMSE_MARK = 2.5
REGISTRY = "https://storage.googleapis.com/sector-lake-registry/"
USGS = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/{c}/items"
ALLOWED = {"www.waterqualitydata.us": "/data/", "archive-api.open-meteo.com": "/v1/archive",
           "storage.googleapis.com": "/sector-lake-registry/", "api.waterdata.usgs.gov": "/ogcapi/v0/collections/"}
FORCING_DAILY = "temperature_2m_mean,shortwave_radiation_sum,wind_speed_10m_mean,relative_humidity_2m_mean"

# Stored columns (protocol stepA). Never ResultMeasureValue; the only ResultMeasure column is the unit code. No free text.
STATION_COLUMNS = ("OrganizationIdentifier", "MonitoringLocationIdentifier", "MonitoringLocationName", "MonitoringLocationTypeName",
                   "LatitudeMeasure", "LongitudeMeasure", "HorizontalCoordinateReferenceSystemDatumName")
ACTIVITY_COLUMNS = ("OrganizationIdentifier", "MonitoringLocationIdentifier", "ActivityIdentifier", "ActivityTypeCode", "ActivityMediaName",
                    "ActivityStartDate", "ActivityStartTime/Time", "ActivityStartTime/TimeZoneCode",
                    "ActivityDepthHeightMeasure/MeasureValue", "ActivityDepthHeightMeasure/MeasureUnitCode")
RESULT_DEPTH_COLUMNS = ("OrganizationIdentifier", "MonitoringLocationIdentifier", "ActivityIdentifier", "ActivityStartDate",
                        "CharacteristicName", "ResultStatusIdentifier", "ResultMeasure/MeasureUnitCode",
                        "ActivityDepthHeightMeasure/MeasureValue", "ActivityDepthHeightMeasure/MeasureUnitCode",
                        "ResultDepthHeightMeasure/MeasureValue", "ResultDepthHeightMeasure/MeasureUnitCode")
USGS_PROPERTIES = ("monitoring_location_id", "site_type_code", "parameter_code")
TENR_RE = re.compile(r"\bTENR[-_ ]?(\d{2,3}(?:\.\d+)?)\b", re.I)


# ----------------------------------------------------------------------------------------------------------- protocol
def load_protocol(path: str = PROTOCOL) -> tuple[dict, str]:
    p, digest = V1.load_protocol(path)
    if p.get("protocolId") != PROTOCOL_ID:
        raise SystemExit(f"REFUSED: this runner executes {PROTOCOL_ID} only, not {p.get('protocolId')}")
    if p.get("censusCutoff") != CUTOFF:
        raise SystemExit("REFUSED: the protocol's census cutoff differs from the runner's")
    return p, digest


def waters(p: dict) -> list[dict]:
    """One candidate per water: sameWater groups become one water keyed by their first id."""
    by_id = {l["lakeId"]: l for l in p["universe"]["lakes"]}
    grouped = {i: g for g in p["universe"]["sameWater"] for i in g}
    out, seen = [], set()
    for l in p["universe"]["lakes"]:
        g = grouped.get(l["lakeId"], [l["lakeId"]])
        if g[0] in seen:
            continue
        seen.add(g[0])
        out.append({**by_id[g[0]], "lakeId": g[0], "memberIds": list(g)})
    return out


def slug(lake_id: str) -> str:
    return V1.lake_slug(lake_id)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ----------------------------------------------------------------------------------------------------------- geometry
def haversine_km(a: list, b: list) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lo2 - lo1) / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def _rings(geom: dict) -> list:
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
        xi, yi, xj, yj = ring[i][0], ring[i][1], ring[j][0], ring[j][1]
        if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-300) + xi:
            inside = not inside
        j = i
    return inside


def _seg_dist_m(lon: float, lat: float, a: list, b: list) -> float:
    kx, ky = 111320.0 * math.cos(math.radians(lat)), 110540.0
    ax, ay, bx, by = (a[0] - lon) * kx, (a[1] - lat) * ky, (b[0] - lon) * kx, (b[1] - lat) * ky
    dx, dy = bx - ax, by - ay
    t = 0.0 if dx == dy == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / (dx * dx + dy * dy)))
    return math.hypot(ax + t * dx, ay + t * dy)


def in_polygon(lat: float, lon: float, geom: dict, tol_m: float = TOL_M) -> bool:
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
    idx = json.load(open(os.path.join(reg_dir, "lakes.v1.json"), encoding="utf-8"))
    out = {}
    for e in idx.get("lakes", []):
        gp = os.path.join(reg_dir, f"{e.get('lakeKey') or slug(e['lakeId'])}.analysis.geojson")
        out[e["lakeId"]] = {"bbox": e.get("bbox"), "geometry": json.load(open(gp, encoding="utf-8")) if os.path.exists(gp) else None}
    return out


# ----------------------------------------------------------------------------------------------------------- fetching
def check_url(url: str) -> None:
    u = urllib.parse.urlparse(url)
    prefix = ALLOWED.get(u.hostname or "")
    if u.scheme != "https" or prefix is None or not u.path.startswith(prefix):
        raise SystemExit(f"REFUSED: {u.scheme}://{u.hostname}{u.path} is not an allowlisted source")


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    """Every redirect hop is re-checked against the allowlist."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = urllib.request.build_opener(_CheckedRedirect)


RETRY_STATUS = (429, 502, 503, 504)
MAX_ATTEMPTS = 6
BACKOFF_BASE_S = 30
BACKOFF_CAP_S = 300
_BACKOFF_SLEEP = time.sleep


def _retry_wait(err: urllib.error.HTTPError, attempt: int) -> float:
    """Seconds to wait before the next try: the server's Retry-After when it sends whole seconds, else 30 s doubling to a 5 min cap."""
    ra = (err.headers.get("Retry-After") if err.headers else None) or ""
    if ra.strip().isdigit():
        return float(min(int(ra), 900))
    return float(min(BACKOFF_CAP_S, BACKOFF_BASE_S * 2 ** attempt))


def _get_bytes(url: str, params: dict | None = None) -> bytes:
    """One allowlisted GET. A rate limit or a transient server error (429/502/503/504) waits and retries the SAME request, so a
    protocol's requests and parameters never change; any other failure, or the last attempt, raises as before."""
    check_url(url)
    full = url + ("?" + urllib.parse.urlencode(params) if params else "")
    for attempt in range(MAX_ATTEMPTS):
        req = urllib.request.Request(full, headers={"User-Agent": "sector-research-readonly/1.0", "Accept-Encoding": "gzip"})
        try:
            with _OPENER.open(req, timeout=300) as r:
                check_url(r.geturl())
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip" or body[:2] == b"\x1f\x8b":
                    body = gzip.decompress(body)
            return body
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_STATUS or attempt == MAX_ATTEMPTS - 1:
                raise
            _BACKOFF_SLEEP(_retry_wait(e, attempt))
    raise AssertionError("unreachable")


def _save(out: str, name: str, body: bytes, url: str, params: dict | None, prov: list, note: str = "") -> str:
    path = os.path.join(out, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(body)
    prov.append({"url": url, "params": params or {}, "path": name, "sha256": sha256_bytes(body), "bytes": len(body),
                 "note": note, "retrievedAt": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
    return path


def strip_rows(rows, out_fh, columns) -> int:
    """Write only `columns` from an iterator of CSV rows (lists). Each data row is indexed only at the whitelisted positions,
    so no other field is read, converted, stored or printed by this code."""
    it = iter(rows)
    header = next(it, None)
    if header is None:
        return 0
    pos = {name: i for i, name in enumerate(header)}
    keep = [(name, pos[name]) for name in columns if name in pos]
    w = csv.writer(out_fh)
    w.writerow([n for n, _ in keep])
    n = 0
    for row in it:
        w.writerow([row[i] if i < len(row) else "" for _, i in keep])
        n += 1
    return n


def strip_result_rows(rows, out_fh) -> int:
    return strip_rows(rows, out_fh, RESULT_DEPTH_COLUMNS)


def _stripped_csv(body: bytes, columns) -> bytes:
    buf = io.StringIO()
    strip_rows(csv.reader(io.StringIO(body.decode("utf-8", errors="replace"))), buf, columns)
    return buf.getvalue().encode("utf-8")


def strip_usgs(body: bytes) -> bytes:
    """Keep only whitelisted properties and the geometry of each feature."""
    try:
        feats = json.loads(body).get("features") or []
    except ValueError:
        feats = []
    keep = [{"id": f.get("id"), "geometry": f.get("geometry"),
             "properties": {k: (f.get("properties") or {}).get(k) for k in USGS_PROPERTIES}} for f in feats]
    return json.dumps({"type": "FeatureCollection", "features": keep}).encode("utf-8")


def cmd_fetch_registry(p: dict, out: str) -> dict:
    prov = []
    url = REGISTRY + "registry/lakes.v1.json"
    idx = _get_bytes(url)
    _save(out, "lakes.v1.json", idx, url, None, prov)
    entries = {e["lakeId"]: e for e in json.loads(idx).get("lakes", [])}
    for l in p["universe"]["lakes"]:
        e = entries.get(l["lakeId"])
        if not e or not e.get("geometry"):
            continue
        key = e.get("lakeKey") or slug(l["lakeId"])
        gurl = REGISTRY + f"lakes/{key}/geometry.v1.analysis.geojson.gz"
        _save(out, f"{key}.analysis.geojson", _get_bytes(gurl), gurl, None, prov)
    V1.write_provenance(out, "registry.provenance.json", prov)
    return {"files": len(prov)}


def _wide_bbox(b: list, km: float) -> list:
    dlat = km / 111.0
    dlon = km / (111.0 * math.cos(math.radians((b[1] + b[3]) / 2)))
    return [round(b[0] - dlon, 5), round(b[1] - dlat, 5), round(b[2] + dlon, 5), round(b[3] + dlat, 5)]


def calibration_sites(path: str) -> list[str]:
    rows = json.load(open(path, encoding="utf-8")).get("rows") or []
    return sorted({str(r.get("sensor", "")).split(":", 1)[-1] for r in rows if r.get("inM0CalibrationSet") and r.get("sensor")})


def cmd_fetch_usgs(p: dict, reg: dict, calibration: str, out: str) -> dict:
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
            body = strip_usgs(_get_bytes(url, params))
            _save(out, f"usgs/{slug(w['lakeId'])}.{coll}.json", body, url, params, prov, "whitelisted properties only")
            for f in json.loads(body)["features"]:
                pr = f["properties"]
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
        raw = _get_bytes(url, {"f": "json"})
        f = json.loads(raw)
        g = (f.get("geometry") or {}).get("coordinates") or [None, None]
        body = json.dumps({"id": f.get("id"), "geometry": f.get("geometry"),
                           "properties": {k: (f.get("properties") or {}).get(k) for k in USGS_PROPERTIES}}).encode()
        _save(out, f"usgs/calibration-{sid}.json", body, url, {"f": "json"}, prov, "whitelisted properties only")
        s = sites.setdefault(sid, {"site": sid, "siteType": (f.get("properties") or {}).get("site_type_code", ""), "lat": g[1], "lon": g[0], "has00010": True})
        s["m0Calibration"] = True
    with open(os.path.join(out, "sites.csv"), "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=["site", "siteType", "lat", "lon", "has00010", "m0Calibration"])
        wr.writeheader()
        for s in sorted(sites.values(), key=lambda s: s["site"]):
            wr.writerow({**s, "m0Calibration": bool(s.get("m0Calibration"))})
    V1.write_provenance(out, "usgs.provenance.json", prov)
    return {"sites": len(sites), "calibrationSites": len(calibration_sites(calibration))}


def wqp_params(b: list) -> dict:
    return {"bBox": ",".join(str(x) for x in b), "siteType": V1.SITE_TYPE, "characteristicName": V1.CHARACTERISTIC,
            "startDateLo": dt.date.fromisoformat(WINDOW_START).strftime("%m-%d-%Y"), "mimeType": "csv", "zip": "no"}


WQP_PARTIAL = "wqp.provenance.partial.json"


def cmd_fetch_wqp(p: dict, reg: dict, out: str) -> dict:
    """Station, Activity and Result-depth files per lake. Each file is recorded in a partial provenance file as it lands, so a run
    stopped by a rate limit resumes after the last good file: a file is reused only when it is on disk with the recorded sha256, url
    and parameters (nothing is re-fetched or re-interpreted), and the final provenance is the same as an uninterrupted run's."""
    os.makedirs(out, exist_ok=True)
    partial_path = os.path.join(out, WQP_PARTIAL)
    done = {}
    if os.path.exists(partial_path):
        done = {i["path"]: i for i in json.load(open(partial_path, encoding="utf-8")).get("items", [])}
    prov = []
    for w in waters(p):
        b = (reg.get(w["lakeId"]) or {}).get("bbox")
        if not b:
            continue
        params = wqp_params(b)
        for kind, cols, name in (("Station", STATION_COLUMNS, "station"), ("Activity", ACTIVITY_COLUMNS, "activity"),
                                 ("Result", RESULT_DEPTH_COLUMNS, "resultdepth")):
            url = V1.WQP.format(kind=kind)
            rel = f"wqp/{slug(w['lakeId'])}.{name}.csv"
            have = done.get(rel)
            full = os.path.join(out, rel)
            if (have and have.get("url") == url and have.get("params") == params and os.path.exists(full)
                    and V1.sha256_file(full) == have.get("sha256")):
                prov.append(have)
                continue
            body = _stripped_csv(_get_bytes(url, params), cols)          # only whitelisted columns are ever written
            _save(out, rel, body, url, params, prov, "whitelisted columns only")
            V1.write_provenance(out, WQP_PARTIAL, prov)
    V1.write_provenance(out, "wqp.provenance.json", prov)
    if os.path.exists(partial_path):
        os.remove(partial_path)
    return {"files": len(prov)}


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


def unresolved_calibration(sites: list[dict], calibration: str) -> list[str]:
    have = {s["site"] for s in sites if V1._f(s.get("lat")) is not None and str(s.get("m0Calibration")).lower() == "true"}
    return [s for s in calibration_sites(calibration) if s not in have]


# ----------------------------------------------------------------------------------------------------------- stations
def station_trm(name: str, sid: str):
    m = TENR_RE.search(sid or "") or TENR_RE.search(name or "")
    if m:
        return float(m.group(1))
    if re.search(r"tenn|\btrm\b", name or "", re.I):
        return V1.river_mile(name or "")
    return None


def classify(p: dict, reg: dict, sid: str, name: str, lat, lon) -> tuple[str, str | None, str]:
    if lat is None or lon is None:
        return "UNCLASSIFIED", None, "no coordinates"
    hits = [w for w in waters(p) if (reg.get(w["lakeId"]) or {}).get("geometry") and in_polygon(lat, lon, reg[w["lakeId"]]["geometry"])]
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
    lid, rm = w["lakeId"], w.get("tennesseeRiverMile")
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
        if rm:
            return "EMBAYMENT", lid, f"names the {other.group(1).title()} River"
        return "UNCLASSIFIED", lid, f"names the {other.group(1).title()} River: the dam's own river (MAIN_BODY) or a tributary (EMBAYMENT)? review"
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
                         "MonitoringLocationName": r.get("MonitoringLocationName", ""), "LatitudeMeasure": "" if lat is None else lat,
                         "LongitudeMeasure": "" if lon is None else lon, "lakeId": lid or "", "class": cls, "reason": why, "reviewNote": ""})
    rows.sort(key=lambda r: (r["lakeId"], r["class"], r["MonitoringLocationIdentifier"]))
    with open(out_csv, "w", encoding="utf-8", newline="") as fh:
        wr = csv.DictWriter(fh, fieldnames=V1.STATION_FIELDS)
        wr.writeheader()
        wr.writerows(rows)
    counts = {}
    for r in rows:
        counts[r["class"]] = counts.get(r["class"], 0) + 1
    return {"stations": len(rows), "byClass": counts}


def load_reviewed(draft_path: str, draft_sha: str, reviewed_path: str, reviewed_sha: str) -> dict:
    """The reviewed station file, checked against both posted hashes and the hashed draft (protocol stepA.stations)."""
    if V1.sha256_file(draft_path) != draft_sha:
        raise SystemExit("REFUSED: the draft station file's sha256 differs from the posted draft hash")
    if V1.sha256_file(reviewed_path) != reviewed_sha:
        raise SystemExit("REFUSED: the station file's sha256 differs from the posted reviewed-file hash")
    draft = {r["MonitoringLocationIdentifier"]: r for r in V1.read_csv(draft_path)}
    rev = {r["MonitoringLocationIdentifier"]: r for r in V1.read_csv(reviewed_path)}
    if set(draft) != set(rev):
        raise SystemExit("REFUSED: the reviewed station file adds or removes stations")
    for sid, r in rev.items():
        d = draft[sid]
        for f in ("OrganizationIdentifier", "MonitoringLocationName", "LatitudeMeasure", "LongitudeMeasure", "reason"):
            if (r.get(f) or "") != (d.get(f) or ""):
                raise SystemExit(f"REFUSED: station {sid} field {f} changed in review")
        changed = (r.get("class"), r.get("lakeId") or "") != (d.get("class"), d.get("lakeId") or "")
        if changed and d.get("class") != "UNCLASSIFIED":
            raise SystemExit(f"REFUSED: station {sid} was {d.get('class')} in the draft; only UNCLASSIFIED rows may be reviewed")
        if (d.get("lakeId") or "") and (r.get("lakeId") or "") != d["lakeId"]:
            raise SystemExit(f"REFUSED: station {sid} keeps the draft's lake {d['lakeId']}")
        if changed and not (r.get("reviewNote") or "").strip():
            raise SystemExit(f"REFUSED: station {sid} was reclassified without a reviewNote")
        if not changed and (r.get("reviewNote") or "") != (d.get("reviewNote") or ""):
            raise SystemExit(f"REFUSED: station {sid} has a reviewNote but was not reclassified")
        if r.get("class") == "MAIN_BODY" and (V1._f(r.get("LatitudeMeasure")) is None or V1._f(r.get("LongitudeMeasure")) is None or not r.get("lakeId")):
            raise SystemExit(f"REFUSED: MAIN_BODY station {sid} has no coordinates or lake")
    return rev


# ----------------------------------------------------------------------------------------------------------- readings
def depth_m(value, unit):
    v = V1._f(value)
    u = (unit or "").strip().lower()
    if v is None:
        return None
    if u in ("m", "meter", "meters", "metre", "metres"):
        return v
    if u in ("ft", "feet", "foot"):
        return v * 0.3048
    if u == "cm":
        return v / 100.0
    return None


def reading_depth(r: dict):
    """One depth order everywhere (protocol truthUnit.depthOrder): Result depth, then Activity depth."""
    d = depth_m(r.get("ResultDepthHeightMeasure/MeasureValue"), r.get("ResultDepthHeightMeasure/MeasureUnitCode"))
    if d is None:
        d = depth_m(r.get("ActivityDepthHeightMeasure/MeasureValue"), r.get("ActivityDepthHeightMeasure/MeasureUnitCode"))
    return d


def unit_known(unit) -> bool:
    return (unit or "").lower().replace(" ", "") in ("degc", "deg.c", "c", "degf", "deg.f", "f")


def reading_status(r: dict) -> str | None:
    """None if the row is a counted reading by metadata (step A and step B alike), else the reject reason."""
    if (r.get("CharacteristicName") or "").strip() != V1.CHARACTERISTIC:
        return "otherCharacteristic"
    if (r.get("ResultStatusIdentifier") or "").strip().lower() == "rejected":
        return "rejectedStatus"
    if not unit_known(r.get("ResultMeasure/MeasureUnitCode")):
        return "unknownUnit"
    d = reading_depth(r)
    if d is None:
        return "noDepth"
    if d > 1.5:
        return "deeperThan1.5m"
    return None


def reading_id(r: dict) -> str:
    return f"{r.get('ActivityIdentifier', '')}@{round(reading_depth(r), 4)}"


# ----------------------------------------------------------------------------------------------------------- census
def _dedupe(casts: dict, stations: dict) -> dict:
    """Same water and date, station coordinates within 0.002 deg: one cast (more readings, then key, wins). Stations
    without coordinates are never merged."""
    by = {}
    for key, c in casts.items():
        by.setdefault((c["lakeId"], c["date"]), []).append((key, c))
    keep = {}
    for group in by.values():
        group.sort(key=lambda kc: (-len(kc[1]["readings"]), kc[0]))
        chosen = []
        for key, c in group:
            s = stations.get(c["station"]) or {}
            lat, lon = V1._f(s.get("LatitudeMeasure")), V1._f(s.get("LongitudeMeasure"))
            dup = False
            if lat is not None and lon is not None:
                for _, k in chosen:
                    t = stations.get(k["station"]) or {}
                    tl, tn = V1._f(t.get("LatitudeMeasure")), V1._f(t.get("LongitudeMeasure"))
                    if tl is not None and tn is not None and abs(lat - tl) <= 0.002 and abs(lon - tn) <= 0.002:
                        dup = True
                        break
            if not dup:
                chosen.append((key, c))
        keep.update(dict(chosen))
    return keep


def census(p: dict, depth_rows: list[dict], stations: dict) -> dict:
    """Counted casts per water. Replacement candidates: WINDOW_START..CUTOFF. Frozen lakes: WINDOW_START..HOLDOUT_END only
    (their count to CUTOFF is reported for information)."""
    frozen = set(p["frozenLakes"])
    casts, rejects = {}, {}

    def rej(lid, why):
        rejects.setdefault(lid or "(unassigned)", {}).setdefault(why, 0)
        rejects[lid or "(unassigned)"][why] += 1

    for r in depth_rows:
        sid, d = r.get("MonitoringLocationIdentifier"), r.get("ActivityStartDate", "")
        s = stations.get(sid)
        lid = (s or {}).get("lakeId") or None
        if not s or s.get("class") != "MAIN_BODY" or not lid:
            rej(lid, "notMainBody")
            continue
        if not V1._date_in_window(d, WINDOW_START, CUTOFF):
            rej(lid, "outsideWindow")
            continue
        why = reading_status(r)
        if why:
            rej(lid, why)
            continue
        c = casts.setdefault((lid, sid, d), {"lakeId": lid, "station": sid, "date": d, "readings": set()})
        c["readings"].add(reading_id(r))
    qual = _dedupe(casts, stations)
    per = {}
    for w in waters(p):
        lid = w["lakeId"]
        all_keys = sorted(k for k in qual if k[0] == lid)
        keys = [k for k in all_keys if k[2] <= HOLDOUT_END] if lid in frozen else all_keys
        per[lid] = {"qualifyingCasts": len(keys), "window": [WINDOW_START, HOLDOUT_END if lid in frozen else CUTOFF],
                    "casts": {"|".join(k): sorted(qual[k]["readings"]) for k in keys}, "stepARejects": rejects.get(lid, {})}
        if lid in frozen:
            per[lid]["infoCastsToCutoff"] = len(all_keys)
    return {"waters": per, "unassignedRejects": rejects.get("(unassigned)", {})}


def _write_once(path: str, rec: dict) -> None:
    try:
        with open(path, "x", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=1)
    except FileExistsError:
        raise SystemExit(f"REFUSED: {os.path.basename(path)} already exists (write-once)")


# ----------------------------------------------------------------------------------------------------------- selection
def select(p: dict, census_rec: dict, excl: dict) -> dict:
    """Count-only retain/replace rule. Uses no value of any kind."""
    counts = {lid: v["qualifyingCasts"] for lid, v in census_rec["waters"].items()}
    ok = lambda lid: not excl.get(lid) and counts.get(lid, 0) >= PER_LAKE
    retained = [lid for lid in p["frozenLakes"] if ok(lid)]
    pool = sorted((lid for lid in counts if lid not in p["frozenLakes"] and ok(lid)),
                  key=lambda lid: (-counts[lid], hashlib.sha256(lid.encode()).hexdigest()))
    chosen = retained + pool[: max(0, SLOTS - len(retained))]
    total = sum(counts[l] for l in chosen)
    outcome = "SELECTED" if len(chosen) == SLOTS and total >= TOTAL else "INSUFFICIENT_TRUTH"
    return {"outcome": outcome, "retained": retained, "replacements": [l for l in chosen if l not in retained],
            "lakes": [{"lakeId": l, "qualifyingCasts": counts[l], "casts": census_rec["waters"][l]["casts"]} for l in chosen],
            "total": total, "needed": {"perLake": PER_LAKE, "total": TOTAL, "lakes": SLOTS},
            "shortfall": None if outcome == "SELECTED" else {"lakesWith25": len(chosen), "total": total},
            "frozenLakeStatus": {l: ("EXCLUDED: " + "; ".join(excl[l])) if excl.get(l) else f"{counts.get(l, 0)} casts to {HOLDOUT_END}" for l in p["frozenLakes"]},
            "rankedPool": [{"lakeId": l, "qualifyingCasts": counts[l]} for l in pool]}


# ----------------------------------------------------------------------------------------------------------- run ledger
ISSUE = f"{RL.ANCHOR_REPO}#{RL.ANCHOR_ISSUE}"
WAIT_SECONDS = 30


def check_ledger_constants(p: dict) -> None:
    rl = p.get("runLedger") or {}
    if sorted(rl.get("resultSteps") or []) != sorted(RESULT_STEPS) or (rl.get("keys") or {}) != STEP_KEYS:
        raise SystemExit("REFUSED: the runner's result steps or keys differ from the protocol's runLedger")


def open_ledger(digest: str, outs: list, cortex_home: str | None = None):
    """The protocol's run ledger: Ledger.for_brain('water-temp', ...), root from Cortex research-path, never inside an --out."""
    return RL.Ledger.for_brain(BRAIN, PROTOCOL_ID, digest, repo=REPO, forbid_under=[o for o in outs if o],
                               result_steps=RESULT_STEPS, cortex_home=cortex_home)


def gh_post(body: str) -> None:
    """Post a research record on Sector_Ops #51 with the caller's gh identity (never an Owner header)."""
    import subprocess
    import tempfile
    if body.lstrip().startswith("Owner"):
        raise SystemExit("REFUSED: research records never carry an Owner header")
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as fh:
        fh.write(body)
        path = fh.name
    try:
        r = subprocess.run(["gh", "api", f"repos/{RL.ANCHOR_REPO}/issues/{RL.ANCHOR_ISSUE}/comments", "-F", f"body=@{path}"],
                           capture_output=True, text=True, timeout=120)
    finally:
        os.unlink(path)
    if r.returncode != 0:
        raise SystemExit(f"posting on {ISSUE} failed: {r.stderr.strip()[:300]}")


def _sleep(seconds: float) -> None:
    import time
    time.sleep(seconds)


def publish_and_confirm(text: str, confirm, poster=None, text_path: str | None = None, wait_seconds: int = 3600, sleep=_sleep):
    """Post `text` once (poster), or write it to `text_path` for the operator to post, then call confirm() until #51 lists it.
    'not listed yet' means wait and retry; it never reposts. Any other refusal propagates."""
    if text_path:
        with open(text_path, "w", encoding="utf-8") as fh:
            fh.write(text)
    if poster is not None:
        poster(text)
    elif not text_path:
        raise SystemExit("REFUSED: no way to publish the record (pass --post, or a path for the operator to post by hand)")
    waited = 0
    while True:
        try:
            return confirm()
        except RL.LedgerRefusal as e:
            if "not listed yet" not in str(e) or waited >= wait_seconds:
                raise
        sleep(WAIT_SECONDS)
        waited += WAIT_SECONDS


def _completed(L, step: str) -> dict:
    """The counted COMPLETED entry of a step (result or not) for its protocol key; refuses otherwise."""
    key = STEP_KEYS[step]
    ents = L.entries()
    if step in RESULT_STEPS:
        done = L.require(step, key)
    else:
        found = [e for e in ents if e["step"] == step and e["key"] == key and e["status"] == RL.COMPLETED and e.get("counted") is True]
        if not found:
            raise RL.LedgerRefusal(f"{PROTOCOL_ID}: step {step!r} key {key!r} has no COMPLETED run; it must run first")
        done = found[0]
    started = next(e for e in ents if e["step"] == step and e["key"] == key and e["status"] == RL.STARTED and e["run"] == done["run"])
    return {**done, "inputs": started["inputs"]}         # inputs are recorded on the STARTED entry of the same run


def _require_output(L, step: str, name: str, path: str) -> dict:
    rec = _completed(L, step)
    if rec["outputs"].get(name) != V1.sha256_file(path):
        raise SystemExit(f"REFUSED: {os.path.basename(path)} is not the {step} output recorded in the run ledger")
    return rec


def _run_plain(L, step: str, args: dict, inputs: dict, work):
    """A non-result ledger step: begin (anchor checked), work() -> (value, outputs {name: sha256}), complete. A failure before any
    output is aborted before result, so the step may be retried."""
    key = STEP_KEYS[step]
    L.begin(step, key, args, inputs)
    try:
        value, outputs = work()
    except BaseException as e:
        L.abort_before_result(step, key, f"{type(e).__name__}: {str(e)[:200]}")
        raise
    L.complete(step, key, outputs)
    return value


def _run_result(L, step: str, args: dict, inputs: dict, compute, publish):
    """A result step: require_external_anchor, begin, publish Run start and confirm it, compute (never aborted once computing),
    complete with outputs and a small result, publish Run result and confirm it."""
    key = STEP_KEYS[step]
    L.require_external_anchor()
    L.begin(step, key, args, inputs)
    try:
        publish(L.start_text(step, key), lambda: L.confirm_started(step, key), "start")
    except RL.RepeatDetected:
        raise
    except BaseException as e:
        L.abort_before_result(step, key, f"start record not confirmed: {type(e).__name__}: {str(e)[:200]}")
        raise
    value, outputs, result = compute()                      # values may be seen from here on: no abort
    L.complete(step, key, outputs, result)
    publish(L.result_text(step, key), lambda: L.confirm_result(step, key), "result")
    return value


def cmd_exclusions(p: dict, digest: str, L, reg_dir: str, sites_path: str, calibration: str, calibration_lakes: str,
                   wt_sat_1: str | None, out: str) -> dict:
    sites = V1.read_csv(sites_path)
    missing = unresolved_calibration(sites, calibration)
    if missing:
        raise SystemExit(f"REFUSED: M0 calibration sites without coordinates: {missing}")
    cal_lakes = json.load(open(calibration_lakes, encoding="utf-8"))
    if not isinstance(cal_lakes, list):
        raise SystemExit("REFUSED: --calibration-lakes must be a JSON list")
    sat = set(json.load(open(wt_sat_1, encoding="utf-8"))) if wt_sat_1 else set()
    if os.path.exists(out):
        raise SystemExit(f"REFUSED: {os.path.basename(out)} already exists (write-once)")
    inputs = {"sites.csv": V1.sha256_file(sites_path), "calibration": V1.sha256_file(calibration),
              "calibrationLakes": V1.sha256_file(calibration_lakes), "registryTree": RL.sha256_tree(reg_dir)}
    if wt_sat_1:
        inputs["wtSat1"] = V1.sha256_file(wt_sat_1)

    def work():
        ex = exclusions(p, load_registry(reg_dir), sites, set(cal_lakes), bound_lakes(), sat)
        rec = {"labels": LABELS, "protocolId": p["protocolId"], "protocolSha256": digest,
               "wtSat1List": sorted(sat) if sat else "unfrozen: LK-in-polygon rule", "sitesSha256": inputs["sites.csv"],
               "calibrationSha256": inputs["calibration"], "calibrationLakes": sorted(cal_lakes),
               "calibrationLakesSha256": inputs["calibrationLakes"], "exclusions": ex}
        _write_once(out, rec)
        return rec, {"exclusions.json": V1.sha256_file(out)}
    return _run_plain(L, "exclusions", {"wtSat1": "committed" if sat else "unfrozen"}, inputs, work)


def cmd_census(p: dict, digest: str, L, wqp: str, draft: str, draft_sha: str, reviewed: str, reviewed_sha: str, excl_path: str, out: str) -> dict:
    if os.path.exists(out):
        raise SystemExit(f"REFUSED: {os.path.basename(out)} already exists (write-once)")
    _require_output(L, "exclusions", "exclusions.json", excl_path)
    stations = load_reviewed(draft, draft_sha, reviewed, reviewed_sha)
    depth = []
    for w in waters(p):
        path = os.path.join(wqp, f"{slug(w['lakeId'])}.resultdepth.csv")
        if os.path.exists(path):
            rows = V1.read_csv(path)
            if rows and any(k not in RESULT_DEPTH_COLUMNS for k in rows[0]):
                raise SystemExit("REFUSED: a result-depth file carries a non-whitelisted column; step A never stores values")
            depth += rows
    excl = json.load(open(excl_path, encoding="utf-8"))
    if excl.get("protocolSha256") != digest:
        raise SystemExit("REFUSED: exclusions made under a different protocol")
    inputs = {"stationDraft": draft_sha, "stationReviewed": reviewed_sha, "exclusions.json": V1.sha256_file(excl_path),
              "wqpTree": RL.sha256_tree(wqp)}

    def work():
        rec = {"labels": LABELS, "protocolId": p["protocolId"], "protocolSha256": digest, "step": "A_census_v6", "valuesOpened": False,
               "cutoff": CUTOFF, "stationDraftSha256": draft_sha, "stationFileSha256": reviewed_sha,
               "exclusionsSha256": inputs["exclusions.json"], "wqpTreeSha256": inputs["wqpTree"], "authoritativeScoresUnchanged": True,
               **census(p, depth, stations)}
        _write_once(out, rec)
        return rec, {"census.json": V1.sha256_file(out)}
    return _run_plain(L, "census", {}, inputs, work)


def cmd_select(p: dict, digest: str, L, census_path: str, excl_path: str, out: str, publish) -> dict:
    census_rec = _require_output(L, "census", "census.json", census_path)
    _require_output(L, "exclusions", "exclusions.json", excl_path)
    c = json.load(open(census_path, encoding="utf-8"))
    if c.get("protocolSha256") != digest:
        raise SystemExit("REFUSED: census made under a different protocol")
    if os.path.exists(out):
        raise SystemExit(f"REFUSED: {os.path.basename(out)} already exists (write-once)")
    excl = json.load(open(excl_path, encoding="utf-8"))["exclusions"]
    inputs = {"census.json": V1.sha256_file(census_path), "exclusions.json": V1.sha256_file(excl_path),
              "stationReviewed": census_rec["inputs"]["stationReviewed"]}

    def compute():
        rec = {"labels": LABELS, "protocolId": p["protocolId"], "protocolSha256": digest, "step": "A_selection_v6", "valuesOpened": False,
               "censusSha256": inputs["census.json"], "stationDraftSha256": c["stationDraftSha256"], "stationFileSha256": c["stationFileSha256"],
               "exclusionsSha256": c["exclusionsSha256"], "authoritativeScoresUnchanged": True, **select(p, c, excl)}
        _write_once(out, rec)
        sha = V1.sha256_file(out)
        return rec, {"selection.json": sha}, {"outcome": rec["outcome"], "selectionSha256": sha, "total": rec["total"],
                                             "lakes": [l["lakeId"] for l in rec["lakes"]]}
    return _run_result(L, "select", {}, inputs, compute, publish)


# ----------------------------------------------------------------------------------------------------------- step B
def load_selection_for_step_b(L, sel_path: str, stations_path: str, digest: str, owner_request: str | None) -> tuple[dict, str]:
    """The ledger's counted selection (the only valid one), checked against the files given. Returns (selection, its sha256)."""
    if not owner_request or not owner_request.startswith("Owner request (Michael, "):
        raise SystemExit("REFUSED: step B opens protected values and needs --owner-request 'Owner request (Michael, ...)' "
                         "(a string check; the request posted on Sector_Ops #51 is the control)")
    rec = _require_output(L, "select", "selection.json", sel_path)
    if rec["result"].get("outcome") != "SELECTED":
        raise SystemExit("REFUSED: the recorded selection is not SELECTED; protected values stay closed")
    if not any(e["step"] == "select" and e["status"] == RL.RESULT_CONFIRMED for e in L.entries()):
        raise SystemExit(f"REFUSED: the selection's Run result is not confirmed on {ISSUE}")
    sel = json.load(open(sel_path, encoding="utf-8"))
    if sel.get("protocolSha256") != digest or sel.get("outcome") != "SELECTED":
        raise SystemExit("REFUSED: selection does not match this protocol or is not SELECTED")
    census = _completed(L, "census")
    if V1.sha256_file(stations_path) != sel.get("stationFileSha256") or sel.get("stationFileSha256") != census["inputs"].get("stationReviewed"):
        raise SystemExit("REFUSED: the station file differs from the one the census recorded")
    return sel, V1.sha256_file(sel_path)


TERMINAL_FETCH = ("{step}/{key} received {n} value-bearing body(ies) before it failed, so this attempt is TERMINAL: it is left "
                  "STARTED and is never aborted, because a retry after seeing values is a peek. Recovery needs a new protocol id AND a "
                  "revised protocol document (new sha256) that records the #51 human review. Cause: {cause}")


def _fetch_step(L, step: str, sel_sha: str, out: str, prov_name: str, names: list[str], fetch) -> dict:
    """A non-result fetch. fetch(receive) calls receive(name, body) the moment each response body arrives, before it parses or
    writes it: receive binds the body's sha256 in the ledger at once, so the audit trail shows what was received. A failure before
    the first body may abort (the step can be retried); after it, the attempt is terminal and is never aborted (protocol
    runLedger.runsThatCount: abort only before any value is seen)."""
    key = STEP_KEYS[step]
    L.begin(step, key, {}, {"selection.json": sel_sha})
    received = []

    def receive(name: str, body: bytes) -> None:
        received.append(name)                               # values are in hand from here on, whatever happens next
        L.bind_inputs(step, key, {name: RL.sha256_bytes(body)})

    try:
        fetch(receive)
        L.bind_inputs(step, key, {n: Path(out, n) for n in names + [prov_name]})
    except BaseException as e:
        cause = f"{type(e).__name__}: {str(e)[:200]}"
        if not received:
            L.abort_before_result(step, key, cause)
            raise
        raise SystemExit("REFUSED (terminal): " + TERMINAL_FETCH.format(step=step, key=key, n=len(received), cause=cause)) from e
    L.complete(step, key, {prov_name: V1.sha256_file(os.path.join(out, prov_name))})
    return {"files": len(names)}


def cmd_fetch_forcing(p: dict, digest: str, L, sel_path: str, stations: str, owner_request: str, out: str) -> dict:
    sel, sel_sha = load_selection_for_step_b(L, sel_path, stations, digest, owner_request)
    names = [forcing_file(l["lakeId"]) for l in sel["lakes"]]
    _refuse_existing(out, ["forcing.provenance.json"] + names)

    def fetch(receive):
        prov = []
        for l in sel["lakes"]:
            params = forcing_params(p, sel, l["lakeId"])
            body = _get_bytes(V1.OPEN_METEO, params)
            receive(forcing_file(l["lakeId"]), body)
            check_forcing(json.loads(body), [d for lid, _, d in counted_casts(sel) if lid == l["lakeId"]])
            _save(out, forcing_file(l["lakeId"]), body, V1.OPEN_METEO, params, prov)
        V1.write_provenance(out, "forcing.provenance.json", prov)
    return _fetch_step(L, "fetch-forcing", sel_sha, out, "forcing.provenance.json", names, fetch)


def cmd_fetch_results(p: dict, digest: str, L, sel_path: str, stations: str, owner_request: str, out: str) -> dict:
    sel, sel_sha = load_selection_for_step_b(L, sel_path, stations, digest, owner_request)
    _refuse_existing(out, ["results.provenance.json", "results"])
    qs = result_queries(sel)

    def fetch(receive):
        prov, url = [], V1.WQP.format(kind="Result")
        for q in qs:
            body = _get_bytes(url, q["params"])
            receive(q["file"], body)
            _save(out, q["file"], body, url, q["params"], prov)
        V1.write_provenance(out, "results.provenance.json", prov)
    return _fetch_step(L, "fetch-results", sel_sha, out, "results.provenance.json", [q["file"] for q in qs], fetch)


def verify_against_provenance(folder: str, prov_name: str, expected: dict, listing: list[str], url: str) -> dict:
    """expected: {relative file: params}. Refuse unless the provenance lists exactly those files once each, with those params
    and the expected endpoint URL, the folder holds exactly those files, and every sha256 matches. Returns {file: sha256}."""
    pp = os.path.join(folder, prov_name)
    if not os.path.exists(pp):
        raise SystemExit(f"REFUSED: {prov_name} is missing")
    items = json.load(open(pp, encoding="utf-8")).get("items") or []
    paths = [i.get("path") for i in items]
    if len(paths) != len(set(paths)):
        raise SystemExit(f"REFUSED: {prov_name} lists a file twice")
    if set(paths) != set(expected):
        raise SystemExit(f"REFUSED: {prov_name} does not list exactly the files the selection implies "
                         f"(missing {sorted(set(expected) - set(paths))[:3]}, extra {sorted(set(paths) - set(expected))[:3]})")
    if sorted(listing) != sorted(expected):
        raise SystemExit(f"REFUSED: the folder does not hold exactly the provenance files "
                         f"(missing {sorted(set(expected) - set(listing))[:3]}, extra {sorted(set(listing) - set(expected))[:3]})")
    hashes = {}
    for i in items:
        if i.get("url") != url:
            raise SystemExit(f"REFUSED: {i['path']} was not fetched from {url}")
        if i.get("params") != expected[i["path"]]:
            raise SystemExit(f"REFUSED: {i['path']} was fetched with parameters the selection does not imply")
        h = V1.sha256_file(os.path.join(folder, i["path"]))
        if h != i.get("sha256"):
            raise SystemExit(f"REFUSED: {i['path']} changed after it was fetched")
        hashes[i["path"]] = h
    return hashes


def counted_casts(sel: dict) -> list[tuple[str, str, str]]:
    return sorted(V1._split_key(k) for l in sel["lakes"] for k in l["casts"])


def forcing_window(sel: dict, lake_id: str) -> tuple[str, str]:
    """[earliest counted cast - 46 days, latest counted cast] for one selected water (protocol stepB.forcing)."""
    ds = sorted(d for lid, _, d in counted_casts(sel) if lid == lake_id)
    return (dt.date.fromisoformat(ds[0]) - dt.timedelta(days=SPIN_UP_DAYS)).isoformat(), ds[-1]


def forcing_params(p: dict, sel: dict, lake_id: str) -> dict:
    lat, lon = {w["lakeId"]: w["point"] for w in waters(p)}[lake_id]
    start, end = forcing_window(sel, lake_id)
    return {"latitude": lat, "longitude": lon, "start_date": start, "end_date": end, "timezone": "auto", "daily": FORCING_DAILY}


def forcing_file(lake_id: str) -> str:
    return f"{slug(lake_id)}.forcing.json"


def check_forcing(forc: dict, dates: list[str]) -> None:
    """Refuse forcing that does not contain every day from 45 days before each counted cast to the cast."""
    have = set((forc.get("daily") or {}).get("time") or [])
    for d in dates:
        d0 = dt.date.fromisoformat(d)
        missing = [x for x in ((d0 - dt.timedelta(days=j)).isoformat() for j in range(SPIN_UP_DAYS)) if x not in have]
        if missing:
            raise SystemExit(f"REFUSED: forcing does not cover counted cast {d} (missing {missing[0]} ...)")


def result_queries(sel: dict) -> list[dict]:
    out = []
    for lid, sid, d in counted_casts(sel):
        day = dt.date.fromisoformat(d).strftime("%m-%d-%Y")
        out.append({"lakeId": lid, "siteid": sid, "date": d, "file": f"results/{slug(lid)}__{slug(sid)}__{d}.csv",
                    "params": {"siteid": sid, "characteristicName": V1.CHARACTERISTIC, "startDateLo": day, "startDateHi": day,
                               "mimeType": "csv", "zip": "no"}})
    return out


def _refuse_existing(out: str, names: list[str]) -> None:
    for n in names:
        if os.path.exists(os.path.join(out, n)):
            raise SystemExit(f"REFUSED: {n} already exists in the output folder (write-once)")


def truth_values(sel: dict, results: list[dict]) -> tuple[dict, dict, dict]:
    """({castKey: surface deg C}, {castKey: [truth rejects]}, {castKey: [counted readings not returned]}) from the counted
    readings only (protocol truthUnit). Refuses duplicate reading ids."""
    counted = {}
    for l in sel["lakes"]:
        for k, readings in l["casts"].items():
            lid, sid, d = V1._split_key(k)
            counted[(sid, d)] = ((lid, sid, d), set(readings))
    vals, rejects, seen = {}, {}, set()
    for r in results:
        key = (r.get("MonitoringLocationIdentifier"), r.get("ActivityStartDate", ""))
        if key not in counted or reading_status(r) is not None:
            continue
        cast, ids = counted[key]
        rid = reading_id(r)
        if rid not in ids:
            continue
        if (cast, rid) in seen:
            raise SystemExit(f"REFUSED: reading {rid} appears twice in the step-B results")
        seen.add((cast, rid))
        t = V1.to_c(r.get("ResultMeasureValue"), r.get("ResultMeasure/MeasureUnitCode"))
        if t is None:
            rejects.setdefault(cast, []).append(f"{rid}: no value")
            continue
        if not (-0.5 <= t <= 40.0):
            rejects.setdefault(cast, []).append(f"{rid}: outside -0.5..40 C")
            continue
        vals.setdefault(cast, {})[rid] = (reading_depth(r), t)
    not_returned = {}
    for cast, ids in counted.values():
        missing = sorted(rid for rid in ids if (cast, rid) not in seen)
        if missing:
            not_returned[cast] = missing
    out = {}
    for cast, rs in vals.items():
        top = [t for dpt, t in rs.values() if dpt <= 1.0]
        out[cast] = sum(top) / len(top) if top else sorted(rs.values())[0][1]
    return out, rejects, not_returned


def compare(p: dict, sel: dict, results: list[dict], forcing: dict) -> dict:
    m0_daily, m0_for_date, m0_sha = V1.m0_functions()
    truth, rejects, not_returned = truth_values(sel, results)
    per = {}
    for l in sel["lakes"]:
        lid = l["lakeId"]
        casts = [c for c in counted_casts(sel) if c[0] == lid]
        rec = {"counted": len(casts), "truthRejectsStepB": {"|".join(c): rejects[c] for c in casts if c in rejects},
               "notReturned": {"|".join(c): not_returned[c] for c in casts if c in not_returned}, "failed": []}
        if rec["notReturned"]:
            rec["failed"].append("CAST_NOT_RETURNED")
        if lid not in forcing:
            rec["failed"].append("FORCING_MISSING")
            rec["n"] = 0
            per[lid] = rec
            continue
        check_forcing(forcing[lid], [c[2] for c in casts])
        forc = m0_daily(forcing[lid]["daily"])
        pairs, unpaired = [], []
        for c in casts:
            if c not in truth:
                continue
            m = m0_for_date(forc, c[2])
            if m is None:
                unpaired.append("|".join(c))
                continue
            pairs.append((c[2], m, truth[c]))
        rec.update({**V1.lake_metrics(pairs), "castsWithoutTruth": sum(1 for c in casts if c not in truth), "unpairedCasts": unpaired})
        if unpaired:
            rec["failed"].append("UNPAIRED_CAST")
        if rec["n"] < PER_LAKE:
            rec["failed"].append("SCORED_BELOW_25")
        per[lid] = rec
    scored = {k: v for k, v in per.items() if not v["failed"]}
    pooled = math.sqrt(sum(v["mseC2"] for v in scored.values()) / len(scored)) if len(scored) == SLOTS else None
    lake_pass = {k: (not v["failed"] and v["rmseC"] <= RMSE_MARK) for k, v in per.items()}
    outcome = "PASS" if pooled is not None and pooled <= RMSE_MARK and all(lake_pass.values()) else "FAIL"
    for v in per.values():
        v.pop("mseC2", None)
    return {"labels": LABELS, "protocolId": p["protocolId"], "step": "B_compare_v6", "valuesOpened": True,
            "model": "surface-energy-balance-v2 (M0, k = 0.09)", "m0ImplementationSha256": m0_sha, "perLake": per,
            "perLakePass": lake_pass, "pooledEqualLakeRmseC": None if pooled is None else round(pooled, 4), "outcome": outcome,
            "authoritativeScoresUnchanged": True,
            "scoreImpact": "none: the frozen water-temp block changes only by an owner decision in a separate change"}


def _listing(folder: str, sub: str | None = None, suffix: str = "") -> list[str]:
    base = os.path.join(folder, sub) if sub else folder
    if not os.path.isdir(base):
        return []
    return sorted((f"{sub}/{n}" if sub else n) for n in os.listdir(base) if n.endswith(suffix) and os.path.isfile(os.path.join(base, n)))


def cmd_compare(p: dict, digest: str, L, sel_path: str, stations: str, results_dir: str, forcing_dir: str,
                owner_request: str, out: str, publish) -> dict:
    """A result step. Every check (ledger inputs, provenance) runs before begin; once it computes it is never aborted."""
    if os.path.exists(out):
        raise SystemExit("REFUSED: a comparison result already exists; compare is write-once")
    sel, sel_sha = load_selection_for_step_b(L, sel_path, stations, digest, owner_request)
    _completed(L, "fetch-results")
    _completed(L, "fetch-forcing")
    exp_results = {q["file"]: q["params"] for q in result_queries(sel)}
    exp_forcing = {forcing_file(l["lakeId"]): forcing_params(p, sel, l["lakeId"]) for l in sel["lakes"]}
    L.check_inputs("fetch-results", STEP_KEYS["fetch-results"], {n: Path(results_dir, n) for n in list(exp_results) + ["results.provenance.json"]})
    L.check_inputs("fetch-forcing", STEP_KEYS["fetch-forcing"], {n: Path(forcing_dir, n) for n in list(exp_forcing) + ["forcing.provenance.json"]})
    rhash = verify_against_provenance(results_dir, "results.provenance.json", exp_results, _listing(results_dir, "results"), V1.WQP.format(kind="Result"))
    fhash = verify_against_provenance(forcing_dir, "forcing.provenance.json", exp_forcing, _listing(forcing_dir, None, ".forcing.json"), V1.OPEN_METEO)
    inputs = {"selection.json": sel_sha, **{f"results/{k}": v for k, v in rhash.items()}, **{f"forcing/{k}": v for k, v in fhash.items()}}

    def compute():
        results = []
        for f in sorted(exp_results):
            results += V1.read_csv(os.path.join(results_dir, f))
        forcing = {l["lakeId"]: json.load(open(os.path.join(forcing_dir, forcing_file(l["lakeId"])), encoding="utf-8")) for l in sel["lakes"]}
        rec = compare(p, sel, results, forcing)
        rec.update({"protocolSha256": digest, "selectionSha256": sel_sha, "stationFileSha256": sel["stationFileSha256"],
                    "inputSha256": {k: v for k, v in inputs.items() if k != "selection.json"}, "ownerRequest": owner_request})
        _write_once(out, rec)
        summary = {"outcome": rec["outcome"], "pooledEqualLakeRmseC": rec["pooledEqualLakeRmseC"], "perLakePass": rec["perLakePass"],
                   "failed": {k: v["failed"] for k, v in rec["perLake"].items() if v["failed"]}}
        return rec, {"compare.json": V1.sha256_file(out)}, summary
    return _run_result(L, "compare", {}, inputs, compute, publish)


# ----------------------------------------------------------------------------------------------------------- CLI
def _publisher(args, out_path: str | None):
    """publish(text, confirm, what): post with gh (--post) or write the text beside the output for the operator to post by hand,
    then wait for #51 to list it (never reposting)."""
    def publish(text, confirm, what):
        path = f"{out_path}.{what}.txt" if out_path else None
        return publish_and_confirm(text, confirm, gh_post if args.post else None, path, args.wait_seconds)
    return publish


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--protocol", default=PROTOCOL)
    ap.add_argument("--cortex-home", default=None, help="Cortex location (default: CORTEX_HOME); the ledger root comes from its research-path")
    ap.add_argument("--post", action="store_true", help="post anchor/start/result records on Sector_Ops #51 with gh (research records)")
    ap.add_argument("--wait-seconds", type=int, default=3600, help="how long to wait for #51 to list a record (never reposting)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("verify")
    s = sub.add_parser("anchor"); s.add_argument("--out", required=True, help="file to write the Run anchor text to")
    sub.add_parser("check-anchor")
    s = sub.add_parser("fetch-registry"); s.add_argument("--out", required=True)
    s = sub.add_parser("fetch-usgs"); s.add_argument("--registry", required=True); s.add_argument("--calibration", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("fetch-wqp"); s.add_argument("--registry", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("exclusions"); s.add_argument("--registry", required=True); s.add_argument("--sites", required=True)
    s.add_argument("--calibration", required=True)
    s.add_argument("--calibration-lakes", required=True, help="JSON list of directory ids in the M0 calibration set (may be [])")
    s.add_argument("--wt-sat-1", default=None, help="committed WT-SAT-1 lake list (JSON list), once frozen"); s.add_argument("--out", required=True)
    s = sub.add_parser("stations"); s.add_argument("--registry", required=True); s.add_argument("--wqp", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("census"); s.add_argument("--wqp", required=True)
    s.add_argument("--stations-draft", required=True); s.add_argument("--stations-draft-sha256", required=True)
    s.add_argument("--stations", required=True); s.add_argument("--stations-sha256", required=True)
    s.add_argument("--exclusions", required=True); s.add_argument("--out", required=True)
    s = sub.add_parser("select"); s.add_argument("--census", required=True); s.add_argument("--exclusions", required=True); s.add_argument("--out", required=True)
    for name in ("fetch-forcing", "fetch-results", "compare"):
        s = sub.add_parser(name); s.add_argument("--selection", required=True)
        s.add_argument("--stations", required=True); s.add_argument("--owner-request"); s.add_argument("--out", required=True)
        if name == "compare":
            s.add_argument("--results", required=True); s.add_argument("--forcing", required=True)
    a = ap.parse_args(argv)
    p, digest = load_protocol(a.protocol)
    check_ledger_constants(p)
    outs = [getattr(a, "out", None), getattr(a, "results", None), getattr(a, "forcing", None)]
    if a.cmd in ("anchor", "select", "compare", "exclusions", "census") and getattr(a, "out", None):
        outs[0] = os.path.dirname(os.path.abspath(a.out))
    ledger_cmds = ("anchor", "check-anchor", "exclusions", "census", "select", "fetch-forcing", "fetch-results", "compare")
    try:
        L = open_ledger(digest, outs, a.cortex_home) if a.cmd in ledger_cmds else None
        if a.cmd == "verify":
            res = {"protocolId": p["protocolId"], "sha256": digest, "censusCutoff": CUTOFF, "resultSteps": sorted(RESULT_STEPS), "status": "OK"}
        elif a.cmd == "anchor":
            text = L.post_anchor_text()
            if os.path.exists(a.out):
                raise SystemExit(f"REFUSED: {os.path.basename(a.out)} already exists")
            with open(a.out, "x", encoding="utf-8") as fh:
                fh.write(text)
            if a.post:
                gh_post(text)
            res = {"anchor": L.anchor(), "text": a.out, "posted": bool(a.post), "next": "check-anchor (wait and retry if not listed yet; never repost)"}
        elif a.cmd == "check-anchor":
            res = L.require_external_anchor()
        elif a.cmd == "fetch-registry":
            res = cmd_fetch_registry(p, a.out)
        elif a.cmd == "fetch-usgs":
            res = cmd_fetch_usgs(p, load_registry(a.registry), a.calibration, a.out)
        elif a.cmd == "fetch-wqp":
            res = cmd_fetch_wqp(p, load_registry(a.registry), a.out)
        elif a.cmd == "exclusions":
            rec = cmd_exclusions(p, digest, L, a.registry, a.sites, a.calibration, a.calibration_lakes, a.wt_sat_1, a.out)
            res = {"excluded": sum(1 for v in rec["exclusions"].values() if v), "eligible": sum(1 for v in rec["exclusions"].values() if not v)}
        elif a.cmd == "stations":
            res = cmd_stations(p, load_registry(a.registry), a.wqp, a.out)
        elif a.cmd == "census":
            r = cmd_census(p, digest, L, a.wqp, a.stations_draft, a.stations_draft_sha256, a.stations, a.stations_sha256, a.exclusions, a.out)
            res = {"waters": {k: {kk: vv for kk, vv in v.items() if kk != "casts"} for k, v in r["waters"].items()}}
        elif a.cmd == "select":
            r = cmd_select(p, digest, L, a.census, a.exclusions, a.out, _publisher(a, a.out))
            res = {"outcome": r["outcome"], "lakes": [(l["lakeId"], l["qualifyingCasts"]) for l in r["lakes"]], "total": r["total"],
                   "selectionSha256": V1.sha256_file(a.out)}
        elif a.cmd == "fetch-forcing":
            res = cmd_fetch_forcing(p, digest, L, a.selection, a.stations, a.owner_request, a.out)
        elif a.cmd == "fetch-results":
            res = cmd_fetch_results(p, digest, L, a.selection, a.stations, a.owner_request, a.out)
        else:
            r = cmd_compare(p, digest, L, a.selection, a.stations, a.results, a.forcing, a.owner_request, a.out, _publisher(a, a.out))
            res = {k: r[k] for k in ("outcome", "pooledEqualLakeRmseC", "perLakePass")}
        if L is not None:
            res = {"result": res, "ledger": L.audit()}
    except RL.LedgerRefusal as e:
        raise SystemExit(f"REFUSED (run ledger): {e}")
    print(json.dumps(res, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
