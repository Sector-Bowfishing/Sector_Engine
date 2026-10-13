# Depth Brain: Southeast Bathymetry Source Request Package

Prepared 2026-10-13. **Nothing in this package has been sent.** Every draft is for Michael to review, personalise and send himself; all tracking rows are `NOT_SENT`. Placeholders: `[YOUR NAME]`, `[CONTACT]` (email and phone), `[COMPANY/PROJECT NAME]`, `[YOUR STATE OF RESIDENCE]`.

This answers blocker B-depth-001 in the Depth Brain blocker queue: no public hydroacoustic or contour bathymetry was found for TVA, Alabama Power, Georgia Power, Duke, Santee Cooper, Dominion, or the AL/GA/SC/NC/KY/VA/LA/MS/MO/AR state agencies (23 states had zero contour/survey candidates; the scout's web-search budget ran out, so "not found" is not proof of absence).

Conventions used below:
* **Channel (verified)** = a page I fetched on 2026-10-13 that shows the channel. **Channel not found** = no official request channel located. **Unverified** = from general knowledge or a search summary, not fetched.
* Lake IDs are `lakeId` values from `data/depth_fleet_evidence_matrix.csv` (research tree). Operator / USACE-district assignments are from general knowledge and are **unverified**; confirm per lake before sending.
* Current evidence tiers for these lakes: Tier B-binary (IENC 9 ft only) for the Tennessee River chain and a few others, Tier C (CWMS hypsometry only) for several Corps lakes, otherwise Tier D (modeled GLOBathy prior). A real bathymetric survey would move a lake to Tier A.
* No person's name, personal email, or direct-dial number is used anywhere; individuals appearing on agency pages were deliberately left out.

## 1. What to ask for (standard list; trim per recipient)

1. Hydroacoustic / sonar survey data: raw soundings (XYZ points) or processed track data.
2. Bathymetric raster / depth grid / DEM (GeoTIFF, ESRI grid).
3. Contour shapefile / geodatabase / GeoPackage (state interval).
4. Survey report (PDF) with method, instrument, date and uncertainty.
5. Stage-area-volume (area-capacity) table or curve, with the elevation step.
6. Datum documentation: horizontal datum/projection; vertical datum (NGVD29 vs NAVD88) and the datum conversion used; and the **pool / water-surface elevation on the survey date(s)** so depths can be referenced to full pool.
7. Survey date(s) and any later sedimentation resurvey.
8. The licence or terms under which the data may be used (section 4).

If a full dataset is not available, partial answers are still valuable: a single PDF map with contours, a max-depth value, or the elevation-area table.

## 2. Intended-use statement (reuse in every request)

> [COMPANY/PROJECT NAME] is developing a bowfishing conditions application. We are building an internal environmental-depth research layer to understand how much of each lake is shallow water (for example 0 to 3 ft, 3 to 6 ft, and 6 to 10 ft) and how that changes with the lake's operating level through the year. We would use any data you share for **internal analysis**, and we would publish only **derived summary metrics** (for example "share of lake area shallower than 6 ft at full pool"), not your raw soundings, contours, rasters or reports, unless you give us explicit permission to do more. The data would not be sold, relicensed or used for navigation, and our published numbers would be labelled as planning estimates with the survey source and date credited as you direct.

## 3. Priority ranking (impact on bowfishing-heavy reservoirs)

Ranking weighs (a) the number of fleet lakes a single "yes" unlocks, (b) bowfishing relevance (Tennessee River chain, Hartwell, Lanier, Santee Cooper, Kentucky/Barkley), and (c) how credible the holder is (TVA is known to hold the data per correspondence cited in the ledger; Corps and utilities commonly hold area-capacity and hydrographic survey records, which is **unverified**).

| Rank | Organisation | Fleet lakes unlocked (count) | Why it ranks here |
|---:|---|---|---|
| 1 | TVA | 17: Guntersville, Wheeler, Wilson, Pickwick, Kentucky (TN and KY ids), Chickamauga, Watts Bar, Nickajack, Fort Loudoun, Douglas, Cherokee, Norris, Tims Ford, Hiwassee, Fontana, South Holston | Largest cluster of core bowfishing reservoirs, currently only Tier B-binary or D. Ledger S-depth-037 records 2009/2011 NRC correspondence indicating TVA holds processed bathymetry for Guntersville, Nickajack, Chickamauga, Watts Bar and Fort Loudoun (read by earlier research, not re-fetched here). |
| 2 | USACE Savannah District | 4: Hartwell, Strom Thurmond (SC and GA ids), Russell | Hartwell and Thurmond are marquee bowfishing waters; currently Tier C (CWMS hypsometry). |
| 3 | USACE Mobile District | 7: Lanier, Allatoona, Carters, West Point, Walter F. George (GA and AL ids), Bankhead | Lanier is a flagship; Corps hydrographic surveys are the likely holder. |
| 4 | Santee Cooper | 2: Lake Marion, Lake Moultrie | Santee Cooper lakes are core bowfishing water (shallow, stump-filled). Public-records channel verified. |
| 5 | Duke Energy | 8: Norman, Hickory, James, Wylie, Wateree, Keowee, Jocassee, Robinson | Many lakes, FERC-licensed projects. Only an informal channel found. |
| 6 | USACE Nashville District | 7: Barkley, Cumberland, Old Hickory, Percy Priest, Center Hill, Dale Hollow, Laurel River | Barkley/Kentucky is a stated core target; Barkley and Old Hickory currently Tier B-binary. |
| 7 | Alabama Power | 7: Martin, Weiss, Logan Martin, Neely Henry, Lay, Jordan, Smith | Lake Martin, Weiss, Logan Martin are popular bowfishing lakes. |
| 8 | SC DNR | 12 (all SC fleet lakes) | State fisheries may hold hydroacoustic surveys for Santee, Murray and others; verified FOIA channel. |
| 9 | Georgia DNR WRD / Georgia Power | 12 GA lakes; Georgia Power: Oconee, Sinclair, Burton | Ledger lead S-depth-035 is a GA PFA bathymetry layer (201 unnamed contour lines), a possible quick win for small lakes only. |
| 10 | Alabama DCNR WFF | 12 AL lakes | State biologists often hold lake maps and surveys. |
| 11 | USACE Little Rock District | 9: Beaver, Bull Shoals, Norfork, Greers Ferry, DeGray, Dardanelle, Ouachita, Millwood, Table Rock | Big Ozark/Ouachita reservoirs. |
| 12 | USACE Tulsa District | 10 OK Corps lakes | OK is partly covered by OWRB (internal-use flag, see licensing matrix). |
| 13 | Dominion Energy | 2: Murray, Monticello | Murray is a large SC lake. |
| 14 | USACE Wilmington District | 5: Falls, Jordan, Kerr (NC and VA ids), Philpott | |
| 15 | NC WRC | 12 NC lakes | |
| 16 | USACE Vicksburg District | 4 MS Corps lakes (Arkabutla, Enid, Grenada, Sardis) | Already Tier C via CWMS. |
| 17 | MDWFP, LDWF, AGFC, MDC, KDFWR, TWRA | MS 11, LA 12, AR 12, MO 11, KY 12, TN 15 | State biologists generally; AGFC publishes lake map PDFs (lead below). |
| 18 | USACE St. Louis District | 3: Wappapello, Clearwater, Mark Twain | |

## 4. Data-use and licence ask (include as a closing paragraph; also usable as a stand-alone email)

> We would like to confirm the terms under which we may use any data you share. Specifically: (1) may we derive and **publish summary depth metrics** (shallow-water shares by depth zone, mean depth, flat-area estimates) for [LAKES] in our application; (2) may we keep the underlying data **internally** for analysis; (3) is **redistribution of raw geometry** (contours, soundings, rasters) permitted, and if not, we will not do it; and (4) what **attribution wording** would you like us to use (for example "Depth data: [ORGANISATION], [YEAR]; derived summary metrics by [COMPANY]")? We will describe all figures as planning estimates, not for navigation, and we will remove or update any derived numbers if you ask.

Note on public-records requests: records-act responses give access to existing records, but they do **not** by themselves grant a licence to republish copyrighted or third-party-contracted material (surveys were often produced by contractors). The licence ask above is still worth making alongside any records request.

## 5. Cover letter template (one page)

```
[YOUR NAME]
[COMPANY/PROJECT NAME]
[CONTACT: email | phone | mailing address]
[DATE]

[ORGANISATION / OFFICE NAME from the channel listed for this recipient]
[ADDRESS or "Submitted via the online portal"]

Re: Request for existing bathymetric survey information for [LAKE(S)]

Dear Records Custodian / Lake Management Team,

I am writing to request existing bathymetric information for [LAKE(S)]. [COMPANY/PROJECT NAME] is
developing a bowfishing conditions application, and we are researching how much of each reservoir is
shallow water at different operating levels.

We are asking for whichever of the following already exists:
 1. hydroacoustic survey data (raw soundings or processed points);
 2. a bathymetric raster, depth grid or DEM;
 3. contour files (shapefile, geodatabase or GeoPackage);
 4. the survey report (PDF) with method, date and accuracy notes;
 5. a stage-area-volume (area-capacity) table or curve; and
 6. datum documentation: the vertical datum (NGVD29 or NAVD88) and the pool or water-surface
    elevation on each survey date.

Intended use: internal environmental-depth research. We would publish only derived summary metrics,
not your raw data, unless you grant additional permission. We have set out our questions about
permitted use and attribution in the attached note and would follow whatever terms you set.

[For public bodies:] I understand that fees may apply. Please contact me before incurring more than
$[AMOUNT]. I am happy to accept electronic delivery and to narrow the request if that helps. [For
agencies with a stated requester-category or residency form, complete it here: [YOUR STATE OF RESIDENCE].]

[For utilities / non-public bodies:] If this information is not something you share publicly, we
would be grateful for a pointer to the right team, or for a conversation about what could be shared.

Thank you for your time.

Sincerely,
[YOUR NAME]
[CONTACT]
```

## 6. Short email / form drafts

### 6a. Public-records version (state agencies, Santee Cooper, TVA, USACE)

Subject: Public records request: bathymetric survey data for [LAKE(S)]

> Dear Records Custodian,
>
> Under [state public-records law or FOIA, as applicable to this agency], I request copies of existing records that describe the bathymetry of [LAKE(S)], including any of: hydroacoustic survey data (soundings), bathymetric rasters or DEMs, contour files (shapefile or geodatabase), survey reports, stage-area-volume (area-capacity) tables, and documentation of the vertical datum and the water-surface elevation on the survey dates. Electronic copies are preferred. If a survey exists but is held by a contractor or another office, please tell me where.
>
> Purpose: internal environmental-depth research for a bowfishing conditions application; we would publish only derived summary metrics. Please let me know the licence or conditions that apply to any data you release, and whether you permit publication of derived summaries with attribution.
>
> Please contact me before incurring fees over $[AMOUNT]. [Requester category / residency statement if the form asks: [YOUR STATE OF RESIDENCE].]
>
> Thank you,
> [YOUR NAME], [COMPANY/PROJECT NAME], [CONTACT]

### 6b. Utility / informal version (Duke, Alabama Power, Georgia Power, Dominion)

Subject: Question about bathymetric data for [LAKE(S)]

> Hello,
>
> I'm [YOUR NAME] with [COMPANY/PROJECT NAME], a bowfishing conditions app. We are researching how much of [LAKE(S)] is shallow water across the year's pool levels. Does [ORGANISATION] hold any bathymetric survey data for these lakes (hydroacoustic data, contours, depth grids, survey reports, or area-capacity tables), and would you be willing to share any of it, or point me to the right team? We would use it for internal research and publish only derived summaries with whatever credit you prefer, and we would not redistribute your raw data without permission. Datum details (vertical datum and pool elevation on the survey date) would be especially helpful.
>
> Thank you,
> [YOUR NAME], [CONTACT]

### 6c. Biologist / fisheries-unit version (state wildlife agencies, general)

Subject: Lake survey data request for [LAKE(S)]

> Hello,
>
> I'm [YOUR NAME] with [COMPANY/PROJECT NAME]. We are putting together a lake-depth research layer for bowfishing, and your fisheries staff may have done hydroacoustic or sonar mapping on [LAKE(S)]. If a bathymetric map, contour file or survey report exists, could you share it or tell me whom to ask? Even a PDF or a note of the maximum depth and the pool level at survey time would help. We would only publish derived summary numbers with credit to your agency and would not redistribute the data without permission.
>
> Thank you,
> [YOUR NAME], [CONTACT]

## 7. Per-organisation sections

### 7.1 TVA (rank 1)
* **Ask for:** bathymetry / hydrographic survey data (processed soundings, DEM or contours) for the Tennessee River reservoirs; area-capacity tables; reservoir datum and elevation-at-survey documentation (flood-control, summer and winter pool levels).
* **Fleet lakes unlocked (17):** Guntersville|AL, Wheeler|AL, Wilson|AL, Pickwick Lake|TN, Kentucky Lake|TN, Kentucky Lake|KY, Chickamauga Lake|TN, Watts Bar Lake|TN, Nickajack Lake|TN, Fort Loudoun Lake|TN, Douglas Lake|TN, Cherokee Lake|TN, Norris Lake|TN, Tims Ford Lake|TN, Hiwassee Lake|NC, Fontana Lake|NC, South Holston Lake|VA.
* **Channel (verified):** TVA FOIA portal, https://foia.tva.gov/ ("Submit A FOIA Records Request"); FAQ https://foia.tva.gov/faq lists the FOIA Requester Service Center at 400 West Summit Hill Dr., Knoxville, TN 37902-1401 and states fee categories (commercial-use requesters pay search, review and reproduction fees; others pay less). Choose the requester category deliberately. The TVA river-management contact page returned 403 to automated fetch (**unverified**), so look for a non-FOIA contact there manually.
* **Notes:** a FOIA request reaches existing records only; a combined informal ask to the reservoir/river-management group may be faster. Use draft 6a for FOIA and 6b for an informal approach.
* **Intended use / licence ask:** sections 2 and 4.

### 7.2 Alabama DCNR, Wildlife and Freshwater Fisheries (rank 10)
* **Ask for:** hydroacoustic or sonar lake surveys, lake maps, contour files, survey PDFs for state-managed and large impoundments.
* **Fleet lakes (12):** Bankhead, Eufaula / W.F. George, Guntersville, Jordan, Lake Martin, Lay, Logan Martin, Neely Henry, Smith (Lewis Smith), Weiss, Wheeler, Wilson (all `|AL`).
* **Channel (verified):** ADCNR contact page https://www.outdooralabama.com/top-navigation/contact-us lists "Requests for Open Records" under ADCNR Administrative Offices with phone (334) 242-3165. No online form or email was found there (**channel partly found**). Residency: Alabama's records law is believed to limit requests to residents (**unverified**, from a search summary); consider whether a resident should file.
* **Use drafts:** 6c (fisheries) or 6a (open records).

### 7.3 Alabama Power (rank 7)
* **Ask for:** hydroacoustic surveys, bathymetric maps, area-capacity tables, datum and pool elevations for Lake Martin, Weiss, Logan Martin, Neely Henry, Lay, Jordan, Smith.
* **Fleet lakes (7):** Lake Martin|AL, Weiss|AL, Logan Martin|AL, Neely Henry|AL, Lay|AL, Jordan|AL, Smith (Lewis Smith)|AL.
* **Channel:** Alabama Power's shorelines site links a contact page, https://apcshorelines.com/contact/ (listed in the site navigation; the site returned 403 to automated fetch and the contact page itself was not read, so **no email or phone verified**). Not a public body, so the informal draft 6b applies; this is a voluntary request.

### 7.4 Georgia DNR Wildlife Resources Division and Georgia Power (ranks 9)
* **Georgia DNR WRD ask:** lake surveys, contour files (ledger lead: the "PFA_Bathymetry" layer, 201 unnamed contour lines, for small public fishing areas), survey reports.
* **Fleet lakes (12):** Allatoona, Blackshear, Burton, Carters, Clarks Hill / J.S. Thurmond, Lake Russell, Lanier, Oconee, Seminole, Sinclair, Walter F. George / Eufaula, West Point (all `|GA`).
* **Channel (verified):** Georgia DNR open records form, https://gadnr.org/gorarequest ("GORA Request"); the page says requests may be oral or written, written preferred, and an hourly administrative charge may apply. Use drafts 6a/6c.
* **Georgia Power ask:** hydrographic surveys for Lake Oconee, Lake Sinclair and Lake Burton; area-capacity; datum.
* **Fleet lakes (3):** Oconee|GA, Sinclair|GA, Burton|GA.
* **Channel (verified):** shoreline management page https://www.georgiapower.com/our-impact/lakes-rivers/shoreline-management.html shows Land Management Offices (East Georgia Lakes general office number listed on the page: 706-484-7500); North Georgia Lakes Resources Office page https://www.georgiapower.com/our-impact/lakes-rivers/our-lakes/north-georgia-lakes.html lists 4 Seed Lake Road, Lakemont, GA 30552, phone 706-746-1450. These are shoreline-permit offices, so ask them to route a data question (draft 6b).

### 7.5 Duke Energy: Catawba-Wateree and Keowee-Toxaway (rank 5)
* **Ask for:** bathymetric survey data and area-capacity for the Catawba-Wateree chain and Lakes Keowee/Jocassee; datum and full-pool elevation documentation.
* **Fleet lakes (8):** Lake Norman|NC, Lake Hickory|NC, Lake James|NC, Lake Wylie|SC, Lake Wateree|SC, Lake Keowee|SC, Lake Jocassee|SC, Lake Robinson|SC. (Duke's lakes page, https://duke-energy.com/community/lakes/services, confirms Catawba-Wateree lakes James, Rhodhiss, Hickory, Lookout Shoals, Norman, Mountain Island, Wylie, Fishing Creek, Rocky Creek and Wateree, Keowee and Jocassee, and a "Shoreline Use at Lake Robinson" page. Badin and High Rock are not listed there; operator unverified.)
* **Channel (verified):** Duke Lake Services, LakeServices@duke-energy.com or 800.443.5193, as printed on the lakes services page above. This is a shoreline-permit team, so ask them to route a data request to the licence/hydro group (draft 6b).
* **Lead (unverified):** FERC relicensing filings for these projects may contain bathymetric studies; a search of FERC eLibrary is worth doing before asking.

### 7.6 Dominion Energy and Santee Cooper (ranks 4 and 13)
* **Santee Cooper ask:** hydroacoustic surveys, sedimentation resurveys and area-capacity tables for Lake Marion and Lake Moultrie, with datum documentation.
* **Fleet lakes (2):** Lake Marion|SC, Lake Moultrie|SC.
* **Channel (verified):** Santee Cooper FOIA page https://www.santeecooper.com/About/FOIA/ : requests must be in writing, sent to the FOIA Officer by email (foia.request@santeecooper.com) or mail (P.O. Box 2946101, Moncks Corner, SC 29461-6101); the page also publishes a fee schedule. Draft 6a. Santee Cooper is a state-owned utility and subject to FOIA.
* **Dominion ask:** Lake Murray and Lake Monticello survey data (the lakes Dominion's pages cover).
* **Fleet lakes (2):** Lake Murray (SC)|SC, Lake Monticello|SC.
* **Channel (verified):** https://dominionenergy.com/lakes-and-recreation/lake-murray-sc lists Dominion Energy Lake Management, PO5, Cayce, SC 29033; Lake Management Office 803-217-9221; Lake Murray hotline 800-830-5253. No email or records form found. Draft 6b.

### 7.7 South Carolina DNR (rank 8)
* **Ask for:** fisheries hydroacoustic surveys, lake maps, contour files for Santee Cooper lakes, Murray, Hartwell, Thurmond and others; survey reports; pool elevations.
* **Fleet lakes (12):** Greenwood, Hartwell, Jocassee, Keowee, Marion, Monticello, Moultrie, Murray, Robinson, Strom Thurmond, Wateree, Wylie (all SC ids).
* **Channel (verified):** SCDNR FOIA page https://www.dnr.sc.gov/admin/foia.html : send to FOIA@dnr.sc.gov, or mail P.O. Box 167, Columbia, SC 29202; how-to page https://www.dnr.sc.gov/admin/foia/howto.html requires a written request, a daytime phone/email, and a maximum search fee you are prepared to pay. Draft 6a, with the max fee stated.

### 7.8 North Carolina Wildlife Resources Commission (rank 15)
* **Ask for:** fisheries lake surveys and maps for NC impoundments and natural lakes.
* **Fleet lakes (12):** Badin Lake, Falls Lake, Fontana Lake, High Rock Lake, Hiwassee Lake, Jordan Lake, Kerr Lake, Lake Hickory, Lake James, Lake Mattamuskeet, Lake Norman, Lake Waccamaw (all `|NC`).
* **Channel (verified):** https://www.ncwildlife.gov/connect/contact-us shows a "Public Records Requests" link that opens an email to publicrecords@ncwildlife.gov. Draft 6a/6c.

### 7.9 State fisheries biologists, generally
No individual contacts are listed here by design. For each state (AL, GA, SC, NC, KY, TN, AR, MS, LA, MO), route through the agency channels in this section and ask the records office to forward draft 6c to the regional fisheries unit. Michael can also ask, in the licence note, for the name of the right biologist.

### 7.10 USACE districts: Mobile, Savannah, Wilmington, Nashville, Little Rock, Tulsa, Vicksburg, St. Louis (ranks 2, 3, 6, 11, 12, 14, 16, 18)
* **Ask for:** hydrographic survey reports and sounding or DEM files; sedimentation resurveys; **stage-area-capacity tables** (the district water-management office typically holds these; unverified); datum documentation for pool elevations (NGVD29 vs NAVD88), including the elevation at each survey date; and clarity on the terms of the public CWMS Data API (see licensing matrix, class UNCLEAR).
* **Fleet lakes by district (unverified assignment):**
  * Savannah (4): Lake Hartwell|SC, Lake Strom Thurmond (Clarks Hill)|SC, Clarks Hill / J.S. Thurmond|GA, Lake Russell (R.B. Russell)|GA.
  * Mobile (7): Lanier (Sidney Lanier)|GA, Allatoona|GA, Carters|GA, West Point|GA, Walter F. George / Eufaula|GA, Eufaula / W.F. George|AL, Bankhead|AL.
  * Wilmington (5): Falls Lake|NC, Jordan Lake|NC, Kerr Lake (John H. Kerr)|NC, Kerr Reservoir (Buggs Island)|VA, Philpott Lake|VA.
  * Nashville (7): Lake Barkley|KY, Lake Cumberland|KY, Old Hickory Lake|TN, Percy Priest Lake|TN, Center Hill Lake|TN, Dale Hollow Lake|TN, Laurel River Lake|KY.
  * Little Rock (9): Beaver|AR, Bull Shoals Lake|AR, Norfork|AR, Greers Ferry|AR, DeGray|AR, Dardanelle|AR, Ouachita (L. Ouachita)|AR, Millwood|AR, Table Rock Lake|MO.
  * Tulsa (10): Lake Eufaula|OK, Keystone Lake|OK, Oologah Lake|OK, Fort Gibson Lake|OK, Lake Tenkiller|OK, Broken Bow Lake|OK, Kaw Lake|OK, Skiatook Lake|OK, Canton Lake|OK, Sardis Lake|OK.
  * Vicksburg (4): Arkabutla Lake|MS, Enid Lake|MS, Grenada Lake|MS, Sardis Lake|MS.
  * St. Louis (3): Wappapello Lake|MO, Clearwater Lake|MO, Mark Twain Lake|MO.
* **Channel: not verified.** The USACE district sites and the main USACE FOIA/disclaimer pages return HTTP 403 to automated fetch, so I could not read any district FOIA page. The federal FOIA portal landing page https://www.foia.gov/ responded (200) but its request routing is script-driven and was not confirmed. Michael should open each district's FOIA page in a normal browser; USACE FOIA offices are organised by division/district (search result, **unverified**). A cheaper first step is the district's water-management or public-affairs office (informal), asking for the survey reports and area-capacity tables.
* **Draft:** 6a, tailored per district. Note: Louisville District lakes (Barren River, Green River, Nolin River, Rough River, Taylorsville in KY), Kansas City District lakes (Truman, Stockton, Pomme de Terre, Smithville in MO) and Memphis District are not in the requested district list; add them if desired.

### 7.11 Arkansas Game and Fish Commission (rank 17)
* **Ask for:** lake survey maps/hydroacoustic data for Lake Chicot, Lake Hamilton, Millwood, Nimrod, Beaver, Bull Shoals, Norfork, Greers Ferry, Catherine, Ouachita, DeGray, Dardanelle (the 12 AR fleet lakes).
* **Existing public lead (verified):** https://www.agfc.com/resources/maps/arkansas-lake-maps/ lists downloadable lake map PDFs, including a "Bathymetry Maps" section for some small lakes and downloadable maps for Lake Chicot and Norfork Lake Tailwater, among others. It is not confirmed that the Chicot file is a bathymetric map; inspect it before asking.
* **Channel: not found** as a dedicated records page (searched the AGFC site; common FOIA paths returned 404). Contact page https://www.agfc.com/contact-us/ lists headquarters phone 501-207-0326 (verified). Arkansas FOIA is believed to be limited to Arkansas citizens (**unverified**).

### 7.12 Missouri Department of Conservation (rank 17)
* **Fleet lakes (11):** Clearwater, Taneycomo, Lake of the Ozarks, Longview, Mark Twain, Pomme de Terre, Smithville, Stockton, Table Rock, Truman, Wappapello (all `|MO`).
* **Channel (verified):** https://mdc.mo.gov/contact-engage/public-records-requests : submit via the MDC Public Records Center online, or fax or mail the Custodian of Records (P.O. Box 180, Jefferson City, MO 65102); the page lists fee and fee-waiver language and a custodian phone line. Draft 6a/6c.

### 7.13 Louisiana Department of Wildlife and Fisheries (rank 17)
* **Fleet lakes (12):** Calcasieu, Catahoula, Cross Lake, False River, Grand Lake, Henderson Lake, Lake Bistineau, Lake D'Arbonne, Lake Maurepas, Lake Pontchartrain, Sabine Lake, White Lake (all `|LA`).
* **Channel (verified):** https://www.wlf.louisiana.gov/page/public-records-request : email WLFPublicRecords@wlf.la.gov or US mail to the LDWF Office of the Secretary (the page lists the mailing details). Draft 6a/6c.

### 7.14 Mississippi Department of Wildlife, Fisheries and Parks (rank 17)
* **Fleet lakes (11):** Arkabutla, Bay Springs, Columbus, Eagle Lake, Enid, Grenada, Lake Washington, Moon Lake, Okatibbee, Ross Barnett, Sardis (all `|MS`).
* **Channel (verified):** online public record request form, https://www.ms.gov/mdwfp/public_record/ (linked as "Public Information Request" from https://www.mdwfp.com/contact-us). Draft 6a/6c.

### 7.15 Kentucky Department of Fish and Wildlife Resources (rank 17)
* **Fleet lakes (12):** Barren River, Buckhorn, Cave Run, Green River, Herrington, Kentucky Lake, Lake Barkley, Lake Cumberland, Laurel River, Nolin River, Rough River, Taylorsville (all `|KY`).
* **Channel (verified):** https://fw.ky.gov/More/Pages/Open-Records-Procedures.aspx . **Two terms matter:** a residency statement is required (KRS 61.872(2) as quoted on the page), and the page defines "commercial purpose" (KRS 61.870(4)) and says KDFWR requires a certified statement for commercial-purpose requests. Sector's use is likely to be treated as commercial; read the page's full conditions before filing and answer honestly.

### 7.16 Tennessee Wildlife Resources Agency and TVA (rank 17; TVA in 7.1)
* **Fleet lakes (15 TN ids):** Center Hill, Cherokee, Chickamauga, Dale Hollow, Douglas, Fort Loudoun, Kentucky Lake, Nickajack, Norris, Old Hickory, Percy Priest, Pickwick, Reelfoot, Tims Ford, Watts Bar.
* **Channel (verified):** https://www.tn.gov/twra/contact-us.html has a "Public Records Request" section (existing records only; the agency does not create records) with a link to TWRA's public records policy. Ask TWRA for Reelfoot Lake and for the 4 small-lake contours already online (ledger lead S-depth-016).

## 8. Tracking table

| # | Organisation | Channel (verified or not) | Priority | Lakes unlocked | Date sent | Status | Response / licence outcome | Follow-up due |
|---:|---|---|---:|---:|---|---|---|---|
| 1 | TVA | foia.tva.gov portal (verified) | 1 | 17 | | NOT_SENT | | |
| 2 | USACE Savannah | FOIA page not verified (403) | 2 | 4 | | NOT_SENT | | |
| 3 | USACE Mobile | FOIA page not verified (403) | 3 | 7 | | NOT_SENT | | |
| 4 | Santee Cooper | FOIA email/mail (verified) | 4 | 2 | | NOT_SENT | | |
| 5 | Duke Energy | LakeServices email/phone (verified) | 5 | 8 | | NOT_SENT | | |
| 6 | USACE Nashville | FOIA page not verified (403) | 6 | 7 | | NOT_SENT | | |
| 7 | Alabama Power | apcshorelines.com/contact (page not read) | 7 | 7 | | NOT_SENT | | |
| 8 | SC DNR | FOIA@ email/mail (verified) | 8 | 12 | | NOT_SENT | | |
| 9 | Georgia DNR WRD | gadnr.org/gorarequest form (verified) | 9 | 12 | | NOT_SENT | | |
| 9b | Georgia Power | Land Management offices (verified) | 9 | 3 | | NOT_SENT | | |
| 10 | Alabama DCNR WFF | open-records phone (verified) | 10 | 12 | | NOT_SENT | | |
| 11 | USACE Little Rock | FOIA page not verified (403) | 11 | 9 | | NOT_SENT | | |
| 12 | USACE Tulsa | FOIA page not verified (403) | 12 | 10 | | NOT_SENT | | |
| 13 | Dominion Energy (Lake Management) | phone/mail (verified) | 13 | 2 | | NOT_SENT | | |
| 14 | USACE Wilmington | FOIA page not verified (403) | 14 | 5 | | NOT_SENT | | |
| 15 | NC WRC | publicrecords@ email (verified) | 15 | 12 | | NOT_SENT | | |
| 16 | USACE Vicksburg | FOIA page not verified (403) | 16 | 4 | | NOT_SENT | | |
| 17 | Mississippi MDWFP | online form (verified) | 17 | 11 | | NOT_SENT | | |
| 18 | Louisiana LDWF | email/mail (verified) | 17 | 12 | | NOT_SENT | | |
| 19 | Missouri MDC | Public Records Center (verified) | 17 | 11 | | NOT_SENT | | |
| 20 | Kentucky KDFWR | open-records procedures (verified; residency + commercial clause) | 17 | 12 | | NOT_SENT | | |
| 21 | Tennessee TWRA | public records section (verified) | 17 | 15 | | NOT_SENT | | |
| 22 | Arkansas AGFC | channel not found (HQ phone only) | 17 | 12 | | NOT_SENT | | |
| 23 | USACE St. Louis | FOIA page not verified (403) | 18 | 3 | | NOT_SENT | | |
| 24 | Licence follow-ups from the Licensing Matrix (MN DNR, ODNR, MT FWP, ND G&F, WA Ecology, IDNR, OWRB, MGS, TWDB fishing-disclaimer question) | various | n/a | see matrix | | NOT_SENT | | |

## 9. Short report

**Licence classification counts (37 sources reviewed; details in `DEPTH_LICENSING_MATRIX.md`):** PUBLIC_REUSABLE 13, ATTRIBUTION_REQUIRED 8, INTERNAL_ONLY 2 (FL FWC, OK OWRB), UNCLEAR 13, RESTRICTED 1 (NJ DEP, "not for commercial use").

**Blocked from customer use:** FL FWC (purpose-limited to aquatic environmental management; verified clause), OK OWRB (service item says "Internal Use"), NJ DEP (not for commercial use), and the UNCLEAR set: MN DNR, MT FWP, ODNR, ND Game and Fish, WA Ecology (contradictory terms), IL DNR, TN TWRA, WI association layer, PA/UT local layers, Maryland Geological Survey, USACE CWMS, USACE NID. Effect on the fleet: 57 of 140 contour-sourced lakes are blocked from customer-facing derived numbers (32 Tier A, 12 Tier B, 13 Tier B-partial); 83 are safe (45 Tier A). The 28 CWMS-only Tier C lakes are also blocked until USACE confirms CWMS terms.

**Clear to use (with the attribution listed):** TWDB (caveat: not-for-fishing disclaimer), MI, WV, MA, IN, NE, CT, NH, KS, USGS inventory and releases (per-release check), EPA NLA, IENC (confirm "non-public" metadata flag), 3DEP, GLOBathy, HydroLAKES, JRC GSW, Landsat, Sentinel-2, NWIS.

**Organisations with an identifiable public request channel (verified by fetch):** TVA (FOIA portal), Santee Cooper (FOIA email/mail), SC DNR (FOIA email/mail), Georgia DNR (GORA form), NC WRC (public-records email), Missouri MDC (Public Records Center), Louisiana LDWF (email/mail), Mississippi MDWFP (online form), Kentucky KDFWR (procedures page, residency and commercial-purpose conditions), Tennessee TWRA (public-records section). Partial: Alabama DCNR (open-records phone line only), Duke Energy (Lake Services email/phone, informal), Georgia Power (land management offices, informal), Dominion Energy (Lake Management phone/mail), Alabama Power (contact page named but not read). **Channel not found or not verified:** Arkansas AGFC (HQ phone only; no records page), all USACE districts (sites return 403 to automated fetch).

**Caveats Michael should know before sending:** several states restrict public-records requests to residents (KY verified; AL and AR from search summaries, unverified); KY and TVA have commercial-requester provisions with fee or certification consequences; a records release is not a licence to republish, so keep the licence ask in every message; operator and district assignments of lakes are from general knowledge and should be confirmed per lake.
