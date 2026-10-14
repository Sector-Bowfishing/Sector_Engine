# Biological Brain: score dimension exhaustion matrix (2026-10-14)

Published **4.6** (uncapped 4.6, completeness 95%). Canonical dimensions (live `/scores/biological-state`): registryCompleteness 10 · assessedCoverage 9.3 · knowledgeDepth **1.0** · evidenceQuality **2.0** · contradictionsGaps **6.6** · regionalTransfer **UNKNOWN** · biologicalStateImpl **4.0** · biologicalStateValidation **0.0** · productionIntegration 10. Active gate: no VALIDATED species (6.0). Dimensions ≥ 7.5 need no row.
Claim levels: 1 provider/observed · 2 deterministic derivation · 3 Sector-derived intelligence.

| Dimension | Score | Claim level | Product value | Why low | Work attempted | Result | More desk work? | Real blocker |
|---|---:|---|---|---|---|---|---|---|
| knowledgeDepth | 1.0 | 3 (knowledge of species) | Medium-High | median over all 27 rows; 15 are species Sector never rates; principal species are single-system evidence (caps 3-4) | researched 25 rows; calibrated proposed rows; 48 usable rules; 27-vs-12 basis analysis | unchanged; potential 4.9 (rows) / basis would read 4.0 | **No**: further literature cannot lift single-system, non-Southeast evidence | MICHAEL DECISION (rows, basis; deferred) → FIELD / EXTERNAL SOURCE |
| evidenceQuality | 2.0 | 3 | High | nothing is REVIEWED or VALIDATED; no reviewer role | two verification passes (43/51 verified); independence accounting; reviewer workflow + tools; 30-rule review packet | rules honestly tagged; maturity unchanged | **No**: a human must read the packet | MICHAEL DECISION (reviewer) → VALIDATION; ceiling 7.0 < 7.5 floor |
| contradictionsGaps | 6.6 | 3 (documentation hygiene) | Low | open entries are mostly conditionals; capped species gain nothing | classified every contradiction (principal species) | ≈ +0.007 per resolved entry | **No** (self-edits would be self-grading) | MICHAEL DECISION (reviewer sign-off) |
| regionalTransfer | UNKNOWN | 2 (a count over rule tags) | **High** | the scorer hard-codes "not published" | tagged every rule; built/tested `transferSummary` + facts row; computed 0 / 28 / 20 of 48 | Biological side done; scorer ignores it | **Done** | IMPLEMENTATION (scorer) + MICHAEL DECISION |
| biologicalStateImpl | 4.0 | 3 (the evaluated state) | **High** | internal pilot only; not published per lake; not consumed | state, contracts, pilots, IN_PROGRESS published; fingerprint; descriptor corrected | 0 → 4.0 (earlier) | **Little** | MICHAEL DECISION (Ops-only shadow); UPSTREAM BRAIN / PREREQUISITE BRANCH (Intelligence) |
| biologicalStateValidation | 0.0 | 3 | **High** | zero field observations | frozen register 51, predictions 7, tooling, **frozen preregistration**, analysis code, field program | infrastructure complete; 0 observations | **No** | FIELD; TIME / SEASON; VALIDATION |

## Have I run out of useful independent work?
For the **score**: yes. Every low dimension now waits on a Michael decision, field data, time, an upstream Brain, or a scorer change. The one remaining Biological-side item (the `transferSummary` fact) is built and tested but, like any change to the published bundle, ships with the next approved publication. For the **product**, the only remaining independent work is waiting on the inputs the rules depend on (tributary discharge, zoned depth, observed vegetation).

## Cost / computation check (reset §15, §25)
Biological has no scheduled job, no polling and no customer-triggered computation. Species knowledge publishes only when the private bundle's version changes (manual, version-driven). The pilot state is a pure function of already-published Brain states; `state_fingerprint` lets a runner write nothing when inputs are materially unchanged, so a future orchestrator computes because input truth changed, not because a page was opened.
