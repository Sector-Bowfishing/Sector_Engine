# Fish Brain — BRAIN OPERATING CONTRACT

> Standard Brain Package V1, 19 sections. Read this first in every Fish research or build session. It states rules and decisions, never evidence, findings, handoffs or run logs. Structured identity and edges live in `brain.json`; platform rules are cited, not copied. A Brain is not a university: research starts from a named gap and stops on a stop condition.
> Contract version **1.0.0** (Fish Structural Certification V1, 2026-10-17). Written from the Fish gap audit and certification record (`docs/architecture/certification/fish/`); it adds no new policy and no species science. Where this file and the certification record disagree, the certification record wins until this file is corrected.

## 1. IDENTITY
`brainId` **`biological-state`** (stable machine id, never renamed; the directory `brains/fish/` differs from the id by design). Display name "Fish Brain", human name "Fish", domain `biology`, lifecycle **PROFILED** (science `NOT_VALIDATED`). Vocabulary: Fish Brain, Species Intelligence, Species Intelligence Profile, Knowledge Coverage, Research Gaps. Contract version: see `brain.json` `contractVersion`. Owner: the Fish Brain lane (Michael approves). Home: `brains/fish/`.

## 2. MISSION
Fish answers two questions: **what does Sector know about this fish?** (species knowledge: evidence-completeness scores, machine rules, response bands, movement knowledge — published today) and **what is this fish likely doing on this lake right now?** (the Biological State — an internal pilot, `NOT_STARTED` as a product). It never decides where to go tonight (Sector Intelligence does) and never measures the environment.

## 3. BOWFISHER DECISION
Fish helps a bowfisher decide **what to expect of a species and when to look for it**: season and spawn windows (as ranges), habitat and depth-class preference, night movement support, which environmental conditions tend to be favourable or limiting, and how sure Sector is of each. An output that does not change one of those decisions is out of scope. Fish describes tendencies with honest confidence; it does not promise a fish.

## 4. OWNERSHIP
- Domain truth: species knowledge summaries (`/species/{id}`), the Fish registry children (`/brains/biological-state/{child}`), `/validation/biological-state`, the domain health facts `/health/brains/biological-state/{status,staleLakeCount}`, its own `-biological-state-` activity events.
- Biological interpretation: species behaviour, movement, seasonal and spawn state, species-response bands, rules and their evidence discipline, the Biological State pilot, and the Biological validation chain (frozen rule register, prediction log, observation schema, preregistered criterion).
- The Fish score definition (`biological-state-score-v1`); the published value lives at `/scores/biological-state` and is written by the Platform scorer.
Exact authorised path families: `contracts/fish-publication-v1.json` (derived from the Publisher registry).

## 5. NON-OWNERSHIP
Fish does **not** own: **species identity** (canonical species identity belongs to the Platform Species Registry, `platform/registries/species`; today identity travels inside the private bundle — audit gap G-1, behaviour unchanged); **legality / regulation** (policy layer); **where a species is present** (Lake Brain `speciesPresence`); water temperature, clarity, depth, vegetation, wind, pool level (their Brains); the final "where tonight" synthesis (Sector Intelligence); Publisher publication metadata (`/brains/biological-state/publication`, `certification`); generic job/process/execution health (Orchestrator); `/scores/*` (Platform); the customer species table (customer Engine). No Brain-to-Brain private import.

## 6. DEPENDENCIES
- Platform: `sector_brain_platform` (envelope, keys, ownership, consumption recorder, Publisher `seal_bundle` and registry), currently at `jobs/brain_platform` (legacy location; resolved by `runtime/brain_platform.py`, vendored into the orchestrator image).
- Own knowledge release: the private canonical bundle (`latest.json` → manifest → hash-verified files). This is Fish's **own release**, not another party's state: it is represented in artifact lineage (`knowledgeRelease`, `manifestRef`, `manifestSha256`), never as a fabricated `consumed[]` dependency.
- Other Brains: **none** (`consumes: []`). Providers: **none**. Signal Registry signals: **none** — Fish consumes no formal signal today and declares none (no `pressure-trend`, `moon-phase`, …). Registries read: none.
- Not yet declared, on purpose: the Biological State pilot (`run_state.py`, `bio_state.py`, `contracts_in.py`) reads published Lake / Water Temperature / Clarity snapshot slots when run by hand. It is internal, unscheduled and publishes nothing; its inputs are declared **when it graduates into an orchestrated execution** (and each declared edge must come with recorder instrumentation, as `run_state.py` already has). A declaration that no execution consumes would only add `declaredNotConsumed` noise.

## 7. COMMUNICATION CONTRACTS
- Published: **`fish-publication-v1`** — ONE `publish-artifact-v2` per Fish execution, two sections (`fish-species-v1`, `fish-registry-v1`), sealed with the Publisher's `seal_bundle`, fingerprint `sector-semantic-fingerprint-v2`, volatile contract `fish-volatile-v1`, explicit typed DELETE only (`SPECIES_REMOVED_FROM_REGISTRY`, `OPTIONAL_CHILD_CLEARED`). Declaration: `contracts/fish-publication-v1.json`; builder: `runtime/publish_artifact.py`. **Shadow only**: proven against the Publisher in non-production mode; not wired into the job.
- Consumers (`brain.json` `authorizedConsumers`): Ops and Sector Intelligence read published Fish state (`/species`, `/brains/biological-state`), never Fish's runtime or research.
- Allowed paths: private bundle → Fish runtime → artifact → Publisher → `sector-brain`. Today the in-process job still writes through the platform client (`run.py --write`, LEGACY, ownership-checked) until the approved Publisher cutover.

## 8. RESEARCH WORKSPACE
Logical workspace id **`fish-brain`** (`brain.json` `researchWorkspace`). The physical root is resolved by the research operator (`<Sector Research root>/fish-brain`), never written into code or architecture (this repository is public). Layout: `sources/ datasets/ research/ analysis/ candidates/ validation/ releases/ manifest.json README.md`. The Engine repository owns architecture and policy; the workspace owns Fish research material. Raw research is never embedded in a runtime package and never stored in `sector-brain`. The production runtime never reads the workspace or any Desktop path (enforced by tests).

## 9. RESEARCH INITIATION RULES
Research starts only to close a **named, OPEN** gap recorded in `research/GAPS.json` (schema `contracts/schemas/research-gaps.schema.json`). A research session adds knowledge to the workspace and, after review, to a new canonical release; it does **not** change this package's structure. New species, rules or response bands enter through the private bundle and its tooling (`runtime/tools/`), not through new runtime code paths.

## 10. RESEARCH STOP RULES
Stop when more reading no longer changes a bowfisher-facing decision, when the remaining question needs field validation (observations on the water), when it needs another Brain or the Platform (Species Registry, Lake Brain presence, Publisher), or when it needs Michael's approval (promotion of a research maturity, publication, spending, live changes). A stop is recorded, not worked around.

## 11. EVIDENCE HIERARCHY
Highest to lowest: (1) pre-registered prospective field observations (including non-encounters) scored against frozen rules; (2) agency data and peer-reviewed regional (Southeast reservoir) studies read in full; (3) peer-reviewed studies from other regions, flagged by transferability; (4) agency statements and grey literature; (5) practitioner knowledge (bowfisher reports) as hypotheses; snippet-only or unopened sources never count (enforced in `runtime/rules.py`). Claim levels follow the platform `CLAIM_LEVEL_MODEL`: provider-observed inputs (L1), deterministic features (L2), species responses (L3, `NOT_VALIDATED`).

## 12. CANONICALIZATION
The canonical knowledge release is the versioned, hash-pinned private bundle (`biology/v1`, `latest.json` → manifest). A release requires: a manifest of file hashes, the Brain's fail-closed validation (`biological_brain.validate`), review, and Michael's approval to promote. Rollback = point `latest.json` at the previous release. Research location never makes anything canonical; promotion of a species' research maturity (REVIEWED / VALIDATED) is a separate decision the runtime refuses to make on its own.

## 13. VALIDATION
Exists: rubric arithmetic checks on every release, rule evidence-discipline tests, frozen-rule register and hash-chained prediction log, preregistered validation criterion (hash-pinned), Publisher shadow acceptance of the artifact. **Not validated:** no species rule has been compared with a field outcome; every species is at research maturity `RESEARCH`. Architecture certification is separate from scientific validation and never implies it.

## 14. PUBLISHING
Target: Fish produces the `fish-publication-v1` artifact; **only the Publisher** writes `sector-brain` (`publisherRequired.required = true`, cutover status **SHADOW**). Today the orchestrator runs `run.py` in-process and `--write` still performs one ownership-checked atomic update (LEGACY, retirement candidate at cutover). Cadence: none (version-driven: runs when the canonical bundle changes). Freshness: evidence freshness is **UNKNOWN** by design (species knowledge never goes stale by age); `lastSuccessfulRun` is process history, not evidence freshness. `customerIntegrationMode` **none**.

## 15. PATH OWNERSHIP
Authorised families and their schemas: `contracts/fish-publication-v1.json`. Rejection order is the Publisher's: `brainId → bundle/section schema → path family` (`CROSS_DOMAIN_PATH`, `RESERVED_PATH`, `BRAIN_NODE_REPLACEMENT`, `PLATFORM_DERIVED_PATH`, `PATH_NOT_AUTHORIZED`). Fish never widens its own families; a change is a Publisher registry change reviewed with Fish certification. Per-lake species presence is Lake Brain's path; Fish can never write it.

## 16. SCORING
Score type `ENGINE_READINESS_SCORE` at `/scores/biological-state` (Platform writes it). Rubric `biological-state-score-v1` (baseline: `verification/fixtures/scores/score_baseline.json`); computed from the live published facts. Certification and repository migration never move a score. The rubric mixes architecture-like and domain-science dimensions — documented, not redesigned here (`feat/biological-score-v2` is a separate isolated proposal).

## 17. COST RULES
Pre-production: OFF by default. No recurring schedule, no always-on service, no provider polling; one bounded in-process run when the bundle changes (≈1 vCPU, 0.5 GiB, minutes). Research runs locally. Cost-freeze rules in `docs/brains/platform/` apply; no new scheduled cloud work without approval.

## 18. SECURITY
This repository is public: no secrets, service-account keys, IAM bindings, private bucket contents, per-lake species presence labels, rule JSON, packets or research text in Git (guarded by `tests/test_rules_state_validation.py`). The artifact carries a runtime reference to the private manifest, never its content. The Fish runtime gets read access to the private bundle and write access only through the ownership-checked platform client.

## 19. SESSION CLOSEOUT FORMAT
Every Fish session closes with: gap addressed (id); bowfisher decision affected; evidence (references, hashes; private items by location id only); files changed; tests run with PASS/FAIL/BLOCKED_DEPENDENCY/NOT_RUN; score before/after (must be equal unless an approved scoring change); open gaps; human/field validation needed; confirmation of what was not changed (live systems, customer behaviour, species identity, lifecycle).
