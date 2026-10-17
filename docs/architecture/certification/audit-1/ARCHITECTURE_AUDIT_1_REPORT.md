# Architecture Audit #1 — Wind + Fish Reusable Brain Factory

**Status: `ARCHITECTURE_AUDIT_1_PASS_WITH_NON_BLOCKING_DEBT`** · verdict word: **PASS_WITH_NON_BLOCKING_DEBT** · parallel lanes: **YES_WITH_CONDITIONS** (`PARALLEL_LANES_READINESS.md`).
**Audit of:** `origin/main` `8c2e22ae698fbcbdea0a8e78a593fe2f2fd78885` (verified by `git fetch`; equals the expected SHA). **Branch:** `audit/brain-factory-v1`. **Date:** 2026-10-17.
Companions: `BRAIN_FACTORY_V1.md` (the definition), `BRAIN_FACTORY_CHECKLIST_V1.md` (the procedure), `TECHNICAL_DEBT_AFTER_AUDIT_1.md`, `PARALLEL_LANES_READINESS.md`.

This is an audit. No Brain, platform code, scheduler, Orchestrator, Publisher mode, production node, Sector Ops or customer surface was changed. Evidence is the repository plus local test runs (§9). Where a claim rests on a prior session's handoff rather than on something re-verified here (the deployed Orchestrator image, live score values), it says so.

## 1. Answer

**Did Wind + Fish prove a reusable Brain factory? Yes, for everything that crosses the Publisher / lineage / health / registry / `brain.json` boundary. Not yet for the surrounding plumbing.**

Two structurally different Brains (Wind: Cloud Run job, scheduled, 3 providers, lake-scoped, observation-time; Fish: in-process, manual, no providers, species-keyed, version-driven, private knowledge release) were put through the same standard. The Publisher, lineage, healthV1, registry and `brain.json` schema frameworks took Fish **without a framework change** (one-line owner-precision fix in `paths.foreign_owner`, reviewed in §6). That is the evidence that matters and it is real.

What is *not* yet a factory: each Brain still hand-edits ~8 platform files, hand-copies ~44 certification tests and a `describe_contract.py`, and an in-process Brain needs a path-specific Orchestrator shim. None of that blocks Brain #3 (Water Clarity is a Cloud Run job, so it takes the Wind path, not the Fish path), none corrupts Brain truth, and none requires a platform redesign first. All of it is bounded, owned and has a trigger (`TECHNICAL_DEBT_AFTER_AUDIT_1.md`). Hence **PASS_WITH_NON_BLOCKING_DEBT**, not PASS and not FAIL_BLOCKING.

**An honesty finding that is not debt in the code but in the vocabulary.** Neither Wind nor Fish holds `ARCHITECTURE_CERTIFIED_V1` as `BRAIN_CERTIFICATION_V1.md` defines it. That status needs exit evidence A–J including **F (tested write-denial under rules and IAM)** and a live Publisher; Wind's own status is `PARTIAL — LIVE CUTOVER PENDING` with F = FAIL and `PRODUCTION_WRITE_SECURITY_GATE_OPEN`, and Fish's is `FISH_BRAIN_ARCHITECTURE_V1_READY_FOR_REVIEW`. What both achieved is **structural certification** (repo layout, contracts, shadow Publisher, lineage, health, tests). The status ladder has no name for that. This audit names it (`STRUCTURALLY_CERTIFIED_V1`, `BRAIN_FACTORY_V1.md` §9) so nobody reads "certified" as "secured/production-ready". The Publisher/IAM work is correctly a separate lane.

## 2. Pass conditions (mission list)

| # | Condition | Result | Basis |
|---|---|---|---|
| 1 | Wind and Fish share a coherent structural standard | **MET** | §3: 24 of 30 dimensions STANDARDIZED or domain-only; same `brain.json` schema, 19-section contract, `publish-artifact-v2`, semantic fingerprint v2, healthV1, lineage |
| 2 | Differences are legitimate or bounded transition debt | **MET** | §4: 0 differences classed as platform failure; 4 classed `PLATFORM_GAP`, all non-blocking |
| 3 | No platform blocker prevents Brain #3 | **MET** | §7 Factory test; Clarity-specific blocker D4 is an adoption decision, not a platform gap |
| 4 | Fish research can proceed without redesigning Fish | **MET** | §8 |
| 5 | Water Clarity can start from the same factory | **MET, with one precondition** | D4 (live job source off-main) is a pre-recorded hard *Clarity-phase* blocker for **adoption**, not for starting the gap audit |
| 6 | health / lineage / Publisher contracts generalize | **MET** | Fish: zero Fish-specific code in healthV1 or lineage; Publisher second registration is data |
| 7 | No NEW architecture violations | **MET** | `report.py --legacy --baseline`: KNOWN 21 · NEW 0 · RESOLVED 0; invariants 1–7, 9–17 PASS; inv 8 = 4 baselined findings (2 Wind, 2 Fish) |
| 8 | Known debt has ownership and triggers | **MET** | `TECHNICAL_DEBT_AFTER_AUDIT_1.md` |
| 9 | Deployment/cutover separable from structural certification | **MET** | §5-F, §5-G; invariant 10 mechanically enforces the ordering |
| 10 | No large cleanup phase required before parallel work | **MET** | 0 P0 items; P1 items are scheduled to *triggers*, not to a pre-phase |

No FAIL condition holds: Fish needed no fundamental special-case architecture; dependency ownership is unambiguous (§5-D); artifact/Publisher/health/lineage do not depend on Wind; Fish research needs no structural redesign; no known flaw risks corrupting future Brain truth (the closest candidates — legacy direct-write doors, §5-F, and platform-authored edges, §5-D — are classified, guarded and test-pinned).

## 3. The 30 dimensions

Class legend: **STD** STANDARDIZED · **GEN-INC** GENERIC_BUT_INCOMPLETE · **DOM** DOMAIN_SPECIFIC · **TRANS** TRANSITIONAL_DEBT · **GAP** BLOCKING_PLATFORM_GAP · **SPECIAL** UNNECESSARY_SPECIAL_CASE. **No dimension is GAP and none is SPECIAL.** "Enforced" = a test or architecture invariant fails if it regresses.

| # | Dimension | Class | Mechanism today | Enforced? |
|---|---|---|---|---|
| 1 | Canonical repository location | **STD** | `brains/<dir>/`; `stable_brain_ids.json` maps dir→brainId (`fish→biological-state`); legacy `jobs/*` = pointer README | inv 1, 3; per-Brain `test_canonical_package_location…` (Fish) / `test_wind_package.py` (Wind) |
| 2 | Brain identity | **STD** | stable machine `brainId`, never renamed; UUIDs for execution/publication | inv 2, 3 |
| 3 | `brain.json` / manifest | **STD** | `contracts/schemas/brain.schema.json`, validated by `report.py` (inv 1, 5, 6) | inv 1 |
| 4 | Ownership | **GEN-INC** | operating contract §4–5 (enforced: 19 sections) + `ownership.py` path table + `tools/architecture/ownership_map.json`; the latter two are per-Brain hand edits | inv 4; ownership table pinned by Publisher tests |
| 5 | Lifecycle | **GEN-INC** | declared in three places — `brain.json`, `control_manifest.json`, artifact lineage — with **no generic drift gate** (only Brain-specific assertions, e.g. Fish `BRAIN["lifecycle"]=="PROFILED"`) | Brain-specific only |
| 6 | Input declaration | **STD** | `consumes[]` incl. legal empty list; Fish `[]` is valid and truthful | inv 17 |
| 7 | Dependency declaration | **STD** | Brain-owned `brain.json`; platform-manifest edges must be a subset of declared (drift gate) | inv 17; `DD.drift == []` |
| 8 | Provider declaration | **STD** | `providers[]` ⊂ `providers/PROVIDERS.json`, consumer authorized | inv 12 |
| 9 | Signal declaration | **STD** | Signal Registry; none fabricated (Fish) | inv 17; `test_no_fabricated_signal_declarations` |
| 10 | Registry declaration | **GEN-INC** | generated Brain registry + `control_manifest.json` brain entry (platform-authored, hand-edited per Brain) | inv 17 (dependencies only) |
| 11 | Actual-consumption lineage | **STD** | platform client `ConsumptionRecorder`; `consumed[]`; own-state reads excluded; absent ≠ `[]` | per-Brain tests (Fish 3) + platform tests |
| 12 | Artifact schema | **STD** | `publish-artifact-v2` envelope + `<brain>-publication-v1` contract derived from the Publisher registry | `describe_contract.py --check` (per-Brain copy) |
| 13 | Artifact builder | **GEN-INC** | each Brain writes `runtime/publish_artifact.py`; no shared builder base (and none is needed — domain content) | per-Brain tests |
| 14 | Semantic fingerprinting | **STD** | `sector-semantic-fingerprint-v2` in the Publisher; Brain supplies no hashing | Publisher tests; per-Brain stability tests |
| 15 | Volatile-field handling | **STD** | `VolatileContract` in the registry; Fish added a volatile *path family* without framework change | Publisher tests |
| 16 | Publisher registration | **GEN-INC** | `SchemaSpec`/`BundleSpec` as data, but registered by editing `publisher/registry.py` in the platform | `test_publisher_<brain>_registration.py` per Brain |
| 17 | Publisher path ownership | **STD** | `brainId → schema → path family`; typed rejection codes (`CROSS_DOMAIN_PATH`, `RESERVED_PATH`, …) | Publisher + per-Brain rejection tests |
| 18 | Direct-write isolation | **GEN-INC** | classified (`LEGACY`/`SHADOW_ONLY`/`BLOCKER`); Fish has an AST test pinning the exact write-site set; **Wind has no equivalent AST pin** (its writer is traced in `WIND_READER_WRITER_TRACE.md`) | inv 10 (cutover ordering); Fish AST test only |
| 19 | healthV1 compatibility | **STD** | zero Brain-specific code; `UNKNOWN` honest | platform health tests + Fish `test_health_v1_*` |
| 20 | Freshness semantics | **GEN-INC** | `STALENESS_MODEL = TIME|VERSION|FINGERPRINT` exists in the registry envelope; the consumer-side health reader honors an owner's `stale`/`freshnessStatus` verdict but a VERSION-basis owner has no documented, explicit statement (§5-B) | Wind: `lastSuccessfulRun≠freshness` tests; Fish same |
| 21 | Execution model | **GEN-INC** | `runtime.kind ∈ {job, in-process}`; Cloud Run jobs started by **job name**; in-process Brains started **by directory path** (§5-A) | `report.py` inv 6 (entrypoint exists) |
| 22 | Orchestrator integration | **GEN-INC** | `EXECUTORS` dict + `control_manifest.json` + `jobs.py`/`keys.py`/`scoring.py` per-Brain entries (§5-A) | orchestrator tests (36) |
| 23 | Runtime packaging / staging | **TRANS** | Wind: own `deploy/`; Fish: `deploy-job.sh` re-stages `brains/fish/runtime` under legacy `jobs/biological-brain` | staged-layout test (Fish `…no_research_workspace_no_home_and_no_repo_docs`, Wind `test_wind_package.py`) |
| 24 | Research / runtime separation | **STD** | `brains/<b>/research/` metadata only (GAPS/MANIFEST) + private workspace by logical id | inv 9, 16; per-Brain tests |
| 25 | Score semantics | **GEN-INC** | `SCORING_SEMANTICS.md` defines six concepts; `ENGINE_READINESS_SCORE` still carries a different meaning per Brain (§5-C) | `score_baseline.py --check` (BEFORE=AFTER) |
| 26 | Architecture certification tests | **GEN-INC** | exist for both, but **hand-copied per Brain**, not a shared kit | per-Brain suites; CI `registered-brains` loop is generic |
| 27 | Science-preservation tests | **DOM** | Fish: golden from the pre-move tree (2 bundles × 9 payload kinds); Wind: equivalence capture vs legacy writer. Method is general, content is domain | per-Brain |
| 28 | Regression coverage | **STD** | CI `registered-brains` loop runs `pytest` in every `brains/*/` that has `brain.json`; Wind package gates; platform suites | CI |
| 29 | Cost / scheduler posture | **STD** | pre-production cost freeze; scheduler PAUSED; Brains register as SHADOW; `check_preproduction_schedules.py` | orchestrator preflight |
| 30 | Customer-publication boundary | **STD** | `customerIntegrationMode: none`; inv 11; Publisher has no live mode | inv 11; `PublisherMode` has no live member |

## 4. Wind vs Fish

`IS DIFFERENCE LEGITIMATE?` — **D** = domain difference · **T** = bounded transition (repo-migration or pre-cutover) · **P** = platform gap (non-blocking). `ACTION` points at `TECHNICAL_DEBT_AFTER_AUDIT_1.md` ids.

| # | Dimension | WIND | FISH | SHARED ABSTRACTION | DIFFERENCE | LEGIT? | ACTION |
|---|---|---|---|---|---|---|---|
| 1 | Location | `brains/wind`, dir = id | `brains/fish`, dir ≠ id (`biological-state`) | Standard Brain Package, `stable_brain_ids.json` | name mapping | D | none |
| 2 | Identity | `wind` | `biological-state` (human "Fish") | stable brainId | none structural | D | none |
| 3 | brain.json | job, schedule `staleHours 6`, 1 consume, 3 providers | in-process, manual, `consumes []`, `providers []`, `score.rubricRef` | one schema | empty arrays legal | D | template shows only the Wind-ish shape (T-3) |
| 4 | Ownership | lake-scoped domain truth | species-keyed knowledge; **species identity not owned** | contract §4–5 | Fish carries identity it does not own | T (Species Registry empty) | D-6 |
| 5 | Lifecycle | CALIBRATION | PROFILED | LIFECYCLE_MODEL | different stage | D | D-9 (drift gate) |
| 6 | Inputs | registry `lakes` REQUIRED | none | `consumes[]` | Wind consumes, Fish does not | D | none |
| 7 | Dependencies | platform edges `[]` | 4 invented edges found and retired | drift gate (inv 17) | Fish exposed the problem; gate worked | T | D-5 |
| 8 | Providers | 3 NOAA/IEM | none | PROVIDERS.json | provider-driven vs not | D | none |
| 9 | Signals | none | none | Signal Registry | — | — | none |
| 10 | Registry | manifest entry, TIME 1.5 h | manifest entry, VERSION | control manifest | staleness model | D | D-9 |
| 11 | Lineage | external producer (provider entries from state provenance) | platform-client recorder; `consumed []`; private release is lineage identity | `consumption-lineage-v1` | producer type | D | none |
| 12 | Artifact schema | `wind-publication-v1`, 5 sections, `require_freshness` | `fish-publication-v1`, 2 schemas, `require_release` | `publish-artifact-v2` | freshness-keyed vs release-keyed | D | none |
| 13 | Builder | `sector_wind/…/artifact` | `runtime/publish_artifact.py` | Publisher `validate/plan` | domain content | D | none |
| 14 | Fingerprint | v2; hourly `observationTime` material? (open Wind decision) | v2; versions/`lastRunAt` volatile | v2 | what is material | D | none |
| 15 | Volatile | field-level | field-level **+ path family** (activity events) | `VolatileContract` | Fish needed family-level | D (generic, no framework change) | none |
| 16 | Publisher registration | `wind_specs/bundles` | `fish_specs/bundles` | `Registry` | both hand-registered in `registry.py` | T | D-7 |
| 17 | Path ownership | 12 families | 5 families + typed DELETE | `PathFamily` | `foreign_owner` precision fix | D (generic) | none |
| 18 | Direct writes | `writer.py` + `wind-hourly` (traced, compat table) | one site `run.py --write`, AST-pinned | write-site classification | Fish AST pin has no Wind twin | T | D-8 |
| 19 | healthV1 | works | works with zero code; deps SATISFIED/freshness UNKNOWN | `brain-health-v1` | — | — | none |
| 20 | Freshness | observation-time (`staleAfterHours`) | version | `stalenessModel` | basis | D | D-4 |
| 21 | Execution | Cloud Run job; Orchestrator does **not** start it (`NOT_STARTED_HERE`: scheduler-owned) | in-process by dir path | executor registry | job-name vs path | T/P | D-1 |
| 22 | Orchestrator | none needed | `_fish_runtime_dir`, `EXECUTORS` entry | `EXECUTORS` | per-Brain code for in-process only | P | D-1 |
| 23 | Packaging | own `deploy/` image | re-staged into orchestrator image | staging | different image | T | D-2 |
| 24 | Research split | `research/tools` collector (live cutover done) | structure only, legacy data inventoried | workspace by logical id | Wind has live research tooling | D | none |
| 25 | Score | `wind-certification-rubric-v1` (3.3), certification-weighted; stale 3.1 mirror + BWIS nested | `biological-state-score-v1` (4.0) live-fact scorer | `/scores/{id}` canonical | rubric meaning | P | D-3 |
| 26 | Cert tests | `test_publish_artifact.py` 24 functions + package gates | `test_fish_certification.py` 33 functions → 44 cases (+3 Publisher registration tests) | none shared | hand-copied | P | D-7b |
| 27 | Science preservation | legacy-writer equivalence | pre-move golden | golden/equivalence | method same | D | none |
| 28 | Regression | 110 passed (16 network deselected) | 285 passed, 2 skipped | CI loop | — | — | none |
| 29 | Cost posture | scheduler ENABLED (wind-hourly, untouched) | none; manual | cost freeze | existing job vs none | D | none |
| 30 | Customer boundary | none; customers get Open-Meteo | none | `customerIntegrationMode none` | — | — | none |

**Reading the table.** Every difference is either a genuine domain difference (consumes vs not; provider-driven vs not; observation-time vs version; lake-scoped vs species-keyed) or bounded transition (the orchestrator shims, species identity, legacy write door, platform edges). The four items classed **P** (21–22 orchestrator path, 25 score meaning, 26 tests hand-copied, 16 registration by file edit) are real platform scalability gaps; none prevents Brain #3.

## 5. Critical friction list

### A. Orchestrator executes Brains by path — **acceptable transition debt; non-blocking for Brain #3; becomes a blocker for the next *in-process* Brain**
Evidence: `orchestrate.py::EXECUTORS` has `"biological-state": {"kind": "in-process", "dir": _fish_runtime_dir()}` and `sector-intelligence` the same shape by sibling-dir path; Cloud Run Brains (`lake-brain`, `water-temp`) are started by **job name** and carry no path; `wind` and `water-clarity` are `NOT_STARTED_HERE`. `deploy-job.sh` special-cases `biological-brain` → `brains/fish/runtime`. `runtime/brain_platform.py` is a Fish-local resolver.
So the per-Brain hack is **not** "every Brain" but **every in-process Brain** — currently Fish and Sector Intelligence, plausibly Depth/Vegetation later. Water Clarity is a Cloud Run job and `MANUAL by decision`, so it needs *no* Orchestrator code to be structurally certified. The correct target is a registry/manifest-derived runner: `brain.json.runtime.{kind,entrypoint}` already carries everything needed (`brains/fish/runtime/run.py`), so the information exists and only the consumer is missing. **Not implemented here**; it is not a blocker to Brain #3. Trigger: *before the next in-process Brain is registered* (D-1, P1).

### B. VERSION-basis freshness — **non-blocking; Water Clarity and Fish research both proceed**
The vocabulary is further along than the Fish report says: `enums.STALENESS_MODEL = (TIME, VERSION, FINGERPRINT)`, `control_manifest.json` already has `biological-state.freshness.stalenessModel = VERSION`, `freshness.freshness()` emits `stale:false` and no `freshUntil` for non-TIME models, and `dependency_health._freshness` accepts an owner's `stale:false` as an `OWNER_VERDICT` FRESH. The real gap is narrower: (i) the Fish artifact does not emit that owner statement, so a consumer sees `UNKNOWN`; (ii) `stale:false` means "not stale by age", which is not the same claim as "fresh as of release R" — the platform has no documented *basis* word beside the timestamps. Recommendation: do **not** invent a new vocabulary; add one owner-published field `freshnessBasis ∈ {OBSERVATION_TIME, SOURCE_TIME, VERSION, STATIC_REFERENCE}` mapped 1:1 onto the existing `stalenessModel` + `ageBasis` words, and let VERSION owners publish `{freshnessStatus: FRESH, freshnessBasis: VERSION, release: R}`. Water Clarity is TIME-based (`staleAfterHours 26`), Fish research changes the bundle not the statement. Trigger: *first downstream consumer of a VERSION-basis Brain goes beyond UNKNOWN* — i.e. Sector Intelligence certification (D-4, P2).

### C. Mixed ENGINE_READINESS_SCORE — **misleading in meaning, not a blocker**
Verified: Fish's number is a live-fact scorer over nine dimensions mixing architecture (`registryCompleteness`, `productionIntegration`), science (`knowledgeDepth`, `evidenceQuality`) and product (`biologicalStateImpl`), capped at 4.0 by the *product* gate `biologicalState = NOT_STARTED`; Wind's rubric is certification-focused; Wind additionally nests BWIS and mirrors a stale 3.1 (documented, unfixed). So the same label means different things per Brain, and **architecture can be certified while the score is unchanged** (Fish 4.0 = 4.0). That is correct behavior — "certification never moves a score" — but it means no consumer can read the score as architecture readiness. It does not block Brain #3 because the rule "BEFORE=AFTER under the same rubric" is enforced (`score_baseline.py --check`). `SCORING_SEMANTICS.md` already names `researchMaturity`, `underlyingScore`, `canonicalScore`, `claimMaturity`, `customerReadiness`. Recommendation (later, not now): add two *orthogonal* published facts rather than a new score — `architectureStatus` (the §9 ladder) and `runtimeHealth` (already `healthV1`) — and keep `ENGINE_READINESS_SCORE` as science/product capability. Do not rebuild the rubric. Trigger: before any Ops surface ranks Brains by score (D-3, P2).

### D. Legacy platform-authored dependency edges — **resolved enough; Brain #3 can avoid the problem**
`brain.json` is now authoritative: inv 17 fails if a platform manifest claims an edge a *registered* Brain does not declare; Fish's four invented edges were found by exactly that gate and retired; Wind's were already `[]`. Residual: edges for **unregistered** Brains remain platform-authored and `provisional: true` (Depth→lake-brain, Vegetation→lake-brain, Sector Intelligence→5 Brains). Those are clearly transitional (flagged `provisional` in the manifest) and become gate-protected when each Brain registers. Clarity's own manifest edges are `[]`. One small inconsistency: Wind's `authorizedConsumers` lists `biological-state`, a leftover of the same invented edges, though Fish declares `consumes: []` — harmless (authorization ≠ consumption) but untrue (D-10, P3).

### E. Species Registry empty — **transitional debt; does not block Fish research**
`platform/registries/species/` is a README only. Fish ships species identity inside its bundle and passes it through verbatim (test `test_species_identity_semantics_pass_through_verbatim…`); the Fish contract declares it does not own identity. Ownership boundary is *documented and test-pinned*, not violated silently. Research adds species knowledge through the unchanged runtime. Condition for research (small, precise): species added must not extend identity fields beyond those already in the bundle, so extraction (CERT-8) stays mechanical, and per-lake presence stays private (existing test). Do not populate here (D-6, P2).

### F. Legacy direct-write doors — **structural certification is meaningful and safe without cutover**
Fish: one LEGACY door (`run.py --write`, ownership-checked, refuses customer DBs, AST-pinned). Wind: `wind-hourly` writer, traced. Safety rests on three mechanically enforced facts: (1) `PublisherMode` has no live member and the shadow sink counts `live_mutations == 0`; (2) inv 10 fails the moment `publisherRequired.cutoverStatus` becomes `CUTOVER_COMPLETE` while a specialist writer remains; (3) `BRAIN_CERTIFICATION_V1.md` §5 explicitly allows certification with legacy paths classified `LEGACY_READER_PRESENT`/`RETIREMENT_CANDIDATE`. What structural certification does **not** claim is security (exit evidence F); the Brain remains able to write production, and that fact is stated in every status line. **Brain #3 can be structurally certified without cutover.** Gap: Wind lacks Fish's AST pin (D-8, P2).

### G. Deployed-Orchestrator drift — **deployment-state lag; blocks nothing in the audit or either lane**
Per the prior session records (not re-inspected — no production read was made): the deployed image (`fc9321e2`, health plane LIVE via `--health-only`, scheduler PAUSED) still carries Fish's four legacy `dependencies` edges; main carries `dependencies: []`. Effects: the live health plane shows four Fish dependency rows as UNKNOWN; no execution reads those edges. Does not block the audit PASS, Fish research (research does not touch the Orchestrator), or Water Clarity structural certification (shadow, no deploy). **Future deploy gate (recorded, not executed):** `preflight_lineage.py` passes (deployed SHA is an ancestor of main); staged-layout smoke `python run.py --plan` from the staged `jobs/biological-brain`; health-plane diff shows exactly Fish edges 4→0 and no other change; scheduler remains PAUSED; Michael's recorded approval. Deploy only with a deliberate orchestrator task.

## 6. Generic-extension audit

| Change made during Fish certification | Verdict | Reason |
|---|---|---|
| `publisher/paths.foreign_owner` owner-precision fix (`and not path_allowed(submitter, "/"+root+"/probe")`) | **A — genuinely generic** | Fixes a latent false-positive: any Brain whose own owned root shares a name with a protected root (Fish `/species`) was reported "foreign to itself". Contains no Brain id; depends only on the ownership table. Three tests, Wind unchanged. |
| Fish as second Publisher registration (`fish_specs`, `fish_bundles`) | **A**, with a note | Pure data through the existing `SchemaSpec/BundleSpec/PathFamily/VolatileContract`; no validator/planner change. Note: it lives in the platform's `registry.py`, so registration is a platform edit per Brain (D-7). |
| Volatile *path family* for activity events | **A** | Expressed in the existing `VolatileContract`; usable by any Brain. |
| Health / lineage | **A** | No Fish code added. The only change is the recorder on `BrainRtdb` in `run.py`/`run_state.py` — the Brain-side instrumentation Wind got via its producer. |
| `SCENARIO_FISH_EDGES` in `test_orchestration.py` | **Acceptable, watch** | Fish was the canonical downstream-consumer fixture; edges were re-attached as an explicit scenario, committed-manifest assertions now say none. Still a test coupling to a Brain id; low risk. |
| `_fish_runtime_dir`, `deploy-job.sh` line, `brain_platform.py` resolver | **Fish exceptions — but openly labeled**, not hidden in generic code | §5-A |

**No hidden Fish abstraction found.** Reject-list is empty.

## 7. Hack budgets

**Fish** — 0 `UNNECESSARY_HACK`; 0 `PLATFORM_GAP` that blocks Brain #3.

| # | Exception | Class |
|---|---|---|
| F1 | `orchestrate._fish_runtime_dir` | TEMPORARY_REPOSITORY_MIGRATION (symptom of platform gap P-A) |
| F2 | `deploy-job.sh` stages `brains/fish/runtime` as `jobs/biological-brain` | TEMPORARY_REPOSITORY_MIGRATION |
| F3 | `runtime/brain_platform.py` resolver shim | TEMPORARY_REPOSITORY_MIGRATION (plan removes at Phase 4/7) |
| F4 | `EXECUTORS["biological-state"]` entry | LEGITIMATE (data) over a PLATFORM_GAP (path executor) |
| F5 | species identity inside the Fish bundle | PLATFORM_GAP (Species Registry empty), non-blocking |
| F6 | legacy `run.py --write` door | TEMPORARY (Publisher cutover) |
| F7 | `docs/` published-label strings in two Fish files (inv 8, baselined) | TEMPORARY_REPOSITORY_MIGRATION (changing them changes published output) |
| F8 | registry children/species-id regexes, volatile contract, VERSION staleness | LEGITIMATE_DOMAIN_SPECIFIC |
| F9 | `SCENARIO_FISH_EDGES` | LEGITIMATE (test scenario) |
| F10 | hand edits to `ownership.py`, `keys.py`, `scoring.py`, `jobs.py`, `control_manifest.json` | PLATFORM_GAP (per-Brain tables; all pre-existing, shared by Wind) |
| F11 | one manual edit to the legacy CI job list | TEMPORARY_REPOSITORY_MIGRATION |

**Wind** — assumptions future Brains must **not** inherit (none is a bug; each is a trap):

| # | Assumption | Where | Note |
|---|---|---|---|
| W1 | provider-driven input | `providers[]`, lineage provider entries | Fish has none; keep optional |
| W2 | scheduled hourly cadence / `staleHours` | `runtime.trigger` | Fish `manual`; Clarity is `MANUAL` too |
| W3 | observation-timestamp freshness (`staleAfterHours`, material `observationTime`) | freshness + fingerprint | version/static Brains differ |
| W4 | lake-keyed paths (`/lakes/{k}/…`, `lakeFleet`) | Publisher families | Fish is species-keyed; Clarity is lake-keyed like Wind |
| W5 | `compat.py` Wind legacy-path table (`WIND_*` classifications) | Publisher | Wind-named module inside the Publisher; a per-Brain legacy map should become data under each Brain at cutover (D-11, P3) |
| W6 | `require_freshness` as the default idea of a "release" | `SchemaSpec` | Fish proved `require_release` is the alternative |
| W7 | own `deploy/` image | packaging | in-process Brains have none |
| W8 | hand-written research collector cutover | `research/tools` | Wind-specific operational story |
| W9 | `NOT_STARTED_HERE` = scheduler-owned | Orchestrator | one-off |
| W10 | Wind's stale 3.1 mirror and nested BWIS | scores | identity-rule violations, documented, unfixed |

## 8. Research independence (Fish) — **PASS**
A Fish research session can adopt legacy research, add evidence, species, candidate releases, validation, and raise legitimate science/readiness components while changing only: workspace content; the private bundle and its release (`researchVersion`, manifest hash); `research/GAPS.json` status. Unchanged by those: `brain.json`, the artifact schema, Publisher path ownership, health, lineage, repo layout. Evidence: new species → new `/species/{id}` mutations; retired species → typed DELETE; new rules/bands → inside existing summary shapes; `REVIEWED`/`VALIDATED` are refused by the runtime until a separate promotion decision. **What would be structural (escalate, do not do in research):** a new registry child, a new path family, publishing the Species Intelligence Profile, graduating the Biological State pilot (new declared dependencies + schema), any VERSION-freshness change. Each fails closed with a named error. Remaining *unstable* surface: none structural; two decisions pending that Fish research should not pre-empt (D-1 pilot graduation, D-4 legacy research adoption).

## 9. Validation performed (this session)
| Check | Result |
|---|---|
| `origin/main` = `8c2e22ae…` (contains Wind `brains/wind` + Fish `brains/fish`) | ✔ |
| `report.py --legacy --baseline` | KNOWN 21 · **NEW 0** · RESOLVED 0; 5 large-file exceptions, 0 stale |
| `report.py` invariants (registered Brains: 2) | 1–7, 9–17 PASS; 8 = 4 findings (Fish 2, Wind 2) all in baseline |
| `brain.schema.json` validation | `brains/wind/brain.json`, `brains/fish/brain.json`, `brains/_template/brain.template.json`: 0 errors |
| `describe_contract.py --check` | Wind ✔, Fish ✔ (match Publisher registry) |
| `tools/architecture` + `verification` | 99 passed, 2 skipped |
| `brains/fish` | 285 passed, 2 skipped (cert file: 44 passed) |
| `brains/wind` (with `eccodes`, `shapely` installed) | 110 passed, 16 network deselected |
| `jobs/brain_platform` | 524 passed |
| `jobs/brain-orchestrator` / `jobs/brain-scores` | 36 / 21 passed |
Note: the two Wind research-tool tests fail without `shapely`; that is a missing `research/tools/requirements.txt` install in a bare environment (CI installs it), not a regression. Environment: a throwaway venv in the session scratchpad; nothing installed in the repo. Not run: Swift suites, network tests, anything touching production.

## 10. Template audit (`brains/_template/`) — **stale; recommend fixes, none applied**
Findings and the exact changes are in `TECHNICAL_DEBT_AFTER_AUDIT_1.md` §Template (T-1…T-7). Headline: `README.md` still says "Phase 1A migrates no Brain; this is the destination shape only"; `brain.template.json` pre-fills `consumes` with a REQUIRED `lakes` registry edge (the exact shape of fabricated dependency Fish exposed) and shows no populated `publishes`/`rubricRef`/in-process variant; `BRAIN_PACKAGE_CHECKLIST.md` has 12 items and omits Publisher registration, artifact determinism, lineage/consumption, direct-write audit, healthV1, `stable_brain_ids.json`/`control_manifest.json` entries, score BEFORE/AFTER, SHADOW-only and the certification suite. No template change was *necessary* to prevent a wrong Brain #3 provided sessions follow `BRAIN_FACTORY_CHECKLIST_V1.md`, so per the mission none was made; the factory checklist is the stop-gap.

## 11. Pipeline maturity
| Stage | Status |
|---|---|
| Existing/research state → discovery + gap audit | **DOCUMENTED ONLY** (Fish/Wind gap audits are prose; `BRAIN_CERTIFICATION_V1` steps 1–6) |
| Domain ownership | **MECHANICALLY ENFORCED** in part (contract 19 sections inv 4; path ownership tables + Publisher rejections) |
| Canonical repo location | **MECHANICALLY ENFORCED** (inv 1, 3; per-Brain location tests) |
| `brain.json` | **MECHANICALLY ENFORCED** (schema, inv 1, 5, 6) |
| Input/output contracts | **MECHANICALLY ENFORCED** (`describe_contract.py --check` — per-Brain script, not in CI) |
| Dependency declarations | **MECHANICALLY ENFORCED** (inv 12, 13, 17) |
| Versioned artifact | **MECHANICALLY ENFORCED** (Publisher validation); builder **MANUAL** per Brain |
| Lineage | **AUTOMATED** (platform recorder) with per-Brain instrumentation **MANUAL** |
| Health | **AUTOMATED** (zero Brain code) |
| Publisher compatibility | **MECHANICALLY ENFORCED**; registration **MANUAL** (file edit) |
| Certification tests | **MANUAL** (hand-copied suite; CI loop runs them generically) |
| SHADOW | **MECHANICALLY ENFORCED** (no live mode; inv 10) |
| Calibration / science validation | **DOCUMENTED ONLY** (model docs; per-Brain) |
| Production ready / production | **DOCUMENTED ONLY** (policy ≥8.0 + critical ≥7.5; no gate code for approval) |
| *Structural-certification status record* | **MISSING** (no status field; this audit proposes the vocabulary) |
| *Generic lifecycle-drift gate* | **MISSING** |
| *Orchestrator runner derived from `brain.json`* | **MISSING** |

## 12. What this audit did not do
No deploy, no Orchestrator or Publisher change, no scheduler change, no write to `sector-brain`, no Sector Ops or customer change, no research, no Clarity work, no Species Registry population, no template rewrite, no score change, no branch or worktree deletion, no force push.
