# Navigation refresh: Generation Brain (2026-11-22)

Standards: Rehtac Cortex 3.1.6 @ a785035, pack sector/engine. Architecture differences between Cortex and the Engine after this change (proposals only; Cortex not modified).

| Item | Cortex says | Engine after this change | Evidence |
|---|---|---|---|
| Brain inventory | nine target Brains (BA-01); eight deployed packages | nine deployed packages: `brains/generation` (brainId `generation`) added, registered DISABLED (control manifest PARKED, executionTarget none) | `tools/architecture/stable_brain_ids.json`, `control_manifest.json`, `keys.BRAINS`, `BrainPlatform.swift` |
| Dam releases | owned by Lake Brain (BA-05, LC-07) | Generation owns release / generation state; Lake keeps its existing release readout unchanged | CG-3.1-19 |
| Data families | no `generation` slot | per-lake slot and snapshot field `generation`; Publisher registration `generation-publication-v1` (no writer active) | `publisher/registry.py` `generation_specs` |
| Providers | — | five Generation-owned provider entries (TVA schedule, CWMS release, SWPA schedule, RISE release, USGS discharge) | `providers/PROVIDERS.json` |
| Cutover order | — | `generation` BLOCKED (no approved release) | `cutover_order.json` |
