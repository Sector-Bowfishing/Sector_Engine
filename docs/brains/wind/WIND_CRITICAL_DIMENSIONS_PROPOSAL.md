# Proposal — which Wind dimensions are CRITICAL (subject to the ≥ 7.5 floor)  — FOR APPROVAL; nothing changed

Sector policy: production needs overall Brain score ≥ 8.0 **and** every critical dimension ≥ 7.5. Engine does not yet name Wind's critical dimensions (so Ops' guardrail cannot evaluate them). Principle used: *a dimension is critical if a bowfisher's decision depends on it and a failure would make Wind's customer output wrong or unsafe.* Scores below are the canonical scorer's credit × 10 (rubric v1) as computed 2026-10-13; v2 names are the proposed replacements (`WIND_CERTIFICATION_RUBRIC_V2.md`). Changing canonical scoring policy requires approval; this file only recommends.

| Capability | v1 dimension → v2 dimension | Recommend | Why | Today (v1) |
|---|---|---|---|---|
| **Direction** (where it is from) | 2 → "Direction when it matters" | **CRITICAL** | drives every bank answer | 5.4 |
| **Useful wind strength** | 1 → "Useful tonight speed" | **CRITICAL** | calm vs light vs windy decides the night; v1 version is blocked by an event gate that does not match use | 0.0 |
| **Tonight usefulness** (category, easing, risk flag) | 4 → "Tonight trend" + "Strong-wind risk" | **CRITICAL** (as one capability) | the product question; includes the honesty rule (no unsupported claims) | trend 10.0 (lead only); risk unscored |
| **Bank exposure / protection (validated)** | 6 → "Bank exposure field-validated" | **CRITICAL** | false PROTECTED is the dangerous error | 0.0 |
| **Operational reliability** | 8 → "Reliability & freshness" | **CRITICAL** | a stale or missing wind is worse than none | 1.7 (5/30 days) |
| **Provenance / Unknown / confidence** | 10 → "Honesty & provenance" + "Confidence calibration" | **CRITICAL** | trust; UNKNOWN never improves | 10.0 |
| Fleet coverage | 9 → "Fleet coverage (tier-capped)" | scored, **not critical** | breadth, not correctness; capped by validation tier | 10.0 (audited only) |
| Fetch method / geometry discipline | 5 → "Geometry & tier discipline" | **CRITICAL for any lake that carries bank words**; not a separate Brain-level floor | wrong geometry makes exposure wrong | 10.0 |
| Practical roughness (surface) | 7 → "Practical roughness" | scored, **not critical** (supports exposure) | tester roughness agreement | 0.0 |
| Gust | 3 → none | **not critical; withheld claim** | no source forecasts gust events; claims stay withheld | 0.0 |
| Over-water reference | cap 7 | **gate**, not a dimension | removes a cap; becomes a dimension in v2 only if it earns points | — |
| Real validation (H2 + field) | 6/7 + H2 | folded into the critical items above | validation is how the others reach 7.5 | — |

## Consequence if approved
Critical set = {Direction, Useful strength, Tonight usefulness, Bank exposure validated, Reliability, Provenance/confidence} (+ geometry discipline as a per-lake gate). Under v1 today four of those are ≤ 5.4 (0.0, 0.0, 0.0, 1.7), so Wind is **far** from production eligibility; the gaps are physical truth (bank pairs), 30 live days, and a rubric decision for the strength/event gate — not engineering. Gust and fleet breadth would not block production, consistent with "Wind is wind".

## Approval needed
1. Michael approves (or edits) the critical set.
2. Engine publishes it (`productionPolicy` / critical designation on Wind's score block) so Ops' existing guardrail can evaluate it.
3. Rubric v2 decision stays separate (not adopted here).
