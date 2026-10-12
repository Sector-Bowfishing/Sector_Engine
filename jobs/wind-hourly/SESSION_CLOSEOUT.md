# wind-hourly / WindBrain — session closeout (2026-10-12)

Pointer for future Sector Engine sessions. This repo is public, so detail stays in the private iOS repo
(`docs/intelligence/wind/WIND_SESSION_CLOSEOUT.md`).

- **Branch `brain/wind`** = `intelligence/wind` (archive job, read service, research scripts) + the WindBrain adapter (`sector_wind/brain`, see `BRAIN.md`). Not merged into `main`.
- **Deployed:** Cloud Run Job `wind-hourly` (generation 3) runs from this branch hourly at :05. It archives NBM/RTMA-RU/METAR and publishes WindBrain to the Brain RTDB `sector-brain`.
  - Rollback: remove the `SECTOR_WIND_BRAIN_RTDB_URL` env var. A redeploy must keep it and `SECTOR_WIND_GCS_APPROVED=yes`.
- **Production wind is unchanged:** Swift `WeatherService`, Open-Meteo Best Match. The Candidate is research/shadow; WindBrain lists it as SHADOW and never promotes it.
- **Holdout:** H2 (NBM inits 2026-10-07 → 12-31) is sealed until 2027-01-01. Do not compute or publish live forecast skill before then.
- **Tests:** `pytest` in `jobs/wind-hourly` (55 pass; network tests deselected).
- **Research scripts** in `research/` read local caches (`~/Library/Caches/sector-wind`) that are not in git. Their inputs are public NOAA/IEM/NDBC data.
