"""The packaged lake directory (the Moon knowledge release): verified on load, refused when tampered, and equal to the Engine's directory."""
import json
import os
import shutil

import pytest

from moon_brain import lakes as L
from sector_brain_platform.keys import lake_keys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def test_projection_matches_the_engine_lake_directory():
    swift = open(os.path.join(REPO, L.SOURCE_REL), encoding="utf-8").read()
    want = L.project(swift)
    got = L.load()
    assert {k: got[k] for k in want} == want
    assert got["count"] == 648                      # the directory size the owner decision names (Sector_Ops #51)


def test_every_lake_has_a_legal_unique_key():
    assert len(lake_keys([r["lakeId"] for r in L.load()["lakes"]])) == 648


def test_release_is_verified_and_not_approved():
    rel = L.load()["release"]
    assert rel["releaseId"].startswith("moon-knowledge-") and rel["releaseDigest"].startswith("sha256:")
    assert rel["approvalStatus"] == "NOT_RECORDED"
    assert L.lineage()[1] == "image:knowledge-release.json"


def test_tampered_or_missing_release_refuses(tmp_path):
    d = tmp_path / "knowledge"
    shutil.copytree(L.RELEASE_DIR, d)
    doc = json.load(open(d / L.FILE))
    doc["lakes"][0]["lat"] += 1.0
    (d / L.FILE).write_text(json.dumps(doc))
    with pytest.raises(L.KnowledgeReleaseError):
        L.load(str(d))
    (d / L.FILE).unlink()
    with pytest.raises(L.KnowledgeReleaseError):
        L.load(str(d))
