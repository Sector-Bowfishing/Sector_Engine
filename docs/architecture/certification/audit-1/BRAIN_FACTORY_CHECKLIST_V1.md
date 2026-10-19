# Brain Factory Checklist V1

Use with `BRAIN_FACTORY_V1.md`. Do the phases **in order**; phases 0–2 are read-only. A box is ticked only when the evidence named beside it exists. `{b}` = brain directory, `{id}` = machine `brainId`. Commands run from the repo root; use Python 3.12 with `pytest` plus the Brain's `runtime/requirements.txt`.

## Phase 0 — Baseline and gap audit (no changes)
- [ ] `git fetch`; record actual `origin/main` SHA; work in a new worktree/branch (never main)
- [ ] **Gap audit written before any implementation:** `docs/architecture/certification/{b}/{BRAIN}_GAP_AUDIT_V1.md` (model: `fish/FISH_GAP_AUDIT_V1.md`) — where the code lives on main **and on every branch** (ahead/behind counts, pushed or local-only), what is live, what is research
- [ ] Branch/lineage decision recorded for Michael (Fish "Decision A": merge the adoption branch with history, no rebase/force) — **do not choose silently**
- [ ] Any pre-recorded hard blocker for this Brain checked (Clarity: **D4**, `REPOSITORY_AUDIT_DECISIONS.md` RA-18)
- [ ] Score BEFORE recorded (value, `scoreVersion`, rubric sha); `python3 verification/integration/score_baseline.py --check`
- [ ] Architecture baseline recorded: `python3 tools/architecture/report.py --legacy --baseline` (KNOWN/NEW/RESOLVED)

## Phase 1 — Canonical location and identity
- [ ] `{id}` unchanged; dir→id in `tools/architecture/stable_brain_ids.json` (exists for Clarity)
- [ ] `git mv` runtime into `brains/{b}/runtime/` (history preserved); `jobs/<old>` becomes a pointer README only
- [ ] exactly one production copy of every module (tree-wide test)
- [ ] `BRAIN_OPERATING_CONTRACT.md` — 19 sections (inv 4); ownership says what the Brain does **not** own
- [ ] `README.md` (≤ 1 page)

## Phase 2 — `brain.json` and honest declarations
- [ ] `brain.json` validates `contracts/schemas/brain.schema.json`; `lifecycle` equals the live value (never promoted by having a contract)
- [ ] `runtime.kind` is `job` (Cloud Run — start by job name; needs no Orchestrator code) or `in-process` (**stop: needs the registry-derived runner, debt D-1; escalate before adding a third path shim**)
- [ ] `consumes`/`providers`/signals list **only what the runtime really reads** — an empty list is valid; no REQUIRED edge "because the template had one"
- [ ] `control_manifest.json` entry exists, its `dependencies` ⊆ `brain.json.consumes` (inv 17); `lifecycle` agrees by hand (no gate: D-9)
- [ ] `authorizedConsumers` lists real readers only
- [ ] `researchWorkspace.workspaceId` is a logical id; no absolute path anywhere

## Phase 3 — Artifact, contract, lineage
- [ ] `runtime/publish_artifact.py` builds ONE `publish-artifact-v2` bundle; chooses `require_freshness` **or** `require_release`
- [ ] `{id}_specs()` / `{id}_bundles()` added to `publisher/registry.py` and `default_registry()` — **data only; `validate.py`/`plan.py`/`paths.py` untouched**
- [ ] `contracts/{id}-publication-v1.json` generated: `PYTHONPATH=jobs/brain_platform python3 brains/{b}/contracts/describe_contract.py --write` then `--check` (copy Fish's script; D-7b)
- [ ] `ConsumptionRecorder` on the Brain's RTDB client; `consumed[]` recorded; absent when unknown
- [ ] semantic fingerprint stable under new `executionId`/timestamps (test); volatile fields declared as data

## Phase 4 — Health, freshness, Publisher shadow
- [ ] healthV1 renders the Brain from engine truth alone (`dependencyHealth`, `freshnessHealth` honest; UNKNOWN stays UNKNOWN)
- [ ] `stalenessModel` chosen from `TIME|VERSION|FINGERPRINT` and stated; nothing derived from `lastSuccessfulRun`
- [ ] Publisher shadow handoff → `SHADOW_READY`, `live_mutations == 0`; re-publish → `SKIP`
- [ ] rejection tests: wrong brain, wrong schema, foreign path, reserved path, node replacement, missing release, production lifecycle without `approvalRef`; typed deletes; null ≠ delete

## Phase 5 — Direct-write isolation
- [ ] `docs/architecture/certification/{b}/{BRAIN}_DIRECT_WRITE_AUDIT.md`: every write site classified `LEGACY` / `SHADOW_ONLY` / `BLOCKER`
- [ ] AST test pins the exact set of write sites (model: `test_no_unauthorized_production_write_in_the_fish_runtime`)
- [ ] `publisherRequired.cutoverStatus` = `SHADOW` (inv 10 will fail if set to `CUTOVER_COMPLETE` while a writer remains)
- [ ] **no write door removed or added**; cutover is a separate approved task

## Phase 6 — Research and science
- [ ] research workspace = structure only; legacy research **inventoried, not moved**; `research/GAPS.json` validates; no raw data in Git (inv 16)
- [ ] runtime works with no workspace, no `HOME`, no `docs/` (staged-layout test)
- [ ] **science preserved:** golden/equivalence produced from the *pre-move* tree matches byte-for-byte (or documented expected diffs)
- [ ] no private data (per-lake presence, private locations) in the public package (test)

## Phase 7 — Score, tests, gates
- [ ] score AFTER = BEFORE, rubric hash unchanged; `{BRAIN}_SCORE_RECONCILIATION.md` states what the score does and does not measure
- [ ] certification suite covers every proof in `BRAIN_FACTORY_V1.md` §7 — **use BRAIN_CERT_KIT_V1** (`tools/brain_certification`): a `BrainCertSpec` + `make_certification_tests`, all proofs and mutation tests green; do not copy another Brain's suite
- [ ] `cd brains/{b} && python -m pytest -q` green; `jobs/brain_platform`, `jobs/brain-orchestrator`, `jobs/brain-scores`, `tools/architecture`, `verification`, `brains/wind`, `brains/fish` green and unchanged
- [ ] `python3 tools/architecture/report.py --legacy --baseline`: **NEW 0**; nothing RESOLVED away without an explanation
- [ ] CI `registered-brains` loop picks the Brain up (it loops `brains/*/brain.json`); legacy-job CI list updated only if the old `jobs/` dir had one

## Phase 8 — Closeout (stay SHADOW)
- [ ] certification report with the §9 status word; **no unqualified "certified"**
- [ ] hack budget listed: each exception `LEGITIMATE_DOMAIN_SPECIFIC` / `TEMPORARY_REPOSITORY_MIGRATION` / `PLATFORM_GAP` / `UNNECESSARY_HACK` (target 0)
- [ ] lifecycle and `cutoverStatus` unchanged; science `NOT_VALIDATED`; no production promotion
- [ ] nothing deployed, scheduled, published, written to `sector-brain`, or changed in Sector Ops / customer surfaces
- [ ] draft PR; handoff written under `Sector Handoffs/Sector Engine/<Brain>/` and indexed (append-only)
- [ ] **STOP.** Research, calibration, production-readiness and cutover are separate tasks.
