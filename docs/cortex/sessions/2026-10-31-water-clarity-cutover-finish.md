# Water Clarity cutover finish (code only): Session Record

```text
Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (clean), pack sector/engine. Repository pin d5c8380 is the merge commit of 3ac7e81 (identical tree, `git diff 3ac7e81 d5c8380` empty).
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/water-clarity-cutover-finish-2026-10-31 · Start commit: ca669772 (origin/main) · Date: 2026-10-31
```

## 1. Scope
- **Request and mode:** overnight run (Sector_Ops issue 24, step 1; roadmap §1). Guided implementation, code only: rework the test harness that blocked removing the legacy write sites, remove those write sites from `run.py`, and prepare the `cutoverStatus: CUTOVER_COMPLETE` / X14 change. No merge, deploy, cloud run, database read or write, IAM change or schedule change.
- **Inspected:** `brains/water-clarity/` (runtime, tests, brain.json, contract docs), `tools/brain_certification/brain_cert_kit/` (exit gate, P14, mutations), `docs/architecture/production/` cutover documents, the 2026-10-29 pilot final report.
- **Scope expansion:** Kit V1 `mutations.py` (two P14 mutations cannot fail for a Brain with zero write sites) and `tools/brain_certification/tests/test_exit_gate.py` (it pinned Water Clarity's write sites as still present).
- **Not inspected:** production state (no credentials used; not needed).

## 2. Findings
| ID | Finding | Status before | Evidence |
|---|---|---|---|
| WC-1 | The blocker: every Water Clarity write-set test drove the REAL `run.main` through `--legacy-direct-write` and read the PATCH bodies from a fake RTDB transport, so the direct writer could not be removed without losing the write-set proofs | FAIL | `tests/clarity_support.py:57` (old `real_run_updates`), `tests/test_water_clarity_brain.py:417` |
| WC-2 | Two RTDB write sites in `run.py`: `write()` and the abort-path health write | FAIL (X14) | `exit_gate.legacy_write_sites` → `[('run.py','main','rtdb.update'), ('run.py','write','rtdb.update')]` |
| WC-3 | Whole-node keys `/brains/water-clarity` (read and emitted) and `/health/brains/water-clarity` (emitted) in `run.py`, plus the expansion literal in `publish_artifact._expand` | FAIL (X14) | same call → `wholeNodeKeys: [run.py:225, run.py:340, publish_artifact.py:228]` |
| WC-4 | Kit mutations `write_site_not_in_audit` and `write_primitive_unrecognised` cannot fail when `allowed_write_sites` is empty, so a retired writer makes the Kit's own suite fail | FAIL after WC-2 | mutation tests "DID NOT RAISE" |

## 3. Plan and changes made
| Correction | Class | Finding | Files |
|---|---|---|---|
| Harness drives `run.main` in CENTRAL mode (in-memory object store) and captures the payload at `publish_artifact.build_artifact`; keys normalised to the RTDB PATCH form | safe (test improvement) | WC-1 | `tests/clarity_support.py`, `tests/test_water_clarity_brain.py` (EndToEnd) |
| Remove `--legacy-direct-write`, both `rtdb.update` sites and the abort-path health write; `write()` becomes `collect()` | requested by the owner (issue 24); code only, not deployed | WC-2 | `runtime/run.py` |
| Read `brains/water-clarity/{version,lastSuccessfulRun}` instead of the whole node; emit `/brains/water-clarity/{child}` and `/health/brains/water-clarity/{child}` | safe (outputs proven identical) | WC-3 | `runtime/run.py` |
| Builder refuses a whole-node key instead of expanding it | safe (fail-closed; no runtime caller emits one) | WC-3 | `runtime/publish_artifact.py` |
| AST pin: `allowed_write_sites=frozenset()` | requested | WC-2 | `tests/clarity_cert_spec.py` |
| Kit: both mutations apply only when the spec still lists write sites (the same rule already used for `arch_findings`) | safe (harness; P14 itself unchanged) | WC-4 | `tools/brain_certification/brain_cert_kit/mutations.py` |
| Exit-gate tests: Water Clarity moves from "legacy writer still present" to "retired in code"; a new test proves `CUTOVER_COMPLETE` passes the guard with the REAL runtime once an exit record exists, and is refused without one | safe (tests) | WC-2, WC-3 | `tools/brain_certification/tests/test_exit_gate.py`, `tests/test_clarity_live_parity.py`, `tests/test_clarity_central_mode.py` |
| `cutoverStatus` **stays `SHADOW`**; the flip is prepared as a document | gated (needs the LIVE exit checks of an approved cutover) | — | `docs/architecture/production/WATER_CLARITY_CUTOVER_COMPLETE_V1.md` |
| Docs: direct-write audit, operating contract, cutover plans, migrations table | safe (stale docs) | — | `docs/architecture/...`, `BRAIN_OPERATING_CONTRACT.md` |
| Engineering status regenerated (Kit re-collected for all 8 Brains) | safe (records) | — | `docs/cortex/engineering-status/` |

Note on WC-3: the X14 guard matches whole-node literals by regex. The builder's refusal set is written as `"/" + root + CLARITY`, so the refusal itself is not flagged as a write key. This is a refusal, not a write; `test_a_whole_brain_node_key_fails_the_build` proves it fails closed.

## 3a. Standing checks
| Check | Component | Result | Evidence |
|---|---|---|---|
| Output equivalence (refactor) | Water Clarity artifact | **PASS: byte-identical** sealed artifact and expanded payload, old harness vs new, for a first run and for a run with previous Brain state (pinned clock and BuildContext) | first run `02c47f63…`, previous state `ece18375…` (sha256 of the canonical artifact) in both |
| Kit V1 (all 8 Brains) | certification | PASS, failing: none | `tools/cortex_status/collect_certification.py` |
| X14 (offline) | Water Clarity | PASS in code: `legacy_write_sites == {writeSites: [], wholeNodeKeys: []}` | `test_water_clarity_legacy_writer_is_retired_in_code` |
| Memory checks (BR-10/11/16, PL-13) | Water Clarity runtime | unchanged: knowledge loading untouched; `test_knowledge_memory.py` passes | Brain suite |
| Data checks (FD) | writer change | the Brain writes nothing; the Publisher's registration is unchanged | `test_declared_write_set.py`, `test_publication_specialist_boundary.py` |
| Security (SEC) | writers | no rules, IAM or client change; the job identity is unchanged | n/a |

## 4. Verification
| Check | Command | Result |
|---|---|---|
| Water Clarity suite | `cd brains/water-clarity && pytest -q` | 138 passed (136 before: 4 new tests; 2 Kit mutation tests no longer apply to a Brain with no write site) |
| Kit, architecture, verification, research | `pytest -q tools/brain_certification tools/architecture verification tools/research` | all passed |
| Platform and orchestrator | `pytest -q jobs/brain_platform`; `cd jobs/brain-orchestrator && pytest -q` | 811 passed; 113 passed |
| Every Brain suite | `cd brains/<b> && pytest -q` (8 Brains) | all passed |
| Engineering status | `build_engineering_status.py --check` | OK |
| Pre-existing (main, without this change) | `tools/brain_certification/integration/test_wind_package.py` | fails only when `eccodes` is not installed; passes with the declared Wind requirements (as in CI) |

## 5. Open items
- **Production integration blocker:** the flip to `CUTOVER_COMPLETE` needs a complete `production-exit-evidence.json`. Twelve of its checks are LIVE (first real CENTRAL run, readback, rollback rehearsal, write denial with real IAM). See the prepared document.
- **Future improvement:** the payload still carries paths the builder drops (`/health/*`, snapshot compatibility copies, `lakeId`); they are declared in `brain.json` `legacyDirectWrites`. Removing them from the run is a later output change.

## 6. Decisions required and approvals
| # | Item | Options | Recommendation |
|---|---|---|---|
| 1 | Merge this branch | merge now (the job identity is already read-only, so production behaviour does not change until the next deploy) / wait for the first real run | merge after review; then redeploy the job from `main` in the same approval as the first real run (Sector_Ops 18 D1) |
| 2 | The flip itself | apply after the LIVE exit checks pass | keep SHADOW until then |

## 6a. Cleanup
New worktree `Worktrees/Sector_Engine/overnight-clarity` for this branch; closeout in the overnight run's closing comment (Sector_Ops issue 24).

## 7. Tested vs. intended
Tested: everything in §4, offline. Not tested: any real run, deploy or database (not approved).

## 8. Cortex gaps
None new.

## 9. Next step
Owner review of the draft PR; then Sector_Ops 18 D1 (one real CENTRAL-mode run).
