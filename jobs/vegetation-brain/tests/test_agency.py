import json
import os
from datetime import datetime, timezone

import pytest

from vegetation_brain import agency as AG
from vegetation_brain import contract as C
from vegetation_brain import fleet as F
from vegetation_brain import state as S
from vegetation_brain.publish import publish
from vegetation_brain.writer import DryRunWriter

NOW = datetime(2026, 10, 14, 12, tzinfo=timezone.utc)
DATA = os.path.join(os.path.dirname(__file__), "..", "vegetation_brain", "data", "agency_fwc_pacpvi.json")
CAND = {"lakeId": "Apopka|FL", "tier": "HIGH", "readiness": "PROFILED", "reasons": [], "areaKm2": 125.0, "geometryConfidence": "HIGH", "geometryVersion": "v1"}


def rec(rows):
    return AG.build_record("Apopka|FL", [{"Year": y, "PAC": a, "PVI": v, "Label": "Apopka (Orange Co.)"} for y, a, v in rows], "2026-10-14")


def test_good_rows_pass_and_bad_rows_are_dropped_not_repaired():
    r = rec([(2022, 40, 12), (2023, 25, 7), (2023, 130, 7), (2021, 10, 30)])
    assert [(x["year"], x["pac"], x["pvi"]) for x in r["rows"]] == [(2022, 40, 12), (2023, 25, 7)]
    assert len(r["rowsDropped"]) == 2 and any("PVI exceeds PAC" in p for d in r["rowsDropped"] for p in d["problems"])


def test_block_is_level1_as_is_with_source_date_units_and_internal_only():
    b = AG.agency_block(rec([(2022, 40, 12), (2023, 25, 7)]), 2026)
    assert b["status"] == "PROVIDER_VERIFIED" and b["level"] == 1 and b["surveyYear"] == 2023 and b["datePrecision"] == "YEAR"
    assert b["values"] == [{"pac": 25, "pvi": 7}] and "percent of lake surface area" in b["units"]["pac"]
    assert b["ageYears"] == 3 and b["historical"] is True and b["internalOnly"] is True and b["licence"] == "UNCONFIRMED_FOR_CUSTOMER_USE"
    assert "Florida Fish and Wildlife" in b["summary"] and "historical" in b["summary"]


def test_absent_record_is_not_assessed_never_zero():
    for r in (None, {"rows": []}):
        b = AG.agency_block(r, 2026)
        assert b["status"] == "NOT_ASSESSED" and "pac" not in json.dumps(b)


def test_state_carries_agency_truth_and_a_level3_failure_does_not_disable_it():
    st, _ = S.build_state(CAND, None, NOW, agency=rec([(2023, 25, 7)]))
    assert st["agencyObservation"]["status"] == "PROVIDER_VERIFIED"
    assert st["claimMaturity"]["agencyVegetationObservation"]["state"] == "PROVIDER_VERIFIED"
    assert st["claimMaturity"]["surfaceVegetationPresence"]["state"] == "NOT_VALIDATED"   # Level 3 stays failing; Level 1 stays verified
    assert st["surfaceVegetation"]["status"] == "UNKNOWN"                                    # the satellite part says nothing here
    assert st["submergedVegetation"]["observed"] is False                                    # agency sonar scope is not a Sector submerged claim
    assert "Agency" not in st["headline"] and st["headline"] == C.LANGUAGE["NONE"]
    st2, _ = S.build_state(CAND, None, NOW)
    assert st2["agencyObservation"]["status"] == "NOT_ASSESSED" and st2["claimMaturity"]["agencyVegetationObservation"]["state"] == "NOT_ASSESSED"


def test_agency_change_changes_the_fingerprint_and_unchanged_skips():
    a, b = rec([(2023, 25, 7)]), rec([(2023, 25, 7), (2024, 30, 9)])
    assert S.input_fingerprint(CAND, None, {}, "t", a) != S.input_fingerprint(CAND, None, {}, "t", b)
    m = F.build_manifest({"lakes": [{"lakeId": "Apopka|FL", "name": "Apopka", "state": "FL", "lakeKey": "Apopka_FL", "areaKm2": 125.0, "geometry": {"x": 1},
                                     "geometryConfidence": {"level": "HIGH"}, "classification": {}, "geometryVersion": "v1"}]}, version="t")
    w = DryRunWriter()
    r1 = publish(m, w, agency={"Apopka|FL": a}, now=NOW)
    r2 = publish(m, w, agency={"Apopka|FL": a}, now=NOW)
    r3 = publish(m, w, agency={"Apopka|FL": b}, now=NOW)
    assert (r1["skippedUnchanged"], r2["skippedUnchanged"], r3["skippedUnchanged"]) == (0, 1, 0)
    assert w.tree["lakes"]["Apopka_FL"]["states"]["vegetation"]["agencyObservation"]["surveyYear"] == 2024


def test_shipped_fwc_data_is_clean_sourced_and_matches_the_map():
    d = json.load(open(DATA))
    assert d["missing"] == [] and set(d["records"]) == set(AG.FWC_NAME_MAP)
    for lid, r in d["records"].items():
        assert r["rows"] and not r["rowsDropped"], lid
        assert all(0 <= x["pac"] <= 100 and 0 <= x["pvi"] <= x["pac"] + 1 for x in r["rows"]), lid
        assert r["source"]["internalOnly"] is True and r["source"]["datePrecision"] == "YEAR"
    assert d["records"]["Okeechobee|FL"]["multipleRowsPerYear"] is True
    assert "/Users/" not in open(DATA).read()
