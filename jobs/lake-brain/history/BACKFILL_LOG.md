# Lake Brain deep TVA history backfill: log

Script: `jobs/lake-brain/history/backfill_tva_deep.py` (dry-run by default, `--write` backs up, uploads with `--if-generation-match`, reads back and verifies md5 and row count).
No secrets in this file. Entries below the line are appended by the script when it writes.

Dry run before the write (2026-10-13, all checks passed for all four lakes): see the summary section at the end of this file.

---

### Guntersville|AL (GVDA1) written 20261013T160437Z

```json
{
 "merged_file": {
  "rows": 7408,
  "bytes": 265958,
  "md5_b64": "Hdy3XmhtmGuA5db2VxBasA==",
  "sha256": "f5bc4326a331dbe6a84eb144e5ec47fffc231ab58f8eaf66e0c587199c71f1eb",
  "first": "2005-01-30",
  "last": "2026-10-13"
 },
 "written": {
  "object": "gs://sector-lake-brain/history/Guntersville_AL/daily.csv",
  "backup": "gs://sector-lake-brain/history_backup/Guntersville_AL/daily.20261013T160437Z.csv",
  "backup_generation": "1791907479264004",
  "backup_size": 28670,
  "generation_before": "1791869696171324",
  "generation_after": "1791907482025579",
  "size_after": 265958,
  "size_before": 28670,
  "md5_b64": "Hdy3XmhtmGuA5db2VxBasA==",
  "crc32c": "HrlOkw==",
  "verify": {
   "md5_ok": true,
   "rows_ok": true,
   "rows": 7408,
   "size": 265958
  },
  "utc": "20261013T160437Z"
 },
 "rows_by_source": {
  "nws:rvdhun:GVDA1": 5964,
  "nws:hads:GVDA1:HP": 793,
  "tva:operating-guide:GVDA1": 651
 },
 "complete_years_before": [
  2025
 ],
 "status_before": "INSUFFICIENT",
 "complete_years_after": [
  2007,
  2008,
  2009,
  2010,
  2011,
  2012,
  2013,
  2014,
  2015,
  2016,
  2017,
  2018,
  2019,
  2020,
  2023,
  2024,
  2025
 ],
 "status_after": "SUFFICIENT"
}
```

### Wheeler|AL (WHLA1) written 20261013T160446Z

```json
{
 "merged_file": {
  "rows": 7140,
  "bytes": 256578,
  "md5_b64": "EuBHceUimvi21Kr0a6qPRg==",
  "sha256": "4ddea6492deaba71920cb5e983b65545609795f4b748395b7c338aca9d8487bc",
  "first": "2005-11-23",
  "last": "2026-10-13"
 },
 "written": {
  "object": "gs://sector-lake-brain/history/Wheeler_AL/daily.csv",
  "backup": "gs://sector-lake-brain/history_backup/Wheeler_AL/daily.20261013T160446Z.csv",
  "backup_generation": "1791907487904586",
  "backup_size": 28670,
  "generation_before": "1791869696239933",
  "generation_after": "1791907490790297",
  "size_after": 256578,
  "size_before": 28670,
  "md5_b64": "EuBHceUimvi21Kr0a6qPRg==",
  "crc32c": "RRrj8w==",
  "verify": {
   "md5_ok": true,
   "rows_ok": true,
   "rows": 7140,
   "size": 256578
  },
  "utc": "20261013T160446Z"
 },
 "rows_by_source": {
  "nws:rvdhun:WHLA1": 5696,
  "nws:hads:WHLA1:HP": 793,
  "tva:operating-guide:WHLA1": 651
 },
 "complete_years_before": [
  2025
 ],
 "status_before": "INSUFFICIENT",
 "complete_years_after": [
  2006,
  2007,
  2008,
  2009,
  2010,
  2011,
  2012,
  2013,
  2014,
  2015,
  2016,
  2017,
  2018,
  2019,
  2020,
  2023,
  2024,
  2025
 ],
 "status_after": "SUFFICIENT"
}
```

### Wilson|AL (WLSA1) written 20261013T160457Z

```json
{
 "merged_file": {
  "rows": 7410,
  "bytes": 266028,
  "md5_b64": "RiNYqTJNaYzvX7veUqeYqA==",
  "sha256": "6f8cc38b770c8df75b30c32bebab295b5c347f6211501f1f34fd2fe2ceee01c2",
  "first": "2005-01-30",
  "last": "2026-10-13"
 },
 "written": {
  "object": "gs://sector-lake-brain/history/Wilson_AL/daily.csv",
  "backup": "gs://sector-lake-brain/history_backup/Wilson_AL/daily.20261013T160457Z.csv",
  "backup_generation": "1791907499034139",
  "backup_size": 28670,
  "generation_before": "1791869696175545",
  "generation_after": "1791907502333160",
  "size_after": 266028,
  "size_before": 28670,
  "md5_b64": "RiNYqTJNaYzvX7veUqeYqA==",
  "crc32c": "v7G8dg==",
  "verify": {
   "md5_ok": true,
   "rows_ok": true,
   "rows": 7410,
   "size": 266028
  },
  "utc": "20261013T160457Z"
 },
 "rows_by_source": {
  "nws:rvdhun:WLSA1": 5966,
  "nws:hads:WLSA1:HP": 793,
  "tva:operating-guide:WLSA1": 651
 },
 "complete_years_before": [
  2025
 ],
 "status_before": "INSUFFICIENT",
 "complete_years_after": [
  2006,
  2007,
  2008,
  2009,
  2010,
  2011,
  2012,
  2013,
  2014,
  2015,
  2016,
  2017,
  2018,
  2019,
  2020,
  2023,
  2024,
  2025
 ],
 "status_after": "SUFFICIENT"
}
```

### Pickwick Lake|TN (PICT1) written 20261013T160506Z

```json
{
 "merged_file": {
  "rows": 6209,
  "bytes": 257145,
  "md5_b64": "pwna5fqfXTCCulYEqg3kAA==",
  "sha256": "c611913fb2a770bca1ac6954b9e401b4f381b114e16cf225b3d55bbb801aa5cb",
  "first": "2003-01-14",
  "last": "2026-10-13"
 },
 "written": {
  "object": "gs://sector-lake-brain/history/Pickwick_Lake_TN/daily.csv",
  "backup": "gs://sector-lake-brain/history_backup/Pickwick_Lake_TN/daily.20261013T160506Z.csv",
  "backup_generation": "1791907508580274",
  "backup_size": 28670,
  "generation_before": "1791869697821108",
  "generation_after": "1791907511369161",
  "size_after": 257145,
  "size_before": 28670,
  "md5_b64": "pwna5fqfXTCCulYEqg3kAA==",
  "crc32c": "tYvvbA==",
  "verify": {
   "md5_ok": true,
   "rows_ok": true,
   "rows": 6209,
   "size": 257145
  },
  "utc": "20261013T160506Z"
 },
 "rows_by_source": {
  "nws:rvdhun:PICT1": 3710,
  "nws:rvdmeg:PICT1": 19,
  "cwms:LRD:Pickwick-Lake.Elev.Inst.1Hour.0.Raw-TVA": 1036,
  "nws:hads:PICT1:HP": 793,
  "tva:operating-guide:PICT1": 651
 },
 "complete_years_before": [
  2025
 ],
 "status_before": "INSUFFICIENT",
 "complete_years_after": [
  2003,
  2004,
  2006,
  2007,
  2008,
  2009,
  2010,
  2011,
  2012,
  2013,
  2020,
  2021,
  2022,
  2023,
  2024,
  2025
 ],
 "status_after": "SUFFICIENT"
}
```

---

## Summary (2026-10-13, written 16:04-16:05 UTC)

Merge rule: `LakeDailyHistory.merge(existing: composite, new: existingGS)`, i.e. the Swift rule (later entry wins) with the live guide-derived rows passed last, so they win on every shared date (651 of 651 existing rows unchanged in every lake). Composite precedence: HADS local midnight > CWMS local midnight (Pickwick) > RVDHUN/RVDMEG 6-7 AM. Composite rows are never added after the last existing day (the TVA guide re-supplies those every run). Day boundary America/Chicago. New `sourceId` values: `nws:rvdhun:<LOC>`, `nws:rvdmeg:PICT1`, `nws:hads:<LOC>:HP`, `cwms:LRD:Pickwick-Lake.Elev.Inst.1Hour.0.Raw-TVA` (existing `tva:operating-guide:<LOC>` untouched; nothing in Swift parses `sourceId`).

| Lake | rows before | rows after | span after | complete years before | complete years after (recount vs expected) | baseline status before / after | rows by source |
|---|---|---|---|---|---|---|---|
| Guntersville | 651 | 7408 | 2005-01-30 to 2026-10-13 | 1 | 17 vs 17 | INSUFFICIENT / SUFFICIENT | nws:rvdhun:GVDA1: 5964, nws:hads:GVDA1:HP: 793, tva:operating-guide:GVDA1: 651 |
| Wheeler | 651 | 7140 | 2005-11-23 to 2026-10-13 | 1 | 18 vs 18 | INSUFFICIENT / SUFFICIENT | nws:rvdhun:WHLA1: 5696, nws:hads:WHLA1:HP: 793, tva:operating-guide:WHLA1: 651 |
| Wilson | 651 | 7410 | 2005-01-30 to 2026-10-13 | 1 | 18 vs 18 | INSUFFICIENT / SUFFICIENT | nws:rvdhun:WLSA1: 5966, nws:hads:WLSA1:HP: 793, tva:operating-guide:WLSA1: 651 |
| Pickwick | 651 | 6209 | 2003-01-14 to 2026-10-13 | 1 | 16 vs 16 | INSUFFICIENT / SUFFICIENT | nws:rvdhun:PICT1: 3710, nws:rvdmeg:PICT1: 19, cwms:LRD:Pickwick-Lake.Elev.Inst.1Hour.0.Raw-TVA: 1036, nws:hads:PICT1:HP: 793, tva:operating-guide:PICT1: 651 |

Complete-year lists equal the research lists exactly (Guntersville 2007-2020 + 2023-2025; Wheeler and Wilson 2006-2020 + 2023-2025; Pickwick 2003-2004, 2006-2013, 2020-2025). Gaps kept honest: 2021-10-01 to 2022-10-27 (392 days) for Guntersville/Wheeler/Wilson; Pickwick 2005-01-14 to 2005-11-22 and 2014-04-17 to 2019-10-07.

### Agreement of the composite's HADS local-midnight values with the existing TVA guide rows (2025-01-01 to 2026-10-13)

| Lake | n | mean abs ft | median | p95 | max abs ft | days differing > 0.02 / > 0.05 ft |
|---|---|---|---|---|---|---|
| Guntersville | 647 | 0.0012 | 0.000 | 0.000 | 0.257 | 8 / 5 |
| Wheeler | 647 | 0.0014 | 0.000 | 0.000 | 0.170 | 13 / 7 |
| Wilson | 647 | 0.0019 | 0.000 | 0.000 | 0.240 | 10 / 9 |
| Pickwick | 647 | 0.0026 | 0.000 | 0.000 | 0.220 | 16 / 8 |

Pickwick CWMS midnight vs existing: n=643, mean abs 0.0023 ft, max 0.22 ft. RVD (6-7 AM, 0.1 ft) vs CWMS 07:00: n=485, mean abs 0.034 ft, p95 0.09 ft, max 0.28 ft. Differences concentrate in Nov-Dec 2025 (TVA guide midnight vs HADS first reading in the midnight hour); the guide value wins by rule.

### Baseline mirror (Python `build_baseline`, v1 `doy15-percentile-v1`) and sanity bands (p10 / p50 / p90 ft; basis = all complete years)

Mirror fidelity: versions (fingerprints), counts, years and statuses are identical to the Swift-written baselines for Guntersville, Wilson (INSUFFICIENT, 2026-10-13) and Hartwell (SUFFICIENT, 60 years); 16,789 of 16,790 quantile cells identical, 1 differs by 0.001 ft (a rounding tie, probably FMA in the arm64 Swift build). Oct 13 bands match the research table to the digit.

| Lake | new baseline version (mirror) | Jan 15 | Jun 15 | Oct 13 |
|---|---|---|---|---|
| Guntersville | `doy15-percentile-v1@2026-10-13#b6ab068b` | 593.30 / 593.84 / 594.66 | 594.20 / 594.66 / 594.90 | 593.80 / 594.10 / 594.49 |
| Wheeler | `doy15-percentile-v1@2026-10-13#367f669f` | 551.20 / 552.00 / 554.00 | 555.20 / 555.70 / 555.98 | 553.30 / 553.80 / 554.20 |
| Wilson | `doy15-percentile-v1@2026-10-13#80dd72fd` | 505.02 / 505.75 / 506.20 | 506.70 / 507.10 / 507.48 | 506.80 / 507.20 / 507.50 |
| Pickwick | `doy15-percentile-v1@2026-10-13#35ea339a` | 408.91 / 410.00 / 412.97 | 413.10 / 413.81 / 414.20 | 411.00 / 411.69 / 412.34 |

### Rate climatology: effect of the 0.1 ft RVDHUN years (Swift follow-up, not changed here)

The builder's `rateByDoy` uses every row. p50 / p95 of abs(change in 24 h), ft, with all rows vs only the 0.01 ft HADS/CWMS/guide era:

| Lake | Jan 15 | Jun 15 | Oct 13 |
|---|---|---|---|
| Guntersville | 0.20/0.50 vs 0.14/0.51 | 0.10/0.40 vs 0.08/0.25 | 0.10/0.40 vs 0.11/0.32 |
| Wheeler | 0.20/0.90 vs 0.20/0.64 | 0.10/0.40 vs 0.07/0.23 | 0.10/0.40 vs 0.09/0.26 |
| Wilson | 0.30/1.00 vs 0.26/0.73 | 0.20/0.64 vs 0.12/0.48 | 0.11/0.60 vs 0.10/0.37 |
| Pickwick | 0.30/1.19 vs 0.24/0.83 | 0.20/0.60 vs 0.10/0.51 | 0.14/0.70 vs 0.13/0.60 |

Recommendation: filter rate pairs on `sourceId` (skip pairs touching `nws:rvd*`). Specified in `docs/brains/LAKE_BRAIN_ARTIFACT_HYGIENE.md` section 4.7.

### Objects written and backups (generation numbers are in the per-lake entries above)

| Live object | generation before | generation after | size before | size after | backup |
|---|---|---|---|---|---|
| `gs://sector-lake-brain/history/Guntersville_AL/daily.csv` | 1791869696171324 | 1791907482025579 | 28670 | 265958 | `gs://sector-lake-brain/history_backup/Guntersville_AL/daily.20261013T160437Z.csv` (gen 1791907479264004) |
| `gs://sector-lake-brain/history/Wheeler_AL/daily.csv` | 1791869696239933 | 1791907490790297 | 28670 | 256578 | `gs://sector-lake-brain/history_backup/Wheeler_AL/daily.20261013T160446Z.csv` (gen 1791907487904586) |
| `gs://sector-lake-brain/history/Wilson_AL/daily.csv` | 1791869696175545 | 1791907502333160 | 28670 | 266028 | `gs://sector-lake-brain/history_backup/Wilson_AL/daily.20261013T160457Z.csv` (gen 1791907499034139) |
| `gs://sector-lake-brain/history/Pickwick_Lake_TN/daily.csv` | 1791869697821108 | 1791907511369161 | 28670 | 257145 | `gs://sector-lake-brain/history_backup/Pickwick_Lake_TN/daily.20261013T160506Z.csv` (gen 1791907508580274) |

Read-back verification for all four: md5 of the object equals the md5 of the local merged file, and the object re-decoded with the Swift decode rules has the expected row count. Upload used `--if-generation-match=<generation read for the merge>`. Hartwell was not touched. The lake-brain job, Cloud Run, Scheduler and the RTDB were not touched; the next orchestrator cycle will recompute baselines (new version ids as in the table above, written under the existing `baselines/{key}/{version}.json` scheme, until the Swift change in the hygiene note ships).

### Anomalies and judgment calls

* Research data root is `~/Desktop/Development/Sector_Research_Data/lake-brain/` (the brief said `~/Desktop/Sector_Research_Data/`).
* Wheeler 2018-08-27: RVDHUN `Wheeler HW` 557.3 ft is above the top of gates (556.28) and 1.5 ft above both neighbours; dropped by the range check (the research composite kept it). One day, no effect on complete years.
* Wheeler 2007-02-01 (555.2 ft, one-day spike of +3.4 / -3.2 ft in the product issued 12:37) and Pickwick 2004-02-06 .. 2004-02-10, 2011-03-12, 2011-04-29 (3 to 4 ft/day, multi-day flood events) are kept: inside the plausible range and plausible for a flood; flagged as `day_steps_gt_3ft_warning` in the dry-run report. Hard limit is 5 ft/day.
* All 9 to 17 values per lake that differ by more than 0.005 ft from the research composite are on dates from 2025-11 onward where the existing TVA guide value now wins (by the collision rule), as required.
* The 2005-2021 rows are 6-7 AM readings at 0.1 ft; their `sourceId` says so. Day-to-day abs changes across the 2021-2022 gap are not computed (no adjacent rows).
* Soft delete is on (7 days) and the bucket is versioned: the pre-backfill objects are also recoverable by generation (`#<generation before>`).
