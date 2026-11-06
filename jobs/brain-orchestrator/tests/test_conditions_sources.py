"""Conditions-sources projection (Sector_Ops #53 spec §7): control/conditionsSourcesV1 from recorded /conditions responses. No network: every
probe is answered from the redacted 2026-11-06 goldens (today's Engine, no tileSources) or a synthetic tileSources overlay."""
import copy
import datetime as dt
import json
import os
import urllib.error

import pytest

import conditions_sources as CSP

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
GOLDEN_DIR = os.path.join(ROOT, "verification", "fixtures", "phone-contract", "2026-11-06")
SYNTHETIC = json.load(open(os.path.join(HERE, "fixtures", "conditions_tile_sources_synthetic.json"), encoding="utf-8"))
POINTS = CSP.load_points()
BY_COORD = {(f"{p['lat']:.5f}", f"{p['lon']:.5f}"): p["slug"] for p in POINTS}
NOW = dt.datetime(2026, 11, 6, 20, 10, tzinfo=dt.timezone.utc)
ON = {"CONDITIONS_SOURCES_PROJECTION": "1", "SECTOR_ENGINE_URL": "https://engine.test", "DEPLOYMENT_VERSION": "brain-orchestrator@abc123def456"}


def golden(slug):
    return json.load(open(os.path.join(GOLDEN_DIR, f"{slug}.json"), encoding="utf-8"))


def slug_of(url):
    q = dict(kv.split("=") for kv in url.split("?", 1)[1].split("&"))
    return BY_COORD[(q["lat"], q["lon"])]


class Fetch:
    """Recorded responses by slug; `fail` maps a slug to an exception; `overlay` adds fields to every body."""

    def __init__(self, overlay=None, fail=None, mutate=None):
        self.overlay, self.fail, self.mutate, self.calls = overlay or {}, fail or {}, mutate, []

    def __call__(self, url, timeout, ua):
        self.calls.append((url, timeout, ua))
        slug = slug_of(url)
        if slug in self.fail:
            raise self.fail[slug]
        body = golden(slug)
        body.update(copy.deepcopy(self.overlay))
        if self.mutate:
            self.mutate(slug, body)
        return 200, json.dumps(body).encode(), {"Content-Type": "application/json"}


class Live:
    def __init__(self, data=None, explode=False):
        self.data, self.explode, self.reads = data or {}, explode, []

    def get(self, path, shallow=False):
        self.reads.append(path)
        if self.explode:
            raise AssertionError("no read allowed")
        return self.data.get(path)


class Db:
    def __init__(self):
        self.writes = []

    def update(self, u):
        self.writes.append(u)


def run(fetch, live=None, env=ON, **kw):
    db = Db()
    res = CSP.stage(live or Live(), db, NOW, write=True, env=env, fetch=fetch, **kw)
    return res, db


def rtdb_safe(v, where="$"):
    """No None values (RTDB drops them) and no keys with characters RTDB refuses."""
    if isinstance(v, dict):
        for k, c in v.items():
            assert isinstance(k, str) and k and not any(ch in k for ch in ".$#[]/"), f"{where}: bad key {k!r}"
            rtdb_safe(c, f"{where}.{k}")
    elif isinstance(v, list):
        for i, c in enumerate(v):
            rtdb_safe(c, f"{where}[{i}]")
    else:
        assert v is not None, f"{where}: None"


# ----------------------------------------------------------------------------------------------------------------- OFF is untouched
def test_off_by_default_touches_nothing():
    f, live = Fetch(), Live(explode=True)
    res, db = run(f, live=live, env={})
    assert res == {"state": "OFF"} and f.calls == [] and db.writes == [] and live.reads == []
    assert not CSP.enabled({}) and not CSP.enabled({"CONDITIONS_SOURCES_PROJECTION": "on"}) and CSP.enabled({"CONDITIONS_SOURCES_PROJECTION": "1"})


def test_orchestrator_calls_the_stage_only_behind_the_switch():
    src = open(os.path.join(HERE, "..", "orchestrate.py"), encoding="utf-8").read()
    i = src.index("CSP.stage(")
    guard = src.rfind("if CSP.enabled() and not a.health_only and not a.control_only:", 0, i)
    assert guard != -1 and src.count("CSP.stage(") == 1 and src[guard:i].count("\n") <= 3


def test_deploy_switch_defaults_off_and_stages_the_inputs():
    sh = open(os.path.join(HERE, "..", "deploy-job.sh"), encoding="utf-8").read()
    assert 'CONDITIONS_SOURCES_PROJECTION="${CONDITIONS_SOURCES_PROJECTION:-0}"' in sh
    assert "CONDITIONS_SOURCES_PROJECTION=$CONDITIONS_SOURCES_PROJECTION" in sh.split("--set-env-vars", 1)[1].split("\n", 1)[0]
    for f in ("points-v1.json", "conditions-phone-contract-v1.json", "conditions_golden/capture.py"):
        assert f in sh


# ----------------------------------------------------------------------------------------------------------------- throttle
@pytest.mark.parametrize("minutes_ago,due", [(None, True), (10, False), (14.9, False), (15, True), (60, True)])
def test_at_most_every_15_minutes(minutes_ago, due):
    prev = None if minutes_ago is None else CSP._iso(NOW - dt.timedelta(minutes=minutes_ago))
    f = Fetch()
    res, db = run(f, live=Live({f"{CSP.NODE}/generatedAt": prev}))
    assert (res["state"] == "WRITTEN") is due and bool(db.writes) is due and bool(f.calls) is due
    assert CSP.due("garbage", NOW)


# ----------------------------------------------------------------------------------------------------------------- today's Engine
def test_todays_engine_derives_classes_and_marks_flags_unknown():
    f = Fetch()
    res, db = run(f, brains={"lake-brain": {"lastSuccessfulRun": "2026-11-06T19:40:00Z"}, "water-clarity": {"lastSuccessfulRun": "2026-11-06T06:00:00Z"}},
                  policy={"schema": "sector-runner-policy-v1", "defaultPrimary": "cloud", "primary": {"water-clarity": "pulse"}})
    assert res["state"] == "WRITTEN" and res["answered"] == 17 and res["contractViolations"] == 0
    [w] = db.writes
    doc = w[CSP.NODE]
    rtdb_safe(doc)
    assert doc["schema"] == "sector-conditions-sources-v1" and doc["generatedAt"] == "2026-11-06T20:10:00Z" and doc["engineRevision"] == "unknown"
    assert set(doc["tiles"]) == set(CSP.TILES) and len(doc["tiles"]) == 11
    assert "errors" not in doc and doc["probe"]["withTileSources"] == 0 and doc["probe"]["points"] == 17
    for name, t in doc["tiles"].items():
        assert t["flag"] == "unknown" and t["breaker"] == "unknown" and t["contractOk"] is True
        assert t["class"] == (3 if name == "moon" else 2)
        assert t["runner"] == ("app" if name == "moon" else "engine")
        assert len(t["lakes"]) == 17 and t["coverage"]["total"] == 17 and t["coverage"]["fallback"] == 0
        assert all(lk["eligible"] is True for lk in t["lakes"].values())                     # no flag limits a point today
        assert t["coverage"]["ok"] + t["coverage"]["unknown"] == 17
    T = doc["tiles"]
    assert T["humidity"]["sourcePath"] == "engine:open-meteo" and T["humidity"]["coverage"] == {"ok": 17, "fallback": 0, "unknown": 0, "total": 17}
    assert T["humidity"]["fresh"] == "green"
    # Amendment 1: weather carries no observation time today, so there is no lastUpdate (a run time is never one); fetchedAt is the Engine's
    assert "lastUpdate" not in T["humidity"] and T["humidity"]["fetchedAt"] == max(golden(p["slug"])["generatedAt"] for p in POINTS)
    gl = T["humidity"]["lakes"]["Guntersville|AL"]
    assert gl == {"status": "AVAILABLE", "path": "engine", "source": "open-meteo", "eligible": True, "fetchedAt": "2026-11-06T20:05:19Z"}
    assert T["generation"]["lakes"]["Lake Hartwell|SC"]["lastUpdate"] == "2026-11-06T21:00:00Z"   # the point keeps the Engine's stamp as sent
    assert T["generation"]["lastUpdate"] == "2026-11-06T20:06:13Z"                              # but a future stamp never becomes the tile's lastUpdate
    assert T["moon"]["sourcePath"] == "app:app" and T["moon"]["fresh"] == "green"
    n_gen = sum("generation" in golden(p["slug"]) for p in POINTS)
    n_water = sum("water" in golden(p["slug"]) for p in POINTS)
    assert T["generation"]["coverage"]["ok"] == n_gen < 17 and T["waterLevel"]["coverage"]["ok"] == n_water < 17
    assert T["generation"]["lakes"]["Kentucky Lake|TN"] == {"status": "UNKNOWN", "path": "engine", "source": "generation-service", "eligible": True}
    g = T["generation"]["lakes"]["Guntersville|AL"]
    assert g["observedAt"] == g["lastUpdate"] == "2026-11-06T19:00:00Z" and g["fetchedAt"] == "2026-11-06T20:05:19Z"
    assert T["clarity"]["lakes"]["Guntersville|AL"]["status"] == "ESTIMATE"
    assert T["waterTemp"]["lakes"]["Lake Champlain|VT"] == {"status": "AVAILABLE", "path": "engine", "source": "water-temp-measured", "eligible": True,
                                                         "fetchedAt": golden("champlain-vt")["generatedAt"]}
    assert "fetchedAt" not in T["moon"] and "lastUpdate" not in T["moon"]
    assert "mississippi-memphis" in T["wind"]["lakes"] and "mobile-bay-al" in T["wind"]["lakes"]      # off-directory points keyed by slug
    assert T["waterLevel"]["brainId"] == "lake-brain" and "brainId" not in T["humidity"]
    assert doc["brains"]["lake-brain"] == {"lastSuccessfulRun": "2026-11-06T19:40:00Z", "runner": "cloud", "runnerBasis": "policy"}
    assert doc["brains"]["water-clarity"]["runner"] == "pulse" and set(doc["brains"]) == {"lake-brain", "water-clarity", "water-temp", "wind"}


def test_requests_are_sequential_with_the_orchestrator_user_agent_and_engine_url():
    f = Fetch()
    run(f)
    assert len(f.calls) == 17
    assert all(u.startswith("https://engine.test/conditions?lat=") for u, _, _ in f.calls)
    assert {ua for _, _, ua in f.calls} == {"Sector-Orchestrator/abc123def456"}
    assert all(t <= CSP.REQUEST_TIMEOUT_SECONDS for _, t, _ in f.calls)
    assert CSP.user_agent(None) == "Sector-Orchestrator/dev"
    assert CSP.engine_url({"ENGINE_URL": "https://e.test/"}) == "https://e.test" and CSP.engine_url({"SECTOR_ENGINE_URL": "https://s.test", "ENGINE_URL": "x"}) == "https://s.test"


def test_default_fetcher_sends_the_user_agent(monkeypatch):
    seen = {}

    class R:
        status = 200
        headers = {"X-Engine-Revision": "r1"}

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout):
        seen["ua"], seen["timeout"], seen["url"] = req.get_header("User-agent"), timeout, req.full_url
        return R()

    monkeypatch.setattr(CSP.urllib.request, "urlopen", urlopen)
    status, body, headers = CSP.http_fetch("https://engine.test/conditions?lat=1&lon=2", 5, "Sector-Orchestrator/x")
    assert (status, body, headers["X-Engine-Revision"]) == (200, b"{}", "r1") and seen == {"ua": "Sector-Orchestrator/x", "timeout": 5, "url": "https://engine.test/conditions?lat=1&lon=2"}


# ----------------------------------------------------------------------------------------------------------------- tileSources present
def test_tile_sources_drive_flag_path_runner_breaker_and_freshness():
    f = Fetch(overlay=SYNTHETIC | {}, mutate=None)
    del f.overlay["purpose"]
    res, db = run(f, brains={"lake-brain": {"lastSuccessfulRun": "2026-11-06T19:40:00Z"}},
                  policy={"schema": "sector-runner-policy-v1", "defaultPrimary": "cloud", "primary": {}})
    doc = db.writes[0][CSP.NODE]
    rtdb_safe(doc)
    T = doc["tiles"]
    assert doc["engineRevision"] == "sector-engine-00042-abc" and doc["probe"]["withTileSources"] == 17
    assert T["humidity"] == {**T["humidity"], "class": 2, "flag": "serve", "sourcePath": "engine:nws-nbm", "fresh": "green", "breaker": "closed",
                             "runner": "engine", "coverage": {"ok": 17, "fallback": 0, "unknown": 0, "total": 17}, "contractOk": True,
                             "lastUpdate": "2026-11-06T20:00:00Z", "fetchedAt": "2026-11-06T20:02:00Z"}
    assert T["sky"]["breaker"] == "open" and T["sky"]["coverage"] == {"ok": 0, "fallback": 17, "unknown": 0, "total": 17}
    assert T["temperature"]["breaker"] == "unknown"
    wl = T["waterLevel"]
    assert (wl["class"], wl["flag"], wl["sourcePath"], wl["runner"], wl["fresh"]) == (1, "serve", "brain:lake-brain", "pulse", "green")
    assert wl["lakes"]["Guntersville|AL"] == {"status": "AVAILABLE", "observedAt": "2026-11-06T19:00:00Z", "path": "brain", "source": "lake-brain",
                                              "eligible": True, "lastUpdate": "2026-11-06T19:00:00Z", "fetchedAt": "2026-11-06T19:05:00Z"}
    assert wl["lastUpdate"] == "2026-11-06T19:00:00Z" and wl["fetchedAt"] == "2026-11-06T19:05:00Z"
    assert T["clarity"]["fresh"] == "amber"                                                         # past freshUntil, within twice its window
    assert T["windOutlookModel"]["runner"] == "cloud" and T["moon"]["class"] == 3 and T["moon"]["sourcePath"] == "app:moon-v1"


def test_a_tile_missing_from_tile_sources_is_unknown_and_red():
    def drop(slug, body):
        del body["tileSources"]["clarity"]
    f = Fetch(overlay={"tileSources": SYNTHETIC["tileSources"]}, mutate=drop)
    _, db = run(f)
    c = db.writes[0][CSP.NODE]["tiles"]["clarity"]
    assert c["coverage"] == {"ok": 0, "fallback": 0, "unknown": 17, "total": 17} and c["fresh"] == "red"
    assert c["lakes"]["Guntersville|AL"] == {"status": "UNKNOWN", "eligible": True}


@pytest.mark.parametrize("entry,now,want", [
    ({"status": "AVAILABLE", "path": "brain", "source": "lake-brain", "observedAt": "2026-11-06T19:00:00Z", "freshUntil": "2026-11-06T20:30:00Z"}, "2026-11-06T20:30:00Z", "green"),
    ({"status": "AVAILABLE", "path": "brain", "source": "lake-brain", "observedAt": "2026-11-06T19:00:00Z", "freshUntil": "2026-11-06T20:30:00Z"}, "2026-11-06T22:00:00Z", "amber"),
    ({"status": "AVAILABLE", "path": "brain", "source": "lake-brain", "observedAt": "2026-11-06T19:00:00Z", "freshUntil": "2026-11-06T20:30:00Z"}, "2026-11-06T22:01:00Z", "red"),
    ({"status": "AVAILABLE", "path": "engine", "source": "open-meteo", "observedAt": "2026-11-06T18:00:00Z"}, "2026-11-06T20:00:00Z", "green"),   # 2x 1 h
    ({"status": "AVAILABLE", "path": "engine", "source": "open-meteo", "observedAt": "2026-11-06T18:00:00Z"}, "2026-11-06T22:00:00Z", "amber"),
    ({"status": "AVAILABLE", "path": "engine", "source": "open-meteo", "observedAt": "2026-11-06T18:00:00Z"}, "2026-11-06T22:01:00Z", "red"),
    ({"status": "ESTIMATE", "path": "engine", "source": "visibility-model", "observedAt": "2026-11-05T21:00:00Z"}, "2026-11-06T20:00:00Z", "green"),
    ({"status": "UNKNOWN", "path": "engine", "source": "open-meteo", "observedAt": "2026-11-06T20:00:00Z"}, "2026-11-06T20:00:00Z", "red"),
    ({"status": "AVAILABLE", "path": "engine", "source": "open-meteo"}, "2026-11-06T20:00:00Z", "red"),
    ({"status": "AVAILABLE", "path": "app", "source": "moon-v1"}, "2026-11-06T20:00:00Z", "green"),
])
def test_freshness_rules(entry, now, want):
    assert CSP.freshness(entry, CSP._t(now)) == want


# ----------------------------------------------------------------------------------------------------------------- failures never fail the cycle
def test_failed_probes_are_recorded_and_the_rest_is_written():
    f = Fetch(fail={"guntersville-al": urllib.error.URLError("timed out"), "havasu-az": ValueError("bad json"),
                    "wheeler-al": urllib.error.HTTPError("u", 503, "unavailable", {}, None)})
    res, db = run(f)
    doc = db.writes[0][CSP.NODE]
    rtdb_safe(doc)
    assert res["answered"] == 14 and doc["probe"]["failed"] == 3
    errs = {e["lake"]: e["error"] for e in doc["errors"]}
    assert errs["Wheeler|AL"] == "HTTP 503" and errs["Guntersville|AL"].startswith("URLError") and errs["Havasu|AZ"].startswith("ValueError")
    h = doc["tiles"]["humidity"]
    assert h["coverage"] == {"ok": 14, "fallback": 0, "unknown": 3, "total": 17} and h["contractOk"] is True
    assert h["lakes"]["Guntersville|AL"] == {"status": "UNKNOWN", "eligible": True}


def test_every_probe_failing_still_writes_a_red_document():
    f = Fetch(fail={p["slug"]: OSError("down") for p in POINTS})
    res, db = run(f)
    doc = db.writes[0][CSP.NODE]
    rtdb_safe(doc)
    assert res["answered"] == 0 and len(doc["errors"]) == 17
    assert all(t["fresh"] == "red" and t["coverage"]["ok"] == 0 and "contractOk" not in t for t in doc["tiles"].values())


def test_the_time_budget_stops_further_requests():
    ticks = iter(range(0, 10_000, 30))                                   # every clock read advances 30 s
    f = Fetch()
    res, db = run(f, clock=lambda: next(ticks))
    doc = db.writes[0][CSP.NODE]
    assert 0 < len(f.calls) < 17 and res["answered"] == len(f.calls)
    assert sum(e["error"] == "not attempted: probe budget exhausted" for e in doc["errors"]) == 17 - len(f.calls)


def test_a_contract_violation_sets_contract_ok_false():
    def breaks(slug, body):
        if slug == "lanier-ga":
            del body["score"]
    _, db = run(Fetch(mutate=breaks))
    doc = db.writes[0][CSP.NODE]
    assert doc["probe"]["contractViolations"] == 1 and all(t["contractOk"] is False for t in doc["tiles"].values())
    assert any(e["lake"] == "Lanier (Sidney Lanier)|GA" and e["error"].startswith("phone contract") for e in doc["errors"])


def test_missing_validator_or_points_is_reported_not_raised(tmp_path):
    res, db = run(Fetch(), validator_file=str(tmp_path / "nope.py"), points_file=str(tmp_path / "nope.json"))
    doc = db.writes[0][CSP.NODE]
    rtdb_safe(doc)
    assert res["points"] == 0 and {e["lake"] for e in doc["errors"]} == {"*"} and len(doc["errors"]) == 2
    assert all("contractOk" not in t for t in doc["tiles"].values())


def test_unreadable_previous_document_counts_as_due():
    class Boom(Live):
        def get(self, path, shallow=False):
            raise RuntimeError("rtdb down")
    res, db = run(Fetch(), live=Boom())
    assert res["state"] == "WRITTEN" and db.writes


# ----------------------------------------------------------------------------------------------------------------- runners
def test_runner_lease_beats_policy_and_unreadable_lease_falls_back():
    pol = {"defaultPrimary": "cloud", "primary": {"water-clarity": "pulse"}}

    def holder(b):
        if b == "lake-brain":
            return "pulse"
        if b == "wind":
            raise RuntimeError("store down")
        return None
    r = CSP.brain_runners(["lake-brain", "wind", "water-clarity", "water-temp"], pol, holder)
    assert r == {"lake-brain": {"runner": "pulse", "basis": "lease"}, "wind": {"runner": "cloud", "basis": "policy"},
                 "water-clarity": {"runner": "pulse", "basis": "policy"}, "water-temp": {"runner": "cloud", "basis": "policy"}}
    assert CSP.brain_runners(["wind"], None, None) == {"wind": {"runner": "unknown", "basis": "unknown"}}


def test_a_run_time_is_never_reported_as_last_update():
    """Amendment 1: lastUpdate is the source's observation time. Without one, the Brain's lastSuccessfulRun (a run time) stays in `brains` only."""
    def no_obs(slug, body):
        body["tileSources"]["waterLevel"].pop("observedAt")
        body["tileSources"]["waterLevel"].pop("runner")
    f = Fetch(overlay={"tileSources": SYNTHETIC["tileSources"]}, mutate=no_obs)
    _, db = run(f, brains={"lake-brain": {"lastSuccessfulRun": "2026-11-06T19:40:00Z"}}, lease_holder=lambda b: "pulse" if b == "lake-brain" else None)
    doc = db.writes[0][CSP.NODE]
    wl = doc["tiles"]["waterLevel"]
    assert "lastUpdate" not in wl and "lastUpdate" not in wl["lakes"]["Guntersville|AL"] and wl["fetchedAt"] == "2026-11-06T19:05:00Z"
    assert wl["runner"] == "pulse" and doc["brains"]["lake-brain"] == {"lastSuccessfulRun": "2026-11-06T19:40:00Z", "runner": "pulse", "runnerBasis": "lease"}


def test_eligibility_limits_coverage_to_the_flagged_lakes():
    """A `lakes` list on a serve/shadow flag limits it; an explicit `eligible` wins; an `off` flag never limits (the old path applies everywhere)."""
    def limit(slug, body):
        ts = body["tileSources"]
        ts["waterLevel"]["lakes"] = ["Guntersville|AL", "Lake Hartwell|SC"]
        ts["clarity"]["eligible"] = slug in ("guntersville-al", "hartwell-sc", "wheeler-al")
        if slug == "wheeler-al":
            ts["clarity"]["status"] = "FALLBACK"
        ts["temperature"]["lakes"] = ["Guntersville|AL"]                                         # flag off: ignored
    f = Fetch(overlay={"tileSources": SYNTHETIC["tileSources"]}, mutate=limit, fail={"hartwell-sc": OSError("down")})
    _, db = run(f)
    T = db.writes[0][CSP.NODE]["tiles"]
    assert T["waterLevel"]["coverage"] == {"ok": 1, "fallback": 0, "unknown": 1, "total": 2}
    assert T["waterLevel"]["lakes"]["Wheeler|AL"]["eligible"] is False and T["waterLevel"]["lakes"]["Guntersville|AL"]["eligible"] is True
    assert T["clarity"]["coverage"] == {"ok": 1, "fallback": 1, "unknown": 1, "total": 3}
    assert T["temperature"]["coverage"]["total"] == 17
    assert CSP.eligible(None, "x") and CSP.eligible({"flag": "serve", "lakes": ["a"]}, "a") and not CSP.eligible({"flag": "serve", "lakes": ["a"]}, "b")


def test_dry_run_computes_without_writing():
    db = Db()
    res = CSP.stage(Live(), db, NOW, write=False, env=ON, fetch=Fetch())
    assert res["state"] == "COMPUTED" and db.writes == []
