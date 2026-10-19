"""Species water-domain metadata V1: registry contract, 29-species backfill, projection equality, and no score impact."""
import copy
import json
import os
import sys

import pytest

import water_domain as W
import biological_brain as BB

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SCHEMA = os.path.join(REPO, "contracts", "schemas", "registry-species-water-domains.schema.json")
sys.path.insert(0, os.path.join(REPO, "tools", "architecture"))
from jsonschema_lite import validate  # noqa: E402

MATRIX = os.path.join(REPO, "docs", "brains", "biological-adoption", "BIOLOGICAL_SPECIES_COVERAGE_MATRIX.json")


def doc():
    return json.load(open(W.CANONICAL_PATH))


def test_registry_validates_against_schema_and_rules():
    assert validate(doc(), json.load(open(SCHEMA))) == []
    assert W.validate_registry(doc()) == []


def test_covers_exactly_the_29_canonical_species_once():
    ids = [s["speciesId"] for s in doc()["species"]]
    assert len(ids) == 29 and ids == sorted(set(ids))
    assert ids == sorted(s["speciesId"] for s in json.load(open(MATRIX))["species"])


def test_packaged_projection_equals_registry_and_is_not_stale():
    from water_domain_registry import REGISTRY
    assert REGISTRY == doc()
    import gen_water_domain_projection as G
    assert G.render() == open(G.OUT).read()


def test_only_allowed_domains_no_dupes_canonical_order():
    for s in doc()["species"]:
        d = s["waterDomains"]
        if d is not None:
            assert d and set(d) <= set(W.DOMAINS) and len(set(d)) == len(d) and d == [x for x in W.DOMAINS if x in d]


def test_diadromous_is_not_a_water_domain():
    assert "DIADROMOUS" not in W.DOMAINS
    d = doc(); d["species"][0]["waterDomains"] = ["DIADROMOUS"]
    assert W.validate_registry(d) and validate(d, json.load(open(SCHEMA)))


@pytest.mark.parametrize("mutate", [
    lambda e: e.update(waterDomains=[]),
    lambda e: e.update(waterDomains=["FRESHWATER", "FRESHWATER"]),
    lambda e: e.update(waterDomains=["MARINE", "FRESHWATER"]),
    lambda e: e.update(waterDomains=["SALTWATER"]),
    lambda e: e.update(waterDomains=None),                      # ASSESSED must not be null
    lambda e: e["assessment"].update(sources=[]),
])
def test_invalid_assessed_entries_rejected(mutate):
    d = doc(); mutate(d["species"][0])
    assert W.validate_registry(d)


def test_unknown_is_null_never_defaulted_to_freshwater():
    by = {s["speciesId"]: s for s in doc()["species"]}
    u = by["suckers_redhorse_carpsuckers_group"]
    assert u["waterDomains"] is None and u["assessment"]["status"] == "UNKNOWN"
    d = doc(); d["species"][0]["assessment"]["status"] = "UNKNOWN"
    assert W.validate_registry(d)                               # UNKNOWN with domains present is rejected
    assert W.project("suckers_redhorse_carpsuckers_group") == {"waterDomainStatus": "UNKNOWN"}


def test_multi_domain_species():
    by = {s["speciesId"]: s["waterDomains"] for s in doc()["species"]}
    assert by["bowfin"] == ["FRESHWATER"]
    assert by["common_carp"] == ["FRESHWATER", "BRACKISH"]
    assert by["striped_mullet"] == ["FRESHWATER", "BRACKISH", "MARINE"] and by["american_shad"] == ["FRESHWATER", "BRACKISH", "MARINE"]


def test_unregistered_species_projects_nothing():
    assert W.project("example_group") == {}


def test_audit_grouping_agrees_with_registry():
    import species_audit as SA
    by = {s["speciesId"]: s["waterDomains"] for s in doc()["species"]}
    for sid, d in by.items():
        if d is None:
            continue
        g = SA.habitat_for(sid)["primaryGroup"]
        assert ("MARINE" in d) if g == "SALTWATER" else ("FRESHWATER" in d), sid


def test_summary_projection_adds_only_water_fields():
    import fish_support as S
    b = S.make_bundle()
    ids = list(b.profiles)
    prof = b.profiles[ids[0]]
    base = BB.species_summary(prof, b, "gs://x", "2026-10-19T00:00:00Z")
    forced = copy.deepcopy(prof); forced["speciesId"] = "common_carp"
    s2 = BB.species_summary(forced, b, "gs://x", "2026-10-19T00:00:00Z")
    assert s2["waterDomains"] == ["FRESHWATER", "BRACKISH"] and s2["waterDomainStatus"] == "ASSESSED"
    assert "waterDomains" not in base or base["speciesId"] in W.load()
    for k in ("knowledge", "assessment", "researchMaturity"):
        assert s2[k] == base[k]


def test_no_score_impact_scorer_never_reads_water_domains_and_result_is_identical():
    import datetime as dt
    import inspect
    from sector_brain_platform import scoring
    from sector_brain_platform import score_biological
    src = inspect.getsource(scoring)
    assert "waterDomain" not in src and "water_domain" not in src
    now = dt.datetime(2026, 10, 19, tzinfo=dt.timezone.utc)
    cov = json.load(open(MATRIX))["species"]
    sp = {s["speciesId"]: {"assessment": "ASSESSED", "researchMaturity": "RESEARCH", "contradictionCount": 1,
                           "knowledge": {"overallRounded": round(s["speciesV2Score"] or 0)}} for s in cov}
    reg = {"responsibilities": {"speciesKnowledge": {"speciesCount": 29, "assessedCount": 29, "notAssessedCount": 0},
                                "biologicalState": {"status": "IN_PROGRESS", "validation": "PARTIAL"}}}
    facts = lambda species: {"registry": reg, "species": species, "intelligenceRegistry": {}}
    before = score_biological(facts(sp), now)
    sp2 = copy.deepcopy(sp)
    for sid, row in sp2.items():
        row.update(W.project(sid))
    assert any("waterDomains" in r for r in sp2.values())
    assert score_biological(facts(sp2), now) == before
