Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (tree-identical to pin d5c8380), pack sector/engine

# Session record: run 2026-11-04, Sector_Ops #50 follow-ups (items 1–6, alongside the Pulse session)

**Asked:** six items.

**Limits:**
- no cloud jobs, deploys, IAM or write tokens;
- the Pulse repository not touched;
- #110 not merged by this session (it was already merged on main when the run started).

| # | Item | Outcome | Where |
|---|---|---|---|
| 1 | Water Temp health-mirror fix | **Draft PR, CI green.** **A real bug was found:** the mirror copied each Brain registry's `status` (the lifecycle: `BETA`, `CALIBRATION`) into `/health/brains/{id}/status`, but run health is `health`. For Water Clarity, the one CENTRAL Brain, the first Orchestrator cycle would have overwritten the live `HEALTHY` with `BETA`; a one-key read with the read-only identity confirmed that live state. Each spec now maps health children to published fields. Water Temp: `lastSuccess` ← `lastSuccessfulRun`; `lastRun`, `errorCount` and `durationMs` are removed at cutover instead of freezing; `failuresLastRun` is carried | Engine #111 |
| 2 | Lake cutover B1–B7 | **B1–B7 rewritten for Pulse as the runner:** a draft plan, plus B3 capture and B4 rehearsal tools (`tools/cutover/`, in CI). **Smoke run with the real `LakeBrainJob` against the GET-only fake:** 12 GETs, no write, one sealed artifact. **Bug found and fixed:** the Publisher image could not stage Lake's or Water Temp's release (nested files). `LakeBrainJob` got the same flag guard as Water Temp. The B5 cutover entry is a separate, inert draft (empty `approvalRef`, so the loader ignores it). **Open:** B4b forced-CWMS failure (CWMS's address is hard-coded); B5's live publish needs a database write (an owner decision) | Engine #113, #114 (stacked, do not merge) |
| 3 | Engine checkout, worktrees | **Main checkout:** moved from `docs/lake-brain-research` (clean, on origin) to `main` at `40c6d952`. **Worktrees:** 17 removed with `git worktree remove` (no force). Each was clean, its HEAD was on `origin/main`, and nothing running or configured used it. Kept: dirty, unique, open-PR and active ones, this session's own worktree, and the Pulse session's `wc-read-rtdb` | — |
| 4 | Presence: no record = UNKNOWN | **Draft PR, CI green.** Fish dropped species with no Lake record and counted every record as "present". A roster now lists them as `UNKNOWN`, `evaluated: false`. Without a roster the output is unchanged, so the frozen Fish V2 baseline is unaffected. Intelligence words the same rule | Engine #112 |
| 5 | Sector Intelligence job | **Plan-first note:** SI-A1 to SI-A6, gates, and decisions SI-P1 and SI-P2. Off-cloud, Intelligence needs `ENGINE_REVISION`, as Water Clarity did | Engine #115 (docs) |
| 6 | #83, #85, #89, #90, #94 | **Main merged in** (stacked: #85 → #89 → #94). Only the generated digest files conflicted. Digests re-recorded; **all CI green**. Nothing merged | those PRs |

**Checks**
- brain_platform 849 (#111) and 845 (#112);
- brain-orchestrator 136;
- brain-publisher 18;
- Fish 407; Intelligence 100; Lake 63;
- tools/cutover 6; tools/architecture 187.
- Digests were re-recorded on every branch.

**Not done / gated:**
- no B step was run against production;
- nothing deployed, enabled or granted.

**Cortex gaps:** CG-3.1-14 (worktree-check keeps a merged, clean worktree as `KEEP_ACTIVE` for 7 days).
