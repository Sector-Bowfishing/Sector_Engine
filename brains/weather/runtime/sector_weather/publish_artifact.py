"""Weather publish-artifact builder for Publisher V2 (envelope v2, bundle `weather-publication-v1`). CONTRACT ONLY.
NOT wired into any write path: the Weather Brain's gated live writer is the platform client (`run.py --write`, refused without an APPROVED release
and WEATHER_WRITE_APPROVED=1); this Publisher bundle is the later CENTRAL path (a Publisher cutover is a separate owner approval). `--dry-run` builds the write set
into the platform's in-memory store).

This module re-expresses the flat update dictionary that `publish.run` builds as ONE sealed bundle through the shared builder
(`sector_brain_platform.publisher.flat_artifact`). It adds no science and changes no value. Weather-specific facts declared here:
  * no snapshot path, no /health or /sources path: the Weather registration has none;
  * `lastError` is the one optional registry child a whole-node write clears;
  * knowledgeRelease / manifestRef / manifestSha256 carry the verified thresholds release (knowledge.lineage_triple).
Pure: no clock, no randomness, no I/O."""
from __future__ import annotations

from sector_brain_platform.publisher.flat_artifact import BuildContext, BuildResult, FlatBrain, NotAuthored, build_flat_artifact, registry_children, sha  # noqa: F401
from sector_brain_platform.publisher.registry import WEATHER_BUNDLE, WEATHER_SCHEMAS

from . import contract as C

WEATHER = C.BRAIN_ID
LIFECYCLE = "CALIBRATION"     # == brain.json lifecycle == control_manifest lifecycle (tested); a contract promotes nothing

_LAKE = r"[A-Za-z0-9_]+"
BRAIN = FlatBrain(
    brain_id=WEATHER, bundle_id=WEATHER_BUNDLE, schema_order=WEATHER_SCHEMAS,
    scopes=((rf"/lakes/{_LAKE}/states/weather", "lake-live"), (rf"/lakeFleet/{_LAKE}/slots/weather", "lake-live"),
            (rf"/lakeFleet/{_LAKE}/(readiness|modelVersions)/weather", "fleet")),
    not_authored=(NotAuthored(rf"/lakeFleet/{_LAKE}/lakeId", "lakefleet-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),),
    clear_absent_children=("lastError",))


def input_fingerprint(updates: dict) -> str:
    """Weather's input identity: Brain and thresholds versions, and per lake the observation time and the weather-change signature it rests on.
    No run time, no execution id."""
    lakes = {k: {"observedAt": (v.get("freshness") or {}).get("observedAt"), "signature": (v.get("weatherChange") or {}).get("signature"),
                 "forecastIssuedAt": (v.get("forecast") or {}).get("issuedAt")}
             for k, v in updates.items() if k.startswith("lakes/") and k.endswith("/states/weather") and isinstance(v, dict)}
    return sha({"brainVersion": C.BRAIN_VERSION, "thresholdsVersion": C.THRESHOLDS_VERSION, "lakes": lakes})


def build_artifact(updates: dict, ctx: BuildContext, release_lineage=("NONE", "NONE", "NONE"), registry=None, consumed=None) -> BuildResult:
    """release_lineage: knowledge_release.lineage_triple of the verified thresholds release (BR-11 e); NONE when not given (never invented)."""
    return build_flat_artifact(BRAIN, updates, ctx, input_fingerprint=input_fingerprint(updates), registry=registry, consumed=consumed,
                               knowledge_release=tuple(release_lineage))
