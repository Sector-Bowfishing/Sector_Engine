Claude request (under Owner approval 2026-11-22): Weather Brain retrospective validation WX-RETRO-2026-11-23 (read-only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

Read-only research. Do not run `run.py --write`, change the Weather Brain, its knowledge release, the control manifest, execution control, any score, rubric or `/validation/weather`, RTDB, Pulse jobs or schedules. Do not create cloud jobs. Do not run anything on the MacBook Pro. Use the Engine checkout at the merged commit of the PR named below (or that PR's branch if it has not merged). Work in the Weather research folder (`weather-brain` under the Sector research home; Cortex `research-path` does not know `weather` yet, see CG-3.1-24): create `README.md` and `manifest.json` there if absent, write outputs only under `weather-brain/retro-validation/`, and end with a research closeout.

Protocol: docs/brains/weather-retro-validation/WX-RETRO-2026-11-23.protocol.json, sha256 6e08d42ed7e808a7a9775e885f865233e7ba2bb2279e4fbb8e0171634ed37ab8 (pre-registered before any data was fetched). Runner: tools/research/weather_retro_validation.py (`python3 -I tools/research/weather_retro_validation.py <cmd>` from the checkout root). Windows (UTC): 5.1 2026-11-05..11-19, 5.2 2026-10-20..11-19, 5.3 2026-09-20..11-19. All lakes in the Engine directory.

Set `SECTOR_WEATHER_USER_AGENT` to the same contact string the Lake Brain uses before any fetch. Let R = `<research home>/weather-brain/retro-validation`.
1. `verify`. Stop if the hash does not match.
2. `fetch-stations --out R` (Engine `/lakes`, NWS `/points` and station lists; about 1,250 NWS requests at 0.25 s).
3. `fetch-asos --stations R/stations.json --out R/asos` (IEM ASOS archive, one request per station at 1 s pacing; plus the last 7 days per Brain station).
4. `fetch-nws-recent --stations R/stations.json --out R/nws` (run within an hour of step 3, so both cover the same 7 days).
5. `fetch-fronts --out R/fronts`. If `codsus.txt` is empty or has no `VALID` lines, do not look for another front source: FRONT_PASSAGE is then NOT_GRADED, as the protocol says.
6. `grade --stations R/stations.json --asos R/asos --nws R/nws --fronts R/fronts/codsus.txt --out R/report.json`.
Register every file or folder in the manifest (sha256 or sha256-tree-v1, source URL from each provenance.json, retention RECONSTRUCTABLE for fetched data, ARCHIVAL for report.json). If anything in the method must change after you have looked at the data, do not edit the protocol: record it in the report under methodChanges and re-run (RS-30).

Post a short summary on #51 (under 15 lines):
- protocol sha256, report.json sha256, Engine commit
- lakes: in directory / BLOCKED / no independent station / graded
- R-SUB: coverage and the temperature, pressure and precipitation agreement, result
- R-5.1: values, match share, provenance share, result
- R-5.2: pressure MAE, trend agreement, air-temperature MAE (pairs, lakes), result, plus the seaLevel/altimeter and distance-band split for pressure MAE
- R-5.3: RAIN_ONSET and FRONT_PASSAGE POD/FAR (primary and all-truth POD), eligible front analyses, result; median CHANGE-hours per lake per week
- qualifiers (SUBSET, SUBSTITUTION_UNCERTAIN) and any methodChanges
- questions for Michael: (a) may retrospective R-5.2/R-5.3 PASS stand in for the prospective 5.2/5.3 windows (protocol rubricMapping)? (b) on any FAIL: open a weather-change-thresholds-v2 proposal (5.3) or a station-rule review (5.2)?
