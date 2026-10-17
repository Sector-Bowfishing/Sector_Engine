# Fish publish artifact — `fish-publication-v1` (SHADOW CONTRACT)

**Status:** implemented and tested; **shadow only**. Not wired into any job, not deployed, no Publisher production write exists. Builder: `brains/fish/runtime/publish_artifact.py`. Declaration (derived from the Publisher registry, `--check`ed): `brains/fish/contracts/fish-publication-v1.json`. Registry: `jobs/brain_platform/sector_brain_platform/publisher/registry.py` (`fish_specs`, `fish_bundles`).

## 1. Shape
ONE `publish-artifact-v2` per Fish execution, bundle `fish-publication-v1`, two sections, ONE atomic plan.

| Section schema | Authorised families | Typed DELETE |
|---|---|---|
| `fish-species-v1` | `/species/{id}` (id = `^[a-z][a-z0-9_]{1,63}$`, value must be an object) | `SPECIES_REMOVED_FROM_REGISTRY` (a species retired from the canonical registry) |
| `fish-registry-v1` | `/brains/biological-state/{child}` (approved children only), `/validation/biological-state`, `/health/brains/biological-state/{status,staleLakeCount}`, `/activity/{event}` (own `-biological-state-` events) | `OPTIONAL_CHILD_CLEARED` (optional registry children only, and only when the baseline still has them) |

Never authorised (tested): the whole `/brains/biological-state` node, `publication` / `certification` (Publisher-owned), any other Brain's node, `/lakes/*/speciesPresence` (Lake Brain), `/speciesProfiles/*`, `/species/{id}/profile` (Species Intelligence Profile publication needs its own reviewed registration and path decision), `/lakeFleet/*` / `/snapshots/*` (no per-lake publication: the Biological State is not a product), `/scores/*`, `/control/*`, `/health/jobs/*`, process/execution health fields.

## 2. Lineage (all fields real; none fabricated)
| Field | Value |
|---|---|
| `brainId` | `biological-state` (producer identity must equal it; checked by the Publisher) |
| `artifactSchema` | `fish-publication-v1` |
| `knowledgeRelease` / `manifestRef` / `manifestSha256` | the verified bundle's `researchVersion`, manifest location (runtime value, private), `sha256:` + its verified manifest hash. All three are required (the schemas set `require_release`) |
| `codeVersion` | the deployed code identity (`DEPLOYMENT_VERSION`) |
| `executionId` | UUIDv4 supplied by the runner (never by the builder) |
| `inputFingerprint` | sha256 of {bundle manifest hash, researchVersion, Brain version} — no execution id, no timestamps |
| `outputFingerprint` | computed by the Publisher's `seal_bundle` (`sector-semantic-fingerprint-v2`) and **recomputed** by the Publisher |
| `generatedAt` | supplied by the runner |
| `lifecycle` | `PROFILED` (== the registry entry's own status; production lifecycles are refused for Fish without an `approvalRef`, and Fish has none) |
| `reviewStatus` / `validationStatus` | `UNREVIEWED` / `NOT_VALIDATED`, derived from the bundle's species maturities; never optimistic (`pa.review_status`, `pa.validation_status`) |
| `artifactId` | assigned by the `ArtifactWriter` (not invented by the builder) |
| `consumed` | passed through only when the platform client recorded reads: `[]` = "read nothing that is a dependency"; **absent = unknown** (offline runs) |

## 3. Semantic fingerprint and idempotence
Volatile contract `fish-volatile-v1` (deliberately minimal; a wrongly-included entry could hide a domain change): keys `updatedAt` (species summaries), `lastRunAt` (validation record); paths `/brains/biological-state/lastSuccessfulRun`, `/brains/biological-state/versions` (embeds the publication date; implied by `researchVersion` + counts), `/activity/{event}` (a log entry caused by other material changes). Shared defaults (`generatedAt`, `publishedAt`, `checkedAt`, `ageHours`, `durationMs`) apply on top. **Proven:** a new `executionId`, a new `generatedAt`, a later `now`, a re-run after the baseline (no version event) and attaching `consumed` all give the same `outputFingerprint`; the Publisher answers **SKIP**. A real knowledge change (new release, changed score) changes the fingerprint and publishes (`SHADOW_READY`). `deploymentVersion` is deliberately material (same as Wind).

## 4. Freshness
No `freshness` block is supplied and `require_freshness` is false for both schemas: species knowledge is **version-driven** (it never goes stale by age). Evidence freshness therefore stays **UNKNOWN** in healthV1 (and `lastSuccessfulRun` — process history — is never used to derive it; tested by source scan and by a health evaluation with a recent successful execution). This is the honest representation, not a defect; see the reuse report for the platform observation (no VERSION-basis freshness statement exists).

## 5. How it is exercised today
`python3 run.py --dry-run [--offline] --bundle DIR --out OUT` (stdlib, no writes) additionally writes `OUT/artifact.json` and prints the in-memory SHADOW Publisher verdict (`result`, `codes`, `live: false`, `outputFingerprint`, mutation counts, `droppedLegacyPaths`). The legacy `--write` path is unchanged (see `FISH_DIRECT_WRITE_AUDIT.md`).

## 6. What the Fish Research session may change without touching this contract
Bundle content (species, rules, bands, cards, profiles) and the release (`researchVersion`, manifest). New species appear as new `/species/{id}` SETs; retired species as typed DELETEs. A new top-level registry child, a new path family, a new section or Species Intelligence Profile publication is a **Publisher registry change** (reviewed), not a research change — the builder fails closed on any registry child the contract does not list, and a test pins that every child the runtime emits is covered.
