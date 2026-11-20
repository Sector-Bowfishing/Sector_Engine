# lake-skin-temp (research lane, Mac mini / Sector Pulse)

Collects each lake's **night-time surface ("skin") temperature** from NASA's VIIRS daily 1 km night land-surface-temperature
grids. This is the observation side of the Water Temp satellite plan (owner direction, Sector_Ops #51, 2026-11-20: Brain
values come from real observations, not estimates).

- **Research only.** Writes local files and nothing else: no database write, no upload, no customer path. Wiring a reading
  into the Water Temp Brain is a later Swift change plus a knowledge release, after the pre-registered check WT-SAT-1
  (`docs/brains/WATER_TEMP_SAT_1_PREREGISTRATION_DRAFT.md`) passes.
- **Products:** `VNP21A1N` (Suomi NPP), `VJ121A1N` (NOAA-20), `VJ221A1N` (NOAA-21), collection 002, NASA LP DAAC. Each is one
  satellite's night pass per day, so a clear night can give up to three readings per lake.
- **Per lake:** cells whose whole 1 km footprint lies inside the lake outline (`jobs/lake-surface/polygons.geojson.gz`; no mixed
  shore pixel), mandatory QA `00` only, cells within `--cloud-buffer-px` (default 2) of a cloudy or not-produced cell dropped,
  then the median of what is left if at least `--min-pixels` (default 3) remain. Readings at or below 273.15 K carry
  `possibleIce: true`.
- **Coverage at 1 km:** 313 of the 599 outlined lakes have at least 3 pure-water cells (Guntersville 53, Hartwell 29); 68 have
  1-2; 218 have none (narrow or small lakes). Those need the 375 m swath product (step 2 below) or Landsat.
- **Latency:** the daily grids land about 6-10 days after the night they describe (VJ121A1N for 2026-11-10 was produced
  2026-11-16 and was the newest tile on 2026-11-20). So this lane builds history and the WT-SAT-1 evidence; it is not a
  tonight reading. The near-real-time path is step 2.

## Credentials

An **Earthdata Login user token** (urs.earthdata.nasa.gov → Generate Token; valid 60 days) in the environment variable
`EARTHDATA_TOKEN`. Pulse passes it from its Keychain item `earthdata-token` (service `com.rehtac.sectorpulse`). The token is
sent only to `*.earthdata.nasa.gov` / `*.earthdatacloud.nasa.gov` over HTTPS (never to the signed S3 redirect), and is never
printed, logged or written. Granule search (NASA CMR) is public and gets no token. Regenerate the token before it expires.

## Run

```bash
pip install -r requirements.txt   # numpy, h5py (wheels)
export EARTHDATA_TOKEN=...        # Pulse does this from the Keychain
python3 skin_temp.py --out /tmp/skin/out --archive /tmp/skin/archive --cache /tmp/skin/cache               # catch up the last 14 days
python3 skin_temp.py --out /tmp/skin/out --archive /tmp/skin/archive --cache /tmp/skin/cache --date 2026-11-10
python3 skin_temp.py --out /tmp/skin/out --archive /tmp/skin/archive --cache /tmp/skin/cache --search-only  # count granules, no token needed
python -m pytest -q                                                                                     # offline tests
```

Output:
- `{archive}/YYYY/YYYY-MM-DD.json`: one file per night, `schema lake-skin-temp-v1`, every lake reading per product
  (`status OK | CLOUDY_OR_SPARSE | NO_WATER_CELLS`, `skinTempK`, `skinTempF`, `iqrK`, `goodCells`, `waterCells`,
  `goodFraction`, `possibleIce`, `viewTimeLocalSolarH`). `complete: false` days (a tile missing or failed) are re-run on the
  next night; complete days are skipped.
- `{out}/lake-skin-temp.json`: the run summary (lakes, days, granule counts, seconds).

## Expected run time (estimate, to be measured in the one-week dry run)

- Lake windows: about 70 s of CPU per run for all 599 outlines.
- Downloads: 17 tiles cover every outlined lake. Up to 3 products x 17 tiles per night, each tile file a few tens of MB
  (estimate), so roughly 0.5-1.5 GB per night, deleted after extraction (`--keep-downloads` keeps them).
- The first run catches up 14 nights, so it is the slowest. Allow 30-60 min; later nights are a few minutes.

## Next steps (not in this version)

1. **GOES hourly** (NOAA GOES-18/19 ABI land-surface temperature on AWS open data, no key) for the ~76 lakes large enough
   for its ~2 km pixels: same-day readings.
2. **Near-real-time 375 m swaths** (LANCE `VJ121IMG_NRT`, about 1-2 h after the pass): tonight's reading, and coverage for
   the narrow lakes the 1 km grid can't see. Needs swath geolocation, not the sinusoidal grid used here.
3. **GLERL GLSEA** for the Great Lakes entries, which have no outline here.
4. Feed WT-SAT-1, then (if it passes) the Water Temp Brain.
