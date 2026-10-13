"""Stale-score guard tests (deterministic, local git only)."""
import json, os, subprocess, sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import check_score_artifacts as G

OLD = {"value": 3.1, "scoreVersion": "v1", "uncapped": None, "basis": "FROZEN", "scoreUpdatedAt": "2026-10-12T06:16:16Z"}
NEW = {"value": 3.3, "scoreVersion": "v1", "uncapped": 3.27, "basis": "COMPUTED", "scoreUpdatedAt": "2026-10-13T21:13:49Z"}


def test_compare_verdicts():
    assert G.compare(OLD, NEW)[0] == "STALE"                                   # the Wind incident: newer generated block, different content
    assert G.compare(NEW, NEW)[0] == "OK"
    assert G.compare(NEW, OLD)[0] == "AHEAD"                                   # baked block newer than the branch's: warn, do not fail
    assert G.compare(OLD, dict(OLD, scoreUpdatedAt="2026-10-13T00:00:00Z"))[0] == "OK"   # newer timestamp only, same content
    assert G.compare(None, NEW)[0] == "STALE" and G.compare(OLD, None)[0] == "MISSING"
    assert G.compare(NEW, dict(NEW, scoreUpdatedAt="2026-10-14T01:00:00Z", value=3.4, uncapped=3.4))[0] == "STALE"


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q", "-b", "main"); git(tmp_path, "config", "user.email", "t@t"); git(tmp_path, "config", "user.name", "t")
    (tmp_path / "frozen.json").write_text(json.dumps({"wind": NEW}))
    git(tmp_path, "add", "."); git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def sources(tmp, ref="HEAD"):
    p = tmp / "sources.json"
    p.write_text(json.dumps({"sources": [{"brain": "wind", "key": "wind", "ref": ref, "path": "frozen.json"}]}))
    return str(p)


def test_guard_passes_when_the_lineage_matches_the_brain_branch(repo, capsys):
    assert G.run(sources(repo), str(repo / "frozen.json"), str(repo)) == 0
    assert "OK" in capsys.readouterr().out


def test_guard_fails_when_the_baked_file_is_older_than_the_brain_branch(repo, capsys):
    (repo / "baked.json").write_text(json.dumps({"wind": OLD}))
    assert G.run(sources(repo), str(repo / "baked.json"), str(repo)) == 1
    assert "STALE" in capsys.readouterr().out


def test_missing_ref_is_reported_not_silently_passed(repo, capsys):
    assert G.run(sources(repo, ref="refs/heads/does-not-exist"), str(repo / "frozen.json"), str(repo)) == 0
    out = capsys.readouterr().out
    assert "MISSING" in out and "NOT CHECKED" in out


def test_committed_sources_manifest_lists_wind_and_matches_this_lineage():
    root = G.ROOT
    srcs = json.load(open(os.path.join(root, "docs", "brains", "scoring", "score-artifact-sources.json")))["sources"]
    assert [s["brain"] for s in srcs] == ["wind"] and srcs[0]["key"] == "wind"
    wind = json.load(open(os.path.join(root, "docs", "brains", "scoring", "frozen-scores.json")))["wind"]
    assert wind["basis"] == "COMPUTED" and wind["evidence"] and wind["scoreBreakdown"]      # generated block carried, with provenance
