"""Dry-run publish: every state matches the contract schema, the write set is declared, reruns on unchanged inputs skip, and the full directory
computes without an error."""
import datetime as dt
import json
import os

import moon_support as S
from moon_brain import contract as C
from moon_brain.publish import publish
from moon_brain.writer import DryRunWriter
from sector_brain_platform import declared_writes as DW

HERE = os.path.dirname(os.path.abspath(__file__))

BRAIN_JSON = json.load(open(os.path.join(HERE, "..", "brain.json"), encoding="utf-8"))
SCHEMA = json.load(open(os.path.join(HERE, "..", "contracts", "moon-night-light-v1.json"), encoding="utf-8"))["stateSchema"]


_TYPES = {"object": dict, "array": list, "string": str, "number": (int, float), "integer": int, "boolean": bool, "null": type(None)}


def schema_errors(v, sch, path="$"):
    """The JSON Schema subset the state schema uses (type incl. nullable lists, const, enum, required, properties, additionalProperties as a
    schema, items, minimum, maximum). Stdlib only: tools/architecture/jsonschema_lite has no nullable type lists."""
    out = []
    t = sch.get("type")
    if t is not None:
        ts = t if isinstance(t, list) else [t]
        if not any(isinstance(v, _TYPES[x]) and not (x in ("number", "integer") and isinstance(v, bool)) for x in ts):
            return [f"{path}: {v!r} is not {t}"]
    if "const" in sch and v != sch["const"]:
        out.append(f"{path}: must equal {sch['const']!r}")
    if "enum" in sch and v not in sch["enum"]:
        out.append(f"{path}: {v!r} not in {sch['enum']}")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        if "minimum" in sch and v < sch["minimum"]:
            out.append(f"{path}: below {sch['minimum']}")
        if "maximum" in sch and v > sch["maximum"]:
            out.append(f"{path}: above {sch['maximum']}")
    if isinstance(v, dict):
        out += [f"{path}: missing {k}" for k in sch.get("required", []) if k not in v]
        props = sch.get("properties", {})
        for k, x in v.items():
            sub = props.get(k, sch.get("additionalProperties") if isinstance(sch.get("additionalProperties"), dict) else None)
            if sub:
                out += schema_errors(x, sub, f"{path}.{k}")
    if isinstance(v, list) and isinstance(sch.get("items"), dict):
        for i, x in enumerate(v):
            out += schema_errors(x, sch["items"], f"{path}[{i}]")
    return out


def test_the_schema_checker_catches_violations():
    assert schema_errors({"darkness": {"rule": "DARKNESS_RULE_V1", "class": "PITCH", "basis": "MOON_ONLY", "cloudCover": {"status": "MISSING"}}},
                         {"properties": {"darkness": SCHEMA["properties"]["darkness"]}})
    assert schema_errors({"illumination": 1.2}, SCHEMA["properties"]["moon"]["properties"]["illumination"] and
                         {"properties": {"illumination": SCHEMA["properties"]["moon"]["properties"]["illumination"]}})
    assert schema_errors({}, SCHEMA)


def test_states_match_the_contract_schema():
    up = S.run_updates()
    states = [v for k, v in up.items() if k.endswith("/states/moon")]
    assert len(states) == len(S.SLICE)
    for st in states:
        assert schema_errors(st, SCHEMA) == [], st["lakeId"]


def test_every_runtime_write_is_declared_and_moon_owned():
    up = S.run_updates()
    assert DW.undeclared(BRAIN_JSON, list(up)) == []
    assert DW.unused_legacy(BRAIN_JSON, list(up)) == []
    assert DW.problems(BRAIN_JSON) == []


def test_unchanged_inputs_skip_and_cloud_input_republishes():
    w = DryRunWriter()
    d = S.directory()
    assert publish(d, w, S.NIGHT, now=S.NOW)["skippedUnchanged"] == 0
    again = publish(d, w, S.NIGHT, now=S.NOW)
    assert again["skippedUnchanged"] == len(S.SLICE)
    cloud = {"Guntersville|AL": {"contract": C.WEATHER_INPUT_CONTRACT, "hourly": [{"at": "2026-11-23T03:00:00Z", "cloudCoverPct": 80}]}}
    assert publish(d, w, S.NIGHT, cloud, now=S.NOW)["skippedUnchanged"] == len(S.SLICE) - 1


def test_whole_directory_runs_clean():
    w = DryRunWriter()
    rep = publish(S.directory(None), w, dt.date(2026, 11, 22), now=S.NOW)
    assert rep["ok"] and rep["evaluated"] == 621 and rep["readinessCounts"] == {"CALIBRATION": 621}
    assert sum(rep["darknessClass"].values()) == 621 and rep["basis"] == {"MOON_ONLY": 621}


def test_registry_says_disabled_and_unscored():
    up = S.run_updates()
    reg = up["brains/moon"]
    assert reg["enabled"] is False and reg["status"] == "CALIBRATION" and "no Engine readiness score" in reg["scoreNote"]
    assert reg["knowledgeRelease"]["approvalStatus"] == "NOT_RECORDED"
