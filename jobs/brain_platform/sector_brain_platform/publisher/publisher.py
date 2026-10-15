"""ShadowPublisher: validate -> SKIP | SHADOW_READY | REJECTED | FAILED_VALIDATION. Never writes a live database.

Order (BRAIN_READ_WRITE_SECURITY_V1 section 3): shape, brainId/identity, schema, paths, lineage, lifecycle+status+freshness, values, size,
recomputed fingerprint, baseline comparison. The first failing stage rejects; the outcome is recorded in history only.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from dataclasses import dataclass, field

from . import artifact as A
from . import validate as V
from .canonical import ALGORITHM, canonical_bytes, sha256_ref
from .refs import ArtifactRef
from .model import (DEFAULT_SCOPE, PUBLISHER_IDENTITY, RECORD_STATUS, PublisherMode, Rejected, Result, Violation)
from .plan import UpdatePlan, artifact_patch, build_update_plan, derive_projections, path_fingerprints
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
        """ONE accepted artifact -> ONE decision -> ONE plan -> ONE publication record. Nothing is persisted or handed to the sink until the whole
        artifact (every section, every mutation, every derived projection) has been validated and the single plan has been built."""
        lin0 = raw.get("lineage") if isinstance(raw, dict) and isinstance(raw.get("lineage"), dict) else {}
        if isinstance(raw, dict) and raw.get("envelope") == "publish-artifact-v1" and isinstance(raw.get("scope"), str) and V.SCOPE.fullmatch(raw["scope"]):
            base["scope"] = raw["scope"]
        sid0 = lin0.get("artifactSchema") if isinstance(lin0.get("artifactSchema"), str) else None
        if sid0 and (self.registry.spec(sid0) or self.registry.bundle(sid0)):
            base["artifactSchema"] = sid0
            if self.registry.spec(sid0):
                head0 = self.history.head(producer, sid0, base["scope"])
                if head0:
                    base["previousPublishId"] = head0["publishId"]
        try:
            parsed = A.parse(raw, producer, self.registry, self._resolve)
            lineage = parsed.lineage
            artifact_id = lineage.get("artifactId") or stored_id or self._new_id()
            if stored_id is None and self.history.artifact_conflicts(producer, artifact_id, raw):
                raise Rejected([Violation("ARTIFACT_ID_CONFLICT", f"artifactId {artifact_id} already holds different content (artifacts are immutable)")])
        except Rejected as r:
            if stored_id:
                base["artifactId"] = stored_id
            return self._rejected(raw, base, r, stored=stored_id is not None)

        base.update(artifactSchema=lineage["artifactSchema"], artifactId=artifact_id, executionId=lineage["executionId"], generatedAt=lineage["generatedAt"],
                    knowledgeRelease=lineage["knowledgeRelease"], codeVersion=lineage["codeVersion"], inputFingerprint=lineage["inputFingerprint"],
                    outputFingerprint=parsed.fingerprint, fingerprintAlgorithm=ALGORITHM, lifecycle=lineage["lifecycle"], reviewStatus=lineage["reviewStatus"],
                    validationStatus=lineage["validationStatus"])
        base.pop("scope", None) if parsed.envelope == "v2" else None
        # baselines, per section
        heads = {(s.schema_id, s.scope): self.history.head(producer, s.schema_id, s.scope) for s in parsed.sections}
        gens = {k: self.history.head_generation(producer, k[0], k[1]) for k in heads}
        prior = [h for h in heads.values() if h]
        if prior:
            base["previousPublishId"] = max(prior, key=lambda h: (h.get("evaluatedAt", ""), h["publishId"]))["publishId"]
        sec_info, changed = [], []
        for sec in parsed.sections:
            h = heads[(sec.schema_id, sec.scope)]
            same = bool(h) and h.get("outputFingerprint") == sec.fingerprint and h.get("fingerprintAlgorithm") == ALGORITHM
            info = {"artifactSchema": sec.schema_id, "scope": sec.scope, "outputFingerprint": sec.fingerprint, "result": "SKIP" if same else "SHADOW",
                    "volatileContract": sec.spec.volatile.id}
            if h:
                info["previousPublishId"] = h["publishId"]
            if sec.freshness:
                info["freshnessStatus"] = sec.freshness["freshnessStatus"]
            sec_info.append(info)
            if not same:
                changed.append(sec)
        base["sections"] = sec_info
        if not changed:
            rec = {**base, "result": Result.SKIP.value, "status": RECORD_STATUS[Result.SKIP]}
            return self._record_only(Result.SKIP, rec)
        try:
            self._check_order(lineage["generatedAt"], [(s, heads[(s.schema_id, s.scope)]) for s in changed])
            derived = derive_projections(changed, parsed.sections)
            if derived:
                V.check_overlaps([(f"{s.schema_id}:{s.scope}", m) for s in changed for m in s.mutations] + [(f"derived:{d['rule']}", d) for d in derived])
        except Rejected as r:
            if any(v["code"] in ("OVERLAPPING_PATHS", "SET_DELETE_CONFLICT") for v in r.violations):
                r = Rejected([Violation("PROJECTION_CONFLICT", v["detail"], v.get("path")) for v in r.violations])
            return self._rejected(raw, base, r, stored=stored_id is not None)
        return self._ready(raw, base, parsed, changed, derived, gens, stored=stored_id is not None)

    def _check_order(self, generated_at: str, changed_with_heads) -> None:
        """ARTIFACT_OLDER_THAN_BASELINE rule (exact; fail closed). Evaluated per CHANGED section against that section's baseline (identical sections are a SKIP
        before this runs); ONE failing section rejects the WHOLE artifact.
          candidate  >  baseline  -> accepted
          candidate  <= baseline  -> ARTIFACT_OLDER_THAN_BASELINE (equality with different content is ambiguous order, so also rejected)
          either side missing or unparsable -> BASELINE_ORDER_UNKNOWN
          candidate  >  publisher clock + MAX_CLOCK_SKEW -> ARTIFACT_FROM_FUTURE (a future-dated artifact would block every later honest one)
        Compared: lineage.generatedAt vs the baseline's recorded generatedAt, ISO-8601 UTC at full sub-second precision. Arrival order is never used.
        An older artifact is replayed only by an explicit rollback (a separate, later, approved mechanism)."""
        cand = V.parse_time(generated_at)
        if cand is not None and cand > self._clock() + MAX_CLOCK_SKEW:
            raise Rejected([Violation("ARTIFACT_FROM_FUTURE", f"generatedAt {generated_at} is more than {int(MAX_CLOCK_SKEW.total_seconds() // 60)} min ahead of the Publisher clock")])
        bad = []
        for sec, head in changed_with_heads:
            if head is None:
                continue
            base_t = V.parse_time(head.get("generatedAt"))
            tag = f"[{sec.schema_id}:{sec.scope}] "
            if cand is None or base_t is None:
                bad.append(Violation("BASELINE_ORDER_UNKNOWN", tag + "cannot establish ordering against the baseline (generatedAt missing or unparsable); refusing to replace it"))
            elif cand <= base_t:
                bad.append(Violation("ARTIFACT_OLDER_THAN_BASELINE", tag + f"generatedAt {generated_at} is not after the baseline's {head['generatedAt']} "
                                                                           f"(baseline publishId {head['publishId']})"))
        if bad:
            raise Rejected(bad)

    def _ready(self, raw, base, parsed, changed, derived, gens, stored=False) -> PublishResult:
        authored = [m for s in changed for m in s.mutations]
        rec = {**base, "result": Result.SHADOW_READY.value, "status": RECORD_STATUS[Result.SHADOW_READY], "live": False,
               "removed": sorted(m["path"] for m in authored + derived if m["op"] == "DELETE")}
        if derived:
            counts = {}
            for d in derived:
                counts[d["rule"]] = counts.get(d["rule"], 0) + 1
            rec["derived"] = [{"rule": r, "count": n} for r, n in sorted(counts.items())]
        everything = authored + derived
        rec["pathSha256"] = path_fingerprints(everything)
        patch = artifact_patch(everything)
        rec["artifactPatchSha256"] = sha256_ref(canonical_bytes(patch))
        rec["paths"] = {"count": len(patch), "bytes": len(canonical_bytes(patch))}
        plan = build_update_plan(base["brainId"], authored, rec, derived)      # the ONE plan; the ONE publication record is embedded in it
        rec["updateSha256"] = plan.update_sha256
        res = PublishResult(Result.SHADOW_READY, self.mode, rec, plan)
        if self.mode is PublisherMode.SHADOW:
            rec["headGenerations"] = {f"{s.schema_id}/{s.scope}": gens[(s.schema_id, s.scope)] for s in changed}
            if not stored:
                self.history.put_artifact(base["brainId"], base["artifactId"], raw)
            self.sink.submit(plan, rec)                    # if this raises nothing below ran: no record, no head advance
            self.history.append_record(rec)
            for s in changed:
                self.history.advance_head(base["brainId"], s.schema_id, s.scope,
                                          {"publishId": rec["publishId"], "artifactId": rec["artifactId"], "outputFingerprint": s.fingerprint,
                                           "fingerprintAlgorithm": ALGORITHM, "generatedAt": rec["generatedAt"], "evaluatedAt": rec["evaluatedAt"]},
                                          gens[(s.schema_id, s.scope)])
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
