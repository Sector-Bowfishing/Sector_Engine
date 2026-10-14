# Handoff History Standard

Recent work found older Brain handoffs missing from expected folders. A light, file-based standard — **no handoff database**.

## Rules
1. **Append-only.** Never delete or overwrite a handoff. Corrections are a new file or an `UPDATE` section appended with a date.
2. **Location.** `~/Desktop/Sector Handoffs/Sector Engine/<Brain>/` (Depth Brain, Biological Brain, Vegetation Brain, Lake Brain, Wind Brain, Intelligence, Brain Platform …). A Brain's handoffs live only in its own folder, not the parent.
3. **Naming.** `YYYY-MM-DD <Project> <Brain> <Topic> Handoff.md`. New file per session/campaign.
4. **Optional `HANDOFF_INDEX.md` per Brain folder**, one row per handoff, newest last:

| date | file | summary | supersededBy | restored | authoritativeCurrent |
|---|---|---|---|---|---|
| 2026-10-13 | `…Foundation Handoff.md` | one line | `—` / file | `no` / `yes (from <source>)` | `no` |
Exactly one row has `authoritativeCurrent = yes`.
5. **Superseded ≠ deleted.** Mark `supersededBy`; keep the file.
6. **Restored flag.** If a handoff is recovered (Time Machine, git, another copy), add the row with `restored: yes (<source>)`; do not rewrite its content.
7. **Repo vs Desktop.** Handoffs are working notes on the Desktop; durable decisions are copied into the repo docs. A repo doc never depends on a Desktop path existing.
8. **Public repo rules still apply** (e.g. no per-lake species presence, no private identifiers).

## Check (manual, 30 s)
List the folder; confirm every file is in the index; confirm one authoritative-current row. The platform lane keeps `~/Desktop/Sector Handoffs/Sector Engine/Brain Platform/HANDOFF_INDEX.md` as the worked example.
