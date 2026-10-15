"""Wind publish-artifact builder (Brain Certification V1, Publisher V1 SHADOW contract). NOT wired into wind-hourly.

Wind computes domain truth exactly as today (`publish.publish`), but instead of PATCHing production it can hand the SAME payload to this module,
which re-expresses it as Publisher artifacts (`publish-artifact-v1`) with child-level SET mutations. Nothing here writes to any database or bucket.

Design rules (Publisher V1 shadow contract):
  * the registry is published as approved CHILD nodes of /brains/wind; never the whole node, never /brains/wind/publication (Publisher-owned);
  * no null / empty value is ever emitted, so nothing can be deleted implicitly. RTDB itself drops null keys and empty containers on write, so omitting
    them yields exactly the node that is stored live today (equivalence, not a behaviour change). A null inside a LIST cannot be omitted without
    shifting indices, so it is refused (ArtifactBuildError) rather than guessed;
  * paths the Publisher's Wind schemas do not authorise are NOT smuggled in; they are reported in `dropped` with the reason so a human decides;
  * deterministic: the same patches + context give byte-identical artifacts (ids derive from content; no clock, no randomness inside).
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from dataclasses import dataclass, field

from . import contract as C

ENVELOPE = "publish-artifact-v1"
LINEAGE = "brain-lineage-v1"
SCHEMA_LAKE, SCHEMA_REGISTRY, SCHEMA_SOURCES = "wind-lake-state-v1", "wind-registry-v1", "wind-source-registry-v1"

_LAKE_RX = r"([A-Za-z0-9_]+)"
#: Baseline scopes WITHIN wind-lake-state-v1 (Publisher scope = baseline key per (brainId, schema, scope)). Splitting by rate of change lets the slow parts SKIP
#: while the hourly state changes, instead of rewriting ~700 unchanged paths every run. States, fleet slots and the snapshot compatibility copy stay together
#: (they must publish in the same atomic plan).
SCOPE_LIVE, SCOPE_STATIC, SCOPE_READINESS = "lake-live", "lake-static", "fleet-readiness"
_SCOPES = [(rf"lakes/{_LAKE_RX}/states/wind", SCOPE_LIVE), (rf"lakeFleet/{_LAKE_RX}/slots/wind", SCOPE_LIVE), (rf"snapshots/{_LAKE_RX}/latest/wind", SCOPE_LIVE),
           (rf"lakes/{_LAKE_RX}/profiles/wind", SCOPE_STATIC), (rf"lakes/{_LAKE_RX}/validation/wind", SCOPE_STATIC), (rf"lakeFleet/{_LAKE_RX}/modelVersions/wind", SCOPE_STATIC),
           (rf"lakeFleet/{_LAKE_RX}/readiness/wind", SCOPE_READINESS)]

#: Wind-specific volatile fields, EXCLUDED from outputFingerprint on top of the shared defaults (generatedAt publishedAt checkedAt ageHours durationMs).
#: Each changes every run without any change in the physical wind state. Evidence times (observationTime, forecastGeneratedAt, latestObservationAt,
#: latestIssuedAt, validTime) are deliberately NOT listed: a new observation is a material change. These must also be registered in the Publisher's
#: wind_specs() (a platform-lane change; see WIND_PUBLISHER_SHADOW_INTEGRATION_REPORT.md).
WIND_VOLATILE_EXTRA = frozenset({"inputAgeHours", "lastUpdatedAt", "updatedAt", "lastRun", "lastSuccess", "lastSuccessfulRun", "lastFetchAt", "latencyMs"})

#: Children of /brains/wind that Wind owns (mirror of the Publisher's WIND_REGISTRY_CHILDREN; asserted equal in tests).
REGISTRY_CHILDREN = frozenset({"brainId", "displayName", "domain", "question", "platform", "version", "schemaVersion", "stalenessModel", "dependsOn", "descriptor",
                               "versions", "activeProductionModel", "researchCandidate", "scores", "readinessDefinitions", "stateKinds", "schedule", "enabled",
                               "health", "status", "supportedLakeCount", "profiledLakeCount", "readinessCounts", "staleLakeCount", "staleAfterHours",
                               "staleRule", "lastSuccessfulRun", "lastError", "deploymentVersion", "breakdowns", "runsPerMinute", "updatedAt", "publishMode"})
WIND_SOURCES = ("noaa-nbm-v5", "noaa-rtma-ru", "iem-metar-wind")

_LAKE = _LAKE_RX = r"([A-Za-z0-9_]+)"
_ROUTES = [  # (regex over the flat RTDB key, schema)
    (rf"lakes/{_LAKE}/(states|profiles)/wind", SCHEMA_LAKE), (rf"lakes/{_LAKE}/validation/wind", SCHEMA_LAKE),
    (rf"lakeFleet/{_LAKE}/(slots|readiness|modelVersions)/wind", SCHEMA_LAKE), (rf"snapshots/{_LAKE}/latest/wind", SCHEMA_LAKE),
    (r"validation/wind", SCHEMA_REGISTRY), (r"health/brains/wind", SCHEMA_REGISTRY), (r"activity/[^/]+-wind-[^/]+", SCHEMA_REGISTRY),
    (r"sources/(%s)" % "|".join(WIND_SOURCES), SCHEMA_SOURCES), (r"health/sources/(%s)" % "|".join(WIND_SOURCES), SCHEMA_SOURCES),
]
_NOT_AUTHORISED = [  # paths wind-hourly writes today that no Publisher Wind schema authorises -> reported, never smuggled in
    (rf"lakeFleet/{_LAKE}/lakeId", "shared identity field, open to every Brain today; not a Wind family in Publisher V1"),
    (rf"snapshots/{_LAKE}/latest/lakeId", "shared snapshot identity field; Publisher authorises only /snapshots/{k}/latest/wind"),
    (rf"snapshots/{_LAKE}/latest/brainVersions/wind", "legacy snapshot sub-field; Publisher authorises only /snapshots/{k}/latest/wind"),
    (r"health/jobs/wind-hourly", "job record; /jobs is Orchestrator-owned and no Wind schema authorises /health/jobs/*"),
]


class ArtifactBuildError(ValueError):
    pass


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(obj) -> str:
    return "sha256:" + hashlib.sha256(canonical(obj)).hexdigest()


_ABSENT = object()


def normalize(v, path=""):
    """Value as RTDB would store it: None keys and empty containers vanish. Returns _ABSENT if nothing remains."""
    if v is None:
        return _ABSENT
    if isinstance(v, float) and not math.isfinite(v):
        raise ArtifactBuildError(f"non-finite number at {path or '/'}")
    if isinstance(v, dict):
        out = {}
        for k in sorted(v):
            n = normalize(v[k], f"{path}/{k}")
            if n is not _ABSENT:
                out[k] = n
        return out or _ABSENT
    if isinstance(v, (list, tuple)):
        out = []
        for i, x in enumerate(v):
            n = normalize(x, f"{path}/{i}")
            if n is _ABSENT:
                if x is None:
                    raise ArtifactBuildError(f"null inside a list at {path}/{i}: cannot be omitted without shifting indices; encode UNKNOWN explicitly")
                continue                  # an empty container element: also dropped by RTDB
            out.append(n)
        return out or _ABSENT
    return v


def _parse(s):
    try:
        return dt.datetime.fromisoformat(s[:-1] + "+00:00") if isinstance(s, str) and s.endswith("Z") else None
    except ValueError:
        return None


def _iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class BuildContext:
    generated_at: str                 # ISO-8601 UTC; the run's `now`
    execution_id: str                 # UUIDv4 of this wind-hourly run
    code_version: str                 # Wind's own commit (sha12), not the orchestrator's
    evidence_sha256: str = "NONE"     # sha256 of validation_evidence.json (an input digest)
    knowledge_release: str = "NONE"   # NONE until Wind defines a canonical release (all three of release/manifest/sha must be NONE or all declared)
    manifest_ref: str = "NONE"
    manifest_sha256: str = "NONE"
    lifecycle: str = "CALIBRATION"
    review_status: str = "UNREVIEWED"
    validation_status: str = "NOT_VALIDATED"
    scope: str | None = None


@dataclass
class BuildResult:
    artifacts: list = field(default_factory=list)
    dropped: list = field(default_factory=list)          # [{path, reason}]  not authorised by any Wind schema (reported, not published)
    unsupported: list = field(default_factory=list)      # [{path, reason}]  shapes the artifact path cannot express yet
    omitted_unknown: int = 0                             # values omitted because they were null/empty (RTDB-equivalent)


def merge_patches(patches) -> dict:
    flat: dict = {}
    for p in patches:
        flat.update(p)
    return flat


def _route(key):
    for rx, schema in _ROUTES:
        if re.fullmatch(rx, key):
            return schema
    return None


def _freshness(states: dict) -> dict:
    """evidenceObservedAt / staleAfter / freshnessStatus from the Wind state records, using Wind's EXISTING thresholds (no threshold change)."""
    if not states:
        return {"freshnessStatus": "UNKNOWN"}
    obs, stale_after, kinds, stale = [], [], [], False
    for s in states.values():
        t = _parse(s.get("observationTime")) or _parse(s.get("forecastGeneratedAt"))
        if t:
            obs.append(t)
        gen = _parse((s.get("provenance") or {}).get("generatedAt"))
        cyc = _parse(s.get("forecastGeneratedAt"))
        if gen:
            stale_after.append(gen + dt.timedelta(minutes=C.STALE_GENERATED_MIN))
        if cyc:
            stale_after.append(cyc + dt.timedelta(hours=C.STALE_FORECAST_CYCLE_H))
        kinds.append(s.get("kind"))
        stale = stale or bool(s.get("stale"))
    fr = {}
    if obs:
        fr["evidenceObservedAt"] = _iso(max(obs))
    if stale_after:
        fr["staleAfter"] = _iso(min(stale_after))
    fr["freshnessStatus"] = "UNAVAILABLE" if all(k == "unavailable" for k in kinds) else ("STALE" if stale else "FRESH")
    return fr


def build_artifacts(patches, ctx: BuildContext) -> BuildResult:
    """patches: the list of {flat-rtdb-key: value} dicts one wind-hourly publish() run would PATCH (e.g. DryRunWriter.patches)."""
    res = BuildResult()
    flat = merge_patches(patches)
    muts: dict[tuple, dict] = {}
    states = {}

    def put(schema, path, value):
        scope = next((sc for rx, sc in _SCOPES if re.fullmatch(rx, path.lstrip("/"))), None) if schema == SCHEMA_LAKE else None
        n = normalize(value, path)
        if n is _ABSENT:
            res.omitted_unknown += 1
            return
        if value != n:
            res.omitted_unknown += 1          # nulls/empties inside the value were dropped (RTDB-equivalent)
        muts.setdefault((schema, scope), {})["/" + path.lstrip("/")] = n

    for key in sorted(flat):
        val = flat[key]
        if key == "brains/wind":                                     # whole-node write -> approved children
            if not isinstance(val, dict):
                raise ArtifactBuildError("brains/wind must be an object")
            for child in sorted(val):
                if child not in REGISTRY_CHILDREN:
                    res.unsupported.append({"path": f"/brains/wind/{child}", "reason": "child not in the approved Wind registry children; ownership ambiguous, not published"})
                else:
                    put(SCHEMA_REGISTRY, f"brains/wind/{child}", val[child])
            continue
        if key.startswith("brains/wind/") or key.startswith("health/brains/wind/"):
            res.unsupported.append({"path": "/" + key, "reason": "leaf write below an exact-depth family (failure-path health patch); no artifact expression yet"})
            continue
        why = next((r for rx, r in _NOT_AUTHORISED if re.fullmatch(rx, key)), None)
        if why:
            res.dropped.append({"path": "/" + key, "reason": why})
            continue
        schema = _route(key)
        if schema is None:
            res.unsupported.append({"path": "/" + key, "reason": "no Wind schema covers this path"})
            continue
        if re.fullmatch(rf"lakes/{_LAKE}/states/wind", key) and isinstance(val, dict):
            states[key] = val
        put(schema, key, val)

    in_fp = sha({"states": {k: {"obs": s.get("observationTime"), "fcst": s.get("forecastGeneratedAt")} for k, s in sorted(states.items())},
                 "evidence": ctx.evidence_sha256, "model": C.CANDIDATE_MODEL, "brainVersion": C.BRAIN_VERSION})
    order = [SCHEMA_LAKE, SCHEMA_REGISTRY, SCHEMA_SOURCES]
    for schema, scope in sorted(muts, key=lambda k: (order.index(k[0]), k[1] or "")):
        ms = [{"op": "SET", "path": p, "value": v} for p, v in sorted(muts[(schema, scope)].items())]
        if not ms:
            continue
        lin = {"schema": LINEAGE, "brainId": C.BRAIN_ID, "artifactSchema": schema, "knowledgeRelease": ctx.knowledge_release, "manifestRef": ctx.manifest_ref,
               "manifestSha256": ctx.manifest_sha256, "codeVersion": ctx.code_version, "executionId": ctx.execution_id, "inputFingerprint": in_fp,
               "outputFingerprint": "sha256:" + "0" * 64, "generatedAt": ctx.generated_at, "lifecycle": ctx.lifecycle, "reviewStatus": ctx.review_status,
               "validationStatus": ctx.validation_status}
        art = {"envelope": ENVELOPE, "lineage": lin, "mutations": ms}
        if schema == SCHEMA_LAKE:
            art["freshness"] = _freshness(states)
        if scope or ctx.scope:
            art["scope"] = scope or ctx.scope
        res.artifacts.append(art)
    return res


def seal(artifacts, fingerprint_fn) -> None:
    """Set outputFingerprint (via the PUBLISHER's own function, passed in so Wind never re-implements it) and a content-derived artifactId."""
    for art in artifacts:
        lin = art["lineage"]
        lin["outputFingerprint"] = fingerprint_fn(lin["brainId"], lin["artifactSchema"], art["mutations"], WIND_VOLATILE_EXTRA)
        lin.pop("artifactId", None)
        lin["artifactId"] = sha(art)
