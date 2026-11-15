#!/usr/bin/env python3
"""Wind's watchdog lake list (W-H3, Sector_Ops #51 decision D3): the 4 live Wind lakes PLUS every nationally profiled lake.

Wind writes lakes/{k}/profiles/wind for every lake in its national manifest, not only the 4 live lakes. The cycle watchdog trips PUBLISH_OUTSIDE_LAKES
on any Wind write for a lake not on its list, so the list must cover them. Decision D3: generate it from the Wind archive's national manifest
(fetch/national/MANIFEST.json, entries PASS/FLAGGED with a table, and in the canonical directory: exactly the lakes publish() profiles) and PIN it into
tools/ops/hybrid-stage/wind.json, so the list is explicit and reviewed. It is generated and pinned at flip time from the seeded Mac mini archive.

  python tools/ops/wind_watchdog_lakes.py --manifest FILE --directory FILE            # print the list (JSON)
  python tools/ops/wind_watchdog_lakes.py --manifest FILE --directory FILE --write    # pin it into the staged fragment (a reviewed PR)
  python tools/ops/wind_watchdog_lakes.py --manifest FILE --directory FILE --check    # exit 1 if the pinned list differs

--directory is the Engine's canonical lake directory (GET /lakes, saved to a file). No network, no database, no bucket. It only ever edits the
STAGED fragment, which no runtime reads; the list goes live only through hybrid_stage.py apply in Michael's flip PR.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
WIND_RUNTIME = os.path.join(ROOT, "brains", "wind", "runtime")
STAGE = os.path.join(HERE, "hybrid-stage", "wind.json")
for p in (WIND_RUNTIME, os.path.join(ROOT, "jobs", "brain_platform")):
    if p not in sys.path:
        sys.path.insert(0, p)

from sector_wind.brain.lakes import WIND_LAKE_IDS, check_keys, national_profiled   # noqa: E402


def lake_list(manifest: dict | None, directory: list[dict]) -> list[str]:
    """Sorted RTDB lake keys: the live Wind lakes + the nationally profiled lakes. Refuses a live lake missing from the directory."""
    keys = check_keys(directory)
    missing = [lid for lid in WIND_LAKE_IDS.values() if lid not in keys]
    if missing:
        raise ValueError(f"live Wind lakes missing from the canonical directory: {missing}")
    lids = set(WIND_LAKE_IDS.values()) | set(national_profiled(manifest, directory))
    return sorted(keys[lid] for lid in lids)


def _load(path: str):
    with open(path) as fh:
        return json.load(fh)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", required=True, help="the Wind archive's fetch/national/MANIFEST.json (a local file)")
    ap.add_argument("--directory", required=True, help="the canonical lake directory: GET /lakes saved to a file (its 'lakes' list, or the list itself)")
    ap.add_argument("--stage", default=STAGE, help=argparse.SUPPRESS)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="pin the list into the staged wind.json fragment")
    g.add_argument("--check", action="store_true", help="exit 1 if the staged fragment's list differs")
    a = ap.parse_args(argv)
    d = _load(a.directory)
    directory = d.get("lakes") if isinstance(d, dict) else d
    if not isinstance(directory, list) or not directory:
        print("REFUSED: --directory has no lakes", file=sys.stderr)
        return 2
    try:
        lakes = lake_list(_load(a.manifest), directory)
    except ValueError as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    stage = _load(a.stage)
    pinned = list(stage.get("watchdog", {}).get("lakes") or [])
    if a.check:
        if pinned != lakes:
            print(f"DIFFERS: pinned {len(pinned)} lakes, generated {len(lakes)}; "
                  f"added {sorted(set(lakes) - set(pinned))}, removed {sorted(set(pinned) - set(lakes))}", file=sys.stderr)
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
