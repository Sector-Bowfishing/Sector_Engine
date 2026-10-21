"""Packaged knowledge releases (Cortex 2.1 BR-11 a/f): verified on load; missing, unreadable, incompatible or tampered memory fails closed."""
import json
import os

import pytest

from sector_brain_platform import knowledge_release as K


def make(tmp_path, brain="demo", status="NOT_RECORDED", **over):
    (tmp_path / "a.json").write_text('{"x": 1}')
    (tmp_path / "sub").mkdir(exist_ok=True)
    (tmp_path / "sub" / "b.json").write_text('{"y": 2}')
    files = K.describe_files(str(tmp_path), ["a.json", "sub/b.json"])
    m = {"schemaVersion": "1.0.0", "brainId": brain, "releaseId": "demo-knowledge-1", "store": "PACKAGED_IN_IMAGE", "owner": brain,
         "approval": {"status": status, "record": None}, "files": files, "releaseDigest": K.release_digest(files)}
    m.update(over)
    (tmp_path / K.MANIFEST).write_text(json.dumps(m))
    return m


def test_a_verified_release_loads_with_its_id_digest_and_approval(tmp_path):
    m = make(tmp_path)
    r = K.load_release(str(tmp_path), "demo")
    assert (r["releaseId"], r["releaseDigest"], r["approvalStatus"], r["store"]) == ("demo-knowledge-1", m["releaseDigest"], "NOT_RECORDED", "PACKAGED_IN_IMAGE")
    assert K.lineage_triple(r) == ("demo-knowledge-1", "image:knowledge-release.json", m["releaseDigest"])
    assert K.lineage_triple(None) == ("NONE", "NONE", "NONE")


def test_missing_manifest_fails_closed(tmp_path):
    with pytest.raises(K.KnowledgeReleaseError, match="missing"):
        K.load_release(str(tmp_path), "demo")


def test_unreadable_manifest_fails_closed(tmp_path):
    (tmp_path / K.MANIFEST).write_text("{not json")
    with pytest.raises(K.KnowledgeReleaseError, match="unreadable"):
        K.load_release(str(tmp_path), "demo")


@pytest.mark.parametrize("over,needle", [({"schemaVersion": "9.9.9"}, "incompatible"), ({"brainId": "other"}, "belongs to"),
                                          ({"store": "DESKTOP"}, "incomplete"), ({"files": []}, "incomplete"), ({"releaseId": ""}, "incomplete"),
                                          ({"approval": {"status": "MAYBE"}}, "approval status")])
def test_incompatible_or_incomplete_manifest_fails_closed(tmp_path, over, needle):
    make(tmp_path, **over)
    with pytest.raises(K.KnowledgeReleaseError, match=needle):
        K.load_release(str(tmp_path), "demo")


def test_a_changed_file_fails_verification_and_is_never_used(tmp_path):
    make(tmp_path)
    (tmp_path / "sub" / "b.json").write_text('{"y": 3}')
    with pytest.raises(K.KnowledgeReleaseError, match="fails verification"):
        K.load_release(str(tmp_path), "demo")


def test_a_deleted_file_fails_closed(tmp_path):
    make(tmp_path)
    os.remove(tmp_path / "a.json")
    with pytest.raises(K.KnowledgeReleaseError, match="missing or unreadable"):
        K.load_release(str(tmp_path), "demo")


def test_an_edited_file_list_breaks_the_release_digest(tmp_path):
    m = make(tmp_path)
    m["files"] = m["files"][:1]
    (tmp_path / K.MANIFEST).write_text(json.dumps(m))
    with pytest.raises(K.KnowledgeReleaseError, match="digest"):
        K.load_release(str(tmp_path), "demo")


def test_a_path_outside_the_release_directory_is_refused(tmp_path):
    m = make(tmp_path)
    m["files"].append({"path": "../outside.json", "sha256": "0" * 64, "bytes": 1})
    m["releaseDigest"] = K.release_digest(m["files"])
    (tmp_path / K.MANIFEST).write_text(json.dumps(m))
    with pytest.raises(K.KnowledgeReleaseError, match="escapes"):
        K.load_release(str(tmp_path), "demo")
