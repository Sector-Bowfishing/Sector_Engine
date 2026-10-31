"""brain-publisher (the recurring central Publisher job): one bounded pass against FAKE clients only. No production service, credential or network is touched."""
import json
import os
import re

import pytest

import publish_job as J
from gatep_fixtures import bundle, lake_section, registry_section, source_section
from live_rig import Rig
from sector_brain_platform import execution_control as EC
from sector_brain_platform import publication_requests as PR
from sector_brain_platform.publisher import PublishHistory, default_registry
from sector_brain_platform.publisher.storage import AccessDenied, orchestrator_view
from sector_brain_platform.publisher_live.authorization import BrainAuthorization, LiveAuthorization
from sector_brain_platform.publisher_live.publisher import LivePublisher

HERE = os.path.dirname(os.path.abspath(__file__))
JOB = os.path.dirname(HERE)
APPROVAL = "approval/test/wind-cutover"
ENABLED = EC.parse({"schema": EC.SCHEMA, "state": "ENABLED", "approvalRef": "approval/test/resume", "brains": {"wind": {"enabled": True}}})
PAUSED = EC.parse({"schema": EC.SCHEMA, "state": "PAUSED", "brains": {}})


def cutover(tmp_path, brains=None):
    p = tmp_path / "cutover.json"
    p.write_text(json.dumps({"schema": "sector-publication-cutover-v1", "brains": brains if brains is not None else {"wind": {"state": "CENTRAL", "approvalRef": APPROVAL, "orderReviewRef": "review/test"}}}))
    return str(p)


class World:
    """One artifact store + fake Brain database; the Orchestrator writes requests, the job publishes through a LivePublisher whose history uses the job's own view."""
    def __init__(self):
        self.rig = Rig(brains=("wind",))
        self.store, self.rtdb = self.rig.store, self.rig.rtdb
        self.made = []

    def publisher(self, brain):
        p = LivePublisher(default_registry(), PublishHistory(PR.publisher_job_view(self.store)), self.rtdb, LiveAuthorization(BrainAuthorization(brain, APPROVAL)),
                          clock=lambda: self.rig.clock)
        self.made.append(p)
        return p

    def produce(self, n=1, speed=None, minutes=0, approval=APPROVAL, reconcile=True):
        secs = [lake_section(speed=speed), registry_section(), source_section()] if speed is not None else None
        ref = self.rig.ref(bundle(n=n, minutes=minutes, sections=secs))
        if reconcile:
            self.publisher("wind").acknowledge_baseline(ref, approval_ref="approval/baseline/test")
        PR.write_request(orchestrator_view(self.store), PR.build_request(ref, approval_ref=approval, requested_at=f"2026-10-31T0{n}:00:00Z", run_id=f"run-{n}"))
        return ref

    def run(self, path, *, live, control=ENABLED, **kw):
        return J.run_pass(store=self.store, control=control, cutover_path=path, make_publisher=self.publisher, live=live, clock=lambda: self.rig.clock, **kw)


def test_paused_execution_control_holds_the_whole_pass_and_touches_nothing(tmp_path):
    w = World(); w.produce()
    made, calls = len(w.made), w.rtdb.calls
    rep = w.run(cutover(tmp_path), live=True, control=PAUSED)
    assert rep["status"] == "HELD" and rep["published"] == 0 and len(w.made) == made and w.rtdb.calls == calls
    assert J.run_pass(store=w.store, control=EC.parse(None), cutover_path=cutover(tmp_path), make_publisher=w.publisher, live=True)["status"] == "HELD"   # absent control = PAUSED


def test_an_admin_run_needs_an_explicit_reference(tmp_path):
    w = World(); w.produce()
    rep = w.run(cutover(tmp_path), live=True, control=PAUSED, admin_ref="admin/test/2026-10-31")
    assert rep["status"] == "DONE" and rep["published"] == 1 and rep["adminRef"] == "admin/test/2026-10-31"


def test_dry_run_prepares_the_exact_update_and_writes_nothing_anywhere(tmp_path):
    w = World(); w.produce()
    before = sorted(w.store.list("publishes/"))
    rep = w.run(cutover(tmp_path), live=False)
    r = rep["brains"]["wind"]["results"]
    assert rep["mode"] == "DRY_RUN" and len(r) == 1 and r[0]["result"] == "PUBLISHED" and r[0]["updatePaths"] > 0 and r[0]["applied"] is False
    assert rep["published"] == 0 and w.rtdb.calls == 0 and sorted(w.store.list("publishes/")) == before


def test_live_pass_publishes_once_and_the_next_pass_finds_nothing_pending(tmp_path):
    w = World(); w.produce()
    rep = w.run(cutover(tmp_path), live=True)
    assert rep["published"] == 1 and rep["brains"]["wind"]["results"][0]["applied"] is True
    assert w.rtdb.get("brains/wind/publication")["status"] == "COMPLETE"
    again = w.run(cutover(tmp_path), live=True)
    assert again["brains"]["wind"]["pending"] == 0 and again["published"] == 0              # decided in the Publisher's history: never submitted twice


def test_only_central_brains_with_the_matching_approval_are_considered(tmp_path):
    w = World(); w.produce()
    assert w.run(cutover(tmp_path, brains={}), live=True)["brains"] == {}                    # not in the cutover document: the Brain's direct writer is the writer
    w2 = World(); w2.produce(approval="approval/someone-else")
    rep = w2.run(cutover(tmp_path), live=True)
    assert rep["published"] == 0 and {p["kind"] for p in rep["problems"]} == {"REQUEST_APPROVAL_MISMATCH"}


def test_a_brain_disabled_in_the_execution_control_is_held(tmp_path):
    w = World(); w.produce()
    ctl = EC.parse({"schema": EC.SCHEMA, "state": "ENABLED", "approvalRef": "approval/test/resume", "brains": {"wind": {"enabled": False}}})
    rep = w.run(cutover(tmp_path), live=True, control=ctl)
    assert rep["brains"]["wind"]["status"] == "HELD" and rep["published"] == 0


def test_a_tampered_or_missing_artifact_is_never_published(tmp_path):
    w = World(); ref = w.produce()
    w.store.put(ref.location, b'{"tampered": true}')                                       # a later generation of the same key: the requested digest no longer matches
    rep = w.run(cutover(tmp_path), live=True)
    assert rep["published"] == 0 and rep["problems"][0]["kind"] == "ARTIFACT_DIGEST_MISMATCH"


def test_malformed_requests_are_reported_and_skipped(tmp_path):
    w = World(); w.produce()
    orchestrator_view(w.store).put(PR.PREFIX + "wind/junk.json", b"not json", if_generation_match=0)
    orchestrator_view(w.store).put(PR.PREFIX + "wind/other.json", json.dumps({"schema": PR.SCHEMA}).encode(), if_generation_match=0)
    rep = w.run(cutover(tmp_path), live=True)
    assert rep["published"] == 1 and {p["kind"] for p in rep["problems"]} == {"REQUEST_UNREADABLE", "REQUEST_SCHEMA"}


def test_the_pass_is_bounded(tmp_path):
    w = World()
    for n, speed in ((1, 3.0), (2, 9.0), (3, 14.0)):
        w.produce(n=n, speed=speed, minutes=n, reconcile=(n == 1))
    rep = w.run(cutover(tmp_path), live=True, max_artifacts=2)
    assert len(rep["brains"]["wind"]["results"]) == 2 and rep["brains"]["wind"]["status"] == "BUDGET_EXHAUSTED"


def test_the_request_module_reads_live_records_with_the_live_publishers_own_mode_name():
    from sector_brain_platform.publisher_live.model import LIVE_MODE
    assert PR.LIVE_MODE == LIVE_MODE


def test_requests_are_create_only_and_idempotent():
    w = World(); ref = w.rig.ref(bundle())
    req = PR.build_request(ref, approval_ref=APPROVAL, requested_at="2026-10-31T01:00:00Z", run_id="r")
    o = orchestrator_view(w.store)
    assert PR.write_request(o, req)[1] is True and PR.write_request(o, req)[1] is False
    with pytest.raises(ValueError):
        PR.write_request(o, {**req, "runId": "different"})
    with pytest.raises(ValueError):
        PR.build_request(ref, approval_ref=" ", requested_at="x", run_id="r")


# ------------------------------------------------------------------------------------------------------------- denied writes (identity split, repository half)
def test_the_publisher_job_view_cannot_write_artifacts_requests_or_the_orchestrator_ledger():
    w = World()
    v = PR.publisher_job_view(w.store)
    for key in ("artifacts/wind/x/artifact.json", PR.PREFIX + "wind/x.json", "exports/orchestrator/ledger.json", "scores/wind/x.json"):
        with pytest.raises(AccessDenied):
            v.put(key, b"{}", if_generation_match=0)
    v.put("publishes/wind/probe/record.json", b"{}", if_generation_match=0)                 # its own prefix only
    assert not hasattr(v, "delete")                                                          # immutable history: no delete at all


def test_the_orchestrator_view_cannot_write_publications_or_heads():
    o = orchestrator_view(World().store)
    for key in ("publishes/wind/x/record.json", "publishes/_heads/x.json", "artifacts/wind/x/artifact.json"):
        with pytest.raises(AccessDenied):
            o.put(key, b"{}", if_generation_match=0)


def test_the_live_publisher_in_the_job_refuses_platform_and_foreign_keys():
    from sector_brain_platform.publisher_live.security_model import AccessDenied as KeyDenied, assert_publisher_keys
    for key in ("scores/wind", "control/executionControlV1", "health/jobs/wind-hourly", "brains/water-clarity/status", "jobs/wind-hourly", "brains/wind/score"):
        with pytest.raises(KeyDenied):
            assert_publisher_keys("wind", {key: 1})


def test_the_job_arms_the_database_client_only_with_live_and_never_weakens_release_approval():
    src = open(os.path.join(JOB, "publish_job.py"), encoding="utf-8").read()
    assert re.findall(r"armed=([^)]*)\)", src) == ["True"] and "if a.live else _ReadOnlyRtdb(reader)" in src
    assert "require_approved=True" in src and "require_approved=False" not in src
    with pytest.raises(PermissionError):
        J._ReadOnlyRtdb(object()).update({"brains/wind/x": 1})


def test_the_deploy_definition_refuses_without_approval_defaults_to_dry_run_and_creates_no_schedule():
    sh = open(os.path.join(JOB, "deploy-job.sh"), encoding="utf-8").read()
    assert 'MICHAEL_APPROVED_BRAIN_PUBLISHER_DEPLOY:-}" != "yes"' in sh
    assert 'PUBLISHER_MODE="${PUBLISHER_MODE:-dry-run}"' in sh and "--live" not in sh.split("PUBLISHER_MODE")[0]
    assert not re.search(r"gcloud\s+scheduler\s+jobs\s+(create|update|resume)", sh)        # PL-15: started by brain-orchestrator only
    assert "add-iam-policy-binding" not in sh and "service-accounts create" not in sh       # identities and grants are a separate approved step (Sector_Ops 19)


def test_the_staged_image_runs_and_verifies_each_central_brains_packaged_release(tmp_path):
    """The deploy context alone (no repo): the job starts and refuses without a bucket; Water Clarity's packaged release verifies file by file, and is NOT approved, so a live
    publication through this job is refused by the release resolver until the release approval is recorded (Sector_Ops 18 D2). That dependency is deliberate and visible."""
    import subprocess
    import sys
    stage = tmp_path / "ctx"
    subprocess.run(["bash", os.path.join(JOB, "deploy-job.sh"), "--stage-only", str(stage)], check=True, capture_output=True, timeout=120)
    r = subprocess.run([sys.executable, "-I", "publish_job.py"], cwd=stage, capture_output=True, text=True, timeout=60, env={"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path)})
    assert r.returncode == 2 and "REFUSED" in r.stderr
    from sector_brain_platform.knowledge_release import load_release
    from sector_brain_platform.publisher_live.release_resolver import PackagedReleaseResolver
    rel = load_release(str(stage / "releases" / "water-clarity"), "water-clarity")
    args = (rel["releaseId"], "image:knowledge-release.json", rel["releaseDigest"])
    assert PackagedReleaseResolver(str(stage / "releases" / "water-clarity"), "water-clarity", require_approved=False)(*args) is True
    assert PackagedReleaseResolver(str(stage / "releases" / "water-clarity"), "water-clarity", require_approved=True)(*args) is (rel["approvalStatus"] == "APPROVED")
