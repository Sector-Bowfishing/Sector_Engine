# Depth Brain: Duke Energy lake-level scale evidence

Date 2026-10-14. Research only; nothing sent to Duke. Raw data: `~/Desktop/Development/Sector_Research_Data/depth-brain/datum3/duke/`. Extends section 3.3 of `DEPTH_DATUM_AUDIT.md`. Machine twin: `proposals/provider_rules.json`.

Question: is `shift = scale - 100` for Duke's "100 = full pond" lake-level scale documented, and for which lakes?

## 1. Bottom line

* **The scale definition is documented for 7 of 8 Duke lakes, by Duke/regulatory documents**, not only inferred from NWS metadata: Catawba-Wateree (Hickory, James, Norman, Wylie, Wateree) by the 2006 Agreement-in-Principle Low Inflow Protocol (LIP), and Keowee-Toxaway (Jocassee, Keowee) by a Duke slide deck of 2023-12-13. In these documents "full pond = 100.0 ft relative" and the absolute full-pond elevation in feet above mean sea level is tabulated, so a level `L` on the relative scale is `L - 100` ft from full pond. That is what the Depth Brain shift is for these lakes, by definition.
* **Not documented, only consistent:** that the *specific live series Lake Brain reads* (Duke API `lake-level-Actual`) is on that relative scale. The Duke API now returns HTTP 403 and Duke's lake-levels web page returns 403 to automated fetches, so this could not be re-verified. It is *consistent with* seven NWS gauges fed from Duke, which publish "Pool" values of 84 to 100 against action stages of 100 (section 3).
* **Lake Robinson (Duke Energy Progress): UNKNOWN.** No public document found; the "real feet" note is a project note only.
* **The datum name is still not stated** by any Duke document: all say "feet above Mean Sea Level". NGVD29 rests on the NWS table (four lakes, section 3). A shift does not need the name, because pool and level are both defined relative to the same full-pond contour. An absolute elevation must not be published as NGVD29 as a Duke fact.
* **Never** compute `level - fullPoolFt` (about -660 ft for Norman).

## 2. What public documentation says

| # | Document [fetched] | Says | Lakes |
|---|---|---|---|
| 1 | Catawba-Wateree Agreement-in-Principle, LIP "Attachment G", dated 2006-01-24, hosted by NC DEQ as FEIS Appendix D (`files.nc.gov/ncdeq/Water Resources/files/ibt/Concord/09Final_Environmental_Impact_Statement_May_2006/FEIS_Appendices/Appendix-D_ Low_Inflow_Protocol_Catawba.pdf`, 18 pages) | Defines Full Pond Elevation as the level at which water would first spill. States the Licensee "has adopted the practice of referring to the Full Pond Elevation for all of its reservoirs as equal to 100.0-feet (ft.) relative", and tabulates full pond in ft above Mean Sea Level: James 1200.0, Rhodhiss 995.1, Hickory 935.0, Lookout Shoals 838.1, Norman 760.0, Mountain Island 647.5, Wylie 569.4, Fishing Creek 417.2, Great Falls-Dearborn 355.8, Cedar Creek 284.4, Wateree 225.5. Normal minimum elevation is "measured in feet above MSL or feet relative to the full pond contour with 100.0 ft corresponding to full pond" | Hickory, James, Norman, Wylie, Wateree |
| 2 | Duke Energy slides to the Upper Savannah River Basin Council, 2023-12-13 (`des.sc.gov/.../USRBC5 - Item 5 (Duke Energy Operations).pdf`, 17 pages) | LIP operations: "Jocassee: 100.0 - 70.0 ft (1110 - 1080 ft AMSL); Keowee: 100.0 - 90.0 ft (800 - 790 ft AMSL)"; stay above "91.5 ft / 791.5 ft AMSL". The Low Inflow Protocol is Appendix D of the Keowee-Toxaway Relicensing Agreement and is part of the FERC licence | Jocassee, Keowee |
| 3 | NWS NWPS gauges (`api.water.noaa.gov/nwps/v1/gauges/<id>`) | see section 3 | 7 gauges |
| 4 | Duke API `api.hydro-derived.duke-energy.app/lakes/current-levels` | HTTP 403 "Missing Authentication Token" (re-tested 2026-10-14) | not verifiable |
| 5 | `duke-energy.com/community/lakes/lake-levels` | the page is a JavaScript app; the served HTML (910 KB, fetched 2026-10-14 with a browser user agent) holds no text about full pond, relative scale, datum or mean sea level, and the values load through the API in row 4 (WebFetch gets HTTP 403) | not verifiable |
| 6 | USGS | no elevation series on any of the lakes found (`LAKE KEOWEE NEAR SIX MILE` 02185145 returns no current parameters; the Catawba gages found are tailraces) | none |
| 7 | FERC licence articles (Catawba-Wateree P-2232, Keowee-Toxaway P-2503) | the licence article text was **not** retrieved; a secondary page and news items restate Keowee's 800 ft full pond; Jocassee's 1110 ft appears only in document 2 | not fetched |

## 3. NWS NWPS gauges on Duke lakes [fetched 2026-10-14]

| Lake | NWS id | Product | Datum table (value) | Observed | Action / flood stages | Reading |
|---|---|---|---|---|---|---|
| Norman | CWAN7 | HP "Pool" | NGVD29 = 660 | 99.43 | action 100, minor 102 | 660 + 100 = 760.0 = LIP full pond |
| Hickory | OXFN7 | HP | NGVD29 = 835 | 98.39 | action 100.5 | 835 + 100 = 935.0 = LIP full pond |
| James | BRWN7 | HP | NGVD29 = 1100 | 100.24 | action 101 | 1100 + 100 = 1200.0 = LIP full pond |
| Wylie | FOMS1 | HP | NGVD29 = 469.4 | 97.63 | action 100 | 469.4 + 100 = 569.4 = LIP full pond |
| Wateree | WATS1 | HP | empty | 98.52 | minor 100, action 99 | scale consistent |
| Jocassee | JCSS1 | HP | empty | 83.98 | action 100 | scale consistent; 100 = 1110 per Duke slides |
| Keowee | KEOS1 | HP | empty | 96.68 | action 100 | scale consistent; 100 = 800 per Duke slides |

Four independent agreements (NWS gage-zero + 100 equals the LIP full pond to the 0.1 ft) show the NWS values are the Duke relative scale and that its zero is an NGVD29 elevation. This is metadata from the NWS, not a Duke statement of the datum.

Caution on the research binding: `lake_brain/binding2` stores Duke medians as absolute feet (Norman 757.47, Wateree 222.3) flagged `S-derived`, i.e. derived from the scale by `fullPond + (scale - 100)`. These are not independent elevation measurements; using them against the pool would be circular. Use the scale value and `shift = scale - 100`.

## 4. Decision per lake

| Lake | Scale definition documented | Series evidence | Decision |
|---|---|---|---|
| Hickory, James, Norman, Wylie, Wateree | Yes, document 1 (2006) | NWS gauges, plausibility 97 to 100 | SAME_SOURCE: shift = scale - 100 (provisional on the series confirmation below) |
| Jocassee, Keowee | Yes, document 2 (2023) | NWS gauges; Jocassee at 83.98 is 16 ft low, in line with the 2026 drought news | SAME_SOURCE: shift = scale - 100 (provisional) |
| Robinson | No | none | UNKNOWN |

Effects: Duke becomes 7 shift-possible lakes if accepted (the audit's 8 minus Robinson). Normal operating targets sit below 100 (Norman 98.5 summer, 96 winter, from the audit), so the shift is negative by design for most of the year; surface that with the operating target, as for Hartwell.

## 5. Residual uncertainty and what is needed from Duke

Needed from Duke (not sent):

1. *Confirm that the lake-level value returned by the public Duke lake-levels page and API for Hickory, James, Norman, Jocassee, Keowee, Wylie and Wateree is expressed in feet relative to full pond with 100.0 = full pond (the LIP convention), and not in feet above mean sea level.*
2. *Confirm Lake Robinson (Duke Energy Progress): the scale and full-pond elevation that the public value uses, and whether it is feet above mean sea level.*
3. *State the vertical datum of the full-pond elevations (NGVD29 or NAVD88) in the Catawba-Wateree and Keowee-Toxaway licences, and whether any of the licensed elevations were re-referenced.*
4. *Confirm the value is the instantaneous lake level at the dam forebay, and whether the Wylie and Wateree full-pond points (569.4, 225.5) are the lowest point of the spillway/gates as defined in the LIP.*
5. *Provide a service-account or documented public access path for the API (the current endpoint returns HTTP 403 without a token), and its licence for a derived depth product.*

If 1 is confirmed in writing, upgrade the seven lakes to `verified_doc`. 3 only matters for publishing an absolute elevation or for comparing with a non-Duke source.
