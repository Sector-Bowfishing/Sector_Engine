"""The artifact handoff, end to end and local (target: Brain -> private artifact storage -> authenticated API signal -> Orchestrator loads the
identified artifact -> Publisher validates -> SHADOW).

  ArtifactWriter    Brain side. Create-only, own prefix only, returns the ArtifactRef the API signal carries. Cannot write publishes/ or another Brain.
  ShadowDispatcher  Orchestrator side. Turns an accepted SUBMIT_ARTIFACT request into ShadowPublisher.evaluate_reference().
  seal_artifact     builds a well-formed envelope with the output fingerprint computed the way the Publisher will recompute it.
  local_shadow_stack  everything wired together on a local directory / memory for a Brain's shadow integration tests.

Nothing here creates a bucket, a service or a credential. The production RTDB is never an artifact queue and never a request inbox.
"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass

from .api import ApiRequest
from .canonical import canonical_bytes, output_fingerprint, sha256_ref
from .model import DEFAULT_SCOPE, ENVELOPE_ID, LINEAGE_ID, PublisherMode
from .publisher import ShadowPublisher
from .refs import ArtifactRef, artifact_location
from .registry import Registry, default_registry
from .sinks import ShadowSink
from .storage import AccessDenied, ArtifactConflict, LocalDirObjectStore, MemoryObjectStore, PreconditionFailed, PublishHistory, brain_view, publisher_view


def seal_artifact(*, brain_id: str, artifact_schema: str, mutations: list, lifecycle: str, review_status: str, validation_status: str, generated_at: str,
                  execution_id: str, code_version: str, input_fingerprint: str, knowledge_release: str = "NONE", manifest_ref: str = "NONE",
                  manifest_sha256: str = "NONE", freshness: dict | None = None, scope: str | None = None, approval_ref: str | None = None,
                  artifact_id: str | None = None, registry: Registry | None = None) -> dict:
    """Envelope with a correct `outputFingerprint`. `registry` supplies the schema's volatile_extra; without it only the shared defaults apply."""
    spec = (registry or default_registry()).spec(artifact_schema)
    extra = spec.volatile_extra if spec else ()
    lin = {"schema": LINEAGE_ID, "brainId": brain_id, "artifactSchema": artifact_schema, "knowledgeRelease": knowledge_release, "manifestRef": manifest_ref,
           "manifestSha256": manifest_sha256, "codeVersion": code_version, "executionId": execution_id, "inputFingerprint": input_fingerprint,
           "outputFingerprint": output_fingerprint(brain_id, artifact_schema, mutations, extra), "generatedAt": generated_at, "lifecycle": lifecycle,
           "reviewStatus": review_status, "validationStatus": validation_status}
    if artifact_id:
        lin["artifactId"] = artifact_id
    art = {"envelope": ENVELOPE_ID, "lineage": lin, "mutations": copy.deepcopy(mutations)}
    for k, v in (("freshness", freshness), ("scope", scope), ("approvalRef", approval_ref)):
        if v is not None:
            art[k] = copy.deepcopy(v)
    return art


class ArtifactWriter:
    """What a specialist Brain is allowed to do with storage: create its own artifacts, once. Built on a brain_view(), so any attempt outside
    artifacts/{brainId}/ (another Brain, publishes/, an overwrite) raises AccessDenied / PreconditionFailed."""

    def __init__(self, store, brain_id: str):
        self.brain_id = brain_id
        self._store = brain_view(store, brain_id)

    def write(self, artifact: dict, *, request_id: str | None = None) -> ArtifactRef:
        art = copy.deepcopy(artifact)
        lin = art.get("lineage") or {}
        if lin.get("brainId") != self.brain_id:
            raise AccessDenied(f"{self.brain_id!r} may write only its own artifacts (lineage.brainId is {lin.get('brainId')!r})")
        aid = lin.setdefault("artifactId", str(uuid.uuid4()))
        data = canonical_bytes(art)
        key = artifact_location(self.brain_id, aid)
        try:
            self._store.put(key, data, if_generation_match=0)
        except PreconditionFailed:
            if self._store.get(key) != data:
                raise ArtifactConflict(f"artifact {aid} already exists with different content") from None
        return ArtifactRef(self.brain_id, aid, key, sha256_ref(data), lin["executionId"], lin["artifactSchema"], request_id)


class ShadowDispatcher:
    """Implements api.Dispatcher. Only SUBMIT_ARTIFACT does anything (SHADOW evaluation); the other workflows are not wired in the shadow task and
    say so rather than pretending."""

    def __init__(self, publisher: ShadowPublisher):
        self.publisher = publisher

    def artifact(self, request: ApiRequest) -> dict:
        p = request.params
        ref = ArtifactRef(request.brain_id, p["artifactId"], p["artifactRef"], p["artifactSha256"], p["executionId"], p["expectedSchema"], request.request_id)
        r = self.publisher.evaluate_reference(ref, trigger="MANUAL_REQUEST")
        return {"result": r.result.value, "publishId": r.publish_id, "codes": r.codes, "live": False, "mode": r.mode.value}

    def _unwired(self, request: ApiRequest) -> dict:
        return {"accepted": False, "reason": "workflow not wired in Publisher V1 shadow"}

    control = review = research = _unwired


@dataclass
class ShadowStack:
    store: MemoryObjectStore
    registry: Registry
    history: PublishHistory
    sink: ShadowSink
    publisher: ShadowPublisher
    dispatcher: ShadowDispatcher

    def writer(self, brain_id: str) -> ArtifactWriter:
        return ArtifactWriter(self.store, brain_id)


def local_shadow_stack(root=None, *, registry: Registry | None = None, mode: PublisherMode = PublisherMode.SHADOW, **publisher_kw) -> ShadowStack:
    """A complete local SHADOW pipeline for a Brain's integration tests. `root=None` keeps everything in memory, a path persists it in a directory.
    The Publisher is given the least-privilege publisher_view(): it can read artifacts and create history, and cannot write artifacts/."""
    store = LocalDirObjectStore(root) if root is not None else MemoryObjectStore()
    reg = registry or default_registry()
    hist = PublishHistory(publisher_view(store))
    sink = ShadowSink()
    pub = ShadowPublisher(reg, hist, sink, mode=mode, **publisher_kw)
    return ShadowStack(store, reg, hist, sink, pub, ShadowDispatcher(pub))
