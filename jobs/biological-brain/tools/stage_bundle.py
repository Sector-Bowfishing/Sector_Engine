"""Stage a NEW private bundle release locally: an existing release plus extra artifacts (rules, register, pilot state).

It never uploads anything. Publishing a staged bundle to the private bucket, and then the Brain RTDB, are separate approved steps.
The staged release is verified by loading it with the same fail-closed loader the publisher uses.

  from tools.stage_bundle import stage
  stage(source_release_dir, out_root, "2026-10-13.1", extra_files={"rules/x.json": b"..."}, manifest_patch={...})
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import biological_brain as bb      # noqa: E402


def stage(source_release_dir: str, out_root: str, new_version: str, *, extra_files: dict[str, bytes] | None = None,
          drop_prefixes: tuple = (), manifest_patch: dict | None = None, now: dt.datetime | None = None) -> bb.Bundle:
    now = now or dt.datetime.now(dt.timezone.utc)
    man = json.load(open(os.path.join(source_release_dir, "manifest.json")))
    rel = f"releases/{new_version}"
    dest = os.path.join(out_root, rel)
    os.makedirs(dest, exist_ok=True)
    files, seen = [], set()
    for f in man["files"]:
        if f["path"].startswith(drop_prefixes):
            continue
        raw = open(os.path.join(source_release_dir, f["path"]), "rb").read()
        if hashlib.sha256(raw).hexdigest() != f["sha256"]:
            raise bb.BundleError(f"source artifact hash mismatch: {f['path']}")
        os.makedirs(os.path.dirname(os.path.join(dest, f["path"])), exist_ok=True)
        open(os.path.join(dest, f["path"]), "wb").write(raw)
        files.append(dict(f))
        seen.add(f["path"])
    for path, raw in sorted((extra_files or {}).items()):
        if path in seen:
            raise bb.BundleError(f"extra file would overwrite a source artifact: {path}")
        os.makedirs(os.path.dirname(os.path.join(dest, path)), exist_ok=True)
        open(os.path.join(dest, path), "wb").write(raw)
        files.append(dict(path=path, sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw), visibility="private"))
    new = dict(man)
    new.update(researchVersion=new_version, createdAt=now.strftime("%Y-%m-%dT%H:%M:%SZ"), files=files)
    new["storage"] = dict(man.get("storage", {}), prefix=f"biology/v1/{rel}")
    new.update(manifest_patch or {})
    mraw = json.dumps(new, indent=1, sort_keys=True).encode()
    open(os.path.join(dest, "manifest.json"), "wb").write(mraw)
    json.dump(dict(schemaVersion=1, brainId=bb.BRAIN_ID, researchVersion=new_version, manifest=f"{rel}/manifest.json",
                   manifestSha256=hashlib.sha256(mraw).hexdigest(), publishedAt=new["createdAt"], staged=True),
              open(os.path.join(out_root, "latest.json"), "w"), indent=1)

    def read(p):
        return open(os.path.join(out_root, p), "rb").read()
    return bb.load_bundle(read)
