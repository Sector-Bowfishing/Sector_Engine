# Intelligence deep-research summary (2026-10-13)

**Branch:** `docs/intelligence-deep-research` from `origin/main` `e596a6bb`. **Boundary kept:** research only. No source under `Sources/`, `jobs/`, `docs/brains/` or any app/Ops was changed; no deploy, merge, publish, API or score change. New files are under `docs/research/intelligence/` and `research/intelligence/` only.

## Answers in one screen
| Question | Answer |
|---|---|
| What is the actual score? | **4.8 / 10** published (reproduced). 94% of it is plumbing; it cannot count the Conditions Score that customers use |
| What does research support? | **3.2 / 10** on the pre-registered decision-readiness ladder (about 2–4); 2.7 if unreleased FishIntel is ignored |
| Design on today's inputs? | 4.5 hypothetical, not a current score |
| Future potential? | 7.0 displayed (7.8 uncapped), conditional on Depth, Vegetation, Biological bands, scheduled upstreams and a PARTIAL field validation. Kept separate |
| Biggest Intelligence-owned problem? | No combination rule over Brain states: the Brain that reads every specialist judges nothing; the thing that answers reads none |
| Biggest upstream blocker? | Biological has no per-species response bands (only common carp rules); knowledge median ≈1.0/10 |
| Biggest overall blocker? | Validation: zero outcome data anywhere |

## What the audit found (full detail: `CURRENT_STATE_AUDIT`)
1. Four implementations; only the Engine Conditions Score reaches customers and it reads no Brain.
2. Measured on the real aggregator (synthetic inputs): one °F of live water temperature moves the score 35→81; 50–59 °F water still scores 84; unknown temp+level scores 96 vs 79 for cool+falling (**missing data raises the score**); a guessed clarity still reads "High" confidence; hiding bank-level wind costs up to 38 points; confidence is a fixed countdown, blind to most inputs.
3. Duplicate science across Engine, FishIntel, Wind and Biological: three conflicting spawn tables, two wind gate thresholds, two clarity conversions.
4. Future nights persist today's hydrology unlabelled; caches can skew `nights[0]` against the headline.
5. Whole-lake averaging is built in everywhere except Wind's per-bank exposure on four lakes.

## The model (full detail: `BOWFISHING_SYNTHESIS_MODEL`, `SPECIES`, `SPATIAL`, `TONIGHT`, `CONFIDENCE`, `EXPLANATION`)
Deterministic, ordinal, species-first, area-capable, confidence-weakest-link, template-explained. Nine rules (R1–R9), implemented in a stdlib prototype with 15 passing tests, including an exhaustive property that **unknown never improves a rating** and a test that five weak agreeing signals cannot create confidence. Mixed-evidence case from the brief (Depth modeled/low, Vegetation stale, Clarity excellent, Temp observed, Wind reliable) yields WORTH_A_LOOK / LOW with the weakest factor named. No learned model, no LLM scoring; why not: no labelled outcomes exist.

## Validation (full detail: `VALIDATION_STRATEGY`)
Outcome = species-specific shootable encounters per effort-hour. Simulation shows a ranking with zero true effect looks 1.39× better on raw catch per trip and 1.00× per effort-hour. Paired blind-area visits need roughly 30–80 pairs to confirm a 2× lift and 240+ for 1.5× at noisy counts; fine ranking ("25% better") is not field-checkable. Plan: blind expert ranking → 20-pair pilot → pre-registered paired study in the 2027 season. Tournament data is context only.

## Upstream contracts, including Depth and Vegetation interfaces (`REQUIRED_UPSTREAM_CONTRACTS`)
One common Factor record; per-Brain asks and interim behaviour; proposed `DepthZoneState` (effective depth computed by Depth from Lake Brain level, with explicit measured/modeled/unknown) and `VegetationZoneState` (presence, cover, broad type, obstruction vs habitat, seasonal state, age). Neither Brain exists; neither is counted.

## Next (full detail: `NEXT_IMPLEMENTATION_PLAN`)
1. Evidence layer in the pilot evaluation (confidence, unknowns, freshness, explanation) with no customer change.
2. Ask Biological for response bands on 3 targets in one reconciled table.
3. Blind expert ranking on the four pilot lakes.
4. Shadow-compare synthesis vs the Conditions Score before any production change.

## Files
Docs in `docs/research/intelligence/` (16 documents); code and data in `research/intelligence/` (`probe/` Swift package, `prototype/` + tests, `validation/` simulation, `tools/` + `data/` research score). Every number traces to a file in the ledger.

## Limits of this research
Dimension levels in the research ladder are judgments against written anchors (±1). Probe and prototype inputs are synthetic; stub species bands are not evidence; power numbers rest on assumed count distributions. FishIntel was audited from a private repo by a read-only subagent and is described here at structure level only. Nothing was read live from RTDB or Cloud Run.
