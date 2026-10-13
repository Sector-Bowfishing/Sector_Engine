# Vegetation Brain - Note 03: Seasonal Phenology, Lake Level / Depth, Bowfishing Accessibility

Status: desk research. Web search budget was small (7 searches); most phenology and depth values below come from
well-established limnology/aquatic-plant-management literature recalled from training and are labelled
**[V]** verified this session via a fetched/searched source, **[L]** literature-based but not re-verified this session
(citation is real to my knowledge; numbers approximate), **[E]** expert-judgment estimate / modeling assumption (no source),
**[A]** anecdotal. Section 6 lists everything that should be checked before it goes into product logic.

---

## 0. Executive summary

1. A seasonal prior is feasible and useful as a *fallback* when imagery is cloudy, but it predicts **state class** (none/scattered/moderate/dense) only roughly: expect about 60-70% exact-class agreement and about 90% within one class for a typical week in unmanaged southern/midwestern reservoirs **[E]**. It is much worse (near coin-flip) in lakes with active herbicide/grass-carp management, hurricane or drought disturbance, or major pool changes. The prior must carry a per-lake "regime" flag and a confidence value, and must be overridden by any clear observation less than ~3 weeks old.
2. Best predictors: (a) water-temperature degree-days (or air-temp proxy) for timing, (b) latitude/region for the amplitude of the seasonal cycle, (c) species-group mix per lake (hydrilla vs curlyleaf vs emergent/lotus), (d) management history, (e) pool-level anomaly.
3. Pool level is the biggest short-term non-seasonal driver: a few feet change moves which depth band is shallow enough to host SAV, floods or strands shoreline grass, and strands emergent stands. A depth-band x clarity table (Section 4) is a defensible first-order SAV-presence model via Zmax ~ f(Secchi).
4. Agency PAC/PVI-style metrics map cleanly to four Sector classes, but must be applied to *bowfishing-relevant* water (<= ~6 ft) rather than whole-lake, because whole-lake PAC is diluted by deep open water (Section 5).

---

## 1. Drivers (what controls timing and amount)

| Driver | Effect | Confidence |
|---|---|---|
| Water temperature / degree-days | Sprouting thresholds: hydrilla tuber sprouting begins roughly 10-15 C, strong growth > 20 C, optimum ~ 25-32 C; Eurasian watermilfoil (EWM) grows at low temp, peaks ~ 20-30 C, starts apical elongation at ~ 10-15 C; curlyleaf pondweed (CLP) turions germinate in autumn at < ~15 C, overwinter under ice as small plants, grows in spring, peaks late May-June, senesces/turions by early July when water > ~ 20-25 C [L] (Woolf & Madsen 2003 J Aquat Plant Manage 41:113-118 on CLP; Barko & Smart 1981 on temperature/light for hydrilla/milfoil; Madsen & Owens on hydrilla) | [L] |
| Photoperiod | Hydrilla tuber formation triggered by short days (< ~ 13 h) -> autumn tuber set; monoecious hydrilla (Carolinas, Mid-Atlantic, Pacific NW) differs from dioecious (Gulf/Southeast) | [L] (Van, Haller & Bowes 1976; Spencer & Anderson; Netherland 1997 review) |
| Light | Canopy self-shading; water clarity sets depth limit (Section 4); spring phytoplankton blooms and turbidity pulses delay green-up | [L] |
| Nutrients | Increase biomass of floaters (water hyacinth, duckweed, salvinia) and phytoplankton competition; SAV less nutrient-limited when sediments rich | [L] |
| Herbicide management | Large step-changes: FWC (fluridone, endothall, diquat, flumioxazin), TVA, Corps contract spraying; spring treatments cut green-up, late-summer treatments produce abrupt "brown-out"; TVA 2025: treated ~555 acres system-wide and harvested 200+ acres boat lanes; Guntersville 1,494 acres treated and 70,000 yd3 eelgrass removed in 2025 **[V]** (southernfishingnews.com "Removing Eelgrass Aquatic Invasive Weed: It Takes a Team") | [V]/[L] |
| Grass carp | Triploid grass carp (TX stocking legal since 1992 per TPWD; stocking ~ 7 fish/acre typical **[V]** via bc4weeds.tamu.edu/grasscarp summary) can eliminate SAV whole-lake within 1-3 years if overstocked; recovery takes years after stocked fish die (lifespan 10-20 y) | [V]/[L] |
| Hurricanes / floods | Uproot and fragment SAV, increase turbidity (light loss -> shallow collapse), flood emergent and push floating mats; Gulf lakes: Okeechobee SAV collapsed after 2004-05 hurricanes (Havens et al. 2004; Rodusky et al. 2005 [L]) | [L] |
| Ice cover | Ice-on halts growth; under-ice low light means winter-annual CLP survives; ice scour and winter drawdown strip shorelines | [L] |
| Hydrology (drought/flood years) | Rising pool floods terrestrial grass and gives a new SAV flush 1-2 seasons later; sustained high water in turbid reservoirs reduces light -> SAV declines (Section 4) | [L] |

Degree-day sketch: use growing degree-days above 10 C (GDD10) on water surface temperature (or air-temp-derived, lagged, smoothed) accumulated from Jan 1 (or from the autumn minimum). Rough guideposts **[E]** derived from the sprouting/peak literature above:

- GDD10 < 100: dormant / winter state.
- 100-400: green-up onset (sparse).
- 400-1200: rapid growth.
- 1200-2200: topped out / peak biomass for warm-water SAV.
- Autumn: senescence begins with falling GDD or surface temp < ~ 15-18 C; photoperiod < 12 h.

---

## 2. Species-group phenology

Generic temperate/Southeast timing. Shift by region per Section 3.

| Group | Green-up | Growth rate | Peak biomass | Senescence | Winter | Notes / sources |
|---|---|---|---|---|---|---|
| Hydrilla (dioecious, South) | Feb-Apr from tubers/turions and overwintering stems | Up to ~ 1 inch/day, can top out (reach surface) in 6-10 wks; very fast in 22-30 C | Jun-Oct (surface mats; Jul-Sep topped out) | Oct-Dec; frost kills surface canopy in N Gulf/TN valley, may persist green in S Florida | Reduced but alive in Deep South (low-biomass year-round); tubers persist in sediment 4+ years | [L] Langeland 1996 Castanea review; Haller & Sutton 1975; Netherland 1997 J Aquat Plant Manage 35:1 |
| Hydrilla (monoecious, Mid-Atlantic/NC/PNW) | Apr-May | Fast | Aug-Sep | Oct | Dormant, dies back to tubers | [L] |
| Eurasian watermilfoil | Early spring (grows at low temp, Mar-Apr South, Apr-May North) | Moderate-fast; canopy at surface by June | Jun-Aug; two-peak in some lakes (spring + late summer) | Late autumn; much stem persists under ice | Winter-green stems/crowns in many lakes | [L] Madsen 1997; Smith & Barko 1990; Aiken et al. 1979 |
| Coontail (Ceratophyllum) | Mar-May | Moderate | Jul-Sep | Autumn; often green late | Persistent green overwinter in mild climates | Non-rooted; blooms in nutrient-rich water [L] |
| Curlyleaf pondweed | Autumn germination, ice-on growth | Fast in cold water | Late May-June (Midwest), Apr-May (South) | Mid-June to July senescence ("midsummer collapse"), turions drop | Winter annual: green under ice | [L] Woolf & Madsen 2003; Nichols & Shaw 1986; Poovey et al. 2002 |
| Elodea/Egeria | Apr-May (Egeria also winter-active in mild climates) | Moderate | Jun-Aug | Autumn | Egeria persists in CA Delta | [L] |
| Southern naiad / Najas | Apr-Jun | Moderate | Aug-Oct (annual, seed-set autumn) | Oct-Nov | Dies, overwinters as seed | [L] |
| Chara/Nitella | Spring (cooler water) | Slow-moderate | Jun-Aug | Autumn | Persists low in clear lakes | Low-growing, rarely a bowfishing barrier [L] |
| American lotus (Nelumbo) | May (leaf emergence at 18-20 C) | Rapid leaf expansion | Jul-Aug (full canopy) | Sept-Oct | Dormant tubers; leaves collapse and rot | Sam Rayburn, Caddo, Reelfoot; [L]/[A] |
| White water lily / yellow lily / spatterdock | Apr-May | Moderate | Jun-Aug | Oct | Rhizome dormant, leaves die | [L] |
| Watershield | May | Moderate | Jul-Aug | Oct | Winter buds | [L] |
| Water hyacinth | Active all-year in S Florida/Gulf coast; regrows from rhizomes after frost | Doubling time ~ 6-18 days in warm months | Jul-Oct | Frost-kill in Nov-Feb north of Gulf coast | Surface mats frost-browned, regrow from protected nodes | [L] FWC/UF-IFAS; Center 1989 |
| Water lettuce, salvinia, duckweed | Spring | Rapid | Summer-Oct | Frost | Duckweed overwinters as turions; salvinia persists in Gulf | [L] |
| Alligatorweed | Spring | Moderate | Summer | Frost-kill of tops | Roots survive | [L] |
| Cattail / bulrush / phragmites | Apr-May | Moderate-rapid | Jul-Sep (standing crop) | Oct-Nov senescence; standing dead through winter | Standing dead stems visible | Phragmites persistent tan stalks winter [L] |
| Giant cutgrass / maidencane / pickerelweed | Mar-May South | Moderate | Jul-Sep | Frost-brown | Dormant but persistent | [L] |
| Flooded buttonbush/willow, flooded terrestrial grass | Woody: leaf-out Mar-May; grass flush follows drawdown + spring rain | n/a | Standing structure year-round; leaf cover May-Oct | Leaf-off Nov | Woody structure persists | Depends entirely on pool level (Section 4) |

---

## 3. Month-by-region expected states

Cell codes for the most important *canopy-forming SAV + mats* in a typical reservoir/lake in each region (the region's dominant bowfishing-relevant group). Codes: 0 = none/dormant, S = sparse/scattered, M = moderate, D = dense/topped out, B = brown/senescent (visible but decaying), N = ice cover/n.a. All are **[E]** syntheses of the species table plus regional climate; uncertainty is quantified below.

| Region (dominant) | J | F | M | A | M | J | J | A | S | O | N | D |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Deep South / Gulf (hydrilla, hyacinth, lotus) | S | S | S-M | M | M-D | D | D | D | D | M-D | M | S |
| Southeast reservoir (hydrilla/EWM/Egeria) | 0-S | 0-S | S | S-M | M | M-D | D | D | D | M | B | S |
| Mid-South / TN valley (EWM, hydrilla, eelgrass, lotus) | 0 | 0 | S | S-M | M | M-D | D | D | D | M-B | B | 0-S |
| Midwest (CLP + EWM + coontail; cattail) | 0 | 0 | S | M (CLP) | M-D (CLP) | M (CLP crash Jul) | M (EWM/coontail) | M-D | M | S-B | S | 0 |
| Great Lakes / upper Midwest | N | N | N-0 | S | S-M | M | M-D | D | M | S-B | 0 | N |
| Northeast | N | N | 0 | S | S-M | M | M-D | D | M | B | 0 | N |
| Great Plains reservoirs | 0 | 0 | 0 | S | S-M | M | M | M | M | S | 0 | 0 (veg is mostly emergent/flooded grass; SAV limited by turbidity) |
| Mountain West (high elevation) | N | N | N | 0 | S | M | M-D | M-D | M | S | 0 | N |
| Pacific NW | 0 | 0 | S | S | M | M-D | D | D | M | S-B | 0 | 0 |
| California (Delta/Egeria/water hyacinth) | S | S | S-M | M | M | D | D | D | M-D | M | S | S |
| Southwest (desert reservoirs; low SAV, shoreline salt cedar) | 0 | 0 | S | S | S | M | M | M | S | S | 0 | 0 |
| Alaska | N | N | N | N | 0 | S | M | M | S | 0 | N | N |

### Example detailed row (user's template)
Southeast reservoir hydrilla: Jan-Feb low (0-S), Mar sparse, Apr sparse-moderate, May moderate, Jun-Sep moderate-to-topped-out dense, Oct moderate, Nov dieback/brown, Dec low.

### Emergent and floating-leaved: timing (any region with growing season)
- Emergents (cattail, bulrush, cutgrass): visible tan standing dead stems in winter; green-up in spring; maximum density Jul-Sep. In imagery, winter emergent stands can look "dormant" (NDVI low) while still physically blocking boats.
- Floating-leaved (lotus, lily): leaf cover nearly absent Dec-Apr, rapid cover Mid-May to July; full canopy Jul-Sep.
- Floating mats (hyacinth, lettuce, salvinia): Deep South year-round risk; northern limit is frost; hurricane/wind can relocate mats in one day.
- Flooded terrestrial grass: appears when pool rises after spring rains; dies/decays after 4-8 weeks submerged (E); see Section 4.

### Climatological uncertainty, quantified (all [E])
- Timing: onset +/- 3-5 weeks year to year (spring temperature anomalies); peak +/- 3-4 weeks; dieback +/- 2-4 weeks (first-frost driven).
- Amplitude (percent of lake covered at peak): coefficient of variation ~ 30-60% year to year in unmanaged reservoirs; > 100% in herbicide/grass-carp-managed lakes or after hurricane/drought.
- Climatology predicting a given week: Exact class correct ~ 60-70% (unmanaged), ~ 40-50% (managed or disturbed); within one class ~ 90% / ~ 70%. Worst weeks: shoulder periods (April-May green-up, Oct-Nov dieback) where timing error dominates.

### Year-to-year history that breaks climatology
- **Grass-carp-driven collapses**: Lake Conroe, TX (hydrilla controlled/eliminated by grass carp stocking in the late 1980s-2000s era; subsequent SAV loss -- details of dates and stocking numbers [L]/not verified); Lake Austin; Lake Fork; Sam Rayburn (hydrilla/lotus cycles with water level and herbicide; TPWD notes level fluctuations average 6-7 ft/yr **[V]** from 2022 survey report https://tpwd.texas.gov/publications/pwdpubs/lake_survey/pwd_rp_t3200_1371/index.phtml). A regional outdoor-news report claims higher water has reduced East Texas hydrilla **[A]**.
- **Guntersville**: TVA estimate ~ 17,000 acres of aquatic plants in 2014, of which TVA managed ~ 7% **[V]** (jcsentinel / southernfishingnews secondary); local claims of 23,000 acres hydrilla+milfoil [A]; 1960s peak milfoil valley-wide 77,000 acres [A, TVA official recollection]; eelgrass (new since ~ 2014) peaked 2023: 120,000 yd3 (2023) -> 90,000 (2024) -> 70,000 (2025) removal volumes **[V]** (southernfishingnews.com).
- **Okeechobee**: SAV crashes post-hurricane (2004-05) and recoveries; high-stage multi-year periods cause SAV loss [L] (Havens et al.).
- **Toledo Bend / Seminole**: hydrilla boom-bust cycles with herbicides and drought [L]; specific citations need verification (Section 6).
- **Lake Toho (FL)**: >3,500 acres managed annually to hold hydrilla near 50% cover; carrying capacity ~ 99% **[V]** (FWC / NE workshop presentation, northeastans.org Hydrilla workshop Jones 2019).

### Published phenology / time-series literature (evaluate before using)
- Remote sensing macrophyte phenology: Landsat/Sentinel-2 SAV and floating-vegetation mapping (Villa et al. 2014 Remote Sens. Environ.? [L]; Luo et al. 2016 on MODIS/Landsat lake macrophytes in China [L]; Cavalli et al. 2009 [L]); MODIS macrophyte cover in Lake Taihu (Zhao et al. [L]); Sentinel-2 hydrilla mapping and water hyacinth tracking (Sentinel-2 hyacinth in Africa/Lake Victoria; Thamaga & Dube 2018 [L]). I did NOT verify any of these this session; they should be treated as search leads.
- Hydrilla biomass time series: Langeland 1996 (Castanea); Haller et al. 1976 (growth regimes) [L]; Barko & Smart 1981; Netherland 1997; Corps APCRP technical notes (apcrp.el.erdc.dren.mil) [L]; USACE ERDC reports on Lake Gaston, Guntersville, Seminole [L].
- Northeast hydrilla surveys: Jones workshop presentation reports PAC rising from 15.9% (June 5 2018, 13 C water) to 90.7% (July 31) with biovolume 1.6% -> 41.4% **[V]** (https://northeastans.org/docs/meetings/201906/files/Hydrilla%20workshop%20Jones.pdf). Demonstrates how steeply June-July growth can be.
- FWC Lake Vegetation Mapping (since 2015, ~ 50 lakes/year, May-Oct) **[V]** https://myfwc.com/research/freshwater/monitoring/plant-mapping/.
- TVA aquatic plant management annual surveys (2025: 10,000 acres surveyed) **[V]**; Corps Aquatic Plant Information System (APIS) [L].

---

## 4. Part B - Lake level and depth interaction

### 4.1 Depth limits vs clarity
- Chambers & Kalff (1985), Can. J. Fish. Aquat. Sci. 42:701-709, "Depth distribution and biomass of submersed aquatic macrophyte communities in relation to Secchi depth" **[V]** (existence, bibliographic data confirmed via search; the paper regresses Zmax on Secchi in a large lake dataset). Commonly quoted form: log10(Zc) = 0.62 log10(SD) + 0.26 (Zc, SD in m; Zc = maximum colonization depth of submersed macrophyte) [L] -- unverified this session; check original. Canfield et al. 1985 (Florida lakes; Zmax vs Secchi, J. Aquat. Plant Manage. 23:25-28) [L]. Also Duarte & Kalff 1987, Middelboe & Markager 1997, Scheffer et al. 1992, Hudon et al. 2000 are cited as supporting the relation **[V]** (as citations in secondary text).
- Rule of thumb: SAV generally limited to ~ 1.0-2.5 x Secchi depth (lower end in tannic/turbid, upper end in clear with canopy-formers like hydrilla/Egeria, which grow with only ~ 1-5% surface light) [L]/[E]. Hydrilla can colonize to ~ 4-8 m in clear Florida spring lakes but is canopy-limited to < 3 m at Secchi 1 m [L].
- Itaipu reservoir study: Zmax of Hydrilla verticillata increased faster with transparency than that of Egeria najas **[V]** (scielo.br abb paper cited in search).
- Minimum depth (upper limit) is controlled by wave exposure/fetch, ice scour, drawdown desiccation, not by light **[V]** (secondary statement).

### 4.2 Euphotic depth sketch
Zeu ~ 2.5-3 x Secchi (rough conversion from 1% light) [E]. SAV maximum colonization is approximately the 1-10% light depth, so Zmax ~ 1.0-1.5 x Secchi for light-limited SAV in turbid water, up to ~ 2.5 x Secchi for canopy formers in clear water [E].

### 4.3 Typical maximum SAV colonization depth by clarity class

| Clarity class | Secchi | Typical Zmax (SAV) | Notes |
|---|---|---|---|
| Very clear (oligotrophic natural lake, spring-fed FL, clear mountain reservoir) | > 3 m (10 ft) | 5-10+ m (16-33 ft) | Chara/Elodea/milfoil to deepest; hydrilla to ~ 6-8 m |
| Clear reservoir (TN valley, Ozark, Texas Hill Country) | 1.5-3 m (5-10 ft) | 3-6 m (10-20 ft) | Milfoil/hydrilla/Egeria canopies |
| Moderately stained / mesotrophic | 0.75-1.5 m (2.5-5 ft) | 1.5-3 m (5-10 ft) | Typical Southern stained reservoirs: SAV to 6-10 ft |
| Heavily stained (tannic, blackwater) | 0.3-1 m | 0.5-2 m (2-6 ft) | Color limits more than turbidity; emergent/floating-leaved dominate |
| Turbid (Great Plains, delta, silty) | < 0.5 m (< 1.5 ft) | 0.3-1 m (1-3 ft) | SAV essentially shoreline only |

All Zmax entries **[E]** computed from the Secchi relation plus general knowledge; flagged for verification.

### 4.4 Vegetation likelihood by depth band (draft prior; probability that SAV or macrophyte cover > 10% in the band during peak season; [E] built from Zmax logic)

| Depth band | Clear reservoir / natural lake | Stained reservoir | Turbid reservoir |
|---|---|---|---|
| 0-1 ft | High for emergent/floating-leaved; SAV moderate (wave/desiccation/ice scour limit); 0.6 | High (emergent) 0.6 | Moderate 0.4 (emergents on shoreline; SAV low) |
| 1-3 ft | Highest SAV 0.8 | 0.7 | 0.3 |
| 3-6 ft | 0.8 | 0.6 | 0.1 |
| 6-10 ft | 0.6 | 0.25 | ~ 0.02 |
| > 10 ft | 0.3 (very clear) / 0.1 typical clear | ~ 0.02 | ~ 0 |

Interpretation: peak SAV cover for most reservoirs is 2-8 ft; bowfishing (shallow-water, visibility-limited) largely occurs in the exact band with highest vegetation likelihood, so the vegetation prior matters most for access (Section 5).

### 4.5 Level-change interaction table (draft; deltas relative to normal pool)

| Pool change | Flooded terrestrial veg / shoreline grass | Emergent stands | SAV light / depth distribution | Desiccation | Boat / bowfisher access | Confidence |
|---|---|---|---|---|---|---|
| +2 ft above normal (spring flood / rising) | New shoreline grass flooded (large area on flat shorelines, ~ 2 ft rise on a 1:50 slope moves shoreline ~ 100 ft horizontally); grass green for 2-6 weeks then decays; best for fish spawning habitat (carp, buffalo, gar) | Inundated: bulrush/cattail partly submerged, new lanes; woody buttonbush/willow standing in water | Shallow SAV gets deeper water (lower light), minimal change if clear; turbid + high water = shallow SAV light loss; sediment resuspension if flood inflow | None | More shallow acreage reachable; grass becomes accessible to boats but may be dense, snaggy | [L]/[E] |
| +5 ft or more | Large-scale flooding of brush/trees; flooded timber hazard; short-lived grass | Emergent zones drown if > ~ 1-2 ft above stems for prolonged periods; floating-leaved plants (lotus, lily) tolerate 3-5 ft | SAV zone shifts shoreward by contour; SAV depth range shifts in lakes with clear water; in turbid lakes, light loss; multi-year high water causes SAV decline (Okeechobee pattern [L]) | None | Terrestrial areas reachable but obstructions (stumps, fences) | [L]/[E] |
| -1 to -3 ft below normal | Shoreline grass exposed (drying); previously flooded grass lost; **new terrestrial veg germinates on exposed mud flats** (moist-soil annuals, smartweed, cocklebur) -- re-flooded later | Emergent stands left stranded and/or colonize new area downslope | SAV in 0-3 ft band exposed; deeper SAV gets more light (lower water over plants) -> topped-out canopies; mats concentrate in remaining water | Rooted SAV in 0-1.5 ft stranded; desiccation kills plants only if exposed days-weeks | Shallow flats become inaccessible by boat (propeller/ground); remaining water concentrates fish at edges of beds | [L]/[E] |
| -5 ft or more (major drawdown) | Large shoreline exposed; terrestrial plants (grasses) can establish in 4-12 weeks during growing season | Emergent stands expand downslope | SAV mostly restricted below normal waterline; lakes with 6-7 ft yearly fluctuation (Sam Rayburn) show strong depth structure **[V]** | Winter drawdown: EWM control via freezing/desiccation is effective with deep freeze, 1-2 months; hydrilla tubers are NOT reliably killed (a north-Texas reservoir 12-month drawdown showed no tuber loss; tuber loss depends on drying and soil type) **[V]** (see weed science papers below) | Many boat ramps unusable; flats unfishable; but exposed vegetation may be "re-flooded" later with high bowfishing value | [V]/[L] |

Drawdown literature: Cooke 1980 "Lake Level Drawdown as a Macrophyte Control Technique," Water Resources Bulletin 16(2):317-322 **[V]** (citation only); Weed Science paper on hydrilla tuber drawdown/desiccation **[V]** (https://resolve.cambridge.org/core/journals/weed-science/article/effects-of-drawdowns-and-dessication-on-tubers-of-hydrilla-an-exotic-aquatic-weed/66259544CA4394462A1457B7FEF4CECB); NC mesocosm: 1-week drawdown killed hydrilla on sand, not silt loam; >= 2 weeks suppressed regrowth and tubers **[V]** (J Aquat Plant Manage 36:127? -- the search result "japm-36-02-127"; verify); Wisconsin McDill Pond / Lower Spring Lake EWM share dropped 46% to 26% **[V]**.

### 4.6 Reservoir/lake case notes (what to look for; most need verification)
- **Sam Rayburn (TX)**: annual fluctuation ~ 6-7 ft; aquatic vegetation primarily hydrilla and American lotus **[V]** 2022 TPWD survey. Hydrilla acreage in recent years: not found this session.
- **Toledo Bend**, **Seminole**, **Guntersville**, **Kentucky Lake**, **Okeechobee**, **Conroe**: no peer-reviewed pool-elevation/vegetation relationship fetched this session; see Section 6. Likely sources: TPWD/TAMU/Corps "Hydrilla and lake level" reports; Corps Mobile District Seminole reports; TVA/ADCNR Guntersville vegetation surveys; Kentucky Lake TWRA; Okeechobee Havens et al., SFWMD.
- **Great Plains reservoirs**: strongly fluctuating pool + turbid water -> SAV rare; flooded terrestrial grass/woody and emergent (cattail, bulrush) dominate; "pool-year effect" -- high pool years flood grass and later enhance fisheries (Kansas/Nebraska reservoir fish-habitat studies, flooded vegetation and year-class strength) [L], e.g., Kansas/Nebraska game agencies; verification needed.

### 4.7 Why spawning habitat matters (not modeled)
Carp, buffalo, and gar commonly spawn in flooded vegetation in spring (shallow inundated grass, willows). Flood-rise events thus concentrate bowfishing quarry in newly flooded shallows [L]. We cite this only to justify why "flooded terrestrial vegetation" is a flag in Sector.

---

## 5. Part C - Bowfishing accessibility and density classes

### 5.1 What is hard to bowfish
Peer-reviewed literature does not quantify bowfishing success vs vegetation density (none found this session). Claims below are **[A]** from bowfishing community knowledge and my general judgment unless noted:

| Density feature | Effect | Label |
|---|---|---|
| Surface-topped hydrilla/EWM/coontail mats (PAC/PVI ~ > 40%) | Impedes outboard/airboat/mud-motor propulsion (weeds foul props); can block arrow penetration: weeds deflect arrows; line tangles in stems | [A] |
| Floating mats (hyacinth, salvinia) | Block both visibility and arrow path | [A] |
| Dense emergent (cattail, giant cutgrass) | Blocks boat completely; fish shot from edges | [A] |
| Sparse-moderate SAV with open pockets | Often the *best* bowfishing structure: fish feed/hold in beds and edges, visible in pockets/holes | [A] |
| Line safety | Tangling of retrieval line with the bowstring can cause snapback toward the shooter; use of safety slide recommended **[V]** (patent-document description, justia patent 6517453); bowfishing line 80-400 lb braid to pull fish through weeds | [V]/[A] |
| Visibility | Stained water + dense canopy reduces visibility; clear water + moderate beds gives clearest shots | [A] |

Bass-fishing observation: hydrilla/milfoil "structured" vegetation is open underneath **[A]** (bassresource forum). No bowfishing-specific agency source found.

### 5.2 Agency metrics
- FWC defines PAC (percent area covered) as horizontal share of mapped lake surface with vegetation, and PVI (percent volume infested) as the average share of the water column occupied by vegetation **[V]** (https://myfwc.com/research/freshwater/monitoring/plant-mapping/).
- PAC and PVI diverge sharply: Northeast hydrilla example 95.8% PAC vs 53.5% PVI in Dec 2016 **[V]**; June 5 2018 PAC 15.9% vs biovolume 1.6% **[V]**.
- Common point-intercept density codes: 0 none, 1 sparse, 2 moderate, 3 dense **[V]** (Jones workshop); NC DEQ uses Trace/Sparse/Moderate/Dense **[V]**.
- Management thresholds: Lake Toho managed to ~ 50% hydrilla cover **[V]**. Commonly cited agency framing (<10% sparse, 10-40% moderate, >40% dense) is a widespread convention [L]; I could not verify a single authoritative document specifying exactly these cutoffs.
- Corps/FWC survey categories for "acres of coverage" often reported as "trace/scattered/moderate/dense" [L].

### 5.3 Recommended Sector classes

Apply to the *accessible-water area* (e.g., 0-8 ft, and not the whole lake). Use biovolume (PVI-like) in addition to cover (PAC-like).

| Sector class | Local cover (PAC-like) | Canopy (PVI-like) | Agency terms mapped | Bowfishing meaning |
|---|---|---|---|---|
| none | < 2% | ~ 0 | none / absent / trace | Open water; fish visible, no tangles; may lack structure |
| scattered | 2-15% | < 10% | trace / sparse / scattered | Open pockets, easy boat travel; good edges |
| moderate | 15-45% | 10-40% | moderate / patchy | Partial blocking; navigable lanes; strong fish-holding structure; line tangle risk rises |
| dense | > 45% | > 40% (or surface-topped) | dense / topped out / mat | Props foul, arrows deflect/tangle, boats can't traverse; fish only at edges |

Rationale **[E]**: cutoffs adapted from the 10/40 convention and the Lake Toho 50% management level. Modifiers: add flags for `surface_topped` (canopy at surface), `floating_mat`, `emergent_wall`, `flooded_terrestrial`. Mapping from imagery NDVI or FAI thresholds must be calibrated per sensor and clarity (water-leaving signal differs from surface canopy).

---

## 6. Seasonal-prior algorithm (draft)

### 6.1 Inputs
- Lake: latitude, elevation, region code, dominant group(s) and regime flag from other notes (managed? grass carp? eutrophic? clarity class? flood-prone?).
- Time: date (week-of-year), daily air temp history (e.g., last 120 days) or water temp (if sensor available).
- Hydrology: current pool elevation, pool anomaly relative to normal pool and 7/30/90-day trend.
- Last good satellite observation: class, date, cloud-free fraction.
- Management events (spraying notice, drawdown schedules) if available.

### 6.2 Formula sketch
1. Water-temp proxy: Tw ~ low-pass (air temp, tau ~ 7-14 d) with shallow-lake lag; compute GDD10 since last winter minimum.
2. Phenology curve per group g: P_g(t) = clip(sigmoid((GDD10 - G_on)/s1) * (1 - sigmoid((D_senesce - t_since_peak)/s2)) ) where autumn senescence triggered by Tw < 15 C and photoperiod < 12 h. CLP uses its own inverted curve (peak at GDD10 ~ 300-600; crash when Tw > 22-25 C).
3. Amplitude A_l: lake-level peak-density baseline from historical imagery (e.g., last 3-5 summers' P90 class) shrunk toward regional prior: A_l = w*A_hist + (1-w)*A_region, w by # clear observations.
4. Level modifier L(depth band): multiply by depth-band likelihood from Section 4.4 shifted by pool anomaly: depth_band_eff = depth_nominal + pool_anomaly. Emergent/flooded-grass flag from pool anomaly rising > 1-2 ft in spring (flooded grass available for ~ 2-6 weeks) [E]; drawdown > 3 ft flags stranded SAV in shallow bands.
5. Management modifier M: scale down amplitude when treatment recently recorded or grass-carp-regime; scale to 0 after a documented collapse until a new clear observation.
6. Combine with observation: posterior class probabilities via simple Bayesian update: prior = softmax over classes from P_g * A_l * L * M; update with last clear observation decayed exponentially with half-life ~ 14-21 days in growing season, ~ 45-60 days in dormant season (state is stable then); cap the prior's influence when a clear-sky observation < 10 days old exists.
7. Output: class probabilities, point class, confidence band, and a "reason string" (e.g., "Seasonal: Southeast hydrilla topped-out period; pool +1.5 ft").

### 6.3 Expected accuracy and limits [E, needs back-test]
- Unmanaged southern reservoir, growing season, stable pool: exact-class ~ 65-75% weekly; adjacent-class ~ 92%.
- Managed / grass-carp lakes: ~ 40-50% exact; should not be used without recent observation.
- Northern lakes: timing precise from ice-off/GDD but amplitude uncertain (CLP/EWM lakes vary).
- Shoulder weeks (green-up, dieback) are least reliable.
- Must back-test: fit on Sentinel-2/Landsat clear-sky history for the 621 lakes, evaluate leave-one-year-out; compare naive climatology (week-of-year median) vs GDD-based vs GDD+pool.
- Highest value: distinguishing "winter low" from "summer dense" and flagging flooded/dry shorelines; lowest value: distinguishing moderate from dense in mid-summer without imagery.

---

## 7. Unverified claims (do not ship without checking)

1. Chambers & Kalff regression coefficients (log Zc = 0.62 log SD + 0.26) and 1.0-2.5 x Secchi rules of thumb. Paper existence verified; numbers not.
2. All GDD thresholds and species temperature optima (Section 1/2); require checking against Barko & Smart 1981, Madsen, Netherland 1997, Woolf & Madsen 2003.
3. All month-by-region cell values in Section 3 (expert synthesis, no direct dataset).
4. Quantified uncertainty (exact-class 60-70%, CV 30-60%, etc.) -- modeling assumptions, not measured.
5. Depth-band probability table (4.4) and Zmax per clarity class (4.3).
6. Lake Conroe / Guntersville / Sam Rayburn / Toledo Bend / Seminole / Kentucky Lake / Okeechobee histories: only partial verified facts (TPWD 6-7 ft fluctuations; TVA 2014 17,000 acres; eelgrass volumes). Conroe grass-carp history, Seminole hydrilla trends, Kentucky Lake vegetation cycles, Okeechobee hurricane collapse specifics are from memory.
7. Remote-sensing phenology citations (Villa, Luo, Cavalli, Thamaga & Dube) are leads, not verified.
8. 23,000 acres hydrilla/milfoil at Guntersville (mayor), 77,000 acres milfoil 1960s: press anecdotes.
9. Hydrilla tuber drawdown outcomes (some verified from abstracts; magnitude of tuber survival depends on soil and moisture).
10. Agency density cutoffs <10 / 10-40 / >40: not located in a single authoritative document.
11. Bowfishing-specific effects of vegetation density: no peer-reviewed or agency source found; all anecdotal.
12. Flooded grass persistence (2-6 weeks green, 4-8 weeks submerged survival), shoreline slope examples, spawning concentrations: general expectation; verify against agency fisheries literature (e.g., Kansas, Nebraska, TPWD).
13. The "regional outdoor-news report" that higher water reduced East Texas hydrilla: secondary, unverified.

## 8. Source URLs (accessed this session via search)
- FWC plant mapping (PAC/PVI): https://myfwc.com/research/freshwater/monitoring/plant-mapping/
- Hydrilla workshop (Jones, NE ANS 2019): https://northeastans.org/docs/meetings/201906/files/Hydrilla%20workshop%20Jones.pdf
- TPWD Sam Rayburn 2022 survey: https://tpwd.texas.gov/publications/pwdpubs/lake_survey/pwd_rp_t3200_1371/index.phtml
- TAMU grass carp: https://bc4weeds.tamu.edu/grasscarp
- TVA / Guntersville eelgrass 2025: https://southernfishingnews.com/removing-eelgrass-aquatic-invasive-weed-it-takes-a-team/
- Guntersville history: https://www.advertisergleam.com/news/a-history-of-weeds-on-g-ville-lake/article_81acab88-e1cf-11ef-91c7-4fa41e0f1584.html
- Chambers & Kalff 1985 secondary: https://scielo.br/j/abb/a/zrzKKvVZ6RDJHdYGbHX4vMD/?lang=en ; Springer record https://link.springer.com/doi/10.1007/BF00026714 (unconfirmed which paper)
- Hydrilla drawdown/tuber (Weed Science): https://resolve.cambridge.org/core/journals/weed-science/article/effects-of-drawdowns-and-dessication-on-tubers-of-hydrilla-an-exotic-aquatic-weed/66259544CA4394462A1457B7FEF4CECB
- NC mesocosm drawdown: https://apms.org/wp-content/uploads/japm-36-02-127.pdf
- EWM winter drawdown (WI/MSU): https://www.canr.msu.edu/news/why_is_my_lake_water_lowered_in_the_winter ; https://www.uwsp.edu/cnr-ap/UWEXLakes/Documents/programs/convention/2010/olson_kristi_mcdill_pond.pdf
- Bowfishing line/snapback patent: https://patents.justia.com/patent/6517453
