"""SI-1 (a) draft: Intelligence seals ONE artifact create-only instead of writing the database, and a runner outside Cloud Run supplies the
Engine serving revision (Sector_Ops #50/#51)."""
import json

import pytest

import intelligence_support as S
import run
import sector_intelligence_brain as sib
import test_sector_intelligence_brain as T
from sector_brain_platform.publisher.storage import LocalDirObjectStore


def test_the_update_set_is_sealed_into_one_create_only_artifact(tmp_path):
    store = LocalDirObjectStore(tmp_path)
    ref = run.seal_and_store(S.run_updates(), now=S.NOW, release=S.release(), consumed=None, store=store, execution_id=S.uid(7))
    keys = store.list(f"artifacts/{sib.BRAIN_ID}/")
    assert keys == [ref["location"]] and ref["executionId"] == S.uid(7)
    art = json.loads(store.get(ref["location"]))
    assert art["lineage"]["artifactSchema"] == "sector-intelligence-publication-v1"
    with pytest.raises(Exception):                                   # create-only: the same artifact is never overwritten
        store.put(ref["location"], b"{}", if_generation_match=0)


def test_artifact_mode_refuses_without_a_destination(capsys):
    assert run.main(["--artifact"]) == 2
    assert "needs --artifact-dir or --artifact-bucket" in capsys.readouterr().err


def test_runner_supplied_revision_is_serving_but_unverified_without_a_digest():
    svc = run.runner_service({"ENGINE_REVISION": "sector-engine-00080-wes"})
    s = sib.engine_serving(svc, T.LINEAGE, S.NOW)
    assert s["status"] == "SERVING" and s["revision"] == "sector-engine-00080-wes" and s["lineageVerified"] is False


def test_runner_supplied_digest_verifies_the_declared_lineage():
    svc = run.runner_service({"ENGINE_REVISION": "r1", "ENGINE_IMAGE_DIGEST": T.LINEAGE["imageDigest"]})
    assert sib.engine_serving(svc, T.LINEAGE, S.NOW)["lineageVerified"] is True


def test_no_revision_means_cloud_run_is_read_as_before():
    assert run.runner_service({}) is None


def test_recorded_consumption_goes_into_the_artifact_lineage(tmp_path):
    import brain_platform as bp
    rec = bp.ConsumptionRecorder(sib.BRAIN_ID)
    rec.observe("brains/water-clarity", {"version": "1.1.0"})
    store = LocalDirObjectStore(tmp_path)
    ref = run.seal_and_store(S.run_updates(), now=S.NOW, release=S.release(), consumed=rec.entries(), store=store)
    art = json.loads(store.get(ref["location"]))
    assert [c["dependencyId"] for c in art["consumed"]] == ["brain:water-clarity"]
