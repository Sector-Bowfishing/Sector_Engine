#!/usr/bin/env python3
"""Derive the versioned JSON schema of a Swift Brain's published per-lake state from its Codable record (BR-13), so the schema can never drift
from what the runtime encodes. Non-optional properties are required (the Swift encoder always emits them); `String` raw-value enums become closed
string enums; nested records are objects (validated by their own Swift types).

  python3 tools/architecture/swift_state_schema.py --check     # exit 1 if a committed schema differs
  python3 tools/architecture/swift_state_schema.py --write

Static only: reads Swift source, writes brains/<dir>/contracts/<id>.schema.json."""
import argparse
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
RECORDS = (
    {"id": "lake-state-v1", "brain": "lake-brain", "struct": "LakeLevelStateRecord", "out": "brains/lake/contracts/lake-state-v1.schema.json",
     "sources": ("brains/lake/runtime/LakeBrain",), "path": "/lakes/{k}/states/lake"},
    {"id": "water-temp-state-v1", "brain": "water-temp", "struct": "State", "out": "brains/water-temperature/contracts/water-temp-state-v1.schema.json",
     "sources": ("brains/water-temperature/runtime/WaterTemperatureBrain",), "path": "/lakes/{k}/states/waterTemp",
     "file": "brains/water-temperature/runtime/WaterTemperatureBrain/WaterTemperatureBrain.swift"},
)
PROP = re.compile(r"^\s*public\s+(?:var|let)\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*([^=/{]+?)\s*(?:=.*)?(?://.*)?$")
ENUM = re.compile(r"\benum\s+([A-Za-z_][A-Za-z0-9_]*)\s*:\s*String\b")
CASE = re.compile(r'^\s*case\s+[A-Za-z_][A-Za-z0-9_]*\s*=\s*"([^"]+)"')
PRIM = {"String": {"type": "string"}, "Int": {"type": "integer"}, "Double": {"type": "number"}, "Bool": {"type": "boolean"}}


def _files(dirs):
    for d in dirs:
        for dp, _, fs in os.walk(os.path.join(ROOT, d)):
            for f in sorted(fs):
                if f.endswith(".swift"):
                    yield os.path.join(dp, f)


def _enums(dirs) -> dict:
    out = {}
    for p in _files(dirs):
        lines = open(p, encoding="utf-8").read().splitlines()
        for i, line in enumerate(lines):
            m = ENUM.search(line)
            if not m:
                continue
            vals, depth = [], 0
            for ln in lines[i:]:
                depth += ln.count("{") - ln.count("}")
                c = CASE.match(ln)
                if c:
                    vals.append(c.group(1))
                if depth <= 0 and "}" in ln:
                    break
            out[m.group(1)] = vals
    return out


def _struct_body(path: str, name: str) -> list:
    lines = open(path, encoding="utf-8").read().splitlines()
    for i, line in enumerate(lines):
        if re.search(rf"\bstruct\s+{name}\s*:", line):
            body, depth = [], 0
            for ln in lines[i:]:
                depth += ln.count("{") - ln.count("}")
                body.append(ln)
                if depth <= 0 and len(body) > 1:
                    return body
    raise SystemExit(f"struct {name} not found in {path}")


def _type(t: str, enums: dict) -> dict:
    t = t.strip()
    if t.startswith("[") and t.endswith("]") and ":" not in t:
        return {"type": "array", "items": _type(t[1:-1], enums)}
    if t in PRIM:
        return dict(PRIM[t])
    if t in enums:
        return {"type": "string", "enum": enums[t]}
    return {"type": "object", "description": f"Swift record {t}"}


def schema(rec: dict) -> dict:
    enums = _enums(rec["sources"] + ("Sources/SectorEngine",))
    path = os.path.join(ROOT, rec["file"]) if rec.get("file") else next(p for p in _files(rec["sources"]) if re.search(rf"\bstruct\s+{rec['struct']}\s*:", open(p).read()))
    props, required = {}, []
    depth = 0
    for ln in _struct_body(path, rec["struct"])[1:]:
        if depth == 0:
            m = PROP.match(ln)
            if m:
                name, t = m.group(1), m.group(2).strip()
                optional = t.endswith("?")
                props[name] = _type(t.rstrip("?"), enums)
                if not optional:
                    required.append(name)
        depth += ln.count("{") - ln.count("}")
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"https://sector.engine/{rec['out']}", "title": rec["id"],
            "description": f"{rec['brain']} published state at {rec['path']}. GENERATED from the Swift Codable record {rec['struct']} "
                           f"({os.path.relpath(path, ROOT)}) by tools/architecture/swift_state_schema.py; do not edit.",
            "type": "object", "additionalProperties": False, "required": required, "properties": props}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    bad = 0
    for rec in RECORDS:
        text = json.dumps(schema(rec), indent=2) + "\n"
        out = os.path.join(ROOT, rec["out"])
        if a.write:
            open(out, "w", encoding="utf-8").write(text)
            print(f"wrote {rec['out']}")
        elif not os.path.exists(out) or open(out, encoding="utf-8").read() != text:
            print(f"{rec['out']}: STALE (regenerate with --write)")
            bad = 1
        else:
            print(f"{rec['out']}: OK")
    return bad


if __name__ == "__main__":
    sys.exit(main())
