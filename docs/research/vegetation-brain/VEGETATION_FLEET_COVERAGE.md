# Vegetation Brain — Fleet Coverage (621 lakes)

**RESEARCH ONLY. Proposed Brain.** Machine-readable matrix: [`data/fleet_matrix.csv`](data/fleet_matrix.csv), built by [`scripts/fleet_matrix.py`](scripts/fleet_matrix.py) from the production lake directory snapshot (621 lakes, 2026-10-13), engine polygons (599), EPA NLA 2017 sites, FWC LTM points, and the modelled shallow-area fractions from the Depth research branch (GloBathy-derived — *modelled, low confidence*).

## 1. What the matrix does and does not claim
- **Measured:** polygon area (this campaign's geometry), whether an NLA 2017 sampling site falls inside the lake polygon, whether FWC point-intercept data names the lake.
- **Modelled:** shallow-water fraction (≤1.8 m) from global bathymetry models — a proxy for "area where submerged vegetation can physically exist". Not validated per lake.
- **Rule-based (not measured):** region, ice-months estimate, state-level survey availability.
- **Not available fleet-wide:** water clarity/Secchi. The Water Clarity Brain does not publish a fleet-wide Secchi. Therefore **no lake is declared "submerged-detectable"**; the best tier is "S2 — shallow candidate, clarity unknown".

## 2. Fleet totals

| Dimension | Count | Notes |
|---|---|---|
| Lakes in directory | 621 | 12/state typical, 9–15 |
| Polygons available | 599 | 22 missing: Great Lakes (Erie, Michigan, Huron, Superior, Ontario, Green Bay), Lake of the Woods, Great Salt Lake, Iliamna, Chickahominy, 5 Hawaii ponds |
| Polygon area < 0.5 km² | 15 | too small for 10 m pixels; several DE ponds. Three polygons compute to ≈0 km² (Lake Shafer IN, Buckeye Lake OH, Lake Waiau HI) — **geometry suspect**, route to Lake Brain geometry flags |
| **Emergent/floating feasibility** — HIGH (≥5 km²) | **498** | S2 10 m resolves shoreline belts and mats |
| MEDIUM (0.5–5 km², mixed pixels) | 86 | usable with density caveats |
| LOW / UNKNOWN | 15 / 22 | |
| **Submerged tier S2** (≥10 % of area ≤1.8 m, modelled; clarity unknown) | **474** | candidate zones only |
| S1/S1b (little modelled shallow area) | 110 | submerged cover unlikely to matter at lake scale |
| S0 (too small) | 15 | |
| Validation now (NLA or FWC data in hand, joined) | **77** | 69 NLA-joined + 10 FWC-point lakes (overlap 2) |
| Validation possible with request / browser download | 56 | MN (UMN dataset), WI (DNR), TVA, UMR, TX |
| NWI prior only | 488 | no independent survey path today |

## 3. By region

| Region | Lakes | Emergent/floating HIGH | Submerged S2 candidate | Validatable now | Validatable w/ request | Est. ice months |
|---|---|---|---|---|---|---|
| Gulf (FL, LA) | 25 | 25 | 12 | 11 | 0 | 0 |
| Southeast (GA SC NC AL MS VA, east TX) | 80 | 77 | 66 | 10 | 14 | 0 |
| Mid-South (TN KY AR WV) | 50 | 42 | 48 | 3 | 9 | 1 |
| Midwest (OH IN IL IA MO) | 62 | 51 | 50 | 7 | 1 | 3 |
| Upper Midwest / Great Lakes (MN WI MI) | 41 | 32 | 28 | 0 | 27 | 5 |
| Northeast (11 states) | 138 | 75 | 106 | 13 | 0 | 4 |
| Plains (KS NE SD ND OK, west TX) | 69 | 63 | 63 | 14 | 5 | 3 |
| Mountain West (MT WY CO ID UT) | 62 | 57 | 43 | 7 | 0 | 5 |
| Pacific NW (WA OR) | 27 | 25 | 22 | 3 | 0 | 2 |
| California | 12 | 12 | 9 | 1 | 0 | 1 |
| Southwest (AZ NM NV) | 34 | 28 | 23 | 8 | 0 | 1 |
| Alaska | 12 | 11 | 3 | 0 | 0 | 7 |
| Hawaii | 9 | 0 | 1 | 0 | 0 | 0 |

(Ice-months and region are rule-of-thumb assignments in the script; replace with measured ice flags from satellite once the observer exists.)

## 4. Lakes best suited to validate *first* (all verified in the matrix)
- **Florida, FWC LTM points in hand:** Okeechobee, Kissimmee, Istokpoga, Harris, Griffin, Apopka, Orange, Lochloosa, George, Crescent.
- **NLA 2017 with real submergent cover rows in the fleet** (examples, mean submergent code 0–4): Nickajack TN 3.5, Concord Pond DE 3.3, Fish Lake UT 3.2, Piney Run MD 2.7, Bitter Lake SD 2.5, Tippecanoe IN 2.3, Habeeb MD 2.2, Lake Zoar CT 1.7, Griffin FL 1.4, Keuka NY 1.4, Wawasee IN 1.4 — plus 17 near-zero lakes (Allatoona, Monroe, Keystone, Skiatook, Jocassee, Philpott, Burnsville…) that are valuable **negative controls**.
- **Request-based but high value:** TVA reservoirs (15 fleet lakes incl. Guntersville, Wheeler, Pickwick, Kentucky Lake, Chickamauga, Watts Bar), Minnesota (UMN dataset), Wisconsin PI surveys, Texas TPWD, SFWMD Okeechobee.

## 5. Per-lake best source (decision rule used in the CSV)
1. Dated survey in hand (FWC/NLA) → VALIDATE with it, OBSERVE with Sentinel-2.
2. Request-only survey path exists → pursue, OBSERVE with Sentinel-2 meanwhile.
3. Otherwise NWI as prior; Sentinel-2 surface-reaching observer with `confidence=UNVALIDATED_LAKE`.
Confidence for any lake without validation is capped by the cross-lake transfer penalty observed in the empirical test (see `VEGETATION_VALIDATION_STRATEGY.md`).

## 6. Fleet-scale feasibility verdict
- **Emergent/floating/topped-out mats: feasible for ≈500 lakes (≈580 with density caveats)** using open Sentinel-2 — the same data source Clarity already pulls.
- **Submerged: only a "SAV-capable zone / potential" product is feasible fleet-wide; an "observed submerged" product is feasible only on lakes with demonstrated clarity and local validation (a few tens at most today).**
- **Seasonal expectation:** feasible fleet-wide as a prior, but unvalidated; needs the S2/Landsat history back-test (see `VEGETATION_SEASONAL_MODEL.md`).
- **Gaps:** 22 lakes without polygons (Great Lakes, a few specials) need geometry before any cell product; clarity is the dominant unknown for 474 submerged-candidate lakes.
