"""Protocol WSW-2026-11-23-R2 runner: guards, budget, M-B fit maths and scoring on SYNTHETIC fixtures (offline)."""
import datetime as dt
import json
import os
import random
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import wind_strong_wind as W  # noqa: E402

UTC = dt.timezone.utc
OLD = os.path.join(os.path.dirname(W.PROTOCOL), "WSW-2026-11-23.protocol.json")


def _clock(monkeypatch, iso):
    monkeypatch.setattr(W, "_utcnow", lambda: dt.datetime.fromisoformat(iso).replace(tzinfo=UTC))


# ------------------------------------------------------------------------------------------------------------------ protocol
def test_protocol_is_pinned_and_matches_runner_constants():
    proto, sha = W.load_protocol()
    assert sha == W.REGISTERED_SHA256 and proto["protocolId"] == "WSW-2026-11-23-R2"
    assert proto["supersedes"]["protocolId"] == "WSW-2026-11-23"
    assert proto["forecastRows"]["leads"] == list(W.LEADS)
    assert proto["methods"]["M-B"]["fit"]["levels"] == list(W.LEVELS)
    assert proto["methods"]["M-B"]["fit"]["minimumRows"] == W.MIN_FIT_ROWS
    for key, w in (("CAL_H1", "cal_h1"), ("PW", "pw"), ("H2", "h2")):
        lo, hi = proto["windows"][key]["inits"]
        assert (lo, hi) == (f"{W.WINDOWS[w][0]:%Y-%m-%dT%H:%MZ}", f"{W.WINDOWS[w][1]:%Y-%m-%dT%H:%MZ}")
    assert proto["budget"]["downloadBytesPerWindow"] == W.BUDGET_BYTES and proto["budget"]["wallClockHoursPerWindow"] * 3600 == W.BUDGET_SECONDS
    assert set(proto["outputsAndAdmission"]["labels"]) == set(W.LABELS)
    assert {h.split()[0] for h in proto["budget"]["hosts"]} == W.ALLOWED_HOSTS


def test_superseded_and_changed_protocols_are_refused(tmp_path):
    with pytest.raises(W.Refused):
        W.load_protocol(OLD)
    p = tmp_path / "p.json"
    shutil.copy(W.PROTOCOL, p)
    W.load_protocol(str(p))
    p.write_text(p.read_text().replace("PRE-REGISTERED", "EDITED"))
    with pytest.raises(W.Refused):
        W.load_protocol(str(p))


def test_no_hidden_clock_or_protocol_flags():
    for flag in ("--now", "--protocol", "--boot", "--fit", "--rows"):
        with pytest.raises(SystemExit):
            W.main(["verify", flag, "x"])


# ------------------------------------------------------------------------------------------------------------------- windows
def test_night_pairs_are_synoptic_night_only():
    for w in ("cal_h1", "pw", "h2"):
        p = W.night_pairs(w)
        days = (W.WINDOWS[w][1].date() - W.WINDOWS[w][0].date()).days + 1
        assert len(p) == 6 * days
        assert all(t.hour in W.SYNOPTIC and 1 <= (t + dt.timedelta(hours=l)).hour <= 8 for t, l in p)
    assert {(t.hour, l) for t, l in W.night_pairs("pw")} == {(0, 1), (0, 3), (0, 6), (6, 1), (12, 18), (18, 12)}


def test_pw_is_one_generation_and_after_the_iem_wind_years():
    lo, hi = W.WINDOWS["pw"]
    assert lo >= dt.datetime(2025, 1, 2, tzinfo=UTC)                        # iem-wind read 2015-2024
    assert hi < dt.datetime(2025, 5, 27, 12, tzinfo=UTC)                     # every init before NBM v4.3 (version is by init)
    assert hi < dt.datetime(2025, 11, 1, tzinfo=UTC)                        # before the W1/W1b window


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


def test_fit_refuses_rows_outside_cal_h1():
    W.guard_fit_window([dt.datetime(2026, 5, 6, tzinfo=UTC), dt.datetime(2026, 10, 6, 23, tzinfo=UTC)])
    for bad in (dt.datetime(2026, 10, 7, tzinfo=UTC), dt.datetime(2025, 3, 1, tzinfo=UTC)):
        with pytest.raises(W.Refused):
            W.guard_fit_window([bad])
    with pytest.raises(W.Refused):
        W.fit_pairs([{"init": "2025-03-01T00:00:00Z", "valid": "2025-03-01T01:00:00Z", "lead": 1, "obs": 3.0, "b0": 2.0}])


# -------------------------------------------------------------------------------------------------------------------- budget
def test_every_request_is_host_checked_and_budgeted(tmp_path):
    t = [0.0]
    b = W.Budget(str(tmp_path / "budget.json"), max_bytes=10, max_seconds=100, clock=lambda: t[0])
    calls = []
    f = b.wrap(lambda url, *a, **k: calls.append(url) or b"x" * 6)
    f("https://mesonet.agron.iastate.edu/a")
    for bad in ("https://example.org/a", "http://mesonet.agron.iastate.edu/a"):
        with pytest.raises(W.Refused):
            f(bad)
    f("https://noaa-nbm-grib2-pds.s3.amazonaws.com/a")
    assert b.bytes == 12 and len(calls) == 2
    with pytest.raises(W.BudgetExceeded):
        f("https://mesonet.agron.iastate.edu/b")                  # bytes exhausted: stopped before sending
    assert len(calls) == 2
    b.save()
    b2 = W.Budget(str(tmp_path / "budget.json"), max_bytes=100, max_seconds=100, clock=lambda: t[0])
    assert b2.bytes == 12                                          # cumulative across runs
    t[0] = 150.0
    with pytest.raises(W.BudgetExceeded):
        b2.wrap(lambda url: b"")("https://mesonet.agron.iastate.edu/c")


def test_fetch_refuses_a_full_volume_and_an_unfitted_pw(tmp_path, monkeypatch):
    out = str(tmp_path)
    assert W.main(["fetch", "--window", "pw", "--out", out]) == 3              # no fit yet
    _, psha = W.load_protocol()
    (tmp_path / W.FIT_FILE).write_text(json.dumps(dict(FLAT_FIT, protocolSha256=psha)))
    assert W.main(["fetch", "--window", "pw", "--out", out, "--month", "2025-02", "--min-free-gb", "1e9"]) == 3
    assert W.main(["fetch", "--window", "pw", "--out", out, "--month", "2026-07"]) == 3
    assert not (tmp_path / "pw").exists()
    _clock(monkeypatch, "2026-11-23T00:00:00")
    assert W.main(["fetch", "--window", "h2", "--out", out]) == 3


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
    assert len(fit["knots"]) == len(W.LEVELS)
    ys = [W.apply_qm(fit, i / 10) for i in range(150)]
    assert all(b >= a for a, b in zip(ys, ys[1:]))
    top = fit["knots"][-1]
    assert abs(W.apply_qm(fit, top[0]) - (top[0] + 0.05 * top[0] ** 2)) < 0.05


def test_fit_refuses_too_few_rows_and_merges_ties():
    with pytest.raises(W.Refused):
        W.fit_qm(_synthetic_pairs(500))
    fit = W.fit_qm([(1.0, 1.0)] * 6000 + [(2.0, 3.0)] * 5)
    xs = [k[0] for k in fit["knots"]]
    assert xs == sorted(set(xs))


# ------------------------------------------------------------------------------------------------------------------- scoring
def test_wi4_and_gate_match_production():
    zero_fc = {str(l): W.table([(False, True)] * 5 + [(False, False)] * 50) for l in W.LEADS}
    assert W.wi4_credit(zero_fc) == 0.0 and not W.scoreboard_gate(zero_fc)       # the CAL+H1 pattern
    perfect = {str(l): W.table([(True, True)] * 5 + [(False, False)] * 50) for l in W.LEADS}
    assert W.wi4_credit(perfect) == 1.0 and W.scoreboard_gate(perfect)
    half = {str(l): W.table([(True, True)] * 2 + [(False, True)] * 2 + [(True, False)] * 3) for l in W.LEADS}
    assert W.wi4_credit(half) == pytest.approx(2 / 3, abs=1e-3)
    no_events_at_18 = dict(perfect, **{"18": W.table([(False, False)] * 50)})
    assert W.wi4_credit(no_events_at_18) == 0.0 and not W.scoreboard_gate(no_events_at_18)
    no_rows_at_18 = dict(perfect, **{"18": W.table([])})                       # production leaves the lead out
    assert W.wi4_credit(no_rows_at_18) == 1.0 and W.scoreboard_gate(no_rows_at_18)
    assert W.wi4_credit({str(l): W.table([]) for l in W.LEADS}) == 0.0


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


FLAT_FIT = {"knots": [[0.0, 0.0], [10.0, 0.0]]}


def test_score_reports_wi4_beside_every_outcome():
    res = W.score(_rows(), FLAT_FIT, "pw", boot_n=200)
    assert res["methods"]["B0"]["pooled"]["pod"] == 0.0 and res["outcome"]["B0"]["wi4Credit"] == 0.0
    assert res["methods"]["M-A"]["pooled"]["pod"] > 0.5
    assert res["outcome"]["M-A"]["outcome"] == "SUPPORTED" and "wi4Credit" in res["outcome"]["M-A"]
    assert res["outcome"]["M-B"]["outcome"] == "NOT_SUPPORTED"
    assert res["bootstrap"]["lowerPercentile"] == 1.25 and res["labels"] == W.LABELS


def test_h2_uses_the_four_rule_correction_and_drops_the_shared_night():
    rows = _rows(start=dt.datetime(2026, 10, 7, tzinfo=UTC))
    res = W.score(rows, FLAT_FIT, "h2", boot_n=100)
    assert res["bootstrap"]["lowerPercentile"] == 0.625
    assert res["rowsNight"] == len([r for r in rows if not r["valid"].startswith("2026-10-07")])


def test_score_is_deterministic():
    assert W.score(_rows(), FLAT_FIT, "pw", 100)["bootstrap"] == W.score(_rows(), FLAT_FIT, "pw", 100)["bootstrap"]


def test_score_refuses_to_pass_without_enough_events_or_p90():
    assert {v["outcome"] for k, v in W.score(_rows(n_days=4), FLAT_FIT, "pw", 50)["outcome"].items() if k != "B0"} == {"INSUFFICIENT_EVENTS"}
    assert {v["outcome"] for k, v in W.score(_rows(p90=False), FLAT_FIT, "pw", 50)["outcome"].items() if k != "B0"} == {"NOT_EVALUABLE"}


def test_day_rows_are_not_scored():
    r = _rows(n_days=1)
    for x in r:
        x["valid"] = x["valid"][:11] + "14:00:00Z"
    assert W.score(r, FLAT_FIT, "pw", 10)["rowsNight"] == 0


def test_recorded_outputs_are_never_overwritten_and_use_2000_resamples(tmp_path, monkeypatch):
    calls = []
    real = W.score
    monkeypatch.setattr(W, "score", lambda rows, fit, window: calls.append(window) or real(rows, fit, window, boot_n=20))
    out = str(tmp_path)
    _, psha = W.load_protocol()
    (tmp_path / W.FIT_FILE).write_text(json.dumps(dict(FLAT_FIT, protocolSha256=psha)))
    for w, start in (("pw", dt.datetime(2025, 1, 2, tzinfo=UTC)), ("h2", dt.datetime(2026, 10, 8, tzinfo=UTC))):
        (tmp_path / w).mkdir()
        (tmp_path / w / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in _rows(start=start)))
    _clock(monkeypatch, "2026-12-31T23:00:00")
    assert W.main(["score", "--window", "h2", "--out", out]) == 3                # sealed
    assert W.main(["score", "--window", "pw", "--out", out]) == 0
    assert W.main(["score", "--window", "pw", "--out", out]) == 3                # never overwritten
    assert W.main(["rows", "--window", "pw", "--out", out]) == 3                 # rows recorded: never rebuilt
    _clock(monkeypatch, "2027-01-02T00:00:00")
    assert W.main(["score", "--window", "h2", "--out", out]) == 0
    assert W.main(["score", "--window", "h2", "--out", out]) == 3                # one shot
    res = json.loads((tmp_path / "h2" / "wsw-result.json").read_text())
    assert res["protocolSha256"] == psha and res["admission"].startswith("none") and calls == ["pw", "h2"]
    assert W.main(["fit", "--out", out]) == 3                                    # fit frozen once
    import inspect
    assert inspect.signature(real).parameters["boot_n"].default == 2000


def test_fit_from_another_protocol_is_refused(tmp_path):
    (tmp_path / W.FIT_FILE).write_text(json.dumps(dict(FLAT_FIT, protocolSha256="0" * 64)))
    assert W.main(["score", "--window", "pw", "--out", str(tmp_path)]) == 3


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


def test_rows_from_a_synthetic_store(tmp_path):
    """SYNTHETIC archive in the corpus layout (grid cut-out, one NBM cycle with P90, one METAR day) -> build_rows."""
    pytest.importorskip("numpy")
    pytest.importorskip("eccodes")
    _, ingest, _, store, _ = W._runtime()
    cfg = W._cfg(ingest)
    st = store.LocalStore(str(tmp_path / "store"))
    sid = "HSV"
    s = cfg["stations"][sid]
    nx = 10
    cells = [r * nx + c for r in range(3) for c in range(3)]
    lat = [s["lat"] - 0.02 + 0.02 * r for r in range(3) for _ in range(3)]
    lon = [s["lon"] - 0.02 + 0.02 * c for _ in range(3) for c in range(3)]
    st.put_json("grids/nbm/wheeler.json", {"cells": cells, "lat": lat, "lon": lon, "nx": nx})
    init = dt.datetime(2025, 1, 2, 0, tzinfo=UTC)
    steps = [{"leadHours": l, "validTime": f"{init + dt.timedelta(hours=l):%Y-%m-%dT%H:%M:%SZ}", "speedMS": [5.0] * 9,
              "dirFromDeg": [180.0] * 9, "gustMS": [8.0] * 9, "speedP90": [7.5] * 9} for l in (1, 3, 6)]
    st.put_json(f"nbm/wheeler/{init:%Y%m%d%H}.json.gz", {"grid": "grids/nbm/wheeler.json", "status": "complete",
                                                          "modelVersion": "NBM pre-v4.3", "steps": steps})
    st.put_json("metar/20250102.json.gz", {"observations": [
        {"station": sid, "validTime": "2025-01-02T00:53:00Z", "speedMS": 7.2, "dirFromDeg": 180.0, "gustMS": None},
        {"station": sid, "validTime": "2025-01-02T03:05:00Z", "speedMS": 3.1, "dirFromDeg": 180.0, "gustMS": None}]})
    rows = {(r["station"], r["lead"]): r for r in W.build_rows("pw", str(tmp_path / "store"))}
    assert rows[(sid, 1)]["obs"] == 7.2 and rows[(sid, 1)]["b0"] == pytest.approx(5.0) and rows[(sid, 1)]["p90"] == pytest.approx(7.5)
    assert rows[(sid, 3)]["obs"] == 3.1 and rows[(sid, 6)]["obs"] is None and rows[(sid, 1)]["nbmVersion"] == "NBM pre-v4.3"


def test_fetch_counts_bytes_through_the_runtime(tmp_path, monkeypatch):
    """The budget wraps the runtime's own fetch functions and restores them afterwards (no network: stubbed)."""
    pytest.importorskip("numpy")
    pytest.importorskip("eccodes")
    grib, ingest, _, _, _ = W._runtime()
    real = (grib.fetch, ingest.fetch)
    seen = []

    def fake_cycle(store, cfg, t, leads, q):
        ingest.fetch("https://noaa-nbm-grib2-pds.s3.amazonaws.com/x")
        return {k: "complete" for k in cfg["lakes"]}

    def fake_metar(store, cfg, d):
        ingest.fetch("https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py")
        store.put_json(f"metar/{d:%Y%m%d}.json.gz", {"observations": []})
        return 0

    monkeypatch.setattr(ingest, "fetch", lambda url, *a, **k: seen.append(url) or b"abc")
    monkeypatch.setattr(ingest, "ingest_nbm_cycle", fake_cycle)
    monkeypatch.setattr(ingest, "ingest_metar_day", fake_metar)
    res = W.do_fetch("pw", str(tmp_path), max_pairs=3, month="2025-01")
    assert res["budget"]["bytes"] == 3 * len(seen) and len(seen) >= 2
    assert json.loads((tmp_path / "pw" / "budget.json").read_text())["bytes"] == res["budget"]["bytes"]
    assert grib.fetch is real[0]
