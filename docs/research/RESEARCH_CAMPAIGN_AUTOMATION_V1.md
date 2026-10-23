# Eight-Brain research campaign automation V1 (2026-10-23)

This is the owner's verification mission: can one Claude Code session research, validate, package and clean up across all eight Brains, unattended? This document records what exists, what was added, and how a campaign is launched. Cloud Brain execution stays PAUSED (Cortex 2.7.0 PL-16); nothing here runs in the cloud or writes Firebase.

## The harness

`tools/research/campaign.py` (stdlib) is the deterministic spine. The coordinating Claude session drives it, and the session's agents do the research itself. It reuses what exists and adds no second orchestrator:

| Need | Reused |
|---|---|
| Per-Brain research folder | Cortex research layout assignments (RS-01) |
| Track order | each `brain.json` `operations.execution.dependsOn`: Intelligence after the five specialists; Depth and Vegetation after Lake |
| Validation and candidate scores | each Brain's **existing** evaluators, wrapped by `tools/research/adapters/run_adapter.py` and registered in `adapters.json` |
| Candidate packaging | `sector_brain_platform.knowledge_release` (the same digest-verified format as approved memory), approval `NOT_RECORDED` |
| Hygiene | Cortex retention classes, manifests, closeout sections (RS-02, RS-05); `cortex.py research-check --closeout` passes |

### Stages per track

Every stage is checkpointed atomically in `$SECTOR_RESEARCH_HOME/shared/campaigns/<id>/state.json`.

| Stage | What it does |
|---|---|
| discover | loads the manifest; classifies items by retention and folder; lists prior tasks, closeouts, candidates and shared evidence; loads the open gaps (`GAPS.json`, or reconstructed when missing); checks declared inputs (present / reconstructed / limitation) — see [RESEARCH_DISCOVERY_AUTOMATION_V1.md](RESEARCH_DISCOVERY_AUTOMATION_V1.md) |
| acquire | the Brain's discovery connectors download public evidence from allowlisted hosts, with provenance, registered in the manifest (the only stage with network access) |
| research | the Brain's research adapter runs (a BLOCKED adapter is recorded, not fatal); the offline discovery analysis generates findings with pre-declared thresholds; agent findings arrive via `submit` |
| validate | for every finding: schema check; evidence in the research home with a matching SHA-256; the Brain's validator metric compared with the declared threshold → VALIDATED or REJECTED (reason recorded). Nothing is approved |
| candidate | validated findings only → `<folder>/candidates/<id>/` as a release package (approval NOT_RECORDED), verified with `load_release`. It refuses to write into the Engine |
| score | the Brain's candidate-score adapter (non-authoritative); the local authoritative score artifacts are hashed before and after and must be identical |
| followup | weak areas (rejected findings, unmatched targets, too little evidence) re-open acquire..followup for a wider iteration, up to `maxIterations`; unreachable sources are a limitation, not a weak area |
| cleanup | deletes only the campaign-owned workspace (`analysis/tmp/<id>/`, owner marker, including read-only clone files); registers retained outputs in `manifest.json`; writes the RS-05 closeout |
| report | one `REPORT.md` / `report.json` for the whole campaign |

### Safety

- **Isolation:** research scripts that write into their root run against an APFS copy-on-write **clone** inside the workspace, so the real folders are only read.
- **No network:**
  - adapter subprocesses run with HTTP(S) proxies pointed at a dead port;
  - no gcloud configuration or Google credentials;
  - `BRAIN_TOKEN_MODE=disabled`;
  - RTDB URLs blocked.
- **Recovery:** rerunning `run` resumes; finished stages are skipped and an interrupted stage is re-run. Each stage has bounded retries (`maxAttempts` 2), a per-command timeout and bounded parallelism (`--parallel`). A failed track never stops the others.
- **Fixtures:** fixture findings are used only by `init --verification` campaigns, and are labelled `fixture: true`.

## Capability classification

Evidence: code, tests, and the 2026-10-23 dry runs.

| Capability | Status | Evidence / gap |
|---|---|---|
| Coordinating research across eight Brains | **IMPLEMENTED** (new) | campaign harness; dependency order; parallel tracks; two full eight-track runs |
| Discovering new sources | **MISSING as tooling** (agent work) | literature and data discovery is done by the session's research agents (web); there is no automated source crawler. The brief tells each agent where to save evidence and how to register it |
| Reusing previous research | **IMPLEMENTED** | discover stage plus brief: manifests, closeouts, prior candidates, shared evidence, `GAPS.json` |
| Validating findings | **PARTIAL** | the gate is automatic, but only against metrics the Brains' existing validators produce. New science needs a new deterministic validator (reviewed code) or is REJECTED. Depth field validation and Vegetation holdout have no data; the Intelligence ledger is empty |
| Updating evidence ledgers | **IMPLEMENTED** | manifest items and task records with SHA-256 and retention; closeouts |
| Developing candidate rules | **PARTIAL** | agents author rules as findings; the harness packages only validated ones. Brain-specific rule encoders (e.g. Fish adoption scripts) are ad-hoc campaign scripts |
| Recalculating scores | **PARTIAL** | computed for Fish (capability v2), Wind (capability v2), Depth and Vegetation (research maturity). Lake, Water Temp and Clarity scores are the values typed in their candidate builders; Intelligence has no candidate-score command. The authoritative scorer needs RTDB, so it is not run |
| Versioned knowledge candidates | **IMPLEMENTED** | `knowledge_release` package, digest-verified, approval NOT_RECORDED |
| Reviewing / promoting approved knowledge | **GATED, manual by design** | no tool, and none should self-approve. Promotion into `brains/*/runtime` and a release approval record are owner/reviewer decisions (M-3, G-1), then a normal Engine PR |
| Publishing operational metadata to Firebase | **IMPLEMENTED, gated and PAUSED** | orchestrator and scorer; global execution control PAUSED (PL-16); the campaign never writes Firebase |
| Cleaning temporary data | **IMPLEMENTED** | owner-marked workspace only; read-only clone files handled; foreign files untouched (tests, two dry runs) |
| Consolidated report | **IMPLEMENTED** | `REPORT.md` / `report.json` |
| Recovery after interruption | **IMPLEMENTED** | hard-kill tests (unit, and two eight-track runs killed mid-stage then resumed) |

## Known blockers outside the harness

These stop specific evaluators, not the campaign:

| Brain | Blocker |
|---|---|
| Wind | evidence regeneration needs `rows.pkl` in the local Wind cache (deleted); the scoreboard CLI looks for `lakes.json` in the wrong place (works as a module call); the scoreboard reads iOS-repo evidence |
| Water Clarity | R3.1 re-certification needs `stage_r31/cache/*.pkl` and the `geo` environment (missing); the national evaluation reads private data in the worktree `Sector_Engine-research` (not in the research home, DEV-02) |
| Lake | the hold-out reads `verified_bindings_v2.csv` and `lake_features.csv` from a hard-coded path in the main checkout, which exist only on branch `docs/lake-brain-research` |
| Lake, Water Temp, Intelligence | no `research/GAPS.json` |
| Environment | no local interpreter ships pytest plus numpy by default; the dry runs used a session venv (Python 3.12, numpy, pytest) |

## Launching the unified research campaign

1. **One-time environment.** Also set `SECTOR_WIND_STAGE3A_EVIDENCE` (Wind scoreboard evidence) and `SECTOR_CLARITY_PRIVATE_ROOT` (Clarity private research root); without them those two research adapters report BLOCKED instead of guessing. Create a venv with Python 3.12 plus `numpy` and `pytest`, then:
   ```
   export SECTOR_RESEARCH_HOME=<the Cortex research home>
   ```
2. **Initialize** the campaign (not `--verification`):
   ```
   python3 tools/research/campaign.py init --campaign <YYYY-MM-DD-name>
   ```
3. **Start ONE Claude Code session** in the Engine repository and ask it to run the campaign with a workflow ("use a workflow"). For each Brain, in dependency order, the session should:
   - (a) print the brief: `campaign.py brief --campaign <id> --brain <b>`;
   - (b) give it to one research agent, who works only in that Brain's research folder, saves and registers evidence, adds a deterministic validator to `run_adapter.py` when a new claim needs one, and writes `findings.json`;
   - (c) `campaign.py submit …`.

   Then the session runs `campaign.py run --campaign <id> --parallel 3`.
4. **Recover** from any interruption by rerunning `campaign.py run --campaign <id>`. Check progress with `campaign.py status`.
5. **Close.** Read `$SECTOR_RESEARCH_HOME/shared/campaigns/<id>/REPORT.md`. Packaged candidates wait for review; promotion into approved memory is a separate, gated Engine change.
