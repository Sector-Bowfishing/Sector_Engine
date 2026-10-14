"""Biological Brain (`biological-state`), species-knowledge side.

Answers "What does Sector know about this fish?" by publishing lightweight summaries of the canonical
species-knowledge bundle. The bundle itself (detailed profiles, rules, evidence, history) is PRIVATE and lives in
gs://sector-biology-private; this public module only knows its *shape*. It never invents, rescales or rounds a
score of its own: it verifies the bundle (hashes, structure, and that every overall equals the v2 weighted sum)
and fails closed on anything inconsistent, then passes the values through.

The per-lake Biological State ("What is this fish likely doing on this lake right now?") is NOT built here yet.

Contract: docs/brains/BIOLOGICAL_BRAIN_INTEGRATION.md; Sector_Ops docs/BRAIN_INTEGRATION_REQUIREMENTS.md section 7.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re

from capability import IN_PROGRESS_NOTE, NOT_STARTED_NOTE  # noqa: E402  (stdlib-only sibling module)
import bands as _bands  # noqa: E402
import target_set as _targets  # noqa: E402

BRAIN_ID = "biological-state"
DISPLAY_NAME = "Biological Brain"
BRAIN_VERSION = "biological-brain-0.1.0"
SCHEMA_VERSION = 1
BUNDLE_SCHEMA_VERSION = 1
SCORING_VERSION = "species-v2"

# The v2 Species Knowledge rubric (SPECIES_SCORING_STANDARD.md v2). Engine validates against it; it does not score.
DOMAINS = [
    ("seasonalLocationReproduction", "Seasonal location & reproduction", 20),
    ("habitatDepthCover", "Habitat, depth & cover", 20),
    ("temperatureOxygen", "Temperature & oxygen", 15),
    ("hydrologyRainInflowLevel", "Hydrology, rain, inflow & level", 15),
    ("foodFeedingLocation", "Food & feeding location", 10),
    ("dayNightMovement", "Day/night movement", 10),
    ("clarityLightWind", "Clarity, light & wind", 5),
    ("aggregationMobilityLifeStage", "Aggregation, mobility & life stage", 5),
]
DOMAIN_IDS = [d[0] for d in DOMAINS]
WEIGHTS = {d[0]: d[2] for d in DOMAINS}

ASSESSMENT = ("ASSESSED", "NOT_ASSESSED")
# researchMaturity is its own field: not the knowledge score, the Brain lifecycle, runtime health, lake readiness,
# current biological state or evidence quality.
RESEARCH_MATURITY = {
    "NOT_STARTED": "No usable species evidence has been compiled (every v2 dimension unknown), or the row is not assessable.",
    "RESEARCH": "Evidence compiled and scored against the v2 rubric; not independently reviewed or field-validated.",
    "REVIEWED": "Not used yet: research independently reviewed and signed off.",
    "VALIDATED": "Not used yet: species rules checked against field observations.",
}
DOMAIN_STATUS = ("SCORED", "UNKNOWN")
SPECIES_ID = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
MAX_TEXT = 220


class BundleError(ValueError):
    """The canonical bundle is missing, corrupted or inconsistent. Nothing is published."""


def round_half(x: float) -> float:
    """Nearest 0.5, exact ties round up (standard v2)."""
    return math.floor(x * 2 + 0.5 + 1e-9) / 2


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _short(s, n=MAX_TEXT):
    if s is None:
        return None
    s = str(s).strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _clean(o):
    """RTDB stores no nulls and no empty containers: drop them so 'unknown stays unknown' (absent)."""
    if isinstance(o, dict):
        out = {k: _clean(v) for k, v in o.items()}
        return {k: v for k, v in out.items() if v is not None and v != {} and v != []}
    if isinstance(o, list):
        out = [_clean(v) for v in o]
        return [v for v in out if v is not None and v != {} and v != []]
    if isinstance(o, float) and (math.isnan(o) or math.isinf(o)):
        raise BundleError("non-finite number in payload")
    return o


# ---------------------------------------------------------------- bundle
class Bundle:
    """A verified canonical bundle: manifest + registry + per-species profiles (+ discrepancies)."""

    def __init__(self, pointer: dict, manifest: dict, files: dict[str, bytes], manifest_ref: str):
        self.pointer, self.manifest, self.files, self.manifest_ref = pointer, manifest, files, manifest_ref
        self.registry = json.loads(files["registry.json"])
        self.discrepancies = json.loads(files["discrepancies.json"]).get("discrepancies", []) if "discrepancies.json" in files else []
        self.profiles = {e["speciesId"]: json.loads(files[e["profile"]]) for e in self.registry["species"]}
        import capability                      # local import: capability reads rules/validation artifacts; absent artifacts -> NOT_STARTED
        self.capability = capability.assess(files)
        self.rule_counts = self.capability["facts"].get("ruleCountsBySpecies", {})
        self.ruleset = self.capability.get("ruleset")        # a validated RuleSet or None; bands are compiled only from validated rules

    @property
    def research_version(self) -> str:
        return self.manifest["researchVersion"]


def load_bundle(read, pointer_path: str = "latest.json") -> Bundle:
    """`read(path) -> bytes` reads relative to the bundle root (biology/v1/ in the bucket, or a local dir)."""
    pointer = json.loads(read(pointer_path))
    if pointer.get("schemaVersion") != BUNDLE_SCHEMA_VERSION or pointer.get("brainId") != BRAIN_ID:
        raise BundleError(f"unexpected pointer {pointer_path}: schemaVersion/brainId")
    mpath = pointer["manifest"]
    mraw = read(mpath)
    if sha256(mraw) != pointer["manifestSha256"]:
        raise BundleError("manifest sha256 does not match latest.json")
    manifest = json.loads(mraw)
    root = mpath.rsplit("/", 1)[0] if "/" in mpath else ""
    files = {}
    for f in manifest.get("files", []):
        raw = read(f"{root}/{f['path']}" if root else f["path"])
        if sha256(raw) != f["sha256"] or len(raw) != f["bytes"]:
            raise BundleError(f"artifact hash/size mismatch: {f['path']}")
        files[f["path"]] = raw
    b = Bundle(pointer, manifest, files, mpath)
    validate(b)
    return b


def validate(b: Bundle) -> None:
    """Structural + arithmetic checks. Any failure aborts the whole publish (fail closed)."""
    m = b.manifest
    if m.get("schemaVersion") != BUNDLE_SCHEMA_VERSION or m.get("brainId") != BRAIN_ID:
        raise BundleError("manifest schemaVersion/brainId")
    if m.get("scoringVersion") != SCORING_VERSION:
        raise BundleError(f"bundle scoringVersion {m.get('scoringVersion')!r}; this brain validates {SCORING_VERSION!r}")
    if "registry.json" not in b.files:
        raise BundleError("registry.json missing from manifest")
    ids = [e["speciesId"] for e in b.registry["species"]]
    if len(ids) != len(set(ids)):
        raise BundleError("duplicate speciesId in registry")
    for sid, p in b.profiles.items():
        where = f"species {sid}"
        if not SPECIES_ID.match(sid) or p.get("speciesId") != sid:
            raise BundleError(f"{where}: speciesId must be snake_case and match its profile")
        if p.get("assessment") not in ASSESSMENT:
            raise BundleError(f"{where}: assessment")
        if p.get("researchMaturity") not in RESEARCH_MATURITY:
            raise BundleError(f"{where}: researchMaturity {p.get('researchMaturity')!r}")
        k = p.get("knowledge") or {}
        if k.get("rubric") != SCORING_VERSION:
            raise BundleError(f"{where}: rubric")
        doms = k.get("domains") or {}
        if p["assessment"] == "NOT_ASSESSED":
            if doms or k.get("overallExact") is not None:
                raise BundleError(f"{where}: a NOT_ASSESSED species carries no scores")
            continue
        if list(doms) != DOMAIN_IDS:
            raise BundleError(f"{where}: domains must be exactly the v2 dimensions in order")
        total = 0
        for did, d in doms.items():
            s = d.get("score")
            if not isinstance(s, int) or not 0 <= s <= 10:
                raise BundleError(f"{where}.{did}: score must be a whole number 0-10")
            if d.get("weight") != WEIGHTS[did]:
                raise BundleError(f"{where}.{did}: weight {d.get('weight')} != v2 {WEIGHTS[did]}")
            if d.get("status") not in DOMAIN_STATUS or (d["status"] == "UNKNOWN") != (s == 0):
                raise BundleError(f"{where}.{did}: status must be UNKNOWN exactly when the score is 0")
            total += s * d["weight"]
        exact = total / 100
        if abs(exact - k.get("overallExact", -1)) > 0.005:
            raise BundleError(f"{where}: overallExact {k.get('overallExact')} != weighted sum {exact}")
        if round_half(exact) != k.get("overallRounded"):
            raise BundleError(f"{where}: overallRounded {k.get('overallRounded')} != round_half({exact})")
        if p["researchMaturity"] in ("REVIEWED", "VALIDATED"):
            raise BundleError(f"{where}: {p['researchMaturity']} is not used yet; promotion is a separate decision")


# ---------------------------------------------------------------- payloads (lightweight summaries only)
def species_summary(p: dict, b: Bundle, profile_uri: str, now: str) -> dict:
    k = p["knowledge"]
    disc = {d["id"]: dict(title=_short(d.get("title")), status=d.get("status"), **{"class": d.get("class")})
            for d in b.discrepancies if p["speciesId"] in d.get("species", [])}
    hist = [dict(date=h.get("date"), rubric=h.get("rubric"), overallRounded=h.get("overallRounded"), overallExact=h.get("overallExact"),
                 label=_short(h.get("label"), 60), reason=_short(h.get("reason"), 160)) for h in (p.get("history") or [])[-14:]]
    ev = p.get("evidence") or {}
    contradictions = sum(len(d.get("contradictions") or []) for d in (k.get("domains") or {}).values())
    return _clean(dict(
        speciesId=p["speciesId"], schemaVersion=SCHEMA_VERSION, displayName=p.get("displayName"), scientificName=p.get("scientificName"),
        aliases=p.get("aliases"), appKeys=p.get("appKeys"), taxonomyStatus=p.get("taxonomyStatus"),
        taxonomyNote=_short((p.get("taxonomyNotes") or [None])[0]),
        assessment=p["assessment"], researchMaturity=p["researchMaturity"], researchVersion=p.get("researchVersion"),
        scoringVersion=p.get("scoringVersion"), lastReviewedAt=p.get("lastReviewedAt"),
        knowledge=dict(rubric=k.get("rubric"), overallExact=k.get("overallExact"), overallRounded=k.get("overallRounded"),
                       domains={did: dict(label=d.get("label"), weight=d.get("weight"), score=d.get("score"), status=d.get("status"),
                                          potentialGainPerPoint=d.get("potentialGainPerPoint"))
                                for did, d in (k.get("domains") or {}).items()},
                       strongest=k.get("strongest"), weakest=k.get("weakest"), unknownDomains=k.get("unknownDomains")),
        nextResearchPriority=_short(p.get("nextResearchPriority")),
        topGaps=[_short(g) for g in (p.get("gaps") or [])[:3]],
        contradictionCount=contradictions or None,
        ruleCount=len(p.get("rules") or []) or None,
        machineRules=(b.rule_counts.get(p["speciesId"]) if getattr(b, "rule_counts", None) else None),
        responseBands=(_bands.compile_species_bands(p["speciesId"], b.ruleset.active_rules(), generated_at=now, rules_version=b.ruleset.rules_version)
                       if getattr(b, "ruleset", None) else None),
        evidence=dict(relationshipRecordCount=ev.get("relationshipRecordCount"),
                      sourcesByVerification=ev.get("sourcesByVerification2026_10_12")),
        openDiscrepancies=disc,
        policyNote=_short(p.get("policyNote")),
        separateAssessments=p.get("separateAssessments"),
        movement=({k: v for k, v in (p.get("movement") or {}).items() if k in ("passLevel", "generalConfidence", "regionalConfidence", "bowfisherTakeaway", "bowfisherKnowledge", "sourcesInspected", "sourcesTotal", "cardVersion")} or None),
        productRole=_targets.role(p["speciesId"]),
        history=hist,
        profileRef=profile_uri, profileSha256=next((f["sha256"] for f in b.manifest["files"] if f["path"] == f"species/{p['speciesId']}.json"), None),
        updatedAt=now))


def _state_responsibility(b: Bundle) -> dict:
    """Lifecycle comes from VERIFIED capability (capability.assess), never from a flag. Never LIVE/VALIDATED here."""
    c = b.capability
    q = "What is this fish likely doing on this lake right now?"
    if c["status"] == "IN_PROGRESS":
        f = c["facts"]
        return dict(status="IN_PROGRESS", validation=c["validation"], question=q, note=IN_PROGRESS_NOTE, pilotLakes=f.get("pilotLakes"),
                    rulesVersion=f.get("rulesVersion"), speciesWithUsableRules=f.get("speciesWithUsableRules"), usableRules=f.get("usableRules"),
                    draftRules=f.get("draftRules"), retiredRules=f.get("retiredRules"), frozenRules=f.get("frozenRules"), predictionsLogged=f.get("predictionsLogged", 0), observationsLogged=f.get("observationsLogged", 0), independentTrips=f.get("independentTrips", 0))
    return dict(status="NOT_STARTED", question=q, note=NOT_STARTED_NOTE + (f" Capability blockers: {'; '.join(c['blockers'][:3])}" if b.capability["facts"] else ""))


def _facts(b: Bundle, by_m: dict) -> list:
    """Generic, Engine-computed maturity facts [{label, value}] that an Ops renderer can show verbatim without per-Brain code."""
    f = b.capability["facts"]
    if not f:
        return []
    ts = f.get("transferSummary") or {}
    tr = ts.get("byTransferability") or {}
    rows = [("Species with usable rules", f.get("speciesWithUsableRules")), ("Usable rules", f.get("usableRules")), ("Draft rules", f.get("draftRules")),
            ("Retired rules", f.get("retiredRules")), ("Frozen rules", f.get("frozenRules")), ("Predictions logged", f.get("predictionsLogged", 0)),
            ("Observations logged", f.get("observationsLogged", 0)), ("Independent trips", f.get("independentTrips", 0)),
            ("Rules with Southeast-transferable evidence", f"{tr.get('TRANSFERS', 0)} of {ts.get('usableRules', 0)}" if ts else None),
            ("Validated species", by_m.get("VALIDATED", 0)), ("Pilot lakes", ", ".join(f.get("pilotLakes") or []) or None), ("Rules version", f.get("rulesVersion"))]
    return [dict(label=k, value=v) for k, v in rows if v is not None]


def registry_entry(b: Bundle, now: str, health: str, deployment: str, manifest_uri: str, descriptor: dict) -> dict:
    profiles = list(b.profiles.values())
    by_m, by_a = {}, {}
    for p in profiles:
        by_m[p["researchMaturity"]] = by_m.get(p["researchMaturity"], 0) + 1
        by_a[p["assessment"]] = by_a.get(p["assessment"], 0) + 1
    open_disc = [d for d in b.discrepancies if d.get("status") == "OPEN"]
    return _clean(dict(
        platform=PLATFORM, facts=_facts(b, by_m), targetReadiness=(b.capability["facts"].get("targetReadiness") or None), targetSet=dict(version=_targets.TARGET_SET_VERSION, targets=sorted(_targets.TARGET), secondary=sorted(_targets.SECONDARY),
                                                              knowledgeOnlyCount=len([s for s in b.profiles if _targets.role(s) == "KNOWLEDGE_ONLY"])), transferSummary=(b.capability["facts"].get("transferSummary") or None),
        stalenessModel="VERSION", dependsOn=[],
        schedule=dict(cadence="manual (version-driven: runs when the canonical bundle changes)", running=False),
        brainId=BRAIN_ID, displayName=DISPLAY_NAME, domain="biology",
        question="What does Sector know about each fish, and what is it likely doing?",
        version=BRAIN_VERSION, schemaVersion=SCHEMA_VERSION, enabled=True, health=health,
        status="PROFILED",
        statusBasis=("Species knowledge is compiled and scored (research only). "
                     + ("An internal pilot Biological State is being built from verified rules; nothing is published per lake, so no lake readiness exists."
                        if b.capability["status"] == "IN_PROGRESS" else
                        "No per-lake Biological State is published, so no lake readiness exists.")),
        supportedLakeCount=0, staleLakeCount=0, lastSuccessfulRun=now, deploymentVersion=deployment, publishMode="manual",
        researchVersion=b.research_version, scoringVersion=b.manifest.get("scoringVersion"),
        manifestRef=manifest_uri, manifestSha256=b.pointer.get("manifestSha256"),
        responsibilities=dict(
            speciesKnowledge=dict(status="PUBLISHED", question="What does Sector know about this fish?",
                                  speciesCount=len(profiles), assessedCount=by_a.get("ASSESSED", 0), notAssessedCount=by_a.get("NOT_ASSESSED", 0)),
            biologicalState=_state_responsibility(b)),
        breakdowns=dict(researchMaturity=by_m, assessment=by_a),
        researchMaturityDefinitions=RESEARCH_MATURITY,
        rubric=dict(id=SCORING_VERSION, dimensions={did: dict(label=label, weight=w) for did, label, w in DOMAINS},
                    dimensionOrder=DOMAIN_IDS,   # RTDB returns map keys sorted; this array keeps the rubric order
                    note="Evidence-completeness scores, not probabilities or predictive accuracy. Overall = sum(score x weight)/100, rounded to 0.5 (ties up). Potential gain per point = weight/100."),
        speciesGroups=b.registry.get("speciesGroups"),
        discrepancies=dict(openCount=len(open_disc),
                           items={d["id"]: dict(title=_short(d.get("title")), status=d.get("status"), species=d.get("species"),
                                                lakeId=d.get("lakeId"), decision=_short(d.get("decision"), 300), **{"class": d.get("class")})
                                  for d in b.discrepancies}),
        knownLimitations=b.manifest.get("knownLimitations"),
        orchestration=descriptor,
        versions=[dict(version=BRAIN_VERSION, date=now[:10], status="CURRENT",
                       note=f"Species knowledge {b.research_version} ({len(profiles)} species, {SCORING_VERSION}); Biological State not started")]))


def validation_summary(now: str, capability: dict | None = None) -> dict:
    f = (capability or {}).get("facts") or {}
    foundation = dict(frozenRules=f.get("frozenRules"), predictionsLogged=f.get("predictionsLogged", 0)) if f.get("frozenRules") else None
    return dict(brainId=BRAIN_ID, modelVersion=SCORING_VERSION, status="NOT_VALIDATED", lastRunAt=now, lakeCount=0, validationFoundation=foundation,
                statusNote=("Species knowledge scores measure evidence completeness, not predictive accuracy. No species rule has been "
                            "checked against field observations. "
                            + ("An internal pilot Biological State exists and its predictions are logged, but no prediction has been compared with an outcome."
                               if (capability or {}).get("status") == "IN_PROGRESS" else "No per-lake Biological State model exists yet.")))


def health_record(now: str, duration_ms: int, deployment: str, status: str = "HEALTHY", error: str | None = None) -> dict:
    return _clean(dict(status=status, lastRun=now, lastSuccess=now if status == "HEALTHY" else None, durationMs=duration_ms,
                       staleLakeCount=0, errorCount=0 if error is None else 1, latestError=error, deployedVersion=deployment, publishMode="manual"))


# The shared Brain Platform this brain publishes through (docs/brains/BRAIN_PLATFORM_CONTRACT.md §13; Engine Score reads it).
PLATFORM = {"implementation": "sector_brain_platform", "contract": "docs/brains/BRAIN_PLATFORM_CONTRACT.md v1.0", "conformant": True}


def build_updates(b: Bundle, *, now: dt.datetime, uri_root: str, deployment: str, descriptor: dict, duration_ms: int,
                  published: dict | None, existing_species: set[str] | None, event_id: str | None) -> dict:
    """The complete multi-path update for one publish (applied atomically)."""
    ts = now.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    manifest_uri = f"{uri_root}/{b.manifest_ref}"
    up = {}
    for sid, p in b.profiles.items():
        root = b.manifest_ref.rsplit("/", 1)[0]
        up[f"/species/{sid}"] = species_summary(p, b, f"{uri_root}/{root}/species/{sid}.json", ts)
    for gone in sorted((existing_species or set()) - set(b.profiles)):
        up[f"/species/{gone}"] = None                       # retired from the registry: remove its summary
    up[f"/brains/{BRAIN_ID}"] = registry_entry(b, ts, "HEALTHY", deployment, manifest_uri, descriptor)
    up[f"/validation/{BRAIN_ID}"] = _clean(validation_summary(ts, b.capability))
    up[f"/health/brains/{BRAIN_ID}"] = health_record(ts, duration_ms, deployment)
    prev = (published or {}).get("researchVersion")
    if event_id and prev != b.research_version:
        up[f"/activity/{event_id}"] = dict(id=event_id, at=ts, brainId=BRAIN_ID, kind="brain.version" if prev else "brain.registered", severity="success",
                                           title=f"Biological Brain species knowledge {b.research_version} published ({len(b.profiles)} species)"
                                                 + (f"; was {prev}" if prev else ""))
    return up


def check_keys(updates: dict) -> None:
    """RTDB forbids . $ # [ ] / in keys (paths may contain /)."""
    bad = re.compile(r"[.$#\[\]/]")

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if bad.search(str(k)):
                    raise BundleError(f"illegal RTDB key {k!r} at {path}")
                walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}/{i}")
    for p, v in updates.items():
        if any(bad.search(seg) for seg in p.strip("/").split("/")):
            raise BundleError(f"illegal RTDB path {p!r}")
        walk(v, p)
