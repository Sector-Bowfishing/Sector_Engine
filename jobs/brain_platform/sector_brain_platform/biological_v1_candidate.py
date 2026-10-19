"""CANDIDATE fixes for two `biological-state-score-v1` defects (Fish scoring audit 2026-10-19 §13; owner directive §28). INACTIVE.

Nothing imports this module in a write path: `score_biological` (v1) stays the published rubric and its history is untouched. This module
exists so the owner can review the exact change and its effect before deciding. It reuses v1 unchanged except for:

  B. evidenceQuality is MONOTONE: max(VALIDATED share x 10, REVIEWED share x 7, 2 if any RESEARCH). In v1 the first VALIDATED species
     replaces the flat RESEARCH floor (2.0) with 1/27 x 10 = 0.37, so a real milestone lowers the Brain score (5.1 -> 5.0).
  D. contradictionsGaps ignores species with NO recorded contradiction count (null) instead of counting them as zero contradictions;
     when no assessed species records a count the dimension is UNKNOWN (contributes 0, excluded from completeness), never a free 10.

Defects A (median over all 27), C (regionalTransfer hard-coded UNKNOWN) and E (connectivity scored without customer consumption) already have
isolated proposals (`feat/biological-score-v2`, `feat/scorer-regional-transfer`); they are deliberately not duplicated here.
"""
from __future__ import annotations

import datetime as dt
import statistics

from .scoring import dim, finish, score_biological

CANDIDATE_VERSION = "biological-state-score-v1.2-candidate"


def evidence_quality_monotone(mats: list) -> float | None:
    if not mats:
        return None
    val = mats.count("VALIDATED") / len(mats)
    rev = mats.count("REVIEWED") / len(mats)
    return max(val * 10, rev * 7, 2 if "RESEARCH" in mats else 0)


def contradictions_known_only(assessed: list[dict]) -> tuple[float | None, int]:
    known = [s.get("contradictionCount") for s in assessed if isinstance(s.get("contradictionCount"), (int, float)) and not isinstance(s.get("contradictionCount"), bool)]
    if not known:
        return None, 0
    return 10 * (1 - statistics.fmean(min(int(c), 5) / 5 for c in known)), len(known)


def score_biological_v1_2_candidate(facts: dict, now: dt.datetime) -> dict:
    """v1 with fixes B and D only. Returns a score block labelled with the candidate version; never published."""
    v1 = score_biological(facts, now)
    species = facts.get("species") or {}
    assessed = [s for s in species.values() if (s or {}).get("assessment") == "ASSESSED"]
    mats = [s.get("researchMaturity") for s in assessed]
    eq = evidence_quality_monotone(mats)
    cg, n_known = contradictions_known_only(assessed)
    dims = []
    for k, d in v1["scoreBreakdown"].items():
        if k == "evidenceQuality":
            dims.append(dim(k, d["weight"], eq, f"monotone ladder over research maturity: {sorted(set(mats)) if mats else 'none'}"))
        elif k == "contradictionsGaps":
            dims.append(dim(k, d["weight"], cg, f"mean normalized contradiction load over {n_known} of {len(assessed)} species that record a count (null = unknown, not 0)"))
        else:
            dims.append(dict(d, id=k) if d["status"] == "SCORED" else {"id": k, "weight": d["weight"], "status": "UNKNOWN", "evidence": d.get("evidence")})
    gates = [{"gate": b["gate"], "cap": b["cap"], "why": b["why"]} for b in v1["scoreBlockers"] if "gate" in b]
    out = finish(CANDIDATE_VERSION, CANDIDATE_VERSION, dims, gates, now, v1["nextScoreOpportunity"])      # documented in BIOLOGICAL_STATE_SCORE_V1_DEFECTS.md
    out["candidate"] = {"status": "CANDIDATE_INACTIVE", "fixes": ["B", "D"], "baseline": {"scoreVersion": v1["scoreVersion"], "value": v1["value"], "uncapped": v1["uncapped"]}}
    return out
