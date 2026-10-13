# Vegetation Brain — Research Summary

**RESEARCH ONLY. The Vegetation Brain is a NEW, PROPOSED Brain; Sector has no production Vegetation Brain.** Campaign date 2026-10-13. Branch `docs/vegetation-brain-research` (worktree `Sector_Engine-vegetation-research`, based on `main`). No score is published; no deploy, merge, registration, Map-Layer, iOS/Android, Intelligence, Biological, Clarity or Ops change was made.

## The answer in six lines
1. **Where is the vegetation / what broad kind / how dense?** Sentinel-2 can answer this for **plants that reach or float on the surface** (floating-leaved beds, mats, topped-out canopy, emergent belts) — AUC 0.98–0.995 and F1 0.94–0.97 on clear PNW lakes with dated polygons — but only moderately in Florida (AUC 0.65–0.67 shore-matched; cell recall 0.32).
2. **Submerged vegetation is not observable at fleet scale.** Every index and a learned model failed against submerged-only truth (AUC 0.57–0.77; recall 4.5 %); sonar lake-level data show Sentinel-2 sees only beds whose canopy reaches ≳40 % of the water column; clarity does not rescue it. The credible product is a labelled **potential-habitat** zone (depth × clarity × history), with observation only where surveys/sonar exist.
3. **Seasonality:** a GDD-based seasonal expectation is feasible as a labelled cloud-day fallback; its accuracy (65–75 % unmanaged, 40–50 % managed) is a hypothesis awaiting a back-test.
4. **Lake level / depth:** pool changes flood or strand shoreline vegetation and shift depth bands; Vegetation consumes Lake/Depth state and owns none of it. Canfield et al. 1985 gives a depth ceiling with a wide CI (46–236 %).
5. **Fleet:** 599 of 621 lakes have a polygon; 584 are ≥0.5 km² and suitable for surface-reaching observation (498 ≥5 km² clean, 86 mixed-pixel); 474 are submerged-*candidate* (clarity unknown); 77 lakes can be validated now (NLA 2017 sites inside the lake or FWC point data), 56 more with a request/browser download.
6. **Maturity (proposed, not official): ≈2.4/10**, ladder level 3. Gate is overall ≥ 8.0 and every critical dimension ≥ 7.5; the weakest critical dimension today is density (1.0).


## What exists today (audit)
- Slot `vegetation` reserved in the Brain platform contract only. 
- Clarity's surface-grass mask (NDVI ≥ 0.30 + FAI/SWIR gates, cloud borrowing ≤10 d) and a Guntersville-only iOS NDVI layer (65.8 % segment coverage, never validated). 
- No survey data in repo. See `VEGETATION_EXISTING_ASSET_AUDIT.md`.

## Best datasets
EPA NLA 2017 (class + density, 69 fleet lakes joined), FL FWC LTM points and lake PAC/PVI sonar, Snohomish WA dated polygons, USGS UMR SAV CSV, NWI (prior only), Minnesota UMN CC0 (needs browser), TVA/SFWMD/TPWD/WI (request). `VEGETATION_DATA_SOURCE_MATRIX.md`, `VEGETATION_SOURCE_LEDGER.md`.

## Evidence strength (be careful quoting)
- **Measured here:** Snohomish and Florida tests (notes 04/05), fleet joins, Canfield computations. Small, regional, with documented limits (5 + 7 lakes; presence-only FL; no Secchi at lake-date level; no confidence intervals).
- **Verified from opened sources:** Canfield 1985, Madsen & Owens 1998, FWC/SFWMD definitions, TPWD Sam Rayburn, Conroe history, Okeechobee SAV recovery.
- **Literature recall / expert estimate:** month-by-region table, GDD thresholds, depth-band probabilities, density cutoffs, seasonal-prior accuracy, all bowfishing-density effects (anecdotal). The remote-sensing and seasonal literature agents read search summaries, not full papers; their tags are carried through.
- **Corrected during the campaign:** the Secchi equation attribution (Canfield, not Chambers & Kalff); the 10/40 density cutoffs (SFWMD treatment-wetland legend, not FWC/Corps/TVA); Conroe grass-carp timing (1981–83); a double reflectance-offset error in the first S2 pass (discarded).

## Bowfishing value
A first Brain can honestly say: *"surface weed mats / lily pads / reed belts here, scattered–dense, seen N days ago, confidence X"*, *"this cove typically has dense hydrilla in July"*, *"pool is +2 ft — shoreline grass is likely flooded here"*, and *"2–8 ft shelf in clear water could hold submerged grass (modelled)"*. It cannot honestly say *"submerged grass is here"* from a satellite. Biological × Vegetation × Depth × Temp × Level is the high-value composition (`VEGETATION_CROSS_BRAIN_OPPORTUNITIES.md`).

## Major blockers (top 5; full list in `VEGETATION_BLOCKER_QUEUE.md`)
B-01 submerged not observable (pixel sonar truth unobtainable — FWC BioVolume services hang) · B-02 no fleet clarity feed · B-04 seasonal prior unvalidated · B-06 big-reservoir truth is request-only · B-10 density cutoffs uncalibrated.

## Recommended path
P0 evidence close-out → P1 offline surface-reaching observer (cell vote + pass acceptance + median persistence + refusals) on ~40 lakes → P2 density calibration vs NLA → P3 seasonal back-test → P4 potential-habitat → P5 fleet shadow. `VEGETATION_NEXT_IMPLEMENTATION_PLAN.md`.

## Deliverables
Summary (this), Asset Audit, Architecture Proposal, Data Source Matrix, Remote Sensing, Submerged, Emergent/Floating, Seasonal Model, Level/Depth Interaction, Validation Strategy, Fleet Coverage (+ `data/fleet_matrix.csv`), Rubric, Score Ladder, Cross-Brain, Blocker Queue, Source Ledger, Next Implementation Plan; plus `data/DATASET_MANIFEST.md`, `notes/` (raw campaign notes 01–05) and `scripts/`.
