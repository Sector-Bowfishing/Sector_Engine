"""Parse and validate ONE logical artifact (envelope v1 = one section, v2 = several sections) into a `Parsed` value, or raise Rejected.

Everything is validated BEFORE any plan exists: all sections, all mutations, lineage, lifecycle, values, sizes and fingerprints. Any single failure rejects
the WHOLE artifact; no partial plan can survive because no plan is built until this function has returned.
"""
from __future__ import annotations

from dataclasses import dataclass

from . import validate as V
from .canonical import bundle_fingerprint, canonical_bytes, output_fingerprint
from .model import DEFAULT_SCOPE, Rejected, Violation
from .registry import BundleSpec, Registry, SchemaSpec


@dataclass(frozen=True)
class Section:
    spec: SchemaSpec
    scope: str
    mutations: tuple              # normalised, sorted by path
    freshness: dict | None
    fingerprint: str              # semantic section fingerprint (recomputed by the Publisher)

    @property
    def schema_id(self) -> str:
        return self.spec.schema_id


@dataclass(frozen=True)
class Parsed:
    envelope: str                 # 'v1' | 'v2'
    brain_id: str
    lineage: dict
    sections: tuple               # canonical order: (schema, scope)
    fingerprint: str              # artifact-level semantic fingerprint (== the section fingerprint for v1)
    bundle: BundleSpec | None = None

    def all_mutations(self) -> list:
        return [m for s in self.sections for m in s.mutations]


def section_fingerprint(spec: SchemaSpec, brain_id: str, mutations) -> str:
    return output_fingerprint(brain_id, spec.schema_id, list(mutations), spec.volatile.keys, spec.volatile.paths)


def parse(raw, producer: str, registry: Registry, release_resolver=None) -> Parsed:
    kind = V.check_shape(raw)
    lineage = raw["lineage"]
    brain = V.check_brain(lineage, producer, registry)
    bundle = None
    if kind == "v1":
        specs = [V.check_schema(lineage, brain, registry)]
        sec_in = [(specs[0], raw.get("scope", DEFAULT_SCOPE), raw["mutations"], raw.get("freshness"))]
    else:
        bundle = registry.bundle(lineage.get("artifactSchema"))
        if bundle is None:
            raise Rejected([Violation("UNKNOWN_SCHEMA", f"artifactSchema {lineage.get('artifactSchema')!r} is not a registered bundle")])
        if bundle.brain_id != brain:
            raise Rejected([Violation("SCHEMA_BRAIN_MISMATCH", f"bundle {bundle.bundle_id!r} belongs to {bundle.brain_id!r}, not {brain!r}")])
        if len(raw["sections"]) > bundle.max_sections:
            raise Rejected([Violation("OVERSIZE", f"{len(raw['sections'])} sections exceeds {bundle.max_sections}")])
        sec_in, seen, bad = [], set(), []
        for sec in raw["sections"]:
            spec = registry.spec(sec["artifactSchema"])
            if spec is None:
                bad.append(Violation("UNKNOWN_SCHEMA", f"section schema {sec['artifactSchema']!r} is not registered"))
            elif spec.brain_id != brain or spec.schema_id not in bundle.sections:
                bad.append(Violation("SECTION_NOT_ALLOWED", f"schema {spec.schema_id!r} is not an allowed section of {bundle.bundle_id!r}"))
            else:
                key = (spec.schema_id, sec.get("scope", DEFAULT_SCOPE))
                if key in seen:
                    bad.append(Violation("DUPLICATE_SECTION", f"section {key} appears twice"))
                seen.add(key)
                sec_in.append((spec, key[1], sec["mutations"], sec.get("freshness")))
        if bad:
            raise Rejected(bad)
        specs = [s[0] for s in sec_in]

    # stage 3: paths, every section; collect ALL violations across sections
    bad, normalised = [], []
    for spec, scope, muts, fr in sec_in:
        try:
            normalised.append((spec, scope, V.check_paths(muts, brain, spec, registry), fr))
        except Rejected as r:
            bad += [Violation(v["code"], f"[{spec.schema_id}:{scope}] {v['detail']}", v.get("path")) for v in r.violations]
    if bad:
        raise Rejected(bad)
    V.check_overlaps([(f"{sp.schema_id}:{sc}", m) for sp, sc, ms, _ in normalised for m in ms])

    # stage 4-5
    V.check_lineage(lineage, any(sp.require_release for sp in specs), release_resolver)
    V.check_lifecycle_and_status(raw, specs, bundle.allowed_lifecycles if bundle else None)
    for spec, scope, ms, fr in normalised:
        V.check_freshness(fr, spec)
    # stage 5b / 6: values and sizes
    for spec, scope, ms, fr in normalised:
        V.check_values(ms, spec, registry)
        V.check_size(ms, spec)
    total = len(canonical_bytes([m for _, _, ms, _ in normalised for m in ms]))
    cap = bundle.max_bytes if bundle else specs[0].max_bytes
    if total > cap:
        raise Rejected([Violation("OVERSIZE", f"{total} bytes exceeds {cap}")])

    # stage 7: fingerprints, recomputed (the declared value is never trusted)
    sections = tuple(sorted((Section(sp, sc, tuple(sorted(ms, key=lambda m: m["path"])), fr, section_fingerprint(sp, brain, ms)) for sp, sc, ms, fr in normalised),
                            key=lambda s: (s.schema_id, s.scope)))
    fp = sections[0].fingerprint if kind == "v1" else bundle_fingerprint(brain, bundle.bundle_id, [(s.schema_id, s.scope, s.fingerprint) for s in sections])
    if lineage["outputFingerprint"] != fp:
        raise Rejected([Violation("FINGERPRINT_MISMATCH", f"declared {lineage['outputFingerprint']} but the canonical content hashes to {fp}")])
    return Parsed(kind, brain, lineage, sections, fp, bundle)
