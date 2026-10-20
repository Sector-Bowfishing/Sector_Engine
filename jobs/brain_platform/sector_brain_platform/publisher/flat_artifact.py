"""Generic publish-artifact-v2 builder for a Brain whose legacy writer sends ONE flat multi-path update dictionary (SHADOW contract only).

Shared so that each Brain declares only its routing facts (which legacy paths it does not author and why, which whole nodes are split into children, which
optional children are cleared by absence, the scope of each lake path, and its input fingerprint) instead of copying the builder. Used by Sector
Intelligence, Lake and Water Temperature. Wind, Fish and Water Clarity keep their certified builders unchanged.

Rules (the same ones every certified builder follows):
  * the routing authority for every path is the Publisher registry; a path no registered family authors is reported in `dropped` with its declared
    classification, or the build FAILS CLOSED (`ArtifactBuildError`) when nothing covers it;
  * whole `/brains/{id}` and `/health/brains/{id}` nodes are split into CHILDREN; `publication` / `certification` stay Publisher-owned;
  * null / missing never means delete. The only inferred removal is a declared optional child (e.g. `lastError`) absent from a whole-node registry
    write, emitted as a typed DELETE with the closed reason `OPTIONAL_CHILD_CLEARED` (the legacy whole-node write clears it the same way);
  * lineage is truthful: `consumed` is passed through only when recorded (absent = unknown, never []); releases are NONE unless the Brain has one;
  * no clock, no randomness, no I/O: same updates + same context => byte-identical artifact. The fingerprint, volatile contract and seal are the Publisher's.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field

from .registry import default_registry
from .handoff import seal_bundle

OPTIONAL_CHILD_CLEARED = "OPTIONAL_CHILD_CLEARED"


class ArtifactBuildError(ValueError):
    pass


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(obj) -> str:
    return "sha256:" + hashlib.sha256(canonical(obj)).hexdigest()


_ABSENT = object()


def normalize(v, path=""):
    """The value as RTDB would store it: None keys and empty containers vanish (absence, never a delete). Returns _ABSENT if nothing remains."""
    if v is None:
        return _ABSENT
    if isinstance(v, float) and not math.isfinite(v):
        raise ArtifactBuildError(f"non-finite number at {path or '/'}")
    if isinstance(v, dict):
        out = {}
        for k in sorted(v):
            n = normalize(v[k], f"{path}/{k}")
            if n is not _ABSENT:
                out[k] = n
        return out or _ABSENT
    if isinstance(v, (list, tuple)):
        out = []
        for i, x in enumerate(v):
            n = normalize(x, f"{path}/{i}")
            if n is _ABSENT:
                if x is None:
                    raise ArtifactBuildError(f"null inside a list at {path}/{i}: cannot be omitted without shifting indices; encode UNKNOWN explicitly")
                continue
            out.append(n)
        return out or _ABSENT
    return v


@dataclass(frozen=True)
class BuildContext:
    """Everything the artifact needs that the Brain must not invent (supplied by the runner; tests pin it)."""
    generated_at: str                 # ISO-8601 UTC ...Z; the run's `now`
    execution_id: str                 # UUIDv4 of this run (ONE per logical artifact)
    code_version: str                 # the deployed code identity
    lifecycle: str = "CALIBRATION"
    review_status: str = "UNREVIEWED"
    validation_status: str = "NOT_VALIDATED"


@dataclass(frozen=True)
class NotAuthored:
    """A legacy path family the Brain does not author, with who produces it instead (the direct-write audit's table, as data)."""
    pattern: str                      # full-match regex on the path
    row: str
    classification: str               # PLATFORM_OWNED | LEGACY_READER_DEPENDENCY | ...
    mechanism: str                    # STOP_WRITING | ORCHESTRATOR_DERIVED | ...
    target_owner: str


@dataclass(frozen=True)
class FlatBrain:
    """The routing facts of one Brain (data only)."""
    brain_id: str
    bundle_id: str
    schema_order: tuple               # section schema ids, in artifact order
    scopes: tuple = ()                # ((regex, scope), ...) for lake-level paths; first match wins
    not_authored: tuple = ()          # NotAuthored rows
    clear_absent_children: tuple = () # optional /brains/{id} children cleared by a whole-node write that omits them


@dataclass
class BuildResult:
    artifact: dict | None = None
    dropped: list = field(default_factory=list)
    unsupported: list = field(default_factory=list)
    omitted_unknown: int = 0
    deletes: list = field(default_factory=list)


def _expand(brain: FlatBrain, flat: dict):
    out = []
    for key in sorted(flat):
        val = flat[key]
        path = "/" + key.lstrip("/")
        if path in (f"/brains/{brain.brain_id}", f"/health/brains/{brain.brain_id}"):
            if not isinstance(val, dict):
                raise ArtifactBuildError(f"{path} must be an object")
            out += [(f"{path}/{c}", val[c]) for c in sorted(val)]
        else:
            out.append((path, val))
    return out


def registry_children(updates: dict, brain_id: str) -> dict:
    """The /brains/{id} children of this run (whole-node or child writes), for an input fingerprint."""
    node = updates.get(f"brains/{brain_id}") or updates.get(f"/brains/{brain_id}") or {}
    return dict(node) if isinstance(node, dict) else {}


def build_flat_artifact(brain: FlatBrain, updates: dict, ctx: BuildContext, *, input_fingerprint: str, registry=None, consumed=None,
                        knowledge_release=("NONE", "NONE", "NONE")) -> BuildResult:
    reg = registry or default_registry()
    specs = [reg.spec(s) for s in reg.schemas_for(brain.brain_id)]
    res = BuildResult()
    sec: dict[tuple, list] = {}

    def authoring(path, delete=False):
        return next((sp for sp in specs if reg.authorizing_family(sp, path, delete=delete) is not None), None)

    def scope(path, schema):
        if schema != brain.schema_order[0]:
            return None
        return next((sc for rx, sc in brain.scopes if re.fullmatch(rx, path)), None)

    def not_authored(path):
        pr = reg.derived_target(brain.brain_id, path)
        if pr is not None:
            return {"path": path, "row": pr.id, "projection": pr.id, "classification": pr.classification, "mechanism": "PUBLISHER_DERIVED",
                    "targetOwner": pr.owner, "why": f"Publisher-derived compatibility projection ({pr.id}); retirement gate: {pr.retirement_gate}"}
        for na in brain.not_authored:
            if re.fullmatch(na.pattern, path):
                return {"path": path, "row": na.row, "classification": na.classification, "mechanism": na.mechanism, "targetOwner": na.target_owner,
                        "why": f"{na.row}: {na.mechanism}"}
        return None

    registry_written = any(k.lstrip("/") == f"brains/{brain.brain_id}" for k in updates)
    for path, val in _expand(brain, updates):
        if val is None and path.startswith("/activity/"):
            res.dropped.append({"path": path, "row": "activity-retention", "classification": "PLATFORM_OWNED", "mechanism": "STOP_WRITING",
                                "targetOwner": "Platform maintenance (bounded-ring retention)", "why": "a Brain's artifact never deletes events"})
            continue
        spec = authoring(path)
        if spec is None:
            why = not_authored(path)
            if why is None:
                res.unsupported.append({"path": path, "reason": f"no {brain.brain_id} schema family, projection or classification covers this path"})
            else:
                res.dropped.append(why)
            continue
        n = normalize(val, path)
        if n is _ABSENT:
            res.omitted_unknown += 1
            continue
        if n != val:
            res.omitted_unknown += 1
        sec.setdefault((spec.schema_id, scope(path, spec.schema_id)), []).append({"op": "SET", "path": path, "value": n})
    if res.unsupported:
        raise ArtifactBuildError(f"paths no {brain.brain_id} registration covers (extend the Publisher registry, reviewed, instead of emitting them): "
                                 + ", ".join(sorted(u["path"] for u in res.unsupported)[:8]))

    if registry_written:
        node = registry_children(updates, brain.brain_id)
        for child in brain.clear_absent_children:
            if node.get(child) is None:
                path = f"/brains/{brain.brain_id}/{child}"
                spec = authoring(path, delete=True)
                if spec is None or OPTIONAL_CHILD_CLEARED not in spec.delete_reasons:
                    raise ArtifactBuildError(f"no {brain.brain_id} schema permits clearing {path}")
                sec.setdefault((spec.schema_id, None), []).append({"op": "DELETE", "path": path, "reason": OPTIONAL_CHILD_CLEARED})
                res.deletes.append({"path": path, "reason": OPTIONAL_CHILD_CLEARED})

    if not sec:
        return res
    sections = []
    for (schema, sc) in sorted(sec, key=lambda k: (brain.schema_order.index(k[0]), k[1] or "")):
        s = {"artifactSchema": schema, "mutations": sorted(sec[(schema, sc)], key=lambda m: m["path"])}
        if sc:
            s["scope"] = sc
        sections.append(s)
    kr, mref, msha = knowledge_release
    art = seal_bundle(brain_id=brain.brain_id, bundle_id=brain.bundle_id, sections=sections, lifecycle=ctx.lifecycle, review_status=ctx.review_status,
                      validation_status=ctx.validation_status, generated_at=ctx.generated_at, execution_id=ctx.execution_id, code_version=ctx.code_version,
                      input_fingerprint=input_fingerprint, knowledge_release=kr, manifest_ref=mref, manifest_sha256=msha, registry=reg, consumed=consumed)
    art["lineage"]["artifactId"] = sha(art)           # content address of the sealed envelope
    res.artifact = art
    return res
