"""Phone contract for GET /conditions (Sector_Ops #53 rule 1): goldens meet the contract; the validator catches breakage."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("capture", ROOT / "tools/conditions_golden/capture.py")
capture = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(capture)

GOLDENS = sorted((ROOT / "verification/fixtures/phone-contract").glob("*/*.json"))
FIELDS = capture.load_contract()


def test_goldens_exist():
    assert len(GOLDENS) >= 10


def test_goldens_meet_contract():
    for f in GOLDENS:
        assert capture.validate(json.loads(f.read_text()), FIELDS) == [], f.name


def test_goldens_are_redacted():
    for f in GOLDENS:
        doc = json.loads(f.read_text())
        assert capture.redact(doc) == doc, f"{f.name} carries unredacted free text"


def test_validator_catches_breaking_changes():
    base = json.loads(GOLDENS[0].read_text())
    for mutate in (
        lambda d: d.pop("moonIllumination"),
        lambda d: d.__setitem__("score", "60"),
        lambda d: d.__setitem__("nights", None),
        lambda d: d["weather"].__setitem__("windDirection", 329.5),
        lambda d: d["tonight"]["hours"][0].__setitem__("date", "2026-11-06T12:00:00.123Z"),
        lambda d: d["factors"][0].pop("weightPct"),
    ):
        doc = copy.deepcopy(base)
        mutate(doc)
        assert capture.validate(doc, FIELDS), "a breaking change passed the validator"
    added = copy.deepcopy(base)
    added["tileSources"] = {"moon": {"path": "app"}}
    assert capture.validate(added, FIELDS) == []


def test_contract_paths_are_well_formed():
    for p, spec in FIELDS.items():
        assert spec["type"] in {"int", "number", "string", "bool", "date", "array", "object"}, p
        parent = p.rsplit(".", 1)[0] if "." in p else None
        if p.endswith("[]"):
            assert FIELDS[p[:-2]]["type"] == "array", p
        elif parent:
            owner = parent[:-2] if parent.endswith("[]") else parent
            assert owner in FIELDS, f"{p}: parent {owner} missing"
