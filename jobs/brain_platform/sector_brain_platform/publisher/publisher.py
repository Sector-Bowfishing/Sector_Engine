"""ShadowPublisher: validate -> SKIP | SHADOW_READY | REJECTED | FAILED_VALIDATION. Never writes a live database.

Order (BRAIN_READ_WRITE_SECURITY_V1 section 3): shape, brainId/identity, schema, paths, lineage, lifecycle+status+freshness, values, size,
recomputed fingerprint, baseline comparison. The first failing stage rejects; the outcome is recorded in history only.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass, field

from . import validate as V
from .canonical import canonical_bytes, sha256_ref
from .refs import ArtifactRef
from .model import (DEFAULT_SCOPE, PUBLISHER_IDENTITY, RECORD_STATUS, PublisherMode, Rejected, Result, Violation)
from .plan import UpdatePlan, artifact_patch, build_update_plan, path_fingerprints
from .registry import Registry
from .sinks import ShadowSink, require_shadow_sink
from .storage import PublishHistory

TRIGGERS = ("SCHEDULE", "DEPENDENCY", "MANUAL_REQUEST")
MAX_CLOCK_SKEW = dt.timedelta(minutes=5)


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
    def evaluate_reference(self, ref: ArtifactRef, *, trigger: str = "DEPENDENCY") -> PublishResult:
        """The target handoff: the API signal named an artifact; the Publisher loads it from private storage and runs the SAME validation as
        evaluate(). The reference is checked for namespace/shape, the stored bytes for the declared hash, and the artifact for agreement with
        the request (artifactId, executionId, schema). The Publisher never writes artifacts/ on this path."""
        producer = ref.brain_id
        if producer not in self.registry.brains:
            raise UnknownProducer(f"{producer!r} is not a registered Brain")
        publish_id, now = self._new_id(), _iso(self._clock())
        base = {"publishId": publish_id, "brainId": producer, "scope": DEFAULT_SCOPE, "evaluatedAt": now, "publisher": PUBLISHER_IDENTITY, "mode": self.mode.value,
                "trigger": trigger, "artifactSchema": ref.expected_schema if self.registry.spec(ref.expected_schema) else None}
        base = {k: v for k, v in base.items() if v is not None}
        if ref.request_id:
            base["requestId"] = ref.request_id
        stored_id = ref.artifact_id if isinstance(ref.artifact_id, str) else None
        try:
            ref.validate()
            data = self.history.read_artifact_bytes(producer, ref.artifact_id)
            if data is None:
                raise Rejected([Violation("ARTIFACT_NOT_FOUND", f"no artifact at {ref.location}")])
            if sha256_ref(data) != ref.sha256:
                raise Rejected([Violation("ARTIFACT_HASH_MISMATCH", f"stored bytes hash to {sha256_ref(data)}, request declared {ref.sha256}")])
            try:
                raw = json.loads(data)
            except ValueError:
                raise Rejected([Violation("MALFORMED", "stored artifact is not valid JSON")]) from None
            lin = raw.get("lineage") if isinstance(raw, dict) and isinstance(raw.get("lineage"), dict) else {}
            mism = [k for k, want in (("artifactId", ref.artifact_id), ("executionId", ref.execution_id), ("artifactSchema", ref.expected_schema))
                    if k in lin and lin[k] != want]
            if mism:
                raise Rejected([Violation("ARTIFACT_BINDING_MISMATCH", f"artifact disagrees with the request on {mism}")])
        except Rejected as r:
            base["artifactId"] = stored_id or "unreferenced"
            return self._rejected(None, base, r, stored=True)
        return self._run(raw, producer, base, stored_id=ref.artifact_id)

    def evaluate(self, raw, *, producer: str, trigger: str = "SCHEDULE", request_id: str | None = None) -> PublishResult:
        """Local/test convenience: the artifact is supplied directly (and persisted by the Publisher in SHADOW). The production handoff is
        evaluate_reference(); both go through the same _run() and the same validation stages."""
        if producer not in self.registry.brains:
            raise UnknownProducer(f"{producer!r} is not a registered Brain")
        if trigger not in TRIGGERS:
            raise ValueError(f"trigger must be one of {TRIGGERS}")
        publish_id, now = self._new_id(), _iso(self._clock())
        scope = raw.get("scope", DEFAULT_SCOPE) if isinstance(raw, dict) and isinstance(raw.get("scope"), str) and V.SCOPE.fullmatch(raw["scope"]) else DEFAULT_SCOPE
        base = {"publishId": publish_id, "brainId": producer, "scope": scope, "evaluatedAt": now, "publisher": PUBLISHER_IDENTITY, "mode": self.mode.value,
                "trigger": trigger}
        if request_id:
            base["requestId"] = request_id
        return self._run(raw, producer, base, stored_id=None)

    def _run(self, raw, producer, base, *, stored_id) -> PublishResult:
        lineage = raw.get("lineage") if isinstance(raw, dict) and isinstance(raw.get("lineage"), dict) else {}
        if isinstance(raw, dict) and isinstance(raw.get("scope"), str) and V.SCOPE.fullmatch(raw["scope"]):
            base["scope"] = raw["scope"]
        scope = base["scope"]
        schema = lineage.get("artifactSchema") if isinstance(lineage.get("artifactSchema"), str) and self.registry.spec(lineage.get("artifactSchema")) else None
        if schema:
            base["artifactSchema"] = schema
            head0 = self.history.head(producer, schema, scope)
            if head0:
                base["previousPublishId"] = head0["publishId"]
        try:
            muts, spec, fp, artifact_id = self._validate(raw, producer, stored_id)
        except Rejected as r:
            if stored_id:
                base["artifactId"] = stored_id
            return self._rejected(raw, base, r, stored=stored_id is not None)
        base.update(artifactSchema=spec.schema_id, artifactId=artifact_id, executionId=lineage["executionId"], generatedAt=lineage["generatedAt"],
                    knowledgeRelease=lineage["knowledgeRelease"], codeVersion=lineage["codeVersion"], inputFingerprint=lineage["inputFingerprint"],
                    outputFingerprint=fp, lifecycle=lineage["lifecycle"], reviewStatus=lineage["reviewStatus"], validationStatus=lineage["validationStatus"])
        head = self.history.head(producer, spec.schema_id, scope)
        if head:
            base["previousPublishId"] = head["publishId"]
        if head and head.get("outputFingerprint") == fp:
            rec = {**base, "result": Result.SKIP.value, "status": RECORD_STATUS[Result.SKIP], "baselineFingerprint": head["outputFingerprint"]}
            return self._record_only(Result.SKIP, rec)
        try:
            self._check_order(lineage["generatedAt"], head)
        except Rejected as r:
            return self._rejected(raw, base, r, stored=stored_id is not None)
        return self._ready(raw, base, muts, stored=stored_id is not None)

    def _check_order(self, generated_at: str, head: dict | None) -> None:
        """ARTIFACT_OLDER_THAN_BASELINE rule (exact; fail closed).
        Applies when the artifact's material content differs from the scope's baseline (equal content is a SKIP before this runs).
        Compared: the artifact's lineage.generatedAt against the baseline record's generatedAt (itself taken from a validated lineage), both parsed as
        ISO-8601 UTC at full sub-second precision. Wall-clock arrival order is never used.
          candidate  >  baseline  -> accepted
          candidate  <= baseline  -> ARTIFACT_OLDER_THAN_BASELINE (equality with different content is ambiguous order, so also rejected)
          either side missing or unparsable -> BASELINE_ORDER_UNKNOWN
          candidate  >  publisher clock + MAX_CLOCK_SKEW -> ARTIFACT_FROM_FUTURE (a future-dated artifact would block every later honest one)
        An older artifact is replayed only by an explicit rollback (a separate, later, approved mechanism)."""
        cand = V.parse_time(generated_at)
        if cand is not None and cand > self._clock() + MAX_CLOCK_SKEW:
            raise Rejected([Violation("ARTIFACT_FROM_FUTURE", f"generatedAt {generated_at} is more than {int(MAX_CLOCK_SKEW.total_seconds() // 60)} min ahead of the Publisher clock")])
        if head is None:
            return
        base_t = V.parse_time(head.get("generatedAt"))
        if cand is None or base_t is None:
            raise Rejected([Violation("BASELINE_ORDER_UNKNOWN", "cannot establish ordering against the baseline (generatedAt missing or unparsable); refusing to replace it")])
        if cand <= base_t:
            raise Rejected([Violation("ARTIFACT_OLDER_THAN_BASELINE", f"generatedAt {generated_at} is not after the baseline's {head['generatedAt']} "
                                                                     f"(baseline publishId {head['publishId']})")])

    # ------------------------------------------------------------------------------------------------------------------------------------
    def _validate(self, raw, producer, stored_id=None):
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
        artifact_id = lineage.get("artifactId") or stored_id or self._new_id()
        if stored_id is None and self.history.artifact_conflicts(brain, artifact_id, raw):
            raise Rejected([Violation("ARTIFACT_ID_CONFLICT", f"artifactId {artifact_id} already holds different content (artifacts are immutable)")])
        return muts, spec, fp, artifact_id

    def _ready(self, raw, base, muts, stored=False) -> PublishResult:
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
            if not stored:
                self.history.put_artifact(base["brainId"], base["artifactId"], raw)
            self.sink.submit(plan, rec)                    # if this raises nothing below ran: no record, no head advance
            self.history.append_record(rec)
            self.history.advance_head(rec)
            res.persisted = True
        return res

    def _record_only(self, result: Result, rec: dict) -> PublishResult:
        res = PublishResult(result, self.mode, rec)
        if self.mode is PublisherMode.SHADOW:
            self.history.append_record(rec)
            res.persisted = True
        return res

    def _rejected(self, raw, base, r: Rejected, stored: bool = False) -> PublishResult:
        """`stored`: the artifact already lives in private storage (reference flow); the record points at it and nothing is written to artifacts/."""
        result = r.result
        rec = {**base, "result": result.value, "status": RECORD_STATUS[result], "violations": list(r.violations)}
        res = PublishResult(result, self.mode, rec, violations=list(r.violations))
        if stored:
            rec.setdefault("artifactId", "unreferenced")
        else:
            rec["artifactId"] = f"rejected-{base['publishId']}"
        if self.mode is PublisherMode.SHADOW:
            if not stored:
                try:
                    canonical_bytes(raw)
                    self.history.put_artifact(base["brainId"], rec["artifactId"], raw)       # the rejected artifact stays with its rejection record
                    rec["artifactStored"] = True
                except (TypeError, ValueError):
                    rec["artifactStored"] = False
            self.history.append_record(rec)
            res.persisted = True
        return res
