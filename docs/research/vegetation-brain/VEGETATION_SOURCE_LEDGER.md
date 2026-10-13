# Vegetation Brain — Source Ledger

**RESEARCH ONLY.** Every external source consulted, its verification grade, and the claims it supports. Grades: **OPENED** (page/PDF read), **FETCHED** (API response seen), **SEARCH-EXCERPT** (search summary only), **BACKGROUND** (not checked). Raw notes: `~/Desktop/Development/Sector_Research_Data/vegetation-brain/notes/01..04*.md`. Date checked: 2026-10-13.

## A. Opened / fetched — strongest evidence

| Source | Supports |
|---|---|
| Canfield, Langeland, Linda & Haller 1985, J. Aquat. Plant Manage. 23:25-28 (apms.org/wp-content/uploads/japm-23-01-023.pdf) — OPENED | **log MDC = 0.61 log SD + 0.26**, r²=0.56, 95 % CI 46–236 % of predicted; Florida-only **log MDC = 0.42 log SD + 0.41** (r² 0.71, n=26); Finland 0.51/0.18; Wisconsin 0.79/0.25. Hydrilla colonises to depths with ~0.5–1.2 % surface light in several FL lakes. *(An earlier campaign note misattributed this equation to Chambers & Kalff — corrected.)* |
| Itaipu hydrilla vs Egeria Zmax–transparency (scielo.br/j/abb/…) — OPENED | Hydrilla Zmax slope 0.49 vs Egeria 0.24 |
| Madsen & Owens 1998, JAPM 36:138-145 — OPENED | Hydrilla north-Texas ponds: ~1000 g/m² peak July; second high Oct–Nov; winter biomass within 50 % of peak; regrowth from crowns not tubers |
| MTRI Michigan Tech EWM biology page — OPENED | EWM photosynthesis starts ~10 °C; peak shortly after June flowering; evergreen if water >10 °C |
| MN DNR curlyleaf pondweed page — OPENED | Fall turion sprouting, June flowering/turions, mid-summer dieback |
| UF/IFAS AG385 water hyacinth — OPENED | Doubling in 6–18 days; growth >50 °F; winter dieback in north FL |
| FWC plant-mapping page — OPENED | PAC and PVI definitions; **no numeric density classes** |
| SFWMD 2011 SFER App. 5-10 legend — OPENED | Cover scale none / trace 0–1 / sparse 1–10 / moderately dense 10–40 / dense 40–80 / very dense >80 % (treatment-wetland SAV; one agency's convention) |
| SFWMD Lake Okeechobee SAV page (docx) — OPENED | SAV <3,000 ac (2006) → >46,000 ac (2009) under drought/low stage; biomass classes sparse <5, moderate 5–50, dense >50 g DW/m² |
| TPWD Sam Rayburn 2022 report & lake page — OPENED | Pool fluctuates 6–7 ft/yr; hydrilla + American lotus; giant salvinia >4,000 ac (2014) |
| Webb & Chilton 2008, J. SEAFWA (Lake Conroe) — OPENED | 270,000 diploid grass carp stocked Sep 1981–Sep 1982; all vegetation gone by Oct 1983 |
| EPA NARS data portal, NLA 2017 phab/site CSVs — FETCHED, downloaded | Cover codes 0–4; 12,076 station rows; 1,147 lakes; 48 states |
| FL FWC `WhatsHappeningOnMyLake` MapServer layer 33 — FETCHED, downloaded | 96,055 LTM point intercepts 2015–2023 |
| USGS UMESC SAV release (ScienceBase 64540e54d34eefd5da843ac9) — FETCHED, downloaded | vegetation_data.csv 29k rows, 1998–2019 |
| USGS NAS API v2 — FETCHED | Presence records returned (hydrilla FL) |
| USFWS NWI REST — FETCHED | Cowardin polygons near Guntersville |
| Michigan EGLE ANC layer 14 — FETCHED | 674 survey locations |
| MDC bowfishing page — OPENED | Qualitative bowfishing guidance only; no vegetation numbers |

## B. Search-excerpt only — treat as leads

| Source | Claim | Caveat |
|---|---|---|
| Chambers & Kalff 1985, CJFAS 42:701-709 | angiosperms Zc^0.5 = 1.33 log D + 1.40 | abstract page 403 — verify |
| Duarte & Kalff 1987 | colonisation depth falls with latitude | no coefficients |
| Villa et al. 2014 IEEE JSTARS; Villa & Bresciani 2014 | NDAVI/WAVI; NDAVI best FC<40–50 %, WAVI above | formula text garbled |
| Hu 2009 RSE | Floating Algae Index | thresholds scene-specific |
| Warren et al. 2019 RSE | atmospheric correction over inland water: Polymer & C2RCC best; >100 % red / >1000 % NIR errors | — |
| Chinese 4-lake Sentinel-2 Res-U-Net (Remote Sens. 2024) | point-validated: submerged 59 %, floating-leaved 78 %, emergent 91 % | labels partly visual |
| Michigan Tech J. Appl. Remote Sens. 13(3):037501 (2019) | multispectral bands can't separate EWM from other SAV; hyperspectral can | — |
| USGS OFR 2011-1208 and related | L-band 83–84 % vs C-band 61–62 % flooded marsh | coastal marsh |
| French wetlands S2 transfer study | 90 % vs 84 % across sites; aquatic vegetation hardest | wetland, not lakes |
| WASI-2D Sentinel-2A lake study | reliable to ~2.5 m at Secchi 4.2 m | one lake |
| Baiyangdian S2 phenology (Remote Sens. 14(3):640; Ecol. Indic. 2023) | phenology-based SAV extraction, OA 94.8 % | China; do not transfer timing |
| Remote Sensing 17(11):1894 (2025) | Sentinel-2 hydrilla index, Florida shallow lakes | **not read — best next read** |
| Jones 2019 NE-ANS hydrilla workshop | PAC vs PVI divergence (95.8 vs 53.5 %) | PDF unreadable |
| FWC presentations | Lake Toho managed at ~50 % hydrilla cover, >3,500 ac/yr | — |
| TVA / trade press (southernfishingnews) | Guntersville 1,494 ac treated 2025; eelgrass removal 120k→70k yd³ | secondary source |

## C. Unverified / background (do not cite as fact)
Water absorption coefficients and NIR e-folding depths; the Secchi × depth detectability table; all month-by-region cells; GDD thresholds; depth-band probabilities; seasonal-prior accuracy (65–75 % exact class); cross-lake transfer drop (5–15 pts); NAIP specifications; Planet specs; NISAR status; FAI as cyanobacteria-vs-plant discriminator; every bowfishing-vs-density effect.

## D. Dead / blocked
Not reachable on 2026-10-13: `apis.erdc.dren.mil`, `midas.aqua.wisc.edu`, `apipp.org`, `lakes.nrri.umn.edu`; 404: WA Ecology freshwater-plants path, SC DNR aquaticnuisance, GA DNR ANS, TPWD vegetation habitat path, NCWRC plants, Vermont AIS, Outdoor Alabama plants, MRLC NLCD deep links, UMESC land-cover page; 403 to curl (try browser): tva.com, NH DES, EDDMapS (works with UA), USGS Lake Erie vegetation page; WAF: conservancy.umn.edu, gisdata.mn.gov; 503: NAS IPT bulk.

## E. Local datasets (outside Git; hashes in `MANIFEST.jsonl`)
`sources/fwc_ltm_point_intercepts/`, `sources/nla_2017_phab/` (3 files), `sources/usgs_sav_upper_miss_rf/`, `sources/globathy_fleet_match_from_depth_research.csv` (copied from the Depth research branch; modelled shallow fractions), plus experiment caches in `experiments/`. Lake polygons: `Sector_Research_Data/lake-brain/geometry/engine_polygons_599.geojson.gz` (read-only).
