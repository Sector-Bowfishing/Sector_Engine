# Water Clarity — score reconciliation (BEFORE = AFTER)

Four things are kept separate and none moves another: **research/science score**, **architecture readiness (structural certification)**, **runtime health (healthV1)**, **production readiness**. Structural work changed none of the numbers below.

| Quantity | BEFORE (origin/main `4ff9bed0`) | AFTER (this branch) | Source |
|---|---|---|---|
| Water Clarity score value | **8.0 / 10** | **8.0 / 10** | `docs/brains/scoring/frozen-scores.json` → `water-clarity` |
| `scoreVersion` | `clarity-research-certification-r3.1` | unchanged | same block |
| basis | `FROZEN` | `FROZEN` | same block |
| `appliesTo` | model `r3.1`, status `CANDIDATE`, `certificationStatus` CERTIFIED, `deploymentStatus` **NOT_DEPLOYED** | unchanged | same block |
| block sha256 | `b2cb88becb9dac6ddddec271ee4dd7c5cfd51141bf4f09ac9b4f2dceca9d13a1` | identical (tested) | `test_research_score_is_unchanged_…` |
| Platform baseline | `score_baseline.py --check`: water-clarity=8.0/10, water-temp=3.0/10, wind=3.3/10 | identical | `verification/integration/score_baseline.py` |
| Rubric reference | frozen record (rubric text points to a private archive) | `brain.json` `score.rubricRef` = `docs/brains/scoring/frozen-scores.json` | no rubric/weight/threshold edited |

## What the score does and does not measure
It is a **research score for the certified research candidate** (frozen bars pass), not a production-quality score. **Production clarity is unscored**: the customer number (`secchi-power-v1` / `rain-decay-v0`) has no deployed consensus model and its validation is partial (the score's own blocker: promotion needs Michael's explicit approval). The score says nothing about this package's architecture and architecture says nothing about the score.

## What changed that touches scoring (nothing)
`brain.json` now names the score path (`/scores/water-clarity`) and the frozen record as its rubric reference; the Clarity Brain writes **no** score (tested: no `scores/*` path in the real write set; `/scores/water-clarity` is rejected by the Publisher and by ownership). `jobs/brain-scores` still takes the frozen block verbatim. No weight, threshold, coefficient, provider science or model logic changed; the builder outputs are byte-identical to the pre-move tree (science golden).

## Lifecycle
`CALIBRATION` — equal in `brain.json`, `control_manifest.json` and the artifact lineage (tested; no generic drift gate exists yet: debt D-9). Not promoted; `publisherRequired.cutoverStatus` = `SHADOW`; science `NOT_VALIDATED` as a customer number.
