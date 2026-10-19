"""Water Clarity publish-artifact builder for Publisher V2 (envelope v2, bundle `clarity-publication-v1`). SHADOW CONTRACT ONLY. NOT wired into any job write path.

ONE Clarity execution -> ONE `publish-artifact-v2` -> ONE Publisher evaluation -> ONE atomic plan (SKIP or SHADOW_READY, or the whole artifact is rejected).

Clarity still computes domain truth with the unchanged `clarity_brain` builders; this module re-expresses the multi-path update dictionary that `run.py` would send
to the Brain RTDB as the sections of one sealed bundle. It adds no science and changes no value. Design rules (the ones Wind's and Fish's builders follow):
  * the routing authority for every path is the Publisher registry (`default_registry()` -> `clarity-lake-state-v1`, `clarity-registry-v1`,
    `clarity-source-registry-v1`); Clarity keeps no second ownership list. A path the registry does not author is never emitted: it is reported in `dropped`
    with its classification (platform-owned / publisher-derived projection / orchestrator-owned process fact / retention), or, if nothing covers it, the build
    FAILS CLOSED (`unsupported` -> ArtifactBuildError);
  * the whole `/brains/water-clarity` node is NEVER replaced: it is split into approved CHILDREN; `publication` / `certification` stay Publisher-owned;
  * `/health/brains/water-clarity` carries domain health facts only (`status`, `staleLakeCount`); the process fields the legacy record also carries are
    Orchestrator-owned and reported in `dropped`;
  * null / missing NEVER means delete. The only inferred removal is the single declared optional child `/brains/water-clarity/lastError` (typed DELETE,
    reason OPTIONAL_CHILD_CLEARED), exactly as Wind's registration; every other null/empty value is plain absence ("unknown stays unknown");
  * lineage is truthful and unfabricated: `consumed` is passed through only when the caller really recorded reads (RTDB reads only: GCS/HTTP reads are NOT
    recorded by the platform recorder, so absent = unknown, never []); knowledgeRelease / manifestRef / manifestSha256 are NONE (Clarity has no canonical
    versioned release or manifest; the catalog digest is carried in `inputFingerprint`);
  * freshness keeps four distinct concepts apart: satellite scene observation time (`evidenceObservedAt`), the Engine evaluation the estimate restates
    (`inputGeneratedAt`), the Brain's generation time (lineage `generatedAt`) and the publication time (the Publisher's). `lastSuccessfulRun` is never evidence freshness;
  * no clock, no randomness, no I/O: same updates + same BuildContext => byte-identical artifact. The semantic fingerprint, the volatile contract
    (`clarity-volatile-v1`) and the bundle seal are the PUBLISHER's (`seal_bundle`); nothing is re-implemented here.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import re
from dataclasses import dataclass, field

import brain_platform as _bp          # noqa: F401  (resolves the shared platform package: repo layout or staged image)
import clarity_brain as cb
from sector_brain_platform.publisher import default_registry, seal_bundle
from sector_brain_platform.publisher.registry import CLARITY_BUNDLE, CLARITY_HEALTH_DOMAIN_CHILDREN

CLARITY = cb.BRAIN_ID
SCHEMA_LAKE, SCHEMA_REGISTRY, SCHEMA_SOURCES = "clarity-lake-state-v1", "clarity-registry-v1", "clarity-source-registry-v1"
LAST_ERROR_PATH = f"/brains/{CLARITY}/lastError"
LAST_ERROR_CLEARED = "OPTIONAL_CHILD_CLEARED"
LIFECYCLE = "CALIBRATION"     # == brain.json lifecycle == control_manifest lifecycle (tested); Clarity is not promoted by having a contract

_LAKE = r"([A-Za-z0-9_]+)"
SCOPE_LIVE, SCOPE_STATIC, SCOPE_READINESS = "lake-live", "lake-static", "fleet-readiness"
_SCOPES = [(rf"/lakes/{_LAKE}/states/{cb.SLOT}", SCOPE_LIVE), (rf"/lakeFleet/{_LAKE}/slots/{cb.SLOT}(/[a-zA-Z]+)?", SCOPE_LIVE),
           (rf"/lakes/{_LAKE}/profiles/{cb.SLOT}", SCOPE_STATIC), (rf"/lakeFleet/{_LAKE}/modelVersions/{cb.SLOT}", SCOPE_STATIC),
           (rf"/lakeFleet/{_LAKE}/readiness/{cb.SLOT}", SCOPE_READINESS)]
_ORDER = (SCHEMA_LAKE, SCHEMA_REGISTRY, SCHEMA_SOURCES)

#: How the legacy writer's paths that Clarity does NOT author are classified (the direct-write audit's table, as data). First match wins.
#: classification: PLATFORM_OWNED | DERIVED_COMPATIBILITY_PROJECTION | LEGACY_READER_DEPENDENCY | CLARITY_DOMAIN_TRUTH ; mechanism says who produces it at cutover.
NOT_AUTHORED = (
    (re.compile(rf"/lakeFleet/{_LAKE}/lakeId"), "lakefleet-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),
    (re.compile(rf"/snapshots/{_LAKE}/latest/lakeId"), "snapshot-lakeid", "PLATFORM_OWNED", "STOP_WRITING", "Platform Lake Registry (lake identity)"),
    (re.compile(r"/health/jobs/.+"), "health-jobs", "PLATFORM_OWNED", "ORCHESTRATOR_DERIVED", "Orchestrator (/jobs + execution ledger)"),
    (re.compile(rf"/health/brains/{CLARITY}/.+"), "health-brains-process", "LEGACY_READER_DEPENDENCY", "ORCHESTRATOR_DERIVED", "Orchestrator (execution / deployment state)"),
    (re.compile(r"/activity/.+"), "activity-retention", "PLATFORM_OWNED", "STOP_WRITING", "Platform maintenance (bounded-ring retention); a Brain never edits activity after the fact"),
)


class ArtifactBuildError(ValueError):
    pass


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def sha(obj) -> str:
    return "sha256:" + hashlib.sha256(canonical(obj)).hexdigest()


def catalog_digest() -> str:
    """Digest (never content) of the catalog this run loaded: public catalog merged with the private overlay when one was supplied. Carried in inputFingerprint."""
    return sha({"catalog": cb.CATALOG, "detail": cb.CATALOG_DETAIL})


_ABSENT = object()


def normalize(v, path=""):
    """The value as RTDB would store it: None keys and empty containers vanish (absence, never a delete). Returns _ABSENT if nothing remains."""
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
                continue
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


@dataclass(frozen=True)
class BuildContext:
    """Everything the artifact needs that Clarity itself must not invent (supplied by the runner; tests pin it)."""
    generated_at: str                 # ISO-8601 UTC ...Z; the run's `now`
    execution_id: str                 # UUIDv4 of this run (ONE per logical artifact)
    code_version: str                 # the deployed code identity
    catalog_sha256: str = "NONE"      # catalog_digest() of the loaded catalog (an input digest, never content)
    lifecycle: str = LIFECYCLE
    review_status: str = "UNREVIEWED"
    validation_status: str = "NOT_VALIDATED"


@dataclass
class BuildResult:
    artifact: dict | None = None
    dropped: list = field(default_factory=list)       # [{path, row, classification, mechanism, targetOwner, why}]  Clarity does not author these
    unsupported: list = field(default_factory=list)   # always empty on success: an uncovered path fails closed
    omitted_unknown: int = 0                          # null/empty values omitted (absence; never a delete)
    deletes: list = field(default_factory=list)       # [{path, reason}] explicit typed deletes emitted


def _scope(path, schema):
    if schema != SCHEMA_LAKE:
        return None
    return next((sc for rx, sc in _SCOPES if re.fullmatch(rx, path)), None)


def freshness(states: dict, generated_at: str, threshold_h: float = cb.STALE_AFTER_H) -> dict:
    """Section freshness from the lake states, using Clarity's EXISTING threshold (staleAfterHours; no threshold change). Only evidence that exists is reported:
      evidenceObservedAt  newest satellite SCENE observation across lakes (gauge reading times are UNKNOWN in the Engine payload; never substituted)
      inputGeneratedAt    newest Engine /conditions evaluation the estimates restate (`evaluationTime`)
      staleAfter          earliest (Engine evaluation + staleAfterHours): the TIME model applied to the INPUT, not to this run
      freshnessStatus     UNAVAILABLE (every lake unavailable) | STALE (some evaluation older than the threshold at generation) | FRESH | UNKNOWN (no evaluation time at all)
    Satellite staleness (14-day window) stays per-lake inside each state; it is not collapsed into this block."""
    if not states:
        return {"freshnessStatus": "UNKNOWN"}
    gen = _parse(generated_at)
    scenes, evals, stale_after, stale, all_unavailable = [], [], [], False, True
    for s in states.values():
        all_unavailable = all_unavailable and s.get("stateType") == "UNAVAILABLE"
        t = _parse(s.get("satelliteObservationAt"))
        if t:
            scenes.append(t)
        e = _parse(s.get("evaluationTime"))
        if e:
            evals.append(e)
            deadline = e + dt.timedelta(hours=threshold_h)
            stale_after.append(deadline)
            stale = stale or (gen is not None and gen > deadline)
    fr = {}
    if scenes:
        fr["evidenceObservedAt"] = _iso(max(scenes))
    if evals:
        fr["inputGeneratedAt"] = _iso(max(evals))
    if stale_after:
        fr["staleAfter"] = _iso(min(stale_after))
    fr["freshnessStatus"] = "UNAVAILABLE" if all_unavailable else ("STALE" if stale else ("FRESH" if evals else "UNKNOWN"))
    return fr


def input_fingerprint(states: dict, ctx: BuildContext) -> str:
    """Identity of what this run was computed from: per lake the input sources it actually used (type, id, observation time), the loaded catalog digest and the
    Brain version. No execution id, no run timestamps => unchanged inputs give an unchanged fingerprint."""
    lakes = {}
    for path, s in sorted(states.items()):
        srcs = [{"t": x.get("sourceType"), "id": x.get("sourceId"), "obs": x.get("lastObservationAt")} for x in (s.get("provenance") or {}).get("sources") or []]
        lakes[path] = {"stateType": s.get("stateType"), "engineEvaluatedAt": s.get("evaluationTime"), "sources": sorted(srcs, key=lambda x: json.dumps(x, sort_keys=True))}
    return sha({"lakes": lakes, "catalogSha256": ctx.catalog_sha256, "brainVersion": cb.BRAIN_VERSION})


class _Router:
    def __init__(self, registry):
        self.reg = registry
        self.specs = [registry.spec(s) for s in registry.schemas_for(CLARITY)]

    def authoring_spec(self, path, delete=False):
        for sp in self.specs:
            if self.reg.authorizing_family(sp, path, delete=delete) is not None:
                return sp
        return None

    def not_authored(self, path):
        pr = self.reg.derived_target(CLARITY, path)
        if pr is not None:
            return {"path": path, "row": pr.id, "projection": pr.id, "classification": pr.classification, "mechanism": "PUBLISHER_DERIVED", "targetOwner": pr.owner,
                    "why": f"Publisher-derived compatibility projection ({pr.id}); retirement gate: {pr.retirement_gate}"}
        for rx, row, cls, mech, owner in NOT_AUTHORED:
            if rx.fullmatch(path):
                return {"path": path, "row": row, "classification": cls, "mechanism": mech, "targetOwner": owner, "why": f"{row}: {mech}"}
        return None


def _expand(flat):
    """Whole-node writes of the legacy writer -> child paths. Returns [(path, value)]."""
    out = []
    for key in sorted(flat):
        val = flat[key]
        path = "/" + key.lstrip("/")
        if path in (f"/brains/{CLARITY}", f"/health/brains/{CLARITY}"):
            if not isinstance(val, dict):
                raise ArtifactBuildError(f"{path} must be an object")
            out += [(f"{path}/{c}", val[c]) for c in sorted(val)]
        else:
            out.append((path, val))
    return out


def build_artifact(updates: dict, ctx: BuildContext, registry=None, consumed=None, removals=()) -> BuildResult:
    """updates: the flat update dictionary one `run.py` execution would send (dry-run `payload`; keys with or without a leading '/').
    consumed: the platform recorder's list for the RTDB reads this run really made, or None when unknown. removals: explicit [{path, reason}] the PRODUCER decided."""
    reg = registry or default_registry()
    router = _Router(reg)
    res = BuildResult()
    sec: dict[tuple, list] = {}
    states = {}
    last_error_none = False
    legacy_none_paths = set()

    def add(spec, path, mutation):
        sec.setdefault((spec.schema_id, _scope(path, spec.schema_id)), []).append(mutation)

    for path, val in _expand(updates):
        if path == LAST_ERROR_PATH and val is None:
            last_error_none = True                                    # explicit typed DELETE below (the legacy writer cleared it with a null)
            continue
        if val is None and path.startswith("/activity/"):
            res.dropped.append({"path": path, "row": "activity-retention", "classification": "PLATFORM_OWNED", "mechanism": "STOP_WRITING",
                                "targetOwner": "Platform maintenance (bounded-ring retention)", "why": "activity pruning is a platform retention concern; a Brain's artifact never deletes events"})
            continue
        spec = router.authoring_spec(path)
        if spec is None:
            why = router.not_authored(path)
            if why is None:
                res.unsupported.append({"path": path, "reason": "no Clarity schema family, projection or classification covers this path"})
            else:
                res.dropped.append(why)
            continue
        n = normalize(val, path)
        if n is _ABSENT:
            res.omitted_unknown += 1                                  # null/empty = absence; nothing is deleted
            legacy_none_paths.add(path)
            continue
        if n != val:
            res.omitted_unknown += 1
        if re.fullmatch(rf"/lakes/{_LAKE}/states/{cb.SLOT}", path) and isinstance(n, dict):
            states[path] = n
        add(spec, path, {"op": "SET", "path": path, "value": n})
    if res.unsupported:
        raise ArtifactBuildError("paths no Clarity registration covers (extend the Publisher registry, reviewed, instead of emitting them): "
                                 + ", ".join(sorted(u["path"] for u in res.unsupported)[:8]))

    dels = [{"path": r["path"], "reason": r["reason"]} for r in removals]
    if last_error_none:
        dels.append({"path": LAST_ERROR_PATH, "reason": LAST_ERROR_CLEARED})
    set_paths = {m["path"] for ms in sec.values() for m in ms}
    for d in sorted(dels, key=lambda d: d["path"]):
        spec = router.authoring_spec(d["path"], delete=True)
        if spec is None:
            raise ArtifactBuildError(f"no Clarity schema permits deleting {d['path']}")
        if d["reason"] not in spec.delete_reasons:
            raise ArtifactBuildError(f"delete reason {d['reason']!r} for {d['path']} is not in the closed vocabulary {list(spec.delete_reasons)}")
        if d["path"] in set_paths:
            raise ArtifactBuildError(f"{d['path']} is both SET and DELETEd in one run")
        add(spec, d["path"], {"op": "DELETE", "path": d["path"], "reason": d["reason"]})
        res.deletes.append(d)

    if not sec:
        return res
    sections = []
    for (schema, scope) in sorted(sec, key=lambda k: (_ORDER.index(k[0]), k[1] or "")):
        s = {"artifactSchema": schema, "mutations": sorted(sec[(schema, scope)], key=lambda m: m["path"])}
        if scope:
            s["scope"] = scope
        if schema == SCHEMA_LAKE:
            s["freshness"] = freshness({p: st for p, st in states.items()}, ctx.generated_at)
        sections.append(s)
    art = seal_bundle(brain_id=CLARITY, bundle_id=CLARITY_BUNDLE, sections=sections, lifecycle=ctx.lifecycle, review_status=ctx.review_status,
                      validation_status=ctx.validation_status, generated_at=ctx.generated_at, execution_id=ctx.execution_id, code_version=ctx.code_version,
                      input_fingerprint=input_fingerprint(states, ctx), knowledge_release="NONE", manifest_ref="NONE", manifest_sha256="NONE",
                      registry=reg, consumed=consumed)
    art["lineage"]["artifactId"] = sha(art)           # content address of the sealed envelope (unique per run, stable for the same inputs)
    res.artifact = art
    return res
