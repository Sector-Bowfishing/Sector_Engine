#!/usr/bin/env python3
"""Depth Brain / contour effective-zone validation against stage-area (elevation-area) curves: write the PREREGISTRATION and hash it.
Input facts (already collected, no comparison computed): docs/brains/depth/data/contour2_lake_facts.json and contour2_curves.csv (their sha256 are frozen in).
Output: jobs/depth-brain/depth_brain/data/proposals/contour_prereg.json (authoritative). sha256 covers json.dumps(doc without 'freeze', sort_keys=True,
separators=(',',':'), ensure_ascii=True). Reference-pool status of every lake is a deterministic function of the frozen rule and the frozen facts and is computed here.
Refuses to overwrite an existing frozen file."""
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "jobs/depth-brain/depth_brain/data/proposals/contour_prereg.json"
DD = REPO / "docs/brains/depth/data"
facts_p, curves_p = DD / "contour2_lake_facts.json", DD / "contour2_curves.csv"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
facts = json.load(open(facts_p))["lakes"]

TOL = 0.25            # ft; = contract SIGMA_POOL['high']
KNOWN_DATUMS = ("NGVD29", "NAVD88")


def status(f):
    """Frozen rule. Returns (status, [reasons / missing evidence])."""
    ps = f.get("pSrc"); why = []
    if not ps:
        return "UNVERIFIED", ["R1: no source statement of the reference water-surface elevation (contours are depth below 'the water surface at survey' with no stated level)"]
    ok = True
    if ps["kind"] == "documented_pool_contradictory":
        ok = False; why.append("R4: the source's own texts contradict each other (normal operating pool vs operating level at the time of survey)")
    if ps["kind"] == "attribute_pool_semantics_unstated":
        ok = False; why.append("R1: attribute pool exists but the source does not say the contours are measured from it")
    if ps.get("internalRange") is not None and ps["internalRange"] > 0.5:
        ok = False; why.append("R1: implied pool (elevation + depth) is not constant within the lake (range %.2f ft)" % ps["internalRange"])
    dp = f.get("dirPoolFt")
    if dp is None:
        ok = False; why.append("R2: directory has no pool elevation")
    elif abs(ps["poolFt"] - dp) > TOL + 1e-9:
        ok = False; why.append("R2: source pool %.2f ft differs from directory pool %.2f ft by %.2f ft (> %.2f)" % (ps["poolFt"], dp, abs(ps["poolFt"] - dp), TOL))
    dd = f.get("dirDatum")
    if dd not in KNOWN_DATUMS:
        ok = False; why.append("R3: directory pool datum is %s (not NGVD29/NAVD88): vertical datum of the pool figure is not established" % dd)
    sd = ps.get("datumStated")
    if sd and sd in KNOWN_DATUMS and dd in KNOWN_DATUMS and sd != dd:
        ok = False; why.append("R3: source datum %s differs from directory datum %s" % (sd, dd))
    if ok:
        why.append("pool %.2f ft stated by the source equals directory pool %.2f ft (<= %.2f) in %s" % (ps["poolFt"], dp, TOL, dd))
    return ("VERIFIED" if ok else "UNVERIFIED"), why


roster = {}
for lid, f in sorted(facts.items()):
    st, why = status(f)
    ps = f.get("pSrc")
    use_src = bool(ps) and (ps.get("internalRange") is None or ps["internalRange"] <= 0.5)
    pref = ps["poolFt"] if use_src else f.get("dirPoolFt")
    roster[lid] = dict(source=f["src"], intervalFt=f["intervalFt"], referenceStatus=st, statusReasons=why, pRefFt=pref,
                       pRefOrigin=("source-stated/implied pool" if use_src else "directory fullPoolFt"), hasCurve=("curve" in f),
                       group=("GRADED" if st == "VERIFIED" and "curve" in f else ("INFORMATIONAL_ASSUMED_POOL" if "curve" in f and pref is not None else "NO_CURVE")))

doc = {
    "schema": "depth-contour-prereg-v1",
    "title": "Contour (non-TWDB) effective-zone validation against USACE CWMS stage-area curves: preregistration",
    "purpose": "Test whether zones.reference_zones_from_shares + zones.effective_zones, fed with the manifest reference shares of the surveyed surface by depth band (candidates.json referenceZones, from rasterised state/agency contour products) predicts the share of the reference-pool surface that is dry at lower pools, against the exact stage-area (elevation-area) curve published in USACE CWMS. Also decide which sources/lakes have a documented survey reference pool (VERIFIED) for the effective-zone gate.",
    "dataBinding": {"factsFile": "docs/brains/depth/data/contour2_lake_facts.json", "factsSha256": sha(facts_p), "curvesFile": "docs/brains/depth/data/contour2_curves.csv", "curvesSha256": sha(curves_p),
                    "note": "Facts were collected before this file was frozen; no share-vs-curve comparison existed."},
    "truth": {
        "source": "USACE CWMS Data API (https://cwms-data.usace.army.mil/cwms-data/ratings/<id>?office=<office>), Elev;Area (ft;acre) or Stage;Area ratings, fetched 2026-10-13; points in contour2_curves.csv. Stage curves (MVP Gull/Leech/Winnibigoshish): elevation = stage + CWMS location 'elevation' (gauge zero; 1100.0, 1200.0, 1200.0 ft NGVD29), an ASSUMPTION flagged on those lakes.",
        "versionChoice": "if a rating has several effective-date versions: the version whose effective year is nearest to the contour survey year (ties: later); latest when the survey year is unknown",
        "interpolation": "linear in elevation; below the curve's lowest elevation the area is 0 only if the first point's area is 0, otherwise UNDEFINED and that lake-level (or band) is excluded; above the highest elevation excluded",
        "formulas": {"A_ref": "A(pRef)", "dryShare(d)": "1 - A(pRef-d)/A_ref", "under3(d)": "(A(L)-A(L-3))/A_ref, L=pRef-d", "threeToSix(d)": "(A(L-3)-A(L-6))/A_ref",
                     "sixToTen(d)": "(A(L-6)-A(L-10))/A_ref", "deeper(d)": "A(L-10)/A_ref"},
        "independence": "The predictor shares come from contour products (sonar/map surveys); the truth is an operator curve (design-era or sediment-resurvey tables). They are independent products, unlike the TWDB S1 predictor, BUT lineage can overlap (e.g. a Corps curve may derive from the same survey) and the curve may predate or postdate the contour survey (sedimentation); curve effective dates and survey years are reported per lake. This is the only test; there is no circular predictor in this study."},
    "referenceVerification": {
        "rule": "A lake is VERIFIED only if ALL hold. R1: a source statement (dataset metadata, the agency's per-lake map/sheet, or a per-contour Elevation attribute that equals pool - depth with range <= 0.5 ft inside the lake) says the contour depths are measured from a stated numeric water-surface ELEVATION (pool). R2: that elevation is within 0.25 ft (contract SIGMA_POOL['high']) of the Sector directory fullPoolFt (no rounding allowance). R3: the directory pool datum is NGVD29 or NAVD88 (recorded, not LOCAL/None) and any datum the source itself states is the same. R4: the source's documentation is not self-contradictory. Otherwise UNVERIFIED, with the missing evidence listed. 'Contours are depth at the date of survey' with no water level is UNVERIFIED.",
        "statusIsFunctionOfFacts": True,
        "rosterAndStatus": roster,
        "excludedFromPassFail": "UNVERIFIED lakes never enter pass/fail; they appear only in the informational 'assumed pool' runs (pRef = source-stated pool if the source has one with constant implied elevation, else directory fullPoolFt)."},
    "levels": {"drawdownBelowPRefFt": [1.5, 3.0, 4.5, 6.0, 8.0], "rule": "pool_low = pRef - d; shift passed to effective_zones = -d. A lake-level is included only if the truth curve is defined at pRef-d (dry share) -- see truth.interpolation; a band is scored only if its lowest needed elevation is within the curve. Excluded lake-levels are listed, never imputed."},
    "sigma": {"graded": "production sigma = sqrt(0.25^2 + 0.1^2 + 0.1^2) = 0.287 ft for every lake (sigma_pool 'high' 0.25, sigma_level DIRECT_OPERATOR_POOL 0.1, sigma_datum SAME_DATUM 0.1); the same value is used for assumed-pool lakes (pool uncertainty there is in truth larger; informational)",
              "informational": "sigma = 0"},
    "predictors": {"C1": {"role": "GRADED (independent of the truth)", "shares": "candidates.json referenceZones.cumulative (keys 3.0/6.0/10.0 -> lt3/lt6/lt10) as frozen in contour2_lake_facts.json; only supported edges exist", "interval": "referenceZones.intervalFt of the lake",
                          "build": "zones.reference_zones_from_shares(shares, interval, coverage, tier, source, reference_verified=True)  (flag forced on so UNVERIFIED lakes can be computed informationally)"},
                   "baseline": "informational: leave-one-lake-out mean dry share at the same d over the other lakes of the same group"},
    "metrics": {"primaryQuantity": "dry share of the reference-pool surface (effective_zones()['shares']['dry'], point estimate = midpoint of (lo, hi)); if the engine WITHHOLDS dry (bound wider than contract MAX_PUBLISHED_BOUND_WIDTH = 0.25) the lake-level is 'withheld' and not scored for accuracy",
                "M1_MAE": "mean |midpoint - truth| over PUBLISHED lake-levels", "M2_maxAbsError": "max |midpoint - truth|", "M3_boundsCoverage": "fraction of published lake-levels with lo-0.0005 <= truth <= hi+0.0005",
                "M4_boundsWidth": "median and p90 of (hi-lo) over published lake-levels", "M5_rank": "pooled Spearman midpoint vs truth over published graded lake-levels (reported per level across lakes, not gating)",
                "M6_publishRate": "published lake-levels / included lake-levels", "bands": "under3/threeToSix/sixToTen/deeper: same M1/M3 where published, reported, not gating", "signedBias": "mean(midpoint - truth) reported"},
    "diagnostics": {"D1_shareCheckAtPRef": "for each supported edge e: S_contour(e) - S_curve(e) with S_curve(e) = (A(pRef)-A(pRef-e))/A(pRef); reported, does not gate",
                    "D2_impliedPool": "grid P in pRef-6..pRef+6 step 0.1; P* minimises sum_e (S_contour(e) - S_curve_P(e))^2 over supported edges; report P*-pRef. INFORMATIONAL ONLY: it shows how far the survey level may be from the assumed pool; it never changes a status, a level or a threshold"},
    "thresholds": {"T1_MAE_max": 0.03, "T2_maxAbsError_max": 0.06, "T3_boundsCoverage_min": 0.80, "T4_medianBoundsWidth_max": 0.15, "T5_pooledSpearman_min": 0.95,
                   "T6_publishRate_min": 0.60, "T6_minPublishedLevelsPerLake": 3,
                   "T6_why": "Different from TWDB (where dry was always published): coarse intervals (5/10 ft) leave only the 10 ft edge so dry bounds are [0, S10] and are withheld by the engine's own 0.25 width rule. A lake that is withheld at most levels cannot be 'passed'; the withhold is the engine's correct refusal, not an accuracy failure, so accuracy metrics use published levels and T6 gates the usefulness.",
                   "perLakePass": "VERIFIED and curve exists and published levels >= 3 and own MAE <= T1, max <= T2, coverage >= T3, median width <= T4 and publishRate >= T6. validation.passed = true only then; false if VERIFIED+curve and any fails; null if UNVERIFIED or no curve (including 'insufficient published levels' = false for VERIFIED lakes).",
                   "pooledPass": "over GRADED lakes: T1..T6 all met (T5 needs >= 3 published points); reported only, not required for a lake's own passed flag", "frozen": True},
    "enableRecommendationRule": "effectiveZones may be enabled for a lake only if VERIFIED and validation.passed is true; a result on assumed-pool lakes is NOT an enable recommendation.",
    "analysisRules": ["Thresholds, levels, rule, roster, predictor and metrics are frozen; nothing changes after results.", "Every included lake-level is reported, withheld ones included.",
                      "The compute script (research/depth/contour2_validate.py) verifies this file's hash AND the data files' hashes and refuses to run on a mismatch.", "Small n is stated; no lake is added or dropped after results."],
    "disclosure": "Before freezing the author had read: the manifest reference shares and intervals of all 94 lakes; the source pool statements (ODNR PDFs, KARS PhysicalLakeData, NE/ND/OK contour Elevation attributes) and their comparison with directory pools (so the status outcomes above are known to the author; the R2 tolerance was kept at 0.25 ft with no rounding allowance deliberately to avoid post-hoc relaxation); the CWMS rating endpoints (minimum/maximum elevation, datum, version dates). No share-vs-curve comparison, no A(pRef), and no effective-zone prediction had been computed.",
    "knownCaveats": ["Shares are of the SURVEYED surface at the survey pool (coverage may be < 1); the curve gives whole-lake area. Partial coverage biases shares (reported in facts coverage).",
                     "Curves may predate the contour survey; sedimentation changes shallow area.", "CWMS curve datum 'OTHER' (NWDM Step templates) and Stage curves (MN) carry assumed datums.",
                     "Withholding follows the engine's 0.25 bound-width rule."]}

canon = json.dumps(doc, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
h = hashlib.sha256(canon.encode()).hexdigest()
if OUT.exists():
    print("REFUSING: prereg already exists:", OUT); sys.exit(1)
ts = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
doc["freeze"] = {"algorithm": "sha256 of json.dumps(doc without 'freeze', sort_keys=True, separators=(',',':'), ensure_ascii=True)", "sha256": h, "frozenAtUtc": ts}
OUT.write_text(json.dumps(doc, indent=1) + "\n")
vs = [k for k, v in roster.items() if v["referenceStatus"] == "VERIFIED"]
print(h, ts); print("VERIFIED:", vs); print("GRADED:", [k for k, v in roster.items() if v["group"] == "GRADED"]); print("ASSUMED:", [k for k, v in roster.items() if v["group"] == "INFORMATIONAL_ASSUMED_POOL"])
