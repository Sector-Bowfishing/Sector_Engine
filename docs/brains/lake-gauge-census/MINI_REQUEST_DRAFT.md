Claude request (under Owner approval 2026-11-22): Lake gauge census LGC-2026-11-23 (read-only, metadata only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

**When:** on or after 2026-12-01, and only after the Lake operator-truth validation (PR #243, 2026-11-24..30) has finished and posted its result on #51. The tool refuses to run before 2026-12-01. Do not run it in parallel with any other Lake job.

**Do not change** bindings, `accepted_batch*.json`, `LakeSourceBindingsGenerated.swift`, the Lake knowledge release, `customer_lake_level_eligible.json`, any score, RTDB, buckets, Pulse jobs or schedules. Do not create cloud jobs. Do not read or judge any level value (stage B is a separate request). Start in the Lake research folder that Cortex `research-path sector/engine lake-brain` returns, write outputs only there, and end with a research closeout.

Use the Engine checkout at the merged commit of the PR named below (or that PR's branch if it has not merged). Rules: `docs/brains/lake-gauge-census/LGC-2026-11-23.rules.json`, sha256 254752ea31823ace94768a7daa658cf70bfa42b8ad0d276ebb1cae1cf86e9e3f. Tool: `tools/research/lake_gauge_census.py`.

1. `python3 tools/research/lake_gauge_census.py verify` must print the sha256 above. Stop if it does not.
2. `python3 tools/research/lake_gauge_census.py lakes --out <folder>/gauge-census/<date>` (offline; expect 621 lakes, 294 reviewed, BINDING 327).
3. `python3 tools/research/lake_gauge_census.py controls --out <folder>/gauge-census/<date>`. Exit 3 means a provider's positive control was not rediscovered (an API shape change). Do not continue for that provider: report which control failed and the HTTP statuses in `requests.jsonl`, then continue with the other providers only if at least USGS and CWMS passed.
4. `python3 tools/research/lake_gauge_census.py census --out <folder>/gauge-census/<date>` (default `--registry` is the public Lake Registry; GET only, about 2,500–4,000 requests at 1 s per host, roughly 1–1.5 h; the budget stops it at 9,000).
5. `python3 tools/research/lake_gauge_census.py summarize --summary <folder>/gauge-census/<date>/census.summary.json`.
6. Register census.json, census.summary.json, robots.json, requests.jsonl, targets.json and controls.json in the folder's manifest.json (sha256, source "LGC-2026-11-23 census", retention RECONSTRUCTABLE). The `cache/` folder holds raw public metadata responses only; keep it for a resumed run, mark it DISPOSABLE.

Post a short summary on #51 (under 15 lines):
- the `summarize` output (controls, BINDING shortlist / hand review / none, the ceiling if every shortlisted lake passes stage B against the 311 target, INDEPENDENT_TRUTH tiers and lakes with a v3-eligible candidate, TVA reservoirs with USGS candidates, outline vs point-only)
- request count, errors by stage, and any host whose robots.txt disallowed a path
- census.json and census.summary.json sha256, and the rules sha256
- questions for Michael:
  (a) Build the batch 3 binding review (stage B, level values, same R1–R9 and checks (b)–(d) as batches 1–2) from the SHORTLIST rows now?
  (b) The HAND_REVIEW rows (point-only lakes, UNKNOWN class, missing datum): review them by hand, or leave them out of batch 3?
  (c) Hand the INDEPENDENT_AGENCY / INDEPENDENT_SITE rows to the operator-truth validation v3 so it can freeze its truth list from them under its own pre-registration?
