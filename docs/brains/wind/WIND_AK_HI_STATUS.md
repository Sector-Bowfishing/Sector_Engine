# Alaska and Hawaii — explicit status (21 lakes: AK 12, HI 9)

Status words: SUPPORTED · PARTIAL · UNTESTED · BLOCKED. Evidence: `jobs/wind-hourly/research/fleet_domain_check.py` (data `data/fleet_domain_check.json`), one archived pre-H2 cycle (2026-09-01 12Z +6 h); geometry manifest; Lake Brain flags. No customer-visible promotion without the evidence marked missing.

| Aspect | AK | HI | Status | Evidence / gap |
|---|---|---|---|---|
| NBM regional product exists | yes | yes | **SUPPORTED** | `blend.*.core.f006.ak/hi.grib2` and qmd percentiles are published; PR and Guam products also exist (no directory lakes in PR/VI) |
| 10 m WIND/WDIR in the product | yes | yes | **SUPPORTED** | listed with the CONUS levels (10, 30, 80 m, surface–610 m) |
| Decode + self-check | ratio 0.8–1.2 (limit 3) | 1.0–1.2 | **SUPPORTED** | polar-stereographic 2.98 km grid (AK), mercator 2.5 km (HI) decode; the row-scramble self-check passes at every lake |
| Fleet sampling | 12 of 12 lakes covered | 9 of 9 | **SUPPORTED** (one cycle) | fleet sampler vs per-lake cut-out: max 0.005 m/s, 0.5° on both grids; 0 nearest-cell fallbacks |
| Hourly ingest wiring | not wired | not wired | **UNTESTED** | `ingest_nbm_cycle` cuts the CONUS file only; the sanity check uses a CONUS bbox; AK/HI would need per-domain ingest (separate GRIB fetches: +2 domains per cycle) |
| Forecast skill (direction, speed, tonight) | none | none | **UNTESTED** | validation stations are in the Southeast only; AK/HI regimes (maritime/glacial/trade-wind) differ; no METAR corpus pulled |
| Percentile (P90) risk flag | not tested | not tested | **UNTESTED** | flag calibrated on CAL+H1 southeastern land stations |
| Time zone / tonight window | America/Anchorage, Pacific/Honolulu | | **SUPPORTED** (code) | in `tonight.STATE_TZ`; Alaska summer evenings are light — "tonight" 19:00–01:00 may not be dark |
| Polygon geometry | 11 of 12 (Iliamna held as large water) | 3 of 9 (6 have no NHD feature) | **PARTIAL** | Lake Registry v1 (2026-10-13) |
| Fetch / bank exposure | 10 lakes carry a tier | 3 lakes carry a tier | **BLOCKED** | manifest blocker `nbmAKDomainNotTested` / `nbmHIDomainNotTested` withholds all bank labels (13 lakes that would otherwise carry a tier are affected, including audited Aleknagik, Lake Clark and Waimaluhia; Lake Registry v1 holds geometry for 11 of the 12 AK and only 3 of the 9 HI lakes — recomputed 2026-10-13) |
| Customer promotion | — | — | **BLOCKED** | needs a station-based skill check per region and the ingest wiring above |

## To lift the block (all independent of the Southeast evidence)
1. Pull METAR for AK and HI airports near the lakes (public IEM) and run the pre-registered direction/category checks for those regions only on **pre-H2** NBM cycles (a regional corpus exists for any date NOAA retains); pre-register first.
2. Add per-domain ingest (or fleet-sampler domains) to the job, behind the prerequisite branch.
3. Re-run the geometry manifest; remove the blocker per domain only when 1–2 pass.
Until then AK/HI lakes publish **no** wind claims to customers (they are not in the Brain's live set anyway).
