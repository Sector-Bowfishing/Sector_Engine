# Session record: Generation Brain (dam releases and generation)

Standards: Rehtac Cortex 3.1.6 @ a785035 (read from a clean checkout at the pin; the session's own Cortex location was at ecaef70, 3.1.2, and was not modified), pack sector/engine. Date: 2026-11-22. Branch: `feat/generation-brain-2026-11-22` (off main 0fc0682a).

## Scope
Owner decision (Michael, chat 2026-11-22 19:37Z, Sector_Ops #51 comment 7084558461): build the Generation Brain; real measured or official operator data only. Owner source-access rule (comment 7076252747). Standing approvals: branch, commit, push, PR. Not done here: merge, deploy, IAM, rules, enabling execution.

## Done
- `brains/generation`: brain.json (CALIBRATION, customer publication off), operating contract, README, `generation-publication-v1` (derived from the Publisher registry) and `generation-dam-state-v1` schema, runtime (TVA / CWMS / SWPA / RISE / USGS readers, access-gated HTTP, assembly, adaptive freshness, state, publish, writer, Ops summary, knowledge loader, artifact builder), candidate knowledge release `generation-knowledge-candidate-2026-11-22.1` (dam catalog of the 401 dam lakes + source-access list), research tooling (catalog builder, release writer, evidence records), research CHARTER / GAPS, 112 tests on labelled hand-built fixtures, Kit V1 certification.
- Registration DISABLED: control manifest (PARKED, executionTarget none, MANUAL/ADMIN triggers), `keys.BRAINS` + Swift `BrainPlatform.brains`, Publisher registry, stable ids, providers, cutover order (BLOCKED), identity-split and publisher security plans (plan documents; no IAM change), engineering-status inputs (memory matrix, brain detail, decisions G-2, D-G, D-H).
- Docs: `docs/brains/GENERATION_BRAIN_PLAN.md`, `docs/brains/GENERATION_BRAIN_PROVIDERS.md`; Cortex gap CG-3.1-19; navigation refresh.

## Verification
Python suites: all `brains/*` (9 packages), `jobs/brain_platform`, `jobs/brain-orchestrator`, `jobs/brain-scores`, `jobs/brain-publisher`, `tools/architecture`, `tools/brain_certification`, `tools/ops/tests`, `tools/runner`, `tools/cutover`, `tools/deploy`, `verification` pass locally. Two `tools/research` tests that rely on read-only file modes fail identically on main when run as root (environment, not this change). Swift is not available here (CI runs it; the only Swift change is one dictionary entry). Release manifest `--check` OK; architecture report: no new findings. Engineering-status digests regenerated.

Not verified: no source was read live (agency hosts unreachable from this session); fixtures are hand-built and labelled.

## Decisions for Michael (batched)
- G-2: approve a Generation knowledge release (after D-G and the validation week).
- D-G: TVA robots.txt and the iOS "TVA blocks automated access" note; SWPA (energy.gov) robots.txt and terms.
- D-H: Cortex release adding Generation as a target Brain and moving dam releases from Lake (CG-3.1-19).
- Enabling: an execution target (in-process or a job; a job costs money) and an execution-control entry.

## Not changed
Live systems, schedulers, execution control, IAM, rules, scores, Lake Brain behaviour, customer paths.
