#!/usr/bin/env python3
"""Depth Brain / TWDB effective-zone validation: write the PREREGISTRATION (frozen before any comparison is computed) and hash it.
Output: jobs/depth-brain/depth_brain/data/proposals/twdb_prereg.json  (authoritative).  The sha256 covers the canonical JSON of the
document WITHOUT the 'freeze' block: json.dumps(doc_without_freeze, sort_keys=True, separators=(',',':'), ensure_ascii=True).
No result of the validation was computed before this file was written. Refuses to overwrite an existing frozen file."""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "jobs/depth-brain/depth_brain/data/proposals/twdb_prereg.json"
RAW = "/Users/mcather/Desktop/Development/Sector_Research_Data/depth-brain/terrain/twdb"

doc = {
    "schema": "depth-twdb-prereg-v1",
    "title": "TWDB effective-zone validation: preregistration",
    "purpose": "Test whether Depth's effective-zone arithmetic (zones.reference_zones_from_shares + zones.effective_zones), fed with reference shares of the surveyed surface by depth band at the survey reference pool, predicts the share of the REFERENCE-pool surface that is dry (and the band shares of the wet part) at lower pool elevations, against the TWDB elevation-area (area-capacity) table.",
    "truth": {
        "source": "TWDB volumetric-survey elevation-area table (0.1 ft steps), table.txt per lake under " + RAW + "/<key>/table.txt; elevations are stored with a negative sign, use abs().",
        "interpolation": "linear in elevation (numpy.interp); area below the table bottom is 0",
        "reference": "A_ref = A(basis) where basis is the table elevation the reference shares are measured from (the research pool_ft in terrain/twdb_truth.json = the elevation whose table area equals the survey pool polygon area).",
        "formulas": {
            "dryShare(d)": "1 - A(basis-d)/A_ref",
            "wetShare(d)": "A(basis-d)/A_ref",
            "under3(d)": "(A(L)-A(L-3))/A_ref with L = basis-d",
            "threeToSix(d)": "(A(L-3)-A(L-6))/A_ref",
            "sixToTen(d)": "(A(L-6)-A(L-10))/A_ref",
            "deeper(d)": "A(L-10)/A_ref"},
        "independenceCaveat": "The fleet-manifest shares for the six TWDB lakes (contour_truth_lakes.csv, method area_capacity_table) are computed from the SAME table that supplies the truth, so predictor S1 is exact at shifts that fall on a supported edge by construction (it then checks the engine arithmetic and bounds logic, not the survey). Predictor S2 (contours rasterised by the research method) is independent of the table and is the real accuracy test."},
    "referenceVerification": {
        "rule": "A lake is VERIFIED only if all hold: (V1) the TWDB report states the vertical datum as NGVD29 (or states the elevations are those of the same gauge/datum system the Sector level binding uses); (V2) the basis elevation of the reference shares is within 0.25 ft of TWDB's stated conservation pool (0.25 ft = contract SIGMA_POOL['high']); (V3) the Sector directory fullPoolFt (candidates.json reference.poolFt) is within 0.25 ft of the basis elevation and its datum is NGVD29; (V4) the survey contours / table are ELEVATIONS (so shift = level - referencePool applies). Otherwise UNVERIFIED.",
        "declaredOutcomeBeforeResults": {
            "Cedar Creek Reservoir|TX": "VERIFIED", "Lake Conroe|TX": "VERIFIED", "Lake Fork Reservoir|TX": "VERIFIED",
            "Lake Livingston|TX": "VERIFIED", "Lake Tawakoni|TX": "VERIFIED", "Lake Texoma|TX": "UNVERIFIED"},
        "declaredReasonTexoma": "Basis elevation 620.0 ft (the 2002 model boundary taken from the USGS quad 620 ft contour) is 3.0 ft above the conservation pool 617.0 ft and the Sector directory pool 617; the report states elevations only as 'ft above msl' at the USACE Denison Dam gauge (no NGVD29 label).",
        "excludedFromPassFail": "UNVERIFIED lakes are computed for information only and never enter any pass/fail statistic."},
    "lakes": {
        "Cedar Creek Reservoir|TX": {"key": "CedarCreek_2017-10", "basisFt": 322.0, "publishedContourIntervalFt": 1.0, "levelCapability": "DIRECT_OPERATOR_POOL", "datumSigmaFt": 0.1},
        "Lake Conroe|TX": {"key": "conroe_2020-10", "basisFt": 201.0, "publishedContourIntervalFt": 1.0, "levelCapability": "DIRECT_LAKE_GAUGE", "datumSigmaFt": 0.1},
        "Lake Fork Reservoir|TX": {"key": "Fork_2009-10", "basisFt": 403.0, "publishedContourIntervalFt": 2.0, "levelCapability": "DIRECT_LAKE_GAUGE", "datumSigmaFt": 0.1},
        "Lake Livingston|TX": {"key": "Livingston_2019-11", "basisFt": 131.1, "publishedContourIntervalFt": 1.0, "levelCapability": "DIRECT_LAKE_GAUGE", "datumSigmaFt": 0.1},
        "Lake Tawakoni|TX": {"key": "tawakoni_2009-08", "basisFt": 437.5, "publishedContourIntervalFt": 1.0, "levelCapability": "DIRECT_LAKE_GAUGE", "datumSigmaFt": 0.1},
        "Lake Texoma|TX": {"key": "Texoma_2002-07", "basisFt": 620.0, "publishedContourIntervalFt": 5.0, "levelCapability": "DIRECT_OPERATOR_POOL", "datumSigmaFt": 0.1}},
    "levels": {
        "drawdownBelowBasisFt": [1.5, 3.0, 4.5, 6.0, 8.0],
        "rule": "pool_low = basis - d for each d; shift passed to effective_zones = -d. 3.0 and 6.0 fall exactly on supported edges, 1.5/4.5/8.0 fall between them (bounds required). All lakes' tables span at least 60 ft below basis, so every level is inside every table.",
        "note": "Chosen before any result; the conservation-pool level (d = 0) is trivially dry = 0 and is not scored."},
    "sigma": {
        "graded": "production sigma = sqrt(sigma_pool^2 + sigma_level^2 + sigma_datum^2) with sigma_pool = 0.25 (contract SIGMA_POOL high), sigma_level by levelCapability (contract SIGMA_LEVEL), sigma_datum from the manifest (0.1, SAME_DATUM). This is what the shipped state would pass to effective_zones.",
        "informational": "sigma = 0 (pure arithmetic, exact shift)"},
    "predictors": {
        "S1": {"role": "GRADED (engine arithmetic / shipped configuration)", "shares": "cumulative shares at edges 3, 6, 10 from the TWDB table at basis: S(x) = (A(basis)-A(basis-x))/A(basis)", "interval": "publishedContourIntervalFt", "build": "zones.reference_zones_from_shares(shares, interval, coverage=1.0, tier='A', source='TWDB', reference_verified=True)"},
        "S2": {"role": "GRADED (independent of the table), only for lakes with data", "shares": "native contour-raster shares native_s3/native_s6/native_s10 from docs/research/depth-brain/data/contour_method_check_twdb.csv (research method: contour_grid on the 1/2 ft TWDB contour shapefile, depth = basis - contour elevation)", "interval": "publishedContourIntervalFt", "available": "Cedar Creek, Conroe, Fork, Tawakoni (Livingston and Texoma are not in that file; not recomputed here)"},
        "S3": {"role": "INFORMATIONAL (supported-edge rule on coarse ladders)", "shares": "d5_* (every 5th foot, interval 5) and d10_* (every 10th foot, interval 10) shares from the same csv, where present", "check": "zones.supported_edges(5) == [10.0] and zones.supported_edges(10) == [10.0]; the built zones must hold only the 10 ft edge"},
        "baseline": {"role": "INFORMATIONAL context", "definition": "leave-one-lake-out mean dry share at the same d over the other graded lakes (truth values), to show how much the engine adds over a fleet-average guess"}},
    "metrics": {
        "primaryQuantity": "dry share of the reference-pool surface at each level (effective_zones()['shares']['dry'], point estimate = midpoint of (lo,hi))",
        "M1_MAE": "mean |midpoint - truth| over graded lake-levels",
        "M2_maxAbsError": "max |midpoint - truth|",
        "M3_boundsCoverage": "fraction of graded lake-levels with lo - 0.0005 <= truth <= hi + 0.0005 (0.0005 = half the 3-decimal rounding applied by effective_zones)",
        "M4_boundsWidth": "median and 90th percentile of (hi - lo)",
        "M5_rank": "Spearman correlation of midpoint vs truth: pooled over all graded lake-levels (dominated by d) and, per level, across lakes (reported only; n <= 5)",
        "secondaryBands": "the same M1 and M3 for under3, threeToSix, sixToTen, deeper (reported, not gating)",
        "wetArea": "wetShare = 1 - dryShare has the identical absolute error and bounds (hi/lo swapped); reported once",
        "signedBias": "mean (midpoint - truth), reported"},
    "thresholds": {
        "T1_MAE_max": 0.03, "T2_maxAbsError_max": 0.06, "T3_boundsCoverage_min": 0.80, "T4_medianBoundsWidth_max": 0.15, "T5_pooledSpearman_min": 0.95,
        "perLakePass": "a lake passes a predictor if its own MAE <= T1, its own max error <= T2, its own coverage >= T3 and its own median width <= T4 (T5 is pooled only). A lake's validation.passed is true only if it passes S1 and, where S2 exists, S2; false if it fails either; null if UNVERIFIED.",
        "pooledPass": "pooled over VERIFIED lakes on S1: T1..T5 all met; separately on S2 over the lakes where it exists.",
        "frozen": True},
    "enableRecommendationRule": "effectiveZones should be enabled for a lake only if it is VERIFIED and its validation.passed is true. A pass on S1 alone with S2 missing is stated as such. A lake that is accurate and covered but fails the width threshold is reported as 'accurate, bounds too wide'; it is NOT recommended for enabling by this study.",
    "analysisRules": [
        "Thresholds, levels, lakes, predictors and metrics above are frozen; nothing is changed after results are seen.",
        "Every graded lake-level is reported, including failures; no lake-level is dropped after the fact.",
        "UNVERIFIED lakes are reported for information only.",
        "The computation script (research/depth/twdb_validate.py) verifies this file's hash before computing and refuses to run on a mismatch."],
    "disclosure": "Before freezing, the author had read: the fleet reference shares and the research method-check biases for these lakes (native contour shares exceed table shares by about +0.005 to +0.021 at 3 ft), the TWDB reports (datum, conservation pool, survey dates, boundary elevations), and had reasoned that wide production-sigma bounds are likely at d = 3.0 and 6.0. No effective-zone prediction or comparison against the table at a lowered pool had been computed.",
    "knownCaveats": [
        "Shares are of the surveyed surface at the reference pool, not of the lake at the lowered level; the dry share is the share of the reference-pool surface that is exposed.",
        "The table is a TIN model: shallow margins are interpolated or extrapolated between 500 ft survey lines, and the pool boundary was digitised from imagery at a water surface that can differ from the stated pool (Fork 402.26 ft, Tawakoni 436.77 ft, Conroe 201.18 ft). The truth is therefore a modelled quantity, not an independent observation of the lake at another level.",
        "Sedimentation after the survey year is not modelled."]}

canon = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
h = hashlib.sha256(canon.encode("utf-8")).hexdigest()
if OUT.exists():
    print("REFUSING: prereg already exists:", OUT); sys.exit(1)
ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
doc["freeze"] = {"algorithm": "sha256 of json.dumps(doc without 'freeze', sort_keys=True, separators=(',',':'), ensure_ascii=True)", "sha256": h, "frozenAtUtc": ts}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(doc, indent=1, sort_keys=False) + "\n")
print(h, ts)
