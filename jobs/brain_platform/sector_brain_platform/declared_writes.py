"""Declared write set (Cortex 2.2 FD-01/FD-03): a Brain's brain.json must describe every path its runtime writes today.

`publishes[0].pathFamilies` is the Publisher contract (Kit P05: equal to the registry bundle). Paths the CURRENT direct writer also writes but the
Brain does not author under that contract (compatibility projections the Publisher will derive at cutover, platform-owned identity fields and
orchestrator-derived records) are declared separately in `publishes[0].legacyDirectWrites`, each with its disposition. Stdlib only."""
from __future__ import annotations

import re

DISPOSITIONS = ("PUBLISHER_COMPATIBILITY_PROJECTION", "PLATFORM_OWNED_STOP_WRITING", "ORCHESTRATOR_DERIVED")


def _rx(pattern: str) -> re.Pattern:
    p = pattern.rstrip("/")
    tail = ""
    if p.endswith("/{child}"):
        p, tail = p[: -len("/{child}")], r"(?:/.+)?"           # a registry written whole, or any child under it
    out = ""
    for seg in re.split(r"(\{[A-Za-z]+\})", p):
        out += r"[^/]+" if re.fullmatch(r"\{[A-Za-z]+\}", seg or "") else re.escape(seg)
    return re.compile("^" + out + tail + r"(?:/.+)?$")


def _norm(path: str) -> str:
    return "/" + path.strip("/")


def families(brain_json: dict) -> tuple[list[str], list[dict]]:
    pub = (brain_json.get("publishes") or [{}])[0]
    return list(pub.get("pathFamilies") or []), list(pub.get("legacyDirectWrites") or [])


def undeclared(brain_json: dict, written_paths) -> list[str]:
    """Concrete written paths matched by neither a pathFamily nor a legacyDirectWrite."""
    fams, legacy = families(brain_json)
    rxs = [_rx(f) for f in fams] + [_rx(e["path"]) for e in legacy]
    return sorted({_norm(p) for p in written_paths if not any(r.match(_norm(p)) for r in rxs)})


def unused_legacy(brain_json: dict, written_paths) -> list[str]:
    """legacyDirectWrites no written path hits: a declaration of a write that does not happen."""
    _, legacy = families(brain_json)
    paths = [_norm(p) for p in written_paths]
    return [e["path"] for e in legacy if not any(_rx(e["path"]).match(p) for p in paths)]


def problems(brain_json: dict) -> list[str]:
    fams, legacy = families(brain_json)
    out = []
    for e in legacy:
        if set(e) - {"path", "disposition", "ref"} or not {"path", "disposition", "ref"} <= set(e):
            out.append(f"{e}: needs exactly path, disposition, ref")
        elif e["disposition"] not in DISPOSITIONS:
            out.append(f"{e['path']}: unknown disposition {e['disposition']!r}")
        if e.get("path") in fams:
            out.append(f"{e.get('path')}: declared both as a contract family and a legacy direct write")
    return out
