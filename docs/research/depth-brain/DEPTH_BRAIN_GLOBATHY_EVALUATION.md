# Depth Brain: GLOBathy evaluation (draft)

Research only. Date 2026-10-13. Scripts: `research/depth-brain/globathy_*.py`. Data: `docs/research/depth-brain/data/globathy_*.csv|json`. Ledger: `ledger/globathy.jsonl`. Raw downloads (not in git): `~/Desktop/Development/Sector_Research_Data/depth-brain/globathy/`.

## 1. Executive summary

| # | Finding | Numbers |
|---|---|---|
| 1 | **The full gridded rasters are obtainable per lake without the 16.7 GB download.** The figshare record is one 16.7 GB zip of 1,427,688 per-lake GeoTIFFs. HTTP range requests (197 MB central directory, then one member per lake) fetched all 554 fleet rasters for 257 MB. | 554 of 554 fetched (4 needed a retry) |
| 2 | **The rasters add nothing beyond Dmax and one exponent.** Each raster is the radial extrapolation of the same A = a h^b law (raster max equals `Dmax_use`; raster-derived mean and shallow share match the A(h)/V table). There is no real morphology (no flats, drop-offs, channels). | raster vs A(h) mean depth: identical to 0.01 m |
| 3 | **Fleet coverage is 554 of 621 lakes (89 %), but only 234 are "verified" matches.** 288 are weak (geo-only match, polygon area ratio off, or the Sector polygon spans several HydroLAKES polygons) and 32 are suspect. 67 lakes have no match. | verified 234, weak 288, suspect 32, none 67 |
| 4 | **59 of the 554 fleet lakes carry an observed/literature Dmax that was supplied to GLOBathy** (1,468 lakes worldwide). For these GLOBathy is a pass-through of a published value (36 truth lakes: within 1.25x for 92 %, Spearman 0.985). These lakes are not a test of the model, and a fleet-wide score must not include them. | supplied: 59; modeled: 495 |
| 5 | **For the 495 modeled lakes Dmax is weak.** Against agency truth for 75 independent-ish lakes (high and medium confidence): median ratio 1.08 but within 1.25x only 28 %, within 2x 68 % (a constant guess of the median truth gets 56 %), Spearman 0.42 (95 % CI 0.19 to 0.62). With high-confidence truth only (n = 31): Spearman 0.64, within 2x 71 %. | table in section 4 |
| 6 | **GLOBathy regresses to the middle.** 85 % of modeled fleet Dmax fall between 10 and 50 m. Lakes truly under 8 m are overestimated 3.6x (median); lakes truly over 40 m are underestimated to 0.51x (Chelan 453 m vs 29 m, Pend Oreille 351 vs 27, Flathead 113 vs 9). Guntersville: 46 m modeled vs 18 to 20 m (low-confidence truth). | by truth bin below |
| 7 | **Shallow-flat information is not usable.** Against real hypsometry (21 reservoirs, mostly Texas) the share of surface shallower than 6 ft has Spearman 0.53 but a larger MAE than a constant (0.064 vs 0.053); it flags the "broad shallow" third of lakes with AUC 0.67 (n = 21, near chance). Against agency littoral share (n = 12) Spearman -0.10. Against USACE CWMS area change per foot (n = 34) Spearman 0.23. | section 5 |
| 8 | **Verdict:** do not use GLOBathy for absolute depth, shallow flats, drop-offs, or per-lake ranking. Acceptable only as (a) a pass-through of observed Dmax where the `supplied_observed` flag is set, and (b) a very coarse, flagged "unknown / probably 8 to 40 m" prior for the remaining lakes. Prefer agency values where known (this study collected about 116 high or medium confidence ones, see data). | section 8 |

## 2. Methods

**Matching.** Sector lake to HydroLAKES id from the Lake Brain join (`external_join.json`: name or geometric match within 5 km, area ratio window). GLOBathy rows come from the basic-parameters CSV and `GLOBathy_hAV_relationships.nc` via the HydroLAKES id. Match QA flags (`globathy_fleet_match.py`): `geo_only_match`, `area_ratio_off` (HydroLAKES area / Sector polygon outside 0.67 to 1.5), `area_ratio_bad` (outside 0.5 to 2), `poly_spans_multi_HL` (Sector polygon overlaps more than one HydroLAKES polygon), `low_iou` (polygon IoU under 0.5), `shared_HL_id` (two Sector rows on one HydroLAKES id), `mega`. Tiers: verified (no flag), weak (geo-only, ratio off, spans multiple, no polygon), suspect (ratio bad, low IoU, shared, mega).

**Supplied versus modeled Dmax.** `Dmax_use_m` equals one of the six geometric/empirical estimates for 99.9 % of the 1.43 M lakes; the 1,468 where it does not are lakes with an observed Dmax supplied. Fleet column `glob_dmax_source`.

**Truth.** Six parallel research passes collected agency or USGS values (state DNR/DEP/WRD pages, TWDB, OWRB, USGS SIRs, USACE, USBR, TVA 1990 reports, utilities), 232 lake records, 188 with a max depth; each with source URL, quote, confidence (high: agency/USGS/survey read directly; medium: agency value seen through a search summary or with a caveat; low: Wikipedia or fishing sites). Nothing from GLOBathy, HydroLAKES or another model counts as truth. Two derived-truth conventions to note: TWDB reports do not state max depth, so it is normal pool minus the lowest surveyed elevation with area > 0 (11 Texas lakes); Beaver, Grand OK, Table Rock and Millwood use the lowest elevation of USGS tables (lower bounds for Beaver and Grand). Overrides excluded Wateree (agency 225 ft is implausible), Upper-Red-only Red Lake, Pontchartrain.

**Primary sample.** Truth confidence high or medium, match tier verified or weak, **modeled** Dmax only: n = 75. Sensitivity rows: high only, all confidences, suspect matches included, chain groups collapsed, verified matches only.

**Independence.** The Tennessee chain (Guntersville, Wheeler, Wilson, Pickwick, Kentucky...) is one hydraulic group; with Savannah, Santee Cooper, Catawba, Chattahoochee, Coosa groups collapsed to one point each the sample is 71 independent points and results barely move (Spearman 0.38).

**Shallow-area truth.** From agency area-capacity tables: share of pool-surface area shallower than d = (A(pool) - A(pool - d)) / A(pool). Tables with fewer than 8 rows or steps over 2.5 ft were rejected (Wheeler, Cherokee, Norris, Lanier, Allatoona, W.F. George, Koocanusa had only pertinent-data points). Remaining n = 21 (Geist, Eufaula OK, Grand OK, Hudson, Fort Gibson, Cheney, Beaver, Millwood, Table Rock, McConaughy and 11 Texas lakes). GLOBathy share = 1 - (1 - d/Dmax)^b, plus the same from the raster.

## 3. Fleet coverage and match quality

| Item | Count |
|---|---|
| Fleet lakes | 621 |
| HydroLAKES id and GLOBathy row | 554 (name match 348, geometric 206) |
| No match (incl. 22 point-only lakes) | 67 |
| Tier verified / weak / suspect | 234 / 288 / 32 |
| Flags (a lake can have several) | geo-only 206, polygon spans several HydroLAKES polygons 100, area ratio off 62, low IoU 20, ratio bad 19, shared id 6, mega 1 |
| Dmax supplied-observed / modeled | 59 / 495 |

Notes on suspect rows: several are real hydrology, not errors. Kentucky Lake (KY, TN), Kerr (NC, VA) and Flaming Gorge (UT, WY) are one lake listed twice under two states (shared id is harmless). Chain reservoirs are the real hazard: Weiss (HydroLAKES area 0.43 of polygon), Strom Thurmond (0.48), Lake Powell (0.23), Bighorn (0.22), Fort Loudoun matched to Tellico Lake, Guntersville (0.63, polygon overlaps 16 HydroLAKES polygons), Wheeler (0.73, 11 polygons). HydroLAKES uses an older, fragmented water mask, and GLOBathy inherits its polygon. Full list: `globathy_eval_summary.json` under `fleet.suspect_matches`.

Modeled Dmax distribution (m), per `fleet` block of the summary:

| Group | n | p10 | median | p90 |
|---|---|---|---|---|
| Lake_type 1 (natural) | 152 | 9.3 | 19.9 | 87.3 |
| Lake_type 2 (reservoir) | 397 | 14.3 | 23.5 | 49.3 |
| Lake_type 3 (regulated) | 5 | 4.8 | 32.8 | 320.6 |
| Area < 5 km2 | 79 | 7.8 | 13.6 | 22.4 |
| 5 to 20 km2 | 146 | 12.0 | 20.4 | 30.3 |
| 20 to 100 km2 | 202 | 17.7 | 24.4 | 48.0 |
| 100 to 500 km2 | 106 | 20.1 | 41.2 | 87.8 |
| Run-of-river pools (R1) | 41 | 13.7 | 20.5 | 36.4 |
| Dendritic storage (R3) | 89 | 19.3 | 28.3 | 71.6 |
| Natural shallow (N1b) | 33 | 9.8 | 19.7 | 83.5 |

The "natural shallow" class has a median modeled Dmax of 19.7 m, the same as other lakes: the model cannot tell shallow-by-nature lakes apart. Modeled A(h) exponent b has median 2.47 and the 1.2 m shallow share median 13 % (p10 5.6 %, p90 22.8 %), nearly flat across lakes.

## 4. Dmax versus truth

| Sample | n | Median ratio (glob/true) | Bias (m) | MAE (m) | within 1.25x | within 1.5x | within 2x | Spearman (95 % CI) |
|---|---|---|---|---|---|---|---|---|
| **Primary (modeled, high+medium, verified+weak)** | 75 | 1.08 | -9.8 | 22.2 | 28 % | 44 % | 68 % | 0.42 (0.19 to 0.62) |
| Constant guess (median truth) | 75 | n/a | n/a | 23.8 | n/a | n/a | 56 % | n/a |
| High-confidence truth only | 31 | 1.15 | -6.5 | 15.1 | 32 % | 52 % | 71 % | 0.64 (0.35 to 0.84) |
| Verified matches only | 35 | 0.96 | -4.5 | 17.1 | 37 % | 49 % | 71 % | 0.48 (0.13 to 0.75) |
| Chain groups collapsed | 71 | 1.02 | -10.9 | 22.2 | 31 % | 45 % | 66 % | 0.38 (0.13 to 0.60) |
| All confidences incl. low | 135 | 1.08 | -10.2 | 26.0 | 27 % | 40 % | 64 % | 0.39 (0.22 to 0.55) |
| Supplied-observed Dmax (not a test) | 36 | 1.00 | +0.9 | 2.1 | 92 % | 100 % | 100 % | 0.985 |

Pairwise ranking: of 2,035 lake pairs whose true Dmax differ by at least 1.5x, GLOBathy orders 68 % correctly (chance 50 %).

By truth magnitude (primary): true < 8 m (n = 6): median ratio 3.6, within 2x 33 %; 8 to 20 m (23): 1.51, within 2x 83 %; 20 to 40 m (22): 1.02, within 2x 82 %, Spearman 0.03; over 40 m (24): 0.51, within 2x 50 %, 8 % overestimated. Inside any magnitude bin there is essentially no rank skill (Spearman -0.03 to 0.28); the overall 0.42 comes from separating the extremes.

By type (multi-label, primary): reservoir with storage (47) Spearman 0.55, within 2x 77 %, MAE 17 m; natural (10) median ratio 0.45, within 2x 30 %; run-of-river (9) bias -0.02 m, MAE 4.6 m (equal to the constant baseline 4.5 m, Spearman 0.42 CI -0.47 to 0.84); complex-arm (4) MAE 25 m; shallow lakes with true Dmax up to 8 m (13): median ratio 2.15, within 2x 46 %, Spearman -0.04.

Three-class accuracy (shallow < 8 m, mid 8 to 25 m, deep 25 m or more): 61 %. Only 1 of 6 truly shallow lakes is called shallow (recall 17 %, precision 100 %); 12 mid lakes are called deep and 12 deep lakes mid.

Mean depth (modeled V/A versus truth mean, n = 59): Spearman 0.23 (CI -0.05 to 0.49), median ratio 0.91, MAE 9.2 m (constant 9.2 m). No skill.

Named cases (truth high/medium unless stated): Guntersville 46 m vs 18 m (low-confidence truth; the Lake Brain note says about 20 m); Pickwick 28.8 vs 25.9; Hartwell 72 vs 56; Lanier 72 vs 46 (USACE pool minus sluice invert, derived); Wheeler 36 modeled vs truth max not found, mean 4.8 m vs modeled mean 10.6 m (TVA); Lake Texoma 30 vs 29; Lake Travis 74 vs 54; Lake Livingston 55 vs 22; Tuttle Creek 60 vs 15 (low); Houghton 23 vs 7; Clear Lake CA 105 vs 18 (low).

## 5. Shallow area, flats and the A(h) curve

| Truth | n | Truth mean | GLOBathy mean | MAE | MAE of constant | Spearman |
|---|---|---|---|---|---|---|
| Share of surface < 3 ft deep (hypsometry) | 21 | 8.2 % | 9.4 % | 0.038 | 0.030 | 0.36 |
| < 6 ft | 21 | 16.0 % | 18.1 % | 0.064 | 0.053 | 0.53 |
| < 10 ft | 21 | 26.8 % | 28.7 % | 0.101 | 0.094 | 0.59 |
| Agency littoral share (about < 15 ft), MN/other lakes | 12 | 42 % | 46 % | 0.178 | 0.110 | -0.10 |
| CWMS area gained per ft near pool (USACE) | 34 | 2.4 % | 3.3 % | within 2x: 47 % | n/a | 0.23 |

Broad-shallow detection (top third of lakes by true share < 6 ft, 7 of 21): AUC 0.67 for the A(h) share, 0.60 from the raster, 0.71 for low Dmax, 0.68 for low mean depth. At n = 21 these are not distinguishable from chance. The mean shares look right only because the model sits near the average of reservoirs (about 10 % at 3 ft); it is no better than a constant and does not rank. The mean is also biased high (GLOBathy area gain per foot 3.3 % versus truth 2.4 %).

Why: the bathymetry is a single power law fitted to area and an estimated Dmax, extruded radially from the shoreline. It cannot produce a flat that is a delta, an overflowed floodplain or a drowned creek bed, nor a drop-off at a channel. The previous Lake Brain test (Spearman 0.33 for relative area per foot, n = 33) is confirmed with a larger and independent sample (0.23 and 0.53 for the 6-ft share).

## 6. Does it preserve relative ranking?

Partly, and only coarsely: 68 % of clearly different lakes are ordered correctly, driven by size and by the shore-slope estimator that separates large lakes in steep terrain from small lowland lakes. Spearman 0.42 overall (0.64 on high-confidence truth). Within a magnitude band or within a type there is no skill. Because truth values are heterogeneous, a ranking claim stronger than "deep-ish versus shallow-ish at the extremes" is not supported. In particular it fails the lakes the app cares about most: broad shallow lakes (Houghton, Red, Clear CA, Livingston, Guntersville) are all rated mid-depth or deep.

## 7. Limits of this evaluation

* **Small n and mixed quality.** 75 primary points, 31 of them high confidence; types are 4 to 47 lakes; CIs are wide. Only 21 lakes have a real hypsometric curve and 11 of those are Texas reservoirs; no natural lake has one.
* **Truth is not uniform.** Some max depths are depth at the dam or a survey bottom elevation, not a surveyed maximum; some agency pages quote conflicting numbers (Yellowstone 390 to 430 ft; Candlewood 85 to 90 ft). Many medium values arrived through search summaries (flagged in the raw file). Guntersville, Wheeler, Wilson truth is thin: Guntersville low confidence, Wilson none, Wheeler no max.
* **Fleet selection.** Truth lakes are those with documentation, biased toward big, surveyed, agency-managed reservoirs.
* **Match noise.** 40 of 75 primary lakes are "weak" matches; if the HydroLAKES polygon is not the Sector lake the comparison is unfair to GLOBathy. The verified-only row (n = 35) is not better in rank, so noise in matching is not the main cause.
* **Not tested:** pixel-level accuracy (needs surveyed contour grids, such as Texas TWDB contour GIS or USGS multibeam for Geist, Beaver, Table Rock, Grand), and the lake-specific morphology of the 4,000-lake validation set in the original paper.

## 8. Verdicts by use case

| Use case | Verdict | Evidence |
|---|---|---|
| Absolute max depth | **No.** Only 28 % within 1.25x, 68 % within 2x (constant: 56 %). Errors of tens of meters on deep lakes. Exception: supplied-observed lakes (59 in fleet) are literature values and fine, labelled as such. | section 4 |
| Mean depth | **No.** Spearman 0.23, no better than a constant. | section 4 |
| Relative depth between lakes | **Weak.** Orders extremes (68 % of pairs at 1.5x or more apart), no skill within a band. | sections 4, 6 |
| Shallow flats / share of shallow area | **No.** Not better than a constant; AUC 0.67 at n = 21; flat distribution across lakes. | section 5 |
| Drop-offs, channels, spatial morphology | **No.** Rasters are radial extrusions of one power law. | finding 2 |
| Ranking lakes for "broad shallow" | **No.** | section 5 |
| Fallback when nothing else exists | **Yes, only as a labelled low-confidence class prior** (see below). | |

## 9. Recommendation

1. Do not integrate GLOBathy rasters or A(h) shapes into Depth Brain; no morphology is gained and 16.7 GB (or the 257 MB fleet subset) is not needed.
2. Keep a fleet column from `globathy_fleet_match.csv` with: `glob_dmax_m`, `glob_dmax_source` and `match_tier`. Use rules:
   * `supplied_observed` and tier verified or weak: treat as a literature Dmax (confidence medium).
   * `modeled_estimate`, tier verified or weak: show nothing numeric; at most a three-bucket prior (modeled Dmax under 12 m: "likely shallow"; 12 to 40 m: "unknown"; over 40 m: "likely deep"), confidence "very low", never feeding shallow-flat scoring. A bucket claim is mostly right at the extremes only; the "likely shallow" bucket under-recalls (17 % of truly shallow lakes).
   * Suspect and no-match lakes: nothing.
3. Replace by evidence in this order (not in scope here): agency survey values (about 116 high or medium collected in `globathy_truth_raw.json`), TWDB/OWRB/USGS area-capacity tables for shallow share, CWMS stage-storage fits, DEM shoreline slope (validated at Spearman 0.76 in Lake Brain), then GLOBathy.
4. If a fleet-wide scored baseline is wanted, score the 495 modeled lakes separately from the 59 supplied-observed lakes; including the latter inflates the apparent skill (Spearman 0.60 to 0.63 on all 116 high/medium truth lakes versus 0.42 modeled only).

## 10. Files

* `data/globathy_fleet_match.csv` per-lake HydroLAKES id, QA flags, tier, Dmax, source, b, mean depth, shallow shares (1.2, 1.8, 3 m).
* `data/globathy_truth_comparison.csv` per truth lake, truth and GLOBathy values, hypsometry shares, source URL.
* `data/globathy_eval_summary.json` all metrics, fleet block, subsets.
* `data/globathy_raster_stats.csv`, `globathy_cwms_relperft.csv`, `globathy_littoral_check.csv`, `globathy_truth_raw.json` (all collected truth records with quotes).
* Scripts: `globathy_zip_index.py`, `globathy_fetch_rasters.py`, `globathy_fleet_match.py`, `globathy_raster_stats.py`, `globathy_truth_compare.py`, `globathy_fleet_summary.py`, `globathy_ledger.py` (run in that order; use the lake-brain venv).
