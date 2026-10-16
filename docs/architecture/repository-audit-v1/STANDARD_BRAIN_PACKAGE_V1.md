# Standard Brain Package V1 (LOCKED FOR PHASE 1)

**Status:** `REPOSITORY_ARCHITECTURE_V1_APPROVED_FOR_PHASE_1` (RA-2, RA-3, RA-4, RA-7, RA-16, RA-17 locked 2026-10-14). Defines what a Brain's permanent GitHub home contains. Consistency without bureaucracy: **six mandatory items, the rest become mandatory only when their trigger occurs.** No Brain-specific contract is written by the audit.

## 1. Layout

```
brains/<dir>/                      dir = human-friendly (fish, lake, wind…); brainId lives in brain.json
├── README.md                      MANDATORY  ≤ 1 page: what this Brain is, the bowfisher decision, where things are
├── BRAIN_OPERATING_CONTRACT.md    MANDATORY  the rules a research/build session must read first (§3)
├── brain.json                     MANDATORY  machine-readable declaration (§4)
├── contracts/                     MANDATORY  published schemas + consumer notes (the only part other Brains may read)
├── runtime/                       MANDATORY  the code that computes and builds state (Python package or Swift target path)
├── tests/                         MANDATORY  unit/contract tests owned by this Brain
├── artifact/                      optional→required at Publisher cutover: artifact builder (state → versioned publish artifact)
├── scoring/                       optional→required: rubric.json (+ README) for ENGINE_READINESS_SCORE
├── validation/                    optional: validators, prereg protocols, evidence-contract, scoreboards, holdout code
├── research/                      optional: GAPS.json, MANIFEST.json, small reproducible tools (NO data)
├── config/                        optional: default config, thresholds, catalogs (versioned), no secrets
├── docs/                          optional: design notes, certification records for this Brain
└── deploy/                        optional: Dockerfile/deploy script if this Brain owns a deploy unit
```

**No empty ceremonial directories.** A directory exists only when it holds a file with a purpose. If a mandatory category genuinely has no files yet (e.g. `contracts/` for an unpublished Brain), the requirement is represented in the package checklist/`brain.json` (`contracts: []`, `publishes: []` with reason) until the category becomes relevant.

**Triggers that make optional directories mandatory:** `artifact/` once the Brain participates in Publisher artifact publication; `scoring/` once it owns an explicit rubric/score definition; `validation/` where architecture or scientific certification requires a durable validation protocol/code. `research/` in Git is **metadata and reproducibility tooling only, never raw datasets.**

**Certification gate (RA-3):** a Brain cannot receive final `ARCHITECTURE_CERTIFIED_V1` without `README.md`, `BRAIN_OPERATING_CONTRACT.md` and `brain.json`, and its required `contracts/`, `runtime/` and `tests/` correctly represented.

## 2. Component table

| Item | Why it exists | Mandatory? | Belongs there | Must NOT belong there |
|---|---|---|---|---|
| `README.md` | orientation for humans and agents | yes | identity, bowfisher decision, map of this directory, how to run tests, links | duplicated contract text; status history |
| `BRAIN_OPERATING_CONTRACT.md` | the rules a Brain session obeys; discoverable, versioned | yes | all §3 sections | evidence, findings, handoffs, run logs |
| `brain.json` | one machine-authoritative declaration used by registry, Publisher, Orchestrator, CI | yes | §4 fields | prose, thresholds, scientific parameters |
| `contracts/` | published interface other Brains/Publisher/Engine rely on | yes once the Brain publishes or consumes a contract; until then represented by `brain.json` (`publishes: []`, with reason) and the package checklist, not an empty directory | JSON Schemas, version, consumer note, example payload | private schemas, research formats |
| `runtime/` | computation + state builder | yes | package code, entrypoint implementing the platform Runner interface | research scripts, one-off analyses, hard-coded paths, provider clients (use `providers/`) |
| `artifact/` | converts state to a versioned Publisher artifact (envelope, lineage, hash) | required at Publisher cutover | builder, artifact tests | any direct `sector-brain` write after cutover |
| `scoring/` | defines the Brain's readiness score | required once a rubric exists | `rubric.json`, notes on what moves each dimension | candidate/science scores, UI work as evidence |
| `validation/` | proves the Brain is right | optional | validators, preregistrations (text), protocol, scoreboards, small golden fixtures | raw observation archives |
| `research/` | rules and metadata for bounded research | optional | `GAPS.json`, `MANIFEST.json`, reproducible small tools | datasets, corpora, notebooks with outputs, absolute paths |
| `config/` | tunables as data | optional | defaults, catalogs, public overlays | secrets, private overlays (gitignored/private) |
| `tests/` | ownership of correctness | yes | unit + contract tests; offline by default | tests of other domains |
| `deploy/` | Brain's own deploy unit | optional | Dockerfile/script, no secrets | shared image recipes (`deploy/` at root) |

## 3. `BRAIN_OPERATING_CONTRACT.md`: location, role, template

**Canonical location:** `brains/<dir>/BRAIN_OPERATING_CONTRACT.md`: at the Brain root, versioned with the code it governs, reviewed in the same PR as changes to behavior. It is **never only** in the external research workspace; the workspace gets a one-line `READ_FIRST.md` that points to the repo path and commit. Until a Brain is migrated, its contract lives at `docs/architecture/certification/<brain>/` (Wind's current certification folder) and moves with the Brain.

**Role:** the first file a research or build session reads; the Brain's answer to "what decision does this help a bowfisher make, what may I do, what must I not do, when do I stop?". It cites, never copies, platform rules.

**Template (every section mandatory; "N/A: reason" allowed):**

| # | Section | Must state |
|---|---|---|
| 1 | IDENTITY | `brainId` (stable), display/human name, domain, lifecycle state, contract version, owner |
| 2 | MISSION | one paragraph: the domain truth this Brain owns |
| 3 | BOWFISHER DECISION | the bowfisher decision(s) this Brain helps make (use "bowfisher/bowfishers"); outputs that don't change a decision are out of scope |
| 4 | OWNERSHIP | data, models, rules, identifiers, RTDB path families, score this Brain owns |
| 5 | NON-OWNERSHIP | what it explicitly does not own (e.g., species identity, legality, lake presence, customer scoring) |
| 6 | DEPENDENCIES | Brains, providers, registries it consumes, each with the contract version |
| 7 | COMMUNICATION CONTRACTS | published contracts (`contracts/`), consumers, allowed communication paths; no private-research reads |
| 8 | RESEARCH WORKSPACE | logical workspace id (e.g. `wind-brain`), `SECTOR_RESEARCH_ROOT` rule, shared folder rules, backup class |
| 9 | RESEARCH INITIATION RULES | research starts only to close a **named** gap in `research/GAPS.json` (product, confidence, readiness, validation, or evidence gap) |
| 10 | RESEARCH STOP RULES | stop when more work no longer changes a useful bowfisher-facing decision, or field validation / another Brain / human approval is required |
| 11 | EVIDENCE HIERARCHY | ranking of evidence types and what each may support (claim levels per platform models) |
| 12 | CANONICALIZATION | how research becomes a canonical release (gate, approver, versioning, rollback) |
| 13 | VALIDATION | what validation exists, what is NOT validated, validation vs architecture certification, field-validation needs |
| 14 | PUBLISHING | artifact schema ids, publish families, cadence/trigger, freshness rule, Publisher requirement, customer-direct restriction |
| 15 | PATH OWNERSHIP | RTDB/storage path families, rejection rules (`brainId → schema → path family`) |
| 16 | SCORING | rubric location, score type, what can and cannot move it; "certification never moves a score" |
| 17 | COST RULES | job cadence/ceilings, provider costs, data-egress limits, cost-freeze compliance |
| 18 | SECURITY | public-repo rules for this Brain, secrets, writer identity, what stays private |
| 19 | SESSION CLOSEOUT FORMAT | required closeout fields: gap addressed, decision affected, evidence, files changed, tests, score before/after, open gaps, human/field validation needed |

(The user-specified minimum list of 19 headings is exactly §1–19 above.)

### Research gap record (`research/GAPS.json`)
Each entry: `id`, `type` (product|confidence|readiness|validation|evidence), `title`, `whyItMatters`, `bowfisherDecision`, `currentEvidence` (pointers into the workspace manifest), `stopCondition`, `expectedOutput`, `humanOrFieldValidationRequired` (bool + what), `status`, `owner`. A session may only start research that references an `OPEN` gap id. This is how GitHub holds the *rules and metadata* of research without holding artifacts.

### 3a. Research classification rule (RA-16, RA-17)
Research artifacts are not bulk-moved. At the Brain's certification/migration each meaningful artifact (including those on `docs/*-research` branches) is classified once:

| Destination | Holds |
|---|---|
| **GitHub** (`brains/<dir>/`) | operating rules; durable Brain specification; canonical decision records; preregistration/protocols; accepted validation methodology; schemas; small fixtures; research-gap metadata; reproducibility tooling needed to support published claims |
| **External research workspace** (logical id, e.g. `wind-brain`) | raw evidence; exploratory research; large datasets; provider dumps; working analyses; private observations; bulky derived outputs; notes not part of the permanent contract |
| **Canonical versioned storage** | accepted durable releases; publication artifacts; validation/history that must be durable but is unsuitable for public Git |

Do not copy-and-forget and do not duplicate evidence because a branch exists; use `MANIFEST.json` references/hashes. Core rule: **a Brain is not a university**; research is triggered by a named gap with a stop condition.

### Research manifest (`research/MANIFEST.json`)
`workspaceId`, per-collection: logical name, class (RESEARCH/CANONICAL/OBSERVATION_VALIDATION/DERIVED/…), content hash or version, backup location id, producing tool + commit. Hashes make the claim "this canonical release came from this evidence" checkable without storing the evidence.

## 4. `brain.json` evaluation

**Recommendation: YES, adopt a minimal declaration; use JSON, not YAML.**

* Why JSON: the Orchestrator image is stdlib-only Python and the Swift side has no YAML parser; both parse JSON natively, and the repo already validates JSON (`control_manifest.json`, schemas, conformance). YAML adds a dependency to the one image that has none. (If humans insist on YAML, a generated JSON is the machine form.)

| Benefit | Evidence in this repo |
|---|---|
| Replaces six hand-synchronized registries | `jobs.py`, `ownership.py`, `control_manifest.json`, `conformance/ownership.json`, `catalog.json`/`DEPENDENCY_ORDER`, `OWNERSHIP_MATRIX`, `jobs/README.md` |
| Derives CI matrix, dependency order, path ownership, Publisher rules | CI list is hand-written and already missing dirs |
| Makes cross-Brain imports checkable | needs a declared `consumes` list |
| Lets agents answer "what is this Brain" in one read | no Brain has this today |

| Risk | Mitigation |
|---|---|
| Duplicates Markdown | `brain.json` carries **identifiers and edges only**; prose (mission, rules) lives only in the contract; contract §1 references `brain.json` for ids, never repeats them |
| A seventh registry | **generate** the existing registries from it and delete hand-maintained copies in the migration (Phase 1) |
| Schema drift | `contracts/schemas/brain.schema.json`, validated by an architecture test |
| Over-specification | ≤ ~25 fields; everything optional except identity/lifecycle/runtime/publish |

**Guardrails (RA-2).**
* JSON, never YAML; **structured identity and edges only**; no prose, reasoning, thresholds or scientific parameters.
* No absolute local path: the research workspace is a **logical id** (e.g. `wind-brain`); `SECTOR_RESEARCH_ROOT`/config resolves the physical root.
* `brain.json` is **not a seventh hand-synchronized registry**: the Brain Registry (`platform/registries/brains/`) and the existing job/ownership/dependency registries are **generated** from it; the old copies retire only after a diff test proves equivalence.
* `BRAIN_OPERATING_CONTRACT.md` remains authoritative for behavior and human/research instructions.

**Machine-authoritative fields:** `schemaVersion`, `brainId`, `displayName`, `humanName`, `domain`, `lifecycle` (platform vocabulary), `contractVersion`, `runtime` (`kind: job|in-process|service`, language, entrypoint, trigger kind/stale hours), `publishes[]` (artifact schema refs, path families), `consumes[]` (brainId + contract id + min version; **lake and species identity come from `registries.lakes` / `registries.species` contracts, not from the Lake or Fish Brain**), `providers[]` (ids used; with the consumer's `domainInterpreter` role), `researchWorkspace` (logical id), `score` (type, path, rubric ref), **`customerIntegrationMode`** (`none` | `embedded` | `published`), `publisherRequired` (bool + cutover status), `authorizedConsumers[]`, `tests[]`, `dataBudget` (bounded runtime metadata, exceptions).
**`customerIntegrationMode` semantics.** `none`: no customer path. `embedded`: the **customer Engine imports/executes a Brain-owned contract/library**; NOT "Brain writes the customer database", NOT "Brain calls customer internals". `published`: the customer Engine consumes the Brain's approved published contract. The dependency direction is **Customer Engine → approved Brain contract/library, never Brain → customer Engine**. (If the shorthand `customerDirect` is ever kept, it must carry exactly these semantics.)
**Human-only (contract Markdown):** mission, bowfisher decision wording, evidence hierarchy, research initiation/stop rules, canonicalization procedure, cost rationale, security rationale, closeout format.

## 5. What Wind would move / reference / adopt (design only; not performed)

Wind is the first Brain conformed. Mapping from base:

| Today | Wind target | Move / reference / adopt |
|---|---|---|
| `jobs/wind-hourly/sector_wind/*.py` (22) | `brains/wind/runtime/sector_wind/` | MOVE (package name unchanged; keep import path via shim until job image updated) |
| `jobs/wind-hourly/sector_wind/brain/{contract,profile,state,publish,lakes,writer,__main__}.py` | `brains/wind/runtime/sector_wind/brain/` (state) ; `publish.py`+`writer.py` → superseded by `artifact/` builder | MOVE; `writer.py` slated for retirement at Publisher cutover (14-step retirement, no deletion now) |
| `sector_wind/brain/artifact.py` (+ its test) from `cert/wind-architecture-v1` | `brains/wind/artifact/` | ADOPT (branch-only) |
| `sector_wind/brain/validation_evidence.json` | `brains/wind/validation/` | MOVE |
| `jobs/wind-hourly/main.py`, `Dockerfile`, `deploy-job.sh`, `requirements.txt`, `check-live.sh`, `pytest.ini` | `brains/wind/deploy/` + `runtime/main.py` | MOVE |
| `jobs/wind-hourly/read_service/` | `brains/wind/deploy/read_service/` | MOVE (separate Cloud Run service; internal) |
| `jobs/wind-hourly/lakes.json` | **retire as a copy** → consume the **Lake Registry** contract (`platform/registries/lakes`; not Lake Brain). Lake Registry geometry found under Wind is Lake Registry-owned reference, not Wind truth | REFERENCE (interim: keep file, marked derived) |
| `jobs/wind-hourly/tests/` (8) + fixtures | `brains/wind/tests/` | MOVE |
| `jobs/wind-hourly/research/` (28 scripts) | classify each per §3a: reproducible-and-needed-for-published-claims → `brains/wind/research/tools/`; exploratory → workspace `wind-brain` + `MANIFEST.json` entry (time-sensitive Wind evidence needs durable backup first; nothing moves until approved) | SPLIT |
| `BRAIN.md`, `README.md`, `SESSION_CLOSEOUT.md` | `README.md`; `BRAIN.md` content → operating contract; `SESSION_CLOSEOUT.md` → `docs/history/` | ADOPT/MOVE |
| `feat/wind-brain-adoption` `docs/brains/wind/*` (91) | specs/prereg/rubric → `brains/wind/validation/` & `docs/`; decisions → `docs/history`; data & field packets → workspace | ADOPT selectively (needs Wind certification session's triage) |
| Wind rubric (does not exist; `frozen-scores.json` row) | `brains/wind/scoring/rubric.json` | CREATE at certification |
| Provider code in `sector_wind/{ingest,grib,rrfs,live}` | stays in Wind runtime for V1 (Wind-exclusive NOAA sources); declared in `PROVIDERS.json` as owner=`wind` | REFERENCE; revisit when a second consumer appears |
| Hard-coded iOS/Handoff paths (`bowfishing.py`, `bowfishing_score.py`, `fieldops.py`, 6 research scripts) | env-config + manifest | FIX during migration (behavior-preserving) |
| Platform import via `sys.path` | `pip install` platform package | ADOPT |
| Open-Meteo baseline label in `contract.py` | unchanged (identity of the *production baseline*), not a provider client | REFERENCE |

The Wind migration (Phase 2) additionally requires Gate P (Publisher/Wind shadow findings F-1…F-9 addressed or explicitly resolved by their owning lanes); see `REPOSITORY_MIGRATION_PLAN_V1.md`. Wind-side changes to ownership of legacy paths (F-5) follow the platform-owned / derived-compatibility / legacy-reader classification, never a broadened Wind ownership.

## 6. Conformance check (what an architecture test asserts per Brain; REPORT-ONLY in Phase 1B, see Target §7a for the full 16 invariants)
1. mandatory items exist; 2. `brain.json` validates; 3. `consumes` ⊆ other Brains' declared `publishes`; 4. no imports across `runtime/` boundaries; 5. no absolute user paths; 6. no file > budget without an exception; 7. every test dir registered; 8. `contracts/` has a version; 9. operating contract contains all 19 headings; 10. every research entry points to an `OPEN` gap.
