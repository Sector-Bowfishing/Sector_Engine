Standards: Rehtac Cortex 3.1.1 @ 3ac7e81 (tree-identical to pin d5c8380), pack sector/engine

# Session record: run 2026-11-03, Sector_Ops #50 follow-ups

The owner approved the six #50 decisions as recommended and added three items: readiness notes for Water Temp and Sector Intelligence, and a Pulse-first line on #23.

**Hard limits:**
- no Cloud Function, Cloud Run job or Scheduler job started, deployed or resumed;
- no IAM change, token creation, database write or outgoing message;
- #83, #85, #89, #90, #94, iOS #219 and iOS #220 not merged.

The standing condition from #50 holds: no cloud runs until Pulse works.

| # | Item | Outcome | Where |
|---|---|---|---|
| 1 | W1b overnight fetch | **Checked first: it is a plain stdlib script.** `tools/w1b.py` and its W1 helper use only `urllib`, make **no Claude/LLM call**, and fetch **public data only** (Open-Meteo previous-runs; the ASOS data is already cached). FREEZE verifies. One serial process, started at 04:53Z under `caffeinate`, with a watchdog that stops it at 13:00Z. About 10 files an hour, so it is not expected to finish. Scoring stays in session | `wind-brain/research/w1b-app-leads-2026-11-02/W1B_STATUS-2026-11-03.md` |
| 2 | #51 C1–C4 | C1+C2 Engine draft: runner executor (grant the lease, start nothing), local runner mode (no Cloud Run or Scheduler API call; `gcp.disable_cloud_calls`; local lock; local Publisher pass, a dry run unless `PUBLISHER_LOCAL_LIVE=on`; **in-process Brains never run locally**), grant ledger. C3+C4 Pulse draft: lease jobs, the central cycle, token refresh (`security -i` on stdin), O1 runbook | Engine #102, Sector-Pulse #3 (drafts) |
| 3 | Merge #96, Pulse #1, #2 | **Merged.** #96 `63e3f255`, after a review fix: a runner execution is reconciled only for a cycle granted to that runner. Pulse #1 `ee2cb284` and #2 `97b9cb42` after an independent review. **Security fixes landed first** (see below). Pulse now has macOS CI (`service-tests`) | Engine #96; Sector-Pulse #1, #2 |
| 4 | O1 Mac mini | **Stopped.** The Mac mini is not reachable from this MacBook Pro: the two `.local` SSH hosts are untrusted, and `10.10.1.214` timed out. **There is no read-only Brain-database identity**, so a parity run with read access needs a new service account or token. Steps written for the owner | Sector-Pulse #3 `docs/runbooks/O1_MAC_MINI.md` |
| 5 | Lake A1–A4 | **Merged** in order after review and green CI: #97 `734bed59`, #98 `895a18b9`, #100 `800627d9`, #99 `58f0878b`. The macOS swift cancellations on the first runs were runner cancellations; every rerun passed. Each branch had main merged in (no history rewrite) and its digests re-recorded. No deploy | Engine #97–#100 |
| 6 | Collector LaunchAgent | Written, but **macOS blocks launchd processes from `~/Desktop`** (EX_CONFIG / `operation not permitted`). The agent is disabled. The collector runs by hand again (about 2 min down, between cycles, none missed). The fix is Full Disk Access (owner security setting) or a path move | `wind-brain/closeouts/2026-11-03-collector-launchagent.md`; CG-3.1-12 |
| + | Readiness notes | Water Temp: a good Pulse fit, not ready (needs the Lake-style A1–A4 equivalents, and its dry run cannot read the previous state). Intelligence: last; needs SI-1 (a) first, because it writes the database in process | Sector_Ops #51 comment |
| + | #23 | Pulse-first line added to the roadmap | Sector_Ops #23 |

**Security fixes from the Pulse review (before merge)**
- **A sandboxed job could read Pulse's API token** and drive the local API. One route went through a crafted Engine path → `git status` outside the sandbox.
- **It could also read the owner's gcloud login and run `/usr/bin/security`.**
- **Fix:** the profile now denies reading the token, the approval key and `~/.config/gcloud`, denies running `/usr/bin/security`, and denies outbound traffic to the API port, even for networked jobs. `scrub_env` points `CLOUDSDK_CONFIG` at a nonexistent dir.
- **Verified** with the real `sandbox-exec`. Without the rules, the probe read the token, ran Keychain and listed gcloud. With them, all three are denied.
- **Defaults now off on fresh installs:** the scheduler, engine auto-fetch and automatic research. Saved configs keep their values.
- **Smaller fixes:**
  - Ops redacts `/tmp/` and `/home/` paths.
  - A hand-off bridge error is recorded as FAILED.
  - An artifact of another Brain is refused before any lease call.

**Checks**
- Engine #96 after its fix: platform 834, orchestrator 129, runner 4.
- Engine #102 (after main with A1–A4): platform 838, orchestrator 134, foundation/architecture/verification 295.
- Lake A3 on main with A4: contract `--check` matches the registry; Lake 63; foundation 295.
- Pulse:
  - main suite: 64 passed, 2 skipped;
  - #3: 73 passed, 2 skipped;
  - the real bridge against the Engine runner tool under the hardened sandbox: passed.
- Digests were re-recorded on every branch; `--check` OK.
- `research-check --closeout`: 0 findings.
- **Not done:**
  - Research backups to `gs://sector-research-backup` were **not written** (no cloud writes this run). They are listed in the closeout.
  - Auto mode refused a force-push, so branches were brought up to date by merging main.

**Not done / gated:** nothing deployed, enabled, resumed or granted. No token was created and nothing was written to a database.

**Cortex gaps:** CG-3.1-12 (the research home and runner checkouts under macOS-protected folders).
