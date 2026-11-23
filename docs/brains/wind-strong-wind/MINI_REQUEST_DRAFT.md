Claude request (under Owner approval 2026-11-22): Wind strong-wind methods, past-window test (read-only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

Read-only research for gap WIND-CNF-001. Do not change frozen-scores.json, wind-measurements-evidence.json, GAPS.json, any score, RTDB, buckets, the wind-hourly job, the provider bake-off collector, Pulse jobs or schedules. Do not create cloud jobs. Do not open, fetch or score H2 (sealed until 2027-01-01; the runner refuses it). Start in the wind research folder that Cortex `research-path` returns, write outputs only there, register them in its manifest.json (sha256, source, retention RECONSTRUCTABLE), and end with a research closeout. Use the Engine checkout at the merged commit of the PR named below (or that PR's branch if it has not merged), with the Wind runtime's Python deps (numpy, eccodes).

Protocol: docs/brains/wind-strong-wind/WSW-2026-11-23.protocol.json, sha256 b9a55721f7a6d2853462c1080bbec384c3a30e3429fce70b10c2872c77449346 (pre-registered and pushed before any past-window value was fetched). Runner: tools/research/wind_strong_wind.py. Methods: B0 deterministic NBM (reference), M-A NBM P90 exceedance (no fitted parameter), M-B night upper-tail quantile mapping fitted on CAL+H1 only.

1. `verify`: the protocol hash must match. Stop if it does not.
2. Never-read check: confirm from the wind-brain manifest and the historical corpus store that no NBM or METAR object dated 2025-10-31 to 2026-05-02 exists. If one does, stop and report it; do not run step 4.
3. `fit --corpus-store <the existing Stage 3C NBM v5.0 corpus store> --out <folder>/wsw-2026-11-23`. Reads CAL+H1 in place, writes wsw-mb-fit.json. Record its sha256.
4. `fetch --window pw --out <folder>/wsw-2026-11-23 --max-pairs 6` (smoke), then `rows --window pw …` and check that the rows carry `p90` values. If speedP90 is missing for NBM v4.3, report it and stop (M-A would be NOT_EVALUABLE). Otherwise run `fetch --window pw` in full (resumable; budget 60 GB, 48 h; public NOAA Open Data and IEM only).
5. `rows --window pw …`, then `score --window pw …`. Record the sha256 of rows.jsonl and wsw-result.json.

Post a short summary on #51 (under 15 lines):
- protocol sha256, fit sha256 (n rows, top knot), rows and result sha256
- never-read check result (step 2)
- rows: night, common, P90 coverage; observed >= 15 mph events in the common rows
- per method (B0, M-A, M-B): pooled POD / FAR / CSI, WI4 credit, scoreboard dimension-1 gate, outcome (SUPPORTED / NOT_SUPPORTED / INSUFFICIENT_EVENTS / NOT_EVALUABLE), and the CSI-difference lower bound vs B0
- the label "NBM v4.3 cool season: version-transfer caveat, not a v5.0 measurement"
- download volume and wall time used
- questions for Michael: (a) whether a post-processed signal (M-A or M-B) may earn WI4 credit at all, since WI4 says "deterministic" (rubric governance); (b) keep both methods for the one-shot H2 score on or after 2027-01-01 (pre-registered: yes, both)

Nothing is admitted to any score. A candidate evidence block, if ever proposed, goes through refresh_wind_score.py (HELD for review) and Michael.
