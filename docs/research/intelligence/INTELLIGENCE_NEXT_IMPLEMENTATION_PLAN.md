# Next implementation plan

**Not authorised by this research.** Each phase is a proposal that needs the approval noted. The order is chosen so that no phase invents science, changes customer behaviour, or counts Depth/Vegetation before they exist.

## Phase 0: decisions (no code)
Accept or reject: the research ladder as the working score; the synthesis design; the blind expert-ranking exercise. See blocker queue "Decisions needed".

## Phase 1: Evidence layer in the pilot evaluation (Intelligence-owned, no customer change)
Extend `jobs/sector-intelligence-brain/evaluation.py` (new version `intelligence-eval-v2`, additive) to emit, per pilot lake:
- `factors[]`: the common `Factor` record per Brain state (value, unit, kind, support, ageHours, staleAfterHours, horizonHours, brainConfidence, `source@version`), built only from fields the Brain already publishes; absent stays absent.
- `confidence`: weakest-link evidence confidence (rules R5–R7) per factor and overall, **without** any species rating yet.
- `explanation`: BEST / LIMITING / UNKNOWN / FRESHNESS blocks as template lines over those records (R8).
- `held[]`: any value used beyond a Brain's horizon (R7).
Still `consumesThisEvaluation: false`, still `NOT_VALIDATED`.
**Tests:** port the 15 prototype tests; golden fixtures from the real pilot evaluation JSON; fingerprint stability; platform tests stay 49/49.
**Moves (research ladder):** confidence 3→5, why 5→7 on the *pilot*; current score only moves if the customer path also adopts it (it will not in this phase), so the honest effect on the *current* research score is small (+0.0 to +0.3). Its value is making the unknowns and contradictions visible and giving the validation study something to log.

## Phase 2: Species bands from Biological (Biological-owned; Intelligence consumes)
1. Agree the band schema (species model §2) with the Biological campaign.
2. First consumer: common carp (the only species with machine rules), flagged `RESEARCH` maturity so every rating carries "species knowledge is research-grade".
3. Intelligence adds the rating step (R1–R4, R9) for assessed species only; everything else prints `NOT_ASSESSED`.
**Gate:** no Intelligence-authored bands. If Biological cannot deliver, ship nothing species-specific.

## Phase 3: Shadow comparison against the customer score (no customer change)
For the pilot lakes and a sample of fleet lakes where Brain states exist, log on every Engine request (or hourly job) the Conditions Score next to the synthesis rating. Review disagreements weekly: expected categories are the audit's cliffs, missing-data optimism, and wind-pocket effects. Output: a short disagreement catalogue that informs which production rules to change, and evidence on how often each rule fires.
**Needs:** Engine-side logging approval (a new write path). Alternative with no write: replay stored states offline.

## Phase 4: Validation Stage 2 and pilot (field, no software beyond a form)
Blind expert ranking on Guntersville, Wheeler, Wilson, Pickwick; then ~20 paired visits to estimate base rate and dispersion; re-run `power_sim.py` with real parameters; pre-register the stage-3 plan. This is the first outcome-related data point Intelligence will have ever had.

## Phase 5: Depth and Vegetation integration (conditional)
When a pilot lake has a published Depth and/or Vegetation state, add the factors through the existing record, confirm the UNKNOWN cap lifts without code changes, and extend tests with real fixtures. Until then: nothing.

## Phase 6: Prospective paired study (one season)
Sample sizes per the validation strategy; success bars pre-registered; report negative results.

## Phase 7: Production adoption (customer decision)
Only after Phase 3 shows acceptable disagreements and Phase 4/6 show PARTIAL validation: a versioned `conditions-score-v2` or a new answer field, behind a flag, parity-tested (`tonight == nights[0] == headline`), with a rollback. Update the published rubric (`r2`) at the same time.

## What not to build
A learned model; an LLM explanation writer; a single blended "fish score" per species; any map UI before Phase 4; any Intelligence-owned species band.

## Test and safety checklist for any phase
- `python3 -m unittest discover -s jobs/sector-intelligence-brain/tests` and platform tests green.
- Research prototype tests green (`research/intelligence/prototype/tests`).
- Probe re-run to confirm the production aggregator is untouched (`git diff` under `Sources/` empty for research phases).
- No RTDB writes except via the existing publisher path with approval.
