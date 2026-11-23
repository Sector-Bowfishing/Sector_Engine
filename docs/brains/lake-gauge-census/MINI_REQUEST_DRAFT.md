Claude request (under Owner approval 2026-11-22): Lake gauge census LGC-2026-11-23.6 (read-only, metadata only)

DRAFT. Not posted. Michael posts it on Sector_Ops #51 if he agrees.

**When:** on or after 2026-12-01T12:00Z, and only after the Lake operator-truth validation (PR #243, 2026-11-24..30) has finished and posted its result on #51. The tool refuses any request before 2026-12-01T12:00Z. Do not run it in parallel with any other Lake job.

**Do not change** bindings, `accepted_batch*.json`, `LakeSourceBindingsGenerated.swift`, the Lake knowledge release, `customer_lake_level_eligible.json`, any score, RTDB, buckets, Pulse jobs or schedules. Do not create cloud jobs. Do not read or judge any level value (stage B is a separate request). Start in the Lake research folder that Cortex `research-path sector/engine lake-brain` returns, write outputs only there, and end with a research closeout.

Use the Engine checkout at the merged commit of Sector_Engine PR #247 (or its branch `research/lake-gauge-census-2026-11-23` if it has not merged); it includes the shared run ledger from #251. Rules: `docs/brains/lake-gauge-census/LGC-2026-11-23.6.rules.json`, sha256 5c04e3197f5ae6f4cdbc24ece6101bc8fe26ee1798b41963083da56b7bd85524 (supersedes the never-used LGC-2026-11-23.5, .4, .3, .2 and the first registration). Tool: `tools/research/lake_gauge_census.py`.

The run is bound to the shared run ledger at the folder Cortex `research-path sector/engine lake-brain` returns (`CORTEX_HOME` must be set; `SECTOR_RESEARCH_ROOT`, if set, must be the same folder). The ledger is `<root>/_ledgers/LGC-2026-11-23.6.jsonl`, and the outputs are `<root>/gauge-census/LGC-2026-11-23.6/`. The tool picks every folder. Only census run #1 counts. The lake set, registry and USGS API are fixed by the rules: do not pass `--lakes`, `--registry`, `--usgs-api` or `--origin-evidence` (no origin evidence is bound).

**#51 records.** This session posts three comments on Sector_Ops #51 as research records under standing item 7: the run anchor, the run start and the run result. Each one starts with its `Run …:` line exactly as the tool prints it. Never put an "Owner approval" or "Owner request" header on them, and never edit or delete them. A mistake gets a new comment and goes to Michael for review. When the tool says a record is "not listed yet", wait; it retries by itself. Never post the same record twice.

1. `python3 tools/research/lake_gauge_census.py verify` must print the sha256 above. Stop if it does not.
2. `python3 tools/research/lake_gauge_census.py lakes --out <root>/gauge-census/targets` (offline; 621 lakes; on 2026-11-23 the reviewed set was 294 and BINDING 327, report the numbers it prints).
3. `python3 tools/research/lake_gauge_census.py anchor`. It opens the ledger and prints the `Run anchor: LGC-2026-11-23.6 <anchor> census <rules sha256>` text (also saved under `<root>/gauge-census/LGC-2026-11-23.6/records/run-anchor.txt`). Post that text unchanged on #51 before anything else. No step runs until this anchor is the earliest one for the rules id.
4. `python3 tools/research/lake_gauge_census.py controls`. Exit 3 means a provider's positive control was not rediscovered (an API shape change): report which control failed and the HTTP statuses in `controls-run-1/requests.jsonl`, and stop unless USGS and CWMS both passed. Exit 2 is a refusal: report its reason and stop.
5. Start `python3 tools/research/lake_gauge_census.py census` and leave it running. It begins the run, prints the `Run start:` text (also in `census-run-1-records/run-start.txt`) and waits. Post that text unchanged on #51. The census goes on only once the comment is listed.
   - GET only. Estimate: USGS about 650 requests (one site query per lake, a few IV and site chunks), CWMS about 1,500–4,000 (38 office location catalogs, then one time-series catalog per location inside a lake box), RISE about 300–800 (the location listing, then items near lakes), plus retries. That is about 3,000–6,000 requests, roughly 1–2 h at 1 s per host. Every retry counts; the budget stops the run at 12,000, and the output is still written with `budgetExhausted: true`.
   - Outputs: `<root>/gauge-census/LGC-2026-11-23.6/census-run-1/`.
   - If it stops with an error or is interrupted after it began, do not run it again: a started attempt with no end is terminal under this rules id. Report the error, the last ledger entries and `audit` output to Michael. Recovery is a new rules id with revised rules that record his review.
6. When the census finishes, it prints the `Run result:` text (also in `census-run-1-records/run-result.txt`). Post it unchanged on #51, then run `python3 tools/research/lake_gauge_census.py confirm-result` (it waits until the comment is listed).
7. `python3 tools/research/lake_gauge_census.py audit`: the findings list must be empty. Then `python3 tools/research/lake_gauge_census.py summarize --summary <root>/gauge-census/LGC-2026-11-23.6/census-run-1/census.summary.json`.
8. Register `targets.json`, the `controls-run-1/`, `census-run-1/` and `*-records/` files and `_ledgers/LGC-2026-11-23.6.jsonl` (plus its head file) in the folder's manifest.json: sha256, source "LGC-2026-11-23.6 census", retention RECONSTRUCTABLE. The ledger is the run record; keep it. The `cache/` folder holds raw public metadata responses only; mark it DISPOSABLE (its tree hash is in the ledger).

Post a short summary on #51 (under 15 lines):
- the `summarize` output (controls, BINDING shortlist / hand review / none, the ceiling if every shortlisted lake passes stage B against the 311 target, INDEPENDENT_TRUTH tiers and lakes with a v3-eligible candidate, TVA reservoirs with USGS candidates, outline vs point-only)
- request count, errors by stage, `budgetExhausted`, lakes discovered / targeted, BINDING `incomplete` (with the incompleteness codes and their counts, e.g. CWMS_OFFICE_UNAVAILABLE, RISE_CATALOG_*, PROVIDER_DISABLED) and `notDiscovered` kept apart from `noCandidate`, and every ROBOTS_DISALLOWED host and path
- the structural cap (bound lakes that can get an INDEPENDENT_* row at all) next to the number that did
- census.json and census.summary.json sha256, the rules sha256, the run number (must be 1), `counted: true`, and the links to the three Run anchor / start / result comments
- questions for Michael:
  (a) Build the batch 3 binding review (stage B, level values, same R1–R9 and checks (b)–(d) as batches 1–2) from the SHORTLIST rows now?
  (b) The HAND_REVIEW rows (point-only lakes, UNKNOWN class, missing datum): review them by hand, or leave them out of batch 3?
  (c) Hand the INDEPENDENT_AGENCY / INDEPENDENT_SITE rows to the operator-truth validation v3 so it can freeze its truth list from them under its own pre-registration?
