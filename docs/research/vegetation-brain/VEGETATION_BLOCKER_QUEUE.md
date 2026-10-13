# Vegetation Brain — Blocker Queue

**RESEARCH ONLY. Proposed Brain.** Ordered by usefulness-per-effort. "Owner" is who can unblock; actions needing Michael are marked **M**. Ids are stable for the handoff.

| ID | Blocker | Why it matters | Next action | Owner | Effort |
|---|---|---|---|---|---|
| **B-01** | **Submerged detectability is unproven/negative** — Sentinel-2 indices fail on submerged-only truth | Submerged is the highest-value class for bowfishing | Lake-level sonar test done (S2 sees beds only above ≈40 % canopy/water-column; clarity does not rescue). **FWC BioVolume ImageServers hang** — ask FWC (WHOML/LTM team) for the rasters or alternative sonar sets; meanwhile commit to potential-habitat design | Research | S |
| **B-02** | **No clarity (Secchi) per lake/date** | Controls detectability and potential-SAV depth limit; Vegetation must not invent clarity | Ask Clarity Brain for a fleet Secchi/clarity-class feed with confidence; or ingest NLA/LAKEWATCH/state Secchi as interim | Clarity owner / **M** | M |
| **B-03** | **No Depth Brain yet** | Potential-SAV, accessible-water density, flooded shoreline all need depth | Use GloBathy-derived shallow fractions as `MODELLED` until Depth exists; align schema | Depth owner | M |
| **B-04** | **Seasonal prior unvalidated** | Cloud-day fallback is a key requirement | Build per-lake weekly S2 history 2017–2025 for ~60 lakes; leave-one-year-out back-test | Research | M |
| **B-05** | **Cell-level behaviour of Clarity's grass rule only partly known** — precision 0.92 with pass acceptance, 1.00 with median persistence but on 60 positive cells (54 in one lake); FL cell recall only 0.32 | Reusing the rule is the cheapest path | Re-score on NLA/FWC/UMR lakes with larger positive samples; use the *production* code (not a replica with truncated windows) on the same lakes | Research / Clarity owner | M |
| **B-06** | **Large-reservoir ground truth is request-only** (TVA, TPWD, SFWMD, Corps; WI DNR) | The bowfishing core is big reservoirs | **M** to email/request: TVA Guntersville/Wheeler annual maps; SFWMD Okeechobee SAV GIS; TPWD Inland Fisheries vegetation GIS; WI DNR SWIMS PI export | **M** | S (person) |
| **B-07** | **Minnesota UMN dataset behind bot challenge** | 372k points, 1,520 lakes, CC0 — best northern truth | **M** open DOI 10.13020/av1t-c667 in a browser and save the zip to `Sector_Research_Data/vegetation-brain/sources/mn_umn/` | **M** | XS |
| **B-08** | **UMRS 2020 land-cover polygons not pulled; class schema unconfirmed** | Only open polygon source for Mississippi pools | Download Pool 4/8/13 zips (ScienceBase 6102cbf7d34ef8d7055e7971); read schema | Research | S |
| **B-09** | **No quantitative pool-elevation vs vegetation studies found** for Guntersville, Kentucky, Seminole, Toledo Bend, Missouri reservoirs | Level interaction is hypothesis only | Mine TVA/Corps/TPWD reports; use S2 history + Lake Brain pool history as natural experiment (Sam Rayburn, Okeechobee) | Research | M |
| **B-10** | **Density cutoffs are estimates** (none/scattered/moderate/dense) | Output vocabulary depends on them | Calibrate cover fractions against NLA codes (47 fleet lakes), Snohomish density polygons, FWC; store `scheme` tag | Research | M |
| **B-11** | **Bloom vs plant ambiguity** — no validated discriminator | False vegetation in nutrient-rich warm lakes | Test red-edge/NDCI persistence/phenology discriminator on lakes with known blooms (e.g., Okeechobee, Lake Erie basin lakes in fleet) | Research | M |
| **B-12** | **22 lakes lack polygons; 3 suspect polygons** (Great Lakes, Great Salt Lake, Iliamna, Lake of the Woods, HI ponds; Shafer, Buckeye, Waiau) | Cell product needs a water mask | Coordinate with Lake Brain geometry work; mark as `NO_POLYGON` refusals meanwhile | Lake Brain owner | S |
| **B-13** | **Turbid/Southern reservoir and Plains truth absent** in our test | Transfer to the fleet's typical lake is unmeasured | Add TVA Guntersville / UMR / NLA turbid lakes to V2–V4 | Research / **M** | M |
| **B-14** | **Atmospheric correction choice over water** untested for vegetation | Literature shows >100 % red errors | Compare Sen2Cor L2A vs Polymer/C2RCC on 3–5 lakes for the surface rule | Research | M |
| **B-15** | **No user/field feedback loop** | "Too dense to bowfish" thresholds are anecdote | Define in-app/field feedback capture for a later phase (no iOS/Android work now) | Product / **M** | L |
| **B-16** | **Species/management regime flags absent** (grass carp, spraying, drawdown) | Dominant source of year-to-year amplitude error | Build a lake regime table from agency management pages (TVA, FWC, TPWD, Corps), start with ~40 lakes | Research | M |
| **B-17** | **Unread literature leads** — Remote Sensing 17(11):1894 (FL hydrilla S2 index), Baiyangdian phenology, Villa NDAVI formulas | Cheap accuracy/design gains | Read and record | Research | S |
| **B-18** | **NLA 2012/2022 not pulled; NLA×S2 not yet scored** | Biggest cross-region density/class dataset | Pull 2012/2022 phab; run V2 | Research | S |

## Critical path to a first useful Brain
`B-05 → B-18/V2 → B-10 → B-02 (Secchi interim) → B-04 → shadow run`. B-01 decides whether any "observed submerged" product exists; B-06/B-07 enlarge truth; B-03 enriches output but does not block a surface-reaching v1.

## Needs from Michael (summary)
1. Browser download of the UMN Minnesota dataset (B-07).
2. Data requests to TVA, SFWMD, TPWD, WI DNR (B-06).
3. Decision whether Clarity can expose a fleet-wide Secchi/clarity class with confidence (B-02).
4. Product decision on whether a labelled `POTENTIAL_HABITAT` ("could hold grass") is acceptable customer language, versus showing only observed surface cover.
