# Contour Effective-Zone Validation vs CWMS Stage-Area Curves: Results

Date: 2026-10-13. Preregistration `DEPTH_CONTOUR_VALIDATION_PREREG.md` / `jobs/depth-brain/depth_brain/data/proposals/contour_prereg.json`, sha256 `04d16d491fa860407800f4c8c1d1bc526e4393880f4983a428f858e49212ba65`, frozen 2026-10-13T21:23:13Z (the script verified the hash of the prereg and of the two data files before computing; it ran once). Script `research/depth/contour2_validate.py` using the real `zones.reference_zones_from_shares` / `zones.effective_zones`; rows `data/contour2_validation_rows.csv` (every lake-level, every band, both sigmas), summary `data/contour2_validation_summary.json`. Reference pools: `DEPTH_CONTOUR_SOURCE_REFERENCE_POOLS.md`. No threshold, level, lake or rule was changed after results.

## 1. Verdict

**No lake passed. `validation.passed = false` for all four graded lakes (Alum Creek, Tappan, Fort Gibson, Sardis); Caesar Creek is VERIFIED but has no area curve (null); the other 89 are UNVERIFIED (null).** Effective zones should stay withheld for every non-TWDB contour lake.

Graded set: the 4 VERIFIED lakes that have a CWMS Elev;Area curve, 5 drawdowns each = 20 lake-levels. Truth: the operator's exact stage-area curve; predictor: the manifest contour shares (independent of the curve; no circularity, see section 5).

| Frozen threshold (dry share, production sigma 0.2872 ft) | Result (graded, n published = 4 of 20) | Pass |
|---|---|---|
| T1 MAE <= 0.03 | 0.047 | FAIL |
| T2 max abs error <= 0.06 | 0.061 | FAIL (0.0609, by 0.0009) |
| T3 bounds coverage >= 0.80 | 1.000 | PASS |
| T4 median bounds width <= 0.15 | 0.132 | PASS |
| T5 pooled Spearman >= 0.95 | 1.000 (n = 4, all Tappan) | PASS but meaningless |
| T6 publish rate >= 0.60 | 0.200 | FAIL |

Why: three of the four graded lakes have 5 or 10 ft contour intervals, so only the 10 ft edge exists and the dry bound is `[0, S10]` (0.27, 0.43 and 0.30 of the surface), wider than the engine's own 0.25 publication limit: the engine **correctly refuses** (0 of 15 lake-levels published). The one fine-interval graded lake, Tappan (3 ft), publishes 4 of 5 levels but is biased high by 0.047 (all four errors positive, 0.021-0.061): the contour product has more shallow area than the 1970 Corps curve.

## 2. Graded lakes, every lake-level (production sigma)

| Lake | Interval | d (ft) | truth dry | published bounds (lo-hi) | midpoint error |
|---|---|---|---|---|---|
| Alum Creek Lake|OH | 5 | 1.5 | 0.042 | withheld (bound wider than 0.25) | - |
| Alum Creek Lake|OH | 5 | 3.0 | 0.083 | withheld (bound wider than 0.25) | - |
| Alum Creek Lake|OH | 5 | 4.5 | 0.123 | withheld (bound wider than 0.25) | - |
| Alum Creek Lake|OH | 5 | 6.0 | 0.160 | withheld (bound wider than 0.25) | - |
| Alum Creek Lake|OH | 5 | 8.0 | 0.208 | withheld (bound wider than 0.25) | - |
| Fort Gibson Lake|OK | 10 | 1.5 | 0.056 | withheld (bound wider than 0.25) | - |
| Fort Gibson Lake|OK | 10 | 3.0 | 0.109 | withheld (bound wider than 0.25) | - |
| Fort Gibson Lake|OK | 10 | 4.5 | 0.164 | withheld (bound wider than 0.25) | - |
| Fort Gibson Lake|OK | 10 | 6.0 | 0.213 | withheld (bound wider than 0.25) | - |
| Fort Gibson Lake|OK | 10 | 8.0 | 0.279 | withheld (bound wider than 0.25) | - |
| Sardis Lake|OK | 10 | 1.5 | 0.047 | withheld (bound wider than 0.25) | - |
| Sardis Lake|OK | 10 | 3.0 | 0.094 | withheld (bound wider than 0.25) | - |
| Sardis Lake|OK | 10 | 4.5 | 0.129 | withheld (bound wider than 0.25) | - |
| Sardis Lake|OK | 10 | 6.0 | 0.169 | withheld (bound wider than 0.25) | - |
| Sardis Lake|OK | 10 | 8.0 | 0.223 | withheld (bound wider than 0.25) | - |
| Tappan Lake|OH | 3 | 1.5 | 0.050 | 0.0-0.143 | +0.021 |
| Tappan Lake|OH | 3 | 3.0 | 0.101 | withheld (bound wider than 0.25) | - |
| Tappan Lake|OH | 3 | 4.5 | 0.151 | 0.143-0.263 | +0.052 |
| Tappan Lake|OH | 3 | 6.0 | 0.202 | 0.143-0.382 | +0.061 |
| Tappan Lake|OH | 3 | 8.0 | 0.269 | 0.263-0.382 | +0.054 |

Zero-sigma run (informational): Tappan publishes all 5 levels, MAE 0.046, but coverage only 0.600 (the bounds collapse to points that are about 0.05 too high). The other three lakes still publish nothing.

## 3. Informational: the same test under an ASSUMED reference pool (20 more lakes)

These lakes are UNVERIFIED, so they never count toward pass/fail. Reference pool = the source-stated/implied pool when the source has one (NE/KS/ND), else the directory pool; CWMS curve as truth. This answers: IF the contours are measured from that pool, would the arithmetic hold? A wide gap between assumed and implied pool (column D2) is evidence the assumption may be wrong or the curve is outdated.

| Lake | Interval | Published/included | MAE | Max err | Coverage | Median width | D1 contour minus curve share at pool (edges) | D2 implied pool minus pool (ft) | Curve version / survey year |
|---|---|---|---|---|---|---|---|---|---|
| Stonewall Jackson Lake|WV | 1 | 4/5 | 0.009 | 0.016 | 1.000 | 0.133 | 3.0:-0.013, 6.0:-0.011, 10.0:-0.005 | +0.8 | 1970 / ? |
| Tygart Lake|WV | 1 | 5/5 | 0.100 | 0.128 | 0.400 | 0.046 | 3.0:+0.126, 6.0:+0.127, 10.0:+0.128 | +4.9 | 1970 / ? |
| Bowman-Haley Reservoir|ND | 2 | 3/5 | 0.032 | 0.039 | 1.000 | 0.192 | 3.0:-0.056, 6.0:-0.030, 10.0:-0.014 | +1.8 | 2024 / ? |
| Branched Oak Lake|NE | 3 | 4/5 | 0.007 | 0.019 | 1.000 | 0.138 | 3.0:-0.001, 6.0:-0.000, 10.0:+0.006 | -0.1 | 2020 / 2003 |
| Lake Milton|OH | 3 | 4/5 | 0.017 | 0.043 | 1.000 | 0.149 | 3.0:+0.002, 6.0:+0.015, 10.0:+0.067 | -2.4 | 1970 / 1998 |
| Mosquito Creek Lake|OH | 3 | 3/5 | 0.028 | 0.052 | 1.000 | 0.178 | 3.0:+0.001, 6.0:+0.020, 10.0:+0.078 | -2.9 | 1970 / 2004 |
| Senecaville Lake|OH | 3 | 2/5 | 0.102 | 0.108 | 0.500 | 0.137 | 3.0:+0.141, 6.0:+0.076, 10.0:+0.117 | -6.0 | 1970 / ? |
| Cheney Reservoir|KS | 5 | 0/5 | n/a | n/a | n/a | n/a | 10.0:-0.003 | +0.5 | 2014 / 2010 |
| Clinton Lake|KS | 5 | 0/5 | n/a | n/a | n/a | n/a | 10.0:-0.020 | +2.3 | 2012 / 2009 |
| El Dorado Lake|KS | 5 | 0/5 | n/a | n/a | n/a | n/a | 10.0:-0.065 | +3.0 | 2014 / 2010 |
| Harlan County Lake|NE | 5 | 5/5 | 0.043 | 0.082 | 1.000 | 0.217 | 10.0:-0.009 | -3.5 | 1998 / ? |
| Lake Winnibigoshish|MN | 5 | 5/5 | 0.084 | 0.165 | 0.600 | 0.210 | 10.0:-0.094 | -0.4 | 2003 / ? |
| Leech Lake|MN | 5 | 0/1 | n/a | n/a | n/a | n/a | 10.0:n/a | n/a | 2003 / ? |
| Pomona Lake|KS | 5 | 0/5 | n/a | n/a | n/a | n/a | 10.0:+0.014 | -0.9 | 1998 / 2009 |
| Swanson Reservoir|NE | 5 | 5/5 | 0.045 | 0.078 | 1.000 | 0.238 | 10.0:+0.001 | -0.5 | 1998 / 2001 |
| Gull Lake|MN | 10 | 0/3 | n/a | n/a | n/a | n/a | 10.0:n/a | n/a | 2003 / ? |
| Melvern Lake|KS | 10 | 0/5 | n/a | n/a | n/a | n/a | 10.0:-0.012 | -0.9 | 2019 / 2009 |
| Milford Lake|KS | 10 | 0/5 | n/a | n/a | n/a | n/a | 10.0:+0.015 | +5.8 | 2012 / 2009 |
| Tiber Reservoir (Lake Elwell)|MT | 10 | 5/5 | 0.032 | 0.058 | 1.000 | 0.124 | 10.0:-0.019 | +1.0 | 2024 / ? |
| Wilson Lake|KS | 10 | 5/5 | 0.038 | 0.062 | 1.000 | 0.185 | 10.0:-0.019 | +0.0 | 2012 / 2008 |

Pooled, interval <= 3 ft (7 lakes): published 25/35 (0.714), MAE 0.040, max 0.128, bias +0.028, coverage 0.840, median width 0.148, Spearman 0.835.

Pooled, interval 5 ft (8 lakes): published 15/36 (0.417), MAE 0.058, max 0.165, bias -0.028, coverage 0.867, median width 0.217, Spearman -0.378.

Pooled, interval 10 ft (5 lakes): published 10/23 (0.435), MAE 0.035, max 0.062, bias +0.000, coverage 1.000, median width 0.154, Spearman 0.035.

Pooled, all assumed-pool lakes (20 lakes): published 50/94 (0.532), MAE 0.045, max 0.165, bias +0.006, coverage 0.880, median width 0.185, Spearman 0.648.

Leave-one-lake-out fleet-mean baseline (dry share at the same d): MAE 0.021 on the 4 graded lakes, 0.042 on the assumed-pool lakes. On the graded lakes the simple baseline (0.021) beats the engine's published midpoints (0.047).

## 4. What the numbers say

1. **Interval decides publishability.** Dry share is published at 9 of 10 levels for 1 ft contours (Stonewall Jackson, Tygart), 3 of 5 for 2 ft, 17 of 25 for 3 ft, 15 of 41 for 5 ft and 10 of 33 for 10 ft (production sigma, all included lake-levels of the 24 lakes; the 10 ft figure is helped by shallow-edge lakes such as Tiber and Wilson whose S10 is below 0.25). With a 5 or 10 ft interval only the 10 ft edge is known; where the lake is shallow enough that S10 < 0.25 the engine publishes `[0, S10]` or `[S10, 1]` bounds, which are honest but nearly information-free.
2. **Where it publishes, bounds cover the truth but the midpoint is often biased.** Assumed-pool lakes with interval <= 3 ft: coverage 0.84, bias +0.028, MAE 0.040. Tygart (+0.100), Senecaville (+0.102), and Winnibigoshish (-0.076) are large, and in each the D2 diagnostic or D1 shows the contour shares disagree with the curve at the assumed pool by 0.05-0.13: either the contour reference level differs from the assumed pool (survey-date water level), the curve predates the contours (1970 design curves vs 1998-2004 surveys), or the lake has changed. This study cannot separate the three.
3. **D1/D2 are suggestive, not conclusive.** Contour minus curve share at the assumed pool is small (|D1| <= 0.02) for Branched Oak, Stonewall Jackson, Swanson, Cheney, Pomona, Melvern, Wilson, Clinton and Tiber, and large for Tygart (+0.13), Senecaville (+0.14), Mosquito Creek (+0.08 at 10 ft), Lake Milton (+0.07 at 10 ft), Tappan (+0.04 to +0.06), Fort Gibson (+0.09), El Dorado (-0.065) and Winnibigoshish (-0.094). The implied-pool shifts (D2) of +2 to -6 ft for the Ohio/Oklahoma lakes would mean a very different survey level, which is unlikely for lakes documented at normal pool; the more probable cause is stale or differently defined curves (e.g. CWMS Fort Gibson curve effective 1951, 2012 survey). Treat these as flags for owner review, not as findings.
4. **The skill over a guess is not demonstrated.** For the four graded lakes a fleet-mean guess beats the engine (0.021 vs 0.047 MAE), mostly because the engine's bounds midpoints are poor when bounds are wide and half the levels are withheld.

## 5. Circularity, independence, small n

* **Circularity:** none by construction here. Predictor = contour-product shares from state/agency surveys; truth = CWMS operator curves. Unlike TWDB's S1 there is no same-table predictor. Possible hidden lineage (a Corps curve updated from the same survey, e.g. NWDM curves effective 2012-2019 for Kansas lakes) was not checked and would make agreement look better than independent.
* **Small n:** 4 graded lakes, 20 lake-levels of which 4 published; the five levels per lake are strongly dependent. The pooled graded Spearman (1.0) rests on four Tappan points. The informational groups (20 lakes, 94 lake-levels) are assumed-pool and not a pass statistic.
* **Truth is a curve, not an observation of the lake at another level.** Curve versions are matched to the survey year (nearest effective year); MN curves cover only the operating range (Leech reaches 2.9 ft, Gull 5.2 ft below pool) so d = 3 to 8 are excluded for Leech and d = 6, 8 for Gull; MN elevations rest on the assumption stage = elevation - CWMS location elevation (1100.0 / 1200.0 ft); NWDM Step templates have datum "OTHER".
* **Shares are of the surveyed surface** (coverage < 1 for some lakes), the curve is of the whole lake.
* Disclosure from the prereg: before freezing the author knew the source-vs-directory pool comparisons and the manifest shares; no share-vs-curve comparison existed. The R2 tolerance was held at 0.25 ft with no rounding allowance on purpose.

## 6. Recommendation

* Keep `effectiveZones` withheld for every non-TWDB contour lake. VERIFIED + passed is the only enable condition and nothing meets it.
* Fine-interval (<= 3 ft) Corps lakes with a curve are the only realistic candidates (Tappan was closest: T3, T4, T6 passed or near, T2 missed by 0.0009, T1 missed by 0.017). Re-run after resolving the Tappan curve question (1970 design table vs 1998 survey): the rule is already frozen; a new prereg is needed for any threshold change.
* Do not try to enable 5/10 ft-interval lakes: the engine's own width rule withholds them, correctly.
* What is still needed: the survey-date water level (or an explicit statement that depths are normalised to the pool) from each owner; pool datum confirmations (section 5 of the reference-pool doc); a current sediment-survey area curve for Ohio/Oklahoma Corps lakes; more fine-interval Corps lakes with curves (Kansas lakes are 5/10 ft in the manifest).
