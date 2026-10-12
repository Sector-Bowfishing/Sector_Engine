"""WindBrain adapter tests (offline): contract keys, canonical lake mapping, state honesty, write isolation."""
import json, math, os, random, sys
from datetime import datetime, timedelta, timezone

import pytest

from sector_wind.store import LocalStore
from sector_wind.ingest import load_config
from sector_wind.brain import contract as C
from sector_wind.brain.lakes import WIND_LAKE_IDS, DirectoryError, check_keys, verify_wind_lakes
from sector_wind.brain.state import build_state, frozen_duration_h
from sector_wind.brain.publish import publish, safe_publish
from sector_wind.brain.writer import DryRunWriter, RtdbWriter, WriteError

NOW = datetime(2026, 10, 12, 6, 20, tzinfo=timezone.utc)
CFG = load_config()
DIRECTORY = [
    {"id": "Guntersville|AL", "name": "Guntersville", "state": "AL", "lat": 34.42, "lon": -86.26},
    {"id": "Wheeler|AL", "name": "Wheeler", "state": "AL", "lat": 34.63, "lon": -87.03},
    {"id": "Wilson|AL", "name": "Wilson", "state": "AL", "lat": 34.77, "lon": -87.45},
    {"id": "Pickwick Lake|TN", "name": "Pickwick Lake", "state": "TN", "lat": 35.05, "lon": -88.2},
    {"id": "Wilson Lake|KS", "name": "Wilson Lake", "state": "KS", "lat": 38.93, "lon": -98.51},
    {"id": "Lake St. Clair|MI", "name": "Lake St. Clair", "state": "MI", "lat": 42.4, "lon": -82.7},
]


def _grid(lat, lon, n=5, step=0.02):
    cells, la, lo = [], [], []
    for r in range(n):
        for c in range(n):
            cells.append(r * n + c); la.append(lat - (n // 2 - r) * step); lo.append(lon + (c - n // 2) * step)
    return {"cells": cells, "lat": la, "lon": lo, "nx": n}


def _arr(v, n=25):
    return [v] * n


def make_store(tmp_path, with_rtma=True, with_nbm=True, speed=6.0, direction=225.0):
    st = LocalStore(str(tmp_path))
    for wl, lid in WIND_LAKE_IDS.items():
        d = next(x for x in DIRECTORY if x["id"] == lid)
        st.put_json(f"grids/nbm/{wl}.json", _grid(d["lat"], d["lon"])); st.put_json(f"grids/rtma/{wl}.json", _grid(d["lat"], d["lon"]))
        if with_nbm:
            init = NOW.replace(minute=0) - timedelta(hours=1)
            steps = [{"leadHours": L, "validTime": C.iso(init + timedelta(hours=L)), "speedMS": _arr(speed + 0.5 * L), "dirFromDeg": _arr(direction),
                      "gustMS": _arr(speed + 3)} for L in range(1, 31)]
            st.put_json(f"nbm/{wl}/{init:%Y%m%d%H}.json.gz", {"schema": "sector-wind-cycle-v1", "kind": "forecast", "model": "NBM", "modelVersion": "NBM v5.0",
                                                               "initTime": C.iso(init), "retrievedAt": C.iso(init + timedelta(minutes=62)), "status": "complete",
                                                               "grid": f"grids/nbm/{wl}.json", "steps": steps})
        if with_rtma:
            for k in range(0, 14 * 4):
                ts = NOW.replace(minute=15) - timedelta(minutes=15 * k)
                st.put_json(f"rtma/{wl}/{ts:%Y%m%d}/{ts:%H%M}.json.gz", {"kind": "analysis", "analysisTime": C.iso(ts), "retrievedAt": C.iso(ts + timedelta(minutes=20)),
                                                                          "grid": f"grids/rtma/{wl}.json", "speedMS": _arr(speed), "dirFromDeg": _arr(direction), "gustMS": _arr(speed + 2)})
    st.put_json(f"metar/{NOW:%Y%m%d}.json.gz", {"observations": [{"station": s, "network": v["network"], "validTime": C.iso(NOW - timedelta(minutes=25)),
                                                                   "speedMS": 5.0, "dirFromDeg": 220.0, "gustMS": None, "averaging": "2-min", "sensorHeightM": 10.0}
                                                                  for s, v in CFG["stations"].items()]})
    return st


def test_lake_key_and_collisions():
    assert C.lake_key("Guntersville|AL") == "Guntersville_AL"
    assert C.lake_key("Lake St. Clair|MI") == "Lake_St_Clair_MI"
    assert check_keys(DIRECTORY)["Pickwick Lake|TN"] == "Pickwick_Lake_TN"
    with pytest.raises(DirectoryError):
        check_keys(DIRECTORY + [{"id": "Lake St Clair|MI"}])


def test_wind_lakes_verified_against_directory():
    assert set(verify_wind_lakes(DIRECTORY, CFG)) == set(WIND_LAKE_IDS)
    bad = [dict(x) for x in DIRECTORY]; bad[2]["lon"] = -98.0      # Wilson|AL moved outside its box
    with pytest.raises(DirectoryError):
        verify_wind_lakes(bad, CFG)
    with pytest.raises(DirectoryError):
        verify_wind_lakes([x for x in DIRECTORY if x["id"] != "Wheeler|AL"], CFG)


def test_frozen_duration_matches_research_mirror():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "research"))
    import wave_memory as W
    rnd = random.Random(3)
    for _ in range(500):
        ser = [(None, None) if rnd.random() < 0.05 else (rnd.uniform(0, 9), rnd.choice([None, rnd.uniform(0, 360)])) for _ in range(13)]
        if ser[-1][0] is None:
            continue
        mine = frozen_duration_h(ser)
        ref = W.duration([{"speedMS": s, "dirFromDeg": d} for s, d in ser])
        assert mine == ref


def test_state_analysis_is_labelled_and_complete(tmp_path):
    st = make_store(tmp_path)
    s, rows, meta = build_state(st, CFG, "guntersville", "Guntersville|AL", DIRECTORY[0], NOW, None, "test")
    assert s["kind"] == "analysis" and meta["readiness"] == "CALIBRATION" and not s["stale"]
    assert s["sustainedMph"] == pytest.approx(6.0 / 0.44704, abs=0.06) and s["directionDeg"] == 225 and s["directionCardinal"] == "SW"
    assert 0 < len(s["hourly"]) <= C.HOURLY_MAX and all(set(e) >= {"at", "mph", "gustMph", "dirDeg"} for e in s["hourly"])
    assert s["trend"] == "rising"                                   # NBM +3 h is ~3.4 mph above the analysis
    assert s["observation"]["station"] in ("8A1", "4A6") and s["analysis"]["product"].startswith("RTMA")
    assert s["provenance"]["modelVersion"] == C.CANDIDATE_MODEL and s["provenance"]["generatedAt"] == C.iso(NOW)
    assert "fetchTablesUnavailable" in s["provenance"]["qualityFlags"] and s["surfaceState"] is None   # unknown stays unknown
    blob = json.dumps(s)
    assert "confidencePct" not in blob and "NaN" not in blob


def test_state_forecast_fallback_and_unavailable(tmp_path):
    st = make_store(tmp_path / "a", with_rtma=False)
    s, _, meta = build_state(st, CFG, "wheeler", "Wheeler|AL", DIRECTORY[1], NOW, None, "test")
    assert s["kind"] == "forecast" and s["analysis"] is None and "noFreshAnalysis" in s["provenance"]["qualityFlags"]
    st2 = make_store(tmp_path / "b", with_rtma=False, with_nbm=False)
    s2, _, meta2 = build_state(st2, CFG, "wheeler", "Wheeler|AL", DIRECTORY[1], NOW, None, "test")
    assert s2["kind"] == "unavailable" and s2["sustainedMph"] is None and s2["directionDeg"] is None and s2["trend"] is None
    assert meta2["readiness"] == "DEGRADED" and s2["stale"]


ALLOWED = ("brains/wind", "validation/wind", "health/brains/wind", "health/jobs/wind-hourly", "sources/noaa-", "sources/iem-",
           "health/sources/noaa-", "health/sources/iem-", "activity/")


def _allowed(path):
    p = path.split("/")
    if path.startswith(ALLOWED):
        return path.startswith("activity/") is False or "_wind_" in path
    if p[0] == "lakes" and len(p) >= 4:
        return p[2:4] in (["states", "wind"], ["profiles", "wind"], ["validation", "wind"])
    if p[0] == "snapshots":
        return p[2] == "latest" and (p[3] in ("wind", "lakeId", "snapshotVersion", "generatedAt") or p[3:5] == ["brainVersions", "wind"])
    if p[0] == "lakeFleet":
        return p[2] in ("lakeId", "lastUpdatedAt") or p[2:4] in (["readiness", "wind"], ["modelVersions", "wind"], ["slots", "wind"])
    return False


def test_publish_writes_only_wind_owned_paths(tmp_path):
    st = make_store(tmp_path)
    w = DryRunWriter()
    rep = publish(st, CFG, w, now=NOW, run_summary={"runAt": C.iso(NOW), "errors": [], "seconds": 90}, directory=DIRECTORY)
    assert rep["ok"], rep["errors"]
    paths = [p for patch in w.patches for p in patch]
    bad = [p for p in paths if not _allowed(p)]
    assert not bad, bad[:5]
    assert not any(p.startswith(("schemaVersion", "health/engine", "health/rtdb", "access", "validationOps")) for p in paths)
    reg = w.get("brains/wind")
    assert reg["readinessCounts"] == {"CALIBRATION": 4, "DISCOVERED": 2} and reg["supportedLakeCount"] == 4
    assert {v["status"] for v in reg["versions"]} == {"CURRENT", "SHADOW"} and reg["researchCandidate"]["promoted"] is False
    assert w.get("lakeFleet/Wilson_Lake_KS/readiness/wind") == "DISCOVERED" and w.get("lakeFleet/Wilson_Lake_KS/lakeId") == "Wilson Lake|KS"
    snap = w.get("snapshots/Pickwick_Lake_TN/latest")
    assert snap["lakeId"] == "Pickwick Lake|TN" and snap["wind"]["provenance"]["brainId"] == "wind" and snap["brainVersions"] == {"wind": C.BRAIN_VERSION}
    assert w.get("validation/wind")["liveValidation"].startswith("SEALED")
    assert w.get("lakeFleet/Wheeler_AL/slots/wind") == {"readiness": "CALIBRATION", "stale": False, "stateType": "analysis", "issueCount": 0, "lastUpdatedAt": C.iso(NOW)}
    assert w.get("health/brains/wind")["status"] == "HEALTHY"


def test_publish_never_raises_on_writer_failure(tmp_path):
    class Broken(DryRunWriter):
        def patch(self, updates):
            raise WriteError("RTDB down")
    rep = safe_publish(make_store(tmp_path), CFG, Broken(), now=NOW, directory=DIRECTORY)
    assert rep["ok"] is False and rep["errors"]


def test_directory_failure_only_marks_health(tmp_path):
    w = DryRunWriter()
    rep = publish(make_store(tmp_path), CFG, w, now=NOW, directory=[d for d in DIRECTORY if d["id"] != "Wilson|AL"])
    assert not rep["ok"] and set(w.tree) == {"health"} and w.get("health/brains/wind/status") == "FAILED"


def test_writer_refuses_app_databases():
    for url in ("https://sector-9393c-default-rtdb.firebaseio.com", "https://sector-dev-1f4d0.firebaseio.com", "https://example.firebaseio.com"):
        with pytest.raises(WriteError):
            RtdbWriter(url, token="x")
    RtdbWriter("https://sector-brain.firebaseio.com", token="x")
