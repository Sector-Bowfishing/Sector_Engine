# Environment and Species Classification (D5, D6, D7)

> **Superseded in part by Brain Certification V1 (`docs/architecture/certification/`, 2026-10-14).** Where they differ, Certification V1 wins:
> (1) the **Orchestrator Publisher is the only steady-state writer** to `sector-brain`; specialist Brains produce artifacts and do not write production (this document had Brains publishing through a shared `publish()` with their own identity);
> (2) **Ops sends requests through an authenticated Engine/Orchestrator API**, not by creating `/requests/*` nodes in RTDB;
> (3) **species identity is owned by the Species Registry (Engine Platform)**, not by the Fish Brain (`biological-state`); Fish Brain owns species intelligence;
> (4) **no path changes** (including `/speciesProfiles`) are approved by this document; they are decided per Brain during certification.
> In the target-schema and source-of-truth tables, "writer" means the **producing Brain**; the physical writer is the Publisher.


## 1. Today
- `/species` holds 29 Biological records (117 KB), read wholesale by Ops and Intelligence. Records mix identity, an 8-domain knowledge score with history, rule `responseBands`, research workflow metadata and, in one case, per-lake text.
- The customer app ecosystem has **other species lists with different ids**: an app-database `speciesCatalog` (16 coarse groups, dev only, unreachable by rules), a bundled iOS `SpeciesCatalog.swift`, Android's BAA species list, and biology tables in both apps (iOS `SpeciesKnowledgeBase.swift`, Android `fishintel/biology/*`). Engine `Config/SpeciesDatabase.swift` (18 rows) is a scoring adapter.
- Biological intelligence is freshwater-only. There is no environment field anywhere.

## 2. One canonical identity per species (owner: Biological Brain)
`/species/{speciesId}` (≤ 2 KB):
```jsonc
{
  "speciesId": "common_carp",
  "commonName": "Common Carp", "scientificName": "Cyprinus carpio", "aliases": ["carp"],
  "group": null,                               // or "buffalo_group" for grouped targets
  "taxonomyStatus": "ACCEPTED",
  "environments": { "freshwater": "PRIMARY", "brackish": "USES" },   // absent key = not used / not assessed → see note
  "environmentsAssessed": true,                // false → environments map is UNKNOWN, not "freshwater only"
  "primaryEnvironment": "freshwater",
  "intelligenceScope": { "freshwater": "IN_SCOPE", "brackish": "OUT_OF_SCOPE", "marine": "OUT_OF_SCOPE" },
  "knowledge": { "score": 6.1, "coverage": "MODERATE", "researchMaturity": "RESEARCH",
                 "openGapCount": 4, "openDiscrepancyCount": 1,
                 "knowledgeRelease": "2026-10-14.4", "profileFingerprint": "sha256:…" },
  "policy": { /* Policy-layer owned child; Biological never writes it */ },
  "lineage": { /* brain-lineage-v1 */ }
}
```
Values: `environments.*` ∈ `PRIMARY | USES | INCIDENTAL`; `intelligenceScope.*` ∈ `IN_SCOPE | PLANNED | OUT_OF_SCOPE`. Because RTDB drops nulls, "not used" is the absent key **only when `environmentsAssessed: true`**; otherwise the reader must show UNKNOWN.

**Rules**
1. `speciesId` never encodes an environment (`common_carp`, never `freshwater_common_carp`). Classification is multi-valued; identity is single.
2. Group targets (e.g. buffalo, gar groups) are their own ids with `members[]`; app catalog groups map onto these ids (an id map, published by Biological, is the migration tool for the apps — not a second registry).
3. `policy` (legality, invasive status, conservation gate) is owned by the Policy layer (existing decision D5); it lives on the identity record as an owned child so consumers get one record, but Biological's publish never includes it and the ownership check enforces that.

## 3. Indexes (derived, owner: Biological)
`/speciesIndexes/{freshwater|brackish|marine}/{speciesId}: "PRIMARY"|"USES"|"INCIDENTAL"` — rebuilt from identity records in the same publish PATCH. Cheap (≈ 30 bytes/entry); lets Ops and Intelligence filter without reading identity records. Names are `freshwater`, `brackish`, `marine` (the habitat terms; "saltwater" is product copy).

## 4. Profiles (D5): `/speciesProfiles/{speciesId}` — RECOMMENDED
| | `/speciesProfiles/{id}` (recommended) | `/species/{id}/profile` |
|---|---|---|
| Ops wholesale `/species` read | unchanged (≈ 60 KB slim) | grows to ≈ 1.2 MB, re-delivered on every species change |
| Separation of identity vs large derived artifact | yes | no |
| Rules / caching granularity | per root, per child | mixed |
| Platform change needed | add root to ownership table (additive) | none (already implemented on `feat/biological-brain-adoption`) |
| Reader change | Ops reads one profile per species tab | none |
**WHY NOT `/species/{id}/profile`:** it is the cheaper change today and the expensive structure forever; every wholesale reader (Ops, Intelligence, scorer) pays ×10, and RTDB cannot read a node "without its children".
**ALTERNATIVE considered:** profiles only in the private bucket, signed URL from Ops. **WHY NOT:** Ops would need bucket credentials; profiles contain no private material by construction (validator refuses private paths, presence keys), so RTDB serving is fine.

## 5. Behaviour ownership across environments
- **Biological Brain owns species behaviour in every environment.** When marine work starts, it is a new *knowledge domain inside Biological* (rules and movement claims tagged `environments: ["marine"]`), possibly researched by a different lane, released through the same bundle. No second Brain re-owns a species.
- Knowledge records (rules, movement claims, response bands) carry `environments[]` applicability. The profile builder emits per-environment sections only for `IN_SCOPE` environments.
- **Freshwater scoring** (Biological score, coverage) uses target set = species with `intelligenceScope.freshwater == IN_SCOPE` and counts only claims whose `environments` include `freshwater`. Marine-only claims change neither numerator nor denominator; the target-scoped score v2 proposal already scopes by target set and needs only the environment filter.
- **Waterbody environment** belongs to the Lake Registry (`environment: freshwater|brackish|marine` on the registry record, later per-zone for estuaries). Presence (`/lakes/{k}/speciesPresence`) stays Lake-owned and environment-agnostic.
- **Ops filters** by reading `/speciesIndexes/{env}` or filtering slim `/species` on `environments` / `intelligenceScope`.

## 6. Migration cost of adding brackish/marine later
None structural: new index entries, `intelligenceScope` flips, new knowledge in a new release, a registry `environment` attribute on new waterbodies. No path renames, no id changes, no score re-basing for freshwater.
