> **2026-10-14 decision (Michael): do NOT apply the proposed MN DNR reclassification automatically.** It stays PROPOSED (`proposals/licence_changes.csv`) until a dedicated licensing decision reviews the exact basis. No licensing assumption may leak into customer eligibility; `source_licences.csv` and the manifest gate are unchanged (MN = UNCLEAR, derived numbers not allowed).

# Depth Brain: Licensing Unlock Queue

Prepared 2026-10-13. **Research and documentation only. Nothing here was sent to anyone, no production code or the matrix/CSV was edited.** This is licence triage by an engineering assistant, **not legal advice**. Anything unclear stays NOT permitted. Placeholders in the draft texts: `[YOUR NAME]`, `[CONTACT]`, `[COMPANY/PROJECT NAME]`.

Inputs: `DEPTH_LICENSING_MATRIX.md`, `data/source_licences.csv`, `DEPTH_SOURCE_REQUEST_PACKAGE.md`, `data/candidates.json` (manifest 2026-10-13.1), `DEPTH_CANDIDATE_FLEET.md`. Every terms page below was re-fetched on 2026-10-13 (URLs in section 5). "Quote" means a short verbatim quote; everything else is a paraphrase.

## 1. Headline

1. **Minnesota is probably already permitted for derived numbers.** The dataset's own metadata (found today, not available to the earlier pass) says Access Constraints "None" and Use Constraints "None" and points to the DNR *General Data & Software License Agreement*, whose term 1 allows derivative works and only bars reselling/distributing/displaying the data **"in its entirety"**. A shallow-share number is a derivative, not the data. Proposed CSV change in `proposals/licence_changes.csv` (MN: UNCLEAR to ATTRIBUTION_REQUIRED, derived-only, raw geometry and map layer stay NOT permitted). This is the single permission that touches the most bowfishing-relevant lakes (Mille Lacs, Leech, Winnibigoshish, Vermilion, plus Pepin, Otter Tail, Gull, Minnetonka, Bemidji, White Bear). A one-paragraph confirmation to MN DNR Fisheries is cheap insurance but is not required to start; Michael decides.
2. **44 of 103 tier A/B lakes are blocked** (confirmed from `candidates.json`: `evidence.tier` in A/B and `licence.customerDerivedMetricsAllowed == "false"`). Only 8 of the 44 are `shiftPossible` (5 HIGH_CONFIDENCE, 3 MEDIUM_CONFIDENCE) and none is a pilot; for most of them the unlock gives a **static shallow-share number**, not a live shift, until datum/binding work lands.
3. The one other cross-cutting permission is **USACE CWMS** (28 tier C lakes whose hypsometry comes from CWMS, including Hartwell). Terms are still unstated; no new evidence changes UNCLEAR.
4. **IENC "non-public" flag resolved**: a catalogue artefact. The USACE IENC metadata states legal and security constraints "None (Public Domain Information)". Keep PUBLIC_REUSABLE; no CSV change.
5. **TWDB "not fishing maps" resolved**: it is a liability disclaimer, not a use restriction (section 4).
6. No source flips from blocked to fully permitted except MN (and that one carries a recommendation, not a certainty).

## 2. Fleet impact of the 44 blocked tier A/B lakes

Computed from `candidates.json`. "Shift" = `shiftPossible`; "HC" = rollout HIGH_CONFIDENCE or PILOT_VERIFIED (none of the blocked lakes is a pilot). The licence source is the most restrictive contour source per lake (`licence.sources`).

| Source key | Blocked A/B lakes | A | B | Shift possible | HC | Also blocks (tier C, B-partial) | Bowfishing-relevant lakes |
|---|---:|---:|---:|---:|---:|---|---|
| MN | 10 | 7 | 3 | 2 (Gull, Winnibigoshish) | 2 | Rainy, Big Stone (SD) | Mille Lacs, Leech, Winnibigoshish, Vermilion, Pepin, Otter Tail, Gull |
| OH | 10 (incl. Pymatuning|PA via OH source) | 7 | 3 | 3 (Alum Creek, Caesar Creek, Mosquito Creek) | 2 | Berlin, Indian | Grand Lake St. Marys, Salt Fork, Mosquito Creek, Alum Creek, Pymatuning |
| FL | 8 | 8 | 0 | 1 (Toho) | 0 | | Kissimmee, Toho, East Toho, Istokpoga, Harris, Griffin, Lochloosa, Orange |
| MT | 5 | 3 | 2 | 0 | 0 | Whitefish, Bighorn (WY) | Flathead, Canyon Ferry, Hebgen, Georgetown, Tiber |
| OK | 4 | 1 | 3 | 2 (Fort Gibson, Sardis) | 1 | Lake Hudson | Grand Lake o' the Cherokees, Fort Gibson, Sardis, Lake Murray (OK) |
| ND | 3 | 3 | 0 | 0 | 0 | | Bowman-Haley, Nelson, Patterson |
| WA | 1 | 1 | 0 | 0 | 0 | Chelan, Crescent, Moses | Lake Sammamish |
| IL | 1 | 1 | 0 | 0 | 0 | | Lake Springfield |
| NJ | 1 | 1 | 0 | 0 | 0 | Absegami | Spruce Run |
| PA (Harveys) | 1 | 0 | 1 | 0 | 0 | | Harveys Lake |
| **Total** | **44** | 32 | 12 | **8** | **5** | 13 | |

Shift-possible blocked lakes: MN 2 (Gull, Winnibigoshish), OH 3 (Alum Creek, Caesar Creek, Mosquito Creek), FL 1 (Toho), OK 2 (Fort Gibson, Sardis) = 8. HIGH_CONFIDENCE among them: Gull, Winnibigoshish, Caesar Creek, Mosquito Creek, Sardis = 5; MEDIUM_CONFIDENCE: Alum Creek, Toho, Fort Gibson = 3. The other 36 blocked lakes are BLOCKED for rollout (datum unknown or no verified binding), so an unlock gives them a static shallow-share number, not a shift.

Sources with no tier A/B lake blocked (no fleet leverage on A/B): TN (0 fleet lakes), WI (Chippewa Flowage, 1 B-partial), UT (Utah Lake, 1 B-partial), MD (contours for Jennings Randolph come from WV, which is permitted), NID (no contour use).

## 3. Prioritised unlock queue

Ranking = (A/B lakes unlocked, with weight for bowfishing relevance and shift-possible lakes) x (chance of a yes) / (effort). "Derived numbers allowed today?" is the CSV/gate value; "needs" says which of the three tiers of permission the source must give: **D** = derived scalar numbers (shallow share, mean depth), **G** = raw geometry/raster redistribution, **L** = customer map layer. Sector's current plan needs **D only**.

| Rank | Source | A/B lakes (shift / HC) | Derived allowed today? | Needs | Effort | Risk | Unlock value |
|---:|---|---|---|---|---|---|---|
| 1 | **MN DNR Fisheries** (MN Geospatial Commons) | 10 (2 / 2) | No in CSV (UNCLEAR); **terms support yes (derived only)** | D (G and L not needed, and the licence does not give them) | Low: Michael sign-off on a CSV change, optionally one confirming email | Low-medium: licence says "restricted, individual" permission and term 1 wording on "displayed" could be read broadly | 4 named flagship bowfishing lakes + 6 more |
| 2 | **USACE CWMS Data API** (HEC / district water management) | 0 A/B; **28 tier C** (includes the Hartwell pilot) | No (UNCLEAR) | D (hypsometry values) | Medium: no stated contact; GitHub Discussions or HEC webmaster | Low (federal work, likely open) but no document says so | 28 lakes' measured hypsometry, many Corps bowfishing reservoirs |
| 3 | **ODNR Division of Wildlife** (Ohio) | 10 (3 / 2) + 2 tier C | No (UNCLEAR, metadata blank) | D | Medium: no GIS terms page found; ODNR pages restructured and return 404 | Medium (silence is not permission; ODNR marks some of its other services internal-only) | Grand Lake St. Marys, Salt Fork, Mosquito, Alum Creek, Pymatuning |
| 4 | **Montana FWP** | 5 (0 / 0) + 2 tier C | No (UNCLEAR) | D | Low: named office and phone printed on the dataset metadata | Low (Access constraints "None") but still no grant | Flathead, Canyon Ferry, Hebgen, Georgetown, Tiber |
| 5 | **Oklahoma Water Resources Board** | 4 (2 / 1) + 1 tier C | No (INTERNAL_ONLY, item says "Internal Use") | D | Medium: online contact form + phone; hosted on an Open Data hub whose bathymetry item licence could not be read | Medium-high (explicit "Internal Use") | Grand Lake o' the Cherokees (see USGS alternate), Fort Gibson, Sardis |
| 6 | **Florida FWC-FWRI** | 8 (1 / 0) | No (INTERNAL_ONLY) | D (and an exception to an "any other use is prohibited" clause) | High | High (explicit purpose limitation; reasonable chance of "no") | Kissimmee, Toho and 6 more Florida bass/bowfishing lakes |
| 7 | **North Dakota Game and Fish / ND GIS Hub** | 3 (0 / 0) | No (UNCLEAR) | D | Medium: no data contact printed; fisheries section via gf.nd.gov | Low-medium | 3 small western ND reservoirs, low bowfishing relevance |
| 8 | **WA Ecology** | 1 (0 / 0) + 3 tier C | No (UNCLEAR, contradictory) | D | High: written authorization, third-party content (USGS, WDFW, King County) | Medium-high | Lake Sammamish (+ Chelan, Crescent, Moses) |
| 9 | **Illinois DNR OWR** | 1 (0 / 0) | No (UNCLEAR, licence "None") | D | Low-medium | Low | Lake Springfield |
| 10 | **NJDEP BFBM** | 1 (0 / 0) + 1 tier C | No (RESTRICTED, "NOT FOR COMMERCIAL USE") | D, and an exception to an explicit prohibition | High | High (probable "no") | Spruce Run (Absegami) |

Not blocking any tier A/B lake, so no unlock leverage: TN TWRA (small-lake layer), WI Chippewa Flowage association layer, UT Utah Lake (B-partial), MD MGS soundings, NID. The PA local layer (Harveys Lake, 1 tier B lake) has no fetched terms page and no known contact; it is not queued until its service URL is identified.

Confirmations that are not unlocks (already allowed, optional courtesy): IENC (28 tier C B-binary lakes; PUBLIC_REUSABLE), TWDB (6 lakes, all HIGH_CONFIDENCE and shift-possible).

## 4. Per-source detail

Each block gives: terms re-checked today, change since the matrix, contact route actually found, what permission is needed, and the unsent draft.

### 4.1 Minnesota DNR (rank 1)

* **Terms re-checked.** The old dataset URL `gisdata.mn.gov/dataset/water-lake-bathymetry` still 301-redirects to `gis.data.mn.gov`, which is now an ArcGIS Hub single-page app, so the earlier pass saw no terms. The Hub search API lists the item (id `c4bbf4b8e45a48afba2d73f24089c187`, "Lake Bathymetric Outlines, Contours, and DEM", originator "DNR Division of Fish and Wildlife - Section of Fisheries", licenseInfo "None"). Its published **metadata PDF** (`operations.gis.data.mn.gov/api/publicdownload/download/901/metadata.pdf`, last updated 05-28-2024) says **Access Constraints: None; Use Constraints: None;** and under Distribution Liability: "The Minnesota Department of Natural Resources General Geographic Data License Agreement is online" at `dnr.state.mn.us/sitetools/data_software_license.html`. The sibling item "Lake Bathymetric DEM Shaded Relief Image" carries the explicit text "Internal DNR use is unrestricted. External use is constrained by the standard, general DNR GIS Data License Agreement."
* **The licence** (`https://www.dnr.state.mn.us/sitetools/data_software_license_plain.html`, fetched; no version or date shown). Grant: "restricted, individual, non-exclusive permission to extract information from, use, copy, share, and alter" the data. Clauses that matter:
  * Term 1: data "may be used for the creation of derivative works"; "however data and/or software in its entirety may not be resold, distributed or displayed for commercial purposes or otherwise" (quotes). So: derived scalar numbers are allowed; shipping or showing the contours/DEM themselves is not.
  * Term 2: a more specific licence tied to the dataset prevails. None found for this dataset (Use Constraints "None").
  * Term 3: MNDNR owns the data; include an MNDNR copyright notice "as appropriate" or acknowledge MNDNR as having contributed to any derivative work.
  * Term 6: map data is reference only, "should not be used for navigational purposes", not legal boundaries.
  * Term 7: no right to use MNDNR's name, marks or logos; not an endorsement.
* **Change since the matrix.** The matrix could not find any terms (UNCLEAR). It now can: the dataset-level constraints are "None" and the governing licence is the DNR general licence above. A second variant of the DNR agreement ("General Geographic Data License Agreement", seen on `dnr.state.mn.us/wmas/kml/license.html`, item 6) says use "is not restricted" but data "may not be sold commercially or privately, without the written permission of MNDNR". Under either variant a derived metric is not a sale of the data.
* **Recommendation.** Reclassify MN to ATTRIBUTION_REQUIRED with `customerDerivedMetricsAllowed=true` and `rawRedistributionAllowed=false`, attribution "Minnesota DNR Division of Fish and Wildlife, Section of Fisheries" with a note that figures are derived and not endorsed. Keep contours, DEM and any map layer NOT permitted. Because the licence grant is described as "restricted" and the "displayed ... or otherwise" wording is broad, a short confirming note to MN DNR is sensible before the first public number, but the engine gate need not wait if Michael accepts the reading. Not legal advice.
* **Contact route actually found.** The dataset metadata PDF prints two contact roles: "GIS Data Contact" (DNR Fisheries, Rochester) and "Publisher Contact" (DNR Division of Fish and Wildlife, Section of Fisheries, 500 Lafayette Rd, Saint Paul MN 55155; phone 651-259-5637 as printed). Individual names and emails are printed there; they are deliberately not reproduced here, so open the PDF. The DNR license page lists no permissions contact. The DNR general data-request route is the Data Practices request (page `dnr.state.mn.us/aboutdnr/dataaccess/index.html`, mail to the Data Practices Compliance Official, 500 Lafayette Road, St. Paul 55155-4075), which is for access to public data, not a licence.
* **Permission needed.** D only. Raw redistribution and map layer: not needed and not granted.
* **Draft (UNSENT).**

> Subject: Question about using derived metrics from the DNR Lake Bathymetric Outlines, Contours, and DEM dataset
>
> Hello,
>
> [COMPANY/PROJECT NAME] is building a bowfishing conditions application. We would like to compute summary metrics (for example the share of a lake's surface area shallower than 6 ft, and mean depth) from the Minnesota Geospatial Commons dataset "Lake Bathymetric Outlines, Contours, and DEM" and show only those numbers, labelled as planning estimates and not for navigation, with credit to MN DNR Division of Fish and Wildlife. We would not redistribute or display the contours, DEM or any map layer. The dataset metadata lists Access and Use Constraints as "None" and refers to the DNR General Data & Software License Agreement, which allows derivative works. Could you confirm that publishing derived summary metrics on that basis is acceptable, and tell us the acknowledgement wording you prefer?
>
> Thank you,
> [YOUR NAME], [COMPANY/PROJECT NAME], [CONTACT]

### 4.2 USACE CWMS Data API (rank 2; open item)

* **Terms re-checked.** (a) The API's own docs FAQ (`cwms-data-api.readthedocs.io/prod/faq.html`) states a key is required only for writing, updating, deleting, or endpoints with sensitive data, and its footer reads "Copyright Public Domain" (that is the docs site, not a data licence). (b) The live Swagger document `cwms-data.usace.army.mil/cwms-data/swagger-docs` (version 2026.09.22-a) has an `info` block with only title, description and version: no licence, no terms of service. (c) `hec.usace.army.mil/cwms/` still says CWMS "is currently available only to USACE offices", with the public HEC-RTS alternative, and gives the contact "Webmaster-HEC@usace.army.mil" for the system developer. (d) USACE disclaimer/copyright pages still return HTTP 403 to automated fetch. (e) The GitHub repo `USACE/cwms-data-api` is MIT (software licence, not data). **No statement of data terms was found.**
* **Change since the matrix.** None. Still UNCLEAR, still not permitted.
* **Contact route actually found.** The repository README's "Getting In Touch" link is the public GitHub Discussions board, `https://github.com/usace/cwms-data-api/discussions`; and the HEC page prints the Webmaster-HEC address above. Neither is a records or licensing office. The district water-management office is a further route (no verified link: USACE district sites return 403).
* **Permission needed.** D (hypsometry-derived numbers and level data). A statement that the public CWMS Data API output is a US-government work in the public domain, or a data-use notice, would suffice. Federal-government works are generally not copyrighted (17 U.S.C. 105), which makes "yes" the likely answer, but no USACE page says so for this API.
* **Draft (UNSENT).**

> Subject: Data-use terms for the public CWMS Data API (cwms-data.usace.army.mil)
>
> Hello,
>
> [COMPANY/PROJECT NAME] is developing a bowfishing conditions application and uses the public CWMS Data API to read reservoir pool elevation and storage/area time series. We could not find a statement of the terms under which this public data may be used. Could you confirm (1) that data returned by the public CWMS Data API may be used in a commercial application, including publishing derived values such as stage-area-based estimates and pool levels, (2) any attribution wording USACE prefers, and (3) any rate or volume limits we should respect? We will credit "U.S. Army Corps of Engineers CWMS" and describe our products as planning estimates.
>
> Thank you,
> [YOUR NAME], [COMPANY/PROJECT NAME], [CONTACT]

### 4.3 Ohio DNR Division of Wildlife (rank 3)

* **Terms re-checked.** ArcGIS item info for `DOW_Lakes_Bathymetry` (`gis.ohiodnr.gov/arcgis/rest/services/DOW_Services/DOW_Lakes_Bathymetry/MapServer/info/iteminfo?f=pjson`): `licenseInfo` and `accessInformation` empty, description empty. Service copyright empty. The ODNR pages I tried for GIS terms, public records and data records returned HTTP 404 today (the ODNR site was reorganised), so no ODNR-wide GIS terms page was readable. A web-search summary says ODNR's GIS terms live in each service's metadata and vary (some ODNR services are marked internal-only; this one is blank).
* **Change since the matrix.** None on the terms (still blank). Previously the matrix's guessed disclaimer URL 404'd; the whole ODNR site layout has since moved.
* **Contact route (partly found).** Search results (not fetched pages) describe the ODNR "Public Records Access" page with an email-request button, mail to ODNR, 2045 Morse Road, Columbus OH 43229 (attention Public Records Officer), and the Division of Wildlife general line 1-800-WILDLIFE. **Unverified**: the page itself no longer resolves for me. A public-records request gets existing records but is not a licence; the licence ask below is still needed.
* **Permission needed.** D.
* **Draft (UNSENT).** Use the generic text in section 6 with `[ORG]` = "Ohio Department of Natural Resources, Division of Wildlife", `[DATASET]` = "the Lake Bathymetry map service (DOW_Lakes_Bathymetry)" and `[LAKES]` = "Grand Lake St. Marys, Salt Fork, Mosquito Creek, Alum Creek, Tappan, Hoover, Caesar Creek, Senecaville, Lake Milton".

### 4.4 Montana Fish, Wildlife and Parks (rank 4)

* **Terms re-checked.** `lakesBathymetry.htm` (2022-10-12): Access constraints "None"; Use constraints: user determines usability, "as is", FWP not liable. No redistribution clause either way. The related services `fish/fishDistribution` (licenseInfo "None") and `fish/fishViewer` ("For use in web mapping applications") were fetched; the earlier search-summary claim that a service was "Display Use Only" is **not reproduced**. The FWP open-data hub item page (`mtfwp.maps.arcgis.com/home/item.html?id=50d10b53...`) returns "Item does not exist or is inaccessible", so its licence is unreadable.
* **Reconsideration.** "Access constraints: None" plus a use-constraints paragraph that is only a disclaimer is a statement of no restriction in the same style as Kansas ("No constraints") but it does not say "use" and it is not a grant. I keep **UNCLEAR** (unclear stays not permitted), with a note that MT is the most likely "yes" after MN.
* **Change since the matrix.** None.
* **Contact route actually found.** The metadata page prints a Point of Contact: GIS Analyst/Technician, Montana Fish, Wildlife & Parks, 1420 East 6th Ave, PO Box 200701, Helena MT 59620-0701, phone 406-444-5365 (an individual's name and email are printed there as well; open the page).
* **Permission needed.** D. **Draft (UNSENT):** generic text, `[ORG]` = "Montana Fish, Wildlife & Parks (GIS)", `[DATASET]` = "Montana Lakes Bathymetry (refrnc/lakesBathymetry)", `[LAKES]` = "Flathead Lake, Canyon Ferry, Hebgen, Georgetown, Tiber Reservoir".

### 4.5 Oklahoma Water Resources Board (rank 5)

* **Terms re-checked.** `LOK_Lakes` service item still `licenseInfo: "Internal Use"`, copyright "OWRB" (the `Lakes_and_Streams` service item is also "Internal Use"). The OWRB GIS page (`oklahoma.gov/owrb/data-and-maps/gis-data.html`) says its data is available as shapefiles, geodatabases or KMZ and points to an Open Data hub (`ok-owrb.hub.arcgis.com`, API search returned nothing readable) and the REST directory; it prints no licence text. A search summary quotes dataset notes asking for OWRB acknowledgement; I could not fetch that page, so unverified.
* **Change since the matrix.** None.
* **Contact route actually found.** OWRB, 3800 North Classen Boulevard, Oklahoma City OK 73118; phone 405-530-8800; an online "Questions or comments" form linked from `oklahoma.gov/owrb/data-and-maps/bathymetric-mapping.html` (no email printed).
* **Permission needed.** D.
* **Alternative for Grand Lake (not a licence fix, a different source).** The USGS data release "Data release of capacity and area of Grand Lake O' the Cherokees, northeastern Oklahoma, 2009" (data.gov record, access level "public", published by USGS; built from the 2009 OWRB survey plus USGS bathymetry and lidar) gives a capacity and area table. USGS releases fall under the USGS public-domain policy at the policy level, but whether the third-party OWRB input is cleared for onward use, and whether the release carries a depth surface (not just the table), is **not verified**. Worth one fetch of the release item before asking OWRB for Grand Lake.
* **Draft (UNSENT):** generic text with `[ORG]` = "Oklahoma Water Resources Board", `[DATASET]` = "the Lakes of Oklahoma (LOK_Lakes) contours", `[LAKES]` = "Grand Lake o' the Cherokees, Fort Gibson, Sardis, Lake Murray, Lake Hudson".

### 4.6 Florida FWC-FWRI (rank 6)

* **Terms re-checked.** Item licence text confirmed verbatim in the earlier verified form: "These data are intended for general aquatic environmental management purposes only. Any other use is prohibited." and no portion may be used to plan or perform activities including "recreational activities, or any other activity having a geographic component". Acknowledgement of FWC-FWRI requested; share edited data back to FWC.
* **Change since the matrix.** None. Still INTERNAL_ONLY.
* **Contact route actually found.** The FGDC metadata (fetched; dated 2012) lists the FWRI "GIS Data Librarian" as point of contact: role mailbox `GISLibrarian@MyFWC.com`, Fish and Wildlife Research Institute, 100 Eighth Avenue Southeast, St. Petersburg FL 33701, phone 727-896-8626. This is a data-librarian role in old metadata; confirm it still answers.
* **Permission needed.** D, and a written exception to the purpose clause. A bowfishing app is on its face an "other use". Probability of yes: lowish; ask anyway because eight Tier A lakes (Kissimmee chain) depend on it.
* **Draft (UNSENT):** generic text with `[ORG]` = "Florida FWC Fish and Wildlife Research Institute", `[DATASET]` = "Bathymetry of Select Lakes in Florida", `[LAKES]` = "Kissimmee, Tohopekaliga, East Tohopekaliga, Istokpoga, Harris, Griffin, Lochloosa, Orange Lake", and add one sentence: "We understand the data are limited to general aquatic environmental management; we are asking whether FWC-FWRI would permit this narrower, derived-numbers use."

### 4.7 North Dakota Game and Fish / ND GIS Hub (rank 7)

* **Terms re-checked.** `GNF_LakeContoursCached` licenseInfo is the State disclaimer beginning "Not for navigation." No grant of rights. `nd.gov` disclaimer page contains no reuse terms. The ND GIS Hub front page (`gis.nd.gov`) lists no terms link and prints ND Information Technology, 4201 Normandy Street, Bismarck, phone 701.328.4470 in its footer. A Game and Fish layer on a third-party catalogue was listed as CC BY, but that is a different layer (Fisheries Districts) and not evidence for this one.
* **Change since the matrix.** None.
* **Contact route actually found.** The Hub footer address and phone above; a "Contact Us" page on `gis.nd.gov`; for data ownership, Game and Fish fisheries via `gf.nd.gov` (no GIS contact printed that I could fetch; the `gf.nd.gov/gis` path 404s).
* **Permission needed.** D. **Draft (UNSENT):** generic, `[ORG]` = "North Dakota Game and Fish Department (via the ND GIS Hub)", `[DATASET]` = "GNF_LakeContoursCached", `[LAKES]` = "Bowman-Haley, Nelson Lake, Patterson Lake".

### 4.8 Washington Ecology (rank 8; open item: contradictory terms)

* **Terms re-checked** (`ecology.wa.gov/about-us/accountability-transparency/website-information/copyright-information`; the old URL in the matrix now redirects here). Verbatim fragments: "Commercial and political use of any Ecology Material are specifically prohibited. This restriction includes any commercial publication of material"; then "Specific terms of use: ... Use of data from Ecology's web sites — provided the Washington State Department of Ecology is credited as the data provider and a link is provided to the Ecology data source web page. Use of images, audio and video ... for non-commercial purposes only, provided ..."; "All other uses of Material from Ecology's websites are prohibited without prior express written authorization from Ecology." The layer's own `licenseInfo` just points at this page, and its copyright names USGS, WDFW, Ecology and King County; its description says most contours were digitised from USGS Water-Supply Bulletin 43 maps (with Lake Chelan and others from other sources).
* **Reconsideration.** The "use of data" line is conditioned on credit and a link and, unlike the image/audio/video line, does not say non-commercial. That is an argument that data use is allowed commercially with credit, but the general paragraph says commercial use and "commercial publication" of Material is prohibited, and the layer includes third-party content. It is a real contradiction; **stays UNCLEAR / not permitted**. No matrix change.
* **Contact route actually found.** The page prints the copyright contact: Web Communications Manager, Washington State Department of Ecology, PO Box 47600, Olympia WA 98504, phone 360-918-1483. The site's "Permission form" is for people granting Ecology permission, **not** for requesting it, so it is not the route. Ecology also has a "Public records requests" page (existing records, not a licence).
* **Alternative.** Lake Sammamish is mostly digitised USGS maps; a USGS-sourced route would avoid Ecology but is not verified.
* **Permission needed.** D. **Draft (UNSENT):** generic, `[ORG]` = "Washington State Department of Ecology", `[DATASET]` = "Lake Bathymetry Contour Lines / Elevation Bands (ECY MapServer layer 3)", `[LAKES]` = "Lake Sammamish (and Chelan, Crescent, Moses Lake)"; add: "Your copyright page prohibits commercial use of Ecology material but permits use of data with credit; we would like written authorization for our narrower use."

### 4.9 Illinois DNR Office of Water Resources (rank 9)

* **Terms re-checked.** `LakeDepthAndCapacity` licenseInfo "None"; copyright "IDNR Office of Water Resources"; snippet says lake maps and capacity graphs are downloadable attachments. No terms.
* **Change since the matrix.** None.
* **Contact route (office list from search results, not a data-request page).** IDNR Office of Water Resources, Springfield, One Natural Resources Way, Springfield IL 62702-1271, phone 217/782-3863 (from the IDNR "Division of Resource Management" listing in search results; unverified by fetch). No bathymetry-specific contact found.
* **Permission needed.** D (1 lake). **Draft (UNSENT):** generic, `[ORG]` = "Illinois DNR Office of Water Resources", `[DATASET]` = "Lake Depth and Capacity", `[LAKES]` = "Lake Springfield".

### 4.10 New Jersey DEP (rank 10)

* **Terms re-checked.** Item description ends "NOT FOR COMMERCIAL USE." and licenseInfo is the NJDEP Data Distribution Agreement (as-is; no reproduction/redistribution without the metadata; any product must carry NJDEP's credit/disclaimer; no warranty of freedom from third-party copyright). Unchanged.
* **Change since the matrix.** None. RESTRICTED stays.
* **Contact route.** None verified: the item names the Bureau of Freshwater & Biological Monitoring (BFBM); no data contact page fetched. Low value (1 A lake). **Do not request unless Michael wants Spruce Run.** If requested use the generic text with `[ORG]` = "NJDEP Bureau of Freshwater and Biological Monitoring", and say plainly that the use is a commercial app.

### 4.11 IENC "non-public" flag (open item; resolved)

* **Evidence.** The data.gov record (fetched today) still shows License CC0 1.0 and "Access Level non-public" with `rights: otherRestrictions`. But (a) the Penn State mirror of the USACE IENC ISO 19139 metadata for the IENC layers states legal constraints and security constraints "Limitations of use: None (Public Domain Information)", classification unclassified; (b) the USDOT NTAD description says the vector data can be downloaded as a geodatabase from `ienccloud.us` and web services are at `ienccloud.us/arcgis/rest/services/IENC_Feature_Classes`; (c) `ienccloud.us` is an open USACE Army Geospatial Center site that prints the contact `AGC-IENC@usace.army.mil`. USACE/NTAD also say the chart data must not be used for navigation.
* **Conclusion.** The "non-public" flag is a catalogue metadata artefact contradicted by the primary USACE metadata and by the anonymous public service. Keep PUBLIC_REUSABLE, derived = true, raw redistribution = unknown (public domain suggests yes but the contradiction on the catalogue was never answered by USACE). **No CSV change.** Optional one-line question to the IENC mailbox (draft below, UNSENT) if Michael wants the flag explained in writing.

> Subject: IENC data.gov record shows "non-public"; confirming public-domain status
>
> Hello, the data.gov record for the Inland Electronic Navigational Charts dataset lists license CC0 but access level "non-public", while the IENC metadata states "None (Public Domain Information)" and the data are served openly at ienccloud.us. We use the IENC 9-foot depth contour only to derive a yes/no shallow-water indicator in a bowfishing conditions app (never for navigation). Could you confirm that IENC data are public domain and may be used in a commercial application, and whether we may display derived values? Thank you, [YOUR NAME], [COMPANY/PROJECT NAME], [CONTACT]

### 4.12 NID (open item; unresolved, no fleet leverage)

* **Evidence.** `nid.sec.usace.army.mil` landing page: title only (single-page app, no terms text). Penn State mirror of the NID ISO metadata: "Limitations of use: No special restrictions or limitations on using the item's content have been provided." (third-party copy). The `catalog.data.gov` NID slugs I tried 404. Third-party reports (not fetched) say USACE has at times restricted public access to parts of the database. A search summary points to `NID@usace.army.mil` as a contact; unverified.
* **Conclusion.** No change: UNCLEAR. No tier A/B lake depends on it; leave until needed.

### 4.13 TWDB "not intended as fishing maps" (open item; resolved)

* **Evidence.** Whole page re-read (the complete page text is about 43k characters, not 143k as the matrix assumed; the earlier note that terms might be hidden in a truncated remainder is closed). The page contains exactly one terms paragraph: authorization for "use or reproduction of any original material contained in these publications" "is freely granted"; TWDB "would appreciate acknowledgement"; TWDB "shall not assume any liability regarding the presentation or reproduction of this survey information or for the misuse of this information in a manner not consistent with the survey design; for example, maps produced from this volumetric survey are not intended for use as recreational boating maps, fishing maps, or for reservoir boundary determinations." No other restrictive, commercial or licence language appears on the page. Survey data requests: `hydrosurvey@twdb.texas.gov`, phone (512) 936-0815 (both printed on the page).
* **Reading.** This is a liability disclaimer that gives examples of misuse (making fishing maps). It does not forbid use of the survey data in a fishing product, and the grant is free and unconditional apart from the acknowledgement request. Sector's derived numbers are not maps and not for navigation, so they sit outside the example. A **customer map layer of TWDB contours would be the risky use** (it makes a fishing map), so keep L = NOT permitted; D = permitted (as in the CSV). No CSV change.
* **Optional courtesy draft (UNSENT)** to the hydrosurvey address: "[COMPANY/PROJECT NAME] uses TWDB volumetric survey data to compute summary shallow-water metrics (not maps) for Lake Fork, Conroe, Livingston, Tawakoni, Texoma and Cedar Creek in a bowfishing app, credited to TWDB and labelled as planning estimates and not for navigation. Your page notes surveys are not intended as fishing maps; we understand that as a caution against mapping use and would like to confirm that derived summary numbers are fine. [YOUR NAME] [CONTACT]".

## 5. Pages re-fetched on 2026-10-13

| Source | Page | Result |
|---|---|---|
| MN | `gisdata.mn.gov/dataset/water-lake-bathymetry` | 200 after 301 to `gis.data.mn.gov` (SPA, no terms) |
| MN | Hub API item `c4bbf4b8e45a48afba2d73f24089c187`; metadata PDF (`.../download/901/metadata.pdf`) | 200; terms "None"; refers to DNR licence |
| MN | `dnr.state.mn.us/sitetools/data_software_license_plain.html` | 200; terms read |
| OH | `gis.ohiodnr.gov/.../DOW_Lakes_Bathymetry/MapServer/info/iteminfo?f=pjson` | 200; blank |
| OH | `ohiodnr.gov` public-records/data-records pages | 404 |
| MT | `fwp-gis.mt.gov/.../lakesBathymetry.htm` | 200; unchanged |
| ND | `ndgishub.nd.gov/.../GNF_LakeContoursCached/MapServer/info/iteminfo?f=pjson`; `nd.gov` disclaimer | 200; unchanged |
| WA | `ecology.wa.gov/.../copyright-information` | 200 (moved under `/website-information/`); text unchanged in substance |
| IL | `maps.dnr.illinois.gov/.../LakeDepthAndCapacity/MapServer/info/iteminfo?f=pjson` | 200; "None" |
| OK | `owrb.csa.ou.edu/.../LOK_Lakes/MapServer/info/iteminfo?f=pjson` | 200; "Internal Use" |
| FL | ArcGIS item 68fbc062... and FGDC metadata | 200; purpose clause unchanged |
| NJ | ArcGIS item f42bc7d9... | 200; "NOT FOR COMMERCIAL USE" unchanged |
| IENC | `catalog.data.gov/dataset/inland-electronic-navigational-charts`; NTAD description; PSU ISO metadata; `ienccloud.us` | 200 |
| TWDB | `twdb.texas.gov/surfacewater/surveys/completed/index.asp` | 200; full text read |
| CWMS | docs FAQ, Swagger JSON, `hec.usace.army.mil/cwms/`, GitHub repo | 200; no data terms; USACE disclaimer pages 403 |
| NID | `nid.sec.usace.army.mil`; PSU mirror | 200 (landing, no terms); mirror "no special restrictions" |

## 6. Generic permission request (UNSENT)

Use for any source above that has no source-specific draft. Fill `[ORG]`, `[DATASET]`, `[LAKES]`.

> Subject: Request to confirm permitted use of [DATASET]
>
> Hello,
>
> I'm [YOUR NAME] with [COMPANY/PROJECT NAME], which is developing a bowfishing conditions application. We would like to use [ORG]'s [DATASET] for [LAKES] to compute **summary depth metrics** (for example the share of a lake's area shallower than 3, 6 and 10 ft, and mean depth) and to publish **only those numbers**, labelled as planning estimates, not for navigation, and credited to [ORG] as you direct. We would not redistribute or display your contours, soundings or rasters, and we would remove or update any figure on request.
>
> The metadata we found does not state whether this use is permitted. Could you tell us (1) whether publishing derived summary metrics is permitted, (2) whether keeping the data internally for analysis is permitted, (3) whether anything beyond that (for example showing contours in the app) would need separate permission, and (4) the attribution wording you prefer?
>
> Thank you for your time,
> [YOUR NAME], [COMPANY/PROJECT NAME], [CONTACT]

## 7. Suggested order

1. MN: decide on the CSV proposal; optionally send the section 4.1 note.
2. OH, MT (both cheap, 15 lakes): generic text.
3. CWMS question (28 tier C lakes).
4. OK, then FL (decide whether to ask at all given the explicit purpose clause).
5. ND, IL.
6. WA, NJ only if the individual lakes matter.
7. Optional confirmations: IENC flag, TWDB courtesy.

The outbound survey-data requests (TVA, USACE, utilities, state fisheries) are tracked separately in `DEPTH_SOURCE_REQUEST_QUEUE.md`.
