# Vegetation Brain — external data request drafts (NOT SENT)

**Nothing here has been sent.** These are Michael-ready drafts. Contacts marked *[confirm]* must be verified on the agency's own site before sending (the scouting note `Sector_Research_Data/vegetation-brain/notes/09_umr_umn_requests_scouting.md` records the published channels the research found). Do not submit forms or email on Michael's behalf without approval.

## Common facts to state (all letters)
* **Who:** Sector Bowfishing (Sector Engine), a fishing-conditions app and data service. Be upfront that it is a commercial product.
* **Why:** to *validate* satellite-based mapping of surface-reaching aquatic vegetation (floating-leaf, mats, emergent belts) on reservoirs and lakes used by anglers. We do not need — and are not asking for — species-level management plans.
* **What we will do:** score our observer against your survey (precision/recall, shore-matched); report back a short summary of agreement; credit the source; **not redistribute your raw data**; ask before any customer-facing use of survey-derived numbers.
* **Licence ask:** written confirmation of (a) internal research/validation use, and (b) whether *derived* statistics (agreement scores, never raw polygons) may appear in product documentation.
* **Format preference:** shapefile/GeoJSON/CSV with survey date, method, lake id; or the report PDFs if no GIS exists.

## 1. TVA — aquatic plant management (Guntersville, Wheeler, Pickwick, Nickajack, Chickamauga, Watts Bar, Kentucky Lake …)
**To:** TVA aquatic plant management *[open https://www.tva.com/aquaticplants in a browser and take the contact address from the page: it returns a Cloudflare challenge to automated clients, so none was fetched]*
**Ask:** annual aquatic plant survey products 2018–2025 per reservoir: georeferenced polygons or grids with acreage and (if available) density class, survey dates, method; treatment/harvest maps with dates (so we do not score a sprayed bed as vegetation); any "potential management zone" layers.
**Why TVA matters:** these are the highest-value bowfishing reservoirs in the fleet and the research found no open survey data for them.

## 2. SFWMD — Lake Okeechobee submerged aquatic vegetation
**To:** SFWMD GIS data: `gisdata@sfwmd.gov`; public records: `publicrecords@sfwmd.gov`, (561) 682-2729 (published on sfwmd.gov). **First check what is already open:** Okeechobee and Kissimmee *littoral* vegetation polygons (2003–2016) are anonymous ArcGIS services on `geodata.sfwmd.gov` (no request needed); open-lake SAV layers were not found, which is what to ask for.
**Ask:** the annual ~700-site SAV mapping (August–September, 2015–2025) as GIS points/grids with species, density/biomass class, and emergent (bulrush/cattail) mapping; sampling-site coordinates and dates.
**Note:** Okeechobee is in both the fleet and FWC's LTM program, so the two can cross-validate.

## 3. Texas Parks & Wildlife — Inland Fisheries aquatic vegetation
**To:** TPWD has no vegetation GIS download. Published formal channel: Open Records Center `https://tpwdtexas.govqa.us`, `Public.Information@tpwd.texas.gov` (Open Records Coordinator). Consider first asking Inland Fisheries habitat staff for the annual survey spreadsheets *[confirm contact on tpwd.texas.gov]*
**Ask:** reservoir aquatic vegetation surveys (acres or percent cover by type, survey dates, any GIS) for Sam Rayburn, Toledo Bend, Conroe, Fork, Caddo, Austin, Canyon and other fleet lakes, 2018–2025; treatment records (herbicide / grass carp) with dates.

## 4. Wisconsin DNR — point-intercept aquatic plant surveys
**To:** `DNRAPMProgram@Wisconsin.gov` (Aquatic Plant Management program, published on the DNR plants page); regional coordinator map: `dnr.wisconsin.gov/sites/default/files/topic/Lakes/APMCoordinatorMap.pdf`. The Aquatic Plant Explorer app is view-only and SWIMS is login-gated, so bulk PI data is request-only.
**Ask:** point-intercept survey results (point coordinates, rake fullness 0–3 or density, species/groups, date, depth, Secchi) for fleet lakes in Wisconsin (and Winnebago system), 2015–2025; the SWIMS export method.

## 5. Florida FWC — Freshwater Fish and Wildlife Research (Aquatic Plant Monitoring)
**To:** FWC aquatic plant monitoring / WhatsHappeningOnMyLake team *[confirm; publish contact on the viewer page]*
**Ask (a):** the **sonar BioVolume rasters 2015–2023** — the public `WhatsHappening_BioVolume<year>` ImageServers are listed but every request hangs. Please advise how to obtain the rasters (or the underlying survey points), their units, extent, resolution and survey dates. These are the only pixel-level submerged-vegetation truth we found.
**Ask (b):** survey dates for the LTM point intercepts and PAC/PVI lake-year records (we use the lake-year median point date as a proxy).
**Ask (c):** terms for use of the LTM and sonar data in a commercial product.

## 6. UMN Minnesota plant dataset — OBTAINED, no request needed
*Occurrence and environmental data for aquatic plants of Minnesota from 1999–2018* (Verhoeven & Larkin), DOI `10.13020/av1t-c667`, **CC0**, downloaded in full (37 MB) through the repository's public API without bypassing anything; stored at `Sector_Research_Data/vegetation-brain/sources/mn_umn/` (outside Git). Caveat: its `SURFACE_GROWTH` flag is empty for fleet lakes, so surface truth comes from a taxon lookup (documented in note 10). Optional courtesy: tell the authors (listed in the dataset README) how it is used.

## 6b. UMRS 2020 land-cover pool polygons — manual browser download (needs a signed URL)
ScienceBase item `6102cbf7d34ef8d7055e7971`. Steps (also in note 09 §1.4): open the item in a browser → "Attached Files" → click `2020_LCU_Pool_04.zip` (62.7 MB; covers Lake Pepin) and optionally `2020_LCU_Pool_08.zip` → save to `Sector_Research_Data/vegetation-brain/sources/umrs_landcover/`. Surface classes in the 2020 schema: `Rf` rooted floating, `Dma`/`Dmp` deep marsh emergents (`Sma`/`Smp` ambiguous); `Sv` submersed is not surface-reaching.

## 7. After sending
Log each request (date, contact, response) in `docs/brains/vegetation/data/vegetation_request_log.csv` (not created until a request is sent). Licence answers go into the licensing matrix before any derived number is used outside internal validation.
