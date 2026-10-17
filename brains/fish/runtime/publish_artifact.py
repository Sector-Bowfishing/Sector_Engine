"""Fish publish-artifact builder for Publisher V2 (envelope v2, bundle `fish-publication-v1`). SHADOW CONTRACT ONLY. NOT wired into any job.

ONE Fish execution -> ONE `publish-artifact-v2` -> ONE Publisher evaluation -> ONE atomic plan (SKIP or SHADOW_READY, or the whole artifact is rejected).

Fish still computes domain truth with the unchanged `biological_brain.build_updates()`; this module re-expresses the multi-path update that run would send as
the sections of one sealed bundle. It adds no science and changes no value. Design rules (the same ones Wind's builder follows):
  * routing authority is the Publisher registry (`default_registry()` -> `fish-species-v1`, `fish-registry-v1`); Fish keeps no second ownership list, so Fish
    ownership cannot drift from the Publisher. A path the registry does not authorise is never emitted: it is reported in `dropped` with its reason, or (for an
    unknown root) the build fails closed;
  * the whole `/brains/biological-state` node is NEVER replaced: the registry entry is split into approved CHILDREN; `publication` / `certification` stay
    Publisher-owned;
  * `/health/brains/biological-state` carries domain health facts only (`status`, `staleLakeCount`); process/execution fields the legacy record also carried
    (lastRun, durationMs, errorCount, deployedVersion, ...) are Orchestrator-owned and are reported in `dropped`, not emitted;
  * null / missing NEVER means delete. A removal exists only as a typed DELETE: a species retired from the registry (`SPECIES_REMOVED_FROM_REGISTRY`) or an
    optional registry child the new release no longer emits while the baseline still has it (`OPTIONAL_CHILD_CLEARED`);
  * lineage is truthful and unfabricated: knowledgeRelease / manifestRef / manifestSha256 are the verified bundle's own identity; `freshness` is NOT supplied
    (species knowledge is version-driven, never stale by age => evidence freshness stays UNKNOWN); `consumed` is passed through only when the caller really
    recorded reads (None = unknown, [] = recorded "read nothing that is a dependency");
  * no clock, no randomness, no I/O: same updates + same BuildContext => byte-identical artifact. The semantic fingerprint, volatile contract
    (`fish-volatile-v1`) and bundle seal are the PUBLISHER's (`seal_bundle`); nothing is re-implemented here.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field

import biological_brain as bb
import brain_platform as _bp          # noqa: F401  (resolves the shared platform package: repo layout or staged image)
from sector_brain_platform.publisher import default_registry, seal_bundle
from sector_brain_platform.publisher.registry import (FISH_BUNDLE, FISH_HEALTH_DOMAIN_CHILDREN, FISH_OPTIONAL_CHILDREN, FISH_REGISTRY_CHILDREN)

FISH = bb.BRAIN_ID
SCHEMA_SPECIES, SCHEMA_REGISTRY = "fish-species-v1", "fish-registry-v1"
SPECIES_REMOVED = "SPECIES_REMOVED_FROM_REGISTRY"
CHILD_CLEARED = "OPTIONAL_CHILD_CLEARED"
LIFECYCLE = "PROFILED"                       # == the registry entry's own `status`; Fish is not promoted by having a contract
_REGISTRY_CHILDREN = frozenset(c for group in FISH_REGISTRY_CHILDREN.values() for c in group)


class ArtifactBuildError(ValueError):
    pass


@dataclass(frozen=True)
class BuildContext:
    """Everything the artifact needs that Fish itself must not invent (supplied by the runner; tests pin it)."""
    execution_id: str          # UUIDv4
    generated_at: str          # ISO-8601 UTC, ...Z
    code_version: str          # the deployed code identity (DEPLOYMENT_VERSION)


@dataclass
class BuildResult:
    artifact: dict
    dropped: list = field(default_factory=list)       # [{path, reason}] legacy-update paths this builder does not author
    counts: dict = field(default_factory=dict)


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(obj) -> str:
    return "sha256:" + hashlib.sha256(canonical(obj)).hexdigest()


def _check_value(v, path):
    """Publisher refuses null / empty containers / non-finite numbers; fail here with the path, never repair."""
    if v is None:
        raise ArtifactBuildError(f"null at {path}: absence is not representable in a SET value")
    if isinstance(v, float) and not math.isfinite(v):
        raise ArtifactBuildError(f"non-finite number at {path}")
    if isinstance(v, dict):
        if not v:
            raise ArtifactBuildError(f"empty object at {path}")
        for k, x in v.items():
            _check_value(x, f"{path}/{k}")
    elif isinstance(v, (list, tuple)):
        if not v:
            raise ArtifactBuildError(f"empty array at {path}")
        for i, x in enumerate(v):
            _check_value(x, f"{path}/{i}")


def review_status(bundle) -> str:
    """UNREVIEWED unless a species carries a reviewed/validated maturity (the Brain refuses those today, so this stays UNREVIEWED; never optimistic)."""
    mats = {p.get("researchMaturity") for p in bundle.profiles.values() if p.get("assessment") == "ASSESSED"}
    if not mats or mats <= {"NOT_STARTED", "RESEARCH"}:
        return "UNREVIEWED"
    return "REVIEWED" if mats <= {"REVIEWED", "VALIDATED"} else "PARTIAL"


def validation_status(bundle) -> str:
    return "VALIDATED" if all(p.get("researchMaturity") == "VALIDATED" for p in bundle.profiles.values() if p.get("assessment") == "ASSESSED") \
        and any(p.get("assessment") == "ASSESSED" for p in bundle.profiles.values()) else "NOT_VALIDATED"


def input_fingerprint(bundle) -> str:
    """Identity of what this run was computed from: the verified bundle (its manifest hash covers every file hash), its research version and this Brain's
    version. No execution id, no timestamps => unchanged inputs give an unchanged fingerprint."""
    return sha({"manifestSha256": bundle.pointer["manifestSha256"], "researchVersion": bundle.research_version, "brainVersion": bb.BRAIN_VERSION})


def build_artifact(updates: dict, bundle, ctx: BuildContext, *, published: dict | None = None, consumed=None, registry=None) -> BuildResult:
    """`updates`: the dict returned by `biological_brain.build_updates` (multi-path, keys with a leading '/'). `published`: the current /brains/biological-state node
    (baseline) or None. `consumed`: the recorder's list, or None when nothing was recorded (unknown)."""
    reg = registry or default_registry()
    species, entries, dropped = {}, {}, []
    registry_node = None
    for raw_path in sorted(updates):
        path, value = "/" + raw_path.lstrip("/"), updates[raw_path]
        seg = path.strip("/").split("/")
        if seg[0] == "species" and len(seg) == 2:
            species[path] = value
        elif path == f"/brains/{FISH}":
            registry_node = value
        elif path == f"/validation/{FISH}":
            entries[path] = value
        elif path == f"/health/brains/{FISH}":
            for k, v in sorted((value or {}).items()):
                if k in FISH_HEALTH_DOMAIN_CHILDREN:
                    entries[f"{path}/{k}"] = v
                else:
                    dropped.append({"path": f"{path}/{k}", "reason": "process/execution health is Orchestrator-owned (lastRun, lastSuccess, durationMs, errorCount, latestError, deployedVersion, publishMode)"})
        elif seg[0] == "activity" and len(seg) == 2:
            entries[path] = value
        else:
            raise ArtifactBuildError(f"{path}: not a path the Fish artifact contract knows; extend the Publisher registry (reviewed) instead of emitting it")

    if not isinstance(registry_node, dict):
        raise ArtifactBuildError(f"the update has no /brains/{FISH} registry entry")
    unknown = sorted(set(registry_node) - _REGISTRY_CHILDREN)
    if unknown:
        raise ArtifactBuildError(f"registry entry carries children no schema authorises: {unknown} (add them to FISH_REGISTRY_CHILDREN in the Publisher registry, reviewed)")

    sp_muts = []
    for path, value in species.items():
        if value is None:
            sp_muts.append({"op": "DELETE", "path": path, "reason": SPECIES_REMOVED})        # the legacy update's explicit "retired from the registry" removal
        else:
            _check_value(value, path)
            sp_muts.append({"op": "SET", "path": path, "value": value})

    rg_muts = []
    for child, value in sorted(registry_node.items()):
        p = f"/brains/{FISH}/{child}"
        _check_value(value, p)
        rg_muts.append({"op": "SET", "path": p, "value": value})
    if published:
        for child in FISH_OPTIONAL_CHILDREN:
            if child in published and child not in registry_node:
                rg_muts.append({"op": "DELETE", "path": f"/brains/{FISH}/{child}", "reason": CHILD_CLEARED})
    for path, value in sorted(entries.items()):
        _check_value(value, path)
        rg_muts.append({"op": "SET", "path": path, "value": value})

    sections = []
    for schema, muts in ((SCHEMA_SPECIES, sp_muts), (SCHEMA_REGISTRY, rg_muts)):
        if muts:
            sections.append({"artifactSchema": schema, "mutations": sorted(muts, key=lambda m: m["path"])})     # NO freshness: UNKNOWN stays UNKNOWN
    if not sections:
        raise ArtifactBuildError("nothing to publish")

    art = seal_bundle(
        brain_id=FISH, bundle_id=FISH_BUNDLE, sections=sections, lifecycle=LIFECYCLE, review_status=review_status(bundle),
        validation_status=validation_status(bundle), generated_at=ctx.generated_at, execution_id=ctx.execution_id, code_version=ctx.code_version,
        input_fingerprint=input_fingerprint(bundle), knowledge_release=bundle.research_version, manifest_ref=registry_node["manifestRef"],
        manifest_sha256="sha256:" + bundle.pointer["manifestSha256"], registry=reg, consumed=consumed)
    return BuildResult(art, dropped, {"species": len(sp_muts), "registry": len(rg_muts), "dropped": len(dropped)})
