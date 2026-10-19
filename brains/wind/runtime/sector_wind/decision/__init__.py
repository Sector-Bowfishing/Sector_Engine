"""Wind Bowfishing Decision layer (Layer 2 of the Wind Brain V2 functional model; see brains/wind/docs/WIND_BOWFISHING_FIRST_V2.md).

Layer 1 (Wind Intelligence) is the existing forcing + physics: ingest/grib/interp/sample/store, `brain.state` (wind state,
frozen duration rule) and the frozen CEM / 9-ray fetch functions in `sector_wind.bowfishing`.
Layer 2 (this package) turns that physics into bowfishing wind decisions: which banks are exposed or sheltered for this wind,
what the surface is likely to look like, how that changes over a trip, which nearby banks are better, and how far to trust it.
Layer 3 (Learning & Validation) is `decision.scenarios` (deterministic capability scenarios) plus the evidence and scoring
entry points listed in brains/wind/contracts/wind-validation-entrypoints-v1.json.

Scope (BRAIN_OPERATING_CONTRACT §1): wind exposure and modeled surface ONLY. Nothing here says where fish are, whether water
is clear, whether a bank is legal, accessible or safe, or whether tonight is a good trip; those belong to other Brains and
Sector Intelligence. Deterministic: no AI, no network, no randomness. Every output is `validated: false` until field truth exists.
"""
from .schema import DECISION_SCHEMA, KNOWLEDGE_VERSION  # noqa: F401
