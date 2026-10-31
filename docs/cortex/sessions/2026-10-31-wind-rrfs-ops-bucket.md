# Wind research: RRFS/REFS collector on the operational bucket + flagged backfill: Session Record

```text
Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/wind-rrfs-ops-bucket-2026-10-31 · Start commit: main 7aefa736 · Date: 2026-10-31
```

## 1. Scope
Owner-approved (Sector_Ops 27, per its latest comment): fix the research-only RRFS/REFS collector's bucket, prefixes and patterns with a test, then backfill the missed cycles from 2026-08-12 as point samples, flagged as backfilled. Research lane only. No production, no Firebase, no other Wind research, no scoring (the H2 holdout stays sealed).

## 2. Findings
| ID | Finding | Evidence |
|---|---|---|
| RR-1 | The collector listed only the pre-operational bucket; operational cycles are in `noaa-rrfs-ops-pds` (rrfs./refs. from 2026-08-12, rrfsens. from 2026-09-09) | listing recorded in `research/tools/tests/fixtures/rrfs_ops_listing_2026103012.json` |
| RR-2 | In the operational layout, 10 m U/V and surface GUST are in `2dfld` files; `prslev` has pressure levels only (10 mb). The old deterministic pattern pointed at `prslev` | `.idx` of `rrfs.t12z.prslev.3km.f003.conus` vs `rrfs.t12z.2dfld.3km.f003.conus` |
| RR-3 | Members live in `rrfsens.YYYYMMDD/HH/mNNN/rrfs.tHHz.mNNN.2dfldnomads.3km.fNNN.conus.grib2` (5 members); the old member pattern matches none | fixture; `test_the_old_patterns_find_nothing_usable_in_the_operational_layout` |
| RR-4 | Member `.idx` lines carry an `ENS=+N` tail; the decoder's exact-tail `find(..., "")` would not find their messages | `test_member_messages_are_found_by_their_ens_tail` |
| RR-5 | Ledger: 525 checks, all "not published"; 0 RRFS/REFS rows in the archive | `active/rrfs_ledger.jsonl` |

## 3. Changes (research lane: `brains/wind/research/tools/sector_wind_research/rrfs.py`, decoder `rrfs 1.1.0`)
Operational bucket first, with both prefixes merged, and the pre-operational bucket and NOMADS kept as fallbacks; operational `2dfld` / `2dfldnomads` patterns; ENS-tail message lookup; `backfill --start --end`, which writes point samples only (no GRIB kept), puts its rows in `normalized/rrfs-backfill-<runId>.jsonl` flagged `backfill: true, asIssued: false` with the real retrievedAt, writes ledger entries flagged `backfill: true`, is idempotent, records a failing cycle as `error` (retried next run, never archived) and never reaches beyond now. The live `collect` behaviour is unchanged except for the corrected discovery. The production `sector_wind` package is untouched.

## 4. Verification
New `research/tools/tests/test_rrfs.py` (7) against the recorded listing; Wind suite and the package-boundary tests pass; engineering status regenerated. A real decode of an operational `2dfld` file (`selftest`) gives the 12 points with earth-relative winds and gusts.

## 5. Backfill run and results
Recorded on Sector_Ops 27.
