Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (tree-identical to pin d5c8380), pack sector/engine

# Session record: overnight research run 2026-11-01 (Sector_Ops #41)

The owner delegated this run on Sector_Ops #41: research, records and scoping only. The results are on the linked Sector_Ops issues.
Private research detail stays in the private research workspace and its backup, not in this repository.

| Item | Outcome | Where reported |
|---|---|---|
| 1. Baseline-first clarity (B1) | Pre-registration frozen and posted before any number existed. Outcome **NO** (development verdict): the per-lake seasonal Secchi baseline passes on South/mid-South reservoirs (about twice production's band accuracy) but fails at the home lakes. The rain/flow adjustment was not adopted, and lakes with no history stay UNKNOWN. | Sector_Ops #40 |
| 2. Low-confidence clarity label | Scoped only. The Engine already marks clarity confidence, but the iOS app does not decode it. The plan is a small Engine change plus an iOS change, both gated. | Sector_Ops #40 |
| 3. Research triage of #26–#39 | Keep / merge / park table posted, with what the research pause means and what lifting it needs. | Sector_Ops #23 |
| 4. Lake capabilities and D1–D8 | Trims and proposed answers, including a new D8 (Beta requires only go-tonight capabilities). The contract is **not** finalized. | Sector_Ops #22 |
| 5. Level / wind coverage per lake | Read-only join, posted. 284 of 621 lakes could have level, wind and clarity history. | Sector_Ops #34 |

**Checks**
- Cortex briefing run. Local Cortex HEAD `3ac7e81` differs from the pin `d5c8380` only because the pin is the merge commit of the same
  tree (`git diff 3ac7e81 d5c8380` is empty), so this is not a standards difference.
- `research-check --closeout` passes for all three closeouts.
- **New research-home finding from this session's work:** three DUPLICATE_DATASET entries. G0 copied the registry polygons and two EPA NLA
  site files that other Brains already hold. Moving them to `shared/` and pointing the G0 tools there is a small follow-up (RS-01).
- The other research-home and repository findings were present before this run.
- `worktree-check`: no REMOVABLE worktrees.
- The Wind collector loop kept running, and its sealed H2 window was not touched.

**Not done:** nothing was deployed or published, and there was no IAM, rules, schedule, database or customer-facing change. Research
execution stays paused (the `RESEARCH_PAUSED` flag is unchanged). This record is the only repository change.
