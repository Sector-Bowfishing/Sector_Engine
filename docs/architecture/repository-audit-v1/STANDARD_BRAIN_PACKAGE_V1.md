# Standard Brain Package V1 (PROPOSED)

**Status:** `REPOSITORY_ARCHITECTURE_PROPOSED_V1`. Defines what a Brain's permanent GitHub home contains. Consistency without bureaucracy: **six mandatory items, the rest optional**. No Brain-specific contract is written by this audit.

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

Do not create empty directories. A directory exists only when it holds a file with a purpose.

## 2. Component table

| Item | Why it exists | Mandatory? | Belongs there | Must NOT belong there |
|---|---|---|---|---|
| `README.md` | orientation for humans and agents | yes | identity, bowfisher decision, map of this directory, how to run tests, links | duplicated contract text; status history |
| `BRAIN_OPERATING_CONTRACT.md` | the rules a Brain session obeys; discoverable, versioned | yes | all §3 sections | evidence, findings, handoffs, run logs |
| `brain.json` | one machine-authoritative declaration used by registry, Publisher, Orchestrator, CI | yes | §4 fields | prose, thresholds, scientific parameters |
| `contracts/` | published interface other Brains/Publisher/Engine rely on | yes (even if "none published yet": a stub declaring `UNPUBLISHED`) | JSON Schemas, version, consumer note, example payload | private schemas, research formats |
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

**Machine-authoritative fields:** `schemaVersion`, `brainId`, `displayName`, `humanName`, `domain`, `lifecycle` (platform lifecycle vocabulary), `contractVersion`, `runtime` (`kind: job|in-process|service`, language, entrypoint, trigger kind/stale hours), `publishes[]` (artifact schema ids, path families, family names), `consumes[]` (brainId + contract id + min version; provider ids), `providers[]` (ids used), `researchWorkspace` (logical id), `score` (type, path, rubric path), `customerDirect` (`none` | `embedded:<lib>`), `publisherRequired` (bool + cutover status), `authorizedConsumers[]`, `tests[]`, `dataBudget`, `docs` pointers.
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
| `jobs/wind-hourly/lakes.json` | **delete as copy** → consume Lake registry contract (`brains/lake/contracts`) | REFERENCE (interim: keep file, marked as derived) |
| `jobs/wind-hourly/tests/` (8) + fixtures | `brains/wind/tests/` | MOVE |
| `jobs/wind-hourly/research/` (28 scripts) | classify each: reproducible-and-needed-for-published-validation → `brains/wind/research/tools/`; exploratory → workspace `wind-brain` + `MANIFEST.json` entry | SPLIT |
| `BRAIN.md`, `README.md`, `SESSION_CLOSEOUT.md` | `README.md`; `BRAIN.md` content → operating contract; `SESSION_CLOSEOUT.md` → `docs/history/` | ADOPT/MOVE |
| `feat/wind-brain-adoption` `docs/brains/wind/*` (91) | specs/prereg/rubric → `brains/wind/validation/` & `docs/`; decisions → `docs/history`; data & field packets → workspace | ADOPT selectively (needs Wind certification session's triage) |
| Wind rubric (does not exist; `frozen-scores.json` row) | `brains/wind/scoring/rubric.json` | CREATE at certification |
| Provider code in `sector_wind/{ingest,grib,rrfs,live}` | stays in Wind runtime for V1 (Wind-exclusive NOAA sources); declared in `PROVIDERS.json` as owner=`wind` | REFERENCE; revisit when a second consumer appears |
| Hard-coded iOS/Handoff paths (`bowfishing.py`, `bowfishing_score.py`, `fieldops.py`, 6 research scripts) | env-config + manifest | FIX during migration (behavior-preserving) |
| Platform import via `sys.path` | `pip install` platform package | ADOPT |
| Open-Meteo baseline label in `contract.py` | unchanged (identity of the *production baseline*), not a provider client | REFERENCE |

The current Wind certification session consumes this mapping after Michael approves the target.

## 6. Conformance check (what an architecture test asserts per Brain)
1. mandatory items exist; 2. `brain.json` validates; 3. `consumes` ⊆ other Brains' declared `publishes`; 4. no imports across `runtime/` boundaries; 5. no absolute user paths; 6. no file > budget without an exception; 7. every test dir registered; 8. `contracts/` has a version; 9. operating contract contains all 19 headings; 10. every research entry points to an `OPEN` gap.
