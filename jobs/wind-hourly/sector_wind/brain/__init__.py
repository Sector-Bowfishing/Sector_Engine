"""WindBrain — Sector Brain Platform adapter for the Wind Candidate (wind-only; research/shadow data).

Writes the wind slot of the dedicated Brain RTDB (`sector-brain`): registry, lake fleet readiness, per-lake profile and
state, snapshot field, validation summary, sources, health and activity. Contract: Sector Ops
docs/BRAIN_INTEGRATION_REQUIREMENTS.md §5 + docs/SECTOR_BRAIN_RTDB_SCHEMA.md. See jobs/wind-hourly/BRAIN.md."""
