# Wind Brain: Bowfishing-First V2 (specialist-aligned)

Status: **implemented in nonproduction, SHADOW.** Lifecycle stays CALIBRATION, `customerIntegrationMode` stays `none`, Publisher cutover status stays SHADOW. Nothing here is deployed, published or read by a customer path. Owner approval is needed for every activation step in §10.

Rules stay in `BRAIN_OPERATING_CONTRACT.md`. This file explains the V2 design and the decisions behind it.

## 0. Specialist alignment (2026-10-19, same day, before any adoption)

Owner rule: **specialist Brains own their domains; Sector Intelligence owns cross-Brain synthesis and the final bowfishing recommendation.** The first V2 cut (PR #34, `c0ccf660`) was wind-only in its inputs but used recommendation-flavoured names. The changes below are terminology and contract boundary only; physics, ranking rules, thresholds, scenario logic and evidence numbers are identical.

| Was | Now | Why |
|---|---|---|
| package `sector_wind.decision`, contract `sector-wind-bowfishing-decision-v1`, `decisionSchema` | `sector_wind.assessment`, `sector-wind-exposure-assessment-v1`, `assessmentSchema` | Wind assesses wind; it does not make the bowfishing decision |
| `fishingImpact` {SURFACE_NOT_LIMITING ... VERY_POOR, "spotting fish is very difficult"} | `windSurfaceDisturbance` {level NONE ... VERY_HIGH, surfaceClass, mechanism, "High wind-driven surface disturbance expected (...)"} | wind alone cannot judge fishing quality; same class-to-level mapping |
| output key `trip`, arg `trip_hours` | `timeline`, `window_hours` | a wind time window, not a fishing trip |
| `scope.doesNotAnswer` without "where to bowfish" | adds "where to bowfish", "overall fishing opportunity", and `synthesisOwner: sector-intelligence` | explicit hand-off to Intelligence |
| (none) | `schema.boundary_problems`: forbids fish, recommendation, opportunity, suitability, best, catch or score keys, and fishing language outside the disclaimers; part of `check()` | the boundary is enforced, not only documented |
| JSON Schema open objects | `additionalProperties: false` on the assessment, the bank and the alternatives | no new field can be added without a contract change |
| rubric `wind-bowfishing-intelligence-v2` "Bowfishing Intelligence" | `wind-specialist-capability-v2` "Wind Capability" | the score measures wind capability, not bowfishing intelligence |
| categories geographic / surface / decision / temporal intelligence; items DI1-DI3 | wind exposure geometry / wind-driven surface / **wind exposure assessment** / wind temporal behaviour; items EA1-EA3 | "decision" measured only wind-domain work (surface-class forecast agreement, exposure-ranking reproducibility, wind-exposure alternatives) |
| scenario suite `wind-bowfishing-scenarios-v1` | `wind-specialist-scenarios-v1` | same 18 scenarios |
| evidence key `decisionAccuracy` | `surfaceClassAgreement` | it is forecast-vs-observed wind agreement on the surface class |

**Score: still 6.7**, because no weight, threshold, criterion, scenario or evidence value changed (evidence regenerated: identifiers only). Every item was reviewed against the boundary. None reads fish, water-clarity, lake-habitat or combined-opportunity evidence; the former "Decision" category was already wind-only and is renamed, not re-scored. No consumer of the old names existed (repository and Ops checked), so the rename carries no compatibility shim.

## 1. Why

The October 19 scoring-objectives audit found that Wind already had real bowfishing logic: ranking 6,504 Guntersville banks, telling protected from exposed shores, giving wave heights and nearby alternatives. That logic lived in research-labelled code, nobody consumed it, and no score measured it. The certification score (3.3) measures something else: proven on the water plus operational maturity. V2 moves the bowfishing logic into a supported runtime layer. It also measures that layer separately from scientific confidence and production readiness.

## 2. Three functional layers (logical, one code tree)

| Layer | Responsibility | Code |
|---|---|---|
| **1. Wind Intelligence** | Forcing (NBM / RTMA-RU / METAR), direction convention (FROM, true north), forecast vs observation labels, frozen duration rule, frozen CEM / SPM84 9-ray fetch physics, Unknown handling | `ingest.py`, `grib.py`, `interp.py`, `sample.py`, `store.py`, `live.py`, `brain/state.py`, `bowfishing.py` (physics section). **Unchanged** except one additive key (below). |
| **2. Wind Exposure Assessment** | Shoreline wind exposure, wind-sheltered banks, surface semantics, wind-driven surface disturbance, hourly wind timeline, wind-exposure alternatives, confidence, limitations, the canonical assessment | `assessment/ranking.py`, `semantics.py`, `timeline.py`, `limitations.py`, `build.py`, `schema.py` |
| **3. Learning & Validation** | Deterministic capability scenarios, evidence for the platform scorer, research gaps, validation entry points | `assessment/scenarios.py`, `research/tools/sector_wind_research/measurement_evidence.py`, `research/GAPS.json`, `contracts/wind-validation-entrypoints-v1.json` |

There are no new services, schedulers, Brains or Publisher, and no AI. The only change to Layer 1 is that `bowfishing.evaluate_bank` now also returns `predictedHm0RangeIn`: the ±1 m/s × 0.7–1.3 fetch range it already computed for `confidence` and then threw away. The change is additive and the physics is unchanged.

## 3. Shoreline ranking and alternatives (Phases 3-4)

`assessment/ranking.py` is an adapter, not a reimplementation. Ordering, exposure rank, confidence, reasons and the frozen nearby-alternative rule are `bowfishing.rank_banks_for_wind` / `evaluate_bank` / `nearby_alternatives`, exactly as frozen in BWIS v1. The adapter:
- takes the runtime fetch object (`state.decode_fetch_table` layout) and a canonical lake id;
- bounds output to the top-N sheltered, the top-N exposed and the requested banks (N ≤ 25). The full ranking is `ranking.full_ranking()` for a storage artifact and is never inlined;
- counts Unknown (below-resolution) banks and never ranks them, lists them as sheltered or offers them as alternatives.

**Finding:** the frozen "nearby alternative" rule (a lower surface class, or ≥ 50 % shorter fetch with no worse class) finds *less exposed* banks, not necessarily *sheltered* ones. At 15 mph SW the alternative for the most exposed Guntersville bank was another High-exposure bank 80 m away with 7.9 km of fetch. V2 keeps the frozen rule under its honest name, `lessExposedAlternatives`, and adds one new rule, `nearestSheltered`: the nearest banks within 10 km whose exposure for this wind is Sheltered or Low. Both carry the note that distance is a straight line on the same lake, and that access, launch, private property, navigation, fish and safety are not checked.

## 4. Exposure vs surface semantics (Phase 6)

The audit case: bank GT-001172 at 15 mph SW was labelled PROTECTED (exposure) and "Light chop" (surface). **Investigation:** these are two different but compatible concepts, and nothing is wrong with the physics.
- **Wind exposure** is the chop class of the modeled wave height Hm0: whether waves can *build*. At 31 m of fetch they reach 0.7 in.
- **Predicted surface** is the frozen map P = max(chop class, texture floor). At 15 mph (6.7 m/s, texture T4 "Broken") the wind roughens the surface even where waves cannot build, so P = 3.

The genuine defect was **terminology**. The frozen surface label for class 1 is "Protected", the same word as exposure rank 1, so one bank read as both protected and choppy. V2 keeps every frozen class, bound and internal label (`bowfishing.CHOP` is unchanged). It changes only the user-facing wording:
- exposure labels Sheltered / Low / Moderate / High / Extreme exposure;
- surface labels Flat / Ripple / Light chop / Moderate chop / Rough;
- `predictedSurface.driver`: `WAVES` or `WIND_TEXTURE`, saying which mechanism sets the surface.

The case now reads: *"Sheltered from the 15 mph SW wind… waves stay small, but the wind itself roughens the surface (broken texture), so the surface reads light chop."* Invariants (surface ≥ wave class; WAVES ⇒ equal; WIND_TEXTURE ⇒ texture raised it; height inside its own range) are checked on every bank for 9 speeds × 8 directions in the tests.

Wind-driven surface disturbance (`windSurfaceDisturbance`: level NONE / LOW / MODERATE / HIGH / VERY_HIGH, the surface class, the mechanism WAVES or WIND_TEXTURE, and a sentence such as "High wind-driven surface disturbance expected (moderate chop, modeled waves about 7.3 in).") is a wind-domain statement derived only from the surface class. It replaced the earlier `fishingImpact` field (see §0).

## 5. Time-dependent conditions (Phase 7)

`assessment/timeline.py` evaluates a requested time window hour by hour with frozen M0 (CEM + frozen duration rule over the hourly series, optionally preceded by pre-window history). It reports wind threshold crossings, direction shifts of 45° or more ("different shores are now exposed"), per-bank exposure changes (SHELTERED / MODERATE / EXPOSED) and a summary per bank.

**Wave memory.** M0 has none: modeled chop drops the moment wind eases. The M4 fetch-scaled memory candidate **failed** its pre-registered promotion rule (rule 1, 2 points of retention short), so it is not run, not even in shadow. Running a failed candidate behind a flag would be silent promotion by another name. Instead every hour after a blow where M0 is likely optimistic is flagged `recessionOptimistic`, and the trip carries the `waveMemory` disclosure. When no pre-trip history is supplied, the timeline says early-hour waves may be *under*-estimated. The work stays in gap WIND-CNF-002.

## 6. Strong wind (Phase 13 of the handoff)

Deterministic NBM detected 0 of 49 observed ≥ 15 mph night events (CAL+H1). V2 handles this as an honest-output problem, not a modeling one:
- `STRONG_WIND_UNDERFORECAST` (WARNING) is attached to **every** assessment, because the failure is a *missed* event, so a light forecast cannot exempt an assessment;
- confidence is LOW for forecast wind ≥ 10 mph, any strong-wind regime, lead > 12 h, mostly-boundary classes, or synthetic input. The ceiling is MODERATE, because HIGH needs field validation that does not exist;
- the probabilistic NBM exceedance flag (POD 0.49, FAR 0.64 at ≥ 10 mph, CAL+H1, exploratory) is named as EXPLORATORY and never used to raise confidence. Its recalibration test waits for H2 (2027-01-01). H2 is untouched and no date moved.

All limitation numbers are read from the published `brain/validation_evidence.json`; none are typed into code.

## 7. The assessment contract (Phase 5, `sector-wind-exposure-assessment-v1`)

Schema: `contracts/wind-exposure-assessment-v1.json`. Builder: `assessment/build.py`. Invariant check: `assessment/schema.py check()`, which runs on every assessment before it is returned (including the specialist-boundary check `boundary_problems`). Fields: lake, evaluation and reference timestamps (valid time, forecast init, lead, state generatedAt), wind (kind, speed, gust, direction, duration and its basis, source, staleness, units), scope (what it answers and does not answer, geometry hash and subset flag), shorelines (sheltered / exposed / requested / not found), lake summary, optional trip, confidence, limitations, explanation, provenance (brain/model version, physics and ranking rules, `deterministic: true`, `aiUsed: false`) and validation (`validated: false`, `observedAccuracy: NOT_FIELD_VALIDATED`, `lifecycle: SHADOW`, `customerExposure: NOT_AUTHORIZED`).

**Never fabricate:** `INPUT_STALE`, `WIND_UNAVAILABLE`, `DIRECTION_UNKNOWN`, `GEOMETRY_UNAVAILABLE` and `UNSUPPORTED_LAKE` carry **no** shoreline results and confidence UNKNOWN. Calm with undefined direction is READY and flat, the same rule as `brain/state.py`.

Inputs are existing contracts only: `wind_from_state(sector-brain-wind-state-v1)` or an explicit `synthetic_wind(...)` (always kind `synthetic`, always LOW confidence, always the `SYNTHETIC_INPUT` warning). The published state carries mph to 0.1, so decision wave heights can differ from the state's own bank rows by a few hundredths of an inch.

Payload: about 44 KB with 2 requested banks and a 3-hour timeline (31 KB without), bounded under 120 KB by the tests. One assessment on the full 6,504-bank Guntersville table takes about 0.15 s (measured). On that table, 12 mph SW names the most exposed bank GT-005788 (9.0 km fetch) and its nearest sheltered bank 277 m away, the same result the Oct 19 audit found by hand.

## 8. Capability scenarios (Phase 8)

`assessment/scenarios.py`: 18 deterministic scenarios (exposed vs sheltered, opposing directions, calm vs strong, direction change, sustained wind, coves vs open water, missing geometry, unknown inputs, stale forecast, class boundaries, alternatives, lead time, strong-wind uncertainty, rapid decrease, coverage limits, determinism, speed monotonicity, contract and explanations). Banks are chosen from geometry by rule, so the suite runs on any lake: the audit pair on Guntersville, otherwise the longest and shortest fetch for the direction. All 18 pass on the **full** frozen fetch tables of all four development lakes, and on the committed 314-bank Guntersville subset used in CI. Winds are SYNTHETIC. A pass is `MODEL_CAPABILITY`, never observed accuracy.

The first full-lake run caught a real defect, in a check rather than the product: S18 compared `8.0` to an explanation reading `8 in` (Wheeler, Wilson). The check was fixed to compare the same formatting.

## 9. Three measurements (Phases 9-14)

All three are evaluated by the **platform scorer** (`jobs/brain_platform/sector_brain_platform/wind_measurements.py`). Wind supplies evidence only (`docs/brains/scoring/evidence/wind-measurements-evidence.json`, metadata, no paths). Ops renders and never computes.

| Measurement | Version | Form | Today |
|---|---|---|---|
| Certification (unchanged) | `wind-certification-rubric-v1` | number | **3.3** (frozen 2026-10-13 block, carried verbatim) |
| BWIS v1 (unchanged) | `bwis-v1` (sha 21e2a326…) | number | **5.4** (carried verbatim) |
| Wind Capability | `wind-specialist-capability-v2` | number, **ADOPTED 2026-10-19** | **6.7** = 28.3/61 measured skill + 39/39 model capability; measured-skill-only view **4.6** |
| Scientific Confidence | `wind-scientific-confidence-v1` | evidence statuses, no number | **LIMITED** (bank exposure and surface NOT_VALIDATED, strong-wind forecast FAILS, geometry VALIDATED) |
| Production Readiness | `wind-production-readiness-v1` | gates, no number | **NOT_READY** (lifecycle, publisher cutover, customer integration, assessment activation, 5/30 live days) |

**Wind Capability v2 design** (`docs/brains/scoring/wind-specialist-capability-v2.json`): six categories (wind interpretation 25, wind exposure geometry 20, wind exposure assessment 20, wind-driven surface 15, wind temporal behaviour 12, uncertainty 8), each with a written product rationale. Items are `MEASURED_SKILL` (real METAR, buoy and exact-geometry evidence: the BWIS v1 curves reused, plus deterministic strong-wind event detection worth 10 and symmetric decision accuracy per the BWIS v1 D1 note) or `MODEL_CAPABILITY` (scenario passes over all four lakes; a missing lake counts as failed). Field validation (BWIS v1 B3, D2) moves to Scientific Confidence, and operations (BWIS v1 E) to Readiness. Both are named in the rubric and remain visible at 0.

**Honesty notes on Wind Capability v2.**
1. It is not blind pre-registered: the weights were written knowing the audit metrics. Michael adopted it as written on 2026-10-19 knowing this (rubric `adoption` record); publication still sits behind the `WIND_MEASUREMENTS=on` deploy switch.
2. 39 of its 67 points come from synthetic capability scenarios that pass by design of the implementation. That is what "capability" means here, and the split is always reported. Every one of the 33 missing points is measured skill: strong wind (10), decision accuracy (6.7), windy-hour error (4.2), transient realism (6), surface accuracy (3.8), direction (1.8). Not one is closable by engineering alone.
3. Symmetric surface-class forecast agreement on all CAL+H1 rows is 0.614. The BWIS v1 note's 0.589 was on the smaller NBM/HRRR common-row subset, so the two are not contradictory.

**Score refresh** (`wind_score_refresh.py`, CLI `jobs/brain-scores/refresh_wind_score.py`): the platform gate for a candidate certification block from the canonical generator. It checks the rubric version, COMPUTED basis, no hypothetical marker, self-consistent arithmetic, an unchanged dimension set and weights, complete evidence ≤ 36 h old, newer than the published block, non-decreasing valid days and an unchanged skill-evidence file. Only dimension 8 (live reliability) refreshes automatically; any other movement is HELD for certification review. History is append-only (`wind-score-history.jsonl`), and HOLD never touches the block.

**Publication:** `score_brains.py --wind-measurements` attaches the envelope to `/scores/wind` as `measurements`. It is additive (value, version and breakdown untouched), causes no `score.changed` event, is HELD if inconsistent, and is **OFF by default**.

## 10. Activation plan (not authorized by this work)

Each step needs Michael's explicit approval. The cutover sequence (Water Clarity → Fish → Wind) is not changed.

1. ~~Adopt or amend Wind Capability v2~~ **Done: adopted as written, 2026-10-19.**
2. **Merge** the V2 PR. Effect: none in production. The assessment layer is not imported by `main.py`, `publish.py` or `artifact.py` (a test enforces this), and `--wind-measurements` is off.
3. **Measurements in Ops:** prepared. `orchestrate.score_cmd()` adds `--wind-measurements` only when the job runs with `WIND_MEASUREMENTS=on`, and `deploy-job.sh` stages the rubric and evidence (brain.json is already staged). Exact steps: `WIND_MEASUREMENTS_ACTIVATION.md`. Shared-orchestrator deploy: `preflight_lineage.py` applies. Ops renders the three measurements from `/scores/wind/measurements` (coordinate with Brain Score Intelligence V1, PR #33, which is open and untouched by this work).
4. **Certification refresh:** run the block generator against the cloud archive metadata, then `refresh_wind_score.py --candidate … --write`, commit, and score as usual.
5. **Assessment shadow artifact:** in `wind-hourly`, after `build_state`, build one assessment per lake-hour from the state, and write it to the private candidate archive (`brain/wind/assessment/latest/{lakeKey}.json.gz`, the same storage pattern as `bankDetailRef`). No RTDB write. Needs a Wind deploy (`MICHAEL_APPROVED_WIND_DEPLOY=yes`).
6. **Publisher contract:** add a `wind-exposure-assessment` section to the Publisher registry and to `wind-publication-v1` (or a v2), with Gate-P equivalence, after Wind's cutover turn.
7. **Consumer:** Sector Intelligence only. It combines Wind's assessment with the Fish, Water Clarity and Lake Brains; any customer-facing recommendation is Intelligence's output and a separate customer-activation decision.

## 11. Limits that remain

- No bank has been checked on the water (0 field observations). Every bank answer is model output.
- Strong-wind nights are not forecast (POD 0), and gusts run about 4 mph low.
- There is no wave memory, so post-blow recession is optimistic.
- Wind is validated only at land stations, with no over-water reference.
- Assessment geometry is available for the 4 development lakes in production storage. The 50 national fetch tables are geometry-QA only and are not wired.
- Wind Capability v2 is adopted but not yet published (needs the orchestrator deploy).
