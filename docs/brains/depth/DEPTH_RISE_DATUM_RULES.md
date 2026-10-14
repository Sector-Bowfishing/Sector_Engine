# Depth Brain: USBR RISE datum rules

> **UPDATE 2026-10-14 (long-run campaign): the residual link (RISE value = the dam gage record the survey describes) was tested with Reclamation's own data.** RISE daily elevation reproduces RISE daily storage through the TSC survey tables (offset 0.00 ft, relative RMS <= 0.0002 for Cheney, Bighorn, El Vado, Elephant Butte, Heron, Navajo, Patterson, Tschida, Calamus) and the Great Plains allocation diagrams (pool figure printed on the diagram; Angostura, Boysen, Fresno, Keyhole, Merritt, Pactola, Pathfinder at <= 0.036 ft). 16 lakes are now `SAME_SOURCE` (project frame, never converted); see `DEPTH_RECLAMATION_DATUM_CHAIN.md`. Section 7's request is narrowed in `DEPTH_RECLAMATION_DATUM_REQUEST.md`.

Date 2026-10-14. Research only: nothing deployed, written to RTDB, sent or committed. Raw downloads are outside git in `~/Desktop/Development/Sector_Research_Data/depth-brain/datum3/{rise,tsc,pdf}`. Machine-readable twin: `jobs/depth-brain/depth_brain/data/proposals/provider_rules.json` (schema `depth-provider-proposals-v1`). Extends section 3.4 of `DEPTH_DATUM_AUDIT.md`.

Evidence labels: **[fetched]** I fetched it on 2026-10-13/14 and it says this. **[computed]** derived from fetched live data. **UNKNOWN** is not established. Document statements are paraphrased, with the file named so they can be re-read.

## 1. Bottom line

* The 46 `rise` candidate rows are **45 distinct RISE series** (Flaming Gorge is bound twice, as UT and WY; one series, item 341). All 45 are parameter 2, "Lake/Reservoir Elevation", daily instant, and **none declares a series datum** (catalog-item `verticalDatum` is null for 45 of 45).
* **No provider-level rule is defensible.** The RISE parameter text says elevations are feet above msl "for the location specified datum", but the location `verticalDatum` it points to is demonstrably an attribute of a site point, not of the reservoir gage (section 4).
* **A real datum source exists, per reservoir.** Reclamation's Technical Service Center (TSC) survey and area-capacity reports state, reservoir by reservoir, that the Reclamation dam gage record, the allocation elevations and the pool figure are all on one local **Reclamation Project Vertical Datum (RPVD, "project datum")**, and often give its offset to NGVD29/NAVD88. A shift needs only that level and pool share a datum, not the datum's absolute name.
* **Proposed unlock: 18 of 45 series (19 of 46 candidate rows)** are documented as gage-and-pool on one project datum (tier A). 8 are partial (tier B), 19 stay UNKNOWN (tier C), including three where Reclamation's own records conflict (Shasta, Trinity, Mohave).
* One link is **not** documented and is the stated residual of every tier-A rule: that the RISE daily value for the reservoir is the dam gage record the survey reports describe. RISE's own metadata for these series says only "Reservoir Forebay Elevation" (Great Plains), or "Lower/Upper Colorado Hydrologic Database" (it names no gage). Confirm once with Reclamation (section 7) before this leaves the proposal stage.
* Project datums must **never** be converted with NCAT/VERTCON (they are not NGVD29 or NAVD88, offsets run from 0.1 to 45 ft). Where a survey gives an offset it is recorded for information only.

## 2. RISE parameter semantics (the one id used by every binding)

All 45 bound series are catalog items with `parameterId` 2. [fetched] `/rise/api/parameter/2`:

| Field | Value |
|---|---|
| parameterName / group | Lake/Reservoir Elevation |
| unit, timestep, transformation | ft, daily, instant ("one measurement per day") |
| description | elevation "is typically reported as feet above mean sea level (msl) for the location specified datum" |

Sibling ids exist but are **not** used by any binding: 1748 (sub-daily instant elevation), 1834 (daily average), 1747 (end-of-month instant). A binding must not substitute one for another without re-reading the description: daily average vs instant matters for a shift against a pool.

Result rows [fetched, 2025-10-01 to 2026-10-13, 45 series, 19,850 rows]: `result` is a float or null; `status` is null on every row; `resultAttributes.resultType` is `observed` for the Upper and Lower Colorado series and absent for Great Plains and Mid-Pacific. There is no quality flag to filter on.

## 3. Catalog, location and asset metadata

| Item | Finding [fetched / computed] |
|---|---|
| Series datum | catalog-item `verticalDatum` null for 45 of 45 |
| Source authority (catalog `sourceCode`) | GPHYDROMET 25 series (Great Plains Hydromet), uchdb2 16 (Upper Colorado Hydrologic Database), lchdb2 3 (Lower Colorado Hydrologic Database), HAR 2 (Mid-Pacific, California-Great Basin) |
| Null placeholders | 1 null in 19,850 rows: Elephant Butte 2026-08-06. No other nulls |
| Zero placeholders | none (0 zero values; the series minima are 446 to 7,680 ft) |
| Latency | 2026-10-13: 39 series end 2026-10-12, 3 end 2026-10-11 (Jordanelle, Starvation, Strawberry), 2 end 2026-10-08 (Deer Creek, Pineview), 1 ends 2026-10-09 (Waconda). Daily, normally one day behind, up to 5 days |
| Record description | Lower Colorado records say "Location elevation reported top of spillway/max pool elevation" (Havasu, Mead, Mohave only); all others give no meaning for the location `elevation` |
| Location `verticalDatum` | across the 45 series: EGM96 15, NGVD29 11, NAVD88 5, USGS 1912 2, none 12. Lake Powell location elevation 3596 vs pool 3700; Bighorn 3200 vs 3640; Horsetooth 5300 vs 5430: the location elevation is a dam/site attribute |
| "Asset" record (Internet of Water RISE EDR join of Reclamation reservoir assets, `api.wwdh.internetofwater.app/collections/rise-edr/items/<locationId>`) | carries capacity elevations for 41 of 45 reservoirs and a `Vertical Datum` label for 16, often a project datum with an offset note (Fresno +4.7 ft vs NGVD29, Waconda +1.2, Caballo/Elephant Butte -43.3, Heron NGVD29 and 4.3 below NAVD88, Glendo ~2.55 below NAVD88, Havasu/Mead/Mohave USGS 1912 +0.55 to NGVD29). **Its capacity elevation is not always the pool**: Great Plains assets list top of flood control (Pactola 4621.5, Glendo 4653) and Mead lists the max water surface 1229 while the pool (top of joint use) is 1219.6 |

Treat the asset record as a pointer to a datum statement, not as the pool.

## 4. Why the location `verticalDatum` cannot be the series datum

The parameter text points at "the location specified datum". Three checks show the location tag is not reliable for the reservoir gage:

1. **Cheney**: RISE location tags NAVD88 (elevation 1419.81). Reclamation's 2015 Cheney survey says the reservoir operates on a project datum that coincides with NGVD29, NGVD29 being 0.479 ft below NAVD88.
2. **Bighorn**: location NAVD88; the 2017 survey says the Yellowtail gage is on RPVD, assumed equal to NGVD29, with NAVD88 2.63 ft above.
3. **Mohave / Shasta / Bighorn / Trinity**: the location says NAVD88 while the asset record for the same site says USGS 1912 (Mohave) or NGVD 29 (Shasta, Trinity, Bighorn). Two Reclamation records for one site disagree.

"EGM96" (15 locations) is an Earth gravitational (geoid) model, not a vertical datum for a reservoir staff gage; it must be read as "unset".

## 5. How Reclamation defines the pool figure, and the datum behind it

* Great Plains `resaloc` reservoir-allocation diagrams (one slide per reservoir, 2012-2015 revisions) label **Top of Active Conservation** (or Top of Joint Use, Maximum Surface). They print the elevations as plain "Elev." with **no datum text**: 18 of 18 pulled diagrams contain none.
* Reclamation's reservoir-capacity form (7-1686) lists conservation / flood-control / joint-use tops; the Lake Mead 2022 allocations sheet states top of active conservation by looking up capacity, "rounded to 1,219.64 ft" (Mead directory pool 1219.6), maximum water surface 1,229.0. No datum text.
* The datum is stated in the TSC survey reports for the same reservoir, where the pool appears as, for example, "top of active conservation 6040.0 ft (RPVD)", "top of joint-use 7519.4 ft RPVD", "spillway 6085 ft (project vertical datum)", "top of active storage 4407 ft (project vertical datum)". This is the document chain used for tier A.
* Regional notes. **Great Plains**: project datums are close to NGVD29 (offsets to NAVD88 0.5 to 2.6 ft); Waconda and Fresno are *above* NGVD29 (1.2 and 4.7 ft). **Upper Colorado**: project datum is a true local datum, much lower than NGVD29/NAVD88 at Elephant Butte/Caballo (43 to 45 ft), El Vado (7.8 to 12.0 ft) and Blue Mesa (4.7 ft below NAVD88); Flaming Gorge's 2019 survey could not confirm RPVD equals NGVD29. **Lower Colorado**: Hoover/Davis/Parker are on the USGS 1912 "Powerhouse" datum, 0.55 ft below NGVD29 (Reclamation 2001 Mead survey and 2009 LiDAR report; RISE asset). **Mid-Pacific**: Folsom (not a candidate) and Millerton surveys use a project datum 2.3 to 2.6 ft below NAVD88; Shasta and Trinity conflict (section 4). **Pacific Northwest** is not RISE-bound here (see `usbr-pnhm` below).

## 6. Per-series classification (45 series)

Tier A = a Reclamation document gives the dam gage record **and** the pool in one project datum. B = part of that, or a datum relation without the link. C = nothing usable or documents conflict. Columns: RISE item, source code, RISE location tag, RISE asset datum, directory pool (ft), tier, evidence.

| Lake | RISE item | Source | Location tag | Asset datum | Pool | Tier | Evidence / what is missing |
|---|---|---|---|---|---|---|---|
| Angostura Reservoir (SD) | 106 | GPHYDROMET | NGVD29 | - | 3187.2 | **A** | original project datum reported as NGVD29; ~2 ft below NAVD88 (2004 survey) |
| Bighorn Lake (WY) | 164 | GPHYDROMET | NAVD88 | NGVD 29 | 3640 | **A** | RPVD assumed equivalent to NGVD29; NAVD88 minus NGVD29 = 2.63 sft at Yellowtail Dam (2017 tables) |
| Box Butte Reservoir (NE) | 142 | GPHYDROMET | NGVD29 | NGVD 29 | 4007 | **A** | project water-surface gage datum tied to NGVD29; 2.0 ft below NAVD88 (2003 survey) |
| Cheney Reservoir (KS) | 133978 | GPHYDROMET | NAVD88 | - | 1421.6 | **A** | project datum coincides with NGVD29; NGVD29 is 0.479 ft below NAVD88 (2015 survey) |
| Fresno Reservoir (MT) | 355 | GPHYDROMET | NGVD29 | Project Datum | 2575 | **A** | project datum 4.7 ft above NGVD29 and 2.0 ft above NAVD88 (2010 survey; NOT the RISE location NGVD29 tag) |
| Jamestown Reservoir (ND) | 451 | GPHYDROMET | NGVD29 | - | 1431 | **A** | project datum tied to NGVD29; NGVD29 is 1.25 ft below NAVD88 (2009 survey) |
| Keyhole Reservoir (WY) | 478 | GPHYDROMET | NGVD29 | - | 4099.3 | **A** | project datum reported as NGVD29; 2.1 ft below NAVD88 (2003 survey) |
| Lake Tschida (ND) | 550 | GPHYDROMET | NGVD29 | - | 2064.5 | **A** | project datum 0.2 ft below NGVD29 and 1.7 ft below NAVD88 (2013 survey; capacity table: gage datum = NAVD88 - 1.7) |
| Merritt Reservoir (NE) | 599 | GPHYDROMET | - | - | 2946 | **A** | project datum tied to NGVD29, ~1.0 ft below NAVD88 (2003 survey) |
| Patterson Lake (ND) | 305 | GPHYDROMET | NGVD29 | - | 2420 | **A** | project datum 0.1 ft below NGVD29 and 1.9 ft below NAVD88 (2013 survey; capacity table: gage datum = NAVD88 - 1.9) |
| Blue Mesa Reservoir (CO) | 78 | uchdb2 | EGM96 | - | 7519.4 | **A** | RPVD is 4.71 ft below NAVD88 (2019 area-capacity tables) |
| Caballo Lake (NM) | 212 | uchdb2 | EGM96 | Project Datum | 4172.44 | **A** | project datum 43.3 ft below NGVD29 and 45.5 ft below NAVD88 (2007 survey) |
| El Vado Lake (NM) | 336 | uchdb2 | EGM96 | Project Datum | 6902 | **A** | project datum ~7.8 ft below NGVD29 and 12.0 ft below NAVD88 (2007 survey; add 7.8 ft to reach NGVD29) |
| Elephant Butte Reservoir (NM) | 332 | uchdb2 | EGM96 | Project Datum | 4407 | **A** | project datum ~43.3 ft below NGVD29 and 45.5 ft below NAVD88 (2007 survey); 2017/2019 tables: RPVD 45.0 ft below NAVD88, NGVD29 2.1 ft below NAVD88 (the two reports differ by 0.5 ft) |
| Flaming Gorge Reservoir (UT) | 341 | uchdb2 | EGM96 | - | 6040 | **A** | RPVD defined; the 2019 survey states CorpsCon results were inconclusive on whether RPVD equals NGVD29 (absolute datum NOT established) |
| Flaming Gorge Reservoir (WY) | 341 | uchdb2 | EGM96 | - | 6040 | **A** | RPVD defined; the 2019 survey states CorpsCon results were inconclusive on whether RPVD equals NGVD29 (absolute datum NOT established) |
| Fontenelle Reservoir (WY) | 349 | uchdb2 | EGM96 | - | 6506 | **A** | RPVD; offset to NAVD88/NGVD29 not extracted from the 2019 survey |
| Heron Lake (NM) | 421 | uchdb2 | EGM96 | NGVD 29 | 7186.1 | **A** | project datum tied to NGVD29; 4.278 ft below NAVD88 (2010 survey) |
| Navajo Reservoir (NM) | 612 | uchdb2 | EGM96 | - | 6085 | **A** | RPVD is 2.97 ft below NAVD88 (2019 area-capacity tables) |
| Buffalo Bill Reservoir (WY) | 152 | GPHYDROMET | - | - | 5393.5 | **B** | 1986 survey on 'Shoshone Project Datum'; conversion to USC&GS datum printed but text garbled; missing: gage statement absent; 1986 datum may have been superseded |
| Calamus Reservoir (NE) | 215 | GPHYDROMET | NGVD29 | NGVD 29 | 2244 | **B** | project datum near NGVD29, 0.84 ft below NAVD88 (2012 report); missing: report pool wording (morning-glory crest 2,244.5) and gage statement not matched to 2,244 |
| Glendo Reservoir (WY) | 374 | GPHYDROMET | NGVD29 | Project Datum | 4635 | **B** | project datum ~2.55 ft below NAVD88 (2003 survey); missing: gage-to-datum statement not found; RISE asset says project datum |
| Shadow Mountain Reservoir (CO) | 738 | GPHYDROMET | - | - | 8367 | **B** | RPVD (offset not extracted); missing: pool 8367 wording not found in the survey |
| Swanson Reservoir (NE) | 134012 | GPHYDROMET | NGVD29 | NGVD 29 | 2752 | **B** | project datum tied to NGVD29, 1.1 ft below NAVD88 (2011 report); missing: gage statement not found |
| Waconda Lake (KS) | 841 | GPHYDROMET | - | Project Datum | 1455.6 | **B** | project datum ~1.2 ft above NGVD29 (2001 survey; RISE asset: RPVD is 1.2 ft greater than NGVD29); missing: no document found that says the dam gage record is on the project datum |
| Havasu (AZ) | 6128 | lchdb2 | USGS 1912 | Other | 450 | **B** | RISE asset record: elevations on USGS 1912/Powerhouse datum (+0.55 ft to NGVD29); location tag agrees; missing: no TSC survey fetched; no gage statement |
| Lake Mead (NV) | 6123 | lchdb2 | USGS 1912 | Other | 1219.6 | **B** | dam construction (Powerhouse/USGS 1912) datum: add 0.55 ft to reach NGVD29 (2001 survey, 2009 LiDAR report, RISE asset); missing: no document ties the Hoover dam gage/RISE series to the construction datum |
| Alcova Reservoir (WY) | 114 | GPHYDROMET | - | - | 5498 | **C** | no TSC datum document; Annual Operating Plan gives 'feet msl' only |
| Boysen Reservoir (WY) | 196 | GPHYDROMET | NGVD29 | - | 4725 | **C** | 1994 survey fetched states no datum; no gage statement |
| Grand Lake (CO) | 372 | GPHYDROMET | - | - | 8367 | **C** | no reservoir document; pool is a natural-surface directory figure (low confidence) |
| Horsetooth Reservoir (CO) | 87 | GPHYDROMET | - | - | 5430 | **C** | no TSC datum document downloaded; resaloc diagram states no datum |
| Lake Granby (CO) | 384 | GPHYDROMET | - | - | 8280 | **C** | no TSC datum document downloaded; resaloc diagram states no datum |
| Pactola Reservoir (SD) | 675 | GPHYDROMET | - | - | 4580.2 | **C** | resaloc diagram states no datum; no TSC document downloaded |
| Pathfinder Reservoir (WY) | 645 | GPHYDROMET | - | - | 5852.49 | **C** | only a combined Pathfinder/Seminoe sedimentation PDF exists (64.8 MB, not fetched) |
| Ruedi Reservoir (CO) | 712 | GPHYDROMET | - | - | 7766 | **C** | no TSC datum document downloaded; resaloc diagram states no datum |
| Seminoe Reservoir (WY) | 733 | GPHYDROMET | - | - | 6357 | **C** | only a combined Pathfinder/Seminoe sedimentation PDF exists (64.8 MB, not fetched) |
| Lake Mohave (NV) | 6133 | lchdb2 | NAVD88 | Other | 647 | **C** | RISE asset record says USGS 1912 datum but the RISE location tags the same site NAVD88; unresolved conflict |
| Shasta (CA) | 10863 | HAR | NAVD88 | NGVD 29 | 1067 | **C** | RISE asset says NGVD 29, RISE location says NAVD88; no survey fetched |
| Trinity (CA) | 10853 | HAR | NAVD88 | NGVD 29 | 2370 | **C** | RISE asset says NGVD 29, location NAVD88; asset capacity elevation 2345 differs from pool 2370 |
| Deer Creek Reservoir (UT) | 293 | uchdb2 | EGM96 | - | 5417 | **C** | no datum document fetched |
| Jordanelle Reservoir (UT) | 471 | uchdb2 | EGM96 | - | 6166.4 | **C** | no datum document fetched; RISE asset TCE 8182 is a typo-level conflict with pool 6166.4 |
| Lake Powell (UT) | 508 | uchdb2 | EGM96 | - | 3700 | **C** | USGS 2021 Glen Canyon survey exists because of uncertainty in Reclamation's local datum; USGS 2018 capacity release is NAVD88; no statement ties the RISE series to either |
| Pineview Reservoir (UT) | 656 | uchdb2 | EGM96 | - | 4900 | **C** | no datum document fetched; RISE location tag EGM96 is not a reservoir-gage datum |
| Starvation Reservoir (UT) | 767 | uchdb2 | EGM96 | - | 5712 | **C** | RISE asset says 'Local Datum'; no relation given |
| Strawberry Reservoir (UT) | 782 | uchdb2 | EGM96 | - | 7602.4 | **C** | no datum document fetched |
| Willard Bay Reservoir (UT) | 869 | uchdb2 | EGM96 | - | 4226 | **C** | no datum document fetched |

TSC report base URL: `{T}` = `https://www.usbr.gov/tsc/techreferences/reservoir/<file>` (file names are in the JSON twin, per lake).

### Counts a documented rule would unlock (45 distinct series)

| Region (legacy RISE) | A (unlock) | B | C | Total |
|---|---|---|---|---|
| Great Plains | 10 | 6 | 9 | 25 |
| Upper Colorado | 8 | 0 | 7 | 15 |
| Lower Colorado | 0 | 2 | 1 | 3 |
| Mid-Pacific | 0 | 0 | 2 | 2 |
| **Total** | **18** | **8** | **19** | **45** |

Candidate-row view: 19 of 46 (Flaming Gorge UT and WY).

Tier A lakes: Angostura, Bighorn, Blue Mesa, Box Butte, Caballo, Cheney, El Vado, Elephant Butte, Flaming Gorge (UT, WY), Fontenelle, Fresno, Heron, Jamestown, Keyhole, Merritt, Navajo, Tschida, Patterson. Tier B: Waconda, Glendo, Calamus, Swanson, Mead, Shadow Mountain, Buffalo Bill, Havasu. Tier C: Mohave, Shasta, Trinity, Grand Lake, Horsetooth, Granby, Ruedi, Boysen, Alcova, Pathfinder, Seminoe, Pactola, Powell, Pineview, Willard Bay, Deer Creek, Jordanelle, Starvation, Strawberry.

### Plausibility screen on tier A (computed)

Over 2025-10-01 to 2026-10-13 no one of the 45 series rose more than 4.1 ft above its directory pool (Cheney +4.1, Jamestown +2.2, Waconda +1.4, all flood-pool lakes), so no series shows a large positive datum mismatch. Drawdown lows are far below pool by design (Powell -183 ft, Mead -182 ft, Elephant Butte -132 ft). The project-datum chain predicts that Elephant Butte and Caballo read about 43 ft below NGVD29 values; their readings against their project-datum pools (4295.6 vs 4407, 4138.9 vs 4172.44) are consistent with that, and they would be 43 ft off if the pool were NGVD29. This is *consistent with* the document chain, not proof of it.

## 7. Open items, caveats and the exact Reclamation confirmation needed

Caveats attached to every tier-A rule:

1. **Residual link**: the RISE daily series is the dam gage record in the survey's datum. Not documented in RISE.
2. **Age of the reports** (1979 to 2019). A re-datum after the report would move the gage and the pool together only if Reclamation changes both; Elephant Butte already shows two offsets (45.5 ft in 2007, 45.0 ft in 2019).
3. **Patterson**: the 2013 report labels a 2,420 contour NAVD88; if that were the true pool the project-datum pool is ~2,418.1. Drop to B until confirmed.
4. **Pool-basis issues are separate from datum**: Bighorn pool 3640 is top of *joint use* (top of active conservation is 3614); Mead 1219.6 is top of joint use, 1229 is max water surface; Waconda and Jamestown flood pools exceed the pool; Trinity's asset capacity elevation 2345 differs from the directory 2370.

Confirmation to request from Reclamation (not sent): *"For RISE daily Lake/Reservoir Elevation series (catalog items listed), is the value the dam water-surface gage reading, and is it expressed in the Reclamation Project Vertical Datum (RPVD / project datum) described in the reservoir's current TSC area-capacity tables? Are the 'Top of Active Conservation' / joint-use elevations on the allocation diagrams in the same datum? Please confirm for the 18 tier-A reservoirs and state the datum, with offset to NAVD88, for the 19 tier-C reservoirs, and say which of the RISE location vs asset vertical-datum fields is authoritative (Shasta, Trinity, Bighorn, Mohave conflict)."* If confirmed in writing, move tier A to `verified_doc`, and tier B/C lakes follow as each datum statement is provided.

## 8. What stays blocked and the external evidence needed

| Group | Count | Blocked because | Needed |
|---|---|---|---|
| RISE tier A | 18 | link between RISE value and project-datum gage not documented | one Reclamation written confirmation (section 7) |
| RISE tier B | 8 | gage or pool link undocumented (Waconda, Glendo, Calamus, Swanson, Mead, Shadow Mountain, Buffalo Bill, Havasu) | gage-datum statement per reservoir |
| RISE tier C | 19 | no datum document or documents conflict | reservoir datum statement; for Powell, the outcome of the 2021 USGS Glen Canyon datum survey |

## 9. Related Reclamation groups (not RISE-bound; brief)

* **Lake Roosevelt (FDR), `cwms-nwdp`**: the 2010-11 Reclamation survey and capacity tables state the Grand Coulee project datum is NGVD29 (adjusted 1947) and about 2.5 ft below NAVD88, with spilling elevation 1,290 ft (project datum). The level is a USACE CWMS `Elev-Forebay` series; whether CWMS carries the project datum is not documented. UNKNOWN until the CWMS location datum tag is compared (the RISE location record for FDR tags NGVD29).
* **Pacific Northwest hydromet (`usbr-pnhm`: Cascade, Crescent OR, Banks, Potholes)**: Cascade's 1995 survey says Reclamation levels are 0.66 ft above the U.S. Coast and Geodetic Survey datum; the Roosevelt survey mentions a Banks Lake gage-to-NAVD88 shift (value truncated in text extraction). No gage statement for the hydromet FB series. UNKNOWN; same method as tier B.
* **CDEC (Almanor PG&E, Berryessa USBR)**: CDEC station pages state no datum; Almanor's RES_ELE arrives via the PG&E data exchange. UNKNOWN.
