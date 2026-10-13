# Depth Validation Plan (effective depth)

Separate: **model/science validation** (`/validation/depth`, currently `NOT_VALIDATED`) vs lake readiness vs runtime health.

## 1. What is validated today (research branch `docs/depth-brain-research`)

| Claim | Evidence | Result | Limit |
|---|---|---|---|
| shift arithmetic and sign | unit tests (80+) incl. positive/negative, stale, missing, datum, uncertainty | pass | arithmetic only |
| shift equals Lake Brain's own difference at the same reference | live read 2026-10-13: Guntersville -1.4 ft, Hartwell -10.63 ft (Lake Brain) vs Depth dry run | agrees by construction | not independent |
| pool figure quality | 149 high-confidence lakes: robust SD of (p95 level - fullPool) = 1.16 ft | sigmaPool 0.25 ft is optimistic for the *p95 comparison*; it is the uncertainty of the reference *figure*, and 1.16 ft is the upper bound | assumed, flagged |
| acres per foot (supporting prior) | 3DEP slope vs CWMS stage-area, n=33 | Spearman 0.77; 85% within x2 | TWDB 63 lakes: 0.44; do not use for flats |
| contour -> shares method | 18 Texas lakes, TWDB area-capacity | MAE 0.010-0.013 (1-2 ft contours), 0.015-0.026 (5 ft), 0.020-0.070 (10 ft) | one regional family |
| Landsat drawdown exposure | 5 Texas lakes, level range 8-25 ft | Spearman 0.87-0.93 vs contour depth; MAE 0.4-1.4 ft | lake-wide shares biased low; not a product |
| worked effective-depth example | Fork (TWDB bathymetry): 475 ac of 3.5-4.5 ft water all dry at the 7.7 ft low | consistent | one lake |

## 2. Gates before any promotion (proposed)

1. **Datum audit complete** for every provider feeding a published shift (`DEPTH_DATUM_AUDIT.md`), conversions verified in both directions before enabling `CONVERTED`.
2. **Field validation** on 5-10 lakes (`DEPTH_FIELD_VALIDATION_PLAN.md`): shift-vs-observed MAE <= 0.5 ft; no dry-called-ideal.
3. **Independent event check**: at an extreme level (Hartwell/TVA winter pool), compare predicted exposed margin with a satellite water mask (Landsat/Sentinel) - only where the methodology holds (reservoirs with exposed bare shore; not vegetation-covered margins).
4. **Calibration of sigma**: 68% of field/event residuals within 1 sigma; replace assumed components with measured ones.
5. **Pre-registration**: freeze thresholds before reading held-out lakes; hold out by state/operator.
6. **Zone gate**: effective zones only for surveys with a verified reference pool/datum, validated against area-capacity tables at a second pool level (TWDB tables give it).

## 3. Independent validation resources identified

* TWDB area-capacity tables (63 reservoirs) - exact share within 3/6/10 ft at conservation pool and at lower pools via the elevation-area table.
* USACE CWMS stage-storage (33) - area gained per foot.
* Operator drawdown events (TVA winter pool 5-15 ft; Hartwell 2007-08, 2012, 2016-17 droughts).
* Landsat/Sentinel scenes at extreme levels (Planetary Computer STAC, no key needed).
* IENC 9 ft contour (34 lakes' footprints) as a binary threshold check at reference pool.
