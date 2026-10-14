# Depth Brain: TVA datum confirmation

> **UPDATE 2026-10-14 (long-run campaign): one more public route tried, nothing found.** `research/depth/tva_link_test.py` looked for an independent USGS lake-elevation series (62614 NGVD29 / 62615 NAVD88 / 72020 NGVD29) within 12 km of each of the 16 TVA dams in the USGS series catalog and found **none** (`data/tva_link_test.json`), so the Hartwell-style pairing that settled Kentucky-line datums elsewhere cannot be run for TVA. TVA publishes no storage series, so the storage-consistency check used for Reclamation does not apply either. The datum NAME stays `inferred`; the shift (one TVA system) is unaffected. The TVA request stays the only route.

Date 2026-10-14. Research only; nothing sent to TVA. Raw data: `~/Desktop/Development/Sector_Research_Data/depth-brain/datum3/tva/`. Extends section 3.1 of `DEPTH_DATUM_AUDIT.md`. Machine twin: `proposals/provider_rules.json`.

Two different questions, kept apart:

* **(a) Are the TVA reading and the TVA pool one system?** (what the shift needs)
* **(b) What is the absolute datum name?** (what an absolute elevation, a conversion or a cross-source comparison needs)

## 1. Bottom line

* **(a) is now evidenced from TVA's own API structure, not only inferred.** For all 17 TVA candidate rows (16 lakes; Kentucky Lake is bound twice) the directory pool figure equals a number in the TVA `operating-guide` payload, and that payload's `MidNightElevation` equals the TVA `observed-data-48-hours` reservoir reading to within 0.05 ft (identical for 7 of the 16 lakes). The guide response carries zone bounds and the current-year elevation on one row for charting, so TVA publishes level and guide on one elevation axis. Decision unchanged: `SAME_OPERATOR_SYSTEM`, sigma 0.1 ft.
* **(b) is still not stated by TVA in anything retrievable.** Nothing here raises the confidence of "NGVD29" above *inferred*. The supporting records are indirect (NWS tailwater gauge, a Kentucky transportation record, a secondary-search hit on a TVA EIS appendix); none is a TVA statement about reservoir elevations.
* **Do not recommend raising `levelDatumBasis` above `inferred`** until TVA answers the request in section 6.

## 2. What TVA's own channels expose [fetched 2026-10-14]

| Channel | Result |
|---|---|
| `https://www.tva.com/RestApi/observed-data-48-hours/<loc>` (the Lake Brain feed, `LakeLevelFeeds.swift`) | JSON array, fields `Day`, `Time` ("4 PM CDT"), `ReservoirElevation`, `TailwaterElevation`, `AverageHourlyDischarge`; 48 rows; no datum, unit or metadata field |
| `.../operating-guide/<loc>` | `MidNightElevation[]` and `items[365]` with `Day`, `TopOfGates`, `PrevYrElev`, `CurYrElev`, `BtmOpZone`, `TopOpZone`, `GuideCurve` (Wilson has no `GuideCurve`); no datum field |
| `.../locations` | 43 locations with `LocationID`, `Name`, `Lat`, `Long`, `River`, `Ownership`, `DamType`, `AltAbbr1`, `TopOfGatesFt`, `RiverMile`; no datum field |
| `.../lake-info/<loc>`, `.../reservoir-info/<loc>` | HTTP 404 (no such endpoints) |
| `lakeinfo.tva.gov/web/sites/guntersville.htm` | page text gives the typical summer operating range 594 to 595 ft and minimum winter elevation 593 ft; **no datum, no "mean sea level" wording** |
| `tva.com/environment/lake-levels/...` | HTTP 403 to the fetcher |

## 3. (a) One system: API structure check

Directory pool vs TVA guide payload, and the guide's `MidNightElevation` vs the observed series' last "Midnight" reading (computed from live fetches):

| Lake | Loc | Directory pool | Where the pool sits in the TVA guide | TVA TopOfGates | Guide midnight | Observed midnight |
|---|---|---|---|---|---|---|
| Guntersville (pilot) | GVDA1 | 595 | max TopOpZone 595 | 595.4 | 593.70 | 593.70 |
| Wheeler (pilot) | WHLA1 | 556 | max TopOpZone 556 | 556.3 | 553.35 | 553.35 |
| Wilson (pilot) | WLSA1 | 507.7 | max TopOpZone 507.7 | 507.9 | 506.98 | 506.98 |
| Pickwick (pilot) | PICT1 | 414 | max TopOpZone 414 | 418 | 411.24 | 411.24 |
| Chickamauga | CKDT1 | 682.5 | max TopOpZone 682.5 | 685.4 | 679.91 | 679.90 |
| Fort Loudoun | FLDT1 | 813 | max TopOpZone 813 | 815 | 812.44 | 812.40 |
| Nickajack | NKJT1 | 634.5 | max TopOpZone 634.5 | 635 | 633.01 | 633.01 |
| Watts Bar | WBOT1 | 740.85 | max TopOpZone 740.85 | 745 | 740.80 | 740.75 |
| Kentucky (KY, TN rows) | KYDK2 | 359 | max GuideCurve 359 (TopOpZone 359.5) | 375 | 354.67 | 354.67 |
| Fontana | FONN7 | 1703 | max GuideCurve 1703 | 1710 | 1676.36 | 1676.35 |
| Hiwassee | HIWN7 | 1520.9 | max GuideCurve 1520.9 | 1526.5 | 1495.36 | 1495.35 |
| Cherokee | CRKT1 | 1070.8 | max GuideCurve 1070.8 | 1075 | 1055.30 | 1055.31 |
| Douglas | DUGT1 | 993.88 | max GuideCurve 993.88 | 1002 | 972.47 | 972.44 |
| Norris | NRST1 | 1020 | max GuideCurve 1020 | 1034 | 1007.68 | 1007.70 |
| Tims Ford | TMFT1 | 888 | max GuideCurve 888 | 895 | 887.16 | 887.16 |
| South Holston | SHDT1 | 1729 | max GuideCurve 1729 | 1742 | 1716.87 | 1716.88 |

So level and pool come from one TVA JSON service and one set of elevation numbers. Small midnight differences are rounding or the hour of the read. This supports (a); it is not a TVA statement that the numbers share a *named* datum.

## 4. (b) Absolute datum: what exists

| Evidence | Says | Strength / status |
|---|---|---|
| NWS NWPS `GVDA1` (Tennessee River below Guntersville Dam, PEDTS HTIRZ, product "Tailwater") | datum table NGVD29 = 538.2. [computed] On 2026-10-13 20:00 UTC the NWS stage 17.31 + 538.2 = 555.51 ft, identical to TVA's `TailwaterElevation` for 3 PM CDT (555.51) | TVA **tailwater** is consistent with NGVD29 at Guntersville. Tailwater, not the reservoir; NWS metadata, not a TVA statement |
| KYTC "KY Lake Historic Water Surface Elevations" (earlier thread, fetched; shown again in a search snippet): record for the TVA-maintained Kentucky Dam upstream gauge | datum NGVD29; NAVD88 = NGVD29 - 0.2 ft; "site is maintained by the TVA" | historical, one lake, a third party's record |
| TVA draft EIS appendix on Hiwassee/Apalachia flood profiles (found by search; document host unreachable from this environment, **not fetched**) | footnote "All Elevations are NGVD 1929" | TVA-authored, but flood profiles for a different object; unverified here |
| NWS NWPS gauges for the TVA lakes: 13 of the 16 ids exist (Wheeler WHLA1, Wilson WLSA1 and Tims Ford TMFT1 return 404) | 12 have **empty** datum tables; only the Guntersville tailwater (GVDA1) lists NGVD29 | no information on the reservoirs |
| USACE CWMS `BARKLEY` project location (Lake Barkley shares Kentucky Lake's 359 ft summer pool) | `vertical-datum` NGVD29 (API) | partial corroboration for the Kentucky/Barkley pair only; the Barkley level `Top of Conservation` was not found in the API under the tested mask |
| TVA Reservoir Operations Study programmatic EIS (2004) | not retrieved; searches found no text naming the datum | gap |
| `lakeinfo.tva.gov` / TVA REST | no datum text or field | gap |

Per-reservoir differences (Fontana, Norris, Watts Bar, South Holston, where mountain-reservoir surveys may differ) remain unchecked. **Result: (b) is inferred NGVD29 for the Tennessee mainstem near Guntersville and Kentucky Dam, unknown elsewhere.**

## 5. Rows for the four pilots and the other TVA lakes

| Lake | (a) same system | (b) datum | Rollout implication |
|---|---|---|---|
| Guntersville, Wheeler, Wilson, Pickwick | evidenced (API structure) | inferred NGVD29, tailwater-consistent at Guntersville only | unchanged: shift allowed, absolute datum not asserted |
| The other 12 lakes (16 total less 4) | evidenced (API structure) | inferred, unverified | unchanged |

## 6. Confirmation request to TVA (unsent text)

> To: TVA River Management / Reservoir Operations. Subject: Vertical datum of reservoir elevations in the TVA lake-levels REST data.
>
> We use the public TVA lake-level data (`https://www.tva.com/RestApi/observed-data-48-hours/<location>` and `/operating-guide/<location>`) and need to state a precise vertical datum. For the following reservoirs: Guntersville, Wheeler, Wilson, Pickwick, Chickamauga, Fort Loudoun, Nickajack, Watts Bar, Kentucky, Fontana, Hiwassee, Cherokee, Douglas, Norris, Tims Ford, South Holston.
>
> 1. What vertical datum are `ReservoirElevation` and `TailwaterElevation` referenced to (NGVD 1929, NAVD 1988, or a TVA datum)? Is it the same for all of the reservoirs listed?
> 2. Are the operating-guide fields (`TopOfGates`, `TopOpZone`, `BtmOpZone`, `GuideCurve`, `PrevYrElev`, `CurYrElev`) in the same datum as `ReservoirElevation`?
> 3. Has the datum of any of these series been changed or re-adjusted since 2000 (date and offset)?
> 4. Is `ReservoirElevation` the forebay elevation at the dam, and what is its measurement precision?
> 5. Is there a public document (operations policy, reservoir operations study, lake-info page) that states the datum so that we can cite it?

## 7. What changes if confirmed

* If TVA states NGVD29 (or any single datum) for the elevation and guide fields: `datum_providers.json` `tva` moves from `levelDatumBasis: inferred` to `verified_doc`; `datumStatus` stays `SAME_OPERATOR_SYSTEM` or upgrades to `SAME_SOURCE`; sigma may drop from 0.1 ft to the instrument figure.
* An absolute elevation, a cross-source comparison with 3DEP/USGS/CWMS, or a conversion to NAVD88 becomes allowed with the NCAT offset (fleet TVA NCAT range -0.56 to +0.54 ft, per the audit). Without confirmation none of these is allowed; only the TVA-internal shift is.
* If TVA states the datum differs by reservoir, split the rule per reservoir (the audit already flags Fontana, Norris, Watts Bar as unchecked).
* If TVA states NAVD88 for any reservoir, the "inferred NGVD29" notes for that lake must be removed.
