"""SI-1 (a) draft: Intelligence seals ONE artifact create-only instead of writing the database, and a runner outside Cloud Run supplies the
Engine serving revision (Sector_Ops #50/#51)."""
import json
import os

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


def test_artifact_mode_refuses_without_a_destination(capsys, monkeypatch):
    monkeypatch.delenv("SI_ARTIFACT_BUCKET", raising=False)                     # else the default destination comes from the environment and the run reads live
    assert run.main(["--artifact"]) == 2
    assert "needs --artifact-dir or --artifact-bucket" in capsys.readouterr().err


def test_runner_supplied_revision_is_serving_but_unverified_without_a_digest():
    svc = run.runner_service({"ENGINE_REVISION": "sector-engine-00080-wes"})
    s = sib.engine_serving(svc, T.LINEAGE, S.NOW)
    assert s["status"] == "SERVING" and s["revision"] == "sector-engine-00080-wes" and s["lineageVerified"] is False
    assert s["reason"] == "unverified: the runner supplied no image digest" and s["lineageSource"] == "RUNNER_SUPPLIED"
    deps = {bid: {"exists": True, "displayName": bid} for bid in sib.DEPENDENCY_ORDER}
    b = [x for x in sib.derived_blockers(deps, s) if x["id"] == "ENGINE_LINEAGE_UNVERIFIED"]
    assert len(b) == 1 and "differs" not in b[0]["title"] and b[0]["severity"] == "info"          # not a false "image differs" blocker


def test_a_runner_supplied_digest_is_a_claim_never_a_verification():
    svc = run.runner_service({"ENGINE_REVISION": "r1", "ENGINE_IMAGE_DIGEST": T.LINEAGE["imageDigest"]})
    s = sib.engine_serving(svc, T.LINEAGE, S.NOW)
    assert s["lineageVerified"] is False and s["digestMatchesDeclared"] is True and "not attested" in s["reason"]
    other = sib.engine_serving(run.runner_service({"ENGINE_REVISION": "r1", "ENGINE_IMAGE_DIGEST": "sha256:" + "0" * 64}), T.LINEAGE, S.NOW)
    assert other["digestMatchesDeclared"] is False and "differs" in other["reason"]


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


def test_a_built_artifact_declares_the_packaged_release_and_the_resolver_accepts_it():
    """SI-A4 (review of #124): the lineage comes from a REAL artifact (publish_artifact.build_artifact), not from lineage_triple called directly. The packaged
    resolver over the release folder accepts it for a test publication. A live publication stays refused while the approval is NOT_RECORDED."""
    import intelligence_support as S
    from sector_brain_platform.knowledge_release import lineage_triple
    from sector_brain_platform.publisher_live.release_resolver import PackagedReleaseResolver
    lin = S.build(S.run_updates()).artifact["lineage"]
    declared = (lin["knowledgeRelease"], lin["manifestRef"], lin["manifestSha256"])
    assert declared == lineage_triple(S.release()) and "NONE" not in declared
    runtime = os.path.join(S.REPO, "brains", "sector-intelligence", "runtime")
    assert PackagedReleaseResolver(runtime, "sector-intelligence", require_approved=False)(*declared) is True
    approved = S.release().get("approvalStatus") == "APPROVED"
    assert approved is False                                                                # NOT_RECORDED today: the owner records it (SI-A5)
    assert PackagedReleaseResolver(runtime, "sector-intelligence", require_approved=True)(*declared) is False


def test_emit_writes_the_stored_artifact_for_a_runner_hand_off(tmp_path):
    """SI-A5 (draft): Pulse's lease jobs hand off {out}/artifact.json; --emit writes exactly the stored artifact there, create-only."""
    store, emit = LocalDirObjectStore(tmp_path / "store"), tmp_path / "artifact.json"
    ref = run.seal_and_store(S.run_updates(), now=S.NOW, release=S.release(), consumed=None, store=store, execution_id=S.uid(8), emit=str(emit))
    assert json.loads(emit.read_text()) == json.loads(store.get(ref["location"]))
    with pytest.raises(FileExistsError):
        run.seal_and_store(S.run_updates(), now=S.NOW, release=S.release(), consumed=None, store=LocalDirObjectStore(tmp_path / "s2"), emit=str(emit))
