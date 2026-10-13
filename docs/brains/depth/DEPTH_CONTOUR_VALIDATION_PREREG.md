# Contour Effective-Zone Validation vs CWMS Stage-Area Curves: Preregistration

Status: **FROZEN** before any share-vs-curve comparison was computed. Authoritative copy: `jobs/depth-brain/depth_brain/data/proposals/contour_prereg.json` (written by `research/depth/contour2_prereg_freeze.py`); this page is the readable twin.

| Freeze record | |
|---|---|
| sha256 (canonical JSON without the `freeze` block) | `04d16d491fa860407800f4c8c1d1bc526e4393880f4983a428f858e49212ba65` |
| Frozen at (UTC) | 2026-10-13T21:23:13Z |
| Canonicalisation | `json.dumps(doc_without_freeze, sort_keys=True, separators=(',',':'), ensure_ascii=True)` |
| Enforcement | `research/depth/contour2_validate.py` recomputes this hash and the sha256 of `docs/brains/depth/data/contour2_lake_facts.json` and `contour2_curves.csv` (bound inside the prereg) and refuses to run on any mismatch |

Design reuse: TWDB's preregistration (`DEPTH_TWDB_VALIDATION_PREREG.md`): levels, sigma, midpoint-of-bounds metric, thresholds T1-T5. Design changes, with reasons:

1. **Truth is a CWMS stage-area curve** (Elev;Area, or Stage;Area + gauge zero for the Mississippi Headwaters lakes), not a survey table. Version nearest the contour survey year.
2. **Predictor is only the manifest contour shares (C1)**; there is no table-derived predictor, so the study has no circular arm (TWDB's S1 was circular).
3. **T6 added** (publish rate >= 0.60 and >= 3 published levels): most of these lakes have 5 or 10 ft contour intervals, where the engine withholds the dry bound (wider than 0.25). TWDB never faced this. Accuracy metrics use published levels; T6 gates usefulness.
4. **Reference-pool rule R1-R4** replaces TWDB V1-V4 (no survey report exists for these sources): a stated numeric pool (report, map or per-contour Elevation attribute, constant within the lake), within 0.25 ft of the directory pool with no rounding allowance, directory datum NGVD29/NAVD88, documentation not self-contradictory. Status is a deterministic function of the frozen facts, computed inside the freeze script.
5. **Graded vs informational:** graded = VERIFIED lakes with a curve (Alum Creek, Tappan, Fort Gibson, Sardis). Everything else with a curve (20 lakes) is run under an assumed pool for information only and can never pass. Diagnostics D1 (share check at the pool) and D2 (implied pool grid) are informational and never change a status or threshold.

Levels: drawdown below the pool d = 1.5, 3, 4.5, 6, 8 ft (included only where the curve reaches the level). Sigma (graded): sqrt(0.25^2 + 0.1^2 + 0.1^2) = 0.287 ft; sigma 0 informational.

Thresholds (frozen): T1 MAE <= 0.03; T2 max abs error <= 0.06; T3 coverage >= 0.80; T4 median bounds width <= 0.15; T5 pooled Spearman >= 0.95; T6 publish rate >= 0.60 and at least 3 published levels. Per-lake `validation.passed` is true only for a VERIFIED lake with a curve meeting T1-T4 and T6; false if it fails; null if UNVERIFIED or no curve.

Declared status (function of the rule): VERIFIED = Alum Creek, Caesar Creek, Tappan, Fort Gibson, Sardis; the other 89 UNVERIFIED. Caesar Creek has no Elev;Area curve (CWMS has only Elev;Stor for it) so it is VERIFIED but not validated.

Disclosure: before freezing the author had read the manifest shares and intervals, the source pool statements (ODNR PDFs, KARS, NE/ND/OK attributes) and their comparison with directory pools, and the CWMS rating endpoints (elevation range, datum, versions). The 0.25 ft tolerance was deliberately kept without a rounding allowance (which would have promoted Mosquito Creek and Grand Lake St. Marys). No A(pool), share-vs-curve difference or effective-zone prediction had been computed.

Known caveats: curves may predate the surveys; Stage curves assume stage zero = CWMS location elevation; NWDM templates have datum "OTHER"; shares are of the surveyed surface, curves of the whole lake; possible shared lineage between a Corps curve and a contour survey was not checked.
