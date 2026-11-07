"""Merge one local TVA archive into another, losing nothing (Sector_Ops #51: the archive moves from the MacBook to Pulse on the Mac mini).

  python3 merge_archive.py --src <old>/archive --dst <new>/archive [--label macbook] [--dry-run]

Both trees have the layout archive.py writes (`water-temp/tva/raw/...` and `water-temp/tva/<DAM>/<YYYY-MM-DD>.json`). The archive's own rules
apply: an observed hour already in `dst` is never overwritten; a different value for that hour from `src` becomes a revision (as a later
fetch would); `src` revisions and predicted fetches are added when missing; raw response files are copied create-only (an existing
`dst` file is kept, and a differing one is reported). Running it twice changes nothing the second time. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys


def _load(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def merge_day(src: dict, dst: dict, label: str) -> dict:
    """Merge src into dst in place. Returns counts."""
    n = {"observedAdded": 0, "revisionsAdded": 0, "predictedAdded": 0}
    for k in ("dam", "localDate"):
        if src.get(k) != dst.get(k):
            raise ValueError(f"day files disagree on {k}: {src.get(k)!r} vs {dst.get(k)!r}")
    dst.setdefault("observed", {})
    dst.setdefault("revisions", [])
    dst.setdefault("predicted", {})

    def has_revision(hour, raw):
        return any(r.get("hour") == hour and r.get("raw") == raw for r in dst["revisions"])

    for hour, entry in sorted((src.get("observed") or {}).items()):
        cur = dst["observed"].get(hour)
        if cur is None:
            dst["observed"][hour] = dict(entry)
            n["observedAdded"] += 1
        elif cur.get("raw") != entry.get("raw") and not has_revision(hour, entry.get("raw")):
            dst["revisions"].append({"hour": hour, "raw": entry.get("raw"), "parsed": entry.get("parsed"),
                                     "seenAt": entry.get("firstSeenAt"), "mergedFrom": label})
            n["revisionsAdded"] += 1
    for rev in src.get("revisions") or []:
        if not has_revision(rev.get("hour"), rev.get("raw")):
            dst["revisions"].append({**rev, "mergedFrom": label})
            n["revisionsAdded"] += 1
    for key, pred in sorted((src.get("predicted") or {}).items()):
        if key not in dst["predicted"]:
            dst["predicted"][key] = pred
            n["predictedAdded"] += 1
    return n


def merge_tree(src_root: str, dst_root: str, label: str = "src", dry_run: bool = False) -> dict:
    totals = {"rawCopied": 0, "rawSame": 0, "rawDiffering": [], "daysNew": 0, "daysMerged": 0,
              "observedAdded": 0, "revisionsAdded": 0, "predictedAdded": 0}
    for dirpath, _dirs, files in os.walk(src_root):
        for name in sorted(files):
            if not name.endswith(".json"):
                continue
            sp = os.path.join(dirpath, name)
            rel = os.path.relpath(sp, src_root)
            dp = os.path.join(dst_root, rel)
            is_raw = f"{os.sep}raw{os.sep}" in f"{os.sep}{rel}"
            if is_raw:
                if not os.path.exists(dp):
                    totals["rawCopied"] += 1
                    if not dry_run:
                        os.makedirs(os.path.dirname(dp), exist_ok=True)
                        with open(sp, "rb") as a, open(dp, "xb") as b:
                            b.write(a.read())
                else:
                    with open(sp, "rb") as a, open(dp, "rb") as b:
                        if a.read() == b.read():
                            totals["rawSame"] += 1
                        else:
                            totals["rawDiffering"].append(rel)      # kept as it is in dst (create-only)
                continue
            src = _load(sp)
            if not os.path.exists(dp):
                totals["daysNew"] += 1
                totals["observedAdded"] += len(src.get("observed") or {})
                totals["revisionsAdded"] += len(src.get("revisions") or [])
                totals["predictedAdded"] += len(src.get("predicted") or {})
                if not dry_run:
                    os.makedirs(os.path.dirname(dp), exist_ok=True)
                    with open(dp, "x", encoding="utf-8") as fh:
                        json.dump(src, fh, indent=1, sort_keys=True)
                continue
            dst = _load(dp)
            counts = merge_day(src, dst, label)
            if any(counts.values()):
                totals["daysMerged"] += 1
                for k, v in counts.items():
                    totals[k] += v
                if not dry_run:
                    tmp = dp + ".merge-tmp"
                    with open(tmp, "w", encoding="utf-8") as fh:
                        json.dump(dst, fh, indent=1, sort_keys=True)
                    os.replace(tmp, dp)
    return totals


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--label", default="src", help="recorded as mergedFrom on revisions taken from src")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    for p in (a.src, a.dst):
        if not os.path.isdir(p):
            print(f"not a directory: {p}", file=sys.stderr)
            return 2
    out = merge_tree(a.src, a.dst, a.label, a.dry_run)
    out["rawDifferingCount"] = len(out["rawDiffering"])
    out["rawDiffering"] = out["rawDiffering"][:20]
    print(json.dumps({"dryRun": a.dry_run, **out}, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
