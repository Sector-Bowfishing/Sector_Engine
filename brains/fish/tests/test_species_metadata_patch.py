"""Field-level species identity-metadata patch: smallest write, refuses everything else, ownership-checked, idempotent, rollback-able. Synthetic data only."""
import copy

import pytest

import brain_platform as bp
import species_metadata_patch as P

SPECIES = {
    "bowfin": {"speciesId": "bowfin", "assessment": "ASSESSED", "knowledge": {"overallExact": 4.9}, "responseBands": {"generatedAt": "T1", "bands": [1]},
               "updatedAt": "T1", "waterDomains": ["FRESHWATER"], "waterDomainStatus": "ASSESSED"},
    "striped_mullet": {"speciesId": "striped_mullet", "assessment": "ASSESSED", "knowledge": {"overallExact": 0.2}, "updatedAt": "T1",
                       "waterDomains": ["FRESHWATER", "BRACKISH", "MARINE"], "waterDomainStatus": "ASSESSED"},
    "group_row": {"speciesId": "group_row", "assessment": "NOT_ASSESSED", "updatedAt": "T1", "waterDomainStatus": "UNKNOWN"},     # UNKNOWN: waterDomains absent
}
WATER = ("waterDomains", "waterDomainStatus")


def desired():
    return {f"/species/{k}": copy.deepcopy(v) for k, v in SPECIES.items()}


def live():
    """Today's production: same knowledge, no water fields, older timestamps."""
    out = {}
    for k, v in SPECIES.items():
        n = {f: x for f, x in copy.deepcopy(v).items() if f not in WATER}
        n["updatedAt"] = "T0"
        if "responseBands" in n:
            n["responseBands"]["generatedAt"] = "T0"
        out[k] = n
    return out


def test_patch_contains_only_the_two_allow_listed_fields_and_skips_timestamps():
    patch, rep = P.plan_patch(live(), desired())
    assert set(patch) == {"/species/bowfin/waterDomains", "/species/bowfin/waterDomainStatus", "/species/striped_mullet/waterDomains",
                          "/species/striped_mullet/waterDomainStatus", "/species/group_row/waterDomainStatus"}
    assert patch["/species/group_row/waterDomainStatus"] == "UNKNOWN" and "/species/group_row/waterDomains" not in patch      # unknown stays unknown
    assert patch["/species/striped_mullet/waterDomains"] == ["FRESHWATER", "BRACKISH", "MARINE"]          # multi-domain keeps every value
    assert rep["paths"] == 5 and rep["speciesChanged"] == 3 and rep["speciesChecked"] == 3
    assert not any(p.endswith(("updatedAt", "generatedAt", "knowledge", "overallExact")) for p in patch)


def test_applied_through_the_ownership_checked_store_only_those_paths_change():
    tree = {"species": live(), "scores": {"biological-state": {"value": 5.1}}, "brains": {"biological-state": {"researchVersion": "2026-10-17.1"}},
            "health": {"brains": {"biological-state": {"status": "HEALTHY"}}}}
    before = copy.deepcopy(tree)
    store = bp.DryRunStore(tree, brain_id="biological-state")                    # same ownership rules as the live client
    patch, _ = P.plan_patch(store.get("species"), desired())
    store.update(patch)
    assert store.writes == 1                                                      # one atomic multi-path update
    assert tree["scores"] == before["scores"] and tree["brains"] == before["brains"] and tree["health"] == before["health"]
    for sid, node in tree["species"].items():
        rest = {k: v for k, v in node.items() if k not in WATER}
        assert rest == before["species"][sid]                                     # every pre-existing field intact (timestamps included)
    assert tree["species"]["bowfin"]["waterDomains"] == ["FRESHWATER"]
    assert P.verify_readback(tree["species"], patch) == []


def test_idempotent_second_plan_is_empty():
    tree = {"species": live()}
    store = bp.DryRunStore(tree, brain_id="biological-state")
    store.update(P.plan_patch(tree["species"], desired())[0])
    patch2, rep2 = P.plan_patch(tree["species"], desired())
    assert patch2 == {} and rep2["paths"] == 0


def test_other_brain_cannot_make_this_write():
    patch, _ = P.plan_patch(live(), desired())
    other = bp.DryRunStore({"species": live()}, brain_id="wind")
    with pytest.raises(PermissionError):
        other.update(patch)


@pytest.mark.parametrize("mutate", [
    lambda d: d["/species/bowfin"]["knowledge"].update(overallExact=5.0),         # a score change
    lambda d: d["/species/bowfin"].update(researchVersion="2026-11-01.1"),         # a new field
    lambda d: d["/species/bowfin"].pop("assessment"),                              # a removed field
    lambda d: d["/species/bowfin"].update(waterDomainStatus="ASSESSED", assessment="NOT_ASSESSED"),
])
def test_refuses_any_difference_beyond_the_allow_list(mutate):
    d = desired(); mutate(d)
    with pytest.raises(P.PatchRefused):
        P.plan_patch(live(), d)


def test_refuses_to_add_or_remove_species():
    d = desired(); d["/species/new_fish"] = {"speciesId": "new_fish"}
    with pytest.raises(P.PatchRefused):
        P.plan_patch(live(), d)
    d = desired(); d.pop("/species/group_row")
    with pytest.raises(P.PatchRefused):
        P.plan_patch(live(), d)
    with pytest.raises(P.PatchRefused):
        P.plan_patch(live(), {})


def test_removed_classification_deletes_only_that_field():
    lv = live(); lv["bowfin"]["waterDomains"] = ["FRESHWATER", "BRACKISH"]; lv["bowfin"]["waterDomainStatus"] = "ASSESSED"
    d = desired(); d["/species/bowfin"].pop("waterDomains"); d["/species/bowfin"]["waterDomainStatus"] = "UNKNOWN"
    patch, _ = P.plan_patch(lv, d)
    assert patch["/species/bowfin/waterDomains"] is None and patch["/species/bowfin/waterDomainStatus"] == "UNKNOWN"


def test_rollback_restores_the_pre_patch_tree():
    tree = {"species": live()}
    before = copy.deepcopy(tree)
    store = bp.DryRunStore(tree, brain_id="biological-state")
    patch, _ = P.plan_patch(tree["species"], desired())
    store.update(patch)
    store.update({p: None for p in patch})                                         # the documented rollback: delete the added child paths
    assert tree == before


def test_run_exposes_plan_by_default_and_write_only_with_apply():
    import run
    src = open(run.__file__).read()
    assert "--patch-species-metadata" in src and 'if a.apply and patch' in src


def test_revert_patch_deletes_only_the_allow_listed_fields():
    tree = {"species": live()}
    store = bp.DryRunStore(tree, brain_id="biological-state")
    store.update(P.plan_patch(tree["species"], desired())[0])
    rb = P.revert_patch(tree["species"])
    assert set(rb) == {f"/species/{s}/{f}" for s, n in tree["species"].items() for f in P.PATCHABLE if f in n} and all(v is None for v in rb.values())
    store.update(rb)
    assert tree == {"species": live()}
    assert P.revert_patch(tree["species"]) == {}
