"""LGC-2026-11-23 lake gauge census, offline. The world fixture is synthetic (no real station, series, location or level)."""
import datetime as dt
import gzip
import json
import os
import re
import shutil
import sys
import urllib.parse

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
import lake_gauge_census as G  # noqa: E402

RULES, DIGEST = G.load_rules()
WORLD = json.load(open(os.path.join(HERE, "fixtures", "lake_gauge_census", "world.json")))
NOW = dt.datetime(2026, 12, 1, 12, 0, tzinfo=dt.timezone.utc)
SENTINEL = str(WORLD["ivValueSentinel"])


# ------------------------------------------------------------------------------------------------------ synthetic services
def _rdb(rows, catalog=True):
    head = ["agency_cd", "site_no", "station_nm", "site_tp_cd", "dec_lat_va", "dec_long_va", "alt_datum_cd"]
    if catalog:
        head += ["data_type_cd", "parm_cd", "begin_date", "end_date", "count_nu"]
    out = ["# synthetic", "\t".join(head), "\t".join("5s" for _ in head)]
    for r in rows:
        base = ["USGS", r["site"], r["name"], r["tp"], str(r["lat"]), str(r["lon"]), r["alt_datum"]]
        if catalog:
            for dtc in ("uv", "dv"):
                out.append("\t".join(base + [dtc, r["param"], "1990-01-01", r["end"], "100"]))
        else:
            out.append("\t".join(base))
    return "\n".join(out).encode()


class World:
    def __init__(self, robots=None):
        self.robots = robots or {}
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append(url)
        assert headers.get("User-Agent", "").startswith("Sector-LakeGaugeCensus")
        u = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/robots.txt":
            body = self.robots.get(u.hostname)
            return (200, body.encode()) if body is not None else (404, b"")
        if u.hostname == "waterservices.usgs.gov" and u.path == "/nwis/site/":
            if "bBox" in q:
                w, s, e, n = map(float, q["bBox"].split(","))
                rows = [r for r in WORLD["usgs"] if w <= r["lon"] <= e and s <= r["lat"] <= n and r["param"] in q["parameterCd"].split(",")]
                return (200, _rdb(rows)) if rows else (404, b"No sites found")
            sites = q["sites"].split(",")
            return 200, _rdb([r for r in WORLD["usgs"] if r["site"] in sites], catalog=False)
        if u.hostname == "waterservices.usgs.gov" and u.path == "/nwis/iv/":
            ts = []
            for site in q["sites"].split(","):
                for r in WORLD["usgs"]:
                    if r["site"] == site and r["param"] in q["parameterCd"].split(","):
                        vals = [{"value": SENTINEL, "qualifiers": ["P"], "dateTime": f"2026-12-01T{h:02d}:{m:02d}:00.000-00:00"}
                                for h in range(6, 12) for m in (0, 15, 30, 45)]
                        ts.append({"sourceInfo": {"siteCode": [{"value": site}]}, "variable": {"variableCode": [{"value": r["param"]}]},
                                   "values": [{"value": vals}]})
            return 200, json.dumps({"value": {"timeSeries": ts}}).encode()
        if u.hostname == "cwms-data.usace.army.mil":
            office = q["office"]
            if u.path.endswith("/LOCATIONS"):
                return 200, json.dumps({"entries": WORLD["cwmsLocations"].get(office, [])}).encode()
            rx = re.compile(q["like"])
            ents = [{"office": t["office"], "name": t["name"], "interval": t["interval"], "units": "ft",
                     "extents": [{"earliest-time": t["earliest"], "latest-time": t["latest"]}]}
                    for t in WORLD["cwmsTimeseries"] if t["office"] == office and rx.search(t["name"])]
            return 200, json.dumps({"entries": ents}).encode()
        if u.hostname == "data.usbr.gov":
            if u.path == "/rise/api/location":
                data = [{"id": l["id"], "type": "Location",
                         "attributes": {"locationName": l["locationName"], "verticalDatumName": l["verticalDatumName"],
                                        "locationCoordinates": {"type": "Point", "coordinates": [l["lon"], l["lat"]]}},
                         "relationships": {"catalogItems": {"data": [{"type": "CatalogItem", "id": i} for i in l["items"]]}}}
                        for l in WORLD["riseLocations"]] if q.get("page") == "1" else []
                return 200, json.dumps({"data": data, "links": {}}).encode()
            m = re.match(r"/rise/api/catalog-item/(\d+)", u.path)
            if m and m.group(1) in WORLD["riseItems"]:
                return 200, json.dumps({"data": {"id": int(m.group(1)), "type": "CatalogItem", "attributes": WORLD["riseItems"][m.group(1)]}}).encode()
            return 404, b""
        return 404, b""


def registry_dir(tmp_path):
    root = tmp_path / "registry"
    (root / "registry").mkdir(parents=True)
    idx = []
    for l in WORLD["lakes"]:
        idx.append({"lakeId": l["lakeId"], "geometry": {"x": 1} if l["outline"] else None})
        if l["outline"]:
            d = root / "lakes" / G.lake_key(l["lakeId"])
            d.mkdir(parents=True)
            feat = {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [l["outline"]]}}
            (d / "geometry.v1.analysis.geojson.gz").write_bytes(gzip.compress(json.dumps(feat).encode()))
    (root / "registry" / "lakes.v1.json").write_text(json.dumps({"lakes": idx}))
    return str(root)


def targets():
    return {"lakes": [{k: v for k, v in l.items() if k != "outline"} for l in WORLD["lakes"]], "inputs": {"synthetic": "x"}}


def fetcher(tmp_path, world):
    return G.Fetcher(RULES, out=str(tmp_path / "out"), transport=world, sleep=lambda s: None)


def run(tmp_path, world=None, skip_controls=True):
    world = world or World()
    f = fetcher(tmp_path, world)
    res = G.run_census(RULES, DIGEST, f, NOW, registry_dir(tmp_path), skip_controls=skip_controls, targets_table=targets())
    return res, f, world


def lake(res, lid):
    return next(l for l in res["lakes"] if l["lakeId"] == lid)


def cand(l, provider, series):
    return next(c for c in l["candidates"] if c["provider"] == provider and c["series"] == series)


# ------------------------------------------------------------------------------------------------------------- rules
def test_rules_hash_is_the_committed_preregistration():
    assert DIGEST == open(G.RULES + ".sha256").read().split()[0]
    assert RULES["rulesId"] == "LGC-2026-11-23" and RULES["notBefore"] == "2026-12-01"
    assert RULES["publication"] == {**RULES["publication"], "changesBindings": False, "changesAcceptedLists": False,
                                    "changesKnowledgeRelease": False, "changesScores": False}
    assert RULES["fetch"]["methods"] == ["GET"]


def test_edited_rules_are_refused(tmp_path):
    q = tmp_path / "r.json"
    shutil.copy(G.RULES, q)
    shutil.copy(G.RULES + ".sha256", str(q) + ".sha256")
    G.load_rules(str(q))
    q.write_text(q.read_text().replace('"insideOrWithinM": 1500', '"insideOrWithinM": 9000'))
    with pytest.raises(SystemExit, match="REFUSED: rules sha256"):
        G.load_rules(str(q))


def test_binding_review_rules_match_batches_1_and_2():
    br = RULES["bindingReview"]
    for k in ("R1_position", "R2_identity", "R3_notTrap", "R4_state", "R5_unique", "R6_live", "R7_level", "R8_datum", "R9_second",
              "check_b", "check_c", "check_d", "historyLive", "noRelaxation"):
        assert k in br
    assert "1.5 km" in br["R1_position"] and "-25..+8 ft" in br["R7_level"] and "2 ft" in br["R9_second"]
    assert "0.5 ft" in br["check_b"] and "5 ft" in br["check_c"] and "25 ft" in br["check_d"] and "15 ft" in br["historyLive"]
    assert "SWOT" in RULES["excludedSources"] and "www.tva.com" not in RULES["hosts"]


# ------------------------------------------------------------------------------------------------------------- targets (real repo files, read only)
def test_target_table_from_committed_files():
    t = G.load_targets()
    assert t["directoryCount"] == 621 and t["reviewedCount"] == 294
    assert sum(1 for l in t["lakes"] if "BINDING" in l["purposes"]) == 621 - 294
    assert all(l["bound"] for l in t["lakes"] if l["reviewed"])  # every reviewed lake has its bound series listed
    assert set(G.handwritten_ids()) == set(G.PILOTS)


def test_target_table_reads_but_never_writes_bindings(tmp_path):
    before = {p: G.sha256_file(p) for p in (G.GENERATED, G.HANDWRITTEN, G.REVIEWED)}
    G.main(["lakes", "--out", str(tmp_path)])
    assert before == {p: G.sha256_file(p) for p in before}


# ------------------------------------------------------------------------------------------------------------- guards
def test_refused_before_not_before(tmp_path):
    f = fetcher(tmp_path, World())
    with pytest.raises(SystemExit, match="REFUSED: the census may not run before 2026-12-01"):
        G.run_census(RULES, DIGEST, f, dt.datetime(2026, 11, 27, tzinfo=dt.timezone.utc), None, targets_table=targets())


def test_fetcher_refuses_hosts_outside_the_allowlist(tmp_path):
    f = fetcher(tmp_path, World())
    for url in ("https://www.tva.com/RestApi/observed-data-48-hours/X", "https://api.water.noaa.gov/nwps/v1/gauges/X"):
        with pytest.raises(G.Refused, match="not allowlisted"):
            f.get(url)


def test_robots_disallow_is_honoured(tmp_path):
    w = World(robots={"data.usbr.gov": "User-agent: *\nDisallow: /rise/\n"})
    f = fetcher(tmp_path, w)
    with pytest.raises(G.Refused, match="robots"):
        f.get("https://data.usbr.gov/rise/api/location")
    assert not any("/rise/api" in c for c in w.calls)
    assert f.robots_report()["data.usbr.gov"]["disallowedPaths"] == ["/rise/api/location"]


# ------------------------------------------------------------------------------------------------------------- geometry + classes
def test_geometry():
    sq = G.polygons_of({"type": "Polygon", "coordinates": [WORLD["lakes"][0]["outline"]]})
    assert G.point_in(sq, -89.95, 35.02) and not G.point_in(sq, -89.95, 34.99)
    assert 1050 < G.distance_to_outline_m(sq, -89.95, 34.99) < 1180


def test_classification_cases():
    out = {"basis": "OUTLINE", "inside": False, "distanceToOutlineM": 4000, "distanceToPointM": 6000}
    ins = {"basis": "OUTLINE", "inside": True, "distanceToOutlineM": 0, "distanceToPointM": 500}
    assert G.classify(RULES, "X DAM TAILWATER", ins)[0] == "TAILWATER"
    assert G.classify(RULES, "X Lake", ins, version="GC-APCO")[0] == "RULE_CURVE"
    assert G.classify(RULES, "X", ins, subparam="Guide Curve")[0] == "RULE_CURVE"
    assert G.classify(RULES, "BIG RIVER AT TOWN", out)[0] == "RIVER"
    assert G.classify(RULES, "X RESERVOIR NEAR Y", ins, base_class="POOL")[0] == "POOL"
    assert G.classify(RULES, "BIG RIVER AT X DAM", ins, base_class="POOL")[0] == "UNKNOWN"
    assert G.cwms_origin(RULES, "Raw-USGS") == "USGS_COPY" and G.cwms_origin(RULES, "Raw-SHEF_SAS") == "USACE"


# ------------------------------------------------------------------------------------------------------------- census
def test_binding_shortlist_on_the_synthetic_world(tmp_path):
    res, f, w = run(tmp_path)
    a = lake(res, "Testa Reservoir|ZZ")
    assert a["geometryBasis"] == "OUTLINE"
    assert cand(a, "cwms", "TestA.Elev.Inst.1Hour.0.Raw-DCP")["selection"]["verdict"] == "SHORTLIST"
    assert cand(a, "cwms", "TestA.Elev-Guide Curve.Inst.1Day.0.Rev")["class"] == "RULE_CURVE"
    assert cand(a, "cwms", "TestA.Elev-Guide Curve.Inst.1Day.0.Rev")["selection"]["verdict"] == "REJECT"
    assert cand(a, "cwms", "TestA-Tailwater.Elev.Inst.1Hour.0.Raw")["selection"]["verdict"] == "REJECT"
    assert cand(a, "usgs", "00062")["class"] == "TAILWATER"
    g = cand(a, "usgs", "62615")
    assert g["selection"]["verdict"] == "SHORTLIST" and g["cadenceMin"] == 15 and g["datum"] == "NAVD88"
    r = cand(a, "rise", "9001")
    assert r["class"] == "POOL" and r["selection"]["verdict"] == "SHORTLIST" and r["cadenceMin"] == 1440
    assert not any(c["provider"] == "rise" and c["series"] in ("9002", "9003") for c in a["candidates"])  # storage; far away
    # S9: both operator pools are inside the outline; the longer record (RISE from 1960, CWMS from 1990) comes first
    assert a["bestShortlist"] == {"provider": "rise", "station": "9001", "series": "9001", "capability": "DIRECT_OPERATOR_POOL"}
    s = res["summary"]["binding"]
    assert s["withShortlist"] == 1 and s["ceilingIfAllShortlistPassStageB"] == 295 and s["targetReachableOnShortlist"] is False


def test_independence_evidence_for_bound_lakes(tmp_path):
    res, _, _ = run(tmp_path)
    b = lake(res, "Testb Lake|ZZ")
    assert cand(b, "cwms", "TestB-Lake.Elev.Inst.1Hour.0.OBS")["boundToThisLake"] is True
    assert cand(b, "usgs", "62615")["boundToThisLake"] is True
    copy = cand(b, "cwms", "TestB-Lake.Elev.Inst.15Minutes.0.Raw-USGS")
    assert copy["independence"]["tier"] == "NOT_INDEPENDENT" and copy["eligibleForV3"] is False
    other = cand(b, "usgs", "62614")
    assert other["independence"]["tier"] == "INDEPENDENT_SITE" and other["eligibleForV3"] is True
    assert "selection" not in other  # reviewed lake: no binding shortlist
    c = lake(res, "Testc Lake|ZZ")
    assert c["geometryBasis"] == "POINT_ONLY"
    assert cand(c, "usgs", "00062")["independence"]["tier"] == "UNCERTAIN"  # bound TVA gauge location unknown
    assert res["summary"]["tvaReservoirsUsgs"]["Testc Lake|ZZ"][0]["station"] == "07000005"
    it = res["summary"]["independentTruth"]
    assert it["v3EligibleLakeIds"] == ["Testb Lake|ZZ"]


def test_no_level_value_is_written(tmp_path):
    res, f, _ = run(tmp_path)
    shas = G.write_outputs(str(tmp_path / "out"), res, f)
    for name in shas:
        assert SENTINEL not in (tmp_path / "out" / name).read_text()
    for p in (tmp_path / "out" / "cache").iterdir():
        assert SENTINEL.encode() not in p.read_bytes()  # IV responses are never cached
    assert res["valuesRead"].startswith("none")


def test_only_get_to_allowlisted_hosts_and_never_tva(tmp_path):
    _, f, w = run(tmp_path)
    hosts = {urllib.parse.urlsplit(u).hostname for u in w.calls}
    assert hosts <= set(RULES["hosts"]) and "www.tva.com" not in hosts
    assert f.count == len(w.calls)


def test_s7_station_bound_by_a_reviewed_lake_is_rejected():
    tg = [{"lakeId": "U|ZZ", "purposes": ["BINDING"], "reviewed": False, "bound": [], "_polys": None},
          {"lakeId": "R|ZZ", "purposes": ["INDEPENDENT_TRUTH"], "reviewed": True,
           "bound": [{"provider": "usgs", "station": "1", "series": "62615", "role": "primary"}]}]
    c = {"provider": "usgs", "station": "1", "series": "62615", "class": "POOL", "host": "waterservices.usgs.gov", "lat": 0, "lon": 0,
         "position": {"basis": "OUTLINE", "inside": True, "distanceToOutlineM": 0, "distanceToPointM": 0}, "latest": NOW.isoformat(),
         "cadenceMin": 15, "datum": "NAVD88", "capabilityIfBound": "DIRECT_LAKE_GAUGE", "origin": "USGS"}
    out = G.finalize(RULES, tg, {"U|ZZ": [dict(c)]}, {}, NOW, {})
    assert out[0]["candidates"][0]["selection"] == {"verdict": "REJECT", "reasons": ["S7 bound by reviewed lake R|ZZ"]}


def test_controls_disable_a_provider_that_is_not_rediscovered(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "CONTROLS", [{"lakeId": "Testb Lake|ZZ", "provider": "usgs", "key": ("usgs", "07000002", "62615")},
                                        {"lakeId": "Testb Lake|ZZ", "provider": "cwms", "key": ("cwms", "NOT-THERE.Elev.Inst.1Hour.0.X")}])
    res, _, _ = run(tmp_path, skip_controls=False)
    assert res["disabledProviders"] == {"cwms": "positive control not rediscovered"}
    assert not any(c["provider"] == "cwms" for l in res["lakes"] for c in l["candidates"])
    assert res["controls"]["results"]["usgs"][0]["found"] is True


def test_controls_reference_committed_bindings():
    rows = {r["lakeId"]: G.bound_refs(r) for r in G.generated_bindings()}
    for c in G.CONTROLS:
        keys = {G.series_key(b["provider"], b.get("station"), b.get("series")) for b in rows[c["lakeId"]]}
        assert tuple(c["key"]) in keys, c


def test_summary_text(tmp_path):
    res, _, _ = run(tmp_path)
    txt = G.summary_text(res)
    assert "BINDING: 1 unprofiled lakes" in txt and "INDEPENDENT_TRUTH" in txt and len(txt.splitlines()) <= 15
