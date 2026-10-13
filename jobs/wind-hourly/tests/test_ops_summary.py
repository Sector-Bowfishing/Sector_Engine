import json
from datetime import datetime, timezone

from sector_wind.brain import contract as C
from sector_wind.brain import ops_summary as OS

NOW = datetime(2026, 10, 14, 1, tzinfo=timezone.utc)
RESCORE = {"computedAt": "2026-10-14T00:55:00Z", "certification": {"previous": 3.1, "new": 3.3, "newRaw": 3.27, "caps": [{"cap": 6.0, "rule": "Exposure or surface never field-validated"}],
           "dimensionsChanged": {"8": {"before": 0.0, "after": 1.33}}, "dimensions": {"8": {"points": 1.33, "weight": 8}, "2": {"points": 4.32, "weight": 8}}},
           "bwis": {"new": 5.4, "newTotal": 54.16}}
REL = {"summary": {"asOf": "2026-10-14T00:50:00Z", "validArchiveDays": 6, "validBrainPublishDays": 1, "invalidArchiveDays": [{"date": "2026-10-07", "reasons": ["clock started"]}], "executions": 190,
        "failedExecutions": 0, "staleStatesLogged": 0, "freshnessHoursAfterInit": {"median": 1.14}, "projectedArchiveGate": "2026-11-07T03:00Z", "projectedBrainPublishGate": "2026-11-12T03:00Z",
        "projectionAssumption": "all remaining days valid"}, "days": [{"date": "2026-10-08", "valid": True}, {"date": "2026-10-13", "valid": True}, {"date": "2026-10-14", "valid": False}]}
FROZEN = {"value": 3.1, "basis": "FROZEN", "updatedAt": "2026-10-12T06:16:16Z"}


def build(**kw):
    base = dict(rescore=RESCORE, reliability=REL, frozen_score=FROZEN, coverage=OS.coverage_from_manifest(), prerequisite_branch={"name": "feat/cost-efficient-scheduling", "merged": False})
    base.update(kw)
    return OS.build(NOW, **base)


def test_values_come_from_inputs_not_constants():
    s = build()
    assert s["certification"]["value"] == 3.3 and s["publishedScore"]["value"] == 3.1 and s["publishedScore"]["differsFromComputed"] is True
    assert s["reliability"]["progress"] == "6 / 30 valid archive days" and s["reliability"]["lastValidArchiveDay"] == "2026-10-13" and s["reliability"]["projectedArchiveGate"] == "2026-11-07T03:00Z"
    other = json.loads(json.dumps(REL)); other["summary"]["validArchiveDays"] = 9
    assert build(reliability=other)["reliability"]["progress"] == "9 / 30 valid archive days"
    rs = json.loads(json.dumps(RESCORE)); rs["certification"]["new"] = 3.9
    assert build(rescore=rs)["certification"]["value"] == 3.9


def test_missing_inputs_are_unknown_never_zero():
    s = build(rescore=None, reliability=None, frozen_score=None, coverage=None)
    for k in ("certification", "bwis", "publishedScore", "reliability", "coverage"):
        assert s[k]["value"] is None and s[k]["unknownReason"], k


def test_coverage_counts_match_the_manifest_and_nothing_is_customer_visible():
    c = build()["coverage"]
    assert (c["audited"], c["estimated"], c["pointOnly"]) == (74, 473, 74) and c["labelEligible"] == 522 and c["blocked"] == 25 and c["directoryLakes"] == 621
    assert c["customerVisibleExposure"] == 0


def test_status_fields_are_honest_about_unreleased_state():
    s = build()
    assert s["h2"]["status"] == "SEALED" and s["h2"]["runnerHasRun"] is False and s["h2"]["sealedUntil"] == C.iso(C.H2_SEALED_UNTIL)
    assert s["providers"]["customer"]["status"] == "ACTIVE_PRODUCTION" and s["providers"]["candidate"]["promoted"] is False
    assert s["providers"]["dualLogging"] == "NOT_STARTED" and s["providers"]["customerSwitch"] == "NOT_APPROVED"
    assert s["tonightContract"]["published"] is False and "layDown" in s["tonightContract"]["withheldClaims"]
    assert s["lifecycle"]["status"] == "CALIBRATION" and s["lifecycle"]["candidatePromoted"] is False


def test_blockers_are_categorised_and_the_prerequisite_branch_appears_only_while_unmerged():
    cats = {b["category"] for b in build()["blockers"]}
    assert cats == {"TIME", "FIELD", "MICHAEL", "LAKE_IDENTITY", "VALIDATION", "PREREQUISITE_BRANCH"}
    merged = build(prerequisite_branch={"name": "feat/cost-efficient-scheduling", "merged": True})
    assert "PREREQUISITE_BRANCH" not in {b["category"] for b in merged["blockers"]}
    assert set(cats) <= set(OS.CATEGORIES)


def test_serialisation_is_deterministic():
    a, b = json.dumps(build(), sort_keys=True), json.dumps(build(), sort_keys=True)
    assert a == b
