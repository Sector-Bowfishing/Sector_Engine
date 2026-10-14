# BRAIN_SPEC: Sector Intelligence (`sector-intelligence`)

**Status:** conformity pass against Sector Brain Model v1 (directive 2026-10-13). Documentation only: no code, score, rubric, lifecycle, schedule or customer change. Facts come from the repository at `feat/intelligence-evidence-layer` `e9e5e571` and the Intelligence research (`docs/research/intelligence/`, branch `docs/intelligence-deep-research`). Intelligence stays **WAITING** for the specialist Brain contracts.

## Identity
**Brain ID:** `sector-intelligence` · **Slot:** `intelligence` · **Display:** Sector Intelligence
**Mission:** combine what the specialist Brains publish into a bowfisher's decision, and say how sure it is.
**Bowfishing decision improved:** where to look, when, what to target, what is limiting, which bank/zone, how confident.

## Owns / does not own
| Owns | Does NOT own |
|---|---|
| combination rules over specialist states; gate precedence (species-independent); rating and confidence semantics; ranking; time-window selection; explanation templates; the evidence record and its provenance | water temperature, clarity, wind or exposure, lake level/context/presence, depth, vegetation, species-response knowledge, legal/policy truth, weather/fog/warning sources (no Brain owns these yet; adapter with provenance) |
Intelligence never recreates specialist science. It restates published values and applies Biological-owned response bands.

## Upstream dependencies / downstream consumers
Upstream: Lake, Water Temp, Water Clarity, Wind, Biological (all consumed in the pilot); Depth, Vegetation (do not exist; placeholders, always UNKNOWN); weather/policy adapter (not yet existing). Downstream: Sector Ops (internal view), and in future the customer answer (decision pending). Today **no customer path consumes this Brain**; the customer Conditions Score reads no Brain.

## Claims by level
| Level | Claim | Status |
|---|---|---|
| 1 Provider/observed truth | restated specialist values with source, kind, age, staleness (evidence factors) | verified by tests (provenance, freshness, units restated); not recomputed |
| 2 Deterministic | weakest-link confidence; ordinal rating from bands; unknown-never-improves; freshness/carry labelling; explanation templates | `intelligence-evidence-v1`, 35 tests incl. exhaustive monotonicity; deterministic |
| 3 Sector-derived | "this species/zone is a good place tonight"; time window; improving/worsening | **NOT_VALIDATED**; blocked by Biological bands, zone Brains and field data; rated UNRANKED today |
Failure of a Level-3 claim must not hide Level-1/2 evidence: the evidence block is useful even while every species is UNRANKED.

## Claim-level maturity
| Claim | Maturity |
|---|---|
| Factor restatement with provenance and freshness | PROVIDER_VERIFIED (pilot, 5 lakes, internal) |
| Confidence propagation | VERIFIED_LOGIC, uncalibrated |
| Unknown-safe ordinal rating machinery | VERIFIED_LOGIC; no species can be rated (no approved bands) |
| Species/zone/time recommendation | NOT_VALIDATED |
| Customer answer | NOT_STARTED |

## Canonical runtime state
`/lakes/{k}/states/intelligence`, mirrored at `/snapshots/{k}/latest/sectorIntelligence`: `evaluationVersion`, `generatedAt`, `inputsUsed` (brain, version, generatedAt, status), `inputs`, `evidence {factors, species, summary, gates}`, `provenance`, `freshness`, `validation`, `customerPath {consumesThisEvaluation:false}`. Registry fields on `/brains/sector-intelligence` (dependencies, evaluation counts, engine serving). Consumers read only this, never the research archive.

## Confidence model / UNKNOWN policy / freshness
Weakest deciding factor; caps for stale, lake-level support, forecast lead, Brain label, readiness, presence evidence and band tier; no sums or bonuses. UNKNOWN is a first-class output: an unknown deciding factor gives `UNRANKED` (below `POOR`); missing band ⇒ `UNSUPPORTED`; beyond a Brain's horizon ⇒ UNKNOWN with the current value shown as `carried`. Freshness: each factor carries age and `stale`; staleness thresholds come from the owning Brain (`staleAfterHours`), never from Intelligence.

## Execution model
| Question | Answer |
|---|---|
| What makes it change? | a specialist state republished or went stale; species presence/knowledge version; catalog; serving Engine revision; evaluation version |
| When run / skip? | run when the input fingerprint changes; skip otherwise (`orchestration.plan`: fingerprint plus a 24 h maximum-age backstop) |
| Needs a clock? | only as a staleness backstop (condition C/D); no compute clock |
| Upstream versions that matter | each of the five Brains' registration, health, version, lifecycle; per-lake input `generatedAt`/status |
| Max acceptable state age | 24 h registry backstop; per-input thresholds from the owning Brain |
| Customer request trigger? | **Never.** Intelligence must not compute on a page view |
| Input fingerprint | `sib.fingerprint` (registry) and `ev.inputs_fingerprint` (pilot inputs, includes `EVAL_VERSION`) |
| Fleet recompute? | no; pilot lakes only; future: only the lakes whose inputs changed |

## Score dimensions
Published `sector-intelligence-score-v1` (8 dimensions, 94% of the 4.8 is wiring) and the research ladder `intelligence-decision-readiness-r1` (9 dimensions; research only, not canonical). Critical dimensions for a customer claim: species, where, confidence, validation. Rubric mismatch and the `r2` proposal are in `docs/research/intelligence/INTELLIGENCE_PRODUCT_RESET_ASSESSMENT.md` (proposal; rubric not changed).

## Lifecycle and production requirements
Current: **CALIBRATION** (internal pilot) per the registry; on the common ladder this is **SHADOW** for the evidence layer (internal, no customer dependency). Not PRODUCTION_READY: needs approved Biological bands, at least one zone-level Brain, a gate source, scheduled upstream Brains, pre-registered field validation (PARTIAL at minimum), and a customer-path decision. General policy (overall ≥ 8.0 and critical ≥ 7.5) is unchanged here.

## Storage budget
Runtime payload ≈ 12.5 KB per lake (3-species fixture). Research directories are 25 MB each after cleanup (well under the 5 GB review threshold); no dataset retained locally above 25 MB.

## Research stop conditions
No new specialist science. Open questions only when the answer changes a bowfisher decision: (1) do approved Biological bands exist, (2) what are the Wind/Depth/Vegetation contracts, (3) what does blind-ranking field data show. Anything else: UNKNOWN or WAITING.

## Ops summary / customer exposure
Ops should show displayed 4.8, underlying capability, claim maturity above, gates `NOT_EVALUATED`, `ratingsIssued: 0`, blockers, next expected update (fingerprint-driven). **Customer exposure: none.** Weak or unvalidated claims must not reach customers; the evidence block is internal.

## Cost and runtime expectations
No provider calls of its own. Reads Brain RTDB state already published; republish only on fingerprint change; small payloads; scale-to-zero friendly. No research artifact is read at runtime. Known runtime dependency risk: none large. Open item: the pilot publisher is unscheduled on `main` (an hourly orchestrator cycle exists on the unmerged `feat/cost-efficient-scheduling`).

## Compatibility with the future shared Field Validation Framework
Intelligence-relevant trip fields: lake, time, area/zone id, target species, effort minutes, sightings in range and count, shots, observed wind/chop, clarity, vegetation, depth cue, the rating and `evidence` version in force at the time (join key = evaluation `generatedAt` + `evaluationVersion`). The blind-ranking template (`research/intelligence/validation/blind_ranking_log_TEMPLATE.csv`) uses exactly these so one trip can later feed Wind, Depth, Vegetation and Biological validation. Not implemented here; no independent framework is being built.

## Rubric audit (dimensions below 7.5)
Every research-ladder dimension is below 7.5. Which measure the intended capability: species, where, when, why, confidence, validation. Which over-reward something else: the published rubric's connectivity/handling/provenance/runtime (wiring, not answers), and the exclusion of `synthesisQuality` as UNKNOWN. Proposal only.
