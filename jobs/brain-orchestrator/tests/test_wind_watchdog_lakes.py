"""W-H3 (Sector_Ops #51 decision D3, corrected 2026-11-23): Wind's watchdog lake list = every lake in the canonical directory, which contains D3's
live + nationally profiled lakes. Wind writes lakeFleet/{k}/readiness/wind for every directory lake, so D3's list alone would halt the first publish
(brains/wind/tests/test_watchdog_scope.py proves that against a sealed write set). Local only: tmp files, no network."""
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "ops"))

import brain_watchdog_lakes as BL                                             # noqa: E402
import hybrid_stage as HS                                                     # noqa: E402
import wind_watchdog_lakes as WL                                              # noqa: E402

LIVE = ["Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN"]
DIRECTORY = [{"id": lid} for lid in LIVE] + [{"id": "Kentucky Lake|KY"}, {"id": "Lake Barkley|KY"}, {"id": "Hartwell|SC"}]
MANIFEST = {"lakes": [
    {"name": "Kentucky Lake", "state": "KY", "status": "PASS", "tableSha256": "a"},
    {"name": "Lake Barkley", "state": "KY", "status": "FLAGGED", "tableSha256": "b"},
    {"name": "Hartwell", "state": "SC", "status": "FAIL", "tableSha256": "c"},        # not profiled
    {"name": "Nowhere", "state": "TX", "status": "PASS", "tableSha256": "d"},         # not in the canonical directory
    {"name": "Hartwell", "state": "SC", "status": "PASS"},                            # no table
]}
ALL = sorted(["Guntersville_AL", "Wheeler_AL", "Wilson_AL", "Pickwick_Lake_TN", "Kentucky_Lake_KY", "Lake_Barkley_KY", "Hartwell_SC"])


def _files(tmp_path, stage=None):
    m, d, s = tmp_path / "m.json", tmp_path / "d.json", tmp_path / "wind.json"
    m.write_text(json.dumps(MANIFEST))
    d.write_text(json.dumps({"lakes": DIRECTORY}))
    s.write_text(json.dumps(stage or json.load(open(WL.STAGE))))
    return ["--manifest", str(m), "--directory", str(d), "--stage", str(s)], s


def test_d3_is_live_plus_profiled_lakes():
    assert WL.d3_lakes(MANIFEST, DIRECTORY) == sorted(
        ["Guntersville_AL", "Wheeler_AL", "Wilson_AL", "Pickwick_Lake_TN", "Kentucky_Lake_KY", "Lake_Barkley_KY"])


def test_the_list_is_the_whole_directory_and_contains_d3():
    lakes = WL.lake_list(MANIFEST, DIRECTORY)
    assert lakes == ALL
    assert set(WL.d3_lakes(MANIFEST, DIRECTORY)) <= set(lakes)
    assert WL.lake_list(None, DIRECTORY) == ALL                                  # the manifest only proves D3 is covered


def test_a_live_lake_missing_from_the_directory_is_refused(tmp_path):
    args, _ = _files(tmp_path)
    (tmp_path / "d.json").write_text(json.dumps({"lakes": DIRECTORY[1:]}))
    assert WL.main(args) == 2


def test_write_pins_and_check_agrees_and_the_fragment_stays_valid(tmp_path):
    args, s = _files(tmp_path)
    assert WL.main(args + ["--check"]) == 1                      # the committed fragment pins the real directory, not this 7-lake one
    assert WL.main(args + ["--write"]) == 0
    assert WL.main(args + ["--check"]) == 0
    frag = json.loads(s.read_text())
    assert frag["watchdog"]["lakes"] == ALL
    assert HS.load_fragment(str(s))["watchdog"]["lakes"] == ALL                  # the stage loader still accepts the pinned fragment


def test_the_committed_fragment_matches_the_directory_golden():
    assert WL.main(["--check"]) == 0


def test_wind_gets_the_same_list_as_the_other_pulse_brains():
    frag = json.load(open(WL.STAGE))
    assert frag["watchdog"]["lakes"] == BL.generated()
    pol = json.load(open(BL.POLICY))
    assert frag["watchdog"]["lakes"] == pol["brains"]["water-clarity"]["lakes"]
    assert {"Guntersville_AL", "Wheeler_AL", "Wilson_AL", "Pickwick_Lake_TN"} <= set(frag["watchdog"]["lakes"])


def test_the_staged_fragment_merges_and_passes_the_real_loaders():
    frag = HS.load_fragment(WL.STAGE)
    r, w, c = (json.load(open(p)) for p in (HS.RUNNER_POLICY, HS.WATCHDOG_POLICY, HS.CUTOVER))
    assert HS.verify(*HS.merged(frag, "check-only", r, w, c), "wind") == []


@pytest.mark.parametrize("bad", [{"lakes": []}, {"lakes": [{"id": "A|AL"}, {"id": "A|AL"}]}])
def test_bad_directories_are_refused(tmp_path, bad):
    args, _ = _files(tmp_path)
    (tmp_path / "d.json").write_text(json.dumps(bad))
    assert WL.main(args) == 2
