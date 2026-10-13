# Source ledger

Every fact in these documents comes from one of the sources below. Status: **READ** (read in full or the relevant parts this session), **RUN** (executed), **DELEGATED-READ** (a read-only subagent reported file-level facts; I did not re-open every file), **RECALLED** (general knowledge, not re-verified this session).

## Code and docs in this repository (public), at `origin/main` e596a6bb
| Source | Status | Used for |
|---|---|---|
| `docs/brains/scoring/sector-intelligence-score-v1.json`, `SCORING.md`, `frozen-scores.json` | READ | published rubric, other Brains' scores |
| `jobs/brain_platform/sector_brain_platform/scoring.py` (`score_intelligence`) | READ | reproduction of 4.8 |
| `docs/consolidation/STABILIZATION_LOG.md`, `HANDOFF_2026-10-12.md` | READ (relevant phases) | score history, pilot facts, staleness |
| `docs/brains/SECTOR_INTELLIGENCE_BRAIN_INTEGRATION.md`, `_STATUS.md`, `OWNERSHIP_MATRIX.md`, `BIOLOGICAL_BRAIN_INTEGRATION.md` | READ | implementations, contracts, ownership exceptions |
| `jobs/sector-intelligence-brain/` (`evaluation.py`, `catalog.json`, tests) | READ + RUN (32 tests pass) | pilot evaluation, catalog |
| `Sources/SectorEngine/Engine/**` (aggregator, gates, config, factors, WhereToLook, species DB) | READ | customer path behaviour |
| `Sources/SectorEngine/Forecast/**`, `API/**`, `Engine/Adapters/ConditionsInputBuilder.swift`, `ConditionsInput.swift`, tests list | DELEGATED-READ | tonight/nights, caches, inputs, test inventory |
| `jobs/wind-hourly/sector_wind/**` incl. `brain/validation_evidence.json` | DELEGATED-READ | wind state, bank exposure, skill numbers |
| `docs/clarity/**`, Water Temp / Clarity / Biological facts | DELEGATED-READ + handoff docs | upstream status |

## Other worktrees (local, read-only)
| Source | Status | Used for |
|---|---|---|
| `Sector_Engine-water-temp-research` (`docs/research/water-temp/*`, branch `docs/water-temp-brain-research` 2219cbc9) | DELEGATED-READ | water temp ladder, blockers |
| `Sector_Engine-wind-research` (`docs/wind-research/WIND_RESEARCH_PREREG.md`, `research/wind-brain`) | DELEGATED-READ | wind validation preregistration |
| `Sector_Engine-depth-research` (`docs/research/depth-brain/DEPTH_EXISTING_ASSET_AUDIT.md`, untracked) | DELEGATED-READ | depth assets, no Brain |
| `Sector_Engine-vegetation-research` | DELEGATED-READ | confirmed absent (no research files) |
| `Sector_Engine-biological-research` (`BIOLOGICAL_CURRENT_STATE_AUDIT.md`, untracked) | DELEGATED-READ | species knowledge aggregates only; no per-lake private labels used |
| Lake Brain handoff (`Sector Handoffs/Sector Engine/…Lake Brain Research Campaign Handoff…`) | READ (head) | convention for layout and boundary rules |

## Private repo (facts only; no thresholds or code in the committed docs)
| Source | Status | Used for |
|---|---|---|
| `iOS/Sector` branch `sector/app-updates` 6fb3fa87: `Sector/FishIntel/**`, `FISH_INTELLIGENCE_BETA_READINESS.md`, `docs/fishintel/LAYER_REVIEW_2026-09-26.md` | DELEGATED-READ | structure, species coverage, spatial unit, unknown handling, exposure, duplicate science. Detail is in the private handoff appendix, not the repository |

## Executed this session
| Artifact | What it is |
|---|---|
| `research/intelligence/probe/` (Swift package, path dependency on the unmodified engine) → `out/aggregator_probe_output.txt` | 9 experiments on the real `ConditionsAggregator`, synthetic inputs |
| `research/intelligence/prototype/` (stdlib Python) | synthesis rules R1–R9, 15 passing tests |
| `research/intelligence/validation/power_sim.py` → `power_sim_output.txt` | seeded Monte Carlo of validation design and effort confound; synthetic |
| `research/intelligence/tools/ladder_score.py`, `data/` | research score computation |

## Background methodology (RECALLED, not re-verified, no claim rests on a specific figure)
- Catch-per-unit-effort can mislead as an abundance index (hyperstability/hyperdepletion) and must be effort-standardised: standard fisheries-assessment literature (e.g. Hilborn & Walters, *Quantitative Fisheries Stock Assessment*, 1992; Harley, Myers & Dunn 2001, *Can J Fish Aquat Sci*). Used only to justify the effort-hour outcome definition.
- Paired designs and pre-registration as standard bias controls. General practice.
Primary-source verification of these two is a to-do for the next session; none of the numbers in the documents depends on them.

## Not done / not available
No live RTDB, Cloud Run, bucket or app-store reads; no user data; no web research on bowfishing biology (Biological owns it). Published Brain states in these documents are quoted from repository docs dated 2026-10-12, not read live. No live Brain states were fabricated; all probe and prototype inputs are labelled synthetic.
