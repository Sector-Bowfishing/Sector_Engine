"""Protocol WSW-2026-11-25-R6 runner (shared run ledger, PW station selection, inputs, accounting, budget, fit, scoring), SYNTHETIC
fixtures, offline.
No test reaches GitHub: #51 is a fake issue, and the Mac mini session's 'post once' is simulated by posting the pending text."""
import datetime as dt
import io
import json
import os
import random
import shutil
import subprocess
import sys
import urllib.error
from pathlib import Path

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import protocol_run_ledger as PRL  # noqa: E402
import wind_strong_wind as W  # noqa: E402

UTC = dt.timezone.utc
FOLDER = os.path.dirname(W.PROTOCOL)
SUPERSEDED = [os.path.join(FOLDER, f"WSW-2026-11-23{x}.protocol.json") for x in ("", "-R2", "-R3", "-R4", "-R5")]
FLAT_FIT = {"knots": [[0.0, 0.0], [10.0, 0.0]]}
CURRENT = {}
ISSUE_PATH = "repos/Sector-Bowfishing/Sector_Ops/issues/51/comments?per_page=100"


class Issue:
    """A fake Sector_Ops #51 behind `gh api --paginate` (pages of 3, concatenated arrays)."""

    def __init__(self):
        self.comments, self.next_id = [], 1000
        self.clock = dt.datetime(2000, 1, 1, tzinfo=UTC)

    def post(self, body):
        self.clock += dt.timedelta(minutes=1)
        t = self.clock.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.comments.append({"id": self.next_id, "created_at": t, "updated_at": t, "body": body, "user": {"login": "mini"},
                              "html_url": f"https://example.invalid/51#issuecomment-{self.next_id}"})
        self.next_id += 1

    def __call__(self, path):
        assert path == ISSUE_PATH, path
        pages = [self.comments[i:i + 3] for i in range(0, len(self.comments), 3)] or [[]]
        return "".join(json.dumps(p) for p in pages)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.delenv(PRL.ENV_ROOT, raising=False)
    monkeypatch.setattr(PRL, "_gh_api", lambda path: (_ for _ in ()).throw(AssertionError(f"real gh reached: {path}")))
    monkeypatch.setattr(W, "_sleep", lambda s: None)


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A SYNTHETIC research root (the research-path folder for wind) with --out inside it, a fake #51, and the anchor posted."""
    root = tmp_path / "Sector Research" / "wind-brain"
    out = root / "run"
    out.mkdir(parents=True)
    issue = Issue()
    monkeypatch.setattr(W, "_open_ledger", lambda forbid_under=(): PRL.Ledger(root, W.PROTOCOL_ID, W.REGISTERED_SHA256, forbid_under,
                                                                          result_steps=W.RESULT_STEPS, gh=issue))
    monkeypatch.setattr(W, "publish", lambda led, key, kind, text: issue.post(text) or "posted")    # the session posts once
    assert W.main(["anchor"]) == 0
    CURRENT["issue"] = issue
    return out


def _clock(monkeypatch, iso):
    monkeypatch.setattr(W, "_utcnow", lambda: dt.datetime.fromisoformat(iso).replace(tzinfo=UTC))


def _acc(rows, **kw):
    """Accounting for SYNTHETIC rows (4 stations): planned = built unless overridden."""
    per = len(rows) // 4
    by = {}
    for r in rows:
        by[r["station"]] = by.get(r["station"], 0) + (r["obs"] is None)
    a = {"plannedPairs": per, "plannedRows": len(rows), "plannedRowsPerStation": per, "plannedCycles": per, "missingCycles": 0,
         "incompleteCycles": 0, "rowsBuilt": len(rows), "rowsNotBuilt": 0, "obsMissing": sum(r["obs"] is None for r in rows),
         "obsMissingByStation": by, "missingObsDays": [],
         "b0Missing": sum(r["b0"] is None for r in rows), "p90Missing": sum(r["p90"] is None for r in rows)}
    a.update(kw)
    return a


def _put_fit(out):
    """A counted fit:cal_h1 through the runner's own result_step (begin, start, compute, complete, result)."""
    _, psha = W.load_protocol()
    led = W._open_ledger()

    def compute(run):
        (out / W.FIT_FILE).write_text(json.dumps(dict(FLAT_FIT, protocolSha256=psha)))
        return {"fit": out / W.FIT_FILE}, {"n": 0, "runNumber": run}
    entry, _ = W.result_step(led, "fit", "fit:cal_h1", {"synthetic": True}, {}, compute)
    return entry["outputs"]["fit"]


def _store(out, window):
    root = out / window / "store"
    for d in ("nbm", "metar", "grids"):
        (root / d).mkdir(parents=True, exist_ok=True)
        (root / d / "synthetic.json").write_text("{}")
    return root


def _put_rows(out, window, rows):
    """A counted rows:<window> with bound inputs (as `rows` does)."""
    store = _store(out, window)
    led = W._open_ledger()
    files = W.input_files(window, str(store), str(out / "pw" / W.STATIONS_FILE))
    led.bind_inputs("rows", f"rows:{window}", files)

    def compute(run):
        (out / window / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        (out / window / "accounting.json").write_text(json.dumps(_acc(rows)))
        return {"rows": out / window / "rows.jsonl", "accounting": out / window / "accounting.json"}, {"runNumber": run}
    W.result_step(led, "rows", f"rows:{window}", {"synthetic": True}, files, compute)


def _feature(sid, lat, lon, ab="2010-01-01"):
    return {"type": "Feature", "id": sid, "properties": {"sid": sid, "sname": f"SYNTHETIC {sid}", "archive_begin": ab},
            "geometry": {"type": "Point", "coordinates": [lon, lat]}}


def _synthetic_networks():
    """SYNTHETIC IEM listings: candidates placed offshore (about 28 N), far from every real excluded station; the iem-wind ids with
    their real coordinates so `exclusions` can find them."""
    nets = {"AL_ASOS": [_feature(f"A0{i}", 28.0, -88.0 + 0.4 * i) for i in range(1, 5)] + [_feature("HSV", 34.6404, -86.7861)],
            "TN_ASOS": [_feature(f"T0{i}", 28.3, -88.0 + 0.4 * i) for i in range(1, 5)] + [_feature("BNA", 36.1245, -86.6782), _feature("MEM", 35.0564, -89.9864)],
            "MS_ASOS": [_feature(f"M0{i}", 27.7, -88.0 + 0.4 * i) for i in range(1, 5)],
            "GA_ASOS": [_feature(f"G0{i}", 28.6, -88.0 + 0.4 * i) for i in range(1, 5)],
            "OK_ASOS": [_feature("TUL", 36.1984, -95.8881)], "MO_ASOS": [_feature("STL", 38.7487, -90.3700)], "AR_ASOS": [_feature("FSM", 35.3366, -94.3674)]}
    return nets


def _listing_bytes(nets):
    return {net: json.dumps({"type": "FeatureCollection", "features": feats}).encode() for net, feats in nets.items()}


def _put_select(out, monkeypatch, nets=None):
    """A counted select:pw through the runner's own command, with SYNTHETIC listings (no network) and a SYNTHETIC W-NOW-3 list."""
    csv = out.parent / "w-now-3-stations.csv"
    csv.write_text("station,lat,lon,nLakes\n2A0,35.4817,-84.9322,1\n1F0,34.147,-97.1226,1\n")
    monkeypatch.setattr(W, "W_NOW_3_STATIONS_SHA256", W.sha256_file(str(csv)))
    monkeypatch.setattr(W, "fetch_listings", lambda budget, opener=None: _listing_bytes(nets or _synthetic_networks()))
    assert W.main(["select", "--window", "pw", "--out", str(out), "--w-now-3-stations", str(csv)]) == 0
    return out / "pw" / W.STATIONS_FILE


# ------------------------------------------------------------------------------------------------------------------ protocol
def test_protocol_is_pinned_and_matches_runner_constants():
    proto, sha = W.load_protocol()
    assert sha == W.REGISTERED_SHA256 and proto["protocolId"] == W.PROTOCOL_ID == "WSW-2026-11-25-R6"
    assert [s["protocolId"] for s in proto["supersedes"]] == ["WSW-2026-11-23-R5", "WSW-2026-11-23-R4", "WSW-2026-11-23-R3", "WSW-2026-11-23-R2", "WSW-2026-11-23"]
    assert proto["status"] == "PRE-REGISTERED" and proto["registration"]["draftSha256"] == "1149d9d9dcfdc7e29ae28c493b5ab483824e0d4367ee3a1a4adedcabd3e09bf7"
    pw = proto["pwStations"]
    assert pw["archiveBeginOnOrBefore"] == W.PW_ARCHIVE_BEGIN_MAX and f"'{W.PW_SALT}'" in pw["selection"] and W.PW_SALT in pw["selectionOrder"]
    assert all(n in pw["candidates"] for n in W.PW_NETWORKS) and all(n in pw["metadataSource"] for n in W.PW_NETWORKS + W.COORD_NETWORKS)
    assert f"{W.PW_BUFFER_KM} km" in pw["distanceRule"] and f"{W.PW_COUNT}" in pw["selectionOrder"] and f"has {W.PW_MAX_PER_STATE}" in pw["selectionOrder"]
    assert W.W_NOW_3_STATIONS_SHA256 in pw["excludedCoordinates"] and W.POINTS_JSON_SHA256 in pw["excludedCoordinates"]
    assert all(sid in pw["excludedCoordinates"] for sid in W.IEM_WIND_IDS) and f"{W.PW_BOX_DEG}" in pw["carrier"]
    assert "select:pw" in proto["runBinding"]["selectStep"] and "before fit" in proto["runBinding"]["selectStep"]
    assert sorted(proto["runBinding"]["resultSteps"]) == sorted(W.RESULT_STEPS)
    assert proto["runBinding"]["keys"] == W.ledger_keys()
    assert tuple(proto["stations"]["ids"]) == W.STATION_IDS and proto["stations"]["lakesJsonSha256"] == W.LAKES_JSON_SHA256
    assert proto["forecastRows"]["leads"] == list(W.LEADS)
    assert proto["methods"]["M-B"]["fit"]["levels"] == list(W.LEVELS)
    assert proto["methods"]["M-B"]["fit"]["minimumRows"] == W.MIN_FIT_ROWS
    for key, w in (("CAL_H1", "cal_h1"), ("PW", "pw"), ("H2", "h2")):
        lo, hi = proto["windows"][key]["inits"]
        assert (lo, hi) == (f"{W.WINDOWS[w][0]:%Y-%m-%dT%H:%MZ}", f"{W.WINDOWS[w][1]:%Y-%m-%dT%H:%MZ}")
    assert proto["budget"]["downloadBytesPerWindow"] == W.BUDGET_BYTES and proto["budget"]["wallClockHoursPerWindow"] * 3600 == W.BUDGET_SECONDS
    assert set(proto["outputsAndAdmission"]["labels"]) == set(W.LABELS)
    assert {h.split()[0] for h in proto["budget"]["hosts"]} == W.ALLOWED_HOSTS
    assert "5%" in proto["accounting"]["truthSideGaps"] and W.MAX_OBS_MISSING == 0.05 and W.MAX_OBS_MISSING_STATION == 0.15


def test_superseded_and_changed_protocols_are_refused(tmp_path):
    for old in SUPERSEDED:
        with pytest.raises(W.Refused):
            W.load_protocol(old)
    p = tmp_path / "p.json"
    shutil.copy(W.PROTOCOL, p)
    W.load_protocol(str(p))
    p.write_text(p.read_text().replace("PRE-REGISTERED", "EDITED"))
    with pytest.raises(W.Refused):
        W.load_protocol(str(p))


def test_superseded_protocols_are_byte_identical():
    for old, sha in zip(SUPERSEDED, ("b9a55721f7a6d2853462c1080bbec384c3a30e3429fce70b10c2872c77449346",
                                     "ba05492be82102fdba170b8dd5181ec557505622246e6a780c52a6ffc129633b",
                                     "82f96596197d6af32e43b9e01ce152e922f3a0c0a42993641993a2da0fda68a2",
                                     "c0e86f6afa9de57d33c71d4eb049d4b1c95e403ad4a9c966edd16c7e9aaf77ca",
                                     "a3578415c6b9f8d6a678e567234e1775512a3db9ea53ede1451f476128d0b565")):
        assert W.sha256_file(old) == sha


def test_no_hidden_clock_or_protocol_flags():
    for flag in ("--now", "--protocol", "--boot", "--fit", "--rows", "--max-pairs"):
        with pytest.raises(SystemExit):
            W.main(["verify", flag, "x"])


# ------------------------------------------------------------------------------------------------------------------- windows
def test_night_pairs_are_synoptic_night_only():
    for w in ("cal_h1", "pw", "h2"):
        p = W.night_pairs(w)
        assert all(t.hour in W.SYNOPTIC and 1 <= (t + dt.timedelta(hours=l)).hour <= 8 for t, l in p)
    days = (W.WINDOWS["pw"][1].date() - W.WINDOWS["pw"][0].date()).days + 1
    assert len(W.night_pairs("pw")) == 6 * days
    assert {(t.hour, l) for t, l in W.night_pairs("pw")} == {(0, 1), (0, 3), (0, 6), (6, 1), (12, 18), (18, 12)}


def test_cal_h1_never_reaches_h2_truth():
    pairs = W.night_pairs("cal_h1")
    assert all(t + dt.timedelta(hours=l) < W.H2_START for t, l in pairs)
    days = (W.WINDOWS["cal_h1"][1].date() - W.WINDOWS["cal_h1"][0].date()).days + 1
    assert len(pairs) == 6 * days - 2                                    # 2026-10-06 12Z+18 and 18Z+12 dropped
    assert max(W.obs_days("cal_h1", pairs)) == dt.date(2026, 10, 6)
    assert W.obs_end("cal_h1") < W.H2_START
    assert max(W.obs_days("h2", W.night_pairs("h2"))) > dt.date(2026, 12, 31)


def test_pw_is_one_generation_and_after_the_iem_wind_years():
    lo, hi = W.WINDOWS["pw"]
    assert lo >= dt.datetime(2025, 1, 2, tzinfo=UTC)
    assert hi < dt.datetime(2025, 5, 27, 12, tzinfo=UTC)
    assert hi < dt.datetime(2025, 11, 1, tzinfo=UTC)


def test_month_by_month_covers_the_window_exactly():
    months = ["2025-01", "2025-02", "2025-03", "2025-04", "2025-05"]
    assert [p for m in months for p in W.month_pairs("pw", m)] == W.night_pairs("pw")
    with pytest.raises(W.Refused):
        W.month_pairs("pw", "2025-11")


def test_h2_is_sealed_by_the_system_clock(monkeypatch):
    _clock(monkeypatch, "2026-12-31T23:59:00")
    with pytest.raises(W.Refused):
        W.guard_h2("h2", "score")
    W.guard_h2("pw", "score")
    _clock(monkeypatch, "2027-01-01T00:00:00")
    W.guard_h2("h2", "score")


def test_fit_refuses_rows_outside_cal_h1_and_gappy_cal_h1():
    ok = {"init": "2026-07-01T00:00:00Z", "valid": "2026-07-01T01:00:00Z", "lead": 1, "obs": 3.0, "b0": 2.0, "station": "HSV", "p90": None}
    acc = _acc([ok] * 4)
    assert W.fit_pairs([ok], acc) == [(2.0, 3.0)]
    for bad in ({"init": "2025-03-01T00:00:00Z", "valid": "2025-03-01T01:00:00Z"},
                {"init": "2026-10-06T18:00:00Z", "valid": "2026-10-07T06:00:00Z"}):
        with pytest.raises(W.Refused):
            W.fit_pairs([dict(ok, **bad)], acc)
    for kw in ({"missingCycles": 1}, {"missingObsDays": ["2026-07-01"]}, {"obsMissing": 1}):
        with pytest.raises(W.Refused):
            W.fit_pairs([ok], dict(acc, **kw))


# ---------------------------------------------------------------------------------------------------------- fit sha ordering
def test_keys_are_fixed_by_the_protocol():
    assert W.key_for("fetch", "pw", "smoke") == "fetch:pw:smoke" and W.key_for("rows", "h2") == "rows:h2" and W.key_for("select", "pw") == "select:pw"
    for bad in (("fetch", "pw", "2025-06"), ("fetch", "cal_h1", "smoke"), ("rows", "cal_h1", None), ("select", "h2", None), ("select", "cal_h1", None)):
        with pytest.raises(W.Refused):
            W.key_for(*bad)


def test_no_step_runs_before_the_anchor(tmp_path, monkeypatch):
    root = tmp_path / "Sector Research" / "wind-brain"
    (root / "run").mkdir(parents=True)
    issue = Issue()
    monkeypatch.setattr(W, "_open_ledger", lambda forbid_under=(): PRL.Ledger(root, W.PROTOCOL_ID, W.REGISTERED_SHA256, forbid_under,
                                                                          result_steps=W.RESULT_STEPS, gh=issue))
    assert W.main(["fetch", "--window", "cal_h1", "--month", "2026-05", "--out", str(root / "run"), "--min-free-gb", "0"]) == 3
    assert not issue.comments and not any(e["status"] == PRL.STARTED for e in W._open_ledger().entries())


def test_past_window_steps_need_the_counted_fit_sha(home, monkeypatch):
    out = str(home)
    _put_select(home, monkeypatch)
    assert W.main(["fetch", "--window", "pw", "--month", "smoke", "--out", out]) == 3     # no counted fit
    fsha = _put_fit(home)
    assert any(c["body"].startswith(f"Run result: {W.PROTOCOL_ID} fit fit:cal_h1") for c in CURRENT["issue"].comments)
    for cmd in ("rows", "score"):
        assert W.main([cmd, "--window", "pw", "--out", out]) == 3
        assert W.main([cmd, "--window", "pw", "--out", out, "--fit-sha", "0" * 64]) == 3
    assert W.main(["fetch", "--window", "pw", "--month", "smoke", "--out", out, "--fit-sha", "0" * 64]) == 3
    assert W.main(["fetch", "--window", "pw", "--month", "smoke", "--out", out, "--fit-sha", fsha, "--min-free-gb", "1e9"]) == 3
    (home / W.FIT_FILE).write_text(json.dumps(dict(FLAT_FIT, protocolSha256=W.REGISTERED_SHA256, other=1)))
    assert W.main(["fetch", "--window", "pw", "--month", "smoke", "--out", out, "--fit-sha", fsha]) == 3   # --out file is not the ledger's
    _clock(monkeypatch, "2026-11-23T23:00:00")
    assert W.main(["fetch", "--window", "h2", "--month", "2026-10", "--out", out, "--fit-sha", fsha]) == 3


def test_out_must_be_inside_the_research_root_and_lakes_json_is_pinned(home, tmp_path, monkeypatch):
    elsewhere = tmp_path / "bootdisk"
    elsewhere.mkdir()
    assert W.main(["fit", "--out", str(elsewhere)]) == 3
    assert W.main(["fit", "--out", str(home.parent)]) == 3                               # the root itself is not an --out
    monkeypatch.setattr(W, "LAKES_JSON_SHA256", "0" * 64)
    with pytest.raises(W.Refused):
        W.check_lakes()
    monkeypatch.undo()
    W.check_lakes()


def test_a_second_fit_is_refused_from_any_out(home, monkeypatch):
    _put_select(home, monkeypatch)
    _put_fit(home)
    other = home.parent / "run2"
    other.mkdir()
    assert W.main(["fit", "--out", str(other)]) == 3
    assert W._open_ledger().require("fit", "fit:cal_h1")["outputs"]["fit"] == W.sha256_file(str(home / W.FIT_FILE))


def test_a_fetch_abort_allows_a_retry_and_a_completed_month_is_not_refetched(home, monkeypatch):
    calls = []

    def fake_fetch(window, out, max_pairs, month, budget, min_free_gb, cfg=None):
        calls.append(month)
        if len(calls) == 1:
            raise OSError("synthetic I/O error")
        return {"budget": {"bytes": 0}}
    monkeypatch.setattr(W, "do_fetch", fake_fetch)
    _put_select(home, monkeypatch)
    args = ["fetch", "--window", "cal_h1", "--month", "2026-05", "--out", str(home), "--min-free-gb", "0"]
    with pytest.raises(OSError):
        W.main(args)
    assert W.main(args) == 0                                                             # attempt 2 after ABORTED_BEFORE_RESULT
    assert W.main(args) == 3                                                             # completed: one-shot
    statuses = [e["status"] for e in W._open_ledger().entries() if e["key"] == "fetch:cal_h1:2026-05"]
    assert statuses == [PRL.STARTED, PRL.ABORTED, PRL.STARTED, PRL.COMPLETED]


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Opener:
    def __init__(self, script):
        self.script, self.urls = list(script), []

    def open(self, req, timeout=None):
        self.urls.append(req.full_url)
        x = self.script.pop(0)
        if isinstance(x, Exception):
            raise x
        return _Resp(x)


class _PartialFail(io.BytesIO):
    """Reads one chunk, then the connection drops."""
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n=-1):
        if self.tell() == 0:
            return super().read(5)
        raise ConnectionResetError("dropped")


def test_every_attempt_is_host_checked_counted_and_redirects_refused(tmp_path):
    t = [0.0]
    b = W.Budget(str(tmp_path / "budget.json"), max_bytes=1000, max_seconds=100, clock=lambda: t[0])

    class Partial(_Opener):
        def open(self, req, timeout=None):
            self.urls.append(req.full_url)
            x = self.script.pop(0)
            return _PartialFail(b"x" * 50) if x == "partial" else _Resp(x)

    op = Partial(["partial", b"y" * 7])
    f = W.budgeted_fetch(b, RuntimeError, op, sleep=lambda s: None)
    assert f("https://mesonet.agron.iastate.edu/a") == b"y" * 7
    assert b.bytes == 12 and b.attempts == 2                                # the dropped attempt's 5 bytes count
    for bad in ("https://example.org/a", "http://mesonet.agron.iastate.edu/a"):
        with pytest.raises(W.Refused):
            f(bad)
    redirect = urllib.error.HTTPError("https://mesonet.agron.iastate.edu/r", 302, "redirect refused", {}, None)
    f2 = W.budgeted_fetch(b, RuntimeError, _Opener([redirect, b"z"]), sleep=lambda s: None)
    with pytest.raises(RuntimeError):
        f2("https://mesonet.agron.iastate.edu/r")                          # not retried, not followed
    assert issubclass(W._NoRedirect, urllib.request.HTTPRedirectHandler)
    with pytest.raises(urllib.error.HTTPError):
        W._NoRedirect().redirect_request(urllib.request.Request("https://mesonet.agron.iastate.edu/r"), None, 302, "", {}, "https://evil.example/")


def test_budget_stops_before_the_next_request_and_is_cumulative(tmp_path):
    t = [0.0]
    b = W.Budget(str(tmp_path / "budget.json"), max_bytes=10, max_seconds=100, clock=lambda: t[0])
    op = _Opener([b"x" * 12, b"never"])
    f = W.budgeted_fetch(b, RuntimeError, op, sleep=lambda s: None)
    f("https://noaa-nbm-grib2-pds.s3.amazonaws.com/a")
    with pytest.raises(W.BudgetExceeded):
        f("https://noaa-nbm-grib2-pds.s3.amazonaws.com/b")
    assert len(op.urls) == 1
    b.save()
    b2 = W.Budget(str(tmp_path / "budget.json"), max_bytes=100, max_seconds=100, clock=lambda: t[0])
    assert b2.bytes == 12
    t[0] = 150.0
    with pytest.raises(W.BudgetExceeded):
        W.budgeted_fetch(b2, RuntimeError, _Opener([b""]))("https://mesonet.agron.iastate.edu/c")


# ------------------------------------------------------------------------------------------------------------------ M-B fit
def test_quantile_type7():
    x = [1.0, 2.0, 3.0, 4.0]
    assert W.quantile(x, 0.5) == 2.5 and W.quantile(x, 0.0) == 1.0 and W.quantile(x, 1.0) == 4.0


def _synthetic_pairs(n=8000, seed=1):
    """SYNTHETIC: forecast low-biased in the upper tail (obs = f + 0.05 f^2)."""
    rng = random.Random(seed)
    return [(f, f + 0.05 * f * f) for f in (rng.gammavariate(2.0, 1.2) for _ in range(n))]


def test_fit_qm_maps_upper_tail_and_is_monotone():
    fit = W.fit_qm(_synthetic_pairs())
    ys = [W.apply_qm(fit, i / 10) for i in range(150)]
    assert all(b >= a for a, b in zip(ys, ys[1:]))
    top = fit["knots"][-1]
    assert abs(W.apply_qm(fit, top[0]) - (top[0] + 0.05 * top[0] ** 2)) < 0.05


def test_fit_refuses_too_few_rows_and_merges_ties():
    with pytest.raises(W.Refused):
        W.fit_qm(_synthetic_pairs(500))
    xs = [k[0] for k in W.fit_qm([(1.0, 1.0)] * 6000 + [(2.0, 3.0)] * 5)["knots"]]
    assert xs == sorted(set(xs))


# ------------------------------------------------------------------------------------------------------------------- scoring
def test_wi4_and_gate_match_production():
    zero_fc = {str(l): W.table([(False, True)] * 5 + [(False, False)] * 50) for l in W.LEADS}
    assert W.wi4_credit(zero_fc) == 0.0 and not W.scoreboard_gate(zero_fc)
    perfect = {str(l): W.table([(True, True)] * 5 + [(False, False)] * 50) for l in W.LEADS}
    assert W.wi4_credit(perfect) == 1.0 and W.scoreboard_gate(perfect)
    half = {str(l): W.table([(True, True)] * 2 + [(False, True)] * 2 + [(True, False)] * 3) for l in W.LEADS}
    assert W.wi4_credit(half) == pytest.approx(2 / 3, abs=1e-3)
    no_events_at_18 = dict(perfect, **{"18": W.table([(False, False)] * 50)})
    assert W.wi4_credit(no_events_at_18) == 0.0 and not W.scoreboard_gate(no_events_at_18)
    no_rows_at_18 = dict(perfect, **{"18": W.table([])})
    assert W.wi4_credit(no_rows_at_18) == 1.0 and W.scoreboard_gate(no_rows_at_18)


def _rows(n_days=60, p90=True, seed=7, start=dt.datetime(2025, 1, 2, tzinfo=UTC)):
    """SYNTHETIC rows: deterministic NBM never reaches 15 mph; P90 does on most strong nights."""
    rng = random.Random(seed)
    rows = []
    for d in range(n_days):
        day = start + dt.timedelta(days=d)
        for t0, lead in ((0, 1), (0, 3), (0, 6), (6, 1), (12, 18), (18, 12)):
            init = day + dt.timedelta(hours=t0)
            valid = init + dt.timedelta(hours=lead)
            for st in ("8A1", "HSV", "MSL", "SNH"):
                strong = rng.random() < 0.06
                obs = rng.uniform(7.0, 10.0) if strong else rng.uniform(0.0, 5.0)
                b0 = min(obs * 0.6, 6.0)
                rows.append({"station": st, "lead": lead, "init": f"{init:%Y-%m-%dT%H:%M:%SZ}", "valid": f"{valid:%Y-%m-%dT%H:%M:%SZ}",
                             "obs": round(obs, 2), "b0": round(b0, 2), "p90": (round(b0 * 1.5, 2) if p90 else None)})
    return rows


def test_score_reports_wi4_and_accounting_beside_every_outcome():
    r = _rows()
    res = W.score(r, FLAT_FIT, _acc(r), "pw", boot_n=200)
    assert res["methods"]["B0"]["pooled"]["pod"] == 0.0 and res["outcome"]["B0"]["wi4Credit"] == 0.0
    assert res["outcome"]["M-A"]["outcome"] == "SUPPORTED" and "wi4Credit" in res["outcome"]["M-A"]
    assert res["outcome"]["M-B"]["outcome"] == "NOT_SUPPORTED"
    assert res["accounting"]["plannedRows"] == len(r) and res["accounting"]["rowsScored"] == len(r)
    assert res["bootstrap"]["lowerPercentile"] == 1.25 and res["labels"] == W.LABELS


def test_missing_forecast_values_count_as_misses_not_drops():
    r = _rows()
    strong = [x for x in r if x["obs"] >= W.T15]
    for x in strong[:10]:
        x["p90"] = None
    res = W.score(r, FLAT_FIT, _acc(r), "pw", boot_n=50)
    full = W.score(_rows(), FLAT_FIT, _acc(_rows()), "pw", boot_n=50)
    a, b = res["methods"]["M-A"]["pooled"], full["methods"]["M-A"]["pooled"]
    assert a["n"] == b["n"] and a["obsEvents"] == b["obsEvents"]          # same rows: nothing dropped
    assert a["misses"] >= b["misses"] + 10 - (b["obsEvents"] - b["hits"] - b["misses"])
    assert res["accounting"]["p90MissingScored"] == 10


def test_cycle_gaps_and_truth_gaps_make_the_result_incomplete():
    r = _rows()
    for kw in ({"missingCycles": 1}, {"incompleteCycles": 2}, {"obsMissing": int(0.06 * len(r))},
               {"obsMissingByStation": {"HSV": int(0.16 * len(r) / 4)}}, {"missingObsDays": ["2025-01-03"]}):
        res = W.score(r, FLAT_FIT, _acc(r, **kw), "pw", boot_n=20)
        assert {res["outcome"][m]["outcome"] for m in ("M-A", "M-B")} == {"INCOMPLETE"} and "bootstrap" not in res
    ok = W.score(r, FLAT_FIT, _acc(r, obsMissing=int(0.04 * len(r)), obsMissingByStation={"HSV": int(0.14 * len(r) / 4)}), "pw", boot_n=20)
    assert ok["outcome"]["M-A"]["outcome"] == "SUPPORTED"


def test_missing_obs_rows_are_counted_not_scored():
    r = _rows()
    for x in r[:40]:
        x["obs"] = None
    res = W.score(r, FLAT_FIT, _acc(r), "pw", boot_n=20)
    assert res["accounting"]["rowsScored"] == len(r) - 40 and res["accounting"]["obsMissing"] == 40


def test_qmd_absent_makes_only_m_a_not_evaluable():
    r = _rows(p90=False)
    res = W.score(r, FLAT_FIT, _acc(r), "pw", boot_n=20)
    assert res["outcome"]["M-A"]["outcome"] == "NOT_EVALUABLE" and res["outcome"]["M-B"]["outcome"] == "NOT_SUPPORTED"


def test_h2_uses_the_four_rule_correction_and_drops_the_shared_night():
    rows = _rows(start=dt.datetime(2026, 10, 7, tzinfo=UTC))
    res = W.score(rows, FLAT_FIT, _acc(rows), "h2", boot_n=100)
    assert res["bootstrap"]["lowerPercentile"] == 0.625
    assert res["accounting"]["rowsNight"] == len([r for r in rows if not r["valid"].startswith("2026-10-07")])


def test_score_is_insufficient_with_few_events_and_deterministic():
    r = _rows(n_days=4)
    assert {W.score(r, FLAT_FIT, _acc(r), "pw", 50)["outcome"][m]["outcome"] for m in ("M-A", "M-B")} == {"INSUFFICIENT_EVENTS"}
    r = _rows()
    assert W.score(r, FLAT_FIT, _acc(r), "pw", 100)["bootstrap"] == W.score(_rows(), FLAT_FIT, _acc(_rows()), "pw", 100)["bootstrap"]


def test_score_is_one_shot_across_outs_and_uses_2000_resamples(home, monkeypatch):
    calls = []
    real = W.score
    monkeypatch.setattr(W, "score", lambda rows, fit, acc, window: calls.append(window) or real(rows, fit, acc, window, boot_n=20))
    out = str(home)
    _put_select(home, monkeypatch)
    fsha = _put_fit(home)
    _put_rows(home, "pw", _rows())
    sha = ["--fit-sha", fsha]
    assert W.main(["score", "--window", "pw", "--out", out] + sha) == 0
    res = json.loads((home / "pw" / "wsw-result.json").read_text())
    assert res["runNumber"] == 1 and res["fitSha256"] == fsha and res["admission"].startswith("none") and res["ledgerAnchor"]
    assert {"gitCommit", "runnerSha256", "windRuntime", "ledgerModuleSha256"} <= set(res["code"]) and res["inputHashes"]
    led = W._open_ledger()
    assert led.require("score", "score:pw")["counted"] is True
    (home / "pw" / "wsw-result.json").unlink()                                          # deleting the result does not reopen it
    assert W.main(["score", "--window", "pw", "--out", out] + sha) == 3
    other = home.parent / "run2"
    other.mkdir()
    assert W.main(["score", "--window", "pw", "--out", str(other)] + sha) == 3          # nor does a new --out
    assert W.main(["rows", "--window", "pw", "--out", out] + sha) == 3
    assert W.main(["fetch", "--window", "pw", "--month", "2025-02", "--out", out] + sha) == 3   # inputs fixed after rows
    assert calls == ["pw"]
    starts = [c for c in CURRENT["issue"].comments if c["body"].startswith(f"Run start: {W.PROTOCOL_ID} score score:pw")]
    assert len(starts) == 1
    assert W.main(["audit"]) == 0
    import inspect
    assert inspect.signature(real).parameters["boot_n"].default == 2000


def test_score_refuses_when_inputs_changed_after_rows(home, monkeypatch):
    monkeypatch.setattr(W, "score", lambda rows, fit, acc, window, _r=W.score: _r(rows, fit, acc, window, boot_n=20))
    _put_select(home, monkeypatch)
    fsha = _put_fit(home)
    _put_rows(home, "pw", _rows())
    (home / "pw" / "store" / "metar" / "synthetic.json").unlink()                       # a deleted observation file
    assert W.main(["score", "--window", "pw", "--out", str(home), "--fit-sha", fsha]) == 3
    assert not any(e["key"] == "score:pw" for e in W._open_ledger().entries())           # refused before begin
    (home / "pw" / "store" / "metar" / "synthetic.json").write_text("{}")                # restored exactly
    assert W.main(["score", "--window", "pw", "--out", str(home), "--fit-sha", fsha]) == 0


def test_clock_guards(home, monkeypatch):
    _put_fit(home)
    _clock(monkeypatch, "2026-11-01T00:00:00")                                          # earlier than the ledger's entries
    with pytest.raises(W.Refused):
        W.guard_clock(W._open_ledger(), "pw")
    led = W._open_ledger()
    led.begin("fetch", "fetch:h2:2026-10", {"synthetic": "an H2 entry before unseal"})
    led.abort_before_result("fetch", "fetch:h2:2026-10", "synthetic")
    _clock(monkeypatch, "2027-01-02T00:00:00")
    with pytest.raises(W.Refused):
        W.guard_clock(W._open_ledger(), "h2")
    W.guard_clock(W._open_ledger(), "pw")


# ------------------------------------------------------------------------------------------------------------------ runtime
def test_import_stays_offline_and_stdlib():
    code = ("import sys; sys.path.insert(0, %r); import wind_strong_wind; "
            "assert not {'numpy', 'eccodes', 'sector_wind'} & set(sys.modules)") % os.path.dirname(HERE)
    subprocess.run([sys.executable, "-c", code], check=True)


def test_definitions_match_the_wind_runtime():
    pytest.importorskip("numpy")
    sys.path.insert(0, W.WIND_RUNTIME)
    validate = pytest.importorskip("sector_wind.validate")
    assert W.T15 == 15 * validate.MPH
    for h in range(24):
        t = dt.datetime(2026, 1, 1, h, tzinfo=UTC)
        assert W.is_night(t) == validate._night(t)


def _synthetic_store(tmp_path, window_inits, obs_by_day, status="complete", speed_p90=True):
    """SYNTHETIC archive in the corpus layout for the Wheeler cut-out around HSV."""
    _, ingest, _, store, _ = W._runtime()
    cfg = W._cfg(ingest)
    st = store.LocalStore(str(tmp_path / "store"))
    s = cfg["stations"]["HSV"]
    nx = 10
    cells = [r * nx + c for r in range(3) for c in range(3)]
    st.put_json("grids/nbm/wheeler.json", {"cells": cells, "nx": nx,
                                           "lat": [s["lat"] - 0.02 + 0.02 * r for r in range(3) for _ in range(3)],
                                           "lon": [s["lon"] - 0.02 + 0.02 * c for _ in range(3) for c in range(3)]})
    for init, leads in window_inits:
        steps = []
        for l in leads:
            stp = {"leadHours": l, "validTime": f"{init + dt.timedelta(hours=l):%Y-%m-%dT%H:%M:%SZ}", "speedMS": [5.0] * 9,
                   "dirFromDeg": [180.0] * 9, "gustMS": [8.0] * 9}
            if speed_p90:
                stp["speedP90"] = [7.5] * 9
            steps.append(stp)
        st.put_json(f"nbm/wheeler/{init:%Y%m%d%H}.json.gz", {"grid": "grids/nbm/wheeler.json", "status": status,
                                                             "modelVersion": "NBM pre-v4.3", "steps": steps})
    for day, obs in obs_by_day.items():
        st.put_json(f"metar/{day}.json.gz", {"observations": obs})
    return str(tmp_path / "store"), cfg


def test_rows_account_for_every_planned_cycle_and_station(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    pytest.importorskip("eccodes")
    init = dt.datetime(2025, 1, 2, 0, tzinfo=UTC)
    monkeypatch.setitem(W.WINDOWS, "pw", (init, init + dt.timedelta(hours=6)))     # one day: 00Z (1,3,6) and 06Z (1)
    root, cfg = _synthetic_store(tmp_path, [(init, (1, 3, 6))], {"20250102": [
        {"station": "HSV", "validTime": "2025-01-02T00:53:00Z", "speedMS": 7.2, "dirFromDeg": 180.0, "gustMS": None},
        {"station": "HSV", "validTime": "2025-01-02T03:05:00Z", "speedMS": 3.1, "dirFromDeg": 180.0, "gustMS": None}]})
    rows, acc = W.build_rows("pw", root)
    by = {(r["station"], r["lead"]): r for r in rows}
    assert by[("HSV", 1)]["obs"] == 7.2 and by[("HSV", 1)]["b0"] == pytest.approx(5.0) and by[("HSV", 1)]["p90"] == pytest.approx(7.5)
    assert by[("HSV", 6)]["obs"] is None
    n_lakes = len(cfg["lakes"])
    assert acc["plannedPairs"] == 4 and acc["plannedRows"] == 4 * len(cfg["stations"])
    assert acc["plannedCycles"] == 2 * n_lakes
    assert acc["missingCycles"] == 2 * n_lakes - 1                     # only the Wheeler 00Z cycle exists
    assert acc["rowsBuilt"] == 3 * 3 and acc["obsMissingByStation"]["HSV"] == 1
    assert acc["missingObsDays"] == ["2025-01-01", "2025-01-03", "2025-01-04"] and acc["plannedRowsPerStation"] == 4
    assert acc["obsMissing"] == 3 * 3 - 2


def test_rows_flag_incomplete_cycles_and_missing_leads(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    pytest.importorskip("eccodes")
    init = dt.datetime(2025, 1, 2, 0, tzinfo=UTC)
    monkeypatch.setitem(W.WINDOWS, "pw", (init, init))
    root, _ = _synthetic_store(tmp_path, [(init, (1, 3))], {}, status="partial", speed_p90=False)
    _, acc = W.build_rows("pw", root)
    assert "nbm/wheeler/2025010200.json.gz" in acc["incompleteCycleKeys"] and acc["incompleteCycles"] == 1
    assert acc["p90Missing"] == acc["rowsBuilt"] > 0


def test_cal_h1_rows_never_load_h2_truth(tmp_path):
    pytest.importorskip("numpy")
    pytest.importorskip("eccodes")
    init = dt.datetime(2026, 10, 6, 0, tzinfo=UTC)
    root, _ = _synthetic_store(tmp_path, [(init, (1, 3, 6))], {
        "20261006": [{"station": "HSV", "validTime": "2026-10-06T01:00:00Z", "speedMS": 2.0, "dirFromDeg": 0.0, "gustMS": None}],
        "20261007": [{"station": "HSV", "validTime": "2026-10-07T03:00:00Z", "speedMS": 9.9, "dirFromDeg": 0.0, "gustMS": None}]})
    rows, _ = W.build_rows("cal_h1", root)
    assert all(r["valid"] < "2026-10-07" for r in rows)
    assert {r["obs"] for r in rows if r["station"] == "HSV" and r["init"].startswith("2026-10-06T00")} == {2.0, None}


def test_fetch_never_requests_h2_days_for_cal_h1_and_counts_bytes(tmp_path, monkeypatch):
    """No network: the runtime ingest functions are stubbed; the budgeted fetch is the one installed by do_fetch."""
    pytest.importorskip("numpy")
    pytest.importorskip("eccodes")
    grib, ingest, _, _, _ = W._runtime()
    real = (grib.fetch, ingest.fetch)
    days, cycles = [], []

    def fake_cycle(store, cfg, t, leads, q):
        cycles.append(t)
        ingest.fetch("https://noaa-nbm-grib2-pds.s3.amazonaws.com/x")
        return {k: "complete" for k in cfg["lakes"]}

    def fake_metar(store, cfg, d):
        days.append(d.date())
        ingest.fetch("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py")
        store.put_json(f"metar/{d:%Y%m%d}.json.gz", {"observations": []})
        return 0

    monkeypatch.setattr(ingest, "ingest_nbm_cycle", fake_cycle)
    monkeypatch.setattr(ingest, "ingest_metar_day", fake_metar)
    budget = W.Budget(str(tmp_path / "budget-cal_h1.json"))
    res = W.do_fetch("cal_h1", str(tmp_path), month="2026-10", budget=budget, min_free_gb=0, opener=_Opener([b"abc"] * 200))
    assert max(days) == dt.date(2026, 10, 6) and max(cycles) < W.H2_START
    assert res["budget"]["bytes"] == 3 * (len(days) + len(cycles))
    assert json.loads((tmp_path / "budget-cal_h1.json").read_text())["bytes"] == res["budget"]["bytes"]
    assert (grib.fetch, ingest.fetch) == real
    with pytest.raises(W.Refused):
        W.do_fetch("cal_h1", str(tmp_path / "again"), month="2026-09", budget=budget, min_free_gb=1e9, opener=_Opener([]))


# ------------------------------------------------------------------------------------------------------------ PW stations (R6)
def test_haversine_and_rank_key_are_the_protocol_definitions():
    assert W.haversine_km(0.0, 0.0, 0.0, 1.0) == pytest.approx(111.195, abs=0.01)
    assert W.haversine_km(34.6404, -86.7861, 34.6404, -86.7861) == 0.0
    assert W.rank_key("BHM") == W.sha256_bytes(b"WSW-2026-11-25-R6|BHM") and W.PW_SALT == "WSW-2026-11-25-R6|"


def test_pw_selection_is_metadata_only_deterministic_and_capped_per_state():
    nets = {"AL_ASOS": [_feature(f"A{i}", 28.0, -88.0 + 0.3 * i) for i in range(1, 6)] + [_feature("A9", 28.0, -86.0, ab=None), _feature("A8", 28.0, -85.5, ab="2024-06-01")],
            "TN_ASOS": [_feature(f"T{i}", 28.3, -88.0 + 0.3 * i) for i in range(1, 5)] + [_feature("BNA", 36.1245, -86.6782)],
            "MS_ASOS": [_feature(f"M{i}", 27.7, -88.0 + 0.3 * i) for i in range(1, 4)],
            "GA_ASOS": [_feature(f"G{i}", 28.6, -88.0 + 0.3 * i) for i in range(1, 4)] + [_feature("G9", 28.6, -85.0)]}
    listings = {n: W.parse_network_listing(b, n) for n, b in _listing_bytes(nets).items()}
    excluded = [{"id": "BNA", "lat": 36.1245, "lon": -86.6782, "why": "iem-wind"}, {"id": "X", "lat": 28.6, "lon": -85.1, "why": "W-NOW-3"}]  # X is ~10 km from G9
    sel = W.select_pw_stations(listings, excluded)
    ids = [s["id"] for s in sel["stations"]]
    assert len(ids) == 8 and len(set(ids)) == 8 and all(sel["perState"][st] <= W.PW_MAX_PER_STATE for st in sel["perState"])
    assert sel["counts"] == {"candidatesListed": 19, "filteredByArchiveBegin": 2, "droppedById": 1, "droppedByBuffer": 1, "eligible": 15}
    assert {d["id"] for d in sel["dropped"]} == {"BNA", "G9"}
    eligible = [f"A{i}" for i in range(1, 6)] + [f"T{i}" for i in range(1, 5)] + [f"M{i}" for i in range(1, 4)] + [f"G{i}" for i in range(1, 4)]
    ranked = sorted(eligible, key=W.rank_key)
    assert sel["eligibleRanking"] == ranked
    expect, per = [], {}
    for sid in ranked:                      # the rule, written independently: walk the ranking, skip a full state, stop at 8
        st = sid[0]
        if per.get(st, 0) == 3:
            continue
        per[st] = per.get(st, 0) + 1
        expect.append(sid)
        if len(expect) == 8:
            break
    assert ids == expect and [s["rank"] for s in sel["stations"]] == list(range(1, 9))
    shuffled = {n: dict(reversed(list(v.items()))) for n, v in listings.items()}
    assert [s["id"] for s in W.select_pw_stations(shuffled, excluded)["stations"]] == ids           # deterministic
    assert all(s["archiveBegin"] <= W.PW_ARCHIVE_BEGIN_MAX for s in sel["stations"])
    with pytest.raises(W.Refused):                                                                  # fewer than 8 remain
        W.select_pw_stations({n: v for n, v in listings.items() if n in ("AL_ASOS", "TN_ASOS")} | {"MS_ASOS": {}, "GA_ASOS": {}},
                             excluded + [{"id": f"T{i}", "lat": 0, "lon": 0, "why": "t"} for i in range(1, 5)])
    with pytest.raises(W.Refused):                                                                  # a missing network
        W.select_pw_stations({n: v for n, v in listings.items() if n != "GA_ASOS"}, excluded)
    dup = dict(listings, GA_ASOS=dict(listings["GA_ASOS"], A1=dict(listings["AL_ASOS"]["A1"], network="GA_ASOS", state="GA")))
    with pytest.raises(W.Refused):                                                                  # one id in two networks
        W.select_pw_stations(dup, excluded)


def test_listing_parser_fails_closed():
    good = _listing_bytes({"AL_ASOS": [_feature("BHM", 33.56, -86.75)]})["AL_ASOS"]
    assert W.parse_network_listing(good, "AL_ASOS")["BHM"]["state"] == "AL"
    sid_only = json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"sid": "BHM", "archive_begin": "2010-01-01"},
                                                                       "geometry": {"type": "Point", "coordinates": [-86.75, 33.56]}}]}).encode()
    assert W.parse_network_listing(sid_only, "AL_ASOS")["BHM"]["id"] == "BHM"                   # properties.sid names the same station
    for bad in (b"not json", json.dumps({"type": "FeatureCollection", "features": []}).encode(),
                json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "id": "BHM", "properties": {"sid": "OTHER", "archive_begin": "2010-01-01"},
                                                                       "geometry": {"type": "Point", "coordinates": [-86.75, 33.56]}}]}).encode(),
                json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "id": "BHM", "properties": {"archive_begin": "2010-01-01"},
                                                                       "geometry": {"type": "Polygon", "coordinates": [[0, 0]]}}]}).encode(),
                json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "id": "BHM", "properties": {"sname": "x"},
                                                                       "geometry": {"type": "Point", "coordinates": [-86.75, 33.56]}}]}).encode(),
                json.dumps({"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"archive_begin": "2010-01-01"},
                                                                       "geometry": {"type": "Point", "coordinates": [-86.75, 33.56]}}]}).encode()):
        with pytest.raises(W.Refused):
            W.parse_network_listing(bad, "AL_ASOS")


def test_exclusions_cover_every_registered_set_and_fail_closed_without_coordinates(tmp_path):
    csv = tmp_path / "w3.csv"
    csv.write_text("station,lat,lon,nLakes\n2A0,35.4817,-84.9322,1\n")
    with pytest.raises(W.Refused):                                             # not the registered W-NOW-3 list
        W.read_w_now_3(str(csv))
    w3 = [{"id": "2A0", "lat": 35.4817, "lon": -84.9322, "why": "W-NOW-3"}]
    listings = {n: W.parse_network_listing(b, n) for n, b in _listing_bytes(_synthetic_networks()).items()}
    ex = W.exclusions(listings, w3)
    ids = {e["id"] for e in ex}
    assert set(W.STATION_IDS) <= ids and set(W.IEM_WIND_IDS) <= ids and "2A0" in ids
    points = json.load(open(W.POINTS_JSON))["points"]
    assert {p["station"] for p in points.values()} <= ids and all(isinstance(e["lat"], float) for e in ex)
    assert W.sha256_file(W.POINTS_JSON) == W.POINTS_JSON_SHA256
    without_tul = {n: v for n, v in listings.items() if n != "OK_ASOS"}
    with pytest.raises(W.Refused):
        W.exclusions(without_tul, w3)


def test_pw_config_is_one_carrier_box_per_station():
    nets = _synthetic_networks()
    listings = {n: W.parse_network_listing(b, n) for n, b in _listing_bytes(nets).items()}
    sel = W.select_pw_stations(listings, W.exclusions(listings, []))
    cfg = W.pw_config(sel)
    assert len(cfg["lakes"]) == 8 and len(cfg["stations"]) == 8
    for sid, st in cfg["stations"].items():
        box = cfg["lakes"][st["lake"]]["bbox"]
        assert st["lake"] == f"pw-{sid}" and box == [round(st["lon"] - W.PW_BOX_DEG, 4), round(st["lat"] - W.PW_BOX_DEG, 4),
                                                     round(st["lon"] + W.PW_BOX_DEG, 4), round(st["lat"] + W.PW_BOX_DEG, 4)]
        assert st["sensorHeightM"] == 10.0 and st["network"].startswith("IEM ")
    with pytest.raises(W.Refused):
        W.pw_config({"stations": sel["stations"][:7]})
    assert W.window_cfg("cal_h1") is None and W.window_cfg("h2") is None


def test_select_is_a_one_shot_result_step_that_fixes_the_list_before_fit_and_fetch(home, monkeypatch, capsys):
    out = str(home)
    assert W.main(["fit", "--out", out]) == 3                                                       # no selection yet
    assert "no counted PW station selection" in capsys.readouterr().err
    assert W.main(["fetch", "--window", "cal_h1", "--month", "2026-05", "--out", out, "--min-free-gb", "0"]) == 3   # no value before the selection
    assert "no counted PW station selection" in capsys.readouterr().err
    assert W.main(["fetch", "--window", "pw", "--month", "smoke", "--out", out, "--min-free-gb", "0"]) == 3
    assert "no counted PW station selection" in capsys.readouterr().err
    assert W.main(["select", "--window", "h2", "--out", out, "--w-now-3-stations", "x"]) == 3
    path = _put_select(home, monkeypatch)
    issue = CURRENT["issue"]
    assert any(c["body"].startswith(f"Run start: {W.PROTOCOL_ID} select select:pw") for c in issue.comments)
    assert any(c["body"].startswith(f"Run result: {W.PROTOCOL_ID} select select:pw") for c in issue.comments)
    led = W._open_ledger()
    entry = led.require("select", "select:pw")
    assert entry["counted"] and entry["outputs"]["stations"] == W.sha256_file(str(path))
    doc = json.loads(path.read_text())
    assert doc["schema"] == W.STATIONS_SCHEMA and doc["protocolSha256"] == W.REGISTERED_SHA256 and len(doc["stations"]) == 8
    assert set(doc["listings"]) == set(W.PW_NETWORKS + W.COORD_NETWORKS) and all(len(v["sha256"]) == 64 for v in doc["listings"].values())
    assert {s["id"] for s in doc["stations"]}.isdisjoint(set(W.STATION_IDS) | set(W.IEM_WIND_IDS))
    assert sorted(os.listdir(home / "pw" / "metadata")) == sorted(f"{n}.geojson" for n in W.PW_NETWORKS + W.COORD_NETWORKS)
    assert W.main(["select", "--window", "pw", "--out", out, "--w-now-3-stations", str(home.parent / "w-now-3-stations.csv")]) == 3   # one shot
    other = home.parent / "run2"
    other.mkdir()
    assert W.main(["select", "--window", "pw", "--out", str(other), "--w-now-3-stations", str(home.parent / "w-now-3-stations.csv")]) == 3
    fsha = _put_fit(home)
    _, cfg, _ = W.guard_pw_stations(led, out)
    assert set(cfg["stations"]) == {s["id"] for s in doc["stations"]}
    original = path.read_bytes()
    path.write_text(json.dumps(dict(doc, stations=doc["stations"][::-1])))                           # a different list
    for args in (["fetch", "--window", "pw", "--month", "smoke", "--out", out, "--fit-sha", fsha, "--min-free-gb", "0"],
                 ["rows", "--window", "pw", "--out", out, "--fit-sha", fsha], ["score", "--window", "pw", "--out", out, "--fit-sha", fsha]):
        capsys.readouterr()
        assert W.main(args) == 3
        assert "differs from the counted selection" in capsys.readouterr().err
    assert not any(e["key"].startswith("fetch:pw") or e["key"] == "rows:pw" for e in led.entries() if e["status"] == PRL.STARTED)
    path.write_bytes(original)
    assert W.main(["fetch", "--window", "pw", "--month", "smoke", "--out", out, "--fit-sha", fsha, "--min-free-gb", "1e9"]) == 3   # free-space guard: reached


def test_pw_fetch_uses_the_selected_stations_not_lakes_json(home, monkeypatch):
    pytest.importorskip("numpy")
    pytest.importorskip("eccodes")
    _put_select(home, monkeypatch)
    fsha = _put_fit(home)
    seen = {}

    def fake_fetch(window, out, max_pairs, month, budget, min_free_gb, cfg=None):
        seen["cfg"] = cfg
        return {"budget": {"bytes": 0}}
    monkeypatch.setattr(W, "do_fetch", fake_fetch)
    assert W.main(["fetch", "--window", "pw", "--month", "smoke", "--out", str(home), "--fit-sha", fsha, "--min-free-gb", "0"]) == 0
    doc = json.loads((home / "pw" / W.STATIONS_FILE).read_text())
    assert set(seen["cfg"]["stations"]) == {s["id"] for s in doc["stations"]} and set(seen["cfg"]["lakes"]) == {f"pw-{s['id']}" for s in doc["stations"]}
    _clock(monkeypatch, "2027-01-02T00:00:00")
    assert W.main(["fetch", "--window", "h2", "--month", "2026-10", "--out", str(home), "--fit-sha", fsha, "--min-free-gb", "0"]) == 0
    assert seen["cfg"] is None                                                                      # H2: lakes.json, the frozen 8


def test_pw_rows_blend_at_the_station_point_and_count_non_bilinear_weights(tmp_path, monkeypatch):
    pytest.importorskip("numpy")
    pytest.importorskip("eccodes")
    _, _, _, store, _ = W._runtime()
    init = dt.datetime(2025, 1, 2, 0, tzinfo=UTC)
    monkeypatch.setitem(W.WINDOWS, "pw", (init, init))
    cfg = {"lakes": {"pw-P1": {"bbox": [-88.15, 27.85, -87.85, 28.15]}, "pw-P2": {"bbox": [-87.75, 27.85, -87.45, 28.15]}},
           "stations": {"P1": {"lake": "pw-P1", "network": "IEM AL_ASOS", "lat": 28.0, "lon": -88.0, "sensorHeightM": 10.0},
                        "P2": {"lake": "pw-P2", "network": "IEM AL_ASOS", "lat": 28.0, "lon": -87.6, "sensorHeightM": 10.0}}}
    st = store.LocalStore(str(tmp_path / "store"))
    nx = 10
    cells = [r * nx + c for r in range(3) for c in range(3)]
    for lake, lon0 in (("pw-P1", -88.0), ("pw-P2", -87.64)):           # P2 sits at the corner cell of its grid: nearest, not bilinear
        st.put_json(f"grids/nbm/{lake}.json", {"cells": cells, "nx": nx, "lat": [28.0 - 0.02 + 0.02 * r for r in range(3) for _ in range(3)],
                                                 "lon": [lon0 - 0.02 + 0.02 * c for _ in range(3) for c in range(3)]})
        steps = [{"leadHours": l, "validTime": f"{init + dt.timedelta(hours=l):%Y-%m-%dT%H:%M:%SZ}", "speedMS": [5.0] * 9, "dirFromDeg": [180.0] * 9,
                  "gustMS": [8.0] * 9, "speedP90": [7.5] * 9} for l in (1, 3, 6)]
        st.put_json(f"nbm/{lake}/{init:%Y%m%d%H}.json.gz", {"grid": f"grids/nbm/{lake}.json", "status": "complete", "modelVersion": "NBM pre-v4.3", "steps": steps})
    st.put_json("metar/20250102.json.gz", {"observations": [{"station": "P1", "validTime": "2025-01-02T01:00:00Z", "speedMS": 7.2, "dirFromDeg": 180.0, "gustMS": None},
                                                            {"station": "P2", "validTime": "2025-01-02T01:00:00Z", "speedMS": 7.2, "dirFromDeg": 180.0, "gustMS": None}]})
    rows, acc = W.build_rows("pw", str(tmp_path / "store"), cfg)
    monkeypatch.setitem(W.WINDOWS, "h2", (init, init))
    h2_rows, h2_acc = W.build_rows("h2", str(tmp_path / "store"), cfg)                 # not PW: counted, values kept
    assert all(r["b0"] == pytest.approx(5.0) for r in h2_rows if r["station"] == "P2") and h2_acc["weightsNotBilinear"] == 3 and h2_acc["b0Missing"] == 0
    by = {(r["station"], r["lead"]): r for r in rows}
    assert by[("P1", 1)]["b0"] == pytest.approx(5.0) and by[("P1", 1)]["p90"] == pytest.approx(7.5) and by[("P1", 1)]["weights"] == "bilinear"
    assert by[("P2", 1)]["b0"] is None and by[("P2", 1)]["p90"] is None and by[("P2", 1)]["weights"] == "nearest" and by[("P2", 1)]["obs"] == 7.2
    assert acc["weightsNotBilinear"] == 3 and acc["b0Missing"] == 3 and acc["p90Missing"] == 3 and acc["plannedRows"] == 3 * 2
    assert all(r["lake"].startswith("pw-") for r in rows)
