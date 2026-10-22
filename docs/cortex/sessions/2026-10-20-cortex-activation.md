# Rehtac Cortex consumer activation — Session Record

```text
Standards: Rehtac Cortex 2.0.1 @ fc56557 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · Branch: cortex/activation-2026-10-20 · Start commit: 7dae7051 · Date: 2026-10-20
```

## 1. Scope

**Request and mode:** activate the Cortex V2.0.1 consumer configuration for `sector/engine`, pinned to `fc56557`, using `cortex.py consumer-config`. That covers:
- appending the generated section to `CLAUDE.md` on an isolated branch;
- merging the generated settings into `.claude/settings.local.json` and keeping it Git-ignored;
- verifying the session-start hook, the task router and the read-only permissions.

No runtime, scoring or deployment changes. This was guided implementation, limited to configuration and records.

**Inspected:**
- Cortex `tools/cortex.py` (`consumer_config`, `session`, `drift`), `templates/consumer-config.md` (via the command output), `INTEGRATION.md` §2–3, `templates/REPORT_TEMPLATE.md`.
- `projects/sector/engine/PROJECT.md` §6 (records location), `projects/sector/engine/navigation/ROUTER.md`.
- Engine `.gitignore`, and the absence of any existing `CLAUDE.md` or `.claude/`.

**Not inspected:** a brand-new interactive session start. Hook execution was reproduced from the shell instead (§4).

## 2. Findings

| ID | Status | Evidence |
|---|---|---|
| ACT-1: pin `fc56557` exists and is Cortex 2.0.1 | PASS | `git log -1 fc56557` → "Cortex 2.0.1: absolute briefing commands…"; `VERSION` = `2.0.1`; Cortex HEAD = `fc56557`, clean |
| ACT-2: repository had no `CLAUDE.md` and no `.claude/` (nothing to preserve) | PASS | `ls` in the primary checkout and in this worktree |
| ACT-3: `.claude/settings.local.json` was ignored only by the user-global ignore | PARTIAL → fixed | `git check-ignore -v` → `~/.gitignore_global:4`; a repository-level entry was added |

## 3. Plan and changes made

| Correction | Class | Finding | Files | Commit |
|---|---|---|---|---|
| Add the generated Cortex section (26 lines, no personal paths) | safe | — | `CLAUDE.md` (new) | this branch |
| Ignore machine-local Claude settings at repository level | safe | ACT-3 | `.gitignore` (+2 lines) | this branch |
| Records folder, gaps log, this record | safe | — | `docs/cortex/README.md`, `docs/cortex/CORTEX_GAPS.md`, `docs/cortex/sessions/2026-10-20-cortex-activation.md` | this branch |
| Machine-local settings (env `CORTEX_HOME`, `additionalDirectories`, allow `cortex.py`, deny `Edit` on Cortex, `SessionStart` hook with `--pin fc56557`) | safe (local, uncommitted) | — | `.claude/settings.local.json` in the **primary checkout** (`Sector_Engine/`; created new, since no prior file existed) | not committed (ignored) |

No Engine runtime, test, scoring, contract or deployment file was changed.

## 4. Verification

| Check | Command | Result (actual) |
|---|---|---|
| Generated settings are valid JSON | `python3 -m json.tool .claude/settings.local.json` | valid |
| Settings file is Git-ignored | `git check-ignore -v .claude/settings.local.json` | ignored (global rule today; repository rule on this branch) |
| Session-start hook runs with a minimal environment | the hook command from the settings, run under `env -i HOME=… PATH=/usr/bin:/bin CLAUDE_PROJECT_DIR=<checkout> /bin/sh -c` | exit 0 in both the primary checkout and this worktree. Prints `Standards: Rehtac Cortex 2.0.1 @ fc56557 (clean), pack sector/engine`, the 8 mandatory files, the 3 per-task standards, the records location `docs/cortex/`, and the drift summary. It resolves through `/usr/bin/python3` 3.9.6 when Homebrew is not on PATH |
| Drift on this branch | `cortex.py drift sector/engine --repo .` | HEAD equals the snapshot commit; 8 Brains match; 0 items need verification |
| Drift in the primary checkout | hook output | Reports 913 changed files and 32 items to verify, because that checkout is on the old branch `docs/lake-brain-research` (`caa9908e`). This is correct behaviour (see Open items) |
| Task router reachable and readable | read `projects/sector/engine/navigation/ROUTER.md` | Readable; task table resolves to Engine paths that exist at `7dae7051` |
| Cortex added as a readable directory | the session environment | Cortex appeared as an additional working directory after the settings were written |
| Edit denied on Cortex | Edit with a non-matching string on `Cortex/VERSION` | **Denied**: "File is in a directory that is denied by your permission settings." |
| Write denied on Cortex | Write of identical bytes to `Cortex/VERSION` | **Denied** (same message). Cortex `git status --porcelain` is empty and `VERSION` mtime is unchanged |
| `cortex.py` runs without prompting | `python3 /Users/…/Cortex/tools/cortex.py session …` | Ran. This session uses auto permissions, so the absence of a prompt does not prove the allow rule independently |
| Engine gates unaffected | `pytest tools/architecture`, `verification`, `tools/brain_certification` | 87 passed; 12 passed, 2 skipped; 32 passed |

**Not run:** an actual new Claude Code session start, which would show the hook output injected into a fresh context. Swift and Python Brain suites were not run because no code was touched.

## 5. Open items

### Current release blockers
None. Activation is configuration only.

### Future items
- Sessions started in the **primary checkout** will see large drift until that checkout is moved to `main` or a current branch. The checkout belongs to another lane, so it was left untouched.
- Worktree sessions get the settings only if Claude Code applies the primary checkout's local settings to them. This was observed once (Cortex was added to this worktree session), but it is not a documented guarantee. Logged in `CORTEX_GAPS.md`.

## 6. Decisions required and approvals

### Decisions required

| # | Item | Options | Recommendation |
|---|---|---|---|
| 1 | Push and open a PR for `cortex/activation-2026-10-20` | push + PR / keep local | Push + PR (docs/config only) |

### Approvals (gated)

| # | Action | Status |
|---|---|---|
| 1 | Push branch / merge | pending |

## 7. Tested vs. intended
- **Executed and observed:**
  - config generation;
  - JSON validity;
  - ignore status;
  - the hook command under a minimal environment, in both checkouts;
  - drift;
  - Edit and Write denial on Cortex;
  - the Engine architecture, verification and kit gates.
- **Intended but not observed:** the hook firing automatically at the start of a new session.

## 8. Cortex gaps
Three entries were added to `docs/cortex/CORTEX_GAPS.md`:
1. The Bash write path into Cortex is not covered by the `Edit` deny rule.
2. Settings placement in multi-worktree repositories is undefined.
3. A user-global ignore should not count as "already ignored".

## 9. Next step
Open a new Claude Code session in the Engine repository and confirm that the Cortex briefing appears in its initial context.
