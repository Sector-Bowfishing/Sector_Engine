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

Species with no ratified policy keep their current behaviour: bowfin,
tilapia, drum, gizzard shad and mullet.

## Tests

`ConservationGateTests` adds 14 tests. `test09_legality` and the flood-lift
test were rewritten. `swift test`: 94/94 pass.

## Not touched

USGS WaterServices migration (`fix/usgs-ogc-migration`) — no file overlap.
