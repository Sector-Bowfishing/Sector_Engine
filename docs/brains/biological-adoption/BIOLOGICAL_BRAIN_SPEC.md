# BRAIN_SPEC: Biological Brain (`biological-state`)

Conformity pass against the Sector Brain Model (2026-10-14). No research was restarted; every statement below is drawn from the existing, verified Biological work. Boundaries still in force: nothing merged to main, no customer deployment, no lifecycle promotion, per-lake publication OFF, no production-table change.

## 1. Identity and mission
* **Brain ID:** `biological-state` (display "Biological Brain"; slot `biology`; species knowledge at `/species/{id}`).
* **Mission:** know what the fish Sector reports tend to do, and say so with honest confidence, so Intelligence can match it to environmental truth.
* **Bowfishing decisions improved:** WHERE to look (habitat classes), WHEN (season/spawn window/night), WHAT conditions are favorable or limiting (rising warm water, cold, turbidity…), and HOW sure (confidence, transfer, validation tier).

## 2. Ownership
| | |
|---|---|
| **Owns** | species-response knowledge: condition-feature meaning (`warmRise`…), response bands, habitat/depth-class/vegetation-association preferences, spawn windows (as ranges), night-movement support, per-rule evidence/confidence/transfer, the Biological State (internal pilot), and the Biological validation chain (frozen rules, predictions, observation schema, preregistered criterion) |
| **Does NOT own** | species presence (Lake Brain); water temperature (Water Temp); clarity (Clarity); lake level/trend/discharge/operations (Lake); depth (Depth); vegetation state (Vegetation); wind (Wind); the final "where tonight" synthesis (Intelligence); legality/regulation; production species table (customer-facing Engine) |
| **Upstream inputs** | Lake (trendState, presence; tributary discharge once published), Water Temp (temperature, 24 h trend), Clarity (clarityFt), Depth (zone shares, when published), Vegetation (observed cells, when published), Engine calendar (month, daypart). Contracts: `BIOLOGICAL_CROSS_BRAIN_INPUT_CONTRACTS.md` |
| **Downstream consumers** | Sector Intelligence (evaluated state; not yet wired); Sector Ops (registry, facts, score); nothing customer-facing |

## 3. Claims by level, with per-claim maturity
Vocabulary: PROVIDER_VERIFIED · VERIFIED (deterministic, tested) · CALIBRATION · NOT_VALIDATED · UNAVAILABLE.
| Claim | Level | Maturity | Basis |
|---|---|---|---|
| Lake trend / pool level, temperature, clarity (relayed inputs) | 1 | PROVIDER_VERIFIED by the owning Brain; Biological only sanity-checks (range, vocabulary, freshness) | `contracts_in.py`, `bio_state.normalize_inputs` |
| `waterTempBand`, `temperatureTrend`, 24 h `temperatureCrossing*`, `daypart`, `clarityBand`, `risingStage/fallingStage` | 2 | **VERIFIED** (unit/boundary tests; lower-bound-inclusive bands; F→C rounding) | `features.py`, tests |
| `warmRise`, `coldRise` definitions | 2 (definition) | VERIFIED as arithmetic; whether fish respond is Level 3 | `features.py` |
| `spawnWindow` (month + temperature range) | 2 | VERIFIED as arithmetic; the ranges themselves are Level 3 literature | `spawn_window` tests |
| Depth availability bounds, observed-only vegetation presence | 2 | VERIFIED validators; **inputs unpublished** → UNKNOWN fleet-wide | `contracts_in.py` |
| `rapidDischargeIncrease` | 2 | **UNAVAILABLE** (no Brain publishes it) | |
| Species response bands, habitat preferences, night support | **3** | **NOT_VALIDATED** (literature tier T1 only); 48 rules at LOW/MEDIUM confidence; the four focus species are the first CALIBRATION candidates once trips exist | rules, packets |
| Spawn windows as predictions of where spawners are | 3 | NOT_VALIDATED | |
| "Rule says favorable → more shootable fish per effort-hour" | 3 | **NOT_VALIDATED**; preregistered test frozen | `…PREREGISTRATION_v1` |
A failure of a Level-3 claim does not invalidate the Level-1/2 rows above.

**Taxonomy invariant:** claim level and validation maturity are separate axes. Level says who created the claim (1 provider/observed, 2 deterministic derivation, 3 Sector-derived intelligence); maturity says how far it is trusted. Species response bands, habitat, night support and spawn-response interpretation are Level 3 even while NOT_VALIDATED, and stay Level 3 through CALIBRATION and VALIDATED. Deterministic environmental transforms are Level 2.

## 4. Canonical runtime state
Each state carries a `claims` block (inputs = Level 1 PROVIDER_VERIFIED, features = Level 2 VERIFIED, speciesResponses = Level 3 NOT_VALIDATED) and has an Intelligence-facing projection, `evaluated_view.intelligence_view` (see the Intelligence band contract).
Per lake: `kind biological-state · stateVersion · status PILOT_INTERNAL · context{region, waterbodyType, month, daypart} · inputs{brain, status, generatedAt, brainVersion} · features{state, reason} · species[{presence, evaluated, knowledge{state}, seasonState, responses[], habitat[], spawnWindow, nightMovementSupported, unknowns[]}] · unknowns[] · provenance{rulesVersion, featuresVersion} · validation NOT_VALIDATED · customerPath{consumed:false}`. Each band carries `confidence, evidenceBasis, region/season applicability, transferability, behavior, reason`. Species-level static `responseBands` (PROPOSED) are published on the species node. Compact: a pilot state is ≈ tens of KB; the largest species node is 13 KB.

## 5. Confidence model, UNKNOWN policy, freshness
* Confidence per rule is capped by **independent evidence streams** (1 → LOW, 2 → MEDIUM, ≥ 3 → HIGH only with a Southeast-transferable basis); degraded input lowers a band one level; rules that disagree resolve to UNKNOWN naming the conflict.
* UNKNOWN is returned for: missing/stale/implausible input, no covering rule, conflicting rules, present-but-unassessed species. No placeholder environmental truth, no speculative rule to remove an UNKNOWN.
* Freshness: input older than **36 h** → UNKNOWN for dependent features. Species knowledge is version-driven and never stale by age.

## 6. Execution model
| Question | Answer |
|---|---|
| What makes it change? | (a) the private bundle version (rules/species knowledge); (b) a material change in a specialist input or in species presence; (c) elapsed time through daypart and month |
| When run / skip? | Species knowledge: publish when `latest.json` version/manifest differs (manual today). State: evaluate on demand for a pilot lake before a trip; **skip all writes/logs if `state_fingerprint` is unchanged** (implemented, tested) |
| Needs a clock? | **No cron.** Schedule test: (A) no external provider; (B) prospective validation needs a snapshot BEFORE an outing, but that is on-demand per observed lake, not periodic; (C) daypart/month change the state, which is why it is evaluated at trip time; (D) no maintenance need. A cheap daily snapshot per observed lake is justified only once testers exist |
| Upstream version changes that matter | Lake/Water Temp/Clarity state versions, presence version, `rulesVersion`, `featuresVersion` |
| Max acceptable state age | inputs 36 h; an evaluated state is meant to be used the same day |
| Input fingerprint | `bio_state.state_fingerprint` (volatile timestamps/ages removed); `orchestration.plan_state` returns WRITE/SKIP |
| Fleet recompute | never: pilot lakes only; per-lake, affected-subset |

## 7. Execution / scheduling matrix
| Component | Current trigger | Recommended trigger | Needs schedule? | Fingerprint? | Reason |
|---|---|---|---|---|---|
| Provider ingestion | none (Biological ingests no provider) | none | No | n/a | consumes other Brains' states |
| Species knowledge publish | manual (`run.py --write`) | manual / orchestrator on bundle version change | No | yes: researchVersion + manifest sha | version-driven, never time-driven |
| Biological State compute | manual dry run (`run_state.py`) | on demand per observed pilot lake; later dependency-driven by the orchestrator | No cron | **yes** (`state_fingerprint`) | inputs change, not clocks; page views never trigger it |
| Validation logging (predictions) | manual cycle | one pre-trip snapshot per observed lake; log only when activated and not a repeat (24 h) | Only once testers exist, and then per outing | yes (repeat suppression) | prospective validation needs timed snapshots |
| Observation ingestion | manual `tools/observations.py` | manual / future app | No | n/a | small, human-entered |
| Score publication | manual platform publisher (`score_brains.py`) | platform orchestrator | Platform-owned | platform | the shared platform owns durable publication; the stale-score protection on the unmerged scheduling branch must be preserved (this branch does not touch publication code) |
| Control-plane publication | same manual publisher | platform-owned | Platform-owned | platform | Ops browsing is never a compute trigger |
| Maintenance / staleness | none | platform health check | Platform-owned | n/a | species knowledge cannot go stale by age |

## 8. Scoring
`biological-state-score-v1` (published **4.6**, one gate: no VALIDATED species ≤ 6.0). Dimensions: registryCompleteness, assessedCoverage, knowledgeDepth, evidenceQuality, contradictionsGaps, regionalTransfer, biologicalStateImpl, biologicalStateValidation, productionIntegration. **Critical (recommended, not published by Engine):** knowledgeDepth, evidenceQuality, regionalTransfer, biologicalStateImpl, biologicalStateValidation. Rubric audit and proposals: `BIOLOGICAL_RUBRIC_MISMATCH_PROPOSAL.md`. Research maturity vs official score: the 4.9 "research potential" is a simulation, never presented as official.

## 9. Claim-level validation requirements
| Level | Required for Biological |
|---|---|
| 1 (relayed inputs) | source identity, units, range, vocabulary, freshness (done, tested) |
| 2 (features, bands arithmetic, validators) | formula/boundary/sign tests, determinism (done; 146 tests) |
| 3 (response bands, habitat, spawn, night) | independent source review (done at literature tier); reviewer approval (pending); **prospective field validation: preregistered, frozen, ≥ 30 independent trips per species per system, ≥ 2 systems for VALIDATED** (not started: 0 observations) |

## 10. Lifecycle (standard vocabulary)
Registry shows **PROFILED**. Capability: Biological State IN_PROGRESS (internal). By the standard ladder Biological is between PROFILED and **SHADOW**: it becomes SHADOW when the truthful per-lake state is published internally (Ops-only, no customer dependency), which needs Michael's approval; **no promotion is made here.** CALIBRATION starts when field trips accumulate; PRODUCTION_READY needs the gates in §11.

## 11. Production requirements
Overall ≥ 8.0 and every critical dimension ≥ 7.5 (current policy, unchanged). Ceiling without field validation is 6.0 and several critical dimensions cannot reach 7.5 without VALIDATED species (`BIOLOGICAL_PRODUCTION_READINESS_MATRIX.md`). Additionally: Intelligence wiring, the Depth/Vegetation/discharge inputs, rollback (bucket generation retained), monitoring through the platform, cost-controlled execution.

## 12. Storage, cost, runtime
* **Storage budget:** research directory ≤ 50 MB expected (now 6.1 MB; review threshold 5 GB, 2 GB per dataset: nowhere near). Recipe over warehouse: source ledgers hold URLs/DOIs; extracts are small.
* **Research stop conditions:** a rule gets a targeted check only when a specific blocker needs it; stop when answered or the source is unavailable (done for Snedden 1999, Lackmann 2023, southern longnose/bowfin temperatures). No new campaign without a QUESTION / WHY / CLAIM LEVEL / DECISION CHANGED / CHEAPEST EVIDENCE / STOP CONDITION.
* **Cost:** no schedule, no polling, no provider calls of its own; publication ≈ 127 KB per version; a pilot evaluation is a handful of RTDB GETs and pure arithmetic.
* **Runtime:** consumes only the compact rules bundle and already-published Brain states; it never reopens `packets/`, `source_extracts/` or any research archive. No unexpectedly large runtime data or slow recompute.

## 13. Exposure and Ops
* **Customer exposure policy:** none. No band, rule or species claim is customer-visible; Intelligence must consume the evaluated Biological state later and never recreate species science.
* **Ops summary:** score, lifecycle, capability, validation, species totals, `facts[]`, `transferSummary`; see `BIOLOGICAL_OPS_VISIBILITY_GAP.md` (underlying/gates/breakdown still not rendered by Ops).

## 14. Compatibility needs for a future Sector Field Validation Framework
One bowfishing trip should produce truth for several Brains. Biological's observation record is already trip- and zone-based (`tripId`, `lakeId`, `observedAt`, zone, effort, species + ID confidence, encounter, shootableCount, optional depth/vegetation/level/wind/clarity context). To share trips it will need: (1) a **common trip envelope** owned by the framework (`tripId`, observer pseudonym, lake, start/end time, weather and level snapshot references); (2) a **shared zone identity**: the same bank/segment/area ID that Wind, Depth and Vegetation use, mapped to Biological's habitat classes (today `zone` is a habitat class, not a geometry); (3) per-Brain blocks keyed by `tripId + zoneId` (Biological: species/encounter/shootable/effort; Wind: predicted vs observed exposure; Depth: sonar depth; Vegetation: surface vegetation seen); (4) a single observer/consent and append-only ledger policy. Biological will not build this independently; the CSV intake is a stopgap that maps cleanly onto such an envelope.

## 15. Open items for the model review
Scorer `regionalTransfer` reading; a SHADOW rubric level; claim-level maturity as a published structure (today only in this document); a platform-level facts renderer for Ops.
