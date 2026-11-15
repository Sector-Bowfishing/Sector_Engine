# Session record: Wind risky-night flag shadow (NBM v5.0 probability fields)

Standards: Rehtac Cortex 3.1.3 @ 8ad5469, pack sector/engine. Date: 2026-11-15. Branch: `cortex/wind-pw15-shadow-2026-11-15` (off main f1fd4a8). Mac mini helper run.

## Scope
Owner approval on Sector_Ops #51 (comment 6882501008), steps 1-2: the Wind runtime reads the NBM v5.0 qmd probability fields (off by default), then a 30-day live shadow of the pW15 >= 0.15 flag on the Mac mini. No customer output, no score, no deploy, no IAM.

## Done
- `sector_wind/pw15.py`: for each W1 point and lead 1/3/6/12/18 of a 00/06/12/18Z NBM cycle, reads core WIND and the four qmd exceedance fields plus the 50/75/90% levels, computes pW15 with the frozen `exceed()` rule (identical to `forcing_eval.exceed`), and records `wouldFlag = night and NBM < 15 mph and pW15 >= 0.15`. Stored under `pw15-shadow/<cycle>.json.gz`. Off unless `WIND_PW15_SHADOW=1`.
- `live.py` hook (same switch) and `main.py pw15` (records the last 24 h of synoptic cycles; refuses without the switch).
- Tests: `tests/test_pw15_shadow.py`.

## Finding
`points.ingest_nbm_points` (#90) passes only sparse point cells to `row_scramble_ratio`, which needs neighbouring cells and returns NaN, so the decoder self-check fails closed on every real cycle. Its test stubs the check. Not fixed here (out of scope, off by default); pw15 uses a contiguous patch around the first point, as the W-NOW-3 fetch did.

## Verification
Wind brain tests pass; a live run on the Mac mini recorded 142 points for the 06/12/18Z cycles of 2026-11-14 (8-12 night would-flags per cycle).

## Not done
The 30-day scorer (flag vs METAR) is written after the log has data. Switching the flag on in the app stays Michael's decision.
