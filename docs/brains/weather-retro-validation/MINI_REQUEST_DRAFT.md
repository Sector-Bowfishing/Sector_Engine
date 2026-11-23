Claude request (under Owner approval 2026-11-22): Weather Brain retrospective validation WX-RETRO-2026-11-23.4 (read-only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

**Limits.** This is read-only research.
- Do not run `run.py --write`.
- Do not change the Weather Brain, its knowledge release, the control manifest, execution control, any score or rubric, `/validation/weather`, RTDB, Pulse jobs or schedules.
- Do not create cloud jobs, and do not run anything on the MacBook Pro.
- Use the Engine checkout at the merged commit of the PR named below, or that PR's branch if it has not merged.

**Where to work.** Use the Weather research folder `weather-brain` under the Sector research home (Cortex `research-path` does not know `weather` yet; see CG-3.1-26). Create `README.md` and `manifest.json` there if absent, and end with a research closeout.

**Protocol.** `docs/brains/weather-retro-validation/WX-RETRO-2026-11-23.4.protocol.json`, sha256 `55f850efe9ebd6dc972df59152667b99a5c49dc26cd87263b049c4ea3e9f314d`, pre-registered before any data was fetched.
- It supersedes `.3` (`492c1bef…`), `.2` (`01eac7bc…`) and v1 (`6e08d42e…`). The runner refuses all three.
- Runner: `tools/research/weather_retro_validation.py`.
- Windows (UTC): R-5.1R 2026-11-05..11-19, 5.2 2026-10-20..11-19, 5.3 2026-09-20..11-19.
- All lakes in the Engine directory.

**How the run is bound (protocol designRule).**
- **Inputs:** every input is fixed in a write-once run folder before anything is compared.
- **Exclusions:** every excluded lake counts against the Brain. Each criterion needs at least 0.75 of the directory, or it is FAIL.
- **Run log:** only the first grading in the run log counts. Run the steps once, in order, into ONE new run folder.
- **If something breaks:**
  - Do not delete or edit anything in the run folder.
  - A rerun means a new run folder. Its grading is then run #2 and is not counted.
  - Report the failure on #51 instead.

**Environment.** Set both before any fetch, and keep them for every step:
- `export PYTHONDONTWRITEBYTECODE=1`
- `export SECTOR_WEATHER_USER_AGENT="<the Lake Brain's NWS contact string>"`

Run each step from the checkout root as `python3 -I tools/research/weather_retro_validation.py <step>`. Use these paths:
- R = `<research home>/weather-brain/retro-validation/run-1` (must not exist yet)
- L = `<research home>/weather-brain/retro-validation/RUNS.jsonl` (append-only run log; create it only through `grade`, never edit or delete it)

1. `verify`. Stop if the hash does not match.
2. `fetch-stations --run R`. This reads the Engine `/lakes` and the NWS `/points` and station lists (about 1,250 NWS requests at 0.25 s) and writes R/stations/.
3. `fetch-asos --run R`. This is the IEM archive for the window, one request per station at 1 s pacing, and writes R/asos/.
4. `fetch-recent --run R`. For every Brain and candidate station, this fetches the IEM archive and then the NWS API for the last 7 days, back to back, and writes R/recent/. Every error is recorded.
5. `fetch-fronts --run R`. This writes R/fronts/.
6. `bind --run R`. This writes R/run-manifest.json (write-once). Record the printed manifest sha256 and the population before grading.
7. `grade --run R --run-log L`. It refuses if anything on disk differs from the manifest. It logs START, writes R/report.json (write-once) and logs RESULT.

**Manifest.** Register in the research folder's manifest:
- each stage folder as a sha256-tree-v1, with its source URLs from provenance.json;
- run-manifest.json, report.json and RUNS.jsonl;
- retention RECONSTRUCTABLE for fetched data, and ARCHIVAL for run-manifest.json, report.json and RUNS.jsonl.

If anything in the method must change after you have looked at the data, do not edit the protocol. Record it in the report under methodChanges and re-run (RS-30). That re-run is a later run number and does not count.

Post a short summary on #51 (under 15 lines):
- the protocol sha256, the run-manifest.json sha256, the report.json sha256, the Engine commit, and the runNumber (must be 1)
- the bound population per criterion versus the directory count, with the coverage share and the excluded lakes by reason, and the excluded-span counts
- R-SUB: result or NOT_GRADED reason, coverage, each metric's value and null agreement (pairs), the wet-conditioned metrics, flagged stations by reason, and the per-criterion gates
- R-5.1R (replay self-consistency, not the plan's 5.1): values, match share, provenance share, result
- R-5.2: pressure MAE and air-temperature MAE (pairs, lakes, truth-no-report counts), trend agreement (Brain-null counted as disagreement; truth gaps excluded), Brain availability, the result, and the seaLevel/altimeter and distance-band split
- R-5.3, for RAIN_ONSET and FRONT_PASSAGE: POD on all truth (graded), POD on evaluable truth (secondary), FAR, unjudgeable fronts, eligible analyses, the result, and the median CHANGE-hours per lake per week
- the qualifiers and any methodChanges
- questions for Michael: (a) may a retrospective R-5.2/R-5.3 PASS stand in for the prospective 5.2/5.3 windows (protocol rubricMapping)? (b) on any FAIL: open a weather-change-thresholds-v2 proposal (5.3), or a station-rule review (5.2)?
