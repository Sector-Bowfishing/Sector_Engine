"""Phone contract for GET /lakes/ready (Sector_Engine #156): the golden meets the contract; the validator catches breakage.

The same validator as the /conditions goldens (tools/conditions_golden/capture.py), against contracts/phone/lakes-ready-v1.json.
The golden is synthetic (Tests/SectorEngineTests/LakesReadyAPITests.swift checks the Engine produces it byte-for-byte in
value); this repository is public, so it may carry only directory ids, names and centroids, statuses and dates.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("capture", ROOT / "tools/conditions_golden/capture.py")
capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(capture)

CONTRACT_PATH = ROOT / "contracts/phone/lakes-ready-v1.json"
CONTRACT = json.loads(CONTRACT_PATH.read_text())
FIELDS = CONTRACT["fields"]
GOLDEN = json.loads((ROOT / "verification/fixtures/phone-contract/lakes-ready-v1.golden.json").read_text())


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
    seen.discard("lakes[]")
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
        assert lake["layers"], "a listed lake has at least one ready layer"
        for name, layer in lake["layers"].items():
            assert name in {"clarity", "waterTemp", "level"}, name
            assert layer["status"] in statuses and capture.DATE_RE.match(layer["asOf"])
            assert set(layer) == {"status", "asOf"}


def test_wind_and_intelligence_are_documented_not_emitted():
    assert set(CONTRACT["layersNotInV1"]) >= {"wind", "intelligence"}
    assert not any(p.startswith(("lakes[].layers.wind", "lakes[].layers.intelligence")) for p in FIELDS)


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
    ):
        assert capture.validate(doc, FIELDS), "a breaking change passed the validator"
    assert capture.validate(lake0(lambda l: l.__setitem__("layers", {})), FIELDS) == []
    assert capture.validate(lake0(lambda l: l["layers"].__setitem__("wind", {"status": "LIVE", "asOf": "2026-11-10T14:00:00Z"})), FIELDS) == []
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
