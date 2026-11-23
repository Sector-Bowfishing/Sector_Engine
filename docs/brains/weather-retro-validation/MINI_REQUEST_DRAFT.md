Claude request (under Owner approval 2026-11-22): Weather Brain retrospective validation WX-RETRO-2026-11-23.2 (read-only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

Read-only research. Do not run `run.py --write`, change the Weather Brain, its knowledge release, the control manifest, execution control, any score, rubric or `/validation/weather`, RTDB, Pulse jobs or schedules. Do not create cloud jobs. Do not run anything on the MacBook Pro. Use the Engine checkout at the merged commit of the PR named below (or that PR's branch if it has not merged). Work in the Weather research folder (`weather-brain` under the Sector research home; Cortex `research-path` does not know `weather` yet, see CG-3.1-26): create `README.md` and `manifest.json` there if absent, write outputs only under `weather-brain/retro-validation/`, and end with a research closeout.

Protocol: docs/brains/weather-retro-validation/WX-RETRO-2026-11-23.2.protocol.json, sha256 01eac7bc56033154dcf64ee365826a0da1c4d33cd921cec7ec76e79df48eb58c (pre-registered before any data was fetched). It supersedes WX-RETRO-2026-11-23 (sha256 6e08d42e…). Do NOT run v1. Runner: tools/research/weather_retro_validation.py. Windows (UTC): R-5.1R 2026-11-05..11-19, 5.2 2026-10-20..11-19, 5.3 2026-09-20..11-19. All lakes in the Engine directory.

Environment for every step: `export PYTHONDONTWRITEBYTECODE=1` and `export SECTOR_WEATHER_USER_AGENT="<the Lake Brain's NWS contact string>"`, both set before any fetch. The runner sends that one User-Agent to every host and refuses redirects. Run each step as `python3 -I tools/research/weather_retro_validation.py <step>` from the checkout root. Let R = `<research home>/weather-brain/retro-validation`.
1. `verify`. Stop if the hash does not match.
2. `fetch-stations --out R` (Engine `/lakes`, NWS `/points` and station lists; about 1,250 NWS requests at 0.25 s).
3. `fetch-asos --stations R/stations.json --out R/asos` (IEM ASOS archive, one request per station at 1 s pacing, for the window; plus the last 7 days for every Brain AND candidate independent station).
4. `fetch-nws-recent --stations R/stations.json --out R/nws`, for the same stations. Run it within one hour of step 3, so both cover the same 7 days.
5. `fetch-fronts --out R/fronts`. If `codsus.txt` is empty or has no `VALID` lines, do not look for another front source: FRONT_PASSAGE is then NOT_GRADED, as the protocol says.
6. `grade --stations R/stations.json --asos R/asos --nws R/nws --fronts R/fronts/codsus.txt --out R/report.json`.
Register every file or folder in the manifest:
- a sha256 for each file, or a sha256-tree-v1 hash for each folder;
- the source URL from each provenance.json;
- retention RECONSTRUCTABLE for fetched data, and ARCHIVAL for report.json.
If anything in the method must change after you have looked at the data, do not edit the protocol. Record it in the report under methodChanges and re-run (RS-30).

Post a short summary on #51 (under 15 lines):
- the protocol sha256, the report.json sha256 and the Engine commit
- lakes: in directory / BLOCKED / SUBSTITUTION_STATION / no independent station / graded, and the excluded-span counts
- R-SUB: coverage, each metric's value and null agreement (pairs), flagged stations, and the per-criterion gates
- R-5.1R (replay self-consistency, not the plan's 5.1): values, match share, provenance share, result
- R-5.2: pressure MAE, trend agreement and air-temperature MAE (with pairs and lakes), the result, and the pressure-MAE split by seaLevel/altimeter and by distance band
- R-5.3, for RAIN_ONSET and FRONT_PASSAGE: POD on all truth (graded), POD on evaluable truth only (secondary) and FAR. Also the number of unjudgeable fronts, the number of eligible analyses, the result, and the median CHANGE-hours per lake per week
- the qualifiers and any methodChanges
- questions for Michael: (a) may a retrospective R-5.2/R-5.3 PASS stand in for the prospective 5.2/5.3 windows (protocol rubricMapping)? (b) on any FAIL: open a weather-change-thresholds-v2 proposal (5.3), or a station-rule review (5.2)?
