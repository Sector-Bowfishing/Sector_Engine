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

**Choices made (reversible, stated):**
- Extra status `OUTPUTS_RECORDED` and method `record_outputs`: abort is refused "if any output was recorded", so a runner needs a way to record an output before the result summary; once recorded the attempt can no longer be aborted. Extra status `INPUTS_BOUND` is what `bind_inputs` writes.
- A head file `<protocol_id>.head.json` beside the ledger, because a hash chain alone cannot detect an edit or truncation of its last line. A head exactly one entry behind (process stopped between append and head write) is repaired under the lock; anything else is refused.
- `counts(step, key, run=None)`: there can only be one COMPLETED per (step, key), so `counts` is True for that first COMPLETED run; with `run`, only if that run is it.
- `root` must exist (a typo would otherwise silently start a fresh ledger); `root` and `SECTOR_RESEARCH_ROOT` both set and different is refused.
- **Coordinator follow-up (same session):** a freely chosen root is the same back door as `--out`. Added `Ledger.for_brain(brain, protocol_id, protocol_sha256, repo=".")`, which resolves the root by running Cortex `research-path sector/engine <brain>` (Cortex from `cortex_home` or `$CORTEX_HOME`, never guessed), and refuses a `SECTOR_RESEARCH_ROOT` that differs from that output. Every new ledger now starts with a `LEDGER_OPENED` entry (resolved root, Brain, machine, how it was resolved), and `LEDGER_OPENED` is valid only as the first entry. `anchor()` returns that entry's hash and `verify_anchor(expected)` checks it. The anchor posted on Sector_Ops #51 is the binding record: a ledger whose first entry does not match it is invalid, which makes deleting and recreating a ledger detectable. `Ledger(root, …)` stays available for tests. Abort rule: abort is allowed only while the attempt has no output and no result; a retry gets the next attempt number; only the first COMPLETED counts.
- **Coordinator follow-up 2 (same session): external anchor.** Reviews of the census and Wind ledgers showed that deleting the ledger folder, or choosing a new one, still produces a fresh run #1 that looks valid, because nothing outside the machine pins it.
  - The genesis entry `LEDGER_OPENED` now also carries a random 128-bit nonce, the protocol id and sha256, the resolved research root, the host and the UTC time.
  - `post_anchor_text()` returns the comment to post on Sector_Ops #51. Its first line is `Run anchor: <protocol_id> <anchor>`, and it never carries an "Owner approval" header.
  - `require_external_anchor(repo="Sector-Bowfishing/Sector_Ops", issue=51)` reads the issue's comments with `gh api --paginate`. The `gh` call can be injected through the constructor's `gh=` argument. The check refuses unless the **earliest** `Run anchor:` comment for the protocol id carries this ledger's anchor and was created before the ledger's first result-producing STARTED entry. A later anchor comment for the same protocol never counts, and a gh failure refuses.
  - `begin(..., result_producing=True)` runs this check. **The default is True (choice: fail closed).** Fetch steps pass `result_producing=False`, and STARTED entries record the flag.
  - A STARTED entry with no end is **terminal** for its (step, key). `abort_before_result`, `record_outputs` and `complete` are accepted only from the `Ledger` object that began the attempt. Recovery from a killed run is a new protocol id.
  - A read-only `gh api` smoke test of Sector_Ops #51 parsed 372 comments over several pages and found 0 anchors. Nothing was posted.
- Input/output values may be a `Path` (file → `sha256_file`, directory → `sha256_tree`) or a sha256 hex string.
- Extra entry fields `protocol_id`, `protocol_sha256` (the protocol binding is checked on every line), `reason` and `git_dirty`.

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
| New tests | `python3 -m pytest -q tools/research/tests/test_protocol_run_ledger.py` | 46 passed |
| Research tools suite | `python3 -m pytest -q tools/research` | 138 passed, 2 failed; both failures are pre-existing in this environment: the session runs as root, so the read-only-folder tests (`test_campaign.py::test_cleanup_removes_read_only_campaign_files_but_nothing_else`, `test_discovery.py::test_read_only_sources_folder_is_never_modified`) cannot see a permission error. They do not import the new module; CI runs as a normal user |
| Engineering status | `collect_certification.py`; `build_engineering_status.py --write`; `--check` | certification failing: none; status written with no diff; `--check` OK |

## 5. Open items
- The four runners adopt the module in their own PRs (#245–#248): construct `Ledger(research_path, protocol_id, sha256(protocol doc), forbid_under=[args.out])`, bind inputs before computing, `begin`/`record_outputs`/`complete`, `require` earlier steps, and print `head()` into reports.
- Limits stated in the module: deleting or replacing the ledger is caught only by the external anchor. The check trusts GitHub's comment timestamps and does not check who posted the comment. Runners must post `post_anchor_text()` on #51 before their first result-producing step, either the runner session or a Mac mini request.
- Smoke test against the real Cortex extract: `for_brain('wind', …)` with `SECTOR_RESEARCH_HOME` set to a scratch folder resolved `<home>/wind-brain` and recorded it in `LEDGER_OPENED`. The folder was removed afterwards.

## 6. Decisions required and approvals
None. Approvals used: the standing owner approvals in `CLAUDE.md` (branch, push, PR). Not merged.

Closeout: [2026-11-23-protocol-run-ledger.closeout.md](2026-11-23-protocol-run-ledger.closeout.md).
