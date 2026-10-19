"""S1: a successful Publisher publication is a Brain state change for the Platform scorer; SKIP / failed / partial are not; scoring stays Platform-owned."""
import ast
import os

from live_rig import Rig
from gatep_fixtures import bundle, lake_section, registry_section, source_section
from sector_brain_platform import publication_trigger as PT

ORCH = os.path.join(os.path.dirname(__file__), "..", "..", "brain-orchestrator", "orchestrate.py")


def test_without_a_publication_the_token_is_exactly_the_legacy_one():
    assert PT.seen_token({"lastSuccessfulRun": "t1", "status": "x"}) == "t1" and PT.seen_token({}) is None and PT.seen_token(None) is None


def test_only_a_complete_publication_with_a_new_artifact_changes_the_token():
    base = {"lastSuccessfulRun": "t1"}
    t0 = PT.seen_token(base)
    complete = {**base, "publication": {"artifactId": "a1", "status": "COMPLETE"}}
    assert PT.seen_token(complete) != t0
    assert PT.seen_token({**base, "publication": {"artifactId": "a1", "status": "COMPLETE"}}) == PT.seen_token(complete)           # idempotent: same artifact, same token
    assert PT.seen_token({**base, "publication": {"artifactId": "a2", "status": "COMPLETE"}}) != PT.seen_token(complete)
    for not_complete in ({"artifactId": "a9", "status": "PARTIAL"}, {"artifactId": "a9", "status": "FAILED"}, {"artifactId": "a9", "status": "SHADOW"}, {"pending": {"artifactId": "a9"}}):
        assert PT.seen_token({**base, "publication": not_complete}) == t0


def test_changed_brains_names_only_the_brain_that_published():
    brains = {"wind": {"lastSuccessfulRun": "t", "publication": {"artifactId": "a2", "status": "COMPLETE"}}, "water-clarity": {"lastSuccessfulRun": "t2"}, "biological-state": {"lastSuccessfulRun": "t3"}}
    last = {"wind": PT.seen_token({"lastSuccessfulRun": "t", "publication": {"artifactId": "a1", "status": "COMPLETE"}}), "water-clarity": "t2", "biological-state": "t3"}
    assert PT.changed_brains(brains, last) == ["wind"]
    assert PT.changed_brains(brains, {b: PT.seen_token(n) for b, n in brains.items()}) == []


def test_end_to_end_publish_skip_failure_against_the_live_publisher():
    r = Rig()
    r.publish_first(bundle(n=1))
    seen = {b: PT.seen_token(n) for b, n in r.rtdb.get("brains").items()}
    assert PT.changed_brains(r.rtdb.get("brains"), seen) == []
    r.live.publish(r.ref(bundle(n=2, minutes=30)))                                              # SKIP
    assert PT.changed_brains(r.rtdb.get("brains"), seen) == []
    r.rtdb.inject("definite")
    r.live.publish(r.ref(bundle(n=3, minutes=40, sections=[lake_section(speed=9.0), registry_section(), source_section()])))     # failed
    assert PT.changed_brains(r.rtdb.get("brains"), seen) == []
    r.live.publish(r.ref(bundle(n=3, minutes=40, sections=[lake_section(speed=9.0), registry_section(), source_section()])))     # published
    assert PT.changed_brains(r.rtdb.get("brains"), seen) == ["wind"]


def test_scoring_stays_outside_the_publisher_and_the_orchestrator_is_wired_to_the_token():
    pkg = os.path.join(os.path.dirname(__file__), "..", "sector_brain_platform", "publisher_live")
    for f in os.listdir(pkg):
        if f.endswith(".py"):
            src = open(os.path.join(pkg, f)).read()
            assert "score_brains" not in src and "scoring" not in src.replace("scoring-", ""), f           # the Publisher neither scores nor invokes the scorer
    tree = ast.parse(open(ORCH).read())
    assert any(isinstance(n, ast.Attribute) and n.attr == "seen_token" and getattr(n.value, "id", "") == "PT" for n in ast.walk(tree)), "orchestrate.py must use publication_trigger.seen_token"
