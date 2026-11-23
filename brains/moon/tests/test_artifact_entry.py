"""artifact_entry.py: Moon's artifact mode for Sector Pulse `moon-central` (prepared, off). A fake live database: no network, no credential, no
database write. The Weather edge: the entry reads Weather's LAST COMPLETED published state (within 3 h) and never waits for a Weather run."""
import json
import os
import subprocess
import sys

import artifact_entry as AE
import moon_support as S
from moon_brain import lakes as L
from sector_brain_platform import lake_key
from sector_brain_platform import python_artifact_entry as E

EXEC_ID = "00000000-0000-4000-8000-000000000001"
NOW = S.NOW.replace(hour=23)


class FakeLive:
    def __init__(self, tree):
        self.tree, self.calls = tree, []

    def get(self, path, shallow=False):
        self.calls.append(path)
        return self.tree.get(path)


def _entry(tmp_path, monkeypatch, tree, *, approved=True, intent="1"):
    if approved:
        monkeypatch.setattr(L, "require_approved", lambda d: d)
    if intent:
        monkeypatch.setenv("MOON_WRITE_APPROVED", intent)
    else:
        monkeypatch.delenv("MOON_WRITE_APPROVED", raising=False)
    live = FakeLive(tree)
    rc = AE.main(["--artifact-dir", str(tmp_path / "store"), "--emit", str(tmp_path / "artifact.json"), "--read-rtdb", "--execution-id", EXEC_ID],
                 live_factory=lambda url, b: E.LiveReadOnly(live), now=NOW)
    return rc, live


def test_the_hand_off_reads_weather_s_last_completed_state_and_seals_one_artifact(tmp_path, monkeypatch, capsys):
    fresh = S.weather_state([], generated_at="2026-11-22T22:00:00Z")           # 1 h old: used
    old = S.weather_state([], generated_at="2026-11-22T19:30:00Z")             # 3.5 h old: not used (moon-only, labelled)
    tree = {f"lakes/{lake_key('Guntersville|AL')}/states/weather": fresh, f"lakes/{lake_key('Lake Martin|AL')}/states/weather": old}
    rc, live = _entry(tmp_path, monkeypatch, tree)
    assert rc == 0
    report = json.loads(capsys.readouterr().out.splitlines()[0])["report"]
    assert report["weatherInput"]["used"] == 1 and report["weatherInput"]["tooOld"] == 1
    assert f"lakes/{lake_key('Guntersville|AL')}/states/moon" in live.calls      # own previous state read from live, GET only
    art = json.load(open(tmp_path / "artifact.json"))
    assert art["lineage"]["brainId"] == "moon" and art["lineage"]["knowledgeRelease"] == L.lineage()[0]


def test_the_entry_never_waits_for_weather_the_edge_does_not_defer():
    m = json.load(open(os.path.join(S.REPO, "jobs", "brain_platform", "sector_brain_platform", "control_manifest.json")))
    edge = next(d for d in m["brains"]["moon"]["dependencies"] if d["id"] == "weather")
    assert edge["deferIfUpstreamStarted"] is False and edge["maxAgeHours"] == AE.R.WEATHER_MAX_AGE_HOURS


def test_the_gates_hold(tmp_path, monkeypatch):
    assert _entry(tmp_path, monkeypatch, {}, approved=False)[0] == 2
    assert _entry(tmp_path, monkeypatch, {}, intent=None)[0] == 3
    assert not (tmp_path / "artifact.json").exists()


def test_the_cli_refuses_while_the_release_is_unapproved(tmp_path):
    r = subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "..", "runtime", "artifact_entry.py"), "--artifact-dir",
                        str(tmp_path / "s"), "--emit", str(tmp_path / "a.json"), "--read-rtdb"], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "MOON_WRITE_APPROVED": "1"})
    assert r.returncode == 2 and "BLOCKED_AWAITING_APPROVED_RELEASE" in r.stderr and not (tmp_path / "s").exists()
