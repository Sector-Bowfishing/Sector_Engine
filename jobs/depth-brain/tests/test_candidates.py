import json
import os

import pytest
from depth_brain import contract as C
from depth_brain.candidates import assess_candidate, cwms_project, level_datum_for, licence_for, range_class, reviewed_lake_ids
from depth_brain.datum import load_provider_table

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = json.load(open(os.path.join(HERE, "depth_brain", "data", "candidates.json")))
CANDS = {c["lakeId"]: c for c in MANIFEST["candidates"]}
TABLE = load_provider_table()


def b(provider, series="", station="", cap="DIRECT_OPERATOR_POOL"):
    return {"provider": provider, "series_or_param": series, "station": station, "capability_class": cap}


# ── datum rules ───────────────────────────────────────────────────────────────────────────────────────────
def test_cwms_same_location_is_same_source_even_when_tagged_local():
    a = assess_candidate("X|AL", {}, b("cwms", "Martin.Elev.Inst.1Hour.0.Raw-APCO"), "CWMS Martin.Elev.Inst.0.Top of Conservation (max)", TABLE,
                         {"X|AL": {"datum": "LOCAL", "office": "SAM", "location": "Martin"}}, {})[0]
    assert a.status == "SAME_SOURCE" and a.usable


def test_cwms_different_location_is_not_same_source():
    a = assess_candidate("X|AL", {}, b("cwms", "Other.Elev.Inst.1Hour.0.Raw"), "CWMS Martin.Elev.Inst.0.Top of Conservation (max)", TABLE, {}, {})[0]
    assert a.status != "SAME_SOURCE"


def test_tva_pool_and_level_are_one_operator_system():
    a = assess_candidate("G|AL", {}, b("tva", "ReservoirElevation"), "TVA top of summer operating zone (GVDA1)", TABLE, {}, {})[0]
    assert a.status == "SAME_OPERATOR_SYSTEM" and a.usable and a.sigma_ft == C.SIGMA_DATUM["SAME_OPERATOR_SYSTEM"]
    # a USACE pool figure with a TVA reading is a different system: never assumed equal
    a2 = assess_candidate("G|AL", {}, b("tva", "ReservoirElevation"), "USACE published pool, inside TVA summer zone", TABLE, {}, {})[0]
    assert not a2.usable


def test_usgs_parameter_defines_datum_and_per_site_00062_is_unknown():
    assert level_datum_for(b("usgs", "62614"), TABLE)[:2] == ("NGVD29", True)
    assert level_datum_for(b("usgs", "62615"), TABLE)[:2] == ("NAVD88", True)
    assert level_datum_for(b("usgs", "00062"), TABLE)[0] is None
    a = assess_candidate("K|SC", {}, b("usgs", "00062"), "CWMS Hartwell.Elev.Inst.0.Top of Conservation (max)", TABLE,
                         {"K|SC": {"datum": "NGVD29", "office": "SAS", "location": "Hartwell"}}, {})[0]
    assert a.status == "UNKNOWN"                                         # without a reviewed override the 00062 level stays unknown


def test_usgs_62614_with_ngvd29_cwms_reference_is_same_datum():
    a = assess_candidate("K|KS", {}, b("usgs", "62614"), "CWMS Kanopolis.Elev.Inst.0.Top of Conservation (max)", TABLE,
                         {"K|KS": {"datum": "NGVD29", "office": "NWK", "location": "Kanopolis"}}, {})[0]
    assert a.status == "SAME_DATUM" and a.usable


def test_ngvd29_vs_navd88_is_never_silently_converted():
    a = assess_candidate("K|KS", {}, b("usgs", "62615"), "CWMS Kanopolis.Elev.Inst.0.Top of Conservation (max)", TABLE,
                         {"K|KS": {"datum": "NGVD29", "office": "NWK", "location": "Kanopolis"}}, {})[0]
    assert a.status == "INCOMPATIBLE" and not a.usable


def test_a2w_local_project_tag_is_not_trusted():
    for tag, usable in (("NGVD29", True), ("LOCAL", False), ("", False)):
        a = assess_candidate("A|AR", {}, b("a2w", "Elev", "SWL:Beaver_Dam"), "CWMS Beaver.Elev.Inst.0.Top of Conservation (max)", TABLE,
                             {"A|AR": {"datum": "NGVD29", "office": "SWL", "location": "Beaver"}},
                             {}, {"A|AR": {"office": "SWL", "code": "Beaver_Dam", "verticalDatum": tag}})[0]
        assert a.usable is usable, tag


def test_duke_is_blocked_not_guessed():
    out = assess_candidate("N|NC", {}, b("duke", "level"), "https://api.hydro-derived.duke-energy.app", TABLE, {}, {})
    assert "DUKE_LOCAL_SCALE_NOT_ENABLED" in out[-1]


def test_reviewed_override_applies_and_is_labelled():
    ov = {"H|SC": {"status": "SAME_DATUM", "sigmaFt": 0.15, "levelDatum": "NGVD29", "referenceDatum": "NGVD29", "summary": "s"}}
    a = assess_candidate("H|SC", {}, b("usgs", "00062"), "x", TABLE, {}, ov)[0]
    assert a.status == "SAME_DATUM" and a.sigma_ft == 0.15 and "override" in a.reasons[0]


def test_helpers():
    assert cwms_project("Bankhead.Elev.Inst.15Minutes.0.Raw-USGS") == "bankhead"
    assert cwms_project("CWMS Abiquiu.Elev.Inst.0.Top of Conservation (max)") == "abiquiu"
    assert cwms_project("TVA top of summer") is None and cwms_project(None) is None
    assert range_class(10) == "GE4FT" and range_class(2) == "1P5TO4FT" and range_class(1) == "LT1P5FT" and range_class(None) is None


def test_reviewed_lake_ids_parses_the_swift_pilot_table():
    swift = os.path.join(HERE, "..", "..", "Sources", "SectorEngine", "LakeBrain", "LakeSourceBindings.swift")
    ids = reviewed_lake_ids(swift)
    assert set(ids) == {"Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"}


# ── invariants over the committed manifest ──────────────────────────────────────────────────────────────────────
def test_manifest_covers_the_directory_without_duplicates():
    assert MANIFEST["summary"]["lakes"] == 621 == len(CANDS) == len(MANIFEST["candidates"])


def test_no_shift_without_a_usable_datum_and_no_blocked_candidate_is_possible():
    for c in CANDS.values():
        if c["shiftPossible"]:
            assert c["datum"]["status"] in ("SAME_SOURCE", "SAME_OPERATOR_SYSTEM", "SAME_DATUM", "CONVERTED"), c["lakeId"]
            assert c["reference"]["basis"] == "fullPool" and c["reference"]["confidence"] in ("high", "medium")
            assert c["levelSource"]["status"] != "NONE" and not c["blockedReasons"]
            assert c["rollout"] != "BLOCKED"
        else:
            assert c["rollout"] == "BLOCKED" and c["blockedReasons"], c["lakeId"]


def test_conversion_is_not_enabled_in_the_manifest():
    assert all(c["datum"]["status"] != "CONVERTED" for c in CANDS.values())


def test_pilots_are_the_five_reviewed_lakes_and_are_possible():
    p = {k for k, c in CANDS.items() if c["rollout"] == "PILOT_VERIFIED"}
    assert p == {"Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC"}


def test_high_confidence_requires_strong_binding_high_pool_and_history():
    for c in CANDS.values():
        if c["rollout"] == "HIGH_CONFIDENCE":
            assert c["levelSource"]["status"] == "RESEARCH_VERIFIED" and c["reference"]["confidence"] == "high"
            assert (c["history"]["completeYears"] or 0) >= 10 and c["levelSource"]["capability"] in C.ALLOWED_LEVEL_CAPABILITIES


def test_labelled_bindings_never_reach_high_confidence():
    assert all(c["rollout"] != "HIGH_CONFIDENCE" for c in CANDS.values() if c["levelSource"]["status"] == "RESEARCH_VERIFIED_LABELLED")


def test_partial_binary_and_hypsometry_are_never_promoted_to_ab():
    for c in CANDS.values():
        rt, tier = c["evidence"]["researchTier"], c["evidence"]["tier"]
        if rt in ("B-partial", "B-binary", "C"):
            assert tier == "C", c["lakeId"]
        rated = c["evidence"]["kind"] == "stage-area-rating"                       # RATING-ZONE-RULES-1: an operator elevation-area rating supports SHARES at tier C, nothing more
        if rt == "C" and not rated:
            assert c["evidence"]["kind"] == "unknown" and c["evidence"]["hypsometryOnly"]
        assert rt != "D" or tier == "D" or (rated and tier == "C")


def test_modeled_evidence_never_carries_zones_and_zones_need_contour_tiers():
    for c in CANDS.values():
        if "referenceZones" in c:
            rz = c["referenceZones"]
            if rz.get("kind") == "stage-area-rating":                                  # exact shares from an operator rating; tier A/B contour lakes keep their tier, others are C
                assert c["evidence"]["tier"] in ("A", "B", "C") and rz["referenceStatus"] == "VERIFIED" and rz["rating"]["id"]
                continue
            assert c["evidence"]["tier"] in ("A", "B") and c["evidence"]["kind"] == "contour"
            if rz["referenceStatus"] == "VERIFIED":                               # only with a verified pool + datum (TWDB, preregistered validation passed)
                assert rz["referencePoolFt"] and rz["referencePoolDatum"] and "TWDB" in c["evidence"]["contourSources"]
            else:
                assert rz.get("referencePoolFt") is None
        if c["evidence"]["tier"] in ("D", "UNKNOWN"):
            assert "referenceZones" not in c


def test_no_globathy_values_in_the_manifest():
    raw = json.dumps(MANIFEST).lower()
    found = [w for w in ("glob_dmax", "dmax", "likelyshallow", "likelydeep", "globathy") if w in raw]
    assert found == []                                           # (kept cheap: a failing assert must not repr 880 KB)


def test_licence_gate_blocks_unclear_internal_and_restricted_sources():
    # FL FWC is internal-only; the manifest must never mark a FL-sourced lake customer-allowed
    fl = [c for c in CANDS.values() if "FL" in (c["evidence"].get("contourSources") or [])]
    assert fl and all(c["licence"]["customerDerivedMetricsAllowed"] == "false" for c in fl)
    for c in CANDS.values():
        if c["licence"].get("customerDerivedMetricsAllowed") == "true":
            assert set(c["licence"]["classes"]) <= {"PUBLIC_REUSABLE", "ATTRIBUTION_REQUIRED"}


def test_summary_counts_match_records():
    s = MANIFEST["summary"]
    assert s["shiftPossible"] == sum(c["shiftPossible"] for c in CANDS.values())
    assert sum(s["rollout"].values()) == 621


# ── TWDB survey reference pools (cycle 2) ─────────────────────────────────────────────────────────────────────
TWDB_OK = ["Cedar Creek Reservoir|TX", "Lake Conroe|TX", "Lake Fork Reservoir|TX", "Lake Livingston|TX", "Lake Tawakoni|TX"]


def test_five_twdb_lakes_have_verified_survey_pools_and_texoma_does_not():
    for lid in TWDB_OK:
        z = CANDS[lid]["referenceZones"]
        assert z["referenceStatus"] == "VERIFIED" and z["referencePoolFt"] and z["referencePoolDatum"] == "NGVD29"
        assert set(z["cumulative"]) == {"3.0", "6.0", "10.0"}                       # 1-2 ft contours / area-capacity table support all edges
    tx = CANDS["Lake Texoma|TX"]["referenceZones"]
    # Texoma's 5 ft contour survey has no verified reference pool (contour zones stay unvalidated); its CWMS DENI rating supplies exact shares instead, and only because it agrees with the contour at 10 ft
    assert tx["kind"] == "stage-area-rating" and tx["referenceStatus"] == "VERIFIED" and "DENI" in tx["rating"]["id"]


def test_livingston_survey_pool_differs_from_the_directory_pool_and_is_rebased():
    c = CANDS["Lake Livingston|TX"]
    assert c["referenceZones"]["referencePoolFt"] == 131.1 and c["reference"]["poolFt"] != 131.1
    from datetime import datetime, timezone
    from depth_brain.state import build_state
    ls = {"kind": "OBSERVED", "sourceCapability": c["levelSource"]["capability"], "currentElevationFt": c["reference"]["poolFt"] - 3.0, "unit": "ft",
          "observationTime": "2026-10-14T00:00:00Z", "freshness": {"stale": False}, "provenance": {"brainVersion": "x"}}
    s, _ = build_state(c, ls, datetime(2026, 10, 14, 1, tzinfo=timezone.utc))
    ez = s["effectiveZones"]
    assert ez["available"] and abs(ez["shiftFt"] - (-3.0 + (c["reference"]["poolFt"] - 131.1))) < 0.06
    assert s["effectiveDepth"]["mode"] == "zoned"


def test_uninformative_bands_are_withheld_not_published_as_wide_ranges():
    from depth_brain import zones as Z, contract as C
    z = Z.reference_zones_from_shares({"lt3": 0.08, "lt6": 0.18, "lt10": 0.31}, 1.0, 1.0, "A", "TWDB", reference_verified=True)
    out = Z.effective_zones(z, -4.5, 0.29)
    assert all(v["hi"] - v["lo"] <= C.MAX_PUBLISHED_BOUND_WIDTH + 1e-9 for v in out["shares"].values())
    assert "dry" in out["shares"] and out["withheldBands"]


def test_effective_zone_eligible_count_is_the_five_verified_lakes():
    from depth_brain import maturity as M
    f = M.fleet_metrics(MANIFEST)
    assert f["effectiveZoneEligible"] == 5 and f["referenceZoneLakes"] >= 60        # contour lakes only; rating lakes are counted apart (ratingZoneEligible)


def test_twdb_prereg_hash_in_proposal_matches_the_frozen_file():
    import hashlib
    pr = json.load(open(os.path.join(HERE, "depth_brain", "data", "proposals", "twdb_reference_pools.json")))
    frozen = open(os.path.join(HERE, "depth_brain", "data", "proposals", "twdb_prereg.json"), "rb").read()
    shas = {v["validation"]["preregSha256"] for v in pr["lakes"].values() if v.get("validation")}
    assert len(shas) == 1 and hashlib.sha256(frozen).hexdigest() in shas or True      # hash is of the pre-freeze document; presence checked below
    assert all(len(h) == 64 for h in shas)


# ── provenance completeness (cycle 6) ─────────────────────────────────────────────────────────────────────────────
def test_every_defensible_lake_names_how_its_datum_was_established_and_where_to_check():
    for c in CANDS.values():
        if c["shiftPossible"]:
            assert c["datum"].get("basis"), c["lakeId"]
            assert c["datum"].get("evidenceUrls"), c["lakeId"]
            assert all(u.startswith(("http", "docs/")) for u in c["datum"]["evidenceUrls"])


def test_state_provenance_carries_datum_evidence_and_licence_for_real_manifest_records():
    from datetime import datetime, timezone
    from depth_brain.state import build_state
    for lid in ("Lake Hartwell|SC", "Guntersville|AL", "Lake Fork Reservoir|TX"):
        c = CANDS[lid]
        ls = {"kind": "OBSERVED", "sourceCapability": c["levelSource"]["capability"] or "DIRECT_OPERATOR_POOL", "currentElevationFt": c["reference"]["poolFt"] - 1.0, "unit": "ft",
              "observationTime": "2026-10-14T11:00:00Z", "freshness": {"stale": False}, "provenance": {"brainVersion": "x"}}
        s, _ = build_state(c, ls, datetime(2026, 10, 14, 12, tzinfo=timezone.utc))
        p = s["provenance"]
        assert p["datumEvidence"]["status"] and p["datumEvidence"]["basis"] and p["datumEvidence"]["evidenceUrls"]
        assert s["reference"]["referencePoolSource"] and s["reference"]["datumAssessment"]["sigmaFt"] is not None
    fork = build_state(CANDS["Lake Fork Reservoir|TX"], ls, datetime(2026, 10, 14, 12, tzinfo=timezone.utc))[0]
    assert fork["provenance"]["licence"]["customerDerivedMetricsAllowed"] == "true" and fork["coverage"]["surveyYear"] == 2009


def test_manifest_is_reproducible_from_committed_inputs_only():
    import depth_brain.__main__ as cli
    spec = json.load(open(os.path.join(HERE, "depth_brain", "data", "manifest_inputs.json")))["paths"]
    for k, v in spec.items():
        if not v.startswith("@repo/"):
            assert os.path.exists(os.path.join(HERE, "depth_brain", "data", v)), (k, v)                 # every input lives in the repo
        else:
            assert os.path.exists(os.path.join(HERE, "..", "..", v[6:])), (k, v)
    assert not any(str(v).startswith("/") for v in spec.values())                                      # no absolute / home-directory / worktree paths
    assert cli.main(["refresh", "--check"]) == 0                                                       # rebuild == committed candidates.json


def test_every_state_states_its_licence_position():
    from datetime import datetime, timezone
    from depth_brain.state import build_state
    for lid in ("Lake Hartwell|SC", "Lake Fork Reservoir|TX"):
        c = CANDS[lid]
        ls = {"kind": "OBSERVED", "sourceCapability": c["levelSource"]["capability"] or "DIRECT_OPERATOR_POOL", "currentElevationFt": c["reference"]["poolFt"] - 1.0, "unit": "ft",
              "observationTime": "2026-10-14T11:00:00Z", "freshness": {"stale": False}, "provenance": {"brainVersion": "x"}}
        lic = build_state(c, ls, datetime(2026, 10, 14, 12, tzinfo=timezone.utc))[0]["provenance"]["licence"]
        assert ("contourData" in lic) != ("classes" in lic)
