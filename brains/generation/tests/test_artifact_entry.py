"""artifact_entry.py: Generation's artifact mode for Sector Pulse `generation-central` (prepared, off). Hand-built source fixtures and a fake
live database: no network, no credential, no database write."""
import json
import os
import subprocess
import sys

import artifact_entry as AE
import generation_support as S
from generation_brain import knowledge as K
from generation_brain.fixtures import fixture_transport
from sector_brain_platform import python_artifact_entry as E

EXEC_ID = "00000000-0000-4000-8000-000000000001"


class FakeLive:
    def __init__(self):
        self.calls = []

    def get(self, path, shallow=False):
        self.calls.append(path)
        return None


def _entry(tmp_path, monkeypatch, *, approved=True, intent="1"):
    if approved:
        monkeypatch.setattr(K, "require_approved", lambda k: k)
    if intent:
        monkeypatch.setenv("GENERATION_WRITE_APPROVED", intent)
    else:
        monkeypatch.delenv("GENERATION_WRITE_APPROVED", raising=False)
    live = FakeLive()
    rc = AE.main(["--artifact-dir", str(tmp_path / "store"), "--emit", str(tmp_path / "artifact.json"), "--read-rtdb", "--execution-id", EXEC_ID],
                 transport=fixture_transport(S.FIXTURES), sleep=lambda s: None, live_factory=lambda url, b: E.LiveReadOnly(live), now=S.NOW)
    return rc, live


def test_the_hand_off_reads_the_live_previous_state_and_seals_one_artifact(tmp_path, monkeypatch):
    rc, live = _entry(tmp_path, monkeypatch)
    assert rc == 0
    assert "brains/generation" in live.calls and any(c.endswith("/states/generation") for c in live.calls)
    art = json.load(open(tmp_path / "artifact.json"))
    assert art["lineage"]["brainId"] == "generation" and art["lineage"]["knowledgeRelease"] == S.knowledge().lineage()[0]


def test_the_gates_hold_and_the_intent_name_is_run_py_s(tmp_path, monkeypatch):
    assert _entry(tmp_path, monkeypatch, approved=False)[0] == 2
    assert _entry(tmp_path, monkeypatch, intent=None)[0] == 3
    assert not (tmp_path / "artifact.json").exists()
    src = open(os.path.join(S.HERE, "..", "runtime", "run.py")).read()
    assert f'"{AE.WRITE_INTENT_ENV}"' in src


def test_the_cli_refuses_while_the_release_is_unapproved(tmp_path):
    r = subprocess.run([sys.executable, os.path.join(S.HERE, "..", "runtime", "artifact_entry.py"), "--artifact-dir", str(tmp_path / "s"),
                        "--emit", str(tmp_path / "a.json"), "--read-rtdb"], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "GENERATION_WRITE_APPROVED": "1"})
    assert r.returncode == 2 and "BLOCKED_AWAITING_APPROVED_RELEASE" in r.stderr and not (tmp_path / "s").exists()
