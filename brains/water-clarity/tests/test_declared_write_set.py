"""Cortex 2.2 FD-01/FD-03: brain.json declares every path this Brain's runtime writes today (the REAL run.main write set (Kit spec)).

Contract families (`pathFamilies`, Publisher contract) plus `legacyDirectWrites` (direct-writer paths the Brain does not author at cutover) must
cover the write set exactly: nothing undeclared, and no legacy declaration for a write that does not happen."""
import json
import os

import clarity_cert_spec
from sector_brain_platform import declared_writes as D

BRAIN_JSON = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "brain.json"), encoding="utf-8"))


def _written():
    return list(clarity_cert_spec._legacy_updates())


def test_every_runtime_write_is_declared():
    assert D.undeclared(BRAIN_JSON, _written()) == []


def test_no_legacy_declaration_without_a_write():
    assert D.unused_legacy(BRAIN_JSON, _written()) == []


def test_legacy_declarations_are_well_formed():
    assert D.problems(BRAIN_JSON) == []
