# Sector Intelligence: current state audit

**Date:** 2026-10-13. **Branch:** `docs/intelligence-deep-research` from `origin/main` `e596a6bb`. **Boundary:** research only. Nothing here changes production, a score, a rubric, an API, an app or Ops.
**Method:** read the code and published rubric; reproduced the published score from the real evaluator; ran the **unmodified** production `ConditionsAggregator` through a separate probe package (`research/intelligence/probe/`) with synthetic inputs; ran the Intelligence test suite (32/32 pass). The probe output is `research/intelligence/probe/out/aggregator_probe_output.txt`.
**Public/private note:** `iOS_Sector` is a private repo. This public document describes on-device FishIntel only at the level `jobs/sector-intelligence-brain/catalog.json` already does, plus structural findings. Thresholds, formulas and ground-truth details are in the private handoff appendix, not here.

## 1. There are four "Intelligences", and only one answers a customer

| Implementation | Lifecycle | Customer-reachable | Reads any Brain | What it does |
|---|---|---|---|---|
| **Engine Conditions Score** (`GET /conditions`) | PRODUCTION, NOT_VALIDATED | **Yes** (iOS + Android) | **No** | 10 weighted factors, 3 regime weight sets, about a dozen gate conditions, a seeability ceiling, `topReasons`, `whereToLook` cards, `tonight`, 6 `nights[]` |
| **iOS FishIntel** (on-device) | merged to `Michael-Master`, in no tagged release | Only if the next build is cut from that branch (no entitlement or flag gate on the "Sector Intelligence" layer) | No (reads Engine `/conditions` DTOs plus a bundled Guntersville profile) | Species-first habitat attraction + huntability per ~200 m shoreline segment, decision table, no blended number. **Guntersville only** |
| **Phase-5A guardrails** | UNMERGED | No | No | Species policy / conservation gate |
| **Normalized Sector Intelligence** (Brain) | PILOT | **No** (`consumesThisEvaluation: false`) | **Yes, all 5** | Assembles normalized inputs with provenance for 5 lakes. **Produces no fishing judgment, no score** |

Consequence: the Brain that is called "Sector Intelligence" reads every specialist and answers nothing; the thing that answers reads no specialist.

## 2. The published score: 4.8 / 10, reproduced

`sector-intelligence-score-v1` (`docs/brains/scoring/sector-intelligence-score-v1.json`, evaluator `jobs/brain_platform/sector_brain_platform/scoring.py:172`). Reproduced from the registry facts in `STABILIZATION_LOG.md` and the evaluator:

| Dimension (weight) | Value | Points | What earned it |
|---|---|---|---|
| specialistConnectivity (20) | 10 | 200 | 5/5 Brains `CONNECTED*` (consumed by the pilot) |
| normalizedEvaluations (20) | 1 | 20 | 5/621 lakes (0.8%), coverage ladder |
| dependencyHandling (10) | 10 | 100 | all 5 dependency statuses published |
| provenance (10) | 10 | 100 | pilot evaluations carry provenance + inputs |
| validation (15) | 0 | 0 | NOT_VALIDATED |
| lakeCoverage (10) | 1 | 10 | 5/621 |
| runtime (5) | 10 | 50 | HEALTHY + schedule descriptor present |
| synthesisQuality (10) | UNKNOWN | 0 | "not measurable until evaluations exist" |
| **Total** | | **480 / 100 = 4.8** | cap 5.0 (validation) not binding |

**Finding A1.** 450 of the 480 points (94%) are plumbing: connectivity, dependency handling, provenance, runtime. The rubric measures whether Intelligence is wired to the Brains, not whether it helps a bowfisher. `synthesisQuality` (10%) is excluded as UNKNOWN, so it never reduces the score. The 4.8 is a truthful plumbing score and a poor predictor of answer quality. It also explicitly cannot count the production Conditions Score (`cannotCount`), which is the only part customers use. The decision-readiness ladder in `INTELLIGENCE_SCORE_LADDER.md` exists to cover that gap without altering the published rubric.

## 3. What the pilot evaluation actually contains

`jobs/sector-intelligence-brain/evaluation.py` (`intelligence-eval-v1`), 5 lakes (Guntersville, Wheeler, Wilson, Pickwick, Hartwell).
- **Inputs per slot:** `PUBLISHED | STALE | DEGRADED | NOT_PUBLISHED`, exact Brain/model version, `generatedAt`, age, readiness, restated values. Biology = Lake Brain presence ∩ Biological knowledge.
- **Output:** `drivers[]` (facts), `limitingFactors[]` (input quality and knowledge gaps), `degradedInputs[]`, `inputsUsed`, `provenance`, `freshness`. The `synthesis` block is only "N of 5 inputs fresh". Validation `NOT_VALIDATED`.
- **Observed on 2026-10-12:** Lake and Water Temp inputs STALE on every pilot (those Brains are unscheduled); Hartwell has no wind state.
- **Good:** nothing is invented; absent stays absent; provenance is exact.
- **Missing:** no species dimension, no zone dimension, no time dimension, no combination rule, no confidence beyond per-input flags, no explanation structure beyond a fact list.

## 4. What the customer path does (Engine Conditions Score)

Code: `Sources/SectorEngine/Engine/` (aggregator, 10 factors, gates, config). Scoring is **per query coordinate**, not per lake.
- Weighted blend over *present* factors with weights renormalised over what exists, then a spawn boost, then gate caps, then a seeability ceiling = `100 × clarity × wind × weather`.
- Species enter in exactly one place: `SpawnFactor` picks the best-intensity species by temperature triangle × date window × flood factor for the headline and regime. Every other factor is species-blind.
- `confidence` = 100 minus 20 (no turbidity gage), 15 (estimated/missing water temp), 15 (tailwater without generation forecast), 10/forecast-day up to 50, 10 (unknown turbidity near the blown-out gate); +10 strong spawn; spawn on estimated temp capped at 74. It does not change the score.
- Outputs: `score`, `band`, `regime`, `confidence`, `factors[{key,score,weightPct,label,why}]`, `gates[]`, `topReasons[≤4]`, `whereToLook[≤4]` (generic habitat copy), `tonight` (hourly curve), `nights[7]` (score, factors, hourly ribbon).

### 4.1 Measured behaviour of the real aggregator (probe, synthetic inputs, unmodified engine)

Baseline: a clear, calm, dark, mid-summer southern-reservoir night. Full tables in the probe output.

| # | Experiment | Result | Why it matters to a bowfisher |
|---|---|---|---|
| E1 | Live water temp 47 → 48 °F | score **35 → 81** (+46 for one degree); estimated temp: 44 → 45 °F, 50 → 81 | The cold gate is a cliff; one sensor tick flips "Poor" to "Prime" |
| E1b | Live water temp 50–59 °F | score **84** throughout, while the temp factor says "Cool — fish slow to move shallow" | Clarity/wind/darkness carry 62% of the normal-regime weight; cool water cannot pull a night below Prime-adjacent. Which fish are active at 55 °F is the Biological Brain's call, and it is not asked |
| E2 | Wind 20 → 21 mph | score **45 → 30** (15 points); 4 → 5 mph −6; 11 → 12 −4 | Band edges are steps; 15 → 16 mph −6 |
| E3 | Gage turbidity 5 → 8 → 12 FNU | 94 → 81 → 70, `conf` stays 100 until 20 FNU | Confidence is blind to everything except four listed gaps |
| E4 | Temp and level **unknown** vs temp 55 °F and level falling 1.5 ft | **96 vs 79** | Missing data raises the score. Weights renormalise over what is present, so an unknown bad factor is simply deleted. Confidence only drops 15 |
| E5 | Clarity estimated (no gage) | score 85, confidence 80 → band **High** | A guessed clarity still reads "High" confidence; temp also estimated: 65 Medium; plus night +3: 35 Low |
| E6 | Wind at lake point vs a protected pocket (3 mph) | pocket beats lake by +6 (6 mph), +15 (12 mph), **+38 (18 mph)** | Whole-lake wind hides exactly the bank-selection decision Wind's per-bank exposure exists to inform |
| E7 | Species by season | headline "species" in spawn regime includes **gizzard shad** (May, 66 °F) and **longnose gar**, **black buffalo** (Apr 72 °F) | The headline species is the best temperature×date intensity, not necessarily a bowfishing target; score hits 100 |
| E8 | Night +0 … +6 | score flat at 93, confidence 100 → 75 → 65 → 55 → 45 → 35 → 35 | Confidence is a linear countdown, not a statement about which inputs were forecast |
| E9 | Full moon high and clear vs cloud-covered | 79 vs 87 | Fine; moon logic is sensible and tested |

**Finding A2 (missing-data optimism).** The renormalisation rule (`ConditionsAggregator.swift`, "weighted blend over present factors") means *unknown can beat known-bad*. Intelligence must treat unknown as a cap on rating and a visible gap, not as a deleted vote. The prototype enforces this (rule R1/R4/R9).
**Finding A3 (cliffs).** Hard gates and band edges produce 15–46 point moves for one unit of input. An ordinal band with explicit "boundary" handling (as Wind already does with `firm | boundary`) is more honest.
**Finding A4 (species-blind).** Outside the spawn headline, "good bowfishing" is one number. The probe shows no species ever changes the score except through `SpawnFactor`.

## 5. Current-environment issues, by the categories requested

### 5.1 Duplicate science (Intelligence is re-deriving what Brains own)
| Domain | Owner | Duplicates found |
|---|---|---|
| Water-temp bands, cold gate | Water Temp Brain (state) + Biological (response) | Engine `WaterTempFactor` bands (50/60/68/82/88), cold gate 48 °F live / 45 °F estimated, FishIntel's own species temperature rules |
| Spawn temperatures | Biological | Engine `SpeciesDatabase` (18 rows) vs FishIntel species state tables vs Biological species-v2: **three tables that disagree** (`OWNERSHIP_MATRIX.md` exception 3) |
| Clarity → feet | Water Clarity | Engine `VisibilityModel` (`secchi-power-v1`) vs the iOS map's own turbidity→metres formula; FishIntel parses the Engine's clarity **label text** to recover feet |
| Wind thresholds | Wind (state) + Intelligence (impact) | Engine wind bands + 20 mph gate, FishIntel's own chop index and a different safety gate, Wind research's chop classes: three threshold sets (matrix lists ~11) |
| Lake level | Lake Brain | Engine `WaterLevelFactor` (USGS nearest gauge, trend scoring) vs Lake Brain; FishIntel uses no level at all |
| Water-temp model | Water Temp | client `k = 0.20` vs Engine `k = 0.09` (matrix exception 1) |
| Gate policy | Policy layer | Engine `SpeciesLegality`, Phase-5A gate (unmerged), FishIntel policy |

### 5.2 Missing confidence handling
- Engine confidence ignores the age and kind of wind, level, pressure, weather and moon inputs, and ignores spatial support. It treats a gage 10 mi away like one at the ramp.
- FishIntel: no staleness check on weather or water temperature at the intelligence layer; confidence is the weaker of two coverage labels, nearly always "moderate".
- Pilot evaluation: lists degraded inputs but does not propagate them to anything.
- No component carries a calibrated probability; correct, since none has been calibrated.

### 5.3 Stale-input issues
- **Pilot:** Lake and Water Temp STALE on 5/5 lakes because those Brains are unscheduled (`STABILIZATION_LOG.md` Phase 9, 12). Beta readiness is 5 × NOT_READY for this reason.
- **Engine, future nights:** stage, discharge, reservoir level, inflow trend, turbidity (if a gage exists), pressure, humidity and fog spread are **persisted from today into nights +1…+6** and never labelled as persisted; a gage within 10 mi makes later nights' clarity equal today's gage reading regardless of forecast rain. Gust is not overridden per night. Generation forecast is dropped (confidence −15) but the score is not.
- **Engine caches:** headline snapshot 5 min, response 5 min, forecast 30 min at a coarser key (≈1 km vs ≈100 m); `nights[0]` can lag the headline by up to 30 min and is not date-aware across midnight.
- **FishIntel:** the forecast scrubber swaps only wind; water temperature, moon, cloud and clarity stay at "now".

### 5.4 Contradictory inputs
- Spawn temperatures: three tables disagree (above). Same lake, same night, two answers on the same device.
- Wind safety gates: 20 mph (Engine, cap 30) vs 25 mph (FishIntel, cap 25).
- Clarity: Engine `~` estimate vs FishIntel number recovered from its label; Wind and Clarity published `provenance` are not read back.
- TVA "Midnight" rows are filed 24 h early in production (matrix decision D8); Lake Brain parses correctly.
- Any NWS alert (including a heat advisory) is a lake-wide safety gate in FishIntel; the Engine gate only fires on named severe-warning labels.
- None of these contradictions is detected by any component; there is no cross-source consistency check.

### 5.5 Whole-lake averaging
- Engine: one coordinate, nearest gauges (turbidity ≤ 10 mi, temp ≤ 15 mi), one wind, one clarity. Two points on the same lake score differently for reasons unrelated to the fish. E6 shows the size of the hidden spatial effect (up to 38 points at 18 mph).
- FishIntel: one wind, one temperature, one clarity, one moon for the whole lake; fetch is the only per-segment physical input.
- Water Temp is explicitly `spatialSupport: lakeWide`; Clarity is lake-level; only Wind has bank-scale quantities (4 pilot lakes, in storage, not RTDB, not field-validated).

## 6. Species support
| Layer | Species answers |
|---|---|
| Engine | Spawn headline only. 18-row table; tier-3 and cavity spawners excluded; protected species never auto-recommended |
| FishIntel | 5 species / 9 model rows on Guntersville only, from local tables |
| Biological Brain | species knowledge for 29 rows (27 assessed, 20 at maturity RESEARCH, 7 not started, 0 REVIEWED/VALIDATED, knowledge median ≈ 1.0 on the v2 rubric); **no machine-readable per-species response rules except common carp**; per-lake Biological State NOT_STARTED |
| Pilot evaluation | reports knowledge median per lake; no species-specific answer |

## 7. Customer exposure
Customers see only the Engine Conditions Score (score, band, reasons, cards, tonight, nights). FishIntel is in code on `Michael-Master` with no gate; whether it is in a customer build could not be confirmed from the repo. The pilot evaluation and all Brain states are internal (Ops allowlist).

## 8. Missing inputs (what Intelligence cannot do for want of data)
Depth/effective depth (no Brain; one binary contour for one lake exists in the iOS app); vegetation (no Brain; satellite `grassPct` lake share and NWI aquatic-bed share exist as indirect indicators); bank-scale wind (4 lakes, not field-validated); in-lake temperature sensors (29/621 lakes); calibrated confidence from any Brain; per-species response rules (common carp only); any outcome data.

## 9. Hardcoded specialist logic that Intelligence must stop owning
Everything in §5.1. The migration path is in `INTELLIGENCE_REQUIRED_UPSTREAM_CONTRACTS.md`; the first step is *reading* Brain states and species response bands instead of local tables, while keeping the customer behaviour unchanged until a deliberate release.

## 10. What is good and should be kept
Gates as a concept (a great score on a night you cannot fish destroys trust); the seeability idea (you shoot *through* the surface); deterministic, versioned, tested scoring (92 aggregator tests); exact provenance in the pilot; FishIntel's refusal to blend attraction and huntability into one number; the unknown-stays-unknown philosophy of the Brain platform.
