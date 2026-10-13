# Vegetation Brain (SHADOW foundation) - `jobs/vegetation-brain`

**Status: shadow / internal. Not deployed, not scheduled, not registered with the orchestrator, no Cloud Run job, no customer consumer, no live writer. Vegetation has no official score and begins `NOT_VALIDATED`.**
Branch `feat/vegetation-brain-foundation` (base `feat/cost-efficient-scheduling` @ `48168baa`). Research: branch `docs/vegetation-brain-research`.

**V1 scope: SURFACE-REACHING aquatic vegetation** (floating-leaf beds, mats, emergent belts, surface-topped canopy). **Submerged vegetation is not observable with Sentinel-2 at fleet scale and is never reported as observed.** `potentialHabitat` is a separate product that always carries `potentialOnly: true`.

```
vegetation_brain/contract.py     constants, closed vocabularies, refusal reasons, production-rule constants, product language
vegetation_brain/observer.py     pure numpy: pixels -> 50 m cells -> pass acceptance -> median persistence -> lake observation; no max composite
vegetation_brain/state.py        VegetationState builder, potential habitat (Canfield ceiling, no modeled depth), confidence (capped by validation)
vegetation_brain/language.py     the only place evidence becomes words; forbidden phrases
vegetation_brain/validation.py   the frozen pre-registered gates as code (pinned to the document by a test)
vegetation_brain/fleet.py        observability tiers from the CANONICAL Lake Registry (no private polygon library)
vegetation_brain/maturity.py     research maturity (official=false); refuses unsupported increases
vegetation_brain/ops_summary.py  registry fields computed for Ops (nothing hardcoded)
vegetation_brain/publish.py      DRY-RUN publisher (no live writer exists)
```

```
python -m pytest -q                                                    # offline; needs numpy
python -m vegetation_brain fleet --registry lakes.v1.json --version V --out vegetation_brain/data/fleet.json
python -m vegetation_brain report
python -m vegetation_brain publish --dry-run /tmp/vegetation_dry.json
```
Docs: `docs/brains/vegetation/` (state contract, cross-brain contracts, Intelligence contract, validation pre-registration, score v1 proposal, production readiness, Ops visibility gap, fleet observability, maturity re-evaluation, external request drafts).
