import datetime as dt

from sector_brain_platform import shadow_lane as SL

REL = {"releaseId": "depth-cand", "releaseDigest": "sha256:" + "b" * 64, "approvalStatus": "NOT_RECORDED", "store": "PACKAGED_IN_IMAGE"}
AP = {"status": "ABSTAIN", "reason": "BLOCKED_AWAITING_APPROVED_RELEASE"}


def _doc(patches, prev=None):
    return SL.summarize("depth", "depth", patches, {"ok": True, "evaluated": 1}, REL, AP, "2026-10-22T07:00:00Z", "brain-orchestrator@abc", prev=prev)


def test_summary_is_labelled_experimental_and_keeps_only_allowlisted_lake_fields():
    d = _doc([{"lakes/X/states/depth": {"readiness": "DEGRADED", "kind": "observed", "bandShares": [0.1], "provenance": {"readiness": "DEGRADED"}}},
              {"brains/depth": {"version": "1"}, "lakes/Y/states/depth": {"provenance": {"readiness": "PROFILED"}}}])
    assert SL.problems(d) == []
    assert d["lakes"] == {"X": {"readiness": "DEGRADED", "kind": "observed"}, "Y": {"readiness": "PROFILED"}}
    assert d["readinessCounts"] == {"DEGRADED": 1, "PROFILED": 1} and d["outputDigest"].startswith("sha256:")
    assert d["authoritative"] is False and d["customerEligible"] is False and "sector-intelligence" in " ".join(d["forbiddenConsumers"])
    assert (d["lane"], d["executionMode"], d["experimental"], d["knowledgeState"]) == ("INTERNAL_EXPERIMENTAL", "INTERNAL", True, "CANDIDATE")   # IO-02/IO-05


def test_digest_is_deterministic_and_history_is_bounded():
    p = [{"lakes/X/states/depth": {"readiness": "DEGRADED"}}]
    a, b = _doc(p), _doc(p)
    assert a["outputDigest"] == b["outputDigest"]
    prev = {"history": [{"runAt": str(i)} for i in range(30)]}
    assert len(_doc(p, prev)["history"]) == SL.HISTORY


def test_problems_refuse_mislabelled_documents():
    d = _doc([])
    assert SL.problems({**d, "authoritative": True}) and SL.problems({**d, "classification": "PUBLIC"})
    assert SL.problems({**d, "candidateRelease": {**REL, "approvalStatus": "APPROVED"}})
    assert SL.problems({**d, "lakes": {"X": {"readiness": "R", "value": 3}}})
    assert SL.problems({**d, "lane": "APPROVED_ASSESSMENT"}) and SL.problems({**d, "experimental": False}) and SL.problems({**d, "executionMode": "APPROVED_SCIENCE"})


def test_due_follows_the_cadence():
    now = dt.datetime(2026, 10, 22, 12, tzinfo=dt.timezone.utc)
    assert SL.due(None, 24, now) and SL.due({"runAt": "garbage"}, 24, now)
    assert not SL.due({"runAt": "2026-10-22T00:00:00Z"}, 24, now) and SL.due({"runAt": "2026-10-21T11:00:00Z"}, 24, now)
