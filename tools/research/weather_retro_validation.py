#!/usr/bin/env python3
"""Weather Brain retrospective validation: read-only runner for protocol WX-RETRO-2026-11-23.5 (gaps WX-001, WX-002).

The protocol (docs/brains/weather-retro-validation/WX-RETRO-2026-11-23.5.protocol.json; .4, .3, .2 and v1 are SUPERSEDED, refused and never run) amends WEATHER_BRAIN_PLAN.md section 5 to grade
the same criteria on a PAST window. It was pre-registered and hashed before any data was fetched. This runner replays the Brain's own
pure logic (sector_weather.reading.assemble, sector_weather.signal.evaluate) on archived station reports. It only reads public sources and
writes local files only inside the run folder (--run) and, through the shared protocol run ledger (protocol_run_ledger.py, #251), the
ledger under the Weather research root. It never writes Firebase or any database, never changes a score, rubric, knowledge release or schedule.

    verify            check the protocol's sha256 against the committed sidecar
    ledger-anchor     --run R: open the run ledger and print the anchor text; post it on Sector_Ops #51 BEFORE any other step
    fetch-stations    --run R: lake directory + NWS /points and station lists (the Brain's own station selection) -> R/stations/
    fetch-asos        --run R: IEM ASOS/AWOS archive per station for the protocol window -> R/asos/
    fetch-recent      --run R: per station, back to back, IEM archive and NWS observation API for the last 7 days -> R/recent/
    fetch-fronts      --run R: WPC coded surface bulletins (CODSUS) from the IEM text-product archive -> R/fronts/
    bind              --run R: write-once R/run-manifest.json and ledger bind_inputs for grade; NO comparison
    grade             --run R: check_inputs + exact disk match; begin, wait for the posted `Run start:`, grade, complete, wait for the
                      posted `Run result:`; writes R/report.json and R/ledger-audit.json
Every step is a ledger step with the fixed key 'directory' and runs once (protocol runLedger). Every run-folder output is write-once; the
station list comes only from R/stations/stations.json.
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
import uuid
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
for _p in (HERE, os.path.join(REPO, "brains", "weather", "runtime"), os.path.join(REPO, "jobs", "brain_platform")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from sector_weather import contract as C  # noqa: E402
from sector_weather.nws import LAYER_PCT, Obs, decode_observations, decode_point, decode_stations, weather_code, PRECIP_CODES  # noqa: E402,F401
from sector_weather.publish import _miles  # noqa: E402
from sector_weather.reading import assemble, tendency  # noqa: E402
from sector_weather.signal import evaluate  # noqa: E402
import protocol_run_ledger as PRL  # noqa: E402  (shared run ledger, #251)

PROTOCOL = os.path.join(REPO, "docs", "brains", "weather-retro-validation", "WX-RETRO-2026-11-23.5.protocol.json")
EXPECTED_PROTOCOL_ID = "WX-RETRO-2026-11-23.5"
SUPERSEDED_SHA256 = {"6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8",   # WX-RETRO-2026-11-23
                     "01eac7bc56033154dcf64ee365826a0da1c4d33cd921cec7ec76e79df48eb58c",   # WX-RETRO-2026-11-23.2
                     "492c1befe2707ce559c5999da7931548e69728c9fffadf16524813efdb5ec7c7",   # WX-RETRO-2026-11-23.3
                     "55f850efe9ebd6dc972df59152667b99a5c49dc26cd87263b049c4ea3e9f314d"}   # WX-RETRO-2026-11-23.4
LABELS = ["INTERNAL_EXPERIMENTAL", "NOT_FOR_CUSTOMERS", "RETROSPECTIVE"]
ALLOWED_HOSTS = {"api.weather.gov", "mesonet.agron.iastate.edu", "sector-engine-e43utajroa-uc.a.run.app"}
ENGINE = "https://sector-engine-e43utajroa-uc.a.run.app"
IEM_ASOS = "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"
IEM_AFOS = "https://mesonet.agron.iastate.edu/cgi-bin/afos/retrieve.py"
NWS = "https://api.weather.gov"
USER_AGENT = os.environ.get("SECTOR_WEATHER_USER_AGENT") or "Sector-WeatherRetroValidation/0.5 (io.sector.co; read-only public data)"
KT_TO_MPH = 1.150779
INDEPENDENT_MAX_MI = 25.0
FRONT_MAX_MI = 50.0
FRONT_TYPES = ("COLD", "WARM", "OCFNT")
FRONT_KEYWORDS = ("HIGHS", "LOWS", "COLD", "WARM", "STNRY", "OCFNT", "TROF")
MI_PER_DEG_LAT = 69.05
MIN_SEPARATION_MI = 3.0
COVERAGE_MIN = 0.75                                                    # protocol exclusionsCountAgainst.minimum
CRITERIA = ("R-5.1R", "R-5.2", "RAIN_ONSET", "FRONT_PASSAGE")
# protocol runLedger: the declared result step, the ledger's Brain folder and the one key every step uses (fixed, never derived)
RESULT_STEPS = frozenset({"grade"})                                     # bind is not result-defining: it never compares values
LEDGER_BRAIN = "weather"
KEY = "directory"
FETCH_STEPS = {"stations": "fetch-stations", "asos": "fetch-asos", "recent": "fetch-recent", "fronts": "fetch-fronts"}
POLL_S = 30                                                             # wait between confirm retries ("not listed yet": never repost)


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
    """Load the protocol and refuse it unless its sha256 equals the committed sidecar (pre-registration is immutable), it is the current
    protocol id, and it is neither marked SUPERSEDED nor a superseded hash (protocol supersedesRule)."""
    digest = sha256_file(path)
    side = path + ".sha256"
    if not os.path.exists(side):
        raise SystemExit(f"REFUSED: no committed hash sidecar {os.path.basename(side)}")
    expected = open(side, encoding="utf-8").read().split()[0]
    if digest != expected:
        raise SystemExit(f"REFUSED: protocol sha256 {digest} != pre-registered {expected}")
    p = json.load(open(path, encoding="utf-8"))
    if digest in SUPERSEDED_SHA256 or str(p.get("status", "")).upper() == "SUPERSEDED":
        raise SystemExit(f"REFUSED: protocol {p.get('protocolId')} ({digest[:12]}) is SUPERSEDED")
    if p.get("protocolId") != EXPECTED_PROTOCOL_ID:
        raise SystemExit(f"REFUSED: protocol id {p.get('protocolId')!r} is not {EXPECTED_PROTOCOL_ID!r}")
    return p, digest


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
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError(f"REFUSED redirect {code} to {newurl[:120]} (protocol execution.http)")


def _default_opener():
    return urllib.request.build_opener(_NoRedirect()).open


class Http:
    def __init__(self, pace_s: float = 1.0, timeout: float = 60.0, attempts: int = 4, opener=None):
        self.pace, self.timeout, self.attempts = pace_s, timeout, attempts
        self._open = opener or _default_opener()
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
                if "REFUSED redirect" in str(e):
                    raise RuntimeError(str(e)) from None
                err = repr(e)
            time.sleep(2 * 2 ** n)
        raise RuntimeError(f"{err} after {self.attempts} attempts: {url}")


_SAVED = [0]                                                           # files saved by the running step (in-memory count)


def _save(root: str, rel: str, data: bytes, prov: list, source: str, **extra) -> None:
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _SAVED[0] += 1                                                     # counted before the write: a partial file is a saved file
    with open(path, "wb") as fh:
        fh.write(data)
    prov.append({"file": rel, "source": source, "sha256": sha256_bytes(data), "bytes": len(data), "fetchedAt": _now_iso(), **extra})


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_prov(out: str, prov: list) -> None:
    with open(os.path.join(out, "provenance.json"), "w") as fh:
        json.dump({"labels": LABELS, "items": prov}, fh, indent=1)


# ----------------------------------------------------------------------------------------------------------------- stations
def select_stations(lake: dict, stations: list[dict]) -> dict:
    """The Brain's 3 stations (publish.resolve_point: NWS order, first MAX_STATIONS) and the independent candidates: every other listed
    station within 25 mi of the lake point and at least 3 mi from every Brain station, nearest to the lake first (protocol stationSelection)."""
    brain = stations[: C.MAX_STATIONS]
    ids = {s["id"] for s in brain}
    cands = []
    for s in stations:
        if s["id"] in ids:
            continue
        d = _miles(lake["lat"], lake["lon"], s.get("lat"), s.get("lon"))
        if d is None or d > INDEPENDENT_MAX_MI:
            continue
        sep = [_miles(s.get("lat"), s.get("lon"), b.get("lat"), b.get("lon")) for b in brain]
        if any(x is None for x in sep):
            continue
        if min(sep, default=INDEPENDENT_MAX_MI) < MIN_SEPARATION_MI:
            continue                                                     # co-located with a Brain station: not independent
        cands.append({"id": s["id"], "name": s.get("name"), "distanceMi": d, "distanceToBrainStationMi": min(sep, default=None)})
    cands.sort(key=lambda s: (s["distanceMi"], s["id"]))
    return {"brainStations": [{"id": s["id"], "name": s.get("name"), "lat": s.get("lat"), "lon": s.get("lon"),
                               "distanceMi": _miles(lake["lat"], lake["lon"], s.get("lat"), s.get("lon"))} for s in brain],
            "candidates": cands}


STAGES = ("stations", "asos", "recent", "fronts")
MANIFEST = "run-manifest.json"
REPORT = "report.json"


def _new_stage(run: str, stage: str) -> str:
    """Write-once: a stage folder is created by exactly one fetch; an existing one is refused (protocol binding.runFolder)."""
    d = os.path.join(run, stage)
    try:
        os.makedirs(d, exist_ok=False)
    except FileExistsError:
        raise SystemExit(f"REFUSED: {d} exists; every run output is write-once, and the run ledger lets each step complete once. A step "
                         f"aborted before it saved any file removes its empty folder and may be retried here; a step that saved a file "
                         f"stays STARTED (terminal): recovery needs a new protocol id AND a revised protocol document recorded in a #51 "
                         f"human review") from None
    return d


def load_stations(run: str) -> tuple[dict, str]:
    """stations/stations.json, refused unless its sha256 equals the one fetch-stations recorded."""
    f = os.path.join(run, "stations", "stations.json")
    prov = _load_prov(os.path.join(run, "stations"))
    rec = next((x for x in prov or [] if x.get("file") == "stations.json"), None)
    if not os.path.exists(f) or rec is None:
        raise SystemExit("REFUSED: no stations/stations.json with a provenance record (run fetch-stations first)")
    digest = sha256_file(f)
    if digest != rec.get("sha256"):
        raise SystemExit(f"REFUSED: stations.json sha256 {digest} != recorded {rec.get('sha256')}")
    return json.load(open(f)), digest


def open_ledger(run: str) -> "PRL.Ledger":
    """The protocol's run ledger (protocol runLedger.open). Tests replace this function; runners never pass another root."""
    _, digest = load_protocol()
    return PRL.Ledger.for_brain(LEDGER_BRAIN, EXPECTED_PROTOCOL_ID, digest, repo=REPO, forbid_under=[run], result_steps=RESULT_STEPS,
                                cortex_home=os.environ.get(PRL.ENV_CORTEX))


def _completed_outputs(L, step: str) -> dict:
    """Outputs of the COMPLETED non-result ledger step (step, KEY); refused when the step has not completed."""
    done = [e for e in L.entries() if e["step"] == step and e["key"] == KEY and e["status"] == PRL.COMPLETED]
    if not done:
        raise SystemExit(f"REFUSED: ledger step {step}/{KEY} has not completed; run it first")
    return done[0]["outputs"]


def _require_stage(L, run: str, stage: str) -> str:
    """The stage folder's sha256-tree, refused unless it equals the output its fetch step completed with in the ledger."""
    want = _completed_outputs(L, FETCH_STEPS[stage]).get(stage)
    have = PRL.sha256_tree(os.path.join(run, stage))
    if have != want:
        raise SystemExit(f"REFUSED: {stage}/ is {have}, but {FETCH_STEPS[stage]} completed with {want}")
    return have


def _has_files(path: str) -> bool:
    if os.path.isfile(path):
        return True
    return any(files for _, _, files in os.walk(path)) if os.path.isdir(path) else False


def _ledger_step(run: str, step: str, inputs: dict, work, out_path: str) -> int:
    """A non-result ledger step: begin (anchor checked by the ledger), work, complete with the output hash.

    On an exception (including an interrupt) before complete:
      * nothing saved yet (no file under ``out_path`` AND the in-memory save count is 0): the attempt is aborted before any result, the
        empty stage folder is removed, and the step may be retried (the ledger gives it the next attempt number);
      * a file was saved: the attempt is left STARTED, which the ledger treats as terminal. A retry would refetch a moving 7-day window
        and could change FETCH_FAILED / COVERAGE_FLOOR flags, so it is never allowed: recovery needs a new protocol id AND a revised
        protocol document recorded in a #51 human review."""
    L = open_ledger(run)
    L.begin(step, KEY, args={}, inputs=inputs)
    _SAVED[0] = 0
    try:
        outputs = work()
    except BaseException as e:
        if _SAVED[0] == 0 and not _has_files(out_path):
            L.abort_before_result(step, KEY, f"{type(e).__name__} before any file was saved: {e}"[:500])
            if os.path.isdir(out_path):
                os.rmdir(out_path)                                       # empty: created by this attempt, nothing in it
        else:
            print(f"TERMINAL: {step} saved {_SAVED[0]} file(s) under {out_path} before {type(e).__name__}; the ledger attempt stays "
                  f"STARTED and this step can never run again under {EXPECTED_PROTOCOL_ID}. Recovery needs a new protocol id AND a "
                  f"revised protocol document recorded in a #51 human review. Do not delete or edit the run folder.", file=sys.stderr)
        raise
    L.complete(step, KEY, outputs=outputs)
    return 0


def cmd_ledger_anchor(a) -> int:
    L = open_ledger(a.run)
    print(L.post_anchor_text())
    return 0


def cmd_fetch_stations(a) -> int:
    load_protocol()
    if os.path.exists(os.path.join(a.run, "stations")):
        raise SystemExit(f"REFUSED: {a.run}/stations exists; every run output is write-once")
    return _ledger_step(a.run, "fetch-stations", {}, lambda: _fetch_stations(a.run), os.path.join(a.run, "stations"))


def _fetch_stations(run: str) -> dict:
    d = _new_stage(run, "stations")
    http = Http(pace_s=0.25)
    raw = http.get(f"{ENGINE}/lakes", "application/json")
    src = f"{ENGINE}/lakes"
    body = json.loads(raw)
    directory = body["lakes"]
    lakes = list(directory)
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
    count = body.get("count", len(directory))
    doc = {"labels": LABELS, "createdAt": _now_iso(), "directory": {"count": count, "listed": len(directory), "sha256": sha256_bytes(raw),
                                                                  "source": src},
           "subset": len(out) != count, "lakes": out}
    prov = []
    _save(d, "stations.json", json.dumps(doc, indent=1).encode(), prov, src)
    _write_prov(d, prov)
    print(json.dumps({"lakes": len(out), "status": {s: sum(1 for x in out if x["status"] == s) for s in ("OK", "BLOCKED", "ERROR")},
                      "requests": http.requests, "subset": doc["subset"]}))
    return {"stations": PRL.Path(d)}


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
    load_protocol()
    doc, _ = load_stations(a.run)
    if os.path.exists(os.path.join(a.run, "asos")):
        raise SystemExit(f"REFUSED: {a.run}/asos exists; every run output is write-once")
    L = open_ledger(a.run)
    _require_stage(L, a.run, "stations")
    return _ledger_step(a.run, "fetch-asos", {"stations": PRL.Path(a.run, "stations")} | {"stations.json": PRL.Path(a.run, "stations", "stations.json")},
                        lambda: _fetch_asos(a.run), os.path.join(a.run, "asos"))


def _fetch_asos(run: str) -> dict:
    p, _ = load_protocol()
    doc, _ = load_stations(run)
    d = _new_stage(run, "asos")
    brain, cand = station_sets(doc)
    frm, to = ts(p["windows"]["archiveFetch"]["from"]), ts(p["windows"]["archiveFetch"]["to"])
    http, prov = Http(pace_s=1.0), []
    for s in brain + cand:
        url = IEM_ASOS + "?" + urllib.parse.urlencode(iem_params(s, frm, to))
        try:
            _save(d, f"window/{s}.csv", http.get(url, "text/csv"), prov, url, station=s, kind="window")
        except (FileNotFoundError, RuntimeError) as e:
            prov.append({"file": f"window/{s}.csv", "station": s, "kind": "window", "source": url, "error": str(e)[:200], "fetchedAt": _now_iso()})
    _write_prov(d, prov)
    print(json.dumps({"stations": len(brain) + len(cand), "errors": sum(1 for x in prov if "error" in x), "requests": http.requests}))
    return {"asos": PRL.Path(d)}


def cmd_fetch_recent(a) -> int:
    load_protocol()
    doc, _ = load_stations(a.run)
    if os.path.exists(os.path.join(a.run, "recent")):
        raise SystemExit(f"REFUSED: {a.run}/recent exists; every run output is write-once")
    L = open_ledger(a.run)
    _require_stage(L, a.run, "stations")
    return _ledger_step(a.run, "fetch-recent", {"stations": PRL.Path(a.run, "stations")} | {"stations.json": PRL.Path(a.run, "stations", "stations.json")},
                        lambda: _fetch_recent(a.run), os.path.join(a.run, "recent"))


def _fetch_recent(run: str) -> dict:
    """R-SUB inputs, per station back to back: the IEM archive and the NWS observation API for the same last 7 days (protocol
    substitutionCheck.data). Stations come only from the run's stations.json. Every fetch time and every error is recorded."""
    load_protocol()
    doc, _ = load_stations(run)
    d = _new_stage(run, "recent")
    brain, cand = station_sets(doc)
    iem_http, nws_http, prov = Http(pace_s=1.0), Http(pace_s=0.25), []
    for s in brain + cand:
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        url = IEM_ASOS + "?" + urllib.parse.urlencode(iem_params(s, now - timedelta(days=7), now))
        try:
            _save(d, f"iem/{s}.csv", iem_http.get(url, "text/csv"), prov, url, station=s, kind="iem")
        except (FileNotFoundError, RuntimeError) as e:
            prov.append({"file": f"iem/{s}.csv", "station": s, "kind": "iem", "source": url, "error": str(e)[:200], "fetchedAt": _now_iso()})
        start = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        url = f"{NWS}/stations/{urllib.parse.quote(s)}/observations?start={start}&limit=500"
        try:
            _save(d, f"nws/{s}.json", nws_http.get(url, "application/geo+json"), prov, url, station=s, kind="nws")
        except (FileNotFoundError, RuntimeError) as e:
            prov.append({"file": f"nws/{s}.json", "station": s, "kind": "nws", "source": url, "error": str(e)[:200], "fetchedAt": _now_iso()})
    _write_prov(d, prov)
    print(json.dumps({"stations": len(brain) + len(cand), "errors": sum(1 for x in prov if "error" in x),
                      "requests": iem_http.requests + nws_http.requests}))
    return {"recent": PRL.Path(d)}


def cmd_fetch_fronts(a) -> int:
    load_protocol()
    doc, _ = load_stations(a.run)
    if os.path.exists(os.path.join(a.run, "fronts")):
        raise SystemExit(f"REFUSED: {a.run}/fronts exists; every run output is write-once")
    L = open_ledger(a.run)
    _require_stage(L, a.run, "stations")
    return _ledger_step(a.run, "fetch-fronts", {"stations": PRL.Path(a.run, "stations")} | {"stations.json": PRL.Path(a.run, "stations", "stations.json")},
                        lambda: _fetch_fronts(a.run), os.path.join(a.run, "fronts"))


def _fetch_fronts(run: str) -> dict:
    p, _ = load_protocol()
    load_stations(run)
    d = _new_stage(run, "fronts")
    frm, to = ts(p["windows"]["frontFetch"]["from"]), ts(p["windows"]["frontFetch"]["to"])
    http, prov = Http(pace_s=1.0), []
    url = IEM_AFOS + "?" + urllib.parse.urlencode({"pil": "CODSUS", "sdate": frm.strftime("%Y-%m-%d"),
                                                   "edate": (to + timedelta(days=1)).strftime("%Y-%m-%d"), "limit": "9999", "fmt": "text", "order": "asc"})
    try:
        _save(d, "codsus.txt", http.get(url, "text/plain"), prov, url, kind="fronts")
    except (FileNotFoundError, RuntimeError) as e:
        prov.append({"file": "codsus.txt", "kind": "fronts", "source": url, "error": str(e)[:200], "fetchedAt": _now_iso()})
    _write_prov(d, prov)
    print(json.dumps({"requests": http.requests, "errors": sum(1 for x in prov if "error" in x)}))
    return {"fronts": PRL.Path(d)}


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else x


WX_ROWS = (                                                            # (predicate(body, vicinity), text(intensity)); earliest row wins
    (lambda b, vc: not vc and "TS" in b, lambda i: "Thunderstorm"),
    (lambda b, vc: not vc and ("FZRA" in b or "FZDZ" in b), lambda i: "Freezing Rain"),
    (lambda b, vc: not vc and "PL" in b, lambda i: "Ice Pellets"),
    (lambda b, vc: not vc and ("SN" in b or "SG" in b), lambda i: f"{i}Snow"),
    (lambda b, vc: not vc and "SH" in b and "RA" in b, lambda i: f"{i}Rain Showers"),
    (lambda b, vc: not vc and "RA" in b, lambda i: f"{i}Rain"),
    (lambda b, vc: not vc and "DZ" in b, lambda i: f"{i}Drizzle"),
    (lambda b, vc: not vc and "UP" in b, lambda i: "Unknown Precipitation"),
    (lambda b, vc: vc and "TS" in b, lambda i: "Thunderstorm in Vicinity"),
    (lambda b, vc: vc and "SH" in b, lambda i: "Showers in Vicinity"),
    (lambda b, vc: not vc and "FG" in b, lambda i: "Fog"),
    (lambda b, vc: vc and "FG" in b, lambda i: "Fog in Vicinity"),
    (lambda b, vc: not vc and ("BR" in b or "HZ" in b), lambda i: "Mist"),
)


def wx_text(wxcodes: str | None) -> str | None:
    """METAR present-weather codes -> NWS textDescription wording (protocol archiveAdapter.wxcodesToText): the token that matches the
    EARLIEST row wins, whatever its position ('BR -RA' -> 'Light Rain'); VC tokens match only the vicinity rows."""
    best = None
    for tok in (wxcodes or "").split():
        inten = "Light " if tok.startswith("-") else ("Heavy " if tok.startswith("+") else "")
        body = tok.lstrip("+-")
        vc = body.startswith("VC")
        body = body[2:] if vc else body
        for n, (match, text) in enumerate(WX_ROWS):
            if match(body, vc):
                if best is None or n < best[0]:
                    best = (n, text(inten))
                break
    return best[1] if best else None


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
HEADING_RE = re.compile(r"^[A-Z]{4}\d{2}\s+[A-Z]{4}\s+(\d{2})(\d{2})(\d{2})")


def _near_year(mo: int, dd: int, hh: int, mi: int, around: datetime) -> datetime | None:
    best = None
    for y in (around.year - 1, around.year, around.year + 1):
        try:
            t = datetime(y, mo, dd, hh, mi, tzinfo=timezone.utc)
        except ValueError:
            continue
        if best is None or abs(t - around) < abs(best - around):
            best = t
    return best


def parse_codsus(text: str, around: datetime) -> dict:
    """-> {valid time: {'eligible', 'fronts': [(type, [(lat, lon), ...])], 'issued'}}. Per VALID time the bulletin with the latest issuance
    (WMO heading DDHHMM) wins, whatever the archive's order; a bulletin without a heading ranks below, then by position. Product separators
    ('000', a WMO heading, the PIL line, the title line, SOH/ETX) end the bulletin in progress. High resolution (7-digit) coordinates only; a
    front line with a 2-5 digit coordinate makes its bulletin ineligible (protocol FRONT_PASSAGE.resolution)."""
    found, cur, feat, centres, issue, pos = {}, None, None, True, None, 0

    for raw in text.splitlines():
        line = raw.strip().strip("\x01\x03").strip()
        hm = HEADING_RE.match(line)
        if line == "000" or hm or line == "CODSUS" or line.startswith("CODED SURFACE") or "\x01" in raw or "\x03" in raw:
            cur, feat, centres = None, None, True
            if hm:
                issue = tuple(int(x) for x in hm.groups())
            elif line == "000" or "\x01" in raw:
                issue = None
            continue
        m = VALID_RE.match(line)
        if m:
            vt = _near_year(int(m.group(1)), int(m.group(2)), int(m.group(3)), 0, around)
            cur, feat, centres, pos = None, None, True, pos + 1
            if vt is None:
                continue
            issued = None
            if issue:
                dd, hh, mi = issue
                for mo_shift in (0, -1, 1):
                    mo = (vt.month - 1 + mo_shift) % 12 + 1
                    cand = _near_year(mo, dd, hh, mi, vt) if 1 <= dd <= 31 else None
                    if cand is not None and abs(cand - vt) <= timedelta(days=5):
                        issued = cand
                        break
            cur = {"eligible": True, "fronts": [], "issued": issued, "rank": (issued is not None, issued or vt, pos)}
            found.setdefault(vt, []).append(cur)
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
            if len(tok) == 7 and feat is not None:
                feat[1].append((int(tok[:3]) / 10.0, -int(tok[3:]) / 10.0))
    out = {}
    for vt, bulls in found.items():
        b = max(bulls, key=lambda x: x["rank"])
        out[vt] = {"eligible": b["eligible"], "fronts": [(k, pts) for k, pts in b["fronts"] if pts], "issued": b["issued"],
                   "bulletins": len(bulls)}
    return out


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
    """POD over ALL truth events (the plan's; protocol PODpopulation PRIMARY), FAR over judgeable Brain events."""
    pod, far = _rate(det, n_truth), _rate(n_brain - hits, n_brain)
    if not (n_truth >= n_min and n_brain >= n_min and lakes >= lakes_min):
        res = "INSUFFICIENT"
    else:
        res = "PASS" if pod >= pod_min and far <= far_max else "FAIL"
    return {"result": res, "POD": pod, "FAR": far, "truthEvents": n_truth, "detected": det, "brainEvents": n_brain, "hits": hits,
            "lakes": lakes, "marks": {"POD>=": pod_min, "FAR<=": far_max}, "PODpopulation": "all truth events (misses without Brain data count)"}


SUB_FIELDS = {                                                         # metric -> (Obs attribute, tolerance) for value + null agreement
    "temperature": ("temp_f", 0.2), "dewPoint": ("dew_f", 0.2), "pressure": ("alt_hpa", 0.35), "seaLevelPressure": ("slp_hpa", 0.15),
    "windSpeed": ("wind_mph", 1.2), "windDirection": ("wind_dir", 5.0), "precipitation": ("precip_1h_in", None)}
WET_METRICS = ("wetPrecipitation", "wetPresentWeatherPresence")
SUB_GATES = {"R-5.1R": ["temperature", "pressure", "seaLevelPressure"], "R-5.2": ["temperature", "pressure", "seaLevelPressure"],
             "R-5.3.RAIN_ONSET": ["precipitation", "presentWeatherPresence", "wetPrecipitation", "wetPresentWeatherPresence"],
             "R-5.3.FRONT_PASSAGE": ["windSpeed", "windDirection", "pressure", "seaLevelPressure", "temperature", "dewPoint"]}
SUB_MIN_PAIRS, SUB_VALUE_MIN, SUB_NULL_MIN, SUB_COVERAGE_MIN = 1000, 0.99, 0.98, 0.95
WET_MIN_PAIRS, WET_VALUE_MIN = 200, 0.95
STATION_MIN_REPORTS, STATION_COVERAGE_FLOOR = 20, 0.90
CONTEMPORANEITY = timedelta(hours=1)


def _ang(a, b):
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _present(icon, text) -> bool:
    return weather_code(icon, text, None) in PRECIP_CODES


def _load_prov(root: str) -> list | None:
    f = os.path.join(root or "", "provenance.json")
    return json.load(open(f)).get("items") if os.path.exists(f) else None


def substitution_check(stations: list[str], recent_dir: str, bound: dict) -> dict:
    """R-SUB metrics (protocol substitutionCheck): NWS API vs IEM archive for the last 7 days, per metric (value and null agreement) and
    wet-conditioned. Which stations exist, failed or are flagged, and whether R-SUB can be graded at all, come ONLY from the bound manifest
    (bind decided them before any comparison). Flagged stations still contribute their pairs; failed ones have none."""
    st = bound.get("stationStatus") or {}
    flagged = {s: v["flag"] for s, v in st.items() if v.get("flag")}
    sub_status = bound.get("substitution") or {}
    if sub_status.get("status") != "BOUND":
        return {"result": "NOT_GRADED", "reason": sub_status.get("reason", "not bound"), "metrics": {}, "flaggedStations": flagged}
    iem = Archive(os.path.join(recent_dir, "iem"))
    val = {k: [0, 0] for k in list(SUB_FIELDS) + ["presentWeatherPresence", "presentWeatherCode", *WET_METRICS]}
    nul = {k: [0, 0] for k in SUB_FIELDS}
    n_nws = matched = 0
    for s in stations:
        if (st.get(s) or {}).get("recentIem") != "OK" or (st.get(s) or {}).get("recentNws") != "OK":
            continue
        nws = decode_observations(json.load(open(os.path.join(recent_dir, "nws", f"{s}.json"))))
        ser = iem.get(s)
        for o in nws:
            n_nws += 1
            m = ser.nearest(o.at, 2, lambda x: True)
            if m is None:
                continue
            matched += 1
            for k, (attr, tol) in SUB_FIELDS.items():
                a, b = getattr(o, attr), getattr(m, attr)
                nul[k][1] += 1
                nul[k][0] += (a is None) == (b is None)
                if a is None or b is None:
                    continue
                if k == "windDirection":
                    if o.wind_mph is None or m.wind_mph is None or o.wind_mph < 5 or m.wind_mph < 5:
                        continue
                    ok = _ang(a, b) <= tol
                elif k == "precipitation":
                    ok = (a >= 0.01) == (b >= 0.01)
                else:
                    ok = abs(a - b) <= tol
                val[k][1] += 1
                val[k][0] += ok
            pa, pb = _present(o.icon, o.text), _present(None, m.text)
            val["presentWeatherPresence"][1] += 1
            val["presentWeatherPresence"][0] += pa == pb
            ca, cb = weather_code(o.icon, o.text, None), weather_code(None, m.text, None)
            if ca is not None and cb is not None:
                val["presentWeatherCode"][1] += 1
                val["presentWeatherCode"][0] += ca == cb
            wa = o.precip_1h_in is not None and o.precip_1h_in >= 0.01
            wb = m.precip_1h_in is not None and m.precip_1h_in >= 0.01
            if wa or wb or pa or pb:                                     # WET-CONDITIONED: either side shows precipitation
                val["wetPrecipitation"][1] += 1
                val["wetPrecipitation"][0] += wa == wb
                val["wetPresentWeatherPresence"][1] += 1
                val["wetPresentWeatherPresence"][0] += pa == pb
    metrics = {}
    for k, (n, d) in val.items():
        r = _rate(n, d)
        lo, mark = (WET_MIN_PAIRS, WET_VALUE_MIN) if k in WET_METRICS else (SUB_MIN_PAIRS, SUB_VALUE_MIN)
        res = "INSUFFICIENT" if d < lo else ("PASS" if r >= mark else "FAIL")
        e = {"value": {"result": res, "agreement": r, "pairs": d, "marks": {"agreement>=": mark, "minPairs": lo}}}
        if k in nul:
            rn = _rate(*nul[k])
            e["null"] = {"result": "INSUFFICIENT" if nul[k][1] < SUB_MIN_PAIRS else ("PASS" if rn >= SUB_NULL_MIN else "FAIL"),
                         "agreement": rn, "pairs": nul[k][1]}
        if k == "presentWeatherCode":
            e["note"] = "reported only, no gate"
        if k in WET_METRICS:
            e["note"] = "wet-conditioned: pairs where either side shows precipitation"
        metrics[k] = e
    cov = _rate(matched, n_nws)
    coverage = {"result": "NOT_GRADED" if not n_nws else ("PASS" if cov >= SUB_COVERAGE_MIN else "FAIL"), "share": cov,
                "nwsReports": n_nws, "matched": matched}
    gate_metrics = sorted({m for ms in SUB_GATES.values() for m in ms})
    ok_all = coverage["result"] == "PASS" and all(_metric_ok(metrics, m) for m in gate_metrics)
    return {"result": "PASS" if ok_all else ("NOT_GRADED" if not n_nws else "FAIL"), "coverage": coverage, "metrics": metrics,
            "flaggedStations": dict(sorted(flagged.items())),
            "marks": {"value>=": SUB_VALUE_MIN, "null>=": SUB_NULL_MIN, "coverage>=": SUB_COVERAGE_MIN, "minPairs": SUB_MIN_PAIRS,
                      "wet>=": WET_VALUE_MIN, "wetMinPairs": WET_MIN_PAIRS}}


# ----------------------------------------------------------------------------------------------------------------- bind (no comparison)
def _stage_files(run: str) -> dict:
    """relpath -> sha256 for every file in the four stage folders (the exact set grade requires on disk)."""
    out = {}
    for stage in STAGES:
        root = os.path.join(run, stage)
        for d, dirs, files in os.walk(root):
            dirs[:] = [x for x in dirs if x != "__pycache__"]
            for f in files:
                p = os.path.join(d, f)
                out[os.path.relpath(p, run).replace(os.sep, "/")] = sha256_file(p)
    return dict(sorted(out.items()))


def _fetch_status(run: str, stage: str, prov: list, station: str | None, kind: str, rel: str) -> str:
    """OK only with a record, no error, a fetchedAt and the file present with the recorded sha256; a hash mismatch REFUSES."""
    rec = [x for x in prov if x.get("kind") == kind and x.get("station") == station]
    if len(rec) != 1 or "error" in rec[0] or not rec[0].get("fetchedAt"):
        return "FETCH_FAILED"
    f = os.path.join(run, stage, rel)
    if not os.path.exists(f):
        return "FETCH_FAILED"
    if sha256_file(f) != rec[0].get("sha256"):
        raise SystemExit(f"REFUSED: {stage}/{rel} sha256 differs from its provenance record")
    return "OK"


def bind(p: dict, protocol_sha: str, run: str) -> dict:
    """The write-once binding (protocol designRule, binding): reads provenance, hashes, timestamps and row presence only. It never compares
    a Brain value with truth. Fixes the station list, every input file, every failure, each lake's exclusion or independent station, and the
    population of every criterion."""
    for stage in STAGES:
        if not os.path.isdir(os.path.join(run, stage)):
            raise SystemExit(f"REFUSED: stage {stage}/ missing; run every fetch step before bind")
    doc, stations_sha = load_stations(run)
    w60 = window(p, "changeSignal_5_3")
    provs = {stage: _load_prov(os.path.join(run, stage)) for stage in STAGES}
    for stage, pv in provs.items():
        if pv is None:
            raise SystemExit(f"REFUSED: {stage}/provenance.json missing")
        recorded = {f"{stage}/{x['file']}" for x in pv if "file" in x and "error" not in x}
        on_disk = {k for k in _stage_files(run) if k.startswith(stage + "/") and k != f"{stage}/provenance.json"}
        extra = sorted(on_disk - recorded)
        if extra:
            raise SystemExit(f"REFUSED: files with no provenance record: {extra[:5]}")
    brain, cand = station_sets(doc)
    status, times = {}, {}
    for s in brain + cand:
        e = {"window": _fetch_status(run, "asos", provs["asos"], s, "window", f"window/{s}.csv"),
             "recentIem": _fetch_status(run, "recent", provs["recent"], s, "iem", f"iem/{s}.csv"),
             "recentNws": _fetch_status(run, "recent", provs["recent"], s, "nws", f"nws/{s}.json"), "flag": None}
        if "FETCH_FAILED" in (e["window"], e["recentIem"], e["recentNws"]):
            e["flag"] = "FETCH_FAILED"
        else:
            t = {x["kind"]: ts(x["fetchedAt"]) for x in provs["recent"] if x.get("station") == s and x.get("kind") in ("iem", "nws")}
            times[s] = t
            nws_t = [o.at for o in decode_observations(json.load(open(os.path.join(run, "recent", "nws", f"{s}.json"))))]
            iem_s = Series(parse_iem_csv(open(os.path.join(run, "recent", "iem", f"{s}.csv"), encoding="utf-8").read(), s))
            hit = sum(1 for t_ in nws_t if iem_s.nearest(t_, 2, lambda x: True) is not None)       # timestamps only
            e["recentCoverage"] = _rate(hit, len(nws_t))
            if len(nws_t) >= STATION_MIN_REPORTS and e["recentCoverage"] < STATION_COVERAGE_FLOOR:
                e["flag"] = "COVERAGE_FLOOR"
        status[s] = e
    late = sorted(s for s, t in times.items() if abs(t["iem"] - t["nws"]) > CONTEMPORANEITY)
    substitution = ({"status": "NOT_GRADED", "reason": "FETCH_NOT_CONTEMPORANEOUS: archive and NWS fetches more than 1 h apart",
                     "stations": late[:50]} if late else {"status": "BOUND"})

    fr = [x for x in provs["fronts"] if x.get("kind") == "fronts"]
    fronts = {"status": "FETCH_FAILED"}
    if _fetch_status(run, "fronts", provs["fronts"], None, "fronts", "codsus.txt") == "OK" and len(fr) == 1:
        an = parse_codsus(open(os.path.join(run, "fronts", "codsus.txt"), encoding="utf-8", errors="replace").read(),
                          w60[0] + (w60[1] - w60[0]) / 2)
        n = sum(1 for t, a in an.items() if a["eligible"] and w60[0] - timedelta(hours=3) <= t <= w60[1] + timedelta(hours=3))
        fronts = {"status": "OK" if n else "NO_ELIGIBLE_ANALYSIS", "eligibleAnalyses": n}

    arch = Archive(os.path.join(run, "asos", "window"))
    lakes, population, exclusions = [], {c: 0 for c in CRITERIA}, {c: {} for c in CRITERIA}

    def exclude(crits, reason):
        for c in crits:
            exclusions[c][reason] = exclusions[c].get(reason, 0) + 1

    for lake in doc["lakes"]:
        e = {"id": lake["id"], "lat": lake["lat"], "lon": lake["lon"], "criteria": {c: False for c in CRITERIA}}
        if lake.get("status") != "OK":
            e["excluded"] = "BLOCKED" if lake.get("status") == "BLOCKED" else "ERROR"
            exclude(CRITERIA, e["excluded"])
            lakes.append(e)
            continue
        sids = [s["id"] for s in lake["brainStations"]]
        e["brainStations"] = sids
        flags = [status[s]["flag"] for s in sids if status[s]["flag"]]
        if flags:
            e["excluded"] = "SUBSTITUTION_FETCH_FAILED" if "FETCH_FAILED" in flags else "SUBSTITUTION_STATION"
            exclude(CRITERIA, e["excluded"])
            lakes.append(e)
            continue
        e["criteria"]["R-5.1R"] = True
        skipped, ind = [], None
        for c in lake["candidates"]:
            f = status[c["id"]]["flag"]
            if f:
                skipped.append({"id": c["id"], "reason": f})
            elif not len(arch.get(c["id"]).between(*w60)):
                skipped.append({"id": c["id"], "reason": "NO_ARCHIVE_ROWS_IN_WINDOW"})
            else:
                ind = c
                break
        e["skippedCandidates"] = skipped
        if ind is None:
            e["excludedFrom5_2and5_3"] = "NO_INDEPENDENT_STATION"
            exclude(("R-5.2", "RAIN_ONSET", "FRONT_PASSAGE"), "NO_INDEPENDENT_STATION")
        else:
            e["independent"] = {"id": ind["id"], "distanceMi": ind["distanceMi"], "distanceToBrainStationMi": ind.get("distanceToBrainStationMi")}
            e["criteria"]["R-5.2"] = True
            if any(o.precip_1h_in is not None for o in arch.get(ind["id"]).between(*w60)):
                e["criteria"]["RAIN_ONSET"] = True
            else:
                exclude(("RAIN_ONSET",), "NO_PRECIP_SENSOR")
            if fronts["status"] == "OK":
                e["criteria"]["FRONT_PASSAGE"] = True
            else:
                exclude(("FRONT_PASSAGE",), "FRONTS_" + fronts["status"])
        lakes.append(e)
    for e in lakes:
        for c in CRITERIA:
            population[c] += e["criteria"][c]
    directory_count = int(doc["directory"]["count"])
    return {"schema": "sector-weather-retro-run-manifest-v1", "protocolId": p["protocolId"], "protocolSha256": protocol_sha,
            "runId": str(uuid.uuid4()), "boundAt": _now_iso(), "labels": LABELS,
            "stationsSha256": stations_sha, "directoryCount": directory_count, "lakesInStations": len(doc["lakes"]),
            "subset": bool(doc.get("subset")) or len(doc["lakes"]) != directory_count,
            "files": _stage_files(run), "stationStatus": status, "substitution": substitution, "fronts": fronts,
            "population": population, "exclusions": exclusions, "lakes": lakes}


def verify_run(manifest: dict, protocol_sha: str, run: str) -> None:
    """grade's gate: the protocol is the bound one and the files on disk match the manifest EXACTLY (no change, no extra, no missing)."""
    if manifest.get("protocolSha256") != protocol_sha:
        raise SystemExit("REFUSED: run-manifest.json was bound under another protocol")
    disk = _stage_files(run)
    want = manifest.get("files") or {}
    if disk != want:
        diff = sorted(set(disk) ^ set(want)) + sorted(k for k in set(disk) & set(want) if disk[k] != want[k])
        raise SystemExit(f"REFUSED: files on disk differ from run-manifest.json: {diff[:5]}")
    _, sha = load_stations(run)
    if sha != manifest.get("stationsSha256"):
        raise SystemExit("REFUSED: stations.json differs from the bound one")


def _metric_ok(metrics: dict, name: str) -> bool:
    e = metrics.get(name)
    return bool(e) and e["value"]["result"] == "PASS" and ("null" not in e or e["null"]["result"] == "PASS")


def gates(sub: dict) -> dict:
    """criterion -> {'ok': bool, 'failed': [metric...]} from R-SUB (protocol substitutionCheck.gating)."""
    out = {}
    for crit, ms in SUB_GATES.items():
        bad = [m for m in ms if not _metric_ok(sub.get("metrics") or {}, m)]
        if (sub.get("coverage") or {}).get("result") != "PASS":
            bad.append("coverage")
        out[crit] = {"ok": not bad, "notPassing": bad}
    return out


def _spans(p: dict) -> list[tuple[set, datetime, datetime]]:
    return [(set(x["lakes"]), ts(x["from"]), ts(x["to"])) for x in p.get("excludedSpans") or []]


def grade(p: dict, manifest: dict, run: str) -> dict:
    """Grade a BOUND run (protocol designRule): the population, independent stations, exclusions and every input come from the manifest;
    nothing here adds or removes a lake. Every exclusion counts against the Brain through the per-criterion coverage minimum."""
    T = C.THRESHOLDS
    protocol_id = p["protocolId"]
    w60, w30, w14 = window(p, "changeSignal_5_3"), window(p, "representativeness_5_2"), window(p, "fidelity_5_1")
    spans = _spans(p)
    arch = Archive(os.path.join(run, "asos", "window"))
    fronts_ok = (manifest.get("fronts") or {}).get("status") == "OK"
    analyses = {}
    if fronts_ok:
        analyses = parse_codsus(open(os.path.join(run, "fronts", "codsus.txt"), encoding="utf-8", errors="replace").read(),
                                w60[0] + (w60[1] - w60[0]) / 2)
    eligible_times = sorted(t for t, a in analyses.items() if a["eligible"])

    sub_stations = sorted(manifest.get("stationStatus") or {})
    sub = substitution_check(sub_stations, os.path.join(run, "recent"), manifest)
    gate = gates(sub)

    span_excluded = {"instants": 0, "values": 0, "truthEvents": 0, "brainEvents": 0, "truthReports": 0}
    fid = {"values": 0, "match": 0, "provenance": 0, "mismatches": [], "lakes": set()}
    rep = {"pressure": [], "trend": [], "temp": [], "slpOnlyExcluded": 0, "truthNoReport": 0, "truthTrendNull": 0, "brainTrendNull": 0,
           "pressureTruthNoReport": 0, "tempTruthNoReport": 0, "availP": [0, 0], "availT": [0, 0]}
    rain = {"truth": 0, "det": 0, "truthEval": 0, "detEval": 0, "brain": 0, "hits": 0, "lakes": set()}
    front = {"truth": 0, "det": 0, "truthEval": 0, "detEval": 0, "brain": 0, "hits": 0, "unjudgeable": 0, "lakes": set()}
    change_hours, independents = {}, []
    hp_steady = C.TREND_3H_STEADY_INHG / C.HPA_TO_INHG

    for lake in manifest["lakes"]:
        crit = lake["criteria"]
        if not crit["R-5.1R"]:
            continue                                                     # excluded in bind; counted in manifest.exclusions
        lid = lake["id"]
        sids = lake["brainStations"]
        lake_spans = [(a, b) for ls, a, b in spans if lid in ls]

        def in_span(t, _sp=lake_spans):
            return t is not None and any(a <= t < b for a, b in _sp)

        ind = lake.get("independent") if crit["R-5.2"] else None
        if ind:
            independents.append({"lake": lid, "station": ind["id"], "distanceMi": ind["distanceMi"],
                                 "distanceToBrainStationMi": ind.get("distanceToBrainStationMi")})
        ser = {s: arch.get(s) for s in sids}
        iser = arch.get(ind["id"]) if ind else None
        band = _band(ind["distanceMi"]) if ind else None
        seen = set()
        ev = {"RAIN_ONSET": [], "FRONT_PASSAGE": []}
        evaluable = {"RAIN_ONSET": [], "FRONT_PASSAGE": []}
        n_change = n_inst = 0
        for now in instants(*w60):
            if in_span(now):
                span_excluded["instants"] += 1
                continue
            n_inst += 1
            rd = assemble(sids, {s: ser[s].lookback(now) for s in sids}, None, now)
            sig = evaluate(rd)
            n_change += sig["level"] == "CHANGE"
            for e in sig["events"]:
                if e["kind"] in ev:
                    t = ts(e["at"])
                    if in_span(t):
                        span_excluded["brainEvents"] += 1
                    else:
                        ev[e["kind"]].append(t)
            if not any(u.startswith("rainOnset") for u in sig["unknown"]):
                evaluable["RAIN_ONSET"].append(now)
            if not any(u.startswith("front:") for u in sig["unknown"]):
                evaluable["FRONT_PASSAGE"].append(now)
            pr, tv = rd.pressure, rd.values.get("airTemperatureF")
            p_span = t_span = False
            if pr is not None and in_span(pr.get("at")):
                span_excluded["values"] += 1
                pr, p_span = None, True
            if tv is not None and in_span(tv.get("at")):
                span_excluded["values"] += 1
                tv, t_span = None, True
            # R-5.1R replay self-consistency: each distinct published value checked once against its own station's archive row
            if w14[0] <= now < w14[1]:
                if pr and ("p", pr.get("station"), pr.get("at")) not in seen:
                    seen.add(("p", pr.get("station"), pr.get("at")))
                    fid["values"] += 1
                    fid["lakes"].add(lid)
                    ok_prov = bool(pr.get("station") and pr.get("at"))
                    fid["provenance"] += ok_prov
                    row = ser.get(pr.get("station"), Series([])).by_at.get(pr.get("at")) if ok_prov else None
                    off = pr.get("seaLevelOffsetHPa")
                    if off is None and pr["kind"] == "seaLevel":
                        good = row is not None and row.slp_hpa is not None and abs(pr["hPa"] - row.slp_hpa) <= 0.05
                    else:
                        good = row is not None and row.alt_hpa is not None and abs(pr["hPa"] - (off or 0.0) - row.alt_hpa) <= 0.05
                    fid["match"] += good
                    if not good and len(fid["mismatches"]) < 20:
                        fid["mismatches"].append({"lake": lid, "tile": "pressure", "station": pr.get("station"), "at": C.iso(pr.get("at"))})
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
                has_t = bool(tv and tv.get("origin") == "observation")
                if not p_span:                                            # Brain availability: every graded instant is in the denominator
                    rep["availP"][1] += 1
                    rep["availP"][0] += pr is not None
                if not t_span:
                    rep["availT"][1] += 1
                    rep["availT"][0] += has_t
                # trend: one pair per Brain pressure observation, and one per instant with NO Brain pressure (unknown counts against)
                trend_ref = None
                if pr and ("rp", pr["station"], pr["at"]) not in seen:
                    seen.add(("rp", pr["station"], pr["at"]))
                    trend_ref = (pr["at"], pr.get("trend3h"), pr["kind"])
                    if pr.get("seaLevelOffsetHPa") is None and pr["kind"] == "seaLevel":
                        rep["slpOnlyExcluded"] += 1
                    else:
                        raw = pr["hPa"] - (pr.get("seaLevelOffsetHPa") or 0.0)
                        io_ = iser.nearest(pr["at"], 30, lambda o: o.alt_hpa is not None and not in_span(o.at))
                        if io_ is not None:
                            rep["pressure"].append({"lake": lid, "err": abs(raw - io_.alt_hpa), "kind": pr["kind"], "band": band})
                        else:
                            rep["pressureTruthNoReport"] += 1
                elif pr is None and not p_span:
                    trend_ref = (now, None, "none")
                if trend_ref is not None:
                    ref_at, bt3, kind = trend_ref
                    io_ = iser.nearest(ref_at, 30, lambda o: o.alt_hpa is not None and not in_span(o.at))
                    if io_ is None:
                        rep["truthNoReport"] += 1
                    else:
                        ind_series = [(o.at, o.alt_hpa) for o in iser.between(io_.at - timedelta(hours=5), io_.at) if o.alt_hpa is not None]
                        it3 = tendency(io_.alt_hpa, io_.at, ind_series, 3, hp_steady)
                        if it3 is None:
                            rep["truthTrendNull"] += 1
                        else:
                            rep["brainTrendNull"] += bt3 is None
                            rep["trend"].append({"lake": lid, "agree": bt3 is not None and it3["trend"] == bt3["trend"], "kind": kind,
                                                 "band": band})
                if tv and tv.get("origin") == "observation" and ("rt", tv["station"], tv["at"]) not in seen:
                    seen.add(("rt", tv["station"], tv["at"]))
                    io_ = iser.nearest(tv["at"], 30, lambda o: o.temp_f is not None and not in_span(o.at))
                    if io_ is not None:
                        rep["temp"].append({"lake": lid, "err": abs(tv["value"] - io_.temp_f), "band": band})
                    else:
                        rep["tempTruthNoReport"] += 1
        if iser is None:
            continue
        change_hours[lid] = round(n_change / max(n_inst / (7 * 24), 1e-9), 2)

        # R-5.3 rain onset (truth definition and 2 h merge: amendment additions)
        tol = timedelta(hours=2)
        if crit["RAIN_ONSET"]:                                           # NO_PRECIP_SENSOR was decided in bind
            bev = [t for t in merge_events(ev["RAIN_ONSET"]) if w60[0] <= t < w60[1]]
            truth = []
            for t in rain_onsets(iser, w60[0], w60[1], T["measurablePrecipIn"]):
                if in_span(t):
                    span_excluded["truthEvents"] += 1
                else:
                    truth.append(t)
            wet = []
            for o in iser.between(w60[0] - tol, w60[1] + tol):
                if o.precip_1h_in is not None and o.precip_1h_in >= T["measurablePrecipIn"]:
                    if in_span(o.at):
                        span_excluded["truthReports"] += 1                # an excluded-span report never makes a hit
                    else:
                        wet.append(o.at)
            rain["brain"] += len(bev)
            rain["hits"] += sum(any(abs(t - x) <= tol for x in wet) for t in bev)
            for t in truth:
                d = any(abs(t - b) <= tol for b in bev)
                rain["truth"] += 1
                rain["det"] += d
                if any(abs(t - x) <= tol for x in evaluable["RAIN_ONSET"]):
                    rain["truthEval"] += 1
                    rain["detEval"] += d
            if bev or truth:
                rain["lakes"].add(lid)
        # R-5.3 front passage
        if fronts_ok and crit["FRONT_PASSAGE"]:
            tol3 = timedelta(hours=3)
            bev = [t for t in merge_events(ev["FRONT_PASSAGE"]) if w60[0] <= t < w60[1]]
            eps = []
            for a, b in front_episodes(lake["lat"], lake["lon"], analyses):
                if b < w60[0] or a >= w60[1]:
                    continue
                if any(a - tol3 < sb and b + tol3 >= sa for sa, sb in lake_spans):   # matching window overlaps the span at all
                    span_excluded["truthEvents"] += 1
                    continue
                eps.append((a, b))
            judgeable = [t for t in bev if any(abs(t - x) <= tol3 for x in eligible_times)]
            front["unjudgeable"] += len(bev) - len(judgeable)
            front["brain"] += len(judgeable)
            front["hits"] += sum(any(a - tol3 <= t <= b + tol3 for a, b in eps) for t in judgeable)
            for a, b in eps:
                d = any(a - tol3 <= t <= b + tol3 for t in bev)
                front["truth"] += 1
                front["det"] += d
                if any(a - tol3 <= x <= b + tol3 for x in evaluable["FRONT_PASSAGE"]):
                    front["truthEval"] += 1
                    front["detEval"] += d
            if judgeable or eps:
                front["lakes"].add(lid)

    # ---- results
    subset = bool(manifest.get("subset"))
    n_f = fid["values"]
    r51 = {"label": "Replay self-consistency check (R-5.1R). NOT the plan's 5.1; never stands in for it.",
           "values": n_f, "lakes": len(fid["lakes"]), "matchShare": _rate(fid["match"], n_f), "provenanceShare": _rate(fid["provenance"], n_f),
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
           "brainAvailability": {"label": "REPORTED, no pass mark: share of graded instants with a Brain value (unknowns in the denominator)",
                                 "pressure": {"share": _rate(*rep["availP"]), "instants": rep["availP"][1]},
                                 "airTemperature": {"share": _rate(*rep["availT"]), "instants": rep["availT"][1]}},
           "trendCounts": {"brainTrendNullCountedAsDisagreement": rep["brainTrendNull"], "truthNoReportExcluded": rep["truthNoReport"],
                           "truthTrendNullExcluded": rep["truthTrendNull"]},
           "maeCounts": {"pressureTruthNoReportExcluded": rep["pressureTruthNoReport"], "airTempTruthNoReportExcluded": rep["tempTruthNoReport"]},
           "excluded": {"slpOnlyBrainValues": rep["slpOnlyExcluded"]}}
    parts = [r52[k]["result"] for k in ("pressureMAE_hPa", "trend3hAgreement", "airTempMAE_F")]
    r52["result"] = "FAIL" if "FAIL" in parts else ("INSUFFICIENT" if "INSUFFICIENT" in parts else "PASS")

    def secondary(d):
        return {"label": "SECONDARY, not graded: truth events with an evaluable Brain rule within the tolerance",
                "truthEvents": d["truthEval"], "detected": d["detEval"], "POD": _rate(d["detEval"], d["truthEval"])}

    ro = grade_pod_far(rain["det"], rain["truth"], rain["hits"], rain["brain"], len(rain["lakes"]), 0.8, 0.3)
    ro["secondaryEvaluableOnly"] = secondary(rain)
    ro["amendmentAdditions"] = ["truth onset = p01i >= 0.01 in after a measured 3 h dry lookback", "Brain events merged within 2 h"]
    if fronts_ok:
        fp = grade_pod_far(front["det"], front["truth"], front["hits"], front["brain"], len(front["lakes"]), 0.6, 0.4)
        fp["secondaryEvaluableOnly"] = secondary(front)
        fp["eligibleAnalyses"] = len(eligible_times)
        fp["unjudgeableBrainEventsExcludedFromFAR"] = front["unjudgeable"]
        fp["amendmentAdditions"] = ["Brain events merged within 2 h", "Brain events with no eligible analysis within +/- 3 h excluded from FAR"]
    else:
        fp = {"result": "NOT_GRADED", "reason": f"fronts {(manifest.get('fronts') or {}).get('status')} (bound in run-manifest.json)"}

    qualifiers = ["SUBSET"] if subset else []
    directory = max(int(manifest.get("directoryCount") or 0), 1)

    def finalise(r, crit, pop_key):
        r["metricsResult"] = r["result"]
        n = (manifest.get("population") or {}).get(pop_key, 0)
        cov = round(n / directory, 4)
        r["coverage"] = {"lakes": n, "directoryLakes": directory, "share": cov, "minimum": COVERAGE_MIN,
                         "excludedByReason": (manifest.get("exclusions") or {}).get(pop_key, {}),
                         "rule": "every excluded lake counts against the Brain (protocol exclusionsCountAgainst)"}
        if r["result"] != "NOT_GRADED" and cov < COVERAGE_MIN:
            r["result"], r["reason"] = "FAIL", "COVERAGE_BELOW_MINIMUM"
        r["computedResult"] = r["result"]
        r["substitutionGate"] = gate[crit]
        q = []
        if not gate[crit]["ok"]:
            q.append("SUBSTITUTION_UNCERTAIN")
        if subset and r["result"] in ("PASS", "FAIL"):
            r["result"] = "NOT_GRADED"
        elif q and r["result"] == "PASS":
            r["result"] = "NOT_GRADED"
        r["qualifiers"] = qualifiers + q

    finalise(r51, "R-5.1R", "R-5.1R")
    finalise(r52, "R-5.2", "R-5.2")
    finalise(fp, "R-5.3.FRONT_PASSAGE", "FRONT_PASSAGE")
    finalise(ro, "R-5.3.RAIN_ONSET", "RAIN_ONSET")
    parts = [ro["result"], fp["result"]]
    r53 = {"RAIN_ONSET": ro, "FRONT_PASSAGE": fp,
           "result": "FAIL" if "FAIL" in parts else ("PASS" if parts == ["PASS", "PASS"] else
                                                     ("NOT_GRADED" if "NOT_GRADED" in parts else "INSUFFICIENT")),
           "changeHoursPerLakePerWeek": {"median": _median(list(change_hours.values())), "max": max(change_hours.values(), default=None),
                                         "lakes": len(change_hours)}}
    if any("SUBSTITUTION_UNCERTAIN" in x.get("qualifiers", []) for x in (r51, r52, ro, fp)):
        qualifiers = qualifiers + ["SUBSTITUTION_UNCERTAIN"]
    return {"labels": LABELS, "protocolId": protocol_id, "qualifiers": qualifiers, "runId": manifest.get("runId"),
            "lakes": {"directory": manifest.get("directoryCount"), "inStationsFile": manifest.get("lakesInStations"),
                      "population": manifest.get("population"), "exclusions": manifest.get("exclusions"),
                      "excludedSpans": span_excluded, "independentStations": independents},
            "R-SUB": sub, "R-5.1R": r51, "R-5.2": r52, "R-5.3": r53,
            "note": "Evidence for /validation/weather only; writes nothing, sets no status, changes no score (protocol resultStates.rubricMapping)."}


def _median(xs):
    xs = sorted(xs)
    if not xs:
        return None
    m = len(xs) // 2
    return xs[m] if len(xs) % 2 else round((xs[m - 1] + xs[m]) / 2, 2)


def grade_inputs(run: str) -> dict:
    """The files grade is bound to (protocol runLedger.chainOfInputs)."""
    return {"run-manifest.json": PRL.Path(run, MANIFEST), **{st: PRL.Path(run, st) for st in STAGES}}


def cmd_bind(a) -> int:
    p, digest = load_protocol()
    out = os.path.join(a.run, MANIFEST)
    if os.path.exists(out):
        raise SystemExit(f"REFUSED: {out} exists; the binding is write-once")
    L = open_ledger(a.run)
    trees = {st: _require_stage(L, a.run, st) for st in STAGES}

    def work():
        m = bind(p, digest, a.run)
        with open(out, "x") as fh:
            json.dump(m, fh, indent=1, sort_keys=True)
        L2 = open_ledger(a.run)
        L2.bind_inputs("grade", KEY, grade_inputs(a.run))
        print(json.dumps({"runId": m["runId"], "subset": m["subset"], "population": m["population"], "directory": m["directoryCount"],
                          "substitution": m["substitution"]["status"], "fronts": m["fronts"]["status"], "manifestSha256": sha256_file(out)}))
        return {"run-manifest.json": PRL.Path(out)}

    return _ledger_step(a.run, "bind", trees, work, out)


def _post_hook(kind: str, text: str, run: str) -> None:
    """Write the comment to post (write-once) and tell the operator. The ledger never posts; the session running the protocol posts it on
    Sector_Ops #51 as a research record (never an Owner header), once, and never edits it. Tests replace this hook."""
    path = os.path.join(run, f"ledger-{kind}.txt")
    with open(path, "x") as fh:
        fh.write(text)
    print(f"POST THIS ON Sector_Ops #51 NOW (once; never edit it): {path}", file=sys.stderr, flush=True)


def _await_confirm(confirm, step: str, max_wait_s: float) -> dict:
    """Retry the ledger confirm while #51 does not list the comment yet ('not listed yet': wait and retry, never repost)."""
    waited = 0.0
    while True:
        try:
            return confirm(step, KEY)
        except PRL.RepeatDetected:
            raise
        except PRL.LedgerRefusal as e:
            if "not listed yet" not in str(e) or (max_wait_s and waited >= max_wait_s):
                raise
        time.sleep(POLL_S)
        waited += POLL_S


def cmd_grade(a) -> int:
    p, digest = load_protocol()
    for name in (REPORT, "ledger-audit.json", "ledger-start.txt", "ledger-result.txt"):
        if os.path.exists(os.path.join(a.run, name)):
            raise SystemExit(f"REFUSED: {a.run}/{name} exists; grade outputs are write-once")
    mpath = os.path.join(a.run, MANIFEST)
    if not os.path.exists(mpath):
        raise SystemExit("REFUSED: no run-manifest.json (run bind first)")
    L = open_ledger(a.run)
    files = grade_inputs(a.run)
    L.check_inputs("grade", KEY, files)                                  # the manifest and stages bound by bind
    manifest = json.load(open(mpath))
    verify_run(manifest, digest, a.run)                                  # and the disk equals the manifest exactly
    L.begin("grade", KEY, args={}, inputs=files)
    _post_hook("start", L.start_text("grade", KEY), a.run)
    _await_confirm(L.confirm_started, "grade", a.max_wait_min * 60)      # before ANY comparison
    rep = grade(p, manifest, a.run)
    msha = sha256_file(mpath)
    rep.update({"protocolSha256": digest, "manifestSha256": msha, "release": C.RELEASE.get("releaseId"),
                "thresholdsVersion": C.THRESHOLDS_VERSION, "gradedAt": _now_iso(),
                "counting": "protocol runLedger.counting: only the ledger's counted COMPLETED grade counts (see ledger-audit.json)"})
    out = os.path.join(a.run, REPORT)
    with open(out, "x") as fh:
        json.dump(rep, fh, indent=1, sort_keys=True, default=str)
    L.record_outputs("grade", KEY, {"report.json": PRL.Path(out)})
    results = {k: rep[k]["result"] for k in ("R-SUB", "R-5.1R", "R-5.2")}
    results.update({"RAIN_ONSET": rep["R-5.3"]["RAIN_ONSET"]["result"], "FRONT_PASSAGE": rep["R-5.3"]["FRONT_PASSAGE"]["result"]})
    entry = L.complete("grade", KEY, outputs={"report.json": PRL.Path(out)},
                       result={"results": results, "qualifiers": rep["qualifiers"], "reportSha256": sha256_file(out), "manifestSha256": msha})
    _post_hook("result", L.result_text("grade", KEY), a.run)
    _await_confirm(L.confirm_result, "grade", a.max_wait_min * 60)
    with open(os.path.join(a.run, "ledger-audit.json"), "x") as fh:
        json.dump(L.audit(check_external=True), fh, indent=1, sort_keys=True, default=str)
    print(json.dumps(results | {"counted": entry["counted"], "qualifiers": rep["qualifiers"], "report": out}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    sp.add_parser("verify")
    for name in ("ledger-anchor", "fetch-stations", "fetch-asos", "fetch-recent", "fetch-fronts", "bind"):
        s = sp.add_parser(name)
        s.add_argument("--run", required=True)
    s = sp.add_parser("grade")
    s.add_argument("--run", required=True)
    s.add_argument("--max-wait-min", type=float, default=0, help="stop waiting for a posted #51 record after this many minutes (0 = wait)")
    a = ap.parse_args(argv)
    if a.cmd == "verify":
        _, d = load_protocol()
        print(f"OK protocol sha256 {d}")
        return 0
    return {"ledger-anchor": cmd_ledger_anchor, "fetch-stations": cmd_fetch_stations, "fetch-asos": cmd_fetch_asos, "fetch-recent": cmd_fetch_recent,
            "fetch-fronts": cmd_fetch_fronts, "bind": cmd_bind, "grade": cmd_grade}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
