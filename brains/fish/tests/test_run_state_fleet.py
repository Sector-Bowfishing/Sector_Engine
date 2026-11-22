"""run_state.py: the pilot path is byte-identical to origin/main (golden), and the fleet mode is OFF unless FISH_FLEET_RUNNER=1.

Every fixture is SYNTHETIC (run_state_fixtures.py). Nothing here reads a live service."""
import json
import os

import pytest

import run_state
import run_state_fixtures as F

GOLDEN = json.load(open(F.GOLDEN, encoding="utf-8"))
SCRIPT = F.RUN_STATE


# ------------------------------------------------------------------------------------------------ pilot golden (switch OFF and ON)
@pytest.mark.parametrize("env", [{}, {"FISH_FLEET_RUNNER": "0"}, {"FISH_FLEET_RUNNER": "1"}], ids=["unset", "off", "on"])
@pytest.mark.parametrize("lake", F.PILOTS)
def test_pilot_snapshot_run_is_byte_identical_to_pre_fleet_main(tmp_path, lake, env):
    got = F.run_pilot(SCRIPT, lake, str(tmp_path), env)
    assert got == GOLDEN["runs"][lake]


@pytest.mark.parametrize("env", [{}, {"FISH_FLEET_RUNNER": "1"}], ids=["unset", "on"])
@pytest.mark.parametrize("lake", F.PILOTS)
def test_pilot_live_run_is_byte_identical_to_pre_fleet_main(tmp_path, lake, env):
    got = F.run_pilot_live(SCRIPT, lake, str(tmp_path), F.PILOT_KEYS[lake], env)
    assert got == GOLDEN["liveRuns"][lake]


def test_golden_exercises_an_evaluated_species():
    s = json.loads(GOLDEN["liveRuns"]["Guntersville|AL"]["file"])
    assert s["summary"]["speciesWithAnyResponseBand"] == 1                                   # not a vacuous golden


def test_non_pilot_lake_is_still_refused_in_pilot_mode(tmp_path):
    p = F.stage(str(tmp_path))
    with pytest.raises(SystemExit, match="not a pilot lake"):
        run_state.main(["--lake", "Weiss|AL", "--rules", p["rules"], "--snapshot", p["snapshot"], "--now", F.NOW, "--out", str(tmp_path / "o")])


def test_fleet_only_flags_are_rejected_in_pilot_mode(tmp_path):
    p = F.stage(str(tmp_path))
    with pytest.raises(SystemExit):
        run_state.main(["--lake", "Guntersville|AL", "--rules", p["rules"], "--snapshot", p["snapshot"], "--directory", "x.json", "--out", str(tmp_path / "o")])


# ------------------------------------------------------------------------------------------------ the switch
@pytest.mark.parametrize("value", [None, "", "0", "true", "yes", "on", "ON", " 1", "2"])
def test_fleet_switch_defaults_off_and_only_exact_1_turns_it_on(value):
    env = {} if value is None else {"FISH_FLEET_RUNNER": value}
    assert run_state.fleet_enabled(env) is False
    assert run_state.fleet_enabled({"FISH_FLEET_RUNNER": "1"}) is True


def directory(tmp_path, ids):
    d = {"lakes": [{"id": i, "lat": 34.5, "lon": -86.5} for i in ids]}
    p = tmp_path / "lakes.json"
    p.write_text(json.dumps(d))
    return str(p)


def stage_inputs(tmp_path, keys, evidence_class="sensor"):
    d = tmp_path / "inputs"
    d.mkdir(exist_ok=True)
    for k in keys:
        (d / f"{k}.snapshot.json").write_text(json.dumps(F.snapshot(evidence_class)))
        (d / f"{k}.presence.json").write_text(json.dumps(F.PRESENCE))
    return str(d)


def fleet_args(tmp_path, ids, *extra):
    rules = F.write_rules(str(tmp_path / "rules"))
    return ["--fleet", "--directory", directory(tmp_path, ids), "--rules", rules, "--now", F.NOW, "--out", str(tmp_path / "out"), *extra]


def test_fleet_is_refused_when_the_switch_is_off(tmp_path, monkeypatch):
    monkeypatch.delenv("FISH_FLEET_RUNNER", raising=False)
    with pytest.raises(SystemExit, match="fleet mode is OFF"):
        run_state.main(fleet_args(tmp_path, ["Guntersville|AL"], "--inputs-dir", stage_inputs(tmp_path, ["Guntersville_AL"])))
    assert not (tmp_path / "out").exists()                                                   # nothing written


def test_fleet_refuses_pilot_only_flags(tmp_path, monkeypatch):
    monkeypatch.setenv("FISH_FLEET_RUNNER", "1")
    with pytest.raises(SystemExit, match="do not apply"):
        run_state.main(fleet_args(tmp_path, ["Guntersville|AL"], "--lake", "Guntersville|AL", "--inputs-dir", str(tmp_path)))


# ------------------------------------------------------------------------------------------------ fleet behaviour (switch ON)
def run_fleet(tmp_path, monkeypatch, ids, keys, *extra):
    monkeypatch.setenv("FISH_FLEET_RUNNER", "1")
    assert run_state.main(fleet_args(tmp_path, ids, "--inputs-dir", stage_inputs(tmp_path, keys), *extra)) == 0
    return json.load(open(tmp_path / "out" / "fleet_run.json"))


def test_fleet_runs_every_directory_lake_and_refuses_lakes_without_context(tmp_path, monkeypatch):
    ids = ["Guntersville|AL", "Weiss|AL", "Kvichak / Ugashik|AK"]
    s = run_fleet(tmp_path, monkeypatch, ids, ["Guntersville_AL", "Weiss_AL", "Kvichak_Ugashik_AK"])
    assert s["counts"] == {"lakes": 3, "written": 1, "unchanged": 0, "refused": 2}
    assert set(s["lakes"]) == set(ids)
    for lid in ("Weiss|AL", "Kvichak / Ugashik|AK"):
        assert s["lakes"][lid]["result"] == "REFUSED" and s["lakes"][lid]["reasonCode"] == "NO_LAKE_CONTEXT"
    assert sorted(os.listdir(tmp_path / "out")) == ["biological_state_Guntersville_AL.json", "fleet_run.json"]


def test_fleet_pilot_lake_state_matches_the_pilot_run(tmp_path, monkeypatch):
    run_fleet(tmp_path, monkeypatch, ["Guntersville|AL"], ["Guntersville_AL"])
    got = open(tmp_path / "out" / "biological_state_Guntersville_AL.json", encoding="utf-8").read()
    assert got == GOLDEN["runs"]["Guntersville|AL"]["file"]                                  # same per-lake path, same bytes


def test_fleet_uses_a_reviewed_lake_context_and_rejects_bad_vocabulary(tmp_path, monkeypatch):
    ctx = tmp_path / "ctx.json"
    ctx.write_text(json.dumps({"Weiss|AL": {"region": "south", "waterbodyType": "storage_reservoir"},
                               "Jordan|AL": {"region": "SE", "waterbodyType": "storage_reservoir"},               # not the rules vocabulary
                               "Lay|AL": {"region": "any", "waterbodyType": "any"}}))                           # 'any' is not a lake's context
    s = run_fleet(tmp_path, monkeypatch, ["Weiss|AL", "Jordan|AL", "Lay|AL"], ["Weiss_AL", "Jordan_AL", "Lay_AL"], "--lake-context", str(ctx))
    assert s["lakes"]["Weiss|AL"]["result"] == "WRITTEN"
    assert s["lakes"]["Jordan|AL"]["reasonCode"] == s["lakes"]["Lay|AL"]["reasonCode"] == "NO_LAKE_CONTEXT"
    st = json.load(open(tmp_path / "out" / "biological_state_Weiss_AL.json"))
    assert st["context"]["region"] == "south" and st["context"]["waterbodyType"] == "storage_reservoir" and st["context"]["daypart"] == "NIGHT"


def test_fleet_missing_inputs_are_unknown_not_guessed(tmp_path, monkeypatch):
    monkeypatch.setenv("FISH_FLEET_RUNNER", "1")
    empty = tmp_path / "empty"
    empty.mkdir()
    assert run_state.main(fleet_args(tmp_path, ["Wheeler|AL"], "--inputs-dir", str(empty))) == 0
    st = json.load(open(tmp_path / "out" / "biological_state_Wheeler_AL.json"))
    assert all(v["status"] == "NOT_PUBLISHED" for v in st["inputs"].values())
    assert st["summary"]["speciesPresent"] == 0 and st["summary"]["speciesPresenceUnknown"] == 1     # roster species: UNKNOWN, not absent


def test_fleet_rerun_is_unchanged(tmp_path, monkeypatch):
    run_fleet(tmp_path, monkeypatch, ["Wilson|AL"], ["Wilson_AL"])
    s = run_fleet(tmp_path, monkeypatch, ["Wilson|AL"], ["Wilson_AL"])
    assert s["counts"]["unchanged"] == 1 and s["counts"]["written"] == 0


def test_fleet_refuses_a_directory_with_key_collisions(tmp_path, monkeypatch):
    monkeypatch.setenv("FISH_FLEET_RUNNER", "1")
    with pytest.raises(ValueError, match="collision"):
        run_state.main(fleet_args(tmp_path, ["A B|AL", "A/B|AL"], "--inputs-dir", stage_inputs(tmp_path, [])))
    assert not (tmp_path / "out").exists()


def test_fleet_live_reads_each_lake_through_the_rtdb(tmp_path):
    ids = ["Guntersville|AL", "Weiss|AL"]
    rules = F.write_rules(str(tmp_path / "rules"))
    args = ["--fleet", "--directory", directory(tmp_path, ids), "--rules", rules, "--live", "--now", F.NOW, "--out", "out"]
    off = F.run_live(SCRIPT, args, str(tmp_path), F.fake_db(["Guntersville_AL", "Weiss_AL"]))
    assert off.returncode != 0 and "fleet mode is OFF" in off.stderr
    on = F.run_live(SCRIPT, args, str(tmp_path), F.fake_db(["Guntersville_AL", "Weiss_AL"]), {"FISH_FLEET_RUNNER": "1"})
    assert on.returncode == 0, on.stderr
    got = open(tmp_path / "out" / "biological_state_Guntersville_AL.json", encoding="utf-8").read()
    assert got == GOLDEN["liveRuns"]["Guntersville|AL"]["file"]


def test_the_repository_full_directory_size_is_what_the_fleet_iterates():
    here = os.path.dirname(os.path.abspath(__file__))
    ids = json.load(open(os.path.join(here, "..", "..", "..", "jobs", "lake-geometry", "tests", "directory_ids_621.json")))["ids"]
    assert len(ids) == 621
    import brain_platform as bp
    assert len(bp.lake_keys(ids)) == 621                                                     # the real directory has no key collisions


def test_fleet_over_the_full_621_lake_directory(tmp_path, monkeypatch):
    here = os.path.dirname(os.path.abspath(__file__))
    ids = json.load(open(os.path.join(here, "..", "..", "..", "jobs", "lake-geometry", "tests", "directory_ids_621.json")))["ids"]
    s = run_fleet(tmp_path, monkeypatch, ids, [])
    assert s["counts"] == {"lakes": 621, "written": 5, "unchanged": 0, "refused": 616}       # no reviewed context yet: only the 5 pilots run
    assert {lid for lid, r in s["lakes"].items() if r["result"] == "WRITTEN"} == set(run_state.PILOT_LAKES)
