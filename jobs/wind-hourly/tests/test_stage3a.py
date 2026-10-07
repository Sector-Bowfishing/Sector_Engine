"""Stage 3A tooling: evidence events, scoreboard derivation, field QA, blind packets, over-water import.
Synthetic inputs here are SOFTWARE TEST FIXTURES ONLY — NOT SCIENTIFIC EVIDENCE — and never reach scoring."""
import csv
import json
import os
import stat
from datetime import datetime, timedelta, timezone

import pytest

from sector_wind import evidence, field_qa, fieldops, overwater, scoreboard
from sector_wind import field_run as FR
from sector_wind.sample import iso
from sector_wind.store import LocalStore

HERE = os.path.dirname(os.path.abspath(__file__))
IOS = fieldops.IOS
STAGE2 = os.path.join(IOS, "docs/intelligence/wind/stage2/validation_baseline_2026-09-22_2026-10-05.json")
needs_ios = pytest.mark.skipif(not os.path.exists(STAGE2), reason="iOS sector-wind worktree not present")


# ── evidence ─────────────────────────────────────────────────────────────────────────────────

def test_contingency_counts_and_insufficient_events():
    thr = 15 * 0.44704
    recs = [(8.0, 0, None, 7.0, 0, None), (5.0, 0, None, 7.0, 0, None), (7.0, 0, None, 5.0, 0, None), (1, 0, None, 1, 0, None)]
    c = evidence.contingency(recs, "speed", thr)
    assert (c["hits"], c["misses"], c["falseAlarms"], c["observedEvents"]) == (1, 1, 1, 2)
    assert c["status"] == "INSUFFICIENT EVENTS" and "pod" not in c


def test_missing_gust_is_not_an_event_and_not_zero():
    recs = [(3, 0, 11.0, 3, 0, None)]
    c = evidence.contingency(recs, "gust", 20 * 0.514444)
    assert c["observedEvents"] == 0 and c["falseAlarms"] == 1


# ── scoreboard ───────────────────────────────────────────────────────────────────────────────

@needs_ios
def test_scoreboard_reproduces_stage2_measured_dimensions():
    d = scoreboard.dims_1_to_4(json.load(open(STAGE2)), "stage2")
    pts = {k: scoreboard.WEIGHTS[k] * v["credit"] for k, v in d.items()}
    assert pts[1] == 0.0                              # >= 15 mph unmeasured -> 0 (strict)
    assert round(pts[2], 1) == 5.7                    # within 22.5 = 0.79 -> 0.71
    assert pts[3] == 0.0                              # >= 20 kt POD 0
    assert pts[4] == 5.0


def test_linear_credit_and_caps():
    assert scoreboard.lin(1.3, 1.6, 1.0) == pytest.approx(0.5)
    assert scoreboard.lin(None, 0, 1) == 0.0
    z = {6: {"credit": 0.0}, 7: {"credit": 0.0}}
    assert [c["cap"] for c in scoreboard.caps(z, {"measuredStationComparisons": 0})] == [6.0, 7.0]
    assert scoreboard.dim9({"developmentLakesComplete": 4, "directoryLakesPassed": 50})["credit"] == 1.0
    assert scoreboard.dim9({"developmentLakesComplete": 4, "directoryLakesPassed": 25})["credit"] == 0.5
    assert scoreboard.dim9({"developmentLakesComplete": 1, "directoryLakesPassed": 60})["credit"] == 0.0


def test_dim8_counts_only_complete_live_days(tmp_path):
    st = LocalStore(str(tmp_path))
    cfg = {"lakes": {"x": {}}, "stations": {}}
    d = scoreboard.dim8(st, cfg, datetime(2026, 10, 7, 20, tzinfo=timezone.utc))
    assert d["credit"] == 0.0 and "no complete live UTC day" in d["why"]


def test_score_log_is_append_only_and_only_on_change(tmp_path):
    log = tmp_path / "log.jsonl"
    s = {"computedAt": "t", "official": 2.9, "raw": 2.87, "caps": [], "dimensions": {1: {"name": "a", "points": 1.0, "why": "w"}}}
    assert scoreboard.append_log(str(log), s, "r") is not None
    assert scoreboard.append_log(str(log), s, "r") is None
    s2 = {**s, "official": 3.3, "dimensions": {1: {"name": "a", "points": 2.0, "why": "w2"}}}
    e = scoreboard.append_log(str(log), s2, "r2")
    assert e["oldScore"] == 2.9 and e["newScore"] == 3.3 and e["dimensionsChanged"] == ["1 a"]
    assert len(open(log).read().splitlines()) == 2


def test_dims_6_7_zero_without_certification(tmp_path):
    d = scoreboard.dims_6_7([str(tmp_path / "none*.jsonl")])
    assert d[6]["credit"] == 0 and d[7]["credit"] == 0


# ── field QA + immutability ─────────────────────────────────────────────────────────────────

def _record(**kw):
    r = {"schema": "sector-wind-field-v1", "candidateId": fieldops.CANDIDATE, "id": "R1", "createdAtUTC": "2026-10-07T02:00:00Z",
         "observer": "mc", "lake": "wilson", "bankId": None, "latitude": 34.8, "longitude": -87.5, "locationSource": "gps",
         "sessionId": "wilson|2026-10-06|mc", "pairId": None, "pairRole": "single", "observedClass": 2, "observedTexture": "T2",
         "photoFiles": [], "handheld": None, "notes": "", "observerWasBlinded": True, "tags": []}
    r.update(kw)
    return r


@needs_ios
def test_record_qa_reasons_and_never_repairs(tmp_path):
    o, _ = fieldops.load_table("wilson")
    bank = o["banks"][100]["id"]
    recs = [_record(id="ok", bankId=bank),
            _record(id="nobank"),
            _record(id="notex", bankId=bank, observedTexture=None),
            _record(id="hh", bankId=bank, handheld={"speedMS": 2.0, "heightM": None}),
            _record(id="photo", bankId=bank, photoFiles=["missing.jpg"]),
            _record(id="practice", bankId=bank, tags=["practice"]),
            _record(id="pairA", bankId=bank, pairId="P1", pairRole="A")]
    raw = tmp_path / "export"; raw.mkdir()
    (raw / "records.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    before = (raw / "records.jsonl").read_text()
    res = {r["recordId"]: r for r in field_qa.qa(str(raw), root=str(tmp_path / "field"))}
    assert res["ok"]["status"] == "ELIGIBLE" and "calibration-only" in res["ok"]["note"]
    assert res["nobank"]["status"] == "INELIGIBLE" and any("bank not identified" in w for w in res["nobank"]["reasons"])
    assert any("texture" in w for w in res["notex"]["reasons"])
    assert any("sensor height" in w for w in res["hh"]["reasons"])
    assert any("missing.jpg" in w for w in res["photo"]["reasons"])
    assert res["practice"]["status"] == "PRACTICE"
    assert any("exactly one A and one B" in w for w in res["pairA"]["reasons"])
    assert (raw / "records.jsonl").read_text() == before


def test_ingest_is_write_once_and_read_only(tmp_path):
    src = tmp_path / "exp"; src.mkdir(); (src / "records.jsonl").write_text("{}\n")
    root = str(tmp_path / "field")
    r = field_qa.ingest(str(src), "mc", "2026-10-07", root=root)
    p = os.path.join(r["folder"], "records.jsonl")
    assert not (os.stat(p).st_mode & stat.S_IWUSR)
    with pytest.raises(FileExistsError):
        field_qa.ingest(str(src), "mc", "2026-10-07", root=root)
    assert field_qa.verify(root)[0]["changedOrMissing"] == []
    for dp, ds, fs in os.walk(root):                  # let pytest clean up
        os.chmod(dp, 0o755)
        for f in fs:
            os.chmod(os.path.join(dp, f), 0o644)


# ── gaps / calibration readiness never expose holdout accuracy ───────────────────────────────

def test_gaps_and_calstatus_report_counts_only():
    rows = [{"sessionId": "wilson|2026-10-0%d|mc" % (i % 9 + 1), "lake": "wilson", "createdAtUTC": "2026-10-0%dT02:00:00Z" % (i % 9 + 1),
             "windMS": 3.0, "fetchM": 500, "dirFromDeg": 180, "geometryType": "cove", "observerWasBlinded": True, "bankId": f"B{i}",
             "observed": 5, "chopClass": 1, "predictedTexture": "T1", "tags": []} for i in range(30)]
    for r in rows:
        r["split"] = FR.F.assignment(r["sessionId"]); r["predicted"] = 1
    g = FR.gaps(rows)
    blob = json.dumps(g)
    assert "exact" not in blob and "within1" not in blob and "concordance" not in blob
    assert g["wind"]["2-4"][1] != "NEED" and g["wind"]["4-6.5"][1] == "NEED"
    c = FR.calstatus(rows)
    assert c["readyForCalibration"] is False and "exact" not in json.dumps(c)


# ── blind packet ─────────────────────────────────────────────────────────────────────────────

def _fake_archive(tmp_path, lake="wilson", speed=5.0, dirn=200.0):
    st = LocalStore(str(tmp_path / "arch"))
    o, _ = fieldops.load_table(lake)
    lats = [b["anchor"][0] for b in o["banks"]]; lons = [b["anchor"][1] for b in o["banks"]]
    la0, la1, lo0, lo1 = min(lats) - 0.05, max(lats) + 0.05, min(lons) - 0.05, max(lons) + 0.05
    nx, ny = 20, 12
    cells, glat, glon = [], [], []
    for r in range(ny):
        for c in range(nx):
            cells.append(r * nx + c); glat.append(la0 + (la1 - la0) * r / (ny - 1)); glon.append(lo0 + (lo1 - lo0) * c / (nx - 1))
    st.put_json(f"grids/nbm/{lake}.json", {"cells": cells, "lat": glat, "lon": glon, "nx": nx})
    init = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
    steps = [{"leadHours": h, "validTime": iso(init + timedelta(hours=h)), "speedMS": [speed] * len(cells),
              "dirFromDeg": [dirn] * len(cells), "gustMS": [speed * 1.5] * len(cells)} for h in range(1, 37)]
    st.put_json(f"nbm/{lake}/{init:%Y%m%d%H}.json.gz", {"initTime": iso(init), "grid": f"grids/nbm/{lake}.json", "steps": steps})
    return st, init


@needs_ios
def test_packet_observer_sheet_is_blind_and_key_is_complete(tmp_path, monkeypatch):
    monkeypatch.setattr(fieldops, "FIELD", str(tmp_path / "field"))
    st, init = _fake_archive(tmp_path)
    r = fieldops.packet(st, "wilson", "2026-10-07", block="1", n_pairs=4, now=init + timedelta(minutes=5))
    sheet = list(csv.DictReader(open(os.path.join(r["folder"], "OBSERVER-SHEET.csv"))))
    assert sheet and set(sheet[0]) == {"order", "pairId", "bank", "bankId", "lat", "lon", "targetTimeUTC", "appleMaps"}
    text = open(os.path.join(r["folder"], "OBSERVER-SHEET.csv")).read() + open(os.path.join(r["folder"], "MAP-LINKS.txt")).read()
    for leak in ("expos", "protect", "fetch", "hm0", "class", "calm", "shelter"):
        assert leak not in text.lower()
    key = json.load(open(os.path.join(r["folder"], "SEALED-KEY.json")))
    need = {"pairId", "bankA", "bankB", "fetchA", "fetchB", "fetchRatio", "hm0A", "hm0B", "hm0Ratio", "texturePredictionA",
            "texturePredictionB", "predictedClassA", "predictedClassB", "windA", "windB", "windDifference", "geometryTypeA", "geometryTypeB"}
    assert need <= set(key["pairs"][0])
    assert {"candidateId", "forecastInit", "validTime", "leadHours"} <= set(key)
    assert all(p["hm0A"] > p["hm0B"] and not p["tieExcluded"] for p in key["pairs"])
    with pytest.raises(SystemExit):
        fieldops.packet(st, "wilson", "2026-10-07", block="1", n_pairs=4, now=init + timedelta(minutes=5))


@needs_ios
def test_practice_packet_is_labelled(tmp_path, monkeypatch):
    monkeypatch.setattr(fieldops, "FIELD", str(tmp_path / "field"))
    st, init = _fake_archive(tmp_path)
    r = fieldops.packet(st, "wilson", "2026-10-07", block="1", n_pairs=3, practice=True, now=init + timedelta(minutes=5))
    assert r["folder"].endswith("-PRACTICE") and 'Tag EVERY record "practice"' in open(os.path.join(r["folder"], "SESSION-README.txt")).read()


# ── over-water import (SYNTHETIC FIXTURE — NOT SCIENTIFIC EVIDENCE) ───────────────────────────

def test_overwater_import_rejects_missing_height_and_bad_qc():
    p = overwater.parse(open(os.path.join(HERE, "fixtures/overwater_SYNTHETIC.jsonl")).read(), "fixture")
    assert p["evidenceClass"] == overwater.SYNTHETIC
    assert len(p["accepted"]) == 3 and len(p["rejected"]) == 2
    reasons = json.dumps(p["rejected"])
    assert "sensorHeightM" in reasons and "qcFlag bad" in reasons
    s = p["accepted"][0]["sample"]
    assert s.kind.kind == "observed" and s.kind.sensorHeightM == 4.5 and s.kind.averaging == "600-s"
    calm = p["accepted"][2]["sample"]
    assert calm.isCalm and calm.dirFromDeg is None


def test_overwater_requires_declared_evidence_class():
    with pytest.raises(ValueError):
        overwater.parse('{"stationId": "x"}\n', "nometa")


def test_synthetic_never_reaches_comparison_by_default(tmp_path):
    st = LocalStore(str(tmp_path))
    p = overwater.parse(open(os.path.join(HERE, "fixtures/overwater_SYNTHETIC.jsonl")).read(), "fixture")
    overwater.store_import(st, p)
    assert st.list("synthetic/overwater/") and not st.list("overwater/")
    cfg = json.load(open(os.path.join(os.path.dirname(HERE), "lakes.json")))
    t0 = datetime(2026, 10, 7, tzinfo=timezone.utc)
    assert overwater.compare(st, cfg, "SYN-WI1", t0, t0)["n"] == 0          # synthetic is invisible unless allowed


def test_synthetic_comparison_is_stamped_when_explicitly_allowed(tmp_path):
    st, init = _fake_archive(tmp_path) if os.path.exists(STAGE2) else (None, None)
    if st is None:
        pytest.skip("needs the iOS fetch table for the fake archive")
    p = overwater.parse(open(os.path.join(HERE, "fixtures/overwater_SYNTHETIC.jsonl")).read(), "fixture")
    overwater.store_import(st, p)
    cfg = json.load(open(os.path.join(os.path.dirname(HERE), "lakes.json")))
    st.put_json("grids/rtma/wilson.json", st.get_json("grids/nbm/wilson.json"))
    r = overwater.compare(st, cfg, "SYN-WI1", init.replace(hour=0), init.replace(hour=0), allow_synthetic=True)
    assert "NOT SCIENTIFIC EVIDENCE" in r["BANNER"] and r["sources"]["NBM +3h"]["n"] >= 1
    assert "SENSITIVITY ONLY" in r["sensitivity"]["label"]
