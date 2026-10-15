# Brain Identity and Lineage V1

## 1. Identifiers
| Id | Form | Meaning | Lifetime |
|---|---|---|---|
| `brainId` | readable kebab-case, **frozen** | logical Brain identity | permanent (renaming needs an explicitly approved migration) |
| `executionId` | UUIDv4 | one run/execution of a Brain or the Orchestrator | one run |
| `artifactId` | UUIDv4, **or** content identity `sha256:<hex>` when the artifact is immutable and content-addressed | one publish artifact produced by a Brain | immutable |
| `publishId` | UUIDv4 | one publication event by the Publisher (one atomic write or one manifest-last chunked write) | immutable |
| `requestId` | UUIDv4 | one control / review / research request from Ops through the API | immutable |
| `releaseId` | per Brain; Fish's existing form is `YYYY-MM-DD.N` | one canonical knowledge release | immutable |
| `speciesId` | snake_case (`common_carp`), Species Registry | one species across all environments | permanent |
| `lakeKey` | `BrainPlatform.lakeKey` / `sector_brain_platform.lake_key` | one lake | permanent |

**Logical Brain ids are never replaced by UUIDs.** Current ids:

| brainId | Display name |
|---|---|
| `lake-brain` | Lake Brain |
| `water-temp` | Water Temperature Brain |
| `water-clarity` | Water Clarity Brain |
| `wind` | Wind Brain |
| `biological-state` | **Fish Brain** (human label; machine id unchanged) |
| `depth` | Depth Brain |
| `vegetation` | Vegetation Brain |
| `sector-intelligence` | Sector Intelligence |

Human-facing terms for `biological-state`: **Fish Brain, Species Intelligence, Species Intelligence Profile, Knowledge Coverage, Research Gaps**. "Study Guide" is retired as UI wording. Contracts and paths are not renamed to match UI wording (e.g. the schema id `biological-species-profile-v1` stays).

## 2. Standard lineage block (`brain-lineage-v1`), on every publish artifact
```jsonc
"lineage": {
  "schema": "brain-lineage-v1",
  "brainId": "wind",                                   // WHO owns it
  "artifactSchema": "wind-lake-state-v1",              // schemaId; with schemaVersion if the family uses integers
  "knowledgeRelease": "wind-model-v1@c6f6232e",        // WHAT canonical release / model version ("NONE" if not applicable)
  "manifestRef": "gs://<private>/releases/<id>/manifest.json",  // release manifest reference ("NONE" if not applicable)
  "manifestSha256": "sha256:…",
  "codeVersion": "c6f6232e",                           // WHAT code produced it: the Brain's OWN commit, not the orchestrator's
  "executionId": "6b0c…",                              // WHO produced it (which run)
  "inputFingerprint": "sha256:…",                      // WHAT inputs (upstream published outputFingerprints + provider payload digests)
  "outputFingerprint": "sha256:…",                     // HAS it changed
  "artifactId": "…",                                   // optional
  "generatedAt": "2026-10-15T03:12:00Z",               // WHEN generated
  "lifecycle": "CALIBRATION",                          // WHAT lifecycle state (Brain Model v1 vocabulary)
  "reviewStatus": "UNREVIEWED",                        // where applicable: UNREVIEWED | PARTIAL | REVIEWED | NOT_APPLICABLE
  "validationStatus": "NOT_VALIDATED"                  // where applicable: claim-maturity summary word
}
```
The **Publisher** adds, on write: `publishId`, `publishedAt` and `publisher` (identity class, never a credential name). "When published" and "can we reproduce it" are answered by the publication record (§3) and the history store.

Per-lake artifacts may carry a compact form (`publishId`, `outputFingerprint`, `generatedAt`), with the full block on the Brain's publication record, to avoid repeating ~400 bytes × 621 lakes.

### Fingerprint rules
- `outputFingerprint = sha256` of the canonical JSON (sorted keys, UTF-8, no insignificant whitespace) of the **material** content, with volatile fields excluded (`generatedAt`, `publishedAt`, `checkedAt`, `ageHours`, `durationMs`, and anything the Brain lists in its contract). Each Brain's contract lists its volatile fields explicitly; the four divergent volatile lists that exist today collapse into the shared default plus per-Brain additions.
- `inputFingerprint` is computed over the upstream `outputFingerprint`s actually read plus digests of provider payloads used. The Orchestrator's existing 16-hex decision fingerprints remain an internal scheduling detail.

## 3. Publication record (written by the Publisher)
`/brains/{brainId}/publication` holds the latest record. Every record is also appended to history storage (`…/publishes/{publishId}.json`) with per-path fingerprints:
```jsonc
{ "publishId": "…", "previousPublishId": "…", "brainId": "wind", "artifactId": "…", "executionId": "…",
  "status": "COMPLETE",                 // COMPLETE | PARTIAL (chunked only) | SKIPPED_UNCHANGED (history only) | REJECTED (history only)
  "publishedAt": "…", "publisher": "orchestrator-publisher", "trigger": "SCHEDULE|DEPENDENCY|MANUAL_REQUEST",
  "requestId": null, "knowledgeRelease": "…", "codeVersion": "…",
  "inputFingerprint": "…", "outputFingerprint": "…", "paths": {"count": 0, "bytes": 0}, "removed": [] }
```
**SKIP and REJECTED are recorded in history only, never in RTDB**, so an idle Brain writes nothing.

## 4. Freshness (standard concepts)
| Field | Meaning |
|---|---|
| `evidenceObservedAt` | when the underlying evidence was observed (provider valid time, observation time) |
| `inputGeneratedAt` | when the upstream published input was generated (consumer Brains), where applicable |
| `generatedAt` | when this artifact was computed |
| `publishedAt` | when the Publisher wrote it |
| `staleAfter` / `expiresAt` | owner-declared: after `staleAfter` it is STALE; after `expiresAt` it must not be used as current |
| `freshnessStatus` | `FRESH` · `STALE` · `EXPIRED` · `UNAVAILABLE` (no evidence exists) · `UNKNOWN` (cannot be determined) |

Rules:
1. **`lastSuccessfulRun` is process health, not evidence freshness.** A parked or MANUAL Brain may be healthy while its evidence is STALE or EXPIRED; both are shown, never merged.
2. Freshness is owner-authoritative (the existing `FRESHNESS_MODEL.md`). Consumers may apply a stricter limit but never a looser one.
3. Consumers propagate: a derived artifact's `freshnessStatus` is no better than its worst REQUIRED input's.
4. UNKNOWN is a value. It is never coerced to FRESH, 0 or false. Ops renders `—`.

## 5. Score publication identity
Different measures are different things. They are never merged or displayed as interchangeable.

| Field | Meaning |
|---|---|
| `scoreType` | `ENGINE_READINESS_SCORE` · `RESEARCH_SCORE` · `VALIDATION_SCORE` · `COVERAGE_SCORE` · `BWIS` (Wind's bowfisher Wind index) · (closed set; a new type needs approval) |
| `scoreValue` | number, or absent with `scoreStatus: UNKNOWN` |
| `scoreVersion` | rubric/definition version |
| `scoreRunId` | the scoring `executionId` |
| `scoreGeneratedAt` | ISO-8601 UTC |
| `scoreScope` | what was scored (e.g. `brain:wind`, `brain:biological-state/targets:freshwater`) |
| `scoreStatus` | `CURRENT` · `STALE` · `HELD` (stale-score guard) · `UNKNOWN` |

Rules:
1. **There is exactly one authoritative current `ENGINE_READINESS_SCORE` per Brain**, at `/scores/{brainId}`. Every other score type lives inside the Brain's own artifact, labelled with its `scoreType`, and is never at `/scores/{brainId}` and never mirrored into the registry, validation or control nodes.
2. The existing score block (`value, scale, basis, scoreVersion, scoreRubric, scoreUpdatedAt, …`) maps onto these fields; existing field names may stay as aliases during migration.
3. **Certification never moves a score.** Record BEFORE and AFTER under the same `scoreType` and `scoreVersion`. A changed definition is a separate, approved change with its own before/after.
4. Known case to reconcile in Wind certification: `/scores/wind` ≈ 3.3, other Wind metadata ≈ 3.1, BWIS 5.4. Decide which record is the authoritative `ENGINE_READINESS_SCORE` and label the others; do not average or pick by recency.

## 6. Overall Engine score (warning; not recomputed during certification)
The current aggregate includes candidate/research maturity from Brains that are not deployed customer models. Before anyone relies on it, define (decision queue):
- included Brains;
- score type (`ENGINE_READINESS_SCORE` only?);
- score version;
- lifecycle eligibility (e.g. ≥ CALIBRATION?);
- whether research-only scores contribute;
- missing-Brain handling (UNKNOWN, not 0);
- stale-score handling (HELD Brains excluded or flagged).

Until then it is displayed as **provisional**. `/engine/score` and `/scores/engine` are the same value (duplicate); do not treat either as certification.
