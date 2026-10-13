# Depth Brain Research Summary (2026-10-13)

Branch `docs/depth-brain-research`, worktree `Sector_Engine-depth-research`, based on `main`. Research only: no deploy, merge, RTDB, scheduler, API, app, Ops or other-Brain change. **Depth Brain did not previously exist**; the asset audit found only reusable evidence.

## Bottom line
**Sector can build a narrow, honest Depth Brain, but not a fleet-wide bathymetry layer.** Proposed maturity **4.3 / 10** (gates fail: overall < 8, all critical dimensions < 7.5). Unknown is better than wrong for about 60 % of the fleet.

## What we found
1. **Assets**: the only measured depth in any Sector product is a 2007 USACE IENC 9 ft contour on Guntersville (67 % of 6,504 segments). Everything else is modeled mean depth, GLOBathy, or the 3DEP shoreline proxy.
2. **GLOBathy is not usable for bowfishing.** Dmax Spearman 0.42 vs truth (n=75), 0.18 vs contour max depth (n=73); within 2x 68 % vs 56 % for a constant; it regresses to the middle (3.6x too deep for lakes < 8 m, 0.51x for > 40 m); shallow-area share no better than a constant (MAE 0.135 vs 0.128; broad-shallow AUC 0.53); rasters are the same power law extruded from shore (no flats or drop-offs). 89 % of the fleet has a row, but only 234 matches are verified (chain-reservoir mismatches). The 59 fleet lakes whose Dmax was literature-supplied are fine but are not a model test. Verdict: low-confidence coarse class prior only, never scored.
3. **Real contours exist for more lakes than expected, but not where bowfishers need them.** 20 sources, 4.6 GB, 140 verified fleet lakes, **103 at tier A/B** (WV, MN, NE, OH, FL (internal), KS, MA, CT, NH, TX, MT, OK, ND ...). Zero TVA lakes; no SE reservoir; 23 states without any source.
4. **What a bowfisher learns where contours exist** (tier A, n~77): median lake has 9 % of its surface in 0-3 ft, 9 % in 3-6 ft, 11 % in 6-10 ft, 69 % deeper; <6 ft is 18 % (10th-90th 8.5-41 %). Shallow water is narrow: median shore-to-6-ft distance 38 m; the 6 ft contour is within 30 m of the bank on 43 % of the median lake's shoreline. Broad flats (>= 200 m wide, 0-6 ft) cover a median 55 ha in 3 patches and 23 of 96 lakes have none. Flats are the exception, which is why locating them is valuable.
5. **No scalable proxy finds them.** Nothing tested beats a constant for the < 6 ft share (3DEP slope, polygon shape, mean depth, GLOBathy; leave-one-state-out). Best: distance to shore (cell AUC 0.82-0.90) and, on lakes whose level moves 8-25 ft, Landsat drawdown exposure (Spearman 0.87-0.93 vs real depth, 5 lakes). Contour interval matters: 5 ft gives 1.3 ft RMSE, 10 ft gives 2.8 ft (overstates shallow). Shoreline slope does predict **acres gained per foot of pool** (Spearman 0.77 on CWMS n=33, 85 % within x2).
6. **Effective depth is the strongest near-term capability.** Shift = level - full pool (same as Lake Brain `differenceFromNormalPoolFt`): possible for 265 lakes in the matrix (339 per terrain eligibility, 187 with 10 y history, median 5-95 % range 10 ft; 145 lakes >= 4 ft). Sigma 0.27 ft (high pool confidence) to 1.0 ft (medium). Datum shifts are real (NGVD29-NAVD88 median 0.64 ft, up to 5.4 ft). Real examples: a 4 ft flat on Guntersville is 2.8-4.0 ft across the year (< 3 ft on 26 % of days); at Hartwell 31 % of days it is dry; on Fork, 475 acres of 3.5-4.5 ft water were all dry at the low; Guntersville moves 4,890 acres per foot.
7. **Fleet matrix** (621): A 77, B 26, B-partial 35, B-binary 28, C 28, D 371, U 56.

## Recommended Depth Brain scope
Own: reference depth evidence with tier/sigma/provenance, tier A/B zones and flats where real, the level-shift state, and explicit `unknown`. Refuse: modeled depth for unsurveyed lakes, per-segment flats from slope.

## Where to look
Architecture, GLOBathy, source matrix, validation, fleet coverage, effective depth, shallow zone, contour truth, rubric, score ladder, cross-brain, blockers, source ledger, next plan: the `DEPTH_BRAIN_*.md` files in this directory; existing assets in `DEPTH_EXISTING_ASSET_AUDIT.md`.

## Caveats
Small n (33 CWMS, 63 TWDB, 77 A-tier, 9 MN, 5 Landsat); truth is 65 % reservoirs and not random; datums for TVA/Santee/Duke not verified; scouting search budget ran out so absence in a state is not proof; no bowfishing field validation exists.
