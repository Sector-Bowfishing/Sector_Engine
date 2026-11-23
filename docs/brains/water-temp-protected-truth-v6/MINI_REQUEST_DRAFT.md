Claude request (under Owner approval 2026-11-22): Water Temp Level-4 protected truth v6, step A only (read-only, counts only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

This is read-only research.
- Do not change bindings, temp_sensors.csv, the lake directory, frozen-scores.json, any score, RTDB, Pulse jobs or schedules.
- Do not create cloud jobs or send any email.
- Start in the water-temperature research folder that Cortex `research-path` returns. Write outputs only under its `protected-truth-v6/` subfolder, and end with a research closeout.
- Use the Engine checkout at the merged commit of PR #248, or that PR's branch if it has not merged.

Setup:
- Protocol: docs/brains/water-temp-protected-truth-v6/PT-L4-2026-11-23-v6.protocol.json, sha256 0569912d4057a229a1ed89b0095abcdd0336ee65840a300e8bb304c40246f37f.
- Runner: tools/research/water_temp_protected_truth_v6.py. It refuses v2 to v5.
- Set CORTEX_HOME (or pass --cortex-home). The runner opens the shared run ledger with `Ledger.for_brain('water-temp', …)`. Its root is the folder Cortex `research-path sector/engine water-temp` returns, and the runner refuses a different SECTOR_RESEARCH_ROOT. The ledger is `_ledgers/PT-L4-2026-11-23-v6.jsonl`.
- Result steps: select and compare. Keys are fixed by the protocol: `all` for exclusions, census and select; `selection` for step B.
- The census cutoff is fixed at 2026-11-22. For the four frozen lakes, only casts up to 2026-06-30 count.
- This follows Michael's 2026-11-23 direction: no agency emails; short lakes are replaced by cast counts only; unknowns count against.

Public records on #51:
- This session posts every `Run anchor:`, `Run start:` and `Run result:` comment on #51 as a research record under standing item 7. Never use an Owner header.
- Nobody edits or deletes them. A correction is a new comment.
- With `--post`, the runner posts them itself through gh. Without `--post`, it writes the text next to the output (`<out>.start.txt`, `<out>.result.txt`) and waits while you post that text by hand.
- When #51 says "not listed yet", wait and retry. Never repost.
- If a step is refused, stop and report it, and never work around it. This covers "already ran", "REPEAT", "edited", and an anchor that is not the earliest. Recovery needs a new protocol id and a revised protocol after #51 human review.

Step A v6. No temperature value is opened. Every WQP and USGS file is stored as whitelisted columns or properties only.
1. `verify`: the protocol id and hash must match. Stop if they do not.
2. `anchor --out …/anchor.txt` (add `--post` to post it): this opens the ledger and writes its Run anchor text. Post it on #51 once. The first line reads `Run anchor: PT-L4-2026-11-23-v6 <anchor> compare,select <protocol sha256>`. Then run `check-anchor` until it succeeds. "not listed yet" means wait. No step runs before this.
3. `fetch-registry --out …/registry`.
4. `fetch-usgs --registry …/registry --calibration <M0 calibration snapshot in the water-temperature folder: validation/campaign-2026-10-22/wt_w5_sensor_snapshot.json> --out …/usgs`. If sites.csv comes out empty for big reservoirs that certainly have LK sites, the runner does not understand the API's answer: stop and report. Do not hand-edit sites.csv.
5. Write calibration_lakes.json: a JSON list of the directory ids in the M0 calibration set, from the same snapshot (`[]` if it names sites only). Then run `exclusions --registry … --sites …/usgs/sites.csv --calibration <snapshot> --calibration-lakes calibration_lakes.json --out exclusions.json`. Do not pass `--wt-sat-1`; that list is not frozen.
6. `fetch-wqp --registry … --out …/wqp`.
7. `stations --registry … --wqp …/wqp --out stations.draft.csv`.
   - Review only the UNCLASSIFIED rows, from names and coordinates only, and do it before the census without looking at any count.
   - Apply the protocol's station rule (`universe.stationReview`): a named river is MAIN_BODY only when it is the river the lake's own dam impounds; otherwise it is EMBAYMENT.
   - Give each changed row a one-line reviewNote. Rows the draft assigned to a lake keep that lake.
   - Save the result as stations.reviewed.csv. Post the sha256 of BOTH station files on #51 before step 8, and change nothing after this step.
8. `census --wqp … --stations-draft stations.draft.csv --stations-draft-sha256 <posted draft hash> --stations stations.reviewed.csv --stations-sha256 <posted reviewed hash> --exclusions exclusions.json --out census.json`.
9. Make sure the anchor from step 2 is on #51: run `check-anchor` again. Then run `--post select --census census.json --exclusions exclusions.json --out selection.json`. select is a result step: the runner checks the anchor, begins, posts `Run start:` and waits until it is confirmed. Only then does it compute the selection; it then completes, posts `Run result:` and waits for that confirmation. Leave it running until it prints the result. The counted select run is the only valid selection.

Register every file in the folder's manifest.json (sha256, source, retention RECONSTRUCTABLE). Register the run ledger and its head file as ARCHIVAL, because they are the record of which runs count. Run research-check and close out.

Do NOT run fetch-forcing, fetch-results or compare. Step B opens values. It needs a separate "Owner request (Michael, …)" that names the selection sha256 in the ledger.

Post a short summary on #51 (under 15 lines). It is a research record, not an Owner header:
- the outcome (SELECTED or INSUFFICIENT_TRUTH), the 4 lakes with their cast counts and the total, and which frozen lakes were kept or replaced, with the reason
- excluded lakes by rule (M0_TUNING, RESOLVER_SENSOR, WT_SAT_1, NO_GEOMETRY) as counts, naming any of the frozen four
- the frozen four's counted casts to 2026-06-30, the count to the cutoff for information, and the step-A rejects (status, unit, depth) for the selected lakes
- station review: how many UNCLASSIFIED rows changed, and to which classes
- hashes: protocol, calibration_lakes.json, exclusions.json, stations.draft.csv, stations.reviewed.csv, census.json, selection.json; the ledger anchor and head entry; and the ids of the Run anchor, Run start and Run result comments
- questions for Michael:
  (a) Post an Owner request for step B on this selection hash?
  (b) Adopt v6 (count-only lake replacement, the 2.5 °C mark, unknowns count against) as the Level-4 rule? That is a rubric decision.
  (c) May out-of-range truth values be excluded (counted against the lake's 25), or must they fail the lake?
  (d) If INSUFFICIENT_TRUTH: widen the universe under a new protocol id, or wait for new casts?
