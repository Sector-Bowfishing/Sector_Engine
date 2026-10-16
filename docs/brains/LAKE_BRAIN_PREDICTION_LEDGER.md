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
- **Failure isolation:** the ledger write cannot throw out of the run. A failure sets `LakeBrainRunResult.ledgerWarning` (also appended to `archiveErrors`, which the job prints). It never changes `ok`, `health`, `writeError` or any RTDB path.
- **Dry run:** a run against a local/read-through dry-run store never writes the ledger to the history archive (which may be `gs://`); it writes under `<dry-run dir>/_ledger/`. `LakeBrainRunOptions.ledgerArchive` overrides the target (tests, local replays); `ledgerEnabled = false` turns it off.

## Volume
Measured record size ≈ 1.3 KB (about 0.7 KB without bands, an estimate). Pilots today: 5 lakes, a stable lake is rechecked about every 2 h, so about 12 objects/day of about 6.5 KB (about 80 KB/day, about 30 MB/year, about 4,400 objects/year).
Fleet scale, 315 bound lakes, every lake due each 2 h run: about 400 KB per object, 12 objects/day, about 3,800 lines/day, about 5 MB/day, about 1.8 GB/year, about 4,400 objects/year. Hourly runs double that. Object count stays small (compare the baseline-artifact hazard of about 115 k objects/year in `LAKE_BRAIN_FLEET_SCALING.md`); storage cost is a few cents a month.
**Retention:** keep everything; no lifecycle deletion on `predictions/`. The `VALIDATED` path needs at least 12 months, and the ledger is the audit trail.

## Guarantees
1. A line is a claim made at `generatedAt`, from the baseline and thresholds named in it. Nothing is recomputed afterwards.
2. Append-only, one object per run, never overwritten.
3. A failure of the ledger cannot fail or alter a Brain publish.
4. The scorer never scores a prediction whose target date has not arrived, and never imputes a missing realised value.

## What it does not mean
- It is not validation, and it does not make the Lake Brain `PARTIAL`. `PARTIAL` still needs every item in the proposed definition, and that definition is itself not adopted.
- A stable lake is rechecked about every 2 h, so many lines make the same claim about the same day. Headline figures use one line per lake per base date (the earliest). Neighbouring days and lakes on one river are correlated. Rates have no sampling-error interpretation.
- Realised levels are the operators' daily values as the history archive holds them at scoring time. Operators revise those values (the merge lets newer rows win); the bands and thresholds are not revised.
- A rules or baseline change makes a new `rulesVersion` / `baselineMethod`; the scorer reports by `rulesVersion`. Results across versions are not pooled silently.
- No pass/fail is computed anywhere in the ledger or the scorer. Applying the pre-registered v2 criteria to ledger data is a separate, explicit act.

## Scoring
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
