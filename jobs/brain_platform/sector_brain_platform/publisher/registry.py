"""Schema + path-authorisation registry: brainId -> artifact schema -> allowed path families.

Generic infrastructure: nothing here knows any Brain's science. A SchemaSpec states which paths a schema may touch, whether deletes are allowed,
its size bounds, which lifecycles it may carry, and which fields are volatile. Unknown brain / schema / path = reject (fail closed).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..keys import BRAINS
from ..model_v1 import CLAIM_MATURITY, LIFECYCLE, LIFECYCLE_CONDITIONS, VALIDATION_STATUS
from ..ownership import SOURCE_OWNERS
from .paths import PathFamily, lake_key_check, not_in, one_of, contains, RESERVED_BRAIN_CHILDREN, FORBIDDEN_ROOTS, normalize_path, touches_reserved, segments

PRODUCTION_LIFECYCLES = ("PRODUCTION_READY", "PRODUCTION")
VALIDATION_WORDS = tuple(dict.fromkeys(VALIDATION_STATUS + CLAIM_MATURITY))
ALL_LIFECYCLES = LIFECYCLE + LIFECYCLE_CONDITIONS


@dataclass(frozen=True)
class VolatileContract:
    """Which parts of an artifact change every run without a change in domain meaning. Inspectable data, never code.
    Shared defaults (canonical.DEFAULT_VOLATILE) ALWAYS apply; a contract can only ADD. `keys` are dict keys excluded at any depth inside values;
    `paths` are exact-depth path families whose SET mutation is excluded from the semantic fingerprint (a volatile scalar child addressed by path).
    `notes` maps each entry to its rationale and retirement condition, so nothing in a list is unexplained."""
    id: str
    version: int
    keys: frozenset = frozenset()
    paths: tuple = ()
    notes: dict = field(default_factory=dict)

    def describe(self) -> dict:
        return {"id": self.id, "version": self.version, "keys": sorted(self.keys), "paths": sorted(f.pattern for f in self.paths), "notes": dict(sorted(self.notes.items()))}


SHARED_VOLATILE = VolatileContract("shared-volatile", 1)


@dataclass(frozen=True)
class CompatibilityProjection:
    """A PLATFORM-OWNED derived mutation, declared apart from anything a Brain authors. The Publisher computes it from an accepted source mutation in the
    SAME atomic plan; a Brain cannot author the target (PLATFORM_DERIVED_PATH). Temporary by definition: it carries its retirement gate.
    kind COPY: target value = source value.  kind VALUE_FROM: target value = the value of `value_from` (a path in the same artifact; no value = no projection)."""
    id: str
    source: str                    # pattern with {placeholders}
    target: str                    # pattern with the same placeholders
    kind: str = "COPY"
    value_from: str | None = None
    classification: str = "DERIVED_COMPATIBILITY_PROJECTION"
    owner: str = "publisher"
    retirement_gate: str = ""

    def __post_init__(self):
        if self.kind not in ("COPY", "VALUE_FROM") or (self.kind == "VALUE_FROM") != bool(self.value_from) or not self.retirement_gate:
            raise ValueError(f"{self.id}: invalid projection declaration (kind/value_from/retirement_gate)")

    def _rx(self, pattern):
        return re.compile("".join(f"(?P<{seg[1:-1]}>[^/]+)" if seg.startswith("{") else re.escape(seg) for seg in re.split(r"(\{[a-zA-Z]+\})", pattern) if seg))

    def match_source(self, path: str):
        m = self._rx(self.source).fullmatch(path)
        return m.groupdict() if m else None

    def match_target(self, path: str) -> bool:
        return self._rx(self.target).fullmatch(path) is not None

    def fill(self, pattern: str, params: dict) -> str:
        return pattern.format(**params)


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
    volatile: VolatileContract = SHARED_VOLATILE
    delete_reasons: tuple = ()                            # CLOSED vocabulary for DELETE.reason; required when delete_families is non-empty
    projections: tuple = ()                               # CompatibilityProjection: Publisher-derived, never Brain-authored

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
        if bool(self.delete_families) != bool(self.delete_reasons):
            raise ValueError(f"{self.schema_id}: delete_families and a closed delete_reasons vocabulary must be declared together")

    @property
    def volatile_extra(self) -> frozenset:
        """Back-compat view: the dict keys the volatile contract adds to the shared defaults."""
        return self.volatile.keys


@dataclass(frozen=True)
class BundleSpec:
    """A multi-section artifact type (envelope v2): which section schemas one logical Brain artifact may contain. The bundle id is lineage.artifactSchema."""
    bundle_id: str
    brain_id: str
    sections: tuple
    allowed_lifecycles: tuple = ("RESEARCH", "PROFILED", "SHADOW", "CALIBRATION")
    max_bytes: int = 8 * 1024 * 1024
    max_sections: int = 16

    def __post_init__(self):
        if self.brain_id not in BRAINS or not self.sections:
            raise ValueError(f"{self.bundle_id}: invalid bundle")


class Registry:
    def __init__(self, specs=(), bundles=()):
        self._specs: dict[str, SchemaSpec] = {}
        self._bundles: dict[str, BundleSpec] = {}
        for s in specs:
            self.register(s)
        for b in bundles:
            self.register_bundle(b)

    def register_bundle(self, b: BundleSpec) -> None:
        if b.bundle_id in self._bundles or b.bundle_id in self._specs:
            raise ValueError(f"duplicate schema/bundle id {b.bundle_id}")
        for sid in b.sections:
            sp = self._specs.get(sid)
            if sp is None or sp.brain_id != b.brain_id:
                raise ValueError(f"{b.bundle_id}: section schema {sid!r} is not a registered schema of {b.brain_id}")
        self._bundles[b.bundle_id] = b

    def bundle(self, bundle_id) -> BundleSpec | None:
        return self._bundles.get(bundle_id) if isinstance(bundle_id, str) else None

    def derived_target(self, brain_id: str, path: str) -> CompatibilityProjection | None:
        """Is `path` the target of a platform-derived projection of any schema of this Brain? (Then no artifact may author it.)"""
        for sp in self._specs.values():
            if sp.brain_id == brain_id:
                for pr in sp.projections:
                    if pr.match_target(path):
                        return pr
        return None

    def register(self, spec: SchemaSpec) -> None:
        if spec.schema_id in self._specs or spec.schema_id in self._bundles:
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


#: Wind's volatile contract (F-8). Deliberately minimal: a wrongly-included entry could HIDE a domain change, a missing one only costs an extra
#: SHADOW_READY, so the list holds only what is known to change every run with no change in meaning. Shared defaults (generatedAt publishedAt checkedAt
#: ageHours durationMs) apply on top. Changing this list is a versioned change (bump version/id) reviewed with Wind certification.
WIND_VOLATILE_CONTRACT_V1 = VolatileContract(
    "wind-volatile-v1", 1,
    keys=frozenset({"inputAgeHours", "lastFetchAt", "latencyMs"}),
    paths=(PathFamily(f"/brains/{WIND}/updatedAt", note="transitional"), PathFamily(f"/brains/{WIND}/lastSuccessfulRun", note="transitional")),
    notes={"key:inputAgeHours": "age of the newest input at run time; moves every run (state)",
           "key:lastFetchAt": "per-source fetch time in /health/sources/{id}; moves every run",
           "key:latencyMs": "per-source fetch latency; moves every run",
           "path:/brains/wind/updatedAt": "run timestamp == Publisher metadata (publication.evaluatedAt); retire when Ops reads publication [legacy table row wind-registry-updatedAt]",
           "path:/brains/wind/lastSuccessfulRun": "execution fact; the Orchestrator reads it for dependency freshness today; retire when it reads its own execution records [row wind-registry-lastsuccessfulrun]"})

WIND_HEALTH_DOMAIN_CHILDREN = ("status", "staleLakeCount")      # /health/brains/wind: domain health FACTS only (F-6); process/execution fields are Orchestrator-owned
WIND_PROJECTIONS = (
    CompatibilityProjection("wind-snapshot-copy-v1", "/lakes/{k}/states/wind", "/snapshots/{k}/latest/wind", "COPY",
                            retirement_gate="WIND_SNAPSHOT_MIGRATION_PLAN S2-S7: Ops and Sector Intelligence read /lakes/{k}/states/wind, window elapsed, zero readers proven, rollback export, Michael approval"),
    CompatibilityProjection("wind-snapshot-brainversion-v1", "/lakes/{k}/states/wind", "/snapshots/{k}/latest/brainVersions/wind", "VALUE_FROM", f"/brains/{WIND}/version",
                            retirement_gate="same gate as wind-snapshot-copy-v1 (the whole legacy snapshot row for Wind retires together)"),
)
WIND_BUNDLE = "wind-publication-v1"


def wind_specs() -> list[SchemaSpec]:
    k = {"k": lake_key_check}
    node = lambda tmpl: PathFamily(tmpl.format(slot=WIND_SLOT, w=WIND), k)      # noqa: E731
    lake_state = SchemaSpec(
        "wind-lake-state-v1", WIND,
        (node("/lakes/{{k}}/states/{slot}"), node("/lakes/{{k}}/profiles/{slot}"), node("/lakes/{{k}}/validation/{w}"),
         PathFamily(f"/lakeFleet/{{k}}/slots/{WIND_SLOT}", k, "DERIVED_PROJECTION", "projection of the lake state; same atomic publish"),
         PathFamily(f"/lakeFleet/{{k}}/readiness/{WIND_SLOT}", k, "DERIVED_PROJECTION"),
         PathFamily(f"/lakeFleet/{{k}}/modelVersions/{WIND_SLOT}", k, "DERIVED_PROJECTION")),
        delete_families=(node("/lakes/{{k}}/states/{slot}"), node("/lakes/{{k}}/profiles/{slot}"), node("/lakes/{{k}}/validation/{w}"),
                         PathFamily(f"/lakeFleet/{{k}}/slots/{WIND_SLOT}", k), PathFamily(f"/lakeFleet/{{k}}/readiness/{WIND_SLOT}", k),
                         PathFamily(f"/lakeFleet/{{k}}/modelVersions/{WIND_SLOT}", k)),
        delete_reasons=("LAKE_LEFT_FLEET", "EVIDENCE_REMOVED"),
        value_types={f"/lakes/{{k}}/states/{WIND_SLOT}": dict, f"/lakes/{{k}}/profiles/{WIND_SLOT}": dict}, require_freshness=True,
        volatile=WIND_VOLATILE_CONTRACT_V1, projections=WIND_PROJECTIONS)
    registry = SchemaSpec(
        "wind-registry-v1", WIND,
        (PathFamily(f"/brains/{WIND}/{{child}}", {"child": one_of(c for group in WIND_REGISTRY_CHILDREN.values() for c in group)},
                    note="approved CHILDREN only (WIND_REGISTRY_CHILDREN); never the whole node, never publication/certification"),
         PathFamily(f"/validation/{WIND}"),
         PathFamily(f"/health/brains/{WIND}/{{child}}", {"child": one_of(WIND_HEALTH_DOMAIN_CHILDREN)}, note="domain health facts only; execution/job health is Orchestrator-owned"),
         PathFamily("/activity/{event}", {"event": contains(f"-{WIND}-")}, note="own domain events only; retention/pruning is a platform concern")),
        delete_families=(PathFamily(f"/brains/{WIND}/lastError"),), delete_reasons=("OPTIONAL_CHILD_CLEARED",),
        volatile=WIND_VOLATILE_CONTRACT_V1)
    sources = SchemaSpec(
        "wind-source-registry-v1", WIND,
        (PathFamily("/sources/{id}", {"id": one_of(_wind_sources())}), PathFamily("/health/sources/{id}", {"id": one_of(_wind_sources())})),
        volatile=WIND_VOLATILE_CONTRACT_V1)
    return [lake_state, registry, sources]


def wind_bundles() -> list[BundleSpec]:
    return [BundleSpec(WIND_BUNDLE, WIND, WIND_SCHEMAS)]


# ---- Fish Brain: the second concrete registration (Fish Structural Certification V1). Same shape as Wind; nothing in the framework changed ----------------
FISH = "biological-state"
FISH_SLOT = BRAINS[FISH][0]
FISH_SCHEMAS = ("fish-species-v1", "fish-registry-v1")
FISH_BUNDLE = "fish-publication-v1"
FISH_SPECIES_ID = re.compile(r"[a-z][a-z0-9_]{1,63}")       # == biological_brain.SPECIES_ID (the Brain validates it first; the Publisher re-checks)

#: /brains/biological-state CHILD ownership: every child the Fish registry entry carries, grouped by what it is. Replaced as a unit (child level).
#: `publication` and `certification` are NOT listed and are reserved (Publisher/Orchestrator).
FISH_REGISTRY_CHILDREN = {
    "identity": ("brainId", "displayName", "domain", "question", "platform"),
    "model": ("version", "schemaVersion", "stalenessModel", "dependsOn", "orchestration", "versions", "rubric", "researchMaturityDefinitions", "scoringVersion", "targetSet"),
    "status": ("schedule", "enabled", "health", "status", "statusBasis", "supportedLakeCount", "staleLakeCount", "lastSuccessfulRun", "deploymentVersion", "publishMode"),
    "knowledge": ("researchVersion", "manifestRef", "manifestSha256", "responsibilities", "breakdowns", "speciesGroups", "discrepancies", "knownLimitations",
                  "facts", "targetReadiness", "transferSummary", "coverageMatrix"),
}
#: Registry children the Brain may legitimately stop emitting (a later release without them); clearing one is an explicit typed DELETE, never a null.
FISH_OPTIONAL_CHILDREN = ("facts", "targetReadiness", "transferSummary", "coverageMatrix", "speciesGroups", "knownLimitations", "discrepancies", "targetSet")
FISH_HEALTH_DOMAIN_CHILDREN = ("status", "staleLakeCount")       # domain health facts only; process/execution fields are Orchestrator-owned (same split as Wind)

#: Fish's volatile contract. Deliberately minimal (a wrongly-included entry could hide a domain change): `updatedAt` is the per-run stamp inside every species
#: summary and `lastRunAt` the run stamp of the validation record; `lastSuccessfulRun` is the execution fact; `versions` embeds the publication date (its content is fully implied by researchVersion /
#: species counts, which are separate material children). Shared defaults apply on top. Changing this list is a versioned change reviewed with Fish certification.
FISH_VOLATILE_CONTRACT_V1 = VolatileContract(
    "fish-volatile-v1", 1,
    keys=frozenset({"updatedAt", "lastRunAt"}),
    paths=(PathFamily(f"/brains/{FISH}/lastSuccessfulRun", note="transitional"), PathFamily(f"/brains/{FISH}/versions", note="transitional"),
           PathFamily("/activity/{event}", {"event": contains(f"-{FISH}-")}, note="log entry, a consequence of a change not state")),
    notes={"key:updatedAt": "per-run publication stamp inside species summaries; no domain meaning",
           "key:lastRunAt": "run timestamp inside /validation/biological-state; the validation STATUS stays material",
           "path:/brains/biological-state/lastSuccessfulRun": "execution fact; retire when the Orchestrator reads its own execution records",
           "path:/brains/biological-state/versions": "carries the publication date; implied by researchVersion + species counts (separate material children); retire with the legacy registry shape",
           "path:/activity/{event}": "a version event exists only because other material children changed in the same artifact; an event alone is never a domain change (a re-run after the baseline emits none)"})


def fish_specs() -> list[SchemaSpec]:
    sid = {"id": lambda s: FISH_SPECIES_ID.fullmatch(s) is not None}
    species = SchemaSpec(
        "fish-species-v1", FISH,
        (PathFamily("/species/{id}", sid, note="species knowledge summary (Fish-owned summary; species IDENTITY is Species Registry-owned, see FISH_GAP_AUDIT_V1 G-1)"),),
        delete_families=(PathFamily("/species/{id}", sid),), delete_reasons=("SPECIES_REMOVED_FROM_REGISTRY",),
        value_types={"/species/{id}": dict}, require_release=True, volatile=FISH_VOLATILE_CONTRACT_V1)
    registry = SchemaSpec(
        "fish-registry-v1", FISH,
        (PathFamily(f"/brains/{FISH}/{{child}}", {"child": one_of(c for group in FISH_REGISTRY_CHILDREN.values() for c in group)},
                    note="approved CHILDREN only (FISH_REGISTRY_CHILDREN); never the whole node, never publication/certification"),
         PathFamily(f"/validation/{FISH}"),
         PathFamily(f"/health/brains/{FISH}/{{child}}", {"child": one_of(FISH_HEALTH_DOMAIN_CHILDREN)}, note="domain health facts only; execution/job health is Orchestrator-owned"),
         PathFamily("/activity/{event}", {"event": contains(f"-{FISH}-")}, note="own domain events only; retention/pruning is a platform concern")),
        delete_families=(PathFamily(f"/brains/{FISH}/{{child}}", {"child": one_of(FISH_OPTIONAL_CHILDREN)}),), delete_reasons=("OPTIONAL_CHILD_CLEARED",),
        require_release=True, volatile=FISH_VOLATILE_CONTRACT_V1)
    return [species, registry]


def fish_bundles() -> list[BundleSpec]:
    return [BundleSpec(FISH_BUNDLE, FISH, FISH_SCHEMAS)]


# ---- Water Clarity Brain (C1): the third concrete registration (Water Clarity Structural Certification V1). DATA ONLY: no validator/planner/path code changed ------
CLARITY = "water-clarity"
CLARITY_SLOT = BRAINS[CLARITY][0]
CLARITY_SCHEMAS = ("clarity-lake-state-v1", "clarity-registry-v1", "clarity-source-registry-v1")
CLARITY_BUNDLE = "clarity-publication-v1"


def _clarity_sources() -> frozenset:
    return frozenset(sid for sid, owner in SOURCE_OWNERS.items() if owner == CLARITY)      # only sources Clarity is the acquisition owner of


#: /brains/water-clarity CHILD ownership: exactly the children `clarity_brain.registry_entry` builds today (grouped by what each child is). Every child is replaced
#: as a unit (child level, never the whole node). `publication` and `certification` are reserved (Publisher/Orchestrator).
CLARITY_REGISTRY_CHILDREN = {
    "identity": ("brainId", "displayName", "domain", "question", "platform"),
    "model": ("version", "schemaVersion", "stalenessModel", "dependsOn", "descriptor", "versions", "activeModel", "candidateModel", "modelRoster", "certifications",
              "processingPaths", "sensorAuthority", "strongPolicy", "readinessRule", "stateTypes", "vocabularies", "layerCatalog", "catalogDetail"),
    "status": ("schedule", "enabled", "health", "status", "statusReasons", "supportedLakeCount", "readinessCounts", "staleLakeCount", "staleAfterHours",
               "satelliteFreshDays", "lastSuccessfulRun", "lastError", "deploymentVersion", "breakdowns", "runsPerMinute", "updatedAt"),
}
CLARITY_HEALTH_DOMAIN_CHILDREN = ("status", "staleLakeCount")        # /health/brains/water-clarity: domain health FACTS only; process/execution fields are Orchestrator-owned
CLARITY_SLOT_ERROR_CHILDREN = ("stale", "lastError", "lastErrorAt")  # children of /lakeFleet/{k}/slots/waterClarity written when the Engine missed a lake (the last good slot is kept)

#: Clarity's volatile contract. Minimal on purpose (same rule as Wind): only fields that are run-clock or fetch-clock values and carry no change of domain meaning.
#: The Engine's own evaluation time (`evaluationTime`, `sources[].lastObservationAt`) is deliberately NOT volatile: a new Engine evaluation IS a new input.
#: Shared defaults (generatedAt publishedAt checkedAt ageHours durationMs) apply on top. Changing this list is a versioned change.
CLARITY_VOLATILE_CONTRACT_V1 = VolatileContract(
    "clarity-volatile-v1", 1,
    keys=frozenset({"inputAgeHours", "satelliteAgeHours", "nextCheckAt", "freshUntil", "lastUpdatedAt", "lastFetchAt", "updatedAt"}),
    paths=(PathFamily(f"/brains/{CLARITY}/updatedAt", note="transitional"), PathFamily(f"/brains/{CLARITY}/lastSuccessfulRun", note="transitional")),
    notes={"key:inputAgeHours": "age of the Engine evaluation at run time; moves every run (state provenance)",
           "key:satelliteAgeHours": "age of the newest scene at run time; the scene time itself (observedAt) is NOT volatile",
           "key:nextCheckAt": "run time + the existing recheck interval (freshness block)", "key:freshUntil": "run time + staleAfterHours (freshness block)",
           "key:lastUpdatedAt": "slot write time; the Orchestrator-era freshness is derived from evidence, never from this",
           "key:lastFetchAt": "per-source fetch time in /sources/{id} and /health/sources/{id}; moves every run",
           "key:updatedAt": "profile write time (a nested key of /lakes/{k}/profiles/waterClarity); no domain meaning",
           "path:/brains/water-clarity/updatedAt": "run timestamp == Publisher metadata (publication.evaluatedAt); retire when Ops reads publication",
           "path:/brains/water-clarity/lastSuccessfulRun": "execution fact; retire when the Orchestrator reads its own execution records"})
CLARITY_PROJECTIONS = (
    CompatibilityProjection("clarity-snapshot-copy-v1", f"/lakes/{{k}}/states/{CLARITY_SLOT}", f"/snapshots/{{k}}/latest/{CLARITY_SLOT}", "COPY",
                            retirement_gate="same Ops/Sector Intelligence snapshot-reader migration program as Wind (reader inventory for the waterClarity field NOT yet verified): readers moved, window elapsed, zero readers proven, rollback export, Michael approval"),
    CompatibilityProjection("clarity-snapshot-brainversion-v1", f"/lakes/{{k}}/states/{CLARITY_SLOT}", f"/snapshots/{{k}}/latest/brainVersions/{CLARITY}", "VALUE_FROM",
                            f"/brains/{CLARITY}/version", retirement_gate="retires with clarity-snapshot-copy-v1 (the whole legacy snapshot row for Clarity retires together)"),
)


def clarity_specs() -> list[SchemaSpec]:
    k = {"k": lake_key_check}
    node = lambda tmpl: PathFamily(tmpl.format(slot=CLARITY_SLOT), k)      # noqa: E731
    lake_state = SchemaSpec(
        "clarity-lake-state-v1", CLARITY,
        (node("/lakes/{{k}}/states/{slot}"), node("/lakes/{{k}}/profiles/{slot}"),
         PathFamily(f"/lakeFleet/{{k}}/slots/{CLARITY_SLOT}", k, "DERIVED_PROJECTION", "projection of the lake state; same atomic publish"),
         PathFamily(f"/lakeFleet/{{k}}/slots/{CLARITY_SLOT}/{{child}}", {**k, "child": one_of(CLARITY_SLOT_ERROR_CHILDREN)},
                    note="engine-miss facts: the last good slot is kept and only these children change"),
         PathFamily(f"/lakeFleet/{{k}}/readiness/{CLARITY_SLOT}", k, "DERIVED_PROJECTION"),
         PathFamily(f"/lakeFleet/{{k}}/modelVersions/{CLARITY_SLOT}", k, "DERIVED_PROJECTION")),
        value_types={f"/lakes/{{k}}/states/{CLARITY_SLOT}": dict, f"/lakes/{{k}}/profiles/{CLARITY_SLOT}": dict}, require_freshness=True,
        volatile=CLARITY_VOLATILE_CONTRACT_V1, projections=CLARITY_PROJECTIONS)                      # no delete family: Clarity never deletes a lake state
    registry = SchemaSpec(
        "clarity-registry-v1", CLARITY,
        (PathFamily(f"/brains/{CLARITY}/{{child}}", {"child": one_of(c for group in CLARITY_REGISTRY_CHILDREN.values() for c in group)},
                    note="approved CHILDREN only (CLARITY_REGISTRY_CHILDREN); never the whole node, never publication/certification"),
         PathFamily(f"/validation/{CLARITY}"),
         PathFamily(f"/health/brains/{CLARITY}/{{child}}", {"child": one_of(CLARITY_HEALTH_DOMAIN_CHILDREN)}, note="domain health facts only; execution/job health is Orchestrator-owned"),
         PathFamily("/activity/{event}", {"event": contains(f"-{CLARITY}-")}, note="own domain events only; retention/pruning is a platform concern")),
        delete_families=(PathFamily(f"/brains/{CLARITY}/lastError"),), delete_reasons=("OPTIONAL_CHILD_CLEARED",),
        volatile=CLARITY_VOLATILE_CONTRACT_V1)
    sources = SchemaSpec(
        "clarity-source-registry-v1", CLARITY,
        (PathFamily("/sources/{id}", {"id": one_of(_clarity_sources())}), PathFamily("/health/sources/{id}", {"id": one_of(_clarity_sources())})),
        volatile=CLARITY_VOLATILE_CONTRACT_V1)
    return [lake_state, registry, sources]


def clarity_bundles() -> list[BundleSpec]:
    return [BundleSpec(CLARITY_BUNDLE, CLARITY, CLARITY_SCHEMAS)]


# ---- Sector Intelligence (synthesis Brain; SHADOW registration, Cortex architecture completion 2026-10-20) ----------------------------------------
INTELLIGENCE = "sector-intelligence"
INTELLIGENCE_SLOT = BRAINS[INTELLIGENCE][0]
INTELLIGENCE_SNAPSHOT_FIELD = BRAINS[INTELLIGENCE][1]
INTELLIGENCE_SCHEMAS = ("intelligence-lake-state-v1", "intelligence-registry-v1")
INTELLIGENCE_BUNDLE = "sector-intelligence-publication-v1"

#: /brains/sector-intelligence CHILD ownership: exactly the children `sector_intelligence_brain.build_updates` builds today. Replaced child by child, never the
#: whole node; `publication` / `certification` stay Publisher-owned.
INTELLIGENCE_REGISTRY_CHILDREN = {
    "identity": ("brainId", "displayName", "domain", "question", "platform"),
    "model": ("version", "schemaVersion", "stalenessModel", "dependsOn", "orchestration", "versions", "activeModel", "modelRoster", "vocabularies",
              "inputContract", "outputContract", "knownLimitations", "catalogVersion", "catalogSha256", "fingerprint"),
    "status": ("schedule", "enabled", "health", "status", "statusBasis", "statusReasons", "supportedLakeCount", "evaluatedLakeCount", "directoryLakeCount",
               "evaluation", "engineServing", "dependencies", "dependencyOrder", "dependencySummary", "blockers", "breakdowns", "publishMode",
               "deploymentVersion", "lastSuccessfulRun", "updatedAt"),
}
INTELLIGENCE_HEALTH_DOMAIN_CHILDREN = ("status",)                   # /health/brains/sector-intelligence: domain fact only; run/process fields are Orchestrator-owned

#: Intelligence's volatile contract: run-clock values only (measured by re-running the builder on identical inputs). The upstream registration, health,
#: version and evaluation inputs are NOT volatile: a change there IS a new input. Shared defaults (generatedAt publishedAt checkedAt ageHours durationMs) apply.
INTELLIGENCE_VOLATILE_CONTRACT_V1 = VolatileContract(
    "intelligence-volatile-v1", 1,
    keys=frozenset({"lastEvaluationAt", "lastUpdatedAt", "updatedAt"}),
    paths=(PathFamily(f"/brains/{INTELLIGENCE}/updatedAt", note="transitional"), PathFamily(f"/brains/{INTELLIGENCE}/lastSuccessfulRun", note="transitional")),
    notes={"key:lastEvaluationAt": "the run's evaluation time (registry evaluation block, dependency entries); moves every run",
           "key:lastUpdatedAt": "slot write time; no domain meaning", "key:updatedAt": "validation/registry write time; no domain meaning",
           "path:/brains/sector-intelligence/updatedAt": "run timestamp == Publisher metadata; retire when Ops reads publication",
           "path:/brains/sector-intelligence/lastSuccessfulRun": "execution fact; retire when the Orchestrator reads its own execution records"})


def intelligence_specs() -> list[SchemaSpec]:
    k = {"k": lake_key_check}
    lake_state = SchemaSpec(
        "intelligence-lake-state-v1", INTELLIGENCE,
        (PathFamily(f"/lakes/{{k}}/states/{INTELLIGENCE_SLOT}", k),
         PathFamily(f"/lakeFleet/{{k}}/slots/{INTELLIGENCE_SLOT}", k, "DERIVED_PROJECTION", "projection of the lake state; same atomic publish"),
         PathFamily(f"/lakeFleet/{{k}}/readiness/{INTELLIGENCE_SLOT}", k, "DERIVED_PROJECTION"),
         PathFamily(f"/lakeFleet/{{k}}/modelVersions/{INTELLIGENCE_SLOT}", k, "DERIVED_PROJECTION"),
         # Brain-authored, NOT a Publisher projection: the legacy writer emits the snapshot field only for EVALUATED pilot lakes (never for NOT_EVALUATED
         # input-availability states). A COPY projection of every lake state would change that meaning.
         PathFamily(f"/snapshots/{{k}}/latest/{INTELLIGENCE_SNAPSHOT_FIELD}", k, note="evaluated lakes only (LEGACY_READER_DEPENDENCY)"),
         PathFamily(f"/snapshots/{{k}}/latest/brainVersions/{INTELLIGENCE}", k, note="evaluated lakes only (LEGACY_READER_DEPENDENCY)")),
        value_types={f"/lakes/{{k}}/states/{INTELLIGENCE_SLOT}": dict, f"/lakeFleet/{{k}}/slots/{INTELLIGENCE_SLOT}": dict},
        volatile=INTELLIGENCE_VOLATILE_CONTRACT_V1)                                       # no delete family: Intelligence never deletes a lake state
    registry = SchemaSpec(
        "intelligence-registry-v1", INTELLIGENCE,
        (PathFamily(f"/brains/{INTELLIGENCE}/{{child}}", {"child": one_of(c for group in INTELLIGENCE_REGISTRY_CHILDREN.values() for c in group)},
                    note="approved CHILDREN only (INTELLIGENCE_REGISTRY_CHILDREN); never the whole node, never publication/certification"),
         PathFamily(f"/validation/{INTELLIGENCE}"),
         PathFamily(f"/health/brains/{INTELLIGENCE}/{{child}}", {"child": one_of(INTELLIGENCE_HEALTH_DOMAIN_CHILDREN)}, note="domain health fact only"),
         PathFamily("/activity/{event}", {"event": contains(f"-{INTELLIGENCE}-")}, note="own domain events only; retention/pruning is a platform concern")),
        volatile=INTELLIGENCE_VOLATILE_CONTRACT_V1)
    return [lake_state, registry]


def intelligence_bundles() -> list[BundleSpec]:
    return [BundleSpec(INTELLIGENCE_BUNDLE, INTELLIGENCE, INTELLIGENCE_SCHEMAS)]


# ---- Lake Brain and Water Temperature (Swift runtimes; SHADOW registrations, Cortex architecture completion 2026-10-20) -------------------------
# Both jobs write whole registry/health nodes and per-lake nodes through the Swift Brain platform client (LEGACY). These registrations describe that
# write set as Publisher families, derived from the runners' recorded output (brains/<dir>/tests/golden/*_run_updates.json, regenerated by Swift tests).
LAKE = "lake-brain"
LAKE_SLOT = BRAINS[LAKE][0]
LAKE_SCHEMAS = ("lake-state-v1", "lake-registry-v1", "lake-source-registry-v1")
LAKE_BUNDLE = "lake-publication-v1"
LAKE_REGISTRY_CHILDREN = {
    "identity": ("brainId", "displayName", "domain", "question", "platform"),
    "model": ("version", "schemaVersion", "stalenessModel", "dependsOn", "orchestration", "versions", "modelVersion", "baselineMethod", "bindingVersion",
              "readinessDefinitions", "stateKindDefinitions", "healthRule"),
    "status": ("schedule", "enabled", "health", "status", "supportedLakeCount", "directoryLakeCount", "readinessCounts", "staleLakeCount", "staleAfterHours",
               "lastSuccessfulRun", "lastError", "deploymentVersion", "breakdowns", "fleetScope"),
}
LAKE_HEALTH_DOMAIN_CHILDREN = ("status", "staleLakeCount", "reasons")      # domain facts + WHY; run/process fields are Orchestrator-owned
LAKE_FLEET_CHILDREN = ("riverSystem",)                                      # the one Lake-only shared fleet field the job writes (ownership.LAKE_BRAIN_ONLY_FLEET)


def _owned_sources(brain_id) -> frozenset:
    return frozenset(sid for sid, owner in SOURCE_OWNERS.items() if owner == brain_id)


#: Run-clock values only, measured by running the Lake runner twice on identical feeds at different clock times (2026-10-20).
LAKE_VOLATILE_CONTRACT_V1 = VolatileContract(
    "lake-volatile-v1", 1,
    keys=frozenset({"inputAgeHours", "sourceAgeHours", "nextCheckAt", "lastUpdatedAt", "updatedAt", "lastFetchAt"}),
    paths=(PathFamily(f"/brains/{LAKE}/lastSuccessfulRun", note="transitional"),),
    notes={"key:inputAgeHours": "age of the newest input at run time (provenance)", "key:sourceAgeHours": "age of the reading at run time; the observation time itself is NOT volatile",
           "key:nextCheckAt": "run time + recheck interval (freshness envelope)", "key:lastUpdatedAt": "slot write time; no domain meaning",
           "key:updatedAt": "profile write time; no domain meaning", "key:lastFetchAt": "per-source fetch time in /sources/{id}",
           "path:/brains/lake-brain/lastSuccessfulRun": "execution fact; retire when the Orchestrator reads its own execution records"})
LAKE_PROJECTIONS = (
    CompatibilityProjection("lake-snapshot-copy-v1", f"/lakes/{{k}}/states/{LAKE_SLOT}", f"/snapshots/{{k}}/latest/{BRAINS[LAKE][1]}", "COPY",
                            retirement_gate="same snapshot-reader migration program as Wind/Clarity: readers moved, zero readers proven, rollback export, Michael approval"),
    CompatibilityProjection("lake-snapshot-brainversion-v1", f"/lakes/{{k}}/states/{LAKE_SLOT}", f"/snapshots/{{k}}/latest/brainVersions/{LAKE}", "VALUE_FROM",
                            f"/brains/{LAKE}/version", retirement_gate="retires with lake-snapshot-copy-v1"),
)


def lake_specs() -> list[SchemaSpec]:
    k = {"k": lake_key_check}
    lake_state = SchemaSpec(
        "lake-state-v1", LAKE,
        (PathFamily(f"/lakes/{{k}}/states/{LAKE_SLOT}", k), PathFamily("/lakes/{k}/brain", k, note="LakeProfile (Lake-owned node)"),
         PathFamily("/lakes/{k}/speciesPresence", k, note="whole presence node, from the validated private presence release (never committed)"),
         PathFamily(f"/lakeFleet/{{k}}/slots/{LAKE_SLOT}", k, "DERIVED_PROJECTION", "projection of the lake state; same atomic publish"),
         PathFamily(f"/lakeFleet/{{k}}/readiness/{LAKE_SLOT}", k, "DERIVED_PROJECTION"),
         PathFamily(f"/lakeFleet/{{k}}/modelVersions/{LAKE_SLOT}", k, "DERIVED_PROJECTION"),
         PathFamily("/lakeFleet/{k}/{child}", {**k, "child": one_of(LAKE_FLEET_CHILDREN)}, note="Lake-only shared fleet fields")),
        value_types={f"/lakes/{{k}}/states/{LAKE_SLOT}": dict, "/lakes/{k}/brain": dict, "/lakes/{k}/speciesPresence": dict},
        volatile=LAKE_VOLATILE_CONTRACT_V1, projections=LAKE_PROJECTIONS)
    registry = SchemaSpec(
        "lake-registry-v1", LAKE,
        (PathFamily(f"/brains/{LAKE}/{{child}}", {"child": one_of(c for group in LAKE_REGISTRY_CHILDREN.values() for c in group)},
                    note="approved CHILDREN only; never the whole node, never publication/certification"),
         PathFamily(f"/validation/{LAKE}"),
         PathFamily(f"/health/brains/{LAKE}/{{child}}", {"child": one_of(LAKE_HEALTH_DOMAIN_CHILDREN)}, note="domain health facts only"),
         PathFamily("/activity/{event}", {"event": contains(f"-{LAKE}-")}, note="own domain events only")),
        delete_families=(PathFamily(f"/brains/{LAKE}/lastError"),), delete_reasons=("OPTIONAL_CHILD_CLEARED",), volatile=LAKE_VOLATILE_CONTRACT_V1)
    sources = SchemaSpec(
        "lake-source-registry-v1", LAKE,
        (PathFamily("/sources/{id}", {"id": one_of(_owned_sources(LAKE))}), PathFamily("/health/sources/{id}", {"id": one_of(_owned_sources(LAKE))})),
        volatile=LAKE_VOLATILE_CONTRACT_V1)
    return [lake_state, registry, sources]


WATER_TEMP = "water-temp"
WATER_TEMP_SLOT = BRAINS[WATER_TEMP][0]
WATER_TEMP_SCHEMAS = ("water-temp-lake-state-v1", "water-temp-registry-v1", "water-temp-source-registry-v1")
WATER_TEMP_BUNDLE = "water-temp-publication-v1"
WATER_TEMP_REGISTRY_CHILDREN = {
    "identity": ("brainId", "displayName", "domain", "question", "platform"),
    "model": ("version", "schemaVersion", "stalenessModel", "dependsOn", "descriptor", "versions", "activeProductionModel", "researchCandidate",
              "readinessDefinitions", "stateKindDefinitions", "healthRule"),
    "status": ("schedule", "enabled", "health", "status", "supportedLakeCount", "readinessCounts", "staleLakeCount", "staleAfterHours",
               "lastSuccessfulRun", "lastError", "deploymentVersion", "breakdowns", "runsPerMinute", "fleetScope"),
}
WATER_TEMP_HEALTH_DOMAIN_CHILDREN = ("status", "staleLakeCount")
WATER_TEMP_VOLATILE_CONTRACT_V1 = VolatileContract(
    "water-temp-volatile-v1", 1,
    keys=frozenset({"inputAgeHours", "sourceAgeHours", "lastUpdatedAt", "lastFetchAt"}),
    paths=(PathFamily(f"/brains/{WATER_TEMP}/lastSuccessfulRun", note="transitional"),),
    notes={"key:inputAgeHours": "age of the newest input at run time (provenance)", "key:sourceAgeHours": "age of the reading at run time; the observation time itself is NOT volatile",
           "key:lastUpdatedAt": "slot write time; no domain meaning", "key:lastFetchAt": "per-source fetch time in /sources/{id}",
           "path:/brains/water-temp/lastSuccessfulRun": "execution fact; retire when the Orchestrator reads its own execution records"})
WATER_TEMP_PROJECTIONS = (
    CompatibilityProjection("water-temp-snapshot-copy-v1", f"/lakes/{{k}}/states/{WATER_TEMP_SLOT}", f"/snapshots/{{k}}/latest/{BRAINS[WATER_TEMP][1]}", "COPY",
                            retirement_gate="same snapshot-reader migration program as Wind/Clarity: readers moved, zero readers proven, rollback export, Michael approval"),
    CompatibilityProjection("water-temp-snapshot-brainversion-v1", f"/lakes/{{k}}/states/{WATER_TEMP_SLOT}", f"/snapshots/{{k}}/latest/brainVersions/{WATER_TEMP}",
                            "VALUE_FROM", f"/brains/{WATER_TEMP}/version", retirement_gate="retires with water-temp-snapshot-copy-v1"),
)


def water_temp_specs() -> list[SchemaSpec]:
    k = {"k": lake_key_check}
    lake_state = SchemaSpec(
        "water-temp-lake-state-v1", WATER_TEMP,
        (PathFamily(f"/lakes/{{k}}/states/{WATER_TEMP_SLOT}", k), PathFamily(f"/lakes/{{k}}/profiles/{WATER_TEMP_SLOT}", k),
         PathFamily(f"/lakes/{{k}}/validation/{WATER_TEMP}", k, note="protected development lakes only"),
         PathFamily(f"/lakeFleet/{{k}}/slots/{WATER_TEMP_SLOT}", k, "DERIVED_PROJECTION", "projection of the lake state; same atomic publish"),
         PathFamily(f"/lakeFleet/{{k}}/readiness/{WATER_TEMP_SLOT}", k, "DERIVED_PROJECTION"),
         PathFamily(f"/lakeFleet/{{k}}/modelVersions/{WATER_TEMP_SLOT}", k, "DERIVED_PROJECTION")),
        value_types={f"/lakes/{{k}}/states/{WATER_TEMP_SLOT}": dict, f"/lakes/{{k}}/profiles/{WATER_TEMP_SLOT}": dict},
        volatile=WATER_TEMP_VOLATILE_CONTRACT_V1, projections=WATER_TEMP_PROJECTIONS)
    registry = SchemaSpec(
        "water-temp-registry-v1", WATER_TEMP,
        (PathFamily(f"/brains/{WATER_TEMP}/{{child}}", {"child": one_of(c for group in WATER_TEMP_REGISTRY_CHILDREN.values() for c in group)},
                    note="approved CHILDREN only; never the whole node, never publication/certification"),
         PathFamily(f"/validation/{WATER_TEMP}"),
         PathFamily(f"/health/brains/{WATER_TEMP}/{{child}}", {"child": one_of(WATER_TEMP_HEALTH_DOMAIN_CHILDREN)}, note="domain health facts only"),
         PathFamily("/activity/{event}", {"event": contains(f"-{WATER_TEMP}-")}, note="own domain events only")),
        delete_families=(PathFamily(f"/brains/{WATER_TEMP}/lastError"),), delete_reasons=("OPTIONAL_CHILD_CLEARED",), volatile=WATER_TEMP_VOLATILE_CONTRACT_V1)
    sources = SchemaSpec(
        "water-temp-source-registry-v1", WATER_TEMP,
        (PathFamily("/sources/{id}", {"id": one_of(_owned_sources(WATER_TEMP))}), PathFamily("/health/sources/{id}", {"id": one_of(_owned_sources(WATER_TEMP))})),
        volatile=WATER_TEMP_VOLATILE_CONTRACT_V1)
    return [lake_state, registry, sources]


def lake_bundles() -> list[BundleSpec]:
    return [BundleSpec(LAKE_BUNDLE, LAKE, LAKE_SCHEMAS)]


def water_temp_bundles() -> list[BundleSpec]:
    return [BundleSpec(WATER_TEMP_BUNDLE, WATER_TEMP, WATER_TEMP_SCHEMAS)]


# ---- Depth (SHADOW / PROFILED; canonical package brains/depth, Cortex 2.1 structural completion 2026-10-20) ---------------------------------------
# The Depth job (brains/depth/runtime/run.py) sends flat multi-path updates through the platform client (LEGACY, pilot-scope shadow only, and only from an
# APPROVED knowledge release). This registration describes that write set as Publisher families so the Brain can be certified; it activates nothing.
DEPTH = "depth"
DEPTH_SLOT = BRAINS[DEPTH][0]
DEPTH_SNAPSHOT_FIELD = BRAINS[DEPTH][1]
DEPTH_SCHEMAS = ("depth-lake-state-v1", "depth-registry-v1")
DEPTH_BUNDLE = "depth-publication-v1"
DEPTH_REGISTRY_CHILDREN = {
    "identity": ("brainId", "displayName", "domain", "question", "platform"),
    "model": ("version", "schemaVersion", "stalenessModel", "dependsOn", "descriptor", "versions", "models", "readinessDefinitions", "stateKinds",
              "contractVersion", "manifestVersion", "knowledgeRelease", "claims", "lifecycle", "shadow", "scoreStatus", "scoreNote", "research", "sourceIds"),
    "status": ("schedule", "enabled", "health", "status", "statusBasis", "supportedLakeCount", "directoryLakeCount", "readinessCounts", "staleLakeCount",
               "staleAfterHours", "lastSuccessfulRun", "lastError", "lastDryRun", "breakdowns", "fleet", "blockers", "primaryBlocker", "lakeDependency",
               "orchestration", "fieldValidation", "execution", "validation", "publishMode", "scope", "updatedAt"),
}
DEPTH_HEALTH_DOMAIN_CHILDREN = ("status", "staleLakeCount")          # domain facts; run/process fields are Orchestrator-owned
DEPTH_VOLATILE_CONTRACT_V1 = VolatileContract(
    "depth-volatile-v1", 1,
    keys=frozenset({"lastUpdatedAt", "updatedAt", "inputAgeHours", "levelAgeHours"}),
    paths=(PathFamily(f"/brains/{DEPTH}/lastSuccessfulRun", note="transitional"), PathFamily(f"/brains/{DEPTH}/versions", note="carries the run date")),
    notes={"key:lastUpdatedAt": "slot write time; no domain meaning", "key:updatedAt": "registry write time; no domain meaning",
           "key:inputAgeHours": "age of the Lake observation at run time", "key:levelAgeHours": "age of the level reading at run time",
           "path:/brains/depth/lastSuccessfulRun": "execution fact; retire when the Orchestrator reads its own execution records",
           "path:/brains/depth/versions": "version history entry dated by the run"})


def depth_specs() -> list[SchemaSpec]:
    k = {"k": lake_key_check}
    lake_state = SchemaSpec(
        "depth-lake-state-v1", DEPTH,
        (PathFamily(f"/lakes/{{k}}/states/{DEPTH_SLOT}", k),
         PathFamily(f"/lakeFleet/{{k}}/slots/{DEPTH_SLOT}", k, "DERIVED_PROJECTION", "projection of the lake state; same atomic publish"),
         PathFamily(f"/lakeFleet/{{k}}/readiness/{DEPTH_SLOT}", k, "DERIVED_PROJECTION"),
         PathFamily(f"/lakeFleet/{{k}}/modelVersions/{DEPTH_SLOT}", k, "DERIVED_PROJECTION"),
         PathFamily(f"/snapshots/{{k}}/latest/{DEPTH_SNAPSHOT_FIELD}", k, note="published lakes only (LEGACY_READER_DEPENDENCY; Brain-authored, no COPY projection)"),
         PathFamily(f"/snapshots/{{k}}/latest/brainVersions/{DEPTH}", k, note="published lakes only (LEGACY_READER_DEPENDENCY)")),
        value_types={f"/lakes/{{k}}/states/{DEPTH_SLOT}": dict, f"/lakeFleet/{{k}}/slots/{DEPTH_SLOT}": dict},
        volatile=DEPTH_VOLATILE_CONTRACT_V1)
    registry = SchemaSpec(
        "depth-registry-v1", DEPTH,
        (PathFamily(f"/brains/{DEPTH}/{{child}}", {"child": one_of(c for group in DEPTH_REGISTRY_CHILDREN.values() for c in group)},
                    note="approved CHILDREN only; never the whole node, never publication/certification"),
         PathFamily(f"/validation/{DEPTH}"),
         PathFamily(f"/health/brains/{DEPTH}/{{child}}", {"child": one_of(DEPTH_HEALTH_DOMAIN_CHILDREN)}, note="domain health facts only"),
         PathFamily("/activity/{event}", {"event": contains(f"-{DEPTH}-")}, note="own domain events only; retention/pruning is a platform concern")),
        delete_families=(PathFamily(f"/brains/{DEPTH}/lastError"),), delete_reasons=("OPTIONAL_CHILD_CLEARED",), volatile=DEPTH_VOLATILE_CONTRACT_V1)
    return [lake_state, registry]


def depth_bundles() -> list[BundleSpec]:
    return [BundleSpec(DEPTH_BUNDLE, DEPTH, DEPTH_SCHEMAS)]


def default_registry() -> Registry:
    """Wind, Fish, Water Clarity, Sector Intelligence, Lake, Water Temperature, Depth and Vegetation (all SHADOW). A registration describes a Brain's
    write set so it can be certified; it activates nothing (Publisher LIVE authorizes no Brain)."""
    return Registry(wind_specs() + fish_specs() + clarity_specs() + intelligence_specs() + lake_specs() + water_temp_specs() + depth_specs(),
                    wind_bundles() + fish_bundles() + clarity_bundles() + intelligence_bundles() + lake_bundles() + water_temp_bundles() + depth_bundles())
