Claude request (under Owner approval 2026-11-22): Wind strong-wind methods, past-window test (read-only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

Read-only research for gap WIND-CNF-001, on the Mac mini only. Nothing in this request runs on Michael's MacBook Pro. Do not change frozen-scores.json, wind-measurements-evidence.json, GAPS.json, any score, RTDB, buckets, the wind-hourly job, the provider bake-off collector, Pulse jobs or schedules. Do not create cloud jobs. Do not open, fetch or score H2 (sealed until 2027-01-01; the runner refuses it by the system clock). Use the Engine checkout at the merged commit of Sector_Engine PR #245 (or its branch research/wind-strong-wind-method-2026-11-23 if it has not merged), with the Wind runtime's Python deps (numpy, eccodes). End with a research closeout.

Protocol: docs/brains/wind-strong-wind/WSW-2026-11-23-R2.protocol.json, sha256 ba05492be82102fdba170b8dd5181ec557505622246e6a780c52a6ffc129633b (pre-registered and pushed before any data was fetched; it supersedes WSW-2026-11-23, which was never run). Runner: tools/research/wind_strong_wind.py (the sha256 is pinned in it). Methods: B0 deterministic NBM (reference), M-A NBM P90 exceedance (no fitted parameter), M-B night upper-tail quantile mapping fitted on CAL+H1 only. Past window: NBM pre-v4.3 (v4.2) inits 2025-01-02 to 2025-05-26.

Storage (Michael, 2026-11-23). Everything goes under the Wind research folder that Cortex `research-path` returns, on the research SSD, never the boot disk; use `--out <that folder>/wsw-2026-11-23-r2`. That SSD froze Pulse once on Nov 21 and still awaits a repair, so:
- Before starting, report the free space on that volume (`df -h <folder>`). Stop if it is under 80 GB. Every fetch also refuses below 80 GB (`--min-free-gb`, default 80).
- Download and process one month at a time with `--month YYYY-MM`, checking free space before each month.
- Do not run during Pulse's busy minutes (:40-:59 UTC). Start a month only between :00 and :35; if it is still running at :40, stop it (the fetch is resumable and skips complete cycles) and resume after :00.
- Stop cleanly on any I/O error, or if the command shows no progress for more than 10 minutes. Report it; do not retry in a loop.
- Network budget is enforced by the runner per window (60 GB downloaded, 48 h wall clock, cumulative across runs; it stops before the next request). Only lake cut-outs are written to disk, so disk use is far smaller than the download.

1. `verify`. Stop if it fails.
2. Never-read check: confirm from the wind-brain manifest (and the W-NOW-1..3 records, whose windows are not in Git) that no NBM or METAR/ASOS object for the 8 frozen stations dated 2025-01-01 to 2025-05-28 was read before. If one was, stop and report it; fetch nothing.
3. CAL+H1 for the fit. Find the Stage 3C corpus store (research default: a historical/v50 folder in the user's macOS cache). If an intact copy is on the Mac mini, use it in place: `fit --out … --corpus-store <it>`. If it is only on the MacBook Pro, do not touch the MacBook: fetch CAL+H1 on the Mini month by month instead (`fetch --window cal_h1 --month 2026-05 … 2026-10`), then `fit --out …`. Record the fit sha256 and whether it came from the corpus or a fetch.
4. Smoke test: `fetch --window pw --out … --month 2025-01 --max-pairs 6`, then check that the cycle files in `pw/store` carry `speedP90`. If they do not (the bucket may not serve qmd for this generation), report it and stop: M-A is NOT_EVALUABLE and the past window can only be exploratory.
5. `fetch --window pw --out … --month <YYYY-MM>` for 2025-01, 2025-02, 2025-03, 2025-04, 2025-05 in order. Record each month's bytes (from pw/budget.json) and the free space after it.
6. `rows --window pw --out …`, then `score --window pw --out …` (2000 resamples, fixed). Record the sha256 of rows.jsonl and wsw-result.json. Both are written once and never overwritten.
7. Register in the folder's manifest.json: the raw NBM/METAR stores (cal_h1/store if fetched, pw/store) as RECONSTRUCTABLE items (public NOAA/IEM data, re-downloadable with this runner and protocol; collectionSha256 with hashMethod sha256-tree-v1), and the fit, rows, result and budget files with their sha256.

Post a short summary on #51 (under 15 lines):
- protocol sha256; fit sha256 (source, n rows, top knot); rows and result sha256
- never-read check (step 2) and the smoke test (step 4)
- rows: night, common, P90 coverage; observed >= 15 mph events in the common rows
- per method (B0, M-A, M-B): outcome with its WI4 credit and scoreboard gate, pooled POD / FAR / CSI, and the CSI-difference lower bound vs B0
- the label "NBM v4.2 winter-spring: version-transfer caveat, not a v5.0 measurement"
- free space before and after each month, bytes and hours used, any stop (I/O error, hang, busy-minute pause, budget)
- questions for Michael: (a) whether a post-processed signal (M-A or M-B) may earn WI4 credit at all, since WI4 says "deterministic" (rubric governance); (b) both methods go to the one-shot H2 score on or after 2027-01-01 (pre-registered, with the four-rule correction)

Nothing is admitted to any score. A candidate evidence block, if ever proposed, goes through refresh_wind_score.py (HELD for review) and Michael.
