"""Protocol WSW-2026-11-23-R3 runner: guards, accounting, budget, M-B fit maths and scoring on SYNTHETIC fixtures (offline)."""
import datetime as dt
import io
import json
import os
import random
import shutil
import subprocess
import sys
import urllib.error

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import wind_strong_wind as W  # noqa: E402

UTC = dt.timezone.utc
FOLDER = os.path.dirname(W.PROTOCOL)
SUPERSEDED = [os.path.join(FOLDER, "WSW-2026-11-23.protocol.json"), os.path.join(FOLDER, "WSW-2026-11-23-R2.protocol.json")]
FLAT_FIT = {"knots": [[0.0, 0.0], [10.0, 0.0]]}


def _clock(monkeypatch, iso):
    monkeypatch.setattr(W, "_utcnow", lambda: dt.datetime.fromisoformat(iso).replace(tzinfo=UTC))


def _acc(rows, **kw):
    """Accounting for SYNTHETIC rows: planned = built unless overridden."""
    a = {"plannedPairs": len(rows) // 4, "plannedRows": len(rows), "plannedCycles": len(rows) // 4, "missingCycles": 0,
         "incompleteCycles": 0, "rowsBuilt": len(rows), "rowsNotBuilt": 0, "obsMissing": sum(r["obs"] is None for r in rows),
         "b0Missing": sum(r["b0"] is None for r in rows), "p90Missing": sum(r["p90"] is None for r in rows)}
    a.update(kw)
    return a


def _put_fit(tmp_path):
    _, psha = W.load_protocol()
    (tmp_path / W.FIT_FILE).write_text(json.dumps(dict(FLAT_FIT, protocolSha256=psha)))
    return W.sha256_file(str(tmp_path / W.FIT_FILE))


# ------------------------------------------------------------------------------------------------------------------ protocol
def test_protocol_is_pinned_and_matches_runner_constants():
    proto, sha = W.load_protocol()
    assert sha == W.REGISTERED_SHA256 and proto["protocolId"] == "WSW-2026-11-23-R3"
    assert [s["protocolId"] for s in proto["supersedes"]] == ["WSW-2026-11-23-R2", "WSW-2026-11-23"]
    assert proto["forecastRows"]["leads"] == list(W.LEADS)
    assert proto["methods"]["M-B"]["fit"]["levels"] == list(W.LEVELS)
    assert proto["methods"]["M-B"]["fit"]["minimumRows"] == W.MIN_FIT_ROWS
    for key, w in (("CAL_H1", "cal_h1"), ("PW", "pw"), ("H2", "h2")):
        lo, hi = proto["windows"][key]["inits"]
        assert (lo, hi) == (f"{W.WINDOWS[w][0]:%Y-%m-%dT%H:%MZ}", f"{W.WINDOWS[w][1]:%Y-%m-%dT%H:%MZ}")
    assert proto["budget"]["downloadBytesPerWindow"] == W.BUDGET_BYTES and proto["budget"]["wallClockHoursPerWindow"] * 3600 == W.BUDGET_SECONDS
    assert set(proto["outputsAndAdmission"]["labels"]) == set(W.LABELS)
    assert {h.split()[0] for h in proto["budget"]["hosts"]} == W.ALLOWED_HOSTS
    assert "20%" in proto["accounting"]["truthSideGaps"] and W.MAX_OBS_MISSING == 0.20


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
                                     "ba05492be82102fdba170b8dd5181ec557505622246e6a780c52a6ffc129633b")):
        assert W.sha256_file(old) == sha


def test_no_hidden_clock_or_protocol_flags():
    for flag in ("--now", "--protocol", "--boot", "--fit", "--rows"):
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
    ok = {"init": "2026-07-01T00:00:00Z", "valid": "2026-07-01T01:00:00Z", "lead": 1, "obs": 3.0, "b0": 2.0}
    W.fit_pairs([ok], {"missingCycles": 0, "incompleteCycles": 0})
    for bad in ({"init": "2025-03-01T00:00:00Z", "valid": "2025-03-01T01:00:00Z"},
                {"init": "2026-10-06T18:00:00Z", "valid": "2026-10-07T06:00:00Z"}):
        with pytest.raises(W.Refused):
            W.fit_pairs([dict(ok, **bad)], {"missingCycles": 0, "incompleteCycles": 0})
    with pytest.raises(W.Refused):
        W.fit_pairs([ok], {"missingCycles": 1, "incompleteCycles": 0})


# ---------------------------------------------------------------------------------------------------------- fit sha ordering
def test_past_window_steps_need_the_posted_fit_sha(tmp_path, monkeypatch):
    out = str(tmp_path)
    assert W.main(["fetch", "--window", "pw", "--out", out]) == 3                      # no fit
    fsha = _put_fit(tmp_path)
    for cmd in ("fetch", "rows", "score"):
        assert W.main([cmd, "--window", "pw", "--out", out]) == 3                      # no --fit-sha
        assert W.main([cmd, "--window", "pw", "--out", out, "--fit-sha", "0" * 64]) == 3
    assert W.main(["fetch", "--window", "pw", "--out", out, "--fit-sha", fsha, "--min-free-gb", "1e9"]) == 3
    assert not (tmp_path / "pw").exists() and not (tmp_path / "fit-record.json").exists()
    W.record_fit_use(out, "pw", fsha)
    rec = json.loads((tmp_path / "fit-record.json").read_text())
    assert rec["fitSha256"] == fsha and "pw" in rec["firstUse"]
    with pytest.raises(W.Refused):
        W.record_fit_use(out, "pw", "1" * 64)
    _clock(monkeypatch, "2026-11-23T00:00:00")
    assert W.main(["fetch", "--window", "h2", "--out", out, "--fit-sha", fsha]) == 3


# -------------------------------------------------------------------------------------------------------------------- budget
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
    for kw in ({"missingCycles": 1}, {"incompleteCycles": 2}, {"obsMissing": int(0.21 * len(r))}):
        res = W.score(r, FLAT_FIT, _acc(r, **kw), "pw", boot_n=20)
        assert {res["outcome"][m]["outcome"] for m in ("M-A", "M-B")} == {"INCOMPLETE"} and "bootstrap" not in res
    ok = W.score(r, FLAT_FIT, _acc(r, obsMissing=int(0.19 * len(r))), "pw", boot_n=20)
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


def test_recorded_outputs_are_never_overwritten_and_use_2000_resamples(tmp_path, monkeypatch):
    calls = []
    real = W.score
    monkeypatch.setattr(W, "score", lambda rows, fit, acc, window: calls.append(window) or real(rows, fit, acc, window, boot_n=20))
    out = str(tmp_path)
    fsha = _put_fit(tmp_path)
    for w, start in (("pw", dt.datetime(2025, 1, 2, tzinfo=UTC)), ("h2", dt.datetime(2026, 10, 8, tzinfo=UTC))):
        (tmp_path / w).mkdir()
        rows = _rows(start=start)
        (tmp_path / w / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows))
        (tmp_path / w / "accounting.json").write_text(json.dumps(_acc(rows)))
    _clock(monkeypatch, "2026-12-31T23:00:00")
    sha = ["--fit-sha", fsha]
    assert W.main(["score", "--window", "h2", "--out", out] + sha) == 3                 # sealed
    assert W.main(["score", "--window", "pw", "--out", out] + sha) == 0
    assert W.main(["score", "--window", "pw", "--out", out] + sha) == 3                 # never overwritten
    assert W.main(["rows", "--window", "pw", "--out", out] + sha) == 3                  # rows recorded
    _clock(monkeypatch, "2027-01-02T00:00:00")
    assert W.main(["score", "--window", "h2", "--out", out] + sha) == 0
    assert W.main(["score", "--window", "h2", "--out", out] + sha) == 3                 # one shot
    res = json.loads((tmp_path / "h2" / "wsw-result.json").read_text())
    assert res["fitSha256"] == fsha and res["admission"].startswith("none") and calls == ["pw", "h2"] and "accountingSha256" in res
    assert W.main(["fit", "--out", out]) == 3
    import inspect
    assert inspect.signature(real).parameters["boot_n"].default == 2000


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
    res = W.do_fetch("cal_h1", str(tmp_path), month="2026-10", min_free_gb=0, opener=_Opener([b"abc"] * 200))
    assert max(days) == dt.date(2026, 10, 6) and max(cycles) < W.H2_START
    assert res["budget"]["bytes"] == 3 * (len(days) + len(cycles))
    assert json.loads((tmp_path / "cal_h1" / "budget.json").read_text())["bytes"] == res["budget"]["bytes"]
    assert (grib.fetch, ingest.fetch) == real
    with pytest.raises(W.Refused):
        W.do_fetch("cal_h1", str(tmp_path / "again"), month="2026-09", min_free_gb=1e9, opener=_Opener([]))
