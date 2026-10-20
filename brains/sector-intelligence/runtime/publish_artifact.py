"""Sector Intelligence publish-artifact builder for Publisher V2 (envelope v2, bundle `sector-intelligence-publication-v1`). SHADOW CONTRACT ONLY.
NOT wired into any job write path; the in-process job still writes through the platform client (`run.py --write`) until an approved Publisher cutover.

Intelligence still computes everything with the unchanged `sector_intelligence_brain.build_updates` (and `evaluation` for the pilot lakes); this module
re-expresses that flat update dictionary as ONE sealed bundle through the shared builder (`sector_brain_platform.publisher.flat_artifact`). It adds no
synthesis and changes no value. Intelligence-specific facts declared here:
  * the snapshot field and its brainVersion are Brain-authored for EVALUATED pilot lakes only (registry families, not a Publisher COPY projection);
  * lake identity fields are platform-owned; the run/process fields of `/health/brains/sector-intelligence` are Orchestrator-owned;
  * no delete family: Intelligence never deletes anything;
  * knowledgeRelease / manifestRef / manifestSha256 are NONE; the runtime's own input fingerprint and the catalog digest are the input identity.
Pure: no clock, no randomness, no I/O.
"""
from __future__ import annotations

import brain_platform as _bp          # noqa: F401  (resolves the shared platform package: repo layout or staged image)
import sector_intelligence_brain as sib
from sector_brain_platform.publisher.flat_artifact import BuildContext, BuildResult, FlatBrain, NotAuthored, build_flat_artifact, registry_children, sha  # noqa: F401
from sector_brain_platform.publisher.registry import INTELLIGENCE_BUNDLE, INTELLIGENCE_SCHEMAS

INTELLIGENCE = sib.BRAIN_ID
LIFECYCLE = "CALIBRATION"     # == brain.json lifecycle == control_manifest lifecycle (tested); a contract promotes nothing

_LAKE = r"[A-Za-z0-9_]+"
BRAIN = FlatBrain(
    brain_id=INTELLIGENCE, bundle_id=INTELLIGENCE_BUNDLE, schema_order=INTELLIGENCE_SCHEMAS,
    scopes=((rf"/lakes/{_LAKE}/states/{sib.SLOT}", "lake-live"), (rf"/lakeFleet/{_LAKE}/slots/{sib.SLOT}", "lake-live"),
            (rf"/lakeFleet/{_LAKE}/(readiness|modelVersions)/{sib.SLOT}", "fleet"), (rf"/snapshots/{_LAKE}/latest/.+", "snapshot")),
    not_authored=(NotAuthored(rf"/lakeFleet/{_LAKE}/lakeId", "lakefleet-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),
                  NotAuthored(rf"/snapshots/{_LAKE}/latest/lakeId", "snapshot-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),
                  NotAuthored(rf"/health/brains/{INTELLIGENCE}/.+", "health-brains-process", "LEGACY_READER_DEPENDENCY", "ORCHESTRATOR_DERIVED",
                              "Orchestrator (execution / deployment state)")))


def input_fingerprint(updates: dict) -> str:
    """The runtime's own input fingerprint (`sector_intelligence_brain.fingerprint`: catalog digest, serving revision/image, upstream registration/health/
    version/lifecycle, pilot inputs), the catalog digest and the Brain version. No run time, no execution id."""
    reg = registry_children(updates, INTELLIGENCE)
    return sha({"fingerprint": reg.get("fingerprint"), "catalogSha256": reg.get("catalogSha256"), "brainVersion": sib.BRAIN_VERSION})


def build_artifact(updates: dict, ctx: BuildContext, registry=None, consumed=None) -> BuildResult:
    return build_flat_artifact(BRAIN, updates, ctx, input_fingerprint=input_fingerprint(updates), registry=registry, consumed=consumed)
