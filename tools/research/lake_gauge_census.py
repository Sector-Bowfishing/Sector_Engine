#!/usr/bin/env python3
"""Lake gauge census: GET-only, metadata-only discovery of gauge-grade level series for every directory lake (rules LGC-2026-11-23).

Two purposes, one pass (docs/brains/lake-gauge-census/LGC-2026-11-23.rules.json, pre-registered and hashed before any request):
  BINDING            unprofiled lakes (not in Lake's reviewed set): candidate pool series for the next binding batch (stage A
                     shortlist; the stage B review with level values follows the same rules as batches 1-2 and runs later).
  INDEPENDENT_TRUTH  every lake with a binding: series that are NOT the lake's bound live/fallback/history series, with
                     independence evidence, so the operator-truth validation v3 can freeze a truth list from metadata alone.

Sources: USGS WaterServices site catalog (fallback: USGS Water Data OGC API), USACE CWMS Data API catalogs, Reclamation RISE
JSON:API, and Sector's public Lake Registry outlines. The TVA host, NWS NWPS/HADS and SWOT are never queried.

It never writes Firebase, buckets, bindings, accepted lists, the knowledge release or any score. It writes only to --out.
The one data call (USGS instantaneous values, last 12 h, shortlisted pool candidates only) keeps time stamps and drops every value
at parse time. It refuses to run before the rules' notBefore date (the operator-truth validation, PR #243, runs 2026-11-24..30).

    lakes        offline: the 621-lake target table (purpose per lake, bound series, prior research status)
    verify       check the rules file against its committed sha256
    controls     run discovery on three positive-control lakes; a provider whose known series is not rediscovered is disabled
    census       the full census (controls first), writes census.json, census.summary.json, robots.json, requests.jsonl
    summarize    print the short #51 summary from census.summary.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
RULES = os.path.join(REPO, "docs", "brains", "lake-gauge-census", "LGC-2026-11-23.rules.json")
DIRECTORY = os.path.join(REPO, "brains", "moon", "runtime", "knowledge", "lakes-directory.json")
REVIEWED = os.path.join(REPO, "jobs", "brain_platform", "sector_brain_platform", "publisher_live", "customer_lake_level_eligible.json")
GENERATED = os.path.join(REPO, "brains", "lake", "runtime", "LakeBrain", "LakeSourceBindingsGenerated.swift")
HANDWRITTEN = os.path.join(REPO, "brains", "lake", "runtime", "LakeBrain", "LakeSourceBindings.swift")
EXCLUDED = os.path.join(REPO, "jobs", "lake-brain", "data", "bindings.proposed.v1.excluded.json")
HELD = os.path.join(REPO, "jobs", "lake-brain", "review", "held_lakes.json")
REGISTRY_BASE = "https://storage.googleapis.com/sector-lake-registry"
LABELS = ["INTERNAL_EXPERIMENTAL", "NOT_FOR_CUSTOMERS"]

USGS_SITE = "https://waterservices.usgs.gov/nwis/site/"
USGS_IV = "https://waterservices.usgs.gov/nwis/iv/"
USGS_OGC = "https://api.waterdata.usgs.gov/ogcapi/v0/collections/{c}/items"
CWMS = "https://cwms-data.usace.army.mil/cwms-data/catalog/{kind}"
CWMS_ACCEPT = "application/json;version=2"
RISE = "https://data.usbr.gov/rise/api/{path}"
RISE_ACCEPT = "application/vnd.api+json"

# The five hand-written REVIEWED pilots (brains/lake/runtime/LakeBrain/LakeSourceBindings.swift `handWritten`); a test keeps the ids
# equal to that file. TVA pilots read the TVA host (never queried here) and its operating-guide history.
PILOTS = {
    "Guntersville|AL": [{"provider": "tva", "station": "GVDA1", "series": None, "role": "primary"}],
    "Wheeler|AL": [{"provider": "tva", "station": "WHLA1", "series": None, "role": "primary"}],
    "Wilson|AL": [{"provider": "tva", "station": "WLSA1", "series": None, "role": "primary"}],
    "Pickwick Lake|TN": [{"provider": "tva", "station": "PICT1", "series": None, "role": "primary"}],
    "Lake Hartwell|SC": [{"provider": "cwms", "station": "SAS", "series": "Hartwell.Elev-Pool.Inst.1Hour.0.Raw-SHEF_SAS", "role": "primary"},
                         {"provider": "usgs", "station": "02187010", "series": "00062", "role": "fallback"},
                         {"provider": "cwms", "station": "SAS", "series": "Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS", "role": "history"}],
}


# TVA reservoirs in the directory with no binding (2026-11-23); the bound TVA lakes are found from their `tva` series.
TVA_UNBOUND = {"Fontana Lake|NC", "Hiwassee Lake|NC"}


# ------------------------------------------------------------------------------------------------------------------ files
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def load_rules(path: str = RULES) -> tuple[dict, str]:
    """Load the rules and refuse them unless their sha256 equals the committed sidecar (pre-registration is immutable)."""
    digest = sha256_file(path)
    side = path + ".sha256"
    if not os.path.exists(side):
        raise SystemExit(f"REFUSED: no committed hash sidecar {os.path.basename(side)}")
    expected = open(side, encoding="utf-8").read().split()[0]
    if digest != expected:
        raise SystemExit(f"REFUSED: rules sha256 {digest} != pre-registered {expected}")
    return json.load(open(path, encoding="utf-8")), digest


def generated_bindings(path: str = GENERATED) -> list[dict]:
    s = open(path, encoding="utf-8").read()
    i = s.index('#"""') + 4
    return json.loads(s[i:s.index('"""#', i)])


def handwritten_ids(path: str = HANDWRITTEN) -> list[str]:
    s = open(path, encoding="utf-8").read()
    block = s[s.index("static let handWritten"):s.index("public static let pilots")]
    return re.findall(r'tvaPilot\("([^"]+)"', block) + re.findall(r'lakeId: "([^"]+)", status: \.reviewed', block)


def bound_refs(row: dict) -> list[dict]:
    """Every series a binding reads: live[0] primary, live[1:] fallbacks, history."""
    out = []
    for i, ref in enumerate(row.get("live") or []):
        out.append({"provider": ref["provider"], "station": ref.get("station"), "series": ref.get("series"),
                    "role": "primary" if i == 0 else "fallback"})
    for h in row.get("history") or []:
        k = h.get("kind")
        if k == "cwmsDaily":
            out.append({"provider": "cwms", "station": h.get("office"), "series": h.get("series"), "role": "history"})
        elif k in ("usgsDaily", "usgsStageDaily"):
            out.append({"provider": "usgs", "station": h.get("site"), "series": h.get("param"), "role": "history"})
        elif k == "riseDaily":
            out.append({"provider": "rise", "station": str(h.get("item")), "series": str(h.get("item")), "role": "history"})
        elif k == "hadsDaily":
            out.append({"provider": "hads", "station": h.get("lid"), "series": h.get("pe"), "role": "history"})
        elif k == "tvaOperatingGuide":
            out.append({"provider": "tva", "station": h.get("locationId"), "series": None, "role": "history"})
        else:
            out.append({"provider": k, "station": None, "series": None, "role": "history"})
    return out


def load_targets(directory: str = DIRECTORY, reviewed: str = REVIEWED, generated: str = GENERATED, handwritten: str = HANDWRITTEN,
                 excluded: str = EXCLUDED, held: str = HELD) -> dict:
    """The 621-lake target table, built offline from committed files (read only)."""
    lakes = json.load(open(directory, encoding="utf-8"))["lakes"]
    rev = set(json.load(open(reviewed, encoding="utf-8"))["lakeIds"])
    hand = handwritten_ids(handwritten)
    if set(hand) != set(PILOTS):
        raise SystemExit(f"REFUSED: hand-written pilots {sorted(hand)} differ from this tool's PILOTS table")
    bindings = {r["lakeId"]: bound_refs(r) for r in generated_bindings(generated)}
    bindings.update(PILOTS)
    prior = {}
    if os.path.exists(excluded):
        for r in json.load(open(excluded, encoding="utf-8"))["excluded"]:
            prior[r["lakeId"]] = {"researchStatus": r.get("researchStatus"), "primaryReason": r.get("primaryReason")}
    out = []
    for l in lakes:
        lid = l["lakeId"]
        out.append({"lakeId": lid, "name": l["name"], "state": l["state"], "lat": l["lat"], "lon": l["lon"],
                    "reviewed": lid in rev,
                    "purposes": (["INDEPENDENT_TRUTH"] if lid in rev else ["BINDING"] + (["INDEPENDENT_TRUTH"] if lid in bindings else [])),
                    "bindingStatus": "REVIEWED" if lid in rev else ("CANDIDATE" if lid in bindings else "NONE"),
                    "bound": bindings.get(lid, []), "priorResearch": prior.get(lid)})
    inputs = {os.path.relpath(p, REPO) if p.startswith(REPO) else os.path.basename(p): sha256_file(p)
              for p in (directory, reviewed, generated, handwritten, excluded, held) if os.path.exists(p)}
    return {"lakes": out, "inputs": inputs, "reviewedCount": len(rev), "directoryCount": len(lakes)}


# ------------------------------------------------------------------------------------------------------------------ geometry
def _meters(lat0: float):
    ky = 111_320.0
    kx = 111_320.0 * math.cos(math.radians(lat0))
    return kx, ky


def haversine_m(lat1, lon1, lat2, lon2) -> float:
    r = 6_371_008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def polygons_of(geom: dict) -> list[list[list[list[float]]]]:
    """GeoJSON (Feature, Polygon or MultiPolygon) -> list of polygons, each a list of rings of [lon, lat]."""
    if geom.get("type") == "Feature":
        geom = geom["geometry"]
    if geom.get("type") == "FeatureCollection":
        return [p for f in geom["features"] for p in polygons_of(f)]
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return list(geom["coordinates"])
    raise ValueError(f"unsupported geometry {geom['type']}")


def _in_ring(x, y, ring) -> bool:
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-300) + x1:
            inside = not inside
    return inside


def point_in(polys, lon, lat) -> bool:
    for rings in polys:
        if rings and _in_ring(lon, lat, rings[0]) and not any(_in_ring(lon, lat, h) for h in rings[1:]):
            return True
    return False


def distance_to_outline_m(polys, lon, lat) -> float:
    """Shortest distance from the point to any ring edge, in a local equirectangular frame (good to < 1% at lake scale)."""
    kx, ky = _meters(lat)
    best = float("inf")
    for rings in polys:
        for ring in rings:
            for i in range(len(ring) - 1):
                ax, ay = (ring[i][0] - lon) * kx, (ring[i][1] - lat) * ky
                bx, by = (ring[i + 1][0] - lon) * kx, (ring[i + 1][1] - lat) * ky
                dx, dy = bx - ax, by - ay
                L = dx * dx + dy * dy
                t = 0.0 if L == 0 else max(0.0, min(1.0, -(ax * dx + ay * dy) / L))
                best = min(best, math.hypot(ax + t * dx, ay + t * dy))
    return best


def bbox_of(polys) -> list[float]:
    xs = [p[0] for rings in polys for ring in rings for p in ring]
    ys = [p[1] for rings in polys for ring in rings for p in ring]
    return [min(xs), min(ys), max(xs), max(ys)]


def expand_bbox(b, meters) -> list[float]:
    kx, ky = _meters((b[1] + b[3]) / 2)
    return [b[0] - meters / kx, b[1] - meters / ky, b[2] + meters / kx, b[3] + meters / ky]


def lake_key(lake_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", lake_id)


def position(lake: dict, lat: float, lon: float) -> dict:
    """Where a gauge sits relative to the lake: inside / distance to outline, else distance to the directory point."""
    d_point = haversine_m(lake["lat"], lake["lon"], lat, lon)
    polys = lake.get("_polys")
    if polys:
        inside = point_in(polys, lon, lat)
        return {"basis": "OUTLINE", "inside": inside, "distanceToOutlineM": 0 if inside else round(distance_to_outline_m(polys, lon, lat)),
                "distanceToPointM": round(d_point)}
    return {"basis": "POINT_ONLY", "inside": None, "distanceToOutlineM": None, "distanceToPointM": round(d_point)}


# ------------------------------------------------------------------------------------------------------------------ fetching
class Refused(Exception):
    pass


class Fetcher:
    """GET-only, host-allowlisted, robots-checked, rate-limited, budgeted. `transport(url, headers) -> (status, bytes)` is injectable."""

    def __init__(self, rules: dict, out: str | None = None, transport=None, sleep=time.sleep, clock=time.monotonic):
        self.rules = rules
        self.hosts = set(rules["hosts"])
        self.ua = rules["fetch"]["userAgent"]
        self.gap = float(rules["fetch"]["minSecondsBetweenRequestsPerHost"])
        self.budget = int(rules["fetch"]["maxRequests"])
        self.timeout = float(rules["fetch"]["timeoutSeconds"])
        self.transport = transport or self._urllib
        self.sleep, self.clock = sleep, clock
        self.last: dict[str, float] = {}
        self.robots: dict[str, dict] = {}
        self.count = 0
        self.log: list[dict] = []
        self.out = out
        self.cache = os.path.join(out, "cache") if out else None
        if self.cache:
            os.makedirs(self.cache, exist_ok=True)

    def _urllib(self, url: str, headers: dict) -> tuple[int, bytes]:
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                return r.status, body
        except urllib.error.HTTPError as e:
            return e.code, e.read() or b""

    def _wait(self, host: str):
        t = self.clock()
        if host in self.last and t - self.last[host] < self.gap:
            self.sleep(self.gap - (t - self.last[host]))
        self.last[host] = self.clock()

    def _raw(self, url: str, headers: dict) -> tuple[int, bytes]:
        host = urllib.parse.urlsplit(url).hostname
        if host not in self.hosts:
            raise Refused(f"host {host} is not allowlisted")
        if self.count >= self.budget:
            raise Refused(f"request budget {self.budget} exhausted")
        self._wait(host)
        self.count += 1
        status, body = 0, b""
        for attempt in range(3):
            try:
                status, body = self.transport(url, dict(headers, **{"User-Agent": self.ua}))
            except Exception as e:  # network failure: recorded, retried
                status, body = -1, str(e).encode()
            if status not in (-1, 429, 500, 502, 503, 504):
                break
            self.sleep(5 * (attempt + 1))
        self.log.append({"url": url, "status": status, "bytes": len(body), "sha256": sha256_bytes(body),
                         "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
        return status, body

    def robots_ok(self, url: str) -> bool:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname
        if host not in self.robots:
            status, body = self._raw(f"{parts.scheme}://{host}/robots.txt", {})
            rp = urllib.robotparser.RobotFileParser()
            if status == 200:
                rp.parse(body.decode("utf-8", "replace").splitlines())
                state = "PARSED"
            elif status in (401, 403):
                rp.disallow_all = True
                state = f"HTTP_{status}_DISALLOW_ALL"
            else:
                rp.allow_all = True
                state = f"HTTP_{status}_ALLOW_ALL" if status > 0 else "UNREACHABLE_ALLOW_ALL"
            self.robots[host] = {"parser": rp, "state": state, "sha256": sha256_bytes(body) if status == 200 else None, "disallowed": []}
        r = self.robots[host]
        ok = r["parser"].can_fetch(self.ua, url)
        if not ok and parts.path not in r["disallowed"]:
            r["disallowed"].append(parts.path)
        return ok

    def get(self, url: str, params: dict | None = None, accept: str | None = None, cache: bool = True) -> tuple[int, bytes]:
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, safe=",:^\\$")
        if not self.robots_ok(url):
            raise Refused(f"robots.txt disallows {url}")
        key = sha256_bytes((url + "|" + (accept or "")).encode())
        if cache and self.cache and os.path.exists(os.path.join(self.cache, key)):
            return 200, open(os.path.join(self.cache, key), "rb").read()
        status, body = self._raw(url, {"Accept": accept} if accept else {})
        if cache and self.cache and status == 200:
            open(os.path.join(self.cache, key), "wb").write(body)
        return status, body

    def robots_report(self) -> dict:
        return {h: {"state": r["state"], "sha256": r["sha256"], "disallowedPaths": r["disallowed"],
                    "terms": self.rules["hosts"].get(h, {}).get("terms")} for h, r in self.robots.items()}


# ------------------------------------------------------------------------------------------------------------------ parsers
def parse_rdb(text: str) -> list[dict]:
    lines = [l for l in text.splitlines() if l and not l.startswith("#")]
    if len(lines) < 2:
        return []
    head = lines[0].split("\t")
    return [dict(zip(head, l.split("\t"))) for l in lines[2:]]


def parse_usgs_site_catalog(text: str, params: set[str]) -> list[dict]:
    """WaterServices site service with seriesCatalogOutput=true -> one row per (site, parameter) with iv/dv extents."""
    by = {}
    for r in parse_rdb(text):
        if r.get("parm_cd") not in params:
            continue
        k = (r["site_no"], r["parm_cd"])
        e = by.setdefault(k, {"site": r["site_no"], "param": r["parm_cd"], "name": r.get("station_nm", ""), "siteType": r.get("site_tp_cd"),
                              "lat": _f(r.get("dec_lat_va")), "lon": _f(r.get("dec_long_va")), "altDatum": (r.get("alt_datum_cd") or "").strip() or None,
                              "agency": r.get("agency_cd"), "dataTypes": {}, "state": None})
        e["dataTypes"][r.get("data_type_cd")] = {"begin": r.get("begin_date"), "end": r.get("end_date"), "count": _i(r.get("count_nu"))}
    return list(by.values())


def parse_usgs_basic_sites(text: str) -> dict:
    return {r["site_no"]: {"lat": _f(r.get("dec_lat_va")), "lon": _f(r.get("dec_long_va")), "name": r.get("station_nm")} for r in parse_rdb(text)}


def parse_iv_timestamps(text: str) -> dict:
    """USGS IV JSON -> {(site, param): [timestamps]}. Every value is dropped here; only time stamps leave this function."""
    d = json.loads(text)
    out = {}
    for ts in d.get("value", {}).get("timeSeries", []):
        code = ts.get("sourceInfo", {}).get("siteCode", [{}])[0].get("value")
        param = ts.get("variable", {}).get("variableCode", [{}])[0].get("value")
        stamps = [v["dateTime"] for block in ts.get("values", []) for v in block.get("value", []) if v.get("dateTime")]
        out.setdefault((code, param), []).extend(stamps)
    return out


def parse_ogc_locations(text: str) -> list[dict]:
    d = json.loads(text)
    out = []
    for f in d.get("features", []):
        p = f.get("properties", {})
        lon, lat = (f.get("geometry") or {}).get("coordinates", [None, None])[:2]
        fid = str(f.get("id") or p.get("id") or "")
        out.append({"site": fid.split("-", 1)[1] if fid.startswith("USGS-") else fid, "ogcId": fid,
                    "name": p.get("monitoring_location_name", ""), "siteType": p.get("site_type_code"), "lat": lat, "lon": lon,
                    "altDatum": p.get("vertical_datum") or p.get("altitude_datum") or None, "agency": p.get("agency_code", "USGS")})
    return out


def parse_ogc_tsmeta(text: str, params: set[str]) -> list[dict]:
    d = json.loads(text)
    out = []
    for f in d.get("features", []):
        p = f.get("properties", {})
        if p.get("parameter_code") in params:
            out.append({"param": p["parameter_code"], "begin": p.get("begin"), "end": p.get("end"),
                        "period": p.get("computation_period_identifier"), "computation": p.get("computation_identifier")})
    return out


def parse_cwms_locations(text: str) -> tuple[list[dict], str | None]:
    d = json.loads(text)
    out = []
    for e in d.get("entries", []):
        lat = _f(e.get("latitude")) or _f(e.get("published-latitude"))
        lon = _f(e.get("longitude")) or _f(e.get("published-longitude"))
        out.append({"office": e.get("office"), "name": e.get("name"), "lat": lat, "lon": lon, "kind": e.get("kind") or e.get("location-kind"),
                    "publicName": e.get("public-name"), "longName": e.get("long-name"), "verticalDatum": e.get("vertical-datum"),
                    "state": e.get("state"), "aliases": [a.get("name") if isinstance(a, dict) else a for a in (e.get("aliases") or [])]})
    return out, d.get("next-page")


def parse_cwms_ts(text: str) -> tuple[list[dict], str | None]:
    d = json.loads(text)
    out = []
    for e in d.get("entries", []):
        ext = (e.get("extents") or [{}])
        latest = max((x.get("latest-time") for x in ext if x.get("latest-time")), default=None)
        earliest = min((x.get("earliest-time") for x in ext if x.get("earliest-time")), default=None)
        out.append({"office": e.get("office"), "tsid": e.get("name"), "interval": e.get("interval"), "units": e.get("units"),
                    "latest": latest, "earliest": earliest})
    return out, d.get("next-page")


def _jsonapi_rel_ids(obj: dict, pattern: str) -> list[str]:
    ids = []
    for k, v in (obj.get("relationships") or {}).items():
        if re.search(pattern, k, re.I):
            data = v.get("data") if isinstance(v, dict) else None
            for x in (data if isinstance(data, list) else [data] if data else []):
                if x and x.get("id") is not None:
                    ids.append(str(x["id"]))
    return ids


def _find_key(attrs: dict, pattern: str):
    for k, v in attrs.items():
        if re.search(pattern, k, re.I) and v not in (None, ""):
            return v
    return None


def parse_rise_locations(text: str) -> tuple[list[dict], str | None]:
    d = json.loads(text)
    out = []
    for o in d.get("data", []):
        a = o.get("attributes", {})
        coords = (a.get("locationCoordinates") or {}).get("coordinates") or [None, None]
        out.append({"id": str(o.get("id")), "name": a.get("locationName", ""), "lon": _f(coords[0]), "lat": _f(coords[1]),
                    "type": a.get("locationTypeName"), "verticalDatum": _find_key(a, r"vertical.?datum"),
                    "state": _find_key(a, r"^(locationStateName|stateName|state)$"),
                    "records": _jsonapi_rel_ids(o, r"catalog.?record"), "items": _jsonapi_rel_ids(o, r"catalog.?item")})
    nxt = (d.get("links") or {}).get("next")
    return out, nxt


def parse_rise_item(text: str) -> dict:
    d = json.loads(text)
    o = d.get("data", {})
    a = o.get("attributes", {})
    return {"id": str(o.get("id")), "title": a.get("itemTitle", ""), "parameter": a.get("parameterName", ""),
            "unit": a.get("parameterUnit"), "timestep": a.get("parameterTimestep"), "begin": a.get("temporalStartDate"),
            "end": a.get("temporalEndDate"), "verticalDatum": _find_key(a, r"vertical.?datum")}


def parse_rise_record_items(text: str) -> list[str]:
    return _jsonapi_rel_ids(json.loads(text).get("data", {}), r"catalog.?item")


def _f(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _i(x):
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def parse_time(s: str | None) -> dt.datetime | None:
    if not s:
        return None
    s = s.strip().replace("Z", "+00:00")
    for fmt in (None, "%Y-%m-%d"):
        try:
            t = dt.datetime.fromisoformat(s) if fmt is None else dt.datetime.strptime(s[:10], fmt)
            return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
    return None


# ------------------------------------------------------------------------------------------------------------------ classification
def _words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (s or "").lower())


def _has(text: str, words: list[str]) -> list[str]:
    low = " " + " ".join(_words(text)) + " "
    return [w for w in words if f" {w} " in low]


def classify(rules: dict, name: str, pos: dict, version: str = "", subparam: str = "", base_class: str | None = None) -> tuple[str, list[str]]:
    c = rules["classification"]
    why = []
    rc = _has(version, c["ruleCurveVersionWords"]) + _has(subparam, c["ruleCurveVersionWords"])
    if rc:
        return "RULE_CURVE", [f"rule/guide/forecast cue {rc}"]
    tail = _has(name, c["tailwaterWords"]) + _has(subparam, c["tailwaterWords"])
    pool = _has(name, c["poolWords"]) + _has(subparam, c["poolWords"])
    river = _has(name, c["riverWords"])
    near = pos["inside"] or (pos["distanceToOutlineM"] is not None and pos["distanceToOutlineM"] <= rules["selection"]["S3_position"]["insideOrWithinM"])
    if tail:
        return "TAILWATER", [f"tailwater cue {tail}"]
    if base_class == "POOL":
        why.append("parameter/kind is a reservoir surface")
    if pool:
        why.append(f"pool cue {pool}")
    if pos["basis"] == "OUTLINE":
        if not near:
            if river and not pool:
                return "RIVER", [f"outside the outline, river cue {river}"]
            if "dam" in _words(name):
                return "TAILWATER", ["dam-named station outside the outline"]
            return "UNKNOWN", ["outside the outline"] + why
        why.append("inside the outline" if pos["inside"] else f"{pos['distanceToOutlineM']} m from the outline")
    if pool or base_class == "POOL":
        if river and not pool:
            return "UNKNOWN", [f"river cue {river} on a reservoir-surface parameter"] + why
        return "POOL", why
    if river:
        return "RIVER" if pos["basis"] == "OUTLINE" and not near else "UNKNOWN", [f"river cue {river}"] + why
    return "UNKNOWN", why or ["no cue"]


def cwms_parts(tsid: str) -> dict:
    p = (tsid or "").split(".")
    loc = p[0] if p else ""
    param = p[1] if len(p) > 1 else ""
    base, _, sub = param.partition("-")
    return {"location": loc, "baseLocation": loc.split("-")[0], "subLocation": loc.partition("-")[2], "param": param,
            "baseParam": base, "subParam": sub, "interval": p[3] if len(p) > 3 else "", "version": p[5] if len(p) > 5 else ""}


def interval_minutes(s: str | None) -> int | None:
    if not s:
        return None
    s = s.lstrip("~")
    m = re.match(r"(\d+)(Minute|Minutes|Hour|Hours|Day|Days|Week|Month)", s)
    if not m:
        return None
    n, u = int(m.group(1)), m.group(2)
    return n * {"Minute": 1, "Minutes": 1, "Hour": 60, "Hours": 60, "Day": 1440, "Days": 1440, "Week": 10080, "Month": 43200}[u]


def rise_minutes(s: str | None) -> int | None:
    s = (s or "").lower()
    for k, v in (("15", 15), ("hour", 60), ("dai", 1440), ("day", 1440), ("month", 43200)):
        if k in s:
            return v
    return None


def cadence_from(stamps: list[str]) -> int | None:
    ts = sorted(t for t in (parse_time(s) for s in stamps) if t)
    diffs = [(b - a).total_seconds() / 60 for a, b in zip(ts, ts[1:]) if b > a]
    return int(round(statistics.median(diffs))) if diffs else None


# ------------------------------------------------------------------------------------------------------------------ discovery
class Census:
    def __init__(self, rules: dict, fetcher: Fetcher, now: dt.datetime, usgs_api: str = "auto"):
        self.r, self.f, self.now = rules, fetcher, now
        self.params = set(rules["usgs"]["parameters"])
        self.usgs_api = usgs_api
        self.errors: list[dict] = []
        self.disabled: dict[str, str] = {}
        self._cwms_locs: dict[str, list[dict]] = {}
        self._rise_locs: list[dict] | None = None
        self._usgs_coords: dict[str, dict] = {}

    # ---- geometry
    def load_geometry(self, lakes: list[dict], registry: str | None):
        if not registry:
            return
        idx = self._registry_json("registry/lakes.v1.json", registry)
        entries = {e["lakeId"]: e for e in (idx.get("lakes") if isinstance(idx, dict) else idx) or []}
        for lake in lakes:
            e = entries.get(lake["lakeId"])
            if not e or not e.get("geometry"):
                continue
            try:
                g = self._registry_json(f"lakes/{lake_key(lake['lakeId'])}/geometry.v1.analysis.geojson.gz", registry)
                lake["_polys"] = polygons_of(g)
            except Exception as ex:  # recorded; the lake falls back to POINT_ONLY
                self.errors.append({"lakeId": lake["lakeId"], "stage": "geometry", "error": str(ex)[:200]})

    def _registry_json(self, rel: str, registry: str):
        if registry.startswith("http"):
            status, body = self.f.get(f"{registry.rstrip('/')}/{rel}")
            if status != 200:
                raise RuntimeError(f"registry {rel}: HTTP {status}")
        else:
            body = open(os.path.join(registry, rel), "rb").read()
        if body[:2] == b"\x1f\x8b":
            body = gzip.decompress(body)
        return json.loads(body)

    def search_box(self, lake: dict) -> list[float]:
        if lake.get("_polys"):
            return expand_bbox(bbox_of(lake["_polys"]), self.r["selection"]["S3_position"]["insideOrWithinM"])
        return expand_bbox([lake["lon"], lake["lat"], lake["lon"], lake["lat"]], 5000)

    # ---- USGS
    def usgs(self, lake: dict) -> list[dict]:
        w, s, e, n = self.search_box(lake)
        if (e - w) * (n - s) > 25:
            self.errors.append({"lakeId": lake["lakeId"], "stage": "usgs", "error": "search box > 25 deg2 (USGS bBox limit)"})
            return []
        rows = None
        if self.usgs_api in ("auto", "waterservices"):
            status, body = self.f.get(USGS_SITE, {"format": "rdb", "bBox": f"{w:.6f},{s:.6f},{e:.6f},{n:.6f}",
                                                  "parameterCd": ",".join(sorted(self.params)), "siteStatus": "all",
                                                  "seriesCatalogOutput": "true"})
            if status == 200:
                rows = parse_usgs_site_catalog(body.decode("utf-8", "replace"), self.params)
            elif status == 404:
                rows = []  # WaterServices answers 404 for "no sites found"
            elif self.usgs_api == "waterservices":
                raise RuntimeError(f"usgs site service HTTP {status}")
        if rows is None:
            rows = self._usgs_ogc((w, s, e, n))
        out = []
        for r in rows:
            if r["lat"] is None:
                continue
            pos = position(lake, r["lat"], r["lon"])
            cls, why = classify(self.r, r["name"], pos, base_class="POOL" if r.get("siteType") in ("LK", "ES") or r["param"] in self.params else None)
            latest = max((parse_time(x.get("end")) for x in r["dataTypes"].values() if x.get("end")), default=None)
            begin = min((x.get("begin") for x in r["dataTypes"].values() if x.get("begin")), default=None)
            datum = self.r["usgs"]["parameterDatum"].get(r["param"])
            if datum == "SITE_DATUM":
                datum = r.get("altDatum")
            out.append({"provider": "usgs", "agency": "USGS", "station": r["site"], "series": r["param"], "name": r["name"],
                        "lat": r["lat"], "lon": r["lon"], "position": pos, "class": cls, "classWhy": why,
                        "cadenceMin": None, "latest": latest.isoformat() if latest else None, "latestBasis": "catalog end date",
                        "begin": begin, "datum": datum, "ivAvailable": "uv" in r["dataTypes"] or "iv" in r["dataTypes"],
                        "host": "waterservices.usgs.gov" if r.get("dataTypes") and not r.get("ogc") else "api.waterdata.usgs.gov",
                        "capabilityIfBound": self.r["selection"]["S8_capability"]["usgs"], "origin": "USGS"})
        return out

    def _usgs_ogc(self, box) -> list[dict]:
        w, s, e, n = box
        status, body = self.f.get(USGS_OGC.format(c="monitoring-locations"), {"bbox": f"{w:.6f},{s:.6f},{e:.6f},{n:.6f}", "f": "json", "limit": 500})
        if status != 200:
            raise RuntimeError(f"usgs ogc monitoring-locations HTTP {status}")
        rows = []
        for loc in parse_ogc_locations(body.decode()):
            st, b2 = self.f.get(USGS_OGC.format(c="time-series-metadata"), {"monitoring_location_id": loc["ogcId"], "f": "json", "limit": 200})
            if st != 200:
                continue
            for m in parse_ogc_tsmeta(b2.decode(), self.params):
                key = "uv" if (m.get("period") or "").lower() in ("points", "instantaneous") else "dv"
                ex = next((r for r in rows if r["site"] == loc["site"] and r["param"] == m["param"]), None)
                if not ex:
                    ex = dict(loc, param=m["param"], dataTypes={}, ogc=True)
                    rows.append(ex)
                ex["dataTypes"][key] = {"begin": m["begin"], "end": m["end"], "count": None}
        return rows

    def usgs_iv_timestamps(self, cands: list[dict]):
        """Last 12 h of IV time stamps for shortlisted USGS pool candidates (values dropped at parse time)."""
        todo = [c for c in cands if c["provider"] == "usgs" and c["class"] == "POOL" and c.get("ivAvailable")]
        for i in range(0, len(todo), 50):
            chunk = todo[i:i + 50]
            st, body = self.f.get(USGS_IV, {"format": "json", "sites": ",".join(sorted({c["station"] for c in chunk})),
                                            "parameterCd": ",".join(sorted({c["series"] for c in chunk})), "period": "PT12H",
                                            "siteStatus": "all"}, cache=False)
            if st != 200:
                self.errors.append({"stage": "usgs-iv", "error": f"HTTP {st}", "sites": [c["station"] for c in chunk]})
                continue
            stamps = parse_iv_timestamps(body.decode())
            del body
            for c in chunk:
                s = stamps.get((c["station"], c["series"])) or []
                if s:
                    c["cadenceMin"] = cadence_from(s)
                    c["latest"] = max(parse_time(x) for x in s).isoformat()
                    c["latestBasis"] = "IV time stamps, last 12 h (values discarded)"

    def usgs_coords(self, sites: list[str]) -> dict:
        need = sorted({s for s in sites if s and s not in self._usgs_coords})
        for i in range(0, len(need), 100):
            st, body = self.f.get(USGS_SITE, {"format": "rdb", "sites": ",".join(need[i:i + 100]), "siteStatus": "all"})
            if st == 200:
                self._usgs_coords.update(parse_usgs_basic_sites(body.decode("utf-8", "replace")))
        return self._usgs_coords

    # ---- CWMS
    def cwms_locations(self, office: str) -> list[dict]:
        if office not in self._cwms_locs:
            locs, page = [], None
            for _ in range(50):
                p = {"office": office, "page-size": 5000}
                if page:
                    p["page"] = page
                st, body = self.f.get(CWMS.format(kind="LOCATIONS"), p, accept=CWMS_ACCEPT)
                if st != 200:
                    self.errors.append({"stage": "cwms-locations", "office": office, "error": f"HTTP {st}"})
                    break
                got, page = parse_cwms_locations(body.decode())
                locs += got
                if not page or not got:
                    break
            self._cwms_locs[office] = locs
        return self._cwms_locs[office]

    def cwms(self, lake: dict) -> list[dict]:
        w, s, e, n = self.search_box(lake)
        out = []
        for office in self.r["cwms"]["offices"]:
            for loc in self.cwms_locations(office):
                if loc["lat"] is None or loc["lon"] is None or not (w <= loc["lon"] <= e and s <= loc["lat"] <= n):
                    continue
                pos = position(lake, loc["lat"], loc["lon"])
                like = "^" + re.escape(loc["name"]) + r"\.Elev"
                page = None
                for _ in range(10):
                    p = {"office": office, "like": like, "include-extents": "true", "page-size": 500}
                    if page:
                        p["page"] = page
                    st, body = self.f.get(CWMS.format(kind="TIMESERIES"), p, accept=CWMS_ACCEPT)
                    if st != 200:
                        self.errors.append({"lakeId": lake["lakeId"], "stage": "cwms-ts", "location": loc["name"], "error": f"HTTP {st}"})
                        break
                    rows, page = parse_cwms_ts(body.decode())
                    for t in rows:
                        cp = cwms_parts(t["tsid"])
                        if cp["baseParam"] != "Elev" or cp["location"] != loc["name"]:
                            continue
                        name = " ".join(filter(None, [loc["name"].replace("-", " "), loc.get("publicName"), loc.get("longName"), cp["subLocation"]]))
                        base = "POOL" if (loc.get("kind") or "").upper() in ("PROJECT", "EMBANKMENT", "LOCK") and not cp["subLocation"] else None
                        cls, why = classify(self.r, name, pos, version=cp["version"], subparam=cp["subParam"], base_class=base)
                        origin = self.cwms_origin(cp["version"])
                        out.append({"provider": "cwms", "agency": "USACE", "station": office, "series": t["tsid"], "location": loc["name"],
                                    "name": loc.get("publicName") or loc.get("longName") or loc["name"], "lat": loc["lat"], "lon": loc["lon"],
                                    "position": pos, "class": cls, "classWhy": why, "cadenceMin": interval_minutes(cp["interval"]),
                                    "latest": t["latest"], "latestBasis": "CDA catalog extent latest-time", "begin": t["earliest"],
                                    "datum": loc.get("verticalDatum"), "aliases": loc.get("aliases"), "host": "cwms-data.usace.army.mil",
                                    "capabilityIfBound": self.r["selection"]["S8_capability"]["cwms"], "origin": origin})
                    if not page or not rows:
                        break
        return out

    def cwms_origin(self, version: str) -> str:
        return cwms_origin(self.r, version)

    # ---- RISE
    def rise_locations(self) -> list[dict]:
        if self._rise_locs is None:
            locs, url, params = [], RISE.format(path="location"), {"itemsPerPage": 100, "page": 1}
            for page in range(1, 400):
                params["page"] = page
                st, body = self.f.get(url, params, accept=RISE_ACCEPT)
                if st != 200:
                    self.errors.append({"stage": "rise-locations", "error": f"HTTP {st}", "page": page})
                    break
                got, nxt = parse_rise_locations(body.decode())
                locs += got
                if not got or not nxt:
                    break
            self._rise_locs = locs
        return self._rise_locs

    def rise(self, lake: dict) -> list[dict]:
        w, s, e, n = self.search_box(lake)
        out = []
        for loc in self.rise_locations():
            if loc["lat"] is None or not (w <= loc["lon"] <= e and s <= loc["lat"] <= n):
                continue
            pos = position(lake, loc["lat"], loc["lon"])
            items = list(loc["items"])
            if not items:
                st, body = self.f.get(RISE.format(path=f"location/{loc['id']}"), accept=RISE_ACCEPT)
                if st == 200:
                    one, _ = parse_rise_locations(json.dumps({"data": [json.loads(body).get("data", {})]}))
                    items, recs = (one[0]["items"], one[0]["records"]) if one else ([], [])
                    for rec in recs:
                        st2, b2 = self.f.get(RISE.format(path=f"catalog-record/{rec}"), accept=RISE_ACCEPT)
                        if st2 == 200:
                            items += parse_rise_record_items(b2.decode())
            for iid in items:
                st, body = self.f.get(RISE.format(path=f"catalog-item/{iid}"), accept=RISE_ACCEPT)
                if st != 200:
                    continue
                it = parse_rise_item(body.decode())
                text = f"{it['title']} {it['parameter']}"
                if "elevation" not in text.lower():
                    continue
                base = "POOL" if re.search(r"lake/reservoir elevation|reservoir elevation|lake elevation|pool elevation", text, re.I) else None
                cls, why = classify(self.r, f"{loc['name']} {text}", pos, base_class=base)
                out.append({"provider": "rise", "agency": "USBR", "station": iid, "series": iid, "location": loc["id"], "name": it["title"] or loc["name"],
                            "lat": loc["lat"], "lon": loc["lon"], "position": pos, "class": cls, "classWhy": why,
                            "cadenceMin": rise_minutes(it["timestep"]), "latest": it["end"], "latestBasis": "RISE catalog temporalEndDate",
                            "begin": it["begin"], "datum": it["verticalDatum"] or loc["verticalDatum"], "host": "data.usbr.gov",
                            "capabilityIfBound": self.r["selection"]["S8_capability"]["rise"], "origin": "USBR"})
        return out

    # ---- per lake
    def discover(self, lake: dict) -> list[dict]:
        cands = []
        for prov, fn in (("usgs", self.usgs), ("cwms", self.cwms), ("rise", self.rise)):
            if prov in self.disabled:
                continue
            try:
                cands += fn(lake)
            except Refused as ex:
                self.errors.append({"lakeId": lake["lakeId"], "stage": prov, "error": f"REFUSED {ex}"})
            except Exception as ex:
                self.errors.append({"lakeId": lake["lakeId"], "stage": prov, "error": str(ex)[:300]})
        return cands


# ------------------------------------------------------------------------------------------------------------------ verdicts
def cwms_origin(rules: dict, version: str) -> str:
    """Origin agency of a CWMS series from its version: a USGS copy, an NWS redistribution, or USACE's own."""
    c = rules["classification"]
    if _has(version, c["usgsCopyVersionWords"]):
        return "USGS_COPY"
    if _has(version, c["nwsRedistributionVersionWords"]):
        return "NWS_REDISTRIBUTION"
    return "USACE"


def series_key(provider: str, station, series) -> tuple:
    if provider in ("cwms", "a2w"):
        return ("cwms", series)
    if provider == "usgs":
        return ("usgs", station, series)
    if provider == "rise":
        return ("rise", str(series or station))
    return (provider, station, series)


def bound_origin(rules: dict, ref: dict) -> str:
    p = ref["provider"]
    if p in ("cwms", "a2w"):
        return cwms_origin(rules, cwms_parts(ref.get("series") or "")["version"])
    return {"usgs": "USGS", "rise": "USBR", "tva": "TVA", "nwps": "NWS_REDISTRIBUTION", "hads": "NWS_REDISTRIBUTION"}.get(p, p.upper())


def age_hours(c: dict, now: dt.datetime) -> float | None:
    t = parse_time(c.get("latest"))
    return round((now - t).total_seconds() / 3600, 1) if t else None


def live_ok(rules: dict, c: dict, now: dt.datetime) -> bool | None:
    a = age_hours(c, now)
    if a is None:
        return None
    s4 = rules["selection"]["S4_live"]
    daily = (c.get("cadenceMin") or 0) >= s4["dailyCadenceMinAtLeast"] or c.get("latestBasis") == "catalog end date"
    return a <= (s4["maxAgeHoursDaily"] if daily else s4["maxAgeHours"])


def within_r1(rules: dict, pos: dict) -> bool | None:
    lim = rules["selection"]["S3_position"]["insideOrWithinM"]
    if pos["basis"] == "OUTLINE":
        return bool(pos["inside"] or pos["distanceToOutlineM"] <= lim)
    return None


def independence(rules: dict, c: dict, bound: list[dict], coords: dict) -> dict:
    """Evidence that a candidate is not the lake's bound series or the same gauge (metadata only)."""
    ind = rules["independence"]
    same_m, other_m = ind["sameGaugeDistanceM"], ind["otherSiteMinDistanceM"]
    origin = c["origin"]
    reasons, dists = [], []
    b_origins = sorted({bound_origin(rules, b) for b in bound})
    unknown_loc = []
    for b in bound:
        loc = coords.get((b["provider"], b.get("station"), b.get("series")))
        if loc:
            dists.append(round(haversine_m(c["lat"], c["lon"], loc[0], loc[1])))
        else:
            unknown_loc.append(f"{b['provider']}:{b.get('station')}")
    ev = {"originAgency": origin, "boundOriginAgencies": b_origins, "minDistanceToBoundGaugeM": min(dists) if dists else None,
          "boundGaugesWithUnknownLocation": unknown_loc}
    if origin == "NWS_REDISTRIBUTION":
        return dict(ev, tier="NOT_INDEPENDENT", reasons=["NWS redistribution"])
    if c["provider"] == "usgs" and any(b["provider"] == "usgs" and b.get("station") == c["station"] for b in bound):
        return dict(ev, tier="NOT_INDEPENDENT", reasons=["same USGS site as a bound series (other parameter or endpoint)"])
    if c["provider"] == "cwms":
        locs = {cwms_parts(b.get("series") or "")["location"] for b in bound if b["provider"] in ("cwms", "a2w")}
        if c.get("location") in locs:
            return dict(ev, tier="NOT_INDEPENDENT", reasons=["same CWMS location as a bound series (other version or interval)"])
        if origin == "USGS_COPY" and any(bound_origin(rules, b) in ("USGS", "USGS_COPY") for b in bound):
            return dict(ev, tier="NOT_INDEPENDENT", reasons=["CWMS copy of a USGS gauge and the lake has a bound USGS series"])
        if origin == "USGS_COPY":
            reasons.append("CWMS copy of an unidentified USGS gauge")
    if c["provider"] == "usgs" and any(bound_origin(rules, b) == "USGS_COPY" for b in bound):
        reasons.append("a bound CWMS series is a USGS copy; its USGS site is not named")
    if dists and min(dists) < same_m and (origin in b_origins or (origin == "USGS" and "USGS_COPY" in b_origins)):
        return dict(ev, tier="NOT_INDEPENDENT", reasons=[f"same agency within {same_m} m of a bound gauge"])
    if reasons:
        return dict(ev, tier="UNCERTAIN", reasons=reasons)
    if unknown_loc:
        return dict(ev, tier="UNCERTAIN", reasons=["a bound gauge's location is unknown: " + ", ".join(unknown_loc)])
    if origin not in b_origins and (not dists or min(dists) >= same_m):
        return dict(ev, tier="INDEPENDENT_AGENCY", reasons=[f"origin {origin} differs from {b_origins}"])
    if origin in b_origins and dists and min(dists) >= other_m:
        return dict(ev, tier="INDEPENDENT_SITE", reasons=[f"same agency, different site {min(dists)} m from the nearest bound gauge"])
    return dict(ev, tier="UNCERTAIN", reasons=["closer than the other-site distance or different agency within the same-gauge distance"])


def selection(rules: dict, c: dict, now: dt.datetime, robots_ok: bool) -> tuple[str, list[str]]:
    why = []
    if c["class"] in ("TAILWATER", "RIVER", "RULE_CURVE"):
        return "REJECT", [f"S2 class {c['class']}"]
    if not robots_ok:
        return "REJECT", ["S6 robots disallow the host path"]
    r1 = within_r1(rules, c["position"])
    if r1 is False:
        return "REJECT", ["S3 outside 1.5 km of the outline"]
    verdict = "SHORTLIST"
    if c["class"] == "UNKNOWN":
        verdict, why = "HAND_REVIEW", why + ["S2 class UNKNOWN"]
    if r1 is None:
        verdict, why = "HAND_REVIEW", why + ["S3 point-only lake (no outline)"]
    lo = live_ok(rules, c, now)
    if lo is False:
        return "REJECT", why + [f"S4 not live (age {age_hours(c, now)} h)"]
    if lo is None:
        verdict, why = "HAND_REVIEW", why + ["S4 latest time unknown"]
    if not c.get("datum"):
        verdict, why = "HAND_REVIEW", why + ["S5 no datum named"]
    return verdict, why


def order_key(c: dict):
    p = c["position"]
    return (0 if c["capabilityIfBound"] == "DIRECT_OPERATOR_POOL" else 1, 0 if p.get("inside") else 1,
            p["distanceToOutlineM"] if p["distanceToOutlineM"] is not None else p["distanceToPointM"], c.get("begin") or "9999")


def finalize(rules: dict, targets: list[dict], found: dict[str, list[dict]], coords: dict, now: dt.datetime, robots: dict) -> list[dict]:
    """Per-lake verdicts: S7 uniqueness across lakes, the BINDING shortlist and the INDEPENDENT_TRUTH evidence."""
    claimed = {}
    for t in targets:
        if t["reviewed"]:
            for b in t["bound"]:
                claimed[series_key(b["provider"], b.get("station"), b.get("series"))] = t["lakeId"]
    best: dict[tuple, tuple] = {}
    for lid, cands in found.items():
        for c in cands:
            k = series_key(c["provider"], c["station"], c["series"])
            p = c["position"]
            score = (0 if p.get("inside") else 1, p["distanceToOutlineM"] if p["distanceToOutlineM"] is not None else p["distanceToPointM"])
            if k not in best or score < best[k][0]:
                best[k] = (score, lid)
    out = []
    for t in targets:
        lid = t["lakeId"]
        bound_keys = {series_key(b["provider"], b.get("station"), b.get("series")) for b in t["bound"]}
        rows = []
        for c in found.get(lid, []):
            k = series_key(c["provider"], c["station"], c["series"])
            c = dict(c, ageHours=age_hours(c, now), liveByS4=live_ok(rules, c, now))
            if k in bound_keys:
                c["boundToThisLake"] = True
                rows.append(c)
                continue
            robots_ok = c["host"] not in robots or not robots[c["host"]]["disallowedPaths"]
            if "BINDING" in t["purposes"]:
                v, why = selection(rules, c, now, robots_ok)
                other = claimed.get(k)
                if other and other != lid:
                    v, why = "REJECT", [f"S7 bound by reviewed lake {other}"]
                elif best.get(k, (None, lid))[1] != lid and v != "REJECT":
                    v, why = "REJECT", [f"S7 {best[k][1]} has this station inside or nearer"]
                c["selection"] = {"verdict": v, "reasons": why}
            if t["bound"]:
                c["independence"] = independence(rules, c, t["bound"], coords)
                c["eligibleForV3"] = (c["independence"]["tier"] in ("INDEPENDENT_AGENCY", "INDEPENDENT_SITE") and c["class"] == "POOL"
                                      and within_r1(rules, c["position"]) is True and c["liveByS4"] is True)
            rows.append(c)
        rows.sort(key=order_key)
        shortlisted = [c for c in rows if (c.get("selection") or {}).get("verdict") == "SHORTLIST"]
        out.append({k2: v2 for k2, v2 in t.items() if not k2.startswith("_")} | {
            "geometryBasis": "OUTLINE" if t.get("_polys") else "POINT_ONLY",
            "candidates": rows,
            "bestShortlist": ({"provider": shortlisted[0]["provider"], "station": shortlisted[0]["station"], "series": shortlisted[0]["series"],
                               "capability": shortlisted[0]["capabilityIfBound"]} if shortlisted else None)})
    return out


def summarize(rules: dict, lakes: list[dict]) -> dict:
    cov = rules["coverageArithmetic"]
    binding = [l for l in lakes if "BINDING" in l["purposes"]]
    sel = lambda l, v: any((c.get("selection") or {}).get("verdict") == v for c in l["candidates"])
    with_short = [l for l in binding if sel(l, "SHORTLIST")]
    hand_only = [l for l in binding if not sel(l, "SHORTLIST") and sel(l, "HAND_REVIEW")]
    by_cap = {}
    for l in with_short:
        by_cap[l["bestShortlist"]["capability"]] = by_cap.get(l["bestShortlist"]["capability"], 0) + 1
    truth = [l for l in lakes if l["bound"]]
    tiers = {}
    for l in truth:
        for c in l["candidates"]:
            if c.get("independence"):
                tiers[c["independence"]["tier"]] = tiers.get(c["independence"]["tier"], 0) + 1
    v3 = [l["lakeId"] for l in truth if any(c.get("eligibleForV3") for c in l["candidates"])]
    v3_reviewed = [l["lakeId"] for l in truth if l["reviewed"] and any(c.get("eligibleForV3") for c in l["candidates"])]
    ceiling = cov["reviewedAtRegistration"] + len(with_short)
    tva = {}
    for l in lakes:  # TVA reservoirs: USGS gauges are the TVA-robots-free alternative (reporting only; selection is unchanged)
        if any(b["provider"] == "tva" for b in l["bound"]) or l["lakeId"] in TVA_UNBOUND:
            tva[l["lakeId"]] = [{"station": c["station"], "series": c["series"], "class": c["class"],
                                 "selection": (c.get("selection") or {}).get("verdict"),
                                 "independence": (c.get("independence") or {}).get("tier"), "eligibleForV3": c.get("eligibleForV3")}
                                for c in l["candidates"] if c["provider"] == "usgs" and not c.get("boundToThisLake")]
    return {
        "binding": {"lakes": len(binding), "withShortlist": len(with_short), "shortlistByCapability": by_cap,
                    "handReviewOnly": len(hand_only), "noCandidate": len(binding) - len(with_short) - len(hand_only),
                    "reviewedAtRegistration": cov["reviewedAtRegistration"], "ceilingIfAllShortlistPassStageB": ceiling,
                    "ceilingShare": round(ceiling / cov["directoryLakeCount"], 4), "target": cov["targetReviewed"],
                    "targetReachableOnShortlist": ceiling >= cov["targetReviewed"],
                    "note": "a ceiling, not a result: every shortlisted lake still faces the stage B review (R1-R9, checks b-d, 15 ft rule)"},
        "independentTruth": {"lakesWithBinding": len(truth), "candidateTiers": tiers, "lakesWithV3Eligible": len(v3),
                             "reviewedLakesWithV3Eligible": len(v3_reviewed), "v3EligibleLakeIds": sorted(v3)},
        "tvaReservoirsUsgs": tva,
        "geometry": {"outline": sum(1 for l in lakes if l["geometryBasis"] == "OUTLINE"),
                     "pointOnly": sum(1 for l in lakes if l["geometryBasis"] == "POINT_ONLY")},
    }


# ------------------------------------------------------------------------------------------------------------------ controls
CONTROLS = [  # positive controls: reviewed lakes whose bound series the discovery must find again (from the committed bindings)
    {"lakeId": "Allegheny Reservoir|PA", "provider": "usgs", "key": ("usgs", "03012520", "62615")},
    {"lakeId": "Allegheny Reservoir|PA", "provider": "cwms", "key": ("cwms", "Kinzua-Lake.Elev.Inst.1Hour.0.RESOPS")},
    {"lakeId": "Bluestone Lake|WV", "provider": "usgs", "key": ("usgs", "03179800", "62614")},
    {"lakeId": "Bluestone Lake|WV", "provider": "cwms", "key": ("cwms", "Bluestone-Lake.Elev.Inst.15Minutes.0.OBS")},
    {"lakeId": "Alcova Reservoir|WY", "provider": "rise", "key": ("rise", "114")},
]


def run_controls(census: Census, targets: dict[str, dict]) -> dict:
    res = {}
    for ctl in CONTROLS:
        lake = targets.get(ctl["lakeId"])
        if lake is None:
            res.setdefault(ctl["provider"], []).append({"control": ctl["lakeId"], "found": False, "why": "lake not in directory"})
            continue
        fn = {"usgs": census.usgs, "cwms": census.cwms, "rise": census.rise}[ctl["provider"]]
        try:
            got = fn(lake)
        except Exception as ex:
            got, err = [], str(ex)[:200]
        else:
            err = None
        hit = [c for c in got if series_key(c["provider"], c["station"], c["series"]) == tuple(ctl["key"])]
        res.setdefault(ctl["provider"], []).append({"control": ctl["lakeId"], "key": list(ctl["key"]), "found": bool(hit),
                                                    "class": hit[0]["class"] if hit else None, "error": err})
    for prov, rows in res.items():
        if not all(r["found"] and r["class"] in ("POOL", "UNKNOWN") for r in rows):
            census.disabled[prov] = "positive control not rediscovered"
    return {"results": res, "disabledProviders": dict(census.disabled)}


# ------------------------------------------------------------------------------------------------------------------ run
def bound_coords(census: Census, targets: list[dict]) -> dict:
    coords = {}
    sites = [b["station"] for t in targets for b in t["bound"] if b["provider"] == "usgs"]
    if "usgs" not in census.disabled:
        try:
            known = census.usgs_coords(sites)
        except Exception as ex:
            census.errors.append({"stage": "bound-usgs-coords", "error": str(ex)[:200]})
            known = {}
        for t in targets:
            for b in t["bound"]:
                if b["provider"] == "usgs" and b["station"] in known and known[b["station"]]["lat"] is not None:
                    coords[(b["provider"], b["station"], b.get("series"))] = (known[b["station"]]["lat"], known[b["station"]]["lon"])
    for t in targets:
        for b in t["bound"]:
            if b["provider"] in ("cwms", "a2w") and "cwms" not in census.disabled:
                office = (b.get("station") or "").split(":")[0]
                loc = cwms_parts(b.get("series") or "")["location"]
                if office in census.r["cwms"]["offices"]:
                    m = next((l for l in census.cwms_locations(office) if l["name"] == loc and l["lat"] is not None), None)
                    if m:
                        coords[(b["provider"], b.get("station"), b.get("series"))] = (m["lat"], m["lon"])
    return coords


def run_census(rules: dict, digest: str, fetcher: Fetcher, now: dt.datetime, registry: str | None, only: list[str] | None = None,
               usgs_api: str = "auto", skip_controls: bool = False, targets_table: dict | None = None) -> dict:
    nb = dt.datetime.fromisoformat(rules["notBefore"]).replace(tzinfo=dt.timezone.utc)
    if now < nb:
        raise SystemExit(f"REFUSED: the census may not run before {rules['notBefore']} ({rules['notBeforeReason']})")
    tt = targets_table or load_targets()
    targets = [dict(t) for t in tt["lakes"] if not only or t["lakeId"] in only]
    census = Census(rules, fetcher, now, usgs_api)
    census.load_geometry(targets, registry)
    if skip_controls:
        controls = {"skipped": True}
    else:
        ctl_ids = {c["lakeId"] for c in CONTROLS}
        ctl = {t["lakeId"]: t for t in targets if t["lakeId"] in ctl_ids}
        extra = [dict(t) for t in tt["lakes"] if t["lakeId"] in ctl_ids and t["lakeId"] not in ctl]
        census.load_geometry(extra, registry)
        ctl.update({t["lakeId"]: t for t in extra})
        controls = run_controls(census, ctl)
    found = {}
    for i, t in enumerate(targets):
        found[t["lakeId"]] = census.discover(t)
        if i % 25 == 0:
            print(f"  {i + 1}/{len(targets)} {t['lakeId']}: {len(found[t['lakeId']])} candidates, {fetcher.count} requests", file=sys.stderr)
    if "usgs" not in census.disabled:
        census.usgs_iv_timestamps([c for cs in found.values() for c in cs])
    coords = bound_coords(census, targets)
    lakes = finalize(rules, targets, found, coords, now, fetcher.robots_report())
    return {"schema": "sector-lake-gauge-census-v1", "labels": LABELS, "rulesId": rules["rulesId"], "rulesSha256": digest,
            "generatedAt": now.isoformat(timespec="seconds"), "inputs": tt["inputs"], "usgsApi": usgs_api,
            "controls": controls, "disabledProviders": dict(census.disabled), "requests": fetcher.count,
            "robots": fetcher.robots_report(), "errors": census.errors, "summary": summarize(rules, lakes), "lakes": lakes,
            "valuesRead": "none (USGS IV time stamps only; values dropped at parse time)"}


def write_outputs(out: str, result: dict, fetcher: Fetcher):
    os.makedirs(out, exist_ok=True)
    files = {"census.json": result, "census.summary.json": {k: result[k] for k in
             ("schema", "labels", "rulesId", "rulesSha256", "generatedAt", "inputs", "controls", "disabledProviders", "requests", "summary")},
             "robots.json": result["robots"]}
    shas = {}
    for name, obj in files.items():
        b = json.dumps(obj, indent=1, sort_keys=False, default=str).encode()
        open(os.path.join(out, name), "wb").write(b)
        shas[name] = sha256_bytes(b)
    with open(os.path.join(out, "requests.jsonl"), "w", encoding="utf-8") as fh:
        for r in fetcher.log:
            fh.write(json.dumps(r) + "\n")
    shas["requests.jsonl"] = sha256_file(os.path.join(out, "requests.jsonl"))
    return shas


def summary_text(s: dict) -> str:
    b, it = s["summary"]["binding"], s["summary"]["independentTruth"]
    lines = [f"Lake gauge census {s['rulesId']} (rules sha256 {s['rulesSha256'][:12]}), {s['generatedAt']}, {s['requests']} GET requests, metadata only",
             f"Controls: {json.dumps({k: [r['found'] for r in v] for k, v in s['controls'].get('results', {}).items()})}; disabled: {s['disabledProviders'] or 'none'}",
             f"BINDING: {b['lakes']} unprofiled lakes; shortlist {b['withShortlist']} ({b['shortlistByCapability']}), hand review only {b['handReviewOnly']}, none {b['noCandidate']}",
             f"  ceiling if every shortlisted lake passes stage B: {b['ceilingIfAllShortlistPassStageB']}/621 ({b['ceilingShare']:.1%}); target {b['target']} reachable on the shortlist: {b['targetReachableOnShortlist']}",
             f"INDEPENDENT_TRUTH: {it['lakesWithBinding']} bound lakes; candidate tiers {it['candidateTiers']}; lakes with a v3-eligible candidate {it['lakesWithV3Eligible']} (reviewed {it['reviewedLakesWithV3Eligible']})",
             f"TVA reservoirs, USGS candidates (lakes with any / with a v3-eligible one): "
             f"{sum(1 for v in s['summary']['tvaReservoirsUsgs'].values() if v)}/{len(s['summary']['tvaReservoirsUsgs'])} / "
             f"{sum(1 for v in s['summary']['tvaReservoirsUsgs'].values() if any(c['eligibleForV3'] for c in v))}",
             f"Geometry: outline {s['summary']['geometry']['outline']}, point only {s['summary']['geometry']['pointOnly']}"]
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("lakes")
    a.add_argument("--out", required=True)
    sub.add_parser("verify")
    for name in ("controls", "census"):
        c = sub.add_parser(name)
        c.add_argument("--out", required=True)
        c.add_argument("--registry", default=REGISTRY_BASE, help="Lake Registry base URL or a local copy; 'none' for point-only")
        c.add_argument("--usgs-api", choices=["auto", "waterservices", "ogc"], default="auto")
        c.add_argument("--lakes", nargs="*", help="limit to these lake ids")
        if name == "census":
            c.add_argument("--skip-controls", action="store_true", help="recorded in the output; for a resumed run only")
    s = sub.add_parser("summarize")
    s.add_argument("--summary", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "summarize":
        print(summary_text(json.load(open(args.summary, encoding="utf-8"))))
        return 0
    rules, digest = load_rules()
    if args.cmd == "verify":
        print(f"OK {rules['rulesId']} sha256 {digest}")
        return 0
    if args.cmd == "lakes":
        t = load_targets()
        os.makedirs(args.out, exist_ok=True)
        json.dump(t, open(os.path.join(args.out, "targets.json"), "w"), indent=1)
        n = {p: sum(1 for l in t["lakes"] if p in l["purposes"]) for p in ("BINDING", "INDEPENDENT_TRUTH")}
        print(f"{t['directoryCount']} lakes, reviewed {t['reviewedCount']}, purposes {n}")
        return 0
    now = dt.datetime.now(dt.timezone.utc)
    fetcher = Fetcher(rules, out=args.out)
    registry = None if args.registry == "none" else args.registry
    if args.cmd == "controls":
        tt = load_targets()
        census = Census(rules, fetcher, now, args.usgs_api)
        targets = {t["lakeId"]: dict(t) for t in tt["lakes"] if t["lakeId"] in {c["lakeId"] for c in CONTROLS}}
        census.load_geometry(list(targets.values()), registry)
        res = run_controls(census, targets)
        os.makedirs(args.out, exist_ok=True)
        json.dump(res, open(os.path.join(args.out, "controls.json"), "w"), indent=1, default=str)
        with open(os.path.join(args.out, "controls.requests.jsonl"), "w", encoding="utf-8") as fh:
            for r in fetcher.log:
                fh.write(json.dumps(r) + "\n")
        print(json.dumps(res, indent=1, default=str))
        return 0 if not res["disabledProviders"] else 3
    result = run_census(rules, digest, fetcher, now, registry, args.lakes, args.usgs_api, args.skip_controls)
    shas = write_outputs(args.out, result, fetcher)
    print(summary_text(result))
    print("sha256: " + ", ".join(f"{k} {v}" for k, v in shas.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
