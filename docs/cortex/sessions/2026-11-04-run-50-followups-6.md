Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (tree-identical to pin d5c8380), pack sector/engine

# Session record: run 2026-11-04 (3), Sector_Ops #50 follow-ups

**Approved:**
- option (a): move Water Clarity's health family to the Orchestrator (Cortex change + Engine PR);
- merging #117, #118 and #119 after review.

**Not decided:** decision 4, the Lake B5 database write.

**Limits:** no cloud jobs, deploys, IAM or write tokens.

| # | Item | Outcome | Where |
|---|---|---|---|
| 1 | Review of #117, #118, #119 | An independent read-only review found **one blocker (#117) and several should-fix items**. The blocker and the safety-relevant items were fixed before merge | — |
| 2 | Merge #117 | **Merged** `3f0e95c1`. **Blocker fixed:** the fault guard read raw argv tokens, so `--fa` (an argparse abbreviation) or an empty `--artifact-dir` could let a fault-injected artifact reach the bucket. It now checks the parsed arguments through a `validate` hook in `swift_artifact_entry.main`, with regression tests for every bypass. `LakeBrainJob` refuses `--fault=NAME`, which was silently ignored and would have run on live CWMS. `REHEARSAL.json` records the faults applied | Engine #117 |
| 3 | Merge #118 | **Merged** `1b8bb327`. A runner-supplied Engine revision is `lineageSource: RUNNER_SUPPLIED` and is never `lineageVerified`. Without a digest the reason is "unverified: the runner supplied no image digest" and the blocker is info, not a false "image differs" warning. A matching digest is recorded as `digestMatchesDeclared` (unattested). The no-destination test no longer reads live when `SI_ARTIFACT_BUCKET` is set. **Left as noted:** the artifact upload uses the same token provider as the reads, the same pattern as Clarity, Lake and Water Temp. Separating them belongs to the identity split (Sector_Ops #19) | Engine #118 |
| 4 | Merge #119 | **Merged** `a9b922f5` after a sync with main. **Left as noted (minor):** `evaluatedLakes` is now written as `0` where the legacy writer left it absent, and `engineRevision` is retired although the registry carries `engineServing.revision` | Engine #119 |
| 5 | Option (a), Engine side | **Draft, green, blocked on Cortex 3.1.2.** The platform write guard follows the registry: `brain-platform` may write `/health/brains/{id}/{child}` and `/health/sources/{id}` only where the registry's current writer is `platform.orchestrator`, and no Brain may write those paths. The mirror carries four proposed rows: Clarity's health and its three sources. A literal segment now beats a `{placeholder}` at equal depth. Swift mirrors the rule, with nine shared conformance cases. Tests that assumed Clarity writes its own health were updated (X14). All suites pass against a scratch copy of Cortex with the proposed rows; against pinned Cortex only the mirror-equality test fails, by design | Engine #121 |
| 6 | Option (a), Cortex side | **Not started.** Starting a Cortex maintenance session from this session was refused by the permission system. The proposal is recorded (Cortex gaps log, CG-3.1-15 follow-up) for the owner to start that session | `docs/cortex/proposals/cg-3-1-15-clarity-health-orchestrator.md` (#121) |

**Checks**
- brain_platform 850–861; brain-orchestrator 136; brain-publisher 18; brain-scores 37;
- Lake 71; Water Temp 59; Clarity 148; Intelligence 106; tools/cutover 10; tools/runner 4;
- tools/architecture + verification 222; brain certification 32;
- Swift `BrainPlatformConformanceTests` 11.
- Every merged PR was green on its head commit before merge.

**Not done / gated:**
- Decision 4 is open.
- Cortex 3.1.2 needs a maintenance session.
- #121 stays draft until then, and its live effect needs an Orchestrator deploy (not authorised).
- Nothing deployed, enabled or granted.
