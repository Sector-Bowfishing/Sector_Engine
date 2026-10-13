# Cross-Brain Opportunities

Documented only. No other system is modified.

## What Biological needs from others
| Brain | Needs | Why (research-driven) |
|---|---|---|
| **Lake Brain** | Species presence (already specified); **pool type** (run-of-river vs storage vs natural), tailwater/dam presence, tributary inventory and connected backwaters/oxbows, **flood-pool/inundation extent**, lock/spillway operations | Archetype D (tailwater stagers) and B (floodplain spawners) cannot be placed without them; smallmouth passes spillways only when inundated; longnose spawn below locks |
| **Depth Brain** | Shallow band classification (≤0.5, 0.5-1.5, 1.5-3 m), shore distance, **inundation depth of flooded terrain**, depth-change rate | Spawn depths are 0.3-1.2 m; non-spawn depth is bottom depth only; flooded-grass depth is the alligator-gar/bigmouth criterion |
| **Water Temp** | Daily surface temperature and **crossings** (10, 15, 18, 20 C), warming/cooling trend, tailwater/outfall warm refuges, inflow-water vs lake-water temperature difference | Spawn, run onset, "warm rise" trigger, cold lethal (tilapia), winter refuges |
| **Clarity** | Secchi/turbidity bands (<0.4, 0.4-1, >1 m); post-rain turbidity | Carp/bigmouth tolerate; spotted gar prefers clearer; detectability for the bowfisher |
| **Wind** | Wave exposure per shoreline segment; setup/seiche | Mediated effects (carp feeding, turbidity); low direct evidence (5% weight) |
| **Vegetation** | Type (submerged / emergent / **flooded terrestrial**), density, seasonal state (senescent), polygon edges | Grass carp (hydrilla), gars/bowfin/bigmouth (spawn), snakehead; edge-vs-interior is unknown biologically |
| **Hydrology** (Lake/inflow) | Tributary stage/discharge **change rate**, pool level trend (rising/falling), recession rate | Strongest cross-species signal; recession kills year classes |

## What Biological can provide to Intelligence
1. **Archetype per species** (A-E in the seasonal doc), so movement rules are not generic.
2. **Condition-feature definitions** that Intelligence can compute from other brains: `warmRise` (≥15 C and rising stage), `springWarmWindow`, `recessionAfterSpawn`, `floodedVegetationAccess`, `tailwaterStaging`, `lowFlowSummer`.
3. **Habitat-class rules with confidence and transfer tag** per species × season × condition (not coordinates).
4. **Negative rules** (important for bowfishers): do not recommend flats in winter for gars; do not apply vegetation rules to silver carp; do not build night rules for alligator gar.
5. **Species-ID gating** (buffalo group, spotted/shortnose gar) so Intelligence does not over-claim species.
6. **A confidence ladder**: each rule carries independence count, region, and transfer, so Intelligence can show uncertainty rather than a single score.

## Interface proposals (not implemented)
- `speciesRules[speciesId]` published (private bundle → summary in RTDB) with `{ruleId, season, conditions[], habitatClassBoost[], confidence, transfer, frozenAt}`. The existing summary only exposes counts today.
- `conditionFeatures` computed by the Intelligence/Orchestrator layer from water-temp and hydrology states; Biological defines the definitions only.
