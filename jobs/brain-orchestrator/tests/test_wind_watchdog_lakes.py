"""W-H3 (Sector_Ops #51 decision D3): Wind's watchdog lake list = the 4 live lakes + every nationally profiled lake, generated and pinned into the
STAGED wind.json fragment. Local only: tmp files, no network."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "tools", "ops"))

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


def _files(tmp_path, stage=None):
    m, d, s = tmp_path / "m.json", tmp_path / "d.json", tmp_path / "wind.json"
    m.write_text(json.dumps(MANIFEST))
    d.write_text(json.dumps({"lakes": DIRECTORY}))
    s.write_text(json.dumps(stage or json.load(open(WL.STAGE))))
    return ["--manifest", str(m), "--directory", str(d), "--stage", str(s)], s


def test_the_list_is_live_plus_profiled_lakes():
    assert WL.lake_list(MANIFEST, DIRECTORY) == sorted(
        ["Guntersville_AL", "Wheeler_AL", "Wilson_AL", "Pickwick_Lake_TN", "Kentucky_Lake_KY", "Lake_Barkley_KY"])


def test_no_manifest_means_the_live_lakes_only():
    assert WL.lake_list(None, DIRECTORY) == sorted(["Guntersville_AL", "Wheeler_AL", "Wilson_AL", "Pickwick_Lake_TN"])


def test_a_live_lake_missing_from_the_directory_is_refused(tmp_path):
    args, _ = _files(tmp_path)
    d = tmp_path / "d.json"
    d.write_text(json.dumps({"lakes": DIRECTORY[1:]}))
    assert WL.main(args) == 2


def test_write_pins_and_check_agrees_and_the_fragment_stays_valid(tmp_path):
    args, s = _files(tmp_path)
    assert WL.main(args + ["--check"]) == 1                      # today's staged fragment pins only the 4 live lakes
    assert WL.main(args + ["--write"]) == 0
    assert WL.main(args + ["--check"]) == 0
    frag = json.loads(s.read_text())
    assert frag["watchdog"]["lakes"] == WL.lake_list(MANIFEST, DIRECTORY)
    assert HS.load_fragment(str(s))["watchdog"]["lakes"] == frag["watchdog"]["lakes"]      # the stage loader still accepts the pinned fragment


def test_the_real_staged_fragment_is_not_touched_by_the_tests():
    frag = json.load(open(WL.STAGE))
    assert frag["brainId"] == "wind" and frag["watchdog"]["lakes"]
