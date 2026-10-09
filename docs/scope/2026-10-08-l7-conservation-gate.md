# L7 Conservation Gate — Conditions Score spawn naming (Phase 5A)

**Status:** built on `feat/intel-guardrails-5a`. Not deployed; deploying
requires Michael's OK.

## What changed

- `Engine/Config/ConservationGate.swift` holds the gate and the ratified
  per-species policy. It mirrors iOS `Sector/FishIntel/Policy/`.
- `SpawnSpecies.id` is a stable id derived from the name
  (`"Alligator gar"` → `alligator_gar`).
- `ConditionsInput.jurisdictions` holds state codes from
  `LakeDirectory.nearest(…, withinMiles: 25)`, set in `ConditionsInputBuilder`.
  Outlook nights copy the base input, so they carry the same jurisdictions.
- `SpawnFactor.isInSeason` and `SpawnFactor.score` skip any species the gate
  withholds from `.spawnTiming`. Because the species never becomes the
  leader, it cannot name a spawn, set the spawn regime, add the spawn boost,
  appear in reasons, cards or nights, or fire Lake Alerts.

## Effect

The following are never named:

- alligator gar (refuse; globally, with no exception path);
- black buffalo (refuse);
- bigmouth buffalo (suppress);
- smallmouth buffalo (spawn timing not public).

Shortnose gar has a policy but no engine spawn row. Grass carp is not named in
FL, SC or TX. Spotted gar is not named in KS, OH, PA, IL, MI, NM or ON.
Longnose gar is not named in NM, SD or NJ. Common carp and the Asian carps are
unchanged.

Species with no ratified policy **fail closed**: they are suppressed with the
reason `policyNotAssessed` and stay internally known (their biology still
runs), but they are never publicly named or targeted. This covers bowfin,
tilapia, freshwater drum, gizzard shad and striped mullet, plus channel
catfish, paddlefish and American shad, which were already excluded by the
legality and sight-shoot checks. This was the Phase 5A closeout decision on
2026-10-09.

Side effect: on a night when only unassessed species are in their spawn
window, the spawn factor is now out of season. It drops from the blend and
the remaining weights are renormalised, instead of an unnamed spawn lifting
the score.

## Tests

`ConservationGateTests` adds 16 tests. `test09_legality` and the flood-lift
test were rewritten. `swift test`: 96/96 pass.

## Not touched

USGS WaterServices migration (`fix/usgs-ogc-migration`) — no file overlap.
