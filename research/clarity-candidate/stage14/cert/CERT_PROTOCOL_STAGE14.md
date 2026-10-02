# Current Clarity Stage 14: certification protocol for the sealed WQP tier

Written 2026-10-01, before any Secchi value of this tier was read. Michael approved the tier's use in the Stage 14
request. The protocol's sha256 goes into `stage14/FREEZE_STAGE14.json`. Nothing here changes after the freeze. Anything
unforeseen is recorded as a timestamped addendum before the data it governs is examined.

**What has been read so far (value-blind).**
- `cert/wqp_blind_index.csv` is `q9/wqp/secchi.csv` with the `secchi_m` column deleted on read. It holds site, org,
  coordinates, date, time and the bottom-visible flag.
- `cert/dev_footprint.json` holds the site ids and coordinates of every development file.
- The eligibility counts in this document were computed from those two files. No Secchi, turbidity or chlorophyll value
  of any certification row has been read.

## 1. The certification set

| Part | Source | Status |
|---|---|---|
| **US core A** | NLA 2017 and 2022: the 165 NLA rows of the Stage 13 blind sample (`stage13/cert/blind_sample13.csv`, sha256 `bcb18659…`) | unchanged |
| **US core B (new)** | The sealed WQP tier: the Stage 1 national WQP Secchi pull, under the rules below | built by this protocol |
| **Out-of-domain stress test** | SYKE (Finland): the 749 SYKE rows of the Stage 13 blind sample | unchanged; reported apart |

The US core (A + B) carries every certification verdict.

## 2. Eligible files (sha256 recorded in the freeze file)

- `q9/wqp/secchi.csv`: the only Secchi source for part B. The `secchi_m` column is read once, at unsealing.
- `q9/wqp/turbidity.csv`: same-site, same-day turbidity, read at unsealing for part B rows only.
- `q9/wqp/sites.csv`: site metadata.

**Not used:** `secchi_censored.csv` (censored readings), and `raw/` (the uncleaned downloads).

**Fetched at unsealing:** same-site, same-day chlorophyll a for part B rows. It comes from WQP `Result/search` with
the Stage 11 characteristic list (`Chlorophyll a`, `…corrected for pheophytin`, `…uncorrected for pheophytin`,
`Chlorophyll a (probe)`) and the Stage 11 unit rules (µg/L; median per site-day).

## 3. Inclusion and exclusion (part B)

A WQP Secchi record is eligible only if all of these hold:

1. It is dated from 2018-01-01 to 2025-12-31.
2. **Not a development site.** Its site id appears in no Stage 5–13 file. Those are the Stage 6 station days and
   readouts, the Stage 7 national sites, the Stage 8 fresh draw and readouts, and the Stage 11 corpus, E draw, G days
   and readouts.
3. **No 2026 record at the site.** The site has no Secchi record dated 2026-01-01 or later, so it cannot be part of the
   P2 fresh national pool.
4. **Not Guntersville.** The site lies outside the Guntersville box (34.27–35.06 N, 86.42–85.60 W).
5. **Lake-independent of development.** The site is more than 5 km from every station in the Stage 5–13 development
   corpora: Stage 11 corpus sets G, N, F and E, the Stage 6/8/11 readouts, and the AERONET-OC sites. This is the Stage 12
   NLA rule.
6. **Lake-independent of the rest of the blind set.** The site is more than 5 km from every Stage 12/13 blind-sample site
   (NLA and SYKE).
7. **Not a Stage 1–4 record.** The record's site-day does not appear in any Stage 1–4 file
   (`q9/national_sample.csv`, `q9/targeted_sample.csv`, `q9/targeted_capped.csv`).
8. It is not a censored reading. Censored readings are in `secchi_censored.csv` and are not used.

**Pool, value-blind:** 77,324 site-days at 5,427 sites in 47 states, 15,935 of them October–April.

**Sensitivity subset.** Stage 1–4 analysed the production champion, not the Stage 13 candidates, so its sites are
excluded record by record, not lake by lake. Rows on a lake with no Stage 1–4 site within 5 km are reported separately,
as the strict-independence subset.

## 4. Lakes, sampling and matching

- **Lakes.** Single-linkage clusters of eligible sites within 5 km, as in Stage 11.
- **Draw** (seed 20261015):
  - site-days are shuffled, and those with a same-day turbidity record go first (record presence only, as in Stage 11);
  - at most 1 site-day per site-month and at most 6 per lake;
  - at most 15% of the draw from any one state;
  - **7,000 site-days** in all.
- **Prescreen.** An event goes to the extractor only if a STAC search finds an item within ±1 day with
  `eo:cloud_cover` ≤ 60%. The collection follows Stage 13 addendum B/B2: `sentinel-2-l2a` for 2017 and 2022,
  `sentinel-2-c1-l2a` otherwise.
- **Match.** `stage12/cert/extract_cert.py --max-dt 1`, with the Stage 13 collection and offset settings and
  `stage6/extract.py` unchanged:
  - production gates and the 60 m disk;
  - the best pass is the smallest |Δt|, then the most valid pixels;
  - at least 5 valid pixels.
- **Final part B sample.** In order:
  1. at most 3 matched observations per lake, filled October–April first, then in seeded order;
  2. at most 15% from any one state;
  3. at most **900 observations**, in seeded order.

  None of these steps reads a value.
- **The frozen ACOLITE path, value-blind.** Every matched observation of the certification set (A, B and SYKE) goes
  through the frozen path (`stage14/cert/run_cert_aco.py`):
  - ACOLITE 20260421.0 K4, with lake-elevation pressure. Elevation comes from USGS EPQS in the US and from Copernicus
    GLO-30 (AWS open data) in Finland;
  - `l2w_mask=False`, with the station sampled under the default mask (tier 1) and under M3 (tier 2);
  - 60 m disk, at least 5 pixels;
  - S2C V-ρw harmonisation is applied at scoring.

  The Sen2Cor readouts come from the match step (tier 3).

## 5. Checks

**Before unsealing (blind):** the Stage 12 checks on the whole set:
- ≥ 400 observations;
- ≥ 100 lakes;
- ≥ 20 US states, with none above 15% of the US core;
- ≥ 15% of observations October–April, across ≥ 20 lakes;
- expected per-class US-core counts (Stage 11 corpus shares) at or above the minima.

**At unsealing**, the US core is scored against the Stage 10 SUPPORTED minima per class:

| Class | Minimum |
|---|---:|
| Clear | 40 |
| Normal | 40 |
| Stained | 60 |
| Algae | 30 |
| Sediment | 20 |
| Limited | 25 |

A class below its minimum is **INSUFFICIENT**: no verdict, and its READY line is NO (insufficient).

**No top-up.** Stage 12's top-up of a short class at unblinding is dropped, because it selects on the truth.

## 6. Truth rules at unsealing

- **WQP:**
  - the median of the site-day's readings in `secchi.csv`, kept if 0.05–25 m;
  - turbidity is the surface-most same-day median in NTU/FNU/FTU/NTRU (the Stage 11 rule);
  - chlorophyll follows section 2.
- **NLA:**
  - Secchi is the mean of disappearance and reappearance; `CLEAR_TO_BOTTOM=Y` rows are dropped;
  - chlorophyll a and turbidity come from the same visit's NLA water-chemistry file.
- **SYKE:**
  - Secchi readings through ice are dropped;
  - chlorophyll a and turbidity are same-event values where they exist.
- **Water types** use the Stage 11 `insitu_type` rule: algal = chlorophyll ≥ 15 µg/L; sediment = turbidity ≥ 8 with
  chlorophyll < 15; both labels are required.

## 7. Use

- **Order.** The Secchi values are unsealed only after two freezes:
  - the Stage 14 pre-registration;
  - the frozen engine manifest (`stage14/engine/`).
- **Scoring.** The values are scored once, and the engine is not changed afterwards.
- **Disjointness.** The certification set is disjoint from every fit and selection: no certification row enters any fit,
  cut-point, band, tier rule or authorisation.
