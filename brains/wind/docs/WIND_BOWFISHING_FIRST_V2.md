# Wind Brain: Bowfishing-First V2

Status: **implemented in nonproduction, SHADOW.** Lifecycle stays CALIBRATION, `customerIntegrationMode` stays `none`, Publisher cutover status stays SHADOW. Nothing here is deployed, published or read by a customer path. Owner approval is needed for every activation step in §10.

Rules stay in `BRAIN_OPERATING_CONTRACT.md`. This file explains the V2 design and the decisions behind it.

## 1. Why

The October 19 scoring-objectives audit found that Wind already had real bowfishing logic: ranking 6,504 Guntersville banks, telling protected from exposed shores, giving wave heights and nearby alternatives. That logic lived in research-labelled code, nobody consumed it, and no score measured it. The certification score (3.3) measures something else: proven on the water plus operational maturity. V2 moves the bowfishing logic into a supported runtime layer. It also measures that layer separately from scientific confidence and production readiness.

## 2. Three functional layers (logical, one code tree)

| Layer | Responsibility | Code |
|---|---|---|
| **1. Wind Intelligence** | Forcing (NBM / RTMA-RU / METAR), direction convention (FROM, true north), forecast vs observation labels, frozen duration rule, frozen CEM / SPM84 9-ray fetch physics, Unknown handling | `ingest.py`, `grib.py`, `interp.py`, `sample.py`, `store.py`, `live.py`, `brain/state.py`, `bowfishing.py` (physics section). **Unchanged** except one additive key (below). |
| **2. Bowfishing Intelligence** | Shoreline exposure, sheltered banks, surface semantics, fishing-impact wording, trip timeline, less-exposed and nearest sheltered banks, confidence, limitations, the canonical decision | `decision/ranking.py`, `semantics.py`, `timeline.py`, `limitations.py`, `build.py`, `schema.py` |
| **3. Learning & Validation** | Deterministic capability scenarios, evidence for the platform scorer, research gaps, validation entry points | `decision/scenarios.py`, `research/tools/sector_wind_research/measurement_evidence.py`, `research/GAPS.json`, `contracts/wind-validation-entrypoints-v1.json` |

There are no new services, schedulers, Brains or Publisher, and no AI. The only change to Layer 1 is that `bowfishing.evaluate_bank` now also returns `predictedHm0RangeIn`: the ±1 m/s × 0.7–1.3 fetch range it already computed for `confidence` and then threw away. The change is additive and the physics is unchanged.

## 3. Shoreline ranking and alternatives (Phases 3-4)

`decision/ranking.py` is an adapter, not a reimplementation. Ordering, exposure rank, confidence, reasons and the frozen nearby-alternative rule are `bowfishing.rank_banks_for_wind` / `evaluate_bank` / `nearby_alternatives`, exactly as frozen in BWIS v1. The adapter:
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

Fishing impact (`fishingImpact`) interprets only the surface class (how hard it may be to see and shoot fish). It always carries the caveat that clarity, light, fish presence, access and safety are not assessed, and that classes are modeled, not field-validated.

## 5. Time-dependent conditions (Phase 7)

`decision/timeline.py` evaluates the trip hour by hour with frozen M0 (CEM + frozen duration rule over the hourly series, optionally preceded by pre-trip history). It reports wind threshold crossings, direction shifts of 45° or more ("different shores are now exposed"), per-bank exposure changes (SHELTERED / MODERATE / EXPOSED) and a summary per bank.

**Wave memory.** M0 has none: modeled chop drops the moment wind eases. The M4 fetch-scaled memory candidate **failed** its pre-registered promotion rule (rule 1, 2 points of retention short), so it is not run, not even in shadow. Running a failed candidate behind a flag would be silent promotion by another name. Instead every hour after a blow where M0 is likely optimistic is flagged `recessionOptimistic`, and the trip carries the `waveMemory` disclosure. When no pre-trip history is supplied, the timeline says early-hour waves may be *under*-estimated. The work stays in gap WIND-CNF-002.

## 6. Strong wind (Phase 13 of the handoff)

Deterministic NBM detected 0 of 49 observed ≥ 15 mph night events (CAL+H1). V2 handles this as an honest-output problem, not a modeling one:
- `STRONG_WIND_UNDERFORECAST` (WARNING) is attached to **every** decision, because the failure is a *missed* event, so a light forecast cannot exempt a decision;
- confidence is LOW for forecast wind ≥ 10 mph, any strong-wind regime, lead > 12 h, mostly-boundary classes, or synthetic input. The ceiling is MODERATE, because HIGH needs field validation that does not exist;
- the probabilistic NBM exceedance flag (POD 0.49, FAR 0.64 at ≥ 10 mph, CAL+H1, exploratory) is named as EXPLORATORY and never used to raise confidence. Its recalibration test waits for H2 (2027-01-01). H2 is untouched and no date moved.

All limitation numbers are read from the published `brain/validation_evidence.json`; none are typed into code.

## 7. The decision contract (Phase 5, `sector-wind-bowfishing-decision-v1`)

Schema: `contracts/wind-bowfishing-decision-v1.json`. Builder: `decision/build.py`. Invariant check: `decision/schema.py check()`, which runs on every decision before it is returned. Fields: lake, evaluation and reference timestamps (valid time, forecast init, lead, state generatedAt), wind (kind, speed, gust, direction, duration and its basis, source, staleness, units), scope (what it answers and does not answer, geometry hash and subset flag), shorelines (sheltered / exposed / requested / not found), lake summary, optional trip, confidence, limitations, explanation, provenance (brain/model version, physics and ranking rules, `deterministic: true`, `aiUsed: false`) and validation (`validated: false`, `observedAccuracy: NOT_FIELD_VALIDATED`, `lifecycle: SHADOW`, `customerExposure: NOT_AUTHORIZED`).

**Never fabricate:** `INPUT_STALE`, `WIND_UNAVAILABLE`, `DIRECTION_UNKNOWN`, `GEOMETRY_UNAVAILABLE` and `UNSUPPORTED_LAKE` carry **no** shoreline results and confidence UNKNOWN. Calm with undefined direction is READY and flat, the same rule as `brain/state.py`.

Inputs are existing contracts only: `wind_from_state(sector-brain-wind-state-v1)` or an explicit `synthetic_wind(...)` (always kind `synthetic`, always LOW confidence, always the `SYNTHETIC_INPUT` warning). The published state carries mph to 0.1, so decision wave heights can differ from the state's own bank rows by a few hundredths of an inch.

Payload: about 44 KB with 2 requested banks and a 3-hour trip (31 KB without), bounded under 120 KB by the tests. One decision on the full 6,504-bank Guntersville table takes about 0.15 s (measured). On that table, 12 mph SW names the most exposed bank GT-005788 (9.0 km fetch) and its nearest sheltered bank 277 m away, the same result the Oct 19 audit found by hand.

## 8. Capability scenarios (Phase 8)

`decision/scenarios.py`: 18 deterministic scenarios (exposed vs sheltered, opposing directions, calm vs strong, direction change, sustained wind, coves vs open water, missing geometry, unknown inputs, stale forecast, class boundaries, alternatives, lead time, strong-wind uncertainty, rapid decrease, coverage limits, determinism, speed monotonicity, contract and explanations). Banks are chosen from geometry by rule, so the suite runs on any lake: the audit pair on Guntersville, otherwise the longest and shortest fetch for the direction. All 18 pass on the **full** frozen fetch tables of all four development lakes, and on the committed 314-bank Guntersville subset used in CI. Winds are SYNTHETIC. A pass is `MODEL_CAPABILITY`, never observed accuracy.

The first full-lake run caught a real defect, in a check rather than the product: S18 compared `8.0` to an explanation reading `8 in` (Wheeler, Wilson). The check was fixed to compare the same formatting.

## 9. Three measurements (Phases 9-14)

All three are evaluated by the **platform scorer** (`jobs/brain_platform/sector_brain_platform/wind_measurements.py`). Wind supplies evidence only (`docs/brains/scoring/evidence/wind-measurements-evidence.json`, metadata, no paths). Ops renders and never computes.

| Measurement | Version | Form | Today |
|---|---|---|---|
| Certification (unchanged) | `wind-certification-rubric-v1` | number | **3.3** (frozen 2026-10-13 block, carried verbatim) |
| BWIS v1 (unchanged) | `bwis-v1` (sha 21e2a326…) | number | **5.4** (carried verbatim) |
| Bowfishing Intelligence | `wind-bowfishing-intelligence-v2` | number, **PROPOSED** | **6.7** = 28.3/61 measured skill + 39/39 model capability; measured-skill-only view **4.6** |
| Scientific Confidence | `wind-scientific-confidence-v1` | evidence statuses, no number | **LIMITED** (bank exposure and surface NOT_VALIDATED, strong-wind forecast FAILS, geometry VALIDATED) |
| Production Readiness | `wind-production-readiness-v1` | gates, no number | **NOT_READY** (lifecycle, publisher cutover, customer integration, decision activation, 5/30 live days) |

**BI v2 design** (`docs/brains/scoring/wind-bowfishing-intelligence-v2.json`): six categories (wind interpretation 25, geographic 20, decision 20, surface 15, temporal 12, uncertainty 8), each with a written product rationale. Items are `MEASURED_SKILL` (real METAR, buoy and exact-geometry evidence: the BWIS v1 curves reused, plus deterministic strong-wind event detection worth 10 and symmetric decision accuracy per the BWIS v1 D1 note) or `MODEL_CAPABILITY` (scenario passes over all four lakes; a missing lake counts as failed). Field validation (BWIS v1 B3, D2) moves to Scientific Confidence, and operations (BWIS v1 E) to Readiness. Both are named in the rubric and remain visible at 0.

**Honesty notes on BI v2.**
1. It is not blind pre-registered: the weights were written knowing the audit metrics. That is why it is PROPOSED and reported only behind an opt-in flag until Michael adopts it.
2. 39 of its 67 points come from synthetic capability scenarios that pass by design of the implementation. That is what "capability" means here, and the split is always reported. Every one of the 33 missing points is measured skill: strong wind (10), decision accuracy (6.7), windy-hour error (4.2), transient realism (6), surface accuracy (3.8), direction (1.8). Not one is closable by engineering alone.
3. Symmetric decision accuracy on all CAL+H1 rows is 0.614. The BWIS v1 note's 0.589 was on the smaller NBM/HRRR common-row subset, so the two are not contradictory.

**Score refresh** (`wind_score_refresh.py`, CLI `jobs/brain-scores/refresh_wind_score.py`): the platform gate for a candidate certification block from the canonical generator. It checks the rubric version, COMPUTED basis, no hypothetical marker, self-consistent arithmetic, an unchanged dimension set and weights, complete evidence ≤ 36 h old, newer than the published block, non-decreasing valid days and an unchanged skill-evidence file. Only dimension 8 (live reliability) refreshes automatically; any other movement is HELD for certification review. History is append-only (`wind-score-history.jsonl`), and HOLD never touches the block.

**Publication:** `score_brains.py --wind-measurements` attaches the envelope to `/scores/wind` as `measurements`. It is additive (value, version and breakdown untouched), causes no `score.changed` event, is HELD if inconsistent, and is **OFF by default**.

## 10. Activation plan (not authorized by this work)

Each step needs Michael's explicit approval. The cutover sequence (Water Clarity → Fish → Wind) is not changed.

1. **Adopt or amend BI v2** (rubric review). Until then nothing shows it.
2. **Merge** the V2 PR. Effect: none in production. The decision layer is not imported by `main.py`, `publish.py` or `artifact.py` (a test enforces this), and `--wind-measurements` is off.
3. **Measurements in Ops (optional, after 1):** add `--wind-measurements` to the orchestrator's score step and stage `docs/brains/scoring/` and `brains/wind/brain.json` in the image (`jobs/brain-orchestrator/deploy-job.sh`). Shared-orchestrator deploy: `preflight_lineage.py` applies. Ops renders the three measurements from `/scores/wind/measurements` (coordinate with Brain Score Intelligence V1, PR #33, which is open and untouched by this work).
4. **Certification refresh:** run the block generator against the cloud archive metadata, then `refresh_wind_score.py --candidate … --write`, commit, and score as usual.
5. **Decision shadow artifact:** in `wind-hourly`, after `build_state`, build one decision per lake-hour from the state, and write it to the private candidate archive (`brain/wind/decision/latest/{lakeKey}.json.gz`, the same storage pattern as `bankDetailRef`). No RTDB write. Needs a Wind deploy (`MICHAEL_APPROVED_WIND_DEPLOY=yes`).
6. **Publisher contract:** add a `wind-decision` section to the Publisher registry and to `wind-publication-v1` (or a v2), with Gate-P equivalence, after Wind's cutover turn.
7. **Consumers:** Sector Intelligence first, then app or web, only with field-validation status shown. This is a customer activation decision.

## 11. Limits that remain

- No bank has been checked on the water (0 field observations). Every bank answer is model output.
- Strong-wind nights are not forecast (POD 0), and gusts run about 4 mph low.
- There is no wave memory, so post-blow recession is optimistic.
- Wind is validated only at land stations, with no over-water reference.
- Decision geometry is available for the 4 development lakes in production storage. The 50 national fetch tables are geometry-QA only and are not wired.
- BI v2 is PROPOSED, not adopted.
