"""Depth's approved operational knowledge: ONE versioned release in `runtime/knowledge/` (Cortex BR-11).

The release is `knowledge/knowledge-release.json` over the candidate manifest (`candidates.json`), the claim levels (`claim_levels.json`) and the
operator stage-area ratings (`stage_area_curves.json`). `load()` verifies the manifest and every file (sector_brain_platform.knowledge_release);
anything missing or tampered raises KnowledgeReleaseError. Research inputs (datum tables, proposals, surveys) are NOT part of the release and are
never read at runtime: the manifest is built offline by research/tools/depth_research.

Approval is a separate stage. A release whose approval status is not APPROVED may be inspected (plan) and exercised locally with an explicit
`allow_unapproved=True` (dry runs, tests), but it can never be published: `require_approved()` raises KnowledgeNotApproved and the job reports
BLOCKED_AWAITING_APPROVED_RELEASE instead of substituting unapproved data."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

from sector_brain_platform.knowledge_release import KnowledgeReleaseError, load_release, lineage_triple  # noqa: F401

from . import contract as C

RELEASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "knowledge")
FILES = ("candidates.json", "claim_levels.json", "stage_area_curves.json")
BLOCKED = "BLOCKED_AWAITING_APPROVED_RELEASE"


class KnowledgeNotApproved(KnowledgeReleaseError):
    """The release verifies but carries no approval: it must not be published from."""


@dataclass(frozen=True)
class Knowledge:
    release: dict
    release_dir: str

    @property
    def approved(self) -> bool:
        return self.release["approvalStatus"] == "APPROVED"

    def path(self, name: str) -> str:
        if name not in self.release["files"]:
            raise KnowledgeReleaseError(f"{name} is not part of the Depth knowledge release")
        return os.path.join(self.release_dir, name)

    def json(self, name: str):
        with open(self.path(name), encoding="utf-8") as fh:
            return json.load(fh)

    def lineage(self) -> tuple[str, str, str]:
        return lineage_triple(self.release)

    def summary(self) -> dict:
        r = self.release
        return {"releaseId": r["releaseId"], "releaseDigest": r["releaseDigest"], "approvalStatus": r["approvalStatus"], "store": r["store"]}


def load(release_dir: str = RELEASE_DIR) -> Knowledge:
    rel = load_release(release_dir, C.BRAIN_ID)
    missing = sorted(set(FILES) - set(rel["files"]))
    if missing:
        raise KnowledgeReleaseError(f"Depth knowledge release lacks {missing}")
    return Knowledge(rel, release_dir)


def require_approved(k: Knowledge) -> Knowledge:
    if not k.approved:
        raise KnowledgeNotApproved(f"{BLOCKED}: release {k.release['releaseId']} approval is {k.release['approvalStatus']}")
    return k
