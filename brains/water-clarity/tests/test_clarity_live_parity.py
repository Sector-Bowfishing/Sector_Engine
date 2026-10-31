"""water-clarity — LIVE-PARITY proofs (PRODUCTION CUTOVER CERTIFICATION, offline portion): the Brain's real artifact through the LIVE Publisher against FAKE clients.
Separate from the 19 structural proofs on purpose. Proves nothing about real databases, rules or IAM (those are LIVE_ONLY exit-gate checks). No cutover is performed."""
from brain_cert_kit.live_parity import make_live_parity_tests
from clarity_cert_spec import SPEC

globals().update(make_live_parity_tests(SPEC))


def test_clarity_live_parity_the_legacy_writer_is_retired_and_the_publisher_never_replaces_the_whole_node():
    """WATER CLARITY SPECIAL CASE (X14): the retired run.py replaced /brains/water-clarity and /health/brains/water-clarity as whole nodes. The runtime now has no write
    site and builds no whole-node key, so the cutover guard has nothing left to refuse on code grounds; the Publisher's own child-level writes never replace those nodes."""
    from brain_cert_kit import exit_gate
    left = exit_gate.legacy_write_sites(SPEC.brain_dir, "water-clarity")
    assert left == {"writeSites": [], "wholeNodeKeys": []}, left
    import datetime as dt
    from sector_brain_platform.publisher_live.rig import Rig
    r = Rig(brains=("water-clarity",), clock=dt.datetime(2026, 10, 15, 4, tzinfo=dt.timezone.utc))
    r.publish_first(SPEC.artifact_factory(1, "2026-10-12T06:30:00Z", None, False))
    assert "brains/water-clarity" not in r.rtdb.write_keys() and "health/brains/water-clarity" not in r.rtdb.write_keys()
    assert r.rtdb.get("brains/water-clarity/publication")["status"] == "COMPLETE"
