"""ACTUAL consumption lineage (consumption-lineage-v1): what an execution really read, recorded at the one generic place a Brain reads
shared state — the platform RTDB client (BrainRtdb / DryRunStore `get`). Nothing here copies a declared dependency list: an entry exists
only because a read happened. Declared vs actual is reconciled later (dependency_health.reconcile_consumption).

Identity of a read is derived from the platform's OWNERSHIP contract (keys.BRAINS slot table, ownership.path_allowed, ownership.SOURCE_OWNERS):
the owner of a path is whoever the contract lets write it. No Brain id, signal id or provider id is written in this module.

Entries use the merged G1/G2 contract exactly (execution_health.CONSUMED_KEYS): dependencyId, dependencyType, ref, stateVersion,
fingerprint, artifactId, generatedAt, evidenceObservedAt, publishedAt, consumedAt, freshnessStatus, staleAfter, expiresAt. Fields the read
did not yield are ABSENT (never invented). Serialisation is deterministic and read-order independent: reads are sorted, then folded with
commutative rules (newest evidence/generated/published, earliest staleAfter/expiresAt, worst freshness, first-in-sorted-order identity).
"""
from __future__ import annotations

import datetime as dt
import re

from .enums import FRESHNESS_STATUS
from .keys import BRAINS
from .ownership import PLATFORM_ONLY, SOURCE_OWNERS, path_allowed
from .timeutil import iso, parse_time

CONSUMPTION_VERSION = "consumption-lineage-v1"
CONSUMED_KEYS = ("dependencyId", "dependencyType", "ref", "stateVersion", "fingerprint", "artifactId", "generatedAt", "evidenceObservedAt",
                 "publishedAt", "consumedAt", "freshnessStatus", "staleAfter", "expiresAt")     # == execution_health.CONSUMED_KEYS (tested)
PREFIX_TYPE = {"brain": "BRAIN", "signal": "ENVIRONMENTAL_SIGNAL", "provider": "PROVIDER_DATA", "registry": "PLATFORM_REGISTRY"}
DEPENDENCY_ID = re.compile(r"^(brain|signal|provider|registry):[a-z][a-z0-9]*(-[a-z0-9]+)*$")
TIME_KEYS = ("generatedAt", "evidenceObservedAt", "publishedAt", "consumedAt", "staleAfter", "expiresAt")
_NEWEST, _EARLIEST = ("generatedAt", "evidenceObservedAt", "publishedAt", "consumedAt"), ("staleAfter", "expiresAt")
_FRESH_RANK = {"FRESH": 0, "UNKNOWN": 1, "UNAVAILABLE": 2, "STALE": 3, "EXPIRED": 4}
_SLOT_OWNER = {v[0]: b for b, v in BRAINS.items()}
_SNAPSHOT_OWNER = {v[1]: b for b, v in BRAINS.items()}
_IGNORED_ROOTS = PLATFORM_ONLY | {"activity", "health"}       # platform nodes and health/jobs are never a Brain's dependency; health/brains|sources handled below


# ------------------------------------------------------------------------------------------------------------ validation / normalisation
def validate_consumed(entries) -> list[str]:
    """Errors for a consumed[] list: a list of dicts with a valid dependencyId, a type matching its prefix, only contract keys, parseable UTC
    times, a vocabulary freshness word and no duplicate dependency. [] == valid."""
    if not isinstance(entries, list):
        return ["consumed must be a list"]
    errs, seen = [], set()
    for i, e in enumerate(entries):
        tag = f"consumed[{i}]"
        if not isinstance(e, dict):
            errs.append(f"{tag}: not an object"); continue
        did = e.get("dependencyId")
        if not isinstance(did, str) or not DEPENDENCY_ID.match(did):
            errs.append(f"{tag}: dependencyId {did!r} must be <brain|signal|provider|registry>:<id>"); continue
        if did in seen:
            errs.append(f"{tag}: duplicate dependency {did}")
        seen.add(did)
        want = PREFIX_TYPE[did.split(":", 1)[0]]
        if e.get("dependencyType") not in (None, want):
            errs.append(f"{tag}: dependencyType {e.get('dependencyType')!r} does not match {did} ({want})")
        extra = sorted(set(e) - set(CONSUMED_KEYS))
        if extra:
            errs.append(f"{tag}: unknown keys {extra}")
        for k in TIME_KEYS:
            if k in e and parse_time(e[k]) is None:
                errs.append(f"{tag}: {k} must be ISO-8601 UTC")
        if "freshnessStatus" in e and e["freshnessStatus"] not in FRESHNESS_STATUS:
            errs.append(f"{tag}: freshnessStatus {e['freshnessStatus']!r} not in {FRESHNESS_STATUS}")
        for k in ("ref", "stateVersion", "fingerprint", "artifactId"):
            if k in e and not (isinstance(e[k], str) and e[k]):
                errs.append(f"{tag}: {k} must be a non-empty string")
    return errs


def finalize(entries) -> list[dict]:
    """Canonical, deterministic consumed[]: contract keys only, dependencyType filled from the id prefix, sorted by dependencyId.
    Raises ValueError when invalid (the producer must fix its lineage, the platform never repairs it silently)."""
    errs = validate_consumed(entries)
    if errs:
        raise ValueError("; ".join(errs))
    out = []
    for e in entries:
        c = {k: e[k] for k in CONSUMED_KEYS if e.get(k) is not None}
        c["dependencyType"] = PREFIX_TYPE[c["dependencyId"].split(":", 1)[0]]
        out.append(c)
    return sorted(out, key=lambda c: c["dependencyId"])


def merge_reads(reads: list[tuple[str, dict]]) -> list[dict]:
    """[(dependencyId, partial entry)] from any number of reads, in ANY order -> one entry per dependency. Order independent: reads are sorted by
    (dependencyId, ref, json) and folded with commutative rules: newest generatedAt/evidenceObservedAt/publishedAt/consumedAt, earliest
    staleAfter/expiresAt, worst freshnessStatus, and the first identity (ref/stateVersion/fingerprint/artifactId) in sorted order."""
    import json
    by: dict[str, dict] = {}
    for did, part in sorted(reads, key=lambda r: (r[0], r[1].get("ref") or "", json.dumps(r[1], sort_keys=True, default=str))):
        cur = by.setdefault(did, {"dependencyId": did})
        for k, v in part.items():
            if v is None or k == "dependencyId":
                continue
            if k in _NEWEST:
                cur[k] = max(cur[k], v) if k in cur else v
            elif k in _EARLIEST:
                cur[k] = min(cur[k], v) if k in cur else v
            elif k == "freshnessStatus":
                cur[k] = max(cur.get(k, "FRESH"), v, key=lambda s: _FRESH_RANK.get(s, 1))
            else:
                cur.setdefault(k, v)
    return finalize(list(by.values()))


# ------------------------------------------------------------------------------------------------------------ classification of a read
def _owner_by_contract(path: str) -> str | None:
    """The Brain the ownership contract lets write `path` (unique), else None."""
    owners = [b for b in BRAINS if path_allowed(b, path)]
    return owners[0] if len(owners) == 1 else None


def _state_fields(value) -> dict:
    """Lineage a per-lake state envelope (contract section 4) or a registry node yields. Only what is present."""
    if not isinstance(value, dict):
        return {}
    out: dict = {}
    fr = value.get("freshness") if isinstance(value.get("freshness"), dict) else {}
    prov = value.get("provenance") if isinstance(value.get("provenance"), dict) else {}
    gen = fr.get("generatedAt") or prov.get("generatedAt") or value.get("generatedAt")
    if gen:
        out["generatedAt"] = gen
    ev = fr.get("sourceObservationAt") or fr.get("evidenceObservedAt") or value.get("evidenceObservedAt") or value.get("sourceObservationAt")
    if ev:
        out["evidenceObservedAt"] = ev
    if fr.get("freshUntil") or value.get("staleAfter"):
        out["staleAfter"] = fr.get("freshUntil") or value.get("staleAfter")
    for k in ("publishedAt", "expiresAt"):
        if fr.get(k) or value.get(k):
            out[k] = fr.get(k) or value[k]
    if fr.get("freshnessStatus") in FRESHNESS_STATUS or value.get("freshnessStatus") in FRESHNESS_STATUS:
        out["freshnessStatus"] = fr.get("freshnessStatus") or value["freshnessStatus"]
    elif fr.get("stale") is not None or fr.get("evidenceStale") is not None:
        out["freshnessStatus"] = "STALE" if (fr.get("stale") is True or fr.get("evidenceStale") is True) else "FRESH"
    sv = value.get("stateVersion") or prov.get("brainVersion") or value.get("version")
    if sv is not None and not isinstance(sv, (dict, list)):
        out["stateVersion"] = str(sv)
    if isinstance(value.get("fingerprint"), str):
        out["fingerprint"] = value["fingerprint"]
    if isinstance(value.get("artifactId"), str):
        out["artifactId"] = value["artifactId"]
    return out


def _source_fields(value, health) -> dict:
    out: dict = {}
    v = value if isinstance(value, dict) else {}
    h = health if isinstance(health, dict) else {}
    ev = v.get("latestObservationAt") or v.get("lastObservationAt") or h.get("lastObservationAt")
    if ev:
        out["evidenceObservedAt"] = ev
    if v.get("latestIssuedAt"):
        out["generatedAt"] = v["latestIssuedAt"]
    ref_t = parse_time(ev or v.get("latestIssuedAt"))
    thr = v.get("staleThresholdHours")
    if ref_t is not None and isinstance(thr, (int, float)) and not isinstance(thr, bool):
        out["staleAfter"] = iso(ref_t + dt.timedelta(hours=float(thr)))       # the OWNER's own threshold, applied mechanically
    return out


def classify_read(path: str, value, *, self_brain: str | None = None) -> list[tuple[str, dict]]:
    """A GET of `path` that returned `value` -> [(dependencyId, partial entry)]. Own state (what `self_brain` may write) is not a dependency.
    Unknown roots yield nothing (reported via ConsumptionRecorder.unclassified)."""
    p = [s for s in path.strip("/").split("/") if s]
    if not p:
        return []
    root = p[0]
    ref = "/" + "/".join(p)
    out: list[tuple[str, dict]] = []

    def brain(bid, fields=None, r=ref):
        if bid and bid != self_brain:
            out.append((f"brain:{bid}", {"ref": r, **(fields or {})}))

    if root == "sources" and len(p) >= 2:
        if not (self_brain and SOURCE_OWNERS.get(p[1]) == self_brain):
            out.append((f"provider:{p[1]}", {"ref": f"/sources/{p[1]}", **_source_fields(value if len(p) == 2 else None, None)}))
    elif root == "health" and len(p) >= 3 and p[1] == "sources":
        if not (self_brain and SOURCE_OWNERS.get(p[2]) == self_brain):
            out.append((f"provider:{p[2]}", {"ref": f"/sources/{p[2]}", **_source_fields(None, value if len(p) == 3 else None)}))
    elif root == "health" and len(p) >= 3 and p[1] == "brains":
        brain(p[2], r=f"/brains/{p[2]}")
    elif root in _IGNORED_ROOTS:
        return []
    elif root == "brains":
        if len(p) == 1:
            if isinstance(value, dict):
                for bid in sorted(value):
                    brain(bid, _state_fields(value[bid]), f"/brains/{bid}")
            else:
                out.append(("registry:brains", {"ref": "/brains"}))
        else:
            fields = _state_fields(value) if len(p) == 2 else ({"stateVersion": str(value)} if len(p) == 3 and p[2] == "version" and value is not None and not isinstance(value, (dict, list)) else {})
            brain(p[1], fields, f"/brains/{p[1]}")
    elif root == "validation" and len(p) >= 2:
        brain(p[1], r=f"/validation/{p[1]}")
    elif root == "species":
        brain(_owner_by_contract("species/x"), r="/species")
    elif root == "lakes":
        if len(p) == 1 and isinstance(value, dict):
            for k in sorted(value):
                out += classify_read(f"lakes/{k}", value[k], self_brain=self_brain)
        elif len(p) == 2 and isinstance(value, dict):
            for sec in ("states", "profiles"):
                for slot, sv in sorted((value.get(sec) or {}).items()) if isinstance(value.get(sec), dict) else []:
                    brain(_SLOT_OWNER.get(slot), _state_fields(sv) if sec == "states" else {}, f"/lakes/{p[1]}/{sec}/{slot}")
            for sec in ("brain", "speciesPresence"):
                if sec in value:
                    brain(_owner_by_contract(f"lakes/{p[1]}/{sec}"), _state_fields(value[sec]) if sec == "brain" else {}, f"/lakes/{p[1]}/{sec}")
        elif len(p) >= 4 and p[2] in ("states", "profiles"):
            brain(_SLOT_OWNER.get(p[3]), _state_fields(value) if p[2] == "states" and len(p) == 4 else {}, f"/lakes/{p[1]}/{p[2]}/{p[3]}")
        elif len(p) >= 4 and p[2] == "validation":
            brain(p[3], r=f"/lakes/{p[1]}/validation/{p[3]}")
        elif len(p) >= 3 and p[2] in ("brain", "speciesPresence"):
            brain(_owner_by_contract(f"lakes/{p[1]}/{p[2]}"), _state_fields(value) if p[2] == "brain" and len(p) == 3 else {}, f"/lakes/{p[1]}/{p[2]}")
    elif root == "lakeFleet":
        if len(p) == 1 and isinstance(value, dict):
            for k in sorted(value):
                out += classify_read(f"lakeFleet/{k}", value[k], self_brain=self_brain)
        elif len(p) == 2 and isinstance(value, dict):
            for sec in ("slots", "readiness", "modelVersions"):
                for slot in sorted(value.get(sec) or {}) if isinstance(value.get(sec), dict) else []:
                    brain(_SLOT_OWNER.get(slot), {"stateVersion": str(value[sec][slot])} if sec == "modelVersions" and not isinstance(value[sec][slot], (dict, list)) else {}, f"/lakeFleet/{p[1]}/{sec}/{slot}")
        elif len(p) >= 4 and p[2] in ("slots", "readiness", "modelVersions"):
            brain(_SLOT_OWNER.get(p[3]), r=f"/lakeFleet/{p[1]}/{p[2]}/{p[3]}")
    elif root == "snapshots" and len(p) >= 3 and p[2] == "latest":
        if len(p) == 3 and isinstance(value, dict):
            versions = value.get("brainVersions") if isinstance(value.get("brainVersions"), dict) else {}
            for f in sorted(value):
                bid = _SNAPSHOT_OWNER.get(f)
                if bid:
                    fields = _state_fields(value[f])
                    if versions.get(bid) is not None and "stateVersion" not in fields:
                        fields["stateVersion"] = str(versions[bid])
                    brain(bid, fields, f"/snapshots/{p[1]}/latest/{f}")
        elif len(p) >= 4 and p[3] == "brainVersions" and len(p) >= 5:
            brain(p[4], {"stateVersion": str(value)} if value is not None and not isinstance(value, (dict, list)) else {}, f"/snapshots/{p[1]}/latest/brainVersions/{p[4]}")
        elif len(p) >= 4:
            brain(_SNAPSHOT_OWNER.get(p[3]), _state_fields(value) if len(p) == 4 else {}, f"/snapshots/{p[1]}/latest/{p[3]}")
    return out


class ConsumptionRecorder:
    """Attached to a platform store (`BrainRtdb(..., recorder=...)` / `DryRunStore(..., recorder=...)`): every successful GET is classified and
    kept; `entries()` is the deterministic consumed[] of the execution so far. A Brain's own state is never a dependency of itself."""

    def __init__(self, brain_id: str | None = None, clock=None):
        self.brain_id = brain_id
        self._clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self.reads: list[tuple[str, dict]] = []
        self.unclassified: list[str] = []
        self.read_count = 0

    def observe(self, path: str, value, shallow: bool = False) -> None:
        self.read_count += 1
        if value is None:
            return                                                   # nothing was consumed from an absent node
        found = classify_read(path, None if shallow else value, self_brain=self.brain_id)
        if not found:
            root = path.strip("/").split("/")[0] if path.strip("/") else ""
            if root and root not in _IGNORED_ROOTS and not (self.brain_id and path_allowed(self.brain_id, path)):
                self.unclassified.append("/" + path.strip("/"))
            return
        at = iso(self._clock())
        for did, part in found:
            self.reads.append((did, {**part, "consumedAt": at}))

    def entries(self) -> list[dict]:
        return merge_reads(self.reads)
