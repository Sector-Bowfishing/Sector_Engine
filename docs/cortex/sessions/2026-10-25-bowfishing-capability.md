# Sector — bowfishing capability, charters, integration and onboarding — Session Record

```text
Standards: Rehtac Cortex 2.7.0 @ ebc7fb9 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/bowfishing-capability-2026-10-25 · Date: 2026-10-25
```

**Mission.** Make the Brains produce evidence-backed bowfishing intelligence, fix what blocked progress, give every Brain a bowfishing charter and a computed capability measurement, integrate their outputs with ABSTAIN, prepare an internal test, and make onboarding a ninth Brain cheap. Cloud PAUSED; nothing approved, published or deployed.

## Blockers fixed

| Blocker | Fix |
|---|---|
| "Exhausted" because no connector existed | gaps no avenue serves get an agent research task and stay visible; EXHAUSTED only after every configured avenue ran |
| Scores typed, recorded or capped | `bowfishing-capability-v1`: computed from recorded evidence, UNMEASURED otherwise, current vs candidate, separate from all other scores |
| Research stopped after a small gain | outcomes are per Brain; avenues continue while gaps remain; resolutions are re-earned in every campaign |
| A finding resolved every gap it touched (found by the first v7 run) | only gaps listed in `resolves` can resolve |
| Information not tied to bowfishing | charters with decisions, predictions, needs, fit-for-purpose targets, abstain conditions |
| Cross-Brain relationships undocumented | charter dependency check: 7 undeclared dependencies found (Fish reads 5 Brains but declares none), recorded, may only shrink |
| Open-web discovery | three parallel research agents searched beyond the five connectors; verified sources registered (USACE CWMS, Dryad, Zenodo, ScienceBase, USGS UMESC LTRM, Iowa Environmental Mesonet) |

## Real results (campaign research-v8-2026-10-25: 2 of 8 improved, 0 authoritative scores changed)

- **Fish (IMPROVED, coverage):** 12 pre-declared rule tests against 17,904 USGS LTRM electrofishing samples (day/night gear, temperature, depth). 8 decisive: 6 supported, 2 contradicted; 4 inconclusive. Freshwater drum night/day 4.0 (CI 3.3-4.8); smallmouth buffalo 1.5 (CI 1.1-2.0), so the draft ">10x" claim is NOT met; common carp 0.90 (CI 0.70-1.14), settling the carp conflict toward "no night advantage"; bowfin night feeding contradicted (0.49); silver carp "active in cold" contradicted (0.08); spotted and longnose gar cold-inactivity supported. Scope: river navigation pools, a surrogate for reservoirs (transferability untested).
- **Wind (IMPROVED, prediction):** month-by-month calm-night probability at 8 airport stations. Held-out years 2022-2024: mean absolute error 0.112 to 0.049 probability points, 8 of 8 stations improved (baseline is a single all-months probability, a weak baseline). Huntsville: 44-50% calm in winter, 85-90% in July-September.
- **Water Temperature (STALLED, 5 rejections, kept):** three bias corrections and two interval hypotheses were rejected under pre-declared rules. Useful finding: the current fixed "80%" band covers only 67-69% of readings at two independent sensor lakes.
- **Lake, Clarity, Depth, Vegetation, Intelligence (STALLED):** evidence leads, owner actions with verified access notes and agent tasks; no capability gain.

## Defects found by running it, all fixed with regression tests

False resolution of a gap the finding did not list; resolved gaps stopping their own avenue in the next campaign; typed readiness mixing deployed and candidate capabilities; LTRM year confound (method corrected and recorded); venv corruption (tests rebuilt on a clean venv).

## Verification

49 offline tests; 20 mutations of the new rules each fail the suite (one survived at first and the test was strengthened); live runs on real data; Cortex research-check validators on the campaign report, ledgers, sources and readiness record.

## Open

Owner decisions: scoring R7-R12 (CG-2.7-6); push and merge of Cortex 2.8.0; the Level-4 recount; promotion of any candidate (M-3, G-1). External data: see each Brain's `research/data-acquisition/` and `research/agent-tasks/`.
