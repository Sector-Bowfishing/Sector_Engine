# Fleet NBM sampling — validation (offline, read-only, not wired)

Code: `jobs/wind-hourly/sector_wind/fleet_sampling.py`; checks `research/fleet_sampling_validation.py` (data `data/fleet_sampling_validation.json`) and `tests/test_adoption.py`. Uses one pre-H2 archived cycle (2026-09-01 12Z +6 h) purely as a real NBM CONUS grid and field; no live or sealed data.

## Result (real 2.5 km Lambert grid, 621 directory lake points)
| Check | Result |
|---|---|
| Lakes in the CONUS grid | 600 (21 AK/HI are outside; marked `forecastDomain` in the manifest) |
| Match to the production per-lake cut-out interpolation | max speed difference **0.005 m/s**; max direction difference **0.5°** (rounding); **0** direction-presence mismatches |
| Interpolation method | bilinear for all 600 (0 nearest-cell fallbacks) |
| Determinism | identical index on a second build |
| Cost | one-time point index **4.7 s** (83 KB json), one lead for 600 lakes **8.5 ms**, 36 leads **0.23 s** |
| Output size | ≈ 0.5 MB json per cycle uncompressed for 600 lakes × 36 leads × 4 vars (≈ 0.13 MB gz estimate in the cost model) |
| Provider calls / GRIB reads added | **0 / 0** (the CONUS fields are already decoded once per cycle) |
| Objects per day vs per-lake cut-outs | **24 vs 14,904** (621 lakes × 24 cycles) |

## A defect found and fixed
The first draft derived direction presence from the *blended* speed; the archive masks direction per cell where speed < 0.5 m/s before storing. 10 lakes differed in direction presence. `sample_lead` now applies the same per-cell calm rule (`CALM_MS`), the validation compares against the masked archive form, and a regression test covers it. Unknown (NaN) stays unknown.

## What is not done
- Not wired into `ingest.py`/`live.py` (customer-adjacent production behavior; deploy blocked on `feat/cost-efficient-scheduling`). Wiring is ≈ 15 lines after `ingest_nbm_cycle`: build the cached index, call `sample_lead` per lead, `store.put_json("nbm_fleet/…")`; the state builder then reads the fleet object for non-cut-out lakes.
- AK/HI NBM products (21 lakes) untested; qmd percentile fields are sampled when present (`p90`) but not exercised on the real grid here (the same gather path).
- Real wall-clock on the Cloud Run job (memory for the full CONUS array is already paid by the current decode).
