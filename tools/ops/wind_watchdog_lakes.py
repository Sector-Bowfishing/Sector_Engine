#!/usr/bin/env python3
"""Wind's watchdog lake list (W-H3, Sector_Ops #51 decision D3, corrected 2026-11-23): every lake in the Engine's /lakes directory.

D3 asked for the 4 live Wind lakes plus every nationally profiled lake (about 50), because Wind writes lakes/{k}/profiles/wind for each of them. That
list is necessary but NOT sufficient: publish() also writes lakeFleet/{k}/readiness/wind ("DISCOVERED") for EVERY lake in the canonical directory
(brains/wind/runtime/sector_wind/brain/publish.py, section 2), and the cycle watchdog's LAKE_PATH matches lakes|lakeFleet|snapshots/<k>/, so a
live+national list would still trip PUBLISH_OUTSIDE_LAKES on the first publish. The list that covers Wind's actual write set is the whole directory,
which contains D3's list (national_profiled only admits directory lakes). It is the same list, generated the same way, as Water Clarity, Water Temp
and Lake (tools/ops/brain_watchdog_lakes.py, owner direction 2026-11-20) and Sector Intelligence (SI-WD (a), which hit the same issue).

  python tools/ops/wind_watchdog_lakes.py [--directory FILE] [--manifest FILE]            # print the list (JSON)
  python tools/ops/wind_watchdog_lakes.py [--directory FILE] [--manifest FILE] --write    # pin it into the staged fragment (a reviewed PR)
  python tools/ops/wind_watchdog_lakes.py [--directory FILE] [--manifest FILE] --check    # exit 1 if the pinned list differs

--directory defaults to the Engine's directory golden (verification/fixtures/lakes/lakes_directory.golden.json); GET /lakes saved to a file also works
(the flip re-checks against the live directory). --manifest (the Wind archive's fetch/national/MANIFEST.json) is optional: with it the tool also
proves every nationally profiled lake (D3) is on the list. No network, no database, no bucket. It only ever edits the STAGED fragment, which no
runtime reads; the list goes live only through hybrid_stage.py apply in Michael's flip PR.
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

if HERE not in sys.path:
    sys.path.insert(0, HERE)
import si_watchdog_lakes as SL                                                       # noqa: E402

GOLDEN = SL.GOLDEN


def d3_lakes(manifest: dict | None, directory: list[dict]) -> list[str]:
    """D3's list as decided: the live Wind lakes + the nationally profiled lakes (what Wind writes under lakes/{k}/profiles/wind)."""
    keys = check_keys(directory)
    return sorted(keys[lid] for lid in set(WIND_LAKE_IDS.values()) | set(national_profiled(manifest, directory)))


def lake_list(manifest: dict | None, directory: list[dict]) -> list[str]:
    """Sorted RTDB lake keys of every directory lake (Wind writes lakeFleet/{k}/readiness/wind for each). Refuses a live Wind lake missing from the
    directory, and proves D3's list (live + national) is contained."""
    keys = check_keys(directory)
    missing = [lid for lid in WIND_LAKE_IDS.values() if lid not in keys]
    if missing:
        raise ValueError(f"live Wind lakes missing from the canonical directory: {missing}")
    out = sorted(set(keys.values()))
    outside = sorted(set(d3_lakes(manifest, directory)) - set(out))
    if outside:
        raise ValueError(f"D3 lakes outside the directory list: {outside}")
    return out


def load_directory(path: str) -> list[dict]:
    """GET /lakes saved to a file ({'lakes': [...]} or the list) or the directory golden ({'orderedLakeIds': [...]}) -> [{'id': ...}]."""
    return [{"id": lid} for lid in SL.directory_ids(_load(path))]


def _load(path: str):
    with open(path) as fh:
        return json.load(fh)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=None, help="optional: the Wind archive's fetch/national/MANIFEST.json, to prove the D3 lakes are covered")
    ap.add_argument("--directory", default=GOLDEN, help="the canonical lake directory: GET /lakes saved to a file, or the directory golden (default)")
    ap.add_argument("--stage", default=STAGE, help=argparse.SUPPRESS)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true", help="pin the list into the staged wind.json fragment")
    g.add_argument("--check", action="store_true", help="exit 1 if the staged fragment's list differs")
    a = ap.parse_args(argv)
    try:
        directory = load_directory(a.directory)
        if not directory:
            raise ValueError("--directory has no lakes")
        lakes = lake_list(_load(a.manifest) if a.manifest else None, directory)
    except (ValueError, KeyError) as e:
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
