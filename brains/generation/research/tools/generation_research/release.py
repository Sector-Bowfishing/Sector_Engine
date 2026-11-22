"""Write runtime/knowledge/knowledge-release.json over the current catalog and source-access list (a CANDIDATE: approval NOT_RECORDED).

  PYTHONPATH=jobs/brain_platform python -m generation_research.release --release-id generation-knowledge-candidate-2026-11-22.1

Approval is a separate, gated step: Michael records it, and only then does a release with status APPROVED and a record replace this one."""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
KNOWLEDGE = os.path.normpath(os.path.join(HERE, "..", "..", "..", "runtime", "knowledge"))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "..", "..", "..", "..", "jobs", "brain_platform")))
from sector_brain_platform.knowledge_release import describe_files, release_digest  # noqa: E402

FILES = ("dams.json", "source_access.json")


def manifest(release_id: str, knowledge_dir: str = KNOWLEDGE) -> dict:
    files = describe_files(knowledge_dir, list(FILES))
    return {"schemaVersion": "1.0.0", "brainId": "generation", "releaseId": release_id, "store": "PACKAGED_IN_IMAGE", "owner": "generation",
            "approval": {"status": "NOT_RECORDED", "record": None}, "files": files, "releaseDigest": release_digest(files)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release-id", required=True)
    a = ap.parse_args(argv)
    m = manifest(a.release_id)
    with open(os.path.join(KNOWLEDGE, "knowledge-release.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(m, indent=2) + "\n")
    print(m["releaseDigest"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
