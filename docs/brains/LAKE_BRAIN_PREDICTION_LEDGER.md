# Lake Brain: prospective prediction ledger (`lake-prediction-ledger-v1`)

Internal. Nothing here is customer-facing, and nothing here changes lifecycle, readiness, the score rubric or `/validation/lake-brain`.
**Lake Brain validation remains `NOT_VALIDATED`. The ledger existing does not make it `PARTIAL`** (`LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md`, "What does not count").

## Why
A hold-out test (rules v2, `LAKE_BRAIN_RULES_V2_PREREGISTRATION.md`) reuses history. It cannot show what the Brain said *before* the outcome. Calendar time for that evidence cannot be bought later,
so every published lake state also leaves an immutable record of the claims it made and the exact thresholds and bands it used. A scorer later joins those claims to what the lake actually did.

## What is recorded
Per published lake per run: one JSON line. Keys are sorted, UTF-8, no personal data, no secrets, public water-level data only.

| Field | Meaning |
|---|---|
| `ledgerVersion` | `lake-prediction-ledger-v1` |
| `runId`, `generatedAt` | Run id (sanitised `[A-Za-z0-9_-]`, ≤ 40) and the run time (UTC, the same for every line of one object) |
| `lakeId`, `provider` (`tva`/`cwms`/`usgs`), `kind` (`OBSERVED`/`PROXY`), `poolBasis` (`fullPool` = regulated, `naturalSurface`, or absent) | Lake and class features for slicing |
| `rulesVersion`, `brainVersion`, `baselineMethod`, `baselineVersion` | Exactly which rules and which baseline artifact produced the claims |
| `historicalTier`, `baselineStatus` | R1 tier and the v1-meaning status at run time |
| `bindingVersion`, `bindingStatus`, `sourceId` | Which reviewed binding and series |
| `timeZone`, `baseDate` | Lake-local date of the observation; horizons count from it |
| `observation {at, ft}` | The reading the labels were computed from |
| `labels {levelState, historicalState, trendState, floodPoolState}` | The published classifications |
| `change {h24, d3}` | Observed 24 h and 72 h level changes behind the trend label (absent when not available) |
| `rapidThresholdFt` | The effective RAPID threshold stored with the label, max(seasonal p95, 0.25 ft); absent for a PROXY |
| `stableFloorFt` | STABLE floor applied to the 72 h mean rate: 0.10 ft/day regulated, 0.05 natural |
| `flags` | The state's `qualityFlags` (stale source, fallback source, `historicalProvisional`, `trend24hFallback`, ...) |
| `horizons[]` | For 1, 7 and 30 days: `targetDate` (lake-local, `baseDate` + days), `doy` (365-day calendar), `band {p02,p10,p50,p90,p98}` + `bandN`, `rateP95` + `rateN` |

**Bands** are the baseline grid's values for the *target* day of year, copied as stored (3 decimals), so a scorer needs no baseline. They are omitted when the lake's history tier is `NONE` (no historical claim is published then) or the day has no level climatology, and always omitted for a `PROXY`.
`rateP95` is the seasonal p95 of |Δ24h| for the target day (omitted without a rate climatology, ≥ 20 samples). Day of year follows `doy365`: Feb 29 shares Feb 28's index; month and year wraps use calendar dates.

Example (synthetic levels from the golden fixture, `jobs/lake-brain/ledger/fixtures/sample_ledger.jsonl`, abbreviated to one horizon):
```json
{"baseDate":"2026-06-01","baselineMethod":"doy15-percentile-v2","baselineStatus":"SUFFICIENT","historicalTier":"PROVISIONAL","horizons":[{"band":{"p02":600,"p10":600.1,"p50":600.5,"p90":600.9,"p98":601},"bandN":105,"days":1,"doy":153,"rateN":105,"rateP95":0.8,"targetDate":"2026-06-02"}],"kind":"OBSERVED","labels":{"floodPoolState":"UNKNOWN","historicalState":"NORMAL","levelState":"IN_ZONE","trendState":"STABLE"},"lakeId":"Guntersville|AL","ledgerVersion":"lake-prediction-ledger-v1","observation":{"at":"2026-06-01T12:00:00Z","ft":600.2},"rapidThresholdFt":0.8,"rulesVersion":"lake-level-rules-v2","sourceId":"tva:GVDA1","stableFloorFt":0.1}
```

## Storage and when it is written
- One object per run: `gs://sector-lake-brain/predictions/{yyyy}/{MM}/{dd}/{HHmmss}Z-{runId}.jsonl` (UTC of the run), `application/x-ndjson`. Records are in `lakeId` order.
- **Immutable.** The writer checks the object does not exist and never replaces it (the bucket is also versioned). Corrections are new objects, never edits.
- Written only when the run **recomputed and published at least one REVIEWED lake with an observation** (`baseline` built on the publish path, state not `UNAVAILABLE`). A pure skip run writes nothing. Lakes whose state was carried forward are not re-recorded.
- Written **after** the Brain RTDB writes succeeded, by the same job and the same identity as the history archive (no new permission, no schedule, no new service). If the RTDB write failed, nothing is ledgered.
- **Bucket facts (read 2026-10-13):** object versioning is on, soft delete keeps a deleted object 7 days, no retention policy, no lifecycle rule, uniform bucket-level access, public access prevention enforced. The writer `brain-writer` holds `roles/storage.objectAdmin` on the whole bucket, so immutability is enforced by the writer code (check, then create-only), by versioning and by process, **not by an IAM or retention rule**. See "Open decisions".
- **Failure isolation:** the ledger write cannot throw out of the run. A failure sets `LakeBrainRunResult.ledgerWarning` (also appended to `archiveErrors`, which the job prints). It never changes `ok`, `health`, `writeError` or any RTDB path.
- **Dry run:** a run against a local/read-through dry-run store never writes the ledger to the history archive (which may be `gs://`); it writes under `<dry-run dir>/_ledger/`. `LakeBrainRunOptions.ledgerArchive` overrides the target (tests, local replays).
- **Switch:** the ledger is **on by default** (`LakeBrainRunOptions().ledgerEnabled == true`) and in every production path. The only way off is the explicit job flag `LakeBrainJob --no-ledger` (or `ledgerEnabled = false` in code) for dry runs, debugging, replay and local tests. A run always records the choice: the job prints `ledger: enabled|disabled` before and after the run, `LakeBrainRunResult.ledgerStatus` carries it, and a publishing run (`--rtdb`) with `--no-ledger` also prints a WARNING on stderr. `jobs/lake-brain/deploy-job.sh` never passes the flag; `LakeBrainRunnerHardeningTests.testProductionDeployScriptCannotSilentlyDisableTheLedger` parses the real `--args=` line and the job source and fails if either could disable it.
- **Create-only write (added 2026-10-13, takes effect with the next job image):** the GCS archive writes ledger objects with `ifGenerationMatch=0`, so GCS itself refuses (HTTP 412) to replace an existing object even if two writers race between the existence check and the upload. The image running when the ledger started (`brain-jobs:98c8871798c5`) checks first and then writes without the precondition.

## Volume
Measured record size ≈ 1.3 KB (about 0.7 KB without bands, an estimate). Pilots today: 5 lakes. **Measured cadence (audit below): the job runs about every 4 h, not 2 h** (`staleAfterHours 3` plus the hourly `:50` orchestrator wake gives a run at +4 h: executions at 08:51, 12:51, 16:52 UTC on 2026-10-13). That is about 6 objects/day of about 6.5 KB (about 40 KB/day, about 14 MB/year, about 2,200 objects/year). The earlier estimate of 12 objects/day assumed 2 h.
Fleet scale, 315 bound lakes, every lake due each run: about 400 KB per object, 6 objects/day, about 1,900 lines/day, about 2.4 MB/day, about 0.9 GB/year (double that at a 2 h cadence). Object count stays small (compare the baseline-artifact hazard of about 115 k objects/year in `LAKE_BRAIN_FLEET_SCALING.md`); storage cost is a few cents a month.
**Retention:** keep everything; no lifecycle deletion on `predictions/`. The `VALIDATED` path needs at least 12 months, and the ledger is the audit trail.

## Guarantees
1. A line is a claim made at `generatedAt`, from the baseline and thresholds named in it. Nothing is recomputed afterwards.
2. Append-only, one object per run, never overwritten.
3. A failure of the ledger cannot fail or alter a Brain publish.
4. The scorer never scores a prediction whose target date has not arrived, and never imputes a missing realised value.

## What it does not mean
- It is not validation, and it does not make the Lake Brain `PARTIAL`. `PARTIAL` still needs every item in the proposed definition, and that definition is itself not adopted.
- A stable lake is rechecked about every 4 h (measured), so several lines make the same claim about the same day. Headline figures use one line per lake per base date (the earliest). Neighbouring days and lakes on one river are correlated. Rates have no sampling-error interpretation.
- Realised levels are the operators' daily values as the history archive holds them at scoring time. Operators revise those values (the merge lets newer rows win); the bands and thresholds are not revised.
- A rules or baseline change makes a new `rulesVersion` / `baselineMethod`; the scorer reports by `rulesVersion`. Results across versions are not pooled silently.
- No pass/fail is computed anywhere in the ledger or the scorer. Applying the pre-registered v2 criteria to ledger data is a separate, explicit act.

## Scoring
Scorer v2 (2026-10-13 hardening; `jobs/lake-brain/ledger/score_predictions.py`, 40 tests) adds, without changing any rate definition:
- **Thresholds immutable.** Bands, `rapidThresholdFt`, `rateP95` and `stableFloorFt` come from the record. The scorer opens only `predictions/` and `history/` (a test spies on every read) and never a baseline.
- **No hindsight.** A record is skipped and counted under `inputs.invalidReasons` when: its observation is later than `generatedAt` (`observationAfterPrediction`); `baseDate` is not the lake-local date of the observation (`baseDateNotObservationDate`); a horizon's `targetDate` is not `baseDate + days` or not after the base date (`targetNotBasePlusDays`); or the target is not strictly after the lake-local day the prediction was made (`targetNotAfterPredictionDay`). A realisation is the history row dated exactly the target date: a neighbouring row never substitutes, and a row dated on or after `--as-of` is never used. Records generated after `--as-of` are excluded (`futureDatedRecords`), so a replay as of a date sees only what existed then. One limit remains: the label-persistence start level is the base day's daily value, which can include hours after the prediction; it is a reference level, not a scored realisation.
- **Versions never pooled silently.** `rulesVersion`, `bindingVersion` and `baselineMethod` are group dimensions (`byClass`), `inputs.versions` counts every version seen, and `warnings` names `MIXED_RULES_VERSIONS`, `MIXED_BINDING_VERSIONS`, `MIXED_BASELINE_METHODS`.
- **Duplicates.** The same lake, run and time seen twice (a line repeated, or an object copied) counts once (`duplicateRecords`). Scoring twice with the same inputs and `--as-of` gives identical bytes.
- **Stale history.** `inputs.historyLatestDate` per lake, and `STALE_HISTORY` when a lake's history stopped before the grace window; later targets are `pending`/`missing`, never imputed.
- **Default `--as-of`** is today (UTC) only after 12:00Z, otherwise yesterday, so a lake-local day that is still running anywhere in the US (Hawaii ends 10:00Z) is not read as a realisation.

`jobs/lake-brain/ledger/score_predictions.py` (see its README) writes `predictions_scores/{YYYY-MM}.json`: per lake and per class (provider, poolBasis, historicalTier, kind, rulesVersion), for each horizon the number of predictions, pending, missing and scored, realised coverage of [p10,p90] and [p02,p98], tail rate, RAPID exceedance rate against the stored threshold (and against the target day's own p95), and a label-persistence table with the next-24 h change against the STABLE floor.

### How it relates to the pre-registered criteria
The v2 hold-out criteria H-A to H-D (coverage near 0.80, tail below 0.06, RAPID rate between 0.03 and 0.08, label stability) were set for the hold-out. The ledger's counts are the inputs a prospective application would use (coverage, tail rate and RAPID rate per lake and class). Which thresholds apply prospectively, and when they are applied once, is a decision that belongs in a new pre-registration before the 12 months are read. Proposed `PARTIAL` item 4 (ledger running at least 90 days and a first monthly scorer output) is a process check, not evidence of accuracy.

## Start record
The ledger was first enabled in production on **2026-10-13 18:53:14 UTC**. Validation of the Lake Brain stays `NOT_VALIDATED`; the ledger starting does not change any status.

| Item | Value |
|---|---|
| First ledger object | `gs://sector-lake-brain/predictions/2026/10/13/185314Z-740761e4e50a.jsonl` (6,620 bytes, 5 records) |
| First run | Cloud Run job execution `lake-brain-qz28h`, job image `brain-jobs:98c8871798c5` (adoption branch commit `98c88717`), health `HEALTHY`, 0 errors |
| `rulesVersion` in force | `lake-level-rules-v2` (pre-registration commit `4a59715b`) |
| `baselineMethod` | `doy15-percentile-v2` (the 4 TVA pilots carry the `nws:rvd` rate filter from commit `98c88717`) |
| `bindingVersion` in force | `bindings-2026-10-13.1` |
| Lakes recorded | the 5 reviewed pilots (Guntersville, Wheeler, Wilson, Pickwick, Hartwell); no generated binding is REVIEWED |
| Historical tier at start | `FULL` for all five (17 / 18 / 18 / 16 / 60 complete years) |
| Trigger | the `brain-orchestrator` hourly wake-up (`50 * * * *` UTC) starts `lake-brain` when it is stale; no new schedule was created |
| Earliest meaningful scoring | 1 d horizons from 2026-10-14; 30 d horizons from 2026-11-12; first monthly scorer run: 2026-11-01 for October |
| Rollback | `IMAGE=…/brain-jobs:e6a5026f5d0f bash jobs/lake-brain/deploy-job.sh` (the previous image); ledger objects already written are immutable and are kept |

## Audit — 2026-10-13T20:18Z
Read-only (`gcloud storage ls -a -l -L` / `cat`, `gcloud run jobs executions list|describe`, `gcloud logging read`). Nothing was written, deleted or reset; the Start record and the prediction object are untouched. The ledger is 85 minutes old, so most checks have a population of one; they are listed so the same audit can be repeated and compared.

| Check | Result |
|---|---|
| Objects under `predictions/` (all generations, `ls -a`) | **1** object, 1 generation, 0 noncurrent versions |
| Object | `predictions/2026/10/13/185314Z-740761e4e50a.jsonl`, 6,620 bytes, `application/x-ndjson` |
| Generation / metageneration | `1791917599867864` (= 2026-10-13T18:53:19.867864Z) / `1` |
| Creation time vs update time | both `2026-10-13T18:53:19Z`; metageneration 1 means never rewritten or re-tagged. Content `sha256 898e958a…4840`, MD5 `IHxrJEsUFK/bsYM9LNodGA==`, CRC32C `GlP6gg==` (the scorer's `inputsSha256` over the lines equals the file hash) |
| Records per object | 5 lines (1,319 / 1,351 / 1,329 / 1,309 / 1,312 bytes), 5 distinct lakes, 1 record per (lake, base date) |
| Duplicates | **0** (lake, run, time) and **0** (lake, base date) |
| Runs since 18:53:14Z that should have written | **0** expected, **0** actual. The next run is due at the first hourly `:50` wake where the published state is at least 3 h old: 21:50 would be 2.95 h, so **about 22:50Z**. The orchestrator woke at 18:56:52 (manual) and 19:50:00 and logged `SKIP lake-brain: published state is current` both times. A 20:50 wake had not happened yet at audit time |
| Missed runs | 0 |
| Executions of `lake-brain` | 5 in the job's history: `47lvs` 05:33:31Z, `gb9jd` 08:51:40Z, `8kq9r` 12:51:45Z, `hqngr` 16:52:01Z (all with the previous image `brain-jobs@sha256:b795690c…`, which has no ledger code and wrote none, by design), and `qz28h` 18:51:56Z (image `sha256:8fab1676…`, label `commit=98c8871798c5`, the first ledger run). All 5 completed 1/1, 0 failed. Cadence between scheduled runs is 4 h (3 h stale threshold plus the hourly wake), not the 2 h assumed when the Volume section was first written (corrected above) |
| Ledger write warnings | **0.** The job prints `! ledger: …` for any ledger warning; no such line exists in `qz28h`'s log, and the only WARNING-or-above entries for the job today are two audit-log `SetIamPolicy ... 'lake-brain' does not exist` errors at 05:25Z, from the first deploy of the job before it existed (none from any execution). (The only `!` line of the day is `! Lake Hartwell|SC: history: CWMS daily unavailable` at 08:54Z, a history fetch in a pre-ledger run, unrelated to the ledger.) The current image does not print the object path, so the log carries no positive confirmation of the write; the bucket listing is the evidence. `LakeBrainJob` now prints `ledger: enabled · <object> (N records)` (takes effect with the next image) |
| `rulesVersion` | `lake-level-rules-v2` ×5; `brainVersion` `1.0.0` ×5 |
| `bindingVersion` / status | `bindings-2026-10-13.1` ×5, all `REVIEWED` |
| `baselineMethod` | `doy15-percentile-v2` ×5 |
| `baselineVersion` | 5 distinct values: Guntersville `…@2026-10-13#b6ab068b`, Pickwick `#35ea339a`, Wheeler `#367f669f`, Wilson `#80dd72fd`, and Lake Hartwell `doy15-percentile-v2@2026-10-12#9bfba66b` (a baseline from the previous day: the other four were rebuilt in this run) |
| `historicalTier` / `baselineStatus` | `FULL` / `SUFFICIENT` ×5 |
| Baseline edges | every one of the 15 horizons (5 lakes × +1/+7/+30) carries a full `band` (p02 < p10 < p50 < p90 < p98, checked) with `bandN` 238 to 450, and a `rateP95` with `rateN` 46 to 441. 0 horizons without a band |
| Target dates | all 5 lakes: +1 `2026-10-14` (doy 287), +7 `2026-10-20` (doy 293), +30 `2026-11-12` (doy 316). Every target is after the base date `2026-10-13` |
| Observations behind the claims | Guntersville, Pickwick, Wheeler, Wilson at `2026-10-13T18:00:00Z` (53 min before `generatedAt`); Lake Hartwell at `17:00:00Z` (1 h 53 min before) |
| Labels | Guntersville IN_ZONE/UNUSUAL/FALLING; Hartwell BELOW_ZONE/UNUSUAL/RISING (flood NORMAL); Pickwick IN_ZONE/NORMAL/RISING; Wheeler IN_ZONE/NORMAL/STABLE; Wilson IN_ZONE/UNUSUAL/STABLE |
| Stored thresholds | `rapidThresholdFt` 0.32 / 0.26 / 0.61 / 0.26 / 0.37; `stableFloorFt` 0.10 ×5 |
| Pending vs scored | all 15 horizons pending; scored 0; missing 0 |
| Bucket protection | versioning **on**; soft delete 7 days; no retention policy; no lifecycle rule; uniform bucket-level access; public access prevention enforced. `brain-writer` has `roles/storage.objectAdmin` on the whole bucket, so nothing in IAM stops that identity from overwriting or deleting a ledger object; protection is the writer's check (and, from the next image, `ifGenerationMatch=0`), versioning and the 7-day soft delete |

Dry-run scorer output against these live objects (`--month 2026-10 --as-of 2026-10-13`): 1 object, 5 records, 5 primary, 5 lakes, 0 malformed, 0 invalid, 0 warnings, every horizon `pending` (15 of 15), no coverage or tail rate (no denominator). Local file only: `~/Desktop/Development/Sector_Research_Data/lake-brain/ledger-dryrun-2026-10-13/predictions_scores/2026-10.json`.

Findings to act on: (1) cadence is 4 h, not 2 h (documentation corrected; the ledger gives about 6 independent-ish claims per lake per day, not 12); (2) object immutability is not enforced by IAM; (3) the log does not confirm the object path until the next image; (4) there are no history gaps for the pilot lakes except Lake Hartwell's latest history row is `2026-10-12` (its daily CWMS pull warned at 08:54Z), which would show as `pending`/`missing` for a target only after grace.

## Monthly evaluation (first: 2026-11-01, October predictions)
Nothing is scheduled. The first evaluation is a command run by hand; a Cloud Run job plus a Cloud Scheduler entry are prepared below and **not executed**.

**Run it (read-only on the bucket, writes one local file):**
```bash
cd <repo> && python3 jobs/lake-brain/ledger/score_predictions.py --month 2026-10 --out ./ledger-scores
# default --as-of is today (UTC) after 12:00Z, else yesterday. Output: ./ledger-scores/predictions_scores/2026-10.json
```
What it reads: `gs://sector-lake-brain/predictions/2026/10/*` and `gs://sector-lake-brain/history/*/daily.csv` through `gcloud storage cat|ls`. Authentication is the caller's gcloud login. To keep the file with the data, `--out gs://sector-lake-brain` writes `gs://sector-lake-brain/predictions_scores/2026-10.json` with `gcloud storage cp` (a derived file that is overwritten on each run; the bucket is versioned). That copy is a bucket write and is Michael's call.

**What 2026-11-01 will and will not show.** October bases (Oct 13 to Oct 31) have +1 d targets Oct 14 to Nov 1 and +7 d targets Oct 20 to Nov 7; only targets before the as-of date are scored. All +30 d horizons (Nov 12 to Nov 30) are still `pending`, and the last +1/+7 targets are too. The same command with a later `--as-of` only moves counts from pending to scored: rerun `--month 2026-10` on or after 2026-12-02 (when the last +30 d target, Nov 30, has a complete day and the 3-day grace is over; use `--as-of 2026-12-03`). Proposed `PARTIAL` item 4 asks for the ledger to have run 90 days with a first monthly output: that is **2027-01-11**; producing the 2026-11-01 file is a process check, not evidence of accuracy, and nothing here changes `NOT_VALIDATED`.

**Prepared, not executed: scheduled scorer (decision for Michael).** The Swift Brain image has no Python or gcloud, so the scorer needs its own small image. The image below has not been built or tested; check `python3` and `gcloud` are on its PATH (`docker run --rm --entrypoint python3 …`) before relying on it.
```bash
# 1. image from a scratch directory (the script is standard library only)
mkdir -p /tmp/lake-ledger-scorer && cp jobs/lake-brain/ledger/score_predictions.py /tmp/lake-ledger-scorer/
printf 'FROM google/cloud-sdk:slim\nCOPY score_predictions.py /app/score_predictions.py\nENTRYPOINT ["python3","/app/score_predictions.py"]\n' > /tmp/lake-ledger-scorer/Dockerfile
gcloud builds submit /tmp/lake-ledger-scorer --project sector-9393c \
  --tag us-central1-docker.pkg.dev/sector-9393c/cloud-run-source-deploy/lake-ledger-scorer:2026-11
# 2. Cloud Run job: default month = previous month, default as-of = today after 12:00Z, output to the bucket
gcloud run jobs create lake-ledger-scorer --project sector-9393c --region us-central1 \
  --image us-central1-docker.pkg.dev/sector-9393c/cloud-run-source-deploy/lake-ledger-scorer:2026-11 \
  --service-account brain-writer@sector-9393c.iam.gserviceaccount.com \
  --args="--out,gs://sector-lake-brain" --tasks 1 --max-retries 1 --cpu 1 --memory 512Mi --task-timeout 15m
gcloud run jobs add-iam-policy-binding lake-ledger-scorer --project sector-9393c --region us-central1 \
  --member serviceAccount:brain-writer@sector-9393c.iam.gserviceaccount.com --role roles/run.invoker
# 3. Scheduler: 13:30 UTC on the 1st (after the 12:00Z completeness rule), same shape as brain-orchestrator
gcloud scheduler jobs create http lake-ledger-scorer-monthly --project sector-9393c --location us-central1 \
  --schedule "30 13 1 * *" --time-zone UTC --http-method POST \
  --uri "https://run.googleapis.com/v2/projects/sector-9393c/locations/us-central1/jobs/lake-ledger-scorer:run" \
  --oauth-service-account-email brain-writer@sector-9393c.iam.gserviceaccount.com \
  --oauth-token-scope https://www.googleapis.com/auth/cloud-platform --attempt-deadline 180s
```
Rollback: `gcloud scheduler jobs delete lake-ledger-scorer-monthly --location us-central1` and `gcloud run jobs delete lake-ledger-scorer --region us-central1`. The scheduled job scores only the previous month; late +30 d targets need the manual rerun described above (or a second scheduler entry with `--args=--month,…`, which cannot compute its own month).

## Open decisions (Michael)
1. **Role mailbox** for the User-Agent contact (`SECTOR_CONTACT`); none exists. Without it requests identify as `Sector-LakeBrain/1.0 (io.sector.co; Rehtac Labs; read-only public data)`. NWS/NWPS accepts any self-identifying User-Agent; its documentation asks for a contact so they can reach the operator before blocking, so set one before the fleet scales.
2. **Enforce immutability in IAM** (optional): replace the bucket-wide `objectAdmin` for the writer by `objectAdmin` on `history/`, `baselines/`, `presence/` (IAM condition on object name prefix) and `objectCreator` only on `predictions/`. Not prepared as commands because the conditions need testing against the writer's real calls, and the current protection (create-only write, versioning, 7-day soft delete) already covers accidents; it does not cover a compromised writer.
3. **Scheduled scorer** (commands above) versus a calendar reminder to run it by hand.
