"""LivePublisher: the production publication door (repository implementation; no Brain is enabled, no client here is a production client).

Per artifact, in order, failing CLOSED at every step:
  authorization -> quarantine -> shared validation (the SHADOW validators, planner and registry, run in DRY_RUN: they persist nothing)
  -> SKIP on an unchanged fingerprint -> baseline reconciled? -> per-Brain apply lock -> live precondition (live publication == the baseline's)
  -> publisher key guard -> atomic apply (single update, or chunked MANIFEST-LAST) -> authoritative readback -> immutable record + head advance (generation-matched)
  -> score signal (S1).
dry_run() runs the identical preparation and returns the exact update that publish() would apply (dry-run/live parity).
The Publisher never writes /scores, /control, /engine, /jobs or platform health, never calculates a score, and never changes domain content.
"""
from __future__ import annotations

import datetime as dt
import uuid
from dataclasses import dataclass, field

from ..keys import check_update
from ..publisher import PublishHistory, PublisherMode, ShadowPublisher, ShadowSink
from ..publisher.canonical import sha256_ref
from ..publisher.model import Result
from ..publisher.plan import rtdb_record
from ..publisher.refs import ArtifactRef, artifact_location
from ..publisher.registry import Registry
from ..publisher.storage import PreconditionFailed
from . import apply as AP
from . import baseline as BL
from . import locks as LK
from .authorization import LiveAuthorization
from .model import (COMPLETE, LIVE_MODE, LiveError, LiveResult, NoRollbackTarget, NotAuthorized, RtdbAmbiguousFailure, RtdbDefiniteFailure)
from .security_model import assert_publisher_keys

DEFAULT_MAX_UPDATE_BYTES = 4 * 1024 * 1024


def _live_sections(sections):
    """The shadow evaluation labels a changed section "SHADOW"; a live record must never carry that word."""
    return [{**x, "result": "PUBLISHED" if x["result"] == "SHADOW" else x["result"]} for x in sections]


def _iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class LivePublishResult:
    result: LiveResult
    record: dict | None = None
    updates: dict | None = None                   # the exact multi-location update (dry_run: what WOULD be applied)
    codes: list = field(default_factory=list)
    detail: str = ""
    score_signal: dict | None = None              # S1: only for PUBLISHED / RECOVERED / ROLLED_BACK
    calls: int = 0
    mode: str | None = None                       # SINGLE | CHUNKED
    mismatched: list = field(default_factory=list)

    @property
    def publish_id(self):
        return (self.record or {}).get("publishId")


class _LiveHistory(PublishHistory):
    """The baseline the validators compare against is the last LIVE head only. A head left by the SHADOW era (no `live` flag) is invisible here, so an artifact is
    never SKIPPED against a baseline that was never proven live (P4); head GENERATIONS are still the real ones, so advance_head stays compare-and-swap."""

    def head(self, brain_id, schema, scope="default"):
        h = super().head(brain_id, schema, scope)
        return h if h and h.get("live") else None


class _NoBaselineHistory(PublishHistory):
    """Rollback re-applies the previous artifact IN FULL, so it is evaluated against NO baseline (never a SKIP, every section changed)."""

    def head(self, brain_id, schema, scope="default"):
        return None


class _RollbackShadow(ShadowPublisher):
    """Identical validation; ONLY the ordering rule differs: an explicit, approved rollback is the one case where an older artifact may replace the baseline.
    The caller (LivePublisher.rollback) has already proven the target is exactly the previous publication of the current live head."""

    def _check_order(self, generated_at, changed_with_heads):
        return None


class LivePublisher:
    def __init__(self, registry: Registry, history: PublishHistory, rtdb, authorization: LiveAuthorization, *, clock=lambda: dt.datetime.now(dt.timezone.utc),
                 id_factory=lambda: str(uuid.uuid4()), release_resolver=None, max_update_bytes: int = DEFAULT_MAX_UPDATE_BYTES, on_published=None):
        if not isinstance(authorization, LiveAuthorization):
            raise TypeError("authorization must be a LiveAuthorization")
        self.registry, self.history, self.rtdb, self.auth = registry, history, rtdb, authorization
        self._clock, self._new_id, self.max_update_bytes, self._on_published = clock, id_factory, max_update_bytes, on_published
        kw = dict(mode=PublisherMode.DRY_RUN, clock=clock, id_factory=id_factory, release_resolver=release_resolver)
        live_view = _LiveHistory(history.store)
        self._shadow = ShadowPublisher(registry, live_view, ShadowSink(), **kw)
        self._rb_shadow = _RollbackShadow(registry, _NoBaselineHistory(history.store), ShadowSink(), **kw)

    # ------------------------------------------------------------------------------------------------------------------------------------
    def publish(self, ref: ArtifactRef) -> LivePublishResult:
        return self._run(ref, apply=True)

    def dry_run(self, ref: ArtifactRef) -> LivePublishResult:
        """Same preparation as publish(); nothing is written anywhere (no lock, no record, no RTDB update). `updates` is what publish() would send."""
        return self._run(ref, apply=False)

    def _run(self, ref, apply: bool) -> LivePublishResult:
        now = _iso(self._clock())
        try:
            self.auth.check(ref.brain_id)
        except NotAuthorized as e:
            return LivePublishResult(LiveResult.NOT_AUTHORIZED, detail=str(e))
        q = LK.quarantined(self.history.store, ref.brain_id)
        if q:
            return LivePublishResult(LiveResult.QUARANTINED, detail=f"{ref.brain_id} is quarantined by {q.get('publishId')}: {q.get('reason')}; roll back or clear after review")
        res = self._shadow.evaluate_reference(ref)
        rec = {**res.record, "mode": LIVE_MODE, "live": False}
        if res.is_rejection:
            if apply:
                self.history.append_record(rec)
            return LivePublishResult(LiveResult(res.result.value), rec, codes=res.codes)
        if res.result is Result.SKIP:
            if apply:
                self.history.append_record(rec)
            return LivePublishResult(LiveResult.SKIP, rec)
        return self._ready(ref, res, rec, now, apply)

    def _ready(self, ref, res, rec, now, apply) -> LivePublishResult:
        brain, plan = rec["brainId"], res.plan
        pub_key = plan.publication_key
        changed = [s for s in rec["sections"] if s["result"] == "SHADOW"]
        heads = {(s["artifactSchema"], s["scope"]): self.history.head(brain, s["artifactSchema"], s["scope"]) for s in changed}
        store = self.history.store
        for (schema, scope), h in heads.items():
            if not BL.is_reconciled(store, brain, schema, scope, h):
                return LivePublishResult(LiveResult.BASELINE_UNRECONCILED, rec, detail=f"{schema}/{scope}: no live-reconciled baseline; run diff_against_live + acknowledge first")
        live_rec = {**rec, "result": LiveResult.PUBLISHED.value, "status": COMPLETE, "mode": LIVE_MODE, "live": True, "publishedAt": now,
                    "sections": _live_sections(rec["sections"])}
        updates = dict(plan.updates)
        live_rec["updateSha256"] = sha256_ref(AP.canonical_bytes({k: v for k, v in updates.items() if k != pub_key}))        # hash of the data update (the record cannot contain its own hash)
        updates[pub_key] = rtdb_record(live_rec)
        check_update(updates)
        try:
            assert_publisher_keys(brain, updates)
        except PermissionError as e:
            return LivePublishResult(LiveResult.REJECTED, rec, codes=["PATH_NOT_AUTHORIZED"], detail=str(e))
        expected_prev = self._expected_previous(brain, changed, heads)
        out = LivePublishResult(LiveResult.PUBLISHED, live_rec, updates, mode="SINGLE" if len(AP.canonical_bytes(updates)) <= self.max_update_bytes else "CHUNKED")
        if not apply:
            return out
        gens = {k: self.history.head_generation(brain, k[0], k[1]) for k in heads}
        pointers = {k: {"publishId": rec["publishId"], "artifactId": rec["artifactId"], "outputFingerprint": s["outputFingerprint"],
                        "fingerprintAlgorithm": rec["fingerprintAlgorithm"], "generatedAt": rec["generatedAt"], "evaluatedAt": rec["evaluatedAt"], "live": True}
                    for k, s in ((( x["artifactSchema"], x["scope"]), x) for x in changed)}
        return self._commit(brain=brain, updates=updates, pub_key=pub_key, rec_full={**live_rec, "pathSha256": rec.get("pathSha256"), "headGenerations": {f"{k[0]}/{k[1]}": g for k, g in gens.items()}},
                            pointers=pointers, gens=gens, expected_prev=expected_prev, new_artifact_id=rec["artifactId"], now=now, result_ok=LiveResult.PUBLISHED, mode=out.mode)

    def _expected_previous(self, brain, changed, heads):
        """The artifactId live `publication` must currently show: the newest live head's artifact, or (first live publish) what the baseline acknowledgement saw."""
        live_heads = [h for h in heads.values() if h and h.get("live")]
        if live_heads:
            return max(live_heads, key=lambda h: (h.get("evaluatedAt", ""), h["publishId"]))["artifactId"]
        for s in changed:
            ack = BL.acknowledgement(self.history.store, brain, s["artifactSchema"], s["scope"])
            if ack:
                return ack.get("liveArtifactId")
        return None

    # ------------------------------------------------------------------------------------------------------------------------------------
    def _plan_for_baseline(self, ref):
        self.auth.check(ref.brain_id)
        res = self._shadow.evaluate_reference(ref)
        if res.plan is None:
            raise LiveError(f"nothing to reconcile: {res.result.value} {res.codes}")
        return res

    def baseline_diff(self, ref: ArtifactRef) -> dict:
        """READ-ONLY: diff of the artifact's plan against what is live (GET only). Review this before acknowledging."""
        res = self._plan_for_baseline(ref)
        return BL.diff_against_live(self.rtdb, ref.brain_id, res.plan.updates)

    def acknowledge_baseline(self, ref: ArtifactRef, *, approval_ref: str) -> dict:
        """Record the DELIBERATE first-live baseline for every changed section of this artifact (diff recomputed now, so the record reflects current live state)."""
        res = self._plan_for_baseline(ref)
        diff = BL.diff_against_live(self.rtdb, ref.brain_id, res.plan.updates)
        live_pub = self.rtdb.get(res.plan.publication_key)
        live_id = live_pub.get("artifactId") if isinstance(live_pub, dict) else None
        now = _iso(self._clock())
        for s in res.record["sections"]:
            if s["result"] == "SHADOW":
                BL.acknowledge(self.history.store, ref.brain_id, s["artifactSchema"], s["scope"], diff=diff, approval_ref=approval_ref, now=now, live_artifact_id=live_id)
        return diff

    def _commit(self, *, brain, updates, pub_key, rec_full, pointers, gens, expected_prev, new_artifact_id, now, result_ok, mode) -> LivePublishResult:
        store = self.history.store
        publish_id = rec_full["publishId"]
        try:
            LK.acquire(store, brain, publish_id, now)
        except LK.LockBusy as e:
            return LivePublishResult(LiveResult.LOCK_BUSY, rec_full, detail=str(e))
        try:
            live_pub = self.rtdb.get(pub_key)
            lp = live_pub if isinstance(live_pub, dict) else {}
            pending = lp.get("pending") if isinstance(lp.get("pending"), dict) else None
            already = lp.get("artifactId") == new_artifact_id and lp.get("status") == COMPLETE and result_ok is not LiveResult.ROLLED_BACK
            if already:
                same_marker = all(lp.get(f) == updates[pub_key].get(f) for f in ("artifactId", "outputFingerprint", "status"))
                if same_marker and not AP.readback(self.rtdb, {k: v for k, v in updates.items() if k != pub_key}):
                    rec_ = self._recover(brain, rec_full, pointers, gens, lp.get("publishId"), now)
                    rec_.updates = updates
                    return rec_                                                                                  # an earlier attempt applied it: finalise, do not re-apply
            elif pending and pending.get("artifactId") != new_artifact_id:
                return self._fail(LiveResult.PRECONDITION_FAILED, rec_full, f"an interrupted publication of {pending.get('artifactId')} is pending; resume or roll it back first", now)
            elif not pending and lp.get("artifactId") != expected_prev:
                return self._fail(LiveResult.PRECONDITION_FAILED, rec_full, f"live publication is {lp.get('artifactId')!r}, the baseline expects {expected_prev!r}", now)
            marker = {"artifactId": new_artifact_id, "publishId": publish_id, "startedAt": now}
            calls, kind = 0, mode
            try:
                kind, calls = AP.apply_plan(self.rtdb, updates, pub_key, max_update_bytes=self.max_update_bytes, pending_marker=marker)
            except (RtdbDefiniteFailure, RtdbAmbiguousFailure) as e:
                bad = AP.readback(self.rtdb, updates)
                if bad:
                    now_pub = self.rtdb.get(pub_key)
                    if isinstance(now_pub, dict) and now_pub.get("artifactId") == new_artifact_id and now_pub.get("status") == COMPLETE:
                        return self._mismatch(brain, rec_full, bad, now, "apply raised and the authoritative marker is new but data differs")
                    return self._fail(LiveResult.APPLY_FAILED, rec_full, f"{type(e).__name__}: {e}; previous release remains authoritative", now)
            bad = AP.readback(self.rtdb, updates)
            if bad:
                return self._mismatch(brain, rec_full, bad, now, "authoritative readback differs from the plan")
            fin = self._finalise(brain, rec_full, pointers, gens, now, result_ok, calls, kind)
            fin.updates = updates
            return fin
        finally:
            LK.release(store, brain, publish_id, now)

    def _recover(self, brain, rec_full, pointers, gens, orig_publish_id, now) -> LivePublishResult:
        """A previous attempt applied and verified this exact publication but died before the baseline moved. Finish under THAT attempt's publishId: no second write."""
        rec = self.history.get_record(brain, orig_publish_id)
        if rec is None:
            rec = {**rec_full, "publishId": orig_publish_id, "result": LiveResult.PUBLISHED.value, "status": COMPLETE, "recovered": True}
            self.history.append_record(rec)
        ptrs = {k: {**v, "publishId": orig_publish_id} for k, v in pointers.items()}
        try:
            for (schema, scope), ptr in ptrs.items():
                self.history.advance_head(brain, schema, scope, ptr, gens[(schema, scope)])
        except PreconditionFailed as e:
            LK.quarantine(self.history.store, brain, orig_publish_id, f"HEAD_ADVANCE_FAILED during recovery: {e}", now)
            return LivePublishResult(LiveResult.QUARANTINED, rec, detail="recovery could not move the baseline head")
        signal = {"brainId": brain, "artifactId": rec["artifactId"], "publishId": orig_publish_id, "reason": "PUBLICATION_COMPLETE"}
        if self._on_published:
            try:
                self._on_published(signal)
            except Exception:
                pass
        return LivePublishResult(LiveResult.RECOVERED, rec, score_signal=signal, calls=0, mode="RECOVERED")

    def _finalise(self, brain, rec_full, pointers, gens, now, result, calls, kind) -> LivePublishResult:
        rec = {**rec_full, "result": result.value if result is not LiveResult.RECOVERED else LiveResult.PUBLISHED.value, "status": COMPLETE, "applyMode": kind}
        if result is LiveResult.RECOVERED:
            rec["recovered"] = True
        try:
            self.history.append_record(rec)
            for (schema, scope), ptr in pointers.items():
                self.history.advance_head(brain, schema, scope, ptr, gens[(schema, scope)])
        except PreconditionFailed as e:
            LK.quarantine(self.history.store, brain, rec["publishId"], f"HEAD_ADVANCE_FAILED after a verified live apply: {e}", now)
            return LivePublishResult(LiveResult.QUARANTINED, rec, detail="live apply verified but the baseline head moved concurrently")
        signal = {"brainId": brain, "artifactId": rec["artifactId"], "publishId": rec["publishId"], "reason": "PUBLICATION_COMPLETE"}
        if self._on_published:
            try:
                self._on_published(signal)
            except Exception as e:                      # a score-signal failure never undoes a verified publication
                rec["scoreSignalError"] = repr(e)[:200]
        return LivePublishResult(result, rec, score_signal=signal, calls=calls, mode=kind)

    def _fail(self, result, rec_full, detail, now) -> LivePublishResult:
        rec = {**rec_full, "result": result.value, "status": "FAILED", "live": False}
        rec.pop("publishedAt", None)
        self.history.append_record(rec)
        return LivePublishResult(result, rec, detail=detail)

    def _mismatch(self, brain, rec_full, bad, now, why) -> LivePublishResult:
        rec = {**rec_full, "result": LiveResult.READBACK_MISMATCH.value, "status": "FAILED", "mismatchedKeys": bad[:50]}
        self.history.append_record(rec)
        LK.quarantine(self.history.store, brain, rec["publishId"], why, now)
        return LivePublishResult(LiveResult.READBACK_MISMATCH, rec, detail=why, mismatched=bad)

    # ------------------------------------------------------------------------------------------------------------------------------------
    def rollback(self, brain_id: str, publish_id: str, *, approval_ref: str, reason: str) -> LivePublishResult:
        """Explicit, reviewed rollback of the CURRENT live publication to the publication before it.
        Recovery operation: re-apply the previous immutable artifact (validated by the same validators; only the ordering rule is waived), PLUS typed deletes for
        every path the rolled-back publication wrote and the previous one did not. Verified by readback; clears a quarantine only when verified."""
        now = _iso(self._clock())
        if not (isinstance(approval_ref, str) and approval_ref.strip() and isinstance(reason, str) and reason.strip()):
            raise ValueError("rollback requires an approval reference and a reason")
        try:
            self.auth.check(brain_id)
        except NotAuthorized as e:
            return LivePublishResult(LiveResult.NOT_AUTHORIZED, detail=str(e))
        cur = self.history.get_record(brain_id, publish_id)
        verified_live = bool(cur) and cur.get("status") == COMPLETE and cur.get("live")
        quarantine_source = bool(cur) and LK.quarantined(self.history.store, brain_id) and cur.get("result") == LiveResult.READBACK_MISMATCH.value
        if not (verified_live or quarantine_source):
            raise NoRollbackTarget(f"{publish_id} is not a COMPLETE live publication of {brain_id} (nor the readback-mismatch that quarantined it)")
        target = self.history.rollback_reference(brain_id, publish_id)
        if target is None or not target["artifactStored"]:
            raise NoRollbackTarget(f"no restorable previous publication before {publish_id}")
        prior = self.history.get_record(brain_id, target["restorePublishId"])
        data = self.history.read_artifact_bytes(brain_id, target["artifactId"])
        art = self.history.get_artifact(brain_id, target["artifactId"])
        ref = ArtifactRef(brain_id, target["artifactId"], artifact_location(brain_id, target["artifactId"]), sha256_ref(data), art["lineage"]["executionId"],
                          art["lineage"]["artifactSchema"])
        res = self._rb_shadow.evaluate_reference(ref)
        if res.is_rejection or res.result is Result.SKIP:
            raise NoRollbackTarget(f"previous artifact is not restorable: {res.result.value} {res.codes}")
        plan, rec = res.plan, res.record
        pub_key = plan.publication_key
        orphans = sorted(k for k in (cur.get("pathSha256") or {}) if k not in plan.updates and k != pub_key)
        rollback_rec = {**rec, "result": LiveResult.ROLLED_BACK.value, "status": COMPLETE, "mode": LIVE_MODE, "live": True, "publishedAt": now, "sections": _live_sections(rec["sections"]),
                        "rollback": {"fromPublishId": publish_id, "restoredPublishId": prior["publishId"], "approvalRef": approval_ref, "reason": reason[:200]}}
        updates = dict(plan.updates)
        updates.update({k: None for k in orphans})
        updates[pub_key] = rtdb_record(rollback_rec)
        check_update(updates)
        assert_publisher_keys(brain_id, updates)
        changed = [s for s in rec["sections"] if s["result"] == "SHADOW"]
        gens = {(s["artifactSchema"], s["scope"]): self.history.head_generation(brain_id, s["artifactSchema"], s["scope"]) for s in changed}
        pointers = {(s["artifactSchema"], s["scope"]): {"publishId": rec["publishId"], "artifactId": rec["artifactId"], "outputFingerprint": s["outputFingerprint"],
                                                        "fingerprintAlgorithm": rec["fingerprintAlgorithm"], "generatedAt": rec["generatedAt"], "evaluatedAt": rec["evaluatedAt"],
                                                        "live": True, "rollbackOf": publish_id} for s in changed}
        full = {**rollback_rec, "pathSha256": rec.get("pathSha256"), "rollbackDeletes": orphans}
        out = self._commit(brain=brain_id, updates=updates, pub_key=pub_key, rec_full=full, pointers=pointers, gens=gens, expected_prev=cur["artifactId"],
                           new_artifact_id=rec["artifactId"], now=now, result_ok=LiveResult.ROLLED_BACK,
                           mode="SINGLE" if len(AP.canonical_bytes(updates)) <= self.max_update_bytes else "CHUNKED")
        if out.result is LiveResult.ROLLED_BACK and LK.quarantined(self.history.store, brain_id):
            LK.clear_quarantine(self.history.store, brain_id, out.publish_id, now)
        return out
