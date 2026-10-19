"""water-clarity — LIVE-PARITY proofs (PRODUCTION CUTOVER CERTIFICATION, offline portion): the Brain's real artifact through the LIVE Publisher against FAKE clients.
Separate from the 19 structural proofs on purpose. Proves nothing about real databases, rules or IAM (those are LIVE_ONLY exit-gate checks). No cutover is performed."""
from brain_cert_kit.live_parity import make_live_parity_tests
from clarity_cert_spec import SPEC

globals().update(make_live_parity_tests(SPEC))


def test_clarity_live_parity_the_whole_node_legacy_writer_is_still_present_and_therefore_blocks_cutover_completion():
    """WATER CLARITY SPECIAL CASE: the legacy run.py replaces /brains/water-clarity and /health/brains/water-clarity as whole nodes. It is NOT retired here; this proves
    the cutover guard sees it (so CUTOVER_COMPLETE is refused) and that the Publisher's own child-level writes never replace those nodes."""
    import os
    from brain_cert_kit import exit_gate
    left = exit_gate.legacy_write_sites(SPEC.brain_dir, "water-clarity")
    assert left["wholeNodeKeys"] and len(left["writeSites"]) == 2
    import datetime as dt
    from sector_brain_platform.publisher_live.rig import Rig
    r = Rig(brains=("water-clarity",), clock=dt.datetime(2026, 10, 15, 4, tzinfo=dt.timezone.utc))
    r.publish_first(SPEC.artifact_factory(1, "2026-10-12T06:30:00Z", None, False))
    assert "brains/water-clarity" not in r.rtdb.write_keys() and "health/brains/water-clarity" not in r.rtdb.write_keys()
    assert r.rtdb.get("brains/water-clarity/publication")["status"] == "COMPLETE"
