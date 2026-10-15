# <Display name> — BRAIN OPERATING CONTRACT

> Template (Standard Brain Package V1). Every section is mandatory; write "N/A: <reason>" rather than deleting one. Terminology: **bowfisher / bowfishers** only. This file holds rules and decisions, never evidence, findings, handoffs or run logs. It cites platform rules, never copies them. Structured ids and edges live in `brain.json` and are referenced here, never repeated.
>
> A Brain is not a university: research begins from a named product, confidence, readiness, validation or evidence gap and has a stop condition.

## 1. IDENTITY
`brainId` (stable machine id, see `brain.json`), display and human name, domain, lifecycle state, contract version, owner.

## 2. MISSION
One paragraph: the domain truth this Brain owns.

## 3. BOWFISHER DECISION
The bowfisher decision(s) this Brain helps make. Outputs that do not change a bowfisher decision are out of scope.

## 4. OWNERSHIP
Data, models, rules, identifiers, RTDB path families and the readiness score this Brain owns.

## 5. NON-OWNERSHIP
What it explicitly does not own (e.g. species identity, lake identity, legality, lake presence, customer scoring).

## 6. DEPENDENCIES
Brains, providers and registries (Lake Registry, Species Registry) consumed, each with the contract version.

## 7. COMMUNICATION CONTRACTS
Published contracts (`contracts/`), consumers, allowed communication paths. No private-research reads; no Brain-to-Brain private imports.

## 8. RESEARCH WORKSPACE
Logical workspace id (e.g. `wind-brain`), the `SECTOR_RESEARCH_ROOT` resolution rule, shared-folder rules, backup class. Never a physical path.

## 9. RESEARCH INITIATION RULES
Research starts only to close a **named, OPEN** gap in `research/GAPS.json` (product, confidence, readiness, validation or evidence gap).

## 10. RESEARCH STOP RULES
Stop when more work no longer changes a useful bowfisher-facing decision, or when field validation, another Brain, or human approval is required.

## 11. EVIDENCE HIERARCHY
Ranking of evidence types and what each may support (claim levels per platform models).

## 12. CANONICALIZATION
How research becomes a canonical release: gate, approver, versioning, rollback.

## 13. VALIDATION
What validation exists, what is NOT validated, validation vs architecture certification, field-validation needs.

## 14. PUBLISHING
Artifact schema ids, publish families, cadence/trigger, freshness rule, Publisher requirement, `customerIntegrationMode` and its restrictions.

## 15. PATH OWNERSHIP
RTDB/storage path families and rejection rules (`brainId → schema → path family`).

## 16. SCORING
Rubric location, score type, what can and cannot move the score. Certification never moves a score.

## 17. COST RULES
Job cadence and ceilings, provider costs, data-egress limits, cost-freeze compliance.

## 18. SECURITY
Public-repo rules for this Brain, secrets, writer identity, what stays private. No private IAM/security detail, customer data or per-lake private observations in this public repo.

## 19. SESSION CLOSEOUT FORMAT
Required closeout fields: gap addressed, bowfisher decision affected, evidence, files changed, tests, score before/after, open gaps, human/field validation needed.
