# WT-SAT-1 pre-registration (DRAFT, for Michael's sign-off)

**Status: DRAFT. Not frozen.** It is frozen only when Michael signs off on Sector_Ops #51 and the lake-list hash below is filled
in and committed before any scoring.

## Question

Does adding night-time satellite surface temperature (VIIRS, `jobs/lake-skin-temp`) make the Water Temp Brain's nightly value
closer to the real water temperature than the model alone, on lakes it has never been tuned on, forward in time?

Why a new test: WT-NOW-4 (Sector_Ops #51, 2026-11-14) failed when a fixed per-lake offset learned from sparse ~11 am Landsat
daytime readings was applied to other years (coverage 0.737, winter/spring bias about +2 °C). This test uses night readings
(no solar warm layer), one fleet-wide skin-to-water offset, and a recent-observation nudge instead of a fixed per-lake offset.

## Lakes (frozen before scoring)

- **Eligible:** every USGS continuous lake surface water-temperature sensor (parameter 00010, lake/reservoir sites) that
  reported on at least 60% of nights in the **past** window 2025-12-01 to 2026-04-30 and lies in a directory lake with at least
  3 pure-water 1 km cells. Eligibility uses only that past window, never the scored months.
- **Excluded:** the 4 lakes protected by earlier tests (as listed in the WT-NOW records).
- **One split rule (training vs scored):** sort the eligible lakes by SHA-256 of their lake id; every third lake (positions
  0, 3, 6, ...) is **training**, all others are **scored**. Training lakes fit the offset and `tau` and are never scored.
- The eligible list, the split and its SHA-256 are committed here before 2026-12-01: `lakes: <to fill>`, `sha256: <to fill>`.
- A scored lake whose sensor reports on fewer than 60% of scored nights is dropped from the result and listed as such.

## Arms (fixed now)

- **M:** the current Water Temp model only.
- **S:** M nudged toward the newest clear VIIRS night reading: value = M + w(age) x (satellite - offset - M), w = 1 on the
  night of the pass, halving every `tau` days (tau fitted on training data, then frozen).
- **S+G:** S plus GOES hourly readings, scored on tier-A lakes only (reported, not part of the pass/fail).

## Truth

The sensor's median water temperature between 00:00 and 04:00 local time on the scored night. Satellite readings never use
the sensor (sensor lakes are scored only on what S would show without the sensor).

## Pass (S against M, all must hold)

1. Nightly mean absolute error improves by at least 0.3 °C fleet-wide, over at least 15 lakes.
2. S's mean bias is within ±1.0 °C in each of: Dec-Feb, Mar-Apr.
3. S is worse than M by more than 0.5 °C mean absolute error on at most 20% of lakes.
4. Reported, not gating: the same numbers for lakes north of 37°N alone, and for ice nights (`possibleIce`).
   November 2026 is not scored (scoring starts 2026-12-01).

A failed bar is a failed test: no re-tuning against the scored months. A fix is a new pre-registration with new months.

## Training (before freezing)

- The fleet-wide skin-to-water offset and `tau` are fitted on 2018-2025 VIIRS night readings against the **training** lakes
  only, then frozen and recorded here with their values.
- The 2018-2025 readings come from the job's backfill mode:
  `skin_temp.py --start 2018-01-01 --end 2025-12-31 --lakes <training lakes> ...` (it skips nights already complete, so it
  can run in pieces).

## Owner decisions needed

- Sign-off on the bars above.
- Who scores it (a Claude session on the Mac mini) and when: scoring starts 2026-12-01; first read-out 2027-02-05 on
  December-January, final 2027-05-07 on December-April.
