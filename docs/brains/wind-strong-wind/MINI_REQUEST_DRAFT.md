Claude request (under Owner approval 2026-11-22): Wind strong-wind methods, past-window test (read-only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

Read-only research for gap WIND-CNF-001. Do not change frozen-scores.json, wind-measurements-evidence.json, GAPS.json, any score, RTDB, buckets, the wind-hourly job, the provider bake-off collector, Pulse jobs or schedules. Do not create cloud jobs. Do not open, fetch or score H2 (sealed until 2027-01-01; the runner refuses it). Start in the wind research folder that Cortex `research-path` returns, write outputs only there, register them in its manifest.json (step 7), and end with a research closeout. Use the Engine checkout at the merged commit of Sector_Engine PR #245 (or its branch research/wind-strong-wind-method-2026-11-23 if it has not merged), with the Wind runtime's Python deps (numpy, eccodes).

Protocol: docs/brains/wind-strong-wind/WSW-2026-11-23.protocol.json, sha256 b9a55721f7a6d2853462c1080bbec384c3a30e3429fce70b10c2872c77449346 (pre-registered and pushed before any past-window value was fetched). Runner: tools/research/wind_strong_wind.py. Methods: B0 deterministic NBM (reference), M-A NBM P90 exceedance (no fitted parameter), M-B night upper-tail quantile mapping fitted on CAL+H1 only.

1. `verify`: the protocol hash must match. Stop if it does not.
2. Never-read check: confirm from the wind-brain manifest and the historical corpus store that no NBM or METAR object dated 2025-10-31 to 2026-05-02 exists. If one does, stop and report it; do not fetch anything.

Storage (Michael, 2026-11-23): all downloads and outputs go under the Wind research folder that `research-path` returns, on the research SSD, never the boot disk. That SSD froze Pulse once on Nov 21 and still awaits a repair, so:
- Before starting, report the free space on that volume (`df -h <folder>`). Stop if it is under 80 GB.
- Download and process one month at a time (2025-11, 2025-12, 2026-01, 2026-02, 2026-03, 2026-04). Pass `--min-free-gb 80` to every fetch; the runner checks free space before each month and refuses on a full volume.
- Do not run during Pulse's busy minutes (:40–:59 UTC). Start a month only between :00 and :35; if it is still running at :40, let the current cycle finish and stop the command, then resume after :00 (the fetch is resumable and skips complete cycles).
- Stop cleanly on any I/O error, or if the command shows no progress for more than 10 minutes (a hang). Report it; do not retry in a loop.

3. `fit --corpus-store <the existing Stage 3C NBM v5.0 corpus store> --out <folder>/wsw-2026-11-23`. Reads CAL+H1 in place, writes wsw-mb-fit.json. Record its sha256.
4. Smoke test: `fetch --window pw --out <folder>/wsw-2026-11-23 --month 2025-11 --max-pairs 6 --min-free-gb 80`, then `rows --window pw …` and check that the rows carry `p90` values. If speedP90 is missing for NBM v4.3, report it and stop (M-A would be NOT_EVALUABLE).
5. For each month in order: `fetch --window pw --out <folder>/wsw-2026-11-23 --month <YYYY-MM> --min-free-gb 80` (public NOAA Open Data and IEM only; budget 60 GB and 48 h in total). Record the month's download size and the free space after it.
6. After all six months: `rows --window pw …`, then `score --window pw …`. Record the sha256 of rows.jsonl and wsw-result.json.
7. Register in the folder's manifest.json: the raw NBM and METAR store as one RECONSTRUCTABLE item (public NOAA/IEM data, re-downloadable with this runner and protocol; collectionSha256 with hashMethod sha256-tree-v1), and the fit, rows and result files with their sha256.

Post a short summary on #51 (under 15 lines):
- protocol sha256, fit sha256 (n rows, top knot), rows and result sha256
- never-read check result (step 2)
- rows: night, common, P90 coverage; observed >= 15 mph events in the common rows
- per method (B0, M-A, M-B): pooled POD / FAR / CSI, WI4 credit, scoreboard dimension-1 gate, outcome (SUPPORTED / NOT_SUPPORTED / INSUFFICIENT_EVENTS / NOT_EVALUABLE), and the CSI-difference lower bound vs B0
- the label "NBM v4.3 cool season: version-transfer caveat, not a v5.0 measurement"
- free space before and after each month, download volume and wall time used, any stop (I/O error, hang, busy-minute pause)
- questions for Michael: (a) whether a post-processed signal (M-A or M-B) may earn WI4 credit at all, since WI4 says "deterministic" (rubric governance); (b) keep both methods for the one-shot H2 score on or after 2027-01-01 (pre-registered: yes, both)

Nothing is admitted to any score. A candidate evidence block, if ever proposed, goes through refresh_wind_score.py (HELD for review) and Michael.
