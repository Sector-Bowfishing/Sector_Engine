# Lake Brain: bucket artifact hygiene (baselines, history versions, lifecycle)

Status: implemented in code on branch `feat/lake-fleet-hygiene` (2026-10-13), **not deployed, no lifecycle rule applied**. Lake Brain data is internal (no customer reads `gs://sector-lake-brain`). Measurements, prices, growth at 5 / 196 / 621 lakes, the scratch-bucket proof and the predictions-retention options are in `LAKE_BRAIN_STORAGE_LIFECYCLE_AND_COST.md`; this note is the policy and the contract. Files in `jobs/lake-brain/history/`: `lake_brain_bucket_lifecycle_proposed.json` (the rule file; was `baselines_lifecycle.json`), `lifecycle_check.py` (model check, pytest in `test_lifecycle_check.py`), `lifecycle_scratch_test.sh`, `cost_model.py`, `BACKFILL_LOG.md`.

## 1. The two growth mechanisms (measured 2026-10-13)

1. **Baselines.** The old writer named the object `baselines/{key}/{method@historyEnd#fp}.json`, new every day the history advanced; versioning cannot prune distinct names. 20 live objects for 5 lakes after one day (1.78 MB). At 621 lakes that is 226,665 objects and 26.7 GB per year.
2. **History noncurrent versions.** `history/{key}/daily.csv` is overwritten whenever it changes; with versioning on each overwrite keeps a full copy. 15 noncurrent copies, 12.0 MB, 4.4x the live history, after one day (Hartwell: 7 copies of 1.68 MB). At 621 lakes: 90.7 GB per year.

Versioning is on, soft delete 7 days, no lifecycle rule, no retention policy.

## 2. Layout and recompute policy (implemented)

```
baselines/{lakeKey}/latest.json                         pointer (about 0.7 KB), overwritten in place
baselines-archive/{lakeKey}/{method}_{end}_{fp16}.json  immutable artifact, named by its input fingerprint
baselines/{lakeKey}/{baselineVersion}.json              LEGACY: no longer written or read
```

Code: `Sources/SectorEngine/LakeBrain/LakeBaselineStore.swift` (+ the call in `LakeBrainRunner.evaluateLake`). The artifact format and `baselineVersion` are unchanged; `LakeBaselineBuilder.build` is untouched.

1. **Input fingerprint** = SHA-256 of: builder version (`LakeBaselineBuilder.builderVersion`), method, pool basis, calendar year, and the history rows as `daily.csv` stores them (deduplicated, 2 decimals). An artifact is a pure function of that text, so identical inputs write nothing and re-deriving from a pinned `daily.csv` gives identical bytes.
2. **Recompute** only when: no or unusable pointer; method/builder changed; calendar year changed (a year became complete); pool basis changed; `--backfill`; `computedAt` 7 or more days old; or a row at or before the stored `historyEnd` differs (backfill or operator revision). Rows appended after `historyEnd` do not trigger it; the classifier uses the stored baseline in between (its `historyEnd` is up to 7 days old).
3. **Write order**: artifact, then pointer. A failed write leaves the previous pointer valid and the run still classifies from an in-memory baseline.
4. **Pointer contents**: `objectPath`, `objectSha256`, `objectBytes`, `inputFingerprint`, `builderVersion`, `method`, `baselineVersion`, `asOfYear`, `poolBasisIsFullPool`, `historyEnd`, `computedAt`, `refreshedAt`, `supersedes` (previous object), `pinned`, `pinnedReason`.
5. **Fallback**: a missing pointer is today's behaviour (build from the merged history and write). An unparsable pointer, a pointer for another lake, an object that is missing, the wrong size or hash, or that does not decode, is treated the same way, the error is returned in the lake's `errors`, and the pointer is repaired by the rewrite.
6. **Rollback**: `LakeBaselineStore.rollback(archive:lakeId:toObjectPath:reason:now:)` rewrites the pointer to an older artifact and pins it; the runner then reuses that artifact unchanged until the pointer is deleted or rewritten. No CLI wraps it yet; an operator can do the same by writing a `latest.json` with `pinned: true` (fields as above; for an older object only `objectPath`, `objectSha256`, `objectBytes`, `baselineVersion` matter while pinned).
7. **Refresh**: a current artifact with unchanged inputs (a stalled history) is re-uploaded unchanged every 45 days, so the 90-day age rule below never retires an object a pointer names.

## 3. Lifecycle (proposed; exact JSON in `LAKE_BRAIN_STORAGE_LIFECYCLE_AND_COST.md` section 4.1)

* rule 1: Delete `baselines-archive/` at age 90;
* rule 2: Delete noncurrent (`isLive:false`) versions 7 days after they became noncurrent under `baselines/` and `baselines-archive/` (in a versioned bucket a Delete on a live object only makes it noncurrent, so two rules are needed);
* rule 3: Delete noncurrent `history/` versions 30 days after they became noncurrent.

Why "the current baseline is never deleted" holds: GCS cannot express "keep the newest object under a prefix" (`numNewerVersions` counts generations of one name; `matchesPrefix` is a literal prefix). So the layout keeps the pointer at a name only noncurrent-version rules can match, and keeps the artifact it names young by the 45-day refresh against the 90-day age rule. If the job stops for more than 90 days the pointed artifact is retired but the pointer survives, and the next run finds a dangling pointer and rebuilds (tested). `predictions/`, `presence/`, `history_backup/` and every live `history/` object match no rule.

`lifecycle_check.py` models these semantics (fleet simulation at 5, 196, 621 lakes for 400 days with weekly recompute and stalled lakes; the job stopped; and the real bucket listing). `test_lifecycle_check.py` asserts it, including that the Swift `refreshDays` is at most half the archive age.

## 4. Status of the proofs

* Model check and structural argument: done, tested (5 pytest tests).
* Behavioural proof on a scratch bucket: see `LAKE_BRAIN_STORAGE_LIFECYCLE_AND_COST.md` section 4.2 and 4.4. The earlier note's "no run after 2 hours" was inconclusive: GCS documents `age` 0 as satisfied at the next midnight UTC and says a configuration change can take up to 24 hours.
* JSON accepted by `gcloud storage buckets update --lifecycle-file` on a scratch bucket.
* **Not applied** to `gs://sector-lake-brain`. Apply only after the new job image is live and has written `latest.json` for the bound lakes: `gcloud storage buckets update gs://sector-lake-brain --lifecycle-file=jobs/lake-brain/history/lake_brain_bucket_lifecycle_proposed.json` (revert `--clear-lifecycle`). Then remove the 20 legacy `baselines/{key}/doy15_percentile_*.json` objects once.

## 5. Still open

* Retention and write protection for `predictions/` (options B-E in the cost note section 4.3; none applied).
* The rate-climatology RVD filter from the backfill (low-resolution rows excluded from the |change in 24 h| quantiles) is already in `LakeBaselineBuilder.build`; it is the reason the artifact name now includes a builder version.
* A history write skip rule (write `daily.csv` only when 7 or more new rows exist) was considered as an alternative to rule 3 and not chosen: rule 3 needs no code and keeps 30 days of snapshots.
