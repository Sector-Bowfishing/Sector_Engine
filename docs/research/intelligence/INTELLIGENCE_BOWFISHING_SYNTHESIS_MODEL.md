# Bowfishing synthesis model: the simplest architecture that can be trusted

**Status:** research design + a tested stdlib prototype (`research/intelligence/prototype/synth.py`, 15 tests pass). Not production, not wired to anything.

## 1. The answer format the bowfisher needs

> **Where:** NW shallow grass flat. **Target:** common carp. **When:** best from about 9 pm, wind lays down after midnight. **Why:** water temperature favourable (observed), shallow (modeled), vegetation present (observed 12 days ago), clarity usable (measured), bank protected from the 12 mph south wind (modeled exposure). **Sure?** Medium: depth is modeled and vegetation is two weeks old.

Five fields: **WHERE, WHEN, WHAT, WHY, CONFIDENCE.** Every word in WHY is one specialist's restated value with its source and age. Intelligence writes none of the science.

## 2. Design principles (from the brief, made testable)

1. **Intelligence combines; it does not measure.** It consumes a published Brain state (value, kind, age, spatial support, own confidence label) and maps it through a *species response band owned by Biological*. It never re-derives temperature, clarity, wind, depth or vegetation.
2. **Ordinal, not numeric.** Inputs become `FAVORABLE | WORKABLE | LIMITING | BLOCKING | UNKNOWN`. Output is a rating class, not a 0–100 number. A bowfisher cannot act on the difference between 71 and 74; the audit shows the current 0–100 hides 15–46 point cliffs (`CURRENT_STATE_AUDIT` §4.1). A numeric score can still be derived for the existing apps later; it must not be the primary truth.
3. **Species first.** Evaluation runs per species present on the lake. A species with no Biological response profile is `NOT_ASSESSED`, never guessed.
4. **Unknown is a cap, not a deleted vote.** Production renormalises weights over what exists, so unknown beats known-bad (96 vs 79, probe E4). Here unknown counts as LIMITING for rating, blocks the top class, and is printed.
5. **Confidence is the weakest deciding factor.** No sum, no mean, no bonus for agreement.
6. **Gates are species-independent and absolute** (lightning, fog, warnings, legal/policy). They override everything and say why.
7. **Explanation is a template over records.** No generated prose.
8. **Zones, not lakes, when the inputs exist** (see `SPATIAL_MODEL`); otherwise the honest answer is lake-level and says so.

## 3. The rule set (all implemented and tested in the prototype)

| Rule | Statement | Test |
|---|---|---|
| R1 | Replacing a known state with UNKNOWN never raises the rating (unknown ≤ LIMITING) | exhaustive over 4⁴ state grids, >500 replacements |
| R2 | A safety/legal gate yields `NOT_TONIGHT` for every species | `test_R2` |
| R3 | A BLOCKING deciding factor yields `POOR`; nothing offsets it | `test_R3` |
| R4 | `START_HERE` needs every deciding factor known and none LIMITING | `test_R4` |
| R5 | Confidence = min over deciding factors; adding agreeing factors never raises it; five weak signals stay LOW | `test_R5_*` |
| R6 | Stale evidence −1 level; lake/point support for an area decision caps at MEDIUM | `test_R6` |
| R7 | Beyond a specialist's forecast horizon a factor is UNKNOWN; persistence is never passed off as forecast | `test_R7` |
| R8 | Every explanation line carries `factor` + `source` that match an input record | `test_R8` |
| R9 | `START_HERE` also needs confidence ≥ MEDIUM, else shown as `WORTH_A_LOOK` with the reason | `test_mission_example_mixed_evidence` |

Rating ladder: `NOT_TONIGHT < POOR < UNRANKED < LOW_PRIORITY < WORTH_A_LOOK < START_HERE`. `UNRANKED` means "too little is known to say" (≥2 and ≥half of the deciding factors unknown) and is displayed as such, never as "poor".

## 4. Pipeline

```
Brain states (lake, temp, clarity, wind, biology, [depth], [vegetation])      <- read-only, with provenance
  -> Factor records {value, unit, kind, support, age, horizon, brain confidence, source@version}
  -> Gates (species-independent): storm, warning, fog, legal/policy               [owner: Policy + Weather]
  -> per species present AND assessed: response bands (Biological-owned) -> ordinal states
  -> rating (R1-R4, R9)  +  confidence (R5-R7)
  -> rank zones by (rating, confidence, count FAVORABLE); no blended number
  -> explanation: BEST / LIMITING / UNKNOWN / FRESHNESS / CONFIDENCE (+ caveats)
```

Three tiny outputs per species: ranked zones, the best time window (see `TONIGHT_MODEL`), and the explanation block.

## 5. Why not something fancier (evidence, not taste)

- **Learned model / deep learning:** needs labelled outcomes. There are none (`VALIDATION_STRATEGY`: even the paired design needs 30–240 pairs per claim). A model trained on nothing is an LLM-style guess. Revisit only after >1,000 effort-controlled observations.
- **Weighted sum with more factors:** adds numbers whose weights nobody can defend and reintroduces the missing-data optimism and cliffs measured in the audit.
- **Probabilistic fusion (Bayesian):** correct in principle, but it needs likelihoods per species × factor that no Brain publishes and no data supports. Ordinal bands with explicit unknown are the honest subset of it.
- **Where the simple model is *deliberately* conservative:** it will often say `UNRANKED` or `WORTH_A_LOOK … unconfirmed`. Today that is the truth for depth and vegetation on nearly every lake.

## 6. Prototype demonstration (synthetic inputs, stub profiles, no biological claim)

Mission example with *mixed evidence*: depth modeled with Brain label LOW, vegetation 400 h old (stale after 240 h), clarity measured, temperature observed (lake-level), wind forecast. Result: every deciding factor favourable, yet **`WORTH_A_LOOK`, confidence `LOW`**, with the caveat "would rate START_HERE but the weakest deciding factor is too uncertain to say so", and the explanation lists `FRESHNESS: vegetation 400 h old - STALE` and `CONFIDENCE: LOW (weakest deciding factor: depth)`.

Contrasts with the production aggregator on matched scenarios (probe vs prototype):
| Scenario | Production | Prototype |
|---|---|---|
| 50–59 °F water, otherwise perfect | 84 | shallow-vegetation feeder stub: cannot rate `START_HERE` (45 °F → `POOR`) |
| temp + depth unknown vs known cool | 96 vs 79 (unknown wins) | unknown → `LOW_PRIORITY` or lower |
| 47 → 48 °F | 35 → 81 | at most one rung at a band edge, flagged boundary |
| protected pocket vs lake-point wind | +6 to +38 points hidden | pocket outranks lake-level wind explicitly, with `LAKE` support caveat |

These are demonstrations of logic, not accuracy. The stub species bands are labelled as such in code and carry no evidence.

## 7. What Intelligence still owns (and nothing else)
Combination rules, gate precedence, rating/confidence semantics, ranking, time-window selection, explanation templates, and the **impact** thresholds that translate a Brain state into "does this matter to a bowfisher" *only where the species band is not yet published* (and then as a flagged interim, see `UPSTREAM_CONTRACTS`).
