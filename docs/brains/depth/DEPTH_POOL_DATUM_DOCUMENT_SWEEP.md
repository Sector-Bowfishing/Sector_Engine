# Depth pool-datum document sweep

Date 2026-10-14. Evidence work only: nothing deployed, no production change, nothing sent. Machine form: `jobs/depth-brain/depth_brain/data/proposals/datum_pairings_2.json` (schema `depth-datum-proposals-v1`). Per-lake CSV: `docs/brains/depth/data/datum_doc_sweep_results.csv`. Scripts: `research/depth/datum_doc_texoma.py`, `datum_doc_merge.py`, `datum_doc_report.py`. Downloads (outside git): `~/Desktop/Development/Sector_Research_Data/depth-brain/datum4/`.

Target: the 58 plausible lakes in `depth_datum_unlock_queue.csv` whose only gap is the datum of the pool figure (RISE, NWPS, Duke excluded). The level side is already fixed (USGS 62614 NGVD29, 62615 NAVD88, CWMS/A2W location stamp). The question per lake was: does a fetched document state the vertical datum of THAT pool figure (or an unambiguous elevation-datum statement covering it)? Four parallel searchers each took about 14 lakes; the lead re-checked conflicts.

Note: the task brief counted about 66 lakes (other-operator 17); the CSV has only 9 plausible `other-operator` rows (37 blocked, 9 plausible), so the target set is 58.

## 1. Result

| Group | Lakes | SAME_DATUM | SAME_SOURCE | INCOMPATIBLE | UNKNOWN |
|---|---|---|---|---|---|
| usgs-pairing | 27 | 10 | 0 | 3 | 14 |
| cwms-pool-datum-unstated | 13 | 7 | 0 | 1 | 5 |
| a2w-pool-datum-unstated | 7 | 2 | 0 | 0 | 5 |
| a2w-local-or-blank | 1 | 0 | 0 | 0 | 1 |
| other-operator | 9 | 3 | 2 | 0 | 4 |
| conversion-disabled | 1 | 0 | 0 | 1 | 0 |
| texoma (extra) | 1 | 0 | 1 | 0 | 0 |
| Total | 59 | 22 | 3 | 5 | 29 |

Texoma is outside the 58 (it is not in the unlock queue). INCOMPATIBLE lakes are not failures: the documents prove the pool and the level are on different datums, and conversion is disabled, so they stay blocked until a conversion rule is adopted or a level on the pool's datum is found.

## 2. Method

1. Re-fetch the manifest `referencePoolSource` and read it for datum words (NGVD, NAVD, "plant datum", "msl").
2. Look for a document that states the datum for the same figure: USGS Water Data Report station entries (datum of gage plus the pool elevation in one entry), FERC notices and licence orders, USACE water control plans and pertinent-data sheets, state reports with datum footnotes, operator pages.
3. For USACE lakes also query CWMS: pool-like level equal to the figure within 0.06 ft, and the stamped `vertical-datum` of that level's location versus the series location.
4. Accept only: explicit datum for the figure; or "all elevations NGVD29" style statements in the same document; or the CWMS value match. Not accepted: "msl", "mean sea level", "above sea level", derived closeness.
5. Level datum vs pool datum differ (NGVD29 vs NAVD88, local datum) -> INCOMPATIBLE, no conversion.

## 3. Document types that worked (SAME_* proposals)

| Document type | Resolved |
|---|---|
| USGS Water Data Report station entry ("datum of gage is ... NGVD of 1929" plus the pool in the same entry) | Great Sacandaga, Wanaque, C.J. Strike, Jordan Lake NC, Bluewater, Billy Chinook, Henrys (derived: gage datum + gage height) |
| CWMS location vertical-datum plus value-matched pool level | Rend Lake, Columbus, Roosevelt, Kissimmee, East Toho (plus SFWMD memo) |
| USACE water control plan / pertinent data stating NGVD29 | Kerr (both lake records), Seminole |
| FERC notices stating "NGVD" for the figure | Cheat Lake, Claytor, Istokpoga (SFWMD MFL report) |
| Operator page with datum on the figure | Smith Mountain, Round Valley (NJWSA, NAVD88) |
| State report with datum footnote | Geist (NAVD88), Eagle Creek and Toledo Bend (incompatible) |
| USGS scientific investigations report | Pend Oreille |

Low yield: USBR project pages, ODNR fishing maps, NRC environmental documents, FERC EAs and most operator pages, which give "msl" or no datum. Wayback was offline during part of the run and several FERC/state PDFs returned 403 (logged per lake in `deadEnds` in the JSON).

## 4. Traps found

* T23 "msl" is not a datum. Hebgen, Greenwood, Chelan, Palisades, Hoover, Ross Barnett, Jackson, Taneycomo, Clinton, Hopatcong, Jordan (AL) are only "msl"/"above sea level".
* T24 Local datums look like elevations: Murray ("plant datum"), Almanor ("PG&E datum"), Coeur d'Alene ("Avista datum"), McConaughy (CNPPD Central datum = 3,266.4 ft NAVD88, so 1.4 ft off), Tahoe (USBR datum 6,229.1 = 6,227.96 ft above sea level, 1.14 ft off the NGVD29 CWMS series). A local datum is SAME_SOURCE at best.
* T25 CWMS stamp vs Corps wording conflict. Mark Twain: CWMS series location is stamped NAVD88 and holds 606.0, but a 2021 Corps update (relayed by the Hannibal Courier-Post) says "Normal lake elevation is 606.0 NGVD". The agent's SAME_DATUM was demoted to UNKNOWN by the lead. Rend Lake has the same structure (project location unstamped, series stamped NAVD88) but no contradicting document was found; it stays SAME_DATUM at medium confidence.
* T26 Manifest figure typo candidate: Lake Wisconsin stored 774.4 while the FERC notice says normal pool 744.4 ft NGVD. Left UNKNOWN; correcting the figure would likely resolve it.
* T27 Missouri mainstem projects are on local project datum / NGVD29 and not converted to NAVD88 (Master Manual), while the USGS 62615 series for Francis Case is NAVD88: INCOMPATIBLE.
* T28 NJWSA switched its reported elevations from NGVD29 to NAVD88 on 2025-11-19. Round Valley (level series NAVD88) is consistent; Spruce Run's pool is NAVD88 while the USGS 62614 series is NGVD29: INCOMPATIBLE.
* T29 Kissimmee's 53 ft is a regulation-schedule zone value (series `Elev-Zone ZoneB1_NGVD`), not a conservation pool; East Toho's level series name points at the Lake Tohopekaliga location (both NGVD29). Medium.
* T30 Derived figures: Henrys Lake 6473.86 is the sum of the WDR gage datum 6457.16 and gage height 16.7, not a printed number.
* T31 The Indiana drought report footnotes differ per reservoir: footnote 3 (NAVD88) sits on Eagle Creek and Geist, footnote 1 (NGVD29) on others; read footnote placement from the table, not the page header.

## 5. Texoma

The TWDB 2002 survey (`Texoma2002_FinalReport.pdf`) states: the vertical datum is that of the USACE lake elevation gauge at Denison Dam, "USCE 07331500 USCOE Lk Texoma nr Denison, TX", "reported as mean sea level (msl)". It does not name NGVD29. The 620.0 ft figure is the survey boundary (USGS quad contour), conservation pool is 617.0 ft. The Brain level is the same gauge (CWMS SWT:DENI, project location stamped NGVD29; levels Top of Constant Conservation 617.0). So the survey elevations are on the gauge scale of the Brain level: SAME_SOURCE, medium, sigma 0.1, re-base to 617.0 (shift 3.0 ft from 620.0). What no document states: that the gauge datum in 2002 was NGVD29 (USGS site record lists NGVD29 only with placeholder altitude 0). Needed to raise to high: a USACE Tulsa pertinent-data sheet for Denison Dam stating NGVD29.

## 6. Per-lake outcome

| Lake | Group | Decision | Level / pool datum | Conf | Doc type | Still needed (UNKNOWN) |
|---|---|---|---|---|---|---|
| Bluewater Lake|NM | usgs-pairing | SAME_DATUM | NGVD29 / NGVD29 | medium | usgs-wdr-gage-datum |  |
| C.J. Strike Reservoir|ID | usgs-pairing | SAME_DATUM | NGVD29 / NGVD29 | high | usgs-wdr-gage-datum |  |
| Cheat Lake|WV | usgs-pairing | SAME_DATUM | NGVD29 / NGVD29 | high | ferc-order |  |
| Claytor Lake|VA | cwms-pool-datum-unstated | SAME_DATUM | NGVD29 / NGVD29 | medium | ferc-order |  |
| Columbus Lake|MS | usgs-pairing | SAME_DATUM | NGVD29 / NGVD29 | medium | cwms-level |  |
| East Lake Tohopekaliga|FL | cwms-pool-datum-unstated | SAME_DATUM | NGVD29 / NGVD29 | medium | state-report |  |
| Geist Reservoir|IN | usgs-pairing | SAME_DATUM | NAVD88 / NAVD88 | medium | state-report |  |
| Great Sacandaga Lake|NY | usgs-pairing | SAME_DATUM | NGVD29 / NGVD29 | medium | usgs-wdr-gage-datum |  |
| Henrys Lake|ID | usgs-pairing | SAME_DATUM | NGVD29 / NGVD29 | medium | usgs-wdr-gage-datum |  |
| Istokpoga|FL | a2w-pool-datum-unstated | SAME_DATUM | NGVD29 / NGVD29 | medium | state-report |  |
| Jordan Lake|NC | cwms-pool-datum-unstated | SAME_DATUM | NGVD29 / NGVD29 | medium | usgs-wdr-gage-datum |  |
| Kerr Lake (John H. Kerr)|NC | cwms-pool-datum-unstated | SAME_DATUM | NGVD29 / NGVD29 | high | usace-water-control-plan |  |
| Kerr Reservoir (Buggs Island)|VA | usgs-pairing | SAME_DATUM | NGVD29 / NGVD29 | high | usace-water-control-plan |  |
| Kissimmee|FL | cwms-pool-datum-unstated | SAME_DATUM | NGVD29 / NGVD29 | medium | cwms-level |  |
| Lake Billy Chinook|OR | usgs-pairing | SAME_DATUM | NGVD29 / NGVD29 | high | usgs-wdr-gage-datum |  |
| Lake Pend Oreille|ID | a2w-pool-datum-unstated | SAME_DATUM | NGVD29 / NGVD29 | medium | usgs-sim-report |  |
| Rend Lake|IL | cwms-pool-datum-unstated | SAME_DATUM | NAVD88 / NAVD88 | medium | cwms-level |  |
| Roosevelt|AZ | other-operator | SAME_DATUM | NGVD29 / NGVD29 | medium | cwms-level |  |
| Round Valley Reservoir|NJ | other-operator | SAME_DATUM | NAVD88 / NAVD88 | high | operator-page |  |
| Seminole|GA | cwms-pool-datum-unstated | SAME_DATUM | NGVD29 / NGVD29 | high | usace-pertinent-data |  |
| Smith Mountain Lake|VA | other-operator | SAME_DATUM | NGVD29 / NGVD29 | high | operator-page |  |
| Wanaque Reservoir|NJ | usgs-pairing | SAME_DATUM | NGVD29 / NGVD29 | high | usgs-wdr-gage-datum |  |
| Lake McConaughy|NE | other-operator | SAME_SOURCE | LOCAL / LOCAL (CNPPD/Central datum) | medium | usgs-report + operator-page |  |
| Lake Texoma|TX | texoma (extra) | SAME_SOURCE | NGVD29 / NGVD29 (Denison gauge datum; 2002 report says only msl) | medium | state-report+cwms-location | USACE Tulsa District statement that the Denison gauge datum has been NGVD29 since before 2002 (pertinent data sheet) |
| Lake Winnipesaukee|NH | other-operator | SAME_SOURCE | NHDES operating datum (same record as pool figure) / NGVD29 | medium | operator-page |  |
| Eagle Creek Reservoir|IN | usgs-pairing | INCOMPATIBLE | NGVD29 / NAVD88 | high | state-report |  |
| Lake Francis Case|SD | usgs-pairing | INCOMPATIBLE | NAVD88 / LOCAL/NGVD29 (project datum; not NAVD88) | medium | usace-master-manual | Fort Randall WCM Table I-1 datum adjustments (local/NGVD29 -> NAVD88) from USACE Omaha District (NWO) Water Management. |
| Lake Tahoe|NV | cwms-pool-datum-unstated | INCOMPATIBLE | NGVD29 / LOCAL (Lake Tahoe Datum / USBR datum) | medium | usgs-wri-report + cwms-location |  |
| Spruce Run Reservoir|NJ | usgs-pairing | INCOMPATIBLE | NGVD29 / NAVD88 | high | operator-page |  |
| Toledo Bend Reservoir|TX | conversion-disabled | INCOMPATIBLE | NAVD88 / NGVD29 | high | state-report |  |
| Almanor|CA | other-operator | UNKNOWN | LOCAL / PG&E datum (LOCAL) | high | operator-doc (local datum) | PG&E (FERC P-2105) statement of PG&E datum offset to NGVD29/NAVD88 and that CDEC ALM sensor uses PG&E datum. |
| Anderson Ranch Reservoir|ID | a2w-pool-datum-unstated | UNKNOWN | NGVD29 / None | medium | none | USBR Pacific Northwest Region (Snake River Area Office) dam data sheet stating datum of 4196 ft normal pool. |
| Berryessa|CA | other-operator | UNKNOWN | LOCAL / None | medium | none | Reclamation Mid-Pacific (Monticello Dam) pertinent data / CDEC station documentation stating datum for 440 ft and the BER RES_ELE series |
| Buckeye Lake|OH | usgs-pairing | UNKNOWN | NGVD29 / None | medium | none | ODNR Dam Safety / Buckeye Lake dam rehabilitation design documents stating pool datum (NGVD29 vs NAVD88) and exact pool value |
| Clinton Lake|IL | usgs-pairing | UNKNOWN | None / None | medium | none | Constellation/Illinois DNR/ISWS statement of Clinton Lake normal pool 690 ft datum and USGS gage datum for the Clinton Lake station |
| Coeur d'Alene|ID | a2w-pool-datum-unstated | UNKNOWN | NGVD29 / None | medium | ferc-order | Avista Hydro (FERC P-2545 licence exhibits) or USGS gage 12415500 station description giving the Avista datum offset to NGVD29/NAVD88. |
| Grand Lake St. Marys|OH | usgs-pairing | UNKNOWN | NGVD29 / None | medium | none | ODNR Division of Parks/Watercraft (or Ohio DNR dam safety / NID record for Grand Lake St. Marys dam) stating datum of the 870.6 ft normal pool. |
| Hebgen Lake|MT | usgs-pairing | UNKNOWN | NGVD29 / None | medium | operator-annual-report | FERC licence order or Exhibit/Article 403 drawing for P-2188 (or NorthWestern Energy hydro compliance staff) stating the datum of 6534.87 ft; NWE can confirm. |
| Hoover Reservoir|OH | usgs-pairing | UNKNOWN | NGVD29 / None | medium | none | City of Columbus Division of Water (Hoover Dam owner) or Ohio DNR Dam Safety (as-built/inspection report) stating the crest-gate/normal-pool elevation datum; or NID record with datum note. |
| Indian Lake|OH | usgs-pairing | UNKNOWN | NGVD29 / None | medium | none | ODNR Division of Parks/Dam Safety or Ohio dam-safety record (Indian Lake / Grand Lake St Marys-type canal reservoir) stating the datum of 996.3 ft; or USGS 03260500 WDR gage datum line |
| Jackson Lake|WY | a2w-pool-datum-unstated | UNKNOWN | NGVD29 / None | medium | none | Reclamation Pacific Northwest (Snake River Area) or Jackson Lake Dam SOP/Hydromet datum statement for 6,769 ft. |
| Jordan|AL | cwms-pool-datum-unstated | UNKNOWN | NGVD29 / None | medium | none | FERC P-618 Exhibit/licence drawing or Alabama Power statement of datum for 252 ft. |
| Lake Bistineau|LA | cwms-pool-datum-unstated | UNKNOWN | NAVD88 (CWMS MVK location); USGS 62614 is NGVD29 / None | medium | none | Louisiana Dept of Wildlife & Fisheries (Lake Bistineau dam) or USACE Vicksburg District (MVK) Water Management stating the datum of the 141.0 ft pool and the CWMS elevation series, and whether the CWMS series is converted to NAVD88. |
| Lake Chelan|WA | a2w-local-or-blank | UNKNOWN | UNKNOWN (A2W blank) / None | medium | none | Chelan PUD (P-637 Article 405 lake level plan) datum statement for 1,100 ft and for the forebay series. |
| Lake Cushman|WA | other-operator | UNKNOWN | UNKNOWN / None | medium | none | Tacoma Power Cushman (P-460) licence/settlement exhibit stating datum, and the NWRFC HF station datum. |
| Lake D'Arbonne|LA | usgs-pairing | UNKNOWN | NGVD29 / None | medium | none | LDWF or Bayou D'Arbonne Lake Watershed District (or NID record) stating datum of 80 ft pool stage. |
| Lake Greenwood|SC | usgs-pairing | UNKNOWN | UNKNOWN (00062 is site-specific) / None | medium | ferc-notice | Greenwood CPW or FERC P-2077 exhibit/gage datum statement for the 439 ft and USGS gage datum for the 00062 series. |
| Lake Hopatcong|NJ | usgs-pairing | UNKNOWN | None / None | medium | none | NJDEP Dam Safety / Lake Hopatcong Water Level Management Plan stating spillway elevation datum, and the USGS 01455400 gage datum for 00065 |
| Lake Marion|SC | usgs-pairing | UNKNOWN | None / None | medium | none | FERC P-199 license exhibit/Santee Cooper (SCPSA) or USGS SC WSC statement of datum for the 00062 Lake Marion gage and for the 75.5 ft rule curve |
| Lake Monticello|SC | usgs-pairing | UNKNOWN | None / NAVD88 | high | ferc-notice | USGS SC Water Science Center (or USGS site datum/rating description) confirming the 00062 datum for 02160900 (NAVD88 expected but undocumented), or a 62615 series |
| Lake Murray (SC)|SC | usgs-pairing | UNKNOWN | UNKNOWN (00062 site-specific) / plant datum (LOCAL) | high | operator-doc (local datum) | Dominion Energy (Saluda hydro, FERC P-516) plant-datum-to-NGVD29 relationship and the datum of USGS 00062 gage; or a FERC P-516 licence/exhibit stating NGVD29 for 360 ft. |
| Lake Taneycomo|MO | usgs-pairing | UNKNOWN | NAVD88 / None | high | ferc-order (msl only) | Liberty/Empire District (Ozark Beach, FERC P-2221) or USACE Little Rock licence exhibit stating NGVD29 or NAVD88 for 701.1 ft. |
| Lake Wisconsin|WI | other-operator | UNKNOWN | NGVD29 / NGVD (document figure 744.4) | medium | ferc-order | Correct the reference pool figure (744.4 vs 774.4) then rerun; Alliant/FERC P-1981 can confirm. |
| Lay|AL | cwms-pool-datum-unstated | UNKNOWN | NGVD29 / None | medium | none | Alabama Power / FERC P-2146 license exhibit stating Lay normal pool 396 ft datum (NGVD29 vs NAVD88) |
| Mark Twain Lake|MO | cwms-pool-datum-unstated | UNKNOWN | NAVD88 / None | medium | cwms-level (conflict) | USACE St. Louis District (Mark Twain Lake project office / Water Control) statement of the vertical datum of the CWMS Mark Twain Lk-Salt elevation series and of the 606.0 ft conservation pool |
| Palisades Reservoir|ID | a2w-pool-datum-unstated | UNKNOWN | NGVD29 / None | medium | none | Reclamation Snake River Area Office / Pacific Northwest Hydromet metadata stating the vertical datum of the PAL forebay elevation series and the 5620 normal water surface. |
| Percy Priest Lake|TN | a2w-pool-datum-unstated | UNKNOWN | NGVD29 / None | medium | none | USACE Nashville District pertinent-data sheet or Cumberland basin water-control manual stating elevation datum for 490/summer pool; Nashville District water management office. |
| Ross Barnett Reservoir|MS | cwms-pool-datum-unstated | UNKNOWN | NGVD29 (CWMS MVK location) / None | medium | none | Pearl River Valley Water Supply District (therez.ms) or USACE Vicksburg District Water Management stating the datum of the 297.5 ft summer pool. |
| Rye Patch Reservoir|NV | usgs-pairing | UNKNOWN | UNKNOWN (00062 site-specific) / None | high | none | USBR Lahontan Basin Area Office / Reclamation dam data (data.usbr.gov) stating vertical datum of Rye Patch pool, plus datum of USGS 10334500 00062. |

## 7. What remains blocked, and the resolver

* Operator datum statement needed (USACE districts): Jackson, Palisades, Anderson Ranch, Jordan AL, Lay (APCO), Percy Priest, Bistineau (state/USACE Vicksburg), Ross Barnett (Pearl River Valley WSD), Coeur d'Alene (Avista: offset of Avista datum to NGVD29), Mark Twain (USACE St. Louis: datum of the CWMS series).
* State/operator pages with only "msl": Hebgen, Greenwood, Marion, Murray (Dominion/Santee Cooper plant datum offset), Indian, Buckeye, Hoover, Grand Lake St. Marys (ODNR), D'Arbonne (LDWF), Hopatcong, Clinton, Taneycomo, Rye Patch, Berryessa, Almanor, Cushman, Chelan.
* Monticello: pool is NAVD88 per FERC notice but the USGS 00062 scale is undocumented (USGS Water Science Center or Dominion).
* Lake Wisconsin: correct the manifest figure then re-run.
* INCOMPATIBLE (need a conversion rule or a same-datum level): Tahoe, Spruce Run, Eagle Creek, Toledo Bend, Francis Case.
