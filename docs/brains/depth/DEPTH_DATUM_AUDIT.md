# Depth Brain: Vertical Datum Audit

Date 2026-10-13. Research only; nothing deployed or sent. Machine-readable twin: `jobs/depth-brain/depth_brain/data/datum_providers.json` (schema `depth-datum-providers-v1`).

Question: when may `currentLevel - referencePool` (the depth shift) be computed? Only when both numbers are in the same vertical datum. This audit establishes, per Lake Brain provider, what datum the live series is in, whether the "full pool" figure is a true elevation in that datum, and what is known about datum changes.

Evidence labels: **[fetched]** = I fetched the URL or API on 2026-10-13 and it says this. **[computed]** = derived from fetched live data. **[project note]** = recorded by an earlier thread in `Sector_Engine-depth-research/docs/data/full_pool.csv` and not re-fetched here (treat as unverified). **UNKNOWN** = not established.

## 1. Executive summary

### Provider counts (28 providers in `verified_bindings_v2.csv`, 427 bound rows)

| Class | Providers | Bound rows |
|---|---|---|
| Verified from a document or API metadata | 13: a2w, cwms, cwms-saw, cwms-nwdp, usgs, usgs-d, coops, sjrwmd, twdb, nipsco, njwsa, aep, alliant | 289 |
| Inferred (consistent evidence, no operator statement) | 3: tva, duke, cdec | 27 |
| Unverified / UNKNOWN | 12: nwps, rise, usbr-pnhm, nhdes, srp, cnppid, eccc, mncsg, nppd, utahlake, nwrfc, wps-hydro | 111 |

"Verified" for a2w, cwms, usgs, usgs-d means the metadata *channel* is verified, not that every lake resolves: 22 of 112 bound A2W lakes and 3 CWMS lakes are tagged LOCAL, 2 A2W lakes are blank, and 14 USGS lakes are on parameter 00062 (datum per site, unresolved). Every `nwps` row and every `rise` row is datum-UNKNOWN until proven per lake.

### Rules a shift engine must follow

1. **Never subtract two numbers unless a rule below says they share a datum.** Default is suppress (`datumUnreconciled`).
2. **Same source wins.** A CWMS/A2W level (Top of Conservation, Top of Normal, Top of Multi-Purpose, Guide Curve) at the same location as the Elev series is stored in that location's one `vertical-datum`; the shift is exact whatever the tag says, including LOCAL. Same for TVA operating-guide pool vs TVA reading, SRP "remaining available" pools, and an operator table that publishes level and full pool together.
3. **Same stated datum is next best.** Both NGVD29, both NAVD88, or both the same named local datum (NIPSCO local, PG&E, Saluda Plant, Pensacola) with each stated in a document or metadata field.
4. **NGVD29 vs NAVD88 is convertible**, but only with NCAT/VERTCON (sigma 0.23 ft, from the earlier NCAT test point) or, better, the operator's own factor (NJWSA 0.8 ft; Kentucky Dam 0.2 ft; USGS paired series). The fleet shift is median 0.64 ft absolute, 31 percent above 1 ft, max 5.4 ft; USBR lakes median 3.1 ft. Skipping conversion where datums differ gives an error as large as the shift signal.
5. **LOCAL, project, plant and utility datums are never converted with NCAT.** Convert only with the operator's published offset, otherwise UNKNOWN.
6. **The tag LOCAL does not tell you NGVD29 vs NAVD88.** Same-source comparison is fine; cross-source is UNKNOWN.
7. **USGS 00062 is not NAVD88.** Use 62614 (NGVD29) or 62615 (NAVD88), or fix the 00062 offset empirically from a paired 62615/62614 series at the same instant. 00065 is gage height, not elevation.
8. **Series datum can change inside a history.** Documented: NJWSA 2025-11-19; USGS NAVD88 mandate (deadline 2023-01-27); IGLD85 to IGLD2020 (tentative 2027). Any history spanning such a date needs a datum-by-date field.
9. **Plausibility guard on every pair:** `|level - pool|` outside the lake's operating range (for example 100 vs 760, or 56.7 vs 1,354) is a scale/datum mismatch, not a shift. Flood-control lakes can legitimately be 15 to 50 ft above pool; a 100+ ft gap never is.
10. **Pool must be a true elevation.** Duke's "100 = full pond" is a scale, not an elevation (see Duke).

### The traps found (all evidence below)

| # | Trap | Evidence |
|---|---|---|
| T1 | USGS 00062 differs from NAVD88 by 0.16 to 6.88 ft, in both directions, and `alt_va` does not give the offset | Section 3.5 |
| T2 | NWS NWPS datum tables contradict observed values (Lake Marion PNVS1 says NAVD88 0 but reads the 00062 scale); 27 of 43 bound gauges have empty tables | Section 3.6 |
| T3 | USACE tag LOCAL means NGVD29-valued at Kanopolis and NAVD88-like at Rathbun | Section 3.2 |
| T4 | RISE publishes no series datum (all 46 catalog items null); the location `verticalDatum` is a site-elevation attribute with mixed EGM96/NGVD29/NAVD88/"USGS 1912" | Section 3.4 |
| T5 | Duke series is a 100-based scale; a naive `level - fullPoolFt` gives about -660 ft | Section 3.3 |
| T6 | NJWSA switched NGVD29 to NAVD88 on 2025-11-19 (0.8 ft step in a continuous history) | Section 3.8 |
| T7 | Santee Cooper pool (75.5) is on the gauge scale that USGS calls 00062; the USGS NAVD88 series reads 0.88 (Marion) / 0.99 (Moultrie) ft lower | Section 3.5 |
| T8 | HP-coded NWPS series can be a local stage (Lake Vermilion reads 56.74 ft); HG-coded ones can be elevations (Liberty Reservoir 410.88) | Section 3.6 |
| T9 | Operator footnote errors: IDNR says NAVD88 for Eagle Creek, readings are NGVD29 [project note]; Lake Bistineau LDWF says NGVD, CWMS tag is NAVD88 | Section 3.9 |
| T10 | CWMS API `datum` parameter is documented unsupported for v2 JSON and had no effect in a live test | Section 3.2 |
| T11 | CWMS locations can be STREAM_LOCATION/SITE kinds with their own datum tag (Rend, Wappapello, Cross, Bistineau, Milton) | Section 3.2 |
| T12 | USGS `alt_va` and the operator disagree at Lake Hopatcong (914.5 NAVD88 vs plan gauge datum 914.57 NGVD29) | Section 3.5 |

## 2. Reference pool sources (`full_pool.csv`, 425 rows)

Datum implied by each distinct `source` pattern (count of rows). Machine form: `referencePoolSources` in the JSON.

| Source pattern | Rows | Implied datum | Basis |
|---|---|---|---|
| CWMS location level (`Top of Conservation`, `Top of Normal`, `Top of Multi-Purpose`, `Guide Curve`, `Top of Power`) | ~150 | the CWMS location's own `vertical-datum` (same datum as the same-location Elev series) | verified [fetched] |
| usbr.gov project / resaloc / AOP pages | 62 | UNKNOWN; document rarely states a datum. Notes say "Datum per USBR RISE" but RISE declares none | unverified |
| pubs.usgs.gov Water Data Reports | 26 | station gage datum; often NGVD29, pre-2023 | inferred |
| epqs.nationalmap.gov (3DEP point) | 14 | NAVD88 lidar surface | inferred |
| blank (no published pool) | 13 | none | n/a |
| waterdatafortexas.org | 11 | NGVD29 (stated on page) | verified [fetched] |
| web.archive.org / state DNR standard pool | 10 | usually unstated | unverified |
| federalregister.gov / govinfo (FERC notices) | 12 | "msl", plant datum or NGVD29 | mixed |
| cwms-data URL levels (NWDM Kansas City) | 8 | CWMS location tag LOCAL | verified tag, datum unresolved |
| USGS historical topo labels (prd-tnm) | 7 | NGVD29-era map datum | inferred |
| Duke full-pond tables | 8 | NGVD29 true elevation, plus 100-scale | inferred |
| TVA guide / summer zone / USACE pool inside TVA zone | ~26 | TVA system | inferred |
| santeecooper.com + NWS PINS1 | 2 | Santee Cooper gauge scale (about NGVD29-equivalent) | inferred |
| Operator single-source pages (Georgia Power, Dominion, AEP, Alliant, NIPSCO, SRP, NJWSA, SJRWMD, GRDA, PG&E ...) | ~40 | per operator (see section 3) | per row |

"Pool is a true elevation": yes for essentially every row with a numeric `fullPoolFt`, except Duke (the numeric is NGVD29 ft; the live series is the 100-scale) and sources quoted as gauge readings (Hopatcong 9.0 ft, Priest Lake 3.0 ft gauge, Winnipesaukee 4.32). `full_pool.csv` already converted those to elevations; the engine must therefore pair them with an *elevation* series.

## 3. Per-provider findings

### 3.1 TVA (17 lakes) - inferred NGVD29, same-source pool

* [fetched] `lakeinfo.tva.gov/web/sites/kentucky.htm` gives 354 ft winter minimum and 359 ft summer target and names no datum. `tva.com` lake-level pages returned HTTP 403 to bots, so no TVA text was obtained.
* [fetched, text extracted] Kentucky Transportation Cabinet record for the TVA-maintained Kentucky Dam upstream gauge: "DATUM: NGVD29 (CONVERSION FROM NGVD29 TO NAVD88 IS -0.2 ft)"; "SITE IS MAINTAINED BY THE TVA". URL: `https://transportation.ky.gov/Construction-Procurement/Project%20Related%20Information/KY%20Lake%20Historic%20Water%20Surface%20Elevations.pdf`.
* [fetched] NWS gauge GVDA1 (Guntersville tailwater) lists NGVD29 = 538.2 ft.
* [computed] NCAT shift at 16 TVA lakes: median -0.17 ft, max abs 0.56 ft. Small, so a mismatch matters less than elsewhere, but is still a 0.2 to 0.5 ft error on a delta of a few feet.
* Pool: `fullPoolFt` is the TVA operating-guide figure, "top of summer operating zone" (mainstem) or "June fill target" (tributary), both in the same system as the live reading. Sheet values are often "top of gates" (higher). Seasonal pool is lower in winter by design (Guntersville -1.7, Kentucky -5), so the shift is negative in winter without being "low".
* Datum changes: none found. Decision: COMPATIBLE_SAME_SOURCE; datum NGVD29 flagged inferred.

### 3.2 USACE: CWMS (63 + 2) and Access2Water (112)

* [fetched] CWMS `GET /locations/<name>?office=<o>` returns `vertical-datum`. Examples: Abiquiu NGVD29, Carlyle (MVS) NAVD88, Pensacola PENS LOCAL, Kerr `ROA JHK` NGVD29, Grand Coulee GCL (NWDP) NGVD29. The `elevation` field there is the site elevation in metres, not the lake level.
* [fetched] CWMS OpenAPI: a posted series without explicit `vertical-datum-info` is assumed to be in the location's datum; the `datum` query parameter (NAVD88|NGVD29) on `/timeseries` is documented as "not supported" for `application/json;version=2`. Live test: Abiquiu Top of Conservation returned 6230.0 with and without `datum=NAVD88` (T10).
* [computed] Resolved datum of the 64 CWMS-family bound series: NGVD29 52, NAVD88 9, LOCAL 3 (Tuttle Creek TUCR, Branched Oak SC18, Grand Lake PENS). NAVD88: Carlyle, Shelbyville, Rend, Mark Twain, Wappapello (MVS), Cross, Bistineau (MVK), Sumner (SPA), Milton (LRP). Rend, Wappapello are STREAM_LOCATION and Cross, Bistineau, Milton are SITE (T11).
* [computed from cached A2W records] The 112 bound A2W lakes: NGVD29 79, LOCAL 22, NAVD88 9, blank 2 (Falls Lake, Lake Chelan). All 613 A2W PROJECT records: NGVD29 456 (+3 spelling variants), LOCAL 94, NAVD88 38, blank 25.
  * NAVD88: Berlin, Mosquito Creek, Allegheny (Kinzua), Shenango, Stonewall Jackson, Tygart (LRP); Beltzville, Blue Marsh (NAP); Santa Rosa (SPA).
  * LOCAL: Kansas City district (Rathbun, Clinton, Kanopolis, Melvern, Milford, Perry, Pomona, Wilson, Longview, Pomme de Terre, Smithville, Harlan County), NWO (Chatfield, Cherry Creek, Bowman-Haley, Canyon Ferry, Tiber), NAB (Randolph, Savage, Raystown), MVP (Lake Pepin, Red Lake).
* **LOCAL is ambiguous (T3), [computed 2026-10-13]:** Kanopolis A2W reading 1467.08 equals USGS 06865000 62614 (NGVD29) 1467.08. Rathbun A2W reading 906.96 vs USGS 06903880 gage height 906.90 (USGS site altitude datum NAVD88, per `alt_datum_cd`). So LOCAL maps to NGVD29 in one case and to a NAVD88-like value in another.
* Pool: ~150 `full_pool.csv` rows are CWMS levels of the same location, so level and pool share the native datum (T5-safe). 37 NGVD29 lakes and 8 LOCAL lakes use URL documents instead; those need a stated datum. Grand Lake PENS: pool 744 is Pensacola Datum, NGVD29 = PD + 1.07 [project note, GRDA FERC exhibit, not re-fetched].
* Datum changes: none dated in sources fetched. Decision: SAME_SOURCE for CWMS-level pools; SAME_DATUM when URL pool states NGVD29/NAVD88 matching the tag; LOCAL with a URL pool is UNKNOWN.

### 3.3 Duke Energy (8 lakes) - local 100-scale, NGVD29 true elevation (inferred)

* [fetched] NWS gauges list the zero of Duke's scale in NGVD29: Lake Norman CWAN7 660 ft (observed 99.44, action stage 100), Lake Hickory OXFN7 835 (98.36), Lake James BRWN7 1100 (100.27). So scale 100 = 760 / 935 / 1200 ft NGVD29. JCSS1 (Jocassee) and KEOS1 (Keowee) have empty datum tables; their readings (83.99, 96.65) are on the same scale.
* [fetch failed] Duke's API (`api.hydro-derived.duke-energy.app/lakes/current-levels`) now returns HTTP 403 "Missing Authentication Token". The statements "AMSL, NGVD 29 datum", "100 = full pond" and Robinson "real feet" come from earlier `full_pool.csv` notes only.
* Rule: `shift = scaleValue - 100`; elevation = `fullPondFt + (scale - 100)`. Pool figures in `full_pool.csv` (760.0, 935.0, 1200.0, 1110.0, 800.0, 225.5, 569.4) are true NGVD29 elevations. Lake Robinson (221.6) is in real feet. Normal targets sit below 100 (Norman 98.5 summer, 96 winter) so the shift is negative most of the year by design.
* Wylie and Wateree: Duke defines full pond as where spill begins [project note]. Decision: SAME_SOURCE after the scale rule; absolute NGVD29 elevation inferred.

### 3.4 USBR: RISE (46) and PN Hydromet (4) - datum UNKNOWN

* [fetched, 46 of 46 items] RISE catalog-item `verticalDatum` is **null** for every bound Lake/Reservoir Elevation series. The location record (`/rise/api/location/{id}`) carries `verticalDatum`, but it describes the location `elevation` (a dam or gage attribute): EGM96 16 lakes, NGVD29 11, NAVD88 5, "USGS 1912" 2 (Havasu, Mead), none 12. For Lake Powell the location elevation is 3596 vs pool 3700; for Bighorn 3200 vs pool 3640, so it is not even the pool.
* [fetched, text extracted] Reclamation's East Park survey: elevations are on the local "Reclamation Project Vertical Datum (RPVD)"; NAVD88 is 3.55 ft higher. RPVD is project-specific. Lower Colorado reservoirs are reported (project note, unverified) as RPVD Parker = NAVD88 - 2.72 ft and RPVD Davis = NAVD88 - 3.39 ft; Mead "USGS 1912".
* Pool: `full_pool.csv` USBR rows are "top of active conservation / joint use", same Reclamation system as the live series. A same-source shift is plausible; any conversion to or from NGVD29/NAVD88 is not defensible. NCAT shift for USBR lakes is large (median 3.13 ft, max 5.4), so mixing USBR with other sources' pools is unsafe.
* Decision: SAME_SOURCE only; otherwise UNKNOWN. Datum class: UNKNOWN.

### 3.5 USGS NWIS (usgs 74, usgs-d 12) and Santee Cooper

* [fetched] Parameter definitions (`api.waterdata.usgs.gov/ogcapi/v0/collections/parameter-codes`): 62614 "above NGVD 1929", 62615 "above NAVD 1988", 72020 "Elevation above NGVD 1929", 72275 "above USBRKB datum", 00062 "reservoir water surface above datum" (unspecified), 00065 "Gage height".
* Bound: 62614 31, 62615 19, 00062 14, 00065 8, 72020 1, 72275 1; usgs-d 12 are 00065 + `alt_va` (11 NAVD88, Payette Lake NGVD29).
* **T1 [computed 2026-10-13], 00062 minus 62615 at the same instant:** Marion +0.88, Moultrie +0.99, Murray +1.31, Greenwood +0.57, Monticello +0.16, Deep Creek -1.82, Bear Lake -6.88 ft. The `alt_va` site field is not the offset (Monticello 382.43, Deep Creek 0.0, Marion -0.88). Hartwell, Thurmond, W.F. George 00062 sites have no paired series.
* **Santee Cooper (Marion, Moultrie) [fetched]:** the lake-data page prints "just above 72.0 ft in winter to 75.5 feet in the summer", FERC maximum 76.8, names no datum, and points to the USGS gauges for live levels. 00062 and 62615 both exist, differ by 0.88 / 0.99 ft, and these equal the NCAT NGVD29 to NAVD88 shifts (-0.879 / -0.984) to two decimals, so the gauge scale is NGVD29-equivalent (inferred). Pairing 62615 with 75.5 would be a 0.88 ft error; use 00062 with 75.5, or 62615 with 74.62.
* Lake Murray: Dominion page shows 356.0 on 2026-10-13 (matches 00062 355.97; 62615 354.66); pool 360 is Saluda Plant Datum, NAVD88 = plant datum - 1.31 here (a FERC 2009 notice gives 358.5 NAVD88 = 360 - 1.5, project note).
* Deep Creek Lake (project note + live check): 00062 is "Historical Spillway Datum 2462"; NAVD88 = spillway datum + 1.82 (confirmed by the live offset -1.82).
* Datum change: [fetched] USGS WMA 2020.02 requires active stations with published water-surface elevations to be on NAVD88 by 2023-01-27. A site's 62614 can be replaced by 62615; histories may straddle.
* T12: Lake Hopatcong (usgs-d): USGS alt 914.5 NAVD88; the Lake Hopatcong plan says gauge datum 914.57 NGVD29 [project note]. Differ by the datum shift; mark low confidence.
* Decision: 62614 NGVD29, 62615 NAVD88 resolved by definition; 00062 and 00065 UNKNOWN unless paired.

### 3.6 NOAA NWS NWPS / HADS (43 lakes) - unverified

* [fetched, all 43] NWPS `datums.vertical` empty for 27; for 16 it lists NGVD29 (about 9), NAVD88 (about 5), STND or MHW; the `value` semantics are undocumented (Seneca Lake: STND 0, NGVD29 -1.33, NAVD88 0).
* [fetched] SHEF Code Manual (2012): HP "Elevation, pool ... usually expressed in MSL"; HL "Elevation, natural lake ... in MSL"; HG river stage; HK lake height above a specified datum "usually not MSL"; HF forebay elevation. MSL is not NGVD29 vs NAVD88.
* T8: Lake Vermilion MN (HPIRG) reads 56.74 (local scale); Crescent Lake FL (HGIRP) reads 1.68 (NAVD88 per its name); Liberty Reservoir (HGIRR) reads 410.88 (an elevation).
* T2: PNVS1 (Marion) lists NAVD88 0 but its observed 72.96 equals USGS 00062, not 62615 72.08. NWS tables cannot be trusted.
* Operator-datum lakes seen through NWPS: Duke Catawba (verified NGVD29 zero), Badin/High Rock (Yadkin local 1926 Alcoa datum, project note), Burton (Georgia Power scale; NWS action stage 1866.6 = Georgia Power full elevation), Lake of the Ozarks (Union Electric Datum, project note).
* Decision: UNKNOWN unless the operator document states a datum AND the magnitude passes the plausibility guard.

### 3.7 NOAA CO-OPS (14 Great Lakes stations) - IGLD 1985

* [fetched] CO-OPS: "currently utilize IGLD 1985"; IGLD (2020) tentative release 2027; aligned with NGS geoid-based NAPGD. [fetched] station 9087044: `datum=IGLD` returns about 579 ft; `datum=NAVD` returns "There is no NAVD for the station"; only GL_LWD 577.43.
* No pool in `full_pool.csv`; no shift applies. IGLD85 is a dynamic-height system; not NCAT-convertible. Enum used in JSON: `PROJECT` (closest value).

### 3.8 Documented datum changes found

| When | Provider | What | Evidence |
|---|---|---|---|
| 2025-11-19 | NJWSA (Round Valley, Spruce Run) | Elevations switched NGVD29 to NAVD88; "NAVD 1988 ELEVATION = NGVD 1929 ELEVATION [minus] 0.8" | [fetched, text extracted] `https://www.njwsa.org/uploads/1/0/8/0/108064771/data.pdf` |
| by 2023-01-27 | USGS | NAVD88 required for active water-surface-elevation stations | [fetched] USGS WMA 2020.02 |
| 2023-10-01 | TWDB/IBWC Falcon | pool 301.10 to 301.20 NGVD29 (pool revision, not datum) | [fetched] waterdatafortexas |
| undated | SJRWMD | moved to NAVD88; NGVD29 about 1 ft higher there | [fetched] chart says "All levels in NAVD88 Datum"; switch date not found |
| tentative 2027 | CO-OPS | IGLD85 to IGLD2020 | [fetched] |
| unknown | USACE, TVA, Duke, Santee Cooper | no dated re-datum event located | UNKNOWN |

### 3.9 Long tail

| Provider | Datum | Basis | Note |
|---|---|---|---|
| sjrwmd (6) | NAVD88 | verified | UORB chart "All levels in NAVD88 Datum" covers Apopka, Griffin, Harris; Jesup, Lochloosa, Orange have no pool |
| twdb (2) | NGVD29 | verified | waterdatafortexas pages state "Vertical datum NGVD29" and pool "ft above NGVD29" |
| aep (1) | NGVD29 | verified | smithmtn.com: 795-ft base is NGVD 29 |
| alliant (1) | NGVD29 | verified | "Head Water (feet NGVD)"; defines NGVD |
| nipsco (1) | LOCAL | verified | "Elevation in feet Local Datum"; offset to NGVD 2.32 ft is a [project note] |
| njwsa (1) | NAVD88 since 2025-11-19 | verified | see 3.8 |
| cdec (2) | PG&E datum (Almanor, about 10 ft off sea level, project note); Berryessa UNKNOWN | inferred | |
| srp (4) | UNKNOWN; pools derived from SRP's own "remaining" so same-source | unverified | |
| cnppid (2) | UNKNOWN ("feet above sea level") | unverified | |
| nhdes (6) | UNKNOWN; Winnipesaukee scale = elevation - 500 (project note) | unverified | |
| nppd, nwrfc, wps-hydro, eccc, mncsg, utahlake | UNKNOWN | unverified | pools from topo labels or datum-unstated pages, or no pool |
| Georgia Power (via nwps/cwms/a2w) | page [fetched] states no datum; USACE lakes match NGVD29 CWMS pools | unverified | Burton 1866.6, Hartwell 660, Thurmond 330, Russell 475 |

## 4. Decision table

Rows: datum of the level series. Columns: datum of the reference pool. Cell = verdict.

| Level series \ Pool | Same published source (same CWMS location, TVA guide, SRP, one operator table) | NGVD29 stated | NAVD88 stated | Same named local datum | Different local datum / project datum | UNKNOWN or unstated |
|---|---|---|---|---|---|---|
| NGVD29 (62614, TVA, CWMS tag, TWDB, AEP) | COMPATIBLE_SAME_SOURCE | COMPATIBLE_SAME_DATUM | CONVERTIBLE: NCAT/VERTCON NGVD29 to NAVD88, sigma 0.23 ft; use operator factor if published (NJWSA 0.8, Kentucky Dam 0.2) | INCOMPATIBLE | CONVERTIBLE only with an operator offset (e.g. Pensacola PD+1.07, NIPSCO 2.32, Saluda -1.5); else UNKNOWN | INCOMPATIBLE -> UNKNOWN |
| NAVD88 (62615, SJRWMD, NJWSA, A2W NAVD88 projects) | COMPATIBLE_SAME_SOURCE | CONVERTIBLE (NCAT, sigma 0.23 ft) | COMPATIBLE_SAME_DATUM | INCOMPATIBLE | operator offset only; else UNKNOWN | INCOMPATIBLE -> UNKNOWN |
| LOCAL / plant / utility datum (NIPSCO, Pensacola, Saluda, PG&E, UED, A2W LOCAL, CWMS LOCAL) | COMPATIBLE_SAME_SOURCE (CWMS/A2W level at same location, SRP-style derived) | CONVERTIBLE only with the operator's published offset, else INCOMPATIBLE -> UNKNOWN | same | COMPATIBLE_SAME_DATUM if the named datum is identical in both | INCOMPATIBLE -> UNKNOWN | INCOMPATIBLE -> UNKNOWN |
| Duke 100-scale | COMPATIBLE_SAME_SOURCE after `scale - 100` | CONVERTIBLE using scale-zero from NWS (660/835/1100 ft NGVD29) or `fullPond - 100` | NCAT after NGVD29 | n/a | INCOMPATIBLE | UNKNOWN |
| USGS 00062 (datum unspecified) | COMPATIBLE_SAME_SOURCE only when pool was derived from the same gauge scale (Santee Cooper, Dominion Murray) | CONVERTIBLE only if a paired 62614/62615 offset is measured, else UNKNOWN | CONVERTIBLE with measured 62615 pair (sigma 0.01 ft instrument) | UNKNOWN | UNKNOWN | UNKNOWN |
| USGS 00065 gage height | not an elevation | CONVERTIBLE only if gage-datum altitude AND its datum are known (usgs-d `alt_va`), else INCOMPATIBLE | same | same | INCOMPATIBLE | INCOMPATIBLE -> UNKNOWN |
| USBR RISE / PNHM (datum undeclared) | COMPATIBLE_SAME_SOURCE (USBR pool vs RISE) | UNKNOWN (large NCAT shift; datum undeclared) | UNKNOWN | UNKNOWN | INCOMPATIBLE (RPVD, USGS 1912, USBRKB) | UNKNOWN |
| NWS NWPS (HP/HL/HG) | rare | accept only if plausibility guard passes AND operator states datum | same | same | INCOMPATIBLE | UNKNOWN |
| IGLD85 (CO-OPS) | n/a (no pool) | INCOMPATIBLE (dynamic height, not NCAT) | INCOMPATIBLE | n/a | INCOMPATIBLE | n/a |

Sigma used for CONVERTIBLE: 0.23 ft for NCAT/VERTCON (earlier thread, at Guntersville test point), reconciled `sigma_datum`; 1.78 ft fleet RMS (3.13 ft USBR median) for an unreconciled mismatch; 0 for same source/same datum.

## 5. What could not be verified

1. **TVA datum**: no TVA document fetched states it (lakeinfo.tva.gov silent; tva.com 403). NGVD29 rests on a KYTC record for one TVA-maintained gauge and an NWS tailwater gauge. Per-reservoir differences (Fontana, Norris, Watts Bar) are unchecked.
2. **Duke**: operator API now requires a token; NGVD29 for Jocassee, Keowee, Wateree, Wylie, Robinson is from project notes only. Only Norman, Hickory, James are verified via NWS metadata.
3. **Santee Cooper**: page names no datum; the 00062-equals-NGVD29 reading is inference from matching the NCAT shift. Santee Cooper's FERC license datum was not located.
4. **Georgia Power / Alabama Power**: published pages show no datum.
5. **USBR RISE and PN Hydromet**: series datum undeclared; the Lower Colorado RPVD offsets (2.72, 3.39) are project notes; the Mohave/Havasu survey PDF text could not be extracted.
6. **NWS NWPS**: datum semantics undocumented, 27 of 43 empty, some contradictory.
7. **LOCAL tag** on 22 A2W lakes and 3 CWMS lakes: only Kanopolis (NGVD29) and Rathbun (NAVD88-like) were resolved.
8. **00062 sites without a paired series** (Hartwell, Thurmond, W.F. George, Rye Patch, Walker, Wild Horse): offset unknown.
9. **NH DES, SRP, CNPPID, NPPD, NWRFC, WPS, ECCC, MN, Utah Lake**: UNKNOWN; several URLs in `full_pool.csv` were truncated and not re-fetched.
10. **Dated datum changes** for USACE districts, TVA, Duke, Santee Cooper: none found. Absence of evidence only.
11. **Abiquiu pool**: CWMS Top of Conservation reads 6230.0 on 2026-10-01 vs 6220.0 in `full_pool.csv` (the `(max)` variant); not a datum issue but a pool-selection issue to check.
12. PDFs (SRP/NJWSA/KYTC/SJRWMD/East Park) were read by an ad-hoc text extractor; quoted lines are real but layout may be lossy (the NJWSA sign before 0.8 dropped in extraction; the 0.8 ft magnitude agrees with the published USGS Spruce Run shift of -0.8).

## 6. Implementation hand-off

* Per-lake datum fields to store: `levelDatum`, `levelDatumBasis`, `poolDatum`, `poolDatumBasis`, `sameSourceFlag`, `levelScale` (Duke), `datumChangeDates`.
* Resolution order: sameSource > both stated equal > both stated NGVD29/NAVD88 convert (NCAT or operator factor) > else UNKNOWN.
* Suppress and log when `|level - pool|` fails the plausibility guard.
* Source files: `jobs/depth-brain/depth_brain/data/datum_providers.json`; inputs `Sector_Engine-depth-research/docs/data/full_pool.csv`, `docs/research/depth-brain/data/datum_shift_ngvd29_navd88.csv`, `datum_inventory.json`.
