# TWDB Effective-Zone Validation: Results Against the Preregistration

Date: 2026-10-13. Preregistration: `DEPTH_TWDB_VALIDATION_PREREG.md` / `jobs/depth-brain/depth_brain/data/proposals/twdb_prereg.json`, sha256 `cac72a99e9f884ffe3993b6630981adf7835dd2387661a9f3908373ff3fdc82c`, frozen 2026-10-13T20:38:45Z (the script verified the hash before computing). Script: `research/depth/twdb_validate.py` (real `zones.reference_zones_from_shares` / `zones.effective_zones`); data: `data/twdb_validation_rows.csv` (all lake-levels, bands, both sigma modes, all predictors) and `data/twdb_validation_summary.json`. Post-hoc descriptive extras (not preregistered, not graded): `research/depth/twdb_validate_posthoc.py` -> `data/twdb_validation_posthoc.json`. Reference-pool status: `DEPTH_TWDB_REFERENCE_POOL_VERIFICATION.md`. No threshold, level or lake was changed after results.

## 1. Verdict against the frozen thresholds

Graded set: 5 VERIFIED lakes x 5 drawdowns (d = 1.5, 3, 4.5, 6, 8 ft below the survey reference pool) = 25 lake-levels on S1; 4 lakes (20 lake-levels) on S2. Texoma is UNVERIFIED and excluded.

| Threshold (dry share, production sigma) | S1 table-derived shares (n=25) | S2 contour-raster shares (n=20) |
|---|---|---|
| T1 MAE <= 0.03 | 0.0082 PASS | 0.0159 PASS |
| T2 max abs error <= 0.06 | 0.0242 PASS | 0.0328 PASS |
| T3 bounds coverage >= 0.80 | 1.00 PASS | 1.00 PASS |
| T4 median bounds width <= 0.15 | 0.113 PASS (p90 0.180) | 0.117 PASS (p90 0.199) |
| T5 pooled Spearman >= 0.95 | 0.983 PASS | 0.979 PASS |
| Signed bias (reported) | +0.0006 | +0.0124 |

Per lake (own MAE / max error / coverage / median width): Cedar Creek 0.0077 / 0.014 / 1.0 / 0.130 (S2 0.0203 / 0.030 / 1.0 / 0.127); Conroe 0.0068 / 0.017 / 1.0 / 0.121 (S2 0.0176 / 0.033 / 1.0 / 0.115); Fork 0.0107 / 0.021 / 1.0 / 0.101 (S2 0.0144 / 0.027 / 1.0 / 0.119); Livingston 0.0064 / 0.014 / 1.0 / 0.094 (no S2); Tawakoni 0.0092 / 0.024 / 1.0 / 0.113 (S2 0.0113 / 0.030 / 1.0 / 0.113). All pass T1-T4 on every available predictor, so `validation.passed = true` for Cedar Creek, Conroe, Fork, Livingston and Tawakoni (Livingston on S1 only). Texoma: `null` (unverified).

## 2. Dry-share table (production sigma; truth from the elevation-area table)

| Lake | d (ft) | truth dry | S1 bounds (lo-hi) | S1 err | S1 in | S2 bounds (lo-hi) | S2 err | S2 in |
|---|---|---|---|---|---|---|---|---|
| Cedar Creek Reservoir | 1.5 | 0.036 | 0.0-0.077 | +0.003 | Y | 0.0-0.098 | +0.013 | Y |
| Cedar Creek Reservoir | 3.0 | 0.077 | 0.0-0.182 | +0.014 | Y | 0.0-0.199 | +0.023 | Y |
| Cedar Creek Reservoir | 4.5 | 0.124 | 0.077-0.182 | +0.006 | Y | 0.098-0.199 | +0.025 | Y |
| Cedar Creek Reservoir | 6.0 | 0.182 | 0.077-0.312 | +0.012 | Y | 0.098-0.326 | +0.030 | Y |
| Cedar Creek Reservoir | 8.0 | 0.251 | 0.182-0.312 | -0.004 | Y | 0.199-0.326 | +0.011 | Y |
| Lake Conroe | 1.5 | 0.041 | 0.0-0.077 | -0.002 | Y | 0.0-0.096 | +0.007 | Y |
| Lake Conroe | 3.0 | 0.077 | 0.0-0.165 | +0.006 | Y | 0.0-0.184 | +0.015 | Y |
| Lake Conroe | 4.5 | 0.117 | 0.077-0.165 | +0.004 | Y | 0.096-0.184 | +0.023 | Y |
| Lake Conroe | 6.0 | 0.165 | 0.077-0.286 | +0.017 | Y | 0.096-0.299 | +0.033 | Y |
| Lake Conroe | 8.0 | 0.231 | 0.165-0.286 | -0.006 | Y | 0.184-0.299 | +0.010 | Y |
| Lake Fork Reservoir | 1.5 | 0.066 | 0.0-0.101 | -0.016 | Y | 0.0-0.119 | -0.007 | Y |
| Lake Fork Reservoir | 3.0 | 0.101 | 0.0-0.161 | -0.021 | Y | 0.0-0.168 | -0.017 | Y |
| Lake Fork Reservoir | 4.5 | 0.130 | 0.101-0.161 | +0.001 | Y | 0.119-0.168 | +0.013 | Y |
| Lake Fork Reservoir | 6.0 | 0.161 | 0.101-0.251 | +0.015 | Y | 0.119-0.257 | +0.027 | Y |
| Lake Fork Reservoir | 8.0 | 0.205 | 0.161-0.251 | +0.001 | Y | 0.168-0.257 | +0.007 | Y |
| Lake Livingston | 1.5 | 0.056 | 0.0-0.094 | -0.009 | Y | n/a | n/a | n/a |
| Lake Livingston | 3.0 | 0.094 | 0.0-0.162 | -0.013 | Y | n/a | n/a | n/a |
| Lake Livingston | 4.5 | 0.135 | 0.094-0.162 | -0.007 | Y | n/a | n/a | n/a |
| Lake Livingston | 6.0 | 0.162 | 0.094-0.236 | +0.003 | Y | n/a | n/a | n/a |
| Lake Livingston | 8.0 | 0.199 | 0.162-0.236 | -0.000 | Y | n/a | n/a | n/a |
| Lake Tawakoni | 1.5 | 0.049 | 0.0-0.078 | -0.009 | Y | 0.0-0.085 | -0.006 | Y |
| Lake Tawakoni | 3.0 | 0.078 | 0.0-0.142 | -0.007 | Y | 0.0-0.147 | -0.005 | Y |
| Lake Tawakoni | 4.5 | 0.105 | 0.078-0.142 | +0.005 | Y | 0.085-0.147 | +0.011 | Y |
| Lake Tawakoni | 6.0 | 0.142 | 0.078-0.255 | +0.024 | Y | 0.085-0.26 | +0.030 | Y |
| Lake Tawakoni | 8.0 | 0.199 | 0.142-0.255 | -0.000 | Y | 0.147-0.26 | +0.005 | Y |

Every truth lies inside the bounds, on both predictors, at all 25 / 20 lake-levels.

## 3. What the pass does and does not mean

1. **S1 is partly circular.** The shares come from the same table as the truth. At d = 3 and 6 with zero uncertainty the bounds are a point equal to the truth (zero-sigma MAE 0.0003 and 0.0002 at those levels). The S1 pass shows the engine arithmetic, bounds and supported-edge handling are correct; it says nothing about the contour product.
2. **S2 is the real accuracy test, and its margin is modest.** Contour-raster shares overstate the shallow share (bias +0.012, up to +0.030 at d = 6). With the exact shift (sigma = 0) S2 bounds cover the truth in only 60% of lake-levels (0% at d = 3 and 6, where the bounds collapse to a point 0.012-0.016 high). Coverage 1.0 in the graded configuration comes from the production-sigma widening (+-0.29-0.31 ft), not from the contour shares being unbiased.
3. **Bounds are broad.** Median width 0.11-0.12 of the reference surface, 0.16-0.18 at d = 3 and 6 (post-hoc by level), because only the 3/6/10 ft cumulative shares are stored and a sigma of 0.3 ft pushes the shifted edge across a stored edge. The bounds are correct, but a width of 0.16-0.18 against a dry share of 0.08-0.18 says little at those drawdowns. The T1 point error is the error of the bounds midpoint, which is a preregistered convenience; the engine reports bounds, not a point.
4. **Skill over a naive guess is thin.** The leave-one-lake-out fleet-mean dry share at the same drawdown has MAE 0.014 on the five lakes (preregistered, informational) and 0.015 on the four S2 lakes (post-hoc subset). S1 (0.008) beats it; S2 (0.016) does not. These reservoirs have similar hypsometry, so a fleet mean already does well; the engine adds a lake-specific, bounded answer and refuses to extrapolate, but no large accuracy gain is shown on this sample.
5. **n is small**: 5 lakes, 25 lake-levels, large Texas water-supply reservoirs of similar shape; the five levels per lake are strongly dependent; and the truth is TIN-model output whose shallow margins are interpolated, not an observation of the lake at a lower pool. Within-level cross-lake rank (n <= 5, reported, not gated): S1 Spearman 0.97 (d 1.5), -0.6 (3.0), 0.7 (4.5), 0.7 (6.0), 1.0 (8.0); S2 0.2, -0.6, 0.8, 1.0, 1.0. Rank across lakes at a fixed drawdown is not reliably recovered; the pooled 0.98 is dominated by d.
6. Nothing here covers post-survey sedimentation (Fork and Tawakoni are 2009 surveys), other lake types, or the dry share of the current lake surface (shares are of the reference-pool surface).

## 4. Secondary bands (reported, not gating; production sigma, S1, VERIFIED lakes)

| Band | MAE | Median width | Reading |
|---|---|---|---|
| under3 (wet, < 3 ft deep now) | 0.078 | 0.177 | informative for d <= 6 (MAE 0.008-0.018, width 0.16-0.18); at d = 8 the needed edge (11 ft) lies beyond the stored 10 ft edge: width 0.84, MAE 0.34 |
| threeToSix | 0.199 | 0.745 | informative only for d <= 3 (width 0.18); wide beyond |
| sixToTen | 0.290 | 0.764 | uninformative at all tested drawdowns (width 0.75-0.84) |
| deeper | 0.254 | 0.745 | uninformative (width 0.75) |

Coverage is 1.0 on all bands only because the bounds are wide. `effective_zones` has no information past the last stored edge (10 ft): a shifted edge beyond it returns [S(10), 1]. The dry share is the one effective-zone quantity informative across the tested drawdowns; `under3` is informative down to about 6 ft of drawdown.

## 5. Informational runs (never graded)

* **Texoma (UNVERIFIED; computed with the verified flag forced on).** Published interval 5 ft, so only the 10 ft edge exists and every bound is [0, 0.238]. It would fail T1 (MAE 0.052) and T4 (width 0.238). Truth at its basis 620.0 ft:

| d (ft) | truth dry | bounds | midpoint err |
|---|---|---|---|
| 1.5 | 0.039 | 0.0-0.238 | +0.080 |
| 3.0 | 0.067 | 0.0-0.238 | +0.052 |
| 4.5 | 0.111 | 0.0-0.238 | +0.008 |
| 6.0 | 0.157 | 0.0-0.238 | -0.038 |
| 8.0 | 0.203 | 0.0-0.238 | -0.084 |

* **Coarse ladders (S3), supported-edge rule.** Zones built from every-5th/10th-foot ladders (intervals 5/10) hold only the 10 ft edge (asserted in the script: a 5 or 10 ft survey does not produce 3/6 ft edges). Dry-share MAE 0.042-0.078 (5 ft ladder) and 0.049-0.072 (10 ft ladder), median widths 0.27-0.37, shares biased high (+0.01 to +0.05), coverage 1.0. The bounds are honest and very wide: the rule prevents false precision at the cost of information.
* **Zero sigma.** S1 MAE 0.0030, coverage 1.0, median width 0.068; S2 MAE 0.0125, coverage 0.60, median width 0.074.

## 6. Recommendation

* Effective zones may be enabled in the shadow Brain for the five VERIFIED, validation-passed lakes: **Cedar Creek, Conroe, Fork, Livingston, Tawakoni**, using `referencePoolFt` and datum from `twdb_reference_pools.json` (Livingston 131.1 ft). Preconditions: the manifest builder must first give these six lakes a contour interval (their `interval_ft` is blank today, so no `referenceZones` exist); the shift must be taken against the survey `referencePoolFt` (matters by 0.1 ft for Livingston); the TWDB "not for fishing maps" clause and the attribution request stay on the output (`DEPTH_LICENSING_MATRIX.md`).
* Scope limits: expose `dry` (and `under3` only for shifts down to about 6 ft below the survey pool); do not present the 3-6, 6-10 and deeper effective bands; present bounds, not midpoints; never present a rising lake's flooded margin.
* **Texoma stays disabled.** Its shares are measured from 620.0 ft, 3 ft above the pool the Brain shifts from; its datum label and quad-derived boundary are unresolved.
* Not shown here: S2-quality accuracy for Livingston (no independent contour shares were available), accuracy for other reservoir types, or any benefit over a fleet-mean guess beyond about 0.01 share.
