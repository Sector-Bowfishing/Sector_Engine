"""LB-14 coverage record (brains/lake/tools/lake_coverage.py), on synthetic rows only."""
import pytest

import lake_coverage as LC

BASE = {"hasDam": "True", "level": "SOURCE_VERIFIED", "levelMissing": "", "levelProvider": "cwms", "levelCurrent": "CURRENT",
        "checkGauge": "NONE_FOUND", "release": "UNKNOWN", "inflow": "UNKNOWN"}


def row(lake, **kw):
    return {"lakeId": lake, **BASE, **kw}


def cov(rec, lake, cap):
    return next(l for l in rec["lakes"] if l["lakeId"] == lake)["capabilityCoverage"][cap]


def test_every_lake_gets_every_capability():
    rec = LC.build([row("B|ST"), row("A|ST")])
    assert rec["schema"] == "sector-lake-coverage-v1" and rec["lakeCount"] == 2
    assert [l["lakeId"] for l in rec["lakes"]] == ["A|ST", "B|ST"]
    for l in rec["lakes"]:
        assert set(l["capabilityCoverage"]) == set(LC.CAPABILITIES)
        assert all(v["status"] in (LC.COVERED, LC.ELIGIBLE, LC.UNKNOWN, LC.NA) and v["reason"] for v in l["capabilityCoverage"].values())


def test_freshness_is_never_assumed():
    rows = [row("T|AL", level="PUBLISHED", levelProvider="tva", release="OPERATOR_OUTFLOW")]
    unfresh = LC.build(rows)
    assert cov(unfresh, "T|AL", "LB-04") == {"status": LC.ELIGIBLE, "reason": "published-freshness-not-shown"}
    assert cov(unfresh, "T|AL", "LB-09")["status"] == LC.ELIGIBLE
    assert unfresh["freshnessSupplied"] is False
    fresh = LC.build(rows, {"T|AL"})
    assert cov(fresh, "T|AL", "LB-04")["status"] == cov(fresh, "T|AL", "LB-07")["status"] == LC.COVERED
    assert cov(fresh, "T|AL", "LB-09") == {"status": LC.COVERED, "reason": "operator-outflow-published"}


def test_applicability_and_unknowns():
    rec = LC.build([row("N|ST", hasDam="False", level="UNKNOWN", levelMissing="level-no-public-source"),
                    row("S|ST", levelCurrent="STALE", release="TAILWATER_GAUGE", checkGauge="CHECK_GAUGE", inflow="INFLOW_GAUGE")])
    assert cov(rec, "N|ST", "LB-09") == {"status": LC.NA, "reason": "no-dam"}
    assert cov(rec, "N|ST", "LB-04") == {"status": LC.UNKNOWN, "reason": "level-no-public-source"}
    assert cov(rec, "N|ST", "LB-13") == {"status": LC.UNKNOWN, "reason": "no-level-source"}
    assert cov(rec, "S|ST", "LB-04") == {"status": LC.ELIGIBLE, "reason": "level-source-stale"}
    assert cov(rec, "S|ST", "LB-09") == {"status": LC.ELIGIBLE, "reason": "tailwater-gauge-source"}
    assert cov(rec, "S|ST", "LB-13") == {"status": LC.ELIGIBLE, "reason": "independent-gauge-recorded"}
    assert rec["summary"]["LB-09"] == {LC.ELIGIBLE: 1, LC.NA: 1}


def test_bad_tables_are_refused():
    with pytest.raises(ValueError):
        LC.build([{"lakeId": "A"}])
    with pytest.raises(ValueError):
        LC.build([row("A"), row("A")])
