# Wind — DECISION_QUEUE (items only Michael can resolve; work continues on everything else)
Updated 2026-10-14.

| # | Decision | Recommendation | Evidence | Blocks | Status |
|---|---|---|---|---|---|
| D1 | Ratify Wind Rubric v2 (split provider accuracy from strong-event gates in dims 1 and 3; forecast-keyed night direction slice) | Approve primary: speed 8/4, gust 2.5/2.5, direction slice C. Raw 3.29 -> 4.42 (displayed 4.4). 6/6 speed split gives 4.22 | `WIND_RUBRIC_V2_RATIFICATION_PACKET.md`, `data/rubric_v2_simulation.json` | Nothing else; v1 stays canonical until approved | OPEN |
| D2 | Field program go-ahead and tester names (Guntersville ~20 pairs, Hartwell 16-20, >=8 mandatory) | Approve; first sessions on afternoons with >=3 h at >=8 mph | `WIND_FIELD_PROGRAM_PLAN.md`, `WIND_BANK_PAIR_FIELD_PACK.md` | Exposure + surface (40 pts) | OPEN (FIELD) |
| D3 | Wind deployment (carries registry `canonicalRef` fix + fingerprint skip, both prepared and tested, not deployed) | Deploy only with the Ops change that prefers the canonical score (so the Wind Brain page never goes blank) | commit on `feat/wind-brain-adoption` | Registry 3.1 duplicate disappears only after deploy | OPEN (PREREQUISITE BRANCH) |
| D4 | Critical-dimension list for the production gate | See `WIND_CRITICAL_DIMENSIONS_PROPOSAL.md` | proposal | Production readiness | OPEN |
| D5 | Dual-wind logging wiring | Wire once D3's prerequisite resolves | `WIND_DUAL_LOGGING_PREP.md` | Provider decision evidence | WAITING |
Time-gated (not decisions): reliability 30 valid days (projected 2026-11-08); H2 sealed until 2027-01-01.
