"""Depth research-tool tests. Tests that need the research dataset snapshot (not in the repository) are skipped unless DEPTH_RESEARCH_DATA
points at it; everything else runs on the committed release and research records."""
import os

import pytest

import depth_brain  # noqa: F401  (bootstraps the platform path)

PACKAGE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
MANIFEST_PATH = os.path.join(PACKAGE, "runtime", "knowledge", "candidates.json")


def research_file(*parts):
    root = os.environ.get("DEPTH_RESEARCH_DATA")
    p = os.path.join(root, *parts) if root else None
    if not p or not os.path.exists(p):
        pytest.skip(allow_module_level=True, reason=f"research dataset file {'/'.join(parts)} not available (set DEPTH_RESEARCH_DATA)")
    return p
