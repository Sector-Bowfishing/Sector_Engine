# Intelligence score ladder

Two scores exist and they answer different questions. Neither replaces the other; neither is edited here.

| Score | Question | Value | Source |
|---|---|---|---|
| **Published** `sector-intelligence-score-v1` | Is Intelligence wired to the Brains, with provenance, health and a schedule? | **4.8 / 10** (uncapped 4.8; validation cap 5.0 not binding) | `scoring.py:score_intelligence`, reproduced in the audit §2 |
| **Research** `intelligence-decision-readiness-r1` | Can Intelligence tell a bowfisher where / when / what / why / how sure, from specialist truth? | **3.2 / 10** current; see §3 for the separate design and future analyses | `research/intelligence/tools/ladder_score.py` |

## 1. Why a second instrument
In the published rubric 94% of the points are plumbing (audit A1) and the one dimension that measures the answer (`synthesisQuality`) is UNKNOWN and therefore excluded. It also forbids counting the customer-facing Conditions Score. A rubric that rewards connecting to Brains the customer path does not read can reach 5.0 with no better answer for a bowfisher. The research ladder is pre-registered here (rubric JSON committed before the facts were scored; anchors were written after reading the code, which is a limitation) and scores *answer capability*, with validation and confidence-propagation gates.

## 2. The ladder (weights sum to 100; anchors in `data/decision_readiness_rubric_r1.json`)
| Dimension | Wt | 0 | 2–3 | 5 | 7–8 | 10 |
|---|---|---|---|---|---|---|
| specialistUse | 10 | none | pilot only | ≥3 Brains drive a shipped answer | all 5 with degrade handling | + version pinning/replay |
| where | 15 | none | one number per point / segment on one lake | | zones on ≥10 lakes → validated | sustained |
| when | 10 | none | now only | tonight/nights, some persistence unlabelled | inside horizons, persistence labelled | validated |
| species | 15 | blind | spawn-only / local tables, one lake | Biological-owned for ≥3 species | fleet-wide | validated |
| why | 10 | none | free text | structured per-factor | best/limiting/unknown/freshness + versions | user-validated |
| confidence | 15 | none | flat deductions / coverage labels | weakest-link incl staleness, support, horizon | calibrated vs outcomes | sustained |
| validation | 15 | none | synthetic only (1) / retrospective (3) | small prospective blind (5) | pre-registered, powered (8) | sustained |
| coverage | 5 | none | handful of lakes | every point, mostly estimated (6) | measured inputs (8) | all |
| integrity | 5 | none | | deterministic/tested/versioned, config unversioned (5) | all versioned, scheduled (8) | replayable |

Gates (cap, never add): validation < 5 → cap 5.0; validation < 8 → cap 7.0; confidence < 5 → cap 6.0.

## 3. Applied (evidence strings in `data/decision_readiness_facts.json`)
| Scenario | specialistUse | where | when | species | why | confidence | validation | coverage | integrity | Uncapped | Displayed |
|---|---|---|---|---|---|---|---|---|---|---|---|
| **CURRENT INPUT** (what runs today) | 2 | 3 | 5 | 3 | 5 | 3 | 1 | 6 | 5 | **3.2** | **3.2** |
| Sensitivity: customer path only (FishIntel ignored) | 2 | 2 | 5 | 2 | 4 | 2 | 1 | 6 | 5 | 2.7 | 2.7 |
| *Design adopted, today's upstream inputs only* (hypothetical) | 8 | 4 | 6 | 4 | 7 | 5 | 1 | 2 | 5 | 4.5 | 4.5 |
| *Future potential* (Depth + Vegetation + upstream gains + PARTIAL validation) | 10 | 8 | 8 | 8 | 9 | 8 | 5 | 7 | 8 | 7.8 | **7.0** (validation <8 cap) |

How to read: only the first row is a current score. Row 3 is the best the *design* could do if built on exactly today's inputs: validation stays 1, coverage 2 (Wind pilots and Biological rules limit it), so it stays below the 5.0 validation cap. Row 4 is a ceiling that requires Depth and Vegetation Brains, Biological bands, scheduled upstreams and a pre-registered field study; it is not a forecast. The three are never added or averaged.

## 4. What moves each number
| To raise the current score | Moves | Needs |
|---|---|---|
| Customer path reads Brain states (behind a flag, parity-tested) | specialistUse +3, integrity | Phase-9 consumption work, no deploy needed to test |
| Ordinal synthesis with unknown-as-cap and weakest-link confidence | confidence 3→5, why 5→7, when 5→6 | prototype → production module (research complete enough to start) |
| Biological response bands for ≥3 species | species 3→5 | Biological Brain publication |
| Blind expert ranking + 20-pair pilot | validation 1→3 | field time, no software |
| Pre-registered paired study ≥30 pairs | validation 3→5 | beta testers, one season |
| Depth/Vegetation published for a pilot lake | where 3→6 | those Brains |

Nothing moves by documentation, UI work or by re-weighting. In particular, building the prototype into production without validation cannot lift the displayed score past 5.0.

## 5. Recommended change to the *published* rubric (proposal only; not applied)
Score `synthesisQuality` as 0, not UNKNOWN, once any evaluation exists, and add a weighted `answersABowfisher` dimension (species-specific, area-specific, with explanation and confidence). Otherwise a pilot that "evaluates" 5 lakes and judges none keeps rising on plumbing. This is a rubric change that belongs to the platform owner and needs an approval; this branch does not edit `docs/brains/scoring/`.
