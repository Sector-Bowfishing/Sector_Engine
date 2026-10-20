# Lake Brain prediction ledger: scorer

Internal. Counts and rates only. **Lake Brain validation remains `NOT_VALIDATED`**; this tool does not change any status and has no pass/fail output.
Format and guarantees: `docs/brains/LAKE_BRAIN_PREDICTION_LEDGER.md`.

## What writes the ledger
The existing `lake-brain` job, after it has published to the Brain RTDB: one object per run at
`gs://sector-lake-brain/predictions/{yyyy}/{MM}/{dd}/{HHmmss}Z-{runId}.jsonl`. The job is started by the Brain Orchestrator when due and
daily by the hand-created Cloud Scheduler job `lake-brain-ledger-daily` (a `VALIDATION_EXCEPTION` in `control_manifest.json`; no repository
script creates it). No extra service. A pure skip run writes nothing.
A dry run writes under `<dry-run dir>/_ledger/` and never to the bucket.

## Run the scorer
```bash
# previous month, from the real bucket (read-only: gcloud storage ls/cat), results to a local folder
python3 jobs/lake-brain/ledger/score_predictions.py --out ./ledger-scores

# a given month, local copies of the data, fixed scoring date (repeatable)
python3 jobs/lake-brain/ledger/score_predictions.py --month 2026-11 --predictions /data/lake-brain --as-of 2026-12-15 --out ./ledger-scores
```
Options: `--month YYYY-MM` (default: the month before `--as-of`), `--predictions` and `--history` (a local directory or `gs://BUCKET`; default `gs://sector-lake-brain`; history defaults to the predictions location),
`--out` (a directory, or `gs://BUCKET/PATH` copied with `gcloud storage cp`; default `./ledger-scores`), `--as-of YYYY-MM-DD` (default: today UTC), `--grace-days N` (default 3).
Output: `{out}/predictions_scores/{YYYY-MM}.json`. Standard library only; tests: `python -m pytest jobs/lake-brain/ledger -q`.

Both locations use the same layout: `predictions/{yyyy}/{MM}/...jsonl` and `history/{lakeKey}/daily.csv` (`date,elevationFt,sourceId`, the `LakeDailyHistory` encoder; `lakeKey` = runs of non-alphanumerics become `_`).

## What the output holds
`primary` (one record per lake per base date, the earliest; the headline) and `allRecords` (every record pooled; not independent). Each has `overall`, `byClass` (provider, poolBasis, historicalTier, kind, rulesVersion) and `byLake`. Per horizon (1, 7, 30 days):
predictions, **pending**, **missingRealised**, scored; coverage of [p10,p90] and [p02,p98]; tail rate (below/above); RAPID exceedance against the stored `rapidThresholdFt` and against the target day's `max(p95, 0.25 ft)`.
`labelPersistence` per predicted trend label: the next 24 h change against the stored STABLE floor (mean, share within the floor, share over the stored RAPID threshold) and the next 72 h mean-rate class (RISING / STABLE / FALLING) against the label's direction.

- **Pending:** a target date on or after `--as-of` is never scored, even if the history has a row; a target within `--grace-days` before it with no row yet is also pending. **Missing:** arrived, grace over, no row; counted, never imputed.
- **Idempotent:** same inputs and `--as-of` give the same bytes (a SHA-256 of the input lines is in `inputs.inputsSha256`). The month file is overwritten as targets arrive (a month's +30 d horizon settles about two months after month end); scoring the same month later with a later `--as-of` only moves pending to scored.
- A header repeats `NOT_VALIDATED`; there are no verdict keys.

## Retention
Keep `predictions/` forever (no lifecycle deletion). Score files are small and re-creatable. History is the operators' daily values at scoring time (revisions are possible).

## How it feeds the pre-registered criteria and PARTIAL
- `LAKE_BRAIN_RULES_V2_PREREGISTRATION.md` H-A..H-D are hold-out criteria. The scorer produces the same quantities prospectively (coverage, tail rate, RAPID rate, label behaviour), per lake and class. Applying thresholds to ledger data needs its own pre-registration; this tool never applies one.
- `LAKE_BRAIN_PARTIAL_VALIDATION_DEFINITION.md` item 4 asks for the ledger to have run at least 90 days with a first monthly scorer output. Producing that output shows the process works. It is not evidence of accuracy, and nothing here changes the status. `VALIDATED` additionally needs at least 12 months scored once under a pre-registered rule.
