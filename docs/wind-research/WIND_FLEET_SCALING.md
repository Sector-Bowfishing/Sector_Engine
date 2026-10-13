# Wind Brain — fleet scaling (621 lakes)

Method: weather grid + canonical lake geometry, no per-lake hand configuration. Numbers from `data/fleet_summary.json` and `data/fleet_fetch_by_lake.json` (per-lake 16-direction median/p90 fetch and class shares at 8/12/18 mph).

## Capability counts
| Capability | Lakes | Basis |
|---|---:|---|
| Directory lakes | 621 | Engine directory 2026-10-13 |
| **Direction / speed / gust / hourly forecast** | **~621 by design, 4 live today** | NBM v5.0 is a CONUS grid (plus AK/HI/PR regional grids); one pull per cycle sampled at each lake point. The archive only cuts out 4 lakes today. 21 lakes are AK (12) or HI (9): need the NBM Alaska/Hawaii domains (not tested here). Direction/speed accuracy is validated at **4 lakes / 8 land stations** only; applying it to other regions is an extrapolation. |
| Engine polygon exists | 599 | Lake Brain geometry; 22 have none (Great Lakes, Great Salt Lake, Green Bay, Lake of the Woods, several HI/AK) |
| Frozen audited fetch tables (QA'd) | 74 (4 dev + 70 profiled) | existing |
| **Polygon-estimated fetch computed** | **595** | this campaign; 4 fail (Waiau HI, Shafer IN, Devils ND, Buckeye OH) |
| …with Lake Brain geometry confidence HIGH or MEDIUM | **544** (351 HIGH) | `lake_geometry_flags.csv`; 53 LOW excluded |
| **New beyond frozen tables** | **479** (309 HIGH-confidence) | 544 − 65 overlap |
| Bank classification (DIRECT/CROSS/PROTECTED/HIGH FETCH) from polygon | 544 (estimate tier) | needs bank facing from the polygon edge (not yet coded) |
| Lakes where tonight's wind makes bank choice matter (max p90 fetch ≥ 1 km) | 430 of 544 | 113 are 300 m–1 km, 1 is pond-like |
| Lakes with ≥ 10% of banks HIGH at 12 mph / 18 mph | 76 / 250 of 544 | reference-wind shares |

## Quality tiers (do not mix them)
1. **AUDITED** (74): frozen tables, SHA-256 verified, QA'd against exact remeasurement (B1) — the only tier with a published QA claim.
2. **ESTIMATED** (up to 544): polygon fetch, same physics, *different polygon and 5-ray method*; agrees in magnitude (median log ratio −0.06 on open lakes) but **failed** the pre-registered direction-rank agreement (G2). Must be labelled as an estimate and shown with a coarser vocabulary (3 classes, no per-bank "best bank" claims) until a matched per-bank comparison passes.
3. **POINT-ONLY** (the rest, 77 incl. missing/LOW geometry): wind direction/speed/trend/risk flag only; no bank classes. Never "Protected".

## Cost / feasibility
- Forecast: one NBM pull per cycle for CONUS; sampling 621 points is trivial. Today's per-lake cut-out design is what limits coverage, not the data.
- Fetch: ≈ 4 s per lake single-core → the fleet in under an hour; re-run only on geometry change (hash like the existing profile SHA).
- Geometry owner is the Lake Registry/Lake Brain, not Wind (ownership matrix item "Wind fetch-table geometry"): the generator currently lives in the iOS repo and should move to Engine `scripts/` when rebuilt; the polygon route reads the same Lake Brain polygons the other Brains use, which removes the NHD-HR/HU4 staging dependency.

## Distribution facts useful for design
- Fleet mean class share (544 lakes): 8 mph LOW 63% / MOD 36% / HIGH 1%; 12 mph 52 / 43 / 4.5; 18 mph 42 / 45 / 12.5. Most lakes are mostly "manageable" at ordinary bowfishing winds; the discriminating work is at 12–18 mph.
- Dominant (p90) exposure direction is spread over all 16 sectors (max sector 10% of lakes): no single prevailing exposure to hard-code.
- Monotonicity (G4): HIGH share is non-decreasing 8 → 12 → 18 mph on **595/595** lakes ✔.

## Gaps
Great Lakes/large natural lakes with no polygon; AK/HI forecast domains; 53 LOW-confidence polygons; narrow-water banks below 20 m raster; no per-bank facing from polygons yet; no check that polygon fetch handles reservoir arms at full-pool vs lower pool (geometry is a single static outline; seasonal drawdown changes fetch — a depth/level Brain interaction).
