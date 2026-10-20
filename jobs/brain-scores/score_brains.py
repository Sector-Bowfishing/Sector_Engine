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
from concurrent.futures import ThreadPoolExecutor
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "brain_platform"))
from sector_brain_platform.score_explanation import explain as explain_score, is_current as is_current_explanation  # noqa: E402
from sector_brain_platform import (BrainRtdb, DryRunStore, beta_readiness, check_schema, event, fleet_rollup, frozen_score, overview,   # noqa: E402
                                   prune_activity, guard_scores, score_biological, score_engine, score_intelligence, score_lake)

WRITER = "brain-platform"
FROZEN = os.environ.get("FROZEN_SCORES", os.path.join(HERE, "..", "..", "docs", "brains", "scoring", "frozen-scores.json"))
MAX_LAKE_PROFILES = 1000     # > the 621-lake directory; a guard, not a sample size
LAKE_READ_WORKERS = 8
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
    # Read EVERY profiled lake (bounded for safety): the coverage dimension counts profiles, so a silent first-200 cap would
    # misreport coverage once the reviewed fleet exceeds 200. Reads are small documents, fetched concurrently.
    keys = sorted(profiled)[:MAX_LAKE_PROFILES]

    def _read(k):
        return k, db.get(f"lakes/{k}/brain"), db.get(f"lakes/{k}/states/lake")

    with ThreadPoolExecutor(max_workers=LAKE_READ_WORKERS) as pool:
        for k, p, s in pool.map(_read, keys):
            if p:
                profiles[k] = p
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
        "sources": db.get("sources") or {}, "healthSources": db.get("health/sources") or {},
        "jobs": db.get("jobs") or {},                     # the Engine's /jobs contract (jobs-v1), not the brains' /health/jobs
        "intelStates": intel_states,
        "engine": {"intelligenceRegistry": intel_reg, "validation": validation, "healthBrains": health,
                   "healthJobs": db.get("health/jobs") or {}, "fleetReadiness": fleet_readiness,
                   # platformHealth: measured from what each brain has PUBLISHED (a brain that conforms on main but has
                   # not republished does not count yet); UNKNOWN until at least one registry carries the ref.
                   "platformConformant": ({b: bool(((brains.get(b) or {}).get("platform") or {}).get("conformant"))
                                           for b in UPSTREAM} if any((brains.get(b) or {}).get("platform") for b in UPSTREAM) else {})},
        "lake": {"registry": lake_reg, "validation": validation.get("lake-brain"), "health": health.get("lake-brain"),
                 "profiles": profiles, "states": states, "directoryLakeCount": directory,
                 "profiledCount": len(profiled)},
        "biological": {"registry": brains.get("biological-state") or {}, "validation": validation.get("biological-state"),
                       "species": species, "intelligenceRegistry": intel_reg},
        "intelligence": {"registry": intel_reg, "validation": validation.get("sector-intelligence"),
                         "health": health.get("sector-intelligence"), "directoryLakeCount": directory, "sampledStates": sampled},
    }


def knowledge_ids(registry: dict | None) -> dict:
    """Lightweight release identifiers a Brain registry already publishes (never copied research content)."""
    r = registry or {}
    return {"brainVersion": r.get("version"), "researchVersion": r.get("researchVersion"), "manifestSha256": r.get("manifestSha256"),
            "lastSuccessfulRun": r.get("lastSuccessfulRun")}


def load_gaps(root: str = os.path.join(HERE, "..", "..")) -> dict:
    """{brainId: {gapId: {status, title}}} from brains/*/research/GAPS.json when present (repo runs and the staged image)."""
    out = {}
    base = os.path.join(root, "brains")
    for d in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        p = os.path.join(base, d, "research", "GAPS.json")
        if os.path.isfile(p):
            try:
                doc = json.load(open(p))
            except (OSError, ValueError):
                continue
            out[doc.get("brainId") or d] = {g["id"]: {"status": g.get("status"), "title": g.get("title")} for g in doc.get("gaps") or [] if g.get("id")}
    return out


def rtdb_safe(o):
    """Frozen blocks come from generators on other branches and may name dimensions with RTDB-illegal key characters (the Wind block has
    'Freshness/reliability'); one illegal key fails the whole multi-path update. Replace them in KEYS only (values untouched)."""
    if isinstance(o, dict):
        return {re.sub(r"[.$#\[\]/\x00-\x1f\x7f]", "-", k): rtdb_safe(v) for k, v in o.items()}
    return [rtdb_safe(v) for v in o] if isinstance(o, list) else o


def compute(facts: dict, now: dt.datetime) -> dict:
    frozen = rtdb_safe(json.load(open(FROZEN)))
    return {
        "lake-brain": score_lake(facts["lake"], now),
        "water-temp": frozen_score(frozen["water-temp"]),
        "water-clarity": frozen_score(frozen["water-clarity"]),
        "wind": frozen_score(frozen["wind"]),
        "biological-state": score_biological(facts["biological"], now),
        "sector-intelligence": score_intelligence(facts["intelligence"], now),
    }


def _content(score: dict | None) -> dict:
    """A score block without its refresh timestamp, for comparing substance."""
    # RTDB does not store empty objects/arrays, so a block computed with `scoreBreakdown: {}` reads back WITHOUT the key; treating {} / [] / None as
    # absent keeps the comparison stable (otherwise every frozen block and the Engine block were rewritten every cycle with no change in content).
    # `explanation` is derived FROM the block (score_explanation.py), never score content: it must not make an unchanged score look changed.
    return {k: v for k, v in (score or {}).items() if k not in ("scoreUpdatedAt", "updatedAt", "explanation") and v not in (None, {}, [])}


def plan_writes(scores: dict, brains: dict, now: dt.datetime, engine: dict | None = None, old_engine: dict | None = None,
                old_scores: dict | None = None, explain: bool = False, gaps: dict | None = None) -> tuple[dict, list[str]]:
    """Writes for score blocks whose CONTENT changed (value, uncapped, breakdown, blockers, version), plus a score.changed
    event only when the displayed value / version / basis changed.
    Why content, not just value (2026-10-13): the displayed value can sit at a gate cap (3.0) while the breakdown underneath
    improves (uncapped 4.3 -> 6.3 after the deep TVA history); comparing only the value left /scores/{id} stale for hours.
    Canonical nodes are /scores/{id} (platform-only root): a registry is written whole by its brain and
    would clobber a sub-node there (seen 2026-10-12 on the Biological republish).
    explain=True (Brain Score Explanation V1): every written block carries `explanation`, built from that same block in this same
    update, so score and explanation can never be read apart; a block whose content is unchanged but whose stored explanation is
    missing or not for this evaluation is rewritten once (backfill), with no score.changed event."""
    updates, changed, n = {}, [], 0
    old_scores = old_scores or {}
    if engine is not None:
        old = old_engine or {}
        if _content(old) != _content(engine):
            updates["scores/engine"] = engine
            updates["engine/score"] = engine                    # alias kept for readers of the first publish
            if old.get("engineScore") != engine["engineScore"] or old.get("engineScoreVersion") != engine["engineScoreVersion"]:
                n += 1
                ev = event(now, WRITER, n, "score.changed",
                           f"Sector Engine score {old.get('engineScore', '—')} → {engine['engineScore']} / 10 ({engine['engineScoreVersion']})", "info")
                updates[f"activity/{ev['id']}"] = ev
                changed.append(f"engine: {old.get('engineScore', '—')} → {engine['engineScore']}")
            else:
                changed.append(f"engine: breakdown refreshed (score unchanged {engine['engineScore']})")
    for bid in UPSTREAM:
        new = scores[bid]
        old = old_scores.get(bid) or {}
        if bid not in brains:
            changed.append(f"{bid}: brain not registered yet — score written anyway (registry absent)")
        if _content(old) == _content(new):
            if not explain or is_current_explanation(old):
                continue
            new = dict(old)                                       # backfill: the PUBLISHED evaluation, explained (score untouched)
            new["explanation"] = explain_score(bid, new, None, gaps=(gaps or {}).get(bid), knowledge=knowledge_ids(brains.get(bid)))
            updates[f"scores/{bid}"] = new
            changed.append(f"{bid}: explanation attached (score unchanged {new.get('value')})")
            continue
        if explain:
            new = dict(new)
            new["explanation"] = explain_score(bid, new, old, gaps=(gaps or {}).get(bid), knowledge=knowledge_ids(brains.get(bid)))
        updates[f"scores/{bid}"] = new
        if not (old.get("value") == new["value"] and old.get("scoreVersion") == new["scoreVersion"] and old.get("basis") == new["basis"]):
            n += 1
            ev = event(now, WRITER, n, "score.changed",
                       f"{bid} score {old.get('value', '—')} → {new['value']} / 10 ({new['basis'].lower()}, {new['scoreVersion']})",
                       "info")
            updates[f"activity/{ev['id']}"] = ev
            changed.append(f"{bid}: {old.get('value', '—')} → {new['value']}")
        else:
            changed.append(f"{bid}: breakdown refreshed (displayed {new['value']} unchanged; uncapped {old.get('uncapped', '—')} → {new.get('uncapped', '—')})")
    return updates, changed


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="publish to the Brain RTDB (default: dry run)")
    ap.add_argument("--db", default=None, help="Brain RTDB URL (default: the contract's)")
    ap.add_argument("--report", default=None, help="write the full report JSON here")
    ap.add_argument("--no-explain", action="store_true", help="do not attach /scores/{id}/explanation (brain-score-explanation-v1)")
    ap.add_argument("--if-changed", action="store_true", help="write a control node only when its content (minus timestamps) differs from what is published")
    a = ap.parse_args()
    now = dt.datetime.now(dt.timezone.utc)
    db = BrainRtdb(a.db, brain_id=WRITER) if a.db else BrainRtdb(brain_id=WRITER)
    check_schema(db)
    facts = fetch_facts(db)
    old_scores = db.get("scores") or {}
    # Stale-score protection (platform docs SCORING_SEMANTICS.md section 6): /scores/{id} is the durable canonical store; a candidate that is OLDER than
    # (or ambiguous against) what is published is HELD and the published block is used, so one Brain's stale artifact cannot move any score, the Engine
    # score or the control overview. Deliberate regression needs a recorded decision: SCORE_GUARD_ALLOW=<brainId>[,<brainId>].
    scores, held = guard_scores(compute(facts, now), old_scores, allow=[x for x in os.environ.get("SCORE_GUARD_ALLOW", "").split(",") if x])
    engine = score_engine(facts["engine"], scores, now)
    updates, changed = plan_writes(scores, facts["brains"], now, engine, old_scores.get("engine"), old_scores,   # canonical: /scores/engine
                                   explain=not a.no_explain, gaps=load_gaps())
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
    for h in held:
        tag = "OVERRIDDEN" if h.get("overridden") else "HELD"
        print(f"{tag:22s} {h['brainId']}: {h['verdict']} - {h['why']} (published {h.get('publishedValue')}, candidate {h.get('candidateValue')})"
              + ("; SCORE_GUARD_ALLOW applied" if h.get("overridden") else "; published block kept"))
    changed.extend(f"{h['brainId']}: {'OVERRIDDEN' if h.get('overridden') else 'HELD'} ({h['verdict']}) {h['why']}" for h in held)
    print(f"\n{len(changed)} change(s): " + ("; ".join(changed) if changed else "none"))
    if a.report:
        json.dump(report, open(a.report, "w"), indent=1)
    print(f"{'CONTROL':22s} overview for {len(control['brains'])} brains, {len(rollups)} fleet rollups; worst health {control['engine'].get('worstBrainHealth')}; work next: "
          + ", ".join(f"{w['brainId']} ({w.get('score')})" for w in control.get("workNext", [])[:3]))
    for k, b in betas.items():
        print(f"{'BETA':22s} {b['lakeId']:18s} {b['betaReadiness']:10s} blockers {[x['code'] + ':' + str(x.get('slot')) for x in b['blockers']]} warnings {len(b['warnings'])}")
    if a.if_changed:                                          # publish only after a change (cost work 2026-10-13, Phase 14)
        before = len(control_updates)
        control_updates = changed_control(control_updates, db.get("control") or {})
        print(f"{'IF-CHANGED':22s} {len(control_updates)} of {before} control path(s) differ from what is published")
    if a.write:
        if updates:
            db.update(updates)
        stale_mirrors = {f"brains/{b}/score": None for b in UPSTREAM if (facts["brains"].get(b) or {}).get("score") is not None}
        if stale_mirrors:                                     # retire the clobber-prone sub-nodes the first publish wrote
            BrainRtdb(brain_id=None).update(stale_mirrors)
        if control_updates:
            db.update(control_updates)
        pruned = prune_activity(db.get("activity"), WRITER, now)
        if pruned:
            db.update(pruned)
        print(f"published {len(updates)} score path(s) + {len(control_updates)} control path(s); pruned {len(pruned)} old platform event(s)")
    return 0


VOLATILE = ("updatedAt", "rolledUpAt", "summarizedAt", "syncedAt", "evaluatedAt")


def _stable(v):
    if isinstance(v, dict):
        return {k: _stable(x) for k, x in v.items() if k not in VOLATILE}
    if isinstance(v, list):
        return [_stable(x) for x in v]
    return v


def changed_control(control_updates: dict, published: dict) -> dict:
    """Only the control paths whose content differs from what is published, ignoring the timestamps every publish refreshes.
    The overview is always rewritten when any sibling changed (its updatedAt then means something)."""
    def at(path):
        node = {"control": published}
        for p in path.split("/"):
            node = node.get(p) if isinstance(node, dict) else None
            if node is None:
                return None
        return node
    out = {p: v for p, v in control_updates.items() if _stable(v) != _stable(at(p))}
    if out and "control/overview" in control_updates:
        out["control/overview"] = control_updates["control/overview"]
    return out


if __name__ == "__main__":
    sys.exit(main())
