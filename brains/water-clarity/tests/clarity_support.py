"""Shared support for the Water Clarity certification tests: repository roots, the synthetic multi-lake update (captured from a REAL `run.main` execution with
every network edge faked, CENTRAL mode), a pinned build context and a local SHADOW Publisher rig. Everything is SYNTHETIC (this repository is public) and offline."""
import datetime as dt
import itertools
import json
import os
import sys
import uuid
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
CLARITY = os.path.dirname(HERE)                                    # brains/water-clarity
REPO = os.path.dirname(os.path.dirname(CLARITY))
RUNTIME = os.path.join(CLARITY, "runtime")
FIXTURES = os.path.join(HERE, "fixtures")
# Tests never read the real private overlay: a synthetic one with the same mechanics (set before clarity_brain is first imported).
os.environ["CLARITY_PRIVATE_CATALOG"] = os.path.join(FIXTURES, "catalog.overlay.example.json")

import brain_platform as bp        # noqa: E402,F401  (resolves the shared platform package)
import clarity_brain as cb         # noqa: E402
import publish_artifact as pa      # noqa: E402
import run                         # noqa: E402

NOW = dt.datetime(2026, 10, 12, 6, 30, tzinfo=dt.timezone.utc)
GENERATED_AT = "2026-10-12T06:30:00Z"


def fx(name):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return json.load(fh)


GUNT, KY, ALEK = fx("engine_guntersville_rain_decay.json"), fx("engine_kentucky_discharge_gauge.json"), fx("engine_aleknagik_openmeteo.json")
LATEST, META = fx("bucket_guntersville_latest.json"), fx("bucket_guntersville_meta.json")
DIRECTORY = [{"id": "Guntersville|AL", "lat": 34.42, "lon": -86.25}, {"id": "Kentucky Lake|KY", "lat": 36.6, "lon": -88.07},
             {"id": "Aleknagik|AK", "lat": 59.3, "lon": -158.6}]


def uid(n):
    return str(uuid.UUID(int=n, version=4))


class FakeTransport:
    """Captures every REST call the platform client makes (PATCH bodies are the real multi-path updates)."""
    def __init__(self, reads=None):
        self.calls, self.reads = [], reads or {}

    def __call__(self, method, url, body):
        self.calls.append((method, url, json.loads(body) if body else None))
        if method == "GET":
            for key, val in self.reads.items():
                if f"/{key}.json" in url:
                    return 200, json.dumps(val)
        return 200, "null"


def real_run_updates(engine=None, reads=None, argv=("--artifact-bucket", "test-artifacts", "--batch", "2")):
    """Execute the REAL run.main in CENTRAL mode with every network edge faked; return (flat updates, transport, exit code).

    `flat` is the update dictionary the run handed to the artifact builder (the payload it seals), captured at `publish_artifact.build_artifact`: the run has no
    database write site any more (X14), so the write set is what the Publisher is asked to publish, not what a direct writer sent. `transport` records every
    REST call the platform client made (reads only; a test asserts no write verb). The artifact itself goes to an in-memory object store."""
    from sector_brain_platform.publisher import MemoryObjectStore
    import sector_brain_platform.object_bucket as ob
    os.environ["BRAIN_ACCESS_TOKEN"] = "test-token"
    t = FakeTransport(reads)
    engine = engine or (lambda lake: {"Guntersville|AL": GUNT, "Kentucky Lake|KY": KY, "Aleknagik|AK": ALEK}[lake["id"]])
    real_init = bp.BrainRtdb.__init__
    real_build = pa.build_artifact
    captured = {}
    store = MemoryObjectStore()

    def init(self_, url=bp.BRAIN_RTDB_URL, tokens=None, **kw):
        kw.pop("transport", None)
        real_init(self_, url, tokens, transport=t, backoff_s=0, **kw)

    def build_capture(updates, *a, **kw):
        captured.update(updates)
        return real_build(updates, *a, **kw)
    with mock.patch.object(run, "load_directory", return_value=list(DIRECTORY)), \
         mock.patch.object(run, "polygon_ids", return_value={"Guntersville|AL", "Kentucky Lake|KY"}), \
         mock.patch.object(run, "bucket_lake", side_effect=lambda lid: {"latest": LATEST, "meta": META, "passCount": 16} if lid == "Guntersville|AL" else {"latest": None, "meta": None, "passCount": None}), \
         mock.patch.object(run, "engine_conditions", side_effect=engine), \
         mock.patch.object(run, "engine_revision", return_value="sector-engine-test"), \
         mock.patch.object(run, "lake_surface_run", return_value=None), \
         mock.patch.object(bp.BrainRtdb, "__init__", init), \
         mock.patch.object(pa, "build_artifact", build_capture), \
         mock.patch.object(ob, "GcsRestObjectStore", lambda bucket, tokens: store), \
         mock.patch.object(sys, "argv", ["run.py", *argv]):
        rc = run.main()
    t.store = store
    return {k.lstrip("/"): v for k, v in captured.items()}, t, rc            # the RTDB key form (no leading slash), as a PATCH body carries it


def ctx(n=1, generated_at=GENERATED_AT, code_version="test@1", catalog_sha256="sha256:" + "ab" * 32):
    return pa.BuildContext(generated_at, uid(n), code_version, catalog_sha256, **pa.release_lineage())


def build(updates, *, n=1, generated_at=GENERATED_AT, consumed=None, **kw):
    return pa.build_artifact(updates, ctx(n, generated_at, **kw), consumed=consumed)


def rig():
    """A local, in-memory SHADOW stack (shared: brain_cert_kit.env.local_rig). publish(artifact, brain=None) -> PublishResult through the real handoff."""
    from brain_cert_kit.env import local_rig
    return local_rig(cb.BRAIN_ID)


def sealed(mutations, schema="clarity-registry-v1", freshness=None, **kw):
    """A correctly sealed single-section bundle with arbitrary mutations (for rejection tests)."""
    from sector_brain_platform.publisher import default_registry, seal_bundle
    sec = {"artifactSchema": schema, "mutations": mutations}
    if freshness:
        sec["freshness"] = freshness
    return seal_bundle(brain_id=kw.pop("brain_id", cb.BRAIN_ID), bundle_id="clarity-publication-v1", sections=[sec], lifecycle=kw.pop("lifecycle", "CALIBRATION"),
                       review_status="UNREVIEWED", validation_status="NOT_VALIDATED", generated_at=GENERATED_AT, execution_id=uid(9), code_version="test@1",
                       input_fingerprint="sha256:" + "cd" * 32, knowledge_release="NONE", manifest_ref="NONE", manifest_sha256="NONE", registry=default_registry())
