# Wind fleet cost + scale model (measured where possible; list prices flagged as assumptions)

Principle: **one weather download per cycle, many lake samples**, no per-lake jobs, no per-lake GRIB reads, no extra provider calls. Measured on 2026-10-13 from public NOAA `.idx` byte ranges (cycle 2026-09-01 12Z), the live archive object sizes, the Cloud Run job description and the fleet-sampler runs.

## Today (4 live lakes)
| Item | Measured |
|---|---|
| Job | Cloud Run Job `wind-hourly`: 1 task, **1 vCPU, 2 GiB**, 900 s timeout, hourly at :05; median run **202 s**, max 446 s (165 executions, 0 failed) |
| NBM download per cycle | **150 MB** (32 leads × WIND/WDIR/GUST 10 m, ≈ 4.7 MB per lead); +**231 MB** qmd percentiles on the four synoptic cycles (00/06/12/18Z) ⇒ **≈ 4.5 GB/day (≈ 135 GB/month)** read from the public NOAA bucket |
| RTMA-RU | 15-minute analyses, small ranges |
| Storage (live archive since 2026-10-07) | NBM 24 MB, RTMA 9 MB, runs/ledger/grids/latest/brain < 2 MB ⇒ **≈ 35 MB in 6.6 days (≈ 160 MB/month)** for 4 lakes |
| Object writes | ≈ 4 lakes × 24 NBM cycles + 4 × 96 RTMA quarter-hours ≈ 480 per day |

## Fleet (621 lakes) with per-lake cut-outs (what NOT to do)
Objects ≈ 621 × (24 NBM + 96 RTMA) ≈ **74,500/day**; storage ≈ 155 × today ≈ **25 GB/month**; per-lake slicing cost grows linearly. Rejected.

## Fleet with point sampling (the design)
| Item | Estimate |
|---|---|
| Extra GRIB downloads / extra provider calls | **0 / 0** for CONUS (the same fields are decoded once) |
| Extra domains | AK (3 km grid): **+75 MB/cycle** (+50%); HI: **+11 MB/cycle** (+7%); i.e. ≈ +86 MB per cycle if AK/HI are ingested (tested to decode and sample correctly; not wired) |
| Fleet interpolation | point index once per grid: **4.3 s**, 83 KB json; one lead for 600 lakes **8.5 ms**; **36 leads 0.23 s**; AK/HI similar |
| Objects/day | **24 NBM fleet objects** (+ RTMA fleet objects if "now" is sampled for the fleet) vs ≈ 74,500 |
| Fleet object | ≈ 0.51 MB JSON per cycle for 600 lakes × 36 leads × 4 variables (≈ 12 MB/day raw, a few MB/day gzipped ⇒ **< 0.2 GB/month** gz) |
| Memory | one CONUS field ≈ 30 MB as float64 (3.7 M cells); the current 2 GiB is ample; index +83 KB |
| Runtime | dominated by GRIB download/decode (~200 s today); fleet sampling adds < 1 s; AK/HI adds ≈ +50% download if wired (≈ +100 s) ⇒ still inside 900 s |
| CPU/memory $ (list-price assumption — verify) | 24 runs × ~200–300 s × 1 vCPU / 2 GiB ≈ 5–7k vCPU-s and 10–14k GiB-s per day ⇒ on the order of **a few dollars a month** at published Cloud Run rates; unchanged by sampling |

## Shadow logging growth (dual-wind log, prepared not wired)
- Record ≈ **0.86 KB**; fleet-hourly = 14,904 rows/day ≈ 12.9 MB raw; measured gzip ratio on a varied synthetic batch 0.032 ⇒ **≈ 0.4 MB/day, ≈ 12 MB/month** (24 objects/day).
- Provider calls: the designed path adds **≈ 240/day** (pilot-lake lookups only; the customer value is logged where the Engine already has it). **Logging the customer provider for every lake every hour would add 14,904 calls/day to Open-Meteo and is not proposed.**

## Cost drivers to watch
1. AK/HI domains (+50% download, +100 s) — only if/when a regional skill check passes.
2. Catch-up re-reads: the early-exit in `live.py` (on `feat/cost-efficient-scheduling`) stops completed cycles being re-read; keep it.
3. qmd percentiles (231 MB per synoptic cycle) are 20% of the daily download but carry the breezy-risk flag; they are needed only for the lakes served.
4. Bank-detail storage: audited banks ≈ 100–7,500 per lake; per-bank rows are written to storage, not RTDB; fleet-wide publication of ~530 lakes × per-bank rows hourly would be large — publish per-bank detail only on change of wind direction class/geometry hash, not hourly (design item, not built).
