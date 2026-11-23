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

### Threat model (written after the review of 420ab9f; it replaces stronger claims made earlier in this session)
The ledger is meant to stop **accidental re-runs** and **re-runs by a session or agent that does not disclose itself**. It does that with a local hash-chained ledger and with public, timestamped comments on Sector_Ops #51, which a local copy cannot take back.

| Threat | Handling |
|---|---|
| Same command again, new `--out`, new process | refused (COMPLETED exists, or a dangling STARTED is terminal) |
| New research folder or deleted ledger (fresh genesis) | refused: the earliest `Run anchor:` for the protocol carries another anchor |
| Ledger rolled back to a snapshot | the restored run must post a second `Run start:` for (protocol, step, key) → REPEAT; without posting it cannot confirm or complete |
| Second `Run start:` appearing while a run is in progress | `complete()` records the result with `counted: false` |
| Local edits, reordering, truncation, copied ledger | refused (hash chain, head file, genesis root must equal the root) |
| Edited `Run anchor:` / `Run start:` comment, or an edited comment that mentions the protocol id | refused |
| **Deliberate deletion of #51 comments** (an admin) | **not preventable from inside the repo — a stated limit.** Every result-producing COMPLETED entry records its anchor and start comment ids and URLs; `audit(check_external=True)` reports missing ones, so a deletion is detectable by anyone holding the ledger or a report that printed `audit()` |
| **Abort after seeing values** | **not enforceable** — a review check every runner must pass (record outputs as soon as written; never abort after computing a result) |
| A forged Cortex | `for_brain` trusts the `cortex_home` it is given |
| GitHub timestamps / comment author | trusted as recorded / not checked |

### Choices made (reversible, stated)
- `result_producing=True` is the default for `begin`, so a runner that forgets the flag fails closed. Fetch steps pass `False`. Such attempts cannot call `record_outputs` and cannot record a result summary.
- Statuses beyond the requested three: `LEDGER_OPENED` (genesis), `INPUTS_BOUND`, `START_CONFIRMED`, `REPEAT_DETECTED` and `OUTPUTS_RECORDED`. Entry fields beyond the requested ones: `protocol_id`, `protocol_sha256`, `reason`, `result_producing`, `counted`, `external` and `git_dirty`.
- REPEAT works as follows. `confirm_started` raises `RepeatDetected` and writes `REPEAT_DETECTED`. A result-producing `complete()` requires a `START_CONFIRMED`, and then re-reads #51. If the start-comment count is not 1, or a `REPEAT_DETECTED` exists for the step, the COMPLETED entry gets `counted: false`. `require()` refuses a result that does not count.
- A retry after `abort_before_result` is clean only if the aborted attempt never posted a `Run start:`. Once a start comment is public, a retry is a REPEAT.
- `record_outputs`, `confirm_started`, `complete` and `abort_before_result` are accepted only from the `Ledger` object that called `begin`. A dangling STARTED is terminal, and recovery is a new protocol id.
- When `complete()` hits a gh failure it refuses. The attempt stays open, so the same object can call `complete()` again.
- The head file catches edits to the last line and truncation. It is repaired only when it is exactly one entry behind, which is what an interrupted append leaves.
- `step` and `key` may not contain whitespace, because they are tokens on the comment's first line.
- `os.write` is looped until every byte is written.

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
| New tests | `python3 -m pytest -q tools/research/tests/test_protocol_run_ledger.py` | 59 passed |
| Research tools suite | `python3 -m pytest -q tools/research` | 151 passed, 2 failed; both failures are pre-existing in this environment: the session runs as root, so the read-only-folder tests (`test_campaign.py::test_cleanup_removes_read_only_campaign_files_but_nothing_else`, `test_discovery.py::test_read_only_sources_folder_is_never_modified`) cannot see a permission error. They do not import the new module; CI runs as a normal user |
| Engineering status | `collect_certification.py`; `build_engineering_status.py --write`; `--check` | certification failing: none; status written with no diff; `--check` OK |

## 5. Open items
- The four runners adopt the module in their own PRs (#245–#248). Each runner:
  1. Opens the ledger with `Ledger.for_brain(brain, protocol_id, sha256(protocol doc), forbid_under=[args.out])`.
  2. Posts `post_anchor_text()` on #51 once, before any result-producing step.
  3. Binds inputs before computing.
  4. For each result-producing step, calls `begin`, posts `start_text`, calls `confirm_started`, then computes.
  5. Calls `record_outputs` as soon as outputs are written, then `complete`.
  6. Calls `require` for earlier steps.
  7. Prints `audit()` into its reports.
- Every runner's review must check that it never aborts after computing values. The ledger cannot enforce this.
- Stated limits are in the threat model above: deliberate deletion of #51 comments, abort after seeing values, a forged Cortex, and GitHub timestamps and comment authors being trusted.
- Smoke tests:
  - `for_brain('wind', …)` against the real Cortex extract, with `SECTOR_RESEARCH_HOME` set to a scratch folder. It resolved `<home>/wind-brain` and recorded it in `LEDGER_OPENED`. The folder was removed afterwards.
  - A read-only `gh api` listing of Sector_Ops #51 parsed 372 comments over several pages. Nothing was posted.

## 6. Decisions required and approvals
None. Approvals used: the standing owner approvals in `CLAUDE.md` (branch, push, PR). Not merged.

Closeout: [2026-11-23-protocol-run-ledger.closeout.md](2026-11-23-protocol-run-ledger.closeout.md).
