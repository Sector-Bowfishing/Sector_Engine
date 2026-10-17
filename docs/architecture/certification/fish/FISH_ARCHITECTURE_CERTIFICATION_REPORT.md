# Fish Brain — Architecture Certification Report V1

**Brain:** Fish Brain (`biological-state`) — Brain #2. **Phase:** Fish Structural Certification V1. **Branch:** `cert/fish-brain-architecture-v1`. **Base:** `origin/main` `3aa39d58cf1438b6665311dd5c8f176e64c2b3e7`.
**Status: `FISH_BRAIN_ARCHITECTURE_V1_READY_FOR_REVIEW`** — structure only. Fish is **not** Production-ready, **not** scientifically validated, research is **not** complete. Lifecycle stays `PROFILED`; science stays `NOT_VALIDATED`; Publisher cutover stays `SHADOW`. Nothing was deployed, published, scheduled or promoted.

## 1. Certification matrix
Legend: PASS · FAIL · NOT_APPLICABLE · BLOCKED. "T:" = test in `brains/fish/tests/test_fish_certification.py` unless stated.

| # | Dimension | Result | Evidence |
|---|---|---|---|
| 1 | Canonical ownership is clear | **PASS** | `BRAIN_OPERATING_CONTRACT.md` §4–§5 (owns / does not own: species identity, legality, presence, other Brains' state); T: `test_ownership_boundaries_in_the_declared_contract` |
| 2 | Canonical code location is clear | **PASS** | `brains/fish/` (repo convention: `brains/README.md`, `stable_brain_ids.json` `fish → biological-state`); T: `test_canonical_package_location_and_shape`, `test_exactly_one_production_fish_implementation` (one copy of each Fish module in the whole tree; `jobs/biological-brain` = pointer README); history kept by `git mv` (+ real merge of the adoption branch) |
| 3 | Research/runtime separation is clear | **PASS** | T: `test_research_is_separate_from_the_production_package`, `test_no_local_mac_research_or_cache_paths_in_fish_runtime`, `test_runtime_works_with_no_research_workspace_no_home_and_no_repo_docs` (runs the staged-image layout with an empty HOME, no `docs/`, no workspace); workspace `Sector Research/fish-brain` created structure-only |
| 4 | Inputs are declared | **PASS** | `brain.json`: `consumes: []`, `providers: []`, no signals; own knowledge release documented (§6) and carried as lineage; T: `test_declared_dependencies_validate…`, `test_no_fabricated_signal_declarations`; architecture inv 17 PASS |
| 5 | Outputs are contracted | **PASS** | `fish-publication-v1` (`contracts/fish-publication-v1.json`, derived from the Publisher registry, `--check` in CI-able form); `FISH_PUBLISH_ARTIFACT_V1.md`; T: artifact/Publisher tests |
| 6 | Dependency ownership is clear | **PASS** | Brain-owned `brain.json` only; platform manifest edges for Fish removed (drift gate); T: `DD.drift == []`; invented edges found and retired (audit B3) |
| 7 | Actual consumption lineage is supported | **PASS** (with documented limits) | recorder on `BrainRtdb` in `run.py` (PR #22) and now `run_state.py`; `consumed` threaded into the artifact (`[]` recorded / absent unknown); T: `test_actual_consumption_capture_…`, `test_pilot_runner_records_what_it_reads`, `test_offline_artifact_carries_no_consumed_key…`, `test_health…consumedNotDeclared`. Limits §5 |
| 8 | healthV1 integration is supported | **PASS** | zero Fish-specific health code; orchestrator health-plane tests now run against a registered Fish (`brain.json` source, 0 declared); T: `test_health_v1_can_represent_fish…` |
| 9 | Publisher contract is supported | **PASS (shadow)** | T: acceptance `SHADOW_READY`, idempotent `SKIP`, end-to-end API handoff, wrong brain/schema/path/release/lifecycle rejections (11 path cases); `PublisherMode` has no live member |
| 10 | Direct-write ownership is correct | **PASS** | `FISH_DIRECT_WRITE_AUDIT.md`: one LEGACY site (`run.py --write`, ownership-checked, retirement-gated), no REST/Admin/other writers, no BLOCKER; T: AST audit pins the exact set |
| 11 | Lifecycle is explicit | **PASS** | `PROFILED` in `brain.json`, artifact lineage and platform manifest; `cutoverStatus SHADOW`; production lifecycles refused by the Publisher without `approvalRef` (T) |
| 12 | Score contract is understood | **PASS** | `FISH_SCORE_RECONCILIATION.md`: BEFORE 4.0 = AFTER 4.0, rubric hash unchanged, mixing documented, not redesigned |
| 13 | Tests / gates are comprehensive | **PASS** | §3 (all 28 required proofs mapped); suites green; no NEW architecture violations |
| 14 | No Wind-specific platform assumptions were required | **PASS** | `FISH_REUSABILITY_REPORT.md`: Publisher / lineage / health / registry frameworks unchanged except one precision fix |
| 15 | No Fish-specific platform hacks were required | **PASS with 3 transitional Fish-specific shims, none in a framework** | reuse report "Fish-specific hacks" (orchestrator executor dir helper, image-staging line, runtime platform resolver) |
| 16 | Research can proceed independently without changing architecture | **PASS** | §4 |
| — | Live score node re-read | **BLOCKED** | production read declined by the session's permission policy; score evidence is by construction + equivalence (see score doc). Last verified live value 4.0 |
| — | Run against the real private bundle | **NOT_RUN** | no complete local release exists (the staged local copy lacks its `releases/` layout); the live bucket was not read (cost/permission rules). Synthetic + golden evidence only |
| — | GitHub Actions on the PR | see PR | filled in after the draft PR's checks complete |
| — | Per-lake Biological State, Species Intelligence Profile publication | **NOT_APPLICABLE** | not products; no registration, by design |
| — | Cloud Run deploy artifacts / provider registration / signal registration | **NOT_APPLICABLE** | Fish is in-process, has no providers or signals |

## 2. Declared vs. actual (the audit's central finding)
Before: the platform's own execution manifest claimed four provisional OPTIONAL Brain edges (`wind`, `water-temp`, `water-clarity`, `lake-brain`) for Fish that **no orchestrated execution reads**; the health plane rendered them as four UNKNOWN rows. After: Fish declares what it consumes (nothing from other Brains), and anything it ever reads undeclared appears as `consumedNotDeclared`. The Biological State pilot's real inputs are *not* declared because that component is not part of any execution; the decision to graduate it (and declare its inputs, with instrumentation already present in `run_state.py`) is Research Gap `FISH-PRD-001` / decision D-1.

## 3. The 28 required proofs → tests
1 location · 2 single implementation · 3 brain.json · 4 brainId · 5 ownership · 6 declared deps · 7 no fake signals · 8 schema/Publisher validity · 9 determinism · 10 fingerprint stability · 11 executionId/timestamps don't change it · 12 lineage · 13 consumption capture · 14 missing stays missing · 15 healthV1 · 16 UNKNOWN honesty · 17 no `lastSuccessfulRun`→freshness · 18 Publisher accepts (shadow) · 19 rejects wrong brain/path · 20 no unauthorized writes · 21 no local paths · 22 no workspace dependency · 23 research separate · 24 science preserved (golden from the pre-move tree, 2 bundles × {updates, species, registry, validation, health, plan, descriptor, profiles, coverage}) · 25 species identity passthrough · 26 registered-Brain gates (no NEW, nothing RESOLVED away) · 27 global platform tests green · 28 Wind green/unchanged — all in `test_fish_certification.py` (44) + `jobs/brain_platform/tests/test_publisher_fish_registration.py` (3) except 27–28 which are suite results:

| Suite | Result |
|---|---|
| `brains/fish` (adoption suite 241 + certification 44) | 285 passed, 2 skipped (skips pre-existing, identical to before the move) |
| `jobs/brain_platform` | 524 passed (521 + 3 new) |
| `jobs/brain-orchestrator` | 36 passed |
| `jobs/brain-scores` | 21 passed |
| `jobs/sector-intelligence-brain` / `water-clarity-brain` / `lake-surface-dispatch` / `water-temp-tva-archive` | 33 / 35 / 11 / 14 passed |
| `tools/architecture` + `verification` | 101 passed; `score_baseline.py --check` OK |
| `brains/wind/tests` | 81 passed (16 network tests deselected as designed); `wind-publication-v1.json` still matches the registry; no Wind file changed |
| Architecture baseline (`report.py --legacy --baseline`) | KNOWN 21 · **NEW 0** · RESOLVED 0 (two Fish `docs/` published-label entries carried to the new path with `carriedFrom`; same retirement condition as Wind's two) |

## 4. Can research proceed without redesigning Fish? (criterion 16)
Yes. A Fish Research session changes only: workspace content; the private bundle (species, rules, bands, cards, profiles) and its release (`researchVersion`, manifest hash); `research/GAPS.json` status. All of that flows through the unchanged runtime: new species → new `/species/{id}` mutations, retired → typed DELETE, new rules/bands → inside existing summary shape (and the Species Intelligence Profile generator). The following would be *structural* (reviewed Publisher/contract changes, not research): a new registry child, a new path family, publishing the Species Intelligence Profile (`/speciesProfiles` decision), graduating the Biological State (new declared dependencies + a new schema), REVIEWED/VALIDATED maturities (the runtime refuses them until a separate promotion decision). Each of these fails closed with a named error rather than silently.

## 5. Remaining gaps (none blocks this certification)
**PLATFORM:** (P1) orchestrator executes Brains by directory path (shims above); (P2) no VERSION-basis freshness statement ⇒ Fish evidence freshness stays UNKNOWN; (P3) single mixed score (`feat/biological-score-v2` is the isolated proposal); (P4) Species Registry has no data, so species identity still ships in the Fish bundle (G-1); (P5) published-label `docs/` strings in two Fish files are baselined, not removed (changing them changes published output; needs approval).
**FISH STRUCTURE:** (F1) `--write` LEGACY door remains until the Publisher cutover (not started, not approved); (F2) `docs/brains/biological-adoption/` not moved under the package (doc churn, no structural value); (F3) the Species Intelligence Profile family is unregistered by design.
**SCIENCE (deferred, Research Gaps):** `FISH-VAL-001` (no field validation), `FISH-EVI-001` (no species reviewed), `FISH-PRD-001` (per-lake state is a pilot; Depth/Vegetation inputs unpublished).
**HUMAN/DECISION:** D-1 pilot graduation + input declarations; D-2 approve (or reject) the history-preserving merge of the adoption branch as the Fish baseline (Decision A in the audit); D-3 Publisher cutover for Fish (later); D-4 adopt legacy research (`Sector_Research_Data/biological-brain`, 13 MB) into the workspace.

## 6. Non-actions confirmed
No production promotion; no customer-visible change (no `/conditions`, iOS, Sector Intelligence recommendation touched); Publisher production writes not enabled (no live mode exists); no deploy; no scheduler or always-on service; no provider polling; no research; no Ops change; no force-push or branch deletion; historical Fish branches and worktrees untouched.
