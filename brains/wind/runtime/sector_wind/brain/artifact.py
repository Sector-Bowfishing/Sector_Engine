"""Wind publish-artifact builder for Publisher V2 (envelope v2, bundle `wind-publication-v1`). SHADOW CONTRACT ONLY. NOT wired into wind-hourly.

ONE Wind execution -> ONE `publish-artifact-v2` -> ONE Publisher evaluation -> ONE atomic plan (SKIP or SHADOW_READY, or the whole artifact is rejected).

Wind still computes domain truth with the unchanged `publish.publish()`; this module re-expresses the PATCH dictionaries that run would send as the
sections of one sealed bundle. It authors ONLY what the Publisher's Wind registration authorises:
  * the routing decision for every path comes from the Publisher registry (`default_registry()`: path families, derived compatibility targets) and the
    machine-readable `compat.LEGACY_PATH_TABLE`; Wind keeps no ownership list of its own, so Wind ownership cannot drift from the Publisher;
  * paths the legacy writer produced that Wind no longer authors (lake identity, snapshot compatibility copies, generic job/process health, activity pruning)
    are reported in `dropped` with their legacy-table row, never emitted;
  * null / missing NEVER means delete. A removal exists only as a typed DELETE with a closed-vocabulary reason, either requested explicitly by the caller
    (`removals`) or for the single declared optional child `/brains/wind/lastError` (see `_last_error`);
  * the semantic fingerprint, the volatile contract (`wind-volatile-v1`) and the bundle seal are the PUBLISHER's (`seal_bundle`); nothing is re-implemented here;
  * no clock, no randomness: same patches + same BuildContext => byte-identical artifact.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from dataclasses import dataclass, field

from . import contract as C
from . import writer as _platform_path  # noqa: F401  (imports the platform through the writer; vendored next to main.py in the image)
from sector_brain_platform.publisher import default_registry, seal_bundle
from sector_brain_platform.publisher.compat import row_for
from sector_brain_platform.publisher.registry import WIND_BUNDLE

WIND = C.BRAIN_ID
SCHEMA_LAKE, SCHEMA_REGISTRY, SCHEMA_SOURCES = "wind-lake-state-v1", "wind-registry-v1", "wind-source-registry-v1"
LAST_ERROR_PATH = f"/brains/{WIND}/lastError"
LAST_ERROR_CLEARED = "OPTIONAL_CHILD_CLEARED"

_LAKE = r"([A-Za-z0-9_]+)"
#: Baseline scopes WITHIN wind-lake-state-v1 (each (schema, scope) section has its own baseline, so the slow parts SKIP while the hourly state changes).
SCOPE_LIVE, SCOPE_STATIC, SCOPE_READINESS = "lake-live", "lake-static", "fleet-readiness"
_SCOPES = [(rf"/lakes/{_LAKE}/states/wind", SCOPE_LIVE), (rf"/lakeFleet/{_LAKE}/slots/wind", SCOPE_LIVE),
           (rf"/lakes/{_LAKE}/profiles/wind", SCOPE_STATIC), (rf"/lakes/{_LAKE}/validation/wind", SCOPE_STATIC), (rf"/lakeFleet/{_LAKE}/modelVersions/wind", SCOPE_STATIC),
           (rf"/lakeFleet/{_LAKE}/readiness/wind", SCOPE_READINESS)]
_ORDER = (SCHEMA_LAKE, SCHEMA_REGISTRY, SCHEMA_SOURCES)


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


def _parse(s):
    try:
        return dt.datetime.fromisoformat(s[:-1] + "+00:00") if isinstance(s, str) and s.endswith("Z") else None
    except ValueError:
        return None


def _iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class BuildContext:
    generated_at: str                 # ISO-8601 UTC; the run's `now`
    execution_id: str                 # UUIDv4 of this wind-hourly run (ONE per logical artifact)
    code_version: str                 # Wind's own commit (sha12), not the orchestrator's
    evidence_sha256: str = "NONE"     # sha256 of validation_evidence.json (an input digest)
    knowledge_release: str = "NONE"   # NONE until Wind defines a canonical release (release/manifest/sha must be all NONE or all declared)
    manifest_ref: str = "NONE"
    manifest_sha256: str = "NONE"
    lifecycle: str = "CALIBRATION"
    review_status: str = "UNREVIEWED"
    validation_status: str = "NOT_VALIDATED"


@dataclass
class BuildResult:
    artifact: dict | None = None
    dropped: list = field(default_factory=list)       # [{path, row, classification, mechanism, targetOwner, why}]  Wind no longer authors these
    unsupported: list = field(default_factory=list)   # [{path, reason}]  no family and no legacy row: reported, not published
    omitted_unknown: int = 0                          # null/empty values omitted (RTDB-equivalent absence; never a delete)
    deletes: list = field(default_factory=list)       # [{path, reason}]  explicit typed deletes emitted

    @property
    def artifacts(self) -> list:
        return [self.artifact] if self.artifact else []


def merge_patches(patches) -> dict:
    flat: dict = {}
    for p in patches:
        flat.update(p)
    return flat


def _scope(path, schema):
    if schema != SCHEMA_LAKE:
        return None
    return next((sc for rx, sc in _SCOPES if re.fullmatch(rx, path)), None)


def _freshness(states: dict) -> dict:
    """evidenceObservedAt / staleAfter / freshnessStatus from the Wind state records using Wind's EXISTING thresholds (no threshold change)."""
    if not states:
        return {"freshnessStatus": "UNKNOWN"}
    obs, stale_after, kinds, stale = [], [], [], False
    for s in states.values():
        t = _parse(s.get("observationTime")) or _parse(s.get("forecastGeneratedAt"))
        if t:
            obs.append(t)
        gen = _parse((s.get("provenance") or {}).get("generatedAt"))
        cyc = _parse(s.get("forecastGeneratedAt"))
        if gen:
            stale_after.append(gen + dt.timedelta(minutes=C.STALE_GENERATED_MIN))
        if cyc:
            stale_after.append(cyc + dt.timedelta(hours=C.STALE_FORECAST_CYCLE_H))
        kinds.append(s.get("kind"))
        stale = stale or bool(s.get("stale"))
    fr = {}
    if obs:
        fr["evidenceObservedAt"] = _iso(max(obs))
    if stale_after:
        fr["staleAfter"] = _iso(min(stale_after))
    fr["freshnessStatus"] = "UNAVAILABLE" if all(k == "unavailable" for k in kinds) else ("STALE" if stale else "FRESH")
    return fr


class _Router:
    def __init__(self, registry):
        self.reg = registry
        self.specs = [registry.spec(s) for s in registry.schemas_for(WIND)]

    def authoring_spec(self, path, delete=False):
        for sp in self.specs:
            if self.reg.authorizing_family(sp, path, delete=delete) is not None:
                return sp
        return None

    def not_authored(self, path):
        """Why Wind no longer authors `path` (or None if it simply has no home): Publisher-derived target first, then the machine-readable legacy table."""
        pr = self.reg.derived_target(WIND, path)
        if pr is not None:
            lr = row_for(path)
            return {"path": path, "row": lr.id if lr else pr.id, "projection": pr.id, "classification": pr.classification, "mechanism": "PUBLISHER_DERIVED", "targetOwner": pr.owner,
                    "why": f"Publisher-derived compatibility projection ({pr.id}); retirement gate: {pr.retirement_gate}"}
        row = row_for(path)
        if row is not None:
            return {"path": path, "row": row.id, "classification": row.classification, "mechanism": row.mechanism, "targetOwner": row.target_owner,
                    "why": f"legacy path table row {row.id}: {row.mechanism}"}
        return None


def _expand(flat):
    """Whole-node writes of the legacy writer -> child paths. Returns [(path, value)]; /brains/wind/lastError handled separately."""
    out = []
    for key in sorted(flat):
        val = flat[key]
        path = "/" + key
        if key in (f"brains/{WIND}", f"health/brains/{WIND}"):
            if not isinstance(val, dict):
                raise ArtifactBuildError(f"{key} must be an object")
            out += [(f"{path}/{c}", val[c]) for c in sorted(val)]
        else:
            out.append((path, val))
    return out


def _last_error(flat):
    """The ONE inferred removal, declared in the Publisher registration (delete family /brains/wind/lastError, reason OPTIONAL_CHILD_CLEARED): the legacy
    registry node carries `lastError: None` when the run had no error. Emitting a typed DELETE keeps a stale error from persisting after recovery. It is
    idempotent (an artifact that always carries the DELETE while healthy is semantically identical run to run, so it SKIPs) and it is the only place a None
    is read as an explicit fact; every other None is plain absence."""
    node = flat.get(f"brains/{WIND}")
    return isinstance(node, dict) and "lastError" in node and node["lastError"] is None


def build_artifacts(patches, ctx: BuildContext, registry=None, removals=()) -> BuildResult:
    """patches: the list of {flat-rtdb-key: value} dicts one wind-hourly publish() run would PATCH (e.g. DryRunWriter.patches).
    removals: explicit [{path, reason}] the PRODUCER decided (e.g. a lake left the fleet): validated here and again by the Publisher."""
    reg = registry or default_registry()
    router = _Router(reg)
    res = BuildResult()
    flat = merge_patches(patches)
    sec: dict[tuple, list] = {}
    states = {}

    def add(spec, path, mutation):
        sec.setdefault((spec.schema_id, _scope(path, spec.schema_id)), []).append(mutation)

    for path, val in _expand(flat):
        spec = router.authoring_spec(path)
        if spec is None:
            why = router.not_authored(path)
            (res.dropped if why else res.unsupported).append(why or {"path": path, "reason": "no Wind schema family and no legacy-table row covers this path"})
            continue
        if path == LAST_ERROR_PATH and val is None:
            continue                                                  # handled by _last_error below (explicit typed DELETE), never as a SET
        n = normalize(val, path)
        if n is _ABSENT:
            res.omitted_unknown += 1                                  # null/empty = absence; nothing is deleted
            continue
        if n != val:
            res.omitted_unknown += 1
        if re.fullmatch(rf"/lakes/{_LAKE}/states/wind", path) and isinstance(n, dict):
            states[path] = n
        add(spec, path, {"op": "SET", "path": path, "value": n})

    dels = [{"path": r["path"], "reason": r["reason"]} for r in removals]
    if _last_error(flat):
        dels.append({"path": LAST_ERROR_PATH, "reason": LAST_ERROR_CLEARED})
    set_paths = {m["path"] for ms in sec.values() for m in ms}
    for d in sorted(dels, key=lambda d: d["path"]):
        spec = router.authoring_spec(d["path"], delete=True)
        if spec is None:
            raise ArtifactBuildError(f"no Wind schema permits deleting {d['path']}")
        if d["reason"] not in spec.delete_reasons:
            raise ArtifactBuildError(f"delete reason {d['reason']!r} for {d['path']} is not in the closed vocabulary {list(spec.delete_reasons)}")
        if d["path"] in set_paths:
            raise ArtifactBuildError(f"{d['path']} is both SET and DELETEd in one run")
        add(spec, d["path"], {"op": "DELETE", "path": d["path"], "reason": d["reason"]})
        res.deletes.append(d)

    if not sec:
        return res
    sections = []
    for (schema, scope) in sorted(sec, key=lambda k: (_ORDER.index(k[0]), k[1] or "")):
        s = {"artifactSchema": schema, "mutations": sorted(sec[(schema, scope)], key=lambda m: m["path"])}
        if scope:
            s["scope"] = scope
        if schema == SCHEMA_LAKE:
            s["freshness"] = _freshness(states)
        sections.append(s)
    in_fp = sha({"states": {k: {"obs": s.get("observationTime"), "fcst": s.get("forecastGeneratedAt")} for k, s in sorted(states.items())},
                 "evidence": ctx.evidence_sha256, "model": C.CANDIDATE_MODEL, "brainVersion": C.BRAIN_VERSION})
    art = seal_bundle(brain_id=WIND, bundle_id=WIND_BUNDLE, sections=sections, lifecycle=ctx.lifecycle, review_status=ctx.review_status,
                      validation_status=ctx.validation_status, generated_at=ctx.generated_at, execution_id=ctx.execution_id, code_version=ctx.code_version,
                      input_fingerprint=in_fp, knowledge_release=ctx.knowledge_release, manifest_ref=ctx.manifest_ref, manifest_sha256=ctx.manifest_sha256,
                      registry=reg)
    art["lineage"]["artifactId"] = sha(art)           # artifact integrity identity: content address of the sealed envelope (unique per run, stable for the same inputs)
    res.artifact = art
    return res
