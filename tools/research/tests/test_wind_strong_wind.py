"""Protocol WSW-2026-11-23 runner: guards, M-B fit maths and scoring on SYNTHETIC fixtures (offline, stdlib only)."""
import datetime as dt
import json
import os
import random
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import wind_strong_wind as W  # noqa: E402

UTC = dt.timezone.utc


def test_protocol_verifies_and_matches_runner_constants():
    proto, sha = W.load_protocol()
    assert proto["protocolId"] == "WSW-2026-11-23" and len(sha) == 64
    assert proto["forecastRows"]["leads"] == list(W.LEADS)
    assert proto["methods"]["M-B"]["fit"]["levels"] == list(W.LEVELS)
    assert proto["methods"]["M-B"]["fit"]["minimumRows"] == W.MIN_FIT_ROWS
    assert proto["windows"]["PW"]["inits"] == ["2025-11-01T00:00Z", "2026-04-30T18:00Z"]
    assert proto["windows"]["H2"]["inits"][0] == "2026-10-07T00:00Z"
    assert set(proto["outputsAndAdmission"]["labels"]) == set(W.LABELS)
    assert {h.split()[0] for h in proto["budget"]["hosts"]} == W.ALLOWED_HOSTS


def test_changed_protocol_is_refused(tmp_path):
    p = tmp_path / "p.json"
    shutil.copy(W.PROTOCOL, p)
    shutil.copy(W.PROTOCOL + ".sha256", str(p) + ".sha256")
    W.load_protocol(str(p))
    p.write_text(p.read_text().replace("PRE-REGISTERED", "EDITED"))
    with pytest.raises(W.Refused):
        W.load_protocol(str(p))


def test_night_pairs_are_synoptic_night_only():
    pw = W.night_pairs("pw")
    days = (W.WINDOWS["pw"][1].date() - W.WINDOWS["pw"][0].date()).days + 1
    assert len(pw) == 6 * days
    for t, l in pw:
        assert t.hour in W.SYNOPTIC and 1 <= (t + dt.timedelta(hours=l)).hour <= 8
        assert W.WINDOWS["pw"][0] <= t <= W.WINDOWS["pw"][1]
    assert {(t.hour, l) for t, l in pw} == {(0, 1), (0, 3), (0, 6), (6, 1), (12, 18), (18, 12)}


def test_h2_is_sealed_until_2027():
    with pytest.raises(W.Refused):
        W.guard_window("h2", dt.datetime(2026, 12, 31, 23, 59, tzinfo=UTC), "score")
    W.guard_window("h2", dt.datetime(2027, 1, 1, tzinfo=UTC), "score")
    W.guard_window("pw", dt.datetime(2026, 11, 23, tzinfo=UTC), "score")


def test_fit_refuses_rows_outside_cal_h1():
    W.guard_fit_window([dt.datetime(2026, 5, 6, tzinfo=UTC), dt.datetime(2026, 10, 6, 23, tzinfo=UTC)])
    for bad in (dt.datetime(2026, 10, 7, tzinfo=UTC), dt.datetime(2026, 3, 1, tzinfo=UTC)):
        with pytest.raises(W.Refused):
            W.guard_fit_window([bad])


def test_hosts_are_limited_to_the_protocol_list():
    W.check_hosts(["https://noaa-nbm-grib2-pds.s3.amazonaws.com/x", "https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py"])
    for bad in ("http://mesonet.agron.iastate.edu/x", "https://storage.googleapis.com/x", "https://example.org/x"):
        with pytest.raises(W.Refused):
            W.check_hosts([bad])


def test_quantile_type7():
    x = [1.0, 2.0, 3.0, 4.0]
    assert W.quantile(x, 0.5) == 2.5 and W.quantile(x, 0.0) == 1.0 and W.quantile(x, 1.0) == 4.0


def _synthetic_pairs(n=20000, seed=1):
    """SYNTHETIC: forecast low-biased in the upper tail (obs = f + 0.5 f^2/10)."""
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        f = rng.gammavariate(2.0, 1.2)
        out.append((f, f + 0.05 * f * f))
    return out


def test_fit_qm_maps_upper_tail_and_is_monotone():
    fit = W.fit_qm(_synthetic_pairs())
    assert fit["n"] == 20000 and len(fit["knots"]) == len(W.LEVELS)
    xs = [i / 10 for i in range(0, 150)]
    ys = [W.apply_qm(fit, x) for x in xs]
    assert all(b >= a for a, b in zip(ys, ys[1:]))
    top = fit["knots"][-1]
    assert abs(W.apply_qm(fit, top[0]) - (top[0] + 0.05 * top[0] ** 2)) < 0.05
    assert W.apply_qm(fit, 6.0) > 6.0


def test_fit_refuses_too_few_rows():
    with pytest.raises(W.Refused):
        W.fit_qm(_synthetic_pairs(500))


def test_fit_ties_are_merged():
    pairs = [(1.0, 1.0)] * 15000 + [(2.0, 3.0)] * 10
    fit = W.fit_qm(pairs)
    assert [k[0] for k in fit["knots"]] == sorted({k[0] for k in fit["knots"]})


def test_wi4_and_gate_match_the_rubric():
    zero_fc = {str(l): W.table([(False, True)] * 5 + [(False, False)] * 50) for l in W.LEADS}
    assert W.wi4_credit(zero_fc) == 0.0 and not W.scoreboard_gate(zero_fc)   # the CAL+H1 pattern: POD 0 everywhere
    perfect = {str(l): W.table([(True, True)] * 5 + [(False, False)] * 50) for l in W.LEADS}
    assert W.wi4_credit(perfect) == 1.0 and W.scoreboard_gate(perfect)
    half = {str(l): W.table([(True, True)] * 2 + [(False, True)] * 2 + [(True, False)] * 3) for l in W.LEADS}   # POD .5 FAR .6
    assert W.wi4_credit(half) == pytest.approx(2 / 3, abs=1e-3)
    one_lead_empty = dict(perfect, **{"18": W.table([(False, False)] * 50)})
    assert W.wi4_credit(one_lead_empty) == 0.0
    assert W.wi4_credit({str(l): W.table([(False, False)] * 10) for l in W.LEADS}) == 0.0


def _rows(n_days=60, p90=True, seed=7):
    """SYNTHETIC rows: deterministic NBM never reaches 15 mph; P90 does on strong nights."""
    rng = random.Random(seed)
    rows = []
    for d in range(n_days):
        day = dt.datetime(2025, 11, 1, tzinfo=UTC) + dt.timedelta(days=d)
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


def test_score_supports_a_method_that_detects_and_not_the_baseline():
    res = W.score(_rows(), FLAT_FIT, boot_n=200)
    assert res["methods"]["B0"]["pooled"]["pod"] == 0.0 and res["methods"]["B0"]["wi4Credit"] == 0.0
    assert res["methods"]["M-A"]["pooled"]["pod"] > 0.5
    assert res["outcome"]["M-A"] == "SUPPORTED" and res["outcome"]["M-B"] == "NOT_SUPPORTED"
    assert res["labels"] == W.LABELS and res["bootstrap"]["resamples"] == 200


def test_score_is_deterministic():
    a = W.score(_rows(), FLAT_FIT, boot_n=100)
    b = W.score(_rows(), FLAT_FIT, boot_n=100)
    assert a["bootstrap"] == b["bootstrap"]


def test_score_refuses_to_pass_without_enough_events_or_p90():
    assert set(W.score(_rows(n_days=4), FLAT_FIT, boot_n=50)["outcome"].values()) == {"INSUFFICIENT_EVENTS"}
    assert set(W.score(_rows(p90=False), FLAT_FIT, boot_n=50)["outcome"].values()) == {"NOT_EVALUABLE"}


def test_day_rows_are_not_scored():
    r = _rows(n_days=1)
    for x in r:
        x["valid"] = x["valid"][:11] + "14:00:00Z"
    assert W.score(r, FLAT_FIT, boot_n=10)["rowsNight"] == 0


def _cli(*args):
    return W.main(list(args))


def test_cli_order_and_one_shot(tmp_path, monkeypatch):
    out = str(tmp_path)
    assert _cli("verify") == 0
    assert _cli("fetch", "--window", "pw", "--out", out) == 3                       # no fit yet: PW data never reaches disk first
    assert _cli("score", "--window", "h2", "--out", out) == 3                       # sealed
    _, psha = W.load_protocol()
    fit = dict(FLAT_FIT, protocolSha256=psha)
    (tmp_path / W.FIT_FILE).write_text(json.dumps(fit))
    rows = tmp_path / "h2" / "rows.jsonl"
    rows.parent.mkdir()
    rows.write_text("".join(json.dumps(r) + "\n" for r in _rows()))
    assert _cli("score", "--window", "h2", "--out", out, "--now", "2026-12-31T23:00:00Z") == 3
    assert _cli("score", "--window", "h2", "--out", out, "--now", "2027-01-02T00:00:00Z", "--boot", "50") == 0
    res = json.loads((tmp_path / "h2" / "wsw-result.json").read_text())
    assert res["protocolSha256"] == psha and res["admission"].startswith("none")
    assert _cli("score", "--window", "h2", "--out", out, "--now", "2027-01-03T00:00:00Z", "--boot", "50") == 3   # one shot
    assert _cli("fit", "--out", out, "--corpus-store", out) == 3                    # fit frozen once


def test_fit_from_another_protocol_is_refused(tmp_path):
    (tmp_path / W.FIT_FILE).write_text(json.dumps(dict(FLAT_FIT, protocolSha256="0" * 64)))
    assert _cli("score", "--window", "pw", "--out", str(tmp_path)) == 3


def test_import_stays_offline_and_stdlib():
    import subprocess
    code = ("import sys; sys.path.insert(0, %r); import wind_strong_wind; "
            "assert not {'numpy', 'eccodes', 'sector_wind'} & set(sys.modules)") % os.path.dirname(HERE)
    subprocess.run([sys.executable, "-c", code], check=True)


def test_definitions_match_the_wind_runtime():
    np = pytest.importorskip("numpy")  # noqa: F841
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
    ingest, interp, store, validate = W._runtime()
    cfg = W._cfg(ingest)
    st = store.LocalStore(str(tmp_path / "pw" / "store"))
    sid = "HSV"
    s = cfg["stations"][sid]
    nx = 10
    cells = [r * nx + c for r in range(3) for c in range(3)]
    lat = [s["lat"] - 0.02 + 0.02 * r for r in range(3) for _ in range(3)]
    lon = [s["lon"] - 0.02 + 0.02 * c for _ in range(3) for c in range(3)]
    st.put_json("grids/nbm/wheeler.json", {"cells": cells, "lat": lat, "lon": lon, "nx": nx})
    init = dt.datetime(2025, 11, 1, 0, tzinfo=UTC)
    steps = [{"leadHours": l, "validTime": f"{init + dt.timedelta(hours=l):%Y-%m-%dT%H:%M:%SZ}", "speedMS": [5.0] * 9,
              "dirFromDeg": [180.0] * 9, "gustMS": [8.0] * 9, "speedP90": [7.5] * 9} for l in (1, 3, 6)]
    st.put_json(f"nbm/wheeler/{init:%Y%m%d%H}.json.gz", {"grid": "grids/nbm/wheeler.json", "status": "complete",
                                                          "modelVersion": "NBM v4.3", "steps": steps})
    st.put_json("metar/20251101.json.gz", {"observations": [
        {"station": sid, "validTime": "2025-11-01T00:53:00Z", "speedMS": 7.2, "dirFromDeg": 180.0, "gustMS": None},
        {"station": sid, "validTime": "2025-11-01T03:05:00Z", "speedMS": 3.1, "dirFromDeg": 180.0, "gustMS": None}]})
    rows = {(r["station"], r["lead"]): r for r in W.build_rows("pw", str(tmp_path))}
    assert rows[(sid, 1)]["obs"] == 7.2 and rows[(sid, 1)]["b0"] == pytest.approx(5.0) and rows[(sid, 1)]["p90"] == pytest.approx(7.5)
    assert rows[(sid, 3)]["obs"] == 3.1 and rows[(sid, 6)]["obs"] is None
    assert rows[(sid, 1)]["nbmVersion"] == "NBM v4.3"


def test_month_by_month_covers_the_window_exactly():
    months = ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04"]
    parts = [p for m in months for p in W.month_pairs("pw", m)]
    assert parts == W.night_pairs("pw")
    with pytest.raises(W.Refused):
        W.month_pairs("pw", "2026-05")


def test_fetch_refuses_a_full_volume_before_any_download(tmp_path):
    _, psha = W.load_protocol()
    (tmp_path / W.FIT_FILE).write_text(json.dumps(dict(FLAT_FIT, protocolSha256=psha)))
    assert W.guard_free_space(str(tmp_path / "pw" / "store"), None) > 0
    assert _cli("fetch", "--window", "pw", "--out", str(tmp_path), "--month", "2025-11", "--min-free-gb", "1e9") == 3
    assert _cli("fetch", "--window", "pw", "--out", str(tmp_path), "--month", "2026-07") == 3
    assert not (tmp_path / "pw").exists()
