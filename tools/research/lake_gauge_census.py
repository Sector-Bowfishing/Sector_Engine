#!/usr/bin/env python3
"""Lake gauge census: GET-only, metadata-only discovery of gauge-grade level series for every directory lake (rules LGC-2026-11-23.5).

Two purposes, one pass (docs/brains/lake-gauge-census/LGC-2026-11-23.5.rules.json, pre-registered and hashed before any request;
it supersedes LGC-2026-11-23.4, .3, .2 and the first registration, none of which was ever used). Every networked run is bound
to one hash-chained run ledger per rules id in the research folder: only census run #1 counts, outputs are write-once, the
arguments are fixed by the rules, and origin evidence must be registered by sha256 before the run.:
  BINDING            unprofiled lakes (not in Lake's reviewed set): candidate pool series for the next binding batch (stage A
                     shortlist; the stage B review with level values follows the same rules as batches 1-2 and runs later).
  INDEPENDENT_TRUTH  every lake with a binding: series that are NOT the lake's bound live/fallback/history series, with
                     independence evidence, so the operator-truth validation v3 can freeze a truth list from metadata alone.

Sources: USGS WaterServices site catalog (fallback: USGS Water Data OGC API), USACE CWMS Data API catalogs, Reclamation RISE
JSON:API, and Sector's public Lake Registry outlines. The TVA host, NWS NWPS/HADS and SWOT are never queried.

It never writes Firebase, buckets, bindings, accepted lists, the knowledge release or any score. It writes only to --out.
The one data call (USGS instantaneous values, last 12 h, shortlisted pool candidates only) keeps time stamps and drops every value
at parse time. No request leaves before the rules' notBefore instant, 2026-12-01T12:00Z (the operator-truth validation, PR #243,
runs 2026-11-24..30): the fetcher refuses it, so controls, geometry and census are all covered. Redirects are never followed,
robots.txt follows RFC 9309 (5xx or no answer = disallow), every retry counts against the budget, and a failed chunk or lake is
recorded while the run continues to a partial output.

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
sys.path.insert(0, HERE)
from lake_census_run_ledger import LedgerRefused, RunLedger, tree_hash  # noqa: E402
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
RULES = os.path.join(REPO, "docs", "brains", "lake-gauge-census", "LGC-2026-11-23.5.rules.json")
RULES_ID = "LGC-2026-11-23.5"
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
# Pagination caps; reaching one with pages left marks the listing truncated (never complete).
CWMS_LOCATION_PAGES, CWMS_TS_PAGES, RISE_LOCATION_PAGES, OGC_PAGES = 50, 10, 399, 20
WATERSERVICES_EMPTY = b"No sites found matching all criteria"

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
    rules = json.load(open(path, encoding="utf-8"))
    if rules.get("rulesId") != RULES_ID:
        raise SystemExit(f"REFUSED: rules {rules.get('rulesId')} are not the current registration {RULES_ID}")
    return rules, digest


def not_before(rules: dict) -> dt.datetime:
    t = dt.datetime.fromisoformat(rules["notBefore"].replace("Z", "+00:00"))
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


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


class OfficeUnavailable(Exception):
    pass


class CatalogUnavailable(Exception):
    pass


# Hosts the census never contacts, whatever a rules file says: TVA (robots.txt Disallow: / for all agents), NWPS and HADS.
NEVER_HOSTS = {"tva.com", "www.tva.com", "api.water.noaa.gov", "mesonet.agron.iastate.edu"}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # never follow; the 3xx is returned as an error
        return None


class Fetcher:
    """GET-only, host-allowlisted, robots-checked, rate-limited, budgeted, date-guarded; never follows redirects.
    `transport(url, headers) -> (status, bytes)` and `now() -> datetime` are injectable."""

    def __init__(self, rules: dict, out: str | None = None, transport=None, sleep=time.sleep, clock=time.monotonic, now=None):
        self.rules = rules
        self.hosts = set(rules["hosts"])
        self.never = set(rules["fetch"].get("neverHosts") or []) | NEVER_HOSTS
        self.ua = rules["fetch"]["userAgent"]
        self.gap = float(rules["fetch"]["minSecondsBetweenRequestsPerHost"])
        self.budget = int(rules["fetch"]["maxRequests"])
        self.timeout = float(rules["fetch"]["timeoutSeconds"])
        self.not_before = not_before(rules)
        self.transport = transport or self._urllib
        self.sleep, self.clock = sleep, clock
        self.now = now or (lambda: dt.datetime.now(dt.timezone.utc))
        self.last: dict[str, float] = {}
        self.robots: dict[str, dict] = {}
        self.count = 0
        self.cache_hits = 0
        self.exhausted = False
        self.log: list[dict] = []
        self.out = out
        self.cache = os.path.join(out, "cache") if out else None
        if self.cache:
            os.makedirs(self.cache, exist_ok=True)

    def _urllib(self, url: str, headers: dict) -> tuple[int, bytes]:
        req = urllib.request.Request(url, headers=headers, method="GET")
        opener = urllib.request.build_opener(_NoRedirect)
        try:
            with opener.open(req, timeout=self.timeout) as r:
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

    def _never(self, host: str | None) -> bool:
        return bool(host) and any(host == h or host.endswith("." + h) for h in self.never)

    def _raw(self, url: str, headers: dict) -> tuple[int, bytes]:
        if self.now() < self.not_before:
            raise Refused(f"no request may be sent before {self.rules['notBefore']} ({self.rules['notBeforeReason']})")
        host = urllib.parse.urlsplit(url).hostname
        if self._never(host):
            raise Refused(f"host {host} is never queried")
        if host not in self.hosts:
            raise Refused(f"host {host} is not allowlisted")
        status, body = 0, b""
        for attempt in range(3):  # every attempt counts against the budget and is logged
            if self.count >= self.budget:
                self.exhausted = True
                raise Refused(f"request budget {self.budget} exhausted")
            self._wait(host)
            self.count += 1
            try:
                status, body = self.transport(url, dict(headers, **{"User-Agent": self.ua}))
            except Exception as e:  # network failure: recorded, retried
                status, body = -1, str(e).encode()[:500]
            self.log.append({"url": url, "attempt": attempt + 1, "status": status, "bytes": len(body), "sha256": sha256_bytes(body),
                             "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
            if status not in (-1, 429, 500, 502, 503, 504):
                break
            self.sleep(5 * (attempt + 1))
        return status, body

    def robots_ok(self, url: str) -> bool:
        """RFC 9309, conservative: 2xx parsed; 401/403/429 disallow all; other 4xx allow all; 5xx, a redirect or no answer disallow all."""
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname
        if host not in self.robots:
            status, body = self._raw(f"{parts.scheme}://{host}/robots.txt", {})
            rp = urllib.robotparser.RobotFileParser()
            if 200 <= status < 300:
                rp.parse(body.decode("utf-8", "replace").splitlines())
                state = "PARSED"
            elif 400 <= status < 500 and status not in (401, 403, 429):
                rp.allow_all = True
                state = f"HTTP_{status}_ALLOW_ALL"
            else:
                rp.disallow_all = True
                state = f"HTTP_{status}_DISALLOW_ALL" if status > 0 else "UNREACHABLE_DISALLOW_ALL"
            self.robots[host] = {"parser": rp, "state": state, "sha256": sha256_bytes(body) if 200 <= status < 300 else None, "disallowed": []}
        r = self.robots[host]
        ok = r["parser"].can_fetch(self.ua, url)
        if not ok and parts.path not in r["disallowed"]:
            r["disallowed"].append(parts.path)
        return ok

    def get(self, url: str, params: dict | None = None, accept: str | None = None, cache: bool = True) -> tuple[int, bytes]:
        if self.now() < self.not_before:
            raise Refused(f"no request may be sent before {self.rules['notBefore']} ({self.rules['notBeforeReason']})")
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params, safe=",:^\\$")
        if self._never(urllib.parse.urlsplit(url).hostname):
            raise Refused(f"host {urllib.parse.urlsplit(url).hostname} is never queried")
        if urllib.parse.urlsplit(url).hostname not in self.hosts:
            raise Refused(f"host {urllib.parse.urlsplit(url).hostname} is not allowlisted")
        if not self.robots_ok(url):
            raise Refused(f"ROBOTS_DISALLOWED {urllib.parse.urlsplit(url).hostname}{urllib.parse.urlsplit(url).path}")
        key = sha256_bytes((url + "|" + (accept or "")).encode())
        if cache and self.cache and os.path.exists(os.path.join(self.cache, key)):
            body = open(os.path.join(self.cache, key), "rb").read()
            self.cache_hits += 1
            self.log.append({"url": url, "cacheHit": True, "status": 200, "bytes": len(body), "sha256": sha256_bytes(body),
                             "cacheFile": key, "at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")})
            return 200, body
        status, body = self._raw(url, {"Accept": accept} if accept else {})
        if 300 <= status < 400:
            raise Refused(f"redirect {status} from {url} (redirects are never followed)")
        if cache and self.cache and status == 200:
            open(os.path.join(self.cache, key), "wb").write(body)
        return status, body

    def robots_report(self) -> dict:
        return {h: {"state": r["state"], "sha256": r["sha256"], "disallowedPaths": r["disallowed"],
                    "terms": self.rules["hosts"].get(h, {}).get("terms")} for h, r in self.robots.items()}

    def robots_disallowed(self) -> list[dict]:
        return [{"code": "ROBOTS_DISALLOWED", "host": h, "path": p} for h, r in self.robots.items() for p in r["disallowed"]] + \
               [{"code": "ROBOTS_DISALLOWED", "host": h, "path": "/*", "state": r["state"]}
                for h, r in self.robots.items() if r["state"].endswith("DISALLOW_ALL")]


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


def ogc_next(text: str) -> str | None:
    """The rel=next link of an OGC API Features response, if any."""
    for link in json.loads(text).get("links") or []:
        if isinstance(link, dict) and link.get("rel") == "next" and link.get("href"):
            return link["href"]
    return None


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


def rise_item_collector(attrs: dict) -> str | None:
    """The collector / source / agency the RISE item's own metadata names, if any (RISE republishes other agencies' data)."""
    for k, v in attrs.items():
        if re.search(r"collect|source|agency|provider|organi[sz]ation|owner", k, re.I) and v not in (None, ""):
            return json.dumps(v) if isinstance(v, (dict, list)) else str(v)
    return None


def rise_origin(collector: str | None) -> str:
    return "USBR" if collector and re.search(r"reclamation|\busbr\b", collector, re.I) else "RISE_UNCONFIRMED"


def parse_rise_item(text: str) -> dict:
    d = json.loads(text)
    o = d.get("data", {})
    a = o.get("attributes", {})
    return {"collector": rise_item_collector(a),"id": str(o.get("id")), "title": a.get("itemTitle", ""), "parameter": a.get("parameterName", ""),
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


def classify(rules: dict, name: str, pos: dict, version: str = "", subparam: str = "", base_class: str | None = None,
             sublocation: str = "", latest: str | None = None, now: dt.datetime | None = None,
             date_granular: bool = False) -> tuple[str, list[str]]:
    c = rules["classification"]
    why = []
    rc = _has(version, c["ruleCurveVersionWords"]) + _has(subparam, c["ruleCurveVersionWords"])
    if rc:
        return "RULE_CURVE", [f"rule/guide/plan/forecast cue {rc}"]
    t = parse_time(latest)
    tol = c["futureLatestToleranceHoursDateGranular"] if date_granular else c["futureLatestToleranceHours"]
    if t and now and t > now + dt.timedelta(hours=tol):
        return "RULE_CURVE", [f"latest time {t.isoformat()} is in the future (a plan series)"]
    tail = _has(name, c["tailwaterWords"]) + _has(subparam, c["tailwaterWords"]) + _has(sublocation, c["tailwaterWords"])
    if not tail and _has(sublocation, c["subLocationNotPoolWords"]):
        return "UNKNOWN", [f"sub-location cue {_has(sublocation, c['subLocationNotPoolWords'])} (upper/lower pool or gate)"]
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


US_STATES = {"alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR", "california": "CA", "colorado": "CO",
             "connecticut": "CT", "delaware": "DE", "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID", "illinois": "IL",
             "indiana": "IN", "iowa": "IA", "kansas": "KS", "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
             "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS", "missouri": "MO", "montana": "MT",
             "nebraska": "NE", "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
             "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR", "pennsylvania": "PA",
             "rhode island": "RI", "south carolina": "SC", "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
             "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY"}


def state_code(s) -> str | None:
    if not s:
        return None
    s = str(s).strip()
    return s.upper() if len(s) == 2 else US_STATES.get(s.lower())


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
    def __init__(self, rules: dict, fetcher: Fetcher, now: dt.datetime, usgs_api: str = "auto", evidence: dict | None = None):
        self.r, self.f, self.now = rules, fetcher, now
        self.params = set(rules["usgs"]["parameters"])
        self.usgs_api = usgs_api
        self.errors: list[dict] = []
        self.disabled: dict[str, str] = {}
        self._cwms_locs: dict[str, list[dict]] = {}
        self._rise_locs: list[dict] | None = None
        self._usgs_coords: dict[str, dict] = {}
        self.evidence = evidence or {}
        self._office_failures: dict[str, int] = {}
        self._office_truncated: set[str] = set()
        self._rise_failures = 0
        self._rise_truncated = False
        self.rise_collectors: dict[str, str | None] = {}
        self.geometry_hashes: dict = {}
        self.no_coordinates: dict[str, int] = {}
        self.incomplete: dict[str, list[str]] = {}

    def mark(self, lake: dict, code: str):
        """Discovery for this lake is incomplete: it can never be counted as 'no candidate'."""
        lst = self.incomplete.setdefault(lake["lakeId"], [])
        if code not in lst:
            lst.append(code)

    # ---- geometry
    def load_geometry(self, lakes: list[dict], registry: str | None):
        """Outlines from the Lake Registry. A failed index or outline marks the lake GEOMETRY_UNAVAILABLE (never 'no candidate');
        a registry entry without geometry is POINT_ONLY by design. The sha256 of every file read is recorded."""
        if not registry:
            return
        self.geometry_hashes.setdefault("registrySource", registry)
        try:
            idx = self._registry_json("registry/lakes.v1.json", registry)
        except Exception as ex:
            self.errors.append({"stage": "geometry", "error": f"registry index: {str(ex)[:200]}"})
            for lake in lakes:
                self.mark(lake, "GEOMETRY_UNAVAILABLE")
            return
        entries = {e["lakeId"]: e for e in (idx.get("lakes") if isinstance(idx, dict) else idx) or []}
        for lake in lakes:
            e = entries.get(lake["lakeId"])
            if not e or not e.get("geometry"):
                continue
            try:
                g = self._registry_json(f"lakes/{lake_key(lake['lakeId'])}/geometry.v1.analysis.geojson.gz", registry, lake["lakeId"])
                lake["_polys"] = polygons_of(g)
            except Exception as ex:  # recorded; the lake is POINT_ONLY and incomplete
                self.errors.append({"lakeId": lake["lakeId"], "stage": "geometry", "error": str(ex)[:200]})
                self.mark(lake, "GEOMETRY_UNAVAILABLE")

    def _registry_json(self, rel: str, registry: str, lake_id: str | None = None):
        if registry.startswith("http"):
            status, body = self.f.get(f"{registry.rstrip('/')}/{rel}")
            if status != 200:
                raise RuntimeError(f"registry {rel}: HTTP {status}")
        else:
            body = open(os.path.join(registry, rel), "rb").read()
        if lake_id:
            self.geometry_hashes.setdefault("outlines", {})[lake_id] = sha256_bytes(body)
        else:
            self.geometry_hashes["index"] = sha256_bytes(body)
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
            self.mark(lake, "USGS_BOX_TOO_LARGE")
            return []
        rows = None
        if self.usgs_api in ("auto", "waterservices"):
            status, body = self.f.get(USGS_SITE, {"format": "rdb", "bBox": f"{w:.6f},{s:.6f},{e:.6f},{n:.6f}",
                                                  "parameterCd": ",".join(sorted(self.params)), "siteStatus": "all",
                                                  "seriesCatalogOutput": "true"})
            if status == 200:
                rows = parse_usgs_site_catalog(body.decode("utf-8", "replace"), self.params)
            elif status == 404 and WATERSERVICES_EMPTY in body:
                rows = []  # the well-formed "no sites found" answer
            else:
                self.errors.append({"lakeId": lake["lakeId"], "stage": "usgs-site", "error": f"HTTP {status}"})
                if self.usgs_api == "waterservices":
                    self.mark(lake, "USGS_SITE_ERROR")
                    raise RuntimeError(f"usgs site service HTTP {status}")
        if rows is None:
            try:
                rows = self._usgs_ogc((w, s, e, n), lake)
            except Exception:
                self.mark(lake, "USGS_SITE_ERROR")
                raise
        out = []
        for r in rows:
            if r["lat"] is None or r["lon"] is None:
                self.mark(lake, "USGS_SITE_NO_COORDINATES")
                continue
            pos = position(lake, r["lat"], r["lon"])
            latest = max((parse_time(x.get("end")) for x in r["dataTypes"].values() if x.get("end")), default=None)
            cls, why = classify(self.r, r["name"], pos, base_class="POOL" if r.get("siteType") in ("LK", "ES") or r["param"] in self.params else None,
                                latest=latest.isoformat() if latest else None, now=self.now, date_granular=True)
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

    def _ogc_pages(self, url: str, params: dict, lake: dict) -> list[str]:
        """Every page of an OGC API collection query, following rel=next links up to OGC_PAGES; a cap reached with a next link
        left marks USGS_OGC_TRUNCATED. Raises on a non-200 first page; a later failed page marks the lake incomplete."""
        pages, nxt = [], None
        for i in range(OGC_PAGES):
            st, body = self.f.get(url, params) if i == 0 else self.f.get(nxt)
            if st != 200:
                if i == 0:
                    raise RuntimeError(f"usgs ogc HTTP {st}")
                self.mark(lake, "USGS_OGC_TRUNCATED")
                return pages
            text = body.decode()
            pages.append(text)
            nxt = ogc_next(text)
            if not nxt:
                return pages
        self.mark(lake, "USGS_OGC_TRUNCATED")
        return pages

    def _usgs_ogc(self, box, lake: dict) -> list[dict]:
        w, s, e, n = box
        locs = [l for page in self._ogc_pages(USGS_OGC.format(c="monitoring-locations"),
                                              {"bbox": f"{w:.6f},{s:.6f},{e:.6f},{n:.6f}", "f": "json", "limit": 500}, lake)
                for l in parse_ogc_locations(page)]
        rows = []
        for loc in locs:
            try:
                pages = self._ogc_pages(USGS_OGC.format(c="time-series-metadata"),
                                        {"monitoring_location_id": loc["ogcId"], "f": "json", "limit": 200}, lake)
            except RuntimeError as ex:
                self.errors.append({"lakeId": lake["lakeId"], "stage": "usgs-tsmeta", "site": loc["site"], "error": str(ex)})
                self.mark(lake, "USGS_TSMETA_UNAVAILABLE")
                continue
            for m in [m for page in pages for m in parse_ogc_tsmeta(page, self.params)]:
                key = "uv" if (m.get("period") or "").lower() in ("points", "instantaneous") else "dv"
                ex = next((r for r in rows if r["site"] == loc["site"] and r["param"] == m["param"]), None)
                if not ex:
                    ex = dict(loc, param=m["param"], dataTypes={}, ogc=True)
                    rows.append(ex)
                ex["dataTypes"][key] = {"begin": m["begin"], "end": m["end"], "count": None}
        return rows

    def usgs_iv_timestamps(self, todo: list[dict]):
        """Last 12 h of IV time stamps for the pre-shortlisted USGS pool candidates (values dropped at parse time). A failed
        chunk is recorded and skipped; its candidates keep the catalog end date."""
        for i in range(0, len(todo), 50):
            chunk = todo[i:i + 50]
            try:
                st, body = self.f.get(USGS_IV, {"format": "json", "sites": ",".join(sorted({c["station"] for c in chunk})),
                                                "parameterCd": ",".join(sorted({c["series"] for c in chunk})), "period": "PT12H",
                                                "siteStatus": "all"}, cache=False)
                if st != 200:
                    raise RuntimeError(f"HTTP {st}")
                stamps = parse_iv_timestamps(body.decode())
                del body
            except Exception as ex:
                self.errors.append({"stage": "usgs-iv", "error": str(ex)[:300], "sites": [c["station"] for c in chunk]})
                continue
            for c in chunk:
                s = stamps.get((c["station"], c["series"])) or []
                if s:
                    c["cadenceMin"] = cadence_from(s)
                    c["latest"] = max(parse_time(x) for x in s).isoformat()
                    c["latestBasis"] = "IV time stamps, last 12 h (values discarded)"

    def usgs_coords(self, sites: list[str]) -> dict:
        need = sorted({s for s in sites if s and s not in self._usgs_coords})
        for i in range(0, len(need), 100):
            try:
                st, body = self.f.get(USGS_SITE, {"format": "rdb", "sites": ",".join(need[i:i + 100]), "siteStatus": "all"})
                if st != 200:
                    raise RuntimeError(f"HTTP {st}")
                self._usgs_coords.update(parse_usgs_basic_sites(body.decode("utf-8", "replace")))
            except Exception as ex:
                self.errors.append({"stage": "bound-usgs-coords", "error": str(ex)[:300], "sites": need[i:i + 100]})
        return self._usgs_coords

    def rise_item_coords(self, items: list[str]) -> dict:
        """RISE item -> (lat, lon) from the already-fetched RISE locations; an item not listed there is looked up once."""
        try:
            locs = self.rise_locations()
        except CatalogUnavailable:
            locs = []
        by_item = {i: l for l in locs for i in l["items"]}
        by_id = {l["id"]: l for l in locs}
        out = {}
        for it in sorted(set(items)):
            loc = by_item.get(it)
            if loc is None:
                try:
                    st, body = self.f.get(RISE.format(path=f"catalog-item/{it}"), accept=RISE_ACCEPT)
                    if st == 200:
                        data = json.loads(body).get("data", {})
                        self.rise_collectors[it] = rise_item_collector(data.get("attributes", {}))
                        ids = _jsonapi_rel_ids(data, r"^location$")
                        loc = by_id.get(ids[0]) if ids else None
                except Exception as ex:
                    self.errors.append({"stage": "bound-rise-coords", "item": it, "error": str(ex)[:300]})
            if loc and loc["lat"] is not None:
                out[it] = (loc["lat"], loc["lon"])
        return out

    # ---- CWMS
    def cwms_locations(self, office: str) -> list[dict]:
        if office not in self._cwms_locs:
            if self._office_failures.get(office, 0) >= 3:
                raise OfficeUnavailable(office)
            locs, page = [], None
            try:
                for i in range(CWMS_LOCATION_PAGES):
                    p = {"office": office, "page-size": 5000}
                    if page:
                        p["page"] = page
                    st, body = self.f.get(CWMS.format(kind="LOCATIONS"), p, accept=CWMS_ACCEPT)
                    if st != 200:
                        raise RuntimeError(f"HTTP {st}")
                    got, page = parse_cwms_locations(body.decode())
                    locs += got
                    if not page or not got:
                        break
                else:
                    if page:  # the cap was reached with pages left: the listing is truncated, never complete
                        self._office_truncated.add(office)
                        self.errors.append({"stage": "cwms-locations", "office": office, "error": "pagination cap reached (truncated)"})
            except Exception as ex:  # never cached as empty: retried for the next lake, at most 3 failures per office
                self._office_failures[office] = self._office_failures.get(office, 0) + 1
                self.errors.append({"stage": "cwms-locations", "office": office, "error": str(ex)[:300],
                                    "failures": self._office_failures[office]})
                raise OfficeUnavailable(office) from ex
            self._cwms_locs[office] = locs
        return self._cwms_locs[office]

    def cwms(self, lake: dict) -> list[dict]:
        w, s, e, n = self.search_box(lake)
        out = []
        for office in self.r["cwms"]["offices"]:
            try:
                office_locs = self.cwms_locations(office)
            except OfficeUnavailable:
                self.mark(lake, f"CWMS_OFFICE_UNAVAILABLE:{office}")
                continue
            if office in self._office_truncated:
                self.mark(lake, f"CWMS_LOCATIONS_TRUNCATED:{office}")
            for loc in office_locs:
                if loc["lat"] is None or loc["lon"] is None:
                    if loc.get("state") and str(loc["state"]).upper() in {lake.get("state", "").upper()} | {x.upper() for x in lake.get("states") or []}:
                        self.mark(lake, f"CWMS_LOCATION_NO_COORDINATES:{office}")
                    elif not loc.get("state"):
                        self.no_coordinates[f"cwms:{office}"] = self.no_coordinates.get(f"cwms:{office}", 0) + 1
                    continue
                if not (w <= loc["lon"] <= e and s <= loc["lat"] <= n):
                    continue
                pos = position(lake, loc["lat"], loc["lon"])
                like = "^" + re.escape(loc["name"]) + r"\.Elev"
                page = None
                for i in range(CWMS_TS_PAGES):
                    p = {"office": office, "like": like, "include-extents": "true", "page-size": 500}
                    if page:
                        p["page"] = page
                    st, body = self.f.get(CWMS.format(kind="TIMESERIES"), p, accept=CWMS_ACCEPT)
                    if st != 200:
                        self.errors.append({"lakeId": lake["lakeId"], "stage": "cwms-ts", "location": loc["name"], "error": f"HTTP {st}"})
                        self.mark(lake, f"CWMS_TS_UNAVAILABLE:{loc['name']}")
                        page = None
                        break
                    rows, page = parse_cwms_ts(body.decode())
                    for t in rows:
                        cp = cwms_parts(t["tsid"])
                        if cp["baseParam"] != "Elev" or cp["location"] != loc["name"]:
                            continue
                        name = " ".join(filter(None, [loc["name"].replace("-", " "), loc.get("publicName"), loc.get("longName"), cp["subLocation"]]))
                        base = "POOL" if (loc.get("kind") or "").upper() in ("PROJECT", "EMBANKMENT", "LOCK") and not cp["subLocation"] else None
                        cls, why = classify(self.r, name, pos, version=cp["version"], subparam=cp["subParam"], base_class=base,
                                            sublocation=cp["subLocation"], latest=t["latest"], now=self.now)
                        origin = self.cwms_origin(cp["version"])
                        out.append({"provider": "cwms", "agency": "USACE", "station": office, "series": t["tsid"], "location": loc["name"],
                                    "name": loc.get("publicName") or loc.get("longName") or loc["name"], "lat": loc["lat"], "lon": loc["lon"],
                                    "position": pos, "class": cls, "classWhy": why, "cadenceMin": interval_minutes(cp["interval"]),
                                    "latest": t["latest"], "latestBasis": "CDA catalog extent latest-time", "begin": t["earliest"],
                                    "datum": loc.get("verticalDatum"), "aliases": loc.get("aliases"), "host": "cwms-data.usace.army.mil",
                                    "capabilityIfBound": self.r["selection"]["S8_capability"]["cwms"], "origin": origin})
                    if not page or not rows:
                        page = None
                        break
                if page:  # cap reached with pages left
                    self.errors.append({"lakeId": lake["lakeId"], "stage": "cwms-ts", "location": loc["name"], "error": "pagination cap reached (truncated)"})
                    self.mark(lake, f"CWMS_TS_TRUNCATED:{loc['name']}")
        return out

    def cwms_origin(self, version: str) -> str:
        return cwms_origin(self.r, version)

    # ---- RISE
    def rise_locations(self) -> list[dict]:
        """The RISE location listing. A failed or partial listing is never cached: it raises CatalogUnavailable and is retried
        for the next lake, at most 3 failures per run. A listing that hits the page cap is kept but flagged truncated."""
        if self._rise_locs is None:
            if self._rise_failures >= 3:
                raise CatalogUnavailable("RISE_CATALOG_UNAVAILABLE")
            locs, url, params, nxt = [], RISE.format(path="location"), {"itemsPerPage": 100, "page": 1}, None
            try:
                for page in range(1, RISE_LOCATION_PAGES + 1):
                    params["page"] = page
                    st, body = self.f.get(url, params, accept=RISE_ACCEPT)
                    if st != 200:
                        raise RuntimeError(f"HTTP {st} at page {page}")
                    got, nxt = parse_rise_locations(body.decode())
                    locs += got
                    if not got or not nxt:
                        nxt = None
                        break
            except Exception as ex:
                self._rise_failures += 1
                self.errors.append({"stage": "rise-locations", "error": str(ex)[:300], "failures": self._rise_failures,
                                    "locationsRead": len(locs)})
                raise CatalogUnavailable("RISE_CATALOG_PARTIAL" if locs else "RISE_CATALOG_UNAVAILABLE") from ex
            if nxt:
                self._rise_truncated = True
                self.errors.append({"stage": "rise-locations", "error": "pagination cap reached (truncated)"})
            self._rise_locs = locs
        return self._rise_locs

    def rise(self, lake: dict) -> list[dict]:
        w, s, e, n = self.search_box(lake)
        out = []
        try:
            listing = self.rise_locations()
        except CatalogUnavailable as ex:
            self.mark(lake, str(ex))
            return []
        if self._rise_truncated:
            self.mark(lake, "RISE_CATALOG_TRUNCATED")
        for loc in listing:
            if loc["lat"] is None or loc["lon"] is None:
                st_ = state_code(loc.get("state"))
                if st_ and st_ in {lake.get("state", "").upper()} | {x.upper() for x in lake.get("states") or []}:
                    self.mark(lake, "RISE_LOCATION_NO_COORDINATES")
                elif not st_:
                    self.no_coordinates["rise"] = self.no_coordinates.get("rise", 0) + 1
                continue
            if not (w <= loc["lon"] <= e and s <= loc["lat"] <= n):
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
                        else:
                            self.errors.append({"lakeId": lake["lakeId"], "stage": "rise-detail", "record": rec, "error": f"HTTP {st2}"})
                            self.mark(lake, f"RISE_DETAIL_UNAVAILABLE:{loc['id']}")
                else:
                    self.errors.append({"lakeId": lake["lakeId"], "stage": "rise-detail", "location": loc["id"], "error": f"HTTP {st}"})
                    self.mark(lake, f"RISE_DETAIL_UNAVAILABLE:{loc['id']}")
            for iid in items:
                st, body = self.f.get(RISE.format(path=f"catalog-item/{iid}"), accept=RISE_ACCEPT)
                if st != 200:
                    self.errors.append({"lakeId": lake["lakeId"], "stage": "rise-item", "item": iid, "error": f"HTTP {st}"})
                    self.mark(lake, f"RISE_ITEM_UNAVAILABLE:{iid}")
                    continue
                it = parse_rise_item(body.decode())
                self.rise_collectors[iid] = it["collector"]
                text = f"{it['title']} {it['parameter']}"
                if "elevation" not in text.lower():
                    continue
                base = "POOL" if re.search(r"lake/reservoir elevation|reservoir elevation|lake elevation|pool elevation", text, re.I) else None
                own = set(_words(loc["name"]))
                title_cues = " ".join(w for w in _words(it["title"]) if w not in own)  # a lake named "Upper ..." is not a plan cue
                cls, why = classify(self.r, f"{loc['name']} {text}", pos, version=title_cues, base_class=base, latest=it["end"], now=self.now)
                out.append({"provider": "rise", "agency": "USBR", "station": iid, "series": iid, "location": loc["id"], "name": it["title"] or loc["name"],
                            "lat": loc["lat"], "lon": loc["lon"], "position": pos, "class": cls, "classWhy": why,
                            "cadenceMin": rise_minutes(it["timestep"]), "latest": it["end"], "latestBasis": "RISE catalog temporalEndDate",
                            "begin": it["begin"], "datum": it["verticalDatum"] or loc["verticalDatum"], "host": "data.usbr.gov",
                            "capabilityIfBound": self.r["selection"]["S8_capability"]["rise"], "collector": it["collector"],
                            "origin": rise_origin(it["collector"])})
        return out

    # ---- per lake
    def discover(self, lake: dict) -> list[dict]:
        cands = []
        for prov, fn in (("usgs", self.usgs), ("cwms", self.cwms), ("rise", self.rise)):
            if prov in self.disabled:
                self.mark(lake, f"PROVIDER_DISABLED:{prov}")
                continue
            try:
                cands += fn(lake)
            except Refused as ex:
                self.errors.append({"lakeId": lake["lakeId"], "stage": prov, "error": f"REFUSED {ex}"})
                self.mark(lake, f"PROVIDER_FAILED:{prov}")
            except Exception as ex:
                self.errors.append({"lakeId": lake["lakeId"], "stage": prov, "error": str(ex)[:300]})
                self.mark(lake, f"PROVIDER_FAILED:{prov}")
        return cands


# ------------------------------------------------------------------------------------------------------------------ verdicts
def cwms_origin(rules: dict, version: str) -> str:
    """Origin of a CWMS series from its version label: a labelled copy (USGS / USBR / CDEC), an NWS redistribution, or unlabelled.
    An unlabelled series is origin-unknown (districts publish other agencies' gauges under their own version names); only an
    origin-evidence entry makes it USACE."""
    for origin, words in rules["classification"]["copyVersionWords"].items():
        if _has(version, words):
            return origin
    return "USACE_UNLABELLED"


FAMILY = {"USGS": {"USGS"}, "USGS_COPY": {"USGS"}, "USACE": {"USACE"}, "USACE_UNLABELLED": {"USACE"},
          "USBR": {"USBR"}, "RISE_UNCONFIRMED": {"USBR"}, "USBR_COPY": {"USBR"}, "CDEC_COPY": {"CDEC"}, "TVA": {"TVA"}, "NWS_REDISTRIBUTION": {"NWS"}}
COPIES = {"USGS_COPY": "USGS", "USBR_COPY": "USBR", "CDEC_COPY": "CDEC"}


def load_origin_evidence(rules: dict, path: str | None) -> tuple[dict, dict | None]:
    """Reviewed origin evidence: [{"provider","series","origin","evidence"}]; origin USACE for a cwms/a2w series, USBR for a rise
    item. An entry for a CWMS series whose version already names an agency is refused (copies stay copies). Returns the entries
    and a record {sha256, text} for the output; whether the file is registered is checked by the run binding."""
    if not path:
        return {}, None
    raw = open(path, "rb").read()
    out = {}
    for e in json.loads(raw):
        allowed = {"cwms": "USACE", "a2w": "USACE", "rise": "USBR"}.get(e.get("provider"))
        if not allowed or e.get("origin") != allowed or not e.get("evidence") or not e.get("series"):
            raise SystemExit(f"REFUSED: origin-evidence entry needs provider, series, origin USACE (cwms) or USBR (rise) and an evidence text: {e}")
        if e["provider"] in ("cwms", "a2w") and cwms_origin(rules, cwms_parts(e["series"])["version"]) != "USACE_UNLABELLED":
            raise SystemExit(f"REFUSED: {e['series']} already names an agency in its version; a labelled copy stays a copy")
        out[series_key(e["provider"], e.get("station"), e["series"])] = e
    return out, {"sha256": sha256_bytes(raw), "text": raw.decode("utf-8", "replace")}


def series_key(provider: str, station, series) -> tuple:
    if provider in ("cwms", "a2w"):
        return ("cwms", series)
    if provider == "usgs":
        return ("usgs", station, series)
    if provider == "rise":
        return ("rise", str(series or station))
    return (provider, station, series)


def bound_origin(rules: dict, ref: dict, evidence: dict | None = None, rise_collectors: dict | None = None) -> str:
    p = ref["provider"]
    if p in ("cwms", "a2w"):
        if evidence and series_key(p, ref.get("station"), ref.get("series")) in evidence:
            return "USACE"
        return cwms_origin(rules, cwms_parts(ref.get("series") or "")["version"])
    if p == "rise":
        if evidence and series_key(p, ref.get("station"), ref.get("series")) in evidence:
            return "USBR"
        return rise_origin((rise_collectors or {}).get(str(ref.get("series") or ref.get("station"))))
    return {"usgs": "USGS", "tva": "TVA", "nwps": "NWS_REDISTRIBUTION", "hads": "NWS_REDISTRIBUTION"}.get(p, p.upper())


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


def is_derived(rules: dict, series: str | None) -> bool:
    """Substring match on the lower-cased version (Rev2, Revised, Computed, Calc1, Best-NWO all match)."""
    v = cwms_parts(series or "")["version"].lower()
    return any(w in v for w in rules["classification"]["derivedVersionWords"])


def independence(rules: dict, c: dict, bound: list[dict], coords: dict, evidence: dict | None = None,
                 rise_collectors: dict | None = None) -> dict:
    """Evidence that a candidate is not the lake's bound series or the same gauge (metadata only). Conservative: anything the
    metadata cannot separate is UNCERTAIN."""
    ind = rules["independence"]
    same_m, other_m = ind["sameGaugeDistanceM"], ind["otherSiteMinDistanceM"]
    origin = c["origin"]
    key = series_key(c["provider"], c["station"], c["series"])
    if evidence and key in evidence:
        origin = {"cwms": "USACE", "rise": "USBR"}.get(c["provider"], origin)
    b_origins = sorted({bound_origin(rules, b, evidence, rise_collectors) for b in bound})
    fam = FAMILY.get(origin, {origin})
    b_fam = set().union(*(FAMILY.get(o, {o}) for o in b_origins)) if b_origins else set()
    dists, unknown_loc = [], []
    for b in bound:
        loc = coords.get((b["provider"], b.get("station"), b.get("series")))
        if loc:
            dists.append(round(haversine_m(c["lat"], c["lon"], loc[0], loc[1])))
        else:
            unknown_loc.append(f"{b['provider']}:{b.get('station')}")
    ev = {"originAgency": origin, "boundOriginAgencies": b_origins, "minDistanceToBoundGaugeM": min(dists) if dists else None,
          "boundGaugesWithUnknownLocation": unknown_loc}

    def out(tier, *why):
        return dict(ev, tier=tier, reasons=list(why))

    if origin == "NWS_REDISTRIBUTION":
        return out("NOT_INDEPENDENT", "NWS redistribution")
    if c["provider"] == "usgs" and any(b["provider"] == "usgs" and b.get("station") == c["station"] for b in bound):
        return out("NOT_INDEPENDENT", "same USGS site as a bound series (other parameter or endpoint)")
    bound_cwms = [b for b in bound if b["provider"] in ("cwms", "a2w")]
    c_derived = c["provider"] == "cwms" and is_derived(rules, c["series"])
    b_derived = any(is_derived(rules, b.get("series")) for b in bound_cwms)
    if c["provider"] == "cwms":
        base = cwms_parts(c["series"])["baseLocation"].lower()
        if base in {cwms_parts(b.get("series") or "")["baseLocation"].lower() for b in bound_cwms}:
            return out("NOT_INDEPENDENT", f"same CWMS base location {base} as a bound series (sub-location, version or interval)")
    if origin in COPIES and COPIES[origin] in b_fam:
        return out("NOT_INDEPENDENT", f"CWMS copy of a {COPIES[origin]} gauge and the lake has a bound {COPIES[origin]} series")
    unknown_origins = {"USACE_UNLABELLED", "RISE_UNCONFIRMED"}
    unknown = origin in unknown_origins or bool(unknown_origins & set(b_origins))
    if dists and min(dists) < same_m and (fam & b_fam or unknown):
        return out("NOT_INDEPENDENT", f"overlapping or unknown origin within {same_m} m of a bound gauge")
    reasons = []
    if origin == "USACE_UNLABELLED" or "USACE_UNLABELLED" in b_origins:
        reasons.append("origin unknown: an unlabelled CWMS series on one side (no origin evidence); two series can derive from one sensor")
    if origin == "RISE_UNCONFIRMED" or "RISE_UNCONFIRMED" in b_origins:
        reasons.append("origin unknown: a RISE item whose metadata does not name Reclamation on one side (RISE republishes other agencies' data)")
    if c_derived:
        reasons.append("derived CWMS version (Best/Rev/Comp/Calc/CCP): a derivation of another series")
    if b_derived:
        reasons.append("a bound CWMS series has a derived version; its inputs are not named")
    if origin in COPIES:
        reasons.append(f"CWMS copy of an unidentified {COPIES[origin]} gauge")
    for o in b_origins:
        if o in COPIES and c["provider"] != "cwms" and COPIES[o] in fam:
            reasons.append(f"a bound CWMS series is a {COPIES[o]} copy; the copied gauge is not named")
    if unknown_loc:
        reasons.append("a bound gauge's location is unknown: " + ", ".join(unknown_loc))
    if reasons:
        return out("UNCERTAIN", *reasons)
    if not (fam & b_fam) and min(dists) >= same_m:
        return out("INDEPENDENT_AGENCY", f"origin {origin} differs from {b_origins}")
    if min(dists) >= other_m:
        return out("INDEPENDENT_SITE", f"same known agency family, different site {min(dists)} m from the nearest bound gauge")
    return out("UNCERTAIN", "closer than the other-site distance")


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


def finalize(rules: dict, targets: list[dict], found: dict[str, list[dict]], coords: dict, now: dt.datetime, robots: dict,
             evidence: dict | None = None, incomplete: dict | None = None, rise_collectors: dict | None = None) -> list[dict]:
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
                c["independence"] = independence(rules, c, t["bound"], coords, evidence, rise_collectors)
                c["eligibleForV3"] = (c["independence"]["tier"] in ("INDEPENDENT_AGENCY", "INDEPENDENT_SITE") and c["class"] == "POOL"
                                      and within_r1(rules, c["position"]) is True and c["liveByS4"] is True)
            rows.append(c)
        rows.sort(key=order_key)
        shortlisted = [c for c in rows if (c.get("selection") or {}).get("verdict") == "SHORTLIST"]
        out.append({k2: v2 for k2, v2 in t.items() if not k2.startswith("_")} | {
            "geometryBasis": "OUTLINE" if t.get("_polys") else "POINT_ONLY",
            "discovered": lid in found,
            "discoveryIncomplete": sorted(set((incomplete or {}).get(lid, []))),
            "candidates": rows,
            "bestShortlist": ({"provider": shortlisted[0]["provider"], "station": shortlisted[0]["station"], "series": shortlisted[0]["series"],
                               "capability": shortlisted[0]["capabilityIfBound"]} if shortlisted else None)})
    return out


def incomplete_codes(lakes: list[dict]) -> dict:
    """How many lakes carry each incompleteness code (the part before ':'), over every lake and purpose."""
    out = {}
    for l in lakes:
        for code in {c.split(":")[0] for c in l.get("discoveryIncomplete") or []}:
            out[code] = out.get(code, 0) + 1
    return dict(sorted(out.items()))


def summarize(rules: dict, lakes: list[dict], reviewed_count: int | None = None) -> dict:
    cov = rules["coverageArithmetic"]
    binding = [l for l in lakes if "BINDING" in l["purposes"]]
    sel = lambda l, v: any((c.get("selection") or {}).get("verdict") == v for c in l["candidates"])
    with_short = [l for l in binding if sel(l, "SHORTLIST")]
    hand_only = [l for l in binding if not sel(l, "SHORTLIST") and sel(l, "HAND_REVIEW")]
    rest = [l for l in binding if not sel(l, "SHORTLIST") and not sel(l, "HAND_REVIEW")]
    not_discovered = [l for l in rest if l.get("discovered") is False]
    incomplete = [l for l in rest if l.get("discovered") is not False and l.get("discoveryIncomplete")]
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
    reviewed = reviewed_count if reviewed_count is not None else cov["reviewedAtRegistration"]
    ceiling = reviewed + len(with_short)
    tva = {}
    for l in lakes:  # TVA reservoirs: USGS gauges are the TVA-robots-free alternative (reporting only; selection is unchanged)
        if any(b["provider"] == "tva" for b in l["bound"]) or l["lakeId"] in TVA_UNBOUND:
            tva[l["lakeId"]] = [{"station": c["station"], "series": c["series"], "class": c["class"],
                                 "selection": (c.get("selection") or {}).get("verdict"),
                                 "independence": (c.get("independence") or {}).get("tier"), "eligibleForV3": c.get("eligibleForV3")}
                                for c in l["candidates"] if c["provider"] == "usgs" and not c.get("boundToThisLake")]
    return {
        "binding": {"lakes": len(binding), "withShortlist": len(with_short), "shortlistByCapability": by_cap,
                    "handReviewOnly": len(hand_only), "noCandidate": len(rest) - len(not_discovered) - len(incomplete),
                    "incomplete": len(incomplete), "notDiscovered": len(not_discovered),
                    "incompleteCodesAllLakes": incomplete_codes(lakes),
                    "reviewedNow": reviewed, "ceilingIfAllShortlistPassStageB": ceiling,
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
        if not all(r["found"] and r["class"] == "POOL" for r in rows):
            census.disabled[prov] = "positive control not rediscovered"
    return {"results": res, "disabledProviders": dict(census.disabled)}


# ------------------------------------------------------------------------------------------------------------------ run
def bound_coords(census: Census, targets: list[dict]) -> dict:
    """Coordinates of bound gauges: USGS sites, CWMS/Access2Water locations, RISE items. TVA and NWS stay unknown."""
    coords = {}
    if "usgs" not in census.disabled:
        known = census.usgs_coords([b["station"] for t in targets for b in t["bound"] if b["provider"] == "usgs"])
        for t in targets:
            for b in t["bound"]:
                k = known.get(b["station"]) if b["provider"] == "usgs" else None
                if k and k["lat"] is not None:
                    coords[(b["provider"], b["station"], b.get("series"))] = (k["lat"], k["lon"])
    if "rise" not in census.disabled:
        try:
            known = census.rise_item_coords([str(b["station"]) for t in targets for b in t["bound"] if b["provider"] == "rise"])
        except Exception as ex:
            census.errors.append({"stage": "bound-rise-coords", "error": str(ex)[:300]})
            known = {}
        for t in targets:
            for b in t["bound"]:
                if b["provider"] == "rise" and str(b["station"]) in known:
                    coords[(b["provider"], b["station"], b.get("series"))] = known[str(b["station"])]
    if "cwms" not in census.disabled:
        for t in targets:
            for b in t["bound"]:
                if b["provider"] not in ("cwms", "a2w"):
                    continue
                try:
                    office = (b.get("station") or "").split(":")[0]
                    loc = cwms_parts(b.get("series") or "")["location"]
                    if office in census.r["cwms"]["offices"]:
                        m = next((l for l in census.cwms_locations(office) if l["name"] == loc and l["lat"] is not None), None)
                        if m:
                            coords[(b["provider"], b.get("station"), b.get("series"))] = (m["lat"], m["lon"])
                except Exception as ex:
                    census.errors.append({"lakeId": t["lakeId"], "stage": "bound-cwms-coords", "error": str(ex)[:300]})
    return coords


def pre_shortlist(rules: dict, targets: list[dict], found: dict, robots: dict) -> list[dict]:
    """USGS POOL candidates of BINDING lakes passing S1-S3 and S6: the only rows that get the IV time-stamp call."""
    out = []
    for t in targets:
        if "BINDING" not in t["purposes"]:
            continue
        bound = {series_key(b["provider"], b.get("station"), b.get("series")) for b in t["bound"]}
        for c in found.get(t["lakeId"], []):
            if (c["provider"] == "usgs" and c["class"] == "POOL" and c.get("ivAvailable") and within_r1(rules, c["position"]) is True
                    and not (robots.get(c["host"]) or {}).get("disallowedPaths")
                    and series_key("usgs", c["station"], c["series"]) not in bound):
                out.append(c)
    return out


def structural_cap(targets: list[dict]) -> dict:
    """Bound lakes whose every bound gauge can have known coordinates (no TVA / NWPS / HADS series): the only lakes that can get an
    INDEPENDENT_* row under the rules."""
    bound = [t for t in targets if t["bound"]]
    ok = [t["lakeId"] for t in bound if all(b["provider"] in ("usgs", "cwms", "a2w", "rise") for b in t["bound"])]
    return {"boundLakes": len(bound), "lakesThatCanBeIndependent": len(ok),
            "reviewedLakesThatCanBeIndependent": sum(1 for t in bound if t["reviewed"] and t["lakeId"] in set(ok)),
            "why": "a bound TVA, NWPS or HADS gauge has no published coordinates here, so every candidate on that lake is UNCERTAIN"}


def run_census(rules: dict, digest: str, fetcher: Fetcher, now: dt.datetime, registry: str | None, only: list[str] | None = None,
               usgs_api: str = "auto", skip_controls: bool = False, targets_table: dict | None = None,
               evidence: dict | None = None, controls_hook=None) -> dict:
    if now < not_before(rules):
        raise SystemExit(f"REFUSED: the census may not run before {rules['notBefore']} ({rules['notBeforeReason']})")
    tt = targets_table or load_targets()
    targets = [dict(t) for t in tt["lakes"] if not only or t["lakeId"] in only]
    census = Census(rules, fetcher, now, usgs_api, evidence)

    def geometry(lakes):
        try:
            census.load_geometry(lakes, registry)
        except Exception as ex:  # the lakes stay POINT_ONLY
            census.errors.append({"stage": "geometry", "error": str(ex)[:300]})

    geometry(targets)
    if skip_controls:
        controls = {"skipped": True}
    else:
        ctl_ids = {c["lakeId"] for c in CONTROLS}
        ctl = {t["lakeId"]: t for t in targets if t["lakeId"] in ctl_ids}
        extra = [dict(t) for t in tt["lakes"] if t["lakeId"] in ctl_ids and t["lakeId"] not in ctl]
        geometry(extra)
        ctl.update({t["lakeId"]: t for t in extra})
        controls = run_controls(census, ctl)
        if controls_hook:
            controls_hook(controls)
    found, done = {}, 0
    for i, t in enumerate(targets):
        if fetcher.exhausted:
            break
        found[t["lakeId"]] = census.discover(t)
        done += 1
        if i % 25 == 0:
            print(f"  {i + 1}/{len(targets)} {t['lakeId']}: {len(found[t['lakeId']])} candidates, {fetcher.count} requests", file=sys.stderr)
    for stage, fn in (("usgs-iv", lambda: census.usgs_iv_timestamps(pre_shortlist(rules, targets, found, fetcher.robots_report()))
                       if "usgs" not in census.disabled else None),
                      ("bound-coords", lambda: bound_coords(census, targets))):
        try:
            res = fn()
        except Exception as ex:  # partial output: record and continue
            census.errors.append({"stage": stage, "error": str(ex)[:300]})
            res = None
        if stage == "bound-coords":
            coords = res or {}
    lakes = finalize(rules, targets, found, coords, now, fetcher.robots_report(), evidence, census.incomplete, census.rise_collectors)
    summary = summarize(rules, lakes, reviewed_count=sum(1 for t in tt["lakes"] if t["reviewed"]))
    errs = {}
    for e in census.errors:
        errs[e["stage"]] = errs.get(e["stage"], 0) + 1
    summary.update({"errorsByStage": errs, "budgetExhausted": fetcher.exhausted, "lakesDiscovered": done, "lakesTargeted": len(targets),
                    "robotsDisallowed": fetcher.robots_disallowed(), "structuralCap": structural_cap(targets),
                    "locationsWithoutCoordinatesOrState": dict(census.no_coordinates)})
    return {"schema": "sector-lake-gauge-census-v1", "labels": LABELS, "rulesId": rules["rulesId"], "rulesSha256": digest,
            "generatedAt": now.isoformat(timespec="seconds"), "inputs": tt["inputs"], "usgsApi": usgs_api,
            "originEvidence": sorted(e.get("series") for e in (evidence or {}).values()),
            "geometry": census.geometry_hashes, "cacheHits": fetcher.cache_hits,
            "controls": controls, "disabledProviders": dict(census.disabled), "requests": fetcher.count,
            "robots": fetcher.robots_report(), "errors": census.errors, "summary": summary, "lakes": lakes,
            "valuesRead": "none (USGS IV time stamps only; values dropped at parse time)"}


def _write_once(path: str, body: bytes) -> str:
    with open(path, "xb") as fh:  # create-exclusive: an output is never overwritten
        fh.write(body)
        fh.flush()
        os.fsync(fh.fileno())
    return sha256_bytes(body)


def write_outputs(out: str, result: dict, fetcher: Fetcher, extra: dict | None = None) -> dict:
    os.makedirs(out, exist_ok=True)
    files = {"census.json": result, "census.summary.json": {k: result[k] for k in
             ("schema", "labels", "rulesId", "rulesSha256", "generatedAt", "inputs", "controls", "disabledProviders", "requests", "summary")},
             "robots.json": result["robots"], **(extra or {})}
    shas = {name: _write_once(os.path.join(out, name), json.dumps(obj, indent=1, default=str).encode()) for name, obj in files.items()}
    shas["requests.jsonl"] = _write_once(os.path.join(out, "requests.jsonl"), "".join(json.dumps(r) + "\n" for r in fetcher.log).encode())
    return shas


def summary_text(s: dict) -> str:
    b, it = s["summary"]["binding"], s["summary"]["independentTruth"]
    lines = [f"Lake gauge census {s['rulesId']} (rules sha256 {s['rulesSha256'][:12]}), {s['generatedAt']}, {s['requests']} GET requests, metadata only",
             f"Controls: {json.dumps({k: [r['found'] for r in v] for k, v in s['controls'].get('results', {}).items()})}; disabled: {s['disabledProviders'] or 'none'}",
             f"BINDING: {b['lakes']} unprofiled lakes; shortlist {b['withShortlist']} ({b['shortlistByCapability']}), hand review only {b['handReviewOnly']}, none {b['noCandidate']}, incomplete {b.get('incomplete')}, not discovered {b.get('notDiscovered')}",
             f"Incomplete discovery by code (lakes, all purposes): {b.get('incompleteCodesAllLakes') or 'none'}",
             f"  ceiling if every shortlisted lake passes stage B: {b['ceilingIfAllShortlistPassStageB']}/621 ({b['ceilingShare']:.1%}); target {b['target']} reachable on the shortlist: {b['targetReachableOnShortlist']}",
             f"INDEPENDENT_TRUTH: {it['lakesWithBinding']} bound lakes; candidate tiers {it['candidateTiers']}; lakes with a v3-eligible candidate {it['lakesWithV3Eligible']} (reviewed {it['reviewedLakesWithV3Eligible']})",
             f"TVA reservoirs, USGS candidates (lakes with any / with a v3-eligible one): "
             f"{sum(1 for v in s['summary']['tvaReservoirsUsgs'].values() if v)}/{len(s['summary']['tvaReservoirsUsgs'])} / "
             f"{sum(1 for v in s['summary']['tvaReservoirsUsgs'].values() if any(c['eligibleForV3'] for c in v))}",
             f"Geometry: outline {s['summary']['geometry']['outline']}, point only {s['summary']['geometry']['pointOnly']}",
             f"Structural cap: {s['summary'].get('structuralCap', {}).get('lakesThatCanBeIndependent')} of "
             f"{s['summary'].get('structuralCap', {}).get('boundLakes')} bound lakes can get an INDEPENDENT_* row (bound TVA/NWPS/HADS gauges have no coordinates)",
             f"Errors by stage: {s['summary'].get('errorsByStage') or 'none'}; budget exhausted: {s['summary'].get('budgetExhausted')}; "
             f"lakes discovered {s['summary'].get('lakesDiscovered')}/{s['summary'].get('lakesTargeted')}; "
             f"robots disallowed: {len(s['summary'].get('robotsDisallowed') or [])}"]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------------------------ run binding
def binding_folder(rules: dict, research_folder: str) -> str:
    return os.path.join(research_folder, "gauge-census", "binding", rules["rulesId"])


def tool_sha256() -> str:
    return sha256_file(os.path.abspath(__file__))


def check_fixed_arguments(rules: dict, args) -> None:
    fixed = rules["runBinding"]["fixedArguments"]
    if getattr(args, "lakes", None):
        raise LedgerRefused("--lakes is not allowed: the rules fix the lake set to 'all'")
    if args.registry != fixed["registry"]:
        raise LedgerRefused(f"--registry must be {fixed['registry']} (fixed by the rules)")
    if args.usgs_api != fixed["usgsApi"]:
        raise LedgerRefused(f"--usgs-api must be {fixed['usgsApi']} (fixed by the rules)")


def registered_evidence(rules: dict, ledger) -> set[str]:
    """Evidence sha256s registered in the rules or by a register-evidence LOG line written before census run #1 started."""
    ok = set(rules["originEvidenceRegistration"]["registeredFiles"])
    for e in ledger.entries():
        if e["kind"] == "START" and e["step"] == "census":
            break
        if e["kind"] == "LOG" and e["step"] == "register-evidence" and e.get("status") == "REGISTERED":
            ok.add(e["detail"]["sha256"])
    return ok


def controls_passed(ledger) -> bool:
    for e in ledger.entries():
        if e["kind"] == "END" and e["step"] == "controls" and e["status"] == "COMPLETED" and not (e.get("result") or {}).get("disabledProviders"):
            return True
        if e["kind"] == "LOG" and e["step"] == "census-controls" and e.get("status") == "PASS":
            return True
    return False


def run_bound(args, rules: dict, digest: str, now: dt.datetime, transport=None, sleep=time.sleep) -> int:
    """controls / census under the run binding: one ledger per rules id, only run #1 counts, write-once outputs."""
    folder = binding_folder(rules, args.research_folder)
    ledger = RunLedger(folder, rules["rulesId"], digest, clock=lambda: now)
    step = args.cmd
    try:
        check_fixed_arguments(rules, args)
    except LedgerRefused as ex:
        ledger.refuse(step, "all", str(ex))
    evidence, ev_record = ({}, None)
    if step == "census":
        evidence, ev_record = load_origin_evidence(rules, args.origin_evidence)
        if ev_record and ev_record["sha256"] not in registered_evidence(rules, ledger):
            ledger.refuse(step, "all", f"origin-evidence file sha256 {ev_record['sha256']} is not registered (rules or a "
                                       "register-evidence line before census run #1)")
        if args.skip_controls:
            aborted = [a for a in ledger.attempts("census", "all") if a["status"] == "ABORTED_NO_RESULT"]
            if not aborted or not controls_passed(ledger):
                ledger.refuse(step, "all", "--skip-controls needs an earlier ABORTED_NO_RESULT census attempt and passing controls in the ledger")
    tt = load_targets()
    fetcher = Fetcher(rules, out=folder, transport=transport, now=lambda: now, sleep=sleep)
    inputs = {"argv": {k: v for k, v in vars(args).items()}, "rulesSha256": digest, "toolSha256": tool_sha256(),
              "inputFiles": tt["inputs"], "registrySource": args.registry, "researchFolder": os.path.abspath(args.research_folder),
              "cacheBefore": tree_hash(os.path.join(folder, "cache")),
              "originEvidence": {"sha256": ev_record["sha256"]} if ev_record else None}
    with ledger.step(step, "all", inputs=inputs) as run:
        out = os.path.join(folder, f"{step}-run-{run.run_number}")
        if step == "controls":
            census = Census(rules, fetcher, now, args.usgs_api)
            targets = {t["lakeId"]: dict(t) for t in tt["lakes"] if t["lakeId"] in {c["lakeId"] for c in CONTROLS}}
            census.load_geometry(list(targets.values()), args.registry)
            res = run_controls(census, targets)
            res.update({"errors": census.errors, "incomplete": census.incomplete, "geometry": census.geometry_hashes})
            run.writing()
            os.makedirs(out)
            shas = {"controls.json": _write_once(os.path.join(out, "controls.json"), json.dumps(res, indent=1, default=str).encode()),
                    "requests.jsonl": _write_once(os.path.join(out, "requests.jsonl"),
                                                  "".join(json.dumps(r) + "\n" for r in fetcher.log).encode())}
            run.outputs = shas
            run.result = {"disabledProviders": res["disabledProviders"], "requests": fetcher.count, "cacheHits": fetcher.cache_hits,
                          "cacheAfter": tree_hash(os.path.join(folder, "cache")), "geometry": census.geometry_hashes}
            print(json.dumps(res, indent=1, default=str))
            rc = 0 if not res["disabledProviders"] else 3
        else:
            def log_controls(res):
                ledger.log("census-controls", "all", "PASS" if not res["disabledProviders"] else "FAIL",
                           {"disabledProviders": res["disabledProviders"], "startSeq": run.seq})
            result = run_census(rules, digest, fetcher, now, args.registry, None, args.usgs_api, args.skip_controls,
                                evidence=evidence, controls_hook=log_controls)
            result["runBinding"] = {"runNumber": run.run_number, "ledger": os.path.join(folder, "ledger.jsonl"), "startSeq": run.seq,
                                    "counts": run.run_number == 1}
            result["originEvidenceFile"] = ev_record
            run.writing()
            os.makedirs(out)
            shas = write_outputs(out, result, fetcher)
            run.outputs = shas
            run.result = {"requests": fetcher.count, "retries": sum(1 for r in fetcher.log if r.get("attempt", 1) > 1),
                          "cacheHits": fetcher.cache_hits, "cacheAfter": tree_hash(os.path.join(folder, "cache")),
                          "geometry": result["geometry"], "budgetExhausted": result["summary"]["budgetExhausted"],
                          "originEvidence": ev_record}
            print(summary_text(result))
            print("sha256: " + ", ".join(f"{k} {v}" for k, v in shas.items()))
            rc = 0
    return rc


def register_evidence(args, rules: dict, digest: str, now: dt.datetime) -> int:
    ledger = RunLedger(binding_folder(rules, args.research_folder), rules["rulesId"], digest, clock=lambda: now)
    if ledger.attempts("census", "all"):
        ledger.refuse("register-evidence", "all", "census run #1 has started; evidence can no longer be registered")
    _, rec = load_origin_evidence(rules, args.file)
    ledger.log("register-evidence", "all", "REGISTERED", rec)
    print(f"REGISTERED origin evidence sha256 {rec['sha256']}")
    return 0


def main(argv=None, now: dt.datetime | None = None, transport=None, sleep=time.sleep) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("lakes")
    a.add_argument("--out", required=True)
    sub.add_parser("verify")
    for name in ("controls", "census"):
        c = sub.add_parser(name)
        c.add_argument("--research-folder", default=os.environ.get("SECTOR_RESEARCH_ROOT"),
                       help="the Lake research folder (Cortex research-path, or env SECTOR_RESEARCH_ROOT); holds the run binding")
        c.add_argument("--registry", default=REGISTRY_BASE, help="fixed by the rules; any other value is refused")
        c.add_argument("--usgs-api", choices=["auto", "waterservices", "ogc"], default="auto", help="fixed by the rules to auto")
        c.add_argument("--lakes", nargs="*", help="refused: the rules fix the lake set to all")
        if name == "census":
            c.add_argument("--skip-controls", action="store_true", help="only after an aborted census attempt with passing controls")
            c.add_argument("--origin-evidence", help="a registered origin-evidence JSON file (none exists at registration)")
    r = sub.add_parser("register-evidence")
    r.add_argument("--research-folder", default=os.environ.get("SECTOR_RESEARCH_ROOT"))
    r.add_argument("--file", required=True)
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
        print(f"{t['directoryCount']} lakes, reviewed {t['reviewedCount']}, purposes {n}, structural cap {structural_cap(t['lakes'])}")
        return 0
    now = now or dt.datetime.now(dt.timezone.utc)
    if not args.research_folder:
        print("REFUSED: --research-folder (or SECTOR_RESEARCH_ROOT) is required: the run binding lives in the research folder", file=sys.stderr)
        return 2
    if args.cmd == "register-evidence":
        try:
            return register_evidence(args, rules, digest, now)
        except LedgerRefused as ex:
            print(f"REFUSED: {ex}", file=sys.stderr)
            return 2
    if now < not_before(rules):  # every networked subcommand; the fetcher enforces it again on each request
        print(f"REFUSED: no networked subcommand may run before {rules['notBefore']} ({rules['notBeforeReason']})", file=sys.stderr)
        return 2
    try:
        return run_bound(args, rules, digest, now, transport, sleep)
    except LedgerRefused as ex:
        print(f"REFUSED: {ex}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
