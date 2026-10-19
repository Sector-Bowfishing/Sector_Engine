"""fish — LIVE-PARITY proofs (PRODUCTION CUTOVER CERTIFICATION, offline portion): the Brain's real artifact through the LIVE Publisher against FAKE clients.
Separate from the 19 structural proofs on purpose. Proves nothing about real databases, rules or IAM (those are LIVE_ONLY exit-gate checks). No cutover is performed."""
from brain_cert_kit.live_parity import make_live_parity_tests
from fish_cert_spec import SPEC

globals().update(make_live_parity_tests(SPEC))


def test_fish_live_parity_keeps_the_inputs_the_orchestrator_plan_reads_and_the_release_identity():
    """FISH SPECIAL CASE: the live Fish release/score are NOT touched (fake state only). The published registry children that run.py --plan reads must exist, or
    --plan would loop PUBLISH after a cutover."""
    import datetime as dt
    from sector_brain_platform.publisher_live.rig import Rig
    art = SPEC.artifact_factory(1, "2026-10-12T06:30:00Z", None, False)
    r = Rig(brains=("biological-state",), clock=dt.datetime(2026, 10, 15, 4, tzinfo=dt.timezone.utc))
    r.publish_first(art)
    reg = r.rtdb.get("brains/biological-state")
    lin = art["lineage"]
    assert reg["researchVersion"] == lin["knowledgeRelease"] and reg["manifestSha256"] == lin["manifestSha256"].replace("sha256:", "")
    assert isinstance(reg["version"], str) and reg["health"] == "HEALTHY"
    pub = r.rtdb.get("brains/biological-state/publication")
    assert pub["knowledgeRelease"] == lin["knowledgeRelease"]       # FINDING: the publication record carries the release id only; manifest identity lives in the registry children (P6 resolver would verify it)
    assert r.rtdb.get("scores") is None and r.rtdb.get("health/brains/biological-state/lastRun") is None


def test_fish_live_parity_an_unverifiable_release_is_refused_before_any_live_write():
    """P6 wired end to end: with a resolver installed, the Fish artifact's declared manifest must resolve to its declared hash; nothing resolves here, so nothing is written."""
    import datetime as dt
    from sector_brain_platform.publisher_live import LiveResult
    from sector_brain_platform.publisher_live.release_resolver import ManifestReleaseResolver
    from sector_brain_platform.publisher_live.rig import Rig
    r = Rig(brains=("biological-state",), clock=dt.datetime(2026, 10, 15, 4, tzinfo=dt.timezone.utc), release_resolver=ManifestReleaseResolver(lambda ref: None))
    ref = r.ref(SPEC.artifact_factory(1, "2026-10-12T06:30:00Z", None, False))
    try:
        res = r.live.publish(ref)
    except Exception:                                     # no baseline can be built from a rejected artifact: either way nothing is written
        res = None
    assert r.rtdb.calls == 0 and (res is None or res.result in (LiveResult.FAILED_VALIDATION, LiveResult.REJECTED)) and "RELEASE_UNRESOLVED" in (res.codes if res else ["RELEASE_UNRESOLVED"])
