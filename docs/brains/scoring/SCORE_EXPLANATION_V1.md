# Brain Score Explanation V1 — `/scores/{brainId}/explanation`

**Owner:** Sector Engine platform scorer (`brain-platform`). **Contract:** `brain-score-explanation-v1`
(schema `contracts/schemas/brain-score-explanation.schema.json`). **Status:** repo-ready; activates with the next
brain-orchestrator image (see *Activation*). **Consumer:** Sector Ops "Why this score? / How to improve? / Path to 7.0".

## What it is

A **derived, read-only companion of one published score block**: why the score is what it is, which real deficiencies
would raise it, and the arithmetic distance to the 7.0 planning target. It is **not** a score input, never changes `value`,
and is not a second scoring system: it restates the evaluation the scorer just produced.

```
score_brains.py  compute() -> guard_scores() -> plan_writes(explain=True)
                                                   └─ for every block it WRITES: block["explanation"] = explain(brainId, block, previousBlock)
                                                      one multi-path RTDB update: /scores/{id} = {value, …, explanation}
```

* **Atomic by construction.** The explanation lives *inside* `/scores/{id}` and is written in the same update as the score,
  so no reader can see a new score with an old explanation. `forScore {value, scoreVersion, scoreUpdatedAt}` repeats the
  binding so a consumer can verify it (Ops shows "Updating" on any mismatch).
* **Never content.** `explanation` is excluded from `score_content` / `_content` (publication guard and write planner): an
  explanation can never make an unchanged score look changed, cause a HOLD, or emit `score.changed`.
* **Backfill once.** A block whose content is unchanged but which lacks a current explanation is rewritten once with the
  published evaluation explained (score untouched, no event). `--no-explain` disables the feature.
* **Automatic.** The scorer already runs on the Orchestrator's S1 trigger (a COMPLETE publication / registry change); a
  SKIPPED or FAILED publication does not trigger it, so the explanation can only change with a new authoritative evaluation.

## Fields (all optional fields are absent, never invented)

| Field | Meaning |
|---|---|
| `evaluationId` | `eval-` + 16 hex of sha256 over the block's substance (timestamps and explanation excluded). Deterministic. |
| `forScore` | value, uncapped, scale, basis, scoreVersion, scoreUpdatedAt of the enclosing block. |
| `scope` | `PUBLISHED`, or `CANDIDATE` when the block's `appliesTo.status` is CANDIDATE (Water Clarity R3.1). |
| `rubric` | scoreVersion, `formula` (`LINEAR_WEIGHTED_CAPPED` only when Σ value×weight/100 **reproduces** the published `uncapped`; else `UNVERIFIED` / `UNKNOWN`), display-safe `ref`. |
| `knowledge` | release identifiers the registry already publishes (brainVersion, researchVersion, manifestSha256, lastSuccessfulRun). |
| `components[]` | each breakdown dimension: value, weight, and — only under a verified formula — `earned`, `possible`, `headroom` (points on the 10 scale). UNKNOWN dimensions carry no value and earn 0, as the rubric says. |
| `caps[]` | every capping gate: `binding` (the lowest cap below uncapped), `belowTarget` (< 7.0). |
| `improvements[]` | one per real deficiency (dimension below full credit, UNKNOWN dimension, cap, or un-capped blocker), worded from `sector_brain_platform/score_improvements_v1.json`, ranked by evidence (below). Stable `id` = `{brainId}/{dimension:<id> \| gate:<gate>[@cap]}`. |
| `target` | `{value 7.0, current, gap, reached, pathway}`; pathway `REACHED` / `ARITHMETIC_PATH_EXISTS` / `NO_ARITHMETIC_PATH` / `NOT_EVALUABLE`, `validated` is **false unless reached**. |
| `change` | vs. the block it replaces: previousEvaluationId, delta, direction (FIRST/UP/DOWN/UNCHANGED), movedDimensions, `resolved[]` (improvements that left the active list), and why (e.g. "held at the coverage cap 3"). |

### Priority (evidence only, no estimates)
HIGH = a cap holding the displayed score now, or ≥ 1.0 point of rubric headroom · MEDIUM = a cap below 7.0 not binding
yet, or ≥ 0.4 · LOW = less · UNRANKED = impact not computable from the published evaluation (e.g. a frozen score without a
breakdown). Impact is reported as "up to" rubric headroom (`UP_TO_UNCAPPED`, `UP_TO_UNCAPPED_IF_MEASURED`) or the displayed
gain of lifting a binding cap (`LIFTS_CAP`). Headrooms are not summed into a promise; the pathway's `availableHeadroom` is
the rubric's own linear arithmetic and states that the path is not validated.

### Status
`OPEN`; `BLOCKED` when a registry entry marks the work blocked by a gate present in this evaluation (H2 holdout, owner approval);
`RESOLVED` items appear in `change.resolved` and leave the active list. The schema reserves RESEARCHING / EVIDENCE_FOUND /
VALIDATING / ACCEPTED / PUBLISHED / REJECTED for a future research service; the scorer never emits them without evidence.

### The improvement registry (`score_improvements_v1.json`)
Per Brain: rubric dimension labels (copied from `*-score-v1.json`) and, per `dimension:<id>` / `gate:<gate>[@cap]`, the
title, the rubric rule and the work (type, nature, blocker, research-gap ids). It is written from the rubric definitions,
Wind's frozen scoreboard (`brains/wind/research/tools/sector_wind_research/scoreboard.py`) and the research gap registers
(`brains/*/research/GAPS.json`; staged into the image for gap status). It never states a measured value or a score promise.
A deficiency with no entry still appears, with Engine's own evidence text and a generic title.

## Current values (production /scores read 2026-10-19, explained with this code)

| Brain | Score | Explanation highlights |
|---|---|---|
| Wind | 3.3 (uncapped 3.27) | 10 components reproduce 3.27; Exposure (field) and Surface (field) 0 of 2 pts each (no field data); Wind speed/Gust 0 (event-detection conditions fail; BLOCKED by H2 until 2027-01-01); caps 6.0 (below 7, not binding) and 7.0; gap 3.7, arithmetic path exists (6.74 headroom). |
| Fish (`biological-state`) | 5.1 | 9 components reproduce 5.1; knowledge depth 0.8 of 2, per-lake validation 0 of 1, regionalTransfer UNKNOWN; cap speciesValidation 6.0 must be lifted; gap 1.9. |
| Water Clarity | — (candidate 8.0) | scope CANDIDATE: FROZEN research certification of undeployed R3.1; no components; pathway NOT_EVALUABLE; one BLOCKED improvement (owner approval + deployment). |

## Activation (production)
The code runs where `score_brains.py` runs. Production needs: (1) this PR merged; (2) a brain-orchestrator image rebuild +
deploy (a SHARED-ORCHESTRATOR deploy: `preflight_lineage.py` applies; `deploy-job.sh` now also stages `brains/*/research/GAPS.json`);
(3) the next scorer run (any Brain change, or `--force-scores`) backfills explanations for all six Brains with no score
change. No RTDB rules change (Ops already reads `/scores`), no new path, no scheduler.

## Nonproduction proof
`verification/integration/score_explanation_e2e.py` drives the real LivePublisher (test authorization) → S1 trigger →
unmodified `score_brains.main` against a local RTDB emulator seeded from a read-only production snapshot; Sector Ops
`npm run e2e:score-sync` runs it end to end against the real Ops client.
