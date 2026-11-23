# Session record: Weather Brain retrospective validation, pre-registration and runner (2026-11-23)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with `git archive`; the loader reports "uncommitted (no-git)" for an extracted tree), pack sector/engine

## Request
Research task (caller request in this session, under the owner's direction to strengthen Brains, Sector_Ops #51 comment 7093610553): let the disabled Weather Brain earn validation now instead of waiting 30–60 prospective days. Pre-register, before fetching any data, a retrospective version of `WEATHER_BRAIN_PLAN.md` §5 (5.1 fidelity, 5.2 representativeness WX-001, 5.3 change signal WX-002) mapped to the draft rubric's validation states (PR #241, `weather-score-v1.json`, DRAFT); hash and commit it first; build a read-only runner with fixture tests; draft (not post) a Mac mini request. Publish nothing, write nothing live.

Branch `research/weather-retro-validation-2026-11-23` from `origin/main` `5db0679`, worktree `/home/claude/sector_engine_wxretro` (cloud container).

## What was read (observed)
| Item | Evidence |
|---|---|
| §5 criteria, marks, windows, minimum samples | `docs/brains/WEATHER_BRAIN_PLAN.md` §5.1–§5.3 |
| Rubric validation states (VALIDATED / PARTIAL / NOT_VALIDATED; INSUFFICIENT is never PASS) | PR #241 `docs/brains/scoring/drafts/weather-score-v1.json` `validationStatusMeaning` (open, not adopted) |
| Station selection: NWS list order, first 3 | `brains/weather/runtime/sector_weather/publish.py` `resolve_point` |
| Per-instant value pick, offset, trend | `reading.py` `assemble`, `tendency` |
| Change rules and thresholds v1 | `signal.py` `evaluate`; `runtime/knowledge/weather-change-thresholds-v1.json` |
| Observation request window (13 h) | `client.py` `LiveSource.observations`, `contract.py` `OBS_LOOKBACK_HOURS` |

## Changes
| Commit | What |
|---|---|
| `c8d2e526` | Protocol `WX-RETRO-2026-11-23` and its sha256 sidecar, committed **before** the runner and before any data was fetched (`6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8`) |
| `fff5b0cb` … `HEAD` | Runner `tools/research/weather_retro_validation.py` (imports the Brain's own `assemble`, `evaluate`, `tendency`, `decode_*`; no second copy of the logic), plan amendment §5.4, Weather research README and GAPS evidence lines, draft Mini request, this record, closeout, Cortex gap CG-3.1-26. **Current state:** protocol `WX-RETRO-2026-11-23.5` (`2133b04e…`) on the shared run ledger (#251), 46 offline tests; the protocol history and every review round are below |

Choices made (reversible, standing approval 6), all fixed in the protocol before data:
- Past window ending 2026-11-19 (4 days before registration, archives settled): 5.1 14 days, 5.2 30 days, 5.3 60 days, evaluation every hour at HH:10Z.
- Archive: IEM ASOS routine + special METARs (the NWS API's feed), mapped to the Brain's `Obs`; wxcodes mapped to NWS text wording so the Brain's own `weather_code` decides "precipitation present".
- Substitution check R-SUB added: the archive must reproduce the NWS API's last 7 days (coverage ≥ 0.95, temperature/pressure/precip agreement ≥ 0.99 at one quantum); otherwise no criterion may be reported PASS.
- Grid not replayed (no archive): RAIN_EXPECTED and WATCH shares are not graded; CHANGE (observed events only) is.
- Fronts: WPC CODSUS, 0.1° bulletins only, COLD/WARM/OCFNT within 50 mi; no substitute source if unavailable (NOT_GRADED).
- 5.3 minimum sample added (30 truth and 30 Brain events per kind, 10 lakes); POD primary population = truth events when the Brain's rule was evaluable (strict POD reported too).
- Rubric mapping proposed only: retrospective PASS is evidence; it never writes `/validation/weather`. Owner decides whether it stands in for prospective 5.2/5.3.

## Verification
- `python3 -I tools/research/weather_retro_validation.py verify`: OK, sha256 as registered.
- `python3 -m pytest -q tools/research`: 109 passed, 2 failed. The 2 failures (`test_cleanup_removes_read_only_campaign_files_but_nothing_else`, `test_read_only_sources_folder_is_never_modified`) are **pre-existing** (recorded in `2026-11-23-water-temp-protected-truth.md`: this container runs as root, so read-only permission checks do not hold). The 17 new tests pass.
- `brains/weather` pytest: 116 passed (unchanged; no runtime file touched). `jobs/brain-scores`: 37 passed.
- Timing: one lake, 60 days of synthetic hourly reports, all criteria: 0.17 s, so the full directory grades in minutes.
- `research-check --repo .`: 85 findings on the branch and on `origin/main` (unchanged); none in the new files. `research-check --gaps brains/weather/research/GAPS.json`: 0. `research-check --closeout`: 0.
- `data-check --repo .`: unchanged output size (548 lines); the runner reads no Firebase path.
- `mission-audit --brain weather`: 5 findings, all pre-existing (`UNREGISTERED_BRAIN` weather/moon/generation, CG-W-1; legacy fish layout) plus `UNKNOWN_BRAIN` for the proposed work, which is the same unregistered-Brain gap.
- Security: no secrets, no machine paths; fixtures are the Brain's recorded NWS files or labelled SYNTHETIC (SEC-02); the runner refuses any host outside the protocol's three and non-https URLs (test), and writes only under `--out`.

## Data fetched
None, by design: the protocol was hashed first and the run belongs to the Mac mini.

## Decisions for Michael (batched)
1. Post the draft Mini request on Sector_Ops #51: `docs/brains/weather-retro-validation/MINI_REQUEST_DRAFT.md`.
2. After results: may retrospective R-5.2 / R-5.3 PASS (with R-SUB PASS) stand in for the prospective 5.2 / 5.3 windows (protocol `resultStates.rubricMapping`)? Recommendation: yes for 5.3 and 5.2 as PARTIAL evidence, keep prospective 5.1 (published values) and a prospective WX-001 window as the confirmation before VALIDATED.
3. Research folder for Weather: Cortex has none (CG-3.1-26). Since `.5` the run ledger resolves its root with `research-path sector/engine weather`, which fails at the pinned Cortex, so the run is BLOCKED until a Cortex release registers the Weather research folder and the Engine pin moves; the protocol registers no fallback (see round 5).
4. (Resolved) Worktrees `se_wt_validation` and `sector_engine_wt_wtpt` (REMOVABLE_MERGED, other sessions) were removed by the coordinator: merged and clean.

## Not done (gated or out of scope)
No data fetched, no Firebase read or write, no Brain runtime, knowledge release, manifest, execution-control, rubric or score change, nothing published, no merge.

## Closeout
[`2026-11-23-weather-retro-validation.closeout.md`](2026-11-23-weather-retro-validation.closeout.md) (stored here because the cloud container has no research home; CG-3.1-22).

## Operating contract
Gaps WX-001, WX-002; bowfisher decision: whether the Pressure and Air Temperature tiles describe the lake and whether Lake/Water Temp refresh when the weather turns; score before/after UNSCORED / UNSCORED (draft rubric, Brain never published); field validation needed: none; not changed: live systems, schedulers, customer `/conditions`, Brain logic, thresholds.

## Review round 1 (coordinator)
- Cortex gap id renumbered CG-3.1-24 → CG-3.1-26 (PR #244 holds CG-3.1-24, PR #245 CG-3.1-25); every citation updated. Protocol bytes and sha256 unchanged. Engineering-status digest regenerated.

## Review round 2 (independent review of 93f7aeb0: NOT CLEAN), re-registered as v2 before any data
Merged `origin/main` (no force-push). Still nothing fetched, so the protocol was re-registered rather than amended after data:
**`WX-RETRO-2026-11-23.2`**, sha256 `01eac7bc56033154dcf64ee365826a0da1c4d33cd921cec7ec76e79df48eb58c`, committed alone in `b8e284f3`. v1 (`6e08d42e…`) is kept byte-for-byte, marked SUPERSEDED in `docs/brains/weather-retro-validation/README.md`, and the runner no longer loads it.

| Finding | Fix (protocol v2 + runner + test) |
|---|---|
| HIGH CODSUS: a `000` separator after a front block made the previous bulletin ineligible | Separators (`000`, WMO heading, PIL, title, SOH/ETX) end the bulletin in progress; per VALID time the latest WMO issuance wins whatever the order (IEM also asked `order=asc`). Two-product test |
| HIGH R-SUB too narrow | Every 5.3 input: temperature, dew point, pressure, wind speed, wind direction (both ≥ 5 mph), precipitation, present-weather presence (code agreement reported only); null-versus-value agreement per field; ≥ 1000 pairs per metric; per-station coverage floor (≥ 20 reports and < 0.90 matched → FLAGGED, lake excluded as SUBSTITUTION_STATION); truth (candidate) stations included; per-criterion gates (`gates()`): any gating metric not PASS → no PASS for that criterion |
| HIGH POD population | Graded POD = all truth events (misses with no Brain data count); evaluable-only POD is a labelled secondary. Truth-onset definition and 2 h merge labelled `amendmentAdditions` |
| MEDIUM fixtures inside windows | Disclosed in `dataExaminedBeforeRegistration`; `excludedSpans` drops Guntersville and Champlain 2026-11-06 07:00Z→11-07 00:00Z (instants, values, pairs, events); counts reported |
| MEDIUM 5.1 label | Now R-5.1R "replay self-consistency check", not the plan's 5.1, never a stand-in |
| MEDIUM wx mapping | Earliest row across all tokens wins (`BR -RA` → Light Rain); VCTS, VCSH, VCFG rows |
| MEDIUM unjudgeable fronts | Brain fronts with no eligible analysis within ±3 h left out of FAR and counted |
| LOW separation | Independent station ≥ 3 mi from every Brain station; distance to lake and to nearest Brain station recorded |
| LOW UA / redirects / bytecode | One User-Agent (`SECTOR_WEATHER_USER_AGENT` or `Sector-WeatherRetroValidation/0.2 …`) for all hosts, stated in the protocol; redirects refused; Mini runs with `PYTHONDONTWRITEBYTECODE=1`, `python3 -I` |

Gap renumbered CG-3.1-24 → CG-3.1-26 (collision with #244 / #245). Verification: 26 runner tests pass; `tools/research` 118 passed, 2 pre-existing failures (root permission); `verify` OK for v2 and v1; engineering-status digest regenerated and `--check` OK; Mini draft updated to v2.

## Review round 3 (independent review of 951f6dd6: NOT CLEAN), re-registered as .3 before any data
Still nothing fetched. **`WX-RETRO-2026-11-23.3`**, sha256 `492c1befe2707ce559c5999da7931548e69728c9fffadf16524813efdb5ec7c7`, committed **alone** in `90876982` (the protocol file only; its sidecar and the README followed in `978ca7c4`, the runner after). `.2` (`01eac7bc…`) and v1 (`6e08d42e…`) are byte-identical and marked SUPERSEDED in the folder README.

| Finding | Fix |
|---|---|
| HIGH R-5.2 dropped pairs where the Brain's trend3h was null | Owner rule (unknowns count against the Brain) stated in `unknownsRule`. A null Brain trend counts as a disagreement; trend pairs are also formed at instants with no Brain pressure. Only truth-side gaps are excluded, counted separately (`truthNoReport`, `truthTrendNull`). `brainAvailability` (pressure and air temperature) is reported with every graded instant in the denominator |
| MEDIUM superseded protocols loadable | `load_protocol` refuses any id other than `.3`, `status` SUPERSEDED, and the v1/.2 hashes; the test that loaded v1 now asserts both are refused and byte-identical |
| MEDIUM failed NWS fetch silently skipped | `fetch-recent` records every error; a station with an error or no response file is FLAGGED `FETCH_FAILED`; its lakes are excluded and counted as `SUBSTITUTION_FETCH_FAILED` |
| MEDIUM no SLP in R-SUB | `seaLevelPressure` value (≤ 0.15 hPa) and null agreement, gating R-5.2, FRONT_PASSAGE (and R-5.1R, which also reads mslp for its offset; choice stated here) |
| MEDIUM no wet-conditioned agreement | `wetPrecipitation` and `wetPresentWeatherPresence` over pairs where either side shows precipitation: ≥ 200 pairs, ≥ 0.95, gating RAIN_ONSET |
| LOW span overlap | a front episode whose matching window [first − 3 h, last + 3 h] overlaps the fixture span is excluded |
| LOW contemporaneity | `fetch-asos` now fetches only the window; the new `fetch-recent` fetches the IEM archive and NWS for each station back to back; `grade` returns R-SUB NOT_GRADED (FETCH_NOT_CONTEMPORANEOUS) when any station's two fetch times are more than 1 h apart |

Verification: 32 runner tests pass; `tools/research` 124 passed, 2 pre-existing failures (root permission); `verify` OK on `.3`; engineering-status digest regenerated, `--check` OK; Mini draft, plan §5.4, research README, GAPS lines and PR body cite `.3`. Temp files for edits and the PR body used unique names in the session scratchpad and were removed.

## Review round 4 (independent review of 2595ddd9: NOT CLEAN), re-registered as .4 before any data
The core finding: the operator could still choose what is graded after seeing results. Still nothing fetched. **`WX-RETRO-2026-11-23.4`**, sha256 `55f850efe9ebd6dc972df59152667b99a5c49dc26cd87263b049c4ea3e9f314d`, committed **alone** in `9cce990c` (the protocol file only; sidecar and README in `1d4b78f1`; runner after). `.3` (`492c1bef…`), `.2` and v1 are byte-identical, marked SUPERSEDED in the folder README and refused by the loader (test). Design rule stated in the protocol (`designRule`): the graded population and every input are bound before any comparison, and every exclusion counts against the Brain.

| Finding | Fix |
|---|---|
| HIGH exclusions decided in the grading pass; fetch-recent re-runnable with any `--stations` | One write-once run folder (`--run R`): each fetch step creates its own stage folder and refuses an existing one; `fetch-asos`/`fetch-recent`/`fetch-fronts` take stations only from `R/stations/stations.json`, refused unless its sha256 equals the fetch-stations record. New `bind` step writes write-once `run-manifest.json` from provenance, hashes, timestamps and row presence only: every file and sha256, every fetch status, station flags (FETCH_FAILED, COVERAGE_FLOOR), contemporaneity, fronts status, each lake's exclusion reason or independent station with skipped candidates, and per-criterion populations. `grade` refuses unless the stage files on disk equal the manifest exactly |
| HIGH exclusions must count against the Brain | Registered rule (`exclusionsCountAgainst`): per criterion, coverage = bound lakes / directory lakes (BLOCKED in the denominator); below 0.75 the criterion is FAIL (COVERAGE_BELOW_MINIMUM); excluded lakes reported by reason |
| HIGH stations.json not verified; lakes ≠ directory count | `load_stations` checks the recorded sha256 everywhere; `subset` is bound when the lake count differs from the directory count (cannot PASS or FAIL) |
| HIGH window provenance unread; fallback not bound | bind reads window provenance: a missing record, error, missing file or missing fetchedAt is FETCH_FAILED; a hash mismatch or an unrecorded file REFUSES; the independent fallback walks candidates in recorded order and skips FETCH_FAILED, COVERAGE_FLOOR and no-rows candidates, recorded per lake |
| MEDIUM files present but fetch time missing | FETCH_FAILED (test) |
| MEDIUM write-once outputs; run log | stage folders, run-manifest.json and report.json are write-once; `grade --run-log L` appends START (runNumber, runId, manifest sha256, protocol sha256) before any comparison and RESULT after; the report shows runNumber, priorRuns and `counts`; runNumber > 1 is REPEAT_RUN and every PASS/FAIL becomes NOT_GRADED (registered `runLog.onlyRunOneCounts`) |
| LOW FAR wet hits / MAE truth drops | wet reports inside the excluded span never make a hit (counted `truthReports`); `maeCounts` reports truth-no-report drops for pressure and air-temperature MAE |

Verification: 37 runner tests pass; `tools/research` 129 passed, 2 pre-existing failures (root permission); `verify` OK on `.4`; engineering-status digest regenerated, `--check` OK. Mini draft, plan §5.4, research README, GAPS lines, closeout and PR body cite `.4`. Edit scripts and the PR body used uniquely named files in the session scratchpad, removed afterwards.

## Round 5 (coordinator): adopt the shared protocol run ledger (#251) as .5, before any data
Merged `origin/main` at `bbdaa35` (no rebase); CORTEX_GAPS kept both sides (CG-3.1-26, then main's CG-3.1-27/28). Read the merged `tools/research/protocol_run_ledger.py` in full first. **`WX-RETRO-2026-11-23.5`**, sha256 `2133b04e9c65d3a10a9a878a92ea206fa1c0745b0023613cf0a74f2ed6f66386`, committed **alone** in `faafe95c`; sidecar and README (marks .4 superseded) in `7c9c36f3`. `.4` (`55f850ef…`) and earlier versions are byte-identical and refused by the loader.

| Item | Choice / change |
|---|---|
| Ledger | `Ledger.for_brain('weather', 'WX-RETRO-2026-11-23.5', sha256(protocol), forbid_under=[run folder], result_steps=RESULT_STEPS)` via `open_ledger()`; the local run log (`--run-log`, START/RESULT lines, `_log`) is removed; `verify_run` stays as the exact disk check next to the ledger's `check_inputs` |
| Result steps | `frozenset({'grade'})`. **Choice:** `bind` is not result-defining (it reads provenance, hashes, timestamps and row presence and never compares values); the fetch steps compare nothing |
| Keys | every step uses the fixed key `directory` (registered in the protocol) |
| Non-result steps | `fetch-stations`, `fetch-asos`, `fetch-recent`, `fetch-fronts` and `bind` each `begin` (the ledger checks the #51 anchor first), do their work, `complete` with their stage tree hash; an exception aborts before any result and the step cannot be redone in this run. Fetch steps after `fetch-stations` pass the stations tree and `stations.json` hash; `bind` refuses unless each stage tree equals its fetch step's completed output, then calls `bind_inputs('grade', 'directory', {run-manifest.json, stations, asos, recent, fronts})` |
| grade | `check_inputs` + exact disk match → `begin` → `start_text` written to `ledger-start.txt` and posted → `confirm_started` (retry on "not listed yet", never repost) before any comparison → grade → `record_outputs(report.json)` → `complete(result summary)` → `result_text` posted → `confirm_result` → `ledger-audit.json` from `audit(check_external=True)` |
| Kept from .4 | bound inputs, coverage ≥ 0.75 per criterion, SUBSET (now only from a short directory read: fetch-stations has no subset options under the protocol id), write-once stages, manifest before grade |
| New `ledger-anchor` step | prints `post_anchor_text()` for #51 before any step |

**Blocker (owner/Cortex):** `research-path sector/engine weather` fails at the pinned Cortex (CG-3.1-26), so `Ledger.for_brain('weather', …)` refuses and the run cannot start until a Cortex release registers the Weather research folder and the Engine pin moves. Checked: `CORTEX_HOME=<extract> … ledger-anchor` → `LedgerRefusal: research-path sector/engine weather failed … unknown Brain or folder 'weather'`. The protocol registers no fallback folder (a later change would need a new protocol id).

Verification: 43 runner tests pass (8 new ledger tests against a mocked #51: anchor-before-any-step, full bind/grade flow with one start and one result record and `counted: true`, ledger refuses a re-run even with outputs removed, `check_inputs` refuses a changed input before any start, bind refuses a stage that differs from its completed fetch, a fetch step runs once, "not listed yet" waits without reposting, a second start hash is a REPEAT before any comparison); `tools/research` 214 passed, 2 pre-existing failures (root permission); `verify` OK on `.5`; engineering-status digest regenerated, `--check` OK.

## Round 6 (independent review of 303026df: NOT CLEAN, one HIGH), runner change only
`_ledger_step` aborted a fetch on any exception, even after per-station files were saved, so a retry could refetch a moving 7-day window and change FETCH_FAILED / COVERAGE_FLOOR flags. Now `abort_before_result` is called only when nothing was saved: no file under the step's output path AND the in-memory save count (`_SAVED`, incremented in `_save` before each write) is 0; the empty stage folder is then removed so the step may be retried in the same run folder (the ledger gives it attempt 2). Otherwise the attempt is left STARTED (terminal), nothing is deleted, and the runner prints that recovery needs a new protocol id AND a revised protocol document recorded in a #51 human review. `bind` follows the same rule (its output is run-manifest.json). The `_ledger_step` docstring and the `_new_stage` refusal text say this. Tests: an interrupt before the first save aborts and the retry completes as attempt 2; an interrupt after one save is terminal, the retry is refused by the existing folder and, with the folder gone, by the ledger ("never completed"); a saved-then-removed file still counts. No protocol change (.5 unchanged). 46 runner tests pass; `tools/research` 217 passed, 2 pre-existing failures (root permission); engineering-status digest regenerated, `--check` OK.

## Round 7 (delta review of 5345ae5e): every write is counted
- **The fix.** Every file write in the runner now goes through one helper, `_write_file`. It increments `_SAVED` before it creates any directory or writes any byte. The writes it covers:
  - archive and NWS responses (`_save`) and `provenance.json` (`_write_prov`);
  - `run-manifest.json` in `bind`;
  - the ledger start and result texts, `report.json` and `ledger-audit.json`, which are write-once and opened exclusively.
- **Abort path.** It removes only an empty directory tree, bottom-up. A removal failure is printed and never masks the original exception.
- **New tests (6):**
  - an AST test fails if any write happens outside `_write_file`: `open` for writing, `json.dump`, `write_text`/`write_bytes`, `os.replace`/`rename`, or `shutil` copies. Directory creation is allowed only in `_write_file` and `_new_stage`;
  - an interrupt after only `provenance.json` is written is terminal;
  - an interrupt inside the writer, after the count but before any directory, is terminal;
  - a `bind` interrupt before the manifest aborts, and the retry completes;
  - a `bind` interrupt after the manifest is written is terminal, and the ledger refuses the retry even with the manifest removed;
  - the empty-tree removal removes only directories.
- **Results.** No protocol change. 52 runner tests pass. `tools/research` has 2 failures, the root-permission tests that already fail in this container. The engineering-status digest was regenerated, and `--check` passes.
