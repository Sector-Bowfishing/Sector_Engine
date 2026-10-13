# Vegetation Brain - Note 03b: Verification of Note 03 claims

Companion to `03_seasonal_and_level_depth.md` (not modified). Verification run 2026-10-13.
Evidence grades: **OPENED** = I read the page/PDF text or rendered page image myself this session and the quote is from it.
**SEARCH-EXCERPT** = quote/number came from a web-search result summary of the page; I could not open the page (403/paywall/binary), so treat as one notch weaker.
Verdicts: CONFIRMED / CORRECTED / UNVERIFIABLE / WRONG.

---

## A. Maximum colonization depth vs Secchi (Section 4.1 of note 03)

### A1. "Chambers & Kalff (1985): log10(Zc) = 0.62 log10(SD) + 0.26"
**Verdict: WRONG attribution and slightly wrong coefficient. The equation (0.61, 0.26) is from Canfield et al. 1985, not Chambers & Kalff.**
- OPENED (scanned PDF, rendered to image and read): Canfield, D.E. Jr., K.A. Langeland, S.B. Linda, W.T. Haller. 1985. "Relations Between Water Transparency and Maximum Depth of Macrophyte Colonization in Lakes." J. Aquat. Plant Manage. 23:25-28. https://apms.org/wp-content/uploads/japm-23-01-023.pdf
  - Abstract: "The best fit logarithmic model was log(MDC) = 0.61 log (SD) + 0.26 where MDC and SD values are expressed in meters. The model, however, has a 95% confidence interval of 46-236 percent of the calculated MDC value."
  - p.27: "The coefficient of determination for this model is 0.56"; "The model tends to underestimate maximum depths of colonization in very clear waters and over estimate colonization depths when Secchi disc depths are low." Data: 27 Finnish, 26 Florida, 55 Wisconsin lakes (p.26); Florida SD/MDC measured once, June-Oct 1981 or 1982, fathometer.
  - Table 1 (p.27), regional fits, all meters, N = number of lakes:
    - Finland N=27: log(MDC)=0.51 log(SD)+0.18, r2=0.82
    - **Florida N=26: log(MDC)=0.42 log(SD)+0.41, r2=0.71**
    - Wisconsin N=55: log(MDC)=0.79 log(SD)+0.25, r2=0.57
  - Table 2 (p.27): % of surface light at MDC for Florida lakes. Hydrilla lakes: Lochloosa 0.46, Orange 0.68, Tyler 0.75, Pineloch 0.82, Fairview 0.86, Catherine 1.1, Milldam 1.2, Sampson 2.7, Rowell 4.3, Stella 5.4. Others: Eleocharis ~3-8%, Utricularia 4.1-8.3%, Nuphar 1.9%, Ceratophyllum 3.4%. Text: hydrilla LCP "about 0.75% of full sunlight"; coontail LCP 35 uE vs hydrilla 15 uE.
- SEARCH-EXCERPT (cdnsciencepub abstract page returned 403): Chambers & Kalff 1985, Can. J. Fish. Aquat. Sci. 42:701-709, doi 10.1139/f85-090. Their abstract gives (Zc in m, D = mean summer Secchi in m): angiosperms **(Zc)^0.5 = 1.33 log(D) + 1.40**; bryophytes (Zc)^-0.5 = -0.48 log(D) + 0.81; charophytes log(Zc) = 0.87 log(D) + 0.31; depth of max angiosperm biomass (Zb)^0.5 = 0.54 log(D) + 1.15. Data: eight southern-Quebec lakes plus literature. (Matches my own recall of the paper; but I did not open the page, so verify before shipping.)
- Computed values (my arithmetic from the above):
  - Canfield pooled: SD 0.5 m -> 1.2 m; 1 m -> 1.8 m; 2 m -> 2.8 m; 3 m -> 3.5 m.
  - Canfield Florida-only: SD 0.5 m -> 1.9 m; 1 m -> 2.6 m; 2 m -> 3.5 m; 3 m -> 4.2 m.
  - Chambers & Kalff angiosperm: SD 0.5 m -> Zc = (1.33*(-0.301)+1.40)^2 = 1.0 m; SD 1 m -> 2.0 m; SD 2 m -> (1.80)^2 = 3.2 m; SD 3 m -> (2.03)^2 = 4.1 m.
- Implication: use Florida-specific Canfield for southern lakes; pooled model has a 46-236% CI, so Zmax is a soft prior only.

### A2. "SAV generally limited to ~1.0-2.5 x Secchi" (rule of thumb) and Section 4.3 table (Zmax by clarity class)
**Verdict: CORRECTED.** Using the fits above the ratio Zmax/SD is not constant: it falls as water gets clearer (Canfield pooled slope 0.61 <1). In turbid water (SD 0.5 m) Zmax is ~2-3.8x Secchi (1.2-1.9 m); at SD 2-3 m it is ~1.2-1.8x Secchi. Table 4.3 "very clear >3 m -> 5-10+ m" is not supported by the pooled fit (3 m -> 3.5-4.2 m) although Canfield warns the model underestimates in very clear water. Table 4.3 stays [E]. Hydrilla-specific: Canfield Table 2 shows hydrilla grows to depths receiving ~0.5-1.2% of surface light in several lakes (consistent with "1-5% light" being too high for hydrilla in Florida; revise to ~0.5-5%).

### A3. Duarte & Kalff (1987)
**Verdict: UNVERIFIABLE (equation); description CONFIRMED in part.** SEARCH-EXCERPT: "Latitudinal influences on the depths of maximum colonization and maximum biomass of submerged angiosperms in lakes," Can. J. Fish. Aquat. Sci. 44(10):1759-1764; says colonization depth declines with latitude. No coefficients obtained. Drop from product logic unless fetched from a library copy.

### A4. Itaipu (hydrilla vs Egeria Zmax-Secchi)
**Verdict: CONFIRMED.** OPENED https://scielo.br/j/abb/a/zrzKKvVZ6RDJHdYGbHX4vMD/?lang=en : log-ANCOVA intercepts 0.84 (E. najas) and 0.46 (H. verticillata), slopes 0.24 and 0.49; Zmax "can be accurately predicted by underwater light intensity" (cites Chambers & Kalff 1985). Slope 0.49 for hydrilla is close to Canfield Florida (0.42).

---

## B. Density categories (Section 5.2)

### B1. "FWC defines PAC and PVI"
**Verdict: CONFIRMED.** OPENED https://myfwc.com/research/freshwater/monitoring/plant-mapping/ : "Percent area covered (PAC) is defined as the overall surface area of a lake that has vegetation growing"; "percent volume infested (PVI) is defined as the average percentage of a lake's water column occupied by vegetation." The page gives NO numeric density classes or thresholds ("species-specific maps with density and occurrence estimates" only).

### B2. "Agency <10% sparse / 10-40% moderate / >40% dense convention - no source found"
**Verdict: CORRECTED - source found, but it is South Florida Water Management District, not FWC/Corps/TVA, and it is for treatment-wetland (STA) SAV cover.**
- OPENED (PDF stream text extracted locally): SFWMD, 2011 South Florida Environmental Report, Vol. I, Appendix 5-10 (App. 5-10-9 and -11 figure legends), https://sfer-docs.sfwmd.gov/2011_SFER/v1/appendices/v1_app5-10.pdf :
  "None - no SAV present (0 percent); Trace - strands of SAV (0-1 percent); Sparse - patchy, small beds (1-10 percent); Moderately dense - semi-continuous, moderate to small beds (10-40 percent); Dense - continuous beds (40-80 percent); Very Dense - continuous thick beds (>80 percent)."
  So the 10/40 cutoffs exist, plus an 80% cutoff. It is a map-legend cover scale, one agency's convention.
- Other agencies differ (SEARCH-EXCERPT): NC DEQ rake scale 1 Trace <25%, 2 Sparse 25-50%, 3 Moderate 50-75%, 4 Dense 75-100% (2022 reports); some NY/MA surveys use 0-4 with 25% steps. Hence: "10/40" is NOT a universal standard; store thresholds with a `scheme` tag.
- Biomass-based alternative, OPENED: SFWMD Lake Okeechobee SAV page (https://www.sfwmd.gov/sites/default/files/documents/quarterlysavmethodsandresults_2010edits.docx, docx unzipped locally): "visual evaluations generally correspond to sparse = less than 5 g dry weight / m2, moderate = 5 to 50 g dry weight / m2, and dense = greater than 50 g dry weight / m2."

### B3. Wisconsin/Minnesota rake fullness 1-3
**Verdict: CONFIRMED (consistent across reports; official protocol text not opened).** SEARCH-EXCERPT of multiple WI survey reports: rating 1 = "few plants on rake head"; 2 = rake head about half full ("moderate"); 3 = "plants overflowing the rake tines" ("abundant"); 0 = empty rake. Protocol attributed to Hauxwell et al. 2010 "Recommended Baseline Monitoring of Aquatic Plants in Wisconsin" (UWSP PI protocol URL moved/404, not opened). This is a per-sample-point abundance score, not a % cover class, so it cannot map directly to PAC cutoffs. Minnesota DNR: plant-survey PDF surfaced in search but not opened. UNVERIFIABLE for MN specifics.

### B4. "Corps/TVA density classes"
**Verdict: UNVERIFIABLE.** No Corps or TVA numeric density class table found; TVA reports acreage by management action, not density classes (see D).

### B5. "Northeast hydrilla PAC 15.9% -> 90.7%, biovolume 1.6% -> 41.4%; 95.8% PAC vs 53.5% PVI" (Jones, NE ANS 2019)
**Verdict: UNVERIFIABLE this session** (PDF is image-based 8 MB; WebFetch returned binary). Prior note marked [V]; not re-checked.

### B6. "Lake Toho ~50% management level, >3,500 acres/yr, carrying capacity 99%"
**Verdict: CONFIRMED (SEARCH-EXCERPT of FWC presentations)**: "more than 3,500 acres of Lake Toho are managed each year to maintain about 50% cover"; carrying capacity up to 99% of lake area.

---

## C. Phenology (Sections 1-3)

### C1. Hydrilla (dioecious, South): "Jun-Oct peak; Oct-Dec senescence; reduced but alive in Deep South"
**Verdict: CONFIRMED with a correction on shape and amplitude.** OPENED (scanned PDF rendered): Madsen & Owens 1998, "Seasonal Biomass and Carbohydrate Allocation in Dioecious Hydrilla," J. Aquat. Plant Manage. 36:138-145, https://apms.org/wp-content/uploads/japm-36-02-138.pdf (Lewisville, TX outdoor ponds, monthly Jan 1994-Jul 1995).
- p.138 abstract: "Biomass increased from May through September, regrowing from overwintering shoots and root crowns, but not tubers." Lowest stored carbohydrate July 1994 / June 1995.
- p.140: "Maximum total biomass for the LAERF was approximately 1000 g m-2 occurring in July 1994"; Fig 1B shows total ~600 g DW/m2 Jan-May, ~1,090 in Jul 1994, a second high ~1,080 in Oct-Nov 1994, ~900 Dec, ~600-800 by Mar-Jun 1995.
- p.140: "Hydrilla did not undergo complete dormancy throughout the winter months, although biomass decreased... biomass remained within 50% of maximum summertime biomass." Over 90% of biomass is aboveground in summer.
- p.140: "Flowering hydrilla was observed in late September, just prior to tuber and turion formation"; tuber/turion density peaked Oct-Nov 1994 (Fig 2D); "optimum temperature for tuber germination ... between 15 and 35 C (Haller et al. 1976)"; "undisturbed hydrilla tubers will germinate in the latter part of July through August in Texas (unpubl.)"; at LAERF regrowth is from stolons/root crowns rather than tubers. Literature range cited: 890 g/m2 Lake Trafford FL (Bowes 1979).
- Corrections to note 03: (1) in north Texas winter biomass is still ~50-60% of peak (our 0-S for TN valley/Southeast Jan-Feb is likely too low in biomass terms, though surface canopy/visibility can still be low); (2) a bimodal shape (Jul and Oct-Nov highs) is observed; (3) tubers are not the main green-up source for established beds, so "Feb-Apr from tubers" is misleading.
- SEARCH-EXCERPT, Little Lake Barton FL: biomass 0.385 kg/m2 (Apr 1977) to 2.275 kg/m2 (Oct 1977) (late-season peak, one year).
- Growth rate "~1 inch/day" and "tops out in 6-10 weeks": UNVERIFIABLE this session.

### C2. Eurasian watermilfoil
**Verdict: CONFIRMED for northern timing; thresholds CORRECTED.** OPENED https://www.mtu.edu/mtri/research/project-areas/environmental/water/eurasian-watermilfoil/biology/ (Michigan Tech Research Institute): "begins photosynthesizing when water temperatures reach 10C in the spring"; shoots emerge as "water temperatures begin increasing and approaching 15C"; sexual reproduction "occurs in June once the inflorescence grows above the surface"; biomass peak "occurs shortly after the plants flower"; "aboveground tissue typically dies back to the root crowns in the late fall"; where "water remains greater than 10C" it "will overwinter in an evergreen form showing little dieback." So EWM peak is roughly June-July in the Great Lakes, earlier than the Jun-Aug (two-peak) in note 03; winter-evergreen in warm water confirmed.
- SEARCH-EXCERPT: Conesus Lake NY 2020 monitoring: biomass peaked in August at 300-400 g/m2. Wisconsin management practice schedules "late-summer EWM peak-biomass" surveys. Net: peak window June-August depending on lake and metric.
- Madsen 1997 (Lewisville TX ponds; carbohydrate lows July 1991, April 1992, May 1993) SEARCH-EXCERPT only.

### C3. Curlyleaf pondweed
**Verdict: CONFIRMED.** OPENED https://dnr.state.mn.us/invasives/aquaticplants/curlyleaf_pondweed.html : "Turions sprout in the fall, and it is generally the first pondweed to come up in the spring"; "typically flowers, fruits, and produces turions in June before dying back in mid-summer"; "Forms dense mats at the water's surface that inhibits water recreationists"; "Midsummer die-offs can litter the shoreline with dead plants."
- SEARCH-EXCERPT: Michigan EGLE/MSU Extension: germination triggered by falling water temperature (roughly <68 F / 20 C, daylight <11 h), late Sept-Nov; shoots form at ~5 C (41 F) in early-mid spring. Note 03 said germinate at "<~15 C" and senesce when ">20-25 C": germination threshold CORRECTED to ~20 C per MSU Extension (secondary). Southern CLP: biomass and turions peak in winter and plants grow year round (SEARCH-EXCERPT, southeastern US study) - supports note 03's "Apr-May South" only loosely; Southeast CLP peak is winter-spring.
- Remote-sensing: Baiyangdian (China) Sentinel-2: NDVI peak of Potamogeton crispus March-May (SEARCH-EXCERPT of Remote Sens. 14(3):640, 2022; page 403).

### C4. Coontail
**Verdict: UNVERIFIABLE (timing).** No timing source opened. Related: Canfield 1985 gives coontail LCP 35 uE/m2/s (higher than hydrilla 15), consistent with "coontail needs more light." Baiyangdian late group incl. Ceratophyllum matured Jul-Sep with ~210-day growing season (SEARCH-EXCERPT, Ecological Indicators 2023; 403) supports Jul-Sep peak in a temperate lake.

### C5. American lotus
**Verdict: UNVERIFIABLE (timing).** No phenology source found. Confirmed only that it is a dominant plant at Sam Rayburn (see D1).

### C6. Water hyacinth
**Verdict: CONFIRMED (doubling), partially CORRECTED (temperatures).** OPENED https://ask.ifas.ufl.edu/publication/AG385 (Gettys, "Waterhyacinth: Florida's Worst Floating Weed," UF/IFAS, (c) 2024): "double in size in as little as 6 to 18 days"; needs "temperatures above 50 F to produce new growth"; "can survive moderate freezes"; "grows throughout the year in southern Florida but undergoes winter dieback in northern parts of the state." Matches note 03's "6-18 days" exactly. Note 03 said "Jul-Oct peak" - not sourced. SEARCH-EXCERPT: Owens & Madsen 1995 (JAPM 33:63-68) near-freezing tolerance limited, rooted plants longer; UC Davis doubling 7.0 d at 25-30 C.

### C7. Cattail / phragmites
**Verdict: UNVERIFIABLE.** Not located. (Linde, Janisch & Smith 1976 WI DNR Tech Bull 94 on cattail phenology is cited in Madsen & Owens reference list; could be pulled.)

### C8. Remote-sensing phenology leads (Villa, Luo, Cavalli, Thamaga & Dube)
**Verdict: UNVERIFIABLE; replacement leads found (SEARCH-EXCERPT):** Baiyangdian Lake, Remote Sens. 14(3):640 (2022), phenology-pixel method on Sentinel-2 in GEE, overall accuracy 94.8%, 5-day NDVI with HANTS gap filling; Baiyangdian 1986-2021 Landsat+Sentinel-2 (Ecological Indicators, Oct 2023): early group (P. crispus) matures Apr-May, growing season ~110 d, later group (Ceratophyllum, Myriophyllum verticillatum) matures Jul-Sep, ~210 d; Villa SPOT5-Take5 macrophyte phenology slides (cesbio.cnrs.fr PDF, not opened); Chimaditida Lake (Greece) Sentinel-2 SAV vs floating/emergent (MDPI 2025). No US reservoir NDVI curves found. These are Chinese/European shallow lakes; do not transfer timing.

---

## D. Reservoir level vs vegetation (Section 4.5-4.6, case notes)

### D1. Sam Rayburn: 6-7 ft fluctuation; hydrilla + lotus
**Verdict: CONFIRMED.** OPENED TPWD 2022 Survey Report https://tpwd.texas.gov/publications/pwdpubs/lake_survey/pwd_rp_t3200_1371/index.phtml : "Water level fluctuations average 6 to 7 feet annually"; "aquatic vegetation (primarily hydrilla and American lotus) and standing timber"; giant salvinia found 2008, "exceeded 4,000 acres in 2014", "reduced abundance to < 1,500 acres during most years" after herbicide plus high inflows. OPENED TPWD lake page https://tpwd.texas.gov/fishboat/fish/recreational/lakes/sam_rayburn/ : "Fluctuation: Average 7 feet annually"; "Drastic water level changes can decrease the amount of vegetation"; "At high water levels, inundated trees and bushes provide excellent habitat"; surface area 114,500 acres. No hydrilla acreage time series found. Toledo Bend: TPWD lists aquatic vegetation, standing timber, flooded terrestrial vegetation; hydrilla main plant (SEARCH-EXCERPT).

### D2. Lake Okeechobee: "SAV collapsed after 2004-05 hurricanes; multi-year high water causes SAV loss"
**Verdict: CONFIRMED, with numbers.**
- OPENED (docx text): SFWMD Lake Okeechobee SAV Assessments: "The drought and managed lower lake levels during 2007-2009 have combined to produce favorable conditions for the recovery of the SAV community... Total acreage of SAV has increased from <3000 acres in 2006 to >46,000 acres in 2009." Survey water levels 13.47-14.75 ft NGVD in 2010, "Light penetration was good"; sites with plants 30-39 of ~51; dense/moderate/sparse breakdown by season (e.g., Jan 2010 14/10/7, Apr 2010 10/11/10, Jul 2010 12/12/15, Oct 2010 8/11/18 of 30-39 vegetated sites). Also "dense emergent vegetation (mostly cattail)" at the two southernmost transects.
- SEARCH-EXCERPT (Springer Ecological Processes 2:23 and SFWMD SFER 2008/2012 chapters; Springer page needed login so not opened): Frances/Jeanne 2004 and Wilma 2005; SAV density fell from 4-34 to 0.1-4 g dry wt/m2; TSS up 4-6x; reduced light transparency persisted >4 years; later decline tied to lower stages under LORS 2008 with spikerush meadows replacing SAV. Conflict note: SAV rebounded in 2007-09 under LOW stage (drought), then declined again at low stage later, so "stage -> SAV" is non-monotonic; turbidity/light is the mediator.

### D3. Lake Conroe: grass-carp / hydrilla history (note 03: "dates and numbers not verified")
**Verdict: CONFIRMED (now verified).** OPENED https://d11.seafwa.org/journal/2008/lake-conroe-case-history-integrated-plant-management-hydrilla-control (Webb & Chilton, J. SEAFWA, March 2008, p.225): hydrilla first identified 1975 (190 ha) two years after impoundment; 1979 over 1,821 ha; "Between September 1981 and September 1982, 270,000 non-sterile diploid grass carp were introduced"; by Oct 1983 all vegetation removed; 13 years without hydrilla; 1996 1.3 ha found; 9 years of herbicide containment; 2005 spread despite herbicide; plan goal "<16.2 ha by spring 2008". SEARCH-EXCERPT: triploid stocking 2006-2008, ~130,000 fish (65/acre of hydrilla) per a news source; TPWD 2009 performance report says native vegetation fell from >1,000 acres (2006) to ~150 acres (2008). Note 03's "late 1980s-2000s era" is WRONG: the first collapse was 1981-83.

### D4. Guntersville / TVA drawdown effects
**Verdict: UNVERIFIABLE (no quantitative pool-elevation vs coverage study found).** Qualitative only, SEARCH-EXCERPT (WBIR/TVA, MSU Extension): TVA "treating thousands of acres" in growing season and relying on winter drawdown + freezing; MSU: "Drawdowns ... may not kill the desired invasive plant." Kentucky Lake: summer pool 359 ft, winter ~354 ft (5 ft) (explorekentuckylake report, undated). Guntersville 2025 numbers (555 acres treated system-wide, 200+ acres harvested, 10,000 acres surveyed; Guntersville 1,494 acres treated, 70,000 yd3 eelgrass vs 120,000 in 2023) re-surfaced in search (southernfishingnews.com); not independently re-opened. Corps WES report Doyle & Smart (ADA273280) exists on native plants for Guntersville; no findings read. Seminole: only press/congressional items on hydrilla, no drawdown/elevation data. Toledo Bend, Missouri River reservoirs, Kentucky Lake vegetation vs pool: nothing found.

### D5. Drawdown mechanics (Section 4.5 last row)
**Verdict: partly CONFIRMED.** SEARCH-EXCERPT: Rodman Reservoir FL drawdown: "80% of the hydrilla tubers were found to germinate" (from Madsen & Owens context); MSU Extension: winter drawdown works through desiccation+freezing, unreliable by species. Prior [V] items from note 03 (Cooke 1980; J Aquat Plant Manage 36:127; McDill Pond 46%->26%) not re-checked.

---

## E. Bowfishing / vegetation density quantitative
**Verdict: CONFIRMED that no quantitative source exists; only qualitative sources.**
- OPENED Missouri Dept. of Conservation https://mdc.mo.gov/fishing/get-started-fishing/bowfishing : "the clearer the water, the more difficult it can be to get close to fish"; "The deeper the fish is in the water, the more distorted it will appear"; "Smooth, still water is most conducive for proper fish identification and shooting"; page does not mention vegetation.
- SEARCH-EXCERPT, ANECDOTAL: guide/magazine text says most bowfishing is in water ~2-4 ft deep near vegetation edges or escape cover; retailer blog says look near vegetation. No source on arrow deflection by stems, boat transit through mats, or % cover thresholds. MN DNR (opened) says CLP "forms dense mats at the water's surface that inhibits water recreationists" (qualitative). SFWMD/Seminole press: dense hydrilla "significantly limits boat use" (SEARCH-EXCERPT, congressional release) - qualitative, no threshold.
- Keep all Section 5.1 effects tagged [A]. Sector class cutoffs (none/scattered/moderate/dense) should be labelled [E], loosely anchored to the SFWMD 1/10/40/80% legend.

---

## F. Summary of changes recommended to note 03
1. Replace "Chambers & Kalff log Zc = 0.62 log SD + 0.26" with Canfield et al. 1985: log MDC = 0.61 log SD + 0.26 (pooled, r2 0.56, 95% CI 46-236%); Florida: log MDC = 0.42 log SD + 0.41 (r2 0.71, n=26). Chambers & Kalff angiosperm: Zc^0.5 = 1.33 log D + 1.40 (verify).
2. Density cutoffs: cite SFWMD 2011 SFER App 5-10 legend (1/10/40/80%); stop describing 10/40 as a FWC/Corps/TVA convention. FWC defines PAC/PVI but no classes.
3. Hydrilla winter biomass in TX ponds is ~50-60% of peak; peaks Jul and Oct-Nov; regrowth from crowns/stolons not tubers.
4. EWM peak shortly after June flowering in Great Lakes; evergreen where water stays >10 C.
5. Lake Conroe first grass-carp collapse was 1981-83 (270,000 diploids), not 1980s-2000s generic.
6. Okeechobee SAV: <3,000 acres (2006) -> >46,000 acres (2009) under drought/low stage; hurricane + turbidity explanation; non-monotonic with stage.
7. Still UNVERIFIABLE: coontail, lotus, cattail/phragmites phenology; GDD thresholds; month-by-region table; any pool-elevation vs vegetation quantification for Guntersville, Kentucky Lake, Seminole, Toledo Bend, Missouri reservoirs; bowfishing density effects.
