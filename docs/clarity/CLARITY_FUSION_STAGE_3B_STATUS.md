# Clarity Fusion Stage 3B: interim status (not the final hand-off)

2026-09-28, mid-run, in `Sector_Engine-fusion`. **No hypothesis, challenger or gate result has been computed or looked at yet.** The historical data is still being assembled. `CLARITY_FUSION_STAGE_3B_HANDOFF.md` follows when validation is done. Production is unchanged.

## 1. Preregistration: frozen

- **Document:** `docs/clarity/CLARITY_STAGE_3B_PREREGISTRATION.md`. It was written, and every artefact hashed, at **2026-09-28T16:01:57Z**, before any pre-2025 file was requested. Hashes are in `CLARITY_STAGE_3B_PREREGISTRATION.sha256`; the document's own hash is `7f4eeb18…28de`.
- **Frozen with it:**
  - the evaluation code (`scripts/hydrology/stage3b_eval.py`, `89476718…52f4`);
  - the discovery-only constants (`docs/data/hydrology/guntersville/stage3b/constants.json`: noise bands and challenger adjustments);
  - Stage 3A's zones;
  - the production Sentinel pipeline;
  - the rain, NWM and pass-candidate scripts.
- **Hypotheses:**
  - H1: cold-season storm response, per class (large, medium, small, main stem).
  - H2: NWM ≥ 3× its own baseline.
  - H3 (secondary): head → mouth, same pass and arm only.
- **Challengers:** persistence, dry-baseline reversion, season-only and relative-flow. Combined only where both are supported.
- **Gate:** G1–G8 per class × challenger, with no lake-wide pass/fail.

## 2. Historical data so far

| Input | Status |
|---|---|
| Sentinel-2 candidates (C1 L2A, a tile at or under 40% cloud), 2020-10-15 → 2024-12-31 | **276**: 2020 19, 2021 72, **2022 6**, 2023 91, 2024 88 |
| Passes read (production gates, per-cell) | **212 of 276 done**. So far 2021: 64 read, 8 rejected; 2023: 51 read, 4 rejected (about 36 still to read); 2024: 73 read, 15 rejected (2 of them network timeouts, to be retried); 2020: 18 read, 1 rejected; 2022: 6 read |
| Daily MRMS Pass 2 (24 h, 17Z), 2020-10-07 → 2024-12-31 | done, 1,547 days |
| Hourly MRMS 01H for the day before each pass | done, 6,325 hours, 22 missing |
| NWM analysis at 16Z, with the model version | done, 1,547 days (2 empty). Versions: v2.0 → 2021-04-19, v2.1 → 2022-06-27 (a one-day v2.2 on 2022-06-01), v2.2 → 2023-09-18, v3.0 after |
| USGS 03572900 and 03572690, 2020-10 → 2025-01 | done, complete (South Sauty has gaps in 2023) |
| Wind (IEM ASOS: Scottsboro, Gadsden, Huntsville) | being collected in small chunks (the server rate-limits); preserved only, not used |

**2022 is not a usable year.** Earth Search's C1 collection has almost nothing for 2022: none in Jan–Feb or May–Oct. The older `sentinel-2-l2a` collection has 2022, but it is a different processing baseline, and the preregistration freezes C1. Under its completeness rule (§2.5: ≥ 40 read passes), 2022 is reported separately with 2020. That leaves **three validation years: 2021, 2023, 2024**, and the gate's "≥ 3 qualifying years" means all three must qualify.

**Rejections are the production SWIR check.** SWIR DN over water reads 1,500–2,900, where 1,000–1,100 is expected, which marks a hazy or glinting pass. Nothing is loosened. Two 2024 passes failed on network timeouts and will be retried.

**Operational note (not an analysis change).** The first readers stalled indefinitely on stalled S3 connections, because GDAL sets no low-speed timeout by default. They were restarted with GDAL HTTP timeouts and retries (`GDAL_HTTP_TIMEOUT=60`, `GDAL_HTTP_LOW_SPEED_TIME=30`, `GDAL_HTTP_MAX_RETRY=6`). No gate or rule changed.

## 3. Item 12 feasibility (separate from the gate; discovery passes only)

`scripts/hydrology/head_gate_diagnostic.py` compares the five-zone arms' head zones on 5 clear 2025–2026 passes (3 cold, 2 warm) under two rules:
- **production**;
- **one relaxed variant:** bank standoff 0 m, structure standoff 30 m, frame-cell minimum 10%, with the cloud, haze and reflectance limits unchanged.

| Arm (head zone) | What removes the water | Readable cells, production → relaxed | Relaxed-only cells vs production-read water (log10) |
|---|---|---|---|
| Town Creek (Marshall) | In winter the **100 m structure standoff** (Jan 13 and Feb 2: 54% of pixels survive the bank rule, 8–9% the structure rule), then cloud/haze | 24 → 283, 30 → 339 (winter); 270–442 → 404–630 | −0.04 to +0.11 |
| South Sauty | cloud/haze and structure | 1,568–2,055 → +96…+238 | −0.05 to **+0.30** |
| Browns | little; already largely readable | +69…+83 | −0.14 to +0.13 |
| Coon | structure, then reflectance | 37–141 → 77–196 | −0.01 to **+0.30** |
| Town Creek (Jackson) | bank and structure | 48–137 → 94–204 | −0.15 to **+0.70** |
| Crow | **Sen2Cor does not call it water** (5–31% of pixels) | 0–3 → 6–105 | too few to compare |
| Mud | the reflectance (FAI/NDVI) limits: grass | 0–293 → 21–438 | −0.12 to 0.00 |

- **The structure rule and winter.** The production structure rule probably treats bare winter fields and leafless riparian land as "bright non-vegetated" and excludes 100 m of water beside them. That removes narrow creek water in exactly the season H1 tests.
- **Loosening it is not safe as a blanket change.** Loosening recovers a lot of water, but the shore's adjacency bias is inconsistent (−0.26 to +0.70 log10 across arms and passes). That is comparable to the effects being tested. A per-pixel rule would have to be validated against in-situ turbidity first.

**Widths** (`head_widths.py`, mid-channel):
- the large arms' heads are 130–1,000 m wide (Town Creek Marshall 178 m, Crow 132 m);
- that leaves 11–104 Sentinel-2 pixels across after one bank pixel each side, and 42–350 at 3 m;
- so width alone does not make them unreadable. The shore rules and the classification do.

**Other sources, not yet assessed in depth:**
- PlanetScope (3 m, near-daily, commercial) is the only realistic route to much more narrow water.
- Landsat (30 m) is worse than Sentinel-2.
- User-reported visibility in the unreadable heads is the natural ground truth for any relaxed rule.

## 4. What remains

1. Finish the pass reads (about 64 left, mostly 2023), then re-read the network failures.
2. Run `zone_history.py` on the historical passes.
3. Run `stage3b_eval.py evaluate`, unchanged, with validation years 2021, 2023, 2024 and 2020 and 2022 separate.
4. Secondary: the Stage 2 state replayed on the untouched years, head coverage, and measured flow.
5. Write `CLARITY_FUSION_STAGE_3B_HANDOFF.md`, ending in `PROCEED TO SPATIAL RUNOFF MODEL` or `DO NOT PROCEED`, with no production implementation.
