#!/usr/bin/env python3
"""Weather Brain retrospective validation: read-only runner for protocol WX-RETRO-2026-11-23 (gaps WX-001, WX-002).

The protocol (docs/brains/weather-retro-validation/WX-RETRO-2026-11-23.protocol.json) amends WEATHER_BRAIN_PLAN.md section 5 to grade
the same criteria on a PAST window. It was pre-registered and hashed before any data was fetched. This runner replays the Brain's own
pure logic (sector_weather.reading.assemble, sector_weather.signal.evaluate) on archived station reports. It only reads public sources and
writes local files under --out. It never writes Firebase or any database, never changes a score, rubric, knowledge release or schedule.

    verify            check the protocol's sha256 against the committed sidecar
    fetch-stations    lake directory + NWS /points and station lists (the Brain's own station selection)
    fetch-asos        IEM ASOS/AWOS archive per station for the protocol window, plus the last 7 days for the substitution check
    fetch-nws-recent  NWS observation API, last 7 days, per Brain station (substitution check R-SUB)
    fetch-fronts      WPC coded surface bulletins (CODSUS) from the IEM text-product archive
    grade             offline: R-SUB, R-5.1, R-5.2, R-5.3 -> report.json (labels INTERNAL_EXPERIMENTAL, NOT_FOR_CUSTOMERS)
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import io
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
for _p in (os.path.join(REPO, "brains", "weather", "runtime"), os.path.join(REPO, "jobs", "brain_platform")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sector_weather import contract as C  # noqa: E402
from sector_weather.nws import LAYER_PCT, Obs, decode_observations, decode_point, decode_stations, weather_code, PRECIP_CODES  # noqa: E402,F401
from sector_weather.publish import _miles  # noqa: E402
from sector_weather.reading import assemble, tendency  # noqa: E402
from sector_weather.signal import evaluate  # noqa: E402

PROTOCOL = os.path.join(REPO, "docs", "brains", "weather-retro-validation", "WX-RETRO-2026-11-23.protocol.json")
LABELS = ["INTERNAL_EXPERIMENTAL", "NOT_FOR_CUSTOMERS", "RETROSPECTIVE"]
ALLOWED_HOSTS = {"api.weather.gov", "mesonet.agron.iastate.edu", "sector-engine-e43utajroa-uc.a.run.app"}
ENGINE = "https://sector-engine-e43utajroa-uc.a.run.app"
IEM_ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
IEM_AFOS = "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py"
NWS = "https://api.weather.gov"
USER_AGENT = os.environ.get("SECTOR_WEATHER_USER_AGENT") or "Sector-WeatherRetroValidation/0.1 (io.sector.co; read-only public data)"
KT_TO_MPH = 1.150779
INDEPENDENT_MAX_MI = 25.0
FRONT_MAX_MI = 50.0
FRONT_TYPES = ("COLD", "WARM", "OCFNT")
FRONT_KEYWORDS = ("HIGHS", "LOWS", "COLD", "WARM", "STNRY", "OCFNT", "TROF")
MI_PER_DEG_LAT = 69.05


# ----------------------------------------------------------------------------------------------------------------- protocol
def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: str) -> str:
    with open(path, "rb") as fh:
        return sha256_bytes(fh.read())


def tree_sha256(root: str) -> str | None:
    """sha256-tree-v1 (Cortex research.md RS-02): sha256 of sorted '<sha256>  <relpath>\\n' lines."""
    if not root or not os.path.isdir(root):
        return None
    lines = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x != "__pycache__"]
        for f in files:
            if f == ".DS_Store":
                continue
            p = os.path.join(d, f)
            lines.append(f"{sha256_file(p)}  {os.path.relpath(p, root).replace(os.sep, '/')}\n")
    return sha256_bytes("".join(sorted(lines)).encode())


def load_protocol(path: str = PROTOCOL) -> tuple[dict, str]:
    """Load the protocol and refuse it unless its sha256 equals the committed sidecar (pre-registration is immutable)."""
    digest = sha256_file(path)
    side = path + ".sha256"
    if not os.path.exists(side):
        raise SystemExit(f"REFUSED: no committed hash sidecar {os.path.basename(side)}")
    expected = open(side, encoding="utf-8").read().split()[0]
    if digest != expected:
        raise SystemExit(f"REFUSED: protocol sha256 {digest} != pre-registered {expected}")
    return json.load(open(path, encoding="utf-8")), digest


def ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)


def window(p: dict, name: str) -> tuple[datetime, datetime]:
    w = p["windows"][name]
    return ts(w["from"]), ts(w["to"])


def instants(frm: datetime, to: datetime) -> list[datetime]:
    """Every hour at HH:10:00Z in [frm, to) (protocol windows.evaluationInstants)."""
    t = frm.replace(minute=10, second=0, microsecond=0)
    if t < frm:
        t += timedelta(hours=1)
    out = []
    while t < to:
        out.append(t)
        t += timedelta(hours=1)
    return out


# ----------------------------------------------------------------------------------------------------------------- network (fetch only)
class Http:
    def __init__(self, pace_s: float = 1.0, timeout: float = 60.0, attempts: int = 4, opener=None):
        self.pace, self.timeout, self.attempts = pace_s, timeout, attempts
        self._open = opener or urllib.request.urlopen
        self._last = 0.0
        self.requests = 0

    def get(self, url: str, accept: str = "*/*") -> bytes:
        host = urllib.parse.urlparse(url).hostname
        if urllib.parse.urlparse(url).scheme != "https" or host not in ALLOWED_HOSTS:
            raise SystemExit(f"REFUSED: host not allowlisted by the protocol: {host}")
        err = None
        for n in range(self.attempts):
            wait = self._last + self.pace - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
                with self._open(req, timeout=self.timeout) as r:
                    return r.read()
            except Exception as e:                                    # retried, then raised: never a silent empty result
                code = getattr(e, "code", None)
                if code == 404:
                    raise FileNotFoundError(url) from None
                err = repr(e)
            time.sleep(2 * 2 ** n)
        raise RuntimeError(f"{err} after {self.attempts} attempts: {url}")


def _save(path: str, data: bytes, prov: list, source: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data)
    prov.append({"file": os.path.basename(path), "source": source, "sha256": sha256_bytes(data), "bytes": len(data),
                 "fetchedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})


def _write_prov(out: str, prov: list) -> None:
    with open(os.path.join(out, "provenance.json"), "w") as fh:
        json.dump({"labels": LABELS, "items": prov}, fh, indent=1)


# ----------------------------------------------------------------------------------------------------------------- stations
def select_stations(lake: dict, stations: list[dict]) -> dict:
    """The Brain's 3 stations (publish.resolve_point: NWS order, first MAX_STATIONS) and the independent candidates: every other listed
    station within 25 mi of the lake point, nearest first (protocol stationSelection)."""
    brain = stations[: C.MAX_STATIONS]
    ids = {s["id"] for s in brain}
    cands = []
    for s in stations:
        if s["id"] in ids:
            continue
        d = _miles(lake["lat"], lake["lon"], s.get("lat"), s.get("lon"))
        if d is not None and d <= INDEPENDENT_MAX_MI:
            cands.append({"id": s["id"], "name": s.get("name"), "distanceMi": d})
    cands.sort(key=lambda s: (s["distanceMi"], s["id"]))
    return {"brainStations": [{"id": s["id"], "name": s.get("name"), "distanceMi": _miles(lake["lat"], lake["lon"], s.get("lat"), s.get("lon"))}
                              for s in brain], "candidates": cands}


def cmd_fetch_stations(a) -> int:
    http = Http(pace_s=0.25)
    if a.directory:
        raw = open(a.directory, "rb").read()
    else:
        raw = http.get(f"{ENGINE}/lakes", "application/json")
    directory = json.loads(raw)["lakes"]
    ids = [x for x in (a.lakes or "").split(",") if x]
    lakes = [l for l in directory if not ids or l["id"] in ids]
    if a.limit:
        lakes = lakes[: a.limit]
    out = []
    for lake in lakes:
        e = {"id": lake["id"], "lat": lake["lat"], "lon": lake["lon"]}
        try:
            pt = decode_point(json.loads(http.get(f"{NWS}/points/{lake['lat']:.4f},{lake['lon']:.4f}", "application/geo+json")))
            if pt is None:
                e.update(status="ERROR", reason="points response without a grid")
            else:
                st = decode_stations(json.loads(http.get(pt.observation_stations, "application/geo+json")))
                e.update(status="OK", gridpoint=pt.gridpoint, nwsStationCount=len(st), **select_stations(lake, st))
        except FileNotFoundError:
            e.update(status="BLOCKED", reason="outside NWS coverage (/points 404)")
        except RuntimeError as err:
            e.update(status="ERROR", reason=str(err)[:200])
        out.append(e)
    os.makedirs(a.out, exist_ok=True)
    doc = {"labels": LABELS, "createdAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "directory": {"count": len(directory), "sha256": sha256_bytes(raw)}, "subset": bool(ids or a.limit), "lakes": out}
    with open(os.path.join(a.out, "stations.json"), "w") as fh:
        json.dump(doc, fh, indent=1)
    print(json.dumps({"lakes": len(out), "status": {s: sum(1 for x in out if x["status"] == s) for s in ("OK", "BLOCKED", "ERROR")},
                      "requests": http.requests, "subset": doc["subset"]}))
    return 0


def station_sets(stations_doc: dict) -> tuple[list[str], list[str]]:
    brain, cand = set(), set()
    for l in stations_doc["lakes"]:
        if l.get("status") == "OK":
            brain.update(s["id"] for s in l["brainStations"])
            cand.update(s["id"] for s in l["candidates"])
    return sorted(brain), sorted(cand - brain)


# ----------------------------------------------------------------------------------------------------------------- IEM archive adapter
def iem_id(nws_id: str) -> str:
    return nws_id[1:] if len(nws_id) == 4 and nws_id.startswith("K") else nws_id


def iem_params(station: str, frm: datetime, to: datetime) -> list[tuple[str, str]]:
    q = [("station", iem_id(station))]
    q += [("data", d) for d in ("tmpf", "dwpf", "relh", "drct", "sknt", "alti", "mslp", "p01i", "skyc1", "skyc2", "skyc3", "skyc4", "wxcodes")]
    q += [("year1", str(frm.year)), ("month1", str(frm.month)), ("day1", str(frm.day)), ("hour1", str(frm.hour)), ("minute1", str(frm.minute)),
          ("year2", str(to.year)), ("month2", str(to.month)), ("day2", str(to.day)), ("hour2", str(to.hour)), ("minute2", str(to.minute)),
          ("tz", "Etc/UTC"), ("format", "onlycomma"), ("latlon", "no"), ("elev", "no"), ("missing", "null"), ("trace", "0.0001"),
          ("direct", "no"), ("report_type", "3"), ("report_type", "4")]
    return q


def cmd_fetch_asos(a) -> int:
    p, _ = load_protocol()
    doc = json.load(open(a.stations))
    brain, cand = station_sets(doc)
    frm, to = ts(p["windows"]["archiveFetch"]["from"]), ts(p["windows"]["archiveFetch"]["to"])
    http, prov = Http(pace_s=1.0), []
    for s in brain + cand:
        url = IEM_ASOS + "?" + urllib.parse.urlencode(iem_params(s, frm, to))
        _save(os.path.join(a.out, "window", f"{s}.csv"), http.get(url, "text/csv"), prov, url)
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    for s in brain:                                                    # R-SUB: the same 7 days the NWS API still serves
        url = IEM_ASOS + "?" + urllib.parse.urlencode(iem_params(s, now - timedelta(days=7), now))
        _save(os.path.join(a.out, "recent", f"{s}.csv"), http.get(url, "text/csv"), prov, url)
    _write_prov(a.out, prov)
    print(json.dumps({"stations": len(brain) + len(cand), "requests": http.requests}))
    return 0


def cmd_fetch_nws_recent(a) -> int:
    doc = json.load(open(a.stations))
    brain, _ = station_sets(doc)
    http, prov = Http(pace_s=0.25), []
    start = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
    for s in brain:
        url = f"{NWS}/stations/{urllib.parse.quote(s)}/observations?start={start}&limit=500"
        try:
            _save(os.path.join(a.out, f"{s}.json"), http.get(url, "application/geo+json"), prov, url)
        except (FileNotFoundError, RuntimeError) as e:
            prov.append({"file": f"{s}.json", "source": url, "error": str(e)[:200]})
    _write_prov(a.out, prov)
    print(json.dumps({"stations": len(brain), "requests": http.requests}))
    return 0


def cmd_fetch_fronts(a) -> int:
    p, _ = load_protocol()
    frm, to = ts(p["windows"]["frontFetch"]["from"]), ts(p["windows"]["frontFetch"]["to"])
    http, prov = Http(pace_s=1.0), []
    url = IEM_AFOS + "?" + urllib.parse.urlencode({"pil": "CODSUS", "sdate": frm.strftime("%Y-%m-%d"),
                                                   "edate": (to + timedelta(days=1)).strftime("%Y-%m-%d"), "limit": "9999", "fmt": "text"})
    _save(os.path.join(a.out, "codsus.txt"), http.get(url, "text/plain"), prov, url)
    _write_prov(a.out, prov)
    print(json.dumps({"requests": http.requests}))
    return 0


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


WX_ROWS = (
    (lambda t: "TS" in t, lambda i: "Thunderstorm"),
    (lambda t: "FZRA" in t or "FZDZ" in t, lambda i: "Freezing Rain"),
    (lambda t: "PL" in t, lambda i: "Ice Pellets"),
    (lambda t: "SN" in t or "SG" in t, lambda i: f"{i}Snow"),
    (lambda t: "SH" in t and "RA" in t, lambda i: f"{i}Rain Showers"),
    (lambda t: "RA" in t, lambda i: f"{i}Rain"),
    (lambda t: "DZ" in t, lambda i: f"{i}Drizzle"),
    (lambda t: "UP" in t, lambda i: "Unknown Precipitation"),
    (lambda t: "FG" in t, lambda i: "Fog"),
    (lambda t: "BR" in t or "HZ" in t, lambda i: "Mist"),
)


def wx_text(wxcodes: str | None) -> str | None:
    """METAR present-weather codes -> NWS textDescription wording (protocol archiveAdapter.wxcodesToText)."""
    for tok in (wxcodes or "").split():
        inten = "Light " if tok.startswith("-") else ("Heavy " if tok.startswith("+") else "")
        body = tok.lstrip("+-")
        for match, text in WX_ROWS:
            if match(body):
                return text(inten)
    return None


def parse_iem_csv(text: str, station: str) -> list[Obs]:
    """IEM asos.py 'onlycomma' rows -> the Brain's Obs (protocol archiveAdapter.mapping), newest first."""
    rows = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    out = []
    for r in csv.DictReader(io.StringIO("\n".join(rows))):
        try:
            at = datetime.strptime(r["valid"].strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except (KeyError, ValueError, AttributeError):
            continue
        sknt, alti = _f(r.get("sknt")), _f(r.get("alti"))
        layers = [LAYER_PCT.get(str(r.get(k) or "").strip().upper()) for k in ("skyc1", "skyc2", "skyc3", "skyc4")]
        layers = [x for x in layers if x is not None]
        wx = r.get("wxcodes")
        wx = None if wx in (None, "", "null", "M") else wx
        out.append(Obs(station=station, at=at, text=wx_text(wx), icon=None, temp_f=_f(r.get("tmpf")), dew_f=_f(r.get("dwpf")),
                       rh=_f(r.get("relh")), wind_mph=None if sknt is None else sknt * KT_TO_MPH, wind_dir=_f(r.get("drct")),
                       slp_hpa=_f(r.get("mslp")), alt_hpa=None if alti is None else alti / C.HPA_TO_INHG,
                       precip_1h_in=_f(r.get("p01i")), layer_pct=max(layers) if layers else None))
    out.sort(key=lambda o: o.at, reverse=True)
    return out


class Series:
    """One station's archived reports, indexed by time."""

    def __init__(self, obs: list[Obs]):
        self.asc = sorted(obs, key=lambda o: o.at)
        self.times = [o.at for o in self.asc]
        self.by_at = {o.at: o for o in self.asc}

    def __len__(self):
        return len(self.asc)

    def lookback(self, now: datetime, hours: float = C.OBS_LOOKBACK_HOURS) -> list[Obs]:
        """What the Brain's observation request would return at `now`: [now - 13 h, now], newest first."""
        i = bisect.bisect_left(self.times, now - timedelta(hours=hours))
        j = bisect.bisect_right(self.times, now)
        return self.asc[i:j][::-1]

    def between(self, a: datetime, b: datetime) -> list[Obs]:
        return self.asc[bisect.bisect_left(self.times, a): bisect.bisect_right(self.times, b)]

    def nearest(self, t: datetime, tol_min: float, has) -> Obs | None:
        c = [o for o in self.between(t - timedelta(minutes=tol_min), t + timedelta(minutes=tol_min)) if has(o)]
        return min(c, key=lambda o: (abs((o.at - t).total_seconds()), o.at)) if c else None


class Archive:
    def __init__(self, root: str | None):
        self.root, self._c = root, {}

    def get(self, station: str) -> Series:
        if station not in self._c:
            f = os.path.join(self.root or "", f"{station}.csv")
            self._c[station] = Series(parse_iem_csv(open(f, encoding="utf-8").read(), station) if os.path.exists(f) else [])
        return self._c[station]


# ----------------------------------------------------------------------------------------------------------------- fronts (CODSUS)
VALID_RE = re.compile(r"^VALID\s+(\d{2})(\d{2})(\d{2})Z")


def parse_codsus(text: str, around: datetime) -> dict:
    """-> {valid time: {'eligible': bool, 'fronts': [(type, [(lat, lon), ...])]}}. The last bulletin for a VALID time wins. High resolution
    (7-digit) coordinates only; a bulletin with any 4-5 digit coordinate is ineligible (protocol FRONT_PASSAGE.resolution)."""
    out, cur, feat, centres = {}, None, None, True

    def coord(tok):
        if len(tok) == 7:
            return int(tok[:3]) / 10.0, -int(tok[3:]) / 10.0
        return None

    for raw in text.splitlines():
        line = raw.strip()
        m = VALID_RE.match(line)
        if m:
            mo, dd, hh = int(m.group(1)), int(m.group(2)), int(m.group(3))
            best = None
            for y in (around.year - 1, around.year, around.year + 1):
                try:
                    t = datetime(y, mo, dd, hh, tzinfo=timezone.utc)
                except ValueError:
                    continue
                if best is None or abs(t - around) < abs(best - around):
                    best = t
            cur = {"eligible": True, "fronts": []}
            if best is not None:
                out[best] = cur                                          # a later bulletin for the same VALID time replaces it
            feat, centres = None, True
            continue
        if cur is None or not line:
            continue
        toks = line.split()
        if toks[0] in FRONT_KEYWORDS:
            centres = toks[0] in ("HIGHS", "LOWS")                       # pressure + position pairs: not front geometry
            feat = [toks[0], []] if toks[0] in FRONT_TYPES else None
            if feat is not None:
                cur["fronts"].append(feat)
            nums = toks[1:]
        elif toks[0].isdigit():
            nums = toks                                                  # continuation of the current line's feature
        else:
            feat, centres = None, True
            continue
        if centres:
            continue
        for tok in nums:
            if not tok.isdigit():
                continue                                                 # WK / MDT / STG
            if len(tok) in (2, 3, 4, 5):
                cur["eligible"] = False
            c = coord(tok)
            if c and feat is not None:
                feat[1].append(c)
    return {t: {"eligible": v["eligible"], "fronts": [(k, pts) for k, pts in v["fronts"] if pts]} for t, v in out.items()}


def dist_to_polyline_mi(lat: float, lon: float, pts: list[tuple[float, float]]) -> float:
    kx = MI_PER_DEG_LAT * math.cos(math.radians(lat))
    xy = [((p[1] - lon) * kx, (p[0] - lat) * MI_PER_DEG_LAT) for p in pts]
    if len(xy) == 1:
        return math.hypot(*xy[0])
    best = float("inf")
    for (x1, y1), (x2, y2) in zip(xy, xy[1:]):
        dx, dy = x2 - x1, y2 - y1
        L = dx * dx + dy * dy
        t = 0.0 if L == 0 else max(0.0, min(1.0, -(x1 * dx + y1 * dy) / L))
        best = min(best, math.hypot(x1 + t * dx, y1 + t * dy))
    return best


def front_episodes(lat: float, lon: float, analyses: dict) -> list[tuple[datetime, datetime]]:
    """Consecutive eligible analyses (3 h apart) with a COLD/WARM/OCFNT front within 50 mi of the lake: [(first, last)]."""
    near = sorted(t for t, a in analyses.items() if a["eligible"]
                  and any(dist_to_polyline_mi(lat, lon, pts) <= FRONT_MAX_MI for _, pts in a["fronts"]))
    eps = []
    for t in near:
        if eps and t - eps[-1][1] <= timedelta(hours=3, minutes=1):
            eps[-1][1] = t
        else:
            eps.append([t, t])
    return [(a, b) for a, b in eps]


# ----------------------------------------------------------------------------------------------------------------- grading helpers
def merge_events(times: list[datetime], gap_h: float = 2.0) -> list[datetime]:
    kept = []
    for t in sorted(set(times)):
        if not kept or t - kept[-1] > timedelta(hours=gap_h):
            kept.append(t)
    return kept


def rain_onsets(series: Series, frm: datetime, to: datetime, mp: float) -> list[datetime]:
    out = []
    for o in series.between(frm, to):
        if o.precip_1h_in is None or o.precip_1h_in < mp:
            continue
        prior = series.between(o.at - timedelta(hours=3), o.at - timedelta(seconds=1))
        if any(x.precip_1h_in is not None for x in prior) and not any(x.precip_1h_in is not None and x.precip_1h_in >= mp for x in prior):
            out.append(o.at)
    return out


def _band(d):
    return "lt10mi" if d is not None and d < 10 else "10to25mi"


def _rate(n, d):
    return None if not d else round(n / d, 4)


def _sufficient(n, lakes, n_min, lakes_min):
    return n >= n_min and lakes >= lakes_min


def grade_pod_far(det, n_truth, hits, n_brain, lakes, pod_min, far_max, n_min=30, lakes_min=10) -> dict:
    pod, far = _rate(det, n_truth), _rate(n_brain - hits, n_brain)
    if not (n_truth >= n_min and n_brain >= n_min and lakes >= lakes_min):
        res = "INSUFFICIENT"
    else:
        res = "PASS" if pod >= pod_min and far <= far_max else "FAIL"
    return {"result": res, "POD": pod, "FAR": far, "truthEvents": n_truth, "detected": det, "brainEvents": n_brain, "hits": hits,
            "lakes": lakes, "marks": {"POD>=": pod_min, "FAR<=": far_max}}


def substitution_check(brain_stations: list[str], recent: Archive, nws_dir: str | None) -> dict:
    if not nws_dir or not os.path.isdir(nws_dir):
        return {"result": "NOT_GRADED", "reason": "no NWS API data supplied (fetch-nws-recent)"}
    n_nws = matched = 0
    agree = {"temperature": [0, 0], "pressure": [0, 0], "precipitation": [0, 0]}
    for s in brain_stations:
        f = os.path.join(nws_dir, f"{s}.json")
        if not os.path.exists(f):
            continue
        nws = decode_observations(json.load(open(f)))
        ser = recent.get(s)
        for o in nws:
            n_nws += 1
            m = ser.nearest(o.at, 2, lambda x: True)
            if m is None:
                continue
            matched += 1
            if o.temp_f is not None and m.temp_f is not None:
                agree["temperature"][1] += 1
                agree["temperature"][0] += abs(o.temp_f - m.temp_f) <= 0.2
            if o.alt_hpa is not None and m.alt_hpa is not None:
                agree["pressure"][1] += 1
                agree["pressure"][0] += abs(o.alt_hpa - m.alt_hpa) <= 0.35
            if o.precip_1h_in is not None and m.precip_1h_in is not None:
                agree["precipitation"][1] += 1
                agree["precipitation"][0] += (o.precip_1h_in >= 0.01) == (m.precip_1h_in >= 0.01)
    rates = {k: _rate(*v) for k, v in agree.items()}
    cov = _rate(matched, n_nws)
    ok = cov is not None and cov >= 0.95 and all(rates[k] is not None and rates[k] >= 0.99 for k in rates)
    return {"result": "PASS" if ok else ("NOT_GRADED" if not n_nws else "FAIL"), "nwsReports": n_nws, "matched": matched, "coverage": cov,
            "agreement": rates, "pairs": {k: v[1] for k, v in agree.items()},
            "marks": {"coverage>=": 0.95, "temperature>=": 0.99, "pressure>=": 0.99, "precipitation>=": 0.99}}


# ----------------------------------------------------------------------------------------------------------------- grade
def grade(p: dict, stations_doc: dict, asos_dir: str, nws_dir: str | None = None, fronts_text: str | None = None) -> dict:
    T = C.THRESHOLDS
    protocol_id = p["protocolId"]                                        # `p` is reused below for the Brain's pressure reading
    w60, w30, w14 = window(p, "changeSignal_5_3"), window(p, "representativeness_5_2"), window(p, "fidelity_5_1")
    arch = Archive(os.path.join(asos_dir, "window"))
    recent = Archive(os.path.join(asos_dir, "recent"))
    analyses = parse_codsus(fronts_text, w60[0] + (w60[1] - w60[0]) / 2) if fronts_text else {}
    fronts_ok = any(a["eligible"] for a in analyses.values())
    excluded = {"BLOCKED": 0, "ERROR": 0, "NO_INDEPENDENT_STATION": 0, "NO_PRECIP_SENSOR": 0}
    fid = {"values": 0, "match": 0, "provenance": 0, "mismatches": [], "lakes": set()}
    rep = {"pressure": [], "trend": [], "temp": [], "slpOnlyExcluded": 0, "trendNullExcluded": 0}
    rain = {"truth": 0, "truthAll": 0, "det": 0, "detAll": 0, "brain": 0, "hits": 0, "lakes": set()}
    front = {"truth": 0, "truthAll": 0, "det": 0, "detAll": 0, "brain": 0, "hits": 0, "lakes": set()}
    change_hours, graded = {}, []
    hp_steady = C.TREND_3H_STEADY_INHG / C.HPA_TO_INHG

    for lake in stations_doc["lakes"]:
        if lake.get("status") != "OK":
            excluded["BLOCKED" if lake.get("status") == "BLOCKED" else "ERROR"] += 1
            continue
        lid = lake["id"]
        ind = next((c for c in lake["candidates"] if len(arch.get(c["id"]).between(*w60))), None)
        if ind is None:
            excluded["NO_INDEPENDENT_STATION"] += 1                      # still graded for R-5.1 (fidelity needs no independent station)
        else:
            graded.append(lid)
        sids = [s["id"] for s in lake["brainStations"]]
        ser = {s: arch.get(s) for s in sids}
        iser = arch.get(ind["id"]) if ind else None
        band = _band(ind["distanceMi"]) if ind else None
        seen = set()
        ev = {"RAIN_ONSET": [], "FRONT_PASSAGE": []}
        evaluable = {"RAIN_ONSET": [], "FRONT_PASSAGE": []}
        n_change = 0
        for now in instants(*w60):
            rd = assemble(sids, {s: ser[s].lookback(now) for s in sids}, None, now)
            sig = evaluate(rd)
            n_change += sig["level"] == "CHANGE"
            for e in sig["events"]:
                if e["kind"] in ev:
                    ev[e["kind"]].append(ts(e["at"]))
            if not any(u.startswith("rainOnset") for u in sig["unknown"]):
                evaluable["RAIN_ONSET"].append(now)
            if not any(u.startswith("front:") for u in sig["unknown"]):
                evaluable["FRONT_PASSAGE"].append(now)
            p, tv = rd.pressure, rd.values.get("airTemperatureF")
            # R-5.1 fidelity: each distinct published value checked once against its own station's archive row
            if w14[0] <= now < w14[1]:
                if p and ("p", p.get("station"), p.get("at")) not in seen:
                    seen.add(("p", p.get("station"), p.get("at")))
                    fid["values"] += 1
                    fid["lakes"].add(lid)
                    ok_prov = bool(p.get("station") and p.get("at"))
                    fid["provenance"] += ok_prov
                    row = ser.get(p.get("station"), Series([])).by_at.get(p.get("at")) if ok_prov else None
                    off = p.get("seaLevelOffsetHPa")
                    if off is None and p["kind"] == "seaLevel":
                        good = row is not None and row.slp_hpa is not None and abs(p["hPa"] - row.slp_hpa) <= 0.05
                    else:
                        good = row is not None and row.alt_hpa is not None and abs(p["hPa"] - (off or 0.0) - row.alt_hpa) <= 0.05
                    fid["match"] += good
                    if not good and len(fid["mismatches"]) < 20:
                        fid["mismatches"].append({"lake": lid, "tile": "pressure", "station": p.get("station"), "at": C.iso(p.get("at"))})
                if tv and tv.get("origin") == "observation" and ("t", tv.get("station"), tv.get("at")) not in seen:
                    seen.add(("t", tv.get("station"), tv.get("at")))
                    fid["values"] += 1
                    fid["lakes"].add(lid)
                    ok_prov = bool(tv.get("station") and tv.get("at"))
                    fid["provenance"] += ok_prov
                    row = ser.get(tv.get("station"), Series([])).by_at.get(tv.get("at")) if ok_prov else None
                    good = row is not None and row.temp_f is not None and abs(tv["value"] - row.temp_f) <= 0.1
                    fid["match"] += good
                    if not good and len(fid["mismatches"]) < 20:
                        fid["mismatches"].append({"lake": lid, "tile": "airTemperature", "station": tv.get("station"), "at": C.iso(tv.get("at"))})
            # R-5.2 representativeness
            if iser is not None and w30[0] <= now < w30[1]:
                if p and ("rp", p["station"], p["at"]) not in seen:
                    seen.add(("rp", p["station"], p["at"]))
                    if p.get("seaLevelOffsetHPa") is None and p["kind"] == "seaLevel":
                        rep["slpOnlyExcluded"] += 1
                    else:
                        raw = p["hPa"] - (p.get("seaLevelOffsetHPa") or 0.0)
                        io_ = iser.nearest(p["at"], 30, lambda o: o.alt_hpa is not None)
                        if io_ is not None:
                            rep["pressure"].append({"lake": lid, "err": abs(raw - io_.alt_hpa), "kind": p["kind"], "band": band})
                            ind_series = [(o.at, o.alt_hpa) for o in iser.between(io_.at - timedelta(hours=5), io_.at) if o.alt_hpa is not None]
                            it3 = tendency(io_.alt_hpa, io_.at, ind_series, 3, hp_steady)
                            bt3 = p.get("trend3h")
                            if it3 is None or bt3 is None:
                                rep["trendNullExcluded"] += 1
                            else:
                                rep["trend"].append({"lake": lid, "agree": it3["trend"] == bt3["trend"], "kind": p["kind"], "band": band})
                if tv and tv.get("origin") == "observation" and ("rt", tv["station"], tv["at"]) not in seen:
                    seen.add(("rt", tv["station"], tv["at"]))
                    io_ = iser.nearest(tv["at"], 30, lambda o: o.temp_f is not None)
                    if io_ is not None:
                        rep["temp"].append({"lake": lid, "err": abs(tv["value"] - io_.temp_f), "band": band})
        if iser is None:
            continue
        change_hours[lid] = round(n_change / ((w60[1] - w60[0]).total_seconds() / (7 * 86400)), 2)

        # R-5.3 rain onset
        tol = timedelta(hours=2)
        has_precip = any(o.precip_1h_in is not None for o in iser.between(*w60))
        if not has_precip:
            excluded["NO_PRECIP_SENSOR"] += 1
        else:
            bev = [t for t in merge_events(ev["RAIN_ONSET"]) if w60[0] <= t < w60[1]]
            truth = rain_onsets(iser, w60[0], w60[1], T["measurablePrecipIn"])
            wet = [o.at for o in iser.between(w60[0] - tol, w60[1] + tol) if o.precip_1h_in is not None and o.precip_1h_in >= T["measurablePrecipIn"]]
            rain["brain"] += len(bev)
            rain["hits"] += sum(any(abs(t - x) <= tol for x in wet) for t in bev)
            for t in truth:
                d = any(abs(t - b) <= tol for b in bev)
                rain["truthAll"] += 1
                rain["detAll"] += d
                if any(abs(t - x) <= tol for x in evaluable["RAIN_ONSET"]):
                    rain["truth"] += 1
                    rain["det"] += d
            if bev or truth:
                rain["lakes"].add(lid)
        # R-5.3 front passage
        if fronts_ok:
            tol3 = timedelta(hours=3)
            bev = [t for t in merge_events(ev["FRONT_PASSAGE"]) if w60[0] <= t < w60[1]]
            eps = [(a, b) for a, b in front_episodes(lake["lat"], lake["lon"], analyses) if b >= w60[0] and a < w60[1]]
            front["brain"] += len(bev)
            front["hits"] += sum(any(a - tol3 <= t <= b + tol3 for a, b in eps) for t in bev)
            for a, b in eps:
                d = any(a - tol3 <= t <= b + tol3 for t in bev)
                front["truthAll"] += 1
                front["detAll"] += d
                if any(a - tol3 <= x <= b + tol3 for x in evaluable["FRONT_PASSAGE"]):
                    front["truth"] += 1
                    front["det"] += d
            if bev or eps:
                front["lakes"].add(lid)

    # ---- results
    subset = bool(stations_doc.get("subset"))
    sub = substitution_check(sorted({s["id"] for l in stations_doc["lakes"] if l.get("status") == "OK" for s in l["brainStations"]}),
                             recent, nws_dir)

    n_f = fid["values"]
    r51 = {"values": n_f, "lakes": len(fid["lakes"]), "matchShare": _rate(fid["match"], n_f), "provenanceShare": _rate(fid["provenance"], n_f),
           "mismatchesFirst20": fid["mismatches"], "marks": {"match>=": 0.995, "provenance": 1.0}}
    if not _sufficient(n_f, r51["lakes"], 500, 20):
        r51["result"] = "INSUFFICIENT"
    else:
        r51["result"] = "PASS" if r51["matchShare"] >= 0.995 and fid["provenance"] == n_f else "FAIL"

    def mae(rows, key="err"):
        return None if not rows else round(sum(r[key] for r in rows) / len(rows), 3)

    def share(rows):
        return None if not rows else round(sum(r["agree"] for r in rows) / len(rows), 4)

    def metric(rows, fn, ok):
        lakes = len({r["lake"] for r in rows})
        v = fn(rows)
        res = "INSUFFICIENT" if not _sufficient(len(rows), lakes, 500, 20) else ("PASS" if ok(v) else "FAIL")
        by = {}
        for dim in ("kind", "band"):
            for val in sorted({r[dim] for r in rows if dim in r}):
                sub_rows = [r for r in rows if r.get(dim) == val]
                by[f"{dim}={val}"] = {"value": fn(sub_rows), "pairs": len(sub_rows)}
        return {"result": res, "value": v, "pairs": len(rows), "lakes": lakes, "breakdown": by}

    r52 = {"pressureMAE_hPa": metric(rep["pressure"], mae, lambda v: v <= 1.0),
           "trend3hAgreement": metric(rep["trend"], share, lambda v: v >= 0.80),
           "airTempMAE_F": metric(rep["temp"], mae, lambda v: v <= 3.0),
           "excluded": {"slpOnlyBrainValues": rep["slpOnlyExcluded"], "trendNull": rep["trendNullExcluded"]}}
    parts = [r52[k]["result"] for k in ("pressureMAE_hPa", "trend3hAgreement", "airTempMAE_F")]
    r52["result"] = "FAIL" if "FAIL" in parts else ("INSUFFICIENT" if "INSUFFICIENT" in parts else "PASS")

    ro = grade_pod_far(rain["det"], rain["truth"], rain["hits"], rain["brain"], len(rain["lakes"]), 0.8, 0.3)
    ro["secondaryAllTruth"] = {"truthEvents": rain["truthAll"], "detected": rain["detAll"], "POD": _rate(rain["detAll"], rain["truthAll"])}
    if fronts_ok:
        fp = grade_pod_far(front["det"], front["truth"], front["hits"], front["brain"], len(front["lakes"]), 0.6, 0.4)
        fp["secondaryAllTruth"] = {"truthEvents": front["truthAll"], "detected": front["detAll"], "POD": _rate(front["detAll"], front["truthAll"])}
        fp["eligibleAnalyses"] = sum(1 for a in analyses.values() if a["eligible"])
    else:
        fp = {"result": "NOT_GRADED", "reason": "no eligible high-resolution coded surface bulletin in the window" if fronts_text
              else "no front bulletins supplied (fetch-fronts)"}
    parts = [ro["result"], fp["result"]]
    r53 = {"RAIN_ONSET": ro, "FRONT_PASSAGE": fp,
           "result": "FAIL" if "FAIL" in parts else ("PASS" if parts == ["PASS", "PASS"] else
                                                     ("NOT_GRADED" if "NOT_GRADED" in parts else "INSUFFICIENT")),
           "changeHoursPerLakePerWeek": {"median": _median(list(change_hours.values())), "max": max(change_hours.values(), default=None),
                                         "lakes": len(change_hours)}}

    qualifiers = (["SUBSET"] if subset else []) + ([] if sub["result"] == "PASS" else ["SUBSTITUTION_UNCERTAIN"])
    for r in (r51, r52, r53):
        r["computedResult"] = r["result"]
        if subset and r["result"] in ("PASS", "FAIL"):
            r["result"] = "NOT_GRADED"
        elif "SUBSTITUTION_UNCERTAIN" in qualifiers and r["result"] == "PASS":
            r["result"] = "NOT_GRADED"
    return {"labels": LABELS, "protocolId": protocol_id, "qualifiers": qualifiers,
            "lakes": {"inStationsFile": len(stations_doc["lakes"]), "gradedFor5_2and5_3": len(graded), "excluded": excluded},
            "R-SUB": sub, "R-5.1": r51, "R-5.2": r52, "R-5.3": r53,
            "note": "Evidence for /validation/weather only; writes nothing, sets no status, changes no score (protocol resultStates.rubricMapping)."}


def _median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else round((xs[m - 1] + xs[m]) / 2, 2)


def cmd_grade(a) -> int:
    p, digest = load_protocol()
    stations_doc = json.load(open(a.stations))
    fronts = open(a.fronts, encoding="utf-8", errors="replace").read() if a.fronts else None
    rep = grade(p, stations_doc, a.asos, a.nws, fronts)
    rep["protocolSha256"] = digest
    rep["release"] = C.RELEASE.get("releaseId")
    rep["thresholdsVersion"] = C.THRESHOLDS_VERSION
    rep["inputs"] = {"stations.json": sha256_file(a.stations), "asos": tree_sha256(a.asos), "nws": tree_sha256(a.nws) if a.nws else None,
                     "fronts": sha256_file(a.fronts) if a.fronts else None}
    rep["gradedAt"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(rep, fh, indent=1, sort_keys=True, default=str)
    print(json.dumps({k: rep[k]["result"] for k in ("R-SUB", "R-5.1", "R-5.2", "R-5.3")} | {"qualifiers": rep["qualifiers"], "report": a.out}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("verify")
    s = sp.add_parser("fetch-stations")
    s.add_argument("--out", required=True)
    s.add_argument("--directory")
    s.add_argument("--lakes", default="")
    s.add_argument("--limit", type=int, default=0)
    for name in ("fetch-asos", "fetch-nws-recent"):
        s = sp.add_parser(name)
        s.add_argument("--stations", required=True)
        s.add_argument("--out", required=True)
    s = sp.add_parser("fetch-fronts")
    s.add_argument("--out", required=True)
    s = sp.add_parser("grade")
    s.add_argument("--stations", required=True)
    s.add_argument("--asos", required=True)
    s.add_argument("--nws")
    s.add_argument("--fronts")
    s.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        _, d = load_protocol()
        print(f"OK protocol sha256 {d}")
        return 0
    return {"fetch-stations": cmd_fetch_stations, "fetch-asos": cmd_fetch_asos, "fetch-nws-recent": cmd_fetch_nws_recent,
            "fetch-fronts": cmd_fetch_fronts, "grade": cmd_grade}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
