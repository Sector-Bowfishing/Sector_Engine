# `biological-species-profile-v1`: the Biological species study guide contract (Ops-facing)

**Owner:** Biological Brain. **Consumers:** Sector Ops (renders), future Intelligence tooling, internal research tooling. **Status:** implemented and tested; generated for every canonical species from the staged candidate bundle; **not published** (publication needs Michael's approval; see "Where Ops reads it").
**Schema:** `BIOLOGICAL_SPECIES_PROFILE_SCHEMA.json` (JSON Schema 2020-12, generated from the code constants; all 34 generated profiles validate). **Examples:** `species-profile/COMMON_CARP_PROFILE_EXAMPLE.json` (strong) and `species-profile/BOWFIN_PROFILE_EXAMPLE.json` (incomplete). **UI intent:** `BIOLOGICAL_SPECIES_PROFILE_UI_INTENT.md`.

## What it is
A living study guide for one fish: how it moves through the year, when it is shallow, how temperature, water level, habitat, light and current affect it, how strong the evidence is, what has been reviewed and field-validated, and exactly what Sector does not yet know. **Ops renders it; it never reads species-v2, rules, movement cards, packets or ledgers.** Biological owns the interpretation. The profile is **derived deterministically** from canonical Biological state (species knowledge + movement card + rules + season assertions + review ledger + prediction/observation logs). There is no second source of truth: change the knowledge, a rule, a review decision or a validation record and the regenerated profile changes. It is regenerated on those events only (no cron, no recurring cost).

## Where Ops reads it (proposal; nothing is published yet)
`/species/{speciesId}/profile` (one fish page), and `/brains/biological-state/coverageMatrix` (the all-fish overview). **Do not read `/species` wholesale from the browser once profiles are published:** a profile is 20-60 KB compact JSON (34 profiles total about 1.1 MB). Read one fish at a time (REST `.../species/{id}/profile.json`). A dedicated `/speciesProfiles` root would be cleaner but needs a shared-platform ownership change (queued as a decision). The publisher emits profiles only when `include_profiles=True`; the current publisher is unchanged.
RTDB drops null and empty values, so **an absent field means UNKNOWN / not applicable**; treat `completeness`, `scientificName`, lists and similar as optional.

## Top level
| Key | Meaning |
|---|---|
| `contract` | always `biological-species-profile-v1` |
| `generatedFrom` | research version, rules version, features version, card version, bundle time. Freshness is "current with this bundle" |
| `identity` | `speciesId`, `sectorLabel` (the existing customer label, never renamed), `scientificName`, `role` (TARGET / SECONDARY / KNOWLEDGE_ONLY), `habitatClass`, `habitatFlag`, `canonical`, optional `doNotResearch` reason |
| `summary` | `knowledgeStatus` (PROFILED / THIN / NOT_ASSESSED / PROPOSED), `bowfisherKnowledge` and `speciesV2Score` (diagnostics, may be absent), `generalConfidence`, `regionalConfidence`, `reviewStatus`, `fieldValidationStatus`, `ruleCount`, `strongest`, `weakest` |
| `yearlyMovement` | the 12-month timeline, condition modifiers, spawn window, conflicts |
| `seasonalGuide` | winter / spring (pre-spawn, spawn, post-spawn) / summer / fall: what to look for and why |
| `spawn`, `temperature`, `depth`, `hydrology`, `habitat`, `dayNight`, `clarityLight`, `currentWaterbody` | study-guide sections: `coverage`, `statements[{label,text,confidence,regionalConfidence,claimIds}]`, `openQuestions` (shown as UNKNOWN, never filled), `rules` |
| `bowfisherGuide` | plain-English "how to find this fish": takeaway, seasons, night, best shallow window |
| `knowledgeCoverage`, `knowledgeGapMatrix`, `knowledgeGaps`, `researchPriorities` | what Sector knows, what it does not, and what is worth learning |
| `rulesSummary` | every rule in plain English with status, review, field state, seasonality, `fires` |
| `evidenceSummary` | source counts by type, inspected counts, strongest source, claim maturity, `claims` (provenance by claim id), `sources` (public metadata only) |
| `reviewSummary`, `validationSummary` | human review and field validation, independent of knowledge |

## Yearly movement (the 12-month track)
`months[12]` JAN..DEC. Each month: `movementStates[]` (WINTER_HOLDING, PRE_SPAWN, SPAWN, POST_SPAWN, SUMMER_PATTERN, FALL_TRANSITION, SHALLOW_ACTIVE, DEEPER_HOLDING, TRIBUTARY_MOVEMENT, BACKWATER_USE, UNKNOWN), `shallowLikelihood` (HIGH / MODERATE / CONDITIONAL / LOW / UNKNOWN), `typicalDepthBehavior`, `favoredHabitat[]`, `spawnState` (ACTIVE_WINDOW / OUTSIDE_WINDOW / UNKNOWN), `temperatureContext`, `hydrologyContext`, `dayNightContext`, `bowfisherMeaning`, `confidence`, `regionalConfidence`, `precision`, `claimIds[]`.
**`precision` is the honesty field.** MONTH = a month-bounded rule or a named month range; SEASONAL = a season-level statement shown across its months (draw it as a seasonal estimate); INFERRED = adjacent to a known window (lighter); UNKNOWN = unknown (draw it empty). No month is invented from a season and no temperature trigger is turned into a calendar window.
**Base pattern vs condition modifiers:** the months show the base pattern. `conditionModifiers[]` are rules that change location *within* it (rising or falling water, temperature bands, night, turbidity). Show them as modifiers, not as months. A modifier with `seasonality: UNBOUNDED` and no YEAR_ROUND review **does not fire** (see seasonal safety). `evidenceConflicts` lists rules whose sources disagree; the month shows "CONFLICTING EVIDENCE" instead of choosing.

## Coverage, gaps and research priority
`knowledgeCoverage[category]` for seasonal, spawn, temperature, depth, hydrology, vegetation, night, clarity, current, regional: `status` STRONG / MODERATE / WEAK / UNKNOWN, `completeness` (internal 0-10; absent when UNKNOWN), `evidence` (NONE / UNVERIFIED / SINGLE_SOURCE / MULTI_SOURCE / RULE_TRANSFER). **UNVERIFIED** means the research answered it but no inspected source confirms it yet: WEAK, not UNKNOWN. `knowledgeGaps` lists every category that is not STRONG with `openQuestions`, `ifWeLearnThis` (what it would change for a bowfisher), `researchPriority` (HIGH / MEDIUM / LOW / DO_NOT_RESEARCH) and `researchStatus` always `RESEARCH_NOT_AUTHORIZED`: **a gap is exposed, never researched automatically.** Priority is a deterministic product of category importance (night and depth 1.0 ... clarity 0.4), species tier (TARGET 1.0, SECONDARY 0.6, KNOWLEDGE_ONLY 0.15) and gap size; >= 0.5 HIGH, >= 0.25 MEDIUM; protected or policy-held fish are DO_NOT_RESEARCH.

## Seasonal safety (shared truth with the evaluator)
The profile and the current-outlook evaluator use the same rules. A rule fires only if its season is established: month-bounded rules and spawn windows do; an unbounded rule needs an explicit `YEAR_ROUND` review assertion; anything else (`NEEDS_REVIEW`, `NOT_ESTABLISHED`) **fails closed** (does not fire; the state says how many rules were held back). Example: the common-carp rise rule is Mar-Jul, so it cannot fire in October even if temperature and rising water match. `outlook_contradictions()` verifies an outlook against the profile.

## Current outlook is a different payload
The study guide is stable knowledge. `biological-movement-outlook-v1` (per lake, per species) is what that knowledge means right now: `state`, `movement`, `activity`, `where`, `why`, `cautions`, `confidence`, and a `trace` for the WHY? panel (`inputs`, `matchedKnowledge`, `seasonCheck`, `result`). Lake presence belongs to the Lake Brain and never appears in a profile.

## Status vocabulary
Coverage: STRONG, MODERATE, WEAK, UNKNOWN. Review: UNREVIEWED, ACCEPTED, REJECTED, NEEDS_MORE_EVIDENCE. Field validation: NOT_VALIDATED, FIELD_PLANNED, OBSERVATIONS_IN_PROGRESS, VALIDATED, FAILED (observation count, trip count, last observation shown; field state never changes the knowledge display; `fieldCandidate` marks a proposed first prediction). Rule maturity: DRAFT, RECONCILED, APPROVED. Season review: BOUNDED, YEAR_ROUND, NEEDS_REVIEW, NOT_ESTABLISHED. Confidence: HIGH, MEDIUM, LOW, UNKNOWN.

## Safety guarantees (tested)
No private paths, bucket names or research text; internal compilations expose no URL; anecdotal sources are never listed as evidence; no per-lake presence; every claim id resolves to provenance; a profile over 90 KB is refused; unknown stays unknown.

## Generated snapshot
34 profiles (29 canonical registry rows plus 5 proposed species flagged `canonical: false`). Month precision across the 29 canonical profiles: MONTH 100, SEASONAL 143, INFERRED 18, UNKNOWN 87 (of 348 canonical month cells). See `BIOLOGICAL_SPECIES_COVERAGE_MATRIX.md`.
