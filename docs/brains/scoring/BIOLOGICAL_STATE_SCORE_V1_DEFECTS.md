# `biological-state-score-v1` defects (audit 2026-10-19 §13; owner directive §28): candidate fixes, INACTIVE

`biological-state-score-v1` (published 5.1) and its history are **not changed**. This file documents the exact defects and where each fix lives, so the owner can approve, reject or combine them. Nothing here is wired to `score_brains.py` or any publisher.

| Defect | Exact cause (`jobs/brain_platform/sector_brain_platform/scoring.py`, `score_biological`) | Effect (audit, real readback) | Fix | Where |
|---|---|---|---|---|
| A | `knowledgeDepth = statistics.median(overallRounded)` over **all 27 assessed** species (19 KNOWLEDGE_ONLY) | 1, 5 or 8 target species raised to 10: still 5.1; all 11 campaign candidates applied: still 5.1 | target-scoped knowledge | existing isolated proposal `biological-state-score-v2` (branch `feat/biological-score-v2`, not wired). Species-level visibility is delivered separately by Fish Biological Capability V2 (Engine PR #35) |
| B | `evidenceQuality = VALIDATED share x 10` takes precedence over the flat `2` RESEARCH floor | first VALIDATED species: 5.1 -> **5.0** | monotone ladder `max(VALIDATED x 10, REVIEWED x 7, 2 if any RESEARCH)` | **this branch**: `biological_v1_candidate.py` (`biological-state-score-v1.2-candidate`) |
| C | `dim("regionalTransfer", 5, None, ...)` hard-coded UNKNOWN although the registry publishes `transferSummary` | 0.5 permanently unreachable (ceiling 9.5) | score from `transferSummary` | existing proposal `biological-state-score-v1.1` (branch `feat/scorer-regional-transfer`, not wired) |
| D | `int(s.get("contradictionCount") or 0)`: a null count counts as zero contradictions | 15 of 27 species record no count yet look contradiction-free | average only species that record a count; all null -> UNKNOWN | **this branch** |
| E | `productionIntegration = 10` when the Intelligence dependency is CONNECTED, while `consumedByCustomerPath: false` | 0.5 for connectivity nobody consumes | move to readiness / customer usefulness | existing v2 proposal (`customerUsefulness`); Capability V2 treats readiness as gates only |

Applying B and D to the 2026-10-19 production readback is reported in the Fish Specialist V2 closeout handoff (private). Activation needs explicit owner approval and its own rubric version; history is never rewritten.
