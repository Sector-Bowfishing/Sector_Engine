#!/usr/bin/env python3
"""Sector Intelligence's watchdog lake list (Sector_Ops #51, owner decision SI-WD (a), 2026-11-16): every lake in the Engine's /lakes directory.

Sector Intelligence writes lakes/{k}/states/intelligence and lakeFleet/{k}/slots/intelligence for EVERY lake the Engine's GET /lakes returns
(brains/sector-intelligence/runtime/run.py). The cycle watchdog trips PUBLISH_OUTSIDE_LAKES on any write for a lake not on the Brain's list, so the
list must be the whole directory. SI-WD (a), the same pattern as Wind's D3 (tools/ops/wind_watchdog_lakes.py): generate the list from the canonical
directory and PIN it into tools/ops/hybrid-stage/sector-intelligence.json, so it is explicit and reviewed. Pinned in the flip PR from the Engine's
directory golden; si-pulse.sh re-checks it against the live GET /lakes at flip time and refuses on any difference.

  python tools/ops/si_watchdog_lakes.py --directory FILE            # print the list (JSON)
  python tools/ops/si_watchdog_lakes.py --directory FILE --write    # pin it into the staged fragment (a reviewed PR)
  python tools/ops/si_watchdog_lakes.py --directory FILE --check    # exit 1 if the pinned list differs

--directory is GET /lakes saved to a file (its 'lakes' list of {id: ...}, or the list itself), or the Engine's directory golden
(verification/fixtures/lakes/lakes_directory.golden.json: its 'orderedLakeIds'). No network, no database, no bucket. It only ever edits the STAGED
fragment, which no runtime reads; the list goes live only through hybrid_stage.py apply in Michael's flip PR.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
STAGE = os.path.join(HERE, "hybrid-stage", "sector-intelligence.json")
GOLDEN = os.path.join(ROOT, "verification", "fixtures", "lakes", "lakes_directory.golden.json")
PLATFORM = os.path.join(ROOT, "jobs", "brain_platform")
if PLATFORM not in sys.path:
    sys.path.insert(0, PLATFORM)

from sector_brain_platform.keys import lake_keys   # noqa: E402


def directory_ids(doc) -> list[str]:
    """Lake ids from a GET /lakes response, its 'lakes' list, or the directory golden's orderedLakeIds."""
    if isinstance(doc, dict) and isinstance(doc.get("orderedLakeIds"), list):
        ids = doc["orderedLakeIds"]
    else:
        rows = doc.get("lakes") if isinstance(doc, dict) else doc
        if not isinstance(rows, list):
            raise ValueError("--directory has no 'lakes' list and no 'orderedLakeIds'")
        ids = [r["id"] if isinstance(r, dict) else r for r in rows]
    if not ids or not all(isinstance(i, str) and i for i in ids):
        raise ValueError("--directory has no lakes")
    if len(set(ids)) != len(ids):
        raise ValueError("--directory repeats a lake id")
    return ids


def lake_list(doc) -> list[str]:
    """Sorted RTDB lake keys for the whole directory. Refuses (raises) on a key collision, as the Brain's own run does."""
    return sorted(lake_keys(directory_ids(doc)).values())


def _load(path: str):
    with open(path) as fh:
        return json.load(fh)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--directory", default=GOLDEN, help="GET /lakes saved to a file, or the directory golden (default)")
    ap.add_argument("--stage", default=STAGE, help=argparse.SUPPRESS)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="pin the list into the staged sector-intelligence.json fragment")
    g.add_argument("--check", action="store_true", help="exit 1 if the staged fragment's list differs")
    a = ap.parse_args(argv)
    try:
        lakes = lake_list(_load(a.directory))
    except (ValueError, KeyError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    stage = _load(a.stage)
    pinned = list(stage.get("watchdog", {}).get("lakes") or [])
    if a.check:
        if pinned != lakes:
            print(f"DIFFERS: pinned {len(pinned)} lakes, generated {len(lakes)}; "
                  f"added {sorted(set(lakes) - set(pinned))[:20]}, removed {sorted(set(pinned) - set(lakes))[:20]}", file=sys.stderr)
            return 1
        print(f"OK: {len(lakes)} lakes pinned")
        return 0
    if a.write:
        stage.setdefault("watchdog", {})["lakes"] = lakes
        with open(a.stage, "w") as fh:
            json.dump(stage, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"pinned {len(lakes)} lakes into {os.path.relpath(a.stage, ROOT)}")
        return 0
    print(json.dumps(lakes, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
