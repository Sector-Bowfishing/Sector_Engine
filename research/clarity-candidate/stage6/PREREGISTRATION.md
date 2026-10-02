# Turbid-event retrieval test: rules fixed before the results

Written 2026-09-28, while the extraction was still running and before any event or ratio had been looked at.

**Question.** On Oct 15, 2025, the satellite read arm water 3–4× clearer than the probes did. Does that happen on *other*, independent turbid events at Guntersville?

## Corpus

- **Station-days:** Guntersville agency station-days (ADEM, TDEC, AWW) from 2015-06-23 onward. Each has a Secchi and/or a surface turbidity (≤ 1 m) and lies on the indexed water (snapped ≤ 90 m). 546 station-days at 25 stations.
- **Passes:** every Sentinel-2 L2A C1 pass within ±1 day.
- **Station reading:** the median production-gated turbidity over the 60 m disk round the station. The gates are the production code (`dws._s2_native_fields`), unchanged.
- **Direct read:** at least 5 valid 10 m pixels in the disk.
- **Which pass counts:** per station-day, the closest pass in time. Among passes equally close, the one with the most valid pixels. Where two tiles cover the same pass, the tile with more valid pixels.

## Definitions

- **Turbid station-day:** surface turbidity ≥ 8 NTU, *or* Secchi ≤ 3.0 ft.
- **Clear station-day (the contrast):** turbidity < 5 NTU and, where measured, Secchi ≥ 4 ft.
- **Event:** turbid station-days with a direct read whose dates are within 5 days of each other form one episode.
  - Episodes more than 5 days apart are independent.
  - Each episode is reported with its year, season (cold = Nov–Mar), stations and scenes.
- **Retrieval failure at a turbid station-day:**
  - where turbidity was measured: satellite FNU / probe NTU < 0.5;
  - where only Secchi was measured: the visibility implied by the satellite FNU (`secchi-power-v1`) ≥ 1.5 × Secchi. The in-situ conversion is unbiased on Guntersville's 2–3 ft water (+0.06 ft), so this isolates retrieval.
- **"The failure repeats"** if two conditions both hold:
  - at least 2 independent episodes other than Oct 2025 show it on the majority of their turbid station-days;
  - those episodes fall in more than one year.
- **"It does not repeat"** if every other episode with ≥ 3 turbid direct reads has the failure on a minority of them.
- **Otherwise:** inconclusive, with the reason stated.

## Diagnostics (descriptive; no thresholds tuned on them)

- **Turbidity-dependent or scene-level?** Compare the satellite/probe ratio on clear and turbid station-days, overall and within the same passes. A turbidity-dependent failure shows up only on turbid water; a scene-level atmospheric-correction offset shows up on clear stations in the same pass too.
- **Gates:** among the SCL-water pixels, how many each gate drops, and the ungated SCL-water turbidity against the gated one. Did the gates remove the turbid pixels?
- **Scene classification:** SCL class of the station pixels. Is turbid water classed as land or unclassified?
- **Atmosphere:** Sen2Cor aerosol (AOT) at the station, against the same station on other passes. Also sun elevation, tile and processing baseline.
- **Production path:** for the event passes, the production map cell (Stage 4 replay where it exists) against the direct read. Do the lake-level filters, fill and tile offsets make it worse?

## Not changed

Production retrieval, gates, conversion, map, services and jobs all stay as they are. This is analysis only.

---

## Addendum: a post-hoc hypothesis, recorded before its held-out test

Written 2026-09-28 after the C1 match-ups had been analysed. The older-collection extraction had not finished and had not been analysed. Landsat had not yet been joined to chlorophyll.

**Found in the C1 match-ups (post hoc):**
- The failures sit at arm stations with high chlorophyll-a. On Oct 15, 2025 it was 19–70 µg/L, with modest suspended solids.
- High-turbidity readings that came out right were mineral (sediment) water: chlorophyll ≈ 0–3 µg/L.
- Spearman(chl, log10 satellite/probe) = −0.54, n 51.
- **Mechanism:** chlorophyll absorbs at 665 nm. Algal turbidity darkens the red band instead of brightening it, so the red-band model (Dogliotti) under-reads it. Secchi is short either way.

**H1.** The satellite/probe ratio falls as chlorophyll-a rises.

**Held-out test on data not yet seen with chlorophyll:**
- (a) the older-collection Sentinel-2 match-ups (station-days with no C1 direct read);
- (b) the Landsat 8/9 match-ups (different sensor and atmospheric correction).

**Predictions:**
- In each set with n ≥ 8: Spearman(chl, log ratio) < 0.
- Pooled across (a) and (b), with each station-day counted once: p < 0.05.
- Turbid station-days with chl ≥ 20 µg/L have a median ratio < 0.5. Turbid station-days with chl < 10 µg/L have a median ratio ≥ 0.7.

**If the predictions fail:** H1 is not supported as a general explanation, and the result is reported as such.

**Correction to the addendum.** The partial older-collection run had already contributed a few 2017–2018 station-days to the table that suggested H1. Every station-day already seen with chlorophyll is listed in `seen_ids.json` (55 station-days, 51 of them with a chlorophyll value). The held-out test uses only station-days **not** in that list, whatever sensor or collection they come from.
