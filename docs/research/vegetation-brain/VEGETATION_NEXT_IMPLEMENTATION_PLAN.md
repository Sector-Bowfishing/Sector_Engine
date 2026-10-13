# Vegetation Brain — Next Implementation Plan

**RESEARCH ONLY. Nothing here authorises deploying, registering, merging, publishing a score, or changing any customer layer.** This is a recommended order of work for a later, separately approved build. Boundaries from the mission remain: no Intelligence / Biological / Clarity / Ops changes; no Vegetation layer back in iOS/Android.

## 0. Recommendation in one paragraph
Build a **surface-reaching vegetation observer** first (emergent, floating-leaved, mats, topped-out canopy) from Sentinel-2 with cell-level voting, refusals and calibrated confidence; wrap it with a **seasonal expectation** and a **labelled potential-habitat** product for submerged/flooded vegetation that consumes Lake/Depth/Clarity/Temp state; validate each stage against independent survey truth before any exposure. Do **not** promise observed submerged vegetation fleet-wide.

## 1. Phased plan

| Phase | Deliverable | Entry | Exit gate | Ladder level |
|---|---|---|---|---|
| **P0 Evidence close-out** (research) | Cell-level rescore of Clarity's rule; sonar-truth test; NLA×S2 (47 lakes + 17 negatives); UMN, UMR pulls; truth requests sent | this campaign | Metrics for presence, cell FPR, density bins, submerged envelope in repo | 3 → 4 |
| **P1 Offline prototype** | Python module + notebooks: water mask, SCL masks, indices, 50 m cell vote, persistence composite, refusals; CSV/JSON outputs for ~40 stratified lakes | P0 | Pre-registered presence metrics met on ≥10 lakes/≥4 regions; open-water FPR below target (propose ≤2 % at cell level) | 4–5 |
| **P2 Density + calibration** | Cover-fraction→density mapping calibrated per regime; NLA/FWC/polygon kappa | P1 | Within-one-class ≥ ~90 %, weighted-kappa target pre-registered | 5 |
| **P3 Seasonal prior** | GDD-based phenology curves, lake amplitude from 2017–2025 history, management flags; back-test | P1 + Water Temp feed | Beats naive climatology per regime (pre-registered) | 6–7 |
| **P4 Potential habitat** | Depth×clarity×history product with Canfield CI; flooded-terrestrial candidates from Lake Brain anomaly | Depth/Clarity inputs (or `MODELLED`/proxy) | Calibrated against sonar (FL) and survey; honest tier labels | 7 |
| **P5 Fleet shadow** | Scheduled run over all 599 polygon lakes, logging only (no customer exposure); health/freshness per Brain-platform contract | P1–P3 | Platform contract tests; refusal rates measured; no regressions in other Brains | 6–7 |
| **P6 Survey fusion** | Ingest FWC/MN/WI/TVA/TPWD/NLA refreshes as `OBSERVED_SURVEY` and calibration | requests answered | Calibration logs by region | 8–9 |
| **P7 Intelligence handoff** | Evidence interface to Intelligence/Biological (read-only, versioned) | P5 + owners agree | Gate: overall ≥ 8.0 and critical ≥ 7.5 under the rubric | 8 |

## 2. Technical choices (proposal)
- **Pipeline home:** new job under `jobs/vegetation-brain/` mirroring `water-clarity-brain` and `lake-surface` layout; separate container; no shared mutable state with Clarity.
- **Data:** Earth Search `sentinel-2-c1-l2a` (offset: DN×1e-4 − 0.1; fall back to `sentinel-2-l2a` where c1 lacks scenes, e.g., 2022); SCL masks; Polymer/C2RCC trial for red/NIR over water later.
- **Cells:** 50 m grid per lake, fraction + class + density; store 10 m evidence only in debug.
- **Cloud gaps:** persistence over 10–30 d, `BORROWED` flag; never silent.
- **Cost:** open data and range reads; the empirical test pulled ≈1 GB of windowed COGs for 12 lakes over ±45 days, so a fleet run should be dominated by incremental daily deltas, not archives (estimate; measure in P1).
- **Language:** Python for the job (as Clarity); Swift reading of states via the Brain platform keys.
- **Tests:** golden-lake regression set (Snohomish, FWC lakes, NLA negatives); refusal tests; schema gate; no network in unit tests.

## 3. Pre-registered success targets (proposal; adjust before P1 scoring)
| Metric | Target to leave P1 |
|---|---|
| Presence F1 (shore-matched, leave-one-lake-out) on surface classes | ≥ 0.80 clear lakes; report turbid separately |
| Open-water false-positive rate (cell-level) | ≤ 2 % |
| Recall of survey-recorded surface vegetation (within ±7 d) | ≥ 0.75 |
| Density within-one-class | ≥ 90 % |
| Refusal accuracy | ≥ 95 % of non-refused cells correct vs truth |
| Seasonal prior vs naive climatology | beats by ≥ 10 pts exact-class on unmanaged; reported separately for managed |

## 4. Risks
1. **Surface-only observer disappoints bowfishers** who think "grass" means submerged beds → wording and `POTENTIAL_HABITAT` labels; product-owner decision.
2. **Bloom false positives** in warm nutrient-rich lakes.
3. **Overreach**: pressure to display potential habitat as observed; mitigated by tier fields and Intelligence contract.
4. **Truth scarcity in the big reservoirs** → keep confidence capped for unvalidated lakes.
5. **Cross-Brain dependency** on Clarity, Depth, Lake Brain readiness.

## 5. Explicitly not recommended
Species identification from satellite; fleet-wide "observed submerged" from NDVI/NDAVI; interpolating unread cells with a lake mean; validating against Dynamic World/NLCD; shipping the unvalidated regional seasonal table as fact.
