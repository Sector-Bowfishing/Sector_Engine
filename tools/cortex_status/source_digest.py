"""Content digest of the engineering surface the status report describes, so a report (and a certification run) can be proven to belong to the
exact code it was produced from. Tracked files only (`git ls-files`, local: no network), hashed from the working tree, under fixed roots.
Records (docs/cortex) are excluded on purpose: updating a record never makes the code "new"."""
from __future__ import annotations

import hashlib
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ROOTS = ("brains/", "jobs/brain_platform/", "jobs/brain-orchestrator/", "jobs/brain-scores/", "tools/brain_certification/", "tools/architecture/",
         "tools/knowledge/", "tools/cortex_status/", "contracts/", "Sources/", "Tests/", "Package.swift", "Package.resolved", "Dockerfile",
         "docs/brains/scoring/", "providers/", "platform/", ".github/workflows/")


def tracked(root: str = ROOT) -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "--", *ROOTS], cwd=root, capture_output=True, check=True).stdout.decode()
    return sorted(p for p in out.split("\0") if p)


def source_digest(root: str = ROOT) -> str:
    h = hashlib.sha256()
    for rel in tracked(root):
        p = os.path.join(root, rel)
        if not os.path.isfile(p):
            continue                                          # deleted in the working tree: not part of the evaluated code
        with open(p, "rb") as fh:
            h.update(rel.encode() + b"\0" + hashlib.sha256(fh.read()).hexdigest().encode() + b"\n")
    return "sha256:" + h.hexdigest()
