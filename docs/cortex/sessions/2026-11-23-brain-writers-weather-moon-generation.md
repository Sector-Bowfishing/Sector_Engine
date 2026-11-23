# Session record: gated live writers for Weather, Moon and Generation (prepared, all DISABLED)

Standards: Rehtac Cortex 3.1.6 @ a785035 (extracted read-only with `git archive` into a scratch directory, so the briefing reports "uncommitted (no-git)"; content is the pinned commit), pack sector/engine. Date: 2026-11-23. Branch: `feat/brain-writers-weather-moon-generation-2026-11-23` off origin/main 6255b6e2. Cloud session; only work covered by the standing approvals (branch, commit, push the branch, open a PR). The task brief named pin ecaef70; this repository's CLAUDE.md pins a785035, which was used.

## Scope
Prepare the live-writer path for the three Brains registered DISABLED on 2026-11-22 so that turning each on is configuration plus owner commands. Not done and not in scope: any deploy, cloud job, IAM, execution-control change, manifest activation, release approval, database write, source-access change.

## Pattern followed
Depth and Generation (the platform client `RtdbWriter`, `--write` gated by an APPROVED release then an operator-intent variable, exit 2 / exit 3), Water Clarity (`deploy/Dockerfile` + `deploy-job.sh` with `--stage-only` and an owner-approval variable), Water Temp (own service account, no fallback to brain-writer, `run.invoker` for brain-orchestrator, no scheduler). The Publisher CENTRAL path (sealed artifacts) stays a later, separately approved cutover: all three already have contract-only `publish_artifact.py` builders.

## Done
- Weather: `sector_weather/writer.py` (RtdbWriter, DryRunWriter), `knowledge.require_approved`, `run.py --write` (approved release, `WEATHER_WRITE_APPROVED=1`, dry-run inputs refused, reads each lake's published state for the planner), `publishMode` parameter (unchanged dry-run value). Kit P14 write sites pinned to the writer.
- Moon: `writer.RtdbWriter`, `lakes.require_approved`, `run.py --write` (approved release, `MOON_WRITE_APPROVED=1`, reads each lake's Weather state from the Brain RTDB and uses it only within the dependency's maxAgeHours 3), `publishMode` parameter. Kit P14 now also pins the live write site.
- Generation: the gated writer already existed; added the live write-set test only. D-G and D-I stay blockers; `source_access.json` unchanged.
- Each Brain: `deploy/Dockerfile` + `deploy/deploy-job.sh` (refuses without `MICHAEL_APPROVED_<BRAIN>_DEPLOY=yes`; own service account required; no scheduler; write intent off unless passed).
- Orchestrator: `PLANNED_EXECUTORS` + `planned_executors(manifest)`: an executor joins only when the manifest target is exactly the planned Cloud Run job with `startedByOrchestrator` true (none today). Edge attribute `deferIfUpstreamStarted` (default true, behaviour unchanged for every existing edge).
- Control manifest (all inert): `plannedJob` for Moon and Generation; Moon accepts `DEPENDENCY_CHANGED`, its weather edge sets `deferIfUpstreamStarted: false`; Weather's fingerprint adds `lastSuccessfulRun`. Notes updated. Moon `brain.json` `dependsOn` ["weather"].
- Docs: per-Brain "how to turn it on" (WEATHER_BRAIN_PLAN §6.1, MOON_BRAIN_PLAN §7.1, GENERATION_BRAIN_PLAN §6.1); stale "no live writer" statements corrected in contracts (describe_contract --check passes), operating contracts and READMEs.

## Findings
- F1 (decision for the owner): Weather in a Cloud Run job has an ephemeral point cache, so each run re-resolves NWS points and stations; measure in plan step 1 before the 2 USD/month cap is relied on.
- F2: the Orchestrator's M08 dispatch refuses all three (UNREGISTERED_BRAIN) until a Cortex release registers them and `data_ownership.json` is re-synced. A second, independent lock; listed as a turn-on step.
- F3 (CG-3.1-21): an every-grant upstream would starve a DEPENDENCY_CHANGED consumer; fixed by the opt-out edge attribute, tested both ways.
- The registry field `enabled` stays a code constant `false` in all three (Generation's precedent); the activation PR should decide whether to derive it.

## Verification
All affected suites pass (counts in the PR); Kit V1 certification suites pass; `describe_contract.py --check` for all three; `ops-check` 0 findings; `data-check` 541 vs 540 on base (the one new line is Weather's live read of `/lakes/{k}/states/weather`, within the known CG-W-1 registry gap); `research-check` unchanged (85); `mission-audit` unchanged (UNREGISTERED_BRAIN x3 + the legacy Fish split); engineering-status digest regenerated and `--check` passes.

## Standing memory checks (weather, moon, generation)
1 storage: PACKAGED_IN_IMAGE releases, unchanged, staged into each job image by `deploy-job.sh` (PASS). 2 developer-machine scan: no new paths; deploy scripts use repo-relative staging (PASS). 3 versioning: release digest verified on load, unchanged (PASS). 4 unavailable/unapproved: refuses, tested (PASS). 5 separation: approvals stay NOT_RECORDED; Weather's chat approval (Sector_Ops #51 comment 7085207021) deliberately NOT recorded here (PASS). 6 Pulse: no Pulse dependency (NOT_APPLICABLE).

## Closeout (DEV-08)
One worktree created for this task: `/home/claude/se_wt` (branch above). Kept until the PR merges (its commits are pushed). Scratch only: the extracted Cortex pin and staged build contexts under the session scratchpad (DISPOSABLE). No research data created or downloaded.
