#!/usr/bin/env python3
"""Write or check a Brain's packaged knowledge-release manifest (sector_brain_platform.knowledge_release).

  python3 tools/knowledge/build_release_manifest.py brains/wind/runtime --check     # exit 1 if any file or the digest drifted
  python3 tools/knowledge/build_release_manifest.py brains/wind/runtime --write --release-id wind-knowledge-YYYY-MM-DD.N

--write keeps the brainId, owner, store, approval and file list of the existing manifest and recomputes digests; a new releaseId is required
whenever the content changes (a release is immutable). Writing a manifest does NOT approve or promote anything: the approval block is copied
as it is, and promotion into production is a separate, gated decision.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "jobs", "brain_platform"))
from sector_brain_platform import knowledge_release as K  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("release_dir")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--write", action="store_true")
    ap.add_argument("--release-id")
    a = ap.parse_args(argv)
    mpath = os.path.join(a.release_dir, K.MANIFEST)
    m = json.load(open(mpath, encoding="utf-8"))
    files = K.describe_files(a.release_dir, [f["path"] for f in m["files"]])
    fresh = dict(m, files=files, releaseDigest=K.release_digest(files))
    if a.check:
        if fresh != m:
            print(f"{mpath}: DRIFT (a packaged knowledge file changed: regenerate with --write and a NEW --release-id)")
            return 1
        K.load_release(a.release_dir, m["brainId"])
        print(f"{mpath}: OK {m['releaseId']} {m['releaseDigest']}")
        return 0
    if m.get("releaseDigest") and fresh["releaseDigest"] != m["releaseDigest"]:     # an existing release changed: it needs a new id
        if not a.release_id or a.release_id == m.get("releaseId"):
            print("content changed: pass a NEW --release-id (releases are immutable)")
            return 2
        fresh["releaseId"] = a.release_id
    elif not m.get("releaseDigest") and a.release_id:
        fresh["releaseId"] = a.release_id                                             # first write of a new manifest (never renames a release)
    open(mpath, "w", encoding="utf-8").write(json.dumps(fresh, indent=2) + "\n")
    print(f"wrote {mpath}: {fresh['releaseId']} {fresh['releaseDigest']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
