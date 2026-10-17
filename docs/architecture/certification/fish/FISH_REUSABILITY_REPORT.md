# Wind vs Fish — platform reusability report (input to Architecture Audit #1)

Question: is the architecture built around Wind reusable, or Wind-specific? Legend: **REUSED_AS_IS** · **REUSED_WITH_GENERIC_EXTENSION** · **DOMAIN_SPECIFIC** · **BROKEN_ABSTRACTION** · **FISH_SPECIFIC_HACK**.

| # | Platform abstraction | Wind | Fish | Verdict | Evidence / note |
|---|---|---|---|---|---|
| 1 | `brain.json` schema + generated registry | cloud job, schedule, 3 providers, 1 registry | **in-process**, manual trigger, no providers/signals/registries, `consumes: []` | REUSED_AS_IS | `runtime.kind: in-process`, `trigger: manual`, empty `consumes`/`providers` all already legal; no schema change |
| 2 | 19-section operating contract + checker | ✓ | ✓ | REUSED_AS_IS | `report.py` inv 4 |
| 3 | Package layout (`runtime/ contracts/ tests/ research/ pytest.ini`) | + `deploy/`, research tools | no `deploy/` (runs inside the orchestrator image) | REUSED_AS_IS (deploy dir N/A) | |
| 4 | Publisher registry (`SchemaSpec` / `BundleSpec` / `PathFamily` / `VolatileContract` / typed DELETE) | 3 schemas, lake-scoped | 2 schemas, species-keyed + registry children | REUSED_AS_IS | Second registration is pure data: `fish_specs()`; no registry/validate/plan code changed |
| 5 | Envelope v2 seal + semantic fingerprint + volatile paths | ✓ | ✓ (incl. volatile **path family** for activity events) | REUSED_AS_IS | |
| 6 | Path-ownership rejection (`CROSS_DOMAIN_PATH`, `RESERVED_PATH`, `BRAIN_NODE_REPLACEMENT`, …) | tested | tested (11 cases) | REUSED_WITH_GENERIC_EXTENSION | `paths.foreign_owner`: a root the submitter itself owns is no longer reported as "foreign to it" (`/species` named 'species' for Fish). Any Brain that owns a protected-root name benefits; Wind unchanged (tested) |
| 7 | Actual Consumption Lineage (recorder, `consumed[]`, declared-vs-actual) | external producer: provider entries from state provenance | platform client recorder (already integrated); pilot runner instrumented | REUSED_AS_IS | Own-state reads correctly excluded ⇒ Fish records `[]`; undeclared reads surface as `consumedNotDeclared` (tested) |
| 8 | Private knowledge release as lineage identity (`knowledgeRelease/manifestRef/manifestSha256`) | `NONE` (no canonical release) | real release | REUSED_AS_IS | The lineage schema already modelled a release; no "knowledge dependency" type was needed (and none was invented) |
| 9 | Declared dependencies + drift gate (`dependency_declarations.drift`) | Wind's manifest edges `[]` | **found 4 invented edges** in the platform execution manifest that Fish never consumes | REUSED_AS_IS | The gate did its job; resolution = Wind precedent (platform manifest edges follow the Brain's declaration) |
| 10 | healthV1 | ✓ | ✓ with zero Fish code; zero declared ⇒ `dependencyHealth SATISFIED`, freshness `UNKNOWN` | REUSED_AS_IS | tests `test_health_v1_can_represent_fish…`, `test_unknown_stays_unknown…` |
| 11 | Freshness model | cadence-driven; supplies `freshness` | **version-driven**; supplies none | REUSED_AS_IS — **platform observation** | UNKNOWN is honest, but the platform has no way for a VERSION-basis Brain to *state* "fresh as of release R, never stale by age" (`FRESHNESS_MODEL` mentions `stale:false` for the legacy registry only). Audit #1 candidate: a `VERSION`-basis freshness statement in the Publisher/health vocabulary |
| 12 | Score contract | `wind-certification-rubric-v1` (certification-focused) | `biological-state-score-v1` (live-fact scorer mixing architecture + science + product) | DOMAIN_SPECIFIC + **BROKEN_ABSTRACTION (global)** | One "ENGINE_READINESS_SCORE" means different things per Brain; Fish proves architecture and score can diverge (cert-ready at 4.0). Not changed |
| 13 | Orchestrator executor model | Wind not started by the orchestrator | in-process, executed **by directory path** (`EXECUTORS["biological-state"].dir`) | **BROKEN_ABSTRACTION** (known smell, repo audit: "platform executes Brain code by path") | See hacks below |
| 14 | Research workspace (logical id + private manifest + public GAPS) | `wind-brain` | `fish-brain` structure created, legacy data inventoried not moved | REUSED_AS_IS | |
| 15 | Species Registry (identity) | n/a | skeleton only; identity still ships inside the Fish bundle | **PLATFORM gap** (not Fish hack) | Fish does not declare `registry:species` because it does not read it. CERT-8 must precede identity separation |
| 16 | Architecture gates + baseline + CI `registered-brains` loop | Wind | Fish picked up automatically; legacy CI list needed one manual edit | REUSED_AS_IS | |
| 17 | Orchestration decision-model tests | independent of Wind | **coupled to Fish's invented edges** (Fish was the canonical downstream-consumer fixture) | **BROKEN_ABSTRACTION (tests)** | Edges re-attached as an explicit scenario fixture (`SCENARIO_FISH_EDGES`); committed-manifest assertions now say Fish has none |

## Fish-specific hacks (all transitional; none in the Publisher / health / lineage / registry framework)
1. `jobs/brain-orchestrator/orchestrate.py::_fish_runtime_dir()` — resolves the executor directory in the repo (`brains/fish/runtime`) or in the staged image (`../biological-brain`). Retires with the registry-derived runner (repository Phase 6/7). **FISH_SPECIFIC_HACK**.
2. `jobs/brain-orchestrator/deploy-job.sh` — stages `brains/fish/runtime` under the legacy `jobs/biological-brain` layout the deployed image expects. Same retirement. **FISH_SPECIFIC_HACK**.
3. `brains/fish/runtime/brain_platform.py` — platform shim that finds `jobs/brain_platform` in the repo layout or the staged layout (repository plan intends to remove Fish's shim at Phase 4; the orchestrator subprocess model still needs a resolver). Fish-local, not platform. **FISH_SPECIFIC_HACK (local)**.
4. `control_manifest.json` — `executionTarget.dir` and `dependencies: []` for Fish (configuration data, same shape as Wind's entry; not a hack).

## Generic platform extensions made (each justified as reusable)
1. `publisher/paths.foreign_owner` owner-precision fix (row 6) — one line + 3 tests.
2. Fish registered as the Publisher's second concrete Brain (data in `registry.py`; framework untouched).

## Verdict for Architecture Audit #1
The Wind-built platform **is reusable**: a second, structurally different Brain (in-process, no providers, version-driven, species-keyed, with a private knowledge release) registered, published (shadow), reported health and carried lineage **without any change to the Publisher, lineage, health or registry frameworks** beyond one precision fix. The friction found is concentrated in four places: (a) orchestrator path-coupling to Brain implementation, (b) no VERSION-basis freshness statement, (c) the single mixed score, (d) legacy platform-authored dependency edges and the tests coupled to them. None required a Fish-specific change to a platform framework.
