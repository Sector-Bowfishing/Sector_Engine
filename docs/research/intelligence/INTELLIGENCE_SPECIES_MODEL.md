# Species model: fish first

**Principle:** different fish want different water. A single "good bowfishing" number is a statement that every target reacts the same way. The audit shows today's customer score does exactly that outside the spawn headline.

## 1. What exists
| Source | Species coverage | Notes |
|---|---|---|
| Engine `SpeciesDatabase` | 18 rows; spawn min/peak/max °F, windows by region, habitat copy, tier, legality | Drives only the spawn headline/regime. Includes non-targets in the headline competition (probe E7: gizzard shad, black buffalo, longnose gar) |
| Biological Brain (species-v2) | 29 rows; 27 assessed; knowledge median ≈ 1.0 / 10; 0 REVIEWED or VALIDATED | Knowledge, not per-lake state. Machine-readable per-species rules exist for common carp only (48 rules); Intelligence currently consumes the median only |
| Lake Brain | species presence per lake for the 5 pilot lakes | Native/introduced, presence confidence |
| On-device FishIntel | 5 species on one lake | Local tables that disagree with Engine and Biological |
| Policy | Engine `SpeciesLegality`; Phase-5A gate unmerged | Species legality must be a gate, not a score |

## 2. The species-first contract (what Intelligence needs, minimal)

For each species, Biological should publish **response bands**, not scores:

```
speciesId, season/state context (e.g. pre-spawn, spawn, post-spawn, summer, fall, winter-dormant)
for each deciding factor:   FAVORABLE / WORKABLE / LIMITING / BLOCKING bands over the factor's native unit
                            + evidence tier (RESEARCH | REVIEWED | VALIDATED) + sources
deciding factors (ordered): which of {waterTemp, depth, vegetation, wind exposure, clarity, lake level trend, ...} decide where this species is
night-shallow behaviour:    does it use shallow flats at night in this season (yes/no/unknown)
regional transfer:          region tags where the bands were derived
```

Intelligence applies bands; Biological owns what they say. Where Biological has not published a band, the species is `NOT_ASSESSED` for that factor, which makes the factor UNKNOWN (rule R1), which caps the rating.

## 3. Algorithm (prototype `species_first`)
1. Species set = Lake Brain presence ∩ species with a response profile. Everything else is reported `NOT_ASSESSED`.
2. For each species, rate and rank zones independently. No cross-species blending.
3. Output per lake and night: the best (species, zone) pairs, e.g. "common carp: NW flat; longnose gar: main-lake point edge". The headline species is the one with the highest *rated* zone and then confidence, not the highest temperature fit.
4. Safety/legal gates apply to every species; legality removes a species from recommendations entirely.

## 4. Demonstrated difference (stub profiles, synthetic zones)
A shallow-vegetation feeder stub and an open-water-edge stub rank the same three zones in different orders (`test_species_differ`): the first puts the protected grass flat first, the second does not. The point is structural: the model can express "different fish, different place", and a single score cannot.

## 5. Species-model blockers (Biological-owned unless noted)
1. Per-species response bands for the principal bowfishing targets are not machine-readable (only common carp has rules).
2. Southeast reservoir transfer and night-shallow behaviour are unresolved in the knowledge base.
3. Three conflicting spawn tables must be reconciled by Biological before Intelligence consumes any of them (OWNERSHIP_MATRIX exception 3).
4. Target relevance: which species count as targets, by state regulation, is a policy decision (D5), not an Intelligence decision.
5. No validation exists that a given species is where the band says (see `VALIDATION_STRATEGY`: species-specific sightings are a first-class observation field).

## 6. What Intelligence must not do
Invent bands "for now", infer species from the Conditions Score, or average species into a lake score. If a species has no band it gets no answer. A visible "NOT_ASSESSED: smallmouth buffalo" is more useful to the product (and to Biological's research queue) than a guess.
