Claude request (under Owner approval 2026-11-22): Water Temp Level-4 protected-truth census (step A only, read-only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

Read-only research. Do not change bindings, temp_sensors.csv, the lake directory, frozen-scores.json, any score, RTDB, Pulse jobs or schedules. Do not create cloud jobs. Start in the water-temperature research folder that Cortex `research-path` returns, write outputs only there, and end with a research closeout. Use the Engine checkout at the merged commit of the PR named below (or that PR's branch if it has not merged).

Protocol: docs/brains/water-temp-protected-truth/PT-L4-2026-11-23.protocol.json, sha256 d0de8ceb18cc6857ec6c4478e49b73dcfb2a458823b30ade4a3d8b73479b8566 (pre-registered before any truth value was fetched). Runner: tools/research/water_temp_protected_truth.py. Lakes: Guntersville|AL, Wheeler|AL, Wilson|AL, Pickwick Lake|TN.

Step A, metadata only. Do NOT open any temperature result value (the Stage 3C.3 hard stop protects these casts).
1. `verify`: the protocol hash must match. Stop if it does not.
2. `fetch-metadata --out <folder>/protected-truth/metadata`: Water Quality Portal Station and Activity metadata per lake box (no Result rows).
3. `stations --metadata … --out stations.draft.csv`. Review every UNCLASSIFIED row against the station name, coordinates and a map; you may move it to MAIN_BODY, EMBAYMENT, TAILWATER or OUTSIDE with a one-line reviewNote. Do not reclassify any other row. Save as stations.reviewed.csv and record its sha256.
4. `census --metadata … --stations stations.reviewed.csv --out census.json` (cutoff = yesterday), then again with `--cutoff 2026-06-30 --out census.holdout-window.json` (the frozen Stage 3C.3 holdout window, for comparison only).
5. `fetch-forcing --start 2021-01-01 --end <cutoff> --out <folder>/protected-truth/forcing` (Open-Meteo archive at the four lake points; model input, not truth).
6. Check the candidate leads in candidate_sources.json (same folder as the protocol) for the four lakes. For each, record: station/site id, agency, distance from the lake point, sensor or sample depth, cadence, history length, public access or by-request, and the terms/robots status of the host. Do not download values from any of them. In particular: ADEM 21AWIC main-stem Tennessee River stations at Wheeler and Wilson after 2021; TVA forebay/mid-reservoir profile stations (Wheeler TRM 277.0 and 295.9, Wilson TRM 260.8); USGS discrete stations; TDEC at Pickwick; the Browns Ferry ambient station (documented depth?).
Register every file in the folder's manifest.json (sha256, source, retention RECONSTRUCTABLE).

Do NOT run step B (fetch-results, compare). Step B opens protected truth values and needs a separate "Owner request (Michael, …)". It also needs census outcome SUFFICIENT_FOR_STEP_B and Michael's choice between this protocol's pass mark and the private Stage 3C.3 rule v3.

Post a short summary on #51 (under 15 lines):
- census per lake: qualifying casts / 25, depth-on-results-only casts, total / 150, outcome
- station classes per lake, and how many UNCLASSIFIED rows were reviewed (with the reviewed-file sha256)
- the census.json sha256 and the protocol sha256
- for Wheeler and Wilson: which candidate sources could add casts, and which need a data request to TVA or ADEM (with the contact page if found)
- census counts per lake for both runs: the frozen holdout window (to 2026-06-30) and the protocol window (to the cutoff), so Michael can see what the later casts add
- questions for Michael: (a) request TVA forebay profiles for Wheeler and Wilson 2021-2026? (b) adopt this protocol's pass mark or the Stage 3C.3 rule for step B? (c) window: the protocol counts casts from 2021-01 to the census cutoff, but the frozen Stage 3C.3 holdout is 2021-01 to 2026-06; may casts after 2026-06 count toward the 25/150 gate? (d) if still insufficient, keep the four lakes and wait, fund loggers (D3), or replace lakes (a rubric change)?
