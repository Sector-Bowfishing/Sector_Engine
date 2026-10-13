# Biological Brain: Ops visibility gap

**Method.** Engine side: live read-only GETs of the Brain RTDB on 2026-10-13 (`/control/overview`, `/scores/biological-state`, `/brains/biological-state`, `/validation/biological-state`, `/health/brains/biological-state`). Ops side: **read-only** shallow clone of `Sector-Bowfishing/Sector_Ops` `main` @ `1742187` (source reading; the deployed UI was not viewed, so "displays" means "a render path exists in code"). Ops was not modified.

**Verdict for "Ops hasn't visibly changed".** For Biological it is **both**, in this order:
1. **ENGINE STATE (primary).** The published Biological state has not changed since 2026-10-13T03:56Z: the registry still says `biologicalState.status = NOT_STARTED`, `researchVersion 2026-10-12.1`, score 4.0. The adoption work (rules, pilot, validation clock, IN_PROGRESS capability, 4.6) lives only in the unpublished candidate bundle `2026-10-13.1`. There is nothing new for Ops to show.
2. **OPS PRESENTATION (secondary).** Even after the candidate is published, Ops would show the score, the lifecycle badge, the per-lake-state status/note and the existing species counts. The new rule / validation / pilot facts have no render path.

| Field | Engine path | Engine publishes? | Ops consumes? | Ops displays? | Note |
|---|---|---|---|---|---|
| Score (value, scale, version, basis, completeness, updatedAt) | `/control/overview.brains["biological-state"].score`; `/scores/biological-state` | **PUBLISHES** (4.0; `scoreUpdatedAt 2026-10-13T19:51Z`) | **CONSUMES** (control hub; `brainScore`/Overview) | **DISPLAYS** | Ops shows "PROFILED · 4.0/10" and applies its own 8.0/7.5 production guardrail (no warning: not PRODUCTION) |
| Uncapped score | `/scores/biological-state.uncapped` | PUBLISHES (4.0) | not in `control.brains.score`; typed for the Engine score only | **DOES NOT DISPLAY** | **OPS GAP** (small) |
| Score breakdown by dimension + gates | `/scores/biological-state.scoreBreakdown`, `.scoreBlockers` | PUBLISHES | **DOES NOT CONSUME** (types mark it "future contract") | **DOES NOT DISPLAY** | **OPS GAP**: dimension values, the 4.0/6.0 gates and "what moves each gate" are invisible |
| Lifecycle status | `/control/overview.brains[...].status`; `/brains/biological-state.status` | PUBLISHES (`PROFILED`) | CONSUMES | DISPLAYS | |
| Capability / per-lake state status + note | `/brains/biological-state.responsibilities.biologicalState.{status,note}` | PUBLISHES (`NOT_STARTED`) | CONSUMES (`BiologyStatusStrip`) | DISPLAYS | Candidate would change this to `IN_PROGRESS`; Ops would render it with no code change |
| Validation state | `/control/overview...validation.status`; `/validation/biological-state` | PUBLISHES (`NOT_VALIDATED`) | CONSUMES (Validation tab) | DISPLAYS status + note | `validationFoundation{frozenRules, predictionsLogged}` (candidate only) would be **ignored** by Ops |
| Species total / assessed / not assessed | `/brains/biological-state.responsibilities.speciesKnowledge` | PUBLISHES (29 / 27 / 2) | CONSUMES | DISPLAYS | |
| **Species supported** (≥1 usable rule or approved band) | none | **DOES NOT PUBLISH** | n/a | n/a | **ENGINE GAP.** `control.brains[...].coverage.supported = 0` counts *lakes*, not species. Candidate adds `speciesWithUsableRules` (9) |
| **Usable / draft / frozen rule counts** | none (candidate: `responsibilities.biologicalState.{usableRules,draftRules,frozenRules}`; per species `machineRules`) | **DOES NOT PUBLISH** (until the candidate is published) | **DOES NOT CONSUME** | **DOES NOT DISPLAY** | **ENGINE GAP now; OPS GAP after publication** |
| Validated species count | `/brains/biological-state.breakdowns.researchMaturity` | PUBLISHES maturity breakdown (`RESEARCH 20`, `NOT_STARTED 9`; no `VALIDATED` key) | Ops recomputes maturity counts client-side from `/species` | Per-species maturity badge only; **no "validated species" tile** | **OPS GAP** (tile) |
| Pilot count / pilot lakes | none (candidate: `pilotLakes`) | **DOES NOT PUBLISH** | no | no | **ENGINE GAP** |
| Prediction count | none (candidate: `predictionsLogged`) | **DOES NOT PUBLISH** | no | no | **ENGINE GAP** |
| Freshness / last updated | `control.brains[...].{stale, staleReason, lastSuccessfulRun, healthAt}`; `stalenessModel: VERSION` | PUBLISHES (`stale:false`, last run 2026-10-13T03:56Z) | CONSUMES | DISPLAYS | Biological is version-driven, so "stale" never fires; a stale *bundle* would not show |
| Last evaluated (per-lake state) | none | **DOES NOT PUBLISH** | no | no | **ENGINE GAP** (no per-lake publication, by design) |
| Bundle / research version | `/brains/biological-state.researchVersion`, `.manifestRef`, `.scoringVersion` | PUBLISHES (`2026-10-12.1`, `species-v2`) | CONSUMES | DISPLAYS (strip) | |
| Rules version / features version | none (candidate: `rulesVersion`) | **DOES NOT PUBLISH** | no | no | **ENGINE GAP** |
| Blockers | `/control/overview.brains[...].blockers[]` | PUBLISHES (4 items) | CONSUMES (typed) | Only in Overview **Attention** and only when health is fair/poor | **OPS GAP**: a HEALTHY brain's blockers are not shown on its page |
| Next opportunity | `control.brains[...].nextOpportunity`, `/scores.nextScoreOpportunity` | PUBLISHES | typed | not verified rendered | check in the deployed UI |


## POST-PUBLICATION VERIFICATION (live Engine state 2026-10-14; Ops source `main` @ 12b59f7, read-only)
The candidate `2026-10-14.4` is published and `score_brains --write` has refreshed the platform-owned nodes. Verified directly in the Brain RTDB:
`/scores/biological-state` = **4.6** (uncapped 4.6, completeness 95%, updated 2026-10-13T21:29Z) · `/control/overview.brains["biological-state"]` = status PROFILED, score 4.6, validation NOT_VALIDATED, stale false, last run 2026-10-13T21:28Z, 2 blockers (speciesValidation gate; biologicalStateValidation), next-opportunity text updated · `/brains/biological-state.responsibilities.biologicalState` = **IN_PROGRESS** / validation NOT_STARTED, researchVersion 2026-10-14.4, 11 `facts[]`, counters (usable 48 · draft 10 · retired 3 · frozen 51 · predictions 7 · observations 0 · trips 0), no per-lake node written.

| Item | Engine | Ops can consume | Ops will display (from source reading) |
|---|---|---|---|
| Score 4.6 | yes | yes | **yes** (score tile; Overview card) |
| Capability IN_PROGRESS + note | yes | yes (`BiologyStatusStrip`) | **yes** (badge + note on the Biological page) |
| Validation NOT_VALIDATED | yes | yes | **yes** |
| Species totals (29 / 27 / 2) | yes | yes | **yes** |
| Research version 2026-10-14.4, rubric | yes | yes | **yes** |
| Last updated / freshness | yes | yes | **yes** |
| Maturity badges per species | yes | yes (computed client-side) | yes; **no "validated species" tile** |
| `facts[]` (rule counts, frozen, predictions, observations, trips, validated species, pilots, rules version) | **yes** | **no** (no field typed or rendered) | **no** |
| Counters under `responsibilities.biologicalState` | yes | no | no |
| Score breakdown by dimension (`/scores/biological-state.scoreBreakdown`) | yes | typed as a future contract | **no** |
| Score gates | yes (`scoreBlockers`: 6.0 speciesValidation) | **yes**: Ops main now has `ScoreCapPanel`/`ScoreCapLine` | **only when a gate is below the underlying score.** At 4.6/4.6 no gate binds, so the 6.0 gate is **not shown** |
| Blockers (2) | yes | typed | **no** for a healthy Brain (shown only in the Overview Attention list for fair/poor health) |
| Pilot state / lakes | counters only | no | no |
| `responseBands` per species | yes (PROPOSED) | no | no |

**Verdict:** Engine now publishes the real capability; the **visible** change in Ops is the score (4.0 → 4.6), the Biological State badge (IN_PROGRESS), the research version and the blockers list inside control data. The new maturity facts, the 6.0 gate, dimension breakdown and blockers remain **OPS PRESENTATION** gaps. Engine-side remainder: `/scores/biological-state.nextScoreOpportunity` still carries the pre-publication wording until the score value next changes (the control overview already shows the corrected text).

## Engine-side change made in the candidate (now published)
The candidate bundle's registry now carries a generic, Engine-computed `facts[]` list `[{label, value}]` (Species with usable rules, Usable / Draft / Retired / Frozen rules, Predictions logged, Observations logged, Independent trips, Validated species, Pilot lakes, Rules version) in addition to the `responsibilities.biologicalState` counters (`usableRules`, `draftRules`, `retiredRules`, `frozenRules`, `predictionsLogged`, `observationsLogged`, `independentTrips`, `speciesWithUsableRules`, `pilotLakes`, `rulesVersion`). **Once published, the ENGINE GAP rows for supported species, rule counts, pilots, predictions, rules version become ENGINE PUBLISHES; the OPS GAP remains until Ops renders `facts[]` (or the new `responsibilities` fields).** Score gates and dimension values are still only in `/scores/biological-state`.

## What the Engine could add so Ops needs no per-brain code
A generic, Engine-computed `control.brains[id].facts[]` of `{label, value, tone?, hint?}` (rendered verbatim) would let every Brain surface its own maturity facts (rules, pilots, predictions, validated species, gate requirements) without Ops learning each schema. For Biological the first facts would be: usable / draft / frozen rules, species with usable rules, pilot lakes, predictions logged, independent trips, VALIDATED species, rules version, and "what moves each score gate". This is an Engine contract change (not made here) and an Ops renderer (not made here).

## Required actions
| Owner | Action |
|---|---|
| Michael | Approve publishing the candidate bundle (registry change) so Engine state actually changes |
| Engine | Add the compact Biological facts above (and `speciesWithUsableRules`) to the registry / control summary; mirror `scoreBreakdown` gates into `control.brains[id].scoreGates` |
| Ops | Render score gates and dimension breakdown; show blockers on the Brain page; add a Validated-species tile; render unknown `facts[]` verbatim |
