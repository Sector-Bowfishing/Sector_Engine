# Cortex gaps log

Append-only. Each entry gives a missing, ambiguous or contradictory Cortex standard, with references. These are proposals for a Cortex maintenance session; nothing here changes Cortex.

| Date | Session | Cortex reference | Gap | Proposed resolution |
|---|---|---|---|---|
| 2026-10-20 | `sessions/2026-10-20-cortex-activation.md` | `templates/consumer-config.md` (part 2, `permissions.deny`) | The read-only protection for Cortex is `Edit(//<cortex>/**)`. Tested here, it blocks Claude Code's Edit and Write tools. It does **not** cover shell commands (`Bash`) that could write into `$CORTEX_HOME`, such as redirection, `cp`, `git -C … commit`. So the "read-only" guarantee rests on the `CLAUDE.md` instruction, not on permissions | Either document that limit in `INTEGRATION.md` §2 and `CLAUDE.md` Boundaries, or add Bash deny patterns for common write forms into `$CORTEX_HOME` (knowing a deny list cannot be exhaustive) |
| 2026-10-20 | same | `INTEGRATION.md` §2 step 3 | It does not say which checkout's `.claude/settings.local.json` to use when a repository has many Git worktrees. Sector Engine has more than 80. Observed: settings placed in the primary checkout were applied to a session running in a sibling worktree, since the session picked up the Cortex `additionalDirectories` live. This is not documented, so it should not be relied on | State the rule. Settings go in the primary checkout, and each worktree session must be verified, or worktrees need their own copy |
| 2026-10-20 | same | `INTEGRATION.md` §2 step 3 ("add it to `.gitignore` if it isn't already ignored") | A user-global ignore (`~/.gitignore_global`) satisfies "already ignored" on one machine only | Recommend a repository-level `.gitignore` entry always. This activation added one |
