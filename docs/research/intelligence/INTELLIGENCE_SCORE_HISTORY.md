# Intelligence score history

Two tracks, never merged. All research scores are produced by `research/intelligence/tools/ladder_score.py` from `research/intelligence/data/`.

## A. Published score (`sector-intelligence-score-v1`, platform-computed)
| Date | Value | Why it moved | Source |
|---|---|---|---|
| 2026-10-12 | 1.0 | 0/621 evaluated → cap 1.0 | `STABILIZATION_LOG.md` Phase 5 |
| 2026-10-12 | 4.5 | pilot evaluation: connectivity 10, provenance 10, evaluations 1/10; validation 0 → cap 5.0 | Phase 9 |
| 2026-10-12 | **4.8** | republished with `schedule`: runtime dimension +5 | Phase 12 |
| 2026-10-13 (this research) | 4.8 | reproduced from the evaluator; unchanged | audit §2 |

Observation: the three published moves were 100% plumbing. None improved any answer to a bowfisher.

## B. Research score (`intelligence-decision-readiness-r1`, this branch)
| Step | What was done | Current | Notes |
|---|---|---|---|
| S0 | Pre-registered rubric JSON written (`decision_readiness_rubric_r1.json`) | — | anchors written after reading code: stated limitation |
| S1 | Code + docs audit (4 implementations), pilot evaluator, iOS FishIntel (private) | **3.2** | scored from evidence strings |
| S2 | Probe of the real aggregator (9 experiments) | 3.2 | confirmed confidence=3, species=3, where=3; found cliffs, missing-data optimism, whole-lake wind effect. No dimension moved: findings document gaps, they do not add capability |
| S3 | Prototype synthesis + 15 tests + validation power simulation | 3.2 current; **4.5 design-adopted (hypothetical)** | a prototype is not production, so *current* does not move; the hypothetical shows what adopting it could earn on today's inputs |
| S4 | Separate analysis: future potential | 7.8 uncapped → **7.0** | needs Depth, Vegetation, Biological bands, scheduled upstreams, PARTIAL prospective validation |
| Sensitivity | FishIntel not credited (unreleased) | 2.7 | the 0.5 difference is the whole dispute about unreleased code |

## C. Rules followed
- No step raised the *current* score by describing or designing something.
- No upstream science was borrowed to lift a dimension (Depth/Vegetation are only in the future row).
- Hypothetical (design-adopted) and future rows are labelled and never added to the current row.
- The published 4.8 was not touched.

## D. Honest error bars
Dimension levels are judgments against written anchors, ±1 on each. Perturbing every dimension ±1 in the unfavourable and favourable directions moves the current score between 2.2 and 4.2 (weights sum to 100, so ±1 on every dimension is exactly ±1.0 overall; the validation and confidence gates do not bind in that range). The ordering of the four scenarios is not sensitive to this; the *absolute* current value is. Treat 3.2 as "about 3, between roughly 2 and 4".
