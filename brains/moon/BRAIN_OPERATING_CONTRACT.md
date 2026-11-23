# Moon and Night Light Brain — BRAIN OPERATING CONTRACT

> Standard Brain Package V1. Terminology: **bowfisher / bowfishers** only. Rules and decisions only; evidence lives in tests and `research/`. Ids and edges live in `brain.json`.

## 1. IDENTITY
`brainId` `moon` (directory `brains/moon`). Display name "Moon and Night Light Brain", human name "Moon and Night Light", domain `condition`, lifecycle **CALIBRATION**, contract version 1.0.0. Owner: Michael (owner decision 2026-11-22, Sector_Ops #51).

## 2. MISSION
For every lake in the lake registry (621 directory lakes), compute tonight's moon phase and illumination, moonrise and moonset, sunset and sunrise, and the end of civil, nautical and astronomical twilight, using a standard published algorithm. Then classify how much moonlight reaches the water across the fishing window (the on-water darkness class), using cloud cover from the Weather Brain when it is available.

## 3. BOWFISHER DECISION
When it is dark enough to start shooting tonight, and which nights have the least moonlight competing with the boat's lights. The class describes shooter visibility only. It makes no claim about fish depth, spookiness or feeding.

## 4. OWNERSHIP
- The Brain's computation: the sector-moon-v1 ephemeris port (`runtime/moon_brain/ephemeris.py`), the event finder (`events.py`), the night and window definition (`night.py`) and **DARKNESS_RULE_V1** (`darkness.py`).
- The state contract `contracts/moon-night-light-v1.json` and the Publisher declaration `contracts/moon-publication-v1.json`.
- The path families in `brain.json` `publishes` (slot `moon`, snapshot field `moonNightLight`), declared so the Brain can be certified. The live writer is gated (below).
- The packaged knowledge release `runtime/knowledge/` (the lake-directory projection).

## 5. NON-OWNERSHIP
- The moon spec itself: `contracts/moon/moon-v1.json` is shared with the Engine, iOS, Android and Web. A change goes to the spec and every copy, never to this port alone.
- Lake identity and coordinates (registry.lakes, `Sources/SectorEngine/Support/LakeDirectory.swift`).
- Cloud cover and every other weather value (the Weather Brain).
- The Engine's conditions score and its darkness factor (the Engine). The Moon and Night Light Brain has no official score.
- Customer surfaces: nothing customer-facing reads this Brain.

## 6. DEPENDENCIES
- registry.lakes 1.0.0, REQUIRED (through the packaged projection; a test fails when it drifts from the Engine's directory).
- Weather Brain cloud cover, OPTIONAL: the Weather state `sector-brain-weather-state-v1` (`forecast.hourly[].cloudCoverPct`, `sky.cloudCoverPct`). Declared in `brain.json` `consumes` (weather-publication-v1 1.0.0, OPTIONAL). The cloud covers only the part of the fishing window still ahead at the Weather run (a state holds 12 forecast hours); the span is reported. No provider is called.

## 7. COMMUNICATION CONTRACTS
`moon-night-light-v1` (the per-lake state) and `moon-publication-v1` (the Publisher bundle). Authorized consumers: `ops`, `sector-intelligence`. No private-research reads and no imports of another Brain's runtime.

## 8. RESEARCH WORKSPACE
Logical workspace `moon`, resolved through `SECTOR_RESEARCH_ROOT`. Nothing is stored in it yet. Never a physical path.

## 9. RESEARCH INITIATION RULES
Research starts only to close an OPEN gap in `research/GAPS.json`.

## 10. RESEARCH STOP RULES
Stop when more work no longer changes which nights a bowfisher would call dark, or when another Brain's contract or an owner decision is needed.

## 11. EVIDENCE HIERARCHY
1. USNO published values (rise/set, twilight, principal phases): the reference the astronomy is tested against.
2. The shared moon spec vectors (`moon-v1.json`): equality with the Engine, iOS, Android and Web.
3. The Engine's DarknessFactor constants: the source of DARKNESS_RULE_V1 so the Brain and the app agree. A rule, not evidence of on-water light.

## 12. CANONICALIZATION
The knowledge release (lake-directory projection) is regenerated with `python -m moon_brain.lakes --write` and a new release id. Its approval is NOT_RECORDED. A change to DARKNESS_RULE_V1 is a new rule id, stated in the contract before any night is classified with it.

## 13. VALIDATION
- Validated: the astronomy against USNO (rise/set and twilight within 2 min, principal phases within 20 min), and the moon spec's 52 vectors.
- NOT validated: the darkness class against measured on-water light (gap MOON-VAL-001). `/validation/moon` says NOT_VALIDATED.
- Architecture certification (Brain Cert Kit V1) is separate from science validation.

## 14. PUBLISHING
The live writer is gated. `runtime/run.py --tonight` writes a local JSON file; `--dry-run` builds the RTDB write set in memory; `--write` publishes through `moon_brain.writer.RtdbWriter` (the platform client) and refuses unless the knowledge release is APPROVED (exit 2) and `MOON_WRITE_APPROVED=1` is set (exit 3). A live run reads each lake's Weather state from the Brain RTDB and uses it only when it was generated within 3 h (the dependency's maxAgeHours). When cloud cover is missing the answer is **MOON_ONLY**, labelled as such, and no cloud value is assumed. Cadence when enabled: once per night per lake, hourly once cloud cover is wired. `customerIntegrationMode` `none`; customer publication NOT_ELIGIBLE.

## 15. PATH OWNERSHIP
`moon` → `moon-lake-state-v1` → `/lakes/{k}/states/moon`, `/lakeFleet/{k}/{slots,readiness,modelVersions}/moon`, `/snapshots/{k}/latest/{moonNightLight, brainVersions/moon}`; `moon` → `moon-registry-v1` → `/brains/moon/{child}`, `/validation/moon`, `/health/brains/moon/{status,staleLakeCount}`. Lake identity fields are platform-owned. Any other path is rejected by the Publisher.

## 16. SCORING
The Moon and Night Light Brain has no official score: no rubric has been approved. Nothing is written under `/scores`.

## 17. COST RULES
Pure computation, no provider calls, no cloud job. The control manifest declares costClass NONE. The full directory computes in a few seconds on one CPU.

## 18. SECURITY
No secrets, no credentials, no writer identity. Lake coordinates are public registry data.

## 19. SESSION CLOSEOUT FORMAT
Gap addressed, bowfisher decision affected, evidence (tests, USNO cross-check), files changed, tests run, score before/after (none), open gaps, human or field validation needed.
