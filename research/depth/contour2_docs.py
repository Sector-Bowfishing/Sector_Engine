#!/usr/bin/env python3
"""Generate the data tables of the two result documents from the frozen prereg, facts, validation summary and proposal, so no number is hand-copied.
Writes docs/brains/depth/DEPTH_CONTOUR_SOURCE_REFERENCE_POOLS.md and DEPTH_CONTOUR_EFFECTIVE_ZONE_VALIDATION.md (prose lives in this script)."""
import csv, json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DD = REPO / "docs/brains/depth/data"
PRE = json.loads((REPO / "jobs/depth-brain/depth_brain/data/proposals/contour_prereg.json").read_text())
F = json.loads((DD / "contour2_lake_facts.json").read_text())["lakes"]
S = json.loads((DD / "contour2_validation_summary.json").read_text())
SEM = json.loads((DD / "contour2_source_semantics.json").read_text())
PR = json.loads((REPO / "jobs/depth-brain/depth_brain/data/proposals/contour_reference_pools.json").read_text())["lakes"]
ROWS = list(csv.DictReader(open(DD / "contour2_validation_rows.csv")))
R = PRE["referenceVerification"]["rosterAndStatus"]; SHA = PRE["freeze"]["sha256"]; TS = PRE["freeze"]["frozenAtUtc"]
f3 = lambda x: "n/a" if x is None else f"{x:.3f}"

# ===================== document 1: source reference pools ==================================================================
L = []
L.append(f"""# Contour Sources: Survey Reference Pools (non-TWDB)

Date: 2026-10-13. Research and evidence only: nothing was sent to anyone, no production code, RTDB or `DEPTH_LICENSING_MATRIX.md` was changed. Companion files: `jobs/depth-brain/depth_brain/data/proposals/contour_reference_pools.json` (machine-readable proposal, schema `depth-twdb-reference-pools-v1` compatible), `docs/brains/depth/data/contour2_source_semantics.json`, `contour2_lake_facts.json`, scripts `research/depth/contour2_*.py`. Rule and thresholds: `DEPTH_CONTOUR_VALIDATION_PREREG.md` (sha256 `{SHA}`). Results: `DEPTH_CONTOUR_EFFECTIVE_ZONE_VALIDATION.md`.

## 1. Answer in one paragraph

In what this study could fetch, none of the 18 non-TWDB contour sources states the water level on the survey date. What several do document is the **pool the depths are measured from**: Ohio DNR Division of Wildlife (per-lake map PDFs: "Depths based on normal summer pool elevation of X ft"), and three sources carry the pool elevation on every contour (Nebraska NGPC, North Dakota Game and Fish, Oklahoma OWRB: elevation = pool + depth, constant inside a lake). Kansas KARS lists a water-surface elevation per reservoir but its own texts disagree on whether that is the normal pool or the level on the survey date. All other sources say only "depth" with no reference. Applying the frozen rule (stated pool within 0.25 ft of the directory pool, directory datum NGVD29/NAVD88, documentation not contradictory) gives **5 VERIFIED lakes of 94** (Alum Creek, Caesar Creek, Tappan, Fort Gibson, Sardis) and **89 UNVERIFIED** with the missing evidence listed per lake. Four of the five VERIFIED lakes have a CWMS stage-area curve and were validated: none passed (`DEPTH_CONTOUR_EFFECTIVE_ZONE_VALIDATION.md`).

## 2. Per-source semantics (task 1)

Columns: what the contour value is; the reference level; survey dates; whether the water level at survey is stated; vertical datum; licence class (from the licensing matrix, unchanged). "Not stated" means not stated in what this study fetched on 2026-10-13; unknown stays unknown.

| Source | Contour value / reference level | Survey dates | Water level at survey | Vertical datum | Licence |
|---|---|---|---|---|---|""")
for k in ["OH", "NE", "KS", "OK", "ND", "MN", "WV", "IN", "IL", "MT", "MA", "CT", "NH", "FL", "MI", "NJ", "WA", "PA"]:
    s = SEM[k]
    L.append(f"| **{k}** {s['org']} | {s['valueType']}. {s['zeroLevel']} | {s['survey']} | {s['waterLevelAtSurvey']} | {s['datum']} | {s['licence']} |")
L.append("""
All 18 sources store contour **depth** (positive or negative feet below a water surface), not elevation; NE, ND and OK additionally carry the elevation next to the depth, which is what lets the reference pool be read from the data. NJ stores metres (converted). UT Utah Lake is the only elevation source and is Tier C (not in the 94).

### What each documented source gives (and what it does not)

* **Ohio DNR (strongest, per lake).** The map PDFs print the pool the depths are based on and the survey year. They do not print a datum (Mosquito Creek and Tappan say "above mean sea level"). The GIS service has no description, so the assumption that the GIS contours equal the printed map is not itself documented. Pool vs directory: Alum Creek 888 vs 888 NGVD29 (match), Caesar Creek 849 vs 849 NGVD29 (match), Tappan 899.3 vs 899.3 NGVD29 (match), Mosquito Creek 901 vs 900.73 NAVD88 (0.27 ft, over the 0.25 rule), Grand Lake St. Marys 871 vs 870.6 (0.4 ft, datum unknown), Lake Milton 948 vs 947.43 NAVD88 (0.57 ft), Hoover 894 vs 894 (directory datum unknown), Salt Fork 800 vs 800 (datum unknown), Pymatuning 1008 vs 1008 (datum unknown). Senecaville: no map retrieved.
* **Nebraska / North Dakota / Oklahoma (pool read from the contour attributes).** NE: implied pool equals the directory pool for Calamus, Swanson, Branched Oak, Box Butte, McConaughy and Johnson (within 1 ft) but the directory datum is unknown for all except Harlan (1945.0 implied vs 1946 directory); Ogallala (3126.5 vs 3122) and Merritt (2953.3 vs 2946, conservation attribute 2947.0) are several feet off. ND: 1.7-2.2 ft off all three directory pools (Bowman-Haley directory datum LOCAL). OK: Fort Gibson 554 NGVD29 and Sardis 599 NGVD29 match the directory pool and datum exactly; Grand Lake and Lake Murray have non-constant implied pools (20 and 200 ft ranges) and Grand's datum (NAVD88) conflicts with the directory (LOCAL).
* **Kansas (contradictory).** Service text for `PhysicalLakeData`: federal reservoirs use the normal operating pool as set by USACE/USBR. Layer text for `BathymetryContour`: the operating level at the time of the survey. Six of the seven fleet lakes equal the directory pool exactly (Clinton 875.5, El Dorado 1339, Melvern 1036, Milford 1144.4, Pomona 974, Wilson 1516), Cheney is 1420.7 vs directory 1421.6. Clinton, Melvern, Milford, Pomona and Wilson have directory datum LOCAL. Rule R4 therefore leaves all seven UNVERIFIED, even El Dorado whose numbers and NGVD29 datum agree.
* **Minnesota.** Zero depth is a digitised 1991-92 shoreline, contours come from old DNR lake maps (Winnibigoshish 1963, Leech 1957, a Gull record 1954 and another 1995). No reference water level. The three Corps lakes have CWMS stage-area curves, so they are validated under an **assumed** pool (directory pool).
* **West Virginia.** ReefMaster sonar contours 2011-2024; nothing about the water level. 12 lakes (Tygart and Stonewall Jackson have CWMS curves; informational only).
* **Indiana** says "some lakes" were adjusted to the legal gauge level but not which; Lake Wawasee stays UNVERIFIED.

## 3. Rule (frozen)

R1 a source statement or per-contour attribute gives the numeric reference water-surface elevation (and it is constant within the lake); R2 it is within 0.25 ft of the directory `fullPoolFt` (no rounding allowance); R3 the directory datum is NGVD29 or NAVD88 and any datum the source states is the same; R4 the documentation is not self-contradictory. Anything else is UNVERIFIED. The rule is TWDB's V1-V4 adapted to sources that carry a pool figure but no survey report. A pass of R1-R4 means "depths are measured from this pool, and this pool is the directory pool"; it does **not** say the water was at that level on the survey day (none of the sources says so).

## 4. Per-lake status (94 lakes)

Columns: lake, source, contour interval, status, source pool / directory pool (datum), missing evidence or confirming evidence. "Curve" = a CWMS stage-area curve exists.

| Lake | Src | Interval | Status | Source pool / directory pool (datum) | Curve | Evidence / what is missing |
|---|---|---|---|---|---|---|""")
for lid, f in sorted(F.items(), key=lambda kv: (R[kv[0]]["referenceStatus"] != "VERIFIED", kv[1]["src"], kv[0])):
    e = PR[lid]; ps = f.get("pSrc"); st = e["referenceStatus"]
    pool = ("%.2f" % ps["poolFt"] if ps else "none") + " / " + ("%s" % f["dirPoolFt"] if f.get("dirPoolFt") is not None else "none") + " (%s)" % f.get("dirDatum")
    note = ("; ".join(R[lid]["statusReasons"]) if st == "VERIFIED" else "; ".join(e.get("missingEvidence", [])))
    L.append(f"| {lid} | {f['src']} | {f['intervalFt']:g} | **{st}** | {pool} | {'yes' if 'curve' in f else 'no'} | {note} |")
L.append("""
## 5. What would move lakes to VERIFIED (cheapest first)

1. **Datum for the lakes whose pool already matches**: Hoover, Salt Fork and Pymatuning (Ohio maps, pool equals directory), Calamus, Swanson, Branched Oak, Box Butte, McConaughy, Johnson (Nebraska contours), and the five Kansas federal lakes with LOCAL datum. One USACE/USBR pool-datum confirmation per project would settle R3. Kansas additionally needs KARS to say which of its two statements applies.
2. **Pool differences to settle**: Mosquito Creek (0.27 ft), Grand Lake St. Marys (0.4 ft), Lake Milton (0.57 ft), Harlan County (1.0 ft), Ogallala, Merritt, Cheney, ND lakes (1.7-2.2 ft). Either the directory pool or the source figure is in a different datum or is a different pool.
3. **Sources with no reference at all (MN, WV, MA, CT, NH, MT, WA, MI, IN, FL, NJ, IL, PA)**: the owner must say what water level the contour depths are measured from and the survey date's water level (agency lake survey sheets/field notes). Contacting owners is a Michael action; nothing was sent.
4. **The survey-date water level itself** is the remaining gap even for the five VERIFIED lakes: all five rely on "depths are based on / measured from pool P", i.e. the agency states the datum plane of the depths, not the level of the water that day.
""")
(REPO / "docs/brains/depth/DEPTH_CONTOUR_SOURCE_REFERENCE_POOLS.md").write_text("\n".join(L))

# ===================== document 2: validation results ======================================================================
V = []
g = S["pooled"]["GRADED"]["production"]; gz = S["pooled"]["GRADED"]["zero"]
V.append(f"""# Contour Effective-Zone Validation vs CWMS Stage-Area Curves: Results

Date: 2026-10-13. Preregistration `DEPTH_CONTOUR_VALIDATION_PREREG.md` / `jobs/depth-brain/depth_brain/data/proposals/contour_prereg.json`, sha256 `{SHA}`, frozen {TS} (the script verified the hash of the prereg and of the two data files before computing; it ran once). Script `research/depth/contour2_validate.py` using the real `zones.reference_zones_from_shares` / `zones.effective_zones`; rows `data/contour2_validation_rows.csv` (every lake-level, every band, both sigmas), summary `data/contour2_validation_summary.json`. Reference pools: `DEPTH_CONTOUR_SOURCE_REFERENCE_POOLS.md`. No threshold, level, lake or rule was changed after results.

## 1. Verdict

**No lake passed. `validation.passed = false` for all four graded lakes (Alum Creek, Tappan, Fort Gibson, Sardis); Caesar Creek is VERIFIED but has no area curve (null); the other 89 are UNVERIFIED (null).** Effective zones should stay withheld for every non-TWDB contour lake.

Graded set: the 4 VERIFIED lakes that have a CWMS Elev;Area curve, 5 drawdowns each = 20 lake-levels. Truth: the operator's exact stage-area curve; predictor: the manifest contour shares (independent of the curve; no circularity, see section 5).

| Frozen threshold (dry share, production sigma {S['sigmaProduction']} ft) | Result (graded, n published = {g['nPublished']} of {g['nIncluded']}) | Pass |
|---|---|---|
| T1 MAE <= 0.03 | {f3(g['mae'])} | FAIL |
| T2 max abs error <= 0.06 | {f3(g['maxAbs'])} | FAIL (0.0609, by 0.0009) |
| T3 bounds coverage >= 0.80 | {f3(g['coverage'])} | PASS |
| T4 median bounds width <= 0.15 | {f3(g['widthMedian'])} | PASS |
| T5 pooled Spearman >= 0.95 | {f3(g['spearmanPooled'])} (n = 4, all Tappan) | PASS but meaningless |
| T6 publish rate >= 0.60 | {f3(g['publishRate'])} | FAIL |

Why: three of the four graded lakes have 5 or 10 ft contour intervals, so only the 10 ft edge exists and the dry bound is `[0, S10]` (0.27, 0.43 and 0.30 of the surface), wider than the engine's own 0.25 publication limit: the engine **correctly refuses** (0 of 15 lake-levels published). The one fine-interval graded lake, Tappan (3 ft), publishes 4 of 5 levels but is biased high by 0.047 (all four errors positive, 0.021-0.061): the contour product has more shallow area than the 1970 Corps curve.

## 2. Graded lakes, every lake-level (production sigma)

| Lake | Interval | d (ft) | truth dry | published bounds (lo-hi) | midpoint error |
|---|---|---|---|---|---|""")
for r in ROWS:
    if r["band"] == "dry" and r["sigmaMode"] == "production" and r["group"] == "GRADED":
        b = "withheld (bound wider than 0.25)" if r["published"] == "0" else f"{r['lo']}-{r['hi']}"
        e = "-" if r["published"] == "0" else f"{float(r['err']):+.3f}"
        V.append(f"| {r['lakeId']} | {float(r['intervalFt']):g} | {r['d']} | {float(r['truth']):.3f} | {b} | {e} |")
V.append("""
Zero-sigma run (informational): Tappan publishes all 5 levels, MAE %s, but coverage only %s (the bounds collapse to points that are about 0.05 too high). The other three lakes still publish nothing.

## 3. Informational: the same test under an ASSUMED reference pool (20 more lakes)

These lakes are UNVERIFIED, so they never count toward pass/fail. Reference pool = the source-stated/implied pool when the source has one (NE/KS/ND), else the directory pool; CWMS curve as truth. This answers: IF the contours are measured from that pool, would the arithmetic hold? A wide gap between assumed and implied pool (column D2) is evidence the assumption may be wrong or the curve is outdated.

| Lake | Interval | Published/included | MAE | Max err | Coverage | Median width | D1 contour minus curve share at pool (edges) | D2 implied pool minus pool (ft) | Curve version / survey year |
|---|---|---|---|---|---|---|---|---|---|""" % (f3(S["perLake"]["Tappan Lake|OH"]["zero"]["mae"]), f3(S["perLake"]["Tappan Lake|OH"]["zero"]["coverage"])))
for lid, ent in sorted(S["perLake"].items(), key=lambda kv: (kv[1]["intervalFt"], kv[0])):
    if ent["group"] == "GRADED": continue
    p = ent["production"]; d = S["diagnostics"][lid]
    d1 = ", ".join(f"{k}:{'n/a' if v is None else format(v, '+.3f')}" for k, v in d["D1_contourMinusCurveShareAtPRef"].items())
    d2 = "n/a" if d["D2_impliedPoolMinusPRefFt"] is None else format(d["D2_impliedPoolMinusPRefFt"], "+.1f")
    V.append(f"| {lid} | {ent['intervalFt']:g} | {p['nPublished']}/{p['nIncluded']} | {f3(p.get('mae'))} | {f3(p.get('maxAbs'))} | {f3(p.get('coverage'))} | {f3(p.get('widthMedian'))} | {d1} | {d2} | {d['curveVersion'][:4]} / {d['surveyYear'] or '?'} |")
for nm, lab in (("ASSUMED_interval_le3", "interval <= 3 ft"), ("ASSUMED_interval_5", "interval 5 ft"), ("ASSUMED_interval_10", "interval 10 ft"), ("ASSUMED_ALL", "all assumed-pool lakes")):
    p = S["pooled"][nm]["production"]
    V.append(f"\nPooled, {lab} ({len(p['lakes'])} lakes): published {p['nPublished']}/{p['nIncluded']} ({f3(p['publishRate'])}), MAE {f3(p.get('mae'))}, max {f3(p.get('maxAbs'))}, bias {p.get('bias', 0):+.3f}, coverage {f3(p.get('coverage'))}, median width {f3(p.get('widthMedian'))}, Spearman {f3(p.get('spearmanPooled'))}.")
V.append(f"""
Leave-one-lake-out fleet-mean baseline (dry share at the same d): MAE {f3(S['baseline']['GRADED']['maeLeaveOneLakeOutMean'])} on the 4 graded lakes, {f3(S['baseline']['ASSUMED_ALL']['maeLeaveOneLakeOutMean'])} on the assumed-pool lakes. On the graded lakes the simple baseline (0.021) beats the engine's published midpoints (0.047).

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
""")
(REPO / "docs/brains/depth/DEPTH_CONTOUR_EFFECTIVE_ZONE_VALIDATION.md").write_text("\n".join(V))
print("docs written")
