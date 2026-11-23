Claude request (under Owner approval 2026-11-22): Water Temp Level-4 protected truth v2, step A only (read-only, counts only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

Read-only research. Do not change bindings, temp_sensors.csv, the lake directory, frozen-scores.json, any score, RTDB, Pulse jobs or schedules. Do not create cloud jobs or send any email. Start in the water-temperature research folder that Cortex `research-path` returns, write outputs only under its `protected-truth-v2/` subfolder, and end with a research closeout. Use the Engine checkout at the merged commit of the v2 PR (or that PR's branch if it has not merged).

Protocol: docs/brains/water-temp-protected-truth-v2/PT-L4-2026-11-23-v2.protocol.json, sha256 e02e2e08740767dec4720a610c112010eb78ad73ad1b223b14365489a499867d. Runner: tools/research/water_temp_protected_truth_v2.py. It follows Michael's 2026-11-23 06:42Z direction: no agency emails, and short lakes are replaced by a rule that looks only at cast counts.

Step A v2. No temperature value is opened. Result rows are read only through the depth-column whitelist.
1. `verify`: the protocol hash must match. Stop if it does not.
2. `fetch-registry --out …/registry`: Lake Registry v1 index and analysis polygons for the 62 universe lakes.
3. `fetch-usgs --registry …/registry --calibration <the M0 calibration snapshot in the water-temperature folder: validation/campaign-2026-10-22/wt_w5_sensor_snapshot.json> --out …/usgs`: USGS site metadata only. If the OGC API answers in a shape the runner cannot parse (sites.csv is empty for big reservoirs that certainly have LK sites), stop and report it. Do not hand-edit sites.csv.
4. `exclusions --registry … --sites …/usgs/sites.csv --calibration <snapshot> --out exclusions.json`. If the snapshot names lakes, pass them with `--calibration-lakes`. The WT-SAT-1 list is not frozen, so do not pass `--wt-sat-1`.
5. `fetch-wqp --registry … --out …/wqp`: WQP Station and Activity metadata, and Result rows through the whitelist. Only `*.resultdepth.csv` is stored, never the raw Result file.
6. `stations --registry … --wqp …/wqp --out stations.draft.csv`. Review the UNCLASSIFIED rows from names and coordinates only, BEFORE running the census and without looking at any count: you may move a row to MAIN_BODY, EMBAYMENT, TAILWATER or OUTSIDE with a one-line reviewNote. Rows that name another river off the Tennessee (for example the Coosa at a Coosa lake) are main stem when the river is the lake's own river. Save as stations.reviewed.csv and record its sha256. Change nothing after this step.
7. `census --wqp … --stations stations.reviewed.csv --exclusions exclusions.json --out census.json` (cutoff = yesterday).
8. `select --census census.json --exclusions exclusions.json --out selection.json`. Record the selection sha256.
Register every file in the folder's manifest.json (sha256, source, retention RECONSTRUCTABLE). Run research-check and close out.

Do NOT run fetch-forcing, fetch-results or compare. Step B opens values and needs a separate "Owner request (Michael, …)" after the selection hash is posted.

Post a short summary on #51 (under 15 lines):
- the outcome (SELECTED or INSUFFICIENT_TRUTH), the 4 lakes with their cast counts and total, which frozen lakes were kept or replaced and why
- excluded lakes by rule (M0_TUNING, RESOLVER_SENSOR, WT_SAT_1, NO_GEOMETRY), as counts, with the lake names for the frozen four
- the four frozen lakes' counts in both windows (to 2026-06-30, and to the cutoff)
- station review: how many UNCLASSIFIED rows were moved, to which classes; the reviewed-file sha256
- hashes: protocol, exclusions.json, census.json, selection.json
- questions for Michael: (a) post an Owner request for step B on this selection? (b) adopt this protocol (count-only lake replacement and the 2.5 °C pass mark) as the Level-4 rule, which is a rubric decision? (c) if INSUFFICIENT_TRUTH, widen the universe (another protocol id) or wait for new casts?
