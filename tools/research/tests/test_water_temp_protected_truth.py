"""PT-L4-2026-11-23 runner, offline. Every fixture is hand-built and synthetic (no real station, cast or temperature)."""
import csv
import datetime as dt
import json
import os
import shutil
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import water_temp_protected_truth as W  # noqa: E402

P, DIGEST = W.load_protocol()
LAKES = [l["lakeId"] for l in P["lakes"]]
REQ = "Owner request (Michael, 2099-01-01): synthetic test"
# synthetic main-stem stations, one per lake, placed inside each box with a river mile in the main body
MAIN = {"Guntersville|AL": ("SYN-G", "SYNTHETIC Tennessee River TRM 360.0", 34.45, -86.30),
        "Wheeler|AL": ("SYN-WH", "SYNTHETIC Tennessee River TRM 280.0", 34.70, -87.20),
        "Wilson|AL": ("SYN-WI", "SYNTHETIC Tennessee River TRM 262.0", 34.80, -87.55),
        "Pickwick Lake|TN": ("SYN-P", "SYNTHETIC Tennessee River TRM 230.0", 35.00, -88.10)}


def test_protocol_hash_is_the_committed_preregistration():
    assert DIGEST == open(W.PROTOCOL + ".sha256").read().split()[0]
    assert P["protocolId"] == "PT-L4-2026-11-23" and P["publication"]["authoritativeScoresUnchanged"] is True
    assert W.per_lake_min(P) == 25 and W.total_min(P) == 150


def test_edited_protocol_is_refused(tmp_path):
    q = tmp_path / "p.json"
    shutil.copy(W.PROTOCOL, q)
    shutil.copy(W.PROTOCOL + ".sha256", str(q) + ".sha256")
    W.load_protocol(str(q))
    q.write_text(q.read_text().replace('"value": 2.5', '"value": 9.9'))
    with pytest.raises(SystemExit, match="REFUSED: protocol sha256"):
        W.load_protocol(str(q))


@pytest.mark.parametrize("name,lat,lon,cls,lake", [
    ("SYNTHETIC Tennessee River TRM 300.0", 34.65, -87.0, "MAIN_BODY", "Wheeler|AL"),
    ("SYNTHETIC Wheeler Reservoir forebay", 34.80, -87.10, "MAIN_BODY", "Wheeler|AL"),
    ("SYNTHETIC Second Creek embayment", 34.80, -87.10, "EMBAYMENT", "Wheeler|AL"),
    ("SYNTHETIC Elk River mile 6", 34.80, -87.10, "EMBAYMENT", "Wheeler|AL"),
    ("SYNTHETIC Tennessee River TRM 273.5", 34.80, -87.45, "TAILWATER", "Wilson|AL"),     # within 2 mi below Wheeler Dam
    ("SYNTHETIC Tennessee River TRM 250.0", 34.80, -87.70, "MAIN_BODY", "Pickwick Lake|TN"),
    ("SYNTHETIC Tennessee River below Wilson Dam", 34.79, -87.62, "TAILWATER", None),       # inside two boxes but tailwater keyword
    ("SYNTHETIC station", 34.79, -87.625, "AMBIGUOUS", None),
    ("SYNTHETIC station", 34.65, -87.0, "UNCLASSIFIED", "Wheeler|AL"),
    ("SYNTHETIC station", 40.0, -90.0, "OUTSIDE", None),
])
def test_station_classes(name, lat, lon, cls, lake):
    got, lid, why = W.classify_station(P, name, lat, lon)
    assert got == cls, why
    if lake:
        assert lid == lake


def _stations_file(path, extra=()):
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=W.STATION_FIELDS)
        w.writeheader()
        for lid, (sid, name, lat, lon) in MAIN.items():
            w.writerow({"MonitoringLocationIdentifier": sid, "OrganizationIdentifier": "SYN", "MonitoringLocationName": name,
                        "LatitudeMeasure": lat, "LongitudeMeasure": lon, "lakeId": lid, "class": "MAIN_BODY", "reason": "t", "reviewNote": ""})
        for row in extra:
            w.writerow(row)
    return str(path)


def _dates(n, start="2022-04-01"):
    d0 = dt.date.fromisoformat(start)
    return [(d0 + dt.timedelta(days=7 * i)).isoformat() for i in range(n)]


def _activities(counts):
    rows = []
    for lid, n in counts.items():
        sid = MAIN[lid][0]
        for d in _dates(n):
            for dep in (0.3, 0.9, 5.0):      # a profile: three depth activities, one cast
                rows.append({"MonitoringLocationIdentifier": sid, "ActivityStartDate": d,
                             "ActivityDepthHeightMeasure/MeasureValue": str(dep), "ActivityDepthHeightMeasure/MeasureUnitCode": "m"})
    return rows


def test_census_counts_casts_not_depths_and_applies_the_gate(tmp_path):
    st = W.load_stations(_stations_file(tmp_path / "s.csv"))
    res = W.census_from_activities(P, _activities({"Guntersville|AL": 40, "Wheeler|AL": 30, "Wilson|AL": 24, "Pickwick Lake|TN": 60}), st, "2026-11-22")
    assert res["lakes"]["Wilson|AL"] == {"qualifyingCasts": 24, "depthOnlyOnResults": 0, "needed": 25, "sufficient": False}
    assert res["lakes"]["Wheeler|AL"]["qualifyingCasts"] == 30
    assert res["outcome"] == "INSUFFICIENT_TRUTH"
    res = W.census_from_activities(P, _activities({"Guntersville|AL": 40, "Wheeler|AL": 30, "Wilson|AL": 25, "Pickwick Lake|TN": 55}), st, "2026-11-22")
    assert res["total"] == 150 and res["outcome"] == "SUFFICIENT_FOR_STEP_B"
    res = W.census_from_activities(P, _activities({"Guntersville|AL": 40, "Wheeler|AL": 30, "Wilson|AL": 25, "Pickwick Lake|TN": 54}), st, "2026-11-22")
    assert res["outcome"] == "INSUFFICIENT_TRUTH"          # every lake >= 25 but total 149 < 150


def test_census_excludes_window_deep_embayment_missing_depth_and_duplicates(tmp_path):
    emb = {"MonitoringLocationIdentifier": "SYN-EMB", "OrganizationIdentifier": "SYN", "MonitoringLocationName": "SYNTHETIC creek",
           "LatitudeMeasure": 34.7, "LongitudeMeasure": -87.2, "lakeId": "Wheeler|AL", "class": "EMBAYMENT", "reason": "t", "reviewNote": ""}
    twin = {"MonitoringLocationIdentifier": "SYN-WH-OTHERORG", "OrganizationIdentifier": "SYN2", "MonitoringLocationName": "SYNTHETIC same spot",
            "LatitudeMeasure": 34.701, "LongitudeMeasure": -87.201, "lakeId": "Wheeler|AL", "class": "MAIN_BODY", "reason": "t", "reviewNote": ""}
    st = W.load_stations(_stations_file(tmp_path / "s.csv", [emb, twin]))
    a = lambda sid, d, dep, unit="m": {"MonitoringLocationIdentifier": sid, "ActivityStartDate": d,
                                        "ActivityDepthHeightMeasure/MeasureValue": dep, "ActivityDepthHeightMeasure/MeasureUnitCode": unit}
    acts = [a("SYN-WH", "2020-12-31", "0.5"),                 # before the window
            a("SYN-WH", "2026-11-23", "0.5"),                 # after the cutoff
            a("SYN-WH", "2023-05-01", "3.0"),                 # deepest-only cast: not a surface reading
            a("SYN-WH", "2023-05-08", ""),                    # depth only on results: reported, not counted
            a("SYN-EMB", "2023-05-15", "0.5"),                # embayment
            a("SYN-WH", "2023-05-22", "4.0", "ft"),           # 1.22 m: qualifies via the 1.5 m fallback
            a("SYN-WH", "2023-05-29", "0.5"), a("SYN-WH", "2023-05-29", "1.0"),
            a("SYN-WH-OTHERORG", "2023-05-29", "0.5")]        # same cast reported by a second organisation
    res = W.census_from_activities(P, acts, st, "2026-11-22")
    assert res["lakes"]["Wheeler|AL"]["qualifyingCasts"] == 2
    assert res["lakes"]["Wheeler|AL"]["depthOnlyOnResults"] == 1
    assert res["excluded"] == {"notMainBody": 1, "outsideWindow": 2, "tooDeep": 1}
    assert "Wheeler|AL|SYN-WH|2023-05-29" in res["castKeys"] and "Wheeler|AL|SYN-WH-OTHERORG|2023-05-29" not in res["castKeys"]


def _census(tmp_path, counts):
    sp = _stations_file(tmp_path / "s.csv")
    md = tmp_path / "md"
    md.mkdir()
    for lid in LAKES:
        rows = [r for r in _activities(counts) if r["MonitoringLocationIdentifier"] == MAIN[lid][0]]
        with open(md / f"{W.lake_slug(lid)}.activity.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    out = tmp_path / "census.json"
    rec = W.cmd_census(P, DIGEST, str(md), sp, "2026-11-22", str(out))
    assert rec["valuesOpened"] is False and "INTERNAL_EXPERIMENTAL" in rec["labels"]
    return rec, sp, str(out)


SUFFICIENT = {"Guntersville|AL": 40, "Wheeler|AL": 30, "Wilson|AL": 25, "Pickwick Lake|TN": 55}


def test_step_b_is_refused_without_owner_request_insufficiency_or_with_changed_stations(tmp_path):
    rec, sp, _ = _census(tmp_path, SUFFICIENT)
    with pytest.raises(SystemExit, match="needs --owner-request"):
        W.require_step_b(rec, DIGEST, sp, None)
    with pytest.raises(SystemExit, match="needs --owner-request"):
        W.require_step_b(rec, DIGEST, sp, "Claude request (under Owner approval 2026-11-22)")
    W.require_step_b(rec, DIGEST, sp, REQ)
    with pytest.raises(SystemExit, match="different protocol hash"):
        W.require_step_b(rec, "0" * 64, sp, REQ)
    with pytest.raises(SystemExit, match="not SUFFICIENT"):
        W.require_step_b({**rec, "outcome": "INSUFFICIENT_TRUTH"}, DIGEST, sp, REQ)
    with open(sp, "a") as fh:
        fh.write("SYN-X,SYN,SYNTHETIC,34.7,-87.0,Wheeler|AL,MAIN_BODY,late change,\n")
    with pytest.raises(SystemExit, match="station file changed"):
        W.require_step_b(rec, DIGEST, sp, REQ)


def test_surface_value_rules():
    k = ("Wheeler|AL", "S", "2023-06-01")
    r = lambda v, dep, unit="deg C", status="Accepted", ch=W.CHARACTERISTIC, dunit="m": {
        "MonitoringLocationIdentifier": "S", "ActivityStartDate": "2023-06-01", "CharacteristicName": ch, "ResultStatusIdentifier": status,
        "ResultMeasureValue": v, "ResultMeasure/MeasureUnitCode": unit, "ResultDepthHeightMeasure/MeasureValue": dep,
        "ResultDepthHeightMeasure/MeasureUnitCode": dunit}
    assert W.surface_values([r("20", "0.2"), r("22", "1.0"), r("10", "6")], {k}) == {k: 21.0}
    assert W.surface_values([r("68", "1.3", "deg F"), r("19", "1.4"), r("10", "6")], {k}) == {k: 20.0}   # shallowest <= 1.5 m
    assert W.surface_values([r("10", "6")], {k}) == {}
    assert W.surface_values([r("99", "0.5"), r("20", "0.5", status="Rejected"), r("7.0", "0.5", ch="pH")], {k}) == {}
    assert W.surface_values([r("20", "0.5")], {("Wheeler|AL", "S", "2023-06-02")}) == {}     # not a counted cast


def _forcing(start, end, air_c):
    """Synthetic forcing with Teq == air (sw 0, wind 5, rh 0), so production M0 equals the air temperature exactly."""
    d0, d1 = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
    days = [(d0 + dt.timedelta(days=i)).isoformat() for i in range((d1 - d0).days + 1)]
    n = len(days)
    return {"daily": {"time": days, "temperature_2m_mean": [air_c] * n, "shortwave_radiation_sum": [0.0] * n,
                      "wind_speed_10m_mean": [5.0] * n, "relative_humidity_2m_mean": [0.0] * n}}


def _results(counts, truth_c):
    rows = []
    for lid, n in counts.items():
        for d in _dates(n):
            for dep, v in ((0.3, truth_c[lid]), (0.9, truth_c[lid]), (5.0, 5.0)):
                rows.append({"MonitoringLocationIdentifier": MAIN[lid][0], "ActivityStartDate": d, "CharacteristicName": W.CHARACTERISTIC,
                             "ResultStatusIdentifier": "Accepted", "ResultMeasureValue": str(v), "ResultMeasure/MeasureUnitCode": "deg C",
                             "ResultDepthHeightMeasure/MeasureValue": str(dep), "ResultDepthHeightMeasure/MeasureUnitCode": "m"})
    return rows


def test_compare_pass_and_fail_against_the_preregistered_mark(tmp_path):
    rec, _, _ = _census(tmp_path, SUFFICIENT)
    forcing = {lid: _forcing("2022-01-01", "2023-12-31", 20.0) for lid in LAKES}
    good = W.compare(P, rec, _results(SUFFICIENT, {lid: 21.0 for lid in LAKES}), forcing)      # M0 20 vs truth 21: error -1 C
    assert good["outcome"] == "PASS" and good["pooledEqualLakeRmseC"] == 1.0
    assert good["perLake"]["Wilson|AL"]["n"] == 25 and good["perLake"]["Wilson|AL"]["biasC"] == -1.0
    assert good["authoritativeScoresUnchanged"] is True and good["valuesOpened"] is True and len(good["m0ImplementationSha256"]) == 64
    bad = W.compare(P, rec, _results(SUFFICIENT, {**{lid: 21.0 for lid in LAKES}, "Wilson|AL": 23.0}), forcing)   # Wilson RMSE 3.0
    assert bad["outcome"] == "FAIL" and bad["perLakePass"]["Wilson|AL"] is False
    assert bad["pooledEqualLakeRmseC"] == pytest.approx(((1 + 1 + 9 + 1) / 4) ** 0.5, abs=1e-4)   # pooled 1.73 passes; the lake bar fails it


def test_missing_forcing_gives_insufficient_paired_not_fail(tmp_path):
    rec, _, _ = _census(tmp_path, SUFFICIENT)
    forcing = {lid: _forcing("2022-01-01", "2023-12-31", 20.0) for lid in LAKES}
    forcing["Wilson|AL"] = _forcing("2022-01-01", "2022-06-30", 20.0)      # most Wilson casts lose their M0 value
    res = W.compare(P, rec, _results(SUFFICIENT, {lid: 21.0 for lid in LAKES}), forcing)
    assert res["outcome"] == "INSUFFICIENT_PAIRED" and res["perLake"]["Wilson|AL"]["unpaired"] > 0


def test_cli_verify_and_census_end_to_end(tmp_path, capsys):
    assert W.main(["verify"]) == 0
    assert json.loads(capsys.readouterr().out)["sha256"] == DIGEST
    md = tmp_path / "md"
    md.mkdir()
    with open(md / f"{W.lake_slug('Wheeler|AL')}.station.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["MonitoringLocationIdentifier", "OrganizationIdentifier", "MonitoringLocationName", "LatitudeMeasure", "LongitudeMeasure"])
        w.writeheader()
        w.writerow({"MonitoringLocationIdentifier": "SYN-1", "OrganizationIdentifier": "SYN", "MonitoringLocationName": "SYNTHETIC Tennessee River TRM 300",
                    "LatitudeMeasure": "34.65", "LongitudeMeasure": "-87.0"})
    assert W.main(["stations", "--metadata", str(md), "--out", str(tmp_path / "st.csv")]) == 0
    assert json.loads(capsys.readouterr().out)["byClass"] == {"MAIN_BODY": 1}
    assert W.main(["census", "--metadata", str(md), "--stations", str(tmp_path / "st.csv"), "--cutoff", "2026-11-22", "--out", str(tmp_path / "c.json")]) == 0
    assert json.loads(capsys.readouterr().out)["outcome"] == "INSUFFICIENT_TRUTH"
    with pytest.raises(SystemExit, match="needs --owner-request"):
        W.main(["fetch-results", "--census", str(tmp_path / "c.json"), "--stations", str(tmp_path / "st.csv"), "--out", str(tmp_path / "r")])


def test_fetch_refuses_hosts_outside_the_allowlist(tmp_path):
    with pytest.raises(SystemExit, match="not allowlisted"):
        W._get("https://example.com/data", {}, str(tmp_path / "x"), [])
