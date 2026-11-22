"""Generation publish-artifact builder for Publisher V2 (envelope v2, bundle `generation-publication-v1`). CALIBRATION CONTRACT ONLY.
NOT wired into any job write path; `run.py --write` writes through the platform client and only from an APPROVED knowledge release.

The flat update dictionary of the unchanged `publish()` is re-expressed as ONE sealed bundle through the shared builder
(`sector_brain_platform.publisher.flat_artifact`). It adds no science and changes no value. Generation-specific facts declared here:
  * the snapshot field and its brainVersion are Brain-authored for published lakes (no Publisher COPY projection);
  * lake identity fields are platform-owned;
  * `lastError` is the one optional registry child a whole-node write clears; activity pruning is a platform concern;
  * knowledgeRelease / manifestRef / manifestSha256 carry the verified Generation knowledge release (knowledge.Knowledge.lineage()).
Pure: no clock, no randomness, no I/O."""
from __future__ import annotations

import generation_brain  # noqa: F401  (bootstraps the platform path)
from sector_brain_platform.publisher.flat_artifact import BuildContext, BuildResult, FlatBrain, NotAuthored, build_flat_artifact, registry_children, sha  # noqa: F401
from sector_brain_platform.publisher.registry import GENERATION_BUNDLE, GENERATION_SCHEMAS

from . import contract as C

GENERATION = C.BRAIN_ID
LIFECYCLE = C.LIFECYCLE     # == brain.json lifecycle == control_manifest lifecycle (tested); a contract promotes nothing

_LAKE = r"[A-Za-z0-9_]+"
BRAIN = FlatBrain(
    brain_id=GENERATION, bundle_id=GENERATION_BUNDLE, schema_order=GENERATION_SCHEMAS,
    scopes=((rf"/lakes/{_LAKE}/states/generation", "lake-live"), (rf"/lakeFleet/{_LAKE}/slots/generation", "lake-live"),
            (rf"/lakeFleet/{_LAKE}/(readiness|modelVersions)/generation", "fleet"), (rf"/snapshots/{_LAKE}/latest/.+", "snapshot")),
    not_authored=(NotAuthored(rf"/lakeFleet/{_LAKE}/lakeId", "lakefleet-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),
                  NotAuthored(rf"/snapshots/{_LAKE}/latest/lakeId", "snapshot-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)")),
    clear_absent_children=("lastError",))


def input_fingerprint(updates: dict) -> str:
    """Generation's input identity: the catalog version, Brain version, knowledge release digest and every lake state's own input fingerprint
    (what the sources said, not when they were read). No run time, no execution id."""
    reg = registry_children(updates, GENERATION)
    lakes = {k: (v.get("provenance") or {}).get("inputFingerprint") for k, v in updates.items()
             if k.startswith("lakes/") and k.endswith("/states/generation") and isinstance(v, dict)}
    return sha({"catalogVersion": reg.get("catalogVersion"), "brainVersion": C.BRAIN_VERSION,
                "knowledgeRelease": (reg.get("knowledgeRelease") or {}).get("releaseDigest"), "lakes": lakes})


def build_artifact(updates: dict, ctx: BuildContext, knowledge=None, registry=None, consumed=None) -> BuildResult:
    """knowledge: the verified knowledge.Knowledge whose id and digest go into the artifact lineage (BR-11 e); None -> NONE (never invented)."""
    triple = knowledge.lineage() if knowledge is not None else ("NONE", "NONE", "NONE")
    return build_flat_artifact(BRAIN, updates, ctx, input_fingerprint=input_fingerprint(updates), registry=registry, consumed=consumed,
                               knowledge_release=triple)
