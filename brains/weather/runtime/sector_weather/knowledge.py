"""The Weather Brain's packaged knowledge: ONE verified release in `runtime/knowledge/` holding the PRE-STATED weather-change thresholds and
freshness tiers (weather-change-thresholds-v1). `load()` verifies the manifest and the file (sector_brain_platform.knowledge_release); a missing
or tampered release raises KnowledgeReleaseError and the Brain refuses to run. There is no fallback copy in code. Approval NOT_RECORDED: the
owner has not yet signed off the thresholds; internal (CALIBRATION) use only, never customer serving."""
from __future__ import annotations

import json
import os

from sector_brain_platform.knowledge_release import KnowledgeReleaseError, lineage_triple, load_release  # noqa: F401

RELEASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
THRESHOLDS_FILE = "weather-change-thresholds-v1.json"


def load(release_dir: str = RELEASE_DIR, brain_id: str = "weather") -> tuple[dict, dict]:
    """-> (release summary, thresholds document). Raises KnowledgeReleaseError when the release does not verify."""
    rel = load_release(release_dir, brain_id)
    if THRESHOLDS_FILE not in rel["files"]:
        raise KnowledgeReleaseError(f"Weather knowledge release lacks {THRESHOLDS_FILE}")
    with open(os.path.join(release_dir, THRESHOLDS_FILE), encoding="utf-8") as fh:
        return rel, json.load(fh)
