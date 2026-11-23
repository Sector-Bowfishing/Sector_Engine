# Session record: Water Temp Level-4 protected truth, pre-registration and runner (2026-11-23)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with `git archive`; the loader reports "uncommitted (no-git)" for an extracted tree), pack sector/engine

## Request
Research task (caller request in this session): unblock the Water Temp score gate "Collect protected truth for the Level-4 comparison" (`score_improvements_v1.json` → `water-temp`, gap WATER-VAL-001). Read what the gate requires, list independent in-situ truth sources the Brain does not use, pre-register the protected-truth set and the comparison before fetching data, hash and commit it, write a read-only runner with tests, and draft (not post) a Mac mini request. Publish no result and change no score.

Branch `research/water-temp-protected-truth-2026-11-23` from `origin/main` `8d421fe`, worktree `/home/claude/sector_engine_wt_wtpt` (cloud container).

## What the gate requires (observed)
| Item | Value | Evidence |
|---|---|---|
| Protected lakes | Guntersville, Wheeler, Wilson, Pickwick | `WaterTemperatureBrain.swift` `protectedLakes` |
| Truth unit | holdout casts, "rule v3, main-body casts", 2021-01 → 2026-06 | same file, `protectedLakeValidation` |
| Sufficiency | ≥ 25 per lake and ≥ 150 total | `protectedTruthRequiredPerLake`, `protectedTruthRequiredTotal` |
| Recorded counts | G 90, Wh 18, Wi 2, P 57 (total 167) | same file; `frozen-scores.json` water-temp blocker |
| Held out | never used for calibration (calibration casts are counted separately: G 106, Wh 14, Wi 0, P 92) | same file |
| Pass mark of the comparison | **NOT_VERIFIED**: in the private iOS document `WATER_TEMP_STAGE_3C3_PROTECTED_VALIDATION.md`, not in any repository this session can read | `SCORING.md` frozen table |
| Publication for the scorer | the scorer publishes `frozen-scores.json` → `water-temp` verbatim (basis FROZEN); a change is an owner decision | `SCORING.md`, `BRAIN_OPERATING_CONTRACT.md` §16 |
| Hard stop | re-counting under rule v3 opens protected values: owner approval | `tools/research/discovery.py` (protected-truth limitation) |
| Prior evidence | 0 new WQP casts at Wheeler or Wilson since 2026-07-01 (metadata); Wilson has no public casts after May 2026 | `sessions/2026-10-23-research-discovery.md` |

## Changes
| Commit | What |
|---|---|
| `3cc5a9b` | Protocol `PT-L4-2026-11-23` and its sha256 sidecar, committed **before** any truth value was fetched (`d0de8ceb18cc6857ec6c4478e49b73dcfb2a458823b30ade4a3d8b73479b8566`) |
| next | `candidate_sources.json` (10 candidates, 1 context-only, 1 owner decision, 5 rejected), runner `tools/research/water_temp_protected_truth.py`, 20 tests, draft Mini request, research README, this record, closeout, Cortex gaps CG-3.1-22 and CG-3.1-23 |

Choices made (reversible, standing approval 6): the protocol keeps the four frozen lakes (replacing lakes is a rubric change); the truth unit stays the cast, so continuous sensors are context only; the pass mark is the repository's pre-declared grab-sample bar (`discovery.json` `pooledRmseC` 2.5 °C) applied pooled and per lake; the model is production M0 through the single research re-implementation in `discovery.py` (no second copy); step B is refused in code unless the census is sufficient, the station file is unchanged and an `Owner request (Michael, …)` string is given.

## Verification
- `python3 -m pytest -q tools/research`: 92 passed, 2 failed. The 2 failures (`test_cleanup_removes_read_only_campaign_files_but_nothing_else`, `test_read_only_sources_folder_is_never_modified`) are **pre-existing** on `origin/main` in this container (it runs as root, so read-only permission checks do not hold); the base run was 72 passed, 2 failed. The 20 new tests pass.
- `research-check --repo .`: 85 findings on the branch and on `origin/main` (unchanged); none in the new files. `research-check --gaps brains/water-temperature/research/GAPS.json`: 0.
- `data-check --repo .`: 541 lines on both (unchanged); the runner reads no Firebase path.
- `ops-check --repo .`: unchanged message. `mission-audit --brain water-temp --text "<this work>"`: 0 findings.
- `research-check --closeout`: see the closeout file.
- Security: no secrets, no machine paths, fixtures are synthetic and labelled (SEC-02); the runner's hosts are allowlisted (WQP, Open-Meteo archive) and it writes only to `--out`.

## Data fetched
None. `waterqualitydata.us` and `api.waterdata.usgs.gov` were refused by this session's network proxy (CONNECT 403; not retried). Candidate sources come from public program pages and search results; every row is an EVIDENCE_LEAD with `verified: false`.

## Decisions for Michael (batched)
1. Post the draft Mini request (step A, metadata only) on Sector_Ops #51: `docs/brains/water-temp-protected-truth/MINI_REQUEST_DRAFT.md`.
2. Before any step B: choose this protocol's pass mark (pooled and per-lake RMSE ≤ 2.5 °C) or the private Stage 3C.3 rule v3; restate the chosen rule in the Engine (CG-3.1-23).
3. Likely outcome on public data alone: still INSUFFICIENT for Wheeler and Wilson. The unlock is a data request to TVA for forebay and mid-reservoir profiles (Wheeler TRM 277.0 / 295.9, Wilson TRM 260.8) for 2021–2026, or ADEM's next Tennessee-basin rotation. Logger purchase (D3) costs money and stays an owner decision.
4. Any change to `frozen-scores.json`, the Swift `protectedLakes` constants or the validation nodes after a PASS is a separate owner-approved change.

## Not done (gated or out of scope)
No truth value opened, no score or rubric change, no Firebase read or write, no binding change, no merge.

## Closeout
[`2026-11-23-water-temp-protected-truth.closeout.md`](2026-11-23-water-temp-protected-truth.closeout.md) (stored here because the cloud container has no research home; CG-3.1-22).

## Operating contract §19
Gap WATER-VAL-001; bowfisher decision: whether the temperature estimate was checked on a protected lake before it is trusted; files as above; tests as above; score before/after 3.0 / 3.0 (unchanged); open gaps WATER-VAL-001 (BLOCKED, now with a pre-registered path), WATER-CAL-001, WATER-UNC-001; field validation needed: none required (loggers optional, RS-39); not changed: live systems, schedulers, customer `/conditions`, model, science.

## Review round 1 (independent review CLEAN; CI fixes)
- Architecture invariant 16 allows only CHARTER/GAPS/MANIFEST/README in `brains/*/research/`. The protocol folder moved unchanged to `docs/brains/water-temp-protected-truth/` (`git mv`; the protocol bytes and sha256 are unchanged and it does not name its own path); the Mini draft became `MINI_REQUEST_DRAFT.md`. The runner's protocol path follows.
- The Mini draft now runs the census twice (frozen holdout window to 2026-06-30, and the protocol window to the cutoff) and asks Michael whether casts after 2026-06 may count toward 25/150.
- Engineering-status digest regenerated (`collect_certification.py`, `build_engineering_status.py --write`, `--check` OK).
- Known limits recorded for step B (not fixed in this protocol): the owner-request gate is a string check, not proof of approval; `fetch-results` pulls all WQP Result rows for each lake box from 2021-01-01, which is more than the counted casts named in the protocol. Fix both before step B, under a new protocol id.
