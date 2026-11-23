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
