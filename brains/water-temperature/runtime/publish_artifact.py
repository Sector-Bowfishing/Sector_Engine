"""Water Temperature Brain publish-artifact builder for Publisher V2 (envelope v2, bundle `water-temp-publication-v1`). SHADOW CONTRACT ONLY.

The runtime is Swift (`WaterTemperatureBrain` / `WaterTempBrainJob`); it still writes the Brain RTDB through the Swift platform client (LEGACY) until an
approved Publisher cutover. This module re-expresses ONE run's flat write set (the job's `--dry-run DIR` output, or the recorded fixture
`tests/golden/water_temp_run_updates.json`) as one sealed bundle. It adds no science and changes no value: the routing authority is the Publisher registry;
the snapshot copy and its brainVersion are Publisher-derived projections; lake identity, job health and process fields are not Water Temperature's.
Pure: no clock, no randomness, no I/O.
"""
from __future__ import annotations

from sector_brain_platform.publisher.flat_artifact import BuildContext, BuildResult, FlatBrain, NotAuthored, build_flat_artifact, registry_children, sha  # noqa: F401
from sector_brain_platform.publisher.registry import WATER_TEMP, WATER_TEMP_BUNDLE, WATER_TEMP_SCHEMAS

_LAKE = r"[A-Za-z0-9_]+"
BRAIN = FlatBrain(
    brain_id=WATER_TEMP, bundle_id=WATER_TEMP_BUNDLE, schema_order=WATER_TEMP_SCHEMAS,
    scopes=((rf"/lakes/{_LAKE}/states/waterTemp", "lake-live"), (rf"/lakeFleet/{_LAKE}/slots/waterTemp", "lake-live"),
            (rf"/lakes/{_LAKE}/profiles/waterTemp", "lake-static"), (rf"/lakes/{_LAKE}/validation/water-temp", "lake-static"),
            (rf"/lakeFleet/{_LAKE}/(readiness|modelVersions)/waterTemp", "fleet")),
    not_authored=(NotAuthored(rf"/lakeFleet/{_LAKE}/lakeId", "lakefleet-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),
                  NotAuthored(rf"/snapshots/{_LAKE}/latest/lakeId", "snapshot-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),
                  NotAuthored(r"/health/jobs/.+", "health-jobs", "PLATFORM_OWNED", "ORCHESTRATOR_DERIVED", "Orchestrator (/jobs + execution ledger)"),
                  NotAuthored(rf"/health/brains/{WATER_TEMP}/.+", "health-brains-process", "LEGACY_READER_DEPENDENCY", "ORCHESTRATOR_DERIVED",
                              "Orchestrator (execution / deployment state)")),
    clear_absent_children=("lastError",))


def input_fingerprint(updates: dict) -> str:
    """Identity of what the run was computed from: per lake the state kind, the measurement's observation time and the model's local date, plus the
    model and Brain versions. No run time and no execution id."""
    lakes = {}
    for key, st in sorted(updates.items()):
        if key.lstrip("/").startswith("lakes/") and key.endswith("/states/waterTemp") and isinstance(st, dict):
            prov = st.get("provenance") or {}
            lakes[key] = {"kind": st.get("kind"), "lastObservationAt": st.get("lastObservationAt"), "lakeLocalDate": st.get("lakeLocalDate"),
                          "modelVersion": prov.get("modelVersion")}
    reg = registry_children(updates, WATER_TEMP)
    return sha({"lakes": lakes, "version": reg.get("version"), "activeProductionModel": reg.get("activeProductionModel")})


def build_artifact(updates: dict, ctx: BuildContext, registry=None, consumed=None) -> BuildResult:
    return build_flat_artifact(BRAIN, updates, ctx, input_fingerprint=input_fingerprint(updates), registry=registry, consumed=consumed)
