# Lake Brain: filling the level-source gaps (wave 2 of binding)

Thread `gaps`, Lake Brain deep-research campaign, 2026-10-13. Research only: GET-only against public endpoints, no deploy, no write to any RTDB or bucket, no rubric edit, no push.
Method and code: `research/lake-brain/binding2/` (wave-1 machinery in `research/lake-brain/binding/` is imported, not copied). Bulk data (candidate series, daily history, raw captures) lives outside Git in `Sector_Research_Data/lake-brain/binding2/`.
Committed results: `data/verified_bindings_v2.csv` (cumulative table with a `wave` column), `data/binding2_summary.json`, `ledger/gaps.jsonl`.

## 1. Result in one table

Wave 1 machine-verified 258 core + 57 flagged of 621 directory lakes (41.5% / 50.7%). Wave 2 profiled the 274 unbound lakes, used four regional scouts (southeast, northeast, Midwest + Great Lakes, West) to test source families in parallel, ran a systematic USGS live scan, re-ran the wave-1 review machinery on every new candidate, and audited wave 1.
Three layers are reported separately because they rest on different rule sets. Only L1 uses the pre-registered `binding-review-v1` unchanged.

| Layer | Rules | Core | Flagged | Stage-only | No binding | Core % | Core + flagged % | Ladder points (core / core+flagged) |
|---|---|---|---|---|---|---|---|---|
| wave 1 (reproduced) | binding-review-v1 | 258 | 57 | 32 | 274 | 41.5% | 50.7% | 5 / 7 |
| **L1** | v1 unchanged + wave-1 probe bug fix + new sources | 278 | 94 | 9 | 240 | 44.8% | 59.9% | 5 / 7 |
| **L2** | + v1.1 rule extensions (section 5) | 300 | 116 | 11 | 194 | 48.3% | 67.0% | 5 / 7 |
| **L3** | + v1.1-R7h history-envelope promotion | **389** | 28 | 10 | 194 | **62.6%** | 67.1% | 7 / 7 |

Reading it honestly: with the pre-registered rules alone the fleet moves from 41.5% to 44.8% core (the 50% ladder step is not reached). The 50% step (7 points instead of 5) is reached only with the labelled v1.1 extensions plus R7h, i.e. with rules that were written after seeing wave-1 failures. All of it is machine-verified, not human-reviewed; per the rubric nothing counts until a human adopts it (blockers B-binding-001 and B-gaps-003, actions M-B02 and M-G01). Each lake's `wave` value in `verified_bindings_v2.csv` (`w1`, `w2-v1`, `w2-v1.1`) lets the reviewer take only the rows that rest on the strict rules.

Newly bound lakes (previously no binding or stage-only): **102** (86 core in L3, 16 flagged). History of all 417 bound lakes: 359 with >= 5 complete years, 20 with 2-4, 38 with none or under 2.

## 2. The 274 unbound lakes and how they were ranked

Profile table: `binding2/unbound_profile.json` (state, operator, `hasDam`, `poolBasis`, area, `apiLevel`, `usgsGage`, wave-1 reason, bowfishing tier). By wave-1 reason: 171 `no-candidate`, 96 `candidates-rejected`, 7 pending. By `poolBasis`: 146 natural-surface, 115 full-pool, 13 unknown; 120 have a dam. Median area 10.1 km2 (only 45 are larger than 50 km2). By operator family: OTHER 151, NONE 88, USACE 26, USBR 9 (`NONE` = natural lakes with no operator). Largest state groups: ME 13, AK 12, CT 12, NH 12, DE 11, RI 11, MA 10, MI 10, VT 10, HI 9, MD 9, PA 9.

There is no popularity field in the directory, so the bowfishing relevance tier is a documented heuristic (`profile_unbound.py`): size class (0-4) + state bowfishing prevalence (1-3: warm-water carp/gar states 3, Mountain West and mid-Atlantic 2, AK/HI/New England 1) + regulated pool (+1) + warm-water lake (+1); tier A >= 8, B 6-7, C otherwise. It encodes judgement, not data, and it only decided where scouts spent effort first.

| Tier | Unbound lakes (wave-1 list) | Bound now (L3 incl. flagged) | Still unbound |
|---|---|---|---|
| A | 45 | 33 | 12 |
| B | 83 | 22 | 61 |
| C | 146 | 23 | 123 |

## 3. Which sources unlocked lakes

Source families tested in parallel by four scouts (southeast, northeast, Midwest + Great Lakes, West) plus this thread's USGS scan. Every scout record, including dead ends, is in `ledger/gaps.jsonl` (`S-gaps-*`) and `binding2/notes/*.json`. Table: lakes newly bound at L3 by the provider that ended up as the binding (a lake counts once; `History >= 5y` is the final history leg, which may come from another provider).

| Provider (binding) | New lakes | of which core | history >= 5y | Examples |
|---|---|---|---|---|
| USGS NWIS (live scan, absolute elevation parameters) | 20 | 17 | 18 | Clarks Hill / J.S. Thurmond (GA), Clear Lake (CA), Clinton Lake (IL), Columbus Lake (MS), Devils Lake (ND), Eufaula / W.F. George (AL), Geist Reservoir (IN) ... |
| NOAA CO-OPS Great Lakes IGLD85 stations | 13 | 13 | 13 | Green Bay (WI), Lake Erie (MI), Lake Erie (NY), Lake Erie (OH), Lake Erie (PA), Lake Huron (MI), Lake Michigan (IN) ... |
| USGS NWIS gage height + gage-datum altitude (derived, flagged class) | 12 | 7 | 9 | Black Hawk Lake (IA), C.J. Strike Reservoir (ID), Clear Lake (IA), Fox Lake (IL), Henrys Lake (ID), Lake Hopatcong (NJ), Lake Pontchartrain (LA) ... |
| Duke Energy Lake View API (documented stage offset, flagged class) | 8 | 5 | 4 | Lake Hickory (NC), Lake James (NC), Lake Jocassee (SC), Lake Keowee (SC), Lake Norman (NC), Lake Robinson (SC), Lake Wateree (SC) ... |
| SJRWMD WISKI static store (FL) | 6 | 6 | 6 | Apopka (FL), Griffin (FL), Harris (FL), Jesup (FL), Lochloosa (FL), Orange Lake (FL) |
| NH DES Dam Bureau real-time platform | 6 | 6 | 6 | Lake Winnipesaukee (NH), Lake Winnisquam (NH), Newfound Lake (NH), Ossipee Lake (NH), Squam Lake (NH), Sunapee Lake (NH) |
| USACE CWMS (re-pointed / dam-named series) | 5 | 5 | 5 | Bay Springs Lake (MS), East Lake Tohopekaliga (FL), Lake Oahe (ND), Lake Sakakawea (ND), Logan Martin (AL) |
| NOAA NWPS relay | 5 | 4 | 4 | Lake Gaston (VA), Lake Minnetonka (MN), Lake Poinsett (SD), Liberty Reservoir (MD), Youghiogheny River Lake (MD) |
| SRP Watershed Connection JSON | 4 | 2 | 0 | Apache (AZ), Canyon (AZ), Roosevelt (AZ), Saguaro (AZ) |
| USBR Pacific Northwest Hydromet (live copy of lagging RISE series) | 4 | 4 | 4 | Banks Lake (WA), Crescent Lake (OR), Lake Cascade (ID), Potholes Reservoir (WA) |
| California CDEC (DWR) | 2 | 2 | 2 | Almanor (CA), Berryessa (CA) |
| USACE Access2Water (re-pointed) | 2 | 1 | 1 | Lake Pepin (MN), Longview Lake (MO) |
| CNPPID | 2 | 2 | 1 | Johnson Lake (NE), Lake McConaughy (NE) |
| NIPSCO hydro page | 1 | 1 | 0 | Lake Shafer (IN) |
| Water Survey of Canada / LWCB (Lake of the Woods) | 1 | 1 | 1 | Lake of the Woods (MN) |
| MN DNR Cooperative Stream Gaging | 1 | 1 | 1 | White Bear Lake (MN) |
| USACE CWMS SAW (Kerr) | 1 | 1 | 1 | Kerr Lake (John H. Kerr) (NC) |
| NPPD | 1 | 1 | 0 | Sutherland Reservoir (NE) |
| NJ Water Supply Authority | 1 | 1 | 0 | Round Valley Reservoir (NJ) |
| utahlake | 1 | 0 | 0 | Utah Lake (UT) |
| AEP Smith Mountain plant-levels | 1 | 1 | 1 | Smith Mountain Lake (VA) |
| NWRFC XML (NWS) | 1 | 1 | 0 | Lake Cushman (WA) |
| USACE CWMS NWDP (Grand Coulee forebay) | 1 | 1 | 1 | Lake Roosevelt (FDR) (WA) |
| WPS/WRPCO hydro page | 1 | 1 | 0 | Castle Rock Lake (WI) |
| Alliant Energy hydro page | 1 | 1 | 0 | Lake Wisconsin (WI) |
| USBR RISE (state-split sibling) | 1 | 1 | 1 | Flaming Gorge Reservoir (WY) |

General methods that unlocked many lakes at once, in order of yield:
1. **Fix the wave-1 matching rules, not the sources** (section 4 and 5): probe-parameter bug, state split, dam-named gauges, sibling lakes.
2. **NOAA CO-OPS Great Lakes** (13 directory entries in one stroke; stations carry 45-126 years of IGLD85 daily means). The lake-wide rule RGL is what makes the town-named harbour stations eligible.
3. **State/district platforms with an index**: NH DES (`nhdes.rtiamanzi.org/api`, hourly, history back to 2010, covers about 20 NH lakes beyond the directory), SJRWMD's static WISKI store (7 lakes of the Harris chain / Ocklawaha / St. Johns, 5-30 years), Duke Energy Lake View (43 Duke lakes; 8 in the directory).
4. **USBR PN Hydromet and CDEC** as live copies of USBR/DWR series that RISE lags by 9-13 days (the original reason for the R6 rejections of Cascade, Crescent, Potholes, Banks, Berryessa).
5. **USGS bounding-box scan** (one request per lake) found the rest: 829 candidate series on 261 lakes, but only 32 lakes end up on USGS because most nearby sites are river/outlet gauges, discontinued, or local stage.

Providers that did **not** help (all recorded in the ledger): SFWMD DBHYDRO (login), mass.gov/des.nh.gov documents/NJDWSC (HTTP 403 to automated clients; not bypassed), FirstLight/Great River Hydro/Baltimore DPW/WSSC/MDC/PA DCNR/DE DNREC/VT/ME/RI state programs (phone line, percent-full PDFs, flows only), Nebraska DWEE AQUARIUS (click-through disclaimer; not bypassed), Dominion (no observed level), Utah DWRi/OWRD/Upper Colorado hydrodata (unreachable or 403), Xcel Chippewa Flowage (404).

## 4. Wave-1 audit: what was wrong

| # | Finding | Evidence | Effect |
|---|---|---|---|
| 1 | **Probe-parameter bug.** `probe_usgs` kept the parameter with the latest timestamp and broke ties by sample count, so sites reporting both an absolute lake elevation (62614/62615/00062) and gage height (00065) were recorded as 00065. | 78 USGS probes chose 00065; 30 of them have a live elevation parameter (`reprobe_usgs.py`, `probe_results_v2.json`). | 14 lakes were `STAGE_ONLY` only because of this (Winnebago, Mendota, Monona, Geneva, Devils, Stump, Higgins, Gogebic, Geist, Greenwood, Quinault, Francis Case, Eufaula, Clear Lake CA). They now bind (4 core, 8 flagged, 12 core via R7h in L3 across the 32 stage-only lakes; 8 stay stage-only). |
| 2 | **State rule rejected cross-state reservoirs.** Kerr (NC entry, station in VA), Thurmond (SC and GA entries), Youghiogheny (MD entry, station in PA), Flaming Gorge (WY). | R4 `state-mismatch` with name similarity 1.0 and the gauge on the dam. | R4b waiver (v1.1). |
| 3 | **Uniqueness rule (R5) blocked sibling entries** of one physical lake: Thurmond SC/GA, Eufaula/W.F. George AL/GA, East Lake Tohopekaliga vs Lake Tohopekaliga. | the same series was claimed by the sibling entry. | R5b (v1.1). |
| 4 | **Identity by name failed for dam-named pools**: Grand Coulee Dam (Lake Roosevelt), Jamie Whitten L&D (Bay Springs), Stennis L&D (Columbus Lake), Garrison Dam (Sakakawea), Libby, Big Bend, Fort Randall. | station inside the polygon, level in the strong window, NID dam name matches. | R2b/R2c (v1.1). |
| 5 | **Geometry rule R1 (1.5 km) rejected dam gauges** of large reservoirs: Logan Martin (1.6 km, two agreeing sources), Longview (3.0 km, four agreeing sources), Smith Mountain (2.3 km). | CWMS/A2W project coordinates sit 1.6-3.2 km from the polygon edge. | R1b (v1.1, strong level + name sim >= 0.75 only). |
| 6 | **Datum rule R8 is a label test.** Operators whose feed carries no datum label (USBR PN Hydromet, CDEC, SRP, utahlake.gov, NWRFC, AEP, CNPPID) failed it although the level sat at the full pool. | R7 strong or the provider publishes its own full pool within 3 ft of the directory's. | R8b/R8c (v1.1). |
| 7 | **TWDB history bookkeeping miss**: Amistad and Falcon recorded `NONE`; the history files exist in lower case. | TWDB CSV exists: Amistad 57 complete years, Falcon 72. | history fixed (history2.py). |
| 8 | **Lake St. Clair (CO-OPS) had no history leg.** | CO-OPS daily means 1990-2025 pulled (`coops_history.py`). | history fixed. |
| 9 | **Great Lakes and Great Salt Lake were unbound** because the five Great Lakes have no polygons (wave-1 blocker B-binding-005). | every CO-OPS harbour station passes level and state; only the position rule fails. | RGL (v1.1). |
| 10 | **R9 limit (not an error).** Lake Francis Case: USGS Chamberlain (upper pool) 1350.2 ft and CWMS Fort Randall forebay 1353.2 ft differ by 3-5 ft, 80 miles apart on a river-run reservoir; the 2 ft agreement band would call them `CONFLICT`. Bound on the Chamberlain USGS gauge (a lake gauge, 26 complete years). | both are right; a single "lake level" does not exist on a long reservoir with a pool slope. | recorded; the Fort Randall forebay is the better dam-pool series if the product wants the forebay |

Checks that came out clean: **Eagle Lake MS** (the "Muddy Bayou control structure" binding): the station name is literally "Eagle Lake Side" (landside = lake side, 75.17 ft vs full pool 76.9) and NWPS `MBGM6` "above Muddy Bayou C/S Eagle Lake Side" agrees (75.02); the other side is Steele Bayou (69.65) and was rejected. **Access2Water tailwater cases:** a station-name/operator-level audit of all 315 wave-1 bindings (`wave1_audit.py`) found no additional tailwater series; the flagged names (`Powell` contains "well", `Outlet`, `Control Structure`, `Pump`) are innocent or are the Eagle Lake case above. The audit's delta-to-full-pool flags (about 50 lakes) are legitimate drawdown or flood-pool in western, Tennessee/Cumberland and Corps flood-control reservoirs, not mis-matches (their own multi-year history reaches the full pool).

Directory data-quality finding (not a binding error): the `fullPoolFt` of several lakes disagrees with every gauge reading for the lake. Spirit Lake IA 1447 ft (gauge ~1401), Storm Lake IA 1437 (~1399), Clear Lake IA 1204 (~1227), Lake Geneva WI 879 (~864), West Grand Lake ME 259 (gauge 296.7, NAVD88, 15 years), Alamo AZ and Bluewater NM (history never within 10 ft of the stored pool). These lakes stay flagged or unbound because R7 compares to the stored value. Action M-G03.

## 5. Proposed v1.1 rules and what they are worth

None of these weakens R6 (liveness), R7 (level window) or R9 (cross-origin agreement). They are labelled v1.1, counted separately (layers L1 vs L2/L3 above) and listed per lake in the `checks_passed` column. Counts are lakes bound (core + flagged class, before R7h) found by the ablation in `ablation.py`: "alone" = gain when only that rule is added to v1; "marginal" = loss when only that rule is removed from the full set.

| Rule | Name | Definition | Gain alone | Marginal in full set | Lakes |
|---|---|---|---|---|---|
| R1b | dam-gauge geometry | polygon distance <= 5 km, linked NID dam within 4 km of the gauge, name similarity >= 0.75, strong R7 only | 3 | 1 | Longview Lake |
| R2b | identity via dam | an NID dam within 1.5 km of the gauge and within 6 km of the polygon with a similar name, or an Access2Water NIDID equal to the lake's linked dam; strong R7 only | 2 | 0 | Bay Springs Lake, Lake Roosevelt (FDR) |
| R2c | inside + dam token | gauge inside the polygon sharing a >= 5-letter token with the linked dam name; strong R7 only | 0 | 0 |  |
| R2d | inside + operator pool | USACE/USBR pool series inside the polygon with strong or weak R7 (Lake Pepin) | 4 | 1 | Lake Pepin |
| R4b | state waiver | gauge inside the polygon or dam-confirmed | 1 | 1 | Flaming Gorge Reservoir |
| R5b | sibling waiver | same linked NID dam or polygons within 3 km | 2 | 2 | East Lake Tohopekaliga, Lake Strom Thurmond (Clarks Hill) |
| R8b | datum label waiver | absolute elevation (not derived) with strong R7 | 13 | 8 | Almanor, Banks Lake, Berryessa, Crescent Lake, Lake Cascade, Lake Cushman |
| R8c | datum via published pool | provider's own full-pool elevation within 3 ft of the directory's | 8 | 6 | Canyon, Lake McConaughy, Newfound Lake, Roosevelt, Sunapee Lake, Utah Lake |
| RGL | Great Lakes / big polygon-less lakes | Great Lakes, Green Bay, Lake of the Woods, Great Salt Lake: gauge within 80 km (150 km for IGLD85 CO-OPS stations) or a lake-wide series; level within 6 ft of the directory's | 14 | 14 | Green Bay, Lake Erie, Lake Erie, Lake Erie, Lake Erie, Lake Huron |
| RI | identity widening | inside the polygon with name similarity >= 0.5, or within 1.5 km with similarity >= 0.6 on a polygon >= 20 km2 (needed for the flagged tier) | 2 | 4 | Lake McConaughy, Lake Minnetonka, Lake Poinsett, Utah Lake |
| R1c | big-lake gauge | USGS LK / state or operator lake page named for the lake within 5 km of a polygon >= 20 km2 (Houghton Lake) | 2 | 1 | Houghton Lake |

**S-derived (derived elevation, capped at the flagged tier).** USGS gage height (00065) + site gage-datum altitude (`alt_va`, with a named vertical datum) from LK-type sites, or a provider-documented stage offset (Duke: gauge zero = published `Elevation` minus 100 ft; NWPS lists 660 ft for Norman, Duke's USACE-matched Jocassee offset 1010.01 ft over 1010 days). Calibration on the USGS sites that report both a published elevation and gage height live now (65 sites, 58 with a usable `alt_va`): 45 of 58 within 0.5 ft and 53 of 58 within 2 ft; the misses are sites with `alt_va` = 0.0 or river gauges, which the rule excludes (site type LK, or a lake-named non-river site). Of the 32 wave-1 stage-only lakes, 17 USGS sites give a derived elevation within 8 ft of the directory pool (`stage_plus_alt.json`); 14 of those turned out to have a published elevation parameter all along (finding 1).

**R7h (history envelope).** A flagged lake (deep drawdown or low-confidence full pool, which is why R7 only allows it as flagged) is promoted to core when its own daily history (>= 5 complete years) has a 99th percentile within +-8 ft of the directory full pool. This is not a second origin; it removes the specific doubt behind the flag (is this series really the lake's pool?). Negative control (`r7h_control.py`): for each of the 90 promoted lakes, the share of the other 337 bound lakes' series that would also pass against its full pool is a median 0.3% and a maximum 4.2% (Great Lakes at 577 ft, where many Michigan/Ohio lakes sit); since identity checks also constrain position, the conditional false-pass rate is lower. R7h cannot rescue a wrong directory pool: it fails for Spirit, Storm, Clear IA, Geneva.

**Fate of the 57 wave-1 flagged lakes** (can any be promoted by a second independent source?): still flagged 12; history envelope (R7h) 44; promoted by a second independent origin / strong series 1. A second independent origin is rare: western USBR reservoirs have no USGS/USACE elevation series at the dam, so only Red Lake MN (USGS agrees within 2 ft) was corroborated by a second origin. The other promotions come from R7h. The 12 still flagged (Alamo, Isabella, Catahoula Lake, Assawompset Pond, Long Pond (Lakeville), Rainy Lake, Fontana Lake, Bluewater Lake, Lahontan Reservoir, Rye Patch Reservoir, Walker Lake, Lake Washington) have short or no history, or a series that never reaches the stored pool (Alamo, Isabella, Catahoula, Bluewater, Walker). Of the 32 wave-1 stage-only lakes, 24 now bind (see finding 1 and the S-derived rule) and 8 remain stage-only.

## 6. NWPS gauges as DIRECT_LAKE_GAUGE, and what history exists

**Acceptability.** NWPS `HP` lake gauges are a relay: the `dataAttribution` field names the owner (USACE, USGS, MN DNR, Duke, TVA...). They are acceptable as a live DIRECT_LAKE_GAUGE source for lakes with no other feed (wave 1 bound 50 lakes this way; the wave-2 additions are Gaston, Smith Mountain, Thurmond GA, Liberty, Youghiogheny), because the level is the operator's, measured on the lake. They are never independent corroboration, and they are not always elevations: the Catawba chain (97-100 ft), Lake of the Woods (59 ft), Vermilion (56.8 ft) and the Idaho reservoirs are local stage, which only the documented-offset route (S-derived) can use. Two further traps: some NWPS gauges transmit twice a day (liveness is then ~20 h, which R6 accepts for daily feeds), and the anonymous listing endpoint allows only 10 requests per 5 minutes.

**History via the IEM HADS archive** (`mesonet.agron.iastate.edu/cgi-bin/request/hads.py`, NWS raw DCP data): probed for the 50 wave-1 NWPS lake gauges by sampling one 3-day window in 2004, 2008, 2012, 2016, 2019, 2022 (`hads_probe.py`). First year with data: 2012 for 35, 2016 for 9, 2022 for 3, 2008 for 1; none for 2. So HADS gives a maximum of about 13 calendar years (2013-2025) and nothing before 2012 (the TVA pool stream starts 2022-10-27, as the baselines thread found). `hads_history.py` converts 5-15-minute data to daily means (UTC date); gauges that transmit only once or twice a day were re-pulled with a 1-observation minimum. Resulting NWPS-chosen bindings with >= 5 complete years: see `history_class` in the verified file. USACE RVD AFOS text products are TVA/Huntsville-specific and did not help the others.

## 7. Coverage where wave 1 was weakest

Bound as core + flagged (wave 1 -> L3):

| State | Lakes | wave 1 | L3 |
|---|---|---|---|
| AK | 12 | 0+0 | 0+0 |
| CT | 12 | 0+0 | 0+0 |
| HI | 9 | 0+0 | 0+0 |
| NH | 12 | 0+0 | 6+0 |
| ME | 14 | 0+1 | 1+0 |
| WI | 13 | 1+0 | 9+1 |
| DE | 12 | 0+1 | 1+0 |
| RI | 12 | 1+0 | 1+0 |
| VT | 12 | 0+2 | 2+0 |
| MA | 12 | 0+2 | 0+2 |
| MD | 12 | 3+0 | 5+0 |
| NJ | 12 | 2+0 | 5+0 |
| PA | 14 | 5+0 | 6+0 |
| FL | 13 | 3+1 | 11+0 |
| SC | 12 | 6+0 | 9+3 |
| MI | 14 | 0+2 | 8+1 |
| MN | 14 | 3+2 | 9+2 |

By operator family (core + flagged, wave 1 -> L3): NONE 113 lakes 1+11 -> 19+9; OTHER 253 lakes 70+17 -> 132+11; USACE 168 lakes 131+8 -> 157+4; TVA 16 lakes 15+1 -> 15+1; USBR 71 lakes 41+20 -> 66+3.

## 8. Lakes still without a DIRECT binding

L3 leaves 194 lakes with no binding and 10 stage-only. Counts by what blocks them: live candidate failed review rules 119; no public level data found 70; STAGE_ONLY (local datum, no usable offset) 10; source exists but not live/stale 3; portal/PDF/login only 2. Full table with the best attempted source and the scout's evidence: `binding2/remaining_unbound.json`; per-lake dead-end records in `ledger/gaps.jsonl`.

**Lakes with no public level data (evidence in the ledger).** Alaska (all 12): no lake gauge in USGS or NWPS (two inactive NWPS gauges at Aleknagik and Lake Nerka); outlet-stream gauges exist (Kenai River below Skilak outlet, Kasilof, Kvichak at Igiugig) but are stream stage/discharge, i.e. PROXY only. Hawaii (all 9): no lake gauge anywhere. Connecticut (12): FirstLight phone line only; USGS has river gauges only. New Hampshire is the success story (6 lakes bound through NH DES). Delaware ponds: DNREC publishes nothing. Rhode Island salt ponds: tidal. The satellite route (Hydroweb, DAHITI, G-REALM) is limited to large lakes and was not tested; at best it gives a PROXY (water-extent or altimetry height with metre-scale error), which per the rubric cannot count as DIRECT_*.

**Bowfishing-relevant lakes still open (tier A and B, largest first).**

| Tier | Lake | km2 | status | Reason / proxy |
|---|---|---|---|---|
| A | Lake Maurepas (LA) | 236 | stage-only | only the Pass Manchac strait gauge (tidal, gauge datum -0.18 ft NAVD88, 3 years); stage-only. PROXY only |
| A | Sabine Lake (LA) | 230 | none | CO-OPS Port Arthur tide gauge 239 m from the polygon (tidal estuary level, 10 years); pending - not a lake pool |
| A | White Lake (LA) | 226 | none | CRMS marsh gauge last reported 2026-07-29 (stale). Proxy: none |
| A | Grand Lake (LA) | 161 | none | Catfish Point control-structure stage intermittent, last 2026-10-05 (190 h). Proxy: structure stage |
| A | Quabbin Reservoir (MA) | 97 | none | MWRA/DCR publish monthly elevations only (517.64 ft on 10/01). Proxy: monthly value |
| A | Chippewa Flowage (WI) | 60 | none | Xcel hydro page 404; no machine-readable level |
| A | Otter Tail Lake (MN) | 57 | none | MN DNR volunteer reads only (last 2026-04-29) |
| A | Pymatuning Reservoir (PA) | 56 | none | USGS record stopped 2026-06-04; PA DCNR publishes nothing |
| A | Lake Thompson (SD) | 56 | none | no gauge; nearest live SD lake level is Poinsett (NWPS PONS2) |
| A | Lake Anna (VA) | 52 | none | Dominion publishes no observed level; USGS sites are water-quality only |
| A | Lake Murray (OK) (OK) | 22 | none | OWRB lake-level page not reachable; nothing published |
| A | Lake Springfield (IL) | 16 | none | CWLP stick reading at the pump station, weekly web table (R3 pump-station name, not daily) |
| B | Salton Sea (CA) | 943 | none | USGS 10254005 stopped; no replacement |
| B | Sevier Lake (UT) | 496 | none | terminal playa, usually dry; USGS 10218500 is a different water body |
| B | Pyramid Lake (NV) | 441 | none | USGS 10336500 last observation 274 h old, non-recording |
| B | Yellowstone Lake (WY) | 342 | none | no lake gauge; the USGS site on the Yellowstone River at the outlet is a river gauge (rejected) |
| B | Moosehead Lake (ME) | 306 | none | Brookfield Safe Waters publishes the current value only (1026.12 ft, no history, no API) |
| B | Mono (CA) | 183 | none | 1-2 manual readings per year |
| B | Lake George (FL) | 176 | none | SJRWMD gauges are stream-side stations (Middle Rd) not named for the lake |
| B | Lake Vermilion (MN) | 157 | stage-only | NWPS LVOM5 and MN DNR gauge 73050001 read local stage (56.8 ft, no documented offset); MN DNR LakeFinder has monthly volunteer reads. Stage-only |
| B | Malheur Lake (OR) | 117 | none | USGS record ends 1989 |
| B | Chesuncook Lake (ME) | 76 | none | no public level (Brookfield publishes ponds near it but not this one) |
| B | Torch Lake (MI) | 76 | none | no gauge; Mullett Lake (USGS) is 45 km away - PROXY only |
| B | Eagle Lake (CA) | 73 | none | monthly manual reading in local news only |
| B | Burt Lake (MI) | 70 | none | Mullett Lake (sibling by outlet) is a PROXY, not DIRECT |
| B | Flagstaff Lake (ME) | 70 | none | Brookfield current value only |
| B | Lake Charlevoix (MI) | 70 | none | no gauge |
| B | West Grand Lake (ME) | 59 | none | USGS 01018900 and NWPS WGLM1 are live at 296.7 ft but the directory pool (259 ft) is wrong by 37 ft: R7 fails; fixing the directory value would bind it |
| B | Mooselookmeguntic Lake (ME) | 55 | none | Brookfield current value only |
| B | Big Stone Lake (SD) | 48 | none | NWPS BSLM5 twice-daily, 188 h old (R6) and in MN; history-only |
| B | Riffe Lake (WA) | 45 | none | NWRFC MSRW1 (10 days) and the stopped USGS 14234800; Tacoma Power publishes nothing machine-readable |
| B | Lake Waccamaw (NC) | 36 | none | no stage gauge (a groundwater well only) |
| B | Skaneateles Lake (NY) | 35 | none | USGS record ended 1995; city publishes yearly PDFs |
| B | Conowingo Reservoir (MD) | 35 | none | Constellation/MDE percent-full only |
| B | Elk Lake (MI) | 33 | none | USGS record ended |
| B | Bitter Lake (SD) | 32 | none | no gauge |
| B | Big Green Lake (WI) | 31 | none | USGS 434840089000001 is a local-stage lake gauge (6.7 ft, gauge altitude 790.13 ft NAVD88 gives 796.8 ft, plausible) but name similarity is only 0.42; stays unbound |
| B | Cranberry Lake (NY) | 28 | none | no gauge |
| B | Lake Bemidji (MN) | 27 | none | MN DNR volunteer reads only |
| B | Washoe Lake (NV) | 23 | none | USGS gauges discontinued |
| B | Waubay Lake (SD) | 23 | none | no gauge |
| B | Lake Wallenpaupack (PA) | 22 | none | Brookfield current value only (1174.54 ft) |
| B | Lac Courte Oreilles (WI) | 21 | none | no gauge |
| B | Candlewood Lake (CT) | 21 | none | FirstLight phone line only |
| B | Wachusett Reservoir (MA) | 16 | none | MWRA monthly elevations only |
| B | Chicot (AR) | 16 | none | MVK pumping-plant gauges 7 km from the polygon |
| B | Holter Lake (MT) | 15 | none | only tailwater stage is public |
| B | Lake Wawasee (IN) | 14 | none | USGS sites silent for 60-90 days on every parameter |
| B | Dillon Reservoir (CO) | 13 | none | CO DWR telemetry live (16 y) but no datum label and name similarity 0.58; left unbound |
| B | False River (LA) | 13 | none | MVN stage with no vertical-datum info (8 years) |
| B | Eleven Mile Reservoir (CO) | 13 | none | Denver Water percent-full PDF only |
| B | Lake Arthur (PA) | 12 | none | USGS 03106280 last observation 7 days old (R6), PA DCNR publishes nothing |
| B | Lake Washington (MS) | 12 | none | no gauge (USGS site is a groundwater well) |
| B | Lake Chesdin (VA) | 12 | none | ARWA homepage prints feet below normal pool, no absolute level |
| B | Georgetown Lake (MT) | 12 | none | USGS 12325000 live 6428.85 ft NAVD88 but the directory has no full pool (county report ~6429.5): cannot pass R7; one value in the directory would bind it |
| B | Moon Lake (MS) | 10 | none | no gauge |
| B | Sherman Reservoir (NE) | 10 | none | Nebraska DWEE AQUARIUS needs a click-through; not bypassed |
| B | Sangchris Lake (IL) | 9 | none | no public level |
| B | Loch Raven Reservoir (MD) | 9 | none | Baltimore DPW percent-full only |
| B | Enemy Swim Lake (SD) | 9 | none | no gauge |
| B | Lake of Egypt (IL) | 9 | none | no public level |
| B | Gull Lake (MI) | 8 | none | live candidate failed review rules |
| B | Eagle Nest Lake (NM) | 7 | none | USGS 07205500 live 8159.9 ft NGVD29 but the directory has no full pool: cannot pass R7 |
| B | Lake Metigoshe (ND) | 6 | none | USGS 05123000 stopped |
| B | Lake Freeman (IN) | 6 | none | NIPSCO Oakdale hydro page reads 610.37 ft (FERC target 610.35) but the plant is 1.8 km from the polygon (R1) |
| B | Prettyboy Reservoir (MD) | 6 | none | Baltimore DPW percent-full only |
| B | Lake Nockamixon (PA) | 6 | none | live candidate failed review rules |
| B | Timothy Lake (OR) | 6 | none | operator publishes nothing machine-readable |
| B | Rice Lake (IL) | 5 | none | no public level |
| B | Lake Macbride (IA) | 4 | none | USGS 05453500 stopped |
| B | Big Creek Lake (IA) | 3 | none | USACE MVR stage with unconfirmed datum |
| B | Lake Ogallala (NE) | 2 | none | no feed (the Kingsley Dam gauge is McConaughy's pool) |
| B | Nelson Lake (ND) | 2 | none | no gauge |

**Tier-A lakes newly bound in wave 2:** Almanor (CA), Apopka (FL), Banks Lake (WA), Bay Springs Lake (MS), Berryessa (CA), Castle Rock Lake (WI), Clarks Hill / J.S. Thurmond (GA), Clinton Lake (IL), East Lake Tohopekaliga (FL), Flaming Gorge Reservoir (WY), Griffin (FL), Harris (FL), Houghton Lake (MI), Kerr Lake (John H. Kerr) (NC), Lake Cascade (ID), Lake Gaston (VA), Lake Hickory (NC), Lake James (NC), Lake Jocassee (SC), Lake Keowee (SC), Lake McConaughy (NE), Lake Minnetonka (MN), Lake Norman (NC), Lake Oahe (ND), Lake Roosevelt (FDR) (WA), Lake Sakakawea (ND), Lake Strom Thurmond (Clarks Hill) (SC), Lake Wateree (SC), Lake Wisconsin (WI), Lake Wylie (SC), Logan Martin (AL), Potholes Reservoir (WA), Smith Mountain Lake (VA).


## 9. Blockers and actions

- **B-gaps-003 / M-G01 (high):** decide whether the labelled v1.1 rules and R7h may be used for the reviewed-binding batch. Without them core coverage is the L1 figure.
- **B-gaps-002 / M-G02 (medium):** permission for undocumented-but-public operator endpoints (Duke Lake View is the largest block, 8 lakes; also SRP, Brookfield Safe Waters, utahlake.gov, CNPPID, WPS, NIPSCO, Alliant).
- **B-gaps-006 / M-G03 (low):** review the directory full pools listed in section 4.
- **B-gaps-001 (medium, no action possible):** about 70 lakes have no public level source at all.
- **M-B02 (carried over, high):** human review of the machine-verified ledger.

## 10. Honest limits

- Everything is machine-verified on a single-day liveness snapshot (2026-10-13); a seasonal outage turns a lake `REJECT`. Weekly re-probing (wave-1 section 6) still applies.
- The v1.1 rules and R7h were designed after seeing wave-1 and wave-2 failures, so their error rate is not measured by a hold-out. The rule ablation and the negative control bound the damage but do not replace review. Spot-check: of the {len(new)} newly bound lakes, the station names and levels were read by hand against dam names and domain knowledge; three classes of false positive were found and removed during the work (river gauges whose gage height + altitude coincidentally sits near the lake, outlet/pass/canyon gauges, and a pump-station reading).
- Derived (S-derived) elevations depend on a gauge-datum altitude or a provider-documented offset; Duke's offsets agree with NWPS metadata and the USACE series for two lakes but were not independently surveyed. They stay in the flagged tier unless R7h or a second origin promotes them.
- Several operator feeds are undocumented web-app endpoints (authority 7 in the ledger) and can change without notice. History for those is mostly 2-4 years.
- Satellite altimetry (DAHITI, Hydroweb, G-REALM) was not tested; it would be PROXY only.
- The bowfishing tier is a heuristic. Wave-2 effort followed it, but the verification itself is lake-blind.

## 11. Reproduce

```
python research/lake-brain/binding2/profile_unbound.py      # unbound profile + tier
python research/lake-brain/binding2/reprobe_usgs.py         # wave-1 probe fix
python research/lake-brain/binding2/usgs_scan.py            # live USGS scan -> cand/usgs_scan.jsonl
python research/lake-brain/binding2/src_se.py | src_ne.py | src_mw.py | src_west.py   # scouts -> cand/*.jsonl, history/
python research/lake-brain/binding2/hads_probe.py; hads_history.py; hads_extra.py; coops_history.py
python research/lake-brain/binding2/assemble_v2.py          # verify (verify2/verify11 -> wave-1 verify.evaluate), history, R7h, summary, verified_bindings_v2.csv
python research/lake-brain/binding2/ablation.py; r7h_control.py; remaining.py; state_cov.py; make_doc.py; write_ledger2.py
```
