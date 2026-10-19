"""Fish Biological Capability V2 scorer (docs/brains/scoring/fish-biological-capability-v2.json, FISH_BIOLOGICAL_CAPABILITY_V2.md).

The shared platform scorer is the only place capability POINTS exist. The Fish evaluator (brains/fish/runtime/capability_eval.py) executes the Fish
runtime and emits an evidence artifact of per-criterion fractions; this module validates that artifact against the rubric and the frozen cohorts,
awards points, scores each species, aggregates the frozen rosters, ranks the research backlog and records changes between evaluations.

Separate from `score_biological` (biological-state-score-v1, the maturity score): nothing here reads or changes that rubric or its history.
CANDIDATE: the rubric and cohorts await owner approval and nothing here publishes. Pure functions (no I/O except `load_json`), deterministic.
"""
from __future__ import annotations

import json
import math
import statistics

RESULT_SCHEMA = "fish-biological-capability-result-v2"
EVIDENCE_SCHEMA = "fish-biological-capability-evidence-v2"
PRECISION = 6
SCORED = "ASSESSED"
UNSCORED = ("NOT_ASSESSED", "INSUFFICIENT_EVIDENCE", "EVALUATION_FAILED")
FORBIDDEN_EVIDENCE_KEYS = frozenset({"capabilityScore", "points", "speciesScore", "categoryScores", "aggregate", "score"})
ROLE_TIER = {"TARGET": 0, "SECONDARY": 1, "KNOWLEDGE_ONLY": 2}
CONNECTABLE = ("KNOWLEDGE_NOT_IN_RUNTIME", "REVIEW_BLOCKED", "RUNTIME_DEFECT")
NEEDS_RESEARCH = ("MISSING_KNOWLEDGE", "THIN_KNOWLEDGE")


def load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _r(x: float) -> float:
    return round(float(x), PRECISION)


def criteria_index(rubric: dict) -> dict:
    return {c["criterionId"]: {**c, "categoryId": cat["categoryId"]} for cat in rubric["categories"] for c in cat["criteria"]}


def validate_rubric(rubric: dict) -> list[str]:
    e = []
    total = 0.0
    for cat in rubric.get("categories") or []:
        s = sum(c["weight"] for c in cat["criteria"])
        if abs(s - cat["maxPoints"]) > 1e-9:
            e.append(f"{cat['categoryId']}: criteria weights {s} != maxPoints {cat['maxPoints']}")
        total += cat["maxPoints"]
    if abs(total - rubric.get("scale", 10)) > 1e-9:
        e.append(f"category maxPoints sum {total} != scale")
    ids = [c["criterionId"] for cat in rubric.get("categories") or [] for c in cat["criteria"]]
    if len(ids) != len(set(ids)):
        e.append("duplicate criterionId")
    for sid, ex in ((rubric.get("normalizationPolicy") or {}).get("biologicalExemptions") or {}).items():
        if not ex.get("reason") or not ex.get("criteria") or any(c not in ids for c in ex["criteria"]):
            e.append(f"exemption {sid}: needs reason and known criteria")
    return e


def _walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k, f"{path}.{k}"
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, f"{path}[{i}]")


def validate_evidence(ev: dict, rubric: dict, cohorts: dict) -> list[str]:
    """Problems (empty = valid). Fails closed on: wrong schema/rubric/cohort version, a roster species missing, a missing or out-of-range criterion,
    an un-exempted NOT_APPLICABLE, and any handwritten score field in the evidence (points exist only here)."""
    e = validate_rubric(rubric)
    if ev.get("schema") != EVIDENCE_SCHEMA:
        e.append(f"evidence schema {ev.get('schema')!r}")
    if ev.get("rubricId") != rubric.get("rubricId"):
        e.append(f"rubricId {ev.get('rubricId')!r} != {rubric.get('rubricId')!r}")
    idx = criteria_index(rubric)
    if sorted(ev.get("criteria") or []) != sorted(idx):
        e.append("evidence criteria set differs from the rubric criteria set")
    if ev.get("cohortsVersion") != cohorts.get("cohortsVersion"):
        e.append(f"cohortsVersion {ev.get('cohortsVersion')!r} != {cohorts.get('cohortsVersion')!r}")
    if not (ev.get("knowledge") or {}).get("knowledgeVersion"):
        e.append("knowledge.knowledgeVersion is required")
    for k, p in _walk(ev.get("species") or {}):
        if k in FORBIDDEN_EVIDENCE_KEYS:
            e.append(f"evidence carries a score field {p}: points are awarded only by the scorer")
    sp = ev.get("species") or {}
    exempt = (rubric.get("normalizationPolicy") or {}).get("biologicalExemptions") or {}
    roster = set()
    for c in cohorts["cohorts"].values():
        roster |= set(c["species"])
    for sid in sorted(roster | set(cohorts.get("notAssessedByPolicy") or [])):
        if sid not in sp:
            e.append(f"{sid}: rostered species missing from the evidence (never silently dropped)")
    for sid in cohorts.get("notAssessedByPolicy") or []:
        if sid in sp and sp[sid].get("evaluationStatus") != "NOT_ASSESSED":
            e.append(f"{sid}: NOT_ASSESSED by policy must stay NOT_ASSESSED")
    for sid, s in sp.items():
        st = s.get("evaluationStatus")
        if st not in (SCORED,) + UNSCORED:
            e.append(f"{sid}: evaluationStatus {st!r}")
        if st != SCORED:
            continue
        crit = s.get("criteria") or {}
        for cid in idx:
            c = crit.get(cid)
            if c is None:
                e.append(f"{sid}.{cid}: missing")
                continue
            if c.get("result") == "NOT_APPLICABLE":
                if cid not in ((exempt.get(sid) or {}).get("criteria") or []):
                    e.append(f"{sid}.{cid}: NOT_APPLICABLE without a reviewed exemption")
                continue
            fr = c.get("fraction")
            if not isinstance(fr, (int, float)) or isinstance(fr, bool) or not 0.0 <= fr <= 1.0 or math.isnan(fr):
                e.append(f"{sid}.{cid}: fraction {fr!r}")
    return e


def score_species(sid: str, s: dict, rubric: dict) -> dict:
    idx = criteria_index(rubric)
    exempt = set((((rubric.get("normalizationPolicy") or {}).get("biologicalExemptions") or {}).get(sid) or {}).get("criteria") or [])
    cats = {}
    implemented, missing = [], []
    earned_total, exempt_w = 0.0, 0.0
    for cat in rubric["categories"]:
        ce, cmax, rows = 0.0, 0.0, {}
        for c in cat["criteria"]:
            cid, w = c["criterionId"], c["weight"]
            r = s["criteria"][cid]
            if cid in exempt:
                exempt_w += w
                rows[cid] = {"weight": w, "result": "NOT_APPLICABLE", "points": None}
                continue
            pts = w * r["fraction"]
            ce += pts
            cmax += w
            rows[cid] = {"weight": w, "result": r["result"], "fraction": r["fraction"], "points": _r(pts)}
            if r["fraction"] >= 1.0:
                implemented.append({"criterion": cid, "label": c["label"], "category": cat["categoryId"]})
            else:
                b = r.get("blocker") or {}
                missing.append({"criterion": cid, "label": c["label"], "category": cat["categoryId"], "lostPoints": _r(w - pts),
                                "result": r["result"], "blocker": b.get("blocker"), "why": b.get("why")})
        earned_total += ce
        cats[cat["categoryId"]] = {"label": cat["label"], "earned": _r(ce), "max": _r(cmax), "criteria": rows}
    denom = rubric.get("scale", 10) - exempt_w
    score = earned_total if not exempt_w else earned_total / denom * rubric.get("scale", 10)
    return {"capabilityScore": _r(score), "displayScore": round(score + 1e-9, 1), "categoryScores": cats, "implementedCapabilities": implemented,
            "missingCapabilities": sorted(missing, key=lambda m: -m["lostPoints"]), "exemptCriteria": sorted(exempt)}


def _bottom_quartile(vals: list[float]) -> float | None:
    if not vals:
        return None
    k = max(1, math.ceil(len(vals) / 4))
    return _r(statistics.fmean(sorted(vals)[:k]))


def aggregate(cohort_id: str, cohort: dict, species: dict, rubric: dict, *, cohorts_version: str, knowledge_versions: set) -> dict:
    """Unweighted mean over the COMPLETE frozen roster. Any rostered species not ASSESSED (failed / insufficient / missing) -> INCOMPLETE, value null."""
    roster = list(cohort["species"])
    scored = {s: species[s]["capabilityScore"] for s in roster if (species.get(s) or {}).get("evaluationStatus") == SCORED}
    unscored = {s: (species.get(s) or {}).get("evaluationStatus", "MISSING") for s in roster if s not in scored}
    vals = list(scored.values())
    complete = not unscored and len(knowledge_versions) == 1
    n = len(roster)
    cat_ids = [c["categoryId"] for c in rubric["categories"]]
    out = {"cohortId": cohort_id, "label": cohort.get("label"), "cohortsVersion": cohorts_version, "rubricId": rubric["rubricId"], "rubricVersion": rubric["rubricVersion"],
           "aggregationPolicy": rubric["aggregationPolicy"]["version"], "eligibleSpecies": n, "evaluated": len(scored), "unscored": unscored,
           "status": "COMPLETE" if complete else "INCOMPLETE", "completenessPct": round(100.0 * len(scored) / n, 1) if n else 0.0}
    if complete:
        mean = statistics.fmean(vals)
        out |= {"value": _r(mean), "display": round(mean + 1e-9, 1)}
    else:
        out |= {"value": None, "display": None,
                "bounds": {"ifUnscoredWere0": _r(sum(vals) / n) if n else None, "ifUnscoredWere10": _r((sum(vals) + 10 * len(unscored)) / n) if n else None},
                "why": "not every rostered species has a valid evaluation under one knowledge version: no false total"}
    if vals:
        lo = min(scored, key=lambda s: (scored[s], s))
        hi = max(scored, key=lambda s: (scored[s], s))
        out |= {"below5": sum(v < 5.0 for v in vals), "below7": sum(v < 7.0 for v in vals),
                "pctAtLeast5": round(100.0 * sum(v >= 5.0 for v in vals) / n, 1), "pctAtLeast7": round(100.0 * sum(v >= 7.0 for v in vals) / n, 1),
                "lowest": {"speciesId": lo, "score": scored[lo]}, "highest": {"speciesId": hi, "score": scored[hi]},
                "lowestScore": scored[lo], "bottomQuartileMean": _bottom_quartile(vals), "median": _r(statistics.median(vals)),
                "categoryAverages": {c: _r(statistics.fmean(species[s]["categoryScores"][c]["earned"] for s in scored)) for c in cat_ids},
                "categoryMax": {c["categoryId"]: c["maxPoints"] for c in rubric["categories"]}}
    return out


def research_backlog(species: dict, rubric: dict, target_roster=()) -> list[dict]:
    """Ranked improvement backlog. Order: role tier (TARGET first) -> not policy-held -> points connectable from EXISTING knowledge
    (unused research, review-blocked rules, runtime defects) -> total gap. Transparent, non-scoring; SECONDARY and KNOWLEDGE_ONLY stay listed."""
    rows = []
    for sid, s in species.items():
        if s.get("evaluationStatus") != SCORED:
            rows.append({"speciesId": sid, "role": s.get("role"), "evaluationStatus": s.get("evaluationStatus"), "currentScore": None,
                         "recommendedNextAction": "POLICY_HOLD" if s.get("evaluationStatus") == "NOT_ASSESSED" else "FIX_EVALUATION",
                         "policyBlocked": s.get("evaluationStatus") == "NOT_ASSESSED", "reason": s.get("reason")})
            continue
        kc = s.get("knowledgeContext") or {}
        by = {}
        for m in s["missingCapabilities"]:
            by[m["blocker"] or "UNCLASSIFIED"] = _r(by.get(m["blocker"] or "UNCLASSIFIED", 0.0) + m["lostPoints"])
        conn = _r(sum(v for k, v in by.items() if k in CONNECTABLE))
        research = _r(sum(v for k, v in by.items() if k in NEEDS_RESEARCH))
        policy = bool(kc.get("doNotResearch"))
        cats = sorted({m["category"] for m in s["missingCapabilities"] if m["lostPoints"] > 0}, key=lambda c: -sum(m["lostPoints"] for m in s["missingCapabilities"] if m["category"] == c))
        if policy:
            action = "POLICY_HOLD"          # protected / not a target: knowledge stays visible, no work commissioned
        elif conn >= 0.5:
            action = "CONNECT_EXISTING_RESEARCH" if by.get("KNOWLEDGE_NOT_IN_RUNTIME", 0) >= by.get("REVIEW_BLOCKED", 0) else "REVIEW_SEASON_ASSERTIONS"
        elif research >= 0.5:
            action = "RESEARCH"
        elif by.get("CONTRADICTORY_EVIDENCE", 0) > 0:
            action = "RESOLVE_CONTRADICTION"
        else:
            action = "MAINTAIN"
        rows.append({"speciesId": sid, "role": s.get("role"), "evaluationStatus": SCORED, "currentScore": s["capabilityScore"],
                     "maxImprovement": _r(rubric.get("scale", 10) - s["capabilityScore"]), "missingCategories": cats, "lostPointsByBlocker": by,
                     "blockerIsMissingKnowledge": research > 0, "blockerIsMissingImplementation": by.get("KNOWLEDGE_NOT_IN_RUNTIME", 0) > 0,
                     "existingResearchUnused": by.get("KNOWLEDGE_NOT_IN_RUNTIME", 0) > 0 or by.get("REVIEW_BLOCKED", 0) > 0,
                     "evidenceContradictory": by.get("CONTRADICTORY_EVIDENCE", 0) > 0 or bool(kc.get("openDiscrepancies")),
                     "fieldObservationsNeeded": by.get("NEEDS_FIELD_OBSERVATIONS", 0) > 0,
                     "policyBlocked": policy, "policyNote": kc.get("doNotResearch"),
                     "researchLikelyImprovesRuntime": research > 0 and not policy,
                     "connectableFromExistingKnowledge": conn, "needsNewResearch": research, "recommendedNextAction": action})
    targets = set(target_roster)

    def key(r):
        return (0 if r["speciesId"] in targets else ROLE_TIER.get(r.get("role"), 3), r["currentScore"] is None, bool(r.get("policyBlocked")), -(r.get("connectableFromExistingKnowledge") or 0.0),
                -(r.get("maxImprovement") or 0.0), r["speciesId"])
    rows.sort(key=key)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def build_result(ev: dict, rubric: dict, cohorts: dict, *, generated_at: str, previous: dict | None = None, maturity: dict | None = None) -> dict:
    errs = validate_evidence(ev, rubric, cohorts)
    if errs:
        raise ValueError("invalid capability evidence: " + "; ".join(errs[:10]) + (f" (+{len(errs) - 10} more)" if len(errs) > 10 else ""))
    kv = (ev.get("knowledge") or {}).get("knowledgeVersion")
    species = {}
    for sid, s in sorted(ev["species"].items()):
        base = {"speciesId": sid, "role": s.get("role"), "evaluationStatus": s["evaluationStatus"], "rubricId": rubric["rubricId"], "rubricVersion": rubric["rubricVersion"],
                "evaluationId": ev["evaluationId"], "knowledgeVersion": kv, "evaluatedAt": ev["evaluatedAt"]}
        if s["evaluationStatus"] != SCORED:
            species[sid] = base | {"capabilityScore": None, "displayScore": None, "reason": s.get("reason")}
            continue
        sc = score_species(sid, s, rubric)
        kc = s.get("knowledgeContext") or {}
        species[sid] = base | sc | {
            "knowledgeContext": {k: kc.get(k) for k in ("knowledgeScoreSpeciesV2", "rules", "taxonomyStatus", "researchMaturity", "openDiscrepancies", "doNotResearch")},
            "knowledgeScoreSpeciesV2": kc.get("knowledgeScoreSpeciesV2"),
            "scientificConfidence": s.get("scientificConfidence"),
            "confidenceLimitations": ["SCENARIO_BEHAVIOR_PASSED, not FIELD_VALIDATED_ACCURACY", "rules are research-derived (NOT_VALIDATED)"]
                                     + ([f"open discrepancies: {', '.join(kc['openDiscrepancies'])}"] if kc.get("openDiscrepancies") else []),
            "referenceCases": s.get("referenceCases") or [],
            "evidenceReferences": {"evaluationId": ev["evaluationId"], "criteriaDetail": "evidence artifact species[].criteria (private)"}}
    aggs = {cid: aggregate(cid, c, species, rubric, cohorts_version=cohorts["cohortsVersion"], knowledge_versions={kv}) for cid, c in cohorts["cohorts"].items()}
    overall_id = (cohorts.get("overall") or {}).get("definition", "ALL_ASSESSED")
    approved = rubric.get("status") == "APPROVED" and cohorts.get("status") == "APPROVED"
    result = {
        "schema": RESULT_SCHEMA, "rubricId": rubric["rubricId"], "rubricVersion": rubric["rubricVersion"], "cohortsVersion": cohorts["cohortsVersion"],
        "evaluationId": ev["evaluationId"], "evaluatedAt": ev["evaluatedAt"], "generatedAt": generated_at, "knowledgeVersion": kv,
        "evaluatorVersion": ev.get("evaluatorVersion"), "outcomeKind": ev.get("outcomeKind"),
        "authority": {"scorer": "sector_brain_platform.fish_capability", "status": "AUTHORITATIVE_APPROVED" if approved else "CANDIDATE",
                      "publication": "INACTIVE", "note": "computed by the shared scorer; not published; rubric/cohorts pending owner approval"},
        "brain": {"brainId": "biological-state", "displayName": "Fish Brain",
                  "overallBiologicalCapability": {"definition": overall_id, "value": aggs[overall_id]["value"], "display": aggs[overall_id]["display"],
                                                  "status": aggs[overall_id]["status"]},
                  "targetSpeciesCapability": {k: aggs["TARGET"].get(k) for k in ("value", "display", "status")} if "TARGET" in aggs else None,
                  "allAssessedSpeciesCapability": {k: aggs["ALL_ASSESSED"].get(k) for k in ("value", "display", "status")} if "ALL_ASSESSED" in aggs else None,
                  "maturityScore": maturity or {"rubric": "biological-state-score-v1", "note": "separate maturity score; unchanged by this result"},
                  "scientificConfidence": {"status": "RESEARCH_UNREVIEWED_NOT_FIELD_VALIDATED" if (ev.get("scientificConfidence") or {}).get("fieldObservations", 0) == 0 else "FIELD_OBSERVATIONS_IN_PROGRESS",
                                           "note": "status only; per species under species[].scientificConfidence"},
                  "productionReadiness": ev.get("productionReadiness")},
        "aggregates": aggs, "species": species, "researchBacklog": research_backlog(species, rubric, (cohorts["cohorts"].get("TARGET") or {}).get("species") or ()),
        "referenceCases": {k: v for k, v in (ev.get("referenceCases") or {}).items() if k != "results"},
        "limitations": ev.get("limitations") or [],
    }
    if previous is not None:
        result["changeRecord"] = compare(previous, result)
    return result


def compare(prev: dict, cur: dict) -> dict:
    """Actual deltas between two results (exact precision). Never edits either; NOT_COMPARABLE when rubric or cohorts differ."""
    same = prev.get("rubricVersion") == cur.get("rubricVersion") and prev.get("cohortsVersion") == cur.get("cohortsVersion")
    out = {"from": {"evaluationId": prev.get("evaluationId"), "knowledgeVersion": prev.get("knowledgeVersion")},
           "to": {"evaluationId": cur.get("evaluationId"), "knowledgeVersion": cur.get("knowledgeVersion")},
           "comparable": same}
    if not same:
        out["why"] = "rubric or cohort version differs: scores are not comparable across versions"
        return out
    sp = []
    for sid in sorted(set(prev.get("species") or {}) | set(cur.get("species") or {})):
        a, b = (prev.get("species") or {}).get(sid) or {}, (cur.get("species") or {}).get(sid) or {}
        va, vb = a.get("capabilityScore"), b.get("capabilityScore")
        if va == vb and a.get("evaluationStatus") == b.get("evaluationStatus"):
            continue
        row = {"speciesId": sid, "from": va, "to": vb, "delta": _r(vb - va) if isinstance(va, (int, float)) and isinstance(vb, (int, float)) else None,
               "statusFrom": a.get("evaluationStatus"), "statusTo": b.get("evaluationStatus")}
        if a.get("categoryScores") and b.get("categoryScores"):
            row["categoryDeltas"] = {c: _r(b["categoryScores"][c]["earned"] - a["categoryScores"][c]["earned"]) for c in b["categoryScores"]
                                     if b["categoryScores"][c]["earned"] != a["categoryScores"][c]["earned"]}
            flips = []
            for c in b["categoryScores"]:
                for cid, rb in b["categoryScores"][c]["criteria"].items():
                    ra = a["categoryScores"][c]["criteria"].get(cid) or {}
                    if ra.get("points") != rb.get("points"):
                        flips.append({"criterion": cid, "from": ra.get("points"), "to": rb.get("points")})
            row["criteriaChanged"] = flips
        sp.append(row)
    ag = {}
    for cid in sorted(set(prev.get("aggregates") or {}) | set(cur.get("aggregates") or {})):
        a, b = (prev.get("aggregates") or {}).get(cid) or {}, (cur.get("aggregates") or {}).get(cid) or {}
        ag[cid] = {"from": a.get("value"), "to": b.get("value"),
                   "delta": _r(b["value"] - a["value"]) if isinstance(a.get("value"), (int, float)) and isinstance(b.get("value"), (int, float)) else None,
                   "statusFrom": a.get("status"), "statusTo": b.get("status")}
    return out | {"species": sp, "aggregates": ag}
