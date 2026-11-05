# Session record: run 2026-11-04 (8), Lake level stack, SI-A2/A4, Water Temp plan, W1b, Lake local B-steps (Sector_Ops #50)

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine

## Owner instruction
- **Merge after review:** #85, #89 and #94. Code only, the flag stays off, no deploy, nothing customer-visible. #83, iOS #219 and iOS #220 stay held.
- **Draft only:** SI-A2 and SI-A4; a Water Temp G3/G4 plan on a new Ops issue; the Wind W1b score and the app-source steps that need no cloud or live writes.
- **Run locally:** Lake B1, B3 and B4 where no IAM, cloud or live token is needed. Skip B2 and B5.
- **Decision 4 (B5):** not decided.

## Merged (after review, CI green on each final commit)
- **#85, Lake level customer path, `308da122`.** Review fix: `/lake/level` is routed only where `SECTOR_LAKE_LEVEL_OUTPUT=1`, so a deploy with the flag off exposes no endpoint. With the flag on it still fails closed: no reader, so UNKNOWN.
- **#89, validated lakes, `fbecf2a1`.** The 30 ids equal the frozen Lake Beta V1 recommendation (18 A + 12 B). Being listed opens nothing.
- **#94, CUSTOMER-lane copy planner, `5c2098c7`.** It is pure and nothing calls it.
  - Note for the wiring PR: `plan` writes UNKNOWN over the previous copy of any eligible lake missing from a Lake write set.
  - The CUSTOMER family is still Cortex gap CG-3.1-8.
- #85 and #89 were stacked; each child was re-targeted to `main` after its parent merged.

## Drafts (no merge, no deploy)
- **#123 SI-A2:** `SI_ARTIFACT_JOB` (default off) makes Intelligence a **lease-only** artifact job.
  - It never runs in-process and never starts a Cloud Run job (none is deployed).
  - Under `--runner-leases` it is leased to a non-cloud primary; otherwise it holds.
  - Its `--plan` is still asked in-process (SI-P2 not decided). 7 new tests.
- **#124 SI-A4:** the packaged release stages into the Publisher context and resolves against Intelligence's own artifact lineage. It is refused while approval is NOT_RECORDED. No code change was needed; the test and a docstring fix are added.
- **#125 Wind:** the default-off `SECTOR_WIND_FORECAST_MODEL=ncep_nbm_conus` overlays NBM **wind only** on tonight's window and the outlook. A null or failed value keeps `best_match`. The W1b result is added to `APP_WIND_SOURCE_REVIEW_V1.md`, and there is a DRAFT scoring review with owner decisions WS-1 to WS-4.
- **Sector_Ops #52:** the Water Temp G3/G4 plan, plan only.
  - G3 is the per-Brain registry move at the CENTRAL cutover (the CG-3.1-15 pattern): rows for `/health/brains/water-temp` and its three sources.
  - G4 has the release in place with approval NOT_RECORDED; the physics scope is decision WT-G4a.

## Research (private Sector Research; owner-approved)
- **W1b scored once** (`wind-brain/research/w1b-app-leads-2026-11-02`). NBM is not worse than `best_match` at 0 h and at days 3–7.
- **Deviation, reported:** the frozen `score` stopped with `KeyError`, because the archive served `previous_day8` as all nulls.
  - `AMENDMENT_1_D8_ALL_NULL.md`, hashed before scoring, applies §4 Day 8: `d8` is NOT_AVAILABLE. It was decided from sample sizes only.
  - The frozen tool and the pre-registration are unchanged.
- **Lake local B-steps** (`lake-brain/cutover/local-2026-11-05`, snapshot `5c2098c7`):
  - **B1** (local form) sealed one `lake-publication-v1` artifact for 5 lakes, with no database.
  - **B3 not run:** it needs a live read token.
  - **B4 and B4b** ran as mechanics only on an empty capture: 0 write attempts, and no lake blanked under a forced CWMS failure (Hartwell degrades to the USGS fallback and is flagged). G6 needs B3's capture.

## Verification
CI green: #85 (9 checks), #89 (9), #94 (7; Swift path-filtered), #123 (7), #124 (7), #125 (9). Local suites:
- **Python:** orchestrator 143, platform 886, Intelligence 106, Publisher 19.
- **Swift:** Lake level 5, wind model 3, forecast tests.

## Not done / gated
- #83, iOS #219 and iOS #220 are held.
- B2 (IAM), B3 (live read token) and B5 (Decision 4) are not run. #114 stays DO NOT MERGE.
- No cloud job, deploy, IAM change, write token, live token or database write. Research outputs were not uploaded to the backup bucket (cloud write).
