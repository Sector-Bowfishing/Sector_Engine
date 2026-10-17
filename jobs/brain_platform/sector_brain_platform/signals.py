"""Shared Signal Registry (platform/registries/signals/signals.json, schema contracts/schemas/registry-signals.schema.json).

The registry owns the DEFINITION of a shared environmental signal (barometric pressure, pressure trend, precipitation, …).
It never owns which Brain consumes a signal: that is the consuming Brain's own declaration in its brain.json
(`consumes[].kind = "signal"`). Nothing here interprets a signal; no science lives in the platform.

Pure, stdlib-only. `load()` reads the committed registry when it is present; a runtime without the file gets an EMPTY registry
and every signal lookup answers `None` (unknown stays unknown: it is never silently "available").
"""
from __future__ import annotations

import json
import os

REGISTRY_VERSION = "1.0.0"
SIGNAL_STATUS = ("DECLARED", "AVAILABLE", "RETIRED")
PRODUCER_KINDS = ("brain", "provider", "platform")
# repo root = <root>/jobs/brain_platform/sector_brain_platform/.. /.. /..
_PKG = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.normpath(os.path.join(_PKG, "..", "..", "..", "platform", "registries", "signals", "signals.json"))


class SignalRegistryError(ValueError):
    pass


def validate_registry(doc: dict) -> list[str]:
    """Structural + semantic errors (the JSON Schema covers shape; this covers what jsonschema_lite cannot express per item)."""
    errs = []
    if not isinstance(doc, dict) or doc.get("schemaVersion") != REGISTRY_VERSION:
        return [f"schemaVersion must be {REGISTRY_VERSION!r}"]
    seen = set()
    for i, s in enumerate(doc.get("signals") or []):
        sid = s.get("signalId")
        if not sid:
            errs.append(f"signals[{i}]: missing signalId"); continue
        if sid in seen:
            errs.append(f"{sid}: duplicate signalId")
        seen.add(sid)
        if s.get("status") not in SIGNAL_STATUS:
            errs.append(f"{sid}: status {s.get('status')!r} not in {SIGNAL_STATUS}")
        prod = s.get("producer")
        if s.get("status") == "AVAILABLE" and not prod:
            errs.append(f"{sid}: AVAILABLE needs a producer")
        if prod is not None and (prod.get("kind") not in PRODUCER_KINDS or not prod.get("id")):
            errs.append(f"{sid}: producer must be {{kind in {PRODUCER_KINDS}, id}}")
        if s.get("status") == "DECLARED" and prod:
            errs.append(f"{sid}: DECLARED must not name a producer (set status AVAILABLE)")
    return errs


def load(path: str | None = None) -> dict:
    """-> {signalId: entry}. Missing file -> {} (the caller reports 'registry unavailable'; nothing is invented).
    A present but invalid file raises: a broken registry must not look like an empty one."""
    p = path or DEFAULT_PATH
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as fh:
        doc = json.load(fh)
    errs = validate_registry(doc)
    if errs:
        raise SignalRegistryError("; ".join(errs))
    return {s["signalId"]: s for s in doc["signals"]}


def lookup(registry: dict, signal_id: str) -> dict | None:
    return (registry or {}).get(signal_id)


def availability(registry: dict | None, signal_id: str) -> tuple[str, str]:
    """-> (AVAILABLE | UNAVAILABLE | UNKNOWN, reason) for a signal as the PLATFORM knows it (no runtime observation involved).
    No registry at all -> UNKNOWN (cannot be determined); unknown id or DECLARED/RETIRED -> UNAVAILABLE (no evidence exists)."""
    if registry is None:
        return "UNKNOWN", "signal registry not available at runtime"
    s = registry.get(signal_id)
    if s is None:
        return "UNAVAILABLE", f"signal {signal_id!r} is not defined in the Signal Registry"
    if s["status"] == "AVAILABLE":
        return "AVAILABLE", f"produced by {s['producer']['kind']}:{s['producer']['id']}"
    if s["status"] == "RETIRED":
        return "UNAVAILABLE", f"signal {signal_id!r} is RETIRED"
    return "UNAVAILABLE", f"signal {signal_id!r} is DECLARED only (no producer registered)"


def summary(registry: dict | None) -> dict:
    """Compact read model for Ops: definitions only, never consumers."""
    if registry is None:
        return {}
    out = {}
    for sid in sorted(registry):
        s = registry[sid]
        rec = {"signalId": sid, "displayName": s["displayName"], "status": s["status"]}
        for k in ("unit", "producer", "stalenessModel"):
            if s.get(k) is not None:
                rec[k] = s[k]
        out[sid] = rec
    return out
