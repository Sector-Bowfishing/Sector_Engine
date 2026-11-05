#!/usr/bin/env python3
"""Lake cutover rehearsal on a fake seeded from the baseline capture (gate G6; step B4, Sector_Ops #48). Local only, nothing is published.

1. Serve the B3 capture through the GET-only fake RTDB on 127.0.0.1 (any write attempt is refused and recorded).
2. Run Lake's artifact mode (`brains/lake/runtime/artifact_entry.py`) against it, with a LOCAL history archive and a LOCAL artifact folder.
3. Compare every mutation of the sealed artifact with the capture, ignoring Lake's registered volatile keys.

  python tools/cutover/lake_rehearsal.py --capture DIR --job PATH/LakeBrainJob --out DIR [--archive DIR] [--seed-archive gs://B] [--presence X] [--fault cwms-unreachable]

The verdict is a summary for the owner: DIFFERENCES_TO_EXPLAIN lists each non-volatile difference; ZERO_UNEXPLAINED needs none. A forced CWMS
failure is a second run with `--fault cwms-unreachable` (LakeBrainJob's dry-run-only fault), compared the same way: no lake may be blanked.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "jobs", "brain_platform"))

from fake_rtdb import FakeRTDB, Tree                              # noqa: E402


def volatile_keys() -> frozenset:
    from sector_brain_platform.publisher.registry import LAKE_VOLATILE_CONTRACT_V1
    return frozenset(LAKE_VOLATILE_CONTRACT_V1.keys)


def volatile_paths() -> tuple:
    """Lake's registered volatile path families (e.g. /brains/lake-brain/lastSuccessfulRun): a change there is expected every run."""
    from sector_brain_platform.publisher.registry import LAKE_VOLATILE_CONTRACT_V1
    return tuple(LAKE_VOLATILE_CONTRACT_V1.paths)


def strip(v, keys):
    if isinstance(v, dict):
        return {k: strip(x, keys) for k, x in v.items() if k not in keys}
    if isinstance(v, list):
        return [strip(x, keys) for x in v]
    return v


def mutations(artifact: dict) -> list[tuple[str, str, object]]:
    return [(m["path"], m.get("op"), m.get("value")) for s in artifact.get("sections") or [] for m in s.get("mutations") or []]


def compare(artifact: dict, capture: dict, keys=None, paths=None) -> dict:
    keys = volatile_keys() if keys is None else keys
    paths = volatile_paths() if paths is None else paths
    tree = Tree(capture)
    out = {"equal": 0, "volatileOnly": 0, "different": [], "notInCapture": [], "deletes": []}
    for path, op, value in mutations(artifact):
        p = path.strip("/")
        if str(op).upper() == "DELETE" or value is None:
            if tree.covered(p) and tree.get(p) is not None:
                out["deletes"].append(path)              # removing a value that exists now (a blanked lake is the first halt condition)
            continue
        if any(f.match("/" + p) for f in paths):
            out["volatileOnly"] += 1
            continue
        if not tree.covered(p):
            out["notInCapture"].append(path)
            continue
        before = tree.get(p)
        if before == value:
            out["equal"] += 1
        elif strip(before, keys) == strip(value, keys):
            out["volatileOnly"] += 1
        else:
            out["different"].append(path)
    out["verdict"] = "ZERO_UNEXPLAINED" if not (out["different"] or out["notInCapture"] or out["deletes"]) else "DIFFERENCES_TO_EXPLAIN"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--capture", required=True, help="the B3 capture folder (capture.json)")
    ap.add_argument("--job", required=True, help="built LakeBrainJob binary")
    ap.add_argument("--out", required=True)
    ap.add_argument("--archive", default=None, help="LOCAL history archive (default OUT/_archive); never a bucket")
    ap.add_argument("--seed-archive", default=None, help="read-only fallback archive (gs:// allowed: read only)")
    ap.add_argument("--presence", default=None, help="presence release location (private)")
    ap.add_argument("--fault", action="append", default=[], help="B4b: e.g. cwms-unreachable (dry-run fault injection in LakeBrainJob)")
    a = ap.parse_args(argv)
    archive = a.archive or os.path.join(a.out, "_archive")
    if archive.startswith("gs://"):
        print("REFUSED: --archive must be local; the job writes its history archive", file=sys.stderr)
        return 2
    capture = json.load(open(os.path.join(a.capture, "capture.json")))
    os.makedirs(a.out, exist_ok=True)
    art_dir = os.path.join(a.out, "artifacts")
    with FakeRTDB(capture) as fake:
        cmd = [sys.executable, os.path.join(REPO, "brains", "lake", "runtime", "artifact_entry.py"), "--job", a.job, "--scope", "pilots",
               "--read-rtdb", fake.url, "--archive", archive, "--artifact-dir", art_dir]
        cmd += (["--seed-archive", a.seed_archive] if a.seed_archive else []) + (["--presence", a.presence] if a.presence else [])
        cmd += [x for f in a.fault for x in ("--fault", f)]
        env = {k: v for k, v in os.environ.items() if k not in ("BRAIN_ACCESS_TOKEN", "SECTOR_BRAIN_ACCESS_TOKEN")}
        env["SECTOR_BRAIN_ACCESS_TOKEN"] = "rehearsal-fake"                       # the fake ignores it; no real database token reaches the job
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=1800)
        reads, uncovered, refused = list(fake.reads), sorted(fake.uncovered), list(fake.refused)
    open(os.path.join(a.out, "job.log"), "w").write(r.stdout + "\n--- stderr ---\n" + r.stderr)
    from sector_brain_platform.publisher.storage import LocalDirObjectStore
    store = LocalDirObjectStore(art_dir)
    found = [k for k in store.list("artifacts/lake-brain/") if k.endswith("/artifact.json")] if os.path.isdir(art_dir) else []
    report = {"faults": sorted(a.fault), "rehearsal": "B4b (fault injected)" if a.fault else "B4", "jobExit": r.returncode, "reads": len(reads), "readsOutsideCapture": uncovered, "writeAttemptsRefused": refused, "artifacts": len(found)}
    if len(found) == 1:
        report["comparison"] = compare(json.loads(store.get(found[0])), capture)
    report["verdict"] = ("REFUSED_WRITE" if refused else "READ_OUTSIDE_CAPTURE" if uncovered
                         else report.get("comparison", {}).get("verdict", "NO_ARTIFACT"))
    json.dump(report, open(os.path.join(a.out, "REHEARSAL.json"), "w"), indent=1)
    print(json.dumps({k: report[k] for k in ("faults", "jobExit", "reads", "artifacts", "verdict")} | {"readsOutsideCapture": len(uncovered)}))
    return 0 if report["verdict"] == "ZERO_UNEXPLAINED" else 1


if __name__ == "__main__":
    sys.exit(main())
