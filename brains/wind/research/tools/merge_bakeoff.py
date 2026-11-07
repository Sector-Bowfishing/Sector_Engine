"""Merge the MacBook's provider bake-off folder into the Mac mini's (Sector_Ops #51), losing nothing.

  python3 merge_bakeoff.py --src <macbook active> --dst <mini job-data/wind-bakeoff/active> [--label macbook] [--dry-run] [--any-minute]

The collector writes two kinds of files (provider_bakeoff.py):
  - files written once per cycle (raw/, observations archives, inventories): copied create-only; one that exists in dst with other
    bytes is kept aside in <dst>/merged/<label>/<path>, never discarded;
  - append-only line files (*.jsonl): every src line (the older machine), then the dst lines src lacks; repeats within one side are kept.
    On the hand-over day both machines appended to the same day file, which is exactly what this joins. Logs (*.log) are copied whole.
Run it while the collector job is NOT running: pause it; the tool refuses between minute 17 and 50 of the hour (the job starts at :20 and
takes up to about 20 min) unless --any-minute. Idempotent. Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

LINE_FILES = (".jsonl",)          # logs (*.log) are copied whole like any once-written file: repeated lines there are history


def _lines(p):
    with open(p, "rb") as fh:
        data = fh.read()
    lines = data.split(b"\n")
    if lines and lines[-1] == b"":
        lines.pop()
    return lines


def merge_lines(src: list[bytes], dst: list[bytes]) -> list[bytes]:
    """Every src line as it is (repeats kept), then the dst lines src lacks (in dst order, repeats kept)."""
    have = set(src)
    return list(src) + [line for line in dst if line not in have]


def merge_tree(src_root: str, dst_root: str, label: str = "src", dry_run: bool = False) -> dict:
    t = {"copied": 0, "same": 0, "keptAside": 0, "lineFilesMerged": 0, "linesAdded": 0, "lineFilesNew": 0}
    for dirpath, dirs, files in os.walk(src_root):
        dirs[:] = [d for d in dirs if not (dirpath == src_root and d == "merged")]
        for name in sorted(files):
            sp = os.path.join(dirpath, name)
            rel = os.path.relpath(sp, src_root)
            dp = os.path.join(dst_root, rel)
            if name.endswith(".merge-tmp"):
                continue
            if name.endswith(LINE_FILES):
                src = _lines(sp)
                if not os.path.exists(dp):
                    t["lineFilesNew"] += 1
                    t["linesAdded"] += len(src)
                    merged = src
                else:
                    dst = _lines(dp)
                    merged = merge_lines(src, dst)
                    if merged == dst:
                        t["same"] += 1
                        continue
                    t["lineFilesMerged"] += 1
                    t["linesAdded"] += len(merged) - len(dst)
                if not dry_run:
                    os.makedirs(os.path.dirname(dp), exist_ok=True)
                    tmp = dp + ".merge-tmp"
                    with open(tmp, "wb") as fh:
                        fh.write(b"\n".join(merged) + (b"\n" if merged else b""))
                    os.replace(tmp, dp)
                continue
            if not os.path.exists(dp):
                t["copied"] += 1
                if not dry_run:
                    os.makedirs(os.path.dirname(dp), exist_ok=True)
                    with open(sp, "rb") as a, open(dp, "xb") as b:
                        b.write(a.read())
                continue
            with open(sp, "rb") as a, open(dp, "rb") as b:
                if a.read() == b.read():
                    t["same"] += 1
                    continue
            t["keptAside"] += 1
            side = os.path.join(dst_root, "merged", label, rel)
            if not dry_run and not os.path.exists(side):
                os.makedirs(os.path.dirname(side), exist_ok=True)
                with open(sp, "rb") as a, open(side, "xb") as b:
                    b.write(a.read())
    return t


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--label", default="src")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--any-minute", action="store_true")
    a = ap.parse_args(argv)
    for p in (a.src, a.dst):
        if not os.path.isdir(p):
            print(f"not a directory: {p}", file=sys.stderr)
            return 2
    minute = dt.datetime.now(dt.timezone.utc).minute
    if not a.dry_run and not a.any_minute and 17 <= minute <= 50:
        print(f"refusing: minute {minute} is inside :17-:50, when the hourly collector may be writing. Pause it, then retry after :50.",
              file=sys.stderr)
        return 3
    print(json.dumps({"dryRun": a.dry_run, **merge_tree(a.src, a.dst, a.label, a.dry_run)}, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
