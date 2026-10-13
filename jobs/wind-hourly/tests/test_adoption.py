"""Wind adoption foundation: tonight block, bank-impact vocabulary, fleet tiers, H2 immutability, field schema.
Offline. Convention tests protect the verified FROM-direction geometry."""
import copy, hashlib, json, math, os
from datetime import datetime, timedelta, timezone

import pytest

from sector_wind.brain import contract as C
from sector_wind.brain import exposure as EX
from sector_wind.brain import field_schema as FS
from sector_wind.brain import fleet as FL
from sector_wind.brain import tonight as TN
from sector_wind import bowfishing as BF
from sector_wind import fleet_sampling as FSM
from sector_wind import h2 as H2

UTC = timezone.utc
HERE = os.path.dirname(os.path.abspath(__file__))


def hrs(start, speeds, dirs=None):
    return [{"at": C.iso(start + timedelta(hours=i)), "mph": s, "dirDeg": (dirs[i] if dirs else 225), "gustMph": None} for i, s in enumerate(speeds)]


NOW = datetime(2026, 10, 12, 18, 20, tzinfo=UTC)       # 13:20 CDT -> tonight = 00Z-06Z on the 13th
INIT = datetime(2026, 10, 12, 17, tzinfo=UTC)
W0 = datetime(2026, 10, 13, 0, tzinfo=UTC)


def tonight(speeds, p90=None, dirs=None, init=INIT, tz="America/Chicago", now=NOW):
    steps = hrs(W0 - timedelta(hours=7), [5.0] * 7) + hrs(W0, speeds, dirs)
    p = None if p90 is None else [{"at": s["at"], "p90Mph": v} for s, v in zip(hrs(W0, p90), p90)]
    return TN.build_tonight(steps, p, init, init if p else None, now, tz, {"kind": "forecast", "sustainedMph": 5.0})


# ── direction convention ────────────────────────────────────────────────────────────────────
def test_wind_from_southwest_hits_the_northeast_shore():
    ne_bank = {"anchor": [34.50, -86.20], "standoff": [34.4997, -86.2003]}      # water lies to the SW of the shoreline point -> faces SW
    sw_bank = {"anchor": [34.40, -86.30], "standoff": [34.4003, -86.2997]}      # water lies to the NE -> faces NE
    fa, fb = EX.facing_deg(ne_bank), EX.facing_deg(sw_bank)
    assert 200 < fa < 250 and 20 < fb < 70
    assert EX.label_bank(225, 12, fa, 4)["label"] == "DIRECT"                   # SW wind (FROM 225) hits the NE shore
    assert EX.label_bank(225, 12, fb, 2)["label"] == "PROTECTED"                # the SW shore has land upwind
    assert EX.label_bank(225, 12, fb, 2)["reason"] == "windComesOverLand"


def test_from_direction_is_not_inverted():
    # wind FROM 270 (west) hits a bank that faces west (water to its west), not one that faces east
    assert EX.label_bank(270, 10, 270, 3)["label"] == "DIRECT"
    assert EX.label_bank(270, 10, 90, 2)["label"] == "PROTECTED"
    assert EX.label_bank(270, 10, 0, 3)["label"] == "CROSS"                    # shore-parallel


def test_direct_cross_protected_thresholds_and_high_fetch():
    assert EX.label_bank(0, 10, 45, 3)["label"] == "DIRECT"                    # alpha 45 inclusive
    assert EX.label_bank(0, 10, 46, 3)["label"] == "CROSS"
    assert EX.label_bank(0, 10, 90, 3)["label"] == "CROSS"
    assert EX.label_bank(0, 10, 91, 2)["label"] == "PROTECTED"
    odd = EX.label_bank(0, 18, 180, 4)                                           # fetch says HIGH although facing says lee: never PROTECTED
    assert odd["label"] == "CROSS" and odd["highFetch"] is True and odd["reason"] == "fetchOverridesFacing"
    mid = EX.label_bank(0, 12, 180, 3)                                           # 3-6 in of chop on a lee-facing bank: also never PROTECTED
    assert mid["label"] == "CROSS" and mid["highFetch"] is False
    assert EX.label_bank(0, 12, 180, 2)["label"] == "PROTECTED"                  # < 3 in and lee: protected
    d = EX.label_bank(0, 18, 0, 4); assert d["label"] == "DIRECT" and d["highFetch"] is True
    c = EX.label_bank(0, 18, 80, 3); assert c["label"] == "CROSS" and c["highFetch"] is False
    cove = EX.label_bank(0, 12, 0, 1); assert cove["label"] == "PROTECTED" and cove["reason"] == "shortFetch"   # short fetch protects even facing the wind


def test_unknown_never_reads_as_protected():
    assert EX.label_bank(225, 12, None, 3)["label"] == "UNKNOWN"
    assert EX.label_bank(225, 12, 225, 3, below_resolution=True)["label"] == "UNKNOWN"
    assert EX.label_bank(None, 12, 225, 3)["label"] == "UNKNOWN"
    assert EX.label_bank(225, 2.0, 225, 3)["reason"] == "windTooLightForDirection"
    assert EX.facing_deg({"anchor": [1, 2], "standoff": [1, 2]}) is None
    assert EX.facing_deg({}) is None


def test_label_classification_is_deterministic():
    banks = [{"anchor": [34.5, -86.2], "standoff": [34.4997, -86.2003]}] * 3
    a = [EX.label_bank(225, 12, EX.facing_deg(b), 4) for b in banks]
    assert a == [EX.label_bank(225, 12, EX.facing_deg(b), 4) for b in copy.deepcopy(banks)]
    assert EX.label_shares(a)["directPct"] == 100.0


# ── estimated geometry end to end (square lake, wind FROM SW) ───────────────────────────────
def test_estimated_table_square_lake_sw_wind():
    pytest.importorskip("shapely"); pytest.importorskip("PIL"); pytest.importorskip("scipy")
    from shapely.geometry import box
    from sector_wind.brain import estimate as ES
    from sector_wind.brain.state import decode_fetch_table
    lat0, lon0 = 35.0, -90.0
    dlat, dlon = 6000 / 110574.0, 6000 / (111320.0 * math.cos(math.radians(35.0)))
    obj = ES.build_estimated_table(box(lon0, lat0, lon0 + dlon, lat0 + dlat), "Test Lake|XX")
    assert obj["geometryTier"] == "ESTIMATED" and obj["validated"] is False
    assert obj == ES.build_estimated_table(box(lon0, lat0, lon0 + dlon, lat0 + dlat), "Test Lake|XX")       # deterministic
    banks, table = decode_fetch_table(obj)
    ne = min(range(len(banks)), key=lambda i: (banks[i]["anchor"][0] - (lat0 + dlat)) ** 2 + (banks[i]["anchor"][1] - (lon0 + dlon)) ** 2)
    sw = min(range(len(banks)), key=lambda i: (banks[i]["anchor"][0] - lat0) ** 2 + (banks[i]["anchor"][1] - lon0) ** 2)
    u = 15 * 0.44704
    def lab(i):
        eff = BF.nine_ray(table[i], 225)
        return eff, EX.label_bank(225, 15, EX.facing_deg(banks[i]), BF.chop_class(BF.cem(u, eff, 6 * 3600)), banks[i]["belowResolution"])
    eff_ne, l_ne = lab(ne); eff_sw, l_sw = lab(sw)
    assert eff_ne > 6000 and l_ne["label"] == "DIRECT" and l_ne["highFetch"] is True
    assert eff_sw < 500 and l_sw["label"] == "PROTECTED"


def test_estimate_rejects_unusable_geometry():
    pytest.importorskip("shapely"); pytest.importorskip("PIL"); pytest.importorskip("scipy")
    from shapely.geometry import Point, GeometryCollection
    from sector_wind.brain import estimate as ES
    assert ES.build_estimated_table(GeometryCollection()) is None
    assert ES.build_estimated_table(Point(0, 0).buffer(0.0001)) is None        # ~11 m pond: fewer than 20 shoreline cells at 20 m


# ── tonight block ───────────────────────────────────────────────────────────────────────────
def test_weak_wind_direction_is_withheld():
    t = tonight([3.0] * 7)
    assert t["available"] and t["direction"]["shown"] is False and t["direction"]["fromDeg"] is None
    assert t["direction"]["reason"] == "windTooLightForDirection"
    assert t["confidence"]["label"] in ("LOW", "MEDIUM")
    t5 = tonight([6.0] * 7, p90=[8.0] * 7)
    assert t5["direction"]["shown"] and t5["direction"]["fromCardinal"] == "SW" and t5["direction"]["fromDeg"] == 225


def test_no_unsupported_trend_or_lay_down_claim():
    rising = tonight([4, 5, 6, 8, 10, 11, 12])
    assert rising["trend"]["label"] is None and "not claimed" in rising["trend"]["basis"]
    assert tonight([10, 9, 8, 7, 6, 5, 4])["trend"]["label"] == "easing"
    assert tonight([8, 8, 8, 8, 8, 8, 8])["trend"]["label"] == "steady"
    s = json.dumps(tonight([10, 9, 8, 7, 6, 5, 3])).lower()
    for banned in ("lays down", "lay down will", "calm by", "will lay"):
        assert banned not in s
    assert "layDown" in tonight([5] * 7)["withheld"] and "rising" in tonight([5] * 7)["withheld"]
    assert tonight([5] * 7)["withheld"]["overWaterSpeed"] and "gust" in tonight([5] * 7)["withheld"]
    assert all(h.get("gustMph") is None for h in hrs(W0, [5] * 3))              # no gust claim is generated by the block itself


def test_breezy_risk_flag_from_p90():
    on = tonight([6.0] * 7, p90=[7, 8, 9, 10.5, 9, 8, 7])
    assert on["breezyRisk"]["flag"] is True and on["breezyRisk"]["meaning"] == "could turn breezy"
    assert on["confidence"]["label"] == "MEDIUM" and "breezyRisk" in on["confidence"]["reasons"]
    assert on["speed"]["ifItBlowsCategory"] == "breezy" and on["speed"]["category"] == "light"
    off = tonight([6.0] * 7, p90=[7.0] * 7)
    assert off["breezyRisk"]["flag"] is False and off["breezyRisk"]["meaning"] is None and off["confidence"]["label"] == "HIGH"
    unk = tonight([6.0] * 7, p90=None)
    assert unk["breezyRisk"]["flag"] is None and unk["breezyRisk"]["unavailableReason"] == "noRecentPercentileCycle"
    assert unk["confidence"]["label"] == "MEDIUM"                                  # unknown risk cannot be HIGH


def test_forecast_stays_distinct_from_observed():
    t = tonight([6.0] * 7)
    assert t["kind"] == "forecast" and "not an over-water observation" in t["basis"]
    assert t["current"]["kind"] in ("analysis", "forecast")
    assert "observation" not in {k for k in t if k not in ("basis",)}


def test_freshness_and_stale_forecast():
    old = tonight([6.0] * 7, init=INIT - timedelta(hours=6))
    assert old["freshness"]["stale"] is True and old["confidence"]["label"] == "LOW"
    assert old["freshness"]["forecastAgeHours"] == 7.33
    fresh = tonight([6.0] * 7)
    assert fresh["freshness"]["stale"] is False and fresh["freshness"]["forecastInit"] == C.iso(INIT)


def test_unknown_when_forecast_does_not_cover_tonight_or_no_timezone():
    steps = hrs(NOW.replace(minute=0), [5.0] * 4)                                  # only the afternoon
    u = TN.build_tonight(steps, None, INIT, None, NOW, "America/Chicago")
    assert u["available"] is False and u["unavailableReason"] == "forecastDoesNotCoverTonight" and u["speed"] is None and u["direction"] is None
    z = TN.build_tonight(steps, None, INIT, None, NOW, None)
    assert z["available"] is False and z["unavailableReason"] == "timeZoneUnknown"
    n = TN.build_tonight([], None, None, None, NOW, "America/Chicago")
    assert n["available"] is False and n["freshness"]["stale"] is True and n["confidence"]["label"] == "LOW"


def test_window_and_timezones():
    s, e = TN.tonight_window(NOW, "America/Chicago")
    assert (C.iso(s), C.iso(e)) == ("2026-10-13T00:00:00Z", "2026-10-13T06:00:00Z")
    s2, _ = TN.tonight_window(datetime(2026, 10, 13, 5, 30, tzinfo=UTC), "America/Chicago")   # 00:30 local: still last evening's window
    assert C.iso(s2) == "2026-10-13T00:00:00Z"
    s3, _ = TN.tonight_window(datetime(2026, 12, 12, 18, 0, tzinfo=UTC), "America/Chicago")  # CST
    assert C.iso(s3) == "2026-12-13T01:00:00Z"
    assert TN.tz_for("AL", -86.2) == "America/Chicago" and TN.tz_for("TN", -88.2) == "America/Chicago" and TN.tz_for("TN", -84.0) == "America/New_York"
    assert TN.tz_for("TX", -106.0) == "America/Denver" and TN.tz_for("ZZ", 0) is None and TN.tz_for(None, 0) is None


def test_categories_and_confidence_rule():
    assert [TN.category(x) for x in (0, 4.9, 5, 9.9, 10, 14.9, 15, 30)] == ["calm", "calm", "light", "light", "breezy", "breezy", "windy", "windy"]
    assert TN.category(None) is None
    assert TN.confidence(6, False, False)[0] == "HIGH" and TN.confidence(4, False, False)[0] == "MEDIUM"
    assert TN.confidence(2, False, False)[0] == "LOW" and TN.confidence(None, None, False)[0] == "LOW" and TN.confidence(8, False, True)[0] == "LOW"
    assert TN.breezy_flag(9.99) is False and TN.breezy_flag(10.0) is True and TN.breezy_flag(None) is None


def test_direction_is_circular_not_arithmetic():
    t = tonight([8.0] * 7, dirs=[350, 10, 350, 10, 350, 10, 350])
    assert t["direction"]["fromCardinal"] == "N" and t["direction"]["maxSpreadDeg"] <= 15


# ── state integration ────────────────────────────────────────────────────────────────────────
def test_state_contains_tonight_and_stays_additive(tmp_path, monkeypatch):
    from tests import test_brain as TB
    from sector_wind.brain.state import build_state
    now = datetime(2026, 10, 12, 18, 20, tzinfo=UTC)
    monkeypatch.setattr(TB, "NOW", now)
    st = TB.make_store(tmp_path, speed=6.0, direction=225.0)
    d = next(x for x in TB.DIRECTORY if x["id"] == "Guntersville|AL")
    state, rows, meta = build_state(st, TB.CFG, "guntersville", "Guntersville|AL", d, now)
    t = state["tonight"]
    assert t["schema"] == TN.SCHEMA and t["kind"] == "forecast" and t["window"]["timeZone"] == "America/Chicago"
    assert state["stateSchema"] == C.STATE_SCHEMA and "trend" in state and "hourly" in state          # existing fields untouched
    assert t["breezyRisk"]["flag"] is None                                                           # synthetic cycle has no percentiles -> unknown, not False
    assert t["trend"]["label"] is None                                                               # synthetic forecast rises 0.5 mph/h: increase not claimed
    assert state["provenance"]["readiness"] in ("CALIBRATION", "DEGRADED")                           # lifecycle untouched
    assert rows is None and "fetchTablesUnavailable" in state["provenance"]["qualityFlags"]           # no fetch table -> no bank labels, no invention


# ── fleet tiers ─────────────────────────────────────────────────────────────────────────────
def test_tier_decisions():
    assert FL.decide_tier(True, True, True, "LOW", 1, 99) == ("AUDITED", "frozenFetchTable")
    assert FL.decide_tier(False, True, True, "HIGH", 300, 20.0) == ("ESTIMATED", "polygonFetch")
    assert FL.decide_tier(False, True, True, "MEDIUM", 300, 40.0)[0] == "ESTIMATED"
    assert FL.decide_tier(False, False, None, "HIGH", None, None) == ("POINT_ONLY", "noPolygon")
    assert FL.decide_tier(False, True, True, "LOW", 300, 20.0) == ("POINT_ONLY", "geometryConfidence:LOW")
    assert FL.decide_tier(False, True, True, None, 300, 20.0)[1] == "geometryConfidence:MISSING"
    assert FL.decide_tier(False, True, False, "HIGH", None, None) == ("POINT_ONLY", "polygonFetchFailed")
    assert FL.decide_tier(False, True, True, "HIGH", 10, 20.0) == ("POINT_ONLY", "tooFewBanks")
    assert FL.decide_tier(False, True, True, "HIGH", 300, 85.0) == ("POINT_ONLY", "coarseRaster")


def test_committed_manifest_matches_research_counts_and_never_promotes_unknown():
    m = FL.load_manifest()
    assert m["directoryLakes"] == 621 and sum(m["counts"].values()) == 621
    assert m["counts"] == {"AUDITED": 74, "ESTIMATED": 471, "POINT_ONLY": 76}
    assert FL.tier_for("Guntersville|AL", m)["tier"] == "AUDITED"
    assert FL.tier_for("Lake Michigan|WI", m)["tier"] == "POINT_ONLY" and FL.tier_for("Lake Michigan|WI", m)["reason"] == "noPolygon"
    assert FL.tier_for("Not A Lake|ZZ", m)["tier"] == "POINT_ONLY"
    assert all(v["tier"] != "ESTIMATED" or v["geometryConfidence"] in ("HIGH", "MEDIUM") for v in m["lakes"].values())    # LOW/MISSING geometry never ESTIMATED
    assert {v["forecastDomain"] for v in m["lakes"].values()} == {"CONUS", "AK", "HI"}


def test_fleet_sampling_matches_per_lake_interpolation():
    import numpy as np
    from sector_wind.interp import CutoutIndex, blend, blend_wind
    nx, ny = 40, 40
    lat = np.array([30 + r * 0.025 for r in range(ny) for c in range(nx)]); lon = np.array([-90 + c * 0.03 for r in range(ny) for c in range(nx)])
    rng = np.random.default_rng(1)
    speed = rng.uniform(1, 9, nx * ny); dirf = rng.uniform(0, 360, nx * ny); p90 = speed + 2
    pts = {"A|XX": (30.31, -89.62), "B|XX": (30.7, -89.2)}
    idx = FSM.build_point_index(lat, lon, nx, pts)
    out = FSM.sample_lead(idx, speed, dirf, None, p90)
    for lid, (la, lo) in pts.items():
        e = idx["lakes"][lid]
        ci = CutoutIndex(list(range(nx * ny)), lat.tolist(), lon.tolist(), nx); wt = ci.weights(la, lo)
        s, d = blend_wind(speed.tolist(), dirf.tolist(), wt)
        assert abs(out[lid]["speedMS"] - s) < 0.02 and e["method"] == "bilinear"
        assert min(abs(out[lid]["dirFromDeg"] - d), 360 - abs(out[lid]["dirFromDeg"] - d)) <= 1
        assert abs(out[lid]["speedP90"] - blend(p90.tolist(), wt)) < 0.02
    assert FSM.build_point_index(lat, lon, nx, pts) == idx                    # deterministic
    cm = FSM.cost_model(); assert cm["fleetObjectsPerDay"] == 24 and cm["perLakeCutoutObjectsPerDay"] == 14904 and cm["extraNetworkCalls"] == 0


# ── H2 pre-registration immutability and gating ──────────────────────────────────────────────
def test_h2_prereg_immutable():
    assert H2.prereg_ok(), "WIND_H2_PREREG.md changed after it was frozen: write WIND_H2_PREREG_v2.md instead of editing"
    fz = json.load(open(os.path.join(H2.PREREG, "WIND_H2_PREREG.freeze.json")))
    assert fz["sealedUntil"] == C.iso(C.H2_SEALED_UNTIL)


def test_h2_runner_refuses_before_release_and_after_first_run(tmp_path):
    with pytest.raises(H2.Sealed, match="sealed until"):
        H2.gate(datetime(2026, 12, 31, 23, 59, tzinfo=UTC), str(tmp_path / "l.json"))
    led = tmp_path / "l.json"; led.write_text("{}")
    with pytest.raises(H2.Sealed, match="already run"):
        H2.gate(datetime(2027, 1, 2, tzinfo=UTC), str(led))
    H2.gate(datetime(2027, 1, 2, tzinfo=UTC), str(tmp_path / "fresh.json"))      # open and unused: allowed


def test_h2_prereg_tamper_is_detected(tmp_path):
    import shutil
    for f in ("WIND_H2_PREREG.md", "WIND_H2_PREREG.freeze.json"):
        shutil.copy(os.path.join(H2.PREREG, f), tmp_path / f)
    (tmp_path / "WIND_H2_PREREG.md").write_text((tmp_path / "WIND_H2_PREREG.md").read_text() + "\nlooser threshold\n")
    assert not H2.prereg_ok(str(tmp_path))
    with pytest.raises(H2.Sealed, match="freeze hash"):
        H2.gate(datetime(2027, 6, 1, tzinfo=UTC), None, str(tmp_path))


def test_h2_scoring_reports_insufficient_not_pass():
    r = H2.score_rows([], [])
    assert all(v["verdict"] in ("INSUFFICIENT", "REPORTED") for v in r.values())
    assert r["H2-T2"]["verdict"] == "INSUFFICIENT"                                 # never a lay-down claim without data


def test_h2_scoring_applies_frozen_thresholds():
    rows = []
    for i in range(3000):          # perfect direction, calm-dominated speeds, breezy nights flagged
        windy = i % 25 == 0
        rows.append({"fcMph": 6.0 if i % 3 == 0 else 3.0, "p90Mph": 11.0 if windy else 6.0, "obsMph": 11.0 if windy else (6.0 if i % 3 == 0 else 3.0),
                     "fcDir": 225, "obsDir": 225 + (i % 5), "night": True, "lead": 6})
    r = H2.score_rows(rows, [])
    assert r["H2-D1"]["verdict"] == "PASS" and r["H2-D1"]["within22_5"] == 1.0
    assert r["H2-B1"]["verdict"] in ("PASS", "INSUFFICIENT")
    bad = [dict(x, obsDir=(x["fcDir"] + 120) % 360) for x in rows]
    assert H2.score_rows(bad, [])["H2-D1"]["verdict"] == "FAIL"


# ── field validation schema ──────────────────────────────────────────────────────────────────
def obs(**kw):
    r = {"schema": FS.SCHEMA, "id": "o1", "lakeId": "Guntersville|AL", "bankId": "GT-000123", "observedAtUtc": "2026-10-10T01:30:00Z", "observer": "mc",
         "roughnessObserved": "choppy", "bankImpactObserved": "DIRECT", "boatability": "noticeable", "observerConfidence": 3, "observerSawPrediction": False,
         "wind": {"source": "handheld", "speedMph": 9.0, "gustMph": 13.0, "directionFromDeg": 225, "deviceId": "kestrel-1", "heightM": 2.0, "averagingSec": 60}}
    r.update(kw); return r


def test_field_observation_validation():
    now = datetime(2026, 10, 15, tzinfo=UTC)
    assert FS.validate_observation(obs(), now) == []
    assert any("prediction" in w for w in FS.validate_observation(obs(prediction={"label": "DIRECT"}), now))
    w = obs()["wind"]; w.pop("heightM")
    assert any("height" in x for x in FS.validate_observation(obs(wind=w), now))
    assert any("gust" in x for x in FS.validate_observation(obs(wind={"source": "visualEstimate", "gustMph": 20}), now))
    assert any("bankId or zoneId" in x for x in FS.validate_observation(obs(bankId=None), now))
    assert any("blinding" in x for x in FS.validate_observation(obs(observerSawPrediction=None), now))
    assert FS.validate_observation(obs(wind={"source": "visualEstimate", "directionFromDeg": 225}), now) == []
    assert any("FROM" in x for x in FS.validate_observation(obs(wind={"source": "visualEstimate", "directionFromDeg": 400}), now))


def test_field_pair_rules_and_concordance():
    a = obs(id="a", pairId="P1", pairRole="A"); b = obs(id="b", bankId="GT-000999", pairId="P1", pairRole="B", observedAtUtc="2026-10-10T01:50:00Z")
    assert FS.validate_pair(a, b) == []
    assert any("apart" in x for x in FS.validate_pair(a, obs(id="b", bankId="GT-9", pairId="P1", pairRole="B", observedAtUtc="2026-10-10T03:30:00Z")))
    assert any("different lakes" in x for x in FS.validate_pair(a, dict(b, lakeId="Wheeler|AL")))
    assert any("same bank" in x for x in FS.validate_pair(a, dict(b, bankId=a["bankId"])))
    c = FS.pair_concordance([
        {"predictedLabelA": "DIRECT", "predictedLabelB": "PROTECTED", "predictedHm0A": 8, "predictedHm0B": 1, "obsA": 3, "obsB": 1},
        {"predictedLabelA": "DIRECT", "predictedLabelB": "PROTECTED", "predictedHm0A": 8, "predictedHm0B": 1, "obsA": 1, "obsB": 3},
        {"predictedLabelA": "CROSS", "predictedLabelB": "CROSS", "predictedHm0A": 4.0, "predictedHm0B": 3.9, "obsA": 2, "obsB": 2},   # tie: excluded
        {"predictedLabelA": "UNKNOWN", "predictedLabelB": "DIRECT", "predictedHm0A": 0, "predictedHm0B": 5, "obsA": 1, "obsB": 3}])    # unknown: excluded
    assert c == {"n": 2, "predictionTies": 2, "concordance": 0.5}


def test_state_with_estimated_geometry_labels_banks_and_marks_estimate(tmp_path, monkeypatch):
    pytest.importorskip("shapely"); pytest.importorskip("PIL"); pytest.importorskip("scipy")
    from shapely.geometry import box
    from tests import test_brain as TB
    from sector_wind.brain import estimate as ES
    from sector_wind.brain.state import build_state
    now = datetime(2026, 10, 12, 18, 20, tzinfo=UTC)
    monkeypatch.setattr(TB, "NOW", now)
    st = TB.make_store(tmp_path, speed=7.0, direction=225.0)
    d = next(x for x in TB.DIRECTORY if x["id"] == "Guntersville|AL")
    lat0, lon0 = d["lat"] - 0.03, d["lon"] - 0.04
    obj = ES.build_estimated_table(box(lon0, lat0, lon0 + 0.08, lat0 + 0.06), "Guntersville|AL")
    state, rows, _ = build_state(st, TB.CFG, "guntersville", "Guntersville|AL", d, now, obj, geometry_tier="ESTIMATED")
    ex = state["exposure"]
    assert ex["geometryTier"] == "ESTIMATED" and ex["estimated"] is True and ex["validated"] is False
    assert ex["bankImpact"]["directPct"] > 0 and ex["bankImpact"]["protectedPct"] > 0
    assert {r["bankImpact"] for r in rows} <= set(EX.LABELS) and all(r["geometryTier"] == "ESTIMATED" for r in rows)
    assert state["surfaceState"]["validated"] is False and "surfaceModelNotFieldValidated" in state["provenance"]["qualityFlags"]
    tn = state["tonight"]
    assert tn["available"] and tn["exposure"]["estimated"] is True and tn["exposure"]["atMean"]["knownBanks"] > 0
    assert tn["exposure"]["ifItBlows"] is None or tn["exposure"]["ifItBlows"]["speedMph"] >= tn["exposure"]["atMean"]["speedMph"]


def test_fleet_sampler_follows_the_archive_calm_rule():
    import numpy as np
    nx = 6
    lat = np.array([30 + r * 0.025 for r in range(6) for c in range(nx)]); lon = np.array([-90 + c * 0.03 for r in range(6) for c in range(nx)])
    speed = np.full(36, 4.0); dirf = np.full(36, 270.0)
    idx = FSM.build_point_index(lat, lon, nx, {"A|XX": (30.06, -89.94)})
    assert FSM.sample_lead(idx, speed, dirf)["A|XX"]["dirFromDeg"] == 270
    calm = np.full(36, 0.3)                                                   # every cell calm: archive stores no direction
    out = FSM.sample_lead(idx, calm, dirf)["A|XX"]
    assert out["dirFromDeg"] is None and out["speedMS"] == 0.3
    nan = np.full(36, np.nan)
    assert FSM.sample_lead(idx, nan, nan)["A|XX"]["speedMS"] is None              # unknown stays unknown


def test_estimated_tier_protected_needs_margin():
    # lee-facing, chop 2 now but 3 at 1.5x fetch -> ESTIMATED geometry may not call it PROTECTED
    assert EX.label_bank(0, 12, 180, 2)["label"] == "PROTECTED"
    e = EX.label_bank_estimated(0, 12, 180, 2, 3)
    assert e["label"] == "CROSS" and e["reason"] == "estimatedGeometryMargin"
    assert EX.label_bank_estimated(0, 12, 180, 1, 2)["label"] == "PROTECTED"          # robust to the margin
    assert EX.label_bank_estimated(0, 12, 180, 2, None)["label"] == "UNKNOWN"          # no margin evaluation -> never PROTECTED
    assert EX.label_bank_estimated(0, 12, None, 1, 1)["label"] == "UNKNOWN"
    assert EX.label_bank_estimated(0, 12, 0, 3, 4)["label"] == "DIRECT"               # exposure is never softened
    for fa in range(0, 360, 30):                                                     # never more protective than the audited rule
        for c, cm in ((1, 1), (1, 2), (2, 3), (3, 4), (4, 4)):
            a, b = EX.label_bank(90, 12, fa, c)["label"], EX.label_bank_estimated(90, 12, fa, c, cm)["label"]
            assert not (b == "PROTECTED" and a != "PROTECTED")


def test_state_tier_changes_label_policy(tmp_path, monkeypatch):
    # an AUDITED and an ESTIMATED run over the same geometry: ESTIMATED never has more PROTECTED banks
    pytest.importorskip("shapely"); pytest.importorskip("PIL"); pytest.importorskip("scipy")
    from shapely.geometry import box
    from tests import test_brain as TB
    from sector_wind.brain import estimate as ES
    from sector_wind.brain.state import build_state
    now = datetime(2026, 10, 12, 18, 20, tzinfo=UTC)
    monkeypatch.setattr(TB, "NOW", now)
    st = TB.make_store(tmp_path, speed=7.0, direction=225.0)
    d = next(x for x in TB.DIRECTORY if x["id"] == "Guntersville|AL")
    obj = ES.build_estimated_table(box(d["lon"] - 0.04, d["lat"] - 0.03, d["lon"] + 0.04, d["lat"] + 0.03), "Guntersville|AL")
    a, _, _ = build_state(st, TB.CFG, "guntersville", "Guntersville|AL", d, now, obj, geometry_tier="AUDITED")
    e, _, _ = build_state(st, TB.CFG, "guntersville", "Guntersville|AL", d, now, obj, geometry_tier="ESTIMATED")
    assert e["exposure"]["bankImpact"]["protectedPct"] <= a["exposure"]["bankImpact"]["protectedPct"]


def test_hard_blockers_withhold_exposure_even_for_audited_lakes():
    m = FL.load_manifest()
    assert m["exposureAllowedCount"] == sum(FL.exposure_allowed(v) for v in m["lakes"].values()) == 528
    for lid in ("Andrews Lake|DE", "Eagle Lake|MS", "Hiwassee Lake|NC", "Long Lake|ME"):      # audited table exists but Lake Brain flags a lake-identity risk
        e = m["lakes"][lid]
        assert e["tier"] == "AUDITED" and "lakeIdentityRisk" in e["blockers"] and not FL.exposure_allowed(e)
    assert not FL.exposure_allowed(m["lakes"]["Aleknagik|AK"])                                  # forecast domain untested
    assert FL.exposure_allowed(m["lakes"]["Guntersville|AL"]) and FL.exposure_allowed(m["lakes"]["Lake Hartwell|SC"])
    assert not FL.exposure_allowed(FL.tier_for("Not A Lake|ZZ", m))                              # unknown lake: never
    assert not any(FL.exposure_allowed(v) for v in m["lakes"].values() if v["tier"] == "POINT_ONLY")


def test_evidence_and_horizon_fields_for_consumers():
    t = tonight([6.0] * 7, p90=[7.0] * 7)
    assert t["evidence"]["kind"] == "MODELED_FORECAST" and t["evidence"]["validationTier"] == "HISTORICAL_LAND_STATIONS_ONLY"
    assert t["forecastHorizonHours"] == 11.7                                      # now 18:20Z -> window end 06:00Z
    assert TN.build_tonight([], None, None, None, NOW, "America/Chicago")["evidence"]["kind"] == "MODELED_FORECAST"


def test_published_intelligence_fixtures_match_the_code():
    """docs/brains/wind/fixtures are the examples Intelligence builds its tests on: regenerate them if this fails (and bump the schema if the shape changed)."""
    fx = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "docs", "brains", "wind", "fixtures")
    t = tonight([9, 9, 8, 7, 6, 5, 4], p90=[11, 10.5, 10, 9, 8, 7, 6])
    t["current"] = {"kind": "analysis", "sustainedMph": 6.0, "gustMph": None, "directionDeg": 225, "note": "analysis/forecast value, not an observation"}
    got = json.load(open(os.path.join(fx, "tonight_light_breezy_risk_easing.json")))
    assert got == json.loads(json.dumps(t, sort_keys=True))
