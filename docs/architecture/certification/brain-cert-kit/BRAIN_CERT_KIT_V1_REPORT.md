# BRAIN_CERT_KIT_V1 — extraction report (D-7b)

**Date:** 2026-10-18 · **Base:** `origin/main` `0335d22810b2d3a068bb7bed26f170a41913692a` · **Branch:** `platform/brain-cert-kit-v1` · **Status: `BRAIN_CERT_KIT_V1_READY_FOR_REVIEW`** (draft PR; not merged).
Platform/test extraction only. Runtime Brain code, platform code, contracts, providers, Swift and `tools/architecture` are byte-identical to main (`git diff origin/main -- 'brains/*/runtime' jobs platform contracts providers Sources tools/architecture` is empty). Wind, Fish and Water Clarity remain `STRUCTURALLY_CERTIFIED_V1`; lifecycles, Publisher states and scores are untouched.

## 1. Before / after
| Measure | Before (main) | After |
|---|---|---|
| Brain-local implementations of the generic proofs | Fish 17 + Clarity 21 + Wind 3 (+ ad-hoc) = **41** test functions, two near-identical full copies | **0** (one implementation, `brain_cert_kit.proofs`) |
| `describe_contract.py` | 3 files, 179 lines, one skeleton | 1 shared descriptor (103 lines) + 3 declarations (34 / 34 / 38 lines); output **byte-identical** |
| Local certification test lines | Fish 518, Clarity 677, Wind package 185 = 1,380 | Fish 313, Clarity 436, Wind package 153 = 902, plus 3 specs (50 / 51 / 63) and three 6–7-line suite files |
| Cost of Brain #4's structural suite | copy ~ 700 lines + a describe script | a ~50-line spec + 6-line test file + ~35-line describe wrapper |
| Coverage Wind has of the 19 proofs | 3 (identity, contract, single impl) + Gate-P artifact tests | all 19 (+ ~30 mutation tests); closes **D-8** (no AST write-site pin) |
Total repository test lines did not shrink (the kit adds its own 1,213 lines incl. self-tests and mutations); the saving is the fourth and later copies, and that every future change to a proof is made once.

## 2. Coverage of every removed assertion (nothing weakened)
| Removed test(s) | Now covered by | Equal or stronger because |
|---|---|---|
| Clarity/Fish `…canonical_package_location…`, `…exactly_one…`, Wind single-impl (kept) | P01, P02 | same checks + mutation tests prove they can fail |
| `…brain_json_validates…` (all three), Wind `test_brain_json_valid…` | P03 (+ local slot/display-name test) | adds brain.json-has-no-local-path, control-manifest lifecycle, artifact-lineage lifecycle, consumers, runtime kind, platform-claims-⊆-declared |
| `…ownership_boundaries…` (Clarity), Wind `test_operating_contract…` | P04 | exact 19-heading list for all (Fish/Clarity only counted) + required/forbidden terms |
| Clarity `…published_contract_derived…`, Wind `test_published_contract…` | P05 | exact family equality for all (Fish/Clarity normalised before) + sections == registered bundle + SHADOW status |
| Fish `…declared_dependencies…`, `…no_fabricated_signal…` | P06 | adds exact consumes/providers equality, provider-registration, owned-but-undeclared providers, signal-id leakage for every Brain |
| `…artifact_is_publisher_valid…` | P07 | + fingerprint-tamper and non-determinism mutations |
| `…semantic_fingerprint…` (kept locally: moved-field lists), `…real_domain_change…` | P08 (+ local domain remainder) | same SKIP / change checks; domain-specific moved fields stay local |
| `…lineage…`, `…review_and_validation…` | P09 | + release-triple rules, `[]`-only-when-recorded, optimistic-status mutation |
| three health tests | P10 | adds registered-Brain discoverability and declared-count == brain.json |
| `…shadow_only_and_end_to_end…` | P11 (+ local snapshot-plan check) | same API handoff, plan roots from spec |
| the parametrised path-rejection tests | P12 | same cases (generic + spec extras) plus **section-crossing** and **foreign-writer** cases for every Brain, and a path-ownership-code assertion |
| wrong brain/schema, requires release/freshness, production lifecycle | P12 | derived from the registry (no per-Brain flag) |
| `…no_unauthorized_production_write…` | P14 | now pins (file, function, call), not just file |
| `…artifact_path_cannot_write…` | P15 | same import/token bans, from spec |
| `…no_local_mac_research…` | P16 | same, with documented exemptions as data |
| `…research_is_separate…` | P17 (+ local exact-listing / domain json checks) | same + data budget for all |
| `…registered_brain_architecture_gates…` | P18 | same; carried baseline entries from spec |
| typed delete generic part | P13 | + closed-vocabulary check on every DELETE and no-delete-family rejection |
Kept locally on purpose (domain / deploy-model specific): science goldens and equivalence, species identity, input-truth AST pin, domain freshness, write-set classification, engine-miss path, consumption capture, staged-layout runs, private-marker scans, Wind Gate-P and package/staging gates.

## 3. Regression comparison (same commands before/after; interpreter `python3.12`)
| Suite | Before | After | Note |
|---|---|---|---|
| `brains/wind` | 110 passed | 161 passed | +51 kit tests |
| `brains/fish` | 285 passed, 2 skipped | 311 passed, 2 skipped | 17 removed, 2 domain tests added, 51 kit tests added |
| `brains/water-clarity` | 87 passed | 114 passed | 21 removed, 4 domain added, 52 kit |
| `tools/brain_certification` (new) | — | 19 passed | kit self-tests |
| `jobs/brain_platform` / orchestrator / scores | 524 / 36 / 21 | 524 / 36 / 21 | identical |
| Sector Intelligence | 33 | 33 | identical |
| `tools/architecture` | 84 | 84 | identical |
| `verification` (incl. Wind package gates) | 17 (9) | 14 (6) | the 3 removed Wind package tests are now P03/P04/P05 |
| lake-surface-dispatch / tva / lake-brain (bindings, ledger, validation, review) | 11 / 14 / 13 / 23 / 70 / 24 | identical | |
| architecture baseline | KNOWN 20 / NEW 0 / RESOLVED 0 | KNOWN 20 / NEW 0 / RESOLVED 0 | baseline untouched |
| score baseline | wind 3.3, water-clarity 8.0, water-temp 3.0 | identical | |
| contract JSON sha256 | wind 8d963328…, fish f058562a…, clarity 4e530cd7… | identical | descriptor output byte-identical |
| **Artifacts** (independent before/after build on untouched main vs this branch) | Fish `47142775…` / `ddf0fca2…`, Wind `f8b97483…`, Clarity golden `b1366a3c…` and normalised write set `5ac7801c…` | identical | `art_hash.py`/`clar_hash.py`; Clarity's real run reads the clock, so it was compared by the deterministic golden and a timestamp-normalised write set (4 runs, 2 trees, all equal) |
Correction to an earlier statement: Wind's "2 environmental failures" in the Water Clarity session were my mixed interpreters (a 3.12/3.14 venv); with the right interpreter Wind is fully green on untouched main (110 passed) — this is demonstrated, not asserted.

## 4. Mutation audit
For every Brain, ~30 mutations (lifecycle, cutover status, workspace, consumers, undeclared consume/provider, wrong bundle, missing file/module/contract statement, unaudited/removed/unrecognised write site, builder I/O import or token, runtime path leak, runtime data file, architecture finding not carried, unexpected baseline entry, undeclared plan root, wrong rejection code, tampered fingerprint, non-deterministic artifact, execution-dependent fingerprint, optimistic validation, invented release, `consumed` emitted when unknown, DELETE outside the closed vocabulary, an artifact that writes a score, score-baseline mismatch, unregistered Brain for health) — **all detected on all three Brains**; a completeness test fails if a proof lacks a mutation.

## 5. Hygiene and safety
The kit contains no Brain name, domain term, per-Brain conditional, private path or bucket (guard tests). No private research, local path, ZIP, PDF set or bucket content was added. No Brain #4 / Lake Brain file was created or touched. Nothing deployed; no scheduler, RTDB, `sector-brain`, Publisher, Orchestrator, customer or Ops change.

## 6. Platform debts discovered / changed
- **D-7b:** resolved by this PR once merged (the factory docs now point to the kit).
- **D-8** (Wind had no AST-pinned write-site test): closed by P14 for Wind.
- **D-9** (no generic lifecycle drift gate): P03 now checks brain.json == control manifest == artifact lineage for every adopting Brain (still a per-Brain test, not a repository-wide gate; Brain #4 must adopt the kit).
- **New, small:** the staged-layout / clean-room run still has three Brain-specific forms (Wind clean copy, Fish orchestrator layout, Clarity `--stage-only`); a V2 could parameterise them if Brain #4 reuses one. The Wind clean-copy production gate must exclude the kit module (needs the whole repository). The `BrainCertSpec` is Python, not JSON; a `brain.cert.json` could replace it later.
- **Unchanged:** D-7 (registration hand edits), D-11 (Wind-named legacy table), RA-20, GCS lineage/write semantics, Publisher cutover.
