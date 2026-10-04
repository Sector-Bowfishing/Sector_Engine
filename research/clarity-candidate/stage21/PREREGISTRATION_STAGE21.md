# Stage 21 pre-registration — pre-ACOLITE S2C radiometric correction

Written and frozen before any real nominal S2C L1C pixel is read. `FREEZE_STAGE21.json` holds this file's SHA-256, then the frozen correction's.

**Seen before writing:** everything in Stage 20, and the tile choice (`select21.json`: validity counts and hashes only).

**Not seen:** any real nominal S2C L1C value, and any Stage 21 pair, reflectance or Secchi value.

## 1. Unchanged

- **Models and code:**
  - the frozen C-gbm and its fold recipe (fold models trained exactly as in Stage 19);
  - the Stage 16 gate (`rule16.json`);
  - the Stage 19 causal consensus code;
  - the frozen ACOLITE K4 path (`stage20/aco20_one.py` settings: K4, `l2w_mask` False, lake-elevation pressure, 60 m disks, M0–M3 sampling).
- **Bars:** the Stage 20 authority-lift bars, unchanged and never lowered; the Stage 16 freeze bars; the true 9/10 targets.
- **Excluded data:** no field reports, and no Secchi value is used for any fit or choice.

## 2. Data

**T, the real nominal tandem:**
- 150 tile-dates from the 29 Oct – 18 Dec 2024 S2A/S2C tandem (`select21.json`).
- S2A: the Google Cloud L1C, N0511 2024, which is the product the reprocessed collection reuses.
- S2C: the real nominal reprocessed L1C, N0511 generated 2026, from `s3://sentinel-s2-l1c` (requester pays), rebuilt into a SAFE byte for byte from the bucket's files.
- Split by datatake (date + relative orbit), whole units:
  - **TD**, derivation: 77 tiles, 41 datatakes;
  - **TH**, held out: 73 tiles, 38 datatakes;
  - TH is also reported by the strata "before 12 Dec" (no ACOLITE run in Stage 20) and "12–18 Dec".

**Current era, fresh (never seen):**
- **F25:** S2C N0511 (Apr–Oct 2025) against S2A/S2B 1–2 days apart, both ≤ 20% cloud, at sites not used by Stage 20's operational pairs. Same rules as `stage20/build20.py ops`, 80 per year.
- **F26:** the same for S2C N0512/N0513, Apr–Sep 2026.

**Current era, seen in Stage 20:** C25, C26 and H4. Secondary; reported, not gating.

**Floor:** the Stage 20 S2A-vs-S2B pairs (`floor20.json`), unchanged.

## 3. The correction (derived on TD only)

### 3a. Top-of-atmosphere additive offsets for S2C B08, B8A, B11, B12

**Grid.** The 20 m grid of the tile. Both L1C share it. B08 is averaged 2×2 and B10 is repeated 3×3.

**Reflectance.** ρt = (DN + RADIO_ADD_OFFSET) / QUANTIFICATION_VALUE, each product's own metadata.

**Water pixels.** All of:
- S2A NDWI (B03, B8A) > 0.2;
- S2A B11 < 0.03;
- S2A and S2C B10 < 0.002 (cirrus);
- |ρt,C(B05) / ρt,A(B05) − 1| < 0.10 (moving cloud or shadow);
- both pixels valid (DN > 0).

A tile counts if it has ≥ 200 water pixels.

**Per tile.** δ_tile,b = median over its water pixels of (ρt,C − ρt,A).

**Model M1** (default): constant δ_b = median over TD tiles of δ_tile,b.

**Model M2:** δ_tile,b = α_b + β_b · m_C,b, where m_C,b is the S2C tile's own median ρt,b over its clear pixels (B10 < 0.002, B02 < 0.3). That is computable from S2C alone. M2 replaces M1 for a band only if, on TD, both hold:
- Spearman |r(δ_tile, m_C)| ≥ 0.5;
- M2's residual MAD across tiles is ≥ 25% below M1's.

The fit is Theil–Sen.

**Diagnostics (reported, not applied):**
- the S2C vs S2A gain, from S2A-reflectance deciles over clear land and water;
- δ by detector, from the S2C detector footprint;
- the visible bands at the top of the atmosphere (TH only).

**Applied.** The offsets are subtracted from S2C's ACOLITE L1R rhot (B08, B8A, B11, B12) before atmospheric correction. ACOLITE's own `offsets_toa` multiplies instead of adding, so a wrapper does it (as Stage 20's `aco20x_one.py`, with B08 added). No gain is changed.

### 3b. B05 band-shape adjustment, after ACOLITE (on S2C L2W ρw)

- **Formula:** B05′ = 1.0332·B05 − 0.0397·(B06 − B04), the `srf20.json` physics adjustment frozen in Stage 20.
- **Why it is applied:** the band-response physics (−7.4%) and the nominal Sen2Cor tandem (−5.5%) agree in sign and size.
- **No other band is adjusted.** The physics predictions for B02 (−5%) and B04 (−3.5%) are not borne out by the nominal Sen2Cor tandem (−1.9%, 0.0%).

### 3c. Versions

| | What it is | Role |
|---|---|---|
| **K2 = 3a + 3b** | The Stage 21 correction | Decides validity and authority. Nothing is selected among versions. |
| K0 | Raw S2C, identical ACOLITE | Reported |
| K1 | 3a only | Reported |
| B | Stage 12 V-ρw on K0 | Comparator |

## 4. Pipeline

- **Same treatment for both satellites:** S2A and S2C go through the identical frozen ACOLITE path, with the same crops (±0.07/±0.09 grouping), elevation (EPQS for US, GLO-30 elsewhere), masks, disks and sampling.
- **S2C runs:** K0 and K1 come from the same download. K2 is K1 plus 3b.
- **Pair quantities:** as Stage 20 section 4 (`stage20/lib20.pair_metrics`):
  - band log ratio B02–B05;
  - Δp (frozen production C-gbm);
  - states (Stage 16 gate, S2C at full authority);
  - state overlap;
  - harm proxy (class jump ≥ 2).

## 5. Bars (Stage 20 section 6, unchanged)

| Bar | TH (near-simultaneous) | F25 / F26 (1–2 days apart) |
|---|---|---|
| Spectral: \|median r_b\|, each of B02–B05 | ≤ 0.0128 | ≤ 0.0212 |
| Visibility: \|median Δp\| | ≤ 0.03 | ≤ 0.03 |
| State overlap | ≥ 0.95 | ≥ min(0.95, floor − 0.03) |
| Harm proxy | ≤ 0.02 | ≤ floor + 0.02 |

- **Pooled:** across all gating held-out pairs, |median Δp| ≤ 0.03.
- **Which strata gate:** TH, F25 and F26, each only with ≥ 15 pairs with both scenes valid. TH must gate, plus at least one of F25/F26.
- **Known strictness:** the S2A–S2B floor itself exceeds the 1–2-day spectral bar (Stage 20 section 8). The bar is kept, and the verdict is also reported without the spectral row, for context only.

## 6. Verdicts

**PRE-ACOLITE S2C CORRECTION VALID: YES** if, on TH:
- every corrected band's residual top-of-atmosphere water offset (median over TH tiles of δ_tile,b after correction) is within ±0.0003;
- K2 meets the TH visibility, state and harm bars.

**Authority-lift bar** (as Stage 20): K2 meets every row of section 5 in every gating stratum, plus the pooled check.

**Secchi validation (after the K2 freeze; never used to choose):**
- **Rows:** every eligible S2C truth row (development anchors with outer folds, certification and fresh rows), re-run through the corrected ACOLITE path.
- **Compared:** K0, K1, K2 and B, against the S2A/B reference rows.

**S2C FULL AUTHORITY: YES** only if the lift bar passes and K2 on S2C rows meets all three:
- harmful ≤ reference + 0.05;
- severe ≤ 0.02;
- |median signed log10 error − the reference's| ≤ 0.05.

**STAGE 12 NOMINAL S2C CORRECTION RETIRED: YES** only if S2C full authority is YES. K2 then replaces Stage 12 for S2C N0511/N0512/N0513 in research. Production is unchanged.

## 7. If full authority: the Stage 19 causal-consensus re-run

**Code.** `stage20/dev20.py`'s patches, with these differences:
- S2C anchors and S2C prior passes use the K2 re-run samples (corrected ACOLITE) instead of raw + the Stage 20 correction;
- the Stage 12 path is not used for any S2C scene;
- the fold models are unchanged.

**Windows and selection.**
- Windows: past 5, 10 and 15 days.
- Candidates are the windows passing the Stage 16 freeze bars; take the best balanced score.
- The selected window is the smallest one whose balanced and stained differences from the best have lake-bootstrap CIs (B = 2000, seed 19) containing 0.

**Material effects, on 2025–26 events at the selected window:**
- **Zero-prior-view rate is "materially lower"** if it falls by ≥ 5 points.
- **Strong is "raised"** if its share of usable answers rises by ≥ 2 points with accuracy ≥ 0.90.

**Also reported:** the same on all events, and every class and operational score, harmful, severe, Unknown, Strong and exact feet.

**Live evidence change.** It is adopted for research only if the selected window passes the Stage 16 freeze bars and harmful is no more than 1 point above Stage 19's 5-day result. Otherwise Stage 19 stands.

## 8. If the lift bar or Secchi validation fails

- S2C stays at lower authority.
- Stage 12 is not retired.
- Stage 19 stands.
- Availability is reported as hypothetical.
