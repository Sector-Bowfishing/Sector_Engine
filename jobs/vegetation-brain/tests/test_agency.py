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


# ---------------------------------------------------------------- source 2: SFWMD Okeechobee littoral map (Level 1, as-is)
LIT = os.path.join(os.path.dirname(__file__), "..", "vegetation_brain", "data", "agency_sfwmd_okeechobee.json")


def lit_rec():
    return AG.build_sfwmd_record("Okeechobee|FL", [{"code": "OW", "desc": "OW: Open Water", "n": 14000}, {"code": "MFGtD", "desc": "MFGtD : Dominant Cattail", "n": 7500},
                                                   {"code": "MFF", "desc": "MFF: Floating Emergent Marsh", "n": 5000}, {"code": "CSs", "desc": "CSs: Willow Scrub", "n": 3900}], "2026-10-14")


def test_area_comes_from_cell_counts_and_open_water_is_not_vegetation():
    r = lit_rec()
    assert r["openWaterKm2"] == 140.0 and r["classes"][0]["code"] == "MFGtD" and r["classes"][0]["areaKm2"] == 75.0
    assert all(c["code"] != "OW" for c in r["classes"]) and AG.validate_sfwmd(r) == []


def test_littoral_block_is_scoped_dated_historical_and_internal_only():
    b = AG.littoral_block(lit_rec(), 2026)
    assert b["status"] == "PROVIDER_VERIFIED" and b["surveyYear"] == 2016 and b["surveyMonth"] == 6 and b["historical"] is True
    assert "Moore Haven" in b["scope"] and b["internalOnly"] is True and "km2" in b["units"]["areaKm2"]
    bad = lit_rec()
    bad["classes"][0]["areaKm2"] = 10_000
    assert AG.littoral_block(bad, 2026) is None                           # class areas exceeding the mapped area are refused, not repaired


def test_state_can_carry_both_agency_sources_and_still_makes_no_satellite_claim():
    st, _ = S.build_state({**CAND, "lakeId": "Okeechobee|FL"}, None, NOW, agency=rec([(2023, 38, 8)]), littoral=lit_rec())
    ag = st["agencyObservation"]
    assert ag["sourceId"] == "fwc-ltm-pac-pvi" and ag["additional"][0]["sourceId"] == "sfwmd-okeechobee-littoral"
    only, _ = S.build_state({**CAND, "lakeId": "Okeechobee|FL"}, None, NOW, littoral=lit_rec())
    assert only["agencyObservation"]["sourceId"] == "sfwmd-okeechobee-littoral" and only["claimMaturity"]["agencyVegetationObservation"]["state"] == "PROVIDER_VERIFIED"
    assert st["surfaceVegetation"]["status"] == "UNKNOWN" and st["submergedVegetation"]["observed"] is False


def test_shipped_sfwmd_data_cross_checks_against_geometry():
    d = json.load(open(LIT))
    r = d["records"]["Okeechobee|FL"]
    assert d["problems"] == [] and AG.validate_sfwmd(r) == []
    assert 0.95 <= r["mercatorAreaCheck"]["ratio"] <= 1.05                # cell-count area agrees with the polygon geometry at the lake's latitude
    assert "/Users/" not in open(LIT).read()
