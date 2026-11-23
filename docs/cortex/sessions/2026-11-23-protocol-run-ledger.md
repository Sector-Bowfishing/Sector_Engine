# Protocol run ledger for pre-registered research runners — Session Record

```text
Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with git archive; the loader reports "uncommitted" because the extract has no .git), pack sector/engine
Repository: Sector-Bowfishing/sector_engine · Branch: research/protocol-run-ledger-2026-11-23 (new worktree off origin/main) · Start commit: f5460aa · Date: 2026-11-23
```

## 1. Scope
- **Request and mode:** guided implementation. Build a shared, stdlib-only module `tools/research/protocol_run_ledger.py` with tests, so the four pre-registered runners (#245 Wind strong-wind, #246 Weather retro, #247 Lake gauge census, #248 Water Temp protected truth) stop operators from re-running a step after seeing its result. Their reviews failed because each write-once guard was tied to the operator-chosen `--out` folder. The API shape was fixed by the coordinator (other sessions code against it).
- **Inspected:** `tools/research/` (existing `ledger.py` is the gap ledger, a different thing; name kept distinct), its test conventions and CI (`foundation-verification.yml` runs `pytest -q tools/research`), Cortex `research.md` RS-02 (`sha256-tree-v1`, reused exactly), RS-15, RS-18, RS-30, `cortex_research.py tree_sha256`, `CORTEX_GAPS.md` on main and on open PR branches #245–#249 (CG ids).
- **Not changed:** the four runners (their own PRs adopt the module). No research data, no Firebase, no network.

## 2. Findings
| ID | Status | Finding | Evidence |
|---|---|---|---|
| F1 | FAIL (in the four PRs, not on main) | Write-once guards keyed on `--out` allow a re-run with a new `--out` | coordinator's review summary of #245–#248 |
| F2 | GAP | Cortex has no rule for where a pre-registered protocol's run record lives | CG-3.1-27 |

## 3. Plan and changes made
| Correction | Class | Finding | Files |
|---|---|---|---|
| Shared run ledger module + tests | Safe (requested, additive) | F1 | `tools/research/protocol_run_ledger.py`, `tools/research/tests/test_protocol_run_ledger.py` |
| Cortex gap entry | Record | F2 | `docs/cortex/CORTEX_GAPS.md` (CG-3.1-27; main ends at CG-3.1-24, #245/#246 use 25/26) |

### Threat model (final scope set by the coordinator after the round-2 review of d2bcccb; replaces every earlier, stronger claim in this session)
**It stops** accidental re-runs, and re-runs by an honest-but-careless or non-disclosing session or agent that uses the ledger API as written.

**It does NOT stop a deliberate actor** who holds the same GitHub or filesystem credentials:
- The gh identity that posted a comment can edit or delete its own comments, and GitHub's REST API does not expose edit history.
- Anyone who can write the research folder can forge ledger lines and recompute the chain and the head.

The hash chain detects accidental corruption and careless edits, not a forger. The real assurance against a deliberate actor is the public #51 trail plus human review.

| Situation (careless or non-disclosing user of the API) | Handling |
|---|---|
| Same command again, new `--out`, new process | refused (a COMPLETED exists, or a dangling STARTED is terminal) |
| New research folder or deleted ledger (fresh genesis) | refused: the earliest `Run anchor:` for the protocol carries another anchor |
| Ledger rolled back to a snapshot | the result step must confirm a single `Run start:` carrying this attempt's STARTED hash. The restored run either posts a second one (REPEAT) or cannot confirm, and so cannot complete |
| Running a result step as a non-result step (the round-1 PoC) | impossible: `result_steps` is declared by the runner, recorded in the genesis entry, fixed on reopen; `begin` has no per-call flag. A non-result `begin` is refused if #51 has a `Run start:` for that step |
| A second or mismatching `Run start:` before `complete()` | the result is recorded with `counted: false`; `first`/`counts`/`require` accept only counted COMPLETED entries of result steps |
| Copied ledger | refused (the genesis root must equal the root) |
| Edited records | refused: a comment whose id the ledger recorded; an edited comment naming the protocol id as an exact token; an edited `Run …` comment by the anchor's author created after the anchor |
| Ledger tail forged after the result was posted | detectable afterwards: `audit(check_external=True)` compares the `Run result:` comment (`<completed_entry_sha256> <result_sha256>`) with the ledger |

| Stated limit | Note |
|---|---|
| Deleting or editing one's own #51 comments | not preventable; edit history is not readable over REST. `audit()` reports recorded comment ids that are missing or no longer start with `Run ` |
| Forging ledger lines | not preventable locally; detectable only against comments that still exist |
| Abort after seeing values | not enforceable; a review check every runner must pass |
| Cortex and GitHub | `for_brain` trusts the `cortex_home` it is given; GitHub timestamps are trusted |

### Choices made (reversible, stated)
- **`result_steps`.** This is a required keyword of both constructors: a frozenset of step-name tokens. It is recorded as `resultSteps` in `LEDGER_OPENED`, and a reopen with a different set is refused. `begin` takes no flag. A non-result step cannot record outputs before completion, and cannot record a result summary.
- **Extra statuses.** Besides the requested three: `LEDGER_OPENED`, `INPUTS_BOUND`, `START_CONFIRMED`, `REPEAT_DETECTED` and `OUTPUTS_RECORDED`.
- **Extra entry fields.** Besides the requested ones: `protocol_id`, `protocol_sha256`, `reason`, `result_producing` (derived), `counted`, `external` and `git_dirty`.
- **REPEAT.**
  - `confirm_started` raises `RepeatDetected` and writes `REPEAT_DETECTED`.
  - `complete()` requires `START_CONFIRMED` and re-reads #51. The result counts only when exactly one `Run start:` exists, it carries this attempt's STARTED hash, and no REPEAT was detected.
  - `external` records the anchor and start comment ids, `startSha` and `startCommentsAtComplete`.
- **`result_text(step, key)`.** It is posted after `complete()`, and `audit(check_external=True)` checks it.
- **Retries.** A retry after `abort_before_result` is clean only if no `Run start:` was posted. Once one is public, the retry is a REPEAT.
- **One object per attempt.** `confirm_started`, `record_outputs`, `complete` and `abort_before_result` are accepted only from the object that began the attempt. A dangling STARTED is terminal, and recovery is a new protocol id.
- **gh failures.** A gh failure refuses. A failed `complete()` can be retried by the same object.
- **Head file.** It is repaired only when it is exactly one entry behind.
- **Step and key names.** `step` and `key` may not contain whitespace.
- **Short writes.** `os.write` is looped until the whole line is written.

## 3a. Standing checks
| Check | Result | Evidence |
|---|---|---|
| research-check `--repo .` | no finding in the new files (pre-existing findings elsewhere unchanged) | `research-check sector/engine --repo .` |
| data-check | no finding in the new files | `data-check sector/engine --repo .` |
| worktree-check | this worktree KEEP_ACTIVE after push; others belong to other sessions, not touched | `worktree-check --repo /home/claude/sector_engine` |
| Security triggers | none apply (no data path, rules, cache, public build or consumer change) | — |
| Memory / ops / mission checks | not applicable (no Brain runtime, knowledge loader, `brain.json` or charter touched) | — |

## 4. Verification
| Check | Command | Result |
|---|---|---|
| New tests | `python3 -m pytest -q tools/research/tests/test_protocol_run_ledger.py` | 68 passed |
| Research tools suite | `python3 -m pytest -q tools/research` | 160 passed, 2 failed; both failures are pre-existing in this environment: the session runs as root, so the read-only-folder tests (`test_campaign.py::test_cleanup_removes_read_only_campaign_files_but_nothing_else`, `test_discovery.py::test_read_only_sources_folder_is_never_modified`) cannot see a permission error. They do not import the new module; CI runs as a normal user |
| Engineering status | `collect_certification.py`; `build_engineering_status.py --write`; `--check` | certification failing: none; status written with no diff; `--check` OK |

## 5. Open items
- The four runners adopt the module in their own PRs (#245–#248). Each runner:
  1. Declares `RESULT_STEPS = frozenset({...})` as a module constant.
  2. Opens the ledger with `Ledger.for_brain(brain, protocol_id, sha256(protocol doc), forbid_under=[args.out], result_steps=RESULT_STEPS)`.
  3. Posts `post_anchor_text()` on #51 once.
  4. Calls `bind_inputs`.
  5. For each result step: `begin`, post `start_text`, `confirm_started`, compute, `record_outputs`, `complete`, post `result_text`.
  6. Calls `require` for earlier result steps.
  7. Prints `audit()` in its reports.
- Every runner's review must check that it never aborts after computing values. The ledger cannot enforce this.
- The stated limits are in the threat model above.
- Smoke tests:
  - `for_brain('wind', …)` against the real Cortex extract, with `SECTOR_RESEARCH_HOME` set to a scratch folder. It resolved `<home>/wind-brain` and recorded it in `LEDGER_OPENED`. The folder was removed afterwards.
  - A read-only `gh api` listing of Sector_Ops #51 parsed 372 comments over several pages. Nothing was posted.

## 6. Decisions required and approvals
None. Approvals used: the standing owner approvals in `CLAUDE.md` (branch, push, PR). Not merged.

Closeout: [2026-11-23-protocol-run-ledger.closeout.md](2026-11-23-protocol-run-ledger.closeout.md).
