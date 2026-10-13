# Vegetation Brain — external data request drafts (NOT SENT)

**Nothing here has been sent.** These are Michael-ready drafts. Contacts marked *[confirm]* must be verified on the agency's own site before sending (the scouting note `Sector_Research_Data/vegetation-brain/notes/09_umr_umn_requests_scouting.md` records the published channels the research found). Do not submit forms or email on Michael's behalf without approval.

## Common facts to state (all letters)
* **Who:** Sector Bowfishing (Sector Engine), a fishing-conditions app and data service. Be upfront that it is a commercial product.
* **Why:** to *validate* satellite-based mapping of surface-reaching aquatic vegetation (floating-leaf, mats, emergent belts) on reservoirs and lakes used by anglers. We do not need — and are not asking for — species-level management plans.
* **What we will do:** score our observer against your survey (precision/recall, shore-matched); report back a short summary of agreement; credit the source; **not redistribute your raw data**; ask before any customer-facing use of survey-derived numbers.
* **Licence ask:** written confirmation of (a) internal research/validation use, and (b) whether *derived* statistics (agreement scores, never raw polygons) may appear in product documentation.
* **Format preference:** shapefile/GeoJSON/CSV with survey date, method, lake id; or the report PDFs if no GIS exists.

## 1. TVA — aquatic plant management (Guntersville, Wheeler, Pickwick, Nickajack, Chickamauga, Watts Bar, Kentucky Lake …)
**To:** TVA aquatic plant management / river management *[confirm contact on tva.com; the site returned 403 to automated fetches, open in a browser]*
**Ask:** annual aquatic plant survey products 2018–2025 per reservoir: georeferenced polygons or grids with acreage and (if available) density class, survey dates, method; treatment/harvest maps with dates (so we do not score a sprayed bed as vegetation); any "potential management zone" layers.
**Why TVA matters:** these are the highest-value bowfishing reservoirs in the fleet and the research found no open survey data for them.

## 2. SFWMD — Lake Okeechobee submerged aquatic vegetation
**To:** SFWMD Lake Okeechobee / watershed research *[confirm via sfwmd.gov and DBHYDRO contact]*
**Ask:** the annual ~700-site SAV mapping (August–September, 2015–2025) as GIS points/grids with species, density/biomass class, and emergent (bulrush/cattail) mapping; sampling-site coordinates and dates.
**Note:** Okeechobee is in both the fleet and FWC's LTM program, so the two can cross-validate.

## 3. Texas Parks & Wildlife — Inland Fisheries aquatic vegetation
**To:** TPWD Inland Fisheries habitat / aquatic vegetation program *[confirm]*
**Ask:** reservoir aquatic vegetation surveys (acres or percent cover by type, survey dates, any GIS) for Sam Rayburn, Toledo Bend, Conroe, Fork, Caddo, Austin, Canyon and other fleet lakes, 2018–2025; treatment records (herbicide / grass carp) with dates.

## 4. Wisconsin DNR — point-intercept aquatic plant surveys
**To:** WI DNR lakes / aquatic invasive species (SWIMS) *[confirm]*
**Ask:** point-intercept survey results (point coordinates, rake fullness 0–3 or density, species/groups, date, depth, Secchi) for fleet lakes in Wisconsin (and Winnebago system), 2015–2025; the SWIMS export method.

## 5. Florida FWC — Freshwater Fish and Wildlife Research (Aquatic Plant Monitoring)
**To:** FWC aquatic plant monitoring / WhatsHappeningOnMyLake team *[confirm; publish contact on the viewer page]*
**Ask (a):** the **sonar BioVolume rasters 2015–2023** — the public `WhatsHappening_BioVolume<year>` ImageServers are listed but every request hangs. Please advise how to obtain the rasters (or the underlying survey points), their units, extent, resolution and survey dates. These are the only pixel-level submerged-vegetation truth we found.
**Ask (b):** survey dates for the LTM point intercepts and PAC/PVI lake-year records (we use the lake-year median point date as a proxy).
**Ask (c):** terms for use of the LTM and sonar data in a commercial product.

## 6. UMN Minnesota plant dataset (manual download, not a request)
Dataset *Occurrence and environmental data for aquatic plants of Minnesota from 1999–2018* (Verhoeven & Larkin), DOI `10.13020/av1t-c667`, CC0. The repository is behind a bot challenge. **Manual steps:** open the DOI in a normal browser → "Download" the CSV/zip → save to `~/Desktop/Development/Sector_Research_Data/vegetation-brain/sources/mn_umn/` (the scouting run writes `MANUAL_DOWNLOAD_STEPS.md` there if it could not fetch it itself). Then tell the next session: it will join to fleet lakes and use it for recall by lake.

## 7. After sending
Log each request (date, contact, response) in `docs/brains/vegetation/data/vegetation_request_log.csv` (not created until a request is sent). Licence answers go into the licensing matrix before any derived number is used outside internal validation.
