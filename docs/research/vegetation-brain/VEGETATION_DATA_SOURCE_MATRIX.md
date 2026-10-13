# Vegetation Brain — Data Source Matrix

**RESEARCH ONLY. Proposed Brain; no production Vegetation Brain exists.** Checked 2026-10-13. Evidence grades: **V-fetch** (API/page fetched and content seen), **V-200** (landing page responded only), **V-search** (seen in a search result, not opened), **U** (background knowledge). Details and dead links: `VEGETATION_SOURCE_LEDGER.md`.

## 1. Headline

**No single multi-state, downloadable, polygon-level submerged-vegetation ground truth exists for US reservoirs.** What does exist:
1. A few point-intercept survey databases (Florida FWC, Minnesota, Wisconsin, Upper Mississippi).
2. One national class-and-density survey (EPA NLA) that happens to be in Sector's target taxonomy.
3. Coarse wetland/land-cover layers (NWI, NLCD, C-CAP, LANDFIRE) usable as priors.
4. Presence-only invasive records (USGS NAS, EDDMapS).
5. Request-only agency acreage reports (TVA, SFWMD, TPWD, Corps).

The Vegetation Brain's **observations** must therefore come from satellites; surveys are the **validation and calibration** layer; NWI et al. are **priors**.

## 2. Roles

| Role | Meaning |
|---|---|
| OBSERVE | Per-lake, dated, repeatable, fleet-scale — can drive a production layer |
| VALIDATE | Independent ground truth to score the observer |
| PRIOR | Static context; never presented as current state |
| LOOKUP | Species→class tables, regimes, management flags |

## 3. Sources, ranked by value to Sector

| # | Source | Role | Evidence | Access | Fleet reach | Class / density mapping | Key limit |
|---|---|---|---|---|---|---|---|
| 1 | **Sentinel-2 L2A** (AWS Earth Search STAC, COGs) | OBSERVE | V (used by Clarity today; empirical test in this campaign) | Open, free | All 621 (polygons for 599) | Surface-reaching EMERGENT/FLOATING/mats well; SUBMERGED only when shallow+clear | 10 m, clouds, ice, atmos. correction over water |
| 2 | **EPA NLA 2017 physical habitat** | VALIDATE | V-fetch, downloaded | Open CSV | **69 fleet lakes** have an NLA site inside their polygon (this campaign's join); 47 have usable cover rows | Direct: emergent / floating / submergent cover 0–4 (0, <10, 10–40, 40–75, >75 %) | Shoreline stations (≈10 m plots), summer 2017 only; big reservoirs rarely sampled |
| 3 | **FL FWC LTM point intercepts** | VALIDATE | V-fetch, downloaded (96,055 pts, 2015–2023) | Open ArcGIS REST | 10 FL fleet lakes (Okeechobee, Kissimmee, Istokpoga, Harris, Griffin, Apopka, Lochloosa, Orange, George, Crescent) | Species list per point → class lookup | Presence only; density via richness; spelling hygiene |
| 4 | **Minnesota plant occurrence (Verhoeven & Larkin, UMN CC0)** | VALIDATE | V-search only (repo behind bot challenge) | Browser download | MN lakes (≈12 in fleet) | Taxon → class; subset has point abundance | **Not downloaded; layout unverified** |
| 5 | **USGS UMESC LTRM vegetation CSV + 2020 land cover polygons** | VALIDATE | CSV V-fetch, downloaded; 2020 polygons listed, not downloaded | Open ScienceBase | Mississippi/Illinois pools | Species presence; LC polygons class schema **unconfirmed** | Few fleet lakes |
| 6 | **USFWS NWI (Wetlands REST)** | PRIOR | V-fetch (query near Guntersville returned L1UBHh, L2USCh, PEM1Ch) | Open REST, 500 rec/page | CONUS | L2AB/PAB aquatic bed, PEM emergent, PFO/PSS flooded woody | Photo-interpreted, decades old; not current |
| 7 | **NLCD 90/95; C-CAP; LANDFIRE** | PRIOR | V-200 | Open | CONUS | NLCD EMERGENT/FLOODED only; C-CAP has Aquatic Bed (coastal) | No submerged |
| 8 | **JRC Global Surface Water** | PRIOR/MASK | V-search | Open | Global | Water occurrence/seasonality → flooded-terrestrial candidate zone, drawdown | Vegetated water can read as non-water |
| 9 | **Sentinel-1 / ALOS L-band** | OBSERVE (emergent/flooded) | V-search | Open | CONUS | C-band moderate; L-band 83–86 % flooded marsh | Open-water SAV invisible |
| 10 | **NAIP (1 m, 4-band, 2–3 yr)** | OBSERVE/LABELS | U (no NAIP-specific aquatic validation found) | Open | CONUS | Emergent/floating polygons; shallow-clear SAV | Single date per cycle, stale |
| 11 | **USGS NAS API** | VALIDATE (species) | V-fetch | Open | Nationwide, uneven | Species→class | Presence-only, no absence |
| 12 | **TVA aquatic plant surveys** | VALIDATE | V-search (tva.com 403 to curl) | Request | 15 fleet lakes are TVA/TN-valley reservoirs by name | Species + acreage | No download found |
| 13 | **SFWMD Okeechobee SAV (700-site grid)** | VALIDATE | V-search; SAV page docx opened | Request | Okeechobee | Species → class; sparse/moderate/dense by biomass | Reports only |
| 14 | **TPWD lake reports / vegetation acreage** | VALIDATE | V-fetch (Sam Rayburn report opened) | Report | TX lakes | % area / acres | PDFs, no GIS |
| 15 | **WI DNR point-intercept (SWIMS)** | VALIDATE | V-200 | Request/PDF | WI lakes | Rake fullness 0–3 | Effort |
| 16 | **MI EGLE ANC survey-site layer** | INDEX | V-fetch (674 sites) | Open REST | MI lakes | Where/when surveyed only | No geometries of vegetation |
| 17 | **EDDMapS / MISIN / iMapInvasives / MIDAS** | VALIDATE (weak) | V-200 (MIDAS no response) | Account | Uneven | Species presence | No absences |
| 18 | **Corps APIS** | LOOKUP | V-search | Web | n/a | Plant ID/management info only; **not survey data** | — |
| 19 | **CA Delta hyperspectral SAV (CSTARS/DBW 2003–08)** | BENCHMARK | V-search | No files | Delta only | Egeria 93 %/73 % (51 ha sites), 29 %/65 % Delta-wide | Accuracy figures only |
| 20 | **Sonar (BioBase-style, consumer side/down imaging)** | OBSERVE (deep SAV) | U (not researched in depth) | Commercial/crowd | None today | Biovolume, canopy height | Only way to see deep SAV; no Sector pipeline |

## 4. Class mapping used across sources

| Sector class | Cowardin / NWI | NLA field | FWC species examples | NLCD |
|---|---|---|---|---|
| SUBMERGED | L2AB3, PAB3 (rooted vascular) | AM_SUBMERGENT | hydrilla, coontail, naiad, bladderwort, eelgrass | — |
| FLOATING (leaved + mats) | PAB4 (floating vascular) | AM_FLOATING | lily, spatterdock, hyacinth, lettuce, duckweed | — |
| EMERGENT | PEM | AM_EMERGENT | cattail, bulrush, pickerelweed, maidencane | 95 |
| FLOODED_TERRESTRIAL | PFO, PSS, flooded PEM | — | willow, buttonbush, cypress | 90 |

## 5. Gaps that block production
1. No dated survey polygons for the large TVA / Texas / Corps reservoirs at the core of bowfishing — only reports or requests.
2. No open Sentinel-2-labelled aquatic vegetation validation set for US lakes was found.
3. NLA 2012/2022 and the UMRS 2020 schema not yet pulled.
4. Minnesota repository needs a browser download.
