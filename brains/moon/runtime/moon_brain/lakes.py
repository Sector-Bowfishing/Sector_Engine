"""The lake registry the Brain runs over: a packaged projection (lakeId, name, state, lat, lon) of the Engine's compiled lake directory
(Sources/SectorEngine/Support/LakeDirectory.swift, registry.lakes), shipped as the Brain's ONE packaged knowledge release (runtime/knowledge/,
Cortex BR-11). The runtime reads ONLY the verified release; the Swift source is read by the maintenance command below and by a test that fails when
the projection drifts from the directory. A missing or tampered release refuses the run.

  python -m moon_brain.lakes --check      # exit 1 if knowledge/lakes-directory.json differs from LakeDirectory.swift
  python -m moon_brain.lakes --write      # then: python3 tools/knowledge/build_release_manifest.py brains/moon/runtime/knowledge --write --release-id ...
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys

import moon_brain  # noqa: F401  (bootstraps the platform path)

from sector_brain_platform.knowledge_release import KnowledgeReleaseError, lineage_triple, load_release

from . import contract as C

RUNTIME = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RELEASE_DIR = os.path.join(RUNTIME, "knowledge")
FILE = "lakes-directory.json"
PACKAGED = os.path.join(RELEASE_DIR, FILE)
SOURCE_REL = "Sources/SectorEngine/Support/LakeDirectory.swift"
SCHEMA = "moon-lake-directory-projection-v1"


class LakeRegistryError(KnowledgeReleaseError):
    pass


def _digest(lakes: list) -> str:
    return hashlib.sha256(json.dumps(lakes, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def project(swift_text: str) -> dict:
    m = re.search(r'lakesJSON = #"""\n(.*?)\n"""#', swift_text, re.S)
    if not m:
        raise LakeRegistryError("LakeDirectory.swift: lakesJSON literal not found")
    rows = json.loads(m.group(1))
    lakes = [{"lakeId": f"{r['name']}|{r['state']}", "name": r["name"], "state": r["state"], "lat": r["lat"], "lon": r["lon"]} for r in rows]
    return {"schema": SCHEMA, "source": SOURCE_REL, "registry": "registry.lakes", "count": len(lakes), "digest": _digest(lakes), "lakes": lakes}


def release(release_dir: str = RELEASE_DIR) -> dict:
    rel = load_release(release_dir, C.BRAIN_ID)
    if FILE not in rel["files"]:
        raise LakeRegistryError(f"the Moon knowledge release lacks {FILE}")
    return rel


def lineage(release_dir: str = RELEASE_DIR) -> tuple[str, str, str]:
    return lineage_triple(release(release_dir))


def load(release_dir: str = RELEASE_DIR) -> dict:
    """The packaged projection, verified twice: the knowledge release (sha256 + bytes + release digest), then the projection's own schema, count
    and digest. Anything missing or edited refuses the run."""
    rel = release(release_dir)
    try:
        doc = json.load(open(os.path.join(release_dir, FILE), encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise LakeRegistryError(f"lake directory projection unreadable: {e}") from None
    lakes = doc.get("lakes") or []
    if doc.get("schema") != SCHEMA or doc.get("count") != len(lakes) or doc.get("digest") != _digest(lakes):
        raise LakeRegistryError("lake directory projection failed verification (schema, count or digest)")
    for r in lakes:
        if not (-90 <= r["lat"] <= 90 and -180 <= r["lon"] <= 180):
            raise LakeRegistryError(f"{r['lakeId']}: coordinate out of range")
    return {**doc, "release": {"releaseId": rel["releaseId"], "releaseDigest": rel["releaseDigest"], "approvalStatus": rel["approvalStatus"]}}


def _render(doc: dict) -> str:
    head = {k: v for k, v in doc.items() if k != "lakes"}
    body = ",\n".join("  " + json.dumps(r, separators=(", ", ": ")) for r in doc["lakes"])
    return json.dumps(head, indent=1)[:-2] + ',\n "lakes": [\n' + body + "\n ]\n}\n"


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    repo = os.path.abspath(os.path.join(RUNTIME, "..", "..", ".."))
    doc = project(open(os.path.join(repo, SOURCE_REL), encoding="utf-8").read())
    text = _render(doc)
    if "--write" in argv:
        open(PACKAGED, "w", encoding="utf-8").write(text)
        print(f"wrote {PACKAGED} ({doc['count']} lakes)")
        return 0
    current = open(PACKAGED, encoding="utf-8").read() if os.path.exists(PACKAGED) else ""
    if current != text:
        print("knowledge/lakes-directory.json is stale: run python -m moon_brain.lakes --write, then rebuild the release manifest")
        return 1
    print(f"ok ({doc['count']} lakes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
