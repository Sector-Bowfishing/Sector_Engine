# Target Repository Architecture V1 (PROPOSED)

**Status:** `REPOSITORY_ARCHITECTURE_PROPOSED_V1`. Nothing here is implemented. Alternatives considered and rejected are in §12.

## 1. Design principles (derived from the audit)

1. **Directory = ownership.** A path answers "who owns this?" before any file is opened.
2. **A Brain has one home**; everything that defines how it works lives there (contract, runtime, builder, contracts, rubric, validation, tests). Raw research does not.
3. **Domains are separated by build/deploy boundary, not by language.** A Brain with Swift runtime and Python tooling keeps both in its home. Languages follow SwiftPM / pip needs.
4. **Boundaries are enforced by tooling** (SwiftPM target graph, an import-lint test, `PROVIDERS.json` consumer check), not by convention.
5. **No runtime input lives in `docs/`.**
6. **Incremental.** The layout can be reached one Brain at a time with compatibility shims; Swift `Package.swift` and the customer Dockerfile stay at the root.
7. **Simpler, not more bureaucratic.** Mandatory pieces are few (§6); everything else is optional.

## 2. Proposed tree

```
Sector_Engine/
├── Package.swift  Package.resolved  Dockerfile  deploy.sh  README.md        (root build entrypoints stay)
│
├── engine/                          CUSTOMER-SERVING ENGINE (class A)
│   ├── Sources/                     SectorEngine (scoring: Aggregator, Factors, Config, WhereToLook, Forecast, API) + SectorEngineServer
│   ├── Tests/                       Engine-owned tests only
│   ├── data/                        full_pool.csv, temp_sensors.csv (build-time reference data)
│   └── docs/                        endpoint & scoring docs, scoreVersion history
│
├── providers/                       SHARED ACQUISITION (class C)
│   ├── PROVIDERS.json               id, owner, authorized consumers, license, cost, health source id, raw-cache policy
│   ├── swift/Sources/SectorProviders/   Open-Meteo, USGS, TVA, CWMS, SWPA, Alabama Power, USBR, NWS, MRMS, NOAA water
│   ├── python/sector_providers/     NBM/RTMA/HRRR/RRFS/MADIS, STAC/Sentinel, TVA archive helpers (only what Python jobs need)
│   └── fixtures/<providerId>/       recorded payloads shared by Swift+Python parity tests
│
├── platform/                        BRAIN PLATFORM (never Brain-specific)
│   ├── python/sector_brain_platform/    installable package (pyproject.toml); stdlib-only
│   ├── swift/Sources/SectorBrainPlatform/   BrainPlatform, BrainContract, BrainRTDBStore
│   ├── orchestrator/                executor, control plane, lineage preflight, deploy
│   ├── publisher/                   Publisher service + Orchestrator API (from feat/publisher-v1-shadow)
│   ├── scoring/                     scorer, beta, score publisher, rubrics/ (engine, beta); SCORING.md
│   ├── registry/                    GENERATED from brains/*/brain.json: brain registry, path ownership, job manifest, dependency order
│   ├── lineage/                     image labels, preflight, identity/lineage block
│   ├── species-registry/            (CERT-8) canonical species identity release
│   └── ops/                         alerting, warm tags
│
├── contracts/                       SHARED, LANGUAGE-NEUTRAL, VERSIONED
│   ├── schemas/                     platform envelope, publication artifact, control state, lineage, score block, freshness
│   ├── conformance/                 cross-language fixtures (was docs/brains/conformance)
│   └── README.md                    version policy, how a Brain registers a published contract
│
├── brains/                          SPECIALIST BRAINS (class B) — one home each
│   ├── _template/                   STANDARD_BRAIN_PACKAGE_V1 skeleton + BRAIN_OPERATING_CONTRACT.template.md
│   ├── wind/
│   ├── fish/                        brainId: biological-state
│   ├── lake/                        also owns lake REGISTRY, geometry, bindings, presence contract
│   ├── water-temperature/
│   ├── water-clarity/
│   ├── depth/
│   ├── vegetation/
│   └── sector-intelligence/
│
├── tests/                           CROSS-CUTTING ONLY
│   ├── architecture/                import-lint, "no runtime input in docs", brain.json schema, PROVIDERS consumer check
│   ├── integration/                 Publisher + Brain handoff, orchestrator + brain.json
│   └── e2e/                         shadow/conformance runs (offline)
│
├── tools/                           repo-wide dev tooling (generators, linters); no domain logic
├── deploy/                          per-deploy-unit Dockerfiles/scripts that don't belong to one Brain (brain-jobs image, orchestrator)
│
└── docs/
    ├── architecture/                governance (this audit, data architecture, certification)
    ├── platform/                    platform models & contracts (was docs/brains/platform + root contracts)
    ├── history/                     consolidation, handoffs, closeouts, scope notes, cost-freeze (private-content review first)
    └── README.md                    "where do I find…" index
```

## 3. Ownership of each major directory

| Directory | Owner | May depend on | Must not contain |
|---|---|---|---|
| `engine/` | Engine (customer) | `providers`, `platform/contracts` | Brain runtime; provider clients; research |
| `providers/` | Platform (per-provider owner in `PROVIDERS.json`) | nothing domain | thresholds, gates, scoring, Brain interpretation, credentials |
| `platform/` | Platform | `contracts`, `providers` (health/IO only) | any Brain's logic or data; sibling Brain imports |
| `contracts/` | Platform, change-controlled | — | Brain-private schemas |
| `brains/<id>/` | that Brain | `providers`, `platform`, other Brains' `contracts/` | other Brains' internals; customer Engine code; raw research data; secrets |
| `tests/` | Platform | everything (read) | unit tests owned by one domain |
| `docs/` | governance | — | runtime inputs, per-Brain operating docs (those live with the Brain) |

## 4. Boundaries

* **Engine-serving boundary.** `engine/` is the only code that answers customer HTTP. It never reads `sector-brain` directly. Customer behavior changes only by a versioned, deliberate cutover (class D) that bumps `scoreVersion`/response version and appears in a decision record. Moving files must not change `scoreVersion` or any response byte (guarded by a golden-response test run before/after each migration phase).
* **Provider boundary.** Acquire, parse, normalize, report source health. Never interpret domain meaning. One client per provider per language; authorized consumers declared and checked.
* **Platform boundary.** Everything common to all Brains (see `PLATFORM_REPOSITORY_INVENTORY` §6). Platform never imports a Brain; Brains register via `brain.json`.
* **Specialist Brain boundary.** A Brain owns its domain truth, builder, schemas, rubric, validation and tests; it publishes through the Publisher (target) and consumes only others' `contracts/`.
* **Embedded adapter exception.** Where customer Engine today shares a Brain's implementation (Water Temp, Clarity visibility), the Brain publishes a library target and declares `customerDirect: embedded` in `brain.json`; Engine links the library, not the Brain's job/runtime. This keeps current behavior, makes the coupling visible, and gives a path to class D.

## 5. Shared contract strategy

* **One definition per contract.** Platform contracts live only in `contracts/schemas/`; Python and Swift implement them and prove equality with `contracts/conformance/`.
* **Brain published contracts** live only in `brains/<id>/contracts/` (JSON Schema + a short consumer note + version). They are the **only** files another Brain may reference. Private/internal schemas stay beside the runtime.
* `brain.json` lists which contracts a Brain publishes and consumes; the generator builds the registry and the dependency order; a test fails if a Brain references another Brain's non-`contracts/` path.
* Versioning: semver in the schema `$id`; breaking change = new major, dual publish for one cycle (Publisher validates both).

## 6. Schema strategy

| Class | Home |
|---|---|
| Platform (envelope, control, lineage, score block, freshness) | `contracts/schemas/` |
| Brain-published state & artifacts | `brains/<id>/contracts/` |
| Brain-private (bundle manifests, catalogs, internal ledgers) | `brains/<id>/runtime/schemas/` (or beside the module) |
| Customer API (`ConditionsResponse` etc.) | `engine/` — add a generated JSON schema for clients (today: Swift DTO only) |
| Runtime state at rest (RTDB shape) | derived from `contracts/` + Publisher `paths`; `TARGET_SECTOR_BRAIN_SCHEMA` stays the governance reference |

Undocumented implicit schemas (every non-Fish Brain today) get a published contract at that Brain's certification; this is part of the Brain package's mandatory set.

## 7. Test strategy

* Tests live with their owner: `engine/Tests`, `providers/*/tests`, `platform/*/tests`, `brains/<id>/tests`. Cross-cutting in `tests/`.
* Swift: split the single `SectorEngineTests` into per-target test targets (`EngineTests`, `ProvidersTests`, `PlatformSwiftTests`, `LakeBrainTests`, `WaterTempBrainTests`, `ClarityTests`); Python: every dir has `pytest.ini`, **no loose `test_*.py` beside scripts**.
* `brain.json` declares `tests: [paths]` and CI **derives its job matrix from the registry** (replacing the hand-written directory list); an unregistered test dir fails an architecture test.
* Add Swift build+test to CI (or a scheduled workflow) so the Brain Swift targets are covered.
* Golden response test for the customer Engine before any move touching `engine/`.
* Network tests are `-m network`, deselected offline (already the Wind convention).

| Current test | Owner (target) |
|---|---|
| Aggregator, Factor, ConfigOverrides, ForecastRain*, FullPool | `engine/` |
| USGSWaterDataTests + USGS fixtures | `providers/` |
| BrainPlatformConformanceTests | `platform/swift` |
| Lake* (7), LakeDirectoryAPITests (registry part) | `brains/lake` (registry cases may live with `engine/` if they test the endpoint) |
| WaterTemp* / WaterTemperatureBrain* (8) | `brains/water-temperature` |
| Clarity*, HydrologyGraph | `brains/water-clarity` |
| `brain_platform/tests` (9) | `platform/python` |
| `brain-orchestrator/tests` (4), `brain-scores` (4 loose) | `platform/orchestrator`, `platform/scoring` |
| Wind 8 / Fish 1 / Intelligence 2 / Clarity 1 / TVA archive 1 | their Brain / provider |
| Lake Python (validation, bindings, ledger, review) 6, lake-geometry 1 | `brains/lake` (and add to CI) |

## 8. Scoring strategy

* `platform/scoring/`: scorer, beta, score publisher, shared rubric mechanics and the two platform rubrics (engine aggregate, beta readiness).
* `brains/<id>/scoring/rubric.json` (+ short `README`): the Brain's `ENGINE_READINESS_SCORE` definition. `frozen-scores.json` lives in `platform/scoring/` and is replaced Brain-by-Brain as rubrics land. **Scores do not change in any migration phase** (before/after check).
* Naming enforced by `brain.json`: `score.type = ENGINE_READINESS_SCORE`, `score.path = /scores/{brainId}`.
* Candidate/science scores (Wind bowfishing score, validation scoreboards) are named `*_candidate` / `validation/` and never published at `/scores`.
* Customer `CONDITIONS_SCORE` stays in `engine/`; its docs say it is not a readiness score.

## 9. Research boundary and public/private rules

Rule of thumb: **GitHub holds how the Brain works and the metadata that governs research; the workspace holds evidence.**

| MUST be in Sector_Engine | Normally stays OUTSIDE (workspace / private storage) |
|---|---|
| `BRAIN_OPERATING_CONTRACT.md`, `brain.json`, README | raw datasets, provider dumps, corpora, literature PDFs |
| runtime code, artifact builder, validators | private observations, field logs, customer data |
| published contracts, schemas, config defaults | sensitive security findings, private IAM detail, credentials, tokens |
| scoring rubric, validation protocols & prereg (text), small golden fixtures | large/binary model artifacts, private validation archives, RTDB exports |
| tests, deploy scripts without secrets | per-lake species presence and other licensed/private research data |
| provider clients, `PROVIDERS.json` | generated bulk data that can be rebuilt from a recorded recipe |
| architecture docs, decision records | working handoffs (private Desktop handoff folder) |
| research **metadata**: `research/GAPS.json`, `research/MANIFEST.json` (workspace id, artifact hashes, locations as logical names) | the research artifacts themselves |

Conservative public-repo rules: no service-account emails, project numbers beyond what is already public, UIDs, or live job snapshots in `docs/`; size budget (suggested: files > 1 MB or > 5 MB per directory need an exception recorded in `brain.json` `dataBudget`); build-time embedded data (registry, bindings, hydrology) must be **generated from a recorded recipe** and either small or stored as a release artifact; generated files carry a header with source hash.

**Code must not hard-code the workspace path.** Tools take `SECTOR_RESEARCH_ROOT` (env) + a Brain workspace id (`wind-brain`, `fish-brain`, …); the absolute path exists only in `docs/architecture/certification/BRAIN_RESEARCH_WORKSPACE_V1.md` and local config.

## 10. Canonical-release boundary

`research workspace → (Brain canonicalization, evidence-gated) → canonical release (versioned, private bucket; CERT-3/4) → artifact builder → Publisher → sector-brain`. The repo records the *schema, validator and rule* for a canonical release (`brains/<id>/contracts`, `validation/`, operating contract §CANONICALIZATION), never the release payload when it is private research.

## 11. Cross-Brain, import, and publication rules (normative once approved)

1. **Import:** `brains/A` may import `providers`, `platform`, and `brains/B/contracts` only. No `brains/B/runtime|artifact|research` imports, no `engine/` imports.
2. **Data:** a Brain never reads another Brain's research workspace; it reads published state/contracts (RTDB or release).
3. **Customer:** only `engine/` serves customers. Brain output reaches customers only via an approved class-D cutover.
4. **Writes:** specialist Brains produce versioned artifacts; only the Publisher writes `sector-brain` (target; the repo structure must not add new direct writers). New direct-writer code is rejected by the architecture test after Publisher cutover.
5. **Providers:** acquisition only through `providers/`; authorized consumers per `PROVIDERS.json`.
6. **Scores:** one `ENGINE_READINESS_SCORE` per Brain at `/scores/{brainId}`; Ops never computes.
7. **Platform duplication:** a Brain may not re-implement envelope/keys/freshness/health/ownership/lineage.
8. **Unknown is not zero**: schemas must allow explicit `UNKNOWN`/absent; builder tests assert it.
9. **Research is bounded**: Research Gaps (below) are the only reason to start research work.

## 12. Alternatives considered

| Alternative | Why not |
|---|---|
| "Everything under `brains/`" | Puts providers, platform and the customer Engine under Brains or leaves them orphaned; customer Engine is not a Brain; fails shared-provider goal |
| Keep `jobs/` as primary (one dir per runtime job) | Runtime units ≠ ownership (Lake spans 3 jobs; Fish/Intelligence are in-process); this is today's confusion |
| Language-first (`swift/`, `python/`) | Splits each Brain across the tree (the current problem) |
| Separate repos per Brain | Platform contracts, Publisher and Orchestrator need atomic cross-Brain changes; public-repo + one CI is simpler at this scale. Revisit only if a Brain becomes independently maintained |
| Monorepo with Python workspace tool (uv/poetry) | Not needed yet; plain `pyproject.toml` per package keeps stdlib-only constraint |
