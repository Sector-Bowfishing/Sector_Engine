# Authoritative Contour Integration Path (Phases 10-12)

Status: **path defined and partly exercised; no contour geometry enters the Brain.** The manifest carries derived shares only, and `effectiveZones` stay withheld until a survey's reference pool is verified.

## 1. What the evidence is (recomputed from the research artifacts, 2026-10-13)

Fleet matrix (621): research tiers A 77, B 26, B-partial 35, B-binary 28, C 28 (hypsometry only), D 371, U 56. Depth Brain tiers: A 77, B 26, C 91 (= B-partial 35 + B-binary 28 + hypsometry 28), D 371, UNKNOWN 56. **B-partial and B-binary are never promoted to full bathymetry** (tested: `test_partial_binary_and_hypsometry_are_never_promoted_to_ab`). `C` hypsometry lakes carry `evidence.kind = unknown` and `hypsometryOnly: true`: they say nothing about depth.

Of the 103 tier A/B lakes: 59 have contour terms that permit customer-facing derived numbers; 44 are internal-only/unclear/restricted (`DEPTH_LICENSING_MATRIX.md`). Florida FWC data is INTERNAL_ONLY (purpose-limited terms; its 8 lakes are all in the blocked set). The shadow Brain is internal, so all 103 may be computed; the licence field gates any later customer use.

## 2. Meaning of each contour tier

| Depth tier | Evidence | May produce |
|---|---|---|
| A | whole-lake contours at <= 3 ft interval (or 5 ft on lakes >= 25 ft deep) / survey tables; verified spatial match | band shares at supported edges; effective zones once reference verified |
| B | 10 ft interval on lakes >= 40 ft deep, or 65-85% coverage; verified spatial match | band shares at supported edges only (10 ft split for 5-10 ft intervals) |
| C | partial coverage, > 10 ft interval, datum doubts, the single IENC 9 ft contour (reference = local low water, no encoded pool), stage-area hypsometry | shift only; no zones |
| D / UNKNOWN | none | shift only, or unavailable |

## 3. Derived zones (Phase 10-11): what contours support

`zones.supported_edges(interval)`: an edge (3, 6, 10 ft) is published only if it is a multiple of the contour interval, or the interval is <= 3 ft (research interpolation RMS: 0.28 ft at 1-2 ft, 1.3 ft at 5 ft, 2.8 ft at 10 ft). So:

| Interval | Published | Withheld |
|---|---|---|
| 1-3 ft | shareUnder3/6/10, share3To6, share6To10, shareDeeper | - |
| 5 ft | shareUnder10Ft, shareDeeper | under3, 3to6, under6 |
| 10 ft | shareUnder10Ft, shareDeeper | all finer edges |

Each carries `support{contourIntervalFt, coverage, surveyYear}`, `coverage.knownAreaShare/unknownAreaShare`, tier and source. Research method accuracy against exact TWDB area-capacity tables: MAE 0.010-0.013 (1-2 ft contours), 0.015-0.026 (5 ft), 0.020-0.070 (10 ft; overstates shallow share). Shares are of the **surveyed** surface at the **survey reference pool**.

Currently 94 lakes carry reference shares in the manifest (tier A/B with a monotone, supported-edge share set).

## 4. Effective zones (Phase 12): the gate

`effectiveZones` re-bins reference shares for the current shift as (lo, hi) bounds (a shifted edge between supported levels is a bound; the shift uncertainty widens it). It is computed **only when**:

1. the survey's reference pool elevation and vertical datum are known and are the same system as the Depth reference (`referenceStatus: VERIFIED`);
2. the shift is defended (datum relationship usable, sigma acceptable);
3. coverage is declared (unsurveyed water stays `unknownAreaShare`).

Today **no lake satisfies (1)**: the research contour tables do not record the survey pool elevation (depths are stored positive-down below the water surface at survey). 94 lakes therefore show reference shares and `effectiveZones.available = false (SURVEY_REFERENCE_POOL_UNVERIFIED)`. Rising lakes flag `floodedMarginUnquantified`.

## 5. To verify a survey reference pool (per source, in this order)

1. **TWDB (6 fleet lakes + 63 area-capacity tables)**: the volumetric survey report states the survey date, the conservation pool elevation (NGVD29) and the water surface at survey. Contours are elevation contours; the elevation-area table gives the exact share at any pool, so effective zones can be validated at a second pool level (the validation gate in `DEPTH_VALIDATION_PLAN.md`). Highest-value first step.
2. **MN DNR / OH / NE / WV / MA / CT / NH**: find the survey date and the water elevation at survey (state lake pages, survey sheets) and the operator's level on that date from Lake Brain history / USGS; record `referencePoolFt` + datum.
3. **Others**: leave unverified.

Each verified lake gets `referenceZones.referenceStatus = VERIFIED`, `referencePoolFt`, datum, evidence; no code change.

## 6. Pipeline to production-quality static builder (not built here)

The research scripts (`research/depth-brain/contour_ingest.py`, `contour_match.py`, `contour_normalize_merge.py`, `contour_truth.py`, `contour_grid.py` on `docs/depth-brain-research`) already ingest 20 sources, require **verified spatial matches** (name-only matches are excluded: 59 pairs), normalize units/sign/datum, and derive shares. Productionising means: idempotent per-source job, versioned output (`candidates.json` section), per-source licence stamp, survey-year capture, and a review queue for `manualReviewNeeded`. Raw contour geometry stays outside Git and outside RTDB.
