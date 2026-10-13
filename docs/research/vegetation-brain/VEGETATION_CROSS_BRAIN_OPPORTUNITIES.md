# Vegetation Brain — Cross-Brain Opportunities and Interfaces

**RESEARCH ONLY. Proposed Brain.** Each interface lists direction, payload, confidence propagation, and what each side must *not* do.

## 1. Interface table

| Brain | Vegetation consumes | Vegetation provides | Hard rule |
|---|---|---|---|
| **Lake Brain** | pool anomaly, trend, basis + confidence; polygon / geometry flags; full-pool basis | — | Never recompute level. Pool uncertainty widens vegetation confidence bands. |
| **Depth Brain** (future) | effective depth per cell, shallow/littoral zones, accessible-water mask | density and class over the 0–8 ft band | Never estimate depth. Until it exists: modelled shallow fraction flagged `MODELLED`. |
| **Water Temperature** | surface temp, GDD10 | — | Seasonal curve uses it; Vegetation does not publish temperature. |
| **Water Clarity** | Secchi/clarity class + confidence; per-cell readability; grass-mask precedent | cell-level plant-presence layer that Clarity can use *instead of* its internal grass mask (future, only if Clarity chooses) | Never invent clarity. Never edit Clarity code. |
| **Wind** | wind speed/direction history | glare/wave risk flag for satellite reading; fetch-exposed shallow zones | Wind owned by Wind. |
| **Biological** | species × season × habitat preferences ("carp use flooded & submerged grass on 1–3 ft flats") | vegetation class/density/location/age/confidence in the biological driver key `vegetationDensity` (exists today, unfed) | No fish behaviour inside Vegetation. |
| **Sector Intelligence** | — | structured evidence (`class`, `density`, `surfaceTopped`, `tier`, `age`, `confidence`, `reason`) | Intelligence composes; Vegetation does not recommend. |

## 2. The valuable combination: BIOLOGICAL × VEGETATION × DEPTH × TEMP (× LEVEL)

Biological knows *which habitat a species wants this week*; Temperature says *whether it is in its spawn/feeding window*; Depth says *where water is the right depth*; Level says *what is flooded*; Vegetation says *where cover exists and how thick*. Intelligence can intersect them:

| Example target (from `SpeciesDatabase.swift`) | Habitat string | Needed Vegetation output | Other Brains |
|---|---|---|---|
| Common carp spawn | "flooded & submerged grass and weedy 1–3 ft flats" | `FLOODED_TERRESTRIAL` candidates + `SUBMERGED`/`EMERGENT` presence in 1–3 ft cells, density not DENSE | Temp 59–77 °F window; Depth 1–3 ft; Level rising |
| Bigmouth buffalo | "freshly flooded vegetated marsh grass and backwater margins" | newly inundated grass/marsh cells | Level anomaly + trend; Temp 60–75 °F |
| Smallmouth buffalo | "submerged vegetation in slightly faster water" | submerged presence near current | Flow (Lake/Hydrology); Temp |
| Black buffalo | "current edges and flooded vegetation" | flooded vegetation edges | Flow; Level |
| Alligator gar | "overbank flooded terrestrial grass by deep backwaters" | flooded-terrestrial extent adjacent to deep water | Level; Depth; Temp 68–86 °F |
| Grass carp | (stocked; manages vegetation) | change/decline of SAV | Management/regime flag |

A ranked "where could fish be" map is a composition problem for Intelligence; Vegetation's job is to provide **explainable, confidence-tagged, dated** cover cells, plus vegetation edges (class-boundary cells), which are separately valuable as holding structure [A].

## 3. Evidence Intelligence should receive (proposed fields)
`class`, `density`, `surfaceTopped`, `edgeDistanceM`, `tier` (`OBSERVED_SATELLITE|OBSERVED_SURVEY|SEASONAL_EXPECTATION|POTENTIAL_HABITAT|PRIOR_MAPPED`), `observedAt/ageDays`, `confidence` (0–1 plus reason codes), `levelContext`, `refusal`. Intelligence should treat `POTENTIAL_HABITAT` and `SEASONAL_EXPECTATION` as weaker evidence by construction and must be able to surface "vegetation not currently visible" differently from "no vegetation".

## 4. Reciprocal data flows worth noting
- Vegetation → **Clarity**: Clarity's current grass mask (NDVI ≥ 0.30) removes plant pixels from water readings, and its documented false positives (haze at NDVI 0.12–0.19) show the failure mode both Brains share. A shared, validated plant mask would help both; coordinate, do not couple.
- Vegetation → **Water Temp**: the Clarity/thermal pipeline documents warm water beside grass mats polluting temperature fits; a plant mask helps exclude them.
- Clarity → **Vegetation**: Clarity's per-cell `reason` codes (cloud, haze, unreadable) can pre-seed Vegetation's refusal codes.
- Biological → **Vegetation**: species-season windows can tell the seasonal model which groups to weight (e.g., lotus is irrelevant in ND).
- Lake Brain geometry flags → Vegetation: lakes with suspect polygons (≈0 km² area computed for Shafer IN, Buckeye OH, Waiau HI) should be refused until fixed.

## 5. Contract hygiene
Follow the Brain platform contract (schema gate, health vocab, readiness slot). Every cross-Brain field is read-only to the consumer. A change in a producer's semantics must bump that Brain's `schemaVersion`, not be silently reinterpreted by Vegetation.
