# 02 - Remote sensing literature review for a "Vegetation Brain"

Scope: scalable remote sensing of aquatic vegetation for 621 US lakes/reservoirs (bowfishing). Research only.
Date: 2026-10-13.

## Provenance legend (read this first)

Evidence tiers used throughout:
- **[V]** = seen in a web search result this session (snippet-level; I did NOT open full PDFs, so tables/quotes are from search summaries).
- **[B]** = background knowledge (physics, textbook, or papers I recall) NOT re-verified this session. Treat as plausible, cite-check before relying on it.
- **[U]** = unverified / extrapolation / my judgment.

Honest limits: web search returned snippet-level summaries; many searched items did not yield a number. Where a number is missing I say so rather than invent one. Section 10 lists claims I could not verify.

---

## 1. Headline conclusions

1. **Surface-reaching vegetation (emergent, floating-leaved, floating mats) is mappable from Sentinel-2/Landsat; submerged vegetation (SAV) is the weak class everywhere.** Every multi-class study found says so: Mediterranean lake study (Tompoulidou et al. 2024, Remote Sensing 16(5):916) [V]: emergent/floating high, SAV needed special criteria. Chinese 4-lake Sentinel-2 Res-U-Net (Remote Sensing, 2024) [V]: against measured points, submerged 59%, floating-leaved 78%, emergent 91%. Landsat 4-site study incl. Taihu [V]: >80% per class except the submerged-floating association.
2. **NIR is absorbed within centimetres of water; NDVI-type indices therefore collapse for canopy even ~10-30 cm below the surface.** SAV is detected through blue/green/red (and red-edge only when the canopy is at/near the surface), i.e. it is a bottom-reflectance problem with a depth ceiling tied to water clarity, not a "greenness" problem.
3. **Detection depth for Sentinel-2 SAV is roughly 1-2 m in clear lakes and under ~0.5-1 m in turbid/CDOM-stained lakes** (see section 4 table; mostly [B]/[U] with partial [V] support: WASI-2D study on a lake with Secchi 4.2 m retrieved depth/macrophyte-sediment separation only to ~2.5 m, r=0.95, RMSE 0.56 m [V]).
4. **Cyanobacteria scums and floating plant mats both have high FAI/NIR; they need a second discriminator** (red-edge/chl-a index e.g. NDCI, phenology, persistence, shape/texture). No study I found directly validated FAI as a discriminator [V: negative finding].
5. **Sentinel-1 helps only for emergent/flooded-vegetation structure and inundation under canopy; open-water SAV is essentially invisible to SAR.** L-band (PALSAR) much better than C-band for sub-canopy water [V: 83-84% vs 61-62% correspondence, USGS coastal marsh].
6. **Cross-lake transfer of trained classifiers is poor for the aquatic-vegetation class** [V: French wetlands Sentinel-2 transfer study: 90% one direction, 84% reverse; aquatic vegetation the most difficult class]. Plan for per-lake or per-regime calibration, not a single global model.
7. **For Sector (broad class + density + seasonality, not species),** a practical design is: use satellite time-series for the surface-reaching classes and for "likely SAV zones," and treat deep submerged SAV as inferred (depth x clarity x substrate x regional species/phenology priors) with a confidence flag, supplemented by sonar/state survey data where they exist.

---

## 2. Sensors and what each can see

### 2.1 Sentinel-2 (MSI)
- 10 m: B2 (490), B3 (560), B4 (665), B8 (842). 20 m: B5/B6/B7 red-edge (705/740/783), B8A (865), B11/B12 SWIR (1610/2190). 5-day revisit with 2 satellites (Europe/US ~ 2-5 d at mid-latitudes) [B].
- Strengths: blue+green bands for shallow bottom signal, red-edge for surface canopy and chl discrimination, 10 m good for lakes >~10 ha.
- Weaknesses: radiometric resolution adequate but SNR over dark water low; atmospheric correction over inland water is uncertain (section 8).

### 2.2 Landsat 8/9 (OLI/OLI-2)
- 30 m, 16-day each, 8-day combined; 12-bit radiometry (better dark-water SNR than TM/ETM+); has coastal blue B1 (443) [B]. Long archive (1984+ TM) enables historic presence/persistence.
- HLS (Harmonized Landsat Sentinel-2, NASA, 30 m, ~2-3 day combined) [B]: good for dense time series; surface reflectance via LaSRC/Fmask. Public domain data.

### 2.3 Sentinel-1 / SAR - section 5.
### 2.4 NAIP / aerial / commercial - section 6.

---

## 3. Spectral physics and indices

### 3.1 Water absorption by wavelength (key physics) [B]
Pure-water absorption coefficient a_w (m^-1), approx: 490 nm ~0.015; 560 ~0.07; 665 ~0.43; 705 ~0.8; 740 ~2.7; 842 ~4.2 (varies by source, 4-5); 1610 ~ 600+; 2190 ~ 2000+.
Consequence: e-folding depth for the two-way path is roughly 1/(2a) at NIR: 842 nm ~ 10-15 cm; 740 ~ 20 cm; 705 ~ 60 cm; 665 ~ 1 m (pure water; much less in real water); 560 / 490 several metres in clear water but limited by CDOM, algae and sediment. SWIR is absorbed in the top mm-cm, so SWIR sees only vegetation at/above the surface (a standard emergent vs submerged discriminator).
So: **NIR/SWIR/red-edge detect only surface-reaching or emergent canopy; blue/green/red carry the submerged signal.** I did not find a single newly cited paper this session giving these numbers (tagged [B]; standard values from Pope & Fry 1997 / Palmer & Williams 1974 style tables - verify before citing).

What happens to NDVI under water [B]: a submerged canopy at depth z has NIR reflectance attenuated by exp(-2 K_NIR z). With K_NIR ~ 3-4 m^-1 even 10-20 cm submergence cuts NIR signal by ~50-80% and a canopy just below the surface can show NDVI near or below zero (NDVI is negative or ~0 over most open water). Shallow-submerged macrophytes in very clear shallow water can show weakly positive NDVI; this is the basis of "NDVI works for SAV in the Mediterranean" papers only when the canopy is at the surface (e.g., topped-out hydrilla/milfoil mats). [U: threshold values; treat as lake-specific]

### 3.2 Index catalogue

| Index | Formula / basis | Targets | Underwater? | Evidence |
|---|---|---|---|---|
| NDVI | (NIR-R)/(NIR+R) | emergent, floating, topped-out canopies | No (surface only) | [B] |
| NDAVI | Villa et al. 2014: (NIR-Blue)/(NIR+Blue) | aquatic veg, low density | surface/near-surface only | [V] Villa, Bresciani, Braga 2014 IEEE JSTARS: compared VIs on Garda, Mantua lakes, Venice Lagoon; NDAVI and WAVI best in most cases. Villa & Bresciani 2014 (Int J Appl Earth Obs Geoinf): NDAVI better at low density (LAI<0.7-1.0, FC<40-50%), WAVI better at medium-high density (LAI>1, FC>50%). Exact formula text was garbled in snippets - verify |
| WAVI | Water-adjusted VI, (1+L)(NIR-Blue)/(NIR+Blue+L), L~0.5 | denser aquatic canopy | surface only | [V] same papers |
| SAVI / EVI | soil/atmosphere adjusted | emergent over wet soil | surface only | [B] |
| FAI | Hu 2009 (Remote Sens Environ 113): NIR minus baseline interpolated between red and SWIR | floating algae / floating plants | surface only | [V] origin + formula; Lake Xingyun FAI threshold 0.0693 (Rayleigh-corrected) [V]; Lake Burdur FAI/RF >99% for water vs floating algae two-class [V]. Thresholds are site/scene-specific |
| FLH / MPH | Fluorescence line height / Maximum Peak Height (Matthews 2012) | chl-a, blooms, surface scums | surface (MPH can flag floating veg too) | [V] Sentinel Hub custom scripts reference; MPH is for blooms [B] |
| NDWI (McFeeters) / MNDWI (Xu) | (G-NIR)/(G+NIR); (G-SWIR)/(G+SWIR) | water mask; low value flags vegetation | n/a (masking) | [B] |
| NDCI | (B5-B4)/(B5+B4) | cyanobacteria chl-a | surface | [V] Sentinel Hub script cited |
| Red-edge indices (B5-B7, NDRE, B6/B5) | | surface canopy, chl vs plant separation | surface only | [B] |
| Lyzenga depth-invariant index | ln(Ri) - (ki/kj) ln(Rj), bands green/blue or green/red | bottom type independent of depth | yes, within optical depth | [B] Lyzenga 1978/1981; needs deep-water radiance subtraction and ki/kj calibration over uniform bottom; degraded by variable turbidity |
| Bottom-reflectance inversion (WASI-2D, semi-analytic, Lee et al. 1998/1999) | physics-based | depth + bottom albedo -> macrophyte vs sediment | yes, to limited depth | [V] WASI-2D Sentinel-2A lake (Secchi 4.2 m): reliable to ~2.5 m, deeper unreliable |
| Rrs-based classification (RF/SVM on band set) | | all classes | by band set | [V] many; see section 7 |
| Spectral unmixing (LSMA) | endmembers: water, SAV, floating, emergent | sub-pixel fraction (density) | partially | [V] Villa & Bresciani used LSMA simulation for fraction cover thresholds |
| "Normalized difference submerged vegetation"-type | I could not confirm a standard named index | | | [V] Chinese study proposed a Sentinel-1/2 fusion index for submerged vegetation, 87.65% average accuracy across 3 lakes - but covers several classes plus algal bloom, not SAV-only |

### 3.3 Species separability (matters for "hydrilla vs milfoil")
- Hyperspectral (350-1000 nm, 651 bands) separates Eurasian watermilfoil from other SAV; **six multispectral bands or eight wetland-centric bands did NOT reliably differentiate EWM from other SAV** (Michigan Tech/ SPIE J. Applied Remote Sensing 13(3):037501, 2019 and related IAGLR abstract) [V]. Implication: do not promise species-level SAV from Sentinel-2/Landsat.
- Drone 6-band multispectral, Lake Huron (Les Cheneaux): EWM OA 76.7%, PA 78.7%, UA 77.6% (2022) [V]. A useful ceiling for multispectral species work even at cm resolution.
- Genus-level floating invasives with Sentinel-2 (MDPI Remote Sensing 2024, "Genus-Level Mapping of Invasive Floating Aquatic Vegetation Using Sentinel-2") exists [V: title only; no numbers].
- Water hyacinth/water primrose Sentinel-2 RF (Ade et al. 2022): average OA 90%, class accuracy 79-91% hyacinth, 85-95% primrose [V; study area not confirmed from snippet].
- Hydrilla Florida: a 2025 Remote Sensing paper (17(11):1894) introduces a Sentinel-2 index for hydrilla in shallow Florida lakes [V]; accuracy numbers not seen - **open this paper next** for Florida-specific thresholds.

---

## 4. Detectable depth vs water clarity (rule of thumb)

Evidence base is thin on the exact Secchi ratio. What I verified [V]:
- WASI-2D, Secchi 4.2 m lake, Sentinel-2A: depth retrieval good to ~2.5 m (r=0.95, RMSE 0.56 m), beyond that macrophyte/sediment separation fails (Kuhwald & Schubert 2022 area / Remote Sensing 2016 8(11):941 lineage; I did not confirm which paper holds which number).
- Baltic seagrass (Sentinel-2): turbid conditions with Secchi 2 to >7 m; mapping range 0-~5 m [V].
- Satellite-derived bathymetry (SDB) general: reliable to ~2-2.5 Secchi depths in clear water [B]. Bottom-visibility physics: bottom signal ~ exp(-2 Kd z); practical detection limit ~ z_max ~ 1.5-2.5/Kd(PAR-green) for bright bottoms and ~1/Kd for dark vegetation over dark sediments [B/U]. Secchi ~ 1.7/Kd so z_max roughly 1-1.5 Secchi for low-contrast SAV, up to ~2 Secchi for bright sand contrast [U].

### Rule-of-thumb table (Sentinel-2, growing season, calm water, good atmospheric correction) [U/B - treat as planning prior, not result]

| Secchi (m) | Water depth to bottom | Canopy-forming SAV (reaches within ~0.5 m of surface) | Low-growing SAV (<0.5 m tall) over sediment |
|---|---|---|---|
| >3 (clear) | 0-1.5 m | Good (OA ~80-90%) | Fair-good |
| >3 | 1.5-3 m | Fair (partly visible) | Poor-fair |
| >3 | >3 m | Poor unless topped out | Not detectable |
| 1-3 (moderate) | 0-1 m | Fair-good | Fair |
| 1-3 | 1-2 m | Fair if topped out; else poor | Poor |
| 1-3 | >2 m | Poor / only topped-out | Not detectable |
| <1 (turbid/algal/CDOM) | any | Only surface-reaching canopy detectable | Not detectable |

Fixed: canopy-forming species (hydrilla, EWM, coontail in some cases) reach near the surface and form a near-surface NIR-visible canopy (red-edge/NIR can see them during topped-out stage). Low-growing (chara/stonewort, vallisneria, naiad) are bottom-reflectance-only and fall to the rows on the right.

### Confounders (all [B] unless marked)
- Turbidity/chlorophyll/CDOM: raise Kd, shrink detectable depth; CDOM absorbs blue so tannin lakes (southeastern blackwater) kill blue bands, leaving green/red; chl absorbs blue/red.
- Sun glint (inland less than ocean but real for 10 m with wind): use glint correction (SWIR-based, Hedley 2005) or avoid high-glint scenes.
- Wind/waves: roughen surface, add noise to dark-water pixels; whitecaps -> false floating.
- Adjacency effect: bright land/shore contaminates pixels within ~ 100-300 m (more at 10 m due to aerosol/haze); ACOLITE/iCOR have adjacency options. Many small lakes are essentially all adjacency-affected.
- Mixed pixels at 10 m: shoreline emergent bands (reeds, cattail) < 10 m wide are mixed with water; Baiyangdian paper names water level fluctuation, life-history differences and mixed pixels as the main SAV error sources [V].
- Shadows: tree/dam/cloud shadow darkens pixels -> false deep water or missing SAV; mask using DEM-based shadow or Fmask shadow.
- Bottom type: bright sand makes SAV contrast high; muck/dark sediment makes SAV hard to see; algal film (periphyton) mimics SAV.
- Water level: reservoir drawdown moves vegetation zones; Baiyangdian paper [V].

### What additional platforms add
- UAV multispectral/hyperspectral (cm-scale): species/density at pilot sites; accuracy 62-99% depending on class granularity (UAS OBIA: 93-99% water-vs-veg, 62-90% growth-form) [V]; limited area. Good for validation of satellite models.
- Sonar (consumer Humminbird/Lowrance/Garmin side/down imaging; BioBase/Navico-based services): detects SAV height above bottom and biovolume in water the satellite cannot see (depth 1-20 m+), the only way to see deep SAV. BioBase accuracy and cost numbers **not verified** this session [U]. Crowd-sourced sonar logs are a plausible scalable data source for Sector (user contribution) - research needed, no number.
- State agency point-intercept/rake surveys (Wisconsin DNR, Minnesota DNR, Florida FWC/UF-IFAS, Texas TPWD, TVA for Guntersville) provide ground truth; coverage per lake varies. I did NOT verify specific survey coverage this session.

---

## 5. SAR (Sentinel-1, ALOS PALSAR, NISAR)

- Mechanism [B]: smooth open water = specular, very low backscatter (VV < ~ -15 to -20 dB). Emergent vegetation over water = double-bounce (stem-water-sensor) -> high backscatter, strongest in HH at L-band; at C-band VV is often volume-dominated. Dense cattail/reed canopies: volume scattering dominates and can mask water signal [V: Biebrza floodplain study].
- C-band Sentinel-1 (10 m, 6-12 d, dual pol VV/VH) [B]: reliable open-water mask, good for emergent/flooded vegetation structure and seasonal inundation; poor canopy penetration in dense forest. Some flooded-vegetation detection uses combined S1+S2 (Swedish GEE K-means study) [V].
- L-band (ALOS-2 PALSAR-2; ALOS-1 PALSAR; NISAR launched 2025 - 12 d, L+S bands, data open; **launch/operational status not verified this session**) [U]: better penetration. USGS coastal marsh: PALSAR 83% correspondence vs C-band ASAR <=61%; later averages 84% (n=160) vs 62% (n=245) [V]. PALSAR-2 ScanSAR basin scale OA 86% [V]. L-band InSAR (Atrato, Colombia): ~70% pairwise agreement, 84% detections align with inventories [V].
- Where SAR fails: **open-water submerged and floating-leaved vegetation are essentially invisible** (water surface dominates; floating mats sometimes raise backscatter via roughness but unreliable); wind-roughened water can resemble vegetation; tall dense reeds mask water [B/V].
- SAR role for Sector: flooded-terrestrial class (flooded timber, buckbrush, flooded grass), shoreline emergent belt, seasonal inundation extent in reservoirs (drawdown/pool-raise), cloud-independent.
- JRC/GSW-style water occurrence + S1 water frequency can define the "flooded-terrestrial candidate" zone (area that is water only part of the year) [U/B].

---

## 6. High-resolution optical: NAIP, state ortho, Planet, commercial

- NAIP [B]: 1 m (0.6 m in some states), 4-band (R,G,B,NIR), leaf-on, every 2-3 yr (3-year cycle in many states; some annual), public domain, delivered via USDA/EE/GEE. Sentinel Hub style access: GEE `USDA/NAIP/DOP`. Typically leaf-on summer flights (acquired near peak canopy) - good timing for floating/emergent and shallow clear SAV. Limits: single date per cycle, variable sun angle/glint/water level, no radiometric calibration across tiles, 4-year-old imagery by the time of use.
- I found **no study validating NAIP specifically for aquatic vegetation** in this session's search [V: negative]. Analogues: QuickBird northern Indiana lakes - OA 68% (2007) and 58% (2008) for emergent/submerged detail split, 75%/74% when grouped; submerged hardest; overhanging trees and shoreline vegetation cause error [V]. IKONOS (4 m) Minnesota wetlands could distinguish groups of aquatic plants [V].
- Planet (PlanetScope 3-5 m daily, SuperDove 8 bands incl. red-edge/coastal blue; Planet Basemaps) [B]: pros: near-daily, 3 m resolves narrow reed belts, many lake studies show improved emergent/floating mapping vs S2; cons: commercial licence (redistribution restricted; research/education programs exist), radiometric consistency between satellites weaker than S2/Landsat, no SWIR. I did not verify accuracy numbers this session.
- Commercial sub-meter (Maxar, Airbus Pleiades) [B]: best for SAV in <~1 m clear water; costly, archive licensing; not scalable to 621 lakes unless limited tasking.
- State orthos: vary by year/state, often higher resolution (15-30 cm), rarely multi-date; useful as labelling source and historic baseline [B].
- Historic imagery (Google Earth, USGS EarthExplorer) useful for labels only.

---

## 7. Existing global/regional products

| Product | Res | Content relevant | Licence | Notes |
|---|---|---|---|---|
| JRC Global Surface Water v1.4 (Pekel et al. 2016, Nature 540:418) | 30 m, 1984-2021 | occurrence, seasonality, recurrence, transitions, max extent, yearly history | Copernicus programme, free with attribution "EC JRC/Google" [V] | GEE: JRC/GSW1_4/GlobalSurfaceWater; older versions deprecated [V]. Seasonality = months/yr with water. Good for drawdown zones/flooded-terrestrial candidates. Vegetation covered water may be classed as non-water (misses dense mats) [B] |
| Dynamic World v1 | 10 m, NRT, 2015-06-27+ | 9 classes incl. water, trees, grass, flooded_vegetation, crops, shrub | CC-BY 4.0 [V] | `flooded_vegetation` class is noisy; per-pixel probabilities usable as features, accuracy for aquatic veg low [B/U] |
| ESA WorldCover 2020/2021 | 10 m | tree cover, shrub, grassland, wetland (herbaceous), water | CC-BY 4.0; commercial promotion needs acknowledgement/approval; one STAC record lists "other" [V] | single-year, no SAV |
| GWL_FCS30 (Zhang et al., ESSD 15:265, 2023) | 30 m | inland wetlands: permanent water, swamp, marsh, flooded flat, saline; coastal | paper CC-BY; dataset licence on Zenodo (10.5281/zenodo.7340516) **not confirmed** [V] | GWL_FCS30D annual 2000-2022, 8 subcategories [V] |
| NLCD (USGS MRLC) incl. Emergent Herbaceous Wetlands, Woody Wetlands, Open Water; Aquatic Bed not in NLCD (Aquatic Bed is C-CAP/NWI) | 30 m | | public domain [B] | NLCD does not have an "aquatic bed" class (I believe; verify) - C-CAP has Aquatic Bed [B/U] |
| NOAA C-CAP | 30 m | Palustrine/Estuarine aquatic bed, emergent, forested wetlands | public domain [B] | coastal US focus |
| USFWS National Wetlands Inventory (NWI) | vector | Palustrine Aquatic Bed (PAB), Unconsolidated Bottom, Emergent (PEM), Forested (PFO) | public domain [B] | static, often 1980s-2010s; excellent prior for class presence |
| USGS NAS (Nonindigenous Aquatic Species DB) | points | species occurrences (hydrilla, EWM, hyacinth) | public [B] | occurrence prior |
| Global Mangrove Watch | | mangrove only | n/a to inland | not relevant |
| "Global floating algae/aquatic vegetation" datasets | | e.g. Sargassum/ ocean; inland aquatic-vegetation global dataset of macrophytes - I could not confirm a validated global inland SAV product | | gap: no authoritative global SAV map exists [U] |
| Landsat Collection 2 Level-2 / ARD, HLS (NASA) | 30 m | surface reflectance | public domain [B] | HLS S30/L30 on GEE and LP DAAC |
| Sentinel-2 L2A (Copernicus) | 10-60 m | Sen2Cor SR | free & open [B] | GEE: COPERNICUS/S2_SR_HARMONIZED |

---

## 8. Machine learning, transfer, gap filling

- Classical RF/SVM/DT on S2 bands + indices: widely used. Chinese 4-lake (Taihu, Caohai, Honghu, Dongting; ~930 samples) Sentinel-2 comparison: Res-U-Net OA 90% vs decision tree 79% vs RF 78% against visual-interpretation labels; against measured points submerged 59%, floating-leaved 78%, emergent 91% (Remote Sensing 2024) [V].
- Landsat ensemble across 4 sites inc. Taihu: OA 90.1%, kappa 0.865; Taihu alone OA 82.8%, kappa 0.762 [V].
- MODIS Taihu 2-step: OA 86%, UA submerged 88%, emergent/floating 79%, cyano scum 85%, water 93% [V] (coarse sensor, merged classes).
- Dniester wetland floating vegetation RF F1 0.88 +/- 0.03 [V].
- Baiyangdian (China): time-series Sentinel-2 SAV extraction improved with phenology and water-level control [V; accuracy not seen].
- Rawa Pening (Indonesia) water hyacinth: S1+S2 features, CNN > RF [V].
- Transfer: French wetlands S2 multitemporal: OA up to 90% (train A, test B) vs 84% (reverse); aquatic vegetation most difficult, InceptionTime/XGBoost most transferable [V]. Tompoulidou 2024 hierarchical OBIA transferred to a similar second lake (numbers not seen) [V]. Seychelles seagrass: transferable but generalisation varied with substrate/water column/tide/species [V]. **Practical expectation: 5-15 pt OA drop for surface-reaching classes, larger for SAV [U, extrapolated from the above].**
- Training data needs [U]: >=~100-300 labelled pixels per class per region; polygons from NAIP/state ortho photo interpretation + state surveys are the scalable label source.
- Cloud gap handling [B]: per-season percentile composites (median, 90th-percentile NDVI/FAI/red-edge "maximum-biomass" composite), harmonic regression of NDVI/FAI/NDAVI for seasonality, best-available-pixel (BAP) compositing, HLS for density; use SAR to fill cloud gaps for emergent/flooded.
- Seasonality: derive months with peak canopy (surface-reaching veg) and persistence (frequency of detection) per pixel; JRC seasonality gives water seasonality.

---

## 9. Practical gotchas

- Cloud/ice: Sentinel-2 SCL/s2cloudless; Landsat QA_PIXEL; ice-on lakes (northern states) give false "floating" signal; mask by winter months or NDSI/MNDWI.
- Atmospheric correction over inland water [V: Warren et al. 2019, Remote Sens Environ; 13 inland waterbodies + 2 coastal, 6 processors ACOLITE, C2RCC, iCOR, l2gen, Polymer, Sen2Cor]: all had high uncertainty, often >100% error in red and >1000% in NIR; Polymer and C2RCC lowest RMSD (~0.0016 sr^-1), MAD ~40-60% in blue/green. Pereira-Sandoval et al. 2019 (Spanish lakes): Polymer and C2RCC best, R2>0.83, MAE<0.01. Tibetan Plateau (Remote Sensing 2023): best processor depends on water type (Sen2Cor best in turbid Dabusun; Polymer in clear Qinghai; C2XC in a reservoir). Implication: use the standard L2A for surface-reaching classes (NIR large signal over vegetation) but expect poor Rrs over open water; for SAV bottom reflectance, ACOLITE/Polymer/C2RCC and per-lake validation, or use top-of-atmosphere (L1C) with relative/within-scene normalisation. Sen2Cor is often poor over dark water [B].
- Algal bloom vs vascular plants: both have high FAI/NIR; separators: (a) red-edge peak position and NDCI vs NDVI behavior, (b) persistence and spatial stability (mats persist for weeks; blooms drift), (c) morphology (blooms with wind streaks), (d) phenology (bloom season/water temp), (e) water quality context (chl-a). No validated discriminator found [V: negative].
- Glint/wave white-caps; shadows; hot adjacency; low sun angles at high latitude/winter.
- 10 m mixed shoreline pixels; classify at lake-level fractions (area-weighted) instead of per-pixel hard labels.
- Water-level change: use same-season composites; reservoirs with drawdown will show terrestrial veg on exposed lakebed (not "aquatic").

---

## 10. Quantified "what can be detected how well" table

Numbers are what the literature reports (tagged) or my planning priors (U). "Class" = broad Sector class.

| Class | Sentinel-2 (10 m) | Landsat 8/9 (30 m) | Sentinel-1 | NAIP/high-res optical | UAV/sonar |
|---|---|---|---|---|---|
| Submerged-deep (>~2 m, Secchi <3 m) | Not detectable (<10% reliable). Only topped-out canopy | Not detectable | Not detectable | Not detectable | Sonar only: reliable; UAV no |
| Submerged-shallow-clear (<1.5-2 m, Secchi >2-3 m) | Moderate: 59% (point-validated, 4 Chinese lakes) [V]; planning range 60-85% [U] with canopy-forming > low | Moderate-low: Taihu Landsat OA 82.8% over all classes with submerged-floating association weak [V]; ~50-75% [U] | Not detectable | Best optical option; QuickBird submerged hardest, OA 58-68% for emergent/submerged split [V]; UAV species 77% (EWM) [V] | UAV multispectral: 62-99% by granularity [V]; sonar reliable |
| Floating-leaved (lotus, lily, water-shield) | ~78% (point-validated) [V]; S2 genus-level floating invasives exist [V] | ~70-85% [U] | Weak (seasonal roughness only) [B] | Good (1 m) | UAV good |
| Floating mats (hyacinth, salvinia, duckweed, hydrilla topped-out) | Good: RF 79-91% (hyacinth), 85-95% (primrose), OA ~90% [V]; F1 0.88 [V]; FAI/threshold methods >99% two-class [V Burdur - algae though] | Good at coarse scale but 30 m underresolves narrow mats [U] | Weak-moderate; fusion helps [V Rawa Pening] | Good | UAV good |
| Emergent (cattail, phragmites, bulrush) | ~91% (point-validated) [V]; best class everywhere | ~85-90% [U] | Good: structure & double-bounce [V/B] | Good (but confusion with shoreline trees) [V] | UAV good |
| Flooded-terrestrial (flooded timber/shrub/grass) | Poor-moderate from optical alone (canopy hides water); Dongting: adding flood index improved accuracy [V] | Poor-moderate | C-band moderate; L-band 83-86% [V] | Poor | UAV LiDAR/thermal [B]; sonar n/a |

Density (none/scattered/moderate/dense): from index-fraction thresholds. Villa & Bresciani [V]: NDAVI discriminates AV vs terrestrial for FC<40-50% (LAI<0.7-1); WAVI above (LAI>1, FC>50%). Practical density classes: sub-pixel fraction via LSMA or FAI/NDAVI quantile bins; expect +-1 class error [U].

---

## 11. Recommended minimal feature set (for a first Vegetation Brain on 621 lakes)

Per lake, per month (growing-season composites; 90th-percentile and median):
1. Water mask: JRC GSW occurrence/seasonality (30 m) + Sentinel-2 MNDWI; S1 VV water frequency.
2. Surface-reaching vegetation (emergent/floating/mats): Sentinel-2 L2A NDVI, NDAVI (B8,B2), FAI (B4,B8,B11), red-edge ratio (B6/B5) and NDCI (B5,B4), B11 (SWIR) to separate emergent from submerged.
3. SAV candidate: green/blue and green/red Lyzenga depth-invariant, depth proxy (bathymetry / DEM / reservoir contours / state depth maps) and clarity proxy (Secchi from state data, chl-a index, Kd from S2/Landsat time series). Output = "SAV-capable zone" and "visible-SAV confidence" rather than hard SAV maps.
4. Flooded-terrestrial: Sentinel-1 VV/VH time series (+ difference to dry baseline), water seasonality (JRC), NWI PFO/PSS classes.
5. Context priors: NWI polygons, USGS NAS species, state DNR vegetation surveys, NLCD/WorldCover shoreline, NAIP-derived 1 m emergent/floating polygons (every 2-3 yr).
6. Temporal: peak-month (harmonic regression or max-composite month), persistence (fraction of years detected), cloud-free count for confidence.
7. Quality flags: % cloudy/ice, glint, adjacency/small-lake flag (<~50 ha), turbidity class, bloom-vs-vegetation ambiguity flag.
8. Output convention: classes + density + confidence + "evidence source" (satellite / NWI / survey / sonar). Do not output species from satellite.

---

## 12. Claims I could not verify (do not cite as facts)

1. All water-absorption values and penetration depths in 3.1 are from memory (standard Pope-Fry tables); not re-verified.
2. The Secchi x depth rule-of-thumb table (section 4) is a planning prior built from the WASI-2D (2.5 m at Secchi 4.2 m) data point and general SDB physics; no paper this session confirmed "1-2 Secchi depths" for SAV with S2/Landsat.
3. The Lake Okeechobee, Lake Guntersville, Florida, Great Lakes/Lake Erie, Wisconsin/Minnesota satellite SAV accuracy figures: searches returned no usable Sentinel-2/Landsat papers; nothing cited.
4. Hydrilla Sentinel-2 index (Remote Sensing 2025, 17(11):1894): title/existence seen, accuracy numbers not.
5. Poyang, Lake Balaton, Garda macrophyte accuracy: not found (Garda only via Villa NDAVI/WAVI comparison, no numbers).
6. NAIP for aquatic vegetation: no validating paper found; NAIP specs (1 m, 4-band, 2-3 yr) are from memory.
7. NISAR operational status and data licence; ALOS-2 availability.
8. NLCD "aquatic bed" class: I believe NLCD lacks it; C-CAP has it; unverified.
9. GWL_FCS30 dataset-level licence (paper CC-BY; Zenodo licence not checked); WorldCover STAC record discrepancy noted.
10. BioBase/Navico/Humminbird accuracy and API access: not searched/verified.
11. Planet pros/cons and licence terms: from memory.
12. The exact NDAVI formula (snippet garbled): commonly (NIR-Blue)/(NIR+Blue) but confirm in Villa et al. 2014.
13. FAI as a cyanobacteria vs macrophyte discriminator: no validating study found; the suggested discriminators are my judgment.
14. Transfer accuracy drop (5-15 pts): my extrapolation from the French wetland (90 vs 84%) result and general experience.
15. Chinese fusion index (87.65%) accuracy: seen only as an average across lakes/classes.

## 13. Sources (as returned by search; check before citing)

- Villa, Bresciani, Braga et al. 2014, IEEE JSTARS (NDAVI/WAVI comparison); Villa & Bresciani 2014, Int J Appl Earth Obs Geoinf (LAI/FC thresholds). Found via CNR IRIS listings (iris.cnr.it).
- Hu 2009, Remote Sensing of Environment, Floating Algae Index; Lake Xingyun and Lake Burdur FAI studies (via search; MDPI RS 13(21):4479 and RS 15(8):2039 per crossref hits).
- Warren et al. 2019, Remote Sens Environ, AC comparison (plymsea.ac.uk/id/eprint/8168); Pereira-Sandoval et al. 2019, Remote Sensing.
- Tompoulidou et al. 2024, Remote Sensing 16(5):916 (api.crossref.org/works/10.3390/RS16050916).
- Chinese Res-U-Net 4-lake Sentinel-2 aquatic vegetation, Remote Sensing Feb 2024 (doaj.org/article/b4e38d994b0f4adb9ff2a4ccaa200a6e).
- Michigan Tech EWM spectral work, J. Applied Remote Sensing 13(3):037501 (2019); IAGLR 2019 abstract.
- Remote Sensing 8(11):941 (2016), Remote Sensing 8(9):724 (2016, QuickBird/aquatic vegetation), Indiana QuickBird lakes (hdl.handle.net/1805/2027).
- Pekel et al. 2016 Nature 540:418; GEE catalog JRC/GSW1_4; Dynamic World GEE catalog; ESA WorldCover; Zhang et al. 2023 ESSD 15:265 (GWL_FCS30).
- USGS coastal marsh L-band vs C-band: pubs.usgs.gov/of/2011/1208 and related USGS node; Atrato L-band InSAR PNNL listing; Biebrza floodplain S1 study.
- Digital Earth Africa FAI notebook; Sentinel Hub custom scripts (MPH, NDCI).
