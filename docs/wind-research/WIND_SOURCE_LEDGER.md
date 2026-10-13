# Wind Brain — source ledger (campaign 2026-10-13)

Every artifact used. "Read" = read for facts; "Ran" = computation executed this campaign. Raw data stay outside git in `~/Desktop/Development/Sector_Research_Data/wind-brain/`.

| ID | Source | Location | Use | Status |
|---|---|---|---|---|
| S1 | WindBrain adapter docs | Engine `brain/wind`: `jobs/wind-hourly/BRAIN.md`, `README.md`, `SESSION_CLOSEOUT.md` | Audit | Read |
| S2 | Brain scoring | Engine `main`: `docs/brains/scoring/SCORING.md`, `frozen-scores.json`, `OWNERSHIP_MATRIX.md` | Audit/ladder | Read |
| S3 | Wind stages 1–3E docs and score log | iOS `intelligence/wind`: `docs/intelligence/wind/**` (incl. `WIND_SCORE_CHANGE_LOG.jsonl`) | Audit, history, ladder | Read |
| S4 | BWIS v1 definition + engine report | iOS `docs/intelligence/wind/bowfishing/` | Ladder, bank rank | Read |
| S5 | Provider bake-off, Open-Meteo audit, nowcast tests | iOS `stage3d1/`, `stage3d2/` | Source research | Read (not re-run) |
| S6 | NBM v5.0 historical corpus + 8 METAR stations, inits 2026-05-06→10-06 (H2 sealed, not read) | `~/Library/Caches/sector-wind/historical/v50` | V1–V5, V7 | **Ran** (`research/wind-brain/bowfishing_validation.py`, `confidence_flag.py`; cached rows `rows_v50.pkl`) |
| S7 | Frozen fetch tables (4 dev lakes in iOS asset catalog; 70 national in `national-fetch/tables`) | local caches | G2, G5, G6 | **Ran** (`compare_frozen.py`, `bank_impact.py`) |
| S8 | Lake Brain engine polygons (599) and geometry confidence flags (621) | `Sector_Research_Data/lake-brain/geometry` | G2–G4 fleet | **Ran** (`polygon_fetch.py`) |
| S9 | Engine directory (621 lakes) | `Sector_Research_Data/lake-brain/directory_lakes_2026-10-13.json` | Fleet counts | Read |
| S10 | Live Brain mirror (state, profile cache) | `~/Library/Caches/sector-wind/live-mirror` | Audit examples only; no skill computed | Read |
| S11 | App wind code | iOS `origin/Michael-Master` `WindFieldGrid.swift`, `LayerCapabilityGate.swift`; Engine `WindFactor.swift` | Customer usage, convention | Read |
| S12 | Pre-registration | `docs/wind-research/WIND_RESEARCH_PREREG.md` (commits 2bbf0431 + addenda before results) | All tests | Written first |

Not used / out of scope: H2 live holdout (sealed to 2027-01-01), paid vendors, any credentialed API, any production resource, any other Brain's data beyond read-only geometry.
