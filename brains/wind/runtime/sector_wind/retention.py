"""Wind archive retention on a runner's LOCAL store (Wind cutover plan, Sector_Ops #51). DRY RUN by default.

The local Wind archive grows every hour and was never pruned. Rule (plan, "Retention"):
  * PRUNE raw forcing cutouts older than --keep-days (default 30), dated by the key itself, not the file time:
      nbm/<lake>/<YYYYMMDDHH>.json.gz   rtma/<lake>/<YYYYMMDD>/<HHMM>.json.gz   nbm-points/<YYYYMMDDHH>.json.gz
  * the NEWEST file of each series (nbm per lake, rtma per lake, nbm-points) is never pruned, however old: a stalled ingest keeps its last input;
  * KEEP everything else forever: fetch tables and manifests (fetch/), Wind's derived state (brain/, latest/), grids/, metar/ (truth for the
    7-day comparison and validation), runs/ and the ledger.

  python main.py retention --store local:DIR [--keep-days 30] [--now ISO] [--apply]

Without --apply it only lists what it would delete. Local stores only (a bucket archive is refused). It deletes files only under the three raw
prefixes, and empty folders left behind there. Running it on a schedule (a runner maintenance job) is a separate owner step.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

SERIES = (
    (re.compile(r"^nbm/(?P<series>[^/]+)/(?P<t>\d{10})\.json\.gz$"), "%Y%m%d%H"),
    (re.compile(r"^rtma/(?P<series>[^/]+)/(?P<d>\d{8})/(?P<hm>\d{4})\.json\.gz$"), "%Y%m%d%H%M"),
    (re.compile(r"^nbm-points/(?P<t>\d{10})\.json\.gz$"), "%Y%m%d%H"),
)
RAW_PREFIXES = ("nbm/", "rtma/", "nbm-points/")


def _classify(key: str):
    """(series id, datetime) for a raw cutout key, else None (kept forever)."""
    for rx, fmt in SERIES:
        m = rx.match(key)
        if not m:
            continue
        g = m.groupdict()
        stamp = g["t"] if "t" in g else g["d"] + g["hm"]
        try:
            t = datetime.strptime(stamp, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
        return f"{key.split('/', 1)[0]}/{g.get('series', '')}", t
    return None


def plan(keys: list[str], now: datetime, keep_days: int = 30) -> list[str]:
    """The keys to delete: raw cutouts older than keep_days, never the newest of a series. Pure (no I/O)."""
    if keep_days < 1:
        raise ValueError("keep_days must be at least 1")
    cutoff = now - timedelta(days=keep_days)
    series: dict[str, list[tuple[datetime, str]]] = {}
    for k in keys:
        c = _classify(k)
        if c:
            series.setdefault(c[0], []).append((c[1], k))
    out = []
    for items in series.values():
        items.sort()
        out += [k for t, k in items[:-1] if t < cutoff]          # the newest of each series is always kept
    return sorted(out)


def _keys(root: str) -> list[str]:
    out = []
    for pre in RAW_PREFIXES:
        base = os.path.join(root, pre)
        for dp, _, fs in os.walk(base):
            for f in fs:
                if not f.endswith(".tmp"):
                    out.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
    return sorted(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--store", required=True, help="local:DIR (the runner's Wind archive)")
    ap.add_argument("--keep-days", type=int, default=30)
    ap.add_argument("--now", default=None, help="ISO-8601 UTC (default: now)")
    ap.add_argument("--apply", action="store_true", help="really delete (default: list only)")
    a = ap.parse_args(argv)
    if not a.store.startswith("local:"):
        print("REFUSED: --store must be local:DIR (a bucket archive is never pruned here)", file=sys.stderr)
        return 2
    root = os.path.abspath(a.store.removeprefix("local:"))
    if not os.path.isdir(root):
        print(f"REFUSED: {root} is not a folder", file=sys.stderr)
        return 2
    try:
        now = (datetime.strptime(a.now, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) if a.now else datetime.now(timezone.utc))
        doomed = plan(_keys(root), now, a.keep_days)
    except ValueError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    freed = 0
    for k in doomed:
        p = os.path.join(root, k)
        freed += os.path.getsize(p)
        if a.apply:
            os.remove(p)
    if a.apply:
        for pre in RAW_PREFIXES:                                  # empty folders left behind, raw prefixes only
            for dp, dns, fs in os.walk(os.path.join(root, pre), topdown=False):
                if dp != os.path.join(root, pre) and not os.listdir(dp):
                    os.rmdir(dp)
    print(json.dumps({"applied": a.apply, "files": len(doomed), "bytes": freed, "keepDays": a.keep_days, "sample": doomed[:5]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
