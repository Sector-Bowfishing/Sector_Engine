Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (tree-identical to pin d5c8380), pack sector/engine

# Session record: run 2026-11-03 (2), Sector_Ops #50 follow-ups, second round

The owner approved the six decisions of the follow-ups report as recommended, with two changes:
- **Decision 3:** move the collector off Desktop instead of granting Full Disk Access.
- **Decision 2:** show the exact IAM change before applying it.

Same hard limits: no cloud jobs, no other IAM, no write tokens.

| # | Decision | Outcome | Where |
|---|---|---|---|
| 1 | W1b nightly until complete | A transport controller runs the frozen fetch each night 00:05–13:00Z (one serial process, public data, no LLM). Hard end 2026-11-10T13:00Z; it stops when the set is complete. Not a LaunchAgent, so it does not survive a reboot | private research workspace (wind-brain) |
| 2 | Read-only database identity | **Prepared, not applied**; the exact change was put to the owner on the private Ops issue | Sector_Ops #50 |
| 3 | Collector off Desktop | Runs under launchd from a folder outside Desktop (own clone, exact venv). The data moved by rename, identical file count and size; the research path is a symlink. The first cycle under launchd ran; no gap | private research workspace (wind-brain) |
| 4 | TVA archive locally | Hourly launchd job writing to a local folder only (no bucket). The first run found only 8 h per dam left at TVA | private research workspace (water-temperature) |
| 5 | Water Temp A1–A4 | Drafts:<br>• #104: `--read-rtdb`; `ReadThroughDryRunStore` moved to the core and shared with Lake.<br>• #105: one shared Swift artifact entry; Lake's becomes a wrapper.<br>• #106: health becomes orchestrator-derived (registry/contract).<br>• #107: release record for the model definition. The physics is shared Engine code a release cannot pin | Engine #104–#107 |
| 6 | Merge #102, Pulse #3 | **Merged** after an independent review: #102 `a1cc4649`, Pulse #3 `12919a1b`. All review findings were fixed first (below) | Engine #102, Sector-Pulse #3 |

**Review fixes before merge**
- **Pulse #3, the blocker:** token refresh could have kept orchestrator and Publisher write tokens. It now refreshes only the read token and the create-only uploader token, with explicit scopes and the real expiry.
- **Pulse #3, lease handling:**
  - a lease job starts only for the cycle held now;
  - the lease is renewed during the run;
  - the hand-off refuses an artifact from another cycle.
- **Engine #102:**
  - the grant ledger is the only proof of a grant, and it is written before the lease;
  - there is a re-grant cooldown per staleness window, and grants count against `maxRunsPerDay`;
  - the local Publisher pass uses only the Publisher token;
  - a local cycle refuses to start without an explicit token;
  - the shadow lane is held in local mode.

**Checks**
- Engine: platform 838–841, orchestrator 136, foundation 295–296.
- Swift: Water Temp 19, Lake 104.
- All 7 release manifests `--check` OK. Digests re-recorded on every branch.
- Pulse: 76 passed, 2 skipped.
- `research-check`: 0 findings.

**Not done / gated:** no IAM change, no token created, no cloud job, deploy or database write. Research backups are still not copied.

**Cortex gaps:** CG-3.1-12 is updated (the owner chose relocation out of the protected folder).
