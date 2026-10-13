# Depth Brain: Guntersville IENC 9 ft contour asset audit

Status: audit / research only. No production change. Branch `feat/depth-brain-foundation` (uncommitted; the lead commits).
Audited 2026-10-13. Everything below was read from the files and services named in each row; "not verified" marks what could not be established.
Scripts: `research/depth/ienc_layers.py`, `ienc_pull.py`, `ienc_attrs.py`, `ienc_geom.py`, `ienc_segments.py`, `ienc_uncharted.py`, `ienc_contour_len.py`, `ienc_newer_pieces.py`, `ienc_lakare.py`, `s57_header.py`, `s57_inventory.py`, `gunt_pool_context.py`.
Downloads (never in git): `~/Desktop/Development/Sector_Research_Data/depth-brain/adoption/` (REST layer pulls as GeoJSON, `s57/` copies of the three cached cells, the IENC Encoding Guide PDF and its text extraction, `seg_vs_depare.csv`).

## 1. Bottom line

The shipped asset is **one measured contour line (9 ft, 2.74 m) and a residual "inside / outside the line" polygon split**, from three USACE Nashville District Inland ENC cells, on a **sounding datum that is declared only as a code ("local low water reference level") with no elevation encoded anywhere in the cell**. It is not a depth surface, not a "shallow water" measurement, and it cannot be level-adjusted to a numeric pool elevation from the chart alone.

Evidence class to assign: **PARTIAL MEASURED CONTOUR EVIDENCE, tier C-limited** (details and the can/cannot table in section 9).

Findings that change how the asset should be described (all verified, sections below):

1. **Datum.** The three S-57 cells declare `DSPM VDAT = 31` and `SDAT = 31`. The IENC Encoding Guide (Ed. 2.4.1, 20 Mar 2018) lists code 31 as "Local low water reference level". There is no `M_SDAT`/`M_VDAT` object in any of the three cells (the layers do not exist), so one sounding datum applies to everything. **No reference pool elevation is given** in the cell header, in any object, or in the REST attribute tables. The 9 ft is therefore "9 ft below an unspecified local low-water plane", not "9 ft below 595 ft" and not "9 ft at a measured stage".
2. **What `0 to 2.74` means.** Encoding Guide section I.1.5 and I.2.1: the US convention is a **single project-depth contour (typically 2.74 m, 9 ft)**, and "a Shallow Depth area or unsurveyed area must form the boundary between the Project Depth and the land". The `DEPARE DRVAL1 = 0, DRVAL2 = 2.74` polygons are therefore **"between the shore and the 9 ft contour: shallower than 9 ft or not surveyed"**, a residual class, not a measured shallow zone. `DRVAL1 = 2.74, DRVAL2 = Unknown` is "deeper than the 9 ft contour, maximum depth not stated".
3. **Survey dates.** The assumption "everything is 2007" is mostly right but not exact. Inside the Guntersville polygon: the `0 to 2.74` polygons are 2007 (126.6 km2, essentially all of it); the `2.74 to Unknown` polygons (92.5 km2) carry **2008**; a sliver (0.007 km2, 19 polygons) carries 2014; one 4.0 km contour piece carries 2020 (`USACE_Nashville_Hydro_Survey_IENC-20-013`). The `SORDAT` values are `YYYY0701`-style nominal dates (July 1), so the survey day is not known. Survey start/end (`SURSTA`/`SUREND`) are empty.
4. **Quality.** One data-quality object per cell: **Zone of Confidence B, "found by echo-sounder"** (`CATZOC = 3`, `TECSOU = 1`), assigned in a 2021/2023 chart-compile action ("graph", USACE Nashville District), not a survey statistic. ZOC B nominal accuracy is +-50 m horizontal and 1.00 m + 2 % of depth vertical at 95 % (IHO table, quoted below), i.e. +-1.05 m (3.5 ft) at 2.74 m, and "full area search not achieved".
5. **Coverage.** 82.3 % of the Lake Brain Guntersville polygon (219.1 of 266.2 km2) falls inside a chart depth area; 17.7 % (47.1 km2) does not. That is the area picture; the **shoreline picture is much worse** because the uncharted water is tributary embayment with long shoreline: 32.6 % of shoreline length (421.5 of 1,292.3 km) and 32.8 % of segments (2,133 of 6,504) are unclassified.
6. **A discrepancy in the shipped metadata.** `LakeRegistry.swift` (~line 172) states coverage `0.62` and "2,445 of 6,504 segments are unmeasured". The segment file says otherwise: 4,371 are `classified` (4,059 shallow + **312 deep**) and 2,133 are `unavailable`. 2,445 = 2,133 + 312 is the number of segments whose littoral polygon came from the 75 m fixed buffer, not the number unmeasured. `FISH_INTELLIGENCE_BETA_READINESS.md` repeats "62 % ... 2,445 unmeasured". The correct statement is 67.2 % classified, 32.8 % unavailable (this matches `guntersville-segmentation-report.json`: `depthClassifiedPct 67.2`, `depthUnavailable 2133`). Recommend fixing the registry text and coverage fraction when the asset is wrapped (not done here).

## 2. Which charts cover Guntersville

REST footprint layer `IENC_Chart_Footprints_2025/MapServer/0`, envelope query (-86.6, 34.2, -85.6, 34.9), returned three cells, all `USACE Nashville District`:

| Cell | Tennessee River mile | M_COVR `Source_Date` (REST) | Cached S-57 edition (read from the file) |
|---|---|---|---|
| U37TN306 | 306.6 to 360.3 (Guntersville Dam at mile 349.0 is inside it; the cell also covers Wheeler Lake below the dam) | 20210210 | Ed. 15, update 7, update date 20230418, issue date 20260629; README source date 20251015 |
| U37TN361 | middle reach (mile range not read) | 20210210 | Ed. 14, update 6, update date 20250417, issue date 20260629 |
| U37TN391 | 391.5 to 450.0 (Nickajack Dam at mile 424.7 is inside it; the cell also covers Nickajack Lake and Chattanooga) | 20230321 | Ed. 14, update 9, update date 20230418, issue date 20260903; source date 20251115 |

Notes. (a) `Source_Date` in the footprint layer is the date of the **coverage/compile object (2021 / 2023), not a survey date**; the research file `ienc_fleet_overlap.csv` row for Guntersville (`20210210;20230321`) is that field and must not be read as survey years. (b) Compilation scale `DSPM CSCL = 5000` (1:5,000). (c) The cached cells are in `Sector-mapbox/.fishintel-cache/guntersville/ienc/` (copied read-only to the adoption folder). (d) Cells also cover Wheeler and Nickajack water, so cell-wide totals (e.g. 631.6 km of 9 ft contour) are not Guntersville-only.

## 3. Vertical datum (the main question)

What the data say, with the evidence:

| Item | Value | Evidence |
|---|---|---|
| Dataset vertical datum (`DSPM_VDAT`) | **31** | `s57_inventory.py`, GDAL S-57 `DSID` layer of all three cells |
| Dataset sounding datum (`DSPM_SDAT`) | **31** | same |
| Meaning of 31 | "Local low water reference level" | Encoding Guide Ed. 2.4.1, C.1.4 and C.1.5 (`verdat` list: 12 MLLW, 31 Local low water reference level, 32 Local high water reference level, 33 Local mean water reference level, ...) |
| `M_SDAT` / `M_VDAT` objects | **none** (layers absent in all three cells) | `s57_header.py`: `Layer 'M_SDAT' could not be opened` |
| `VERDAT` on `DEPARE` / `DEPCNT` | empty on every feature | `s57_inventory.py` (the guide prohibits per-object `verdat` on depth objects: I.1.1 A, I.1.5 F) |
| Gauge datum values (`WATERWAY_GAUGE_POINT`: elevation, reference level, high/low water names, sounding datum name) | **all blank** on all 20 gauge points (9 + 11); staff gauges at Guntersville and Nickajack locks and bridges, source dates 2003 and 2014 | REST pull, `ienc_attrs.py` |
| Horizontal datum | `HDAT = 2` (WGS 84) | `DSID` |
| Depth unit | metres (`DUNI = 1`); 9 ft is encoded as 2.74 m | `DSID`, `DEPARE`/`DEPCNT` values |
| Reference pool elevation stated anywhere in the chart data | **none** | all of the above |

How the guide describes the reference level: depth areas carry a single "reference water level", which "is only provided in the cell header (field: DSPM, subfield SDAT) or in m_sdat" (I.1.1 A, I.1.5 F). The guide does not tell the encoder to publish the elevation of that level, and Nashville District did not. The guide's own shoreline rule is project-specific: "in pool areas, project pool is used" (D.2.5 B), which describes the **shoreline** (`COALNE`), not the sounding datum.

What is known about the pool, from other sources (not from the chart):
* TVA: Guntersville is held at a **minimum winter elevation of 593 ft "to maintain the depth required for navigation"**, typical summer 594 to 595 ft (TVA lake info page for Guntersville, fetched 2026-10-13; the page does not state a datum). Sector uses 595 ft as full pool (summer pool; top of gates 595.4 per the effective-depth research).
* Observed pool, TVA GVDA1 2005-01-30 to 2026-10-13 (7,404 days, `gunt_pool_context.py`): min 592.84 (2022-12-05), p01 593.20, p05 593.47, median 594.33, p95 595.00, p99 595.20, max 595.90. Jun-Sep median 594.6, Dec-Feb median 593.9; fraction of days under 593.0 ft: 0.09 %.
* Pool around the nominal survey dates: Jun-Aug 2007 min / median / max 594.0 / 594.5 / 595.2 (Jul 2007: 594.2 / 594.5 / 595.0); 15 Jun to 15 Aug 2008 593.5 / 594.2 / 594.8; 20 Apr to 31 May 2014 594.1 / 594.8 / 595.2. The survey-day pool is unknown because the survey day is unknown.

**Conclusion on the datum.** The reference plane is "local low water", elevation unspecified. Plausible candidates are 593.0 ft (the TVA minimum winter operating level that exists to protect navigation depth) or a Nashville District project plane; **this is an inference, not a verified statement, and I could not find a published statement tying the IENC sounding datum to a number**. The nominal ambiguity is about 2 ft (593 vs 595), which is the full operating range of the lake. To close it, ask IENC_POC@usace.army.mil (the contact in the service metadata) or the Nashville District Navigation/Channel survey group what elevation the Tennessee River IENC low-water reference plane is for pool 8 (Guntersville), and which NGVD29/NAVD88 realisation. Until answered, label the datum "IENC local low water reference level (code 31), elevation not published".

## 4. Survey years and source

| Layer (inside / near Guntersville) | Source string in the data | Year | Extent |
|---|---|---|---|
| `DEPARE 0 to 2.74` (shore to 9 ft contour) | `US,U3,SURVY,2007_USACE_Hydrographic` | 2007 | 126.6 km2 inside the lake polygon (about 100 % of that class) |
| `DEPARE 2.74 to Unknown` (deeper than 9 ft) | `US,U3,SURVY,2008_USACE_Hydrographic` | 2008 | 92.5 km2 inside the lake polygon |
| `DEPARE 0 to 2.74` | `2014_USACE_Nashville_Hydro_Survey` | 2014 | 19 polygons, 0.007 km2 (upper end of the lake, lat 35.02, near Nickajack Dam) |
| `DEPCNT 2.74` | 2007 `2007_USACE_Hydrographic` | 2007 | 625.8 km (all three cells) |
| `DEPCNT 2.74` | `2014_USACE_Nashville_Hydro_Survey` | 2014 | 1.8 km |
| `DEPCNT 2.74` | `USACE_Nashville_Hydro_Survey_IENC-20-013` | 2020-07-28 | 4.0 km (upper end, lat 35.03) |
| Coverage / quality compile | `graph, USACE Nashville District` | 2021-02-10 and 2023-03-21 | `M_COVR`, `M_QUAL` |
| Shoreline `COALNE`/`SLCONS` | `2007_Photo_Science,_Inc.` (aerial imagery), `2014_SEAS_LIDAR_Mapping_Survey`, `2008_USACE_Field_Survey` | 2007, 2014, 2008 | not depth |

Observations:
* **The "deep" (2008) polygons and the 9 ft contour (2007) have different dates.** That is a compile artefact worth knowing: the deep polygon is bounded by a 2007 line but dated 2008.
* The survey is a USACE navigation hydrographic survey (echo-sounder). `SURSTA`/`SUREND` are empty, `POSACC`/`SOUACC` are empty, `TECSOU` is "found by echo-sounder". The day of survey is unknown; July 1 is a nominal placeholder.
* 19 years have passed since the 2007 data; Guntersville sedimentation rate is not established in this audit (not verified; no source read). The chart has been revised since (Ed. 14 and 15, updates up to 2025), but the depth objects themselves were barely touched (about 5.8 km of contour and a sliver of area carry post-2007 dates).
* No `SOUNDG` (soundings), `UNSARE`, `DRGARE` or `OBSTRN` layers have features in any of the three cells.

## 5. Contour semantics

* `DEPCNT VALDCO = 2.74` is a **single project-depth contour**. Encoding Guide I.2.1 A: "US: USACE shall show a single depth contour for project depth (typically 2.74 (9')). A zero (0) depth contour shall also be used if a Low / High Water Range (Drying Height) exists." In the three cells there are 136 `DEPCNT` features, all 2.74; no zero contour.
* `DEPARE` is two-valued: `(0, 2.74)` and `(2.74, Unknown)`; no other bands.
* The guide's rule D for the project-depth area: "A Shallow Depth area or unsurveyed area must form the boundary between the Project Depth and the land". This is why the `(0, 2.74)` class is a residual that includes unsurveyed margin. Its `DRVAL1 = 0` is the bank-bounded convention (I.1.1 D), not a measured minimum depth.
* So the 9 ft value is best read as a **chart-datum depth: 9 ft below the IENC local low-water reference level at the time the chart was compiled from a 2007 echo-sounder survey**. It is not "depth below pool at survey time" (the survey-time pool was about 594.5 ft; the reference plane need not equal it), and it is not "project depth 9 ft" in the sense of a dredged channel depth. It is the display line for the navigation project depth.
* Positional meaning: a contour line is a thin set. Inside-versus-outside classification of a shoreline polygon relative to it inherits +-50 m (ZOC B) of line position uncertainty, which is large against the 200 m segments and the median 44 m shore-to-contour effective width (`effectiveWidthMedianM 44.2` in the segmentation report).

ZOC B (IHO CATZOC table, as reproduced by TeledyneCARIS and the Kartverket copy; the guide's own table is an image in the PDF and was not machine-readable): position +-50 m, depth accuracy 1.00 m + 2 % of depth (95 %), full area search not achieved, uncharted features "not expected but may exist". At 2.74 m the vertical term is 1.00 + 0.055 = about 1.05 m.

## 6. Coverage and why 33 % is unavailable

Area (Lake Brain Guntersville polygon, 266.2 km2; `ienc_geom.py`, `ienc_uncharted.py`):

| Class | km2 inside lake polygon | Share |
|---|---|---|
| `DEPARE (0, 2.74)`, 2007 | 126.6 | 47.6 % |
| `DEPARE (2.74, Unknown)`, 2008 | 92.5 | 34.7 % |
| Charted total | 219.1 | 82.3 % |
| Not inside any `DEPARE` | 47.1 | 17.7 % (3,294 pieces; 13 pieces over 0.5 km2 hold 41.9 km2) |

So the survey is **not channel-only**: the deep polygon is 35 % of the lake's area. The uncovered 18 % is tributary embayments and similar, per the segment evidence below. The M_COVR `No Coverage` polygons (CATCOV 2) are the rectangular remainder of each cell and intersect the lake over 23.9 km2.

Segments (6,504, `ienc_segments.py`, join of segment centroids to the depth areas):

| Shipped class | Segments | Shoreline km | Nearest `DEPARE` within 150 m |
|---|---|---|---|
| shallow (`littoralBoundary ienc9ft`) | 4,059 | 808.5 | `(0, 2.74)` 2007 for 4,020; 39 nearest to the deep polygon |
| deep (`fixedBuffer`) | 312 | 62.4 | 145 nearest `(0, 2.74)`, 160 nearest deep polygon, 7 none |
| unavailable | 2,133 | 421.5 | none within 150 m for 2,115 (median distance 2.79 km, min 87 m); 18 within 150 m of a `(0, 2.74)` polygon |

Why 33 % is unavailable: the unavailable segments are overwhelmingly in the **tributary arms and creeks** that the chart does not cover, not on the mainstem. By basin class: mainstem 6 of 1,009 unavailable (0.6 %), large tributary arms 1,056 of 2,251 (46.9 %), minor tributaries 1,023 of 3,154 (32.4 %), unclassified 48 of 90. The largest regions are Mud Creek 479, Town Creek 281, Crow Creek 249, North Sauty Creek 178, Browns Creek 145, Long Island Creek 103. The mechanism (the IENC covers the navigable waterway and adjacent water; side embayments are outside the compiled depth areas) is an **inference from where the gaps are**; I did not find a USACE statement of the compile limits for Guntersville. Because the Encoding Guide asks that all navigable water bodies be covered by a depth object, the gaps are consistent with the embayments not being treated as navigable waterway.

The shapefile trap in the Phase 1-3 handoff is real in that it hides an upper-lake cell: `U37TN391_SHAPE.zip` carries no data, consistent with the S-57 route chosen. Not re-tested here.

## 7. Can it support a measured threshold zone, and with what uncertainty

A **measured threshold zone** here would mean "inside the 9 ft contour at reference pool". What the evidence supports:

* The **line** is measured (2007 echo-sounder, ZOC B, +-50 m). The **zone** shoreward of it is the residual class, so the data support "shoreward of the charted 9 ft contour", not "water shallower than 9 ft at every point in the zone".
* It supports it only for the 67 % of shoreline the chart reaches. Outside, the statement is "unknown", never "deep" and never "shallow". (The shipped data already treats unavailable as unknown; keep that.)
* Vertical meaning of the threshold: **9 ft below an unspecified local low-water plane, +-1.05 m nominal (ZOC B), plus an unresolved reference-plane offset of up to about 2 ft** (593 vs 595 ft candidates, section 3). Combined (+-3.5 ft vertical accuracy plus up to 2 ft of unresolved reference offset), the threshold is not better known than roughly +-3.5 to 5.5 ft in the worst case, which is large against the 0 to 9 ft band it bounds. That is why no depth value should be derived from it.
* Horizontal: +-50 m for the line; add for 19 years of sedimentation and bank change (not quantified).

## 8. Does the contour move with pool level, and is level adjustment valid

The chart contour is a line fixed in space (the intersection of the bed with the reference plane, minus 9 ft). The **actual** 9-ft-deep line moves when the pool moves. If Z_ref is the reference plane and the pool is P, the "9 ft deep now" line sits where the bed is at P minus 9; the chart line is where the bed is at Z_ref minus 9. At P below Z_ref the 9 ft line moves toward the channel by (Z_ref minus P) divided by the local bed slope; at P above Z_ref it moves shoreward.

* Magnitude is not computable here: there is **no bathymetric surface** to give a slope, and I did not extrapolate one. Illustration of the geometry only: the Guntersville pool spans 593.2 to 595.2 ft between p01 and p99 (2.0 ft, 0.61 m). The shift stays under the +-50 m ZOC B line uncertainty wherever the local bed slope between the contours is steeper than about 1.2 % (0.61 m over 50 m). It exceeds it on flatter bottoms, which are exactly the shallow flats that matter. The slope is unmeasured.
* **Level adjustment is not valid in absolute terms** because Z_ref has no published elevation. It is valid only in a **relative** sense, as a statement of difference (for example "the pool is 1.1 ft below the winter-summer reference of 595 ft, so the 9 ft line is not where it was when the lake is at 595"), and only with the offset between Z_ref and Sector's 595 ft stated as unresolved.
* The Guntersville case is benign relative to other lakes because of the narrow operating range (the effective-depth research measured a 4.0 ft flat staying between 1.8 and 4.9 ft over 2005 to 2026), but benign is not valid.

## 9. What this asset can and cannot be used for

Evidence class: **PARTIAL MEASURED CONTOUR EVIDENCE, tier C-limited.** Measured: the position of one contour (+-50 m, ZOC B, 2007), at one named datum code. Not measured: any depth surface, any depth between 0 and 9 ft, any depth above 9 ft, any point in the uncharted 18 % of the area, any stage-specific depth.

| Use | Verdict | Condition / wording |
|---|---|---|
| Statement "this shoreline lies inside the charted 9 ft (2.74 m) contour (IENC 2007, ZOC B)" | **Can** | Only on the 67.2 % classified segments; always with chart vintage |
| Segment class `shallow` = "shoreward of the 9 ft contour, shallower than 9 ft or not surveyed" | **Can**, with caveat | Do not describe it as a measured shallow zone; wording must keep "or not surveyed" |
| Segment class `deep` = "shore adjoins water charted deeper than 9 ft" | **Can** | 312 segments, 62.4 km; low in count |
| Distance from a shoreline point to the 9 ft contour | **Can**, with +-50 m and 2007 vintage | Distance only; not a slope or depth |
| `unavailable` as unknown | **Can** (already so) | Never convert to deep or shallow; never to a depth number |
| Min / max / mean depth, slope, depth between contours | **Cannot** | No soundings, no other contours |
| Depth in feet at a point, or "X ft deep" | **Cannot** | Single contour only |
| Absolute level adjustment (e.g. "9 ft contour at 593 ft pool is ...") | **Cannot** | Reference elevation unpublished |
| Relative pool-difference note ("pool is N ft below 595") alongside the chart | **Can** | Must not move or redraw the contour |
| Extrapolating the 9 ft contour into bathymetry (infill, interpolation, DEM) | **Cannot** | Not done; not to be done |
| Treating the 33 % unavailable as deep because it adjoins deep water, or as shallow | **Cannot** | Unsurveyed tributary arms |
| Habitat / structure inference ("flat", "drop", "ledge") | **Cannot** | No surface; one line |
| Validating a modelled depth proxy (GLOBathy, DEM slope) at the 9 ft line | **Can**, as a single-threshold sanity check | Pass/fail on one isobath, with +-50 m / +-3.5 ft tolerance; a weak test |
| Use in navigation | **Cannot** | USACE: only ienccloud.us charts in an ECDIS/ECS are suitable for navigation |

## 10. Recommendations for the foundation (no code changed)

1. Record the asset in the Depth Brain evidence ledger as `PARTIAL_MEASURED_CONTOUR_EVIDENCE` (tier C-limited) with fields: `contourValueM 2.74`, `datumCode 31`, `datumName "IENC local low water reference level"`, `datumElevationFt null (unpublished)`, `surveyYear 2007 (deep polygons 2008)`, `zoc B`, `positionToleranceM 50`, `verticalToleranceM 1.05`, `coveragePct 82.3 area / 67.2 segments`, `coverageDefinition "inside a charted DEPARE"`.
2. Correct the `LakeRegistry.swift` bathymetry coverage text: 67.2 % classified (4,059 shallow, 312 deep), 32.8 % (2,133) unavailable; stop equating "fixedBuffer" with "unmeasured".
3. Ask USACE (IENC_POC@usace.army.mil) for the elevation of the Tennessee River IENC low-water reference level and the 2007/2008 survey reports; this is the single question that would upgrade level handling.
4. Re-pull the IENC on the semi-monthly update cycle; the 2014 and 2020 pieces show Nashville District feeds new channel surveys into the cells, and a re-survey would be the first real upgrade of this asset.
5. Do not ship any wording that treats the polygon as a "measured shallow zone" or that gives a depth number.

## 11. Not verified

* The elevation of the IENC local low-water reference level for Guntersville (not published in any file read).
* The survey day, instrument and vertical control of the 2007/2008 USACE surveys (no survey report found).
* Guntersville sedimentation since 2007.
* The compile rule that left tributary embayments uncharted (inferred from the gap pattern).
* The mile range of cell U37TN361 (not read).
* The ZOC B accuracy figures come from the IHO table reproductions (TeledyneCARIS, Kartverket), not the guide's embedded image.
