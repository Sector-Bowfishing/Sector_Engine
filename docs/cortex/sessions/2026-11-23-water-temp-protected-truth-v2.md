# Session record: Water Temp Level-4 protected truth v2 (2026-11-23)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only), pack sector/engine

## Request
Coordinator request: after v1 step A came back INSUFFICIENT_TRUTH (Sector_Ops #51 comment 7094108377: 0/25 at all four lakes because depth sits on Result rows; with them Guntersville 36, Wheeler 22, Wilson 0, Pickwick 0), and following Michael's direction (comment 7093610553: no agency emails; replace short lakes by a count-only rule; new research directions pre-approved), pre-register v2 with a new id and hash, change the runner, test it, draft the Mini request (step A v2 only). Fix PR #242's review MEDIUMs. No merge.

Branch `research/water-temp-protected-truth-v2-2026-11-23` from `origin/main` `f5460aa` (PR #242 merged as `5db0679`).

## Changes
| Commit | What |
|---|---|
| `f7a7fb5` | Protocol `PT-L4-2026-11-23-v2`, sha256 `e02e2e08740767dec4720a610c112010eb78ad73ad1b223b14365489a499867d`, committed before any v2 data fetch |
| next | Runner `tools/research/water_temp_protected_truth_v2.py`, 26 offline tests, draft Mini request, research README, this record and its closeout |

What v2 does:
- **Result depth without values.** `strip_result_rows` keeps only 10 whitelisted columns, none of them `ResultMeasure*`, indexing each row only at those positions. The raw Result response is never written; the census refuses a depth file that carries a `ResultMeasure` column. Test `test_result_depth_whitelist_never_reads_or_stores_the_value` uses a row type that fails if the value positions are read or the row is iterated. Limit (stated in the protocol): the value still travels in the HTTP bytes.
- **Replacement rule.** Universe: the Lake Registry v1's SE `R1_run_of_river_pool` and `R2_flow_through_reservoir` lakes as committed in `brains/vegetation/runtime/knowledge/fleet.json` (62 ids, 60 waters after the two same-water pairs). Exclusions: M0 tuning (directory id or calibration site in polygon or within 10 mi), resolver sensor (tempSensor binding: Lake Russell GA, Okatibbee MS; or any USGS LK 00010 site within 10 mi of the point), WT-SAT-1 (committed list, or while unfrozen any LK 00010 site inside the polygon), no registry geometry. Frozen lakes with ≥ 25 casts are kept; free slots go to the highest counts, ties by sha256(lakeId); SELECTED needs 4 lakes and ≥ 150. Selection is hashed and posted before step B.
- **Stations.** Registry polygons (100 m tolerance) assign stations; Tennessee river miles (from names or ADEM `TENR-nnn` ids) resolve overlaps and the tailwater reach. Off the Tennessee, a station naming another river goes to review (it may be the lake's own river). Review happens before the census, from names and coordinates only.
- **PR #242 MEDIUMs.** Step B fetches one WQP Result query per counted cast (site, date, date), nothing else (test `test_step_b_fetches_only_counted_casts_one_site_date_each`). The census window (2021-01 → cutoff) and the frozen Stage 3C.3 holdout (2021-01 → 2026-06) are stated separately, and the census reports both for the frozen four. The `--owner-request` check is documented as a string check, not proof of approval.

Choices (standing approval 6): the universe comes from the committed registry snapshot rather than a hand list; the pass mark is unchanged from v1; v1's runner is left as the record of v1's step A (its step B can never run: v1's census is INSUFFICIENT).

## Verification
See the PR for command output: v2 tests 26 passed; `tools/research` and `tools/architecture` suites (same two pre-existing root-container failures as main); architecture report has no finding in the new paths; `research-check --repo .`, `data-check`, `mission-audit` unchanged against main; engineering-status digest regenerated and `--check` OK.

## Data fetched
None. The universe and points come from committed repository files.

## Decisions for Michael (batched)
1. Post the v2 Mini request (step A only): `docs/brains/water-temp-protected-truth-v2/MINI_REQUEST_DRAFT.md`.
2. After a SELECTED result: an Owner request for step B on that selection hash.
3. Adopting v2 (replacement lakes and the 2.5 °C mark) as the Level-4 rule is a rubric decision; any score or validation-node change after a PASS is separate.

## Closeout
[`2026-11-23-water-temp-protected-truth-v2.closeout.md`](2026-11-23-water-temp-protected-truth-v2.closeout.md)

## Operating contract §19
Gap WATER-VAL-001; bowfisher decision: whether the temperature estimate was checked on protected lakes before it is trusted; score before/after 3.0 / 3.0; not changed: live systems, schedulers, customer `/conditions`, model, science, bindings.
