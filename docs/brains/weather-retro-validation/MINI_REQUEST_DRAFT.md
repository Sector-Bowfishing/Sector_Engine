Claude request (under Owner approval 2026-11-22): Weather Brain retrospective validation WX-RETRO-2026-11-23.3 (read-only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

**Limits.** This is read-only research.
- Do not run `run.py --write`.
- Do not change the Weather Brain, its knowledge release, the control manifest, execution control, any score or rubric, `/validation/weather`, RTDB, Pulse jobs or schedules.
- Do not create cloud jobs, and do not run anything on the MacBook Pro.
- Use the Engine checkout at the merged commit of the PR named below, or that PR's branch if it has not merged.

**Where to work.** Use the Weather research folder `weather-brain` under the Sector research home (Cortex `research-path` does not know `weather` yet; see CG-3.1-26). Create `README.md` and `manifest.json` there if absent. Write outputs only under `weather-brain/retro-validation/`, and end with a research closeout.

**Protocol.** `docs/brains/weather-retro-validation/WX-RETRO-2026-11-23.3.protocol.json`, sha256 `492c1befe2707ce559c5999da7931548e69728c9fffadf16524813efdb5ec7c7`, pre-registered before any data was fetched.
- It supersedes `.2` (`01eac7bc…`) and v1 (`6e08d42e…`). The runner refuses both, so do not try to run them.
- Runner: `tools/research/weather_retro_validation.py`.
- Windows (UTC): R-5.1R 2026-11-05..11-19, 5.2 2026-10-20..11-19, 5.3 2026-09-20..11-19.
- All lakes in the Engine directory.

**Environment.** Set both before any fetch, and keep them for every step:
- `export PYTHONDONTWRITEBYTECODE=1`
- `export SECTOR_WEATHER_USER_AGENT="<the Lake Brain's NWS contact string>"`

The runner sends that one User-Agent to every host and refuses redirects. Run each step from the checkout root as `python3 -I tools/research/weather_retro_validation.py <step>`. Below, R = `<research home>/weather-brain/retro-validation`.

1. `verify`. Stop if the hash does not match.
2. `fetch-stations --out R`. This reads the Engine `/lakes` and the NWS `/points` and station lists: about 1,250 NWS requests at 0.25 s.
3. `fetch-asos --stations R/stations.json --out R/asos`. This is the IEM ASOS archive for the window, one request per station at 1 s pacing.
4. `fetch-recent --stations R/stations.json --out R/recent`. For every Brain and candidate independent station, this fetches the IEM archive and then the NWS API for the last 7 days, back to back, and records each fetch time and every error.
   - If you rerun it, rerun it whole. `grade` reports R-SUB NOT_GRADED if any station's two fetches are more than 1 h apart.
   - Stations whose fetch failed are flagged, and their lakes are excluded and counted.
5. `fetch-fronts --out R/fronts`. If `codsus.txt` is empty or has no `VALID` lines, do not look for another front source: FRONT_PASSAGE is then NOT_GRADED, as the protocol says.
6. `grade --stations R/stations.json --asos R/asos --recent R/recent --fronts R/fronts/codsus.txt --out R/report.json`.

**Manifest.** Register every file or folder in the manifest:
- a sha256 for each file, or a sha256-tree-v1 hash for each folder;
- the source URL from each provenance.json;
- retention RECONSTRUCTABLE for fetched data, and ARCHIVAL for report.json.

If anything in the method must change after you have looked at the data, do not edit the protocol. Record it in the report under methodChanges and re-run (RS-30).

Post a short summary on #51 (under 15 lines):
- the protocol sha256, the report.json sha256 and the Engine commit
- lakes: in directory / BLOCKED / SUBSTITUTION_FETCH_FAILED / SUBSTITUTION_STATION / no independent station / graded, and the excluded-span counts
- R-SUB: result or NOT_GRADED reason, coverage, each metric's value and null agreement (pairs), the wet-conditioned metrics, flagged stations by reason, and the per-criterion gates
- R-5.1R (replay self-consistency, not the plan's 5.1): values, match share, provenance share, result
- R-5.2: pressure MAE, trend agreement (Brain-null trends counted as disagreement; the excluded truth gaps), air-temperature MAE (pairs, lakes), Brain availability for pressure and temperature, the result, and the seaLevel/altimeter and distance-band split
- R-5.3, for RAIN_ONSET and FRONT_PASSAGE: POD on all truth (graded), POD on evaluable truth (secondary), FAR, unjudgeable fronts, eligible analyses, the result, and the median CHANGE-hours per lake per week
- the qualifiers and any methodChanges
- questions for Michael: (a) may a retrospective R-5.2/R-5.3 PASS stand in for the prospective 5.2/5.3 windows (protocol rubricMapping)? (b) on any FAIL: open a weather-change-thresholds-v2 proposal (5.3), or a station-rule review (5.2)?
