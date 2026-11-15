"""B6 / exit check X14 for a Swift Brain: Lake's runtime has no direct database writer left.

exit_gate.legacy_write_sites() scans Python only, so this pins the Swift side: LakeBrainJob refuses --rtdb before anything runs, has no code path that
builds an RTDBRestStore as the run's store outside --dry-run --read-rtdb (GET only), and the retired Cloud Run deploy refuses."""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
LAKE = os.path.abspath(os.path.join(HERE, ".."))
MAIN = os.path.join(LAKE, "runtime", "LakeBrainJob", "main.swift")


def _code(path):
    return "\n".join(line.split("//", 1)[0] for line in open(path, encoding="utf-8").read().splitlines())


def test_rtdb_flag_is_refused_before_anything_runs():
    code = _code(MAIN)
    guard = code.index('argv.contains("--rtdb")')
    assert "refuse(" in code[guard:guard + 300]
    assert guard < code.index("LakeBrainRunner.run(")


def test_no_live_writer_branch_remains():
    code = _code(MAIN)
    assert 'flag("--rtdb")' not in code
    assert "SECTOR_BRAIN_RTDB_URL" not in code
    # the only RTDBRestStore is the GET-only reader behind --dry-run DIR --read-rtdb URL, wrapped in ReadThroughDryRunStore
    assert len(re.findall(r"RTDBRestStore\(", code)) == 1
    assert "ReadThroughDryRunStore(reader: rest!" in code
    assert "store = rest\n" not in code and "store = rest;" not in code


def test_no_other_lake_swift_file_builds_a_database_writer():
    hits = []
    for root, _dirs, files in os.walk(os.path.join(LAKE, "runtime")):
        for f in files:
            p = os.path.join(root, f)
            if f.endswith(".swift") and p != MAIN and "RTDBRestStore(" in _code(p):
                hits.append(os.path.relpath(p, LAKE))
    assert hits == []


def test_the_retired_cloud_run_deploy_refuses():
    s = open(os.path.join(LAKE, "deploy", "deploy-job.sh"), encoding="utf-8").read()
    i = s.index("set -euo pipefail")
    assert "exit 2" in s[i:i + 300]
    assert "gcloud run jobs deploy" not in s
