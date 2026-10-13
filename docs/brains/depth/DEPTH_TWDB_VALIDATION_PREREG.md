# TWDB Effective-Zone Validation: Preregistration

Status: **FROZEN** before any comparison was computed. Authoritative copy: `jobs/depth-brain/depth_brain/data/proposals/twdb_prereg.json` (written by `research/depth/twdb_prereg_freeze.py`; this page is the readable twin).

| Freeze record | |
|---|---|
| sha256 (canonical JSON without the `freeze` block) | `cac72a99e9f884ffe3993b6630981adf7835dd2387661a9f3908373ff3fdc82c` |
| Frozen at (UTC) | 2026-10-13T20:38:45Z |
| Canonicalisation | `json.dumps(doc_without_freeze, sort_keys=True, separators=(',',':'), ensure_ascii=True)` |
| Enforcement | `research/depth/twdb_validate.py` recomputes the hash and refuses to run on a mismatch |

## 1. Question

Does `zones.reference_zones_from_shares` + `zones.effective_zones` (reference shares of the surveyed surface by depth band at the survey reference pool, shifted by `shift = pool_low - pool_ref`) predict, from the 3/6/10 ft reference shares alone, the share of the reference-pool surface that is dry at a lower pool, and the wet band shares, as measured by the TWDB elevation-area table?

## 2. Truth

TWDB elevation-area table (0.1 ft steps; elevations stored negative, abs taken; linear interpolation). `A_ref = A(basis)`, basis = the table elevation the reference shares are measured from. At `L = basis - d`:
`dry = 1 - A(L)/A_ref`; `under3 = (A(L)-A(L-3))/A_ref`; `threeToSix = (A(L-3)-A(L-6))/A_ref`; `sixToTen = (A(L-6)-A(L-10))/A_ref`; `deeper = A(L-10)/A_ref`.

**Independence caveat (frozen into the design).** The fleet-manifest shares for the TWDB lakes were themselves derived from the same table. A prediction built from those shares (S1) is therefore exact at shifts that land on a supported edge (3 and 6 ft) by construction; S1 checks the engine arithmetic and bounds logic, not the survey. S2, shares from rasterised contours (the research method, independent of the table), is the real accuracy test.

## 3. Reference-pool verification rule (decides who is graded)

VERIFIED only if: (V1) the TWDB report states NGVD29 (or the same gauge/datum system as the Sector level binding); (V2) the basis elevation is within 0.25 ft of TWDB's stated conservation pool; (V3) the Sector directory `fullPoolFt` is within 0.25 ft of the basis and NGVD29; (V4) the contours/table are elevations. Otherwise UNVERIFIED. Declared before results: Cedar Creek, Conroe, Fork, Livingston, Tawakoni VERIFIED; Texoma UNVERIFIED (basis 620.0 ft is the 2002 quad-derived model boundary, 3.0 ft above conservation pool 617.0 ft; report gives elevations only as "ft above msl" at the USACE gauge). UNVERIFIED lakes never enter pass/fail.

## 4. Design

* Levels: drawdown below basis d = **1.5, 3.0, 4.5, 6.0, 8.0 ft** for every lake (3.0 and 6.0 sit on supported edges; 1.5, 4.5, 8.0 require bounds). All tables span >= 60 ft.
* Sigma passed to `effective_zones` (graded): production sigma = sqrt(0.25^2 + sigma_level^2 + 0.1^2) (pool "high" 0.25; level 0.1 for operator pool, 0.15 for lake gauge). Informational: sigma = 0.
* Interval: the survey contour product's published interval (Cedar 1, Conroe 1, Fork 2, Livingston 1, Tawakoni 1, Texoma 5 ft), so supported-edge rules apply (Texoma, 5 ft, may only hold the 10 ft edge).
* Predictors: **S1** table-derived shares (graded); **S2** contour-raster shares `native_s3/6/10` from `contour_method_check_twdb.csv` (graded, independent; Cedar, Conroe, Fork, Tawakoni); **S3** every-5th/10th-foot ladders (`d5_*`, `d10_*`, informational, tests the supported-edge rule); baseline = leave-one-lake-out mean dry share at the same d (informational).

## 5. Metrics and thresholds (frozen)

Primary quantity: dry share; point estimate = midpoint of the engine's (lo, hi).

| ID | Metric | Pass |
|---|---|---|
| T1 | MAE of dry share | <= 0.03 |
| T2 | max abs error | <= 0.06 |
| T3 | bounds coverage (truth within lo-0.0005 .. hi+0.0005) | >= 0.80 |
| T4 | median bounds width (hi - lo) | <= 0.15 |
| T5 | pooled Spearman, midpoint vs truth | >= 0.95 |

Per-lake pass: own MAE <= T1, max <= T2, coverage >= T3, median width <= T4 (T5 pooled only). `validation.passed` is true only if the lake passes S1 and, where it exists, S2; false otherwise; null if UNVERIFIED. Within-level cross-lake Spearman (n <= 5), band shares (under3, threeToSix, sixToTen, deeper), signed bias and the wet share (same error as dry) are reported but do not gate.

Enable rule: effective zones should be enabled for a lake only if it is VERIFIED and `passed` is true. A lake that is accurate and covered but fails the width threshold is reported as "accurate, bounds too wide" and is not recommended by this study.

## 6. Analysis rules and disclosure

Nothing above changes after results. Every graded lake-level is reported, failures included. Disclosure: before freezing the author had read the reference shares, the research method-check biases (native contour shares exceed table shares by about +0.005 to +0.021 at 3 ft), and the TWDB reports, and had reasoned that production-sigma bounds are probably wide at d = 3 and 6; no prediction-vs-truth comparison at a lowered pool had been computed.

Known caveats: shares are of the reference-pool surface (not the lake at the lowered level); the table is a TIN model with interpolated/extrapolated shallow margins and pool boundaries digitised at water surfaces that differ from the stated pool (Fork 402.26 ft, Tawakoni 436.77 ft, Conroe 201.18 ft), so truth is modelled, not an independent observation; post-survey sedimentation is not modelled.
