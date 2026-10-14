# Clarity readiness rubric — PROPOSAL (`clarity-readiness-v1`)

**Status: proposed, not ratified. Not the canonical score.** The canonical Clarity score remains the frozen research
certification (`docs/brains/scoring/frozen-scores.json`). This rubric exists because that number measures a *candidate
that is not deployed*; "production-ready" needs a score over what customers would actually receive.
Pre-registered here before any re-scoring so it cannot be tuned to reach a target. Ratification is a Michael decision (D1).

## Dimensions (weights sum to 100). ★ = critical (must be ≥ 7.5 for PRODUCTION_READY)

| id | Dimension | Weight | Claim level | What earns points |
|---|---|---|---|---|
| accuracyInDomain ★ | Level-3 accuracy on the lakes/regions where it would be shown | 20 | 3 | validated error vs independent truth *in that region*; unvalidated = 0 |
| servingParity ★ | The validated model is the model that serves | 15 | 3 | certified path = deployed path; candidate-only = 0 |
| refusalHonesty ★ | Uncertainty and refusal are explicit | 10 | 1–3 | reason codes, ranges only when validated, UNKNOWN/INVALID paths tested |
| freshnessSemantics ★ | Freshness defined from product needs | 10 | 2 | separate clocks, TTL, rain-event invalidation |
| pilotTransfer ★ | Works at pilot systems / regional transfer | 10 | 3 | per-pilot state + in-region validation |
| executionCost | Input-driven execution, bounded cost | 10 | 2 | fingerprint no-op, no hot-path compute, cost known |
| failureTesting | Failures fail honestly | 5 | 2 | tested failure matrix |
| contracts | Ops / Intelligence / customer contracts | 5 | — | specified, tested for shape |
| storageSafety | Bounded storage; no private leakage | 5 | — | audit + leak scan |
| deployRollback | Deploy + rollback documented and rehearsed | 10 | — | runbook, shadow evidence |

Gates (cap, never add): any ★ dimension < 5 → overall capped at **5.0**; servingParity = 0 → capped at **5.5**;
accuracyInDomain = 0 → capped at **4.0**; private-data leak found → capped at **0**.

## Indicative scoring, 2026-10-13 (evidence in private campaign notes)

| id | Production path today | After this campaign's independent work |
|---|---|---|
| accuracyInDomain | 2 | 2 |
| servingParity | 2 | 2 |
| refusalHonesty | 6 | 7 |
| freshnessSemantics | 4 | 5 |
| pilotTransfer | 3 | 3 |
| executionCost | 5 | 7 |
| failureTesting | 6 | 8 |
| contracts | 4 | 6 |
| storageSafety | 6 | 7 |
| deployRollback | 3 | 6 |
| **Weighted** | **3.6** | **4.6** (★ gates cap at 5.0) |

The 8.0 target is unreachable by independent work: the three heaviest ★ dimensions need (a) a deployment decision for the
candidate model, (b) in-region truth/validation for the southern pilot lakes, and (c) serving the validated model.
