"""Schema + path-authorisation registry: brainId -> artifact schema -> allowed path families.

Generic infrastructure: nothing here knows any Brain's science. A SchemaSpec states which paths a schema may touch, whether deletes are allowed,
its size bounds, which lifecycles it may carry, and which fields are volatile. Unknown brain / schema / path = reject (fail closed).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..keys import BRAINS
from ..model_v1 import CLAIM_MATURITY, LIFECYCLE, LIFECYCLE_CONDITIONS, VALIDATION_STATUS
from ..ownership import SOURCE_OWNERS
from .paths import PathFamily, lake_key_check, not_in, one_of, contains, RESERVED_BRAIN_CHILDREN, FORBIDDEN_ROOTS, normalize_path, touches_reserved, segments

PRODUCTION_LIFECYCLES = ("PRODUCTION_READY", "PRODUCTION")
VALIDATION_WORDS = tuple(dict.fromkeys(VALIDATION_STATUS + CLAIM_MATURITY))
ALL_LIFECYCLES = LIFECYCLE + LIFECYCLE_CONDITIONS


@dataclass(frozen=True)
class SchemaSpec:
    schema_id: str
    brain_id: str
    families: tuple[PathFamily, ...]
    delete_families: tuple[PathFamily, ...] = ()          # empty = this schema can never delete anything
    allowed_lifecycles: tuple[str, ...] = ("RESEARCH", "PROFILED", "SHADOW", "CALIBRATION")
    max_bytes: int = 8 * 1024 * 1024                      # canonical size of all mutations; larger needs manifest-last (not in V1)
    max_mutations: int = 5000
    require_review_status: bool = True
    require_validation_status: bool = True
    require_freshness: bool = False
    require_release: bool = False                         # True: knowledgeRelease/manifestRef/manifestSha256 may not be "NONE"
    value_types: dict = field(default_factory=dict)       # family pattern -> python type of the SET value (structural only)
    volatile_extra: frozenset = frozenset()

    def __post_init__(self):
        if self.brain_id not in BRAINS:
            raise ValueError(f"{self.schema_id}: unknown brainId {self.brain_id!r}")
        bad = [lc for lc in self.allowed_lifecycles if lc not in ALL_LIFECYCLES]
        if bad:
            raise ValueError(f"{self.schema_id}: unknown lifecycles {bad}")
        for fam in self.families + self.delete_families:
            probe = normalize_path(fam.pattern.replace("{", "x").replace("}", "x"))
            if segments(probe)[0] in FORBIDDEN_ROOTS:
                raise ValueError(f"{self.schema_id}: family {fam.pattern} targets a forbidden root")
        if not self.families:
            raise ValueError(f"{self.schema_id}: a schema with no path family can publish nothing")


class Registry:
    def __init__(self, specs=()):
        self._specs: dict[str, SchemaSpec] = {}
        for s in specs:
            self.register(s)

    def register(self, spec: SchemaSpec) -> None:
        if spec.schema_id in self._specs:
            raise ValueError(f"duplicate schema {spec.schema_id}")
        self._specs[spec.schema_id] = spec

    @property
    def brains(self) -> frozenset:
        return frozenset(BRAINS)

    def schemas_for(self, brain_id: str) -> list[str]:
        return sorted(s.schema_id for s in self._specs.values() if s.brain_id == brain_id)

    def spec(self, schema_id) -> SchemaSpec | None:
        return self._specs.get(schema_id) if isinstance(schema_id, str) else None

    def authorizing_family(self, spec: SchemaSpec, path: str, delete: bool = False) -> PathFamily | None:
        for fam in (spec.delete_families if delete else spec.families):
            if fam.match(path):
                return fam
        return None


# ---- Wind: the first concrete registration (BRAIN_PATH_OWNERSHIP_V1 section 1, row `wind`) ------------------------------------------------
WIND = "wind"
WIND_SLOT = BRAINS[WIND][0]
WIND_SCHEMAS = ("wind-lake-state-v1", "wind-registry-v1", "wind-source-registry-v1")


def _wind_sources() -> frozenset:
    return frozenset(sid for sid, owner in SOURCE_OWNERS.items() if owner == WIND)      # only sources Wind is the acquisition owner of


#: /brains/wind CHILD ownership (follows the current registry contract in jobs/wind-hourly; grouped by what each child is). Every child here is owned by
#: Wind and replaced as a unit (child level). `publication` and `certification` are NOT listed and are reserved: owned by the Publisher/Orchestrator.
WIND_REGISTRY_CHILDREN = {
    "identity": ("brainId", "displayName", "domain", "question", "platform"),
    "model": ("version", "schemaVersion", "stalenessModel", "dependsOn", "descriptor", "versions", "activeProductionModel", "researchCandidate",
              "scores", "readinessDefinitions", "stateKinds"),
    "status": ("schedule", "enabled", "health", "status", "supportedLakeCount", "profiledLakeCount", "readinessCounts", "staleLakeCount",
               "staleAfterHours", "staleRule", "lastSuccessfulRun", "lastError", "deploymentVersion", "breakdowns", "runsPerMinute", "updatedAt", "publishMode"),
}
BRAIN_NODE_OWNERS = {"publication": "publisher", "certification": "publisher"}      # reserved children of every /brains/{brainId}


def wind_specs() -> list[SchemaSpec]:
    k = {"k": lake_key_check}
    lake_state = SchemaSpec(
        "wind-lake-state-v1", WIND,
        (PathFamily(f"/lakes/{{k}}/states/{WIND_SLOT}", k),
         PathFamily(f"/lakes/{{k}}/profiles/{WIND_SLOT}", k),
         PathFamily(f"/lakes/{{k}}/validation/{WIND}", k),
         PathFamily(f"/lakeFleet/{{k}}/slots/{WIND_SLOT}", k, "DERIVED_PROJECTION", "projection of the lake state; same atomic publish"),
         PathFamily(f"/lakeFleet/{{k}}/readiness/{WIND_SLOT}", k, "DERIVED_PROJECTION"),
         PathFamily(f"/lakeFleet/{{k}}/modelVersions/{WIND_SLOT}", k, "DERIVED_PROJECTION"),
         PathFamily(f"/snapshots/{{k}}/latest/{WIND}", k, "LEGACY_READER_PRESENT",
                    "exact copy of the lake state; written only until its readers move (PATH_OWNERSHIP section 2)")),
        value_types={f"/lakes/{{k}}/states/{WIND_SLOT}": dict, f"/lakes/{{k}}/profiles/{WIND_SLOT}": dict}, require_freshness=True)
    registry = SchemaSpec(
        "wind-registry-v1", WIND,
        (PathFamily(f"/brains/{WIND}/{{child}}", {"child": one_of(c for group in WIND_REGISTRY_CHILDREN.values() for c in group)},
                    note="approved CHILDREN only (WIND_REGISTRY_CHILDREN); never the whole node, never publication/certification"),
         PathFamily(f"/validation/{WIND}"),
         PathFamily(f"/health/brains/{WIND}"),
         PathFamily("/activity/{event}", {"event": contains(f"-{WIND}-")}, note="own events only")),
        require_freshness=False)
    sources = SchemaSpec(
        "wind-source-registry-v1", WIND,
        (PathFamily("/sources/{id}", {"id": one_of(_wind_sources())}), PathFamily("/health/sources/{id}", {"id": one_of(_wind_sources())})))
    return [lake_state, registry, sources]


def default_registry() -> Registry:
    """Wind only. Every other Brain is registered as an identity (so an unknown id is distinguishable from an unmigrated one) but has no schema:
    anything submitted for them is rejected UNKNOWN_SCHEMA until their own certification registers one."""
    return Registry(wind_specs())
