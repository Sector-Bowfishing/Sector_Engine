# Wind Brain: publish artifact V1 (step 7; DESIGN ONLY, nothing implemented)

Conforms to `BRAIN_READ_WRITE_SECURITY_V1.md` §2-3 and `BRAIN_IDENTITY_AND_LINEAGE_V1.md`. Wind computes this; the Orchestrator Publisher validates and publishes it. Wind never writes production. Proposed items needing Michael's decision are marked **[D]**.

## 1. Envelope
```jsonc
{
  "artifactSchema": "wind-publish-artifact-v1",
  "lineage": {
    "schema": "brain-lineage-v1",
    "brainId": "wind",
    "artifactSchema": "wind-publish-artifact-v1",
    "knowledgeRelease": "wind-model-v1@<codeCommit>",   // [D] see §4: no canonical release object exists yet
    "manifestRef": "gs://<private artifact bucket>/…/manifest.json",  // or "NONE" until a release manifest exists
    "manifestSha256": "sha256:…",
    "codeVersion": "<wind commit sha12>",                // Wind's own commit; not the orchestrator's, not a hard-coded "main@"
    "executionId": "<uuid of the wind-hourly run>",
    "inputFingerprint": "sha256:…",                      // digests of NBM cycle id, RTMA-RU valid time, METAR payload digest, fetch-table shas
    "outputFingerprint": "sha256:…",                     // canonical JSON of material content, volatile fields excluded (§3)
    "artifactId": "sha256:<outputFingerprint hex>",      // content-addressed (artifact is immutable)
    "generatedAt": "…Z",
    "lifecycle": "CALIBRATION",
    "reviewStatus": "UNREVIEWED",
    "validationStatus": "NOT_VALIDATED"                  // or PARTIAL where the registry says PARTIAL; use the existing validation word, do not upgrade
  },
  "freshness": { /* §5 */ },
  "scores": [ /* §6: labelled by scoreType, informational for the Publisher */ ],
  "set":    { "<absolute RTDB path>": <value>, … },     // everything to write
  "remove": [ "<absolute RTDB path>", … ]               // explicit deletes only; never implied by a missing value
}
```
`set` contains the existing, unchanged record shapes: `sector-brain-wind-state-v1`, `sector-brain-wind-profile-v1`, the lake-validation record, the fleet slot, readiness, modelVersions, the registry node, the validation summary, source and source-health nodes, health nodes, activity events. **No scientific value is recomputed or reshaped by certification.** Per-lake records may carry only the compact lineage form (`publishId` added by the Publisher, `outputFingerprint`, `generatedAt`); the full block is on the Brain publication record.

## 2. Authorized path families (anything else is REJECTED)
Exactly the `wind` row of `BRAIN_PATH_OWNERSHIP_V1.md` §1:
1. `/lakes/{k}/states/wind`
2. `/lakes/{k}/profiles/wind`
3. `/lakes/{k}/validation/wind`
4. `/lakeFleet/{k}/slots/wind`, `/lakeFleet/{k}/readiness/wind`, `/lakeFleet/{k}/modelVersions/wind`
5. `/brains/wind` (registry; **not** `/brains/wind/publication` or `/certification`, which the Publisher writes)
6. `/validation/wind`
7. `/health/brains/wind`
8. `/sources/{noaa-nbm-v5|noaa-rtma-ru|iem-metar-wind}` and `/health/sources/{same}` (Wind is acquisition owner; non-owner may be added only as `authorizedConsumers`)
9. own `/activity/{id}` events (id pattern strict `…-wind-…` for the Publisher, matched on the brain field, not substring)
10. **transitional (status `LEGACY_READER_PRESENT`):** `/snapshots/{k}/latest/wind` and `/snapshots/{k}/latest/brainVersions/wind`, written only in the **same atomic publish** as the state, and removed from the allow-list at path retirement.

**Explicitly rejected (Publisher tests):** `/speciesProfiles/*`, `/species/*`, any other Brain's `/lakes/{k}/states/*|profiles/*|validation/*|speciesPresence|brain`, any `/brains/{other}`, `/scores/*`, `/control/*`, `/jobs/*`, `/access`, `/engine/*`, `/lakeFleet/{k}/lakeId` and roll-up fields, `/snapshots/{k}/latest/{other fields}`. Includes the required row "`wind` → `/speciesProfiles/common_carp` → REJECT".

Also: `/scores/wind` (the one `ENGINE_READINESS_SCORE`) belongs to Platform; Wind supplies the score *evidence* but does not write it.

## 3. Fingerprint and material-change semantics
- `outputFingerprint` = sha256 of canonical JSON of `set` + `remove` with the **shared volatile defaults** (`generatedAt`, `publishedAt`, `checkedAt`, `ageHours`, `durationMs`) plus Wind additions: `provenance.generatedAt`, `provenance.inputAgeHours`, `lastRun`, `lastSuccess`, `updatedAt`, `deploymentVersion` build-label text where it varies without behaviour change.
- **Material for Wind:** evidence values and their valid times (`observationTime`, `forecastGeneratedAt`, wind/gust/direction, hourly arrays, `stale`, `kind`), readiness, profile content, validation summary, source health status and counts, model/Brain version.
- **Consequence [D]:** the hourly states carry new provider data every cycle, so the 4 lake states and the slot change on essentially every run, whereas **profiles, `readiness` (621 rows), `modelVersions`, `validation`, sources and registry rarely change**. Per-path fingerprints let the Publisher write only changed paths in one atomic update (drops the ~1,260-path unconditional rewrite to roughly the 4 states, 4 slots, health and activity) while a fully unchanged run is a SKIP. Decision needed: whether a run whose only change is a new `observationTime` with identical values counts as material (recommended: **yes**, because `observationTime` is evidence time).
- Mandatory: `remove[]` is explicit. The current null-on-miss for `lakes/{k}/validation/wind` is replaced by "omit from `set`, keep the existing record, mark `validationStatus: UNKNOWN`", never a silent delete.

## 4. Canonical release and manifest (open)
No CANONICAL Wind release object exists today: model v1 is code + config + the candidate bucket's frozen fetch tables (`fetch/national/MANIFEST.json`, the only manifest) + the baked `validation_evidence.json`. Proposed **[D]**: a `wind-model-v1` release = {commit sha, `MANIFEST.json` sha256, fetch-table shas, `validation_evidence.json` sha256, rubric/BWIS definition shas}, stored immutable in the private versioned artifact bucket (CERT-3, **not created yet**), with a local copy in `Sector Research/wind-brain/releases/`. Until then `knowledgeRelease` uses `wind-model-v1@<commit>` and `manifestRef: "NONE"` with a recorded warning.

## 5. Freshness fields (gap analysis)
| Required | Today | Artifact |
|---|---|---|
| `evidenceObservedAt` | `observationTime` (state), `forecastGeneratedAt` | map from `observationTime` (analysis) / NBM cycle time; per lake |
| `inputGeneratedAt` | n/a: Wind is a primary acquirer | `NOT_APPLICABLE` |
| `generatedAt` | `provenance.generatedAt` | keep |
| `publishedAt` | none | Publisher |
| `staleAfter` / `expiresAt` | none (rule text only: >3 h NBM, >90 min `generatedAt`) | **new fields, populated from the existing rule: `staleAfter = min(generatedAt + 90 min, newest NBM cycle + 3 h)`; no threshold change [D: confirm the same numbers define `expiresAt`, or leave `expiresAt` absent]** |
| `freshnessStatus` | boolean `stale` | derive FRESH/STALE; UNAVAILABLE when `kind="unavailable"`; UNKNOWN never coerced |
| `lastSuccessfulRun` | `/health/brains/wind` | kept as process health, shown separately |

Wind's scientific freshness thresholds are **not** changed. A successful job does not imply fresh evidence: a run that archives yesterday's NBM cycle must publish `STALE`.

## 6. Scores in the artifact
`ENGINE_READINESS_SCORE` is not written by Wind. The artifact may carry `scores[]` entries `{scoreType, scoreValue, scoreVersion, scoreRunId, scoreGeneratedAt, scoreScope, scoreStatus}` for `BWIS` (labelled, never at `/scores/wind`). The legacy `/brains/wind.scores` mirror is dropped only after Ops reads `/scores/wind`.

## 7. Cutover constraints
Wind still writes `/snapshots/{k}/latest/wind` until Ops and Sector Intelligence move to `states/wind`. One atomic multi-path update per run (≈1.3k paths, well under a single-write limit once unchanged paths are skipped); manifest-last chunking is not needed. The Publisher records the publication under `/brains/wind/publication`; history includes SKIP and REJECTED.
