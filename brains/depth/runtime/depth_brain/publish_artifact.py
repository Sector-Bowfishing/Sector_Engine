"""Depth publish-artifact builder for Publisher V2 (envelope v2, bundle `depth-publication-v1`). SHADOW CONTRACT ONLY.
NOT wired into any job write path; `run.py --write` still writes through the platform client (and only from an APPROVED knowledge release).

Depth computes everything with the unchanged `publish()`; this module re-expresses that flat update dictionary as ONE sealed bundle through the shared
builder (`sector_brain_platform.publisher.flat_artifact`). It adds no science and changes no value. Depth-specific facts declared here:
  * the snapshot field and its brainVersion are Brain-authored for published lakes (registry families, not a Publisher COPY projection);
  * lake identity fields are platform-owned; the run/process fields of `/health/brains/depth` are Orchestrator-owned;
  * `lastError` is the one optional registry child a whole-node write clears; activity pruning is a platform concern (never in the artifact);
  * knowledgeRelease / manifestRef / manifestSha256 carry the verified Depth knowledge release (knowledge.Knowledge.lineage()).
Pure: no clock, no randomness, no I/O."""
from __future__ import annotations

import depth_brain  # noqa: F401  (bootstraps the platform path)
from sector_brain_platform.publisher.flat_artifact import BuildContext, BuildResult, FlatBrain, NotAuthored, build_flat_artifact, registry_children, sha  # noqa: F401
from sector_brain_platform.publisher.registry import DEPTH_BUNDLE, DEPTH_SCHEMAS

from . import contract as C

DEPTH = C.BRAIN_ID
LIFECYCLE = "PROFILED"     # == brain.json lifecycle == control_manifest lifecycle (tested); a contract promotes nothing

_LAKE = r"[A-Za-z0-9_]+"
BRAIN = FlatBrain(
    brain_id=DEPTH, bundle_id=DEPTH_BUNDLE, schema_order=DEPTH_SCHEMAS,
    scopes=((rf"/lakes/{_LAKE}/states/depth", "lake-live"), (rf"/lakeFleet/{_LAKE}/slots/depth", "lake-live"),
            (rf"/lakeFleet/{_LAKE}/(readiness|modelVersions)/depth", "fleet"), (rf"/snapshots/{_LAKE}/latest/.+", "snapshot")),
    not_authored=(NotAuthored(rf"/lakeFleet/{_LAKE}/lakeId", "lakefleet-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),
                  NotAuthored(rf"/snapshots/{_LAKE}/latest/lakeId", "snapshot-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),
                  NotAuthored(rf"/health/brains/{DEPTH}/.+", "health-brains-process", "LEGACY_READER_DEPENDENCY", "ORCHESTRATOR_DERIVED",
                              "Orchestrator (execution / deployment state)")),
    clear_absent_children=("lastError",))


def input_fingerprint(updates: dict) -> str:
    """Depth's input identity: the registry's manifest version, Brain version, knowledge release digest and every lake state's own input fingerprint
    (Lake observation + reference + manifest + Depth version). No run time, no execution id."""
    reg = registry_children(updates, DEPTH)
    lakes = {k: (v.get("provenance") or {}).get("inputFingerprint") for k, v in updates.items()
             if k.startswith("lakes/") and k.endswith("/states/depth") and isinstance(v, dict)}
    return sha({"manifestVersion": reg.get("manifestVersion"), "brainVersion": C.BRAIN_VERSION,
                "knowledgeRelease": (reg.get("knowledgeRelease") or {}).get("releaseDigest"), "lakes": lakes})


def build_artifact(updates: dict, ctx: BuildContext, knowledge=None, registry=None, consumed=None) -> BuildResult:
    """knowledge: the verified knowledge.Knowledge whose id and digest go into the artifact lineage (BR-11 e); None -> NONE (never invented)."""
    triple = knowledge.lineage() if knowledge is not None else ("NONE", "NONE", "NONE")
    return build_flat_artifact(BRAIN, updates, ctx, input_fingerprint=input_fingerprint(updates), registry=registry, consumed=consumed,
                               knowledge_release=triple)
