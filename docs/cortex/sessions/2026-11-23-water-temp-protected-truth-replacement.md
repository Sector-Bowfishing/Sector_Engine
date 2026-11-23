# Session record: Water Temp Level-4 protected truth, lake replacement (protocols v2 → v4) (2026-11-23)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only), pack sector/engine

## Request
v1's step A came back INSUFFICIENT_TRUTH (Sector_Ops #51 comment 7094108377). Every public main-body cast keeps its depth on Result rows. Counting those anyway gives Guntersville 36, Wheeler 22, Wilson 0, Pickwick 0. Michael's direction (comment 7093610553):
- no agency emails;
- replace short lakes by a count-only rule;
- new research directions are pre-approved;
- unknowns count against.

The coordinator asked me to pre-register a replacement protocol, build the runner and tests, draft the Mini request (step A only), and not merge. Two independent reviews were NOT CLEAN. Each led to a new pre-registration, because no data had been fetched under the protocol it replaced.

Branch `research/water-temp-protected-truth-v2-2026-11-23` from `origin/main` `f5460aa` (PR #242 merged as `5db0679`). PR #248.

## Protocol chain (every file is byte-identical to what was registered; each superseded folder has a `SUPERSEDED.md`)
| Protocol | sha256 | Commit | Status |
|---|---|---|---|
| PT-L4-2026-11-23-v2 | `e02e2e08740767dec4720a610c112010eb78ad73ad1b223b14365489a499867d` | `f7a7fb5` | superseded after review round 2 (never run) |
| PT-L4-2026-11-23-v3 | `ebc1a77b1977924c2bb586340887f2fad7a3196b20bf4f2ef2305853716f170d` | `210c5c1` (alone) | superseded after review round 3 (never run) |
| **PT-L4-2026-11-23-v4** | `aac78d48276ba692d7f485971e594c01c000ccc966631f4900bf46a817a096e0` | `4095ff7` (alone) | current |

The runner is `tools/research/water_temp_protected_truth_v4.py`. It refuses every protocol id except v4. Tests: `tools/research/tests/test_water_temp_protected_truth_v4.py`, 30 offline tests on synthetic fixtures.

## What v4 defines
- **Universe.** The Lake Registry v1's SE R1/R2 reservoirs from the committed Vegetation fleet snapshot: 62 ids, which is 60 waters.
- **Exclusions.**
  - M0 tuning: the calibration-lake list (required, recorded with its hash) or a calibration site.
  - Resolver sensor: a tempSensor binding, or a USGS LK 00010 site within 10 mi.
  - WT-SAT-1: the committed list, or while it is unfrozen, an LK site inside the polygon.
  - No geometry.
- **Counted set.** It is fixed in step A from whitelisted WQP Result-depth rows. The unit code is read; the value never is.
  - A row counts only if all of these hold: characteristic, status, a known unit, and depth ≤ 1.5 m.
  - Depth is the Result depth, then the Activity depth, in both steps.
- **Census.** Cutoff fixed at 2026-11-22. The frozen four count only to 2026-06-30; their count to the cutoff is reported for information. The census is write-once.
- **Selection.** Frozen lakes with ≥ 25 casts are retained, and the rest are filled by count (ties by sha256). It needs 4 lakes and ≥ 150 casts.
  - The first selection hash posted on #51 is the only valid one.
  - `select` writes once, together with a write-once selection registry. Step B refuses any other hash.
- **Stations.** The draft and reviewed hashes are both posted and both bound. Only rows the draft marked UNCLASSIFIED may change, each with a reviewNote. A lake assigned in the draft is kept. The "dam's own river" rule is in the protocol.
- **Step B.**
  - One query per counted cast, with a forcing window derived from the selection and checked for coverage. Every fetch is write-once.
  - `compare` verifies the result and forcing files one-to-one against provenance (paths, sha256, derived parameters). It refuses missing, extra or duplicate files and duplicate readings. It writes once and records every input hash.
- **Unknowns count against.** A lake fails on any of: CAST_NOT_RETURNED, FORCING_MISSING, UNPAIRED_CAST, SCORED_BELOW_25 (after out-of-range values, the only step-B truth reject). Whether out-of-range values may be excluded at all is open for Michael.
- **Pass mark.** Unchanged: RMSE ≤ 2.5 °C, pooled and per lake.

## Review rounds
- **Round 2 (at d8790362) → v3:** the forcing window was chosen on the command line; the census was not bound to the reviewed station file; unpaired casts were dropped; the calibration-lake list was not required; Activity and USGS metadata were stored unstripped; redirects were not checked; dedupe crashed on stations without coordinates.
- **Round 3 (at 271f2a02) → v4:** deleting returned rows could still PASS; compare did not check files against provenance; more than one selection was possible; the cutoff was a command-line value; the draft hash was not bound; reviewers could change a lake; `select` was not write-once; the window for the frozen four was not stated.
- v1's `load_stations` is left as the record of v1, whose census was INSUFFICIENT so its step B can never run. v4 uses its own `load_reviewed`.

## Verification
See the PR: v4 tests pass; the `tools/research` and `tools/architecture` suites show the same 2 failures as main, which happen in a root container; the architecture report has no finding in the new paths; `research-check --repo .` and `data-check` are unchanged against main; the engineering-status digest is regenerated and `--check` passes.

## Data fetched
None. The universe and points come from committed repository files. This session's proxy refuses WQP, USGS and the registry bucket.

## Decisions for Michael (batched)
1. Post the v4 Mini request (step A only): `docs/brains/water-temp-protected-truth-v4/MINI_REQUEST_DRAFT.md`.
2. After a SELECTED result, an Owner request for step B naming the registered selection hash.
3. Whether out-of-range truth values may be excluded (counted against the lake's 25), or must fail the lake.
4. Adopting v4 as the Level-4 rule is a rubric decision; any change to a score or validation node is separate.

## Closeout
[`2026-11-23-water-temp-protected-truth-replacement.closeout.md`](2026-11-23-water-temp-protected-truth-replacement.closeout.md)

## Operating contract §19
- Gap: WATER-VAL-001.
- Bowfisher decision: whether the temperature estimate was checked on protected lakes before it is trusted.
- Score before/after: 3.0 / 3.0.
- Not changed: live systems, schedulers, customer `/conditions`, model, science, bindings.
