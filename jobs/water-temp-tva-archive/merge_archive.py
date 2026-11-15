"""Merge one local TVA archive into another, losing nothing (Sector_Ops #51: the archive moves from the MacBook to Pulse on the Mac mini).

  python3 merge_archive.py --src <old>/archive --dst <new>/archive [--label macbook] [--dry-run] [--any-minute]

Both trees have the layout archive.py writes (`water-temp/tva/raw/...` and `water-temp/tva/<DAM>/<YYYY-MM-DD>.json`). The archive's own rules
apply, and nothing from `src` is ever dropped:
  - an observed hour already in `dst` is never overwritten; a different `src` value for it becomes a revision (as a later fetch would), unless
    it equals the observed value or a revision already there; the earliest `firstSeenAt` of the two is kept;
  - `src` revisions and predicted fetches are added when missing; revisions stay in time order;
  - raw response files are copied create-only;
  - anything that differs and cannot be added under the archive's rules (a raw file with other bytes, a predicted fetch with other rows) is
    kept beside the archive in `water-temp/tva-merged/<label>/...`, never discarded, and counted.
Running it twice changes nothing the second time. A file that can't be read is reported and skipped (the run continues; exit 1).

**Run it while the archive job is NOT running**: pause the job first (the Mac mini steps do), and the tool refuses to start between minute
17 and 32 of the hour (the job runs at :20) unless --any-minute is given. Stdlib only.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

SIDE = "tva-merged"          # sibling of the archive's "tva" prefix: water-temp/tva-merged/<label>/...


def _load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(p, obj, *, create_only=False):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".merge-tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=1, sort_keys=True)
    if create_only and os.path.exists(p):
        os.remove(tmp)
        raise FileExistsError(p)
    os.replace(tmp, p)


def _write_bytes(p, data, *, create_only=True):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "xb" if create_only else "wb") as fh:
        fh.write(data)


def side_path(dst_root: str, rel: str, label: str) -> str:
    """water-temp/tva/<rest> -> water-temp/tva-merged/<label>/<rest> (any other layout: <dst>/tva-merged/<label>/<rel>)."""
    parts = rel.split(os.sep)
    if len(parts) >= 2 and parts[1] == "tva":
        return os.path.join(dst_root, parts[0], SIDE, label, *parts[2:])
    return os.path.join(dst_root, SIDE, label, rel)


def merge_day(src: dict, dst: dict, label: str) -> tuple[dict, dict]:
    """Merge src into dst in place. -> (counts, kept_aside): kept_aside holds predicted fetches that differ from dst's."""
    n = {"observedAdded": 0, "revisionsAdded": 0, "predictedAdded": 0, "firstSeenEarlier": 0, "predictedDiffering": 0}
    for k in ("dam", "localDate"):
        if src.get(k) != dst.get(k):
            raise ValueError(f"day files disagree on {k}: {src.get(k)!r} vs {dst.get(k)!r}")
    dst.setdefault("observed", {})
    dst.setdefault("revisions", [])
    dst.setdefault("predicted", {})

    def known(hour, raw):
        cur = dst["observed"].get(hour)
        return (cur is not None and cur.get("raw") == raw) or any(r.get("hour") == hour and r.get("raw") == raw for r in dst["revisions"])

    for hour, entry in sorted((src.get("observed") or {}).items()):
        cur = dst["observed"].get(hour)
        if cur is None:
            dst["observed"][hour] = dict(entry)
            n["observedAdded"] += 1
            continue
        if cur.get("raw") == entry.get("raw"):
            a, b = entry.get("firstSeenAt"), cur.get("firstSeenAt")
            if a and (not b or a < b):                         # the same value, seen earlier by src
                cur["firstSeenAt"] = a
                n["firstSeenEarlier"] += 1
        elif not known(hour, entry.get("raw")):
            dst["revisions"].append({"hour": hour, "raw": entry.get("raw"), "parsed": entry.get("parsed"),
                                     "seenAt": entry.get("firstSeenAt"), "mergedFrom": label})
            n["revisionsAdded"] += 1
    for rev in src.get("revisions") or []:
        if not known(rev.get("hour"), rev.get("raw")):
            dst["revisions"].append({**rev, "mergedFrom": label})
            n["revisionsAdded"] += 1
    dst["revisions"].sort(key=lambda r: (r.get("seenAt") or "", r.get("hour") or ""))
    aside = {}
    for key, pred in sorted((src.get("predicted") or {}).items()):
        if key not in dst["predicted"]:
            dst["predicted"][key] = pred
            n["predictedAdded"] += 1
        elif dst["predicted"][key] != pred:
            aside[key] = pred
            n["predictedDiffering"] += 1
    return n, aside


def merge_tree(src_root: str, dst_root: str, label: str = "src", dry_run: bool = False) -> dict:
    t = {"rawCopied": 0, "rawSame": 0, "rawDiffering": 0, "daysNew": 0, "daysMerged": 0, "observedAdded": 0, "revisionsAdded": 0,
         "predictedAdded": 0, "predictedDiffering": 0, "firstSeenEarlier": 0, "keptAside": [], "unreadable": []}
    for dirpath, dirs, files in os.walk(src_root):
        dirs[:] = [d for d in dirs if d != SIDE]                  # never re-merge a side folder
        for name in sorted(files):
            if not name.endswith(".json"):
                continue
            sp = os.path.join(dirpath, name)
            rel = os.path.relpath(sp, src_root)
            dp = os.path.join(dst_root, rel)
            if f"{os.sep}raw{os.sep}" in f"{os.sep}{rel}":
                with open(sp, "rb") as fh:
                    data = fh.read()
                if not os.path.exists(dp):
                    t["rawCopied"] += 1
                    if not dry_run:
                        _write_bytes(dp, data)
                    continue
                with open(dp, "rb") as fh:
                    same = fh.read() == data
                if same:
                    t["rawSame"] += 1
                    continue
                t["rawDiffering"] += 1
                side = side_path(dst_root, rel, label)
                t["keptAside"].append(os.path.relpath(side, dst_root))
                if not dry_run and not os.path.exists(side):
                    _write_bytes(side, data)
                continue
            try:
                src = _load(sp)
            except (OSError, ValueError) as e:
                t["unreadable"].append({"side": "src", "file": rel, "error": type(e).__name__})
                continue
            if not os.path.exists(dp):
                t["daysNew"] += 1
                t["observedAdded"] += len(src.get("observed") or {})
                t["revisionsAdded"] += len(src.get("revisions") or [])
                t["predictedAdded"] += len(src.get("predicted") or {})
                if not dry_run:
                    _write_json(dp, src, create_only=True)
                continue
            try:
                dst = _load(dp)
            except (OSError, ValueError) as e:
                t["unreadable"].append({"side": "dst", "file": rel, "error": type(e).__name__})   # left as it is for a person to look at
                continue
            counts, aside = merge_day(src, dst, label)
            if aside:
                side = side_path(dst_root, rel, label)
                t["keptAside"].append(os.path.relpath(side, dst_root))
                if not dry_run:
                    prev = _load(side) if os.path.exists(side) else {"dam": src.get("dam"), "localDate": src.get("localDate"), "predicted": {}}
                    prev["predicted"].update(aside)
                    _write_json(side, prev)
            if any(v for k, v in counts.items() if k != "predictedDiffering"):
                t["daysMerged"] += 1
                if not dry_run:
                    _write_json(dp, dst)
            for k, v in counts.items():
                t[k] += v
    return t


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--label", default="src", help="recorded as mergedFrom, and the side-folder name for anything kept aside")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--any-minute", action="store_true", help="skip the :17-:32 guard (only when the archive job is certainly stopped)")
    a = ap.parse_args(argv)
    for p in (a.src, a.dst):
        if not os.path.isdir(p):
            print(f"not a directory: {p}", file=sys.stderr)
            return 2
    minute = dt.datetime.now(dt.timezone.utc).minute
    if not a.dry_run and not a.any_minute and 17 <= minute <= 32:
        print(f"refusing: minute {minute} is inside :17-:32, when the hourly archive job may be writing. Pause it, then retry after :32.",
              file=sys.stderr)
        return 3
    out = merge_tree(a.src, a.dst, a.label, a.dry_run)
    out["keptAsideCount"] = len(out["keptAside"])
    print(json.dumps({"dryRun": a.dry_run, **out}, indent=1, sort_keys=True))
    return 1 if out["unreadable"] else 0


if __name__ == "__main__":
    sys.exit(main())
