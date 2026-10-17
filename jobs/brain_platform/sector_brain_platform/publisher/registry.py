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


def default_registry() -> Registry:
    """Wind and Fish. Every other Brain is registered as an identity (so an unknown id is distinguishable from an unmigrated one) but has no schema:
    anything submitted for them is rejected UNKNOWN_SCHEMA until their own certification registers one."""
    return Registry(wind_specs() + fish_specs(), wind_bundles() + fish_bundles())
