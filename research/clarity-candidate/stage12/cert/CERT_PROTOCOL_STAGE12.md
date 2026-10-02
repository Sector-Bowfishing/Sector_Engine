# Current Clarity: blind external certification protocol

Written 2026-09-30, before any site, visit or observation file from these sources was fetched. Its sha256 goes into
`FREEZE_STAGE12.json`. The protocol is not changed after the freeze. Anything unforeseen is recorded as a timestamped
addendum before the data it governs is looked at.

**Purpose.** To certify a frozen Current Clarity engine on authoritative Secchi-disk observations that no Sector
development stage (1–12) has fetched, fitted or evaluated, without anyone having to survey lakes.

**Michael's Guntersville field survey** is a separate real-world acceptance test. It is never used for model selection,
and it is not part of this set.

## 1. Sources

| Tier | Source | What is fetched while the sample is built | What stays sealed |
|---|---|---|---|
| **US core** | EPA National Lakes Assessment 2022, from EPA's NARS data files (not WQP) | `nla22_siteinfo.csv`: sites, index-site coordinates, visit dates, the sampled flag | `nla22_secchi.csv`, and every other results file. It is not downloaded, and neither is the combined report zip |
| **US core** | EPA National Lakes Assessment 2017, from EPA's NARS files | `nla_2017_site_information-data.csv`; the index-site coordinates and date/time columns of `nla_2017_profile-data.csv` (the profile values are dropped on read) | `nla_2017_secchi-data.csv`, and every other results file |
| **Cool season, out of domain** | Finland SYKE Vesla open data (OData, CC BY 4.0) | `Paikka` (lake sites), `Naytteenotto` (sampling events and times), and `YmpHavainto` with `$select=Naytteenotto_Id` and `YmpSuure_Id=4` only, to know which events have a Secchi reading | the Secchi values (`YmpHavainto.Arvo`) |

**Not used:**
- WQP (already fetched in full for 2018–2026);
- LAGOS-US (compiled from WQP);
- Quebec RSVL (seasonal means only);
- Sweden MVM (needs an account);
- Ontario Lake Partner (dates and values appear to share one file);
- TVA (no public bulk access).

**The US core carries the certification verdicts.** SYKE is reported apart as a cool-season, humic-lake stress test.

## 2. Independence

- **Never fetched.** NLA 2022 is not in WQP. NLA 2017 is in WQP only for 2017, outside the 2018–2026 pull, and it is taken
  from EPA's files. SYKE was never fetched.
- **Duplicate visits.** An NLA visit is dropped if the Stage 1 WQP pull has any record at a site within 100 m of the
  index site on the same date. That test reads only the pull's site coordinates and dates.
- **Development lakes.** A lake is dropped if its index site is within 5 km of any station in the Stage 5–12 development
  corpora (Stage 11 corpus sets G, N, F and E, and the AERONET-OC sites), or it is Guntersville.
- **The P2 fresh holdout.** Every observation is dated ≤ 2025-12-31, and nothing from 2026 is used.

## 3. Eligibility and matching

- **NLA:** visits of sampled lakes (2022: `SITESAMP=Y`), at the index site.
- **SYKE:**
  - lake sites (`YmpTyyppi_Id=10`) with a Secchi-bearing event from April to November;
  - events with an ice-thickness record are dropped (`YmpSuure_Id=2`);
  - lakes are taken in a random order (seed 20261002), up to 400 lakes and 3 events per lake, spread across months where
    possible.
- **Satellite match:**
  - `stage6/extract.py --max-dt 1`, unchanged, with the production gates and the 60 m disk;
  - the best pass is the smallest |Δt|, then the most valid pixels;
  - at least 5 valid pixels, and one row per site-cell and scene-day.
- **Per lake:** at most 3 matched observations, chosen in seeded order.

## 4. What the set must reach

**Checked blind, before any value is fetched:**
- ≥ 400 matched observations;
- ≥ 100 distinct lakes;
- ≥ 20 US states in the US core, with no state above 15% of the US-core observations;
- ≥ 15% of all observations from October to April, across ≥ 20 lakes.

**Per class, checked at unblinding** (the Stage 10 SUPPORTED minima): clear 40, normal 40, stained 60, algae 30, sediment
20, limited 25.
- **Planning prior:** the Stage 11 corpus class shares. The set is declared ready only if its expected per-class counts
  meet these minima.
- **At unblinding, a short class** is topped up by raising the per-lake cap to 5, in the same seeded order. Anything
  still short is reported as INSUFFICIENT for that capability; no claim is made from it.

**Secchi-grade rules, applied at unblinding:**
- **NLA:** the mean of disappearance and reappearance; `CLEAR_TO_BOTTOM=Y` is dropped.
- **SYKE:** readings through ice are dropped.

## 5. Sealing and use

- **The frozen list.** Once built, the matched sample (site IDs, dates, Sentinel-2 items) is written to
  `cert/blind_sample.csv` and its sha256 recorded. Its satellite readouts are used for nothing but counting valid matches.
- **Unsealing.** The Secchi values are fetched only in a future certification stage, after the engine to be certified
  is frozen and hashed. They are scored once, with the Stage 10 bars and the Stage 12 §5 rubrics. The engine is not
  changed afterwards.
