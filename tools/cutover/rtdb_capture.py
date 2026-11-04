#!/usr/bin/env python3
"""Read-only baseline capture of Brain RTDB paths (cutover gate G5; Lake step B3, Sector_Ops #48).

GET only. The token comes from $BRAIN_ACCESS_TOKEN (a read-only identity's 1-hour token) and is never printed or stored. The capture holds live
data, so it is written OUTSIDE any git checkout (this repository is public) and never committed.

  python tools/cutover/rtdb_capture.py --brain lake-brain --out DIR [--rtdb URL]

Writes DIR/capture.json ({path: value}) and DIR/MANIFEST.json (paths, time, sha256 of capture.json). Exit 2 = refused, nothing written.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "jobs", "brain_platform"))

from sector_brain_platform.keys import lake_key            # noqa: E402

RTDB_URL = "https://sector-brain.firebaseio.com"
LAKE_PILOTS = ("Guntersville|AL", "Wheeler|AL", "Wilson|AL", "Pickwick Lake|TN", "Lake Hartwell|SC")   # LakeSourceBindings.handWritten


def lake_paths() -> list[str]:
    """What Lake writes for the pilots (whole lake and fleet nodes, so every consumer slot is in the baseline too), plus its registry/sources."""
    from sector_brain_platform.publisher.registry import LAKE, _owned_sources
    out = ["schemaVersion", "activity", f"brains/{LAKE}", f"validation/{LAKE}", f"health/brains/{LAKE}"]   # the job reads /activity whole (rehearsal 2026-11-04)
    for lid in LAKE_PILOTS:
        k = lake_key(lid)
        out += [f"lakes/{k}", f"lakeFleet/{k}", f"snapshots/{k}/latest"]
    for sid in sorted(_owned_sources(LAKE)):
        out += [f"sources/{sid}", f"health/sources/{sid}"]
    return out


PATHS = {"lake-brain": lake_paths}


def inside_git(path: str) -> bool:
    d = os.path.abspath(path)
    while not os.path.isdir(d):
        d = os.path.dirname(d)
    return subprocess.run(["git", "-C", d, "rev-parse", "--show-toplevel"], capture_output=True).returncode == 0


def get(url: str, path: str, token: str, timeout: int = 30):
    req = urllib.request.Request(f"{url.rstrip('/')}/{urllib.parse.quote(path)}.json", headers={"Authorization": f"Bearer {token}"}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def main(argv=None, fetch=get) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--brain", required=True, choices=sorted(PATHS))
    ap.add_argument("--out", required=True)
    ap.add_argument("--rtdb", default=RTDB_URL)
    a = ap.parse_args(argv)
    token = os.environ.get("BRAIN_ACCESS_TOKEN")
    if not token:
        print("REFUSED: set BRAIN_ACCESS_TOKEN to a read-only token", file=sys.stderr)
        return 2
    u = urllib.parse.urlparse(a.rtdb)
    if u.scheme != "https" or not (u.hostname or "").endswith(".firebaseio.com"):
        print("REFUSED: --rtdb must be an https://*.firebaseio.com database (the token is sent to it)", file=sys.stderr)
        return 2
    if inside_git(a.out):
        print(f"REFUSED: {a.out} is inside a git checkout; a capture holds live data and must stay private", file=sys.stderr)
        return 2
    if os.path.exists(os.path.join(a.out, "capture.json")):
        print(f"REFUSED: {a.out} already holds a capture (captures are never overwritten)", file=sys.stderr)
        return 2
    paths = PATHS[a.brain]()
    capture = {p: fetch(a.rtdb, p, token) for p in paths}
    os.makedirs(a.out, mode=0o700, exist_ok=True)
    body = json.dumps(capture, indent=1, sort_keys=True, ensure_ascii=False).encode()
    manifest = {"schema": "sector-rtdb-capture-v1", "brain": a.brain, "rtdb": a.rtdb, "capturedAt": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "paths": paths, "absent": [p for p, v in capture.items() if v is None], "sha256": hashlib.sha256(body).hexdigest()}
    old = os.umask(0o077)                                    # live data: readable by the owner only
    try:
        open(os.path.join(a.out, "capture.json"), "wb").write(body)
        json.dump(manifest, open(os.path.join(a.out, "MANIFEST.json"), "w"), indent=1)
    finally:
        os.umask(old)
    print(json.dumps({k: manifest[k] for k in ("brain", "capturedAt", "sha256")} | {"paths": len(paths), "absent": len(manifest["absent"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
