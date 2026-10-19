"""wind — LIVE-PARITY proofs (PRODUCTION CUTOVER CERTIFICATION, offline portion): the Brain's real artifact through the LIVE Publisher against FAKE clients.
Separate from the 19 structural proofs on purpose. Proves nothing about real databases, rules or IAM (those are LIVE_ONLY exit-gate checks). No cutover is performed."""
from brain_cert_kit.live_parity import make_live_parity_tests
from wind_cert_spec import SPEC

globals().update(make_live_parity_tests(SPEC))


def test_wind_live_parity_reproduces_the_intended_projection_including_the_publisher_derived_snapshot_copies():
    """WIND SPECIAL CASE: nothing here assumes the deployed Wind image equals repository HEAD (that is a LIVE cutover verification item). The test proves the Publisher
    can reproduce the INTENDED Wind projection from the repository's own artifact builder."""
    import datetime as dt
    from sector_brain_platform.publisher_live.rig import Rig
    r = Rig(brains=("wind",), clock=dt.datetime(2026, 10, 15, 4, tzinfo=dt.timezone.utc))
    r.publish_first(SPEC.artifact_factory(1, "2026-10-12T06:30:00Z", None, False))
    lakes = [k for k in (r.rtdb.get("lakes") or {}) if (r.rtdb.get(f"lakes/{k}/states/wind") is not None)]
    assert lakes, "the Wind artifact carries live-lake state"
    for k in lakes:
        assert r.rtdb.get(f"snapshots/{k}/latest/wind") == r.rtdb.get(f"lakes/{k}/states/wind"), "Publisher-derived legacy snapshot copy equals the state"
        assert r.rtdb.get(f"snapshots/{k}/latest/brainVersions/wind") is not None
        assert r.rtdb.get(f"snapshots/{k}/latest/lakeId") is None and r.rtdb.get(f"lakeFleet/{k}/lakeId") is None, "lake identity stays Platform Lake Registry-owned"
    assert r.rtdb.get("health/jobs/wind-hourly") is None, "job health is Orchestrator-owned"
