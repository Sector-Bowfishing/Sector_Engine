# Brain Data Classification V1

Every meaningful dataset or artifact a Brain touches gets exactly **one** classification. If something seems to need two, it is two artifacts; split it.

| Class | What it is | Examples | Where it lives | Mutability | Deletable? |
|---|---|---|---|---|---|
| **RESEARCH** | raw sources, notes, candidate science, literature, exploration, rejected hypotheses, unresolved analysis, experimental outputs | papers, agency downloads, evidence packets, movement cards, candidate rules, research scripts' outputs | the Brain's research workspace (`Sector Research/<brain>/`) + private versioned backup | captured sources immutable; notes evolve under version control | **No** (may be archived, never discarded without Michael) |
| **CANONICAL** | accepted Brain knowledge; what the Brain believes; its source of truth | released rules, accepted species knowledge, accepted model parameters, registry identity, release manifests | immutable release (manifest + hash) in private versioned storage; local copy under `releases/` | immutable per release; only the "current release" pointer moves | **No** |
| **OBSERVATION_VALIDATION** | field observations, prospective validation ledgers, preregistered evaluation data, accepted validation results, holdout registries | trip observations, prediction ledgers, frozen holdouts, preregistration docs | append-only private versioned storage; `validation/` in the workspace | immutable / append-only; corrections are new records | **Never** |
| **DERIVED** | reproducible from CANONICAL + inputs | compiled profiles, coverage matrices, extracts regenerated from raw, intermediate model outputs | wherever useful; must name what it is derived from | overwrite | yes, once reproducibility is demonstrated (rebuild + fingerprint match) |
| **RUNTIME** | compact current serving state | `sector-brain` states, profiles, registry entries, scores, health | `sector-brain` (via the Publisher only) | overwrite | replaced by the next publish; retired only via path retirement |
| **HISTORY** | immutable prior releases, publish history, score history, accepted decisions, rollback artifacts, RTDB exports, handoffs | publication records, `review_ledger.jsonl`, old releases, Wind deploy rollback package, handoffs | private append-only history storage; handoffs folder | immutable / append-only | **No** |
| **OBSOLETE_CANDIDATE** | appears superseded or unreferenced | an old extract no code reads, a superseded candidate bundle | stays where it is | — | **Never deleted on this classification alone.** It must be reclassified (usually as DERIVED with proven reproducibility, or HISTORY) and pass retirement |

## Rules
1. **Classification is about the data, not its location.** A raw dataset in a bucket is RESEARCH; a release sitting on a laptop is still CANONICAL and needs its private versioned copy.
2. **Irreplaceable classes** (RESEARCH, CANONICAL, OBSERVATION_VALIDATION, HISTORY) must have a private versioned backup that is **not** the local Mac. This is exit evidence B.
3. Only RUNTIME data goes into `sector-brain`. RESEARCH never does.
4. DERIVED is deletable only after its rebuild is demonstrated. If the rebuild cannot be demonstrated, it is HISTORY.
5. A lifecycle cleanup rule (GCS lifecycle, pruning job) may target only DERIVED or bounded RUNTIME/control data, and must name the class of every prefix it touches.
6. Licence restrictions are recorded alongside the class (`licence: RESTRICTED|OPEN|UNKNOWN`). Restricted material is RESEARCH and never leaves private storage.
7. Shared datasets (`Sector Research/shared`) carry the same classes plus an owner (`BRAIN_RESEARCH_WORKSPACE_V1.md` §4).

## Inventory record (one row per artifact during certification step 2/3)
`path | bytes | class | owner | used by (code ref) | canonical? | duplicate of | rebuildable from | historical evidence? | backup location | licence | proposed action (ADOPT_INTO_WORKSPACE | REFERENCE_IN_PLACE | MOVE_TO_SHARED | KEEP | RECLASSIFY)`
