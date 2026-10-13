# TWDB Survey Reference-Pool Verification

Date: 2026-10-13. Scope: the six fleet lakes whose manifest evidence is `contour:TWDB` (Cedar Creek, Conroe, Fork, Livingston, Tawakoni, Texoma). No other fleet lake carries a TWDB contour source (checked on `candidates.json`: exactly these six). Machine-readable twin: `jobs/depth-brain/depth_brain/data/proposals/twdb_reference_pools.json`; extraction script `research/depth/twdb_report_facts.py` (output `data/twdb_report_facts.json`, including sha256 of each downloaded PDF).

Everything below was read from the TWDB final reports (PDFs downloaded to `Sector_Research_Data/depth-brain/twdb2/`, text extracted with pypdf) or from the TWDB Completed Surveys page. Anything not stated there is marked unknown.

## 1. Result

| Lake | Status | referencePoolFt (basis of the shares) | Datum | Why |
|---|---|---|---|---|
| Cedar Creek Reservoir | **VERIFIED** | 322.0 | NGVD29 | Report states conservation pool 322.0 ft NGVD29; basis equals it; directory pool 322 |
| Lake Conroe | **VERIFIED** | 201.0 | NGVD29 | Report: 201.0 ft, NGVD29 (gage USGS 08067600); basis and directory 201 |
| Lake Fork Reservoir | **VERIFIED** | 403.0 | NGVD29 | Report: 403.0 ft NGVD29; basis and directory 403 |
| Lake Livingston | **VERIFIED** (with a 0.1 ft note) | 131.1 | NGVD29 | Report: conservation pool 131.0 ft NGVD29; shares are measured from 131.1 ft (table area 78,170 ac matches the survey pool polygon; report area at 131.0 is 77,729 ac); 0.1 ft is inside the 0.25 ft pool sigma; directory 131 |
| Lake Tawakoni | **VERIFIED** | 437.5 | NGVD29 | Report: 437.5 ft NGVD29; basis and directory 437.5 |
| Lake Texoma | **UNVERIFIED** | 620.0 (not the pool) | not stated as NGVD29 | Shares are measured from 620.0 ft (2002 model boundary from the USGS quad 620 ft contour), 3.0 ft above conservation pool 617.0 and the directory pool 617; report gives only "ft above msl" at the USACE gauge |

Rule applied (frozen in the prereg before the validation ran): VERIFIED needs (V1) NGVD29 stated, or the same gauge/datum system as the Sector level binding; (V2) basis within 0.25 ft of TWDB's conservation pool; (V3) Sector directory `fullPoolFt` within 0.25 ft of basis, NGVD29; (V4) contours/table are elevations. Texoma fails V1 (label) and V2 and V3 (3.0 ft).

A finding that changes an earlier statement: the manifest does **not** currently carry `referenceZones` for these six lakes. `contour_truth_lakes.csv` has a blank `interval_ft` for TWDB rows (method `area_capacity_table`; only `first_level_ft = 1.0`), so `reference_zones_from_shares` receives no interval, supports no edges and returns None. The manifest builder needs an explicit interval (published contour interval per lake, table below) before zones exist for them.

## 2. Verified facts per lake

Report URL root: `https://www.twdb.texas.gov/surfacewater/surveys/completed/files/`. Table = area (acres) vs elevation at 0.1 ft steps. "Table vs report" compares the downloaded `.txt` elevation-area table with the area the report states at conservation pool.

| Item | Cedar Creek | Conroe | Fork | Livingston | Tawakoni | Texoma |
|---|---|---|---|---|---|---|
| Report (path under root) | `CedarCreek/2017-10/CedarCreek2017_FinalReport2.pdf` | `conroe/2020-10/Conroe2020_FinalReport.pdf` | `Fork/2009-10/Fork2009_FinalReport.pdf` | `Livingston/2019-11/Livingston2019_FinalReport.pdf` | `tawakoni/2009-08/Tawakoni2009_FinalReport.pdf` | `Texoma/2002-07/Texoma2002_FinalReport.pdf` |
| Sounding dates | Nov 9, 2016; Apr 3-Oct 26, 2017 | Mar 2-Oct 30, 2020; Apr 12, 2021 | Jul 28-Nov 5, 2009; May 25, 2010 | Sep 17, 2018-Nov 21, 2019 | Jun 10-Aug 18, 2009; Oct 15 and Nov 4, 2009 | Jun 3-Jul 9, 2002 |
| Water surface during sounding (ft) | 320.29; 320.33-322.28 | 199.18-200.31; 200.47 | 402.45-404.41; 403.1 | 130.97-132.93 | 435.52-437.25; 439.71, 438.84 | 617.53-619.71 (above pool) |
| Survey age (to Oct 2026) | 8-9 yr | 6 yr | 17 yr | 7 yr | 17 yr | 24 yr |
| Conservation pool (ft, per TWDB) | 322.0 | 201.0 | 403.0 | 131.0 | 437.5 | 617.0 |
| Datum stated | NGVD29 | NGVD29 | NGVD29 | NGVD29 (Riverside gauge is NAVD88, 0.43 ft below NGVD29; TWDB converted) | NGVD29 | "mean sea level" at USACE Denison gauge only |
| Area at conservation pool, report (ac) | 33,099 | 19,894 | 26,889 | 77,729 | 37,325 | 74,686 |
| Table vs report (ac) | 33,099.5 | 19,894.4 | 26,889.1 | 77,729.3 | 37,325.4 | 74,685.7 |
| Table range (ft) | 257.6-322.0 | 139.6-201.0 (bathymetric) | 327.9-403.0 | 57.4-131.1 (bathymetric) | 374.4-437.5 | 520.6-620.0 |
| Pool boundary used by TWDB | 322.0 ft contour from LiDAR | imagery at 201.18 ft water surface, assigned 201.0 | imagery at 402.26 ft, assigned 403.0 | 131.17 ft contour | imagery at 436.77 ft, assigned 437.5 | USGS quad 620 ft contour (incl. Cumberland Pool 4,858 ac) |
| Contour product | `CedarCreek17_1ftcont`, 1 ft | `Conroe20_1ftcont`, 1 ft | `Fork09_2ftcont`, 2 ft | `Liv19_1ftcont`, 1 ft | `Tawakoni09_1ftcont`, 1 ft | `Tex_cont_5`, 5 ft |
| Contour values | elevations 258-322 | elevations 141-201 | elevations 328-402 | not opened (named 1 ft; TWDB treats contours as elevations) | elevations 375-437 | not opened (named 5 ft) |
| Published map in report | 5 ft | 5 ft | 5 ft | (contour map PDF) | 5 ft | 5 ft |
| Surface covered | whole reservoir (hull coverage 1.0 in research) | whole | whole | whole | whole | whole |
| Sector directory `fullPoolFt` | 322 | 201 | 403 | 131 | 437.5 | 617 |
| Directory pool == TWDB pool, same datum? | yes (NGVD29) | yes | yes | yes (0.0; basis 0.1 above) | yes | yes for 617; but shares basis is 620 |

Elevation-contour check: the Cedar, Conroe, Fork and Tawakoni contour shapefiles were opened; their numeric attribute is elevation in feet (steps 1, 1, 2, 1 ft), not depth. The research "depth" is `basis - elevation`.

Did the water surface at survey equal conservation pool? No, not throughout: soundings were taken at water surfaces from about 2 ft below pool (Cedar, Conroe, Tawakoni) to 2.7 ft above it (Texoma 619.71 vs 617.0) and TWDB converts each sounding to elevation using the gauge. The elevation-area table therefore refers to elevations, not to a survey-day water level. The pool-boundary polygon was digitised from imagery at a lower stage for Fork (-0.74 ft), Tawakoni (-0.73 ft) and Conroe (+0.18 ft) and assigned the pool elevation; shallow-margin areas are interpolated/extrapolated (TWDB line extrapolation, 500 ft line spacing).

## 3. Caveats that remain

* Livingston: reference elevation for the shares is 131.1 ft (not 131.0). Record `referencePoolFt = 131.1`; the directory pool 131 differs by 0.1 ft (< 0.25 ft pool sigma). TWDB also notes the survey underestimates sediment and heavy sedimentation above about 120.5 ft.
* Texoma: could be re-based (shift from 620.0 ft) and its datum cross-checked (the Brain's CWMS DENI level is the same gauge), but the report states no NGVD29 label, the 620 ft boundary is quad-derived, the survey is 24 years old and its published product supports only the 10 ft edge. Left UNVERIFIED; a TWDB/USACE statement of the Denison gauge datum in 2002 would close it.
* Survey age: Fork and Tawakoni (2009) and Texoma (2002) are old; no sedimentation correction is applied anywhere.
* Table-derived shares in the manifest come from the same table that serves as validation truth (see the validation doc).

## 4. Licence (cross-check with `DEPTH_LICENSING_MATRIX.md`)

TWDB Completed Surveys page (`https://www.twdb.texas.gov/surfacewater/surveys/completed/index.asp`, fetched in full, 268 KB HTML, 43 k characters of text; the matrix's "truncated at 100,000 characters" concern is resolved: the page contains one terms paragraph and no other licence, copyright, permission or commercial-use text). It says: authorisation for use or reproduction of original material "is freely granted"; TWDB "would appreciate acknowledgement"; TWDB "shall not assume any liability ... for the misuse of this information in a manner not consistent with the survey design; for example, maps produced from this volumetric survey are not intended for use as recreational boating maps, fishing maps, or for reservoir boundary determinations." The reports repeat the first two sentences on their title pages. This agrees with the matrix row (ATTRIBUTION_REQUIRED; derived metrics allowed; customer map layer not advised). New fact: the "not for fishing" language is in a sentence about maps; whether derived shallow-share numbers for fishing use are "consistent with the survey design" is a legal reading, still open (the matrix already asks TWDB to confirm).
