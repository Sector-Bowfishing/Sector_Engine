import copy
import json
import os

import pytest

from brain_cert_kit import exit_gate as g

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
BRAINS = ("wind", "fish", "water-clarity")


def _full(brain_id="b"):
    return {"standard": g.STANDARD, "brainId": brain_id, "checks": {cid: {"status": "PASS", "evidenceRef": f"ev/{cid}", "mode": mode} for cid, _s, mode, _c in g.CHECKS}}


def test_check_definitions_are_unique_and_cover_the_required_gate():
    assert len(g.CHECK_IDS) == len(set(g.CHECK_IDS)) == 16
    assert len({c[1] for c in g.CHECKS}) == 16
    assert {c[2] for c in g.CHECKS} == {g.OFFLINE, g.LIVE}
    # exit evidence F (write denial) and rollback are LIVE-only: they cannot be claimed from a unit test
    modes = {c[1]: c[2] for c in g.CHECKS}
    assert modes["write_denial"] == g.LIVE and modes["rollback"] == g.LIVE and modes["atomic_write"] == g.LIVE


def test_complete_record_passes_and_every_single_defect_blocks():
    assert g.evaluate(_full(), "b")["verdict"] == "PASS"
    for cid in g.CHECK_IDS:
        e = _full(); del e["checks"][cid]
        assert g.evaluate(e, "b")["verdict"] == "BLOCKED" and cid in g.evaluate(e, "b")["missing"]
        e = _full(); e["checks"][cid]["status"] = "FAIL"
        assert g.evaluate(e, "b")["verdict"] == "BLOCKED"
        e = _full(); e["checks"][cid]["evidenceRef"] = " "
        assert g.evaluate(e, "b")["verdict"] == "BLOCKED"
    for mutate in (lambda e: e.update(brainId="other"), lambda e: e.update(standard="x"), lambda e: e["checks"].update(X99={"status": "PASS", "evidenceRef": "r"}),
                   lambda e: e["checks"]["X07"].update(mode="OFFLINE")):
        e = _full(); mutate(e)
        assert g.evaluate(e, "b")["verdict"] == "BLOCKED"
    assert g.evaluate(None)["verdict"] == "BLOCKED" and g.evaluate({})["verdict"] == "BLOCKED"


@pytest.mark.parametrize("brain", BRAINS)
def test_current_brains_are_shadow_and_the_gate_is_not_yet_claimable(brain):
    d = os.path.join(REPO, "brains", brain)
    assert g.cutover_guard(d)["gate"] == "NOT_REQUIRED_WHILE_SHADOW"
    assert not os.path.exists(os.path.join(d, "contracts", "production-exit-evidence.json")), "no exit evidence may exist before a live Publisher"


def _clone(tmp_path, brain, status, evidence=None):
    d = tmp_path / brain
    (d / "contracts").mkdir(parents=True)
    with open(os.path.join(REPO, "brains", brain, "brain.json"), encoding="utf-8") as f:
        b = json.load(f)
    b["publisherRequired"]["cutoverStatus"] = status
    (d / "brain.json").write_text(json.dumps(b))
    if evidence is not None:
        (d / "contracts" / "production-exit-evidence.json").write_text(json.dumps(evidence))
    return str(d), b["brainId"]


@pytest.mark.parametrize("brain", BRAINS)
def test_cutover_complete_is_refused_while_a_legacy_write_site_remains_active(tmp_path, brain):
    """Even a fully PASSing evidence record cannot complete a cutover while the Brain still carries a direct production write site (Water Clarity: the whole-node
    /brains/water-clarity + /health/brains/water-clarity replacement). The guard reads the runtime source, not a claim."""
    import shutil
    d, bid = _clone(tmp_path, brain, "CUTOVER_COMPLETE", _full("placeholder"))
    ev = _full(bid)
    (tmp_path / brain / "contracts" / "production-exit-evidence.json").write_text(json.dumps(ev))
    shutil.copytree(os.path.join(REPO, "brains", brain, "runtime"), os.path.join(d, "runtime"))
    left = g.legacy_write_sites(d, bid)
    assert left["writeSites"], f"{brain} is expected to still hold its legacy direct write site"
    with pytest.raises(AssertionError, match="legacy writer remains active"):
        g.cutover_guard(d)
    shutil.rmtree(os.path.join(d, "runtime"))
    os.makedirs(os.path.join(d, "runtime"))                                    # the retired state: no runtime write site at all
    assert g.cutover_guard(d)["gate"] == "PASS"


def test_water_clarity_whole_node_legacy_write_keys_are_named_by_the_guard():
    left = g.legacy_write_sites(os.path.join(REPO, "brains", "water-clarity"), "water-clarity")
    assert left["wholeNodeKeys"], "run.py builds the whole-node keys /brains/water-clarity and /health/brains/water-clarity"
    assert {s[2] for s in left["writeSites"]} == {"rtdb.update"} and len(left["writeSites"]) == 2


def test_the_repo_coverage_matrix_names_real_tests_and_keeps_live_only_checks_live_only():
    rs = g.repo_status()
    assert set(rs) == set(g.CHECK_IDS)
    assert rs["X16"]["tier"] == "LIVE_ONLY" and all(rs[c]["liveStillRequired"] for c in g.CHECK_IDS if g.REPO_COVERAGE[c][0] != "OFFLINE")
    assert {c for c in g.CHECK_IDS if rs[c]["tier"] == "OFFLINE"} == {"X01", "X02", "X03", "X04", "X05", "X06", "X14"}
    for cid, tests in ((c, rs[c]["tests"]) for c in g.CHECK_IDS):
        for ref in tests:
            rel, _, name = ref.partition("::")
            path = os.path.join(REPO, "tools", "brain_certification", rel) if rel.startswith(("brain_cert_kit", "tests")) else os.path.join(REPO, rel)
            assert os.path.isfile(path), (cid, rel)
            assert f"def {name}" in open(path, encoding="utf-8").read(), (cid, ref)


@pytest.mark.parametrize("brain", BRAINS)
def test_cutover_complete_is_refused_without_a_passing_exit_record(tmp_path, brain):
    d, bid = _clone(tmp_path / "a", brain, "CUTOVER_COMPLETE")
    with pytest.raises(AssertionError):
        g.cutover_guard(d)
    partial = _full(bid); partial["checks"]["X13"]["status"] = "NOT_RUN"
    d, _ = _clone(tmp_path / "b", brain, "CUTOVER_COMPLETE", partial)
    with pytest.raises(AssertionError):
        g.cutover_guard(d)
    d, _ = _clone(tmp_path / "c", brain, "CUTOVER_COMPLETE", _full("someone-else"))
    with pytest.raises(AssertionError):
        g.cutover_guard(d)
    d, _ = _clone(tmp_path / "d", brain, "CUTOVER_COMPLETE", _full(bid))
    assert g.cutover_guard(d)["gate"] == "PASS"
    d, _ = _clone(tmp_path / "e", brain, "BOGUS")
    with pytest.raises(AssertionError):
        g.cutover_guard(d)
