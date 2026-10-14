# Fleet NBM sampling (foundation; not wired)

`sector_wind/fleet_sampling.py` + `brain/data/geometry_tiers.json`.

## Problem
`ingest_nbm_cycle` already decodes each CONUS field once per cycle (WIND/WDIR/GUST, plus qmd percentiles at 00/06/12/18Z) but writes **one cut-out object per lake**. Scaled to the fleet that is 621 × 24 = 14,904 small GCS writes/day plus per-lake bundle code.

## Design
One point-sampled object per cycle: `nbm_fleet/<YYYYMMDDHH>.json.gz` → `{lakeId: {speedMS[], dirFromDeg[], gustMS[], speedP90[]}}`, fed by per-lake bilinear weights computed **once per grid** (4 cells each, stored in a sidecar index). Same bilinear scalar blend and direction-from-blended-u/v as today; tested to match the per-lake cut-out interpolation.
- **Extra GRIB reads: 0. Extra network calls: 0.** Cost per cycle is a numpy gather over ≈ 2,500 values per lead.
- **No job per lake.** It lives inside the existing `wind-hourly` execution and honours its `/jobs` contract and early-exit (a fully archived cycle is not re-read).
- Size ≈ 0.1 MB/cycle gz (`cost_model`), a few GB/month at most.
- Forecast domains: CONUS 600 lakes; AK 12 and HI 9 need the NBM AK/HI products (not tested here; manifest marks `forecastDomain`).
- Lake point = directory coordinate (126 are off-water by Lake Brain flags; at 2.5 km the cell is unaffected but the **state must say representative point**, as it does).

## Wiring plan (needs approval; changes wind-hourly)
1. After `ingest_nbm_cycle`, call `build_point_index` (cached) and `sample_lead` for every lead; write the fleet object.
2. `build_state` reads `nbm_fleet` for lakes not in `lakes.json`; the four live lakes keep their cut-outs until the fleet reader reproduces them bit-for-bit on shadow runs.
3. Publish `POINT_ONLY` lakes' wind/tonight; publish exposure only for AUDITED/ESTIMATED tiers.
4. Orchestrator registration: no new schedule; same job, same cadence.

## Tiers (manifest, 621 lakes)
AUDITED 74 · ESTIMATED 473 (Lake Registry v1 confidence HIGH/MEDIUM, ≥ 20 sampled banks, raster ≤ 40 m) · POINT_ONLY 74 (37 LOW confidence, 28 no registry geometry, 9 coarse raster) — recomputed 2026-10-13 from the published registry; see `WIND_FLEET_EXPOSURE_READINESS.md`. Regenerate with `python -m sector_wind.brain.fleet build …`; the diff is the review.
