# Lake Brain: bucket artifact hygiene (baselines, history versions, lifecycle)

Status: analysis and infra, 2026-10-13. Lake Brain data is internal (no customer reads `gs://sector-lake-brain`). Companion files in `jobs/lake-brain/history/`: `baselines_lifecycle.json` (the rule file), `lifecycle_check.py` (model check), `BACKFILL_LOG.md`.

## 1. Measured today (`gs://sector-lake-brain`, 2026-10-13 after the TVA backfill)

Versioning is ON, soft delete 7 days, uniform access, public access prevention enforced, **no lifecycle rule** before this work.

| Prefix | Live objects | Live bytes | Noncurrent versions | Noncurrent bytes |
|---|---|---|---|---|
| `baselines/` | 10 (2 per pilot lake, one per day of change) | 646 KB (50 KB per pilot, 122 KB Hartwell) | 0 | 0 |
| `history/` | 5 (`daily.csv`) | 2.73 MB | **13** | **8.63 MB** (already 3.2x the live history) |
| `history_backup/` | 4 (written by the backfill) | 115 KB | 0 | 0 |
| `presence/` | 2 | 2.65 MB | 0 | 0 |
| total | 21 | 6.14 MB | 13 | 8.63 MB (all of the bucket is 14.76 MB) |

Two growth mechanisms exist today:

1. **Baselines (named in `LAKE_BRAIN_FLEET_SCALING.md` section 8).** `baselineVersion = method@historyEnd#fingerprint`, so the object path `baselines/{key}/{version}.json` is new every day a lake's history advances. Objects are immutable under distinct names, so GCS *versioning cannot prune them* (`numNewerVersions` counts generations of one name, never different names).
2. **History noncurrent versions (not in the earlier note).** `history/{key}/daily.csv` is overwritten every day it changes; with versioning on, each overwrite leaves a full noncurrent copy. Hartwell already has 5 noncurrent copies (1.68 MB each).

## 2. Growth projection (no policy vs the chosen policy)

Assumptions: baseline artifact 55 KB blended (pilots 50 KB, Hartwell 122 KB); history file 0.4 MB on average per fleet lake (about 15 years at 70 bytes/day; the four TVA pilots are now 0.26 MB, Hartwell 1.68 MB); a lake's history changes every day.

| Lakes | Baseline objects per year, today | Bytes per year | Baseline objects standing, policy | Bytes standing, policy | Noncurrent history bytes per year, no rule |
|---|---|---|---|---|---|
| 5 | 1,825 | 100 MB | 30 (1 latest + about 5 archive per lake) | 1.7 MB | 0.7 GB |
| 100 | 36,500 | 2.0 GB | 600 | 33 MB | 14.6 GB |
| 315 | 114,975 | 6.3 GB | 1,890 | 104 MB | 46 GB (115,000 objects) |

Under the policy 315 lakes write 16,380 archive objects per year (52 per lake) instead of 114,975, and about 4.4 archive objects per lake exist at any time (measured in the model, `lifecycle_check.py`). Dollar cost is negligible either way (standard storage about 0.02 USD per GB-month; 115k Class A operations about 0.6 USD per year); the real costs are listing time, console clutter and the 46 GB per year of noncurrent history copies, which is the larger of the two.

## 3. Policy

1. **Recompute the stored baseline at most weekly**, and immediately when any of these change: baseline method, rules/model version, binding version, the history rows at or before the stored `historyEnd` (a backfill or an operator revision), or the calendar year (a year becomes complete). History keeps appending daily; the classifier uses the stored baseline between recomputes.
2. **Read-latest object.** The newest baseline lives at a fixed name, `baselines/{lakeKey}/latest.json` (the full artifact, overwritten in place). Readers never list a prefix.
3. **Archive copy for provenance.** Each recompute also writes the immutable `baselines-archive/{lakeKey}/{versionKey}.json`, so any `baselineVersion` cited by a published `LakeState` in the last 30 days can be resolved.
4. **Lifecycle** (`jobs/lake-brain/history/baselines_lifecycle.json`):
   * rule 1: Delete when `matchesPrefix: ["baselines-archive/"]` and `age >= 30`;
   * rule 2: Delete when `isLive == false`, `daysSinceNoncurrentTime >= 7`, `matchesPrefix: ["baselines/", "baselines-archive/"]` (cleans the superseded generations of `latest.json` and the archive objects after rule 1 retires them; in a versioned bucket a `Delete` on a live object only makes it noncurrent, so two rules are required).

### Why "latest per lake" is guaranteed (and why the obvious alternative is not)

GCS lifecycle cannot express "keep the newest object under a prefix": `numNewerVersions` is per object name and `matchesPrefix` is a literal prefix with no wildcard in the middle, so `baselines/*/versions/` cannot be written. Therefore the layout is chosen so that no rule can match the live latest object:

* `baselines/{key}/latest.json` is live and no rule has an age condition on `baselines/` (rule 2 requires `isLive == false`); it can only be replaced by a newer upload, never removed by lifecycle, even if the job stops for a year.
* `age >= 30` is applied only under `baselines-archive/`, where nothing is "the latest" by definition (the latest is also at `baselines/`).
* If the current layout (`baselines/{key}/{version}.json`, one name per day) had an age rule over `baselines/`, a lake that was not run for 30 days would lose its newest baseline. No GCS rule can prevent that for distinct names, which is why the layout change is part of the policy.

### Proof

* **Model check** (`python jobs/lake-brain/history/lifecycle_check.py <listing.json>`, GCS semantics for a versioned bucket): a 400-day fleet simulation of the weekly policy at 5 and 315 lakes ends every day with exactly one live `latest.json` per lake; only `baselines/` and `baselines-archive/` objects are ever touched; archive objects older than 29 days never survive live. Applied to the real bucket listing for 400 days with the job stopped, **0 objects are touched**: the current `baselines/` objects, every `history/` (live and noncurrent), `history_backup/`, `presence/` object is intact.
* **Scratch bucket test** (`jobs/lake-brain/history/lifecycle_scratch_test.sh`; run once as `gs://sector-lake-brain-scratch-1143e6`, versioned, created and deleted during this work): same two rules with the day thresholds set to 0 on a bucket holding `baselines/` (two generations of `latest.json`, a legacy-named object), `baselines-archive/`, `history/` (two generations), `history_backup/`, `presence/`, `predictions/`, and decoy prefixes (`baselines-archive-keep/`, `history-baselines/`). The rule file was accepted. **GCS had not executed the lifecycle run after 2 hours** (it states up to 24 hours), so the behavioural result was not observed and the bucket was deleted as instructed.
* JSON accepted by `gcloud storage buckets update --lifecycle-file` (scratch and production).

### Not applied (needs a decision)

History noncurrent versions (section 2, 46 GB per year at 315 lakes) are not covered by the applied file because the brief excludes `history/` from any rule. A safe rule exists: `{"isLive": false, "daysSinceNoncurrentTime": 30, "matchesPrefix": ["history/"]}` never matches a live `daily.csv` (and `history_backup/` is another prefix). Alternative: have the runner write `history/` only when 7 or more new rows exist (rows older than the TVA guide window or the 21-day CWMS window would never be lost because both feeds re-supply recent rows each run). Recommend the lifecycle rule, once Michael OKs touching `history/` noncurrent versions.

## 4. Swift-side change (spec; no Swift edited here)

Files: `Sources/SectorEngine/LakeBrain/LakeLevelBaseline.swift`, `LakeBrainRunner.swift` (`evaluateLake`, lines about 148-160 today), `LakeBrainContract.swift` (`LakeBrainSpec`), `LakeBrainArchive.swift` (header comment).

1. `LakeBrainSpec`: `static let baselineRecomputeDays = 7`.
2. `LakeLevelBaseline` gets three optional Codable fields (older artifacts still decode): `computedAt: String?` (ISO UTC), `bindingVersion: String?` (`LakeSourceBindings.version`), `basisFingerprint: String?` (`fingerprint(encode(rows with date <= historyEnd))`, the same FNV used for the version).
3. Paths in `LakeLevelBaseline.swift`:
   * `latestPath(lakeId) = "baselines/\(lakeKey)/latest.json"`;
   * `archivePath(b) = "baselines-archive/\(lakeKey)/\(lakeKey(b.baselineVersion)).json"` (replaces `LakeBaselineBuilder.path`).
   `baselineVersion` keeps its `method@historyEnd#fingerprint` format; `historyEnd` is now the history end at compute time (up to 7 days behind).
4. `evaluateLake`, after `merged` is computed (replaces the block that builds and writes `b` each run):
   ```
   let stored = archive.read(latestPath) → decode LakeLevelBaseline?   // nil if absent or undecodable
   func needsRecompute(stored) -> Bool {
       guard let s = stored else { return true }
       if s.method != LakeBrainSpec.baselineMethod { return true }
       if s.bindingVersion != LakeSourceBindings.version { return true }          // also bump on a rules/model version change: use "\(modelVersion)|\(bindings)"
       if (daysBetween(s.computedAt, now) ?? 99) >= LakeBrainSpec.baselineRecomputeDays { return true }
       if year(of: today) != year(of: s.computedAt) { return true }                 // a year may have become complete
       let rowsAtOrBeforeEnd = merged.filter { $0.date <= s.historyEnd! }
       if fingerprint(encode(rowsAtOrBeforeEnd)) != s.basisFingerprint { return true } // backfill or revised history
       return options.force || options.backfill
   }
   let b = needsRecompute(stored) ? LakeBaselineBuilder.build(...) with computedAt/bindingVersion/basisFingerprint set : stored!
   if recomputed, b.status != .none {
       write archivePath(b)  (skip if it already exists)   // first
       write latestPath      (contentType application/json) // second; failure leaves the old latest, retried next run
   }
   ```
   The classifier, the profile and the LakeState provenance take `b` unchanged; they cite `b.baselineVersion` and `b.historyEnd`, which are those of the stored artifact.
5. One-time cleanup after the first cycle that writes `latest.json` for every bound lake: delete the old `baselines/{key}/doy15_percentile_v1_*.json` objects (10 objects, 0.65 MB today; they are live and the lifecycle does not touch them).
6. Tests to add: no recompute when stored is 3 days old and the history only appended; recompute at 7 days; recompute when a row before `historyEnd` changes (backfill); recompute on a `bindingVersion` change; `latest.json` written after the archive copy; undecodable `latest.json` triggers a recompute.
7. Rate-climatology follow-up found while backfilling (separate from hygiene): the rate samples include the 0.1 ft, 6-7 AM RVDHUN years, which inflates the |change in 24 h| quantiles that feed STABLE and RAPID (for example Wilson, Jun 15: p95 0.64 ft with RVDHUN rows vs 0.48 ft from the 0.01 ft era alone; p50 0.20 vs 0.115; details in `BACKFILL_LOG.md`). Build `rateByDoy` only from pairs whose two rows both have a `sourceId` that does not start with `nws:rvd` (the new ids make this a one-line filter).

## 5. Applying the rule file: NOT applied

The brief allowed applying the rule only if the scratch bucket proved it cannot delete the latest baseline or any `history/`, `presence/`, `predictions/` object. The structural argument and the model check hold (section 3), but the scratch bucket's lifecycle run did not happen within the 2 hours available, so the behavioural proof is missing. `gs://sector-lake-brain` still has **no lifecycle rule**. Since the rule file only matches `baselines-archive/` and noncurrent versions under `baselines/` and `baselines-archive/`, and neither exists yet, applying it today would be inert and could be done at any time; it only starts working once the Swift change in section 4 ships.

To finish: `jobs/lake-brain/history/lifecycle_scratch_test.sh setup` (prints the bucket name), wait about 24 h, `... verify <bucket>` (expected outcome in the script header), `... teardown <bucket>`, then
`gcloud storage buckets update gs://sector-lake-brain --lifecycle-file=jobs/lake-brain/history/baselines_lifecycle.json` (revert with `--clear-lifecycle`).
