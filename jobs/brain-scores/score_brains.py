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
from sector_brain_platform import (BrainRtdb, DryRunStore, beta_readiness, check_schema, event, fleet_rollup, frozen_score, overview,   # noqa: E402
                                   prune_activity, score_biological, score_engine, score_intelligence, score_lake)

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
    sampled, intel_states = [], {}
    if intel_reg.get("evaluatedLakeCount"):
        evaluated_keys = [k for k, row in fleet.items() if (((row or {}).get("slots") or {}).get("intelligence") or {}).get("kind") == "evaluated"]
        for k in sorted(evaluated_keys)[:50]:
            s = db.get(f"lakes/{k}/states/intelligence")
            if s and str(s.get("kind", "")).lower() == "evaluated":
                sampled.append(s); intel_states[k] = s
    fleet_readiness = {k: ((row or {}).get("readiness") or {}) for k, row in fleet.items()}
    return {
        "brains": brains, "health": health, "validation": validation, "fleet": fleet,
        "sources": db.get("sources") or {}, "healthSources": db.get("health/sources") or {}, "jobs": db.get("health/jobs") or {},
        "intelStates": intel_states,
        "engine": {"intelligenceRegistry": intel_reg, "validation": validation, "healthBrains": health,
                   "healthJobs": db.get("health/jobs") or {}, "fleetReadiness": fleet_readiness,
                   # platformHealth: measured from what each brain has PUBLISHED (a brain that conforms on main but has
                   # not republished does not count yet); UNKNOWN until at least one registry carries the ref.
                   "platformConformant": ({b: bool(((brains.get(b) or {}).get("platform") or {}).get("conformant"))
                                           for b in UPSTREAM} if any((brains.get(b) or {}).get("platform") for b in UPSTREAM) else {})},
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


def plan_writes(scores: dict, brains: dict, now: dt.datetime, engine: dict | None = None, old_engine: dict | None = None,
                old_scores: dict | None = None) -> tuple[dict, list[str]]:
    """Writes for scores whose value/version changed, plus a score.changed event per change.
    Canonical nodes are /scores/{id} (platform-only root): a registry is written whole by its brain and
    would clobber a sub-node there (seen 2026-10-12 on the Biological republish)."""
    updates, changed, n = {}, [], 0
    old_scores = old_scores or {}
    if engine is not None:
        old = old_engine or {}
        if old.get("engineScore") != engine["engineScore"] or old.get("engineScoreVersion") != engine["engineScoreVersion"]:
            updates["scores/engine"] = engine
            updates["engine/score"] = engine                    # alias kept for readers of the first publish
            n += 1
            ev = event(now, WRITER, n, "score.changed",
                       f"Sector Engine score {old.get('engineScore', '—')} → {engine['engineScore']} / 10 ({engine['engineScoreVersion']})", "info")
            updates[f"activity/{ev['id']}"] = ev
            changed.append(f"engine: {old.get('engineScore', '—')} → {engine['engineScore']}")
    for bid in UPSTREAM:
        new = scores[bid]
        old = old_scores.get(bid) or {}
        if bid not in brains:
            changed.append(f"{bid}: brain not registered yet — score written anyway (registry absent)")
        if old.get("value") == new["value"] and old.get("scoreVersion") == new["scoreVersion"] and old.get("basis") == new["basis"]:
            continue
        updates[f"scores/{bid}"] = new
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
    engine = score_engine(facts["engine"], scores, now)
    old_scores = db.get("scores") or {}
    updates, changed = plan_writes(scores, facts["brains"], now, engine, old_scores.get("engine"), old_scores)   # canonical: /scores/engine
    # Ops control plane (Phase 10): computed here from published facts, rendered by Ops, never recomputed there.
    control = overview(brains=facts["brains"], health=facts["health"], validation=facts["validation"], scores=scores, engine=engine,
                       fleet=facts["fleet"], sources=facts["sources"], health_sources=facts["healthSources"], jobs=facts["jobs"], now=now)
    rollups = {f"control/fleet/{k}": r for k, row in facts["fleet"].items() if (r := fleet_rollup(k, row, now))}
    control_updates = {"control/overview": control, **rollups}
    # Beta readiness (Phase 12): pilot lakes = those with a normalized Intelligence evaluation. Never a customer rollout.
    src_stale = {sid: v.get("stale") for sid, v in (control.get("sources") or {}).items() if v.get("stale")}
    betas = {}
    for k, st in facts["intelStates"].items():
        row = facts["fleet"].get(k) or {}
        betas[k] = beta_readiness(row.get("lakeId") or k, row, st, facts["validation"], facts["health"], src_stale, now,
                                  brain_stale={b: (control["brains"].get(b) or {}).get("stale") for b in control["brains"]})
        control_updates[f"control/beta/{k}"] = betas[k]
    if betas:
        counts = {}
        for b in betas.values():
            counts[b["betaReadiness"]] = counts.get(b["betaReadiness"], 0) + 1
        control_updates["control/beta/_summary"] = {"version": betas[next(iter(betas))]["betaReadinessVersion"], "lakes": len(betas), "counts": counts,
                                                     "updatedAt": control["updatedAt"], "note": "pilot lakes only; not a customer rollout decision"}
    report = {"at": now.isoformat(), "mode": "write" if a.write else "dry-run", "scores": scores, "engine": engine, "changes": changed, "control": control, "beta": betas}
    for bid in UPSTREAM:
        s = scores[bid]
        print(f"{bid:22s} {s['value']:>4} / 10  {s['basis']:8s} {s['scoreVersion']}  completeness {s.get('completenessPct')} %")
        for g in s.get("scoreBlockers", []):
            print(f"    - {g.get('gate') or g.get('dimension')}: {g.get('why')}" + (f" (cap {g['cap']})" if "cap" in g else ""))
    print(f"{'ENGINE':22s} {engine['engineScore']:>4} / 10  COMPUTED {engine['engineScoreVersion']}  completeness {engine['completenessPct']} %  strongest {engine['strongestArea']}  weakest {engine['weakestArea']}")
    for g in engine["blockers"]:
        print(f"    - {g.get('gate') or g.get('dimension')}: {g.get('why')}" + (f" (cap {g['cap']})" if "cap" in g else ""))
    print(f"\n{len(changed)} change(s): " + ("; ".join(changed) if changed else "none"))
    if a.report:
        json.dump(report, open(a.report, "w"), indent=1)
    print(f"{'CONTROL':22s} overview for {len(control['brains'])} brains, {len(rollups)} fleet rollups; worst health {control['engine'].get('worstBrainHealth')}; work next: "
          + ", ".join(f"{w['brainId']} ({w.get('score')})" for w in control.get("workNext", [])[:3]))
    for k, b in betas.items():
        print(f"{'BETA':22s} {b['lakeId']:18s} {b['betaReadiness']:10s} blockers {[x['code'] + ':' + str(x.get('slot')) for x in b['blockers']]} warnings {len(b['warnings'])}")
    if a.write:
        if updates:
            db.update(updates)
        stale_mirrors = {f"brains/{b}/score": None for b in UPSTREAM if (facts["brains"].get(b) or {}).get("score") is not None}
        if stale_mirrors:                                     # retire the clobber-prone sub-nodes the first publish wrote
            BrainRtdb(brain_id=None).update(stale_mirrors)
        db.update(control_updates)
        pruned = prune_activity(db.get("activity"), WRITER, now)
        if pruned:
            db.update(pruned)
        print(f"published {len(updates)} score path(s) + {len(control_updates)} control path(s); pruned {len(pruned)} old platform event(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
