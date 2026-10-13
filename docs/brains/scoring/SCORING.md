# Brain Scores — how Sector answers "how strong is each Brain?"

**Owner:** Sector Engine (platform writer `brain-platform`). **Version:** scoring-v1, 2026-10-12.
Rubrics are machine-readable in this directory (`*-score-v1.json`); the evaluator is
`jobs/brain_platform/sector_brain_platform/scoring.py`; the publisher is `jobs/brain-scores/`.
Ops displays scores; it never computes them.

## What a score is

- A **maturity / evidence score, 0–10, one decimal**, per Brain. It says how much Sector can
  trust that Brain's published truth and how far it is from production-grade. It is **not** a
  probability, not a customer-quality metric, and not comparable across Brains as a ranking of
  "better science".
- Every score carries `scoreVersion`, `scoreRubric`, `scoreUpdatedAt`, `scoreBreakdown`,
  `scoreBlockers`, `nextScoreOpportunity`, `basis` (`FROZEN` or `COMPUTED`) and `completenessPct`.
- **Unknown stays unknown.** A dimension whose facts are not published is `UNKNOWN`: it
  contributes 0 and is excluded from `completenessPct`. A score with low completeness is shown as
  such, never padded.
- **Gates cap, never add.** A failing hard gate caps the final value; the breakdown still shows
  what the dimensions earned so the cap is explainable.
- **Scores move only with evidence.** Each rubric lists what moves each dimension and what cannot
  count (e.g. UI work, docs, un-validated candidates).

## The `score` block (`/scores/{brainId}`; canonical, platform-written — a mirror may appear inside the registry)

```jsonc
{ "value": 3.0, "scale": 10, "basis": "COMPUTED",
  "scoreVersion": "lake-brain-score-v1", "scoreRubric": "docs/brains/scoring/lake-brain-score-v1.json",
  "scoreUpdatedAt": "…", "completenessPct": 95,
  "scoreBreakdown": { "sourceAuthority": { "value": 10, "weight": 15, "status": "SCORED", "evidence": "5/5 profiled lakes on DIRECT_OPERATOR_POOL" }, "…": {} },
  "scoreBlockers": [ { "gate": "coverage", "cap": 3.0, "why": "5 of 621 lakes profiled (0.8 % < 10 %)" } ],
  "nextScoreOpportunity": "…", "uncapped": 4.7 }
```

## Frozen scores (not recomputed by this system)

| Brain | Score | Basis | Provenance |
|---|---|---|---|
| Water Temperature | **3 / 10** | FROZEN | Stage 3C.3 decision, 2026-10-11 (iOS private repo `docs/intelligence/water-temp/WATER_TEMP_STAGE_3C3_PROTECTED_VALIDATION.md`). Level-4 gate FAILED on protected-truth sufficiency, not on model error. Moves when the protected truth gate passes (TVA forebay data or Sector loggers). |
| Water Clarity | **8 / 10 (research)** | FROZEN | R3.1 `CERTIFIED_CANDIDATE`, certified 2026-10-12, `NOT_DEPLOYED`; private certification detail in `gs://sector-clarity-candidate/research-archive/2026-10-12-closeout/`. The production models (`secchi-power-v1`, `rain-decay-v0`) carry no research score. Never promoted by this system. |
| Wind | **3.1 / 10** (certification) | FROZEN | `jobs/wind-hourly/sector_wind/brain/validation_evidence.json`, frozen 2026-10-12T06:16Z: `windCertificationScore` 3.1 (frozen Stage 1/2 rubric v1) and `bowfishingWindIntelligenceScore` 5.4 (BWIS v1, definition sha256 recorded). Production wind (Open-Meteo) is unscored. |

These are published verbatim with `basis: FROZEN`; re-scoring them "for consistency" is forbidden.

## Computed rubrics

### Lake Brain — `lake-brain-score-v1`
Quality dimensions are evaluated over **profiled** lakes (those with a published `/lakes/{k}/brain`);
coverage and validation are fleet-wide. Weights sum to 100.

| id | Dimension | Weight | Fact | Scale |
|---|---|---|---|---|
| sourceAuthority | level source is the operator pool or the lake's own gauge | 15 | `sourceCapability.level ∈ {DIRECT_OPERATOR_POOL, DIRECT_LAKE_GAUGE}` share | share × 10 |
| operatorPlan | operating guide or zone known | 10 | `operatingPools` has a guide curve or a zone | share × 10 |
| historyQuality | ≥ 5 complete years of daily history | 15 | `historicalCoverage.baselineStatus == SUFFICIENT` share | share × 10 |
| seasonalBaseline | a day-of-year baseline exists | 10 | `baselineStatus ∈ {SUFFICIENT, LIMITED}` share | share × 10 |
| trendQuality | last state is observed, not a proxy | 10 | `states/lake.kind == observed` share | share × 10 |
| floodDroughtContext | flood-pool state known | 5 | `states/lake.floodPoolState != UNKNOWN` share | share × 10 |
| validation | fleet validation | 15 | `/validation/lake-brain.status` | NOT_VALIDATED 0 · PARTIAL 5 · VALIDATED 10 |
| coverage | lakes profiled | 20 | profiled / directory count | 0 → 0; > 0 → 1; ≥ 5 % → 2; ≥ 10 % → 3; ≥ 25 % → 5; ≥ 50 % → 7; ≥ 75 % → 9; ≥ 90 % → 10 |

Gates: coverage < 10 % → cap **3.0**; validation NOT_VALIDATED → cap **5.0**; brain health
FAILED/UNKNOWN → cap **2.0**. Moves up with: reviewed bindings for more lakes, history backfill,
a validation run against operator truth. Cannot count: the 621-lake directory itself, Ops pages.

### Biological Brain — `biological-state-score-v1`
Not an average of species scores. Knowledge depth is **one** dimension.

| id | Dimension | Weight | Fact | Scale |
|---|---|---|---|---|
| registryCompleteness | every registered species is assessed or explicitly NOT_ASSESSED | 10 | registry `responsibilities.speciesKnowledge` | speciesCount > 0 and assessed + notAssessed == speciesCount → 10; else 0 |
| assessedCoverage | share of species assessed | 15 | assessedCount / speciesCount | share × 10 |
| knowledgeDepth | median species-v2 `overallRounded` over assessed species | 20 | `/species/*.knowledge.overallRounded` | median (0–10) |
| evidenceQuality | research maturity | 10 | share of assessed species `researchMaturity ≥ REVIEWED` | VALIDATED share × 10, else REVIEWED share × 7, else RESEARCH present → 2 |
| contradictionsGaps | open contradictions | 10 | mean over assessed of min(contradictionCount, 5)/5 | 10 × (1 − mean) |
| regionalTransfer | knowledge tagged for the lake's region | 5 | not published yet | UNKNOWN |
| biologicalStateImpl | per-lake Biological State exists | 15 | `responsibilities.biologicalState.status` | NOT_STARTED 0 · IN_PROGRESS 4 · LIVE 8 · VALIDATED 10 |
| biologicalStateValidation | per-lake state validated | 10 | same node, `validation` | NOT_STARTED 0 · PARTIAL 5 · VALIDATED 10 |
| productionIntegration | consumed by Intelligence or a customer path | 5 | `/brains/sector-intelligence.dependencies[biological-state].status == CONSUMED` | 10 / 0 |

Gates: Biological State NOT_STARTED → cap **4.0**; no species VALIDATED → cap **6.0**.

### Sector Intelligence — `sector-intelligence-score-v1`

| id | Dimension | Weight | Fact | Scale |
|---|---|---|---|---|
| specialistConnectivity | upstream Brains actually consumed | 20 | consumed / 5 | share × 10 |
| normalizedEvaluations | lakes with a normalized evaluation | 20 | evaluatedLakeCount / directory | same ladder as Lake coverage |
| dependencyHandling | every upstream Brain has a published dependency status | 10 | `dependencies` has all 5 with a status | 10 / proportional |
| provenance | evaluations carry full provenance | 10 | share of evaluated lakes with `provenance` + `inputs` | share × 10; UNKNOWN when nothing evaluated |
| validation | `/validation/sector-intelligence.status` | 15 | | NOT_VALIDATED 0 · PARTIAL 5 · VALIDATED 10 |
| lakeCoverage | supportedLakeCount / directory | 10 | | ladder |
| runtime | health and schedule | 5 | `health == HEALTHY` (+5) and a schedule/job (+5) | |
| synthesisQuality | drivers / limiting factors present and consistent | 10 | not measurable until evaluations exist | UNKNOWN |

Gates: evaluatedLakeCount == 0 → cap **1.0**; consumed == 0 → cap **2.0**; validation
NOT_VALIDATED → cap **5.0**.

## Publishing
`jobs/brain-scores/score_brains.py --dry-run` prints every score with its breakdown from live
Brain facts; `--write` publishes `/scores/{id}` for all six Brains (and `/scores/engine`) (frozen ones verbatim) and
one `score.changed` activity event per changed value, as `brain-platform`. Manual only; no
scheduler (the Orchestrator will own cadence).

## Sector Engine Score — `engine-score-v1` (`/scores/engine`; `/engine/score` kept as an alias)

Not a naive average. Frozen before first computation (2026-10-12); rubric in `engine-score-v1.json`.

| id | Dimension | Weight | Scale |
|---|---|---|---|
| specialistBrainMaturity | mean of the five specialist Brain scores | 25 | mean 0–10 |
| integrationCompleteness | specialist Brains consumed by Intelligence | 20 | consumed/5 × 10 |
| lakeCoverage | lakes with ≥ 1 specialist slot at readiness ≥ CALIBRATION | 10 | share × 10 |
| scientificValidation | mean over six Brains of VALIDATED 10 / PARTIAL or holdout-only 5 / else 0 | 15 | |
| runtimeReliability | Brains and scheduled jobs HEALTHY in their last run | 10 | share × 10 |
| productionConsistency | serving revision's source lineage verified | 10 | 10 / 0 |
| platformHealth | Brains on a conforming platform implementation | 10 | UNKNOWN until Phase 7 publishes it |

Gates: no specialist Brain consumed → cap **4.0**; lineage unverified → cap **3.0**; any Brain
FAILED → cap **5.0**. Output: `engineScore, engineScoreVersion, dimensions, blockers, strongestArea,
weakestArea, updatedAt, brainScores{id→value}`. Engine Score, Brain scores, lifecycle, health,
coverage and beta readiness stay separate nodes.
