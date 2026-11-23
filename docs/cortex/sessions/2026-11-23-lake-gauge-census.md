# Session record: Lake gauge census, pre-registered rules and GET-only tool (2026-11-23)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with `git archive`; the loader reports "uncommitted (no-git)" for an extracted tree), pack sector/engine

## Request
Research task (caller request in this session, under Michael's pre-approval of new directions to strengthen Brains, Sector_Ops #51 comment 7093610553): raise Lake coverage honestly from 294/621 (47%) to at least 311 (50%) with gauge-grade sources (`DIRECT_LAKE_GAUGE` / `DIRECT_OPERATOR_POOL`, `lake-brain-score-v1` `sourceAuthority`), not SWOT. Write a GET-only, metadata-only census tool for unprofiled lakes (USGS 62614/62615/00062 via WaterServices or the OGC API, USACE CWMS `Elev` series, Reclamation RISE elevation items, USGS gauges at TVA reservoirs), with pool vs tailwater/river classification, cadence, latest time, datum and robots/terms; pre-register the candidate-to-binding rules (same R1–R9 and checks (b)–(d) as batches 1–2); tests on fixtures; a draft Mac mini request to run after 2026-11-30. Do not change any binding, accepted list, `LakeSourceBindingsGenerated.swift` or the knowledge release (PR #243's runner refuses if bindings change).

Mid-task addition (coordinator): the operator-truth validation v2 (#243) found only 7 lakes with independent truth; v3 will be discovery-first. The census output must also list, for every bound lake, candidate series that are not the lake's bound primary/fallback/history series, with independence evidence (different agency, different site, not a CWMS USGS copy, not an NWS redistribution). Still metadata only, still after 2026-11-30.

Branch `research/lake-gauge-census-2026-11-23` from `origin/main` `5db0679`, worktree `/home/claude/se_wt_gauge_census` (cloud container).

## Observed (repository, 2026-11-23)
| Item | Value | Evidence |
|---|---|---|
| Directory | 621 lakes | `brains/moon/runtime/knowledge/lakes-directory.json` (projection of `LakeDirectory.swift`) |
| Reviewed set | 294 (5 pilots + 289 accepted) | `customer_lake_level_eligible.json`, `approvals/lake-knowledge-2026-11-22.3.md` |
| Unprofiled | 327 (4 with a candidate binding row) | the two above, `LakeSourceBindingsGenerated.swift` (298 rows) |
| Coverage ladder | ≥ 25% → 5, ≥ 50% → 7; 311 lakes needed | `docs/brains/scoring/SCORING.md`, `lake-brain-score-v1.json` |
| Batch rules | binding-review-v1 R1–R9; dry-run checks (b)–(d); 15 ft history/live | `LAKE_BRAIN_BINDING_REVIEW_PROTOCOL.md` §3, `LAKE_BRAIN_ACCEPTED_BATCH2_2026-11-22.md`, `LAKE_BRAIN_DRYRUN_CHECK_2026-11-21.md` |
| Unbound TVA reservoirs | Fontana Lake NC, Hiwassee Lake NC | directory vs reviewed set |

## Changes
| Commit | What |
|---|---|
| 1 | Rules `LGC-2026-11-23.rules.json` + sha256 sidecar (`254752ea…9e3f`), committed before any census request was sent |
| 2 | `tools/research/lake_gauge_census.py`, 18 offline tests on a synthetic world fixture, folder README, draft Mini request, this record and the closeout |

Choices made (reversible, standing approval 6): one tool serves both purposes (BINDING for the 327, INDEPENDENT_TRUTH for every bound lake) so the hosts are visited once; the census refuses to run before 2026-12-01 in code, not only in the request; positive controls (three reviewed lakes whose bound series must be rediscovered) disable a provider whose API shape changed, instead of reporting a silent zero; point-only lakes (no outline in the Lake Registry) can only reach HAND_REVIEW because R1 cannot be evaluated; SHEF in a CWMS version is a transfer format, not an NWS origin (Hartwell's reviewed series is `Raw-SHEF_SAS`); a bound gauge with unknown coordinates (TVA, NWS) makes nearby candidates UNCERTAIN rather than independent; S9 orders operator pools first, then inside, nearer, longer record; the one data call (USGS IV, 12 h, shortlisted pools) keeps time stamps only and is never cached.

## Verification
- `python3 -m pytest -q tools/research/tests/test_lake_gauge_census.py`: 18 passed. `python3 -m pytest -q tools/research`: 110 passed, 2 failed; the 2 (`test_cleanup_removes_read_only_campaign_files_but_nothing_else`, `test_read_only_sources_folder_is_never_modified`) fail on `origin/main` in this container too (it runs as root).
- `pytest tools/architecture` 196 passed; `pytest verification` 51 passed, 3 skipped; `tools/architecture/report.py --legacy --baseline`: 0 new findings.
- `research-check --repo .`: 85 findings on the branch and on `origin/main` (unchanged); none in the new files. `data-check`: unchanged (the tool reads no Firebase path).
- `build_engineering_status.py --check`: OK.
- Offline target build on the committed files: 621 lakes, 294 reviewed, BINDING 327, INDEPENDENT_TRUTH 298; no input file changed (test).
- Security (SEC-02): no secrets or machine paths; fixtures are synthetic and labelled; the tool's hosts are allowlisted, it honours robots.txt, uses GET only and writes only to `--out`.

## Data fetched
None. The public hosts (USGS, USACE CDA, USBR RISE, the Lake Registry bucket) were refused by this session's network proxy; nothing was retried. The parsers follow the providers' documented formats and the Engine's adapters; the positive controls are the check that they match the live APIs.

## Decisions for Michael (batched)
1. Post the draft Mini request on Sector_Ops #51 after #243 has run: `docs/brains/lake-gauge-census/MINI_REQUEST_DRAFT.md`.
2. After the census: build batch 3 (stage B, level values, R1–R9 and checks (b)–(d)) from the SHORTLIST rows; decide whether HAND_REVIEW rows are reviewed by hand.
3. Hand the INDEPENDENT_AGENCY / INDEPENDENT_SITE rows to the operator-truth validation v3 for its own pre-registered freeze.
4. Two REMOVABLE_MERGED worktrees of other sessions (`se_wt_validation`, `sector_engine_wt_wtpt`) are unregistered: confirm removal (DEV-04).

## Not done (gated or out of scope)
No census run, no level value read, no binding, accepted list, knowledge release, score or rubric change, no Firebase read or write, no merge.

## Closeout
[`2026-11-23-lake-gauge-census.closeout.md`](2026-11-23-lake-gauge-census.closeout.md) (stored here because the cloud container has no research home; CG-3.1-22).

## Operating contract §19
Gap: Lake coverage (`coverage` 5 → 7 at 50%) and independent operator truth (validation v3); bowfisher decision: whether a lake's level is from the lake's own gauge or operator pool; files as above; tests as above; score before/after unchanged (no publication); field validation needed: none; not changed: live systems, schedulers, bindings, customer lists.

## Review round 1 (independent review of #247 @ 85509b1a: NOT CLEAN; fixed before any request was sent)
Rules re-registered as **LGC-2026-11-23.2** (sha256 `c17feef35f03c072cb79f4d318b465d807fc72afe5ca351f0b787cc3df382ba7`). `LGC-2026-11-23.rules.json` is kept byte for byte, marked superseded (`LGC-2026-11-23.SUPERSEDED.md`), never used, and refused by the tool. Branch merged with `origin/main` (no binding or list change came in: the reviewed set is still 294).

| Finding | Fix |
|---|---|
| HIGH date guard only on `census` | `notBefore` 2026-12-01T12:00Z; the fetcher refuses every request before it (controls, geometry, census), and `main` refuses every networked subcommand before creating anything; tests at 11:59Z and 12:00Z |
| HIGH unlabelled CWMS treated as USACE | `USACE_UNLABELLED`; any USGS/USACE pair with it is UNCERTAIN; only a reviewed `--origin-evidence` entry makes a CWMS series USACE (none exists) |
| MEDIUM rule-curve cues | guide, curve, conservation, flood, control, inflow, upper, lower, top, bottom … in version / sub-parameter / RISE title (minus the lake's own name); sub-location Upper/Lower → UNKNOWN; a future latest time → RULE_CURVE, never live |
| MEDIUM robots / redirects / retries | RFC 9309 (5xx, 3xx or no answer = disallow; 401/403 disallow; other 4xx allow); redirects never followed; every attempt logged and counted against the budget (now 12,000) |
| MEDIUM partial output | per-chunk catch in IV and bound coordinates, per-lake catch in discovery and geometry; on budget exhaustion discovery stops and the output is still written; `errorsByStage`, `budgetExhausted`, `lakesDiscovered` in the summary |
| MEDIUM structural cap | computed from the committed bindings: 130 of 298 bound lakes (129 of 294 reviewed) can get an INDEPENDENT_* row; in README, rules and `summary.structuralCap` (the reviewer's ≈112 estimate was close; the computed figure is used) |
| MEDIUM RISE bound coordinates | from the already-fetched RISE locations (item → location), one lookup for an unlisted item |
| LOW IV scope / controls / ceiling / robots / estimate | IV only for the BINDING pre-shortlist; controls require class POOL; ceiling from the live reviewed count; `ROBOTS_DISALLOWED` per host and path; request estimate 3,000–6,000 in the draft |

Verification after the fixes: census tests 37 passed; `pytest tools/research` 129 passed, 2 failed (the same 2 pre-existing root-container failures); `pytest tools/architecture` 196 passed; `pytest verification` 51 passed, 3 skipped; architecture report 0 new findings; `build_engineering_status.py --check` OK; `research-check` 85 findings (unchanged), closeout 0. No file under `brains/lake`, `jobs/lake-brain`, `jobs/brain_platform` or `Sources` differs from `origin/main`.

## Review round 2 (independent review of #247 @ 46a81bde: NOT CLEAN; round-1 fixes confirmed; fixed before any request was sent)
Rules re-registered as **LGC-2026-11-23.3** (sha256 `2a46ac96df8021c5fca08d19406f5e60eedd19e266289f9130515ecb76b5b8b1`). `LGC-2026-11-23.2.rules.json` is kept byte for byte, marked superseded (`LGC-2026-11-23.2.SUPERSEDED.md`), never used, and refused by the tool, as is the first registration. No fetch of `origin` this round.

| Finding | Fix |
|---|---|
| HIGH border covered only USGS/USACE | an unlabelled CWMS series is origin-unknown against every other agency (USGS, USBR, CDEC, TVA, states, labelled copies): UNCERTAIN unless an origin-evidence entry exists; USBR/BOR/Reclamation and CDEC/DWR labels in a CWMS version are parsed as `USBR_COPY` / `CDEC_COPY` (NOT_INDEPENDENT against a bound series of that agency, otherwise UNCERTAIN); tests in both directions (unlabelled vs RISE, RISE vs unlabelled, USGS vs unlabelled, unlabelled vs USGS, Raw-USBR vs RISE, Raw-CDEC vs USGS), plus the positive cases (RISE vs USGS far apart, evidence-resolved unlabelled vs RISE) |
| MEDIUM failed office catalog cached empty | never cached; retried for the next lake, at most 3 failures per office per run; each lake discovered while an office was down carries `CWMS_OFFICE_UNAVAILABLE:<office>` in `discoveryIncomplete`; tests for recovery and for the cap (9 requests = 3 gets × 3 attempts) |
| LOW budget-undiscovered lakes in noCandidate | BINDING counts are now `noCandidate` (complete, nothing found), `incomplete` and `notDiscovered` |
| LOW USGS future tolerance | registered text now has `futureLatestToleranceHoursDateGranular` 24 for the date-granular USGS catalog end date; the code uses it (no extra day) |
| LOW robots 429 | disallow-all, stated in the rules |
| LOW stale text | PR body no longer says 9,000; Mini draft manifest source is "LGC-2026-11-23.3 census" |
| TVA | `tva.com`, NWPS and HADS are refused by the fetcher even if a rules file listed them; `tva_robots.txt` fixture (`Disallow: /`) proves robots handling would block it too; TVA reservoirs are reached only through USGS gauges |

Verification after the fixes: census tests 53 passed; `pytest tools/research` 145 passed, 2 failed (the same 2 pre-existing root-container failures); `pytest tools/architecture` 196 passed; `pytest verification` 51 passed, 3 skipped; architecture report 0 new findings; `build_engineering_status.py --check` OK; `research-check` 85 findings (unchanged), closeout 0. No file under `brains/lake`, `jobs/lake-brain`, `jobs/brain_platform` or `Sources` differs from `origin/main`.

## Review round 3 (independent review of #247 @ c4199ae9: NOT CLEAN; fixed before any request was sent)
Rules re-registered as **LGC-2026-11-23.4** (sha256 `64ca297f43331893dd70a15edcc5a84fd76721c434c042cc67c381b616f41494`), committed alone (`c1a73f70`) before the code changes. `LGC-2026-11-23.3.rules.json` is kept byte for byte and marked superseded (`LGC-2026-11-23.3.SUPERSEDED.md`); the tool refuses `.3`, `.2` and the first registration (tested). No fetch of `origin` this round.

| Finding | Fix |
|---|---|
| HIGH unlabelled-vs-unlabelled ≥ 1 km → INDEPENDENT_SITE | any pair with `USACE_UNLABELLED` on either side is UNCERTAIN without reviewed origin evidence; CWMS series compared by `cwms_parts().baseLocation` (same base, any sub-location / version / interval → NOT_INDEPENDENT); derived versions (Best, Rev, Comp, Calc, CCP) NOT_INDEPENDENT at the same base, UNCERTAIN otherwise, both directions. Kinzua probe on the committed Allegheny binding: `Kinzua-Lake…RESOPS`, `Kinzua-Tailwater…`, `Kinzua.Elev-Pool…Best-LRP` → NOT_INDEPENDENT; USGS vs the unlabelled bound OBS/RESOPS → UNCERTAIN |
| MEDIUM discovery failures counted as no candidate | every failure marks the lake incomplete: `PROVIDER_FAILED`, `PROVIDER_DISABLED`, `USGS_TSMETA_UNAVAILABLE`, `CWMS_TS_UNAVAILABLE`, `RISE_CATALOG_UNAVAILABLE` / `_PARTIAL`, `RISE_DETAIL_UNAVAILABLE`, `RISE_ITEM_UNAVAILABLE`; a failed or partial RISE listing is never cached (retried, max 3); `incompleteCodesAllLakes` in the summary; a test per code |
| LOW oversize box / pagination caps | `USGS_BOX_TOO_LARGE`; `CWMS_LOCATIONS_TRUNCATED`, `CWMS_TS_TRUNCATED`, `RISE_CATALOG_TRUNCATED` when a cap is reached with pages left (caps are module constants, tested at small values) |
| LOW RISE origin | `USBR` only when the item's own metadata names Reclamation, else `RISE_UNCONFIRMED`: UNCERTAIN against USGS in either direction; bound RISE items use the collector the census read; origin evidence may name USBR for a RISE item |
| Docs | README, Mini draft (rules id, hash, manifest source, incompleteness codes), closeout, PR body |

Verification after the fixes: census tests 73 passed (including the OGC path in the synthetic world); `pytest tools/research` 165 passed, 2 failed (the same 2 pre-existing root-container failures); `pytest tools/architecture` 196 passed; `pytest verification` 51 passed, 3 skipped; architecture report 0 new findings; `build_engineering_status.py --check` OK; `research-check` 85 findings (unchanged), closeout 0; every rules sidecar verifies. No file under `brains/lake`, `jobs/lake-brain`, `jobs/brain_platform` or `Sources` differs from `origin/main`.
