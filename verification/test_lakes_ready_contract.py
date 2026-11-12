"""Phone contract for GET /lakes/ready (Sector_Engine #156, #158): the golden meets the contract; the validator catches breakage.

1.2.0 adds the Engine-computed wind layer (owner approval on Sector_Ops #51, 2026-11-11): always ESTIMATE, with an hourly list.

The same validator as the /conditions goldens (tools/conditions_golden/capture.py), against contracts/phone/lakes-ready-v1.json.
The golden is synthetic (Tests/SectorEngineTests/LakesReadyAPITests.swift checks the Engine produces it byte-for-byte in
value); this repository is public, so it may carry only directory ids, names and centroids, statuses, dates, and made-up
layer values and boxes.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("capture", ROOT / "tools/conditions_golden/capture.py")
capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(capture)

CONTRACT_PATH = ROOT / "contracts/phone/lakes-ready-v1.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text())
FIELDS = CONTRACT["fields"]
GOLDEN = json.loads((ROOT / "verification/fixtures/phone-contract/lakes-ready-v1.golden.json").read_text())

sys.path.insert(0, str(ROOT / "jobs/brain_platform"))
from sector_brain_platform.keys import lake_key  # noqa: E402  (the one lake-key algorithm, as BrainPlatform.lakeKey)

LAYER_KEYS = {"clarity": ({"status", "asOf", "valueFt"}, {"lowFt", "highFt"}),
              "waterTemp": ({"status", "asOf", "valueF"}, set()),
              "level": ({"status", "asOf"}, set()),
              "wind": ({"status", "asOf", "speedMph", "fromDeg", "hourly"}, set())}


def _directory() -> dict:
    src = (ROOT / "Sources/SectorEngine/Support/LakeDirectory.swift").read_text()
    body = re.search(r'lakesJSON = #"""\n(.*?)\n"""#', src, re.S).group(1)
    return {f"{d['name']}|{d['state']}": d for d in json.loads(body)}


def test_golden_meets_contract():
    assert capture.validate(GOLDEN, FIELDS) == []


def test_golden_exercises_every_contract_path_and_nothing_else():
    seen: set[str] = set()

    def walk(v, path):
        if v is None:
            return
        if path:
            seen.add(path)
        if isinstance(v, dict):
            for k, c in v.items():
                walk(c, f"{path}.{k}" if path else k)
        elif isinstance(v, list):
            for c in v:
                walk(c, path + "[]")

    walk(GOLDEN, "")
    seen = {p for p in seen if not p.endswith("[]")}  # array elements ("lakes[]", "...hourly[]") are not contract paths
    assert seen == set(FIELDS)


def test_golden_is_synthetic_directory_data_only():
    """Public repo: only directory lakes (id, name, centroid as GET /lakes serves them), known statuses and dates."""
    directory = _directory()
    statuses = set(CONTRACT["statusValues"])
    assert statuses == {"LIVE", "ESTIMATE"}
    assert GOLDEN["version"] == 1 and capture.DATE_RE.match(GOLDEN["generatedAt"])
    ids = [lake["lakeId"] for lake in GOLDEN["lakes"]]
    assert ids == sorted(ids) and ids
    for lake in GOLDEN["lakes"]:
        d = directory[lake["lakeId"]]
        assert lake["name"] == d["name"]
        assert lake["centroid"] == {"lat": d["lat"], "lon": d["lon"]}
        assert lake["directoryId"] == lake["lakeId"]
        assert lake["brainKey"] == lake_key(lake["lakeId"])
        assert lake["layers"], "a listed lake has at least one ready layer"
        for name, layer in lake["layers"].items():
            assert name in LAYER_KEYS, name
            assert layer["status"] in statuses and capture.DATE_RE.match(layer["asOf"])
            required, optional = LAYER_KEYS[name]
            assert required <= set(layer) <= required | optional, (name, set(layer))
        if "extent" in lake:
            b, conf = lake["extent"]["bbox"], lake["extent"]["confidence"]
            assert conf in {"HIGH", "MEDIUM"}
            assert -180 <= b["west"] < b["east"] <= 180 and -90 <= b["south"] < b["north"] <= 90
            assert b["west"] <= d["lon"] <= b["east"] and b["south"] <= d["lat"] <= b["north"], "a box around the lake"
    assert any("extent" in lake for lake in GOLDEN["lakes"]) and not all("extent" in lake for lake in GOLDEN["lakes"])


def test_golden_wind_is_an_hourly_estimate():
    """wind (1.2.0): always ESTIMATE; hourly[0] is the asOf hour with the layer's values; then later whole hours, at most 12 h on;
    whole-degree FROM directions 0-359; one-decimal mph. Some listed lakes have it and some do not."""
    winds = [lake["layers"]["wind"] for lake in GOLDEN["lakes"] if "wind" in lake["layers"]]
    assert winds and len(winds) < len(GOLDEN["lakes"])
    for w in winds:
        assert w["status"] == "ESTIMATE"
        assert w["asOf"].endswith(":00:00Z") and w["asOf"] <= GOLDEN["generatedAt"]
        assert w["hourly"] and w["hourly"][0] == {"time": w["asOf"], "speedMph": w["speedMph"], "fromDeg": w["fromDeg"]}
        times = [h["time"] for h in w["hourly"]]
        assert times == sorted(set(times)) and all(t.endswith(":00:00Z") for t in times)
        assert len(times) <= 13
        for h in w["hourly"]:
            assert isinstance(h["fromDeg"], int) and 0 <= h["fromDeg"] <= 359
            assert h["speedMph"] >= 0 and round(h["speedMph"], 1) == h["speedMph"]


def test_intelligence_is_documented_not_emitted_and_wind_is_in_the_contract():
    assert "intelligence" in CONTRACT["layersNotInV1"] and "wind" not in CONTRACT["layersNotInV1"]
    assert not any(p.startswith("lakes[].layers.intelligence") for p in FIELDS)
    assert FIELDS["lakes[].layers.wind"] == {"type": "object", "required": False}


def test_contract_1_x_is_additive_over_1_0():
    """1.1.0 and 1.2.0 (#158) only add: every 1.0.0 path keeps its type and requiredness; the response version stays 1."""
    v1_0 = {
        "version": ("int", True), "generatedAt": ("date", True), "lakes": ("array", True), "lakes[].lakeId": ("string", True),
        "lakes[].name": ("string", True), "lakes[].centroid": ("object", True), "lakes[].centroid.lat": ("number", True),
        "lakes[].centroid.lon": ("number", True), "lakes[].layers": ("object", True),
        **{f"lakes[].layers.{n}": ("object", False) for n in ("clarity", "waterTemp", "level")},
        **{f"lakes[].layers.{n}.status": ("string", True) for n in ("clarity", "waterTemp", "level")},
        **{f"lakes[].layers.{n}.asOf": ("date", True) for n in ("clarity", "waterTemp", "level")},
    }
    for p, (t, req) in v1_0.items():
        assert (FIELDS[p]["type"], FIELDS[p]["required"]) == (t, req), p
    # New keys the Engine always sends (directoryId, brainKey, a ready layer's value) are required: adding a response key is
    # additive for a client that ignores unknown keys.
    assert CONTRACT["version"] == "1.2.0" and GOLDEN["version"] == 1


def test_contract_1_2_is_additive_over_1_1():
    """1.2.0 (#158 wind) adds only paths under lakes[].layers.wind, the layer itself optional; every 1.1.0 path is unchanged."""
    v1_1 = {"lakes[].directoryId": ("string", True), "lakes[].brainKey": ("string", True), "lakes[].extent": ("object", False),
            "lakes[].extent.bbox": ("object", True), "lakes[].extent.confidence": ("string", True),
            "lakes[].layers.clarity.valueFt": ("number", True), "lakes[].layers.clarity.lowFt": ("number", False),
            "lakes[].layers.clarity.highFt": ("number", False), "lakes[].layers.waterTemp.valueF": ("number", True),
            **{f"lakes[].extent.bbox.{k}": ("number", True) for k in ("west", "south", "east", "north")}}
    for p, (t, req) in v1_1.items():
        assert (FIELDS[p]["type"], FIELDS[p]["required"]) == (t, req), p
    new = {p for p in FIELDS if p.startswith("lakes[].layers.wind")}
    assert new == {"lakes[].layers.wind", *(f"lakes[].layers.wind.{k}" for k in ("status", "asOf", "speedMph", "fromDeg", "hourly")),
                   *(f"lakes[].layers.wind.hourly[].{k}" for k in ("time", "speedMph", "fromDeg"))}
    assert [r["version"] for r in CONTRACT["revisions"]] == ["1.0.0", "1.1.0", "1.2.0"]


def test_validator_catches_breaking_changes():
    def lake0(mutate):
        doc = copy.deepcopy(GOLDEN)
        mutate(doc["lakes"][0])
        return doc

    for doc in (
        {**GOLDEN, "version": "1"},
        {**GOLDEN, "version": 1.5},
        {**GOLDEN, "generatedAt": "2026-11-10T15:30:00.000Z"},
        {**GOLDEN, "lakes": None},
        lake0(lambda l: l.pop("lakeId")),
        lake0(lambda l: l.pop("centroid")),
        lake0(lambda l: l["centroid"].pop("lon")),
        lake0(lambda l: l["centroid"].__setitem__("lat", "41.03")),
        lake0(lambda l: l.__setitem__("layers", None)),
        lake0(lambda l: l["layers"]["clarity"].pop("asOf")),
        lake0(lambda l: l["layers"]["clarity"].__setitem__("asOf", "2026-11-10T14:00:00.250Z")),
        lake0(lambda l: l.pop("directoryId")),
        lake0(lambda l: l.pop("brainKey")),
        lake0(lambda l: l["layers"]["clarity"].pop("valueFt")),
        lake0(lambda l: l["layers"]["clarity"].__setitem__("valueFt", "2.0")),
        lake0(lambda l: l["extent"].pop("bbox")),
        lake0(lambda l: l["extent"]["bbox"].pop("north")),
        lake0(lambda l: l["extent"].__setitem__("bbox", [-81.08, 40.98, -80.95, 41.07])),
    ):
        assert capture.validate(doc, FIELDS), "a breaking change passed the validator"
    assert capture.validate(lake0(lambda l: l.__setitem__("layers", {})), FIELDS) == []
    assert capture.validate(lake0(lambda l: l.pop("extent")), FIELDS) == [], "extent is optional"
    assert capture.validate(lake0(lambda l: l["layers"]["clarity"].pop("lowFt")), FIELDS) == []
    assert capture.validate(lake0(lambda l: l["layers"].pop("wind")), FIELDS) == [], "wind is optional"
    for mutate in (lambda w: w.pop("speedMph"), lambda w: w.pop("fromDeg"), lambda w: w.pop("hourly"),
                   lambda w: w.__setitem__("fromDeg", 225.5), lambda w: w.__setitem__("hourly", [{"time": "2026-11-10T15:00:00Z"}]),
                   lambda w: w.__setitem__("hourly", [1])):
        assert capture.validate(lake0(lambda l: mutate(l["layers"]["wind"])), FIELDS), "a broken wind layer passed"
    assert capture.validate(lake0(lambda l: l["layers"].__setitem__("intelligence", {"status": "LIVE"})), FIELDS) == [], \
        "an unknown layer is additive"
    assert capture.validate({**GOLDEN, "newTopLevel": 1}, FIELDS) == [], "additive fields must be allowed"


def test_contract_paths_are_well_formed():
    for p, spec in FIELDS.items():
        assert spec["type"] in {"int", "number", "string", "bool", "date", "array", "object"}, p
        if "." in p:
            parent = p.rsplit(".", 1)[0]
            owner = parent[:-2] if parent.endswith("[]") else parent
            assert owner in FIELDS, f"{p}: parent {owner} missing"


def test_conditions_goldens_do_not_pick_up_this_golden():
    """The /conditions golden loaders glob <dir>/*.json; this golden sits at the top level so it is not one of them."""
    assert all("lakes-ready" not in str(f) for f in (ROOT / "verification/fixtures/phone-contract").glob("*/*.json"))
