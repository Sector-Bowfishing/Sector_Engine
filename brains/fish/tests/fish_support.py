"""Shared support for the Fish certification tests: repository roots, the synthetic bundle, a pinned build context, a local SHADOW Publisher rig.
Everything is SYNTHETIC (this repository is public) and offline."""
import datetime as dt
import itertools
import json
import os
import tempfile
import uuid

import biological_brain as bb      # noqa: F401  (runtime import roots come from pytest.ini)
import brain_platform as bp        # noqa: F401  (resolves the shared platform package)
import orchestration as orch
import publish_artifact as pa
import run
import test_biological_brain as T

HERE = os.path.dirname(os.path.abspath(__file__))
FISH = os.path.dirname(HERE)                                       # brains/fish
REPO = os.path.dirname(os.path.dirname(FISH))
RUNTIME = os.path.join(FISH, "runtime")
NOW = dt.datetime(2026, 10, 12, 18, 0, tzinfo=dt.timezone.utc)
EVENT_ID = "1760292000000-biological-state-0"


def uid(n):
    return str(uuid.UUID(int=n, version=4))


def make_bundle(profiles=None, research_version="0000-00-00.1"):
    d = tempfile.mkdtemp()
    T.write_bundle(d, profiles or [T.synthetic_profile(), T.not_assessed()], research_version=research_version)
    return bb.load_bundle(run.local_reader(d))


def updates_for(b, *, now=NOW, published=None, existing=None, event_id=EVENT_ID, deployment="test@1", duration_ms=5):
    return bb.build_updates(b, now=now, uri_root="local:bundle", deployment=deployment, descriptor=orch.DESCRIPTOR, duration_ms=duration_ms,
                            published=published, existing_species=existing, event_id=event_id)


def ctx(n=1, generated_at="2026-10-12T18:00:00Z", code_version="test@1"):
    return pa.BuildContext(uid(n), generated_at, code_version)


def build(b=None, *, n=1, now=NOW, generated_at="2026-10-12T18:00:00Z", published=None, existing=None, consumed=None, deployment="test@1", event_id=EVENT_ID):
    b = b or make_bundle()
    return pa.build_artifact(updates_for(b, now=now, published=published, existing=existing, deployment=deployment, event_id=event_id), b,
                             ctx(n, generated_at, deployment), published=published, consumed=consumed)


def rig():
    """A local, in-memory SHADOW stack (shared: brain_cert_kit.env.local_rig). publish(artifact, brain=None) -> PublishResult through the real handoff."""
    from brain_cert_kit.env import local_rig
    return local_rig(bb.BRAIN_ID)


def sealed(mutations, schema="fish-registry-v1", **kw):
    """A correctly sealed single-section bundle with arbitrary mutations (for rejection tests)."""
    from sector_brain_platform.publisher import default_registry, seal_bundle
    b = make_bundle()
    return seal_bundle(brain_id=kw.pop("brain_id", bb.BRAIN_ID), bundle_id="fish-publication-v1", sections=[{"artifactSchema": schema, "mutations": mutations}],
                       lifecycle="PROFILED", review_status="UNREVIEWED", validation_status="NOT_VALIDATED", generated_at="2026-10-12T18:00:00Z", execution_id=uid(9),
                       code_version="test@1", input_fingerprint=pa.input_fingerprint(b), knowledge_release=b.research_version,
                       manifest_ref="local:bundle/manifest.json", manifest_sha256="sha256:" + b.pointer["manifestSha256"], registry=default_registry())
