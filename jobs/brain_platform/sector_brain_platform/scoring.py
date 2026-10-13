"""Brain score evaluator (docs/brains/scoring/SCORING.md).

Pure functions over published Brain facts. Each rubric returns the contract's `score` block:
  value (0-10, one decimal, gate-capped) · uncapped · completenessPct · scoreBreakdown · scoreBlockers.
Unknown stays unknown: a dimension without facts is UNKNOWN, contributes 0, and is excluded from
completeness. Gates cap, never add.
"""
from __future__ import annotations

import datetime as dt
import statistics

from .timeutil import iso

COVERAGE_LADDER = ((0.90, 10), (0.75, 9), (0.50, 7), (0.25, 5), (0.10, 3), (0.05, 2))


def ladder(share: float | None) -> int:
    """Coverage ladder: 0 -> 0; > 0 -> 1; >= 5 % -> 2; 10 % -> 3; 25 % -> 5; 50 % -> 7; 75 % -> 9; 90 % -> 10."""
    if share is None or share <= 0:
        return 0
    for floor, pts in COVERAGE_LADDER:
        if share >= floor:
            return pts
    return 1


def _share(n: int, d: int) -> float | None:
    return None if d <= 0 else n / d


def dim(id_: str, weight: int, value: float | None, evidence: str) -> dict:
    """A scored dimension, or UNKNOWN when value is None."""
    if value is None:
        return {"id": id_, "weight": weight, "status": "UNKNOWN", "evidence": evidence}
    v = max(0.0, min(10.0, float(value)))
    return {"id": id_, "weight": weight, "value": round(v, 1), "status": "SCORED", "evidence": evidence}


def finish(score_version: str, rubric_ref: str, dims: list[dict], gates: list[dict], now: dt.datetime,
           next_opportunity: str, extra: dict | None = None) -> dict:
    """Combine dimensions and gates into the score block. `gates` = [{gate, cap, why}] that FIRED."""
    scored_w = sum(d["weight"] for d in dims if d["status"] == "SCORED")
    earned = sum(d["value"] * d["weight"] for d in dims if d["status"] == "SCORED")
    uncapped = round(earned / 100.0, 1)
    cap = min([g["cap"] for g in gates], default=10.0)
    value = round(min(uncapped, cap), 1)
    blockers = [{"gate": g["gate"], "cap": g["cap"], "why": g["why"]} for g in sorted(gates, key=lambda g: g["cap"])]
    for d in dims:
        if d["status"] == "SCORED" and d["value"] == 0 and d["weight"] >= 10:
            blockers.append({"dimension": d["id"], "why": d["evidence"]})
    out = {
        "value": value, "scale": 10, "basis": "COMPUTED", "uncapped": uncapped,
        "scoreVersion": score_version, "scoreRubric": rubric_ref, "scoreUpdatedAt": iso(now),
        "completenessPct": int(round(100.0 * scored_w / 100.0)),
        "scoreBreakdown": {d["id"]: {k: v for k, v in d.items() if k != "id"} for d in dims},
        "scoreBlockers": blockers,
        "nextScoreOpportunity": next_opportunity,
    }
    if extra:
        out.update(extra)
    return out


# ---------------------------------------------------------------- Lake Brain
def score_lake(facts: dict, now: dt.datetime) -> dict:
    """facts: registry, validation, health, profiles{key: profile}, states{key: state}, directoryLakeCount."""
    reg = facts.get("registry") or {}
    profiles = facts.get("profiles") or {}
    states = facts.get("states") or {}
    n = len(profiles)
    directory = facts.get("directoryLakeCount") or reg.get("directoryLakeCount") or 0

    def share_of(pred, items):
        items = list(items)
        return None if not items else sum(1 for x in items if pred(x)) / len(items)

    src = share_of(lambda p: ((p.get("sourceCapability") or {}).get("level")) in ("DIRECT_OPERATOR_POOL", "DIRECT_LAKE_GAUGE"), profiles.values())
    plan = share_of(lambda p: bool(((p.get("operatingPools") or {}).get("guideCurve") or {}).get("available"))
                    or bool((p.get("operatingPools") or {}).get("operatingZoneSource")), profiles.values())
    hist = share_of(lambda p: (p.get("historicalCoverage") or {}).get("baselineStatus") == "SUFFICIENT", profiles.values())
    base = share_of(lambda p: (p.get("historicalCoverage") or {}).get("baselineStatus") in ("SUFFICIENT", "LIMITED"), profiles.values())
    obs = share_of(lambda s: str(s.get("kind", "")).lower() == "observed", states.values())
    flood = share_of(lambda s: s.get("floodPoolState") not in (None, "UNKNOWN"), states.values())
    vstatus = (facts.get("validation") or {}).get("status")
    vmap = {"NOT_VALIDATED": 0, "PARTIAL": 5, "VALIDATED": 10}
    cov = _share(n, directory)
    health = (facts.get("health") or {}).get("status") or reg.get("health")

    def pct(x):
        return "n/a" if x is None else f"{round(100 * x)} %"
    dims = [
        dim("sourceAuthority", 15, None if src is None else src * 10, f"{pct(src)} of {n} profiled lakes on operator pool / own gauge"),
        dim("operatorPlan", 10, None if plan is None else plan * 10, f"{pct(plan)} of profiled lakes with a guide curve or zone"),
        dim("historyQuality", 15, None if hist is None else hist * 10, f"{pct(hist)} of profiled lakes with >= 5 complete years (SUFFICIENT)"),
        dim("seasonalBaseline", 10, None if base is None else base * 10, f"{pct(base)} of profiled lakes with a baseline (SUFFICIENT/LIMITED)"),
        dim("trendQuality", 10, None if obs is None else obs * 10, f"{pct(obs)} of {len(states)} states observed (not proxy)"),
        dim("floodDroughtContext", 5, None if flood is None else flood * 10, f"{pct(flood)} of states with a known flood-pool state"),
        dim("validation", 15, vmap.get(vstatus) if vstatus in vmap else None, f"/validation/lake-brain: {vstatus or 'absent'}"),
        dim("coverage", 20, None if cov is None else ladder(cov), f"{n} of {directory} directory lakes profiled ({pct(cov)})"),
    ]
    gates = []
    if cov is not None and cov < 0.10:
        gates.append({"gate": "coverage", "cap": 3.0, "why": f"{n} of {directory} lakes profiled ({pct(cov)} < 10 %)"})
    if vstatus == "NOT_VALIDATED" or vstatus is None:
        gates.append({"gate": "validation", "cap": 5.0, "why": f"validation {vstatus or 'absent'}"})
    if health in ("FAILED", "UNKNOWN", None):
        gates.append({"gate": "health", "cap": 2.0, "why": f"brain health {health or 'absent'}"})
    return finish("lake-brain-score-v1", "docs/brains/scoring/lake-brain-score-v1.json", dims, gates, now,
                  "review source bindings for more lakes (coverage gate), then a validation run against operator truth")


# ---------------------------------------------------------------- Biological Brain
def score_biological(facts: dict, now: dt.datetime) -> dict:
    """facts: registry, validation, species{id: node}, intelligenceRegistry."""
    reg = facts.get("registry") or {}
    sk = ((reg.get("responsibilities") or {}).get("speciesKnowledge")) or {}
    bs = ((reg.get("responsibilities") or {}).get("biologicalState")) or {}
    species = facts.get("species") or {}
    total = sk.get("speciesCount", len(species) or None)
    assessed_n = sk.get("assessedCount")
    not_assessed_n = sk.get("notAssessedCount")
    assessed = [s for s in species.values() if (s or {}).get("assessment") == "ASSESSED"]
    if assessed_n is None:
        assessed_n = len(assessed) if species else None

    complete = None
    if total:
        complete = 10 if (assessed_n or 0) + (not_assessed_n or 0) == total else 0
    cov = _share(assessed_n or 0, total) if total else None
    depth_vals = [((s.get("knowledge") or {}).get("overallRounded")) for s in assessed]
    depth_vals = [v for v in depth_vals if isinstance(v, (int, float))]
    depth = statistics.median(depth_vals) if depth_vals else None
    mats = [s.get("researchMaturity") for s in assessed]
    if not mats:
        evidence_q = None
    else:
        val = mats.count("VALIDATED") / len(mats)
        rev = mats.count("REVIEWED") / len(mats)
        evidence_q = val * 10 if val > 0 else (rev * 7 if rev > 0 else (2 if "RESEARCH" in mats else 0))
    contr = [min(int(s.get("contradictionCount") or 0), 5) / 5 for s in assessed]
    contradictions = 10 * (1 - statistics.fmean(contr)) if contr else None
    impl_map = {"NOT_STARTED": 0, "IN_PROGRESS": 4, "LIVE": 8, "VALIDATED": 10}
    impl = impl_map.get(bs.get("status"))
    bval_map = {"NOT_STARTED": 0, "PARTIAL": 5, "VALIDATED": 10}
    bval = bval_map.get(bs.get("validation") or ("NOT_STARTED" if bs.get("status") == "NOT_STARTED" else None))
    ireg = facts.get("intelligenceRegistry") or {}
    conn = (((ireg.get("dependencies") or {}).get("biological-state")) or {}).get("connectionStatus")
    integ = None if not ireg else (10 if conn in ("CONNECTED", "CONNECTED_DEGRADED") else 0)

    dims = [
        dim("registryCompleteness", 10, complete, f"{total or 0} species: {assessed_n or 0} assessed + {not_assessed_n or 0} not assessed"),
        dim("assessedCoverage", 15, None if cov is None else cov * 10, f"{assessed_n or 0} of {total or 0} species assessed"),
        dim("knowledgeDepth", 20, depth, f"median species-v2 overallRounded over {len(depth_vals)} assessed species = {depth}"),
        dim("evidenceQuality", 10, evidence_q, f"research maturity of assessed species: {sorted(set(mats)) if mats else 'none'}"),
        dim("contradictionsGaps", 10, contradictions, f"mean normalized contradiction load over {len(contr)} species"),
        dim("regionalTransfer", 5, None, "not published by the Biological Brain yet"),
        dim("biologicalStateImpl", 15, impl, f"biologicalState.status = {bs.get('status') or 'absent'}"),
        dim("biologicalStateValidation", 10, bval, f"biologicalState validation = {bs.get('validation') or bs.get('status') or 'absent'}"),
        dim("productionIntegration", 5, integ, f"sector-intelligence dependency connectionStatus = {conn or 'absent'}"),
    ]
    gates = []
    if bs.get("status") in (None, "NOT_STARTED"):
        gates.append({"gate": "biologicalState", "cap": 4.0, "why": "per-lake Biological State NOT_STARTED"})
    if not mats or "VALIDATED" not in mats:
        gates.append({"gate": "speciesValidation", "cap": 6.0, "why": "no species at researchMaturity VALIDATED"})
    started = bs.get("status") not in (None, "NOT_STARTED")
    nxt = ("independent review of assessed species, then real field validation toward the first VALIDATED species (gate 6.0)" if started
           else "start per-lake Biological State (gate 4.0); independent review of assessed species")
    return finish("biological-state-score-v1", "docs/brains/scoring/biological-state-score-v1.json", dims, gates, now, nxt)


# ---------------------------------------------------------------- Sector Intelligence
def score_intelligence(facts: dict, now: dt.datetime) -> dict:
    """facts: registry, validation, health, directoryLakeCount, sampledStates[list]."""
    reg = facts.get("registry") or {}
    deps = reg.get("dependencies") or {}
    upstream = ["lake-brain", "water-temp", "water-clarity", "wind", "biological-state"]
    consumed = sum(1 for b in upstream if ((deps.get(b) or {}).get("connectionStatus")) in ("CONNECTED", "CONNECTED_DEGRADED"))
    present = sum(1 for b in upstream if (deps.get(b) or {}).get("connectionStatus"))
    directory = facts.get("directoryLakeCount") or reg.get("directoryLakeCount") or 0
    evaluated = reg.get("evaluatedLakeCount")
    supported = reg.get("supportedLakeCount")
    vstatus = (facts.get("validation") or {}).get("status")
    vmap = {"NOT_VALIDATED": 0, "PARTIAL": 5, "VALIDATED": 10}
    health = (facts.get("health") or {}).get("status") or reg.get("health")
    sched = reg.get("schedule") or {}
    has_job = bool(sched.get("jobId") or sched.get("cadence") not in (None, "", "none"))
    runtime = (5 if health == "HEALTHY" else 0) + (5 if has_job else 0)
    sampled = facts.get("sampledStates") or []
    prov = None
    if evaluated and sampled:
        prov = sum(1 for s in sampled if s.get("provenance") and s.get("inputs")) / len(sampled)

    dims = [
        dim("specialistConnectivity", 20, consumed / 5 * 10 if deps else None, f"{consumed} of 5 upstream Brains consumed"),
        dim("normalizedEvaluations", 20, None if evaluated is None else ladder(_share(evaluated, directory)), f"{evaluated if evaluated is not None else '?'} of {directory} lakes evaluated"),
        dim("dependencyHandling", 10, present / 5 * 10 if deps else None, f"{present} of 5 upstream dependency statuses published"),
        dim("provenance", 10, None if prov is None else prov * 10, "no evaluations to inspect" if not evaluated else f"{round(100 * (prov or 0))} % of {len(sampled)} sampled evaluations carry provenance + inputs"),
        dim("validation", 15, vmap.get(vstatus) if vstatus in vmap else None, f"/validation/sector-intelligence: {vstatus or 'absent'}"),
        dim("lakeCoverage", 10, None if supported is None else ladder(_share(supported, directory)), f"supportedLakeCount {supported if supported is not None else '?'} of {directory}"),
        dim("runtime", 5, runtime if reg else None, f"health {health or 'absent'}; schedule/job {'present' if has_job else 'none'}"),
        dim("synthesisQuality", 10, None, "not measurable until evaluations exist"),
    ]
    gates = []
    if not evaluated:
        gates.append({"gate": "evaluations", "cap": 1.0, "why": "evaluatedLakeCount is 0: no normalized synthesis exists"})
    if consumed == 0:
        gates.append({"gate": "connectivity", "cap": 2.0, "why": "no specialist Brain is consumed"})
    if vstatus in (None, "NOT_VALIDATED"):
        gates.append({"gate": "validation", "cap": 5.0, "why": f"validation {vstatus or 'absent'}"})
    return finish("sector-intelligence-score-v1", "docs/brains/scoring/sector-intelligence-score-v1.json", dims, gates, now,
                  "consume one specialist Brain's normalized state and evaluate the pilot lakes with provenance")


def frozen_score(entry: dict) -> dict:
    """A frozen score published verbatim (basis FROZEN), with the contract's required keys present."""
    out = dict(entry)
    out.setdefault("basis", "FROZEN")
    out.setdefault("scale", 10)
    out.setdefault("scoreBreakdown", {})
    out.setdefault("completenessPct", 100)
    return out


# ---------------------------------------------------------------- Sector Engine Score
SPECIALISTS = ("lake-brain", "water-temp", "water-clarity", "wind", "biological-state")
ALL_BRAINS = SPECIALISTS + ("sector-intelligence",)


def score_engine(facts: dict, brain_scores: dict, now: dt.datetime) -> dict:
    """facts: intelligenceRegistry, validation{id}, healthBrains{id}, healthJobs{job}, fleetReadiness{key: {slot: readiness}},
    lineageVerified (bool|None), platformConformant{id: bool} (optional). brain_scores: {id: score block}."""
    vals = [brain_scores.get(b, {}).get("value") for b in SPECIALISTS]
    maturity = None if any(v is None for v in vals) else statistics.fmean(vals)
    deps = (facts.get("intelligenceRegistry") or {}).get("dependencies") or {}
    consumed = sum(1 for b in SPECIALISTS if ((deps.get(b) or {}).get("connectionStatus")) in ("CONNECTED", "CONNECTED_DEGRADED"))
    fleet = facts.get("fleetReadiness") or {}
    ladder_ok = ("CALIBRATION", "BETA", "VALIDATED", "PRODUCTION")
    covered = sum(1 for r in fleet.values() if any(v in ladder_ok for k, v in (r or {}).items() if k != "intelligence"))
    cov = _share(covered, len(fleet)) if fleet else None
    vmap = []
    for b in ALL_BRAINS:
        st = str(((facts.get("validation") or {}).get(b) or {}).get("status") or "")
        vmap.append(10 if st == "VALIDATED" else (5 if ("PARTIAL" in st or "HOLDOUT" in st) else 0))
    validation = statistics.fmean(vmap)
    hb = facts.get("healthBrains") or {}
    hj = facts.get("healthJobs") or {}
    hb_ok = [((hb.get(b) or {}).get("status")) == "HEALTHY" for b in ALL_BRAINS if hb.get(b)]
    hj_ok = [((j or {}).get("status")) == "HEALTHY" for j in hj.values()]
    runtime = None
    if hb_ok or hj_ok:
        parts = [statistics.fmean(hb_ok) if hb_ok else None, statistics.fmean(hj_ok) if hj_ok else None]
        parts = [p for p in parts if p is not None]
        runtime = statistics.fmean(parts) * 10
    lineage = facts.get("lineageVerified")
    if lineage is None:
        lineage = ((facts.get("intelligenceRegistry") or {}).get("engineServing") or {}).get("lineageVerified")
    plat = facts.get("platformConformant") or {}
    platform = None if not plat else statistics.fmean(1.0 if plat.get(b) else 0.0 for b in ALL_BRAINS) * 10

    dims = [
        dim("specialistBrainMaturity", 25, maturity, "mean of " + ", ".join(f"{b} {brain_scores.get(b, {}).get('value', '?')}" for b in SPECIALISTS)),
        dim("integrationCompleteness", 20, consumed / 5 * 10, f"{consumed} of 5 specialist Brains consumed by Sector Intelligence"),
        dim("lakeCoverage", 10, None if cov is None else cov * 10, f"{covered} of {len(fleet)} fleet lakes with a specialist slot at readiness >= CALIBRATION"),
        dim("scientificValidation", 15, validation, "validation states: " + ", ".join(f"{b}={((facts.get('validation') or {}).get(b) or {}).get('status') or 'absent'}" for b in ALL_BRAINS)),
        dim("runtimeReliability", 10, runtime, f"{sum(hb_ok)}/{len(hb_ok)} brains and {sum(hj_ok)}/{len(hj_ok)} jobs HEALTHY"),
        dim("productionConsistency", 10, None if lineage is None else (10 if lineage else 0), f"serving lineage verified: {lineage}"),
        dim("platformHealth", 10, platform, "not published until Brains land on the shared platform (Phase 7)" if platform is None else f"{sum(1 for b in ALL_BRAINS if plat.get(b))}/6 conformant"),
    ]
    gates = []
    if consumed == 0:
        gates.append({"gate": "synthesisDisconnected", "cap": 4.0, "why": "Sector Intelligence consumes no specialist Brain"})
    if lineage is False:
        gates.append({"gate": "lineageUnverified", "cap": 3.0, "why": "serving revision not verified against git"})
    failed = [b for b in ALL_BRAINS if ((hb.get(b) or {}).get("status")) == "FAILED"]
    if failed:
        gates.append({"gate": "brainFailed", "cap": 5.0, "why": f"FAILED: {', '.join(failed)}"})
    block = finish("engine-score-v1", "docs/brains/scoring/engine-score-v1.json", dims, gates, now,
                   "connect Sector Intelligence to one specialist Brain (synthesis gate), then validation runs")
    scored = {k: v for k, v in block["scoreBreakdown"].items() if v["status"] == "SCORED"}
    strongest = max(scored, key=lambda k: scored[k]["value"]) if scored else None
    weakest = min(scored, key=lambda k: scored[k]["value"]) if scored else None
    return {
        "engineScore": block["value"], "engineScoreVersion": "engine-score-v1", "scale": 10, "uncapped": block["uncapped"],
        "completenessPct": block["completenessPct"], "dimensions": block["scoreBreakdown"], "blockers": block["scoreBlockers"],
        "strongestArea": strongest, "weakestArea": weakest, "updatedAt": block["scoreUpdatedAt"],
        "brainScores": {b: brain_scores.get(b, {}).get("value") for b in ALL_BRAINS},
        "nextOpportunity": block["nextScoreOpportunity"], "rubric": "docs/brains/scoring/engine-score-v1.json",
    }
