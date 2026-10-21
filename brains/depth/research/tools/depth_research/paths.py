"""Where Depth's OFFLINE research tooling finds things. Research datasets are never in the repository and never read by the runtime.

  DEPTH_RESEARCH_DATA   root of the Depth research dataset snapshot (the layout of the former package `data/` directory: manifest_inputs.json,
                        inputs/, proposals/, datum tables, licence table, and the docs data such as depth_progress_log.jsonl). It lives in the
                        research workspace / the docs/depth-brain-research branch, not in this package. Unset -> research_data() raises.
"""
from __future__ import annotations

import os

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE = os.path.abspath(os.path.join(HERE, "..", "..", ".."))                 # brains/depth
REPO = os.path.abspath(os.path.join(PACKAGE, "..", ".."))
KNOWLEDGE_DIR = os.path.join(PACKAGE, "runtime", "knowledge")                   # the release the runtime verifies (written only by build/refresh)
MANIFEST = os.path.join(KNOWLEDGE_DIR, "candidates.json")
RESEARCH_RECORDS = os.path.join(HERE, "records")                                # small research records kept with the tooling (prereg, rubric inputs)
LAKE_BINDINGS = os.path.join(REPO, "brains", "lake", "contracts", "reviewed-lake-bindings-v1.json")   # Lake-owned contract (never Lake's Swift source)


class ResearchDataUnavailable(RuntimeError):
    pass


def research_data(*parts: str, required: bool = True) -> str | None:
    root = os.environ.get("DEPTH_RESEARCH_DATA")
    if not root:
        if required:
            raise ResearchDataUnavailable("set DEPTH_RESEARCH_DATA to the Depth research dataset snapshot (not in the repository)")
        return None
    return os.path.join(root, *parts)


def write_manifest(manifest: dict, path: str = MANIFEST) -> None:
    """Compact, sorted JSON (the release's on-disk form). Writing it changes the release: regenerate knowledge-release.json with a NEW release id."""
    import json
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, separators=(",", ":"), sort_keys=True)
