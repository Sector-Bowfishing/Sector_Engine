# Wind published-score refresh — handoff to the shared `brain-orchestrator` / `feat/cost-efficient-scheduling` lineage

**Status: Wind canonical scorer = 3.3. Durable publication is WAITING on the shared brain-orchestrator lineage to consume the updated generated `frozen-scores.json`.**

## What was approved and done (Michael, 2026-10-13)
The refresh of the published Wind score was approved *through the normal canonical path*, with: no hand-edit, no rubric change, no threshold change, no evidence tuning, no redeploy of the shared orchestrator from the Wind session, and no temporary one-off write. Wind did exactly that:
1. Re-ran the canonical scorers immediately before generating (`jobs/wind-hourly/research/wind_score_entry.py --refresh --emit docs/brains/scoring/frozen-scores.json`): metadata refreshed from the ledger/run summaries/executions (no live values; H2 sealed), `sector_wind.scoreboard.compute` (frozen rubric v1) and `sector_wind.bowfishing_score` (BWIS v1).
2. The generator **spliced only the `wind` object** into `docs/brains/scoring/frozen-scores.json`; every other entry is byte-identical (the script asserts it).
3. Committed on `feat/wind-brain-adoption`. Nothing was written to the Brain RTDB; the deployed orchestrator was not touched.

## The numbers (record: `data/wind_score_refresh_record.json`)
| | Old published | New (generated) |
|---|---|---|
| Wind Certification | **3.1** (basis FROZEN, scoreUpdatedAt 2026-10-12T06:16:16Z) | **3.3** (raw 3.27; 32.65 / 100 points; basis COMPUTED; scoreUpdatedAt = scorer time in the file) |
| BWIS v1 | 5.4 (54.06) | 5.4 (54.16) |
| Score version | wind-certification-rubric-v1 | wind-certification-rubric-v1 (unchanged) |
| Dimension changes | — | **only dimension 8 Freshness/reliability 0 → 1.33 / 8** ("5/30 complete days, worst completeness 1.0000, median age 68 min"); 1, 3, 6, 7 = 0; 2 = 4.32; 4 = 5; 5 = 10; 9 = 4; 10 = 8 |
| Caps | 6.0 (exposure/surface never field-validated), 7.0 (land-only) | same, neither binding |
| Source evidence | frozen CAL+H1 skill file `v50_corpus_validation.json` (sha prefix in the block's `evidence`), live reliability ledger metadata through the `evidence.metadataThrough` timestamp | scorer code `evidence.scorerCode` (git short SHA) |
Dry run of the real publisher with the generated file (read-only): **exactly one change — `wind: 3.1 → 3.3`**; Engine score unchanged at 7.1; 10 of 628 control paths differ (the wind score blocks and the overview timestamp). The publisher was *not* run with `--write`.

## What the orchestrator / `feat/cost-efficient-scheduling` owner must do
1. **Carry the generated `docs/brains/scoring/frozen-scores.json` (wind entry) into the orchestrator lineage before its next redeploy.** `jobs/brain-orchestrator/deploy-job.sh` copies that file into the image (`stage/docs/brains/scoring/`), so a redeploy from a tree that contains it is the whole publication step. (Cherry-pick this one file/commit, or take it with the Wind merge.)
2. **Until that happens, the currently deployed orchestrator (`brain-orchestrator@4e436e32267d`, hourly at :50, `score_brains.py --write --if-changed`) keeps republishing the old 3.1** — it re-publishes after any Brain state change, which for Wind is every hour. **Do not treat any temporary published value as durable until the orchestrator image contains the updated generated file.** A one-off `--write` from anywhere else would be reverted at the next cycle (observed: scores published at 10:52, 11:51 … 20:51 UTC on 2026-10-13).
3. After redeploy, verify (read-only): `GET /scores/wind` → value 3.3, basis COMPUTED, scoreVersion wind-certification-rubric-v1; `GET /control/overview/brains/wind/score`; Activity shows one `score.changed` event `wind score 3.1 → 3.3`.
4. **Re-generate before each deploy** if more valid live days have accrued: `python research/wind_score_entry.py --refresh --emit <repo>/docs/brains/scoring/frozen-scores.json` (the value moves with dimension 8, ≈ +0.27 raw points per valid day; 30 valid days ≈ 3.9). Never edit the number by hand.

## What Ops will and will not show after the orchestrator publishes
- Overview tile (`BrainScoreRow`) prefers `control.brains.wind.score` → will show **3.3** (basis computed, "scored <time> ago").
- The Wind Brain page's "Validation & gates" card and `brainScore()` fallbacks read the Wind registry field `/brains/wind.scores.windCertificationScore` (and BWIS), written by `wind-hourly` from the `validation_evidence.json` baked into **its** image (still 3.1 / 5.4). That is a second consumer needing a `wind-hourly` redeploy (blocked on the prerequisite branch) or an Ops change to prefer the canonical score block. Until then Ops can show 3.3 on the overview and 3.1 on the Wind page. (Ops is not edited from the Wind session.)
- SCORING.md still lists Wind as "FROZEN 3.1"; the table row should read "COMPUTED from the Wind scorer, generated block" when this lands.

## Prerequisite line for the Wind handoff
**Wind canonical scorer = 3.3; durable publication is waiting on the shared brain-orchestrator lineage to consume the updated generated frozen-scores.json.**
