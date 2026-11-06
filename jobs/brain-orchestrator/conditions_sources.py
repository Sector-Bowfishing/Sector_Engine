"""Conditions sources projection for Sector Ops (Sector_Ops #53, CONDITIONS_CONSOLIDATION_SPEC_V1 §4 and §7).

Behind env CONDITIONS_SOURCES_PROJECTION=1 (default OFF: nothing is probed, read or written), once per orchestrator cycle and no more often than
every 15 minutes, the Orchestrator:

  1. probes the Engine's normal request path, GET {SECTOR_ENGINE_URL}/conditions?lat&lon, at the 17 fixed points in
     verification/fixtures/phone-contract/points-v1.json. Requests are sequential, share a ~120 s budget, and send
     `User-Agent: Sector-Orchestrator/<version>`;
  2. reads `tileSources` (spec §4) from each response. Today's Engine sends none: then class and source are derived from today's known paths
     (every tile class 2 `engine`, moon class 3 `app`) and the flag is "unknown";
  3. merges each Brain's brains/{id}/lastSuccessfulRun and its runner (the fresh runner lease holder, else the reviewed runner-policy primary);
  4. computes per-tile freshness (green/amber/red, §7), coverage over ELIGIBLE points {ok, fallback, unknown, total}, per tile and per point
     `lastUpdate` (the source's observation time, never a run time) and `fetchedAt` (Engine fetch or Brain copy publish time), the breaker state ("unknown" unless tileSources carries one) and `contractOk`
     from the phone-contract validator (tools/conditions_golden/capture.py);
  5. writes ONE document, control/conditionsSourcesV1 (schema sector-conditions-sources-v1).

A failed probe never fails the cycle: the document is written with what was collected, and every failure is listed under `errors`.
The last-run time is the written document's own `generatedAt` (the shadow lane's `runAt` pattern), so the throttle needs no other state.
Nothing here writes a Brain, customer or Engine path, and nothing here starts anything. Stdlib only.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import json
import os
import time
import urllib.error
import urllib.request
from collections import Counter

NODE = "control/conditionsSourcesV1"
SCHEMA = "sector-conditions-sources-v1"
ENV_SWITCH = "CONDITIONS_SOURCES_PROJECTION"
MIN_INTERVAL_MINUTES = 15
BUDGET_SECONDS = 120.0
REQUEST_TIMEOUT_SECONDS = 30.0
DEFAULT_ENGINE_URL = "https://sector-engine-e43utajroa-uc.a.run.app"     # the same default every Engine reader in this repository uses

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))                 # the repository, or /job in the staged image (deploy-job.sh)
POINTS_FILE = os.path.join(ROOT, "verification", "fixtures", "phone-contract", "points-v1.json")
VALIDATOR_FILE = os.path.join(ROOT, "tools", "conditions_golden", "capture.py")

STATUSES = ("AVAILABLE", "ESTIMATE", "FALLBACK", "UNKNOWN")
COVERED = ("AVAILABLE", "ESTIMATE", "FALLBACK")                          # a value was served (FALLBACK = the old path's value)
PATH_CLASS = {"brain": 1, "engine": 2, "app": 3}

# Spec §1: the 10 flag keys plus moon. `brainId` is the Brain whose lastSuccessfulRun and runner are merged in (None: no Brain behind the tile).
TILES = {
    "humidity":         {"brainId": None},
    "pressure":         {"brainId": None},
    "temperature":      {"brainId": None},
    "sky":              {"brainId": None},
    "wind":             {"brainId": None},
    "windOutlookModel": {"brainId": "wind"},
    "waterLevel":       {"brainId": "lake-brain"},
    "clarity":          {"brainId": "water-clarity"},
    "waterTemp":        {"brainId": "water-temp"},
    "generation":       {"brainId": "lake-brain"},
    "moon":             {"brainId": None},
}

# Source cadence in hours. Class 2 is green within 2x the cadence (§7); a source with no entry uses DEFAULT_CADENCE_HOURS.
CADENCE_HOURS = {
    "open-meteo": 1, "nws-nbm": 1, "nearest-gauge": 1, "generation-service": 1, "tva-restapi": 1,
    "visibility-model": 24, "water-temp-model": 24, "water-temp-measured": 6,
    "lake-brain": 1.5, "lake-brain-bindings": 24, "water-clarity-brain": 26, "water-temp-brain": 26, "wind-brain": 6,
}
DEFAULT_CADENCE_HOURS = 1


# --------------------------------------------------------------------------------------------------------------------------------- switches
def enabled(env=None) -> bool:
    env = os.environ if env is None else env
    return env.get(ENV_SWITCH) == "1"


def engine_url(env=None) -> str:
    """SECTOR_ENGINE_URL; else ENGINE_URL (what the deployed Orchestrator and the Brain jobs already carry); else the production default."""
    env = os.environ if env is None else env
    return (env.get("SECTOR_ENGINE_URL") or env.get("ENGINE_URL") or DEFAULT_ENGINE_URL).rstrip("/")


def user_agent(deployment_version: str | None) -> str:
    """Sector-Orchestrator/<version>: the commit from DEPLOYMENT_VERSION (brain-orchestrator@<commit>), else 'dev'."""
    v = (deployment_version or "").rsplit("@", 1)[-1].strip() or "dev"
    return f"Sector-Orchestrator/{v}"


def _t(s):
    try:
        t = dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def due(prev_generated_at, now: dt.datetime, min_interval_minutes: float = MIN_INTERVAL_MINUTES) -> bool:
    """Due when nothing was written yet, the last generatedAt is unreadable, or it is at least `min_interval_minutes` old."""
    last = _t(prev_generated_at) if prev_generated_at else None
    return last is None or (now - last).total_seconds() >= min_interval_minutes * 60


# --------------------------------------------------------------------------------------------------------------------------------- inputs
def load_points(path: str = POINTS_FILE) -> list[dict]:
    return list(json.load(open(path, encoding="utf-8"))["points"])


def load_validator(path: str = VALIDATOR_FILE):
    """The phone-contract validator as a function doc -> [violations], or None when the validator or contract is not present (contractOk then unknown)."""
    try:
        spec = importlib.util.spec_from_file_location("conditions_golden_capture", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fields = mod.load_contract()
    except Exception:                                                      # noqa: BLE001 - absent or unreadable: unknown, never a failed cycle
        return None
    return lambda doc: mod.validate(doc, fields)


def http_fetch(url: str, timeout: float, ua: str) -> tuple[int, bytes, dict]:
    """GET with the Orchestrator's User-Agent. -> (status, body, headers). Non-2xx raises urllib.error.HTTPError."""
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": ua})
    with urllib.request.urlopen(req, timeout=timeout) as r:               # noqa: S310 - https Engine URL from the job's environment
        return r.status, r.read(), dict(r.headers.items())


def lake_key(point: dict) -> str:
    return point.get("lakeId") or point["slug"]


def probe(points: list[dict], base_url: str, *, ua: str, fetch=http_fetch, budget_seconds: float = BUDGET_SECONDS,
          timeout_seconds: float = REQUEST_TIMEOUT_SECONDS, clock=time.monotonic) -> tuple[list[dict], float]:
    """Sequential GET /conditions per point within one total budget. -> (results, seconds). Each result: {point, ok, body?, headers?, error?}."""
    t0 = clock()
    out = []
    for p in points:
        left = budget_seconds - (clock() - t0)
        if left <= 1:
            out.append({"point": p, "ok": False, "error": "not attempted: probe budget exhausted"})
            continue
        url = f"{base_url}/conditions?lat={float(p['lat']):.5f}&lon={float(p['lon']):.5f}"
        try:
            status, body, headers = fetch(url, min(timeout_seconds, left), ua)
            doc = json.loads(body)
            if not isinstance(doc, dict):
                raise ValueError("response is not a JSON object")
            out.append({"point": p, "ok": True, "status": status, "body": doc, "headers": headers or {}})
        except urllib.error.HTTPError as e:
            out.append({"point": p, "ok": False, "error": f"HTTP {e.code}"})
        except Exception as e:                                             # noqa: BLE001 - one failed point never stops the others
            out.append({"point": p, "ok": False, "error": f"{type(e).__name__}: {str(e)[:120]}"})
    return out, round(clock() - t0, 1)


# --------------------------------------------------------------------------------------------------------------------------------- per-response tiles
def _today(resp: dict) -> dict:
    """Today's Engine (no tileSources): class and source from the known paths (spec §1 'Old path'); flag 'unknown'.
    `observedAt` is set only where the response carries the source's own observation time (generation); `fetchedAt` is the response's generatedAt
    (the Engine's fetch/compute time). A run time is never reported as an observation time (§7 Amendment 1)."""
    gen_at = resp.get("generatedAt")
    w = resp.get("weather") if isinstance(resp.get("weather"), dict) else {}

    def e(present, source, status="AVAILABLE", observed=None, path="engine"):
        out = {"flag": "unknown", "path": path, "source": source, "status": status if present else "UNKNOWN"}
        if present and observed:
            out["observedAt"] = observed
        if present and gen_at and path != "app":
            out["fetchedAt"] = gen_at
        return out

    wt_state = resp.get("waterTempState") if isinstance(resp.get("waterTempState"), dict) else {}
    measured = wt_state.get("kind") == "measured"
    gen = resp.get("generation") if isinstance(resp.get("generation"), dict) else None
    return {
        "humidity": e(w.get("humidity") is not None, "open-meteo"),
        "pressure": e(w.get("pressure") is not None, "open-meteo"),
        "temperature": e(w.get("temperature") is not None, "open-meteo"),
        "sky": e(w.get("cloudCover") is not None or w.get("weatherCode") is not None, "open-meteo"),
        "wind": e(w.get("windSpeed") is not None, "open-meteo"),
        "windOutlookModel": e(bool(resp.get("nights")), "open-meteo"),
        "waterLevel": e(isinstance(resp.get("water"), dict), "nearest-gauge"),
        "clarity": e(isinstance(resp.get("clarityVisibility"), dict), "visibility-model", status="ESTIMATE"),
        "waterTemp": e(bool(wt_state) or isinstance(resp.get("waterTemp"), dict), "water-temp-measured" if measured else "water-temp-model",
                       status="AVAILABLE" if measured else "ESTIMATE"),
        "generation": e(gen is not None, "generation-service", observed=(gen or {}).get("observedAt")),
        "moon": e(resp.get("moonIllumination") is not None, "app", path="app"),
    }


def tiles_of(resp: dict) -> tuple[dict, bool]:
    """-> ({tile: entry}, fromTileSources). An entry missing from a tileSources response is UNKNOWN (the spec promises all keys once shipped).
    `fetchedAt` comes from the entry (`fetchedAt`, else a Brain copy's `publishedAt`); eligibility from the entry's `eligible`, else its flag's `lakes`."""
    ts = resp.get("tileSources")
    if not isinstance(ts, dict):
        return _today(resp), False
    out = {}
    for tile in TILES:
        v = ts.get(tile)
        if not isinstance(v, dict):
            out[tile] = {"flag": "unknown", "status": "UNKNOWN"}
            continue
        st = v.get("status") if v.get("status") in STATUSES else "UNKNOWN"
        out[tile] = {k: v[k] for k in ("flag", "path", "source", "observedAt", "freshUntil", "runner", "publishId", "breaker", "eligible", "lakes")
                     if v.get(k) is not None}
        fetched = v.get("fetchedAt") or v.get("publishedAt")
        if fetched:
            out[tile]["fetchedAt"] = fetched
        out[tile]["status"] = st
        out[tile].setdefault("flag", "unknown")
    return out, True


def eligible(entry: dict | None, key: str) -> bool:
    """§7 Amendment 1: does the tile's flag apply at this point? An explicit `eligible` wins; a `lakes` list limits the flag to those lakes (an `off`
    flag never limits: the old path applies everywhere); otherwise every point is eligible. A failed probe is eligible (counted as unknown)."""
    if not entry:
        return True
    if isinstance(entry.get("eligible"), bool):
        return entry["eligible"]
    lakes = entry.get("lakes")
    if isinstance(lakes, list) and entry.get("flag") not in ("off", "unknown", None):
        return key in lakes
    return True


# --------------------------------------------------------------------------------------------------------------------------------- freshness
def freshness(entry: dict, now: dt.datetime) -> str:
    """§7: green within freshUntil (class 2 without one: within 2x the source cadence); amber within twice that window; red when stale or UNKNOWN.
    The age is taken from the source's observation time; when the response gives none (most of today's Engine tiles), from the Engine's fetch time.
    App tiles (class 3) are computed on the device: green whenever AVAILABLE."""
    if entry.get("status") not in COVERED:
        return "red"
    if entry.get("path") == "app":
        return "green"
    obs, until = _t(entry.get("observedAt") or entry.get("fetchedAt")), _t(entry.get("freshUntil"))
    if until is not None:
        window = (until - obs) if obs is not None and until > obs else dt.timedelta(hours=CADENCE_HOURS.get(entry.get("source"), DEFAULT_CADENCE_HOURS))
        return "green" if now <= until else ("amber" if now <= until + window else "red")
    if obs is None:
        return "red"
    w = dt.timedelta(hours=2 * CADENCE_HOURS.get(entry.get("source"), DEFAULT_CADENCE_HOURS))
    age = now - obs
    return "green" if age <= w else ("amber" if age <= 2 * w else "red")


_RANK = {"green": 0, "amber": 1, "red": 2}


# --------------------------------------------------------------------------------------------------------------------------------- runners
def brain_runners(brain_ids, policy: dict | None, lease_holder=None) -> dict:
    """{brainId: {"runner", "basis"}}: the fresh runner-lease holder when one can be read, else the reviewed runner-policy primary, else unknown."""
    out = {}
    for b in sorted(set(brain_ids)):
        holder = None
        if lease_holder is not None:
            try:
                holder = lease_holder(b)
            except Exception:                                              # noqa: BLE001 - unreadable lease: fall back to the policy
                holder = None
        if holder:
            out[b] = {"runner": holder, "basis": "lease"}
        elif policy:
            out[b] = {"runner": (policy.get("primary") or {}).get(b, policy.get("defaultPrimary", "cloud")), "basis": "policy"}
        else:
            out[b] = {"runner": "unknown", "basis": "unknown"}
    return out


# --------------------------------------------------------------------------------------------------------------------------------- build
def _most_common(values, default):
    vals = [v for v in values if v is not None]
    return Counter(vals).most_common(1)[0][0] if vals else default


def _breaker(values) -> str:
    vals = {v for v in values if v}
    if "open" in vals:
        return "open"
    if "half-open" in vals or "half_open" in vals:
        return "half-open"
    if vals and vals <= {"closed"}:
        return "closed"
    return "unknown"


def build(results: list[dict], *, now: dt.datetime, brains: dict | None = None, runners: dict | None = None, validator=None,
          seconds: float | None = None, budget_seconds: float = BUDGET_SECONDS, extra_errors: list | None = None) -> dict:
    """The control/conditionsSourcesV1 document (spec §7) from probe results. Pure given its inputs."""
    brains = brains or {}
    runners = runners or {}
    errors = list(extra_errors or [])
    per_point = []                       # (key, {tile: entry}) for answered points; None entries for failed ones
    violations, checked, from_ts, revisions = 0, 0, 0, []
    for r in results:
        key = lake_key(r["point"])
        if not r.get("ok"):
            errors.append({"lake": key, "error": r.get("error", "probe failed")})
            per_point.append((key, None))
            continue
        body = r["body"]
        tiles, has_ts = tiles_of(body)
        from_ts += int(has_ts)
        if validator is not None:
            checked += 1
            v = validator(body)
            if v:
                violations += 1
                errors.append({"lake": key, "error": f"phone contract: {len(v)} violation(s), first: {str(v[0])[:120]}"})
        hdr = {k.lower(): v for k, v in (r.get("headers") or {}).items()}
        revisions.append(body.get("engineRevision") or hdr.get("x-engine-revision"))
        per_point.append((key, tiles))

    contract_ok = None if validator is None or checked == 0 else violations == 0
    total = len(results)
    doc_tiles = {}
    for tile, meta in TILES.items():
        lakes, entries = {}, []
        for key, tiles in per_point:
            if tiles is None:
                lakes[key] = {"status": "UNKNOWN", "eligible": True}
                continue
            en = tiles[tile]
            el = eligible(en, key)
            entries.append((en, el))
            lk = {k: en[k] for k in ("status", "observedAt", "path", "source") if en.get(k) is not None}
            lk["eligible"] = el
            if en.get("observedAt"):
                lk["lastUpdate"] = en["observedAt"]
            if en.get("fetchedAt"):
                lk["fetchedAt"] = en["fetchedAt"]
            lakes[key] = lk
        failed = sum(1 for _, t in per_point if t is None)
        elig = [en for en, el in entries if el]
        ok = [en for en in elig if en.get("status") in ("AVAILABLE", "ESTIMATE")]
        fb = [en for en in elig if en.get("status") == "FALLBACK"]
        covered = ok + fb
        all_en = [en for en, _ in entries]
        path = _most_common([en.get("path") for en in all_en], "engine" if tile != "moon" else "app")
        source = _most_common([en.get("source") for en in all_en], "unknown")
        fresh = max((freshness(en, now) for en in covered), key=_RANK.get, default="red")    # the worst eligible covered point; nothing covered = red
        # a time ahead of the probe (an upstream's forecast-window stamp) is not an observation: it never becomes the tile's lastUpdate
        observed = [t for t in (_t(en.get("observedAt")) for en in covered) if t is not None and t <= now + dt.timedelta(minutes=5)]
        fetched = [t for t in (_t(en.get("fetchedAt")) for en in covered) if t is not None]
        bid = meta["brainId"]
        if path == "brain":
            runner = _most_common([en.get("runner") for en in all_en], (runners.get(bid) or {}).get("runner", "unknown"))
        elif path == "engine":
            runner = "engine"
        else:
            runner = "app"
        t = {"class": PATH_CLASS.get(path, 2), "flag": _most_common([en.get("flag") for en in all_en], "unknown"),
             "sourcePath": f"{path}:{source}", "fresh": fresh, "runner": runner,
             "coverage": {"ok": len(ok), "fallback": len(fb), "unknown": len(elig) - len(covered) + failed, "total": len(elig) + failed},
             "breaker": _breaker([en.get("breaker") for en in all_en]), "lakes": lakes}
        if observed:
            t["lastUpdate"] = _iso(max(observed))          # the source's newest observation time, never a run time (Amendment 1)
        if fetched:
            t["fetchedAt"] = _iso(max(fetched))
        if contract_ok is not None:
            t["contractOk"] = contract_ok                   # build 28 decodes strictly: one violation blanks every tile, so it is per response, not per tile
        if bid:
            t["brainId"] = bid
        doc_tiles[tile] = t

    answered = sum(1 for _, t in per_point if t is not None)
    doc = {"schema": SCHEMA, "generatedAt": _iso(now), "engineRevision": _most_common(revisions, "unknown"), "tiles": doc_tiles,
           "brains": {bid: {k: v for k, v in {"lastSuccessfulRun": (brains.get(bid) or {}).get("lastSuccessfulRun") if isinstance(brains.get(bid), dict) else None,
                                               "runner": (runners.get(bid) or {}).get("runner", "unknown"),
                                               "runnerBasis": (runners.get(bid) or {}).get("basis", "unknown")}.items() if v is not None}
                      for bid in sorted({m["brainId"] for m in TILES.values() if m["brainId"]})},
           "probe": {k: v for k, v in {"points": total, "answered": answered, "failed": total - answered, "withTileSources": from_ts,
                                        "contractChecked": checked, "contractViolations": violations, "seconds": seconds,
                                        "budgetSeconds": budget_seconds}.items() if v is not None}}
    if errors:
        doc["errors"] = errors[:40]
    return doc


# --------------------------------------------------------------------------------------------------------------------------------- the cycle stage
def stage(live, db, now: dt.datetime, *, write: bool, env=None, brains: dict | None = None, policy: dict | None = None, lease_holder=None,
          fetch=http_fetch, points_file: str = POINTS_FILE, validator_file: str = VALIDATOR_FILE, clock=time.monotonic) -> dict:
    """One cycle's projection. OFF (the default) touches nothing. Never raises for a probe failure; returns a short summary for the cycle log."""
    env = os.environ if env is None else env
    if not enabled(env):
        return {"state": "OFF"}
    try:
        prev_at = live.get(f"{NODE}/generatedAt")
    except Exception:                                                      # noqa: BLE001 - unreadable: treat as due
        prev_at = None
    if not due(prev_at, now):
        return {"state": "NOT_DUE", "lastGeneratedAt": prev_at}
    extra = []
    try:
        points = load_points(points_file)
    except Exception as e:                                                 # noqa: BLE001
        points = []
        extra.append({"lake": "*", "error": f"probe points unreadable: {type(e).__name__}"})
    validator = load_validator(validator_file)
    if validator is None:
        extra.append({"lake": "*", "error": "phone-contract validator unavailable: contractOk unknown"})
    results, secs = probe(points, engine_url(env), ua=user_agent(env.get("DEPLOYMENT_VERSION")), fetch=fetch, clock=clock)
    runners = brain_runners([m["brainId"] for m in TILES.values() if m["brainId"]], policy, lease_holder)
    doc = build(results, now=now, brains=brains, runners=runners, validator=validator, seconds=secs, extra_errors=extra)
    if write:
        db.update({NODE: doc})
    return {"state": "WRITTEN" if write else "COMPUTED", "answered": doc["probe"]["answered"], "points": doc["probe"]["points"],
            "seconds": secs, "errors": len(doc.get("errors") or []), "contractViolations": doc["probe"]["contractViolations"]}
