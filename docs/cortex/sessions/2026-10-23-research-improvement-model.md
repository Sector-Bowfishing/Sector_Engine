# Sector — autonomous research improvement fix — Session Record

```text
Standards: Rehtac Cortex 2.7.0 @ ebc7fb9 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/research-discovery-2026-10-23 · Date: 2026-10-23
```

**Mission.** Fix the research automation so it improves what the Brains know instead of downloading data and packaging unchanged knowledge; prepare a controlled Guntersville app-test pilot. Cloud PAUSED; nothing approved, published or deployed.

## Root cause of research-campaign-2026-10-23

| Failure | Cause |
|---|---|
| 132 s, all DONE | stages proved execution only (download, count, package) |
| Fish "no weak areas" | the weak list came from the connector's own sanity check, not the Brain's gaps |
| VALIDATED datasets and leads | a finding passed on a size or lead-count threshold; no tiers |
| 8 packages, 0 improvements | packaging ran regardless; score adapters re-ran unchanged evaluators |
| 1-2 iterations | fixed `maxIterations`; no ledger of tried avenues, no budget |
| evidence/certification paths unused | missing inputs were report text, not avenues |

## Changed

`tools/research/ledger.py` (tiers, gap ledger, avenue dedupe), `campaign.py` (tiered validation, ledger-driven follow-up, budget and stall rules, outcome classes, EVIDENCE_ONLY packages, rejected-hypothesis preservation, score provenance labels, `register-source`, `--budget-hours`), `experiments.py` (Water Temp hypothesis ladder, Fish evidence grading, CWMS levels, dataset search, owner actions, cross-Brain test), `discovery.py` (source registry, evidence reuse, owner-action records), `discovery.json` (budget, weaknesses, avenues, pre-declared thresholds, score metadata), `sources.json`. Docs: `RESEARCH_DISCOVERY_AUTOMATION_V1.md`, `SCORING_CONTRACT_AUDIT_V1.md`, `SCORING.md` (Wind row fixed, engineering vs scientific note).

## Verification

- 38 tests (offline); 12 mutations of the new rules each fail the suite (3 survived at first and the tests were strengthened).
- Real runs: Water Temp ladder on 12,515 fleet residuals and 4 independent USGS sensor lakes; full eight-Brain runs v2-v5.
- Defects the real runs exposed, all fixed with regression tests: CWMS location names with spaces; stall rule cutting hypothesis ladders; `researchComplete` true while gaps were blocked; gaps blocked in an earlier campaign disabling their avenues; analysis avenues counted as "no progress"; **a spurious Lake coverage gain from regulation-schedule lines** (now rejected).

## Outcome of the final campaign (research-v5-2026-10-23)

8/8 executed, **0/8 successful improvement campaigns**: Fish, Wind, Clarity, Lake, Water Temp, Depth, Vegetation, Intelligence STALLED, each with its blockers and next evidence source. Water Temp's three correction hypotheses were rejected on independent data (fleet-holdout gain 0.21 C but one good lake made worse; season-only gain 0.095 C under the 0.10 bar). Authoritative scores byte-identical. Cloud: 9/9 schedulers PAUSED, control PAUSED.

## Open

Owner decisions R7-R12 (CG-2.7-6); Cortex 2.8.0 standard (separate Cortex session, CG-2.7-5); owner-action datasets listed in each Brain's `research/data-acquisition/`.
