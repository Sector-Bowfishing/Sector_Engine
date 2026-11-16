"""SI-WD (a) (Sector_Ops #51, owner approval 2026-11-16 18:09Z): Sector Intelligence's watchdog lake list = every lake in the Engine's /lakes
directory, generated and pinned into the STAGED sector-intelligence.json fragment, then applied into watchdog-policy.json. Local only: no network."""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "ops"))
sys.path.insert(0, os.path.join(ROOT, "jobs", "brain_platform"))

import si_watchdog_lakes as SL                                                # noqa: E402
from sector_brain_platform import cycle_watchdog as WD                       # noqa: E402

DIRECTORY = {"lakes": [{"id": "Guntersville|AL"}, {"id": "Pickwick Lake|TN"}, {"id": "Kentucky Lake|KY"}]}


def test_the_list_is_every_directory_lake_as_keys():
    assert SL.lake_list(DIRECTORY) == ["Guntersville_AL", "Kentucky_Lake_KY", "Pickwick_Lake_TN"]


def test_it_reads_the_list_form_and_the_golden_form():
    assert SL.lake_list(DIRECTORY["lakes"]) == SL.lake_list({"orderedLakeIds": ["Guntersville|AL", "Pickwick Lake|TN", "Kentucky Lake|KY"]})


def test_it_refuses_a_key_collision_and_an_empty_or_repeated_directory():
    with pytest.raises(ValueError):
        SL.lake_list({"lakes": [{"id": "Lake A|TX"}, {"id": "Lake-A|TX"}]})
    with pytest.raises(ValueError):
        SL.lake_list({"lakes": []})
    with pytest.raises(ValueError):
        SL.lake_list({"lakes": [{"id": "X|AL"}, {"id": "X|AL"}]})


def test_check_and_write_round_trip(tmp_path):
    d, s = tmp_path / "d.json", tmp_path / "si.json"
    d.write_text(json.dumps(DIRECTORY))
    s.write_text(json.dumps({"watchdog": {"holder": "pulse", "lakes": ["Guntersville_AL"]}}))
    args = ["--directory", str(d), "--stage", str(s)]
    assert SL.main(args + ["--check"]) == 1
    assert SL.main(args + ["--write"]) == 0
    assert SL.main(args + ["--check"]) == 0
    assert json.loads(s.read_text())["watchdog"] == {"holder": "pulse", "lakes": SL.lake_list(DIRECTORY)}


def test_the_pinned_fragment_and_the_live_policy_cover_the_whole_directory():
    golden = SL.lake_list(json.load(open(SL.GOLDEN)))
    assert SL.main(["--check"]) == 0
    assert json.load(open(SL.STAGE))["watchdog"]["lakes"] == golden
    assert WD.load_policy()["brains"]["sector-intelligence"]["lakes"] == golden
