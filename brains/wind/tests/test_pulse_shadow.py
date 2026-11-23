"""The Pulse 7-day shadow runner (tools/ops/wind_pulse_shadow.py; protocol wind-pulse-shadow-v1, decision D4). Local only: tmp archives, no network,
no database. The re-seal must leave the archive on disk byte-for-byte unchanged."""
import datetime as dt
import hashlib
import json
import os
import sys
import uuid

import pytest

import artifact_entry as E
from sector_wind.brain.lakes import WIND_LAKE_IDS
from sector_wind.ingest import verified_release
from test_brain import CFG, DIRECTORY, NOW, make_store

TOOLS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tools", "ops")
if not os.path.isdir(TOOLS):                     # the Wind package gate runs these tests in a clean copy without the repo's tools/ops
    pytest.skip("repo tools/ops is not in this copy", allow_module_level=True)
sys.path.insert(0, TOOLS)
import wind_pulse_shadow as S                                                      # noqa: E402

UTC = dt.timezone.utc
START = dt.datetime(2026, 11, 24, 0, 0, tzinfo=UTC)


def _tree_digest(root):
    h = hashlib.sha256()
    for dp, _, fs in sorted(os.walk(root)):
        for f in sorted(fs):
            p = os.path.join(dp, f)
            h.update(os.path.relpath(p, root).encode() + b"\0" + open(p, "rb").read())
    return h.hexdigest()


class _NothingLive:                                   # the live Brain database during the shadow: Wind is not publishing, so nothing changes
    def get(self, path, shallow=False):
        return None


def _sealed(tmp_path):
    from sector_wind.brain.live_previous import live_previous
    st = make_store(tmp_path / "archive")
    rep, built = E.build(st, CFG, now=NOW, run_summary=None, execution_id=str(uuid.uuid4()), code_version="wind@test",
                         release=verified_release(), directory=DIRECTORY, previous=live_previous(_NothingLive()))
    assert rep["ok"], rep.get("errors")
    return st, built.artifact


def _stub(at: str, mutations=()):
    return {"envelope": "publish-artifact-v2", "lineage": {"brainId": "wind", "generatedAt": at, "artifactId": f"sha256:{at}"},
            "sections": [{"artifactSchema": "wind-lake-state-v1", "mutations": list(mutations)}]}


# ── C2: re-seal ──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_a_reseal_of_the_same_hour_is_equal_and_leaves_the_archive_untouched(tmp_path):
    st, art = _sealed(tmp_path)
    before = _tree_digest(tmp_path / "archive")
    rec = S.reseal(f"local:{tmp_path / 'archive'}", art, reader=_NothingLive(), directory=DIRECTORY)
    assert rec["equal"] is True and rec["originalWritesetSha256"] == rec["resealWritesetSha256"] and rec["differingPaths"] == []
    assert _tree_digest(tmp_path / "archive") == before


def test_a_changed_write_is_caught_and_named(tmp_path):
    _, art = _sealed(tmp_path)
    m = next(m for s in art["sections"] for m in s["mutations"] if m["path"].endswith("/states/wind"))
    m["value"] = {**m["value"], "sustainedMph": 99.0}
    rec = S.reseal(f"local:{tmp_path / 'archive'}", art, reader=_NothingLive(), directory=DIRECTORY)
    assert rec["equal"] is False and m["path"] in rec["differingPaths"]


def test_a_reseal_after_a_later_run_is_refused(tmp_path):
    st, art = _sealed(tmp_path)
    later = NOW + dt.timedelta(hours=1)
    st.put_json(f"runs/{later:%Y%m%d}/{later:%H%M%S}.json", {"runAt": S._iso(later), "errors": []})
    with pytest.raises(ValueError, match="later run"):
        S.reseal(f"local:{tmp_path / 'archive'}", art, reader=_NothingLive(), directory=DIRECTORY)


def test_the_writeset_hash_ignores_only_duration(tmp_path):
    a = _stub("2026-11-24T00:05:00Z", [{"op": "SET", "path": "/brains/wind/x", "value": {"durationMs": 5, "v": 1}}])
    b = json.loads(json.dumps(a)); b["sections"][0]["mutations"][0]["value"]["durationMs"] = 999
    c = json.loads(json.dumps(a)); c["sections"][0]["mutations"][0]["value"]["v"] = 2
    d = json.loads(json.dumps(a)); d["lineage"]["generatedAt"] = "2026-11-24T00:06:00Z"
    assert S.writeset_sha256(a) == S.writeset_sha256(b) == S.writeset_sha256(d) != S.writeset_sha256(c)


def test_a_reseal_without_the_live_previous_state_is_refused(tmp_path):
    _, art = _sealed(tmp_path)
    with pytest.raises(ValueError, match="read-rtdb"):
        S.reseal(f"local:{tmp_path / 'archive'}", art, read_rtdb=False, directory=DIRECTORY)


def test_cli_reseal_writes_one_record_and_never_overwrites(tmp_path, monkeypatch):
    import sector_brain_platform as BP
    from sector_wind.brain import publish as P
    monkeypatch.setattr(P, "fetch_directory", lambda *a, **k: DIRECTORY)
    monkeypatch.setattr(BP, "BrainRtdb", lambda url, tokens: _NothingLive())
    monkeypatch.setattr(BP, "TokenProvider", lambda: None)
    _, art = _sealed(tmp_path)
    (tmp_path / "a.json").write_text(json.dumps(art))
    args = ["reseal", "--store", f"local:{tmp_path / 'archive'}", "--artifact", str(tmp_path / "a.json"), "--out", str(tmp_path / "r.json"), "--read-rtdb"]
    assert S.main(args) == 0 and json.loads((tmp_path / "r.json").read_text())["equal"] is True
    assert S.main(args) == 2
    assert S.main(["reseal", "--store", "gs://b/wind/v1", "--artifact", "x", "--out", str(tmp_path / "r2.json")]) == 2


# ── C1, C2 accounting ────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def _hours(n_missing: int, late_minute: int | None = None):
    arts = []
    for h in range(24 * 7):
        if h < n_missing:
            continue
        t = START + dt.timedelta(hours=h, minutes=late_minute if (late_minute is not None and h == 24 * 7 - 1) else 5)
        arts.append(_stub(S._iso(t)))
    return arts


def test_c1_needs_95_percent_and_every_miss_explained():
    miss8 = [S._iso(START + dt.timedelta(hours=h)) for h in range(8)]
    assert S.c1_completeness(_hours(8), START, 7, {})["status"] == "FAIL"                      # 160/168 = 95.2% but unexplained
    assert S.c1_completeness(_hours(8), START, 7, {h: "NOAA NBM outage 2026-11-24" for h in miss8})["status"] == "PASS"
    miss9 = [S._iso(START + dt.timedelta(hours=h)) for h in range(9)]
    assert S.c1_completeness(_hours(9), START, 7, {h: "x" for h in miss9})["status"] == "FAIL"   # 159/168 = 94.6%


def test_c1_a_seal_later_than_20_minutes_is_a_miss():
    r = S.c1_completeness(_hours(0, late_minute=25), START, 7, {})
    assert r["missed"] == [S._iso(START + dt.timedelta(hours=24 * 7 - 1))] and r["status"] == "FAIL"


def _window_art(day: int):
    return _stub(S._iso(START + dt.timedelta(days=day, hours=3, minutes=5)), [{"op": "SET", "path": f"/brains/wind/d{day}", "value": day}])


def _rec(art, equal=True, original=None):
    return {"schema": S.RESEAL_SCHEMA, "generatedAt": art["lineage"]["generatedAt"], "equal": equal, "artifactId": art["lineage"]["artifactId"],
            "originalWritesetSha256": original or S.writeset_sha256(art)}


def test_c2_needs_one_equal_reseal_per_day_of_a_stored_artifact():
    arts = [_window_art(d) for d in range(7)]
    assert S.c2_determinism([_rec(a) for a in arts], START, 7, arts)["status"] == "PASS"
    r = S.c2_determinism([_rec(a) for a in arts[:6]], START, 7, arts)
    assert r["status"] == "FAIL" and r["daysMissing"] == ["2026-11-30"]
    r = S.c2_determinism([_rec(a, equal=(i != 3)) for i, a in enumerate(arts)], START, 7, arts)
    assert r["unequal"] == [arts[3]["lineage"]["artifactId"]] and r["status"] == "FAIL"


def test_c2_rejects_records_for_unknown_artifacts_or_a_wrong_original_hash():
    arts = [_window_art(d) for d in range(7)]
    r = S.c2_determinism([_rec(a) for a in arts], START, 7, arts[1:])                   # day 0's artifact is not in the report's set
    assert r["status"] == "FAIL" and r["unknownArtifact"] == [arts[0]["lineage"]["artifactId"]]
    recs = [_rec(a) for a in arts]
    recs[2] = _rec(arts[2], original="0" * 64)                                          # a record that claims a different original
    r = S.c2_determinism(recs, START, 7, arts)
    assert r["status"] == "FAIL" and r["originalHashMismatch"] == [arts[2]["lineage"]["artifactId"]]


# ── C3 skill ─────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────

class _MetarStore:
    def __init__(self, obs_by_day):
        self.obs_by_day = obs_by_day

    def get_json(self, key):
        return {"observations": self.obs_by_day.get(key, [])}


def _skill_case(n: int, offset_mph: float):
    wl, lid = next(iter(WIND_LAKE_IDS.items()))
    cfg = {"stations": {"KTEST": {"lake": wl}}}
    days, arts = {}, []
    for h in range(n):
        t = START + dt.timedelta(hours=h)
        obs_ms = 3.0 + (h % 5)
        days.setdefault(f"metar/{t:%Y%m%d}.json.gz", []).append({"station": "KTEST", "validTime": S._iso(t), "speedMS": obs_ms})
        st = {"lakeId": lid, "kind": "analysis", "analysis": {"analysisTime": S._iso(t)}, "sustainedMph": obs_ms * S.MPH_PER_MS + offset_mph}
        arts.append(_stub(S._iso(t + dt.timedelta(minutes=5)), [{"op": "SET", "path": "/lakes/X/states/wind", "value": st}]))
    return arts, _MetarStore(days), cfg


EVIDENCE = {"metrics": {"speedMaeMph": 2.189}}


def test_c3_passes_within_ten_percent_of_the_recorded_mae():
    arts, store, cfg = _skill_case(210, 1.0)
    r = S.c3_skill(arts, store, cfg, EVIDENCE)
    assert r["status"] == "PASS" and r["pairs"] == 210 and abs(r["maeMph"] - 1.0) < 1e-6 and r["barMph"] == 2.408


def test_c3_fails_above_the_bar_and_is_not_evaluated_on_too_few_pairs():
    assert S.c3_skill(*_skill_case(210, 2.5)[:3], EVIDENCE)["status"] == "FAIL"
    assert S.c3_skill(*_skill_case(150, 0.0)[:3], EVIDENCE)["status"] == "NOT_EVALUATED"


def test_c3_ignores_forecast_states_and_off_hour_analyses():
    arts, store, cfg = _skill_case(210, 0.0)
    for a in arts[:20]:
        a["sections"][0]["mutations"][0]["value"]["kind"] = "forecast"
    for a in arts[20:40]:
        v = a["sections"][0]["mutations"][0]["value"]
        v["analysis"]["analysisTime"] = v["analysis"]["analysisTime"].replace(":00:00Z", ":15:00Z")
    assert S.c3_skill(arts, store, cfg, EVIDENCE)["pairs"] == 170


# ── C4 bounds, C5 Mac mini ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_c4_a_real_sealed_artifact_is_in_bounds_for_the_pinned_list(tmp_path):
    _, art = _sealed(tmp_path)
    lakes = json.load(open(S.STAGE))["watchdog"]["lakes"]
    ok = S.c4_bounds([art], lakes)
    assert ok["status"] == "PASS" and ok["stateLakes"] == sorted(["Guntersville_AL", "Pickwick_Lake_TN", "Wheeler_AL", "Wilson_AL"])
    r = S.c4_bounds([art], [k for k in lakes if k != "Guntersville_AL"])
    assert r["status"] == "FAIL" and r["lakesOutsideList"] == ["Guntersville_AL"]
    bad = _stub("2026-11-24T00:05:00Z", [{"op": "SET", "path": "/brains/water-clarity/x", "value": 1}])
    assert S.c4_bounds([art, bad], lakes)["notOwned"] == ["/brains/water-clarity/x"]


def test_c5_sleep_and_retention():
    log_sleep = "2026-11-25 01:00:00 -0600 Sleep               \tEntering Sleep state due to 'Idle Sleep'\n"
    log_clean = "2026-11-25 01:00:00 -0600 Wake                \tWake from Normal Sleep\n2026-11-20 01:00:00 -0600 Sleep  \told\n"
    assert S.c5_mac_mini(log_sleep, [], START, 7)["status"] == "FAIL"
    assert S.c5_mac_mini(log_clean, [], START, 7)["status"] == "PASS"
    assert S.c5_mac_mini(None, [], START, 7)["status"] == "NOT_EVALUATED"
    old = ["rtma/guntersville/20261001/0000.json.gz", "rtma/guntersville/20261130/0000.json.gz"]
    r = S.c5_mac_mini(log_clean, old, START, 7)
    assert r["status"] == "FAIL" and r["retentionOverdue"] == 1


# ── the protocol is pinned ───────────────────────────────────────────────────────────────────────────────────────────────────────────────────

def test_the_protocol_doc_states_the_runner_thresholds():
    doc = open(S.PROTOCOL_DOC, encoding="utf-8").read()
    assert S.PROTOCOL_ID in doc and S.protocol_sha256()
    for needle in ("95%", "20 min", "1.10", "200 pairs", "30 days", "durationMs", "7 consecutive days", "No other live Wind writer",
                   "recomputes the original write-set hash", "stateLakes"):
        assert needle in doc, needle


def test_report_cli_is_incomplete_without_the_window_evidence(tmp_path, capsys):
    _sealed(tmp_path)
    (tmp_path / "arts").mkdir(); (tmp_path / "reseals").mkdir()
    rc = S.main(["report", "--artifacts", str(tmp_path / "arts"), "--store", f"local:{tmp_path / 'archive'}", "--start", S._iso(START),
                 "--reseals", str(tmp_path / "reseals")])
    out = json.loads(capsys.readouterr().out)
    assert rc == 1 and out["verdict"] == "FAIL" and out["criteria"]["C1"]["sealedOnTime"] == 0    # no seals at all is a failed window
    assert S.main(["report", "--artifacts", "x", "--store", "local:/x", "--start", "2026-11-24T00:30:00Z", "--reseals", "x"]) == 2
