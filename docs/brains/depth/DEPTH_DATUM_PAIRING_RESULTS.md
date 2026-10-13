# Depth Brain: Datum Pairing Results

Date 2026-10-14. Evidence work only: nothing deployed, no production change, nothing sent. Machine form: `jobs/depth-brain/depth_brain/data/proposals/datum_pairings.json` (schema `depth-datum-proposals-v1`, 180 lakes). Scripts: `research/depth/datum_pair_*.py`. Small data: `docs/brains/depth/data/datum_pairings_cwms.csv`, `datum_pairings_usgs.csv`. Raw API responses are cached outside git in `~/Desktop/Development/Sector_Research_Data/depth-brain/datum2/`.

All facts below were fetched on 2026-10-13/14 from the public USACE CWMS Data API, USACE Access2Water (A2W) reporting API and USGS waterservices. Nothing is inferred from "the numbers look close" alone.

## 1. Result

180 blocked lakes examined (107 USACE-served, 73 USGS-served). 82 get a defensible SAME_SOURCE / SAME_DATUM proposal; 98 stay UNKNOWN. No lake was loosened to raise a count.

| Group | Lakes | SAME_SOURCE | SAME_DATUM | UNKNOWN | Main unresolved reason |
|---|---|---|---|---|---|
| 1. A2W project datum LOCAL or blank | 24 | 20 | 1 (Harlan, via USGS 62614 pairing) | 3 (Lake Pepin, Red Lake, Lake Chelan) | no CWMS pool level / pool figure has no source |
| 2. A2W NGVD29/NAVD88 tagged, pool datum unknown | 36 | 18 | 10 | 8 | pool figure not equal to any CWMS pool-like level (document only) |
| 3. CWMS-served, pool is a URL/document | 47 | 16 | 13 | 18 | same; 2 with an unstamped project location (Rend, Mark Twain) |
| 4. USGS-served (62614/62615/00062/00065) | 73 | 0 | 4 (Thurmond GA+SC, W.F. George GA+AL) | 69 | pool document states no datum / 00065 |
| Total | 180 | 54 | 28 | 98 | |

Confidence of the 82 proposals: 43 high, 39 medium (medium = pool figure came from a document and was matched by value to a CWMS level, series location unstamped, or the pairing is circular).

## 2. Method that generalised: CWMS location-level matching (cwms-location)

For every USACE-served lake:

1. R0 Same series. The tsid A2W shows is retrieved from the CWMS Data API; the value equals A2W at the same instant (all checked, difference 0.0 ft). A2W is therefore a view of the same CWMS record.
2. R1 Pool = a CWMS location level. List `/levels?office=X&level-id-mask=<project>*` and keep Elev levels with a pool-like name (Top of Conservation / Normal / Multi-Purpose / Gross Pool / Power / Recreation, Bottom of Flood) whose constant or seasonal value equals the manifest pool figure within 0.06 ft. A numeric coincidence with a non-pool level (Max Non-Damaging, x% Flood Storage, Top of Flood) is rejected. This also re-binds document-sourced pools: if the document figure equals the CWMS level the reference can simply be the CWMS level.
3. R2 Same CWMS location for series and level: SAME_SOURCE. One location has one native datum, so the shift is exact whatever the tag says, LOCAL included. sigma 0.
4. R3 Different locations of one project (e.g. `Bull_Shoals_Dam-Headwater` series, `Bull_Shoals_Dam` level): SAME_DATUM only when both are stamped with the same NGVD29/NAVD88. sigma = max(0.15, |mean USGS offset|, min(2 SD, 1.0)); 0.15 if only metadata. The sub-location is a separate CWMS location and can carry a different tag, so the tag of each is read separately.
5. R4 Series LOCAL and the only pool level is NGVD29 at another location: only if an independent USGS 62614 series on the same pool equals the series (|mean| <= 0.15 ft and the other datum is at least 0.15 ft worse). Used once (Harlan County).
6. Independent check where possible: USGS lake elevation series (62614/62615/72020/00062; never 00065) within 3 km, compared at identical UTC instants over 365 days: n, mean, SD, min, max, half-year and per-quarter means. Expected offsets: 0 if the datums are equal, the measured or NCAT NAVD88-NGVD29 shift if they differ. Pairings were run for every lake with a gauge in range (see `datum_pairings_cwms.csv`); most NGVD29-tagged series agree with 62614 to within 0.05 ft mean.

Hartwell-pattern pairing (authoritative CWMS location datum + independent USGS series + offset) was used for group 4: Thurmond (USGS 02193900 00062 minus CWMS SHEF pool series, NGVD29 location: +0.178 ft mean, 0.084 SD, n 8,621, quarters 0.13 to 0.20; NAVD88 would be about -0.66) and W.F. George (USGS 00062 minus independent USGS 0234296910 62614 gauge: +0.04 ft, SD 0.07, n 35,000; CWMS Top of Conservation 190 ft stamped NGVD29).

## 3. Traps found (new, beyond DEPTH_DATUM_AUDIT T1-T12)

| # | Trap | Evidence |
|---|---|---|
| T13 | The project-level CWMS location and the series sub-location carry separate datum tags (`X-Headwater`, `X-Lake`, `X-Pool` vs `X`). Token comparison of names (current `cwms_project`) misses these and blocks ~25 lakes that are in fact stamped identically (Bluestone, Sutton, Tappan, Shenango, Tygart, Milton ...). | `cwms_pairs.json` location records |
| T14 | A2W project tag LOCAL does not describe the pool level's location: for Clinton, Melvern, Milford, Pomona, Smithville, Pomme de Terre, Tuttle Creek, Harlan the "Top of Multi-Purpose" level is stored at a sibling location stamped NGVD29 while the series location is LOCAL; the same value is also stored at the LOCAL location. Both are equal numerically. | levels API |
| T15 | CWMS series whose version names USGS (`Raw-USGS`, `USGS-raw`, `USGS-rev`) are the USGS feed (Falls, Jordan, Kerr, W.F. George, Seminole, Salamonie): pairing them with that gauge returns offset 0.000 and proves nothing about the CWMS tag. Flagged `circularFeed` and excluded as independent evidence. Same for SD <= 0.01 and mean <= 0.01. | usgs_pairs.json |
| T16 | Nearest-gauge matching can pick a different water body: Claytor Lake picked Little River Reservoir (offset -73.6 ft). Rejected by magnitude/SD guard; Claytor stays UNKNOWN. | usgs_pairs.json |
| T17 | Manifest pool figure disagrees with the CWMS level by 1-2 ft (document vs district): Anderson Ranch 4196 vs Top of Normal 4194; Palisades 5620 vs 5619; Jackson 6769 vs 6768; Seminole 77 vs 76-78; Red Lake 1175 vs 1174.5. These are not datum conflicts but must not be auto-rebound. Alternatives are listed in the JSON (`alternativeReference`). | levels API |
| T18 | Series version names can carry the datum: Lake Pepin and Red Lake series are `best-MSL1912` (Sea Level Datum of 1912). The level is therefore not NGVD29/NAVD88; their pools have no source. | A2W tsids |
| T19 | Measured NAVD88-NGVD29 shifts at sites with both 62614 and 62615 differ from NCAT by up to 0.1 ft (Falls -0.90 vs NCAT -0.85; Ashtabula +1.23 vs +1.18; Spruce Run -0.80 matches NJWSA). Where the shift is under 0.35 ft (Louisiana, W.F. George) a near-zero offset cannot discriminate the datums; those cases are labelled medium. | usgs_lakes.json |
| T20 | CWMS API `vertical-datum-info.native-datum` is `OTHER` for every LOCAL series; some series return `null`. NWDP/MVP/LRN series often have no vdi at all. The location tag is the only stamp for those. | timeseries API |
| T21 | CWMS series for a daily or manual (`~1Day`, MANUAL) product (Don Pedro) cannot be compared at identical instants with a USGS iv series (SD 0.59, max 11 ft); pairing discarded. | usgs_pairs.json |
| T22 | Document route is low yield: the only SAW pertinent-data text fetched (Jordan Lake, BEJPERT.TXT) says "msl" without naming NGVD29/NAVD88; the SAM Seminole PDF is not text-extractable; the Bistineau LDWF archive page could not be fetched. "msl" is not evidence of NGVD29. | WebFetch |

## 4. Group notes

* Group 1 (LOCAL/blank). 20 of 24 are exact SAME_SOURCE because the pool level lives under the same CWMS location as the live series. This does not make the level an NGVD29/NAVD88 elevation: levelDatum is recorded as LOCAL. Rathbun (906.9) is a case in point, the earlier audit found it NAVD88-like while Kanopolis is NGVD29 numerically (USGS 62614 offset -0.013 ft, SD 0.02, n 8,218); neither matters for the shift. Falls Lake and Lake Chelan have a blank A2W tag: Falls is SAME_SOURCE (same location NEU FLP) with the datum unstated in CWMS, but its series equals USGS 62614 (NGVD29) to 0.001 ft (circular feed, fixes the numbers' datum); Chelan has no pool level.
* Group 2 (A2W NGVD29/NAVD88 tagged). 28 of 36 resolved. 
* Group 3 (CWMS-served). 29 of 47 resolved. Unresolved: 14 with no CWMS pool level (APCO, SFWMD, MVK, Corps SAW/SAM documents), Rend Lake and Mark Twain (project location unstamped while series location is NAVD88), Cross Lake and Lake Bistineau (series NAVD88; USGS 62614 minus CWMS = +0.13/+0.157 ft agrees with the NAVD88 tag, the earlier note that the LDWF pool document says NGVD would make these INCOMPATIBLE, but that document was not re-fetched here).
* Group 4 (USGS). The level datum of 62614/62615 lakes is fixed by parameter definition; the blocker is always the pool datum, which no fetched source states. 00062 sites: measured offsets to the site's own 62615 series: Marion +0.88, Moultrie +0.99, Murray +1.31, Greenwood +0.57, Monticello +0.165, Deep Creek +1.82 (constant), Bear Lake +6.885 ft, so none of these scales is NAVD88; the pool for each is still a document with no datum. Hartwell-style pairing worked only where a CWMS pool exists (Thurmond, W.F. George). Kerr (62614) has an NGVD29-stamped CWMS series with vdi offset to NAVD88 -1.018 ft and equals the USGS gauge, but CWMS has no Kerr pool level.

## 5. What remains and the resolver each needs

| Count | Lakes | Resolver |
|---|---|---|
| ~27 | USACE lakes whose pool figure matches no CWMS level (APCO Jordan/Lay, SFWMD Tohopekaliga/Kissimmee/Istokpoga/Okeechobee, Seminole, Anderson Ranch, Palisades, Jackson, Coeur d'Alene, Pend Oreille, Chelan, Cross, Bistineau, Eagle Lake, Ross Barnett, Catahoula, Kerr, Jordan Lake NC, Claytor, Tahoe, Lake Washington, Moses, Percy Priest, Pepin, Red Lake) | operator document stating the datum of the pool figure, or an operator-approved decision to re-bind to the CWMS level listed in `alternativeReference` |
| 2 | Rend Lake, Mark Twain Lake | MVS confirmation of the datum of the project-level CWMS location (null) versus the NAVD88 series location |
| 69 | USGS-served lakes | document naming the datum of the pool figure: USGS Water Data Report gage-datum line, state/FERC exhibit, Santee Cooper/Dominion for 00062 sites; 00065+alt_va lakes also need the gauge-datum record |

## 6. Recommendation to the lead (not applied)

1. Replace the token-equality `same_source` test in `candidates.py` with the location-level lookup above (read the CWMS location of the series and of the pool level; same location = SAME_SOURCE, equal NGVD29/NAVD88 stamps = SAME_DATUM). That alone moves ~78 lakes (groups 1-3). It needs `poolLevelId` stored per lake (present in the proposals).
2. Keep LOCAL levels labelled LOCAL; the shift is valid only against the same-location pool level.
3. Treat circular feeds as datum-fixing, never as independent confirmation.
