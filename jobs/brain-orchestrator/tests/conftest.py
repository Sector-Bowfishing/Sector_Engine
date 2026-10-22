"""Orchestrator scenario tests run on a FROZEN copy of the pre-activation execution manifest (2026-10-20: Water Temp and Intelligence PARKED,
Clarity MANUAL), so they keep testing the decision model's semantics (parking, no implicit starts, change gating) independently of which Brains
the live board activates. Tests of the live board (internal activation 2026-10-22) are marked `live_manifest` and read the committed file."""
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "brain_platform"))
from sector_brain_platform import orchestration as O  # noqa: E402

PRE_ACTIVATION = os.path.join(HERE, "..", "..", "brain_platform", "tests", "fixtures", "control_manifest_pre_activation_2026-10-20.json")


def pytest_configure(config):
    config.addinivalue_line("markers", "live_manifest: run against the committed (live) execution manifest instead of the frozen scenario copy")


@pytest.fixture(autouse=True)
def _scenario_manifest(request, monkeypatch):
    if request.node.get_closest_marker("live_manifest"):
        return
    real = O.load_manifest
    monkeypatch.setattr(O, "load_manifest", lambda path=PRE_ACTIVATION: real(path))
