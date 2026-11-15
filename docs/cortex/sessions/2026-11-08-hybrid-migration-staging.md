# 2026-11-08: staged hybrid moves for Lake, Water Temp and Wind (Roadmap #23 section 2)

**Standards:** Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine.

**Request:** prepare section 2 of the roadmap: move Lake, Water Temp and Wind onto Pulse the way Water Clarity moved. Build the code, review it, get every check green, and merge with the flags off. Deploy nothing, apply no IAM, flip nothing, and run nothing new on the owner's MacBook.

**Done (code only, flags off):**
- **Staged fragments:** `tools/ops/hybrid-stage/{lake-brain,water-temp,wind}.json`. No runtime reads them.
- **The tool:** `tools/ops/hybrid_stage.py` (show, check, apply).
- **Tests:** `jobs/brain-orchestrator/tests/test_hybrid_stage.py`. They prove three things:
  - the live policies still name Water Clarity only;
  - each fragment passes the real loaders;
  - the watchdog allows exactly the staged Brain inside its lakes.
- **Wind:** the lease-path entry `brains/wind/runtime/artifact_entry.py`, with its tests.
- **Sector-Pulse:** `water-temp-central` and `wind-central` catalog jobs, off by default (a separate PR).

**Readiness, and what blocks each:** recorded in each fragment's `blockers`. The IAM and the run sheets are on Sector_Ops #51 only, because IAM details stay out of this public repo.

**Gated, not done:** every IAM grant, the policy flips (`apply --write`), the Orchestrator and Publisher deploys, the execution control, and the release approvals.

**Cortex gaps:** none new.
