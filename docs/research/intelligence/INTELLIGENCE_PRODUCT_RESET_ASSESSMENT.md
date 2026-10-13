# Intelligence under the product reset (2026-10-13)

Intelligence stays **WAITING** for the specialist Brain contracts. This assessment prepares; it does not restart any specialist science, wiring, rebase, merge or deploy.

## 1. Verified current state
| | |
|---|---|
| Research branch | `docs/intelligence-deep-research` pushed, `dd53c237` (this assessment is committed on top, local) |
| Implementation branch | `feat/intelligence-evidence-layer` pushed, `e9e5e571`, 67/67 tests |
| Published score | **4.8** (`sector-intelligence-score-v1`), unchanged; the evaluator does not read `evidence` |
| Customer path | unchanged (Engine Conditions Score, reads no Brain) |

## 2. Score report (displayed vs underlying, per the reset §10)
| | Value | Meaning |
|---|---|---|
| Published | 4.8 | plumbing rubric; cap 5.0 (validation) not binding |
| **Displayed / current** (research ladder) | **3.2** | what runs for customers today; unchanged |
| **Underlying** (adds the internal evidence layer: implemented, tested, pushed, not deployed) | **3.8** | `why` 5→7 and `confidence` 3→5, both internal only |
| Active caps | validation<5 (5.0) on the underlying; also confidence<5 (6.0) on the displayed | not binding at these values |
| Moved | why, confidence (internal) | |
| Did not move | specialistUse, where, when, species, validation, coverage, integrity | all wait on upstream Brains, field data or deployment |
| Next legitimate mover | Biological response bands (species 3→5), then a customer-path decision; validation 1→3 needs the blind-ranking data | |
Nothing was lowered, redefined or reclassified to get 3.8; the facts file shows the evidence string for each changed dimension.

## 3. Classification of the low dimensions (reset §31 C)
| Dimension | Score | Class |
|---|---:|---|
| specialistUse | 2 | consume provider/Brain truth (contracts pending) |
| where | 3 | Sector-derived (Depth/Vegetation/Wind exposure) |
| when | 5 | Sector-derived, bounded by each Brain's horizon |
| species | 3 | Sector-derived on Biological knowledge |
| why | 5 (7 internal) | deterministic (templates) |
| confidence | 3 (5 internal) | deterministic; calibration is validation |
| validation | 1 | validation / time |
| coverage | 6 | provider/Brain coverage |
| integrity | 5 | implementation (scheduling) |

## 4. SCORE DIMENSION EXHAUSTION MATRIX
| Dimension | Score | Product value | Work this session | Result | More desk work? | Real blocker |
|---|---:|---|---|---|---|---|
| specialistUse | 2 | High: Intelligence must read the Brains | evidence layer reads all 5 states with provenance | consumed internally, not in customer answer | **No** until real contracts exist | UPSTREAM BRAIN; MICHAEL DECISION (customer path) |
| where | 3 | High: which bank/zone | spatial model, Depth/Vegetation interfaces, wind exposure recorded as gap | UNKNOWN by design | No | UPSTREAM BRAIN (Depth, Vegetation, Wind exposure contract) |
| when | 5 | High: tonight, changing | tonight model, horizon rule R7, `carried` labelling | pilot evaluates NOW only | Small: checkpoint strip over fixtures, low value until bands exist | UPSTREAM BRAIN (horizons), IMPLEMENTATION |
| species | 3 | Highest: what to target | species-first assessment, bands parser | all species UNSUPPORTED, honestly | No | UPSTREAM BRAIN (Biological bands) |
| why | 5→7 internal | High | structured explanation with sources | done internally | No | MICHAEL DECISION / IMPLEMENTATION (customer wording) |
| confidence | 3→5 internal | High | weakest-link, caps, basis | done internally, uncalibrated | No | VALIDATION (calibration) |
| validation | 1 | High: proves usefulness | power simulation, validation strategy; **blind-ranking protocol + empty log template (new)** | ready for a field evening | **Done what desk work can; the rest is field** | FIELD, TIME / SEASON |
| coverage | 6 | Medium | none possible | n/a | No | UPSTREAM BRAIN |
| integrity | 5 | Medium | determinism, versioning tests | pilot unscheduled | No | PREREQUISITE BRANCH (`feat/cost-efficient-scheduling` unmerged) |
Intelligence-owned desk work is exhausted apart from the one deferred item above; everything else is upstream, field, a decision, or a prerequisite branch.

## 5. Rubric mismatch (documented, proposal only; the rubric is not changed)
`sector-intelligence-score-v1` measures wiring (94% of 4.8 is connectivity, dependency handling, provenance, runtime) and excludes `synthesisQuality` as UNKNOWN. Product capability is "can it tell a bowfisher where/when/what/why/how sure". Proposal `r2` (needs approval): score `synthesisQuality` as 0 once any evaluation exists; add `answersABowfisher` (species-specific, area-specific, explained, with confidence) weighted to at least the current plumbing share; cap validation as now. Proof of concept: `research/intelligence/tools/ladder_score.py`.

## 6. Simplification applied to Intelligence itself
Provider truth is restated, never recomputed. The evidence layer is one pure file with no I/O and no numeric score. Future work should shrink, not grow: no new models, no new data, no new tables.

## 7. Cost and computation rules honoured
The evidence layer runs only inside the existing pilot publisher (input-fingerprint driven); no customer request triggers it; no polling or new schedule was added.
