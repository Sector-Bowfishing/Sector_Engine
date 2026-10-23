# Sector — eight-Brain research automation verification and completion — Session Record

```text
Standards: Rehtac Cortex 2.7.0 @ ebc7fb9 (clean), pack sector/engine
Repository: Sector-Bowfishing/Sector_Engine · main @ d4b70bc7 (start) · Branch: cortex/research-automation-2026-10-23 · Date: 2026-10-23
```

**Mission.** Verify, and where safe complete, unattended eight-Brain research automation. Cloud Brain execution stays PAUSED. No cloud, no Firebase, no approvals, no science changes. The full research campaign was not started.

## Inventory (before)

**What existed:**
- per-Brain research tools and campaign scripts;
- manifests and closeouts in all eight research folders;
- the Cortex hygiene checks;
- `tools/knowledge/build_release_manifest.py`;
- the scorer (needs RTDB).

The 2026-10-22 campaign was coordinated by hand: separate sessions plus hand-maintained `tracker-*.json` / `TRACKER.md`. There was no coordinator, checkpoint, resume, validation gate, cleanup executor or consolidated report. Four read-only agents, two Brains each, ran every candidate evaluator offline. The result is in `docs/research/RESEARCH_CAMPAIGN_AUTOMATION_V1.md`.

## Added

- **`tools/research/campaign.py`:** the campaign harness. It provides:
  - init, run, submit, status, report and brief;
  - checkpointed stages discover → research → validate → candidate → score → cleanup, then report;
  - dependency order from `brain.json`;
  - bounded parallelism, timeouts, bounded retries and failure isolation;
  - adapters with network, gcloud and Firebase blocked;
  - candidates packaged with `knowledge_release` and approval NOT_RECORDED, never into the Engine;
  - authoritative score artifacts hash-checked;
  - cleanup limited to the owner-marked workspace, including read-only clone files;
  - manifest and closeout updates (RS-02, RS-05).
- **`tools/research/adapters/run_adapter.py` and `adapters.json`:** research, validate and score stages for all 8 Brains, wrapping only existing evaluators. Root-writing scripts run on APFS clones. Local paths come from environment variables or the Cortex layout; there are no hard-coded machine paths.
- **`tools/research/fixtures/*.json`:** labelled verification findings (one should validate, one should be rejected). They cite real evidence and are judged by real metrics, and are used only by `init --verification`.
- **`tools/research/tests`** (12 tests, mutation-checked) and a CI step in foundation-verification.

## Verification evidence

- **Unit tests on a fixture home:** 12 pass.
- **Mutations caught (7):**
  - no SHA check
  - cleanup ignoring ownership
  - candidate approved
  - resume redoing finished stages
  - network not blocked
  - no dependency order
  - plain `rmtree` on read-only files
- **Three eight-Brain runs on APFS clones of the real research home** (real evidence bytes):
  - each was hard-killed mid-stage (`lake-brain:validate`, `wind:candidate`, `depth:research`) and then resumed;
  - every track finished DONE, and only interrupted stages ran a second time;
  - 1 validated / 1 rejected finding per Brain, each rejected for its real reason;
  - 8 candidates verify as releases, approval NOT_RECORDED;
  - authoritative scores unchanged;
  - workspaces deleted;
  - all 8 closeouts pass `research-check --closeout`;
  - Cortex `research-check` finding count identical before and after a campaign.
- **Real research home:** file fingerprint identical before and after every run.
- **Defect found and fixed:** clones keep read-only permissions (some research snapshots are write-protected), so cleanup now makes only campaign-owned files writable before deleting them.

## Readiness

| Capability | Readiness |
|---|---|
| Autonomous research | PARTIAL: agent-performed; the harness gives briefs, a contract and gates |
| Autonomous validation | PARTIAL: automatic against existing validator metrics only |
| Candidate packaging | READY |
| Approved-memory publication | GATED, manual (M-3, G-1) |
| Authorized Firebase updates | GATED and PAUSED (PL-16); never by a campaign |
| Local cleanup | READY |
| Unattended execution and recovery | READY for the harness |

Blockers outside the harness: see the automation doc (Wind cache, Clarity R3.1 cache and private worktree data, Lake branch-only inputs, missing `GAPS.json` for 3 Brains).
