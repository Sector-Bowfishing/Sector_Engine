"""The committed dam catalog is exactly what build_catalog produces from repository evidence, every dam lake has a coverage state with a reason,
nothing is bound without evidence, and the candidate release covers the committed files. Offline."""
import json
import os

from generation_research import build_catalog as B, release as R

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", ".."))
KNOW = os.path.join(REPO, "brains", "generation", "runtime", "knowledge")


def committed():
    return json.load(open(os.path.join(KNOW, "dams.json")))


def test_committed_catalog_equals_a_rebuild():
    assert B.build(REPO) == committed()


def test_counts_cover_every_directory_lake():
    c = committed()
    assert c["directoryLakeCount"] == 621 and c["damLakeCount"] + c["noDamLakeCount"] == 621 and c["damLakeCount"] == len(c["dams"]) == 401
    assert sum(c["counts"]["byCoverage"].values()) == 401 and set(c["counts"]["byCoverage"]) <= set(B.COVERAGE)


def test_every_dam_lake_states_a_reason_and_only_evidenced_sources_are_bound():
    for d in committed()["dams"]:
        assert d["coverage"] in B.COVERAGE and d["reason"], d["lakeId"]
        for s in d["sources"]:
            if s["status"] == "BOUND":
                assert s.get("evidence"), (d["lakeId"], s)
                assert s["provider"] in ("tva", "swpa") and (s.get("locationId") or s.get("project"))
            else:
                assert s["status"] == "DISCOVERY_PENDING" and s.get("reason"), (d["lakeId"], s)


def test_tva_bound_lakes_are_exactly_the_evidenced_records():
    recs = json.load(open(os.path.join(os.path.dirname(B.__file__), "records", "tva_locations.json")))["locations"]
    bound = {d["lakeId"]: s["locationId"] for d in committed()["dams"] for s in d["sources"] if s["provider"] == "tva" and s["status"] == "BOUND"}
    assert bound == {r["lakeId"]: r["locationId"] for r in recs}


def test_operator_groups():
    assert B.group_of("TVA (Kentucky Dam)", "x", {}) == "TVA" and B.group_of("USACE Nashville (Wolf Creek)", "x", {}) == "TVA_CUMBERLAND"
    assert B.group_of("USACE Tulsa", "Keystone Lake|OK", {"Keystone Lake|OK": {}}) == "SWPA_USACE"
    assert B.group_of("USBR (Hoover Dam)", "x", {}) == "USBR" and B.group_of("Alabama Power", "x", {}) == "UTILITY_OR_POWER_AUTHORITY"
    assert B.group_of("Baltimore City DPW", "x", {}) == "OTHER_OPERATOR"


def test_the_candidate_release_matches_the_committed_files_and_is_not_approved():
    rel = json.load(open(os.path.join(KNOW, "knowledge-release.json")))
    again = R.manifest(rel["releaseId"], KNOW)
    assert again == rel and rel["approval"]["status"] == "NOT_RECORDED"
