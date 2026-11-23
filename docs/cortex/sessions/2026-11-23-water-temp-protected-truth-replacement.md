# Session record: Water Temp Level-4 protected truth, lake replacement (protocols v2 → v6) (2026-11-23)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only), pack sector/engine

## Request
v1's step A came back INSUFFICIENT_TRUTH (Sector_Ops #51 comment 7094108377). Every public main-body cast keeps its depth on Result rows. Counting those anyway gives Guntersville 36, Wheeler 22, Wilson 0, Pickwick 0. Michael's direction (comment 7093610553):
- no agency emails;
- replace short lakes by a count-only rule;
- new research directions are pre-approved;
- unknowns count against.

The coordinator asked me to pre-register a replacement protocol, build the runner and tests, draft the Mini request (step A only), and not merge. Three independent reviews were NOT CLEAN. Each led to a new pre-registration, because no data had been fetched under the protocol it replaced.

Branch `research/water-temp-protected-truth-v2-2026-11-23` from `origin/main` `f5460aa` (PR #242 merged as `5db0679`). PR #248.

## Protocol chain (every file is byte-identical to what was registered; each superseded folder has a `SUPERSEDED.md`)
| Protocol | sha256 | Commit | Status |
|---|---|---|---|
| PT-L4-2026-11-23-v2 | `e02e2e08740767dec4720a610c112010eb78ad73ad1b223b14365489a499867d` | `f7a7fb5` | superseded after review round 2 (never run) |
| PT-L4-2026-11-23-v3 | `ebc1a77b1977924c2bb586340887f2fad7a3196b20bf4f2ef2305853716f170d` | `210c5c1` (alone) | superseded after review round 3 (never run) |
| PT-L4-2026-11-23-v4 | `aac78d48276ba692d7f485971e594c01c000ccc966631f4900bf46a817a096e0` | `4095ff7` (alone) | superseded after review round 4 (never run) |
| PT-L4-2026-11-23-v5 | `c2367bf246e62f2214e4b0110c2f2e920ad3184e299d05a40ea6486a7c1b7509` | `6d964a5` (alone) | superseded for the shared run ledger, PR #251 (never run) |
| **PT-L4-2026-11-23-v6** | `0569912d4057a229a1ed89b0095abcdd0336ee65840a300e8bb304c40246f37f` | `61924e5` (alone) | current |

The runner is `tools/research/water_temp_protected_truth_v6.py`. It refuses every protocol id except v6. Tests: `tools/research/tests/test_water_temp_protected_truth_v6.py`, 39 offline tests on synthetic fixtures, with a fake #51 and no network. The run ledger is the shared module `tools/research/protocol_run_ledger.py` (PR #251, merged at main `bbdaa35`). The vendored shim is deleted.

## What v6 defines
- **Shared run ledger and public anchor (new in v6).** The runner opens the ledger with `Ledger.for_brain('water-temp', 'PT-L4-2026-11-23-v6', sha256, result_steps={select, compare})`, so the root is pinned to Cortex research-path. Before ANY step, a `Run anchor:` research record is posted on #51.
  - select and compare call `require_external_anchor()`. They follow begin, then `Run start:` with confirm_started, then compute, then complete, then `Run result:` with confirm_result. "Not listed yet" means wait and never repost.
  - Keys are fixed by the protocol: `all` for the step-A steps, `selection` for step B.
  - A STARTED attempt with no end is terminal. Recovery needs a new protocol id and a revised protocol after #51 human review.
  - Records are posted with `--post` (gh) or by hand, never with an Owner header, and nobody edits them.
- **Universe.** The Lake Registry v1's SE R1/R2 reservoirs from the committed Vegetation fleet snapshot: 62 ids, which is 60 waters.
- **Exclusions.**
  - M0 tuning: the calibration-lake list (required, recorded with its hash) or a calibration site.
  - Resolver sensor: a tempSensor binding, or a USGS LK 00010 site within 10 mi.
  - WT-SAT-1: the committed list, or while it is unfrozen, an LK site inside the polygon.
  - No geometry.
- **Counted set.** It is fixed in step A from whitelisted WQP Result-depth rows. The unit code is read; the value never is.
  - A row counts only if all of these hold: characteristic, status, a known unit, and depth ≤ 1.5 m.
  - Depth is the Result depth, then the Activity depth, in both steps.
- **Census.** Cutoff fixed at 2026-11-22. The frozen four count only to 2026-06-30; their count to the cutoff is reported for information. The census is a ledger step (key `all`) and write-once.
- **Selection.** Frozen lakes with ≥ 25 casts are retained, and the rest are filled by count (ties by sha256). It needs 4 lakes and ≥ 150 casts.
  - select is a result step (key `all`). Its counted run in the shared ledger, with its Run start and Run result records on #51, is the only valid selection, and step B refuses any other.
- **Stations.** The draft and reviewed hashes are both posted and both bound. Only rows the draft marked UNCLASSIFIED may change, each with a reviewNote. A lake assigned in the draft is kept. The "dam's own river" rule is in the protocol.
- **Step B.**
  - One query per counted cast, with a forcing window derived from the selection and checked for coverage. Every fetch is write-once.
  - `compare` verifies the result and forcing files one-to-one against provenance (paths, sha256, derived parameters). It refuses missing, extra or duplicate files and duplicate readings. It writes once and records every input hash.
- **Unknowns count against.** A lake fails on any of: CAST_NOT_RETURNED, FORCING_MISSING, UNPAIRED_CAST, SCORED_BELOW_25 (after out-of-range values, the only step-B truth reject). Whether out-of-range values may be excluded at all is open for Michael.
- **Pass mark.** Unchanged: RMSE ≤ 2.5 °C, pooled and per lake.

## Review rounds
- **Round 2 (at d8790362) → v3:** the forcing window was chosen on the command line; the census was not bound to the reviewed station file; unpaired casts were dropped; the calibration-lake list was not required; Activity and USGS metadata were stored unstripped; redirects were not checked; dedupe crashed on stations without coordinates.
- **Review at b68a1faf (runner-only fix, still v6):** `_fetch_step` aborted a fetch after value-bearing bodies were already on disk, so someone could look at the values and retry. Now the attempt is terminal from the moment the first body is received: it is left STARTED, never aborted, and prints the recovery rule. Each body's sha256 is bound in the ledger as it arrives. Only a failure before any body is received may abort. The reviewer's PoC is now refused. This needs no new protocol: v6 `runLedger.runsThatCount` already says abort only before any value is seen.
- **Shared ledger (PR #251 merged) → v6:** the vendored shim let a session pick a new root. v6 uses the shared module through `for_brain()`, adds the public anchor, start and result records, and calls `require_external_anchor` in select and compare.
- **Round 4 (at 7ba0f63) → v5:** every write-once guard sat at an operator-chosen path. Two selections in different folders both passed the step-B gate, and compare into a new folder accepted edited values with rewritten provenance. Both cases are now refused through the run ledger (tests `test_one_selection_per_protocol_whatever_the_folder` and `test_edited_values_with_rewritten_provenance_are_refused`).
- **Round 3 (at 271f2a02) → v4:** deleting returned rows could still PASS; compare did not check files against provenance; more than one selection was possible; the cutoff was a command-line value; the draft hash was not bound; reviewers could change a lake; `select` was not write-once; the window for the frozen four was not stated.
- v1's `load_stations` is left as the record of v1, whose census was INSUFFICIENT so its step B can never run. v6 uses its own `load_reviewed`.

## Verification
See the PR: v6 tests pass; the `tools/research` and `tools/architecture` suites show the same 2 failures as main, which happen in a root container; the architecture report has no finding in the new paths; `research-check --repo .` and `data-check` are unchanged against main; the engineering-status digest is regenerated and `--check` passes.

## Data fetched
None. The universe and points come from committed repository files. This session's proxy refuses WQP, USGS and the registry bucket.

## Decisions for Michael (batched)
1. Post the v6 Mini request (step A only): `docs/brains/water-temp-protected-truth-v6/MINI_REQUEST_DRAFT.md`.
2. After a SELECTED result, an Owner request for step B naming the registered selection hash.
3. Whether out-of-range truth values may be excluded (counted against the lake's 25), or must fail the lake.
4. Adopting v6 as the Level-4 rule is a rubric decision; any change to a score or validation node is separate.

## Closeout
[`2026-11-23-water-temp-protected-truth-replacement.closeout.md`](2026-11-23-water-temp-protected-truth-replacement.closeout.md)

## Operating contract §19
- Gap: WATER-VAL-001.
- Bowfisher decision: whether the temperature estimate was checked on protected lakes before it is trusted.
- Score before/after: 3.0 / 3.0.
- Not changed: live systems, schedulers, customer `/conditions`, model, science, bindings.
