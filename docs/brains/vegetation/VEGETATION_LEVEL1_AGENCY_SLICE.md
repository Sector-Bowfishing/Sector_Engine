# Vegetation Brain — Level-1 agency observation slice (v1)

**Level 1 = provider / observed truth shown as-is.** Validation is source, date, units, range sanity and provenance — not an accuracy study. A failing Level-3 claim (satellite presence) never disables it. Code: `jobs/vegetation-brain/vegetation_brain/agency.py`; data: `vegetation_brain/data/agency_fwc_pacpvi.json` (16 KB, rebuildable with `tools/build_agency_fwc.py`, one open request).

## What is ingested now
| | |
|---|---|
| Source | Florida FWC Freshwater Fisheries Research, Long-Term Monitoring **lake PAC / PVI** (`…/WhatsHappeningOnMyLake/MapServer/41`) |
| Definitions | **PAC** = percent of the lake surface area with vegetation; **PVI** = percent of the water column occupied by vegetation (lake mean) — FWC definitions, `myfwc.com/research/freshwater/monitoring/plant-mapping/` |
| Scope | all vegetation the agency's sonar sees, including submerged. This is the **agency's** observation; it is not Sector observing submerged vegetation (`submergedVegetation.observed` stays false; a test enforces it) |
| Date | survey **year** (month not published) |
| Fleet lakes (9) | Apopka, Griffin, Harris (reported with Little Harris), Istokpoga, Kissimmee, Lochloosa, East Lake Tohopekaliga, Tohopekaliga (Toho), Okeechobee (several sector rows per year; listed, never averaged) — years 2015/2020–2023 depending on lake |
| Verification applied | source identity, units (agency definitions), survey year, 0–100 range, PVI ≤ PAC (rows failing are dropped and counted, never repaired — 0 dropped in the shipped data) |
| State block | `agencyObservation`: `status PROVIDER_VERIFIED`, `surveyYear`, `ageYears`, `historical` (> 2 years), `values[{pac,pvi}]`, units, scope, licence, `internalOnly`, summary sentence ("… survey 2023: vegetation covers 25 % of the lake surface and occupies 7 % of its water volume — historical") |
| Claim | `agencyVegetationObservation` = `PROVIDER_VERIFIED` for those lakes, `NOT_ASSESSED` elsewhere |
| Licensing | **UNCONFIRMED for customer use** (state open data; FWC asks users to acquire from FWC). Marked `internalOnly`; LICENSING blocker |
| Freshness | the layer holds no survey after 2023 (checked 2026-10-14: 2024–2026 = 0 rows), so every record is already "historical" |
| Cross-check | the layer separates East Lake Toho (PAC 15 %) from Toho (PAC 74 %) — consistent with the finding that the registry gives both the same polygon (Lake-owner issue) |

## Second source (ingested): SFWMD Lake Okeechobee littoral vegetation map, June 2016
| | |
|---|---|
| Source | SFWMD open ArcGIS layer `VEG_OKE_2016` (dominant vegetation class per **1-hectare** cell, photo-interpreted from June 2016 stereo aerial imagery) |
| Scope (stated in the block) | **Moore Haven and the south islands part of the Okeechobee marsh only** — not the whole lake, not open-lake SAV |
| Values shown as-is | mapped area 484.2 km², open water 142.4 km², largest vegetation classes by the agency's own labels: dominant cattail 75.0 km², floating emergent marsh 50.9, willow scrub 39.4, spikerush 23.7, swamp shrubland 21.0, dominant torpedograss 17.1 (+47 smaller classes omitted, counted) |
| Verification | area = cell COUNT × 0.01 km²; the layer's `Shape__Area` is web-mercator inflated (≈ 25 % at this latitude) so it is only a **cross-check** — corrected geometry area / cell-count area = **1.002**; class areas must not exceed mapped area (else the block is refused) |
| Date / age | June 2016 → **historical** (10 years) |
| Licence | SFWMD data policies: acknowledgement requested, "as is"; customer-use terms unconfirmed → `internalOnly` |
| Registry caveat | ≈ 80 % of this mapped marsh lies **outside** the Okeechobee registry polygon (Lake-owner issue); the block is lake-scoped context, not a cell overlay |
Rebuild: `tools/build_agency_sfwmd.py` (two small group-by requests).

## Not ingested (and why) — each is a product-use decision, not a download target
| Source | Product use | Status |
|---|---|---|
| SFWMD Kissimmee-chain littoral map (East Toho / Toho, April 2016, FLUCCS classes) | marsh extent on Toho / East Toho | different schema (FLUCCS) than the Okeechobee layer; needs a reviewed class mapping and the registry fix for the Toho polygons first → queued |
| FWC LTM point intercepts (96k points) | where agency saw plants | presence-only (no absences); useful as locations, large; not ingested |
| UMN Minnesota plant surveys (CC0, 1999–2018) | historical presence by lake | old; 1 GB raw → on request only |
| TVA, TPWD, WI DNR (request-only) | the large reservoirs bowfishers use | **EXTERNAL SOURCE**: request drafts ready, none sent |

## Rule for adding a source
It must (1) be authoritative and open or licensed, (2) have a stated date and units, (3) match fleet lakes one-to-one by a reviewed map, (4) answer a bowfisher question (is there vegetation, how much, where, how old), and (5) fit a compact record. Otherwise: do not ingest.
