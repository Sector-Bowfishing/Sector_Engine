"""Orchestrator publication coordination (Cortex 3.1 PL-19, FD-15). LOCAL and fail-closed: it arms nothing and writes no production database.

For every Brain run the Orchestrator records what was PRODUCED (Brain, run id, artifact id, version, digest, input lineage), whether publication was REQUESTED, and what the
Publisher said: PUBLISHED, SKIPPED (semantic no-op), REJECTED (with the failed check) or FAILED (with the reason and whether a retry is allowed). The Orchestrator never writes Brain
intelligence itself; it hands a validated artifact reference to the existing Publisher (the live Publisher package) and records the answer.

Rules this module enforces and the tests prove:
  * SHADOW is not PUBLISHED. A shadow evaluation is recorded in its own `shadow` block; it can never set `publication.outcome`. Only a LiveResult from the live Publisher can.
  * Before a Brain's approved cutover its run record says `writePath: DIRECT_WRITE_PRE_CUTOVER` and `publication.outcome: NOT_REQUESTED`: the Brain's existing direct writer is the writer,
    and produced is never confused with published.
  * An unarmed Publisher (no live publisher, or no LiveAuthorization for that Brain) is never asked. Existing direct writers stay untouched.
  * Idempotent: one record per (Brain, run, artifact). A record that reached PUBLISHED / SKIPPED / REJECTED is never submitted again; a retry after an ambiguous failure goes through the
    Publisher's own idempotent recovery (RECOVERED) and cannot publish twice. FAILED retries use bounded backoff and a maximum number of attempts.
  * A succeeded Cloud Run execution with no artifact is recorded as a MISSING artifact (never as published, never silently ignored); a failed execution is recorded as a failed run.
  * `resume()` makes an interrupted coordinator continue exactly where it stopped (collect -> shadow -> request) from the persisted ledger.
Nothing here is wired to a production path: `orchestrate.py` may call it only behind an explicit flag (default off).
"""
from __future__ import annotations

import datetime as dt
import json
import os

from .publisher.canonical import canonical_bytes, sha256_ref
from .publisher.refs import ArtifactRef, artifact_location
from .publisher.model import Rejected
from . import data_ownership as DO
from .timeutil import iso, parse_time

SCHEMA = "sector-publication-run-record-v1"
OUTCOMES = ("NOT_REQUESTED", "PUBLISHED", "SKIPPED", "REJECTED", "FAILED")
FINAL = ("PUBLISHED", "SKIPPED", "REJECTED")
DIRECT, VIA_PUBLISHER = "DIRECT_WRITE_PRE_CUTOVER", "PUBLISHER"
SHADOW_OK = ("SHADOW_READY", "SKIP")
BACKOFF_MIN = (5, 15, 45)
MAX_ATTEMPTS = 3

# live Publisher vocabulary -> the PL-19 outcome and whether another attempt may help
_LIVE = {
    "PUBLISHED": ("PUBLISHED", False), "RECOVERED": ("PUBLISHED", False), "SKIP": ("SKIPPED", False),
    "REJECTED": ("REJECTED", False), "FAILED_VALIDATION": ("REJECTED", False), "NOT_AUTHORIZED": ("REJECTED", False),
    "APPLY_FAILED": ("FAILED", True), "PRECONDITION_FAILED": ("FAILED", True), "LOCK_BUSY": ("FAILED", True),
    "BASELINE_UNRECONCILED": ("FAILED", False), "READBACK_MISMATCH": ("FAILED", False), "QUARANTINED": ("FAILED", False), "ROLLED_BACK": ("FAILED", False),
}


class PublicationLedger:
    """The Orchestrator's persisted account of runs and publications. In memory by default; a path makes it a single JSON document written atomically."""

    def __init__(self, path: str | None = None):
        self.path = path
        self.doc = {"schema": "sector-publication-ledger-v1", "records": {}}
        if path and os.path.exists(path):
            self.doc = json.load(open(path, encoding="utf-8"))

    @staticmethod
    def key(brain_id: str, run_id: str, artifact_id: str | None) -> str:
        return f"{brain_id}|{run_id}|{artifact_id or 'NO_ARTIFACT'}"

    def get(self, key: str) -> dict | None:
        return self.doc["records"].get(key)

    def put(self, rec: dict) -> dict:
        self.doc["records"][rec["key"]] = rec
        if self.path:
            tmp = self.path + ".tmp"
            json.dump(self.doc, open(tmp, "w", encoding="utf-8"), indent=1, sort_keys=True)
            os.replace(tmp, self.path)
        return rec

    def records(self, brain_id: str | None = None) -> list:
        return [r for _, r in sorted(self.doc["records"].items()) if brain_id in (None, r["brainId"])]

    def for_run(self, brain_id: str, run_id: str) -> list:
        return [r for r in self.records(brain_id) if r["runId"] == run_id]


def _blank(brain_id: str, run_id: str, artifact_id: str | None, now: str) -> dict:
    rec = DO.recognize(brain_id)
    return {"schema": SCHEMA, "key": PublicationLedger.key(brain_id, run_id, artifact_id), "brainId": brain_id, "targetBrains": rec.get("targets") or [brain_id], "runId": run_id,
            "recordedAt": now, "runStatus": "UNKNOWN", "artifact": {"state": "NOT_COLLECTED"}, "inputLineage": None, "writePath": DIRECT,
            "shadow": {"checked": False}, "publication": {"requested": False, "outcome": "NOT_REQUESTED", "reason": "NOT_EVALUATED", "attempts": 0}}


class PublicationCoordinator:
    def __init__(self, ledger: PublicationLedger, store, *, shadow=None, live=None, cutover=(), clock=lambda: dt.datetime.now(dt.timezone.utc), max_attempts: int = MAX_ATTEMPTS,
                 backoff_minutes=BACKOFF_MIN, hold_reason: str | None = None):
        """store: object store holding artifacts/{brainId}/... (read only here). shadow: a ShadowPublisher (SHADOW mode). live: a LivePublisher, or None while the Publisher is unarmed.
        cutover: Brain ids whose approved cutover has happened; for every other Brain the existing direct writer stays the writer and nothing is requested."""
        self.ledger, self.store, self.shadow, self.live = ledger, store, shadow, live
        self.cutover, self._clock, self.max_attempts, self.backoff = set(cutover), clock, max_attempts, tuple(backoff_minutes)
        self.hold_reason = hold_reason                                           # e.g. EXECUTION_PAUSED: artifacts are still collected and recorded, no publication is requested

    def _now(self) -> str:
        return iso(self._clock())

    # ----------------------------------------------------------------------------------------------------------------------------- collect
    def collect(self, ref: ArtifactRef, run_status: str = "SUCCEEDED") -> dict:
        """Record the artifact a run produced. The stored bytes must hash to the reference digest; the artifact must agree with the reference (Brain, artifact id, run id, schema)."""
        key = PublicationLedger.key(ref.brain_id, ref.execution_id, ref.artifact_id)
        have = self.ledger.get(key)
        if have and have["artifact"].get("state") == "COLLECTED":
            return have                                                       # idempotent: a re-report of the same artifact changes nothing
        rec = have or _blank(ref.brain_id, ref.execution_id, ref.artifact_id, self._now())
        rec["runStatus"] = run_status
        try:
            ref.validate()
        except Rejected as e:
            rec["artifact"] = {"state": "INVALID", "artifactId": ref.artifact_id, "problems": [v.code for v in e.violations]}
            return self.ledger.put(rec)
        data = self.store.get(ref.location)
        if data is None:
            rec["artifact"] = {"state": "MISSING", "artifactId": ref.artifact_id, "location": ref.location, "reason": "ARTIFACT_NOT_IN_STORE"}
            rec["publication"].update(reason="ARTIFACT_MISSING")
            return self.ledger.put(rec)
        if sha256_ref(data) != ref.sha256:
            rec["artifact"] = {"state": "INVALID", "artifactId": ref.artifact_id, "location": ref.location, "problems": ["DIGEST_MISMATCH"], "expected": ref.sha256, "actual": sha256_ref(data)}
            rec["publication"].update(reason="ARTIFACT_DIGEST_MISMATCH")
            return self.ledger.put(rec)
        art = json.loads(data)
        if canonical_bytes(art) != data:                                         # a Brain's ArtifactWriter always stores canonical bytes; anything else was not sealed by it
            rec["artifact"] = {"state": "INVALID", "artifactId": ref.artifact_id, "location": ref.location, "problems": ["NOT_CANONICAL"]}
            rec["publication"].update(reason="ARTIFACT_NOT_CANONICAL")
            return self.ledger.put(rec)
        lin = art.get("lineage") or {}
        problems = [n for n, a, b in (("brainId", lin.get("brainId"), ref.brain_id), ("artifactId", lin.get("artifactId"), ref.artifact_id), ("executionId", lin.get("executionId"), ref.execution_id),
                                       ("artifactSchema", lin.get("artifactSchema"), ref.expected_schema)) if a != b]
        if problems:
            rec["artifact"] = {"state": "INVALID", "artifactId": ref.artifact_id, "problems": [f"LINEAGE_{p.upper()}_MISMATCH" for p in problems]}
            rec["publication"].update(reason="ARTIFACT_LINEAGE_MISMATCH")
            return self.ledger.put(rec)
        rec["artifact"] = {"state": "COLLECTED", "artifactId": ref.artifact_id, "schema": lin.get("artifactSchema"), "location": ref.location, "digest": ref.sha256,
                           "outputFingerprint": lin.get("outputFingerprint"), "generatedAt": lin.get("generatedAt"),
                           "version": {"codeVersion": lin.get("codeVersion"), "knowledgeRelease": lin.get("knowledgeRelease"), "manifestSha256": lin.get("manifestSha256"),
                                       "lifecycle": lin.get("lifecycle"), "reviewStatus": lin.get("reviewStatus"), "validationStatus": lin.get("validationStatus")}}
        rec["inputLineage"] = {"inputFingerprint": lin.get("inputFingerprint"), "consumed": art.get("consumed"), "knowledgeRelease": lin.get("knowledgeRelease")}
        rec["writePath"] = VIA_PUBLISHER if ref.brain_id in self.cutover else DIRECT
        rec["publication"]["reason"] = "COLLECTED"
        return self.ledger.put(rec)

    def report_missing(self, brain_id: str, run_id: str, run_status: str, reason: str) -> dict:
        """A run that produced no artifact: recorded as such (never published, never ignored)."""
        key = PublicationLedger.key(brain_id, run_id, None)
        rec = self.ledger.get(key) or _blank(brain_id, run_id, None, self._now())
        rec["runStatus"] = run_status
        rec["artifact"] = {"state": "MISSING" if run_status == "SUCCEEDED" else "NOT_PRODUCED", "reason": reason}
        rec["publication"].update(reason="ARTIFACT_MISSING" if run_status == "SUCCEEDED" else "RUN_" + run_status)
        return self.ledger.put(rec)

    # ----------------------------------------------------------------------------------------------------------------------------- shadow (separate from publication)
    def _ref(self, rec: dict) -> ArtifactRef:
        a = rec["artifact"]
        return ArtifactRef(rec["brainId"], a["artifactId"], a["location"], a["digest"], rec["runId"], a["schema"])

    def evaluate_shadow(self, key: str) -> dict:
        """Run the SHADOW check and record it in `shadow` ONLY. A passing shadow never changes `publication`."""
        rec = self.ledger.get(key)
        if not rec or rec["artifact"].get("state") != "COLLECTED" or self.shadow is None or rec["shadow"].get("checked"):
            return rec
        try:
            r = self.shadow.evaluate_reference(self._ref(rec), trigger="DEPENDENCY")
            rec["shadow"] = {"checked": True, "result": r.result.value, "codes": list(r.codes) if hasattr(r, "codes") else [], "publishId": r.publish_id, "at": self._now(), "live": False}
        except Exception as e:                                                  # noqa: BLE001 - a shadow failure is a recorded fact, never a crash and never a publication
            rec["shadow"] = {"checked": True, "result": "ERROR", "codes": [type(e).__name__], "detail": str(e)[:200], "at": self._now(), "live": False}
        return self.ledger.put(rec)

    # ----------------------------------------------------------------------------------------------------------------------------- publication
    def request_publication(self, key: str) -> dict:
        rec = self.ledger.get(key)
        if not rec:
            raise KeyError(key)
        pub = rec["publication"]
        if pub["outcome"] in FINAL:
            return rec                                                          # already decided: never submitted twice
        if rec["artifact"].get("state") != "COLLECTED":
            return rec
        now = self._clock()

        def hold(reason):
            pub.update(requested=False, outcome="NOT_REQUESTED", reason=reason)
            return self.ledger.put(rec)
        if rec["brainId"] not in self.cutover:
            return hold("DIRECT_WRITER_ACTIVE")                                  # pre-cutover: the Brain's own writer is the writer
        if self.hold_reason:
            return hold(self.hold_reason)
        if self.live is None:
            return hold("PUBLISHER_UNARMED")
        if rec["shadow"].get("checked") and rec["shadow"].get("result") not in SHADOW_OK:
            return hold("SHADOW_" + str(rec["shadow"].get("result")))            # the shadow already said no: the Publisher is not asked
        if pub["outcome"] == "FAILED":
            if not pub.get("retryable") or pub["attempts"] >= self.max_attempts:
                pub.update(retryable=False, reason=pub.get("reason", "") if pub.get("reason") == "RETRIES_EXHAUSTED" else pub.get("reason"))
                return self.ledger.put(rec)
            after = parse_time(pub.get("nextAttemptAfter"))
            if after and now < after:
                return rec                                                       # backoff not elapsed: nothing happens
        data = self.store.get(rec["artifact"]["location"])                      # the digest pinned at collection must still be the stored artifact: tampering after collection is never published
        if data is None or sha256_ref(data) != rec["artifact"]["digest"]:
            rec["artifact"].update(state="INVALID", problems=["DIGEST_CHANGED_AFTER_COLLECTION"] if data is not None else ["ARTIFACT_REMOVED_AFTER_COLLECTION"])
            pub.update(requested=False, outcome="REJECTED", reason="ARTIFACT_CHANGED_AFTER_COLLECTION", retryable=False)
            return self.ledger.put(rec)
        pub["attempts"] += 1
        pub.update(requested=True, lastAttemptAt=iso(now))
        try:
            res = self.live.publish(self._ref(rec))
        except Exception as e:                                                  # noqa: BLE001 - an exception means the outcome is UNKNOWN, never published
            return self._failed(rec, now, "PUBLISHER_ERROR:" + type(e).__name__, retryable=True, detail=str(e)[:200])
        name = res.result.value
        outcome, retry = _LIVE.get(name, ("FAILED", False))
        if outcome in FINAL:
            pub.update(outcome=outcome, reason=name, codes=list(res.codes or []), livePublishId=res.publish_id, retryable=False, nextAttemptAfter=None,
                       recovered=(name == "RECOVERED"), readback=(None if outcome == "SKIPPED" else {"verified": outcome == "PUBLISHED", "mismatched": list(res.mismatched or [])}),
                       detail=(res.detail or "")[:200])
            return self.ledger.put(rec)
        return self._failed(rec, now, name, retryable=retry, codes=list(res.codes or []), mismatched=list(res.mismatched or []), detail=(res.detail or "")[:200], publish_id=res.publish_id)

    def _failed(self, rec: dict, now: dt.datetime, reason: str, *, retryable: bool, codes=None, mismatched=None, detail: str = "", publish_id=None) -> dict:
        pub = rec["publication"]
        exhausted = pub["attempts"] >= self.max_attempts
        step = self.backoff[min(pub["attempts"] - 1, len(self.backoff) - 1)]
        pub.update(outcome="FAILED", reason="RETRIES_EXHAUSTED" if (retryable and exhausted) else reason, lastReason=reason, codes=codes or [], detail=detail, livePublishId=publish_id,
                   retryable=bool(retryable and not exhausted), nextAttemptAfter=(iso(now + dt.timedelta(minutes=step)) if retryable and not exhausted else None),
                   readback={"verified": False, "mismatched": mismatched or []} if mismatched else None)
        return self.ledger.put(rec)

    def process(self, ref: ArtifactRef, run_status: str = "SUCCEEDED") -> dict:
        """collect -> shadow -> request, each step idempotent."""
        rec = self.collect(ref, run_status)
        if rec["artifact"].get("state") != "COLLECTED":
            return rec
        rec = self.evaluate_shadow(rec["key"]) or rec
        return self.request_publication(rec["key"])

    # ----------------------------------------------------------------------------------------------------------------------------- reconcile with Cloud Run
    def reconcile(self, executions: list, window_minutes: int = 10) -> dict:
        """Reconcile Cloud Run execution results (orchestration.execution_record dicts) with the artifacts in storage. A SUCCEEDED execution is matched to an artifact first by
        lineage.executionId, otherwise (labelled `matchBasis: TIME_WINDOW`) by the Brain's artifact generated inside the execution window. No match = MISSING artifact."""
        out = {"collected": [], "missing": [], "failedRuns": [], "alreadyKnown": 0}
        index: dict = {}

        def artifacts(brain):
            if brain not in index:
                found = []
                for k in self.store.list(f"artifacts/{brain}/"):
                    if k.endswith("/artifact.json"):
                        data = self.store.get(k)
                        try:
                            lin = (json.loads(data).get("lineage") or {})
                        except (ValueError, TypeError):
                            continue
                        found.append((k, data, lin))
                index[brain] = found
            return index[brain]
        for ex in executions or []:
            brain, run_id, status = ex.get("brainId"), ex.get("executionId"), ex.get("status")
            if not brain or not run_id or status == "RUNNING":
                continue
            if any(r["artifact"].get("state") in ("COLLECTED", "INVALID") for r in self.ledger.for_run(brain, run_id)):
                out["alreadyKnown"] += 1
                continue
            if status != "SUCCEEDED":
                self.report_missing(brain, run_id, "FAILED", "execution did not succeed")
                out["failedRuns"].append({"brainId": brain, "runId": run_id})
                continue
            hit, basis = None, None
            for k, data, lin in artifacts(brain):
                if lin.get("executionId") == run_id:
                    hit, basis = (k, data, lin), "EXECUTION_ID"
                    break
            if hit is None:
                s, e = parse_time(ex.get("startedAt")), parse_time(ex.get("endedAt"))
                for k, data, lin in artifacts(brain):
                    g = parse_time(lin.get("generatedAt"))
                    if s and e and g and s - dt.timedelta(minutes=window_minutes) <= g <= e + dt.timedelta(minutes=window_minutes) and not self._known_artifact(brain, lin.get("artifactId")):
                        hit, basis = (k, data, lin), "TIME_WINDOW"
                        break
            if hit is None:
                self.report_missing(brain, run_id, "SUCCEEDED", "no artifact in the store for this execution")
                out["missing"].append({"brainId": brain, "runId": run_id})
                continue
            k, data, lin = hit
            ref = ArtifactRef(brain, lin["artifactId"], k, sha256_ref(data), lin.get("executionId") or run_id, lin["artifactSchema"])
            rec = self.collect(ref)
            if basis == "TIME_WINDOW":
                rec["matchBasis"] = basis
                self.ledger.put(rec)
            out["collected"].append(rec["key"])
        return out

    def output_change(self, rec: dict) -> str:
        """YES / NO / UNKNOWN: did this run's artifact carry a different outputFingerprint than the Brain's previous collected artifact? Scoring triggers are NOT changed by this; it only
        replaces the execution record's UNKNOWN with evidence."""
        fp = rec["artifact"].get("outputFingerprint")
        if rec["artifact"].get("state") != "COLLECTED" or not fp:
            return "UNKNOWN"
        prev = [r for r in self.ledger.records(rec["brainId"]) if r["key"] != rec["key"] and r["artifact"].get("state") == "COLLECTED"
                and r["artifact"].get("generatedAt", "") < (rec["artifact"].get("generatedAt") or "~")]
        if not prev:
            return "UNKNOWN"
        last = max(prev, key=lambda r: r["artifact"].get("generatedAt") or "")
        return "NO" if last["artifact"].get("outputFingerprint") == fp else "YES"

    def _known_artifact(self, brain: str, artifact_id: str | None) -> bool:
        return any(r["artifact"].get("artifactId") == artifact_id for r in self.ledger.records(brain))

    # ----------------------------------------------------------------------------------------------------------------------------- recovery and reporting
    def resume(self) -> dict:
        """After an interruption: continue every unfinished record from the persisted ledger. Finished records are untouched (no duplicate publication)."""
        done = {"shadowed": 0, "requested": 0, "retried": 0}
        for rec in list(self.ledger.records()):
            if rec["artifact"].get("state") != "COLLECTED":
                continue
            if not rec["shadow"].get("checked") and self.shadow is not None:
                self.evaluate_shadow(rec["key"])
                done["shadowed"] += 1
            before = rec["publication"]["attempts"]
            cur = self.ledger.get(rec["key"])
            if cur["publication"]["outcome"] not in FINAL:
                after = self.request_publication(rec["key"])
                if after["publication"]["attempts"] > before:
                    done["retried" if before else "requested"] += 1
        return done

    def summary(self) -> dict:
        """Operational summary for the control plane (PROPOSED family; see docs/cortex/CORTEX_GAPS.md): per Brain, the last run, what was produced, published and failed."""
        by = {}
        for r in self.ledger.records():
            b = by.setdefault(r["brainId"], {"runs": 0, "produced": 0, "published": 0, "skipped": 0, "rejected": 0, "failed": 0, "notRequested": 0, "missingArtifacts": 0, "problems": [],
                                              "directWriter": r["writePath"] == DIRECT})
            b["runs"] += 1
            b["produced"] += r["artifact"].get("state") == "COLLECTED"
            b["missingArtifacts"] += r["artifact"].get("state") == "MISSING"
            o = r["publication"]["outcome"]
            b[{"PUBLISHED": "published", "SKIPPED": "skipped", "REJECTED": "rejected", "FAILED": "failed", "NOT_REQUESTED": "notRequested"}[o]] += 1
            if o == "FAILED" or r["artifact"].get("state") in ("MISSING", "INVALID"):
                b["problems"].append({"runId": r["runId"], "artifactId": r["artifact"].get("artifactId"), "reason": r["publication"].get("reason")})
        return {"schema": "sector-publication-summary-v1", "generatedAt": self._now(), "brains": by, "note": "PUBLISHED counts only outcomes returned by the live Publisher; shadow checks are never counted"}
