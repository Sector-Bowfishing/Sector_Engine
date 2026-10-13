# Biological Brain: Current State Audit

> **CORRECTION (2026-10-13, adoption pass).** The baseline in this document is wrong. The live canonical score (`/scores/biological-state`) is **4.0**, not 3.46: the local recomputation omitted the `productionIntegration` dimension (+0.5; Intelligence's dependency on the Biological Brain is CONNECTED). Corrected figures: published **4.0** (State-NOT_STARTED gate cap 4.0 not reducing it); research-supported rows would add +0.3 but stay hidden behind that gate until a Biological State exists. Also: "four independent silver-carp flow datasets" is **three** (the Illinois 2004-05 and Swan Lake papers share one tagged program), and the channel-catfish production-temperature concern was overstated (only the 85 F upper bound is above agency spawning figures). See `docs/brains/biological-adoption/` on `feat/biological-brain-adoption`.


**Date:** 2026-10-13 · **Branch:** `docs/biological-brain-research` (research only; nothing deployed, merged or published)
**Method:** read the live private bundle (`gs://sector-biology-private/biology/v1`, release `2026-10-12.1`, read-only), the public contract (`docs/brains/BIOLOGICAL_BRAIN_INTEGRATION.md`), the scoring rubric (`docs/brains/scoring/biological-state-score-v1.json`), the publisher (`jobs/biological-brain/`), the production species table (`SpeciesDatabase.swift`) and the Intelligence consumer (`jobs/sector-intelligence-brain/evaluation.py`).
**Public-safety:** this file contains scores, structure and counts only. No species profiles, rules or evidence text.

## 1. Published state

| Item | Value |
|---|---|
| Release | `2026-10-12.1`, scoring `species-v2` |
| Registry rows | 29 (27 ASSESSED, 2 NOT_ASSESSED: `tilapia_unresolved`, `suckers_redhorse_carpsuckers_group`) |
| Research maturity | 20 `RESEARCH`, 7 `NOT_STARTED` (all-zero rows), 2 not assessable. **0 REVIEWED, 0 VALIDATED** |
| Species with engine-format rules | **1** (common carp, 48 rules). The other 26 assessed rows carry a score but no rules |
| Open discrepancies | 3+ (grass carp / smallmouth / bigmouth / black buffalo presence vs shipping iOS; all Guntersville) |
| Per-lake Biological State | `NOT_STARTED` (nothing written to `/lakes/{k}/states/biology`) |
| Field validation | `NOT_VALIDATED`; no species rule has been checked against observations |
| Intelligence consumption | Intelligence reads `/species/{id}` only for a **knowledge median** shown as a driver line ("N present species; knowledge median X / 10"). **No species rule, season, temperature or habitat fact is consumed.** |

## 2. Species scores (species-v2, evidence completeness, not accuracy)

| Tier | Species | Overall (rounded) |
|---|---|---:|
| Researched | Common carp | 7.0 |
| | Grass carp | 5.5 |
| | Alligator gar | 5.0 |
| | Silver carp | 4.5 |
| | Longnose gar | 4.5 |
| | Spotted gar | 4.5 |
| | Smallmouth buffalo | 3.5 |
| | Bigmouth buffalo | 3.5 |
| | Bighead carp | 3.0 |
| Thin | Shortnose gar 2.0 · Northern snakehead 2.0 · Bowfin 1.5 · Paddlefish 1.5 · Black carp 1.0 · Black buffalo 1.0 · Freshwater drum 0.5 |
| Effectively empty | Channel catfish, shorthead redhorse, striped mullet, carpsuckers group (0.0, with a single 1-point fact each) |
| Zero (`NOT_STARTED`) | Gizzard shad, golden redhorse, blue sucker, silver redhorse, American shad, river redhorse, goldfish |

Median of the 27 assessed rows' rounded scores is **1.0**; mean exact is **1.86**.

## 3. Actual published Biological Brain score (`biological-state-score-v1`)

Reproduced from the bundle (the evaluator reads the live RTDB; this is a local recomputation of the same rubric):

| Dimension | Weight | Fact | Earned |
|---|---:|---|---:|
| registryCompleteness | 10 | 27 + 2 = 29 | 10.0 |
| assessedCoverage | 15 | 27 / 29 | 9.3 |
| knowledgeDepth | 20 | median species overall = 1.0 | 1.0 |
| evidenceQuality | 10 | RESEARCH only, no REVIEWED/VALIDATED | 2.0 |
| contradictionsGaps | 10 | mean capped contradiction load 0.34 | 6.6 |
| regionalTransfer | 5 | not published | UNKNOWN (0) |
| biologicalStateImpl | 15 | NOT_STARTED | 0 |
| biologicalStateValidation | 10 | NOT_STARTED | 0 |
| productionIntegration | 5 | Intelligence does not use species rules; connection status per dependency node | 0 (assumed; verify live) |

Weighted total ≈ **3.5 / 10** (3.6 if the unknown 5-point dimension is excluded). Gates: Biological State NOT_STARTED caps at **4.0**; no species VALIDATED caps at **6.0**. The cap is not binding today; **the score is held down by knowledgeDepth (median 1.0), evidenceQuality (no REVIEWED/VALIDATED), and the two Biological-State dimensions (25 points at 0).**

> The live score was not read from RTDB in this session (no write or RTDB credentials were exercised). Treat 3.5 as a reproduction, to be confirmed against `/scores/biological-state`.

## 4. Structural findings

1. **The median is the wrong lever for bowfishing impact.** `knowledgeDepth` is the median over all 27 assessed species. 18 of 27 rows are obscure (redhorses, shad, mullet, snakehead, goldfish…) and sit at 0–2, so the median is 1.0 even though the nine principal targets average ~4.6. Getting a real score gain by raising the median would mean assessing minor fish, which does not help a bowfisher. This should be raised with Michael as a rubric question, **not gamed** (see `BIOLOGICAL_SCORE_LADDER.md`).
2. **Rules are the product, scores are the audit trail.** Only common carp has rules. Intelligence can not say *where to look* for any other species without them.
3. **A third of the assessed rows are empty.** Seven rows are `ASSESSED` + `NOT_STARTED` with all-zero domains; policy says assessed, knowledge says nothing.
4. **No independent review process exists** to ever reach REVIEWED; promotion is deliberately a separate decision.
5. **Production species logic disagrees in places** (spawn windows and temperature bands in `SpeciesDatabase.swift`; see `BIOLOGICAL_SPAWN_RESEARCH.md` for the comparison). Production is not changed here.
6. **Regional transfer is unscored.** Nearly all telemetry is northern or foreign; Southeast reservoir (TVA-type) transfer is the dominant uncertainty.

## 5. Knowledge fields in the profile schema

`displayName, scientificName, aliases, appKeys, taxonomy*, assessment, researchMaturity, knowledge{8 domains: score, status, basis[], contradictions[], limits[]}, rules[], evidence, gaps, nextResearchPriority, policyNote, separateAssessments, discrepancies, history, provenance`. A rule has: conditions, locationImplication, mechanism, exceptionsAndConflicts, evidence, confidenceAndTransfer, inputDependency.

## 6. Private / protected research

Detailed profiles, rules, evidence and history are private (`gs://sector-biology-private`, public access prevention on). This campaign's raw packets live **outside git** at `Sector_Research_Data/biological-brain/` (bundle snapshot, evidence packets, source texts). Only public-safe summaries are committed under `docs/research/biological-brain/`.

## 7. Major gaps (ranked by bowfishing value)

1. Rules for the eight principal non-carp targets (silver, bighead, grass, buffalo ×3, gars ×4): scored but rule-less.
2. Southeast-reservoir transfer: non-spawning, summer-night and winter positions.
3. Night shallow-water behavior (the app's primary use case) for nearly every species.
4. Zero-knowledge rows that are still ASSESSED.
5. No validation design; no field-observation pathway.
6. Per-lake Biological State not started (25 rubric points).
