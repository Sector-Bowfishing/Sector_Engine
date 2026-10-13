# Vegetation Brain — Emergent, Floating and Flooded Vegetation Research

**RESEARCH ONLY. Proposed Brain.** These are the classes Sentinel-2 can see — the practical heart of a first Vegetation Brain.

## 1. Scalable accuracy summary

| Class | Sentinel-2 evidence | Our test | Fleet-scale verdict |
|---|---|---|---|
| **Floating-leaved** (lily, lotus, watershield) | 78 % point-validated, 4 Chinese lakes [V] | **AUC 0.98–0.995, F1 0.94–0.97 (leave-one-lake-out)** on clear PNW lakes with dated polygons | **Good where water is dark/clear and beds are ≥ a few pixels.** Small beds (Storm: 20 px) and shore-adjacent beds degrade (Storm AUC 0.54 matched) |
| **Free-floating mats** (hyacinth, lettuce, salvinia, duckweed) | RF class accuracy 79–95 %, OA ~90 % [V] | not separately tested | Good; confounded with bloom scums (no validated discriminator) |
| **Emergent** (cattail, bulrush, phragmites, cutgrass) | 91 % point-validated [V] | FL surface (floating + emergent) AUC 0.65–0.67 shore-matched; recall 0.60 at Sector rule, 0.85 within 30 m of shore, 0.35 beyond 120 m | **Good as shoreline belts; narrow belts (<10–20 m) are mixed pixels**; presence-only FL labels depress measured precision |
| **Topped-out submerged canopy** (hydrilla/milfoil mats) | behaves like floating mats [B] | not separable from mats in surface indices | Detect as `surfaceTopped`; species unknown |
| **Flooded terrestrial** (grass, shrub, timber) | optical poor–moderate; flood index helped Dongting [V]; SAR L-band 83–86 % [V] | not tested | Needs Lake Brain pool anomaly + DEM/slope + SAR/JRC seasonality; start as `POTENTIAL_HABITAT` |

## 2. Indicators that worked and did not (empirical)
- **Best:** NDAVI (0.995), FAI (0.992), NDVI (0.982) on PNW floating-leaf; any of the three is acceptable in clear water — consistent choice matters more than the choice.
- **Not good:** red-edge NDRE alone (0.81/0.61); raw NIR/SWIR look strong unmatched (0.998) only because of shoreline adjacency — a **trap to avoid in any future validation**.
- **Sector rule NDVI ≥ 0.30:** recall 0.99 (floating-leaf) but 9.9 % open-water false positives per pixel; use a dark-water guard + cell vote + persistence. (Clarity's FAI>0.005 term is a water-quality gate, not a vegetation test; as a vegetation add-on it raised false positives to 18 % single date.)

## 3. Density from satellite
- **Method:** sub-pixel plant fraction per ~50 m cell (fraction of plant-flagged 10 m pixels, optionally weighted by index strength), mapped to `SCATTERED/MODERATE/DENSE` with stored cutoffs.
- **Calibration targets:** NLA cover codes (0, <10, 10–40, 40–75, >75 %) joined to 47 fleet lakes with cover rows; FWC point richness; Snohomish density polygons.
- **Literature:** NDAVI discriminates low-density (FC <40–50 %), WAVI for higher density [V]; expect ±1 class error [U].
- **Caveat:** surface density ≠ biovolume. Agency PAC and PVI can diverge strongly (95.8 % vs 53.5 % in a Northeast hydrilla survey) [S].

## 4. Bowfishing meaning of each surface class
- Dense floating mats and emergent walls impede boats and arrows [A]; sparse–moderate pockets and **edges** are likely productive [A]. No quantitative source exists — keep tagged anecdotal; cutoffs for "likely too dense" should be tuned from user feedback and agency complaints, not asserted.
- Standing dead emergents in winter stay physically present while NDVI reads "dormant" — the Brain should keep a `lastGreen` memory per cell rather than reporting "none" in winter.

## 5. Failure modes to design out
1. **Algal bloom vs plant mat** → `BLOOM_AMBIGUOUS` flag when FAI is high but persistence/phenology unsupportive.
2. **Haze/thin cloud over dark water** reading NDVI 0.12–0.19 (documented by Clarity authors) → dark-water guard.
3. **Shoreline trees and bank grass inside a 10 m pixel** → erode shoreline; refuse narrow arms.
4. **Sun glint / whitecaps** → wind-based and scene-based refusal.
5. **Ice/snow** (north) → seasonal mask and `ICE` refusal.
6. **Exposed lakebed in drawdown** reading as vegetation → mask via pool anomaly / JRC occurrence ("terrestrial", not aquatic).
7. **Date mismatch** — never present an old observation as current; always carry age.

## 6. Flooded-terrestrial candidate recipe (for experimentation)
`candidate = (pool_anomaly > +0.5 ft) AND (land-cover in {grass, shrub, wetland, forest} in NLCD/NWI within the flooded contour) AND (S1 water frequency increased vs seasonal baseline)`. Output tier `POTENTIAL_HABITAT` until validated against flood-event imagery (S1 water extent) and agency flood-pool vegetation reports. Needs DEM/contours (Depth Brain) and Lake Brain pool anomaly.
