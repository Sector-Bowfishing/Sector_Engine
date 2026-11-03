Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (tree-identical to pin d5c8380), pack sector/engine

# Session record: run 2026-11-03 (3), Sector_Ops #50 follow-ups, third round

The owner approved:
- the read-only Brain database identity, as shown on the private Sector_Ops #50, then one verification read and the Mac-mini parity check;
- merging Water Temp A1–A4 (#104, #105, #106, #107) in order after review;
- copying this run's research files and the collector data to the research backup bucket.

The TVA upload is left for later. **Limits:** no cloud jobs, and no other IAM change. The identity details stay in the private issue, not in this public repository.

| # | Item | Outcome | Where |
|---|---|---|---|
| 1 | Read-only identity | **Applied as shown, then verified with one read.** A 1-hour token returned HTTP 200 for a shallow read of the Water Clarity Brain node. The identity has no write role and no key file | Sector_Ops #50 |
| 2 | Parity with read access | **The Mac mini could not be reached** (it accepts no key from this Mac), so the same check ran on the MacBook Pro as a stand-in. The run is Water Clarity's own central mode, with the bucket store replaced by a local folder and database writes refused, and the read token as its only credential. **Frozen 11-02 rules, unchanged.** Run 1: `NO_PARITY`, because `deploymentVersion` was missing (the read token cannot read the Engine's Cloud Run revision). Run 2, with `ENGINE_REVISION` set as written before it: **`PARITY_STRUCTURAL`** (R1 match; R2 48 = 48; R3 "other" only input age). The 11-02 false "registered" event is gone. Nothing was written to any database or bucket | `water-clarity/research/pulse-parity-2026-11-03-read/` (private research home) |
| 3 | Water Temp A1–A4 | **Merged in order** after an independent review (no code blockers) and green CI: #104 `e9a24592`, #105 `ceb3e8d9`, #106 `d90db71d`, #107 `b781289a`. Two review notes were fixed before merge: #104 refuses `--read-rtdb` or a bare `--dry-run` instead of falling through to the live writer; #105 requires an integer `--limit`. The #106 macOS swift job was a runner cancellation (no step ran) and passed on rerun. No deploy | Engine #104–#107 |
| 4 | Research backups | **Copied and checksum-verified** (0 differences): this run's Water Clarity parity folder, closeouts, manifests, the W1b folder, the runner scripts and LaunchAgents, and the collector data (5,516 objects, 3.8 GB). The bucket's 30-day retention lock forbids overwriting, so changed files went to new `snapshots/2026-11-03-run50/` prefixes; new folders went to their mirrored paths. The TVA archive data was not copied | private backup bucket |

**Review notes left open (none has any effect before the Water Temp cutover):**
- **The health mirror would serve less Water Temp health than the job writes today.** It carries `status` and `staleLakeCount` only. Old children such as `lastSuccess` would freeze, and the source health uses `failuresLastRun`, not `failures24h`. This must be settled before G3.
- **A `--lake` / `--limit` scoped artifact carries no "partial" marker.**
- **The Water Temp cert spec allows `.json` under `runtime/`.** That is the kit default, and every Brain allows it; narrowing it is a kit change.

**Pulse cutover item found:** an off-cloud runner must set `ENGINE_REVISION` in the job environment.

**Checks**
- Water Temp: 59 passed, 2 skipped.
- Lake: 63 passed, 2 skipped.
- Platform: 842.
- CI was green on every PR before merge.
- On main after #107, `build_engineering_status.py --check` is OK.

**Not done / gated:** nothing deployed, started or resumed, and no other IAM change. The TVA upload is left for later.

**Cortex gaps:** CG-3.1-13 (backup retention lock vs mirrored backup paths).
