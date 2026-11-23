Claude request (under Owner approval 2026-11-22): Lake gauge census LGC-2026-11-23.5 (read-only, metadata only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

**When:** on or after 2026-12-01T12:00Z, and only after the Lake operator-truth validation (PR #243, 2026-11-24..30) has finished and posted its result on #51. The tool refuses any request before 2026-12-01T12:00Z. Do not run it in parallel with any other Lake job.

**Do not change** bindings, `accepted_batch*.json`, `LakeSourceBindingsGenerated.swift`, the Lake knowledge release, `customer_lake_level_eligible.json`, any score, RTDB, buckets, Pulse jobs or schedules. Do not create cloud jobs. Do not read or judge any level value (stage B is a separate request). Start in the Lake research folder that Cortex `research-path sector/engine lake-brain` returns, write outputs only there, and end with a research closeout.

Use the Engine checkout at the merged commit of Sector_Engine PR #247 (or its branch `research/lake-gauge-census-2026-11-23` if it has not merged). Rules: `docs/brains/lake-gauge-census/LGC-2026-11-23.5.rules.json`, sha256 befcc41dece500688e4c6062372c54e4907aa288d4cad44c38a2ce0b131e23de (supersedes the never-used LGC-2026-11-23.4, .3, .2 and the first registration). Tool: `tools/research/lake_gauge_census.py`.

`<folder>` below is the Lake research folder from `research-path`. The run binding (the hash-chained ledger, the cache and every output) lives in `<folder>/gauge-census/binding/LGC-2026-11-23.5/`; the tool picks the output folders itself. Only census run #1 counts, and the tool refuses a second one. The lake set, registry and USGS API are fixed by the rules: do not pass `--lakes`, `--registry`, `--usgs-api` or `--origin-evidence` (no origin evidence is registered).

1. `python3 tools/research/lake_gauge_census.py verify` must print the sha256 above. Stop if it does not.
2. `python3 tools/research/lake_gauge_census.py lakes --out <folder>/gauge-census/targets` (offline; 621 lakes; on 2026-11-23 the reviewed set was 294 and BINDING 327, report the numbers it prints).
3. `python3 tools/research/lake_gauge_census.py controls --research-folder <folder>`. Exit 3 means a provider's positive control was not rediscovered (an API shape change): report which control failed and the HTTP statuses in `controls-run-1/requests.jsonl`, and stop unless USGS and CWMS both passed. Exit 2 is a refusal: report its reason and the last ledger lines, and stop.
4. `python3 tools/research/lake_gauge_census.py census --research-folder <folder>`. GET only. Estimate: USGS about 650 requests (one site query per lake, a few IV and site chunks), CWMS about 1,500–4,000 (38 office location catalogs, then one time-series catalog per location inside a lake box), RISE about 300–800 (the location listing, then items near lakes), plus retries; about 3,000–6,000 requests, roughly 1–2 h at 1 s per host. Every retry counts; the budget stops it at 12,000 and the output is still written, with `budgetExhausted: true`. Outputs: `<folder>/gauge-census/binding/LGC-2026-11-23.5/census-run-1/`.
   - If it stops before writing any output (the ledger's END line says ABORTED_NO_RESULT), run the same command once more with `--skip-controls`. That is accepted only because the aborted attempt logged passing controls.
   - If the END line says FAILED, or any other refusal appears, do not retry: report it.
5. `python3 tools/research/lake_gauge_census.py summarize --summary <folder>/gauge-census/binding/LGC-2026-11-23.5/census-run-1/census.summary.json`.
6. Register `targets.json`, the `controls-run-1/` and `census-run-1/` files and `ledger.jsonl` in the folder's manifest.json (sha256, source "LGC-2026-11-23.5 census", retention RECONSTRUCTABLE; the ledger is the run record, keep it). The `cache/` folder holds raw public metadata responses only: mark it DISPOSABLE (its tree hash is in the ledger).

Post a short summary on #51 (under 15 lines):
- the `summarize` output (controls, BINDING shortlist / hand review / none, the ceiling if every shortlisted lake passes stage B against the 311 target, INDEPENDENT_TRUTH tiers and lakes with a v3-eligible candidate, TVA reservoirs with USGS candidates, outline vs point-only)
- request count, errors by stage, `budgetExhausted`, lakes discovered / targeted, BINDING `incomplete` (with the incompleteness codes and their counts, e.g. CWMS_OFFICE_UNAVAILABLE, RISE_CATALOG_*, PROVIDER_DISABLED) and `notDiscovered` kept apart from `noCandidate`, and every ROBOTS_DISALLOWED host and path
- the structural cap (bound lakes that can get an INDEPENDENT_* row at all) next to the number that did
- census.json and census.summary.json sha256, the rules sha256, the run number (must be 1) and the ledger END line hash
- questions for Michael:
  (a) Build the batch 3 binding review (stage B, level values, same R1–R9 and checks (b)–(d) as batches 1–2) from the SHORTLIST rows now?
  (b) The HAND_REVIEW rows (point-only lakes, UNKNOWN class, missing datum): review them by hand, or leave them out of batch 3?
  (c) Hand the INDEPENDENT_AGENCY / INDEPENDENT_SITE rows to the operator-truth validation v3 so it can freeze its truth list from them under its own pre-registration?
