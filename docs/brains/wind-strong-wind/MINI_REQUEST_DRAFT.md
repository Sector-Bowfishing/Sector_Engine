Claude request (under Owner approval 2026-11-22): Wind strong-wind methods, past-window test (read-only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

Read-only research for gap WIND-CNF-001, on the Mac mini only. Nothing in this request runs on Michael's MacBook Pro. Do not change frozen-scores.json, wind-measurements-evidence.json, GAPS.json, any score, RTDB, buckets, the wind-hourly job, the provider bake-off collector, Pulse jobs or schedules. Do not create cloud jobs. Do not open, fetch or score H2 (sealed until 2027-01-01; the runner refuses it by the system clock). Use the Engine checkout at the merged commit of Sector_Engine PR #245 (or its branch research/wind-strong-wind-method-2026-11-23 if it has not merged), with the Wind runtime's Python deps (numpy, eccodes). End with a research closeout.

Protocol: docs/brains/wind-strong-wind/WSW-2026-11-23-R3.protocol.json, sha256 82f96596197d6af32e43b9e01ce152e922f3a0c0a42993641993a2da0fda68a2 (registered alone before any runner change and before any data was fetched; it supersedes R2 and WSW-2026-11-23, neither of which was run). Runner: tools/research/wind_strong_wind.py (the sha256 is pinned in it). Methods: B0 deterministic NBM (reference), M-A NBM P90 exceedance (no fitted parameter), M-B night upper-tail quantile mapping fitted on CAL+H1 only. Past window: NBM pre-v4.3 (v4.2) inits 2025-01-02 to 2025-05-26. Unknowns count against a method: a missing or incomplete planned cycle makes the window INCOMPLETE, a missing forecast value is a miss, and missing observations are counted (more than 20% -> INCOMPLETE).

Storage (Michael, 2026-11-23). Everything goes under the Wind research folder that Cortex `research-path` returns, on the research SSD, never the boot disk; use `--out <that folder>/wsw-2026-11-23-r3`. That SSD froze Pulse once on Nov 21 and still awaits a repair, so:
- Before starting, report the free space on that volume (`df -h <folder>`). Stop if it is under 80 GB. The runner also checks free space before every cycle and day (`--min-free-gb`, default 80).
- Download and process one month at a time with `--month YYYY-MM`.
- Do not run during Pulse's busy minutes (:40-:59 UTC). Start a month only between :00 and :35; if it is still running at :40, stop it with Ctrl-C (the budget is saved on SIGINT/SIGTERM; the fetch is resumable and skips complete cycles) and resume after :00.
- Stop cleanly on any I/O error, or if the command shows no progress for more than 10 minutes. Report it; do not retry in a loop.
- The runner enforces the network budget per window (60 GB including retries, 48 h, cumulative across runs) and refuses redirects. Only lake cut-outs are written to disk, so disk use is far smaller than the download.

1. `verify`. Stop if it fails.
2. Never-read check: confirm from the wind-brain manifest (and the W-NOW-1..3 records, whose windows are not in Git) that no NBM or METAR/ASOS object for the 8 frozen stations dated 2025-01-01 to 2025-05-28 was read before. If one was, stop and report it; fetch nothing.
3. CAL+H1 for the fit. Find the Stage 3C corpus store (research default: a historical/v50 folder in the user's macOS cache). If an intact copy is on the Mac mini, use it in place: `fit --out … --corpus-store <it>`. If it is only on the MacBook Pro, do not touch the MacBook: fetch CAL+H1 on the Mini month by month (`fetch --window cal_h1 --out … --month 2026-05` … `2026-10`; it never fetches a day on or after 2026-10-07), then `fit --out …`. The fit refuses a CAL+H1 with any missing or incomplete cycle; report its accounting if it does.
4. Post the fit sha256 on Sector_Ops #51 as its own comment (with its source and n rows), BEFORE any past-window request. Every later step needs it as `--fit-sha <sha>`; the runner refuses without it and records the first use in fit-record.json.
5. Smoke test: `fetch --window pw --out … --fit-sha <sha> --month 2025-01 --max-pairs 6`, then check that the cycle files in `pw/store` carry `speedP90`. If they do not (the bucket may not serve qmd for this generation), report it and stop: M-A would be NOT_EVALUABLE and the past window would test only M-B.
6. `fetch --window pw --out … --fit-sha <sha> --month <YYYY-MM>` for 2025-01, 2025-02, 2025-03, 2025-04, 2025-05 in order. Record each month's bytes and attempts (pw/budget.json) and the free space after it.
7. `rows --window pw --out … --fit-sha <sha>`, then `score --window pw --out … --fit-sha <sha>` (2000 resamples, fixed). Record the sha256 of rows.jsonl, accounting.json and wsw-result.json. All are written once and never overwritten.
8. Register in the folder's manifest.json: the raw NBM/METAR stores (cal_h1/store if fetched, pw/store) as RECONSTRUCTABLE items (public NOAA/IEM data, re-downloadable with this runner and protocol; collectionSha256 with hashMethod sha256-tree-v1), and the fit, fit-record, rows, accounting, result and budget files with their sha256.

Post a short summary on #51 (under 15 lines):
- protocol sha256; fit sha256 (as posted in step 4); rows, accounting and result sha256
- never-read check (step 2) and the smoke test (step 5)
- accounting: planned pairs and rows, missing/incomplete cycles, rows built, obs missing (share, worst station), b0 and p90 missing; observed >= 15 mph events in the scored rows
- per method (B0, M-A, M-B): outcome (incl. INCOMPLETE) with its WI4 credit and scoreboard gate, pooled POD / FAR / CSI, and the CSI-difference lower bound vs B0
- the label "NBM v4.2 winter-spring: version-transfer caveat, not a v5.0 measurement"
- free space before and after each month, bytes, attempts and hours used, any stop (I/O error, hang, busy-minute pause, budget)
- questions for Michael: (a) whether a post-processed signal (M-A or M-B) may earn WI4 credit at all, since WI4 says "deterministic" (rubric governance); (b) both methods go to the one-shot H2 score on or after 2027-01-01 (pre-registered, with the four-rule correction)

Nothing is admitted to any score. A candidate evidence block, if ever proposed, goes through refresh_wind_score.py (HELD for review) and Michael.
