"""Cortex 2.2 FD-01/FD-03: brain.json declares every path this Brain's runtime writes today (the real publish() patches (Kit spec)).

Contract families (`pathFamilies`, Publisher contract) plus `legacyDirectWrites` (direct-writer paths the Brain does not author at cutover) must
cover the write set exactly: nothing undeclared, and no legacy declaration for a write that does not happen."""
import json
import os

from sector_brain_platform import declared_writes as D

BRAIN_JSON = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "brain.json"), encoding="utf-8"))


def _patches():
    """The real publish() patches on the deterministic test store (as the Kit spec builds them, without importing the Kit: this test also runs in
    the clean production copy, verification/integration/test_wind_package.py)."""
    import tempfile

    import test_brain as TB
    from sector_wind.brain import contract as C
    from sector_wind.brain.publish import publish
    from sector_wind.brain.writer import DryRunWriter
    st, w = TB.make_store(tempfile.mkdtemp()), DryRunWriter()
    rep = publish(st, TB.CFG, w, now=TB.NOW, run_summary={"runAt": C.iso(TB.NOW), "errors": [], "seconds": 90}, directory=TB.DIRECTORY)
    assert rep["ok"], rep["errors"]
    return w.patches


def _written():
    return [k for p in _patches() for k in p]


def test_every_runtime_write_is_declared():
    assert D.undeclared(BRAIN_JSON, _written()) == []


def test_no_legacy_declaration_without_a_write():
    assert D.unused_legacy(BRAIN_JSON, _written()) == []


def test_legacy_declarations_are_well_formed():
    assert D.problems(BRAIN_JSON) == []
