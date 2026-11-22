"""Moon and Night Light publish-artifact builder for Publisher V2 (envelope v2, bundle `moon-publication-v1`). CONTRACT ONLY.
NOT wired into any write path: the Brain has NO live writer (`run.py --dry-run` builds the write set into an in-memory store only).

The unchanged `publish()` computes everything; this module re-expresses its flat update dictionary as ONE sealed bundle through the shared builder
(`sector_brain_platform.publisher.flat_artifact`). It adds no science and changes no value. Declared here:
  * the snapshot field and its brainVersion are Brain-authored (registry families, not a Publisher COPY projection);
  * lake identity fields are platform-owned; `lastError` is the one optional registry child a whole-node write clears;
  * knowledgeRelease / manifestRef / manifestSha256 carry the verified packaged lake-directory release (lakes.lineage()); None -> NONE, never invented.
Pure: no clock, no randomness, no I/O."""
from __future__ import annotations

import moon_brain  # noqa: F401  (bootstraps the platform path)
from sector_brain_platform.publisher.flat_artifact import BuildContext, BuildResult, FlatBrain, NotAuthored, build_flat_artifact, registry_children, sha  # noqa: F401
from sector_brain_platform.publisher.registry import MOON_BUNDLE, MOON_SCHEMAS

from . import contract as C

MOON = C.BRAIN_ID
LIFECYCLE = "CALIBRATION"     # == brain.json lifecycle == control_manifest lifecycle (tested); a contract promotes nothing

_LAKE = r"[A-Za-z0-9_]+"
BRAIN = FlatBrain(
    brain_id=MOON, bundle_id=MOON_BUNDLE, schema_order=MOON_SCHEMAS,
    scopes=((rf"/lakes/{_LAKE}/states/moon", "lake-live"), (rf"/lakeFleet/{_LAKE}/slots/moon", "lake-live"),
            (rf"/lakeFleet/{_LAKE}/(readiness|modelVersions)/moon", "fleet"), (rf"/snapshots/{_LAKE}/latest/.+", "snapshot")),
    not_authored=(NotAuthored(rf"/lakeFleet/{_LAKE}/lakeId", "lakefleet-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),
                  NotAuthored(rf"/snapshots/{_LAKE}/latest/lakeId", "snapshot-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)")),
    clear_absent_children=("lastError",))


def input_fingerprint(updates: dict) -> str:
    """The Brain version, the knowledge release digest and every lake state's own input fingerprint (coordinate, night, cloud rows). No run time,
    no execution id."""
    lakes = {k: (v.get("provenance") or {}).get("inputFingerprint") for k, v in updates.items()
             if k.startswith("lakes/") and k.endswith("/states/moon") and isinstance(v, dict)}
    reg = registry_children(updates, MOON)
    return sha({"brainVersion": C.BRAIN_VERSION, "knowledgeRelease": (reg.get("knowledgeRelease") or {}).get("releaseDigest"), "lakes": lakes})


def build_artifact(updates: dict, ctx: BuildContext, release_lineage: tuple | None = None, registry=None, consumed=None) -> BuildResult:
    """release_lineage: (knowledgeRelease, manifestRef, manifestSha256) of the verified knowledge release, from lakes.lineage()."""
    return build_flat_artifact(BRAIN, updates, ctx, input_fingerprint=input_fingerprint(updates), registry=registry, consumed=consumed,
                               knowledge_release=tuple(release_lineage) if release_lineage else ("NONE", "NONE", "NONE"))
