"""Brain operational truth (docs/brains/platform/BRAIN_OPERATIONAL_TRUTH_V1.md): ONE freshness verdict per Brain, the timestamps that answer
different questions, the reason behind a non-HEALTHY health word, and the lake coverage split. Shared by both Engine control planes
(/control/overview, written by the scorer; /control/orchestratorV1, written by the orchestrator) so they can no longer disagree.

Rules:
  * One effective freshness policy per Brain. The Orchestrator manifest (`brains.{id}.freshness`) is the OPERATING policy and wins; the rule the
    Brain declares in its own registry (`staleAfterHours`, `stalenessModel`) is reported beside it as `declared…`, never silently dropped.
  * Verdict per model: TIME = age of the last successful run vs the limit; VERSION = the Brain's own `--plan` (SKIP = the published version is the
    newest canonical one); FINGERPRINT = current input fingerprint vs the one the Brain last processed. Missing evidence = UNKNOWN, never FRESH.
  * Freshness says nothing about the schedule: a PAUSED scheduler stays PAUSED in its own field; a STALE verdict stays STALE.
  * Timestamps are not interchangeable: lastExecution (an attempt), lastSuccessfulRun (a run that finished), lastDataUpdate (newest published data),
    lastScoreEvaluation (when the scorer last evaluated the score).
Pure functions; no I/O.
"""
from __future__ import annotations

import datetime as dt

from .timeutil import age_hours, parse_time

VERDICTS = ("FRESH", "STALE", "UNKNOWN")
MODELS = ("TIME", "VERSION", "FINGERPRINT")
BAD_HEALTH = ("WARNING", "DEGRADED", "FAILED")
# Lake-slot of each Brain in /lakeFleet (its per-lake published state); used for lastDataUpdate.
LAKE_SLOT = {"lake-brain": "lake", "water-temp": "waterTemp", "water-clarity": "waterClarity", "wind": "wind", "sector-intelligence": "intelligence",
             "depth": "depth"}


def _round(x):
    return None if x is None else round(float(x), 2)


def effective_policy(manifest_brain: dict | None, registry: dict | None) -> dict:
    """{model, staleAfterHours?, source, declaredModel?, declaredStaleAfterHours?, note?}"""
    mf = (manifest_brain or {}).get("freshness") or {}
    reg = registry or {}
    declared_model, declared_sa = reg.get("stalenessModel"), reg.get("staleAfterHours")
    if mf:
        model = mf.get("stalenessModel") or ("TIME" if mf.get("staleAfterHours") is not None else None)
        sa, source = mf.get("staleAfterHours"), "ORCHESTRATOR_MANIFEST"
    else:
        model = declared_model or ("TIME" if declared_sa is not None else None)
        sa, source = declared_sa, "BRAIN_REGISTRY" if (declared_model or declared_sa is not None) else "NONE"
    out = {"model": model, "staleAfterHours": sa if model == "TIME" else None, "source": source}
    if source == "ORCHESTRATOR_MANIFEST" and (declared_model, declared_sa) != (None, None) and \
            (declared_sa != sa or (declared_model or "TIME") != (model or "TIME")):
        out |= {"declaredModel": declared_model, "declaredStaleAfterHours": declared_sa}
    if mf.get("note"):
        out["note"] = mf["note"]
    return {k: v for k, v in out.items() if v is not None}


def verdict(policy: dict, *, last_successful_run: str | None, now: dt.datetime, plan: dict | None = None,
            input_fingerprint: str | None = None, last_processed_fingerprint: str | None = None) -> dict:
    """{verdict FRESH|STALE|UNKNOWN, stale bool|None, reason, model, ageHours?, staleAfterHours?}"""
    model = policy.get("model")
    age = age_hours(last_successful_run, now) if last_successful_run else None
    base = {"model": model, "policySource": policy.get("source"), "ageHours": _round(age)}
    if model == "TIME":
        sa = policy.get("staleAfterHours")
        base["staleAfterHours"] = sa
        if age is None:
            return base | {"verdict": "UNKNOWN", "stale": None, "reason": "no successful run recorded"}
        if sa is None:
            return base | {"verdict": "UNKNOWN", "stale": None, "reason": "TIME model without a limit"}
        st = age > float(sa)
        return base | {"verdict": "STALE" if st else "FRESH", "stale": st,
                       "reason": f"last successful run {'older than' if st else 'within'} the {sa} h limit"}
    if model == "VERSION":
        action = (plan or {}).get("action")
        if (plan or {}).get("planError"):
            why = "; ".join(str(r) for r in ((plan or {}).get("reasons") or [])[:1]) or "plan failed"
            return base | {"verdict": "UNKNOWN", "stale": None, "reason": f"VERSION model: the Brain plan did not complete ({why[:160]})"}
        if action == "SKIP":
            return base | {"verdict": "FRESH", "stale": False, "reason": "the published version is the newest canonical version (Brain plan: SKIP)"}
        if action == "PUBLISH":
            why = "; ".join(str(r) for r in ((plan or {}).get("reasons") or [])[:2]) or "a newer version is available"
            return base | {"verdict": "STALE", "stale": True, "reason": f"Brain plan: PUBLISH ({why})"}
        return base | {"verdict": "UNKNOWN", "stale": None, "reason": "VERSION model: no Brain plan this cycle (cannot compare versions)"}
    if model == "FINGERPRINT":
        if not input_fingerprint:
            return base | {"verdict": "UNKNOWN", "stale": None, "reason": "FINGERPRINT model: current input fingerprint unknown"}
        if not last_processed_fingerprint:
            return base | {"verdict": "UNKNOWN", "stale": None,
                           "reason": "FINGERPRINT model: no orchestrated run recorded the inputs it processed (manual runs are not tracked)"}
        same = input_fingerprint == last_processed_fingerprint
        return base | {"verdict": "FRESH" if same else "STALE", "stale": not same,
                       "reason": "inputs unchanged since the last processed run" if same else "inputs changed since the last processed run"}
    return base | {"verdict": "UNKNOWN", "stale": None, "reason": "no freshness policy"}


def newest_slot_updates(fleet: dict | None) -> dict:
    """{slot: newest lastUpdatedAt/generatedAt across /lakeFleet rows} - the newest per-lake data each Brain has published."""
    out: dict[str, str] = {}
    best: dict[str, dt.datetime] = {}
    for row in (fleet or {}).values():
        for slot, s in ((row or {}).get("slots") or {}).items():
            if not isinstance(s, dict):
                continue
            for k in ("lastUpdatedAt", "generatedAt"):
                t = parse_time(s.get(k))
                if t and (slot not in best or t > best[slot]):
                    best[slot], out[slot] = t, s.get(k)
    return out


def data_update(brain_id: str, policy: dict, registry: dict | None, slot_newest: dict | None) -> dict | None:
    """lastDataUpdate {at, basis}: newest per-lake state for lake-slot Brains; for VERSION Brains the run that published the current version."""
    slot = LAKE_SLOT.get(brain_id)
    if slot and (slot_newest or {}).get(slot):
        return {"at": slot_newest[slot], "basis": "NEWEST_LAKE_STATE"}
    reg = registry or {}
    if policy.get("model") == "VERSION" and reg.get("lastSuccessfulRun"):
        return {"at": reg["lastSuccessfulRun"], "basis": "VERSION_PUBLISH_RUN", "version": reg.get("researchVersion") or reg.get("version")}
    return None


def health_reasons(brain_id: str, health: dict | None, sources: dict | None, source_health: dict | None) -> dict | None:
    """Why a Brain is not HEALTHY. The Brain's own reasons win (BRAIN_REPORTED); otherwise Engine derives them from facts the same Brain published
    (its sources' health and its stale-lake count) and labels them DERIVED_FROM_PUBLISHED_FACTS. HEALTHY / unknown -> None."""
    h = health or {}
    if h.get("status") not in BAD_HEALTH:
        return None
    own = h.get("reasons") or h.get("healthReasons")
    if own:
        return {"basis": "BRAIN_REPORTED", "reasons": [str(r) for r in own][:6]}
    reasons = []
    for sid in sorted(sources or {}):
        rec = (sources or {}).get(sid) or {}
        if rec.get("ownerBrainId") != brain_id:
            continue
        sh = ((source_health or {}).get(sid) or {}).get("status") or rec.get("health")
        if sh in BAD_HEALTH:
            n = rec.get("lakeCount")
            obs = rec.get("latestObservationAt")
            reasons.append(f"source {sid} {sh}" + (f" ({n} lake{'s' if n != 1 else ''})" if n is not None else "") +
                           ("" if obs else "; no observation") + (f"; {rec.get('failuresLastRun')} failure(s) last run" if rec.get("failuresLastRun") else ""))
    if h.get("staleLakeCount"):
        reasons.append(f"{h['staleLakeCount']} lake state(s) stale")
    if h.get("latestError"):
        reasons.append(f"latest error: {str(h['latestError'])[:160]}")
    if not reasons:
        return {"basis": "UNEXPLAINED", "reasons": [f"the Brain reports {h.get('status')} without a reason and no published fact explains it"]}
    return {"basis": "DERIVED_FROM_PUBLISHED_FACTS", "reasons": reasons[:6]}


def coverage_split(brain_id: str, registry: dict | None, intelligence_registry: dict | None) -> dict | None:
    """Lake coverage by meaning: internal pilot (no publication), published state, customer-enabled. Only what the Brain/Intelligence publish."""
    reg = registry or {}
    pilot = (((reg.get("responsibilities") or {}).get("biologicalState")) or {}).get("pilotLakes")
    dep = (((intelligence_registry or {}).get("dependencies") or {}).get(brain_id)) or {}
    out = {}
    if isinstance(pilot, list):
        out["internalPilotLakes"] = len(pilot)
    if reg.get("supportedLakeCount") is not None:
        out["publishedLakes"] = reg["supportedLakeCount"]
    if dep.get("consumedByCustomerPath") is False:
        out["customerEnabledLakes"] = 0
    elif dep.get("consumedByCustomerPath") is True and reg.get("supportedLakeCount") is not None:
        out["customerEnabledLakes"] = reg["supportedLakeCount"]
    return out or None
