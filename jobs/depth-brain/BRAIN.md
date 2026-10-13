# Depth Brain (SHADOW foundation) - `jobs/depth-brain`

**Status: shadow / internal. Not deployed, not scheduled, not registered with the orchestrator, no Cloud Run job, no customer consumer. Depth has no official score.**
Branch `feat/depth-brain-foundation` (base `feat/cost-efficient-scheduling` @ `48168baa`). Research: branch `docs/depth-brain-research`.

First capability: **effective-depth shift** = current Lake Brain level - datum-compatible reference pool. Real contour zones are supported where the evidence exists but effective zones stay withheld until a survey's reference pool is verified. Modeled bathymetry (GLOBathy) is forbidden.

```
depth_brain/contract.py    constants, sign convention, tiers, thresholds, assumed sigmas
depth_brain/datum.py       vertical-datum compatibility (SAME_SOURCE / SAME_DATUM / CONVERTED / INCOMPATIBLE / UNKNOWN)
depth_brain/shift.py       compute_shift(): the shift engine, refusals, uncertainty
depth_brain/zones.py       contour-interval-aware shares and shifted bounds
depth_brain/evidence.py    tiers, precedence, GLOBathy restriction (assert_allowed_use)
depth_brain/state.py       DepthState builder, fingerprint, plan()
depth_brain/candidates.py  OFFLINE candidate-manifest builder (Phase 6)
depth_brain/publish.py     shadow publisher (dry-run store or live with explicit flag)
depth_brain/data/          candidates.json, datum_providers.json, source_licences.csv
tests/                     datum, shift, zones/evidence, state/publish, golden contract fixtures
```

```
python -m pytest -q                                                  # offline; 80+ tests
python -m depth_brain publish --lake-states rtdb:https://sector-brain.firebaseio.com --dry-run /tmp/depth_dry.json   # GET-only reads
```
A live write needs `--rtdb URL --yes-write-shadow`; it would create `/brains/depth` and `/lakes/{k}/states/depth`, which Ops renders. That is a Michael decision, not part of this phase.

Docs: `docs/brains/depth/` (state contract, evidence policy, datum audit, candidate fleet, contracts for Intelligence / Temp / Clarity / Vegetation / Biological, licensing, field validation, source requests, production readiness).
