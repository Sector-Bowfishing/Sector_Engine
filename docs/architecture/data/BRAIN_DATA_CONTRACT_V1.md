# Brain Data Contract v1 (`brain-data-contract-v1`)

> **Superseded in part by Brain Certification V1 (`docs/architecture/certification/`, 2026-10-14).** Where they differ, Certification V1 wins:
> (1) the **Orchestrator Publisher is the only steady-state writer** to `sector-brain`; specialist Brains produce artifacts and do not write production (this document had Brains publishing through a shared `publish()` with their own identity);
> (2) **Ops sends requests through an authenticated Engine/Orchestrator API**, not by creating `/requests/*` nodes in RTDB;
> (3) **species identity is owned by the Species Registry (Engine Platform)**, not by the Fish Brain (`biological-state`); Fish Brain owns species intelligence;
> (4) **no path changes** (including `/speciesProfiles`) are approved by this document; they are decided per Brain during certification.
> In the target-schema and source-of-truth tables, "writer" means the **producing Brain**; the physical writer is the Publisher.


**Status:** PROPOSED. Extends, does not duplicate, the existing surfaces:
- registry `/brains/{id}` (`BRAIN_PLATFORM_CONTRACT.md` — `brainId, domain, version, schemaVersion, dependsOn[], schedule{}, models{}, versions[], validation{ref,status}, sourceIds[], descriptor{}`, `deploymentVersion`, `platform{}`),
- Model v1 additive fields (`model, lifecycle, executionType, claims[], dependencies[], fingerprint{ingredients}`),
- control manifest (`docs/brains/platform/orchestrator/control_manifest.json` — `allowedTriggers, dependencies[].usesFields, freshness, fingerprint{outputSource,materialFields}, costClass, customerPublication`),
- `/jobs` manifest (`inputs, outputs, statePaths, sourceLineage, consumers`).

None of those say **where a Brain's knowledge lives, what it publishes where, how long anything is kept, or how a publish is traced**. This contract adds exactly that, as one `data` block per Brain in the control manifest (single source; not re-published per run), plus the runtime `lineage` and `publication` records defined in `PUBLISHING_AND_PROMOTION_MODEL.md`.

## 1. The `data` block (declared once, in the control manifest)
```jsonc
"biological-state": {
  // … existing control-manifest fields unchanged …
  "data": {
    "contract": "brain-data-contract-v1",
    "domainOwner": "biological-state",              // = brainId; who owns the science
    "inputs": [                                      // what it READS (never re-owns)
      {"from": "lake-brain",  "path": "/lakes/{k}/speciesPresence", "grain": "PER_LAKE", "use": "target set"},
      {"from": "water-temp",  "path": "/lakes/{k}/states/waterTemp", "grain": "PER_LAKE", "use": "thermal response"},
      {"from": "water-clarity","path": "/lakes/{k}/states/waterClarity","grain": "PER_LAKE","use": "visibility response"}
    ],
    "research": {"repo": "Sector_Research/biological-brain", "bucket": "gs://sector-research-private/biological-brain/"},
    "canonical": {"kind": "RELEASE_BUNDLE", "bucket": "gs://sector-biology-private", "pointer": "latest.json",
                  "releaseId": "YYYY-MM-DD.N", "approval": "MICHAEL"},
    "published": [
      {"path": "/species/{speciesId}",          "schema": "biological-species-registry-v2", "grain": "PER_SPECIES", "maxBytes": 2048,  "readPattern": "COLLECTION_OK"},
      {"path": "/speciesIndexes/{env}/{speciesId}", "schema": "species-index-v1",        "grain": "PER_SPECIES", "maxBytes": 16,    "readPattern": "COLLECTION_OK"},
      {"path": "/speciesProfiles/{speciesId}",  "schema": "biological-species-profile-v1","grain": "PER_SPECIES", "maxBytes": 65536, "readPattern": "LEAF_ONLY"},
      {"path": "/brains/biological-state",      "schema": "brain-registry-v1",            "grain": "BRAIN",       "maxBytes": 16384, "readPattern": "COLLECTION_OK"},
      {"path": "/validation/biological-state",  "schema": "validation-summary-v1",        "grain": "BRAIN",       "maxBytes": 8192,  "readPattern": "COLLECTION_OK"}
    ],
    "outputFingerprint": {"over": ["/speciesProfiles/*", "/species/*"], "excludes": ["generatedAt", "publishedAt"]},
    "freshness": "KNOWLEDGE",                         // KNOWLEDGE (changes only on release) | OBSERVATION (provider-driven) | DERIVED
    "observation": {"store": "release:validation/*.jsonl", "mutability": "APPEND_ONLY"},
    "retention": {"runtime": "CURRENT_ONLY", "releases": "FOREVER", "publishManifests": "FOREVER", "activity": "PLATFORM_DEFAULT"},
    "validationSource": "release:validation/predictions.jsonl + observations.jsonl",
    "downstream": ["sector-intelligence", "ops"],
    "allowedTriggers": "see control manifest",        // not redeclared
    "costClass": "see control manifest",              // not redeclared
    "rollback": "REPUBLISH_FROM_RELEASE"              // REPUBLISH_FROM_RELEASE | REDEPLOY_PRIOR_IMAGE | NONE_SELF_HEALING
  }
}
```

### Field rules
| Field | Rule |
|---|---|
| `inputs[].from` | must be a different Brain (or `provider:<id>`); a Brain may **never** list its own published path as an input of another Brain's domain, and must never appear in `published` for a path whose domain owner is another Brain |
| `canonical.kind` | `RELEASE_BUNDLE` (knowledge Brains: Biological, Depth, Vegetation, Lake registry/presence) · `CODE_AND_PROVIDERS` (observation Brains: Wind, Water Temp, Clarity — their "knowledge" is the model code + config in git) · `NONE` (Intelligence: code + evidence catalog) |
| `published[].path` | must exist in `TARGET_SECTOR_BRAIN_SCHEMA.json` with this Brain as owner; the platform ownership table is generated from these entries (one list, not two) |
| `published[].maxBytes` | enforced by `validate()` before publish; exceeding it fails the publish, not silently truncates |
| `published[].readPattern` | `COLLECTION_OK` (parent may be read whole; children must be small) · `LEAF_ONLY` (consumers read one child at a time; no whole-collection listener allowed — Ops lint) |
| `freshness` | selects the existing freshness model (`FRESHNESS_MODEL.md`); not a new staleness rule |
| `retention.runtime` | always `CURRENT_ONLY` for RTDB; history lives in `gs://sector-brain-history` |
| `rollback` | must be executable without the Firebase console |

## 2. Per-Brain declaration (current proposal)

| Brain | Inputs (owner) | Canonical | Published | Freshness | Rollback |
|---|---|---|---|---|---|
| `lake-brain` | providers (TVA, CWMS, USGS, RISE, NWPS) | RELEASE_BUNDLE-like: `gs://sector-lake-brain` (presence, baselines), `gs://sector-lake-registry` | `/lakes/{k}/{brain,states/lake,speciesPresence}`, `/lakeFleet/{k}/slots/lake`, `/brains/lake-brain`, `/validation/lake-brain`, `/sources/{owned}` | OBSERVATION | REDEPLOY_PRIOR_IMAGE (state) / restore baseline generation (knowledge) |
| `water-temp` | providers | CODE_AND_PROVIDERS (+ archive bucket) | `/lakes/{k}/{states,profiles}/waterTemp`, fleet slot, registry, validation, sources | OBSERVATION | REDEPLOY_PRIOR_IMAGE |
| `water-clarity` | providers, `/conditions` (to remove — read providers or Lake directly) | CODE_AND_PROVIDERS (+ candidate bucket) | `/lakes/{k}/{states,profiles}/waterClarity`, fleet slot, registry, validation, sources | OBSERVATION | REDEPLOY_PRIOR_IMAGE |
| `wind` | providers, Lake registry geometry | CODE_AND_PROVIDERS (+ `gs://sector-wind-candidate`) | `/lakes/{k}/{states,profiles,validation}/wind`, fleet slot, registry, validation, sources | OBSERVATION | REDEPLOY_PRIOR_IMAGE (`413bbbae` package) |
| `biological-state` | Lake presence, Water Temp, Clarity (Depth, Vegetation later) | RELEASE_BUNDLE `gs://sector-biology-private` | `/species/*`, `/speciesIndexes/*`, `/speciesProfiles/*`, registry, validation; later `/lakes/{k}/states/biology` | KNOWLEDGE (+ DERIVED for outlooks) | REPUBLISH_FROM_RELEASE |
| `depth` | Lake state + registry geometry | RELEASE_BUNDLE (to create; decide public/private) | `/lakes/{k}/states/depth`, fleet slot, registry, validation | KNOWLEDGE | REPUBLISH_FROM_RELEASE |
| `vegetation` | Lake registry, imagery | RELEASE_BUNDLE (to create) | `/lakes/{k}/states/vegetation` (later), registry | KNOWLEDGE | REPUBLISH_FROM_RELEASE |
| `sector-intelligence` | all specialists' published states/profiles, Lake presence | NONE (code + evidence catalog) | `/lakes/{k}/states/intelligence`, fleet slot, registry, validation | DERIVED | rerun prior image |
| platform (`brain-platform`) | all published facts | code (`score_brains.py`, frozen scores) | `/scores/*`, `/control/{overview,beta}`, `/lakeFleet/{k}/rollup` | DERIVED | republish from prior score history |
| orchestrator | `/brains`, `/jobs`, `/scores`, `/requests/control` | control manifest + Cloud Scheduler | `/control/orchestratorV1/*`, `/jobs/*`, `/requests/control/{id}/outcome` | CONTROL | redeploy prior image |

## 3. Invariants (each becomes a test in campaign C2/C3)
1. Every `published[].path` maps to exactly one owner in the target schema; the ownership table in `ownership.py` is generated from the manifest `data` blocks.
2. `BrainRtdb` refuses a write with no `brain_id`; the platform writer uses an enumerated exception list.
3. A Brain's publish touches only its declared paths plus `/activity` (own events) and `/health/{brains/self, sources/owned}`.
4. No Brain lists another Brain's domain path in `published`.
5. Every published artifact carries `lineage` (`PUBLISHING_AND_PROMOTION_MODEL.md` §3); `validate()` fails without it.
6. `maxBytes` is enforced; `LEAF_ONLY` paths may not be read wholesale by any reader (Ops lint + Engine reader lint).
7. UNKNOWN rules (`SECTOR_DATA_OWNERSHIP_ARCHITECTURE.md` §12) are checked by `validate()` for required enum fields.
