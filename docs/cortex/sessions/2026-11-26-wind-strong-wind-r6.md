# Session record: Wind strong-wind protocol R6 registered and the runner changed (2026-11-26)

Standards: Rehtac Cortex 3.1.6 @ a785035 (clean), pack sector/engine

## Request
Owner decisions (Michael, 2026-11-25 23:25 CT), Sector_Ops #51 comment 7183456058, item 5: "Wind R6 draft: accepted (fresh stations, site-transfer caveat). Review it, then anchor it only through a reviewed runner PR." Item 8: merges stay with the cloud runner. Carried out by the Mac mini helper (scheduled run; start post #51 7186368959) because the draft protocol lived only on the research SSD and no Engine branch carried it.

Repository `Sector-Bowfishing/Sector_Engine`, branch `research/wind-strong-wind-r6-2026-11-26` from `origin/main` `0f7715ed`, worktree `scratchpad/eng-r6` (registered in `.git/cortex-worktrees.json`).

## Scope
Inspected: the R6 draft and its README and closeout (research SSD, `wind-brain/research/wsw-r6-draft-2026-11-25`), the R5 protocol, `tools/research/wind_strong_wind.py`, its tests, `tools/research/protocol_run_ledger.py` (API), the Wind runtime `sector_wind/ingest.py`, `interp.py`, `store.py`, `grib.py` (read only), `lakes.json`, `points.json`, the W-NOW-3 station list header (sha256 only). Not inspected: the IEM network listing format (no request made; see Verification). Scope did not expand: the Wind runtime is unchanged; CAL+H1 and H2 keep the frozen 8 stations.

## Review of the draft (observed)
| Item | Finding | Evidence |
|---|---|---|
| Never-read audit | Sound: every period since 2024-07 at the 8 frozen stations was read (W-NOW-1/2, W1/W1b, CAL+H1, H2) and iem-wind read 2015–2024 at HSV, DCU, MSL; no never-read window exists there | draft `dataExaminedBeforeRegistration.neverReadAudit2026_11_25`; `#51` 7153314652 |
| Selection rule | Metadata-only, fixed before any value is read; deterministic (sha256 ranking); exclusions named with hashes (W-NOW-3 list `a5474abe…`, `points.json` `e24da503…`) | draft `pwStations` |
| Gaps the runner had to close | Metadata source and fields, archive-begin cut-off, state rule, distance rule, coordinates for the iem-wind stations outside the four states, how the station value is extracted without a lake cut-out, where the list is recorded and how a different list is refused, and when the selection runs relative to the fit | draft `runnerChangesNeeded`; `registration.changesFromDraft` in the registered R6 |
| Everything else | R5's windows, methods, scoring, decision, budget and accounting, unchanged | `diff` R5 vs draft (only the fields above differ) |

## Changes
| Commit | What |
|---|---|
| `5b67f9e0` | **Registered alone, before any runner change:** `docs/brains/wind-strong-wind/WSW-2026-11-25-R6.protocol.json` (sha256 `cd309fb947076ff87ad924d1e52e107dae2179a4138205ea5c9f782754fd8262`) and its sidecar; `SUPERSEDED.md` adds R5 (byte-identical, never run, no anchor posted). The registered R6 is the accepted draft (sha256 `1149d9d9…7bf7`) with: status PRE-REGISTERED and the owner review recorded; a fourth result step `select` (key `select:pw`) in `runBinding`; the executable `pwStations` details; the PW sentence in `forecastRows`; `weightsNotBilinear` in `accounting`; the registration session in `dataExaminedBeforeRegistration`. Listed in `registration.changesFromDraft`. |
| `c3c161d5` | **Runner** `tools/research/wind_strong_wind.py`: pins R6 and refuses R5..R1; `select --window pw --out O --w-now-3-stations CSV` fetches only the IEM network listings (AL, TN, MS, GA candidates; OK, MO, AR for TUL, STL, FSM coordinates) through the budgeted fetch, parses them fail-closed, builds the exclusion set (frozen 8 from `lakes.json`, W-NOW-3 list with its pinned sha256, `points.json` with its pinned sha256, the 8 iem-wind ids, 25 km haversine buffer), ranks by `sha256('WSW-2026-11-25-R6|' + id)`, takes 8 with at most 3 per state, writes `pw/pw-stations.json` once (listing bytes kept under `pw/metadata/`) and records it as a result step (Run start / Run result on #51). `fit` and every pw `fetch`, `rows`, `score` refuse without a counted `select:pw` or when the file in `--out` differs from the counted output. PW `fetch`/`rows` use a configuration derived from the selection: one station-centred carrier box (±0.15°) per station, blended bilinearly at the station point; rows whose weights are not bilinear count their forecast values as missing (`weightsNotBilinear`, counted, never dropped). `rows:pw` binds the stations file; `score:pw` re-checks it. CAL+H1 and H2 keep `lakes.json`. **Tests** 46 (was 38): the R5 hash and refusal, the protocol constants, the rule (archive filter, id and buffer exclusions, ranking, per-state cap, determinism under re-ordering, fewer than 8 refused, missing network refused), the parser failing closed, the exclusion set and a missing iem-wind coordinate, the carrier configuration, `select` as a one-shot result step before fit and fetch with a different list refused, PW fetch using the selected stations and H2 using `lakes.json`, PW rows at the station point with the non-bilinear case. **Docs:** `MINI_REQUEST_DRAFT.md` rewritten for R6 (step 3a `select` after the anchor); `brains/wind/research/GAPS.json` WIND-CNF-001 evidence pointer. |
| next | This record, the status digest, the closeout reference. |

Choices made (reversible, standing approval 6): the selection is a ledger **result step** so the list is public on #51 before any value is read; `fit` requires the counted selection too (the protocol says the stations are fixed before any value is read, and the fit reads CAL+H1 values); the station value uses a small carrier box through the existing `ingest_nbm_cycle` and `CutoutIndex` rather than a new point path in the Wind runtime (smallest change; the value definition is the protocol's bilinear blend at the point, and anything else is counted as missing); the listing bytes count against the pw download budget; no `--stations-sha` flag (the ledger check plus the public Run result comment carry the hash).

## Verification
- `pytest -q tools/research/tests/test_wind_strong_wind.py`: 46 passed (numpy and eccodes present, so the runtime-glue tests ran; no test reaches GitHub or the network).
- `pytest -q tools/research`: 422 passed.
- `wind_strong_wind.py verify`: `OK WSW-2026-11-25-R6 sha256 cd309fb9…8262`; `plan --window pw`: 870 (init, lead) pairs, 6,960 planned rows (unchanged from R5).
- `research-check --repo .`: 85 findings, identical to `origin/main` (none in the changed files). `research-check --gaps brains/wind/research/GAPS.json`: 0. `research-check` (home): 174 findings / 87 information, unchanged, none naming this task. `research-check --closeout`: 0.
- `data-check --repo .`: 194 findings, identical to `origin/main` (the runner reads and writes no Firebase path). `ops-check --repo .`: 0. `mission-audit --brain wind --text <the PW scoring task>`: 0 findings.
- `worktree-check`: `eng-r6` KEEP_DIRTY before commit (registered ACTIVE); see the closeout.
- `collect_certification.py` (Kit V1, every registered Brain): failing none; `build_engineering_status.py --write` then `--check`: OK (`sector-engine-engineering-status-2026-10-22.1`). No Brain package changed; the run only refreshes the source digest.
- Security: no secrets or machine-local paths in the changes; the only hosts are the registered public ones (`ALLOWED_HOSTS`); fixtures are synthetic and labelled (SEC-02); writes only under `--out`.

## Data fetched
None. No IEM listing, NBM grib2, `.idx` or METAR object was fetched or read. One request for the AL_ASOS metadata listing (to confirm the GeoJSON field names) was declined by the session's permission layer before it was sent, so the listing format is **NOT_VERIFIED**; `parse_network_listing` fails closed on a listing without a station id, a Point geometry or `archive_begin`, and the Mini run's `select` step would stop there and report. Recorded in R6 `pwStations.metadataSource` and `dataExaminedBeforeRegistration.thisSession`.

## Decisions for Michael (batched)
1. **Merge** of this PR stays with the cloud runner (item 8) once the independent review is clean and CI is green. Nothing is customer-visible; no IAM, rules, scores or rubrics change.
2. After the merge, the Mac mini run needs an **Owner request** naming protocol sha256 `cd309fb947076ff87ad924d1e52e107dae2179a4138205ea5c9f782754fd8262` and the `--out` folder (the rewritten `docs/brains/wind-strong-wind/MINI_REQUEST_DRAFT.md`; about 30–60 GB of public data on the research SSD, no cloud job). The anchor is posted only then.
3. Still open from the R5 record: rubric governance (whether a post-processed strong-wind signal may earn WI4 credit) and Cortex gap CG-3.1-25.

## Not done (gated or out of scope)
No data fetched, no anchor posted, no run step, no H2 access, no score, rubric or evidence-file change, no Firebase or bucket access, no schedule, no merge. The Wind runtime is unchanged.

## Closeout
Research closeout on the research SSD: `wind-brain/closeouts/2026-11-26-wsw-r6-runner.md` (`research-check --closeout`: 0). Manifest: item `wsw-r6-draft-2026-11-25` ARCHIVAL (registration recorded), task `wsw-r6-runner-2026-11-26` DONE.

## Operating contract §19
Gap WIND-CNF-001; bowfisher decision: whether a calm or moderate wind forecast can be trusted to keep an exposed shoreline undisturbed tonight; evidence: protocol sha256 above (registered, not run); files and tests as above; score before/after: unchanged (no score, rubric or evidence file touched; the GAPS pointer text only); open gaps WIND-CNF-001 (BLOCKED on the Mini run and H2), WIND-CNF-002, WIND-CNF-003, WIND-EVI-001; field validation: none required (RS-39); not changed: live systems, the wind-hourly job, the bake-off collector, the research workspace data, sealed data.
