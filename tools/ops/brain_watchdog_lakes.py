#!/usr/bin/env python3
"""Watchdog lake lists for the all-lakes rollout (owner direction, Michael, 2026-11-20, Sector_Ops #51 comment 7049169954): every Brain covers
every lake, so Water Clarity, Water Temp and Lake may publish any lake in the Engine's /lakes directory.

The cycle watchdog trips PUBLISH_OUTSIDE_LAKES on any write for a lake not on the Brain's list (cycle_watchdog.py). This generates each list from
the canonical directory, the same way Sector Intelligence's is (si_watchdog_lakes.py, SI-WD (a)), and pins it into the live watchdog policy and the
Brain's staged hybrid-stage fragment (when it has one), so the two stay equal (hybrid_stage.live_problems). Holder and approvalRef are untouched;
the owner direction is recorded per Brain as lakesScopeRef. Lake writes only lakes with an accepted binding, so its list is a superset by design.

  python tools/ops/brain_watchdog_lakes.py                 # print each Brain's generated count
  python tools/ops/brain_watchdog_lakes.py --write         # pin the lists (a reviewed PR)
  python tools/ops/brain_watchdog_lakes.py --check         # exit 1 if any pinned list differs

No network, no database, no bucket. The policy goes live only with the next brain-orchestrator deploy.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import si_watchdog_lakes as SL   # noqa: E402

ROOT = SL.ROOT
POLICY = os.path.join(ROOT, "jobs", "brain_platform", "sector_brain_platform", "watchdog-policy.json")
STAGE_DIR = os.path.join(HERE, "hybrid-stage")
BRAINS = ("water-clarity", "water-temp", "lake-brain")
SCOPE_REF = "owner-direction-2026-11-20/sector-ops-51-7049169954"


def generated(directory: str = SL.GOLDEN) -> list[str]:
    return SL.lake_list(SL._load(directory))


def _dump(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def problems(policy: dict, lakes: list[str], stage_dir: str = STAGE_DIR) -> list[str]:
    out = []
    for b in BRAINS:
        entry = (policy.get("brains") or {}).get(b) or {}
        if list(entry.get("lakes") or []) != lakes:
            out.append(f"watchdog-policy {b}: {len(entry.get('lakes') or [])} lakes pinned, {len(lakes)} generated")
        if entry.get("lakesScopeRef") != SCOPE_REF:
            out.append(f"watchdog-policy {b}: lakesScopeRef must be {SCOPE_REF}")
        frag_path = os.path.join(stage_dir, f"{b}.json")
        if os.path.exists(frag_path):
            frag = SL._load(frag_path)
            if list((frag.get("watchdog") or {}).get("lakes") or []) != lakes:
                out.append(f"hybrid-stage {b}.json: watchdog.lakes differs from the generated list")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--directory", default=SL.GOLDEN)
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--write", action="store_true")
    g.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    try:
        lakes = generated(a.directory)
    except (ValueError, KeyError) as e:
        print(f"REFUSED: {e}", file=sys.stderr)
        return 2
    policy = SL._load(POLICY)
    if a.check:
        probs = problems(policy, lakes)
        for p in probs:
            print(f"DIFFERS: {p}", file=sys.stderr)
        if probs:
            return 1
        print(f"OK: {', '.join(BRAINS)} pinned to {len(lakes)} lakes")
        return 0
    if a.write:
        for b in BRAINS:
            entry = policy["brains"][b]
            entry["lakes"] = lakes
            entry["lakesScopeRef"] = SCOPE_REF
            frag_path = os.path.join(STAGE_DIR, f"{b}.json")
            if os.path.exists(frag_path):
                frag = SL._load(frag_path)
                frag.setdefault("watchdog", {})["lakes"] = lakes
                _dump(frag_path, frag)
        _dump(POLICY, policy)
        print(f"pinned {len(lakes)} lakes for {', '.join(BRAINS)}")
        return 0
    for b in BRAINS:
        print(f"{b}: {len(lakes)} lakes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
