# Repository Audit Decisions: RA-1 … RA-23 (LOCKED)

**Decision date:** 2026-10-14 (Michael). **Status:** `REPOSITORY_ARCHITECTURE_V1_APPROVED_FOR_PHASE_1` (see `REPOSITORY_ARCHITECTURE_V1_DECISION_LOCK.md`).
Approval authorizes **additive Phase 1A/1B work only**, each phase still starting on its own go-ahead. It authorizes no runtime move, no deploy, no push, no branch/worktree deletion.

| ID | Decision | Result | Locked text (summary) | Applies in |
|---|---|---|---|---|
| RA-1 | Top-level ownership tree | **APPROVED** | `engine/ providers/ platform/ contracts/ brains/ verification/ tools/ deploy/ docs/` (amended Phase 1B: `verification/` replaces root `tests/`, see decision lock §6)`; root build/bootstrap files stay; directory expresses ownership | 1A |
| RA-2 | `brains/<dir>/brain.json` | **APPROVED WITH GUARDRAILS** | JSON; machine-authoritative for structured identity and edges only; no prose/research reasoning; no absolute Desktop path (logical workspace id e.g. `wind-brain`, env/config resolves root); not a seventh manual registry; generated registries derive from it and old copies retire only after proven equivalence; the operating contract stays authoritative for behavior | 1A schema; 2+ per Brain |
| RA-3 | Operating contract `brains/<dir>/BRAIN_OPERATING_CONTRACT.md`, 19 sections | **APPROVED** | mandatory for final certification; no `ARCHITECTURE_CERTIFIED_V1` without README + contract + `brain.json` + required contracts/runtime/tests correctly represented | 2+ |
| RA-4 | Directory names | **APPROVED** | `wind fish lake water-temperature water-clarity depth vegetation sector-intelligence`; machine ids unchanged (`fish` ↔ `biological-state`) | 2+ |
| RA-5 | Lake identity ownership | **APPROVED WITH CHANGE** | **Platform owns canonical entity identity.** Lake Registry = canonical lake identity; Lake Brain = intelligence about lakes. Mirrors Species Registry vs Fish Brain. Wind/Clarity/Temperature/Fish consume the Lake Registry contract, not Lake Brain, to resolve identity. Registries named explicitly: `platform/registries/{brains,lakes,species}/`. Git-vs-release-storage split for the 621-lake dataset defined in Target §6a. Not implemented now. | 1A skeleton; Lake phase |
| RA-6 | Wind first | **APPROVED WITH UPDATED GATE** | Wind is Brain #1, Fish #2, Audit #1 after both. Wind migration requires **A** architecture locked, **B** additive skeleton, **C** baseline CI/conformance/golden gates, **D** Publisher/Wind shadow issues F-1…F-9 addressed or explicitly resolved (by the owning lanes) | Gate for Phase 2 |
| RA-7 | Embedded adapter mode | **APPROVED WITH CLARIFICATION** | `customerIntegrationMode: none | embedded | published`. `embedded` = customer Engine imports/executes a Brain-owned contract/library; NOT Brain writes customer DB; NOT Brain calls customer internals. Direction: Customer Engine → Brain contract/library, never Brain → Engine implementation. Eliminates Clarity's `/conditions` dependency in the Clarity phase | Standard package; Water Temp/Clarity phases |
| RA-8 | Provider layer + `PROVIDERS.json` | **APPROVED WITH PRACTICAL BOUNDARY** | fields at minimum: `providerId`, `acquisitionOwner`, `authorizedConsumers`, `costClass`/budget, `healthOwner`, `licenseRef`. Brain-exclusive single-consumer clients may stay with the Brain while registered with explicit ownership and movable without changing the Brain contract. Shared/reused/customer-serving acquisition converges on `providers/`. No per-Brain duplicate general-purpose Open-Meteo clients | 1A schema; incremental |
| RA-9 | No TVA consolidation before D8 | **APPROVED** | no cleanup may silently change Midnight-row semantics or customer results | all |
| RA-10 | Ownership semantics split | **APPROVED WITH EXPLICIT SEMANTICS** | `acquisitionOwner`, `healthOwner`, `authorizedConsumers`, `domainInterpreter` are distinct; `ownership.py`'s single "owner" must stop standing for all four. Design updated; implementation later | design now |
| RA-11 | Runtime JSON leaves `docs/` | **APPROVED** | runtime JSON, runtime-required fixtures/config leave `docs/`; behavior never depends on documentation paths | 1B (conformance), then per Brain |
| RA-12 | CI understands `brain.json` | **APPROVED** | Brain coverage derived from `brain.json`; non-Brain infrastructure (platform, provider, customer Engine, cross-cutting integration) enrolled explicitly; `brain.json` is not the only way into CI. Phase 1 adds Swift tests, missing Python job/tool tests, architecture/conformance checks, clean-clone install/import checks | 1B |
| RA-13 | Split Swift tests by owner | **APPROVED** | incremental, behavior-preserving, part of the Swift move order | Phase 6/7 |
| RA-14 | Read-only private-content review | **APPROVED** | precedes any relocation of historical docs/snapshots; no cleanup/deletion; private IAM/security findings stay out of the public repo | before historical doc moves |
| RA-15 | Generated/large-data policy | **APPROVED** | ≥ 1 MB tracked content needs a documented reason; generated runtime data records source, generator, version/provenance, rebuild instructions | 1B check (report-only) |
| RA-16 | Research metadata in repo | **APPROVED** | `GAPS.json`, manifest metadata, preregistration/validation protocols, accepted/rejected decision records; never raw data; research starts from a named gap with a stop condition | per Brain |
| RA-17 | Research branch handling | **APPROVED WITH CHANGE** | no automatic bulk move of `docs/*-research`; classify each meaningful artifact at the Brain's turn into GitHub / external research workspace / canonical versioned storage (Standard package §3a); manifest/reference/hash instead of copying | per Brain |
| RA-18 | Clarity D4 | **DEFERRED, recorded as HARD CLARITY-PHASE BLOCKER** | choose among the live/off-main job options and reconcile the actual deployment source before Clarity can be migrated/certified. Does NOT block Phase 1, Wind, Fish, or Audit #1 | Clarity phase |
| RA-19 | Depth/Vegetation branches | **APPROVED** | preserved; adopted only at their certification turn | per Brain |
| RA-20 | Clarity stops using customer `/conditions` and `/lakes` | **APPROVED** | replace with provider/platform/Lake Registry/Brain contracts during the Clarity phase; no runtime change now | Clarity phase |
| RA-21 | Root README | **APPROVED** | updated during migration to describe the whole platform and point to architecture docs; not a duplicate of them | during migration |
| RA-22 | Swift move order | **APPROVED** | split tests → platform target → providers target → Brain library targets → physical move; protect build/test behavior | Phase 6/7 |
| RA-23 | Branch/worktree hygiene separate | **APPROVED** | no deletion as part of migration; historical branches are evidence until reconciled | after Phase 7 |

## Blockers and gates recorded by the lock
| Item | Blocks | Does not block |
|---|---|---|
| **D4** (Clarity live/off-main job source) | Clarity migration/certification (hard) | Phase 1, Wind, Fish, Audit #1 |
| **D8** (TVA Midnight rows) | any TVA consolidation | everything else |
| **D5** (policy/legality gate) | moving `SpeciesLegality` out of the scoring path | Phase 1 |
| **Publisher/Wind shadow findings F-1…F-9** | Wind Phase 2 (RA-6 D) and Wind final Publisher certification | Phase 1A/1B |
| **Publisher production-security gate** | any live cutover (certification/security lane; no private detail in repo) | repository migration of non-cutover files |
| **RA-14 review** | relocating historical docs/snapshots | Phase 1A, Phase 1B (only fixtures move) |

## Still open after the lock
No decision blocks Phase 1A. Informational: confirm the final names `platform/registries/{brains,lakes,species}/` (default adopted); 1B records, rather than fixes, any pre-existing baseline failure; the Lake dataset split (Target §6a) is finalized at the Lake phase.

## Governed elsewhere (not re-decided here)
CERT-1…9, D5, D8, Publisher security model.
