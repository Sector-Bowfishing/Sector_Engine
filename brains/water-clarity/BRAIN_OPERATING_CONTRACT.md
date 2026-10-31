# Water Clarity Brain — BRAIN OPERATING CONTRACT

> Standard Brain Package V1, 19 sections. Read this first in every Water Clarity research or build session. It states rules and decisions, never evidence, findings, handoffs or run logs. Structured identity and edges live in `brain.json`; platform rules are cited, not copied. A Brain is not a university: research starts from a named gap and stops on a stop condition.
> Contract version **1.0.0** (Water Clarity Structural Certification V1, 2026-10-18). Written from the Clarity gap audit and certification record (`docs/architecture/certification/water-clarity/`); it adds no new policy and no clarity science. Where this file and the certification record disagree, the certification record wins until this file is corrected.

## 1. IDENTITY
`brainId` **`water-clarity`** (stable machine id, never renamed). Display name "Water Clarity Brain", human name "Water Clarity", domain `condition`, lifecycle **CALIBRATION** (science: production clarity **not validated as a customer number**; a certified research candidate exists and is `NOT_DEPLOYED`). Brain slot/snapshot field `waterClarity`. Home: `brains/water-clarity/`. The scope of this package is **component C1, the Brain publisher** (see §6); C2 (lake-surface pipeline), C3 (ClarityPrecompute), C4 (candidate shadow) and C5 (production Engine clarity) are separate components and are not part of this implementation. Owner: the Water Clarity lane (Michael approves).

## 2. MISSION
Water Clarity answers: **what does the water look like?** Today the Brain *restates* production clarity for every lake (the Engine `/conditions` clarity estimate, plus the newest usable satellite evidence from the lake-surface pipeline) as semantic Brain state with provenance, readiness and quality flags. It does not compute the customer number and it does not decide whether a lake is fishable.

## 3. BOWFISHER DECISION
Clarity informs whether the water is likely clear enough to see fish under lights, and — only as a hint — which part of a lake looks better. It makes **no promise beyond current truth**: the published number is a production estimate whose model is not validated for every lake, and `clarityClass` (a band taxonomy) is deliberately unpublished until Michael decides it. An output that does not change that decision is out of scope.

## 4. OWNERSHIP
- Domain truth: the lake clarity state and profile (`/lakes/{k}/states|profiles/waterClarity`) and the lake-fleet slot/readiness/model-version projections, the Clarity registry children (`/brains/water-clarity/{child}`), `/validation/water-clarity`, the domain health facts `/health/brains/water-clarity/{status,staleLakeCount}`, source health for the sources Clarity owns (`/sources/{id}`, `/health/sources/{id}` for sentinel-2-l2a, usgs-nwis-turbidity, noaa-mrms), and its own `-water-clarity-` activity events.
- Clarity interpretation: state types, readiness rule, quality flags, the model roster and certification status, sensor-authority and processing-path records, the strong policy ("not evaluated" until a consensus model is deployed).
- The Clarity score definition; the published value lives at `/scores/water-clarity` (frozen research score; written by the Platform scorer).
Exact authorised path families: `contracts/clarity-publication-v1.json` (derived from the Publisher registry).

## 5. NON-OWNERSHIP
Clarity does **not** own: the production clarity **number** (the customer Engine computes `secchi-power-v1` / `rain-decay-v0`; the Brain restates it — ownership debt RA-20); **lake identity** (the Lake Registry); Sentinel-2 acquisition and the satellite pipeline (C2, same domain but a separate job); water temperature, depth, wind, vegetation (their Brains); the "where tonight" synthesis (Sector Intelligence); labels and display wording (Sector Ops owns all labels); Publisher publication metadata (`/brains/water-clarity/publication`, `certification`); job/process/execution health and `/health/jobs/*`; lake-fleet roll-ups and `lakeId` fields; snapshot compatibility copies (Publisher-derived); activity retention.

## 6. DEPENDENCIES
The dependency truth is `contracts/INPUTS_V1.json`, derived from the code and pinned by tests. In summary:
- **Declared in `brain.json`:** the Lake Registry (`consumes registry lakes`, REQUIRED). Caveat, recorded not blessed: C1 reads the lake directory through the **customer Engine `/lakes` endpoint**, not through a registry contract; no registry contract version is actually read (**RA-20**).
- **Read but not declarable as a dependency edge:** the customer Engine `/conditions` clarity estimate for every lake (**RA-20 ownership debt — not a legitimate long-term dependency**); the lake-surface pipeline's GCS outputs (C2 is this Brain's own pipeline, class OWN_PIPELINE_OUTPUT); C2 run records and the Engine revision label (operational metadata); the local catalog and the optional private overlay (own model); lake outlines (static input).
- **Providers: none declared.** C1 calls no provider; Sentinel-2 L2A, USGS NWIS turbidity and NOAA MRMS reach it through the Engine and C2. **Signals: none. Other Brains: none.**
- **Lineage of HTTP/GCS reads is NOT recorded** (the platform's actual-consumption recorder covers RTDB reads only). The artifact therefore carries `consumed` absent (= unknown), never an empty list and never a fabricated entry (**GCS_HTTP_LINEAGE_PLATFORM_DEBT**).
- Platform: `sector_brain_platform` (envelope, keys, ownership, consumption recorder, Publisher `seal_bundle` and registry), at `jobs/brain_platform` (legacy location; resolved by `runtime/brain_platform.py`).

## 7. COMMUNICATION CONTRACTS
- Published: **`clarity-publication-v1`** — ONE `publish-artifact-v2` per execution, three sections (`clarity-lake-state-v1`, `clarity-registry-v1`, `clarity-source-registry-v1`), sealed with the Publisher's `seal_bundle`, fingerprint `sector-semantic-fingerprint-v2`, volatile contract `clarity-volatile-v1`, a single typed DELETE (`OPTIONAL_CHILD_CLEARED` for `/brains/water-clarity/lastError`). Declaration: `contracts/clarity-publication-v1.json`; builder: `runtime/publish_artifact.py`. **Shadow only**: proven against the Publisher in non-production mode; not wired into the job's write path.
- Consumers (`brain.json` `authorizedConsumers`): Ops and Sector Intelligence read published Clarity state; they never read Clarity's runtime or research.
- Allowed path today: Engine/GCS/Brain-RTDB reads → C1 runtime → one sealed artifact (CENTRAL mode, private bucket) → Orchestrator → central Publisher. `--dry-run` writes local files only. The direct RTDB writer is retired in code (X14).

## 8. RESEARCH WORKSPACE
Logical workspace id **`water-clarity`** (`brain.json` `researchWorkspace`). The physical root is resolved by the research operator, never written into code or architecture (this repository is public). The Engine repository owns architecture and policy; the workspace owns Clarity research material. Raw research, the research branch corpus, agency request material and private catalog detail are never embedded in the runtime package, never committed, and never stored in `sector-brain`. The production runtime never reads the workspace or any Desktop path (enforced by tests).

## 9. RESEARCH INITIATION RULES
Research starts only to close a **named, OPEN** gap recorded in `research/GAPS.json` (schema `contracts/schemas/research-gaps.schema.json`). A research session adds knowledge to the workspace and, after review, to the private catalog overlay; it does **not** change this package's structure. Certification and structure work are separate sessions and never change science.

## 10. RESEARCH STOP RULES
Stop when more reading no longer changes a bowfisher-facing decision, when the remaining question needs field observations, when it needs another component or the Platform (Lake Registry, Publisher), or when it needs Michael's approval (promotion of a model, a band taxonomy, publication, spending, live changes). A stop is recorded, not worked around.

## 11. EVIDENCE HIERARCHY
Highest to lowest: (1) independent field clarity observations on the water scored against a frozen method; (2) agency in-situ Secchi/turbidity data matched by site and day; (3) in-situ turbidity gauges converted by a validated relation; (4) satellite-derived estimates with documented sensor authority; (5) rainfall-driven heuristics and practitioner reports as hypotheses. Unvalidated models are labelled `NOT_VALIDATED`; the Brain never upgrades them by restating them.

## 12. CANONICALIZATION
The production clarity number is canonical in the Engine; the Brain's catalog (`runtime/catalog.json`, plus the optional private overlay) is the canonical statement of models, certification *status*, sensor authority and processing paths. Detailed research results are canonical only in the private research workspace/archive and reach the Brain only as the private overlay at run time. Promotion of a model to production is a separate decision (Michael) and a separate deployment; no structural work promotes anything.

## 13. VALIDATION
Exists: unit tests on every builder, the science-preservation golden, rejection/shape tests against the Publisher, the production validation record published at `/validation/water-clarity` (status-level in the public catalog). **Not validated:** the customer clarity number as a whole (rain-decay-v0 has no validation; the satellite number does not reproduce southern Secchi in absolute feet); every lake's `strong` state is `NOT_EVALUATED`. Architecture certification is separate from scientific validation and never implies it.

## 14. PUBLISHING
Target: Clarity produces the `clarity-publication-v1` artifact and **only the Publisher** writes `sector-brain` (`publisherRequired.required = true`, cutover status **SHADOW**). `run.py` has no database write site (the direct writer is retired in code, X14; the status flips to `CUTOVER_COMPLETE` only with the exit record of an approved cutover); there is no scheduler (execution is MANUAL by decision). Freshness: TIME model (`staleAfterHours` 26) applied to the Engine evaluation time the estimate restates; the artifact keeps four times apart — satellite scene observation (`evidenceObservedAt`), Engine evaluation (`inputGeneratedAt`), Brain generation (`lineage.generatedAt`) and publication (Publisher). `lastSuccessfulRun` is process history, never evidence freshness; UNKNOWN stays UNKNOWN. `customerIntegrationMode` **none**.
Fail-closed behaviour: fewer than 100 lakes in the directory → refuse to publish; an Engine miss for a lake keeps its last good state and ages it to stale (never blanks it); a malformed Engine payload yields `UNAVAILABLE` with unknown values absent, never zero; a builder path no registration covers aborts the artifact build.

## 15. PATH OWNERSHIP
Authorised families and their schemas: `contracts/clarity-publication-v1.json`. Rejection order is the Publisher's: `brainId → bundle/section schema → path family` (`CROSS_DOMAIN_PATH`, `RESERVED_PATH`, `BRAIN_NODE_REPLACEMENT`, `PLATFORM_DERIVED_PATH`, `PATH_NOT_AUTHORIZED`). Clarity never widens its own families; a change is a Publisher registry change reviewed with Clarity certification. GCS writes by C2–C4 are outside the Publisher's RTDB path families (**GCS_WRITE_SEMANTICS_PLATFORM_DEBT**) and are not part of this contract.

## 16. SCORING
Score type `ENGINE_READINESS_SCORE` at `/scores/water-clarity`. The current value is a **frozen research score** (8.0 / 10, `clarity-research-certification-r3.1`, basis FROZEN) that belongs to the certified research *candidate*; production clarity is unscored. Certification, repository migration and structural work never move it; it is not a production-quality score and promotes nothing.

## 17. COST RULES
Pre-production: OFF by default. No schedule, no always-on service; one manual bounded run (one Engine `/conditions` call per lake, ≈ 621 per run — a known cost; a slimmer source is part of the RA-20 replacement). Cost-freeze rules in `docs/brains/platform/` apply; no new scheduled cloud work without approval.

## 18. SECURITY
This repository is public: no secrets, service-account keys, IAM bindings, private bucket contents, private catalog detail, research thresholds/populations, agency request material or research corpus in Git (guarded by `tests/test_clarity_certification.py`). The runtime reads the optional private overlay from a path or private object supplied at run time. Firebase RTDB IAM is project-wide; the code refuses app-database URLs. Open item: least-privilege scoping of the writer.

## 19. SESSION CLOSEOUT FORMAT
Every Water Clarity session closes with: gap addressed (id); bowfisher decision affected; evidence (references, hashes; private items by location id only); files changed; tests run with PASS/FAIL/BLOCKED_DEPENDENCY/NOT_RUN; score before/after (must be equal unless an approved scoring change); open gaps; human/field validation needed; confirmation of what was not changed (live systems, schedulers, customer behaviour, lifecycle, science).
