#!/usr/bin/env python3
"""Engine-owned Brain score publisher (docs/brains/scoring/SCORING.md).

Reads each Brain's published facts from the Brain RTDB, evaluates the versioned rubrics
(sector_brain_platform.scoring), takes the frozen scores verbatim, and writes
/brains/{id}/score for all six Brains as the platform writer `brain-platform`.

  python3 score_brains.py            # dry run: prints every score + breakdown, writes nothing
  python3 score_brains.py --write    # publish changed scores (+ one score.changed event each)

Manual only. No scheduler: the Orchestrator will own cadence. Ops never computes scores.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))
from sector_brain_platform import (BrainRtdb, DryRunStore, check_schema, event, frozen_score, prune_activity,   # noqa: E402
                                   score_biological, score_intelligence, score_lake, slot_for)

WRITER = "brain-platform"
FROZEN = os.path.join(HERE, "..", "..", "docs", "brains", "scoring", "frozen-scores.json")
UPSTREAM = ("lake-brain", "water-temp", "water-clarity", "wind", "biological-state", "sector-intelligence")


def fetch_facts(db) -> dict:
    """Every fact the rubrics read, with read-only GETs. Missing nodes stay None (unknown stays unknown)."""
    brains = db.get("brains") or {}
    validation = db.get("validation") or {}
    health = (db.get("health/brains") or {})
    fleet = db.get("lakeFleet") or {}
    lake_reg = brains.get("lake-brain") or {}
    directory = lake_reg.get("directoryLakeCount") or (len(fleet) if fleet else None)
    profiled = [k for k, row in fleet.items() if ((row or {}).get("slots") or {}).get("lake") or ((row or {}).get("readiness") or {}).get("lake")]
    profiles, states = {}, {}
    for k in sorted(profiled)[:200]:
        p = db.get(f"lakes/{k}/brain")
        if p:
            profiles[k] = p
        s = db.get(f"lakes/{k}/states/lake")
        if s:
            states[k] = s
    species = db.get("species") or {}
    intel_reg = brains.get("sector-intelligence") or {}
    sampled = []
    if intel_reg.get("evaluatedLakeCount"):
        for k in sorted(fleet)[:50]:
            s = db.get(f"lakes/{k}/states/intelligence")
            if s and str(s.get("kind", s.get("stateType", ""))).lower() in ("evaluated",):
                sampled.append(s)
    return {
        "brains": brains,
        "lake": {"registry": lake_reg, "validation": validation.get("lake-brain"), "health": health.get("lake-brain"),
                 "profiles": profiles, "states": states, "directoryLakeCount": directory},
        "biological": {"registry": brains.get("biological-state") or {}, "validation": validation.get("biological-state"),
                       "species": species, "intelligenceRegistry": intel_reg},
        "intelligence": {"registry": intel_reg, "validation": validation.get("sector-intelligence"),
                         "health": health.get("sector-intelligence"), "directoryLakeCount": directory, "sampledStates": sampled},
    }


def compute(facts: dict, now: dt.datetime) -> dict:
    frozen = json.load(open(FROZEN))
    return {
        "lake-brain": score_lake(facts["lake"], now),
        "water-temp": frozen_score(frozen["water-temp"]),
        "water-clarity": frozen_score(frozen["water-clarity"]),
        "wind": frozen_score(frozen["wind"]),
        "biological-state": score_biological(facts["biological"], now),
        "sector-intelligence": score_intelligence(facts["intelligence"], now),
    }


def plan_writes(scores: dict, brains: dict, now: dt.datetime) -> tuple[dict, list[str]]:
    """Writes for scores whose value/version changed, plus a score.changed event per change."""
    updates, changed, n = {}, [], 0
    for bid in UPSTREAM:
        new = scores[bid]
        old = (brains.get(bid) or {}).get("score") or {}
        if bid not in brains:
            changed.append(f"{bid}: brain not registered yet — score written anyway (registry absent)")
        if old.get("value") == new["value"] and old.get("scoreVersion") == new["scoreVersion"] and old.get("basis") == new["basis"]:
            continue
        updates[f"brains/{bid}/score"] = new
        n += 1
        ev = event(now, WRITER, n, "score.changed",
                   f"{bid} score {old.get('value', '—')} → {new['value']} / 10 ({new['basis'].lower()}, {new['scoreVersion']})",
                   "info")
        updates[f"activity/{ev['id']}"] = ev
        changed.append(f"{bid}: {old.get('value', '—')} → {new['value']}")
    return updates, changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="publish to the Brain RTDB (default: dry run)")
    ap.add_argument("--db", default=None, help="Brain RTDB URL (default: the contract's)")
    ap.add_argument("--report", default=None, help="write the full report JSON here")
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    db = BrainRtdb(a.db, brain_id=WRITER) if a.db else BrainRtdb(brain_id=WRITER)
    check_schema(db)
    facts = fetch_facts(db)
    scores = compute(facts, now)
    updates, changed = plan_writes(scores, facts["brains"], now)
    report = {"at": now.isoformat(), "mode": "write" if a.write else "dry-run", "scores": scores, "changes": changed}
    for bid in UPSTREAM:
        s = scores[bid]
        print(f"{bid:22s} {s['value']:>4} / 10  {s['basis']:8s} {s['scoreVersion']}  completeness {s.get('completenessPct')} %")
        for g in s.get("scoreBlockers", []):
            print(f"    - {g.get('gate') or g.get('dimension')}: {g.get('why')}" + (f" (cap {g['cap']})" if "cap" in g else ""))
    print(f"\n{len(changed)} change(s): " + ("; ".join(changed) if changed else "none"))
    if a.report:
        json.dump(report, open(a.report, "w"), indent=1)
    if a.write and updates:
        db.update(updates)
        pruned = prune_activity(db.get("activity"), WRITER, now)
        if pruned:
            db.update(pruned)
        print(f"published {len(updates)} path(s); pruned {len(pruned)} old platform event(s)")
    elif a.write:
        print("nothing to publish")
    return 0


if __name__ == "__main__":
    sys.exit(main())
