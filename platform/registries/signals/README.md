# platform/registries/signals/

**Owner:** Platform
**Purpose:** SHARED SIGNAL REGISTRY: platform-owned **definitions** of shared environmental signals (barometric pressure, pressure trend, precipitation, air temperature, humidity, cloud cover, moon phase, …). Schema: `contracts/schemas/registry-signals.schema.json`. Loaded by `sector_brain_platform.signals`.

**Belongs here:** what a signal *is* (id, name, description, unit), whether a producer publishes it (`status`, `producer`), how it goes stale.

**Does NOT belong here:** which Brain consumes a signal (that is the consuming Brain's own declaration in its `brain.json`, `consumes[].kind = signal`); any domain interpretation ("pressure falling means fish bite"); science thresholds; Brain logic.

**Import / dependency rules:** read by the platform (dependency discovery, dependency/freshness health, architecture gate 17). Ops/Canvas never hardcodes a signal→Brain table; it discovers edges from the Engine (`control/healthV1/dependencies`).

**Status:** every entry is `DECLARED` (no producer). A declared consumption of a DECLARED signal evaluates `UNAVAILABLE`, never FRESH and never zero. Registering a producer is a reviewed change here (`status: AVAILABLE`, `producer`), not a code change. Introduced by Orchestrator G1/G2 (`docs/brains/platform/ORCHESTRATOR_HEALTH_V1.md`).
