# Depth Brain: Hartwell effective-depth validation case

Status: audit / research only. No production change. Branch `feat/depth-brain-foundation` (uncommitted; the lead commits).
Run 2026-10-13. Re-derived independently from the cached CWMS daily series; compared with `DEPTH_BRAIN_EFFECTIVE_DEPTH_RESEARCH.md` (research worktree).
Scripts: `research/depth/hartwell_effective_depth.py`, `research/depth/hartwell_landsat_pilot.py`. Results: `docs/brains/depth/data/hartwell_effective_depth_results.json`, `docs/brains/depth/data/hartwell_landsat_pilot_results.json`. Raw pulls (never in git): `~/Desktop/Development/Sector_Research_Data/depth-brain/adoption/hartwell/`.

**Reading rule for everything below.** "Effective depth of a 4 ft flat" is `4 ft + (pool - 660 ft)`: arithmetic on a *hypothetical* reference depth that is assumed to sit 4 ft under a 660 ft pool. It is a statement about how far the water surface moved, not about any bathymetry. No Hartwell contour or sounding is in the research set.

## 1. Bottom line

1. The research numbers **reproduce exactly**: for 2016-01-01 to 2026-10-06 (3,932 daily values; the research file counts 3,933 because its date stamps sit one day later) shift p05 / median / p95 = **-9.14 / -1.52 / +1.41 ft**, and a 4 ft flat is dry (effective depth <= 0, shift <= -4 ft) on **30.7 %** of days (research: 30.66 %).
2. **The 31 % is a property of the window, not a stable fact.** Year-block bootstrap 90 % interval for the 2016-2026 window is **16 % to 47 %**. The same statistic is 25.4 % for the ten full years 2016-2025, 31.1 % over the whole 1962-2026 record, 34.8 % since 1990, 40.4 % over the last 20 years and 49.6 % over 2000-2015. The 2016-2026 window includes a year-to-date 2026 in which every one of 279 days is at least 4 ft under 660 (pool 649.0 ft on 2026-10-06, an in-progress drought year).
3. **"Full pool 660" is the summer top of conservation, not a flat setpoint.** CWMS publishes a seasonal Top of Conservation of 656.0 ft (winter) rising to 660.0 ft by about April 1, held until about mid October, then falling to 656.0 ft by mid December. Against the operator's own guide (Elev-GC) the 2016-2026 shift is -0.19 ft median and the 4 ft flat is "dry" on 24.6 % of days. Against a 656 ft reference it is 8.0 %, against 662 ft 46.1 %. The choice of reference pool moves the headline by a factor of 5.
4. **Area change per foot agrees across three independent routes**: CWMS stage-storage derived 946 acres per foot (relative 0.0169 per foot at 660 ft), the Lake Brain `hypso_truth` fit 962 acres per foot (0.0166), the 3DEP proxy 1,002 acres per foot (0.0179). A small Landsat pilot measures 778 acres per foot (90 % bootstrap 751 to 806) and, more usefully, the same **fractional** area loss between 660 and 650 ft (17.3 % versus 16.9 % from the rating).
5. **Authoritative depth evidence for Hartwell: none usable.** There is no Tier A or B contour, hydroacoustic grid or published depth map for Hartwell in the research set or that I could reach. USACE Savannah holds recent complete bathymetric surveys (cited as showing a 14 % storage loss at top of conservation since 1962) but I found no public dataset, and the live CWMS stage-storage relation has **not changed since 1962** (largest difference between eras 0.5 %). The area-per-foot numbers above therefore describe a design-era rating, not the surveyed present-day lake.

## 2. The pool series

| Item | Value |
|---|---|
| Source | CWMS Data API, office SAS, `Hartwell.Elev-Pool.Inst.1Day.0.Raw-SHEF_SAS` (cached in Lake Brain as `history/lakebrain_gcs/Lake_Hartwell_SC.csv` and `history/cwms/hartwell_daily.csv`) |
| Span | 1961-12-31 to 2026-10-06 (Lake Brain date labels; the raw CWMS stamps are one day later) |
| Count | 23,656 values, **0 missing days** in the span, largest gap between consecutive observations 1 day |
| Cross-check | The two cached copies are identical after the one-day label shift (max difference 2e-13 ft) |
| Resolution | 0.01 ft |
| Quality codes of the 23,656 values | 23,467 code 1, 147 code 0, 42 code 3 (meaning of the CWMS codes not verified here) |
| Range | 637.49 ft (2008-12-09) to 665.40 ft |
| Datum | **NGVD29**, verified: `GET /cwms-data/locations/Hartwell?office=SAS` returns `"vertical-datum":"NGVD29"`, `"horizontal-datum":"NAD27"`, dam top elevation 206.9592 m (679.0 ft), Corps Reservoir, public name HARTWELL DAM |
| Independent gauge | USGS 02187010 "Hartwell Lake near Anderson, SC", parameter 00062, daily mean, 3,913 days from 2016-01-01: median difference to CWMS **-0.02 ft**, median absolute deviation 0.09 ft, correlation 0.9991 (best day alignment is a one-day shift). The USGS series' own datum label was not established (site file lists altitude -0.04 ft NAVD88 for the gauge), so this proves agreement, not datum identity |
| NGVD29 to NAVD88 | Lake Brain/research file `datum_shift_ngvd29_navd88.csv` lists Hartwell at -0.269 ft; negligible against shifts measured in feet |

CWMS location levels for Hartwell (office SAS, fetched today, converted from metres): Top of Conservation seasonal 656.0 / 660.0 ft; **Top of Flood 665.0 ft**; Top of Inactive 625.0 ft; Streambed 475.0 ft; Top of Dam 679.0 ft; Drought Level 1 654 to 656 ft, Level 2 652 to 654 ft, Level 3 646.0 ft (seasonal values dated 2024-12-12). Area levels: **61,400 acres at 665 ft** (Top of Flood) and **27,650 acres at 625 ft** (Top of Inactive). The Hartwell Lake Master Plan (2021), per a search-result excerpt I could not open directly (the file returned 403 to my fetches), gives 55,950 acres and 2,549,600 acre-feet at 660 ft and 27,650 acres and 1,134,100 acre-feet at 625 ft; the 27,650 matches the CWMS value exactly, and the CWMS-derived area at 660 ft (55,794 to 55,914 acres) is within 0.3 % of 55,950.

## 3. Shift statistics (shift = pool - 660.0 ft)

Percentiles and fractions, with the 90 % interval from resampling whole calendar years with replacement (2,000 draws, 1,000 for the long windows). Only 11 year-blocks exist in the research window, so its interval is wide on purpose.

| Window | Days | p05 / p50 / p95 (ft) | Share of days shift <= -4 ft | <= -2 ft | < -1 ft | <= -6 ft |
|---|---|---|---|---|---|---|
| 2016-01-01 to 2026-10-06 (research window) | 3,932 | -9.14 / -1.52 / +1.41 | **30.7 %** [16.1, 47.2] | 46.1 % [33.1, 59.6] | 54.9 % [43.1, 66.9] | 22.4 % [6.6, 40.4] |
| 2016 to 2025 (ten full years) | 3,653 | -8.72 / -1.15 / +1.44 | 25.4 % [13.4, 41.4] | 41.9 % [30.0, 55.3] | 51.4 % [40.2, 63.2] | 16.5 % [4.4, 34.2] |
| 1990 to 2026-10-06 | 13,428 | -11.29 / -2.01 / +1.97 | 34.8 % [26.3, 43.8] | 50.2 % [42.6, 58.4] | 59.1 % [52.2, 66.8] | 23.1 % [15.0, 32.6] |
| 1962 to 2026-10-06 (full record) | 23,656 | -11.33 / -1.75 / +2.04 | 31.1 % [25.3, 37.6] | 47.8 % [42.5, 53.7] | 57.1 % [52.5, 62.4] | 19.5 % [13.8, 25.8] |
| 2000 to 2015 (pre-window) | 5,844 | -13.40 / -3.95 / +1.51 | 49.6 % [34.6, 64.0] | 62.4 % [48.8, 75.3] | 71.0 % | 35.7 % |

Extremes: minimum -22.51 ft (637.49 ft, 2008-12-09); maximum +5.40 ft (whole record), +4.85 ft in the research window.

Against the operator guide (Elev-GC, 2016 to 2026, n = 3,932): p05 / p50 / p95 = **-7.70 / -0.19 / +2.41 ft**; share of days at least 4 ft below the guide 24.6 %, at least 2 ft below 36.2 %.

Sensitivity of the "4 ft flat dry" share to what is called full pool (2016 to 2026): reference 656 ft 8.0 %; 658 ft 22.4 %; **660 ft 30.7 %**; 662 ft 46.1 %.

Dry spells are persistent, not flickering: in 2016 to 2026 there are 12 separate runs of shift <= -4 ft, median length 28.5 days, longest 546 days, and 96.6 % of the dry days sit in runs of 30 days or more.

## 4. Seasonality and drought years

Annual cycle of the shift (monthly medians; "share <= -4" is the share of days at least 4 ft under 660 ft in that month):

| Month | 2016-2026 median | share <= -4 | 1990-2026 median | share <= -4 |
|---|---|---|---|---|
| Jan | -2.30 | 30 % | -3.11 | 42 % |
| Feb | -1.73 | 22 % | -2.22 | 35 % |
| Mar | -0.15 | 18 % | -0.50 | 24 % |
| Apr | +0.34 | 18 % | +0.31 | 19 % |
| May | +0.46 | 18 % | +0.41 | 18 % |
| Jun | +0.24 | 18 % | +0.12 | 16 % |
| Jul | -0.88 | 19 % | -1.02 | 21 % |
| Aug | -2.21 | 29 % | -2.70 | 34 % |
| Sep | -3.26 | 40 % | -3.71 | 46 % |
| Oct | -4.04 | 51 % | -4.25 | 55 % |
| Nov | -4.52 | 54 % | -4.75 | 54 % |
| Dec | -4.72 | 56 % | -4.88 | 55 % |

The median pool is highest in April to June (about 660.2 to 660.5 ft, the annual fill) and lowest in December (about 655.3 ft), a spread of 5.2 to 5.3 ft in the monthly medians. Part of that is the designed 4 ft winter step in the rule curve (660 to 656 ft); the median sits only about 0.7 ft below the 656 ft guide in December, so the design explains most of the median drawdown and drought explains the tail.

Selected years (shift = pool - 660; days counted at <= -4 ft):

| Year | Min pool (date) | Median shift | Days <= -4 | Days <= -8 | Note |
|---|---|---|---|---|---|
| 2000 | 649.68 (Dec 29) | -5.93 | 257 | 80 | start of the 2000-2002 drought |
| 2001 | 648.29 (Jan 18) | -7.02 | 365 | 142 | |
| 2002 | 645.68 (Sep 12) | -10.94 | 365 | 285 | |
| 2007 | 646.63 (Dec 20) | -4.41 | 219 | 92 | 2007-08 drought begins |
| 2008 | **637.49** (Dec 9) | -12.19 | 366 | 355 | record low in the series |
| 2009 | 641.38 (Jan 1) | -4.34 | 195 | 92 | recovery, swing 20.1 ft |
| 2011 | 649.88 (Nov 23) | -4.46 | 214 | 81 | |
| 2012 | 644.77 (Dec 14) | -9.54 | 366 | 244 | |
| 2013 | 646.26 (Jan 11) | -0.14 | 86 | 37 | refill, swing 18.1 ft |
| 2016 | 648.90 (Dec 31) | -2.56 | 140 | 66 | 2016-17 drought; swing 15.3 ft |
| 2017 | 649.01 (Jan 1) | -7.83 | 365 | 168 | |
| 2018 | 649.99 (Jan 7) | -0.29 | 43 | 25 | |
| 2022 | 653.97 (Nov 22) | -1.63 | 74 | 0 | |
| 2023 | 652.15 (Dec 8) | -2.06 | 108 | 0 | |
| 2024 | 653.30 (Jan 4) | -1.54 | 64 | 0 | 2024 pool never below 653.3 |
| 2025 | 653.23 (Dec 31) | -1.59 | 76 | 0 | |
| 2026 (to Oct 6) | 649.03 (Oct 6) | -7.04 | 279 | 55 | every day to date is <= -4 |

Years with no day at or below -4 ft in 1990 to 2026: 1995, 1996, 2004, 2005, 2020, 2021 (6 of 37). Years with every day at or below -4: 2001, 2002, 2008, 2012, 2017 (and 2026 to date). 2024 is mild in this series: 64 days at or below -4 ft and a minimum of 653.30 ft (2024-01-04); the 2016-17 and 2026 episodes are far deeper, and 2007-08 and 2012 deeper still. I did not test the drought-trigger crossings against the Level 1/2/3 series.

## 5. Area change per foot (what the stage-storage relation gives)

Method. The CWMS daily storage `Hartwell.Stor.Inst.1Day.0.Raw-SHEF_SAS` (23,567 values, 1962 to 2026-07-10, acre-feet) was paired with the elevation series on identical CWMS stamps (23,567 pairs). Surface area at elevation z is `A(z) = dS/dz` and the quantity the research calls "acres per foot" is `dA/dz`. I fitted `S(z)` with a quadratic on the 2010 to 2026 pairs inside 647 to 665 ft, and separately took local linear slopes in 1-ft steps for two eras.

| Quantity | Value |
|---|---|
| A(650), A(655), A(660), A(661.98) from the quadratic (2010 to 2026) | 46,339, 51,067, 55,794, 57,667 acres |
| A(660) from the 1990-2009 and 2010-2026 local fits | 55,914 and 55,895 acres (Master Plan: 55,950) |
| **dA/dz, rating-derived** | **946 acres per foot** (quadratic); 958 (table slope 650 to 660, 1990-2009); 1,038 (table slope 650 to 660, 2010-2026, fewer low-pool pairs); 955 to 969 for 654 to 660 |
| Relative area change per foot | 0.0169 at 660 ft, 0.0164 at 661.98 ft |
| Lake Brain `hypso_truth` (`Lake Hartwell|SC#Hartwell`) | dA/dz **961.8** acres per foot, relative 0.016645, reference 661.98 ft, A_ref 57,783 acres, fit range 646.99 to 664.85 ft, r2 0.9995, 13,002 days |
| 3DEP shoreline proxy (research `acres_per_ft_by_lake.csv`) | **1,001.6** acres per foot, relative 0.0179 (about +4 % to +6 % versus the stage-storage numbers; the research cites 960 as the measured value, 1,002 as the proxy) |
| CWMS area levels (665 ft and 625 ft) | mean 844 acres per foot over 625 to 665 ft; the slope is steeper near the top and flatter low, consistent with the table |
| Fraction of the 660-ft surface lost at 656 / 650 / 648 ft | 6.8 % / 16.9 % / 20.3 % (quadratic; 647 ft is the lower edge of the fitted data, so 648 is barely supported) |

Two checks that matter more than the third decimal:
* **The stage-storage relation is time-invariant.** Median storage per 1-ft pool bin from 646 to 665 ft differs between 1962-1989, 1990-2009 and 2010-2026 by at most **0.5 %**. USACE's own summary of recent complete surveys of Hartwell reports a 14 % storage loss at top of conservation since 1962 (Upper Savannah River Basin Council presentation, "Sedimentation Projections for USACE Reservoirs"); a 14 % loss is not visible in this series. So the CWMS storage and area, and anything derived from it, is the original design relationship (or a table not refreshed after the surveys). The 946 to 962 acres per foot is therefore a rating-based figure, not a measurement of today's lake, and the "measured" label in the research (`hypso_truth`) should read "rating-derived".
* The three routes agree within about 6 % (946 to 1,002), which is far better than the order-of-magnitude the proxy was designed for. This is a validation of the proxy against the rating, not against the lake.

## 6. Authoritative depth and shoreline evidence for Hartwell

Honest statement: **no Tier A or Tier B contour, hydroacoustic grid, depth map or area-capacity survey for Hartwell exists in the research set, and I could not reach one.** The research blocker queue (B-depth-001) already records "no public bathymetry for Southeast/TVA/Duke/Santee/Alabama Power reservoirs" and lists Hartwell among the affected bowfishing-core lakes. Hartwell is not in `ienc_fleet_overlap.csv` (no USACE IENC cell covers it) and is not in the depth-brain source manifest.

What does exist, with what I verified:

| Source | What it is | Status |
|---|---|---|
| USACE Savannah District, CWMS (`water.usace.army.mil`, `cwms-data.usace.army.mil`) | Pool, storage, project levels (656/660/665/625/475/679 ft), area at 665 and 625 ft, NGVD29 | **Verified today.** Authoritative for level and datum; rating appears to be the original table |
| USACE Savannah District, Hartwell Master Plan (2021) | Elevation-area-storage values (660 ft: 55,950 acres, 2,549,600 acre-feet; 625 ft: 27,650 acres, 1,134,100 acre-feet), project description, older statement of "very limited siltation" from limited surveys near intakes and the forebay | Second-hand (search excerpt); the file returned 403 to my requests, so not read directly |
| USACE complete bathymetric surveys of Hartwell, Russell, Thurmond (cited by SC DES / Upper Savannah River Basin Council, "recent"; Hartwell -14 % storage at top of conservation, about 1,900 MG per year since 1962; a repeat survey planned within ten years) | Full-lake multi-beam style surveys by USACE; used for the 2024 Lake Hartwell Water Supply Study stage-storage projection to 2072 (-25 % assumed) | **Exists, not public as far as I found.** Survey year not established. A 17 % conservation-storage-loss figure also appears in other SC DNR/USACE material (not reconciled). The draft Hartwell Water Supply Storage Reallocation Report (Oct 2025) and its Appendix A (Engineering) are the likely places for the survey details; both returned 403 to my requests |
| Georgia Tech GWRI, "Reservoir Shoreline Erosion" (Paul Work), 10 to 13 Feb 2003 | Dual-frequency echo-sounder bathymetry, ADCP velocity, DGPS shoreline, mostly the main pool; reports about 2 +- 0.27 m of thalweg deposition over 40 years | Research report page read; no depth grid link; datum and coverage not established. Contact GWRI |
| SC DNR lake description page | Average depth 45 ft, maximum 185 ft (summary figures) | Not a contour |
| Commercial charts (C-MAP 1-ft contour card, Longitude Maps) | Proprietary depth contours | Not usable without a licence; not evidence for the Brain |
| USGS | Gauge 02187010 (pool); no bathymetry found | Level only |
| SC DNR and Georgia DNR fisheries | Possible hydroacoustic or contour files for fishery management | Not found online; only a request would tell |

Recommendation: record Hartwell as **no contour truth; level truth tier A (NGVD29, CWMS); area-per-foot rating-derived, tier C** and keep the effective-depth output for Hartwell a *shift in feet*, never a depth. Open requests: USACE Savannah (survey year, method, datum, whether a gridded product or the Appendix A stage-storage table can be shared), Georgia Tech GWRI (2003 grids), SC DNR and Georgia DNR fisheries.

## 7. Reference flats: effective-depth outcomes

Fraction of days a hypothetical flat that is 2, 4 or 6 ft deep at 660.0 ft would have each effective depth, `d0 + shift`. Classes: **dry** (<= 0 ft), 0 to 1 ft, 1 to 3 ft, 3 to 6 ft, 6 ft or more. "Below 1 ft" is dry plus 0 to 1 ft. Brackets are the 90 % year-block bootstrap interval. These are depth-shift statements for a hypothetical reference depth, not known bathymetry. A real flat does not behave as a flat bench: shoreward cells drain first, deeper cells never dry, and the table says nothing about how much lake has such a depth.

**Window 2016-01-01 to 2026-10-06 (3,932 days; the research window)**

| Reference flat at 660 ft | Dry (<= 0) | 0 to 1 ft | **Below 1 ft** (incl. dry) | 1 to 3 ft | 3 to 6 ft | 6 ft or more |
|---|---|---|---|---|---|---|
| 2 ft | 46.1 % [33.1, 59.6] | 8.8 % | **54.9 %** [43.1, 66.9] | 34.4 % [25.9, 42.4] | 10.2 % [5.6, 15.0] | 0.5 % [0.0, 1.3] |
| 4 ft | 30.7 % [16.1, 47.2] | 6.9 % | **37.5 %** [23.6, 52.6] | 17.3 % [12.8, 21.5] | 43.0 % [31.7, 54.0] | 2.1 % [1.0, 3.3] |
| 6 ft | 22.4 % [6.6, 40.4] | 3.0 % | **25.3 %** [10.1, 43.0] | 12.2 % [7.4, 16.8] | 31.4 % [23.4, 38.7] | 31.1 % [21.9, 40.0] |

**Full record 1962-2026 (23,656 days)**

| Reference flat at 660 ft | Dry (<= 0) | 0 to 1 ft | **Below 1 ft** | 1 to 3 ft | 3 to 6 ft | 6 ft or more |
|---|---|---|---|---|---|---|
| 2 ft | 47.8 % [42.5, 53.7] | 9.4 % | **57.1 %** [52.5, 62.4] | 29.2 % [25.7, 32.5] | 13.3 % [10.5, 15.8] | 0.3 % [0.2, 0.5] |
| 4 ft | 31.1 % [25.3, 37.6] | 7.1 % | **38.2 %** [32.5, 44.5] | 18.9 % [16.5, 21.2] | 37.5 % [32.9, 41.9] | 5.4 % [4.0, 6.6] |
| 6 ft | 19.5 % [13.8, 25.8] | 5.6 % | **25.0 %** [19.1, 31.3] | 13.2 % [11.3, 15.2] | 31.3 % [27.8, 34.5] | 30.5 % [26.1, 34.4] |

Other windows (4 ft flat, dry / below 1 ft): 2016-2025 25.4 % / 32.8 %; 1990-2026 34.8 % / 41.3 %; last 20 years 40.4 % / 47.6 %; 2000-2015 49.6 % (below-1-ft share not tabulated).

Uncertainty that the brackets do **not** cover, in decreasing size:
* **Reference pool** (what "full pool" means): 656 / 658 / 660 / 662 ft give 8.0 / 22.4 / 30.7 / 46.1 % dry for the 4 ft flat. Using the operator's seasonal guide as the reference gives 24.6 %.
* **Window / regime**: dry share ranges 25 % to 50 % across windows from 10 years to the full record; the year-block interval already shows this but with only 11 blocks it is a rough guide.
* **Reference depth itself** (the 2, 4, 6 ft is a hypothesis; a real contour map has 1 to 5 ft interval error and its own datum, see the research sigma_propagation).
* Gauge and datum: level +-0.1 ft (USGS agreement 0.09 ft MAD), NGVD29 to NAVD88 0.27 ft; both small beside the above.
* Non-stationarity: drawdown policy changed (drought levels dated 2024; pool operations after the 2007-08 drought), so the pre-2016 record is not a forecast of the current regime.

## 8. Validation tests that use only evidence that exists

| Test | Uses | Status / result |
|---|---|---|
| T1 Reproduction of the research numbers from the cached CWMS series | Pool series | **Done.** Exact match (section 1). Residual difference of one day in the window start |
| T2 Series integrity: gaps, duplicate copies, second gauge | CWMS, Lake Brain cache, USGS 02187010 | **Done.** 0 gaps, copies identical, USGS agrees within 0.09 ft MAD |
| T3 Reference-pool and window sensitivity | Pool series + CWMS guide | **Done** (sections 3 and 7) |
| T4 Stage-area response: does the lake surface respond to level the way the rating says | CWMS storage + Landsat | **Pilot done** (section 9) |
| T5 Proxy versus rating: 3DEP acres per foot against stage-storage acres per foot | research proxy, CWMS storage | **Done.** 1,002 versus 946 to 962 acres per foot (+4 % to +6 %) |
| T6 Rating stability: has the stage-storage mapping moved with time | CWMS storage | **Done.** No change above 0.5 %; compare against the surveyed -14 % storage loss when USACE releases the survey |
| T7 Extend T4 to the 2007-2012 drought (pool down to 637 to 646 ft) | Landsat 5/7 scenes (2007-2012), same pool series | **Proposed.** Gives the stage-area curve down to 637 ft and tests the rating below its 647 ft fitted edge |
| T8 Exposed-terrain elevation consistency | Per-pixel inundation thresholds from the scene stack (as in the Texas pilots) against 3DEP elevation of the same pixels (NGVD29/NAVD88 corrected by 0.27 ft) | **Proposed.** Pixels that are dry only below some pool should show a DEM elevation near that pool where the lidar was flown at a higher pool; check the 3DEP acquisition pool first |
| T9 Rating cross-check once available | USACE survey/Master Plan table or the survey-based stage-storage (Appendix A of the draft reallocation report) | **Blocked** on access (403 from my requests); request from USACE Savannah |
| T10 Real-flat test of the effective-depth arithmetic | A lake with contour truth and a long level series (Lake Fork in the research) | **Already done in the research**; Hartwell has no truth, so it cannot be done here |

## 9. Landsat pilot (small, run once)

Design: Landsat 8 and 9, Microsoft Planetary Computer `landsat-c2-l2`, path 18 row 36, 2013-04-01 to 2026-10-10, cloud under 35 %. 199 candidate scenes had a pool value; 140 were read (all 67 with pool <= 656 ft plus a random draw of the rest), 94 had at least 97 % valid pixels in the lake mask. Wet = MNDWI > 0 (green and SWIR1 surface reflectance), QA cloud, shadow, snow, fill masked. Lake mask = the largest connected component of pixels wet in any scene with pool at or above 658.5 ft, dilated one pixel (54,883 acres of 30 m pixels). Pool level taken from the Lake Brain CWMS series on the scene date. Pool range of the used scenes 649.17 to 661.88 ft; scenes in every month (4 to 12 per month).

| Metric | Landsat pilot | CWMS rating |
|---|---|---|
| Spearman correlation, pool vs wet area (94 scenes) | **0.971** | n/a |
| dA/dz, Theil-Sen over 650 to 661 ft (86 scenes) | **778 acres per foot** (95 % 744 to 812; scene-bootstrap 90 % 751 to 806) | 946 (quadratic), 958 to 1,038 (table) |
| Wet area at 660 ft from a linear fit | 45,046 acres | 55,794 acres |
| Fraction of the 660 ft area lost by 650 ft | **17.3 %** | **16.9 %** |
| Binned median wet area, 649 / 651 / 653 / 655 / 657 / 659 / 661 ft | 36,486 / 38,261 / 39,557 / 40,972 / 42,748 / 44,577 / 45,158 acres | |
| Pixels wet at high pool but dry in 70 % of the 13 scenes at or below 652 ft | 9,488 acres | |

Reading: the lake surface responds to the pool monotonically and with very nearly the rating's proportional slope; the absolute area and the slope are 19 % and 18 % low, as expected from 30 m mixed pixels along narrow coves and the mask built from the same classification. The ratio test is what the pilot supports: **the rating's fractional response is reproduced**; the absolute acreage is not. This supports using the relative area-per-foot (0.0165 to 0.0169 per foot) for Hartwell, not the absolute.

Limits. One sensor family, no ground truth, no correction for shoreline vegetation or turbidity, seasonal mix of scenes is uneven, level assigned to scene date without time-of-day, pool range stops at 649 ft (no data below), 46 of 140 scenes dropped for more than 3 % invalid (cloud, shadow, fill) pixels. It tests the shape of the stage-area relation only; it cannot test depth, because Landsat does not see below the surface here. It does not validate any contour.

## 10. Caveats the Depth Brain must carry for Hartwell

* An effective-depth number for Hartwell is a **shift in feet** relative to a stated reference pool and datum (NGVD29), with the reference pool named (summer top of conservation 660 ft or the seasonal guide).
* No point on Hartwell has a known depth in the Brain. The 2, 4, 6 ft flats are scenarios.
* Area-per-foot for Hartwell is rating-derived from a table that has not tracked sedimentation; carry it at tier C and with the relative form.
* The 31 % dry figure must not be quoted without its window and reference pool, and not as a forecast.

## 11. Not verified

* The text of the 2021 Hartwell Master Plan and of the draft reallocation report and its Appendix A (403 to my fetches; only search excerpts seen).
* The year, method and vertical datum of the USACE complete bathymetric surveys; whether any gridded product exists; the 14 % versus 17 % storage-loss difference.
* Whether the CWMS quality codes 0 / 1 / 3 mean anything that affects the series.
* The datum label of USGS 02187010.
* The Drought Level crossings of 2024 against the Level 1 to 3 series.
* Anything about Hartwell depth below the pool beyond the arithmetic above.
