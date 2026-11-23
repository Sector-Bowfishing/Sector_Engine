Claude request (under Owner approval 2026-11-22): Lake gauge census LGC-2026-11-23.2 (read-only, metadata only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

**When:** on or after 2026-12-01T12:00Z, and only after the Lake operator-truth validation (PR #243, 2026-11-24..30) has finished and posted its result on #51. The tool refuses any request before 2026-12-01T12:00Z. Do not run it in parallel with any other Lake job.

**Do not change** bindings, `accepted_batch*.json`, `LakeSourceBindingsGenerated.swift`, the Lake knowledge release, `customer_lake_level_eligible.json`, any score, RTDB, buckets, Pulse jobs or schedules. Do not create cloud jobs. Do not read or judge any level value (stage B is a separate request). Start in the Lake research folder that Cortex `research-path sector/engine lake-brain` returns, write outputs only there, and end with a research closeout.

Use the Engine checkout at the merged commit of Sector_Engine PR #247 (or its branch `research/lake-gauge-census-2026-11-23` if it has not merged). Rules: `docs/brains/lake-gauge-census/LGC-2026-11-23.2.rules.json`, sha256 c17feef35f03c072cb79f4d318b465d807fc72afe5ca351f0b787cc3df382ba7 (supersedes the never-used LGC-2026-11-23). Tool: `tools/research/lake_gauge_census.py`.

1. `python3 tools/research/lake_gauge_census.py verify` must print the sha256 above. Stop if it does not.
2. `python3 tools/research/lake_gauge_census.py lakes --out <folder>/gauge-census/<date>` (offline; 621 lakes; on 2026-11-23 the reviewed set was 294 and BINDING 327, report the numbers it prints).
3. `python3 tools/research/lake_gauge_census.py controls --out <folder>/gauge-census/<date>`. Exit 3 means a provider's positive control was not rediscovered (an API shape change). Do not continue for that provider: report which control failed and the HTTP statuses in `controls.requests.jsonl`, then continue with the other providers only if at least USGS and CWMS passed.
4. `python3 tools/research/lake_gauge_census.py census --out <folder>/gauge-census/<date>` (default `--registry` is the public Lake Registry; GET only. Estimate: USGS about 650 (one site query per lake, a few IV and site chunks), CWMS about 1,500–4,000 (38 office location catalogs, then one time-series catalog per location inside a lake box), RISE about 300–800 (the location listing, then items near lakes), plus retries; about 3,000–6,000 requests, roughly 1–2 h at 1 s per host. Every retry counts; the budget stops it at 12,000 and the output still gets written with `budgetExhausted: true`. Do not pass `--origin-evidence`).
5. `python3 tools/research/lake_gauge_census.py summarize --summary <folder>/gauge-census/<date>/census.summary.json`.
6. Register census.json, census.summary.json, robots.json, requests.jsonl, targets.json, controls.json and controls.requests.jsonl in the folder's manifest.json (sha256, source "LGC-2026-11-23 census", retention RECONSTRUCTABLE). The `cache/` folder holds raw public metadata responses only; keep it for a resumed run, mark it DISPOSABLE.

Post a short summary on #51 (under 15 lines):
- the `summarize` output (controls, BINDING shortlist / hand review / none, the ceiling if every shortlisted lake passes stage B against the 311 target, INDEPENDENT_TRUTH tiers and lakes with a v3-eligible candidate, TVA reservoirs with USGS candidates, outline vs point-only)
- request count, errors by stage, `budgetExhausted`, lakes discovered / targeted, and every ROBOTS_DISALLOWED host and path
- the structural cap (bound lakes that can get an INDEPENDENT_* row at all) next to the number that did
- census.json and census.summary.json sha256, and the rules sha256
- questions for Michael:
  (a) Build the batch 3 binding review (stage B, level values, same R1–R9 and checks (b)–(d) as batches 1–2) from the SHORTLIST rows now?
  (b) The HAND_REVIEW rows (point-only lakes, UNKNOWN class, missing datum): review them by hand, or leave them out of batch 3?
  (c) Hand the INDEPENDENT_AGENCY / INDEPENDENT_SITE rows to the operator-truth validation v3 so it can freeze its truth list from them under its own pre-registration?
