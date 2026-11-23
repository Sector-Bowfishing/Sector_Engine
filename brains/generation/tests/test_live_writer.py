"""The gated live writer (run.py --write; GENERATION_BRAIN_PLAN.md section 6.1): with an APPROVED release AND GENERATION_WRITE_APPROVED=1 it
writes through RtdbWriter exactly the paths brain.json declares (Cortex BR-13, FD-03), and the release in this repository is NOT approved.
The refusals themselves are in test_run_entry.py. No network, no database: fixture transport and an in-memory recorder."""
import importlib
import json
import os

import pytest

import generation_support as GS
from generation_brain import knowledge as K, writer as WR
from generation_brain.fixtures import fixture_transport
from generation_brain.http import Fetcher
from sector_brain_platform import declared_writes as D

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN_JSON = json.load(open(os.path.join(HERE, "..", "brain.json"), encoding="utf-8"))


def test_the_release_is_not_approved_in_this_repository():
    k = K.load()
    assert k.release["approvalStatus"] == "NOT_RECORDED"
    with pytest.raises(K.KnowledgeNotApproved):
        K.require_approved(k)


def test_the_live_client_refuses_an_app_database():
    with pytest.raises(WR.WriteError):
        WR.RtdbWriter("https://sector-9393c-default-rtdb.firebaseio.com")


class Recorder(WR.DryRunWriter):
    last = None
    made = []

    def __init__(self, base_url, token=None, timeout=20.0):
        super().__init__()
        Recorder.made.append(base_url)
        Recorder.last = self


class _Approved:
    """The packaged release marked APPROVED for this test only, over the support catalog (four lakes answered by fixtures)."""

    def __init__(self, k):
        self._k = k
        self.release = {**k.release, "approvalStatus": "APPROVED"}
        self.approved = True

    def catalog(self):
        return GS.catalog()

    def access(self):
        return self._k.access()

    def summary(self):
        return {**self._k.summary(), "approvalStatus": "APPROVED"}


def test_live_write_set_is_fully_declared(monkeypatch, capsys):
    import run as R
    R = importlib.reload(R)
    real = K.load()
    monkeypatch.setattr(R.K, "load", lambda: _Approved(real))
    monkeypatch.setattr(R, "Fetcher", lambda access, **kw: Fetcher(access, transport=fixture_transport(GS.FIXTURES), sleep=lambda s: None))
    monkeypatch.setattr(R, "RtdbWriter", Recorder)
    monkeypatch.setenv("GENERATION_WRITE_APPROVED", "1")
    Recorder.made.clear()
    rc = R.main(["--write"])
    out = json.loads(capsys.readouterr().out)
    assert out["published"] is True and Recorder.made == [R.RTDB_URL] and rc in (0, 1)
    written = {}
    for p in Recorder.last.patches:
        written.update(p)
    assert written and D.undeclared(BRAIN_JSON, written) == [] and D.unused_legacy(BRAIN_JSON, written) == []
    dry = GS.run_updates()
    assert {p.split("/")[0] for p in written} == {p.split("/")[0] for p in dry}         # the live path writes the same families as the dry run
