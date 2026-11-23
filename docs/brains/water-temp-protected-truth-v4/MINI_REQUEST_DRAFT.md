Claude request (under Owner approval 2026-11-22): Water Temp Level-4 protected truth v4, step A only (read-only, counts only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

Read-only research. Do not change bindings, temp_sensors.csv, the lake directory, frozen-scores.json, any score, RTDB, Pulse jobs or schedules. Do not create cloud jobs or send any email. Start in the water-temperature research folder that Cortex `research-path` returns, write outputs only under its `protected-truth-v4/` subfolder, and end with a research closeout. Use the Engine checkout at the merged commit of PR #248 (or that PR's branch if it has not merged).

Protocol: docs/brains/water-temp-protected-truth-v4/PT-L4-2026-11-23-v4.protocol.json, sha256 aac78d48276ba692d7f485971e594c01c000ccc966631f4900bf46a817a096e0. v2 and v3 were superseded before they ran; the runner refuses them. Runner: tools/research/water_temp_protected_truth_v4.py. The census cutoff is fixed by the protocol at 2026-11-22. For the four frozen lakes only casts up to 2026-06-30 count. It follows Michael's 2026-11-23 direction: no agency emails, short lakes replaced by cast counts only, and unknowns count against.

Step A v4. No temperature value is opened. Every WQP and USGS file is stored as whitelisted columns or properties only.
1. `verify`: the protocol id and hash must match. Stop if they do not.
2. `fetch-registry --out …/registry`.
3. `fetch-usgs --registry …/registry --calibration <M0 calibration snapshot in the water-temperature folder: validation/campaign-2026-10-22/wt_w5_sensor_snapshot.json> --out …/usgs`. If sites.csv comes out empty for big reservoirs that certainly have LK sites, the API shape is not what the runner expects: stop and report. Do not hand-edit sites.csv.
4. Write calibration_lakes.json: a JSON list of the directory ids in the M0 calibration set, taken from the same snapshot (write `[]` if it names sites only). Then run `exclusions --registry … --sites …/usgs/sites.csv --calibration <snapshot> --calibration-lakes calibration_lakes.json --out exclusions.json`. Do not pass `--wt-sat-1` (that list is not frozen).
5. `fetch-wqp --registry … --out …/wqp`.
6. `stations --registry … --wqp …/wqp --out stations.draft.csv`. Review only the UNCLASSIFIED rows, from names and coordinates only, before the census and without looking at any count. Apply the protocol's station rule (`universe.stationReview`): a named river is MAIN_BODY only when it is the river the lake's own dam impounds, otherwise EMBAYMENT. Give each changed row a one-line reviewNote. Save it as stations.reviewed.csv. Post the sha256 of BOTH stations.draft.csv and stations.reviewed.csv on #51 before step 7. Rows the draft assigned to a lake keep that lake. Change nothing after this step.
7. `census --wqp … --stations-draft stations.draft.csv --stations-draft-sha256 <posted draft hash> --stations stations.reviewed.csv --stations-sha256 <posted reviewed hash> --exclusions exclusions.json --out census.json`. The command is write-once.
8. `select --census census.json --exclusions exclusions.json --out selection.json --selection-registry selection-registry.json`. It writes once and records the selection sha256 in the registry. Post that sha256 on #51. Under the protocol, the first selection hash posted for v4 is the only valid one, so run select once.
Register every file in the folder's manifest.json (sha256, source, retention RECONSTRUCTABLE). Run research-check and close out.

Do NOT run fetch-forcing, fetch-results or compare. Step B opens values and needs a separate "Owner request (Michael, …)" naming the posted selection sha256, and runs only against selection-registry.json.

Post a short summary on #51 (under 15 lines):
- the outcome (SELECTED or INSUFFICIENT_TRUTH), the 4 lakes with their cast counts and total, and which frozen lakes were kept or replaced, with the reason
- excluded lakes by rule (M0_TUNING, RESOLVER_SENSOR, WT_SAT_1, NO_GEOMETRY) as counts, naming any of the frozen four
- the frozen four's counted casts to 2026-06-30, with the count to the cutoff for information, and the step-A rejects (status, unit, depth) for the selected lakes
- station review: how many UNCLASSIFIED rows changed, and to which classes
- hashes: protocol, calibration_lakes.json, exclusions.json, stations.draft.csv, stations.reviewed.csv, census.json, selection.json
- questions for Michael: (a) post an Owner request for step B on this selection hash? (b) adopt v4 (count-only lake replacement, 2.5 °C mark, unknowns count against) as the Level-4 rule, which is a rubric decision? (c) may out-of-range truth values be excluded (counted against the lake's 25), or must they fail the lake? (d) if INSUFFICIENT_TRUTH, widen the universe under a new protocol id, or wait for new casts?
