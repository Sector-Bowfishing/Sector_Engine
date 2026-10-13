# Depth Existing Asset Audit

**Depth Brain does not currently exist. This audit covers reusable evidence and assets that could support a future Depth Brain.**

Audit date 2026-10-13. Branch `docs/depth-brain-research` (based on `main`, not on another Brain research branch). Scope searched: this repo and the other Sector_Engine worktrees, the Lake Brain and Water Temp research branches, `Sector_Research_Data/`, the iOS (`sector-intel-phase3`), Android, Web (Ops) and macOS (Sweep) repos. Nothing was changed.

## Summary

| # | Asset | Where | What it is | Depth value | Status |
|---|---|---|---|---|---|
| 1 | **USACE IENC 9 ft contour, Guntersville only** (2007 survey) | iOS `Sector/Assets.xcassets/FishIntel/Guntersville*Geometry.dataset` (6,504 segments of 200 m); `Sector/FishIntel/Lake/LakeRegistry.swift:172`; Phase 1-3 and Pre-Phase-10 handoffs | One binary contour at 2.74 m (9 ft) from S-57 DEPARE/DEPCNT: segments classified `shallow` / `deep` / `unavailable`. Counts: 4,059 shallow, 312 deep, 2,133 unknown (67 % coverage). **No depth surface, no SOUNDG.** | Real measured shallow/deep split at one level, the only measured depth evidence in any Sector app. A Tier B-/C asset for one lake and a proof that the **IENC product exists for navigable USACE waterways** (a scalable lead; see source matrix). | Shipped in iOS Fish Intelligence, shoreline segments only. Not a Brain. |
| 2 | **GLOBathy** basic parameters (1.4 M lakes) and h-A-V relationships | `Sector_Research_Data/lake-brain/context/globathy/` (CSV bundle 115 MB, NetCDF 525 MB); copy in `water-temp-brain/depth_spatial/globathy/` | Modeled Dmax, area, power-law A(h); keyed by HydroLAKES id | Candidate fallback; Lake Brain found Guntersville Dmax 46 m modeled vs about 20 m real; relative area per ft Spearman 0.33 | Cached; evaluated in `DEPTH_BRAIN_GLOBATHY_EVALUATION.md` |
| 3 | **HydroLAKES** points/polygons | `lake-brain/context/hydrolakes`, `lake-brain/geometry/hydrolakes` (2.2 GB) | Lake_type, volume, depth_avg (modeled), elevation, shore development; 554 of 621 lakes matched | Match key for GLOBathy; `Depth_avg` modeled (independent validation R2 0.46 per the Water Temp thread) | Cached |
| 4 | **Fleet depth proxy table** | Water Temp research branch `docs/research/water-temp/data/depth_proxy_candidates.csv`, builder `scripts/depth_spatial_depth_proxy_build.py` | 621 rows: `mean_depth_m` from HydroLAKES Depth_avg (335) or NID normal storage / surface area (245); 41 UNKNOWN; every row flagged MODELED with a x1.5-x2.4 uncertainty note | Reusable mean-depth prior; **mean depth only**, no distribution, not bowfishing-grade | Research only, not merged |
| 5 | **Lake Brain fleet features** | `docs/research/lake-brain/data/lake_features.csv` (Lake Brain branch) | `mean_depth_m` 577, `glob_dmax_m`, `glob_shallow_frac_1p2m`, `frac_within_100m`, `frac_narrow_300m`, `n_narrow_arms`, `hl_match`, NID dam height | Geometry-only shallow proxies; shore-band and narrow-water fractions are free for 599 lakes | Research branch only |
| 6 | **3DEP shoreline slope** (4 offsets x about 700 points, 56 lakes) | `research/lake-brain/context_shore_dem.py`, `context/shore_dem*.json`, `shore_dem_val_*.json` | Median slope 10-60 m outside the shoreline, horizontal run per vertical ft | The one shallow-water proxy that validated: Spearman 0.76, log-Pearson 0.84, 82 % within x2 against CWMS stage-area slope (n=33). Predicts area change per ft of pool | Validated for lake-level response, not for depth distribution |
| 7 | **CWMS stage-area truth** | `lake-brain/context/hypso_truth.json`, `hypso_pairs.json`; scripts `context_hypso_*.py` | Measured storage and pool elevation pairs for 53 USACE projects, 33 usable fits | First real hypsometric truth Sector owns (area gained per foot near full pool) | Cached; validation set |
| 8 | **Pool reference table** `full_pool.csv` | `docs/data/full_pool.csv` (on main) | 425 lakes: full-pool elevation, basis, confidence (353 high, 34 med, 25 low), 62 with winter pool | Datum anchor for **effective depth** (reference level vs current level) | On main |
| 9 | **Lake polygons (599)** | `lake-brain/geometry/engine_polygons_599.geojson.gz` | Canonical-ish outlines with provenance flags | Basis for any shoreline-band or flat analysis | Cached |
| 10 | **Lake level / pool history** | Lake Brain `history/`, `plan/` data and ledger; production Lake Brain level fields (`poolBasis`, `apiLevel`) | Current level, guide-curve/plan evidence | Level side of the effective-depth equation (owned by Lake Brain) | Research / production |
| 11 | **JRC Global Surface Water** tiles | `lake-brain/context/gsw`, `lake-brain/geometry/gsw` (about 1 GB) | Occurrence / seasonality | Confounded by vegetation and clarity; screening only | Cached |
| 12 | **NWI aquatic bed / littoral** | `context/nwi_features.json` | Mapped aquatic bed (Guntersville 10.6 %) | Vegetation, not depth | Cached |
| 13 | **Water Clarity `grassPct`** | production Clarity Brain | Satellite vegetated-shallows share, 566 lakes | Indirect shallow indicator (vegetation lives shallow); not to be rebuilt in Depth | Production (another Brain) |
| 14 | **iOS FishIntel depth consumers** | `HuntabilityEngine`, `AttractionEngine`, `SegmentAssociator`, `FishIntelMapModel` | Spawning depth band 1.2-6.1 m, `workableShallows`; depth is a *required* factor and is renormalised away when unmeasured | **Demand-side evidence**: shows exactly which depth question the app already asks and the honest handling of "unmeasured" | Production client |
| 15 | **NID dam height / storage** | `lake-brain/context/nid` | Dam height, normal storage | Upper bound on Dmax for dammed reservoirs; mean depth = storage / area | Cached |

## Searched and found nothing

* No bathymetry raster, depth contour set, TIN or SOUNDG layer in any Sector repo other than the Guntersville IENC derived segments.
* No existing DEM-derived bottom elevation, no sonar or user-contributed depth data (Android, iOS, Web, Ops, Sweep).
* Android `ShorelineSegment.kt`/`LakeLoader.kt` only mirror the iOS depth fields (`DepthClass { shallow, deep, unknown }`).
* No "Depth" node in RTDB paths, engine code (`Sources`, `jobs`) or Ops pages (Ops `BrainPage.tsx` mentions depth only as Water Temp/Intelligence inputs).
* The Water Temp thread's documents refer to the depth proxy as an input; they do not publish depth.

## What this means for Depth Brain

1. **The only measured depth Sector owns is one binary contour for one lake.** Everything else is modeled or proxy.
2. **Lake-level response (area change per foot) is the best-validated fleet-wide capability**, and the pool reference table (425 lakes) makes a delta-depth (effective-depth shift) capability close at hand.
3. The existing app already needs 1.2-6.1 m spawning-band classification and handles "unmeasured" correctly, so a Depth Brain should emit an explicit `unknown` rather than guess.
4. The IENC finding suggests the USACE navigation-channel S-57 charts are a lead for broader coverage (tested in the source scouting thread; see the data source matrix).
