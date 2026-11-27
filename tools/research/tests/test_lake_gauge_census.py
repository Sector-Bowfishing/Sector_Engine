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
    def __init__(self, robots=None, iv_status=200, locations_fail=0, **faults):
        self.faults = faults  # rise_page_status {page: status}, rise_endless, rise_item_status {item: status}, cwms_ts_status,
        #                       cwms_ts_endless, tsmeta_status
        self.robots = robots or {}
        self.iv_status = iv_status
        self.locations_fail = locations_fail  # number of LRP location-catalog calls that fail with 500 (-1: always)
        self.calls = []

    def __call__(self, url, headers):
        self.calls.append(url)
        assert headers.get("User-Agent", "").startswith("Sector-LakeGaugeCensus")
        u = urllib.parse.urlsplit(url)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path == "/robots.txt":
            body = self.robots.get(u.hostname)
            if isinstance(body, int):
                return body, b""
            return (200, body.encode()) if body is not None else (404, b"")
        if u.hostname == "waterservices.usgs.gov" and u.path == "/nwis/site/":
            if "bBox" in q:
                w, s, e, n = map(float, q["bBox"].split(","))
                rows = [r for r in WORLD["usgs"] if w <= r["lon"] <= e and s <= r["lat"] <= n and r["param"] in q["parameterCd"].split(",")]
                if self.faults.get("ws_status"):
                    return self.faults["ws_status"], b"<html>gateway</html>"
                return (200, _rdb(rows)) if rows else (404, b"No sites found matching all criteria")
            sites = q["sites"].split(",")
            return 200, _rdb([r for r in WORLD["usgs"] if r["site"] in sites], catalog=False)
        if u.hostname == "waterservices.usgs.gov" and u.path == "/nwis/iv/":
            if self.iv_status != 200:
                return self.iv_status, b""
            ts = []
            for site in q["sites"].split(","):
                for r in WORLD["usgs"]:
                    if r["site"] == site and r["param"] in q["parameterCd"].split(","):
                        vals = [{"value": SENTINEL, "qualifiers": ["P"], "dateTime": f"2026-12-01T{h:02d}:{m:02d}:00.000-00:00"}
                                for h in range(6, 12) for m in (0, 15, 30, 45)]
                        ts.append({"sourceInfo": {"siteCode": [{"value": site}]}, "variable": {"variableCode": [{"value": r["param"]}]},
                                   "values": [{"value": vals}]})
            return 200, json.dumps({"value": {"timeSeries": ts}}).encode()
        if u.hostname == "storage.googleapis.com":
            rel = u.path.split("/sector-lake-registry/", 1)[1]
            if rel == "registry/lakes.v1.json":
                if self.faults.get("registry_index_status"):
                    return self.faults["registry_index_status"], b""
                return 200, json.dumps({"lakes": [{"lakeId": l["lakeId"], "geometry": {"x": 1} if l["outline"] else None}
                                                  for l in WORLD["lakes"]]}).encode()
            for l in WORLD["lakes"]:
                if l["outline"] and rel == f"lakes/{G.lake_key(l['lakeId'])}/geometry.v1.analysis.geojson.gz":
                    if (self.faults.get("outline_status") or {}).get(l["lakeId"]):
                        return self.faults["outline_status"][l["lakeId"]], b""
                    feat = {"type": "Feature", "properties": {}, "geometry": {"type": "Polygon", "coordinates": [l["outline"]]}}
                    return 200, gzip.compress(json.dumps(feat).encode())
            return 404, b""
        if u.hostname == "api.waterdata.usgs.gov":
            if u.path.endswith("/monitoring-locations/items"):
                if q.get("page") == "2" or self.faults.get("ogc_endless") and q.get("page"):
                    rows = [r for r in WORLD["usgs"] if r["site"] == "07000001"] if q.get("page") == "2" else []
                    links = [{"rel": "next", "href": url.split("&page=")[0] + "&page=3"}] if self.faults.get("ogc_endless") else []
                else:
                    w_, s_, e_, n_ = map(float, q["bbox"].split(","))
                    rows = [r for r in WORLD["usgs"] if w_ <= r["lon"] <= e_ and s_ <= r["lat"] <= n_]
                    links = []
                    if self.faults.get("ogc_paged") or self.faults.get("ogc_endless"):
                        rows = [r for r in rows if r["site"] != "07000001"]
                        links = [{"rel": "next", "href": url + "&page=2"}]
                feats = [{"type": "Feature", "id": f"USGS-{r['site']}", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                          "properties": {"monitoring_location_name": r["name"], "site_type_code": r["tp"], "vertical_datum": r["alt_datum"]}}
                         for r in rows]
                return 200, json.dumps({"type": "FeatureCollection", "features": feats, "links": links}).encode()
            if u.path.endswith("/time-series-metadata/items"):
                if self.faults.get("tsmeta_status"):
                    return self.faults["tsmeta_status"], b""
                site = q["monitoring_location_id"].split("-", 1)[1]
                feats = [{"type": "Feature", "properties": {"parameter_code": r["param"], "begin": "1990-01-01", "end": r["end"],
                                                            "computation_period_identifier": "Points"}}
                         for r in WORLD["usgs"] if r["site"] == site]
                return 200, json.dumps({"type": "FeatureCollection", "features": feats}).encode()
        if u.hostname == "cwms-data.usace.army.mil":
            office = q["office"]
            if u.path.endswith("/LOCATIONS"):
                if office == "LRP" and self.locations_fail:
                    self.locations_fail -= 1 if self.locations_fail > 0 else 0
                    return 500, b""
                return 200, json.dumps({"entries": WORLD["cwmsLocations"].get(office, [])}).encode()
            if self.faults.get("cwms_ts_status"):
                return self.faults["cwms_ts_status"], b""
            rx = re.compile(q["like"])
            ents = [{"office": t["office"], "name": t["name"], "interval": t["interval"], "units": "ft",
                     "extents": [{"earliest-time": t["earliest"], "latest-time": t["latest"]}]}
                    for t in WORLD["cwmsTimeseries"] if t["office"] == office and rx.search(t["name"])]
            if self.faults.get("cwms_ts_endless"):
                return 200, json.dumps({"entries": ents, "next-page": "more"}).encode()
            return 200, json.dumps({"entries": ents}).encode()
        if u.hostname == "data.usbr.gov":
            if u.path == "/rise/api/location":
                st = (self.faults.get("rise_page_status") or {}).get(int(q.get("page", 0)))
                if st:
                    return st, b""
                if self.faults.get("rise_endless"):
                    l = WORLD["riseLocations"][1]
                    one = [{"id": l["id"], "type": "Location", "attributes": {"locationName": l["locationName"],
                            "locationCoordinates": {"type": "Point", "coordinates": [l["lon"], l["lat"]]}}}]
                    return 200, json.dumps({"data": one, "links": {"next": "more"}}).encode()
                if self.faults.get("rise_two_pages") and q.get("page") == "1":
                    l = WORLD["riseLocations"][1]
                    one = [{"id": l["id"], "type": "Location", "attributes": {"locationName": l["locationName"],
                            "locationCoordinates": {"type": "Point", "coordinates": [l["lon"], l["lat"]]}}}]
                    return 200, json.dumps({"data": one, "links": {"next": "p2"}}).encode()
                data = [{"id": l["id"], "type": "Location",
                         "attributes": {"locationName": l["locationName"], "verticalDatumName": l["verticalDatumName"],
                                        "locationCoordinates": {"type": "Point", "coordinates": [l["lon"], l["lat"]]}},
                         "relationships": {"catalogItems": {"data": [{"type": "CatalogItem", "id": i} for i in l["items"]]}}}
                        for l in WORLD["riseLocations"]] if q.get("page") == "1" else []
                return 200, json.dumps({"data": data, "links": {}}).encode()
            m = re.match(r"/rise/api/catalog-item/(\d+)", u.path)
            if m and (self.faults.get("rise_item_status") or {}).get(m.group(1)):
                return self.faults["rise_item_status"][m.group(1)], b""
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


def fetcher(tmp_path, world, now=NOW, rules=RULES):
    return G.Fetcher(rules, out=str(tmp_path / "out"), transport=world, sleep=lambda s: None, now=lambda: now)


def run(tmp_path, world=None, skip_controls=True, evidence=None, rules=RULES, usgs_api="auto"):
    world = world or World()
    f = fetcher(tmp_path, world, rules=rules)
    res = G.run_census(rules, DIGEST, f, NOW, registry_dir(tmp_path), usgs_api=usgs_api, skip_controls=skip_controls,
                       targets_table=targets(), evidence=evidence)
    return res, f, world


TESTB_OBS_EVIDENCE = {G.series_key("cwms", "LRP", "TestB-Lake.Elev.Inst.1Hour.0.OBS"):
                      {"provider": "cwms", "series": "TestB-Lake.Elev.Inst.1Hour.0.OBS", "origin": "USACE", "evidence": "SYNTHETIC"}}


def lake(res, lid):
    return next(l for l in res["lakes"] if l["lakeId"] == lid)


def cand(l, provider, series):
    return next(c for c in l["candidates"] if c["provider"] == provider and c["series"] == series)


# ------------------------------------------------------------------------------------------------------------- rules
def test_rules_hash_is_the_committed_preregistration():
    assert DIGEST == open(G.RULES + ".sha256").read().split()[0]
    assert RULES["rulesId"] == "LGC-2026-11-23.6" and RULES["notBefore"] == "2026-12-01T12:00:00Z"
    side = lambda n: open(os.path.join(os.path.dirname(G.RULES), n + ".sha256")).read().split()[0]
    assert RULES["supersedes"]["sha256"] == side("LGC-2026-11-23.5.rules.json")
    assert [e["sha256"] for e in RULES["supersedes"]["earlier"]] == [side(f"LGC-2026-11-23{x}.rules.json") for x in (".4", ".3", ".2", "")]
    assert RULES["runBinding"]["resultSteps"] == sorted(G.RESULT_STEPS) == ["census"]
    assert set(RULES["runBinding"]["steps"]) == {G.CONTROLS_STEP, G.CENSUS_STEP} and G.KEY == "all"
    assert "--out" not in json.dumps(RULES["publication"]["output"]).replace("no --out", "")
    assert RULES["originEvidenceRegistration"]["registeredFiles"] == []
    assert RULES["runBinding"]["fixedArguments"]["registry"] == G.REGISTRY_BASE
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
    assert t["directoryCount"] == 648 and t["reviewedCount"] == 294
    assert sum(1 for l in t["lakes"] if "BINDING" in l["purposes"]) == 648 - 294
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
        with pytest.raises(G.Refused, match="never queried|not allowlisted"):
            f.get(url)
    with pytest.raises(G.Refused, match="not allowlisted"):
        f.get("https://example.org/x")


def test_robots_disallow_is_honoured(tmp_path):
    w = World(robots={"data.usbr.gov": "User-agent: *\nDisallow: /rise/\n"})
    f = fetcher(tmp_path, w)
    with pytest.raises(G.Refused, match="ROBOTS_DISALLOWED"):
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
    assert G.cwms_origin(RULES, "Raw-USGS") == "USGS_COPY" and G.cwms_origin(RULES, "Raw-SHEF_SAS") == "USACE_UNLABELLED"
    assert G.cwms_origin(RULES, "Raw-USBR") == "USBR_COPY" and G.cwms_origin(RULES, "Raw-CDEC") == "CDEC_COPY"
    assert G.cwms_origin(RULES, "Rev-NWS") == "NWS_REDISTRIBUTION"
    for v in ("Top of Conservation", "Flood Control", "Inflow", "Upper-Rule", "Lower", "Bottom of Flood"):
        assert G.classify(RULES, "X Lake", ins, version=v, base_class="POOL")[0] == "RULE_CURVE", v
    assert G.classify(RULES, "X Lake", ins, sublocation="Upper", base_class="POOL")[0] == "UNKNOWN"
    fut = G.classify(RULES, "X Lake", ins, base_class="POOL", latest="2027-01-01T00:00:00Z", now=NOW)
    assert fut[0] == "RULE_CURVE" and "future" in fut[1][0]
    later = lambda h: (NOW + dt.timedelta(hours=h)).isoformat()
    assert G.classify(RULES, "X Lake", ins, base_class="POOL", latest=later(2), now=NOW)[0] == "RULE_CURVE"  # timestamped: 1 h
    assert G.classify(RULES, "X Lake", ins, base_class="POOL", latest=later(20), now=NOW, date_granular=True)[0] == "POOL"
    assert G.classify(RULES, "X Lake", ins, base_class="POOL", latest=later(30), now=NOW, date_granular=True)[0] == "RULE_CURVE"


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
    # the ceiling uses the reviewed count of the target table (2 synthetic reviewed lakes), not the registration constant
    assert s["withShortlist"] == 1 and s["reviewedNow"] == 2 and s["ceilingIfAllShortlistPassStageB"] == 3


def test_independence_evidence_for_bound_lakes(tmp_path):
    res, _, _ = run(tmp_path)
    b = lake(res, "Testb Lake|ZZ")
    assert cand(b, "cwms", "TestB-Lake.Elev.Inst.1Hour.0.OBS")["boundToThisLake"] is True
    assert cand(b, "usgs", "62615")["boundToThisLake"] is True
    copy = cand(b, "cwms", "TestB-Lake.Elev.Inst.15Minutes.0.Raw-USGS")
    assert copy["independence"]["tier"] == "NOT_INDEPENDENT" and copy["eligibleForV3"] is False
    other = cand(b, "usgs", "62614")
    # the bound primary is an unlabelled CWMS series: its origin is unknown across the USGS/USACE border, so never independent
    assert other["independence"]["tier"] == "UNCERTAIN" and other["eligibleForV3"] is False
    assert any("unlabelled CWMS series" in r for r in other["independence"]["reasons"])
    assert "selection" not in other  # reviewed lake: no binding shortlist
    c = lake(res, "Testc Lake|ZZ")
    assert c["geometryBasis"] == "POINT_ONLY"
    assert cand(c, "usgs", "00062")["independence"]["tier"] == "UNCERTAIN"  # bound TVA gauge location unknown
    assert res["summary"]["tvaReservoirsUsgs"]["Testc Lake|ZZ"][0]["station"] == "07000005"
    it = res["summary"]["independentTruth"]
    assert it["v3EligibleLakeIds"] == []
    assert res["summary"]["structuralCap"]["boundLakes"] == 2 and res["summary"]["structuralCap"]["lakesThatCanBeIndependent"] == 1


def test_origin_evidence_is_the_only_way_across_the_border(tmp_path):
    res, _, _ = run(tmp_path, evidence=TESTB_OBS_EVIDENCE)
    other = cand(lake(res, "Testb Lake|ZZ"), "usgs", "62614")
    assert other["independence"]["tier"] == "INDEPENDENT_SITE" and other["eligibleForV3"] is True
    assert res["summary"]["independentTruth"]["v3EligibleLakeIds"] == ["Testb Lake|ZZ"]
    with pytest.raises(SystemExit, match=r"origin USACE \(cwms\) or USBR \(rise\) and an evidence text"):
        p = tmp_path / "ev.json"
        p.write_text(json.dumps([{"provider": "cwms", "series": "X", "origin": "USACE"}]))
        G.load_origin_evidence(RULES, str(p))


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
                                        {"lakeId": "Testa Reservoir|ZZ", "provider": "rise", "key": ("rise", "9001")},
                                        {"lakeId": "Testb Lake|ZZ", "provider": "cwms", "key": ("cwms", "NOT-THERE.Elev.Inst.1Hour.0.X")}])
    res, _, _ = run(tmp_path, skip_controls=False)
    assert res["disabledProviders"] == {"cwms": "positive control not rediscovered"}
    assert not any(c["provider"] == "cwms" for l in res["lakes"] for c in l["candidates"])
    assert res["controls"]["results"]["usgs"][0]["found"] is True and res["controls"]["results"]["usgs"][0]["class"] == "POOL"
    assert "rise" not in res["disabledProviders"]


def test_controls_require_class_pool(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "CONTROLS", [{"lakeId": "Testa Reservoir|ZZ", "provider": "usgs", "key": ("usgs", "07000003", "00062")}])
    res, _, _ = run(tmp_path, skip_controls=False)  # found, but TAILWATER
    assert res["disabledProviders"] == {"usgs": "positive control not rediscovered"}


def test_controls_reference_committed_bindings():
    rows = {r["lakeId"]: G.bound_refs(r) for r in G.generated_bindings()}
    for c in G.CONTROLS:
        keys = {G.series_key(b["provider"], b.get("station"), b.get("series")) for b in rows[c["lakeId"]]}
        assert tuple(c["key"]) in keys, c


def test_summary_text(tmp_path):
    res, _, _ = run(tmp_path)
    txt = G.summary_text(res)
    assert "BINDING: 1 unprofiled lakes" in txt and "INDEPENDENT_TRUTH" in txt and len(txt.splitlines()) <= 15


# ------------------------------------------------------------------------------------------------------------- review fixes (LGC-2026-11-23.2)



def cli(argv, world=None, now=NOW):
    return G.main(argv, now=now, transport=world or World(), sleep=lambda s: None)


SYN_CONTROLS = [{"lakeId": "Testb Lake|ZZ", "provider": "usgs", "key": ("usgs", "07000002", "62615")},
                {"lakeId": "Testb Lake|ZZ", "provider": "cwms", "key": ("cwms", "TestB-Lake.Elev.Inst.1Hour.0.OBS")},
                {"lakeId": "Testa Reservoir|ZZ", "provider": "rise", "key": ("rise", "9001")}]








@pytest.mark.parametrize("status,allowed", [(404, True), (410, True), (403, False), (401, False), (429, False), (500, False),
                                            (503, False), (301, False), (-1, False)])
def test_robots_status_follows_rfc9309(tmp_path, status, allowed):
    def t(url, headers):
        if url.endswith("/robots.txt"):
            if status == -1:
                raise OSError("unreachable")
            return status, b""
        return 200, b"ok"
    f = fetcher(tmp_path, t)
    if allowed:
        assert f.get("https://data.usbr.gov/rise/api/location")[0] == 200
    else:
        with pytest.raises(G.Refused, match="ROBOTS_DISALLOWED"):
            f.get("https://data.usbr.gov/rise/api/location")
        assert {"code": "ROBOTS_DISALLOWED", "host": "data.usbr.gov", "path": "/rise/api/location"} in f.robots_disallowed()


def test_redirects_are_refused(tmp_path):
    f = fetcher(tmp_path, lambda url, h: (404, b"") if url.endswith("robots.txt") else (302, b""))
    with pytest.raises(G.Refused, match="redirect 302"):
        f.get("https://cwms-data.usace.army.mil/cwms-data/catalog/LOCATIONS")
    assert isinstance(G._NoRedirect().redirect_request(None, None, 302, "", {}, "https://evil.example/"), type(None))


def test_every_retry_counts_against_the_budget(tmp_path):
    rules = dict(RULES, fetch=dict(RULES["fetch"], maxRequests=4))
    f = fetcher(tmp_path, lambda url, h: (404, b"") if url.endswith("robots.txt") else (503, b""), rules=rules)
    st, _ = f.get("https://waterservices.usgs.gov/nwis/site/", cache=False)
    assert st == 503 and f.count == 4 and [r["attempt"] for r in f.log] == [1, 1, 2, 3]
    with pytest.raises(G.Refused, match="budget 4 exhausted"):
        f.get("https://waterservices.usgs.gov/nwis/site/?x=1", cache=False)
    assert f.exhausted


def test_budget_exhaustion_writes_partial_output(tmp_path):
    rules = dict(RULES, fetch=dict(RULES["fetch"], maxRequests=12))
    res, f, _ = run(tmp_path, rules=rules)
    assert res["summary"]["budgetExhausted"] is True and res["summary"]["lakesDiscovered"] < 3
    assert len(res["lakes"]) == 3 and f.count <= 12
    G.write_outputs(str(tmp_path / "out"), res, f)
    assert json.loads((tmp_path / "out" / "census.summary.json").read_text())["summary"]["budgetExhausted"] is True


def test_failed_iv_chunk_is_recorded_and_the_run_completes(tmp_path):
    res, _, _ = run(tmp_path, world=World(iv_status=500))
    assert res["summary"]["errorsByStage"].get("usgs-iv") == 1
    g = cand(lake(res, "Testa Reservoir|ZZ"), "usgs", "62615")
    assert g["latestBasis"] == "catalog end date" and g["selection"]["verdict"] == "SHORTLIST"


def test_iv_only_for_the_binding_pre_shortlist(tmp_path):
    _, _, w = run(tmp_path)
    iv = [dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(u).query)) for u in w.calls if "/nwis/iv/" in u]
    assert [q["sites"] for q in iv] == ["07000001"]  # not the reviewed lakes' 07000004 / 07000005, not the tailwater 07000003


def test_rise_bound_coordinates_come_from_the_fetched_locations(tmp_path):
    c = G.Census(RULES, fetcher(tmp_path, World()), NOW)
    assert c.rise_item_coords(["9001", "9003"]) == {"9001": (35.03, -89.93), "9003": (40.0, -100.0)}


@pytest.mark.parametrize("name,sha", [
    ("LGC-2026-11-23.rules.json", "254752ea31823ace94768a7daa658cf70bfa42b8ad0d276ebb1cae1cf86e9e3f"),
    ("LGC-2026-11-23.2.rules.json", "c17feef35f03c072cb79f4d318b465d807fc72afe5ca351f0b787cc3df382ba7"),
    ("LGC-2026-11-23.3.rules.json", "2a46ac96df8021c5fca08d19406f5e60eedd19e266289f9130515ecb76b5b8b1"),
    ("LGC-2026-11-23.4.rules.json", "64ca297f43331893dd70a15edcc5a84fd76721c434c042cc67c381b616f41494"),
    ("LGC-2026-11-23.5.rules.json", "befcc41dece500688e4c6062372c54e4907aa288d4cad44c38a2ce0b131e23de")])
def test_superseded_rules_files_are_kept_and_refused(name, sha):
    old = os.path.join(os.path.dirname(G.RULES), name)
    assert G.sha256_file(old) == sha
    with pytest.raises(SystemExit, match="not the current registration"):
        G.load_rules(old)


# ------------------------------------------------------------------------------------------------------------- round 2 (LGC-2026-11-23.3)
def _c(provider, series, origin, lat=36.0, lon=-90.0, location=None):
    return {"provider": provider, "station": "S", "series": series, "origin": origin, "lat": lat, "lon": lon, "location": location}


FAR = {("rise", "77", "77"): (36.2, -90.0), ("usgs", "08000001", "62615"): (36.2, -90.0),
       ("cwms", "SPK", "Far-Lake.Elev.Inst.1Hour.0.Raw"): (36.2, -90.0)}
RISE_BOUND = [{"provider": "rise", "station": "77", "series": "77", "role": "primary"}]
USGS_BOUND = [{"provider": "usgs", "station": "08000001", "series": "62615", "role": "primary"}]
CWMS_BOUND = [{"provider": "cwms", "station": "SPK", "series": "Far-Lake.Elev.Inst.1Hour.0.Raw", "role": "primary"}]


@pytest.mark.parametrize("cand_,bound,tier", [
    (_c("cwms", "Res.Elev.Inst.1Hour.0.Raw", "USACE_UNLABELLED", location="Res"), RISE_BOUND, "UNCERTAIN"),   # unlabelled vs USBR
    (_c("rise", "88", "USBR"), CWMS_BOUND, "UNCERTAIN"),                                                     # USBR vs unlabelled
    (_c("usgs", "62615", "USGS"), CWMS_BOUND, "UNCERTAIN"),                                                  # USGS vs unlabelled
    (_c("cwms", "Res.Elev.Inst.1Hour.0.Raw", "USACE_UNLABELLED", location="Res"), USGS_BOUND, "UNCERTAIN"),  # unlabelled vs USGS
    (_c("cwms", "Res.Elev.Inst.1Hour.0.Raw-USBR", "USBR_COPY", location="Res"), RISE_BOUND, "NOT_INDEPENDENT"),
    (_c("cwms", "Res.Elev.Inst.1Hour.0.Raw-CDEC", "CDEC_COPY", location="Res"), USGS_BOUND, "UNCERTAIN"),
    (_c("rise", "88", "USBR"), USGS_BOUND, "INDEPENDENT_AGENCY"),                                            # both labelled, far
    (_c("cwms", "Res.Elev.Inst.1Hour.0.Raw", "USACE_UNLABELLED", location="Res"), CWMS_BOUND, "UNCERTAIN"),  # unlabelled vs unlabelled
    (_c("rise", "88", "RISE_UNCONFIRMED"), USGS_BOUND, "UNCERTAIN"),                                           # RISE may republish USGS
    (_c("usgs", "62615", "USGS"), RISE_BOUND, "UNCERTAIN"),                                                    # bound RISE unconfirmed
])
def test_unlabelled_cwms_is_origin_unknown_against_every_agency(cand_, bound, tier):
    got = G.independence(RULES, cand_, bound, FAR)
    assert got["tier"] == tier, got


def test_origin_evidence_resolves_an_unlabelled_series_against_usbr():
    c = _c("cwms", "Res.Elev.Inst.1Hour.0.Raw", "USACE_UNLABELLED", location="Res")
    ev = {G.series_key("cwms", "S", c["series"]): {"provider": "cwms", "series": c["series"], "origin": "USACE", "evidence": "SYNTHETIC"}}
    assert G.independence(RULES, c, RISE_BOUND, FAR, ev, rise_collectors={"77": "Bureau of Reclamation"})["tier"] == "INDEPENDENT_AGENCY"
    assert G.independence(RULES, c, RISE_BOUND, FAR, ev)["tier"] == "UNCERTAIN"  # bound RISE item unconfirmed


def test_failed_office_catalog_is_not_cached_and_marks_the_lake(tmp_path):
    res, f, w = run(tmp_path, world=World(locations_fail=3))  # the first get (3 attempts) fails, the next succeeds
    a, b = lake(res, "Testa Reservoir|ZZ"), lake(res, "Testb Lake|ZZ")
    assert a["discoveryIncomplete"] == ["CWMS_OFFICE_UNAVAILABLE:LRP"] and not any(c["provider"] == "cwms" for c in a["candidates"])
    assert b["discoveryIncomplete"] == [] and any(c["provider"] == "cwms" for c in b["candidates"])  # retried, not cached empty


def test_office_failures_stop_after_three(tmp_path):
    res, f, w = run(tmp_path, world=World(locations_fail=-1))
    lrp = [u for u in w.calls if "/LOCATIONS" in u and "office=LRP" in u]
    assert len(lrp) == 9  # 3 failed gets x 3 attempts, then no more requests
    assert all("CWMS_OFFICE_UNAVAILABLE:LRP" in l["discoveryIncomplete"] for l in res["lakes"])


def test_binding_counts_keep_incomplete_and_undiscovered_apart():
    def l(lid, **kw):
        return dict({"lakeId": lid, "purposes": ["BINDING"], "reviewed": False, "bound": [], "candidates": [], "discovered": True,
                     "discoveryIncomplete": [], "geometryBasis": "OUTLINE", "bestShortlist": None}, **kw)
    lakes = [l("a"), l("b", discoveryIncomplete=["CWMS_OFFICE_UNAVAILABLE:LRP"]), l("c", discovered=False), l("d", discovered=False)]
    b = G.summarize(RULES, lakes, reviewed_count=294)["binding"]
    assert (b["noCandidate"], b["incomplete"], b["notDiscovered"]) == (1, 1, 2)


def test_tva_is_never_queried_even_if_allowlisted(tmp_path):
    tva = open(os.path.join(HERE, "fixtures", "lake_gauge_census", "tva_robots.txt")).read()
    rules = dict(RULES, hosts=dict(RULES["hosts"], **{"www.tva.com": {"provider": "tva", "agency": "TVA", "terms": "x"}}))
    w = World(robots={"www.tva.com": tva})
    f = fetcher(tmp_path, w, rules=rules)
    with pytest.raises(G.Refused, match="never queried"):
        f.get("https://www.tva.com/RestApi/observed-data-48-hours/GVDA1")
    assert w.calls == []


def test_tva_robots_fixture_disallows_everything(tmp_path):
    tva = open(os.path.join(HERE, "fixtures", "lake_gauge_census", "tva_robots.txt")).read()
    f = fetcher(tmp_path, World(robots={"data.usbr.gov": tva}))  # TVA's file served by an allowlisted host
    with pytest.raises(G.Refused, match="ROBOTS_DISALLOWED"):
        f.get("https://data.usbr.gov/rise/api/location")
    assert "tva.com" in G.NEVER_HOSTS and "www.tva.com" in RULES["fetch"]["neverHosts"]


# ------------------------------------------------------------------------------------------------------------- round 3 (LGC-2026-11-23.4)
def _allegheny():
    return next(G.bound_refs(r) for r in G.generated_bindings() if r["lakeId"] == "Allegheny Reservoir|PA")


def _coords_for(bound, lat=41.84, lon=-79.0):
    return {(b["provider"], b.get("station"), b.get("series")): (lat, lon) for b in bound}


@pytest.mark.parametrize("series,tier", [
    ("Kinzua-Lake.Elev.Inst.1Hour.0.RESOPS", "NOT_INDEPENDENT"),        # bound fallback itself, same base
    ("Kinzua-Tailwater.Elev.Inst.1Hour.0.OBS", "NOT_INDEPENDENT"),      # same base, other sub-location
    ("Kinzua.Elev-Pool.Inst.1Hour.0.Best-LRP", "NOT_INDEPENDENT"),      # derived version at the same base
])
def test_kinzua_probe_same_base_location(series, tier):
    bound = _allegheny()
    c = dict(_c("cwms", series, G.cwms_origin(RULES, G.cwms_parts(series)["version"]), lat=41.95, lon=-78.95),
             location=G.cwms_parts(series)["location"])
    assert G.independence(RULES, c, bound, _coords_for(bound))["tier"] == tier


def test_kinzua_probe_usgs_against_unlabelled_bound_is_uncertain():
    bound = [b for b in _allegheny() if b["provider"] != "usgs"]  # the CWMS/A2W bound series only (unlabelled OBS / RESOPS)
    got = G.independence(RULES, _c("usgs", "62615", "USGS", lat=41.95, lon=-78.95), bound, _coords_for(bound))
    assert got["tier"] == "UNCERTAIN" and any("unlabelled" in r for r in got["reasons"])


def test_derivations_both_directions():
    ev_c = {G.series_key("cwms", "S", "Other.Elev.Inst.1Hour.0.Best"): {"provider": "cwms", "series": "x", "origin": "USACE", "evidence": "S"}}
    c = dict(_c("cwms", "Other.Elev.Inst.1Hour.0.Best", "USACE_UNLABELLED"), location="Other")
    assert G.independence(RULES, c, USGS_BOUND, FAR, ev_c)["tier"] == "UNCERTAIN"  # derived candidate, even with evidence
    bound = [{"provider": "cwms", "station": "SPK", "series": "Far-Lake.Elev.Inst.1Hour.0.Rev-Calc", "role": "primary"}]
    ev_b = {G.series_key("cwms", "SPK", bound[0]["series"]): {"provider": "cwms", "series": "x", "origin": "USACE", "evidence": "S"}}
    coords = {("cwms", "SPK", bound[0]["series"]): (36.2, -90.0)}
    got = G.independence(RULES, _c("rise", "88", "USBR"), bound, coords, ev_b)
    assert got["tier"] == "UNCERTAIN" and any("bound CWMS series has a derived version" in r for r in got["reasons"])
    assert G.is_derived(RULES, "X.Elev.Inst.1Hour.0.CCP") and not G.is_derived(RULES, "X.Elev.Inst.1Hour.0.Raw-DCP")


def test_rise_origin_needs_reclamation_named_in_metadata():
    assert G.rise_origin(G.rise_item_collector({"sourceAgency": "Bureau of Reclamation"})) == "USBR"
    assert G.rise_origin(G.rise_item_collector({"dataProvider": "U.S. Geological Survey"})) == "RISE_UNCONFIRMED"
    assert G.rise_origin(None) == "RISE_UNCONFIRMED"
    confirmed = G.independence(RULES, _c("usgs", "62615", "USGS"), RISE_BOUND, FAR, rise_collectors={"77": "Bureau of Reclamation"})
    assert confirmed["tier"] == "INDEPENDENT_AGENCY"


def test_unconfirmed_rise_candidate_in_the_world(tmp_path):
    res, _, _ = run(tmp_path)
    r = cand(lake(res, "Testa Reservoir|ZZ"), "rise", "9001")
    assert r["origin"] == "RISE_UNCONFIRMED" and r["collector"] is None


def _incomplete(res, lid="Testa Reservoir|ZZ"):
    return lake(res, lid)["discoveryIncomplete"]


def test_rise_catalog_failure_marks_lakes_and_is_retried(tmp_path):
    res, _, w = run(tmp_path, world=World(rise_page_status={1: 404}))
    assert "RISE_CATALOG_UNAVAILABLE" in _incomplete(res)
    assert len([u for u in w.calls if u.split("?")[0].endswith("/rise/api/location")]) == 3  # retried per lake, max 3 failures


def test_rise_catalog_partial_is_not_cached(tmp_path):
    res, _, _ = run(tmp_path, world=World(rise_two_pages=True, rise_page_status={2: 404}))
    assert "RISE_CATALOG_PARTIAL" in _incomplete(res)
    assert not any(c["provider"] == "rise" for c in lake(res, "Testa Reservoir|ZZ")["candidates"])


def test_rise_catalog_truncated(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "RISE_LOCATION_PAGES", 3)
    res, _, _ = run(tmp_path, world=World(rise_endless=True))
    assert "RISE_CATALOG_TRUNCATED" in _incomplete(res)


def test_rise_item_failure_marks_the_lake(tmp_path):
    res, _, _ = run(tmp_path, world=World(rise_item_status={"9001": 500}))
    assert "RISE_ITEM_UNAVAILABLE:9001" in _incomplete(res)


def test_cwms_timeseries_failure_and_truncation(tmp_path, monkeypatch):
    res, _, _ = run(tmp_path, world=World(cwms_ts_status=404))
    assert "CWMS_TS_UNAVAILABLE:TestA" in _incomplete(res)
    monkeypatch.setattr(G, "CWMS_TS_PAGES", 2)
    res, _, _ = run(tmp_path / "b", world=World(cwms_ts_endless=True))
    assert "CWMS_TS_TRUNCATED:TestA" in _incomplete(res)


def test_cwms_locations_truncated(tmp_path, monkeypatch):
    class Endless(World):
        def __call__(self, url, headers):
            st, body = super().__call__(url, headers)
            if "/catalog/LOCATIONS" in url and st == 200:
                d = json.loads(body)
                d["next-page"] = "more"
                return st, json.dumps(d).encode()
            return st, body
    monkeypatch.setattr(G, "CWMS_LOCATION_PAGES", 2)
    res, _, _ = run(tmp_path, world=Endless())
    assert "CWMS_LOCATIONS_TRUNCATED:LRP" in _incomplete(res)


def test_usgs_tsmeta_failure_marks_the_lake(tmp_path):
    res, _, _ = run(tmp_path, world=World(tsmeta_status=503), usgs_api="ogc")
    assert "USGS_TSMETA_UNAVAILABLE" in _incomplete(res)


def test_ogc_path_finds_the_same_pool(tmp_path):
    res, _, _ = run(tmp_path, usgs_api="ogc")
    g = cand(lake(res, "Testa Reservoir|ZZ"), "usgs", "62615")
    assert g["class"] == "POOL" and g["host"] == "api.waterdata.usgs.gov"


def test_oversize_usgs_box_marks_the_lake(tmp_path):
    c = G.Census(RULES, fetcher(tmp_path, World()), NOW)
    big = {"lakeId": "Big|ZZ", "lat": 40, "lon": -90, "_polys": [[[[-100, 30], [-80, 30], [-80, 45], [-100, 45], [-100, 30]]]]}
    assert c.usgs(big) == [] and c.incomplete["Big|ZZ"] == ["USGS_BOX_TOO_LARGE"]


def test_disabled_provider_marks_every_lake(tmp_path, monkeypatch):
    monkeypatch.setattr(G, "CONTROLS", [{"lakeId": "Testb Lake|ZZ", "provider": "rise", "key": ("rise", "NOPE")}])
    res, _, _ = run(tmp_path, skip_controls=False)
    assert all("PROVIDER_DISABLED:rise" in l["discoveryIncomplete"] for l in res["lakes"])
    assert res["summary"]["binding"]["noCandidate"] == 0
    assert res["summary"]["binding"]["incompleteCodesAllLakes"] == {"PROVIDER_DISABLED": 3}
    assert "PROVIDER_DISABLED" in G.summary_text(res)


# ------------------------------------------------------------------------------------------------------------- round 4 (LGC-2026-11-23.5)






def test_outputs_are_write_once(tmp_path):
    G._write_once(str(tmp_path / "a.json"), b"1")
    with pytest.raises(FileExistsError):
        G._write_once(str(tmp_path / "a.json"), b"2")














def _evidence_file(tmp_path, series="Other.Elev.Inst.1Hour.0.Raw", provider="cwms", origin="USACE"):
    p = tmp_path / f"ev-{abs(hash(series))}.json"
    p.write_text(json.dumps([{"provider": provider, "series": series, "origin": origin, "evidence": "SYNTHETIC sensor id"}]))
    return str(p)





@pytest.mark.parametrize("series", ["X.Elev.Inst.1Hour.0.Raw-USGS", "X.Elev.Inst.1Hour.0.Raw-USBR", "X.Elev.Inst.1Hour.0.CDEC",
                                    "X.Elev.Inst.1Hour.0.Rev-NWS"])
def test_evidence_for_a_labelled_series_is_refused(tmp_path, series):
    with pytest.raises(SystemExit, match="labelled copy stays a copy"):
        G.load_origin_evidence(RULES, _evidence_file(tmp_path, series))





@pytest.mark.parametrize("other", ["RISE_UNCONFIRMED", "CDEC_COPY", "USACE", "USBR", "USGS"])
def test_rise_unconfirmed_is_origin_unknown_against_every_family(other):
    bound = {"RISE_UNCONFIRMED": RISE_BOUND, "USBR": RISE_BOUND, "USGS": USGS_BOUND,
             "CDEC_COPY": [{"provider": "cwms", "station": "SPK", "series": "Far-Lake.Elev.Inst.1Hour.0.Raw-CDEC", "role": "primary"}],
             "USACE": CWMS_BOUND}[other]
    coords = {**FAR, ("cwms", "SPK", "Far-Lake.Elev.Inst.1Hour.0.Raw-CDEC"): (36.2, -90.0)}
    ev = {G.series_key("cwms", "SPK", CWMS_BOUND[0]["series"]): {"origin": "USACE"}} if other == "USACE" else None
    col = {"77": "Bureau of Reclamation"} if other == "USBR" else None
    got = G.independence(RULES, _c("rise", "88", "RISE_UNCONFIRMED"), bound, coords, ev, col)
    assert got["tier"] == "UNCERTAIN", got
    if other in ("RISE_UNCONFIRMED", "USBR"):  # and the other direction
        assert G.independence(RULES, _c("usgs", "62615", "USGS"), RISE_BOUND, FAR)["tier"] == "UNCERTAIN"


def test_geometry_failures_mark_lakes(tmp_path):
    c = G.Census(RULES, fetcher(tmp_path, World(registry_index_status=503)), NOW)
    lakes = [dict(l) for l in targets()["lakes"]]
    c.load_geometry(lakes, G.REGISTRY_BASE)
    assert all(c.incomplete[l["lakeId"]] == ["GEOMETRY_UNAVAILABLE"] for l in lakes)
    c = G.Census(RULES, fetcher(tmp_path / "b", World(outline_status={"Testa Reservoir|ZZ": 404})), NOW)
    lakes = [dict(l) for l in targets()["lakes"]]
    c.load_geometry(lakes, G.REGISTRY_BASE)
    assert c.incomplete == {"Testa Reservoir|ZZ": ["GEOMETRY_UNAVAILABLE"]}  # Testc has no geometry by design: not incomplete
    assert "_polys" in lakes[1] and "_polys" not in lakes[0]


def test_ogc_pagination_follows_next_links(tmp_path, monkeypatch):
    res, _, _ = run(tmp_path, world=World(ogc_paged=True), usgs_api="ogc")
    assert cand(lake(res, "Testa Reservoir|ZZ"), "usgs", "62615")["station"] == "07000001"  # found on page 2
    monkeypatch.setattr(G, "OGC_PAGES", 3)
    res, _, _ = run(tmp_path / "b", world=World(ogc_endless=True), usgs_api="ogc")
    assert "USGS_OGC_TRUNCATED" in lake(res, "Testa Reservoir|ZZ")["discoveryIncomplete"]


def test_waterservices_404_must_be_a_well_formed_empty_result(tmp_path):
    res, _, _ = run(tmp_path, world=World(ws_status=404), usgs_api="waterservices")
    assert "USGS_SITE_ERROR" in lake(res, "Testa Reservoir|ZZ")["discoveryIncomplete"]
    res, _, _ = run(tmp_path / "b", world=World(ws_status=404))  # auto: OGC fallback still finds the pool
    assert cand(lake(res, "Testa Reservoir|ZZ"), "usgs", "62615")["host"] == "api.waterdata.usgs.gov"
    assert res["summary"]["errorsByStage"].get("usgs-site")


@pytest.mark.parametrize("version", ["Rev2", "Revised", "Computed", "Calc1", "Best-NWO", "Raw-CCP", "PREVIOUS"])
def test_derived_versions_match_by_substring(version):
    assert G.is_derived(RULES, f"X.Elev.Inst.1Hour.0.{version}")


def test_base_location_comparison_is_case_insensitive():
    bound = [{"provider": "a2w", "station": "LRP:Kinzua", "series": "Kinzua-Lake.Elev.Inst.1Hour.0.OBS", "role": "primary"}]
    c = dict(_c("cwms", "KINZUA-Tailwater.Elev.Inst.1Hour.0.Raw", "USACE_UNLABELLED"), location="KINZUA-Tailwater")
    assert G.independence(RULES, c, bound, {})["tier"] == "NOT_INDEPENDENT"


def test_locations_without_coordinates_mark_the_lake(tmp_path, monkeypatch):
    world = World()
    real = world.__call__

    def patched(url, headers):
        st, body = real(url, headers)
        if "/catalog/LOCATIONS" in url and st == 200:
            d = json.loads(body)
            d["entries"] += [{"office": "LRP", "name": "NoCoord", "state": "ZZ"}, {"office": "LRP", "name": "NoState"}]
            return st, json.dumps(d).encode()
        if "/nwis/site/" in url and "bBox" in url and st == 200:
            return st, body + b"\nUSGS\t07999999\tNO COORD LAKE\tLK\t\t\tNAVD88\tuv\t62615\t1990-01-01\t2026-12-01\t1"
        return st, body
    f = G.Fetcher(RULES, out=str(tmp_path / "o"), transport=patched, sleep=lambda s: None, now=lambda: NOW)
    res = G.run_census(RULES, DIGEST, f, NOW, registry_dir(tmp_path), skip_controls=True, targets_table=targets())
    inc = lake(res, "Testa Reservoir|ZZ")["discoveryIncomplete"]
    assert "CWMS_LOCATION_NO_COORDINATES:LRP" in inc and "USGS_SITE_NO_COORDINATES" in inc
    assert res["summary"]["locationsWithoutCoordinatesOrState"]["cwms:LRP"] >= 1


# ------------------------------------------------------------------------------------------------------------- round 5: shared run ledger (LGC-2026-11-23.6)
import protocol_run_ledger as PRL  # noqa: E402


class FakeIssue:
    """A synthetic Sector_Ops #51 behind `gh api --paginate` (comments printed as one JSON array)."""

    def __init__(self):
        self.comments, self.next_id, self.clock, self.lag = [], 5000, dt.datetime(2000, 1, 1, tzinfo=dt.timezone.utc), 0

    def post(self, body):
        self.clock += dt.timedelta(minutes=1)
        t = self.clock.strftime("%Y-%m-%dT%H:%M:%SZ")
        self.comments.append({"id": self.next_id, "created_at": t, "updated_at": t, "body": body,
                              "html_url": f"https://example.invalid/51#c{self.next_id}", "_lag": self.lag})
        self.next_id += 1

    def __call__(self, path):
        out = []
        for c in self.comments:
            if c["_lag"] > 0:
                c["_lag"] -= 1
                continue
            out.append({k: v for k, v in c.items() if k != "_lag"})
        return json.dumps(out)


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.delenv(PRL.ENV_ROOT, raising=False)
    monkeypatch.setattr(PRL, "_gh_api", lambda path: (_ for _ in ()).throw(AssertionError("real gh reached")))
    monkeypatch.setattr(G, "load_targets", targets)
    monkeypatch.setattr(G, "CONTROLS", SYN_CONTROLS)
    root = tmp_path / "Sector Research" / "lake-brain"
    root.mkdir(parents=True)
    issue = FakeIssue()
    monkeypatch.setattr(G, "open_ledger", lambda rules, digest: PRL.Ledger(root, rules["rulesId"], digest,
                                                                         result_steps=G.RESULT_STEPS, gh=issue))
    led = lambda: PRL.Ledger(root, RULES["rulesId"], DIGEST, result_steps=G.RESULT_STEPS, gh=issue)
    base = os.path.join(str(root.resolve()), "gauge-census", RULES["rulesId"])
    return {"root": root, "issue": issue, "ledger": led, "base": base}


def run_cli(env, argv, world=None, now=NOW, post=True):
    return G.main(argv, now=now, transport=world or World(), sleep=lambda s: None, poster=env["issue"].post if post else None)


def anchored(env):
    assert run_cli(env, ["anchor"]) == 0
    assert env["issue"].comments[-1]["body"].startswith(f"Run anchor: {RULES['rulesId']} ")
    return env


def statuses(env, step=None):
    return [e["status"] for e in env["ledger"]().entries() if step is None or e["step"] == step]


def test_every_networked_step_refuses_before_not_before(env, tmp_path):
    anchored(env)
    w = World()
    early = dt.datetime(2026, 12, 1, 11, 59, tzinfo=dt.timezone.utc)
    for cmd in (["controls"], ["census"]):
        assert run_cli(env, cmd, world=w, now=early) == 2
    assert w.calls == [] and statuses(env) == ["LEDGER_OPENED"]
    f = fetcher(tmp_path, w, now=early)
    with pytest.raises(G.Refused, match="before 2026-12-01T12:00:00Z"):
        f.get("https://waterservices.usgs.gov/nwis/site/")
    c = G.Census(RULES, f, NOW)
    lk = dict(targets()["lakes"][0])
    c.load_geometry([lk], G.REGISTRY_BASE)
    assert c.incomplete[lk["lakeId"]] == ["GEOMETRY_UNAVAILABLE"] and w.calls == []
    assert G.not_before(RULES) == dt.datetime(2026, 12, 1, 12, 0, tzinfo=dt.timezone.utc)


def test_no_step_before_the_run_anchor(env):
    w = World()
    assert run_cli(env, ["controls"], world=w) == 2 and run_cli(env, ["census"], world=w) == 2
    assert w.calls == [] and "STARTED" not in statuses(env)


def test_controls_then_census_full_trail(env):
    anchored(env)
    assert run_cli(env, ["controls"]) == 0
    assert statuses(env, "controls") == ["STARTED", "COMPLETED"]
    assert run_cli(env, ["census"]) == 0
    assert statuses(env, "census") == ["STARTED", "START_CONFIRMED", "OUTPUTS_RECORDED", "COMPLETED"]
    bodies = [c["body"].split("\n", 1)[0] for c in env["issue"].comments]
    assert [b.split()[1] for b in bodies] == ["anchor:", "start:", "result:"]
    assert not any("Owner" in c["body"] for c in env["issue"].comments)
    assert run_cli(env, ["confirm-result"]) == 0
    assert statuses(env, "census")[-1] == "RESULT_CONFIRMED"
    led = env["ledger"]()
    done = led.require("census", "all")
    assert done["counted"] is True and done["run"] == 1
    assert set(done["outputs"]) == {"census.json", "census.summary.json", "robots.json", "requests.jsonl"}
    assert done["result"]["registryIndexSha256"] and done["result"]["cacheAfter"]
    start = next(e for e in led.entries() if e["status"] == "STARTED" and e["step"] == "census")
    assert start["args"]["toolSha256"] == G.tool_sha256() and start["args"]["registrySource"] == G.REGISTRY_BASE
    res = json.load(open(os.path.join(env["base"], "census-run-1", "census.json")))
    assert res["runBinding"]["anchor"] == led.anchor()
    hits = [json.loads(l) for l in open(os.path.join(env["base"], "census-run-1", "requests.jsonl")) if '"cacheHit": true' in l]
    assert hits and all(len(h["sha256"]) == 64 for h in hits)  # the census reran the controls' metadata requests from the cache
    assert led.audit(check_external=True)["findings"] == []


def test_second_census_is_refused(env):
    anchored(env)
    assert run_cli(env, ["census"]) == 0
    assert run_cli(env, ["census"]) == 2
    assert not os.path.exists(os.path.join(env["base"], "census-run-2"))
    assert run_cli(env, ["controls"]) == 0  # controls is its own step, and also runs once only
    assert run_cli(env, ["controls"]) == 2


def test_not_listed_yet_waits_and_never_reposts(env):
    anchored(env)
    env["issue"].lag = 3  # the Run start comment shows up only on the 4th listing
    assert run_cli(env, ["census"]) == 0
    assert sum(1 for c in env["issue"].comments if c["body"].startswith("Run start:")) == 1


@pytest.mark.parametrize("extra", [["--lakes", "Testa Reservoir|ZZ"], ["--registry", "https://storage.googleapis.com/other"],
                                   ["--usgs-api", "ogc"], ["--usgs-api", "waterservices"]])
def test_fixed_arguments(env, extra):
    anchored(env)
    assert run_cli(env, ["census"] + extra) == 2
    assert "STARTED" not in statuses(env) and not os.path.exists(os.path.join(env["base"], "census-run-1"))


def test_interrupt_after_requests_is_terminal_not_an_abort(env, monkeypatch):
    anchored(env)
    real = G.run_census

    def interrupted(rules, digest, fetcher, *a, **k):
        fetcher.get("https://waterservices.usgs.gov/nwis/site/", {"sites": "07000001"})
        raise KeyboardInterrupt()
    monkeypatch.setattr(G, "run_census", interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_cli(env, ["census"])
    monkeypatch.setattr(G, "run_census", real)
    assert statuses(env, "census") == ["STARTED", "START_CONFIRMED"]  # no ABORTED_BEFORE_RESULT: terminal
    assert run_cli(env, ["census"]) == 2  # no retry under this rules id


def test_abort_only_when_no_request_was_sent(env, monkeypatch):
    anchored(env)
    monkeypatch.setattr(G.Census, "load_geometry", lambda self, lakes, registry: (_ for _ in ()).throw(KeyboardInterrupt()))
    with pytest.raises(KeyboardInterrupt):
        run_cli(env, ["controls"])
    assert statuses(env, "controls") == ["STARTED", "ABORTED_BEFORE_RESULT"]
    monkeypatch.undo()
    monkeypatch.setattr(G, "load_targets", targets)
    monkeypatch.setattr(G, "CONTROLS", SYN_CONTROLS)
    monkeypatch.setattr(PRL, "_gh_api", lambda path: (_ for _ in ()).throw(AssertionError("real gh reached")))
    issue = env["issue"]
    monkeypatch.setattr(G, "open_ledger", lambda rules, digest: PRL.Ledger(env["root"], rules["rulesId"], digest,
                                                                         result_steps=G.RESULT_STEPS, gh=issue))
    assert run_cli(env, ["controls"]) == 0  # attempt 2 is allowed after a clean abort
    assert os.path.exists(os.path.join(env["base"], "controls-run-2", "controls.json"))


def test_origin_evidence_is_bound_before_the_census(env, tmp_path):
    anchored(env)
    ev = _evidence_file(tmp_path)
    assert run_cli(env, ["census", "--origin-evidence", ev]) == 2  # not bound
    assert run_cli(env, ["register-evidence", "--file", ev]) == 0
    assert statuses(env, "census") == ["INPUTS_BOUND"]
    assert run_cli(env, ["census"]) == 2  # bound evidence must be passed
    assert run_cli(env, ["census", "--origin-evidence", ev]) == 0
    res = json.load(open(os.path.join(env["base"], "census-run-1", "census.json")))
    assert res["originEvidenceFile"]["sha256"] == G.sha256_file(ev) and "SYNTHETIC sensor id" in res["originEvidenceFile"]["text"]
    assert run_cli(env, ["register-evidence", "--file", _evidence_file(tmp_path, "Another.Elev.Inst.1Hour.0.Raw")]) == 2


def test_root_comes_from_cortex_research_path(monkeypatch):
    seen = {}

    def fake_for_brain(brain, pid, sha, **kw):
        seen.update(brain=brain, pid=pid, sha=sha, **kw)
        return "L"
    monkeypatch.setattr(G.Ledger, "for_brain", staticmethod(fake_for_brain))
    assert G.open_ledger(RULES, DIGEST) == "L"
    assert seen["brain"] == "lake-brain" and seen["pid"] == "LGC-2026-11-23.6" and seen["result_steps"] == frozenset({"census"})


def test_old_local_ledger_module_is_gone():
    assert not os.path.exists(os.path.join(os.path.dirname(G.__file__), "lake_census_run_ledger.py"))
