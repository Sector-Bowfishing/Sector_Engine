Claude request (under Owner approval 2026-11-22): Weather Brain retrospective validation WX-RETRO-2026-11-23.5 (read-only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

**Blocked today.** The run ledger opens with `Ledger.for_brain('weather', …)`, which resolves its folder with Cortex `research-path sector/engine weather`. At the pinned Cortex (3.1.6 @ a785035), that command fails with "unknown Brain or folder 'weather'" (CG-3.1-26). Nothing below can run until a Cortex release registers the Weather research folder and the Engine pin moves to it. Do not work around this by using another folder: the protocol registers no fallback.

**Limits.** This is read-only research.
- Do not run `run.py --write`.
- Do not change the Weather Brain, its knowledge release, the control manifest, execution control, any score or rubric, `/validation/weather`, RTDB, Pulse jobs or schedules.
- Do not create cloud jobs, and do not run anything on the MacBook Pro.
- Use the Engine checkout at the merged commit of the PR named below, or that PR's branch if it has not merged.

**Protocol.** `docs/brains/weather-retro-validation/WX-RETRO-2026-11-23.5.protocol.json`, sha256 `2133b04e9c65d3a10a9a878a92ea206fa1c0745b0023613cf0a74f2ed6f66386`, pre-registered before any data was fetched.
- It supersedes `.4` (`55f850ef…`), `.3`, `.2` and v1. The runner refuses all of them.
- Runner: `tools/research/weather_retro_validation.py`, with the shared run ledger `tools/research/protocol_run_ledger.py`.
- Windows (UTC): R-5.1R 2026-11-05..11-19, 5.2 2026-10-20..11-19, 5.3 2026-09-20..11-19.
- All lakes in the Engine directory.

**Rules (protocol designRule and runLedger).**
- **Inputs are bound before any comparison.**
- **Exclusions count against the Brain:** each criterion needs at least 0.75 of the directory, otherwise it is FAIL.
- **Each step runs once.** Every step is a ledger step with the fixed key `directory`. The ledger refuses a second run of any step, and only the ledger's counted first `grade` counts.
- **Comments are research records.** The `Run anchor:`, `Run start:` and `Run result:` comments on #51 are research records posted by this session. Never put them under an "Owner approval" header. Nobody edits or deletes them; a correction is a new comment.
- **"Not listed yet":** the runner waits and retries. Never post a record twice.
- **If anything fails:**
  - Do not delete or edit anything in the run folder or the ledger.
  - Stop and report it on #51.
  - Recovery needs a new protocol id and a revised protocol recorded in a #51 human review.

**Environment.** Set these before step 1, and keep them for every step:
- `export PYTHONDONTWRITEBYTECODE=1`
- `export CORTEX_HOME=<the Cortex checkout at the Engine pin>`
- `export SECTOR_WEATHER_USER_AGENT="<the Lake Brain's NWS contact string>"`
- `gh` must be authenticated: the ledger reads #51 through it.

Run each step from the checkout root as `python3 -I tools/research/weather_retro_validation.py <step>`. Below, R = `<the research-path folder for weather>/retro-validation/run-1`; it must not exist yet.

1. `verify`. Stop if the hash does not match.
2. `ledger-anchor --run R`. This opens the ledger and prints the anchor text. Post that text on #51 exactly as printed, once, before any other step, for example with `gh api repos/Sector-Bowfishing/Sector_Ops/issues/51/comments -F body=@<file holding the text>`.
3. `fetch-stations --run R`. This reads the Engine `/lakes` and the NWS `/points` and station lists.
4. `fetch-asos --run R`.
5. `fetch-recent --run R`. Per station, this fetches the archive and the NWS API back to back for the last 7 days.
6. `fetch-fronts --run R`.
7. `bind --run R`. This writes R/run-manifest.json and binds grade's inputs in the ledger. Record the printed manifest sha256 and population.
8. `grade --run R`, which runs in three stages:
   1. It checks the bound inputs, begins the step, and writes `R/ledger-start.txt`. Post that text on #51 once, from a second shell, while grade waits. It confirms the post before comparing anything.
   2. It grades and writes R/report.json.
   3. It writes `R/ledger-result.txt`. Post that once in the same way, and it confirms it. It then writes R/ledger-audit.json.

**Manifest.** Register in the Weather research folder's manifest:
- each stage folder as a sha256-tree-v1, with its source URLs from provenance.json;
- run-manifest.json, report.json, ledger-audit.json, and the ledger files `_ledgers/WX-RETRO-2026-11-23.5.*`;
- retention RECONSTRUCTABLE for fetched data, and ARCHIVAL for the rest.

Post a short summary on #51 (under 15 lines), separate from the three ledger records:
- the protocol sha256, the manifest sha256, the report sha256, the Engine commit, and the ledger's counted flag for grade, from ledger-audit.json (it must be true, with no findings)
- the bound population per criterion versus the directory count, with the coverage share and the excluded lakes by reason, and the excluded-span counts
- R-SUB: result or NOT_GRADED reason, coverage, each metric's value and null agreement (pairs), the wet-conditioned metrics, flagged stations by reason, and the per-criterion gates
- R-5.1R (replay self-consistency, not the plan's 5.1): values, match share, provenance share, result
- R-5.2: pressure and air-temperature MAE (pairs, lakes, truth-no-report counts), trend agreement (Brain-null counted as disagreement), Brain availability, the result, and the seaLevel/altimeter and distance-band split
- R-5.3, for RAIN_ONSET and FRONT_PASSAGE: POD on all truth (graded), POD on evaluable truth (secondary), FAR, unjudgeable fronts, eligible analyses, the result, and the median CHANGE-hours per lake per week
- the qualifiers and any methodChanges
- questions for Michael: (a) may a retrospective R-5.2/R-5.3 PASS stand in for the prospective 5.2/5.3 windows (protocol rubricMapping)? (b) on any FAIL: open a weather-change-thresholds-v2 proposal (5.3), or a station-rule review (5.2)?
