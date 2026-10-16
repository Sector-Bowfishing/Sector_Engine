# Brain Read/Write Security V1 (target model)

This document is **target-only** and safe for a public repo. Current-state findings about credentials, IAM and rules are kept **privately** and are reviewed per Brain at certification step 9. The public record states only pass/fail.

## 1. Principals and what each may do (target)
| Principal | Read `sector-brain` | Write `sector-brain` | Other |
|---|---|---|---|
| **Specialist Brain** (each, its own identity) | the published paths its contract declares as inputs (its own + upstream contracts) | **none** | writes its artifact to the private artifact store (its own prefix only); reads/writes its own private research/release storage |
| **Orchestrator Publisher** (one identity) | what it needs to validate and plan | **the only writer**, bounded to authorized path families (`BRAIN_PATH_OWNERSHIP_V1.md`) | reads artifacts; appends publication history |
| **Sector Ops** (allowlisted human users) | Ops-visible state | **none to domain truth** (per-user UI preferences may remain, outside domain paths) | sends authenticated requests to the Engine/Orchestrator API |
| **Engine/Orchestrator API** | as needed to authorize | none directly; it hands accepted requests to the Orchestrator/Publisher, which records them | verifies identity, authorization, schema, Brain/action |
| **Customer clients** (iOS, Android, Web) | **none** (no internal Brain DB access) unless a customer-serving contract is separately designed and approved | none | use the Engine API |
| **Humans (emergency)** | yes | break-glass only, logged; must be followed by a republish from canonical state | console edits are never a workflow |
| **Tests / research tools** | read-only helpers at most | **none**; tests use injected transports and refuse real URLs | — |

## 2. Artifact handoff (how a Brain gets output to the Publisher without writing production)
Recommended: **private artifact store** (one private, versioned bucket; prefix per Brain).
1. The Brain run writes `artifacts/{brainId}/{artifactId}.json` (immutable, `ifGenerationMatch=0`) plus its lineage. Its identity may create objects only under its own prefix.
2. The Brain signals completion: through the Orchestrator's execution record when the Orchestrator started it, or through an API publish request carrying `{brainId, artifactId}`.
3. The Publisher reads the artifact, validates (§3), and SKIPs or publishes.
4. Published artifacts remain in the store as HISTORY: they are the rollback source. A rejected artifact remains with its rejection record.

Brains that run in-process inside the Orchestrator today (Fish, Intelligence) follow the same contract: the artifact is persisted before publication, so it has the same lineage, history and rollback as any other.
*Alternative:* the Brain calls the Publisher synchronously with the artifact in the request body. *Why not as the default:* it loses the immutable rollback artifact unless the Publisher persists it anyway, which is the store above.

## 3. Publisher validation (structural only; never scientific)
In order; the first failure rejects the artifact (recorded in history, with no RTDB write):
1. `brainId` is registered; the artifact's identity matches the Brain identity that produced it.
2. `artifactSchema` is allowed for this `brainId`, and the artifact validates against that schema (including `maxBytes`).
3. Every target path is in the Brain's authorized path families. **Cross-domain → REJECT.**
4. `lineage` is complete and well-formed (`BRAIN_IDENTITY_AND_LINEAGE_V1.md` §2); `knowledgeRelease`/`manifestRef` resolve where the Brain declares a release.
5. Lifecycle and status semantics: required fields present; UNKNOWN encoded as UNKNOWN; review and validation status present where the contract requires them; a lifecycle may not claim a value it is not authorized for (e.g. no PRODUCTION without the approval record).
6. `outputFingerprint` recomputed by the Publisher and equal to the declared one; then compared with the current publication record: equal → **SKIP**.
7. **Publish atomically:** one multi-location update containing the artifact paths plus the publication record. If the payload is too large for one write, use manifest-last (status `PARTIAL` first, stop on the first failed chunk, `COMPLETE` last).
8. Append the publication record to history.

The Publisher never edits, recomputes or "fixes" domain values. A wrong value is rejected (structurally) or published as given (scientifically); scientific correctness is the Brain's responsibility.

## 4. Ops control model
```
Michael clicks (Run / Pause / Resume / Research gap / Submit review / Accept-reject rule / Recalculate / Retry)
 → Ops sends an authenticated request (Firebase ID token) to the Engine/Orchestrator API
 → API verifies: identity · allowlist authorization · request schema · Brain and action allowed · confirmation for protected actions
 → the request gets a requestId; the Orchestrator records it in control state (through the Publisher)
 → workflow: control → Orchestrator; review → owning Brain's review process (into its CANONICAL release on the next release);
             research → the Brain's research queue (RESEARCH workspace only)
 → if a specialist runs, it produces an artifact → Publisher validates → publishes
 → Ops observes the resulting state (request outcome + Brain state)
```
Three request kinds (control, review, research) with separate schemas and consumers. Protected actions keep the existing confirm-phrase rule. Engine mode, production lifecycle, customer publication and lifecycle promotion are never grantable through the API. Ops browser code contains no RTDB write calls to domain paths (lint-enforced).

## 5. Enforcement layers (all three are required at certification)
| Layer | Target |
|---|---|
| **RTDB security rules** | client principals: read-only on Ops-visible paths; no client write to domain paths |
| **Google Cloud IAM / service identities** | rules do not bind Admin SDK or service-account credentials with broad database roles. Therefore: specialist identities hold **no** database write capability; only the Publisher identity holds database write; customer app databases are not reachable by Brain identities. Verified per Brain against the identity **actually used** by its jobs and CLIs |
| **Code** | the write client exists only in the Publisher; specialist code paths have no write client (import lint); writes require explicit flags; env vars never enable writing; the ownership check is always on |

**Certification cannot pass on code convention alone.** An application-side URL check or ownership table is a defence-in-depth layer, not the control.

## 6. Local development
Local runs use the developer's own credentials, so local tooling must default to dry-run, refuse production writes outright in the target state (production writes are the Publisher's), and read production through GET-only helpers.
