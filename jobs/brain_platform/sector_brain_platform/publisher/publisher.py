"""ShadowPublisher: validate -> SKIP | SHADOW_READY | REJECTED | FAILED_VALIDATION. Never writes a live database.

Order (BRAIN_READ_WRITE_SECURITY_V1 section 3): shape, brainId/identity, schema, paths, lineage, lifecycle+status+freshness, values, size,
recomputed fingerprint, baseline comparison. The first failing stage rejects; the outcome is recorded in history only.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from . import validate as V
from .canonical import canonical_bytes, sha256_ref
from .model import (DEFAULT_SCOPE, PUBLISHER_IDENTITY, RECORD_STATUS, PublisherMode, Rejected, Result, Violation)
from .plan import UpdatePlan, artifact_patch, build_update_plan, path_fingerprints
from .registry import Registry
from .sinks import ShadowSink, require_shadow_sink
from .storage import PublishHistory

TRIGGERS = ("SCHEDULE", "DEPENDENCY", "MANUAL_REQUEST")


class UnknownProducer(ValueError):
    """The authenticated submitter is not a registered Brain. Nothing can be attributed or stored, so this is an error, not a result."""


@dataclass
class PublishResult:
    result: Result
    mode: PublisherMode
    record: dict
    plan: UpdatePlan | None = None
    violations: list = field(default_factory=list)
    persisted: bool = False
    live_mutations: int = 0          # always 0 in V1

    @property
    def publish_id(self) -> str:
        return self.record["publishId"]

    @property
    def codes(self) -> list[str]:
        return [v["code"] for v in self.violations]

    @property
    def is_rejection(self) -> bool:
        return self.result in (Result.REJECTED, Result.FAILED_VALIDATION)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class ShadowPublisher:
    def __init__(self, registry: Registry, history: PublishHistory, sink: ShadowSink, *, mode: PublisherMode = PublisherMode.SHADOW,
                 clock=_now, id_factory=lambda: str(uuid.uuid4()), release_resolver=None):
        if not isinstance(mode, PublisherMode):
            raise TypeError("mode must be a PublisherMode")
        self.registry, self.history, self.mode = registry, history, mode
        self.sink = require_shadow_sink(sink)
        self._clock, self._new_id, self._resolve = clock, id_factory, release_resolver

    # ------------------------------------------------------------------------------------------------------------------------------------
    def evaluate_stored(self, producer: str, artifact_id: str, **kw) -> PublishResult:
        """Evaluate an artifact the Brain already wrote to the artifact store (the target handoff, READ_WRITE_SECURITY section 2)."""
        raw = self.history.get_artifact(producer, artifact_id)
        if raw is None:
            raise KeyError(f"no stored artifact {producer}/{artifact_id}")
        return self.evaluate(raw, producer=producer, **kw)

    def evaluate(self, raw, *, producer: str, trigger: str = "SCHEDULE", request_id: str | None = None) -> PublishResult:
        if producer not in self.registry.brains:
            raise UnknownProducer(f"{producer!r} is not a registered Brain")
        if trigger not in TRIGGERS:
            raise ValueError(f"trigger must be one of {TRIGGERS}")
        publish_id, now = self._new_id(), _iso(self._clock())
        scope = raw.get("scope", DEFAULT_SCOPE) if isinstance(raw, dict) and isinstance(raw.get("scope"), str) and V.SCOPE.fullmatch(raw["scope"]) else DEFAULT_SCOPE
        lineage = raw.get("lineage") if isinstance(raw, dict) and isinstance(raw.get("lineage"), dict) else {}
        schema = lineage.get("artifactSchema") if isinstance(lineage.get("artifactSchema"), str) and self.registry.spec(lineage.get("artifactSchema")) else None
        head = self.history.head(producer, schema, scope) if schema else None
        base = {"publishId": publish_id, "brainId": producer, "scope": scope, "evaluatedAt": now, "publisher": PUBLISHER_IDENTITY, "mode": self.mode.value,
                "trigger": trigger}
        if request_id:
            base["requestId"] = request_id
        if schema:
            base["artifactSchema"] = schema
        if head:
            base["previousPublishId"] = head["publishId"]
        try:
            muts, spec, fp, artifact_id = self._validate(raw, producer)
        except Rejected as r:
            return self._rejected(raw, base, r)
        base.update(artifactSchema=spec.schema_id, artifactId=artifact_id, executionId=lineage["executionId"], generatedAt=lineage["generatedAt"],
                    knowledgeRelease=lineage["knowledgeRelease"], codeVersion=lineage["codeVersion"], inputFingerprint=lineage["inputFingerprint"],
                    outputFingerprint=fp, lifecycle=lineage["lifecycle"], reviewStatus=lineage["reviewStatus"], validationStatus=lineage["validationStatus"])
        head = self.history.head(producer, spec.schema_id, scope)
        if head:
            base["previousPublishId"] = head["publishId"]
        if head and head["outputFingerprint"] == fp:
            rec = {**base, "result": Result.SKIP.value, "status": RECORD_STATUS[Result.SKIP], "baselineFingerprint": head["outputFingerprint"]}
            return self._record_only(Result.SKIP, rec, raw=None)
        if head and V.parse_time(lineage["generatedAt"]) <= V.parse_time(head["generatedAt"]):
            return self._rejected(raw, base, Rejected([Violation("ARTIFACT_OLDER_THAN_BASELINE", f"generatedAt {lineage['generatedAt']} is not after the "
                                                                 f"baseline's {head['generatedAt']}; an older artifact is replayed only by an explicit rollback")]))
        return self._ready(raw, base, muts)

    # ------------------------------------------------------------------------------------------------------------------------------------
    def _validate(self, raw, producer):
        V.check_shape(raw)
        lineage = raw["lineage"]
        brain = V.check_brain(lineage, producer, self.registry)
        spec = V.check_schema(lineage, brain, self.registry)
        muts = V.check_paths(raw["mutations"], brain, spec, self.registry)
        V.check_lineage(lineage, spec, self._resolve)
        V.check_semantics(raw, spec)
        V.check_values(muts, spec, self.registry)
        V.check_size(muts, spec)
        fp = V.verify_fingerprint(lineage, brain, spec, muts)
        artifact_id = lineage.get("artifactId") or self._new_id()
        if self.history.artifact_conflicts(brain, artifact_id, raw):
            raise Rejected([Violation("ARTIFACT_ID_CONFLICT", f"artifactId {artifact_id} already holds different content (artifacts are immutable)")])
        return muts, spec, fp, artifact_id

    def _ready(self, raw, base, muts) -> PublishResult:
        rec = {**base, "result": Result.SHADOW_READY.value, "status": RECORD_STATUS[Result.SHADOW_READY], "live": False, "removed": sorted(
            m["path"] for m in muts if m["op"] == "DELETE")}
        rec["pathSha256"] = path_fingerprints(muts)
        # two-phase: the record needs the patch hash, the plan embeds the record
        patch = artifact_patch(muts)
        rec["artifactPatchSha256"] = sha256_ref(canonical_bytes(patch))
        rec["paths"] = {"count": len(patch), "bytes": len(canonical_bytes(patch))}
        plan = build_update_plan(base["brainId"], muts, rec)
        rec["updateSha256"] = plan.update_sha256
        res = PublishResult(Result.SHADOW_READY, self.mode, rec, plan)
        if self.mode is PublisherMode.SHADOW:
            rec["headGeneration"] = self.history.head_generation(base["brainId"], base["artifactSchema"], base["scope"])
            self.history.put_artifact(base["brainId"], base["artifactId"], raw)
            self.sink.submit(plan, rec)                    # if this raises nothing below ran: no record, no head advance
            self.history.append_record(rec)
            self.history.advance_head(rec)
            res.persisted = True
        return res

    def _record_only(self, result: Result, rec: dict, raw) -> PublishResult:
        res = PublishResult(result, self.mode, rec)
        if self.mode is PublisherMode.SHADOW:
            self.history.append_record(rec)
            res.persisted = True
        return res

    def _rejected(self, raw, base, r: Rejected) -> PublishResult:
        result = r.result
        rejected_id = f"rejected-{base['publishId']}"
        rec = {**base, "result": result.value, "status": RECORD_STATUS[result], "violations": list(r.violations), "artifactId": rejected_id}
        res = PublishResult(result, self.mode, rec, violations=list(r.violations))
        if self.mode is PublisherMode.SHADOW:
            try:
                canonical_bytes(raw)
                self.history.put_artifact(base["brainId"], rejected_id, raw)       # the rejected artifact stays with its rejection record
                rec["artifactStored"] = True
            except (TypeError, ValueError):
                rec["artifactStored"] = False
            self.history.append_record(rec)
            res.persisted = True
        return res
