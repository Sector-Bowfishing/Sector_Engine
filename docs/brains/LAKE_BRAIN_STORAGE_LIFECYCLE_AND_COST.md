# Lake Brain: storage, lifecycle and cost model (5, 196 and 621 lakes)

Status: analysis, code on branch `feat/lake-fleet-hygiene`, 2026-10-13. **Nothing here is deployed and no lifecycle rule or retention setting is applied to any real bucket.** Read-only measurements were taken on 2026-10-13 around 20:00 UTC; the one cloud mutation was a scratch bucket (section 4), created and deleted by this work.

Companion files: `docs/brains/LAKE_BRAIN_ARTIFACT_HYGIENE.md` (policy and layout), `docs/brains/LAKE_BRAIN_PREDICTION_LEDGER.md` (ledger contract), `jobs/lake-brain/history/lake_brain_bucket_lifecycle_proposed.json` (the exact proposed rule file), `lifecycle_check.py` (model check), `lifecycle_scratch_test.sh` (scratch-bucket proof), `cost_model.py` (re-derives every number in sections 3 and 6).

## 1. What was built (baseline recompute architecture)

The baseline writer is the Swift job (`LakeBrainRunner.evaluateLake`, the `lake-brain` Cloud Run job). The Python `backfill_tva_deep.py` only computes baselines in memory for a before/after comparison; it never writes one. The change is in the Swift writer.

| Piece | Where | Behaviour |
|---|---|---|
| Input fingerprint | `LakeBaselineBuilder.inputFingerprint` | SHA-256 over: builder version, method, pool basis, calendar year, and the history rows exactly as `history/{key}/daily.csv` stores them (deduplicated, 2 decimals). No wall clock in it. |
| Immutable artifact | `baselines-archive/{lakeKey}/{method}_{historyEnd}_{fp16}.json` | Named by its inputs. Equal inputs give the same name and the same bytes, so a repeat write is a no-op. The artifact format is unchanged: it is byte-for-byte what the old builder + encoder produced (tested). |
| Pointer | `baselines/{lakeKey}/latest.json` (about 0.7 KB) | Names the current artifact and carries its SHA-256, size, input fingerprint, `computedAt`, `refreshedAt`, `supersedes`, `pinned`. Written last (artifact first), so a crash leaves the old pointer valid. |
| Recompute policy | `LakeBaselineStore.decide` | Reuse the stored artifact unless: no/corrupt pointer, method or builder version changed, calendar year changed, pool basis changed, `--backfill`, `computedAt` is 7 or more days old, or a row at or before the stored `historyEnd` differs (revision or backfill). Rows appended after `historyEnd` do not trigger a recompute. |
| Weekly recompute with unchanged inputs | `ensure` | Rebuilds, finds the identical object name and hash, writes nothing. |
| Refresh | `refreshDays = 45` | A still-current artifact with unchanged inputs is re-uploaded (same bytes) once per 45 days so the bucket age rule (90 days) never retires the object a pointer names. Costs 2 Class A operations per lake per 45 days. |
| Corrupt or missing pointer/object | `resolve` | Unparsable pointer, wrong lake, path outside `baselines-archive/`, missing object, size/SHA mismatch, or an object that does not decode: the stored baseline is ignored, the baseline is rebuilt from the merged history (today's behaviour), written fresh, and the error is returned in the lake's `errors` for that run. |
| Rollback | `LakeBaselineStore.rollback` | Rewrites `latest.json` to an older artifact and **pins** it (`pinned: true`). A pinned pointer is reused as is: never recomputed, never moved by the runner. The artifact bytes are untouched. Unpin by deleting `latest.json` (the next run rebuilds and moves it). |
| Reproducibility | tested | Re-deriving from a pinned copy of `daily.csv` (decode, build, encode) gives bytes whose SHA-256 equals the pointer's `objectSha256`. For that to hold, the builder now runs on the CSV-round-tripped rows (2 decimals) instead of the raw feed doubles. |
| Read path compatibility | `ensure` | Missing pointer = old behaviour (build from merged history, write). Legacy `baselines/{key}/{baselineVersion}.json` objects are neither read nor written any more; they stay until cleaned up (section 5). With no archive, the baseline is built every run as before. |

Two things worth knowing:

1. **`baselineVersion` is not a content identity.** It is `method@historyEnd#csvFingerprint8`. The rate-climatology RVD filter (commit `98c88717`) changed the artifact content without changing the method string, so the old read-before-write scheme would have kept serving the old content under the same name. The new object name includes the builder version through the input fingerprint (`LakeBaselineBuilder.builderVersion`, bumped on any change to `build`). The `baselineVersion` string inside the artifact and in published `LakeState` provenance is unchanged.
2. **Behaviour change, small and deliberate:** between recomputes the classifier uses a baseline whose `historyEnd` is up to 7 days old (the level climatology uses complete years only, so only the rate climatology and the coverage fields lag). The profile's `coverage.historyEnd` therefore shows the stored baseline's end, not today.

Tests: `Tests/SectorEngineTests/LakeBaselineStoreTests.swift` (18): SHA-256 vectors, fingerprint determinism/sensitivity, first publish equals today's builder output, unchanged input writes nothing, appended rows inside the week write nothing, weekly recompute moves the pointer and keeps the old object, a stalled history writes nothing, refresh only after 45 days, revision/backfill/new year/pool basis/builder bump recompute, missing and corrupt pointer fallback and repair, tampered and missing object, write failure keeps the old pointer, byte-identical re-derivation from a pinned snapshot, feed precision beyond 2 decimals does not change the artifact, rollback + pin + identical results, and the real `evaluateLake` runner writing one object and one pointer across two runs. Full suite: 288 tests, 0 failures (was 270). Python: `jobs/lake-brain/history/test_lifecycle_check.py` (5) and `test_cost_model.py` (4).

## 2. Measured state of the buckets (2026-10-13, read-only)

Commands: `gcloud storage buckets describe gs://sector-lake-brain` / `gs://sector-lake-registry`, `gcloud storage ls -a -r --json`, `gcloud storage buckets get-iam-policy`, `gcloud run jobs executions list`, `gcloud logging read` (job logs), Cloud Monitoring `timeSeries` GET. The listing used for the table is committed as `jobs/lake-brain/history/fixtures/lake_brain_bucket_listing_2026-10-13.json` (object names, sizes, times only).

| Bucket | Class | Location | Versioning | Soft delete | Lifecycle | Retention | Access |
|---|---|---|---|---|---|---|---|
| `gs://sector-lake-brain` | STANDARD | us-central1 | **on** | 7 days | **none** | none | uniform, public access prevention enforced; `brain-writer` SA has `roles/storage.objectAdmin` on the whole bucket |
| `gs://sector-lake-registry` | STANDARD | us-central1 | **off** | 7 days | **none** | none | uniform, public read (`allUsers` objectViewer), PAP inherited, CORS for the Ops site |

`sector-lake-brain` contents (47 object versions):

| Prefix | Live objects | Live bytes | Noncurrent versions | Noncurrent bytes |
|---|---|---|---|---|
| `baselines/` (legacy `{key}/{version}.json`) | 20 | 1,779,788 | 0 | 0 |
| `history/` | 5 | 2,725,737 | **15** | **11,986,895** (4.4x the live history) |
| `history_backup/` (written by the TVA backfill) | 4 | 114,680 | 0 | 0 |
| `predictions/` | 1 (5 records, 6,620 B) | 6,620 | 0 | 0 |
| `presence/` | 2 | 2,650,687 | 0 | 0 |
| total | 32 | 7,277,512 | 15 | 11,986,895 |

Hartwell alone has 7 noncurrent copies of `daily.csv` at 1.68 MB each (it was rewritten 8 times in 20 hours, mostly identical content). The 20 legacy baselines are 4 per pilot lake (one per day of change, v1 and v2 names) and show the old growth mechanism directly: 114-122 KB each for SUFFICIENT lakes, about 50 KB for INSUFFICIENT ones.

`sector-lake-registry`: 1,183 live objects, 9,337,983 bytes (`lakes/` 1,180 objects for 590 lakes = 9,108,590 B, 15.4 KB per lake, largest 174 KB; `registry/` 3 objects, 229,393 B), 0 noncurrent versions (versioning is off).

Cloud Run job `lake-brain` (`us-central1`, 1 vCPU, 1 GiB, task timeout 900 s, 0 retries, args `--scope pilots`): 5 executions on 2026-10-13, all succeeded.

| Execution (start UTC) | Wall (start to completion) | In-process `5 lakes in N ms` | Wall minus in-process |
|---|---|---|---|
| 05:33 | 70.3 s | 4.5 s | 65.9 s |
| 08:51 | 148.0 s | 38.3 s | 109.7 s |
| 12:51 | 108.4 s | 34.6 s | 73.9 s |
| 16:52 | 82.5 s | 14.8 s | 67.7 s |
| 18:52 | 71.0 s | 5.0 s | 66.0 s |

Average wall 96.0 s. The in-process time swings with source latency (the 08:51 and 12:51 runs logged `Lake Hartwell|SC: history: CWMS daily unavailable`). Roughly 66-110 s of every execution is outside the Swift process (container/sandbox start; the `Started` condition comes 58-107 s after the execution `startTime`); this is the fixed cost per execution. Memory: Cloud Monitoring `container/memory/utilizations` had data for one of the five executions (the 16:52 hour): p99 0.03 of the 1 GiB limit, CPU p99 0.20 (single-sample distribution buckets, coarse; treat as "well under 100 MB, one core mostly idle waiting on network").

## 3. Prices (verified) and growth projections

**Prices.** Read from the Cloud Billing Catalog API (`cloudbilling.googleapis.com/v1/services/{id}/skus`, called read-only with the account's own token, USD, SKUs with `effectiveTime` 2026-10-13); the public pricing pages are client-rendered and could not be fetched as text.

| Item | SKU | Price |
|---|---|---|
| Standard storage, us-central1 | "Standard Storage US Regional" | $0.02 per GiB-month (first 5 GiB-month free) |
| Class A operation (insert, list, patch) | "Regional Standard Class A Operations" | $0.005 per 1,000 (first 5,000 per month free) |
| Class B operation (get) | "Regional Standard Class B Operations" | $0.0004 per 1,000 (first 50,000 per month free) |
| Cloud Run job CPU, us-central1 | "Jobs CPU in us-central1" | $0.000018 per vCPU-second |
| Cloud Run job memory, us-central1 | "Jobs Memory in us-central1" | $0.000002 per GiB-second |

Not verified here: Cloud Run's monthly free allowance, internet egress for the public registry bucket (Ops traffic is not measured), and the soft-delete price. Soft-deleted data is billed at the storage class rate for its retention window, which is Google's documented behaviour (`docs.cloud.google.com/storage/docs/soft-delete`), not something the catalog shows. All dollar figures below ignore the free tiers (upper bounds). Standard storage has no retrieval or early-deletion charge.

**Assumptions** (`cost_model.py`; MEASURED = from section 2, ESTIMATE = not measured): baseline artifact 118 KB (MEASURED, SUFFICIENT lakes; 50 KB when history is too short, so this is the upper case); history file 0.40 MB per lake average (ESTIMATE: TVA lakes measured 0.26 MB at 36 B per row, Hartwell 1.68 MB at 71 B per row; the real fleet mix is unknown); one history rewrite per lake per day; ledger record 1,324 B (MEASURED: 6,620 B / 5); 6 runs per day (ESTIMATE: 5 executions over 13 hours by the hourly orchestrator); every lake published every run (upper bound).

Projected growth per year (the "old" column is today's writer; lifecycle columns are the proposal, applied to nothing yet). Dollar figure = storage cost per month at that size.

| Lakes | Baselines per year, old writer (daily new object) | Baselines per year, new writer, no lifecycle (weekly) | Baselines standing, new writer + 90-day rule | History noncurrent per year, no rule | History noncurrent standing, 30-day rule (+7 day soft delete) | Predictions ledger per year | Registry live (no growth) |
|---|---|---|---|---|---|---|---|
| 5 | 1,825 obj, 215 MB ($0.004/mo) | 260 obj, 31 MB | 70 obj, 7.7 MB | 1,825 obj, 0.73 GB ($0.014/mo) | 185 obj, 74 MB | 2,190 obj, 14.5 MB | 0.1 MB |
| 196 | 71,540 obj, 8.4 GB ($0.16/mo) | 10,192 obj, 1.2 GB | 2,744 obj, 301 MB | 71,540 obj, 28.6 GB ($0.53/mo) | 7,252 obj, 2.9 GB ($0.054/mo) | 2,190 obj, 568 MB ($0.011/mo) | 3.1 MB |
| 621 | 226,665 obj, 26.7 GB ($0.50/mo) | 32,292 obj, 3.8 GB | 8,694 obj, 954 MB ($0.018/mo) | 226,665 obj, **90.7 GB ($1.69/mo)** | 22,977 obj, 9.2 GB ($0.17/mo) | 2,190 obj, 1.8 GB ($0.034/mo) | 9.8 MB |

(The history-noncurrent column grows each year it is left; after 3 years at 621 lakes it would be about 272 GB, $5/month. The ledger is one object per run, so its object count does not grow with lakes; bytes do. The registry holds 590 lakes today and was published once; geometry objects are written once and never overwritten, so its growth is new lakes and new geometry versions only, and an index republish costs 0.22 MB of transient soft-delete storage.)

**GCS operations per year** (Class A + Class B, new writer, 6 runs per day): 5 lakes 4,535 A + 39,680 B = $0.04; 196 lakes 94,114 A + 1.30 M B = $0.99; 621 lakes 293,439 A + 4.12 M B = $3.12. The old writer costs about the same (it reads less per run but writes a baseline daily): $0.04, $1.10, $3.46. The new writer trades 52 baseline writes per lake per year (instead of 365) for one extra pointer read per lake per run. Operations are not a driver either way.

**Reading the numbers.** Dollars are small at every scale; the largest line is noncurrent history, $1.69 per month after one year at 621 lakes. The reasons to act are operational: 227k baseline objects per year (listing and console time), 227k noncurrent history copies, and the absence of any retention statement for `predictions/`. The 5-lake case today costs about $0.01 per month in storage.

## 4. GCS lifecycle: what is proven and what is not

### 4.1 Rules proposed (not applied)

File: `jobs/lake-brain/history/lake_brain_bucket_lifecycle_proposed.json`, for `gs://sector-lake-brain` only:

```json
{
  "rule": [
    {
      "action": {"type": "Delete"},
      "condition": {"age": 90, "matchesPrefix": ["baselines-archive/"]}
    },
    {
      "action": {"type": "Delete"},
      "condition": {"isLive": false, "daysSinceNoncurrentTime": 7, "matchesPrefix": ["baselines/", "baselines-archive/"]}
    },
    {
      "action": {"type": "Delete"},
      "condition": {"isLive": false, "daysSinceNoncurrentTime": 30, "matchesPrefix": ["history/"]}
    }
  ]
}
```

Apply (the lead, after review): `gcloud storage buckets update gs://sector-lake-brain --lifecycle-file=jobs/lake-brain/history/lake_brain_bucket_lifecycle_proposed.json`. Revert: `gcloud storage buckets update gs://sector-lake-brain --clear-lifecycle`. Per Google's lifecycle documentation a changed configuration can take up to 24 hours to take effect and actions are asynchronous.

| Prefix | Object class | Versioning today | Behaviour today | Proposed | Recovery impact | Storage impact |
|---|---|---|---|---|---|---|
| `baselines/{key}/latest.json` | pointer, overwritten in place | on | not written yet (legacy objects only) | rule 2: noncurrent generations deleted 7 days after being replaced. The live pointer matches no rule (rule 2 needs `isLive:false`, rule 1 is another prefix) | A bad pointer can be restored from a noncurrent generation for 7 days; beyond that, rollback uses `supersedes` in the next pointer or an operator-written pointer | negligible (0.7 KB per generation) |
| `baselines-archive/{key}/...` | immutable artifact | on | not written yet | rule 1: delete at age 90; rule 2 removes the resulting noncurrent version after 7 days. The writer re-uploads the current object every 45 days (`refreshDays`), so the object a pointer names is never older than 45 days while the job runs | Any artifact written in the last 90 days is restorable by pointer rollback; 97 days after a replacement it is gone, but it is also re-derivable from a pinned `history/` snapshot and the builder version (tested) | standing about 14 objects x 118 KB per lake (section 3) |
| `baselines/{key}/{version}.json` (legacy, 20 live) | immutable, old naming | on | accumulate forever | no rule matches a live legacy object; clean up once (section 5) | n/a | 1.8 MB today |
| `history/{key}/daily.csv` | overwritten daily | on | every overwrite keeps a full noncurrent copy forever (15 copies, 12.0 MB, 4.4x live) | rule 3: noncurrent copies deleted 30 days after replacement. A live `daily.csv` never matches (`isLive:false`) | The last 30 days of daily snapshots stay restorable (more than the soft-delete 7); the backfill's own `history_backup/` is another prefix and untouched | from 227k copies and 90.7 GB per year at 621 lakes to a standing 22,977 copies and 9.2 GB |
| `history_backup/` | operator backup, write once | on | accumulates (4 objects) | no rule | n/a | grows only on backfills |
| `presence/` | private research bundle | on | 2 objects | no rule | n/a | static |
| `predictions/` | prospective evidence | on | write-once objects | **no deletion rule** (section 4.3) | n/a | section 3 |

Cost of getting rule 3 wrong is bounded: a `Delete` on a noncurrent version never removes the live file, and a rewrite always leaves the previous version for 30 days. The conservative alternative is to have the runner skip the `history/` write when no row changed (it already does: `merged != existing`) and write at most daily; the 30-day rule is still needed because a new row arrives every day.

### 4.2 Scratch-bucket proof of lifecycle behaviour

Bucket: `gs://sector-lake-brain-lifecycle-scratch-d0ed8d` (versioned, uniform access, PAP enforced, us-central1, project `sector-9393c`), created 2026-10-13 20:13 UTC by `lifecycle_scratch_test.sh setup`, **to be deleted by this work** (state below). It holds the full prefix mix of the real bucket (two generations of `baselines/Lake_A/latest.json`, a legacy-named baselines object, two archive objects, two generations of `history/` and of `predictions/`, `history_backup/`, `presence/`, and the decoy prefixes `baselines-archive-keep/`, `history-baselines/`, `history2/`) and the proposed rule file with every day threshold set to 0.

What Google's documentation says about timing (`docs.cloud.google.com/storage/docs/lifecycle`, read 2026-10-13): actions are performed asynchronously with no latency guarantee; configuration changes can take up to 24 hours; **`age` 0 is valid and is satisfied at midnight UTC after the object is created**; `daysSinceNoncurrentTime` 0 makes a noncurrent version eligible as soon as it is noncurrent (subject to the same asynchrony); `isLive:false` matches noncurrent versions only.

Consequences for the previous attempt (`LAKE_BRAIN_ARTIFACT_HYGIENE.md` section 3: "no run after 2 hours"): that was not enough time for two reasons the earlier note did not account for. An `age 0` rule cannot match a live object created the same day before the next 00:00 UTC, and a new configuration may take up to 24 hours. So the absence of an effect after 2 hours says nothing about the rules.

Result of this run: see section 4.4 (filled in at the end of the session).

### 4.3 Retention for `predictions/` (needs a decision; nothing applied)

Facts: the ledger contract says "keep everything; no lifecycle deletion" and "immutable", but nothing in the bucket enforces it. The writer checks the object does not exist, then creates it; `brain-writer` holds `roles/storage.objectAdmin` on the whole bucket, so a bug or a mistaken command could overwrite or delete ledger objects, and the 7-day soft delete is the only net. The `VALIDATED` path needs at least 12 months of unmodified evidence, so the failure that matters is silent alteration, not cost (1.8 GB per year at 621 lakes, $0.04 per month).

| Option | What it does | Tradeoffs |
|---|---|---|
| A. Status quo plus a **no-rule guarantee** (current) | nothing deletes ledger objects by lifecycle | does not stop a human or the writer SA overwriting or deleting; no cost; reversible |
| B. **IAM split** (reversible) | replace `objectAdmin` on the bucket by `objectAdmin` conditioned on the prefixes `history/`, `baselines`, `presence/` and `history_backup/`, and `objectCreator` + `objectViewer` on `predictions/` (IAM condition on `resource.name`) | the SA can create ledger objects and check existence but cannot overwrite or delete them; owners can still change it; needs a policy edit by Michael; a mistake in conditions could break the job, so test on the scratch bucket first |
| C. **Create-only writes** (code) | upload ledger objects with `ifGenerationMatch=0` | makes "never replaced" atomic instead of a read-then-write race; a Swift change in `GCSLakeBrainArchive.write`, not done here |
| D. **Separate ledger bucket** with a bucket retention policy (for example `gs://sector-lake-brain-ledger`, retention 400 days, later locked) | objects cannot be deleted or replaced before the retention age, enforced by GCS, even for owners | one more bucket and a config change in the job (`ledgerArchive`); a *locked* policy is irreversible and the bucket then cannot be deleted before the retention ends; a bucket retention policy blocks replacing objects, so it cannot go on `sector-lake-brain` itself, where `history/` and `latest.json` are overwritten; retention and versioning coexistence was not verified here |
| E. **Object Retention Lock** on `sector-lake-brain` | per-object retain-until date set at upload (Unlocked or Locked mode); only ledger objects would carry it | per Google's documentation (`docs.cloud.google.com/storage/docs/object-lock`) an existing bucket can only enable the feature **from the Cloud console**, and it **cannot be disabled afterwards**; it also places a lien on project deletion at best effort; the writer would need to send retention fields and hold `storage.objects.setRetention` |

Recommendation: do B now (reversible, closes the realistic failure) and C in code; use D (unlocked first, locked only when the decision to claim VALIDATED is made) before any VALIDATED claim, since retention is the only option GCS enforces against owners. Do not use E on the shared bucket unless the irreversibility is accepted explicitly.

### 4.4 Scratch run result and cleanup

(Section completed at the end of the session.)

## 5. One-time cleanup (not performed)

After the first cycle that writes `latest.json` for every bound lake, the 20 legacy objects `baselines/{key}/doy15_percentile_*.json` (1.78 MB) become unreferenced. In a versioned bucket, deleting a live object makes it noncurrent and rule 2 retires it 7 days later. Command (lead, after the deploy): `gcloud storage rm "gs://sector-lake-brain/baselines/*/doy15_percentile_*.json"`. Do not run it before the new job image is live.

## 6. API-call, runtime and memory cost model

MEASURED = section 2. ESTIMATE = extrapolation; `cost_model.py` re-derives the table.

**Per-run model.** Cloud Run job, 1 vCPU, 1 GiB, billed per second at $0.000020 per second together (catalog rates). One execution is a fixed part (66-110 s measured outside the Swift process) plus lake work: batches of 3 lakes (`LakeBrainRunOptions.concurrency`), each batch measured at about 2.2-19 s (the in-process time of the 5-lake runs divided by 2 batches).

| Lakes | Batches | Wall per run (fixed 66-110 s + batches x 2.2-19 s) | Fits the 900 s task timeout | Cloud Run cost per run | Per year at 6 runs/day |
|---|---|---|---|---|---|
| 5 (MEASURED) | 2 | 70-148 s (observed 70.3, 71.0, 82.5, 108.4, 148.0; mean 96.0) | yes | $0.0014-0.0030 (mean $0.0019) | $3.1-6.5 (mean $4.2) |
| 196 (ESTIMATE) | 66 | 213-1,374 s | **no at the slow end** | $0.0043-0.0275 | $9-60 |
| 621 (ESTIMATE) | 207 | 527-4,074 s | **no at the slow end** | $0.0105-0.0815 | $23-178 |

At 12 runs per day the Cloud Run figures double. The slow end is the day the 5 pilots took 34-38 s in-process because a CWMS history endpoint was unavailable; fleet lakes with one source and a short history will usually sit nearer the fast end, which is why these are ranges and not forecasts. **Sharding is needed before a 196-lake run can promise to finish**: with a 900 s limit and 0 retries, an overrun kills the whole run. Options: raise `--task-timeout` (maximum for a job task is 24 hours, per Cloud Run limits; not verified here), raise the concurrency, or split the fleet across tasks (`--lake` already selects subsets; Cloud Run job `--tasks` plus a task-index argument would need a small Swift change). Cost is the same whichever way the work is split.

**Memory.** Measured: far below 1 GiB for 5 lakes. Estimate for 621 lakes: `run` keeps every lake's `LakeBrainLakeResult`, including the decoded baseline (365 days x 2 grids x 23 doubles, about 134 KB as Swift values), so about 85 MB of baselines plus states and profiles; history for the lakes in flight (3 x about 0.4 MB, decoded about 3x) and the 2.65 MB presence bundle. Expected peak 150-300 MB, inside 1 GiB. The new store adds one 118 KB artifact read and decode per lake per run instead of one build; the build itself (365 days x two quantile grids over a 7,400-row history) was 0.9-2.4 s in a debug test run including fixture generation, so well under that in release (not benchmarked in release here).

**API calls per lake per run** (new writer): GCS reads: `latest.json`, the artifact, `daily.csv` = 3 Class B; presence bundle + ledger existence check = 3 per run. GCS writes: `daily.csv` when a row changed (about once a day), artifact + pointer weekly (2 Class A per lake per week), one ledger object per run. External source calls (TVA, CWMS, USGS, HADS; public endpoints, no cost): ESTIMATE 2-4 per lake per run (live series, optional guide, daily history tail), so at 621 lakes and 6 runs per day about 7,500-15,000 calls per day spread over the providers, which is the number to check against each provider's etiquette before a fleet run (it is not measured).

**Registry bucket** (`gs://sector-lake-registry`): storage 9.3 MB now, 9.8 MB at 621 lakes, no versioning, no growth outside new geometry versions; operations are reads by the Ops UI (not measured); internet egress was not priced.

## 7. Findings

1. `gs://sector-lake-brain` still has no lifecycle rule; noncurrent `history/` copies are already 4.4x the live history after one day of operation (15 copies, 12.0 MB; 8.6 MB when the hygiene note was written).
2. `baselineVersion` does not identify content (the rate-filter change altered artifacts under unchanged names). The new object name is keyed on the input fingerprint, which includes a builder version that must be bumped on any change to `LakeBaselineBuilder.build`. This is the one rule a future editor has to remember.
3. `brain-writer` has `objectAdmin` on the whole bucket, which makes the ledger's "immutable" a convention.
4. A full fleet run cannot be assumed to fit the 900 s task timeout (section 6).
5. The earlier "lifecycle did not run in 2 hours" result was inconclusive by construction (age 0 means the next midnight UTC; configuration changes take up to 24 hours).
6. The registry bucket is public-read by design and cost-irrelevant; its only open number is internet egress.

## 8. Follow-ups for the lead (nothing executed)

1. Review and deploy the Swift change (new job image through the normal build). First production cycle writes `baselines-archive/...` objects and `latest.json` per lake; check one with `gcloud storage cat gs://sector-lake-brain/baselines/Guntersville_AL/latest.json` and compare `objectSha256` with `gcloud storage hash`.
2. After a full cycle, apply the lifecycle file (4.1) and run the one-time legacy cleanup (5). Apply the lifecycle only after the new image is live.
3. Decide predictions retention (4.3): B and C now, D before any VALIDATED claim.
4. Decide sharding for the fleet scope before enabling a 196-lake run.
