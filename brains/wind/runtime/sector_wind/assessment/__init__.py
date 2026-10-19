"""Wind Exposure Assessment layer (Layer 2 of the Wind Brain V2 functional model; see brains/wind/docs/WIND_BOWFISHING_FIRST_V2.md).

Layer 1 (Wind Intelligence) is the existing forcing + physics: ingest/grib/interp/sample/store, `brain.state` (wind state,
frozen duration rule) and the frozen CEM / 9-ray fetch functions in `sector_wind.bowfishing`.
Layer 2 (this package) is the WIND-DOMAIN assessment built on that physics: which banks are exposed to or sheltered from this
wind, the wind-driven surface disturbance, how both change over a time window, which nearby banks are less exposed to the wind,
and how far to trust it. It is a specialist output for Sector Intelligence to combine with other Brains; it never recommends a
place to bowfish.
Layer 3 (Learning & Validation) is `assessment.scenarios` (deterministic capability scenarios) plus the evidence and scoring
entry points listed in brains/wind/contracts/wind-validation-entrypoints-v1.json.

Specialist boundary (BRAIN_OPERATING_CONTRACT §2-§3): wind exposure and wind-driven surface ONLY. Nothing here says where fish
are, whether water is clear, whether a bank is legal, accessible or safe, or where/whether to fish; Sector Intelligence owns the
cross-Brain synthesis and the final bowfishing recommendation. Deterministic: no AI, no network, no randomness. Every output is
`validated: false` until field truth exists.
"""
from .schema import ASSESSMENT_SCHEMA, KNOWLEDGE_VERSION  # noqa: F401
