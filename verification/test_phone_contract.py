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


def _strings(v, path=""):
    if isinstance(v, dict):
        for k, c in v.items():
            yield from _strings(c, f"{path}.{k}" if path else k)
    elif isinstance(v, list):
        for c in v:
            yield from _strings(c, path + "[]")
    elif isinstance(v, str):
        yield path, v


def test_goldens_carry_no_free_text():
    """Public repo: every string is redacted, an ISO date, or an enum/code/id on the keep-list."""
    for f in GOLDENS:
        for path, s in _strings(json.loads(f.read_text())):
            ok = s == capture.REDACTED or capture.DATE_RE.match(s) or path in capture.KEEP
            assert ok, f"{f.name}: free text at {path}"


def test_redaction_is_default_deny():
    doc = {"brandNewProse": "Carp are spawning in the creek", "band": "Good", "nights": [{"rating": "Fair", "x": "y"}]}
    red = capture.redact(doc)
    assert red["brandNewProse"] == capture.REDACTED
    assert red["band"] == "Good" and red["nights"][0]["rating"] == "Fair" and red["nights"][0]["x"] == capture.REDACTED


def test_validator_catches_breaking_changes():
    base = json.loads(GOLDENS[0].read_text())
    for mutate in (
        lambda d: d.pop("moonIllumination"),
        lambda d: d.__setitem__("score", "60"),
        lambda d: d.__setitem__("nights", None),
        lambda d: d["weather"].__setitem__("windDirection", 329.5),
        lambda d: d["tonight"]["hours"][0].__setitem__("date", "2026-11-06T12:00:00.123Z"),
        lambda d: d["factors"][0].pop("weightPct"),
        lambda d: d.__setitem__("score", 72.0),
        lambda d: d.__setitem__("moonIllumination", float("nan")),
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
