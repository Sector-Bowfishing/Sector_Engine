# Addendum B to CERT_PROTOCOL_STAGE12.md: the satellite collection for 2017 and 2022

Recorded before any certification match was counted. No Secchi, chlorophyll or turbidity value from any certification
source has been fetched or seen.

**Found on first use.** Earth Search's production collection `sentinel-2-c1-l2a` has no scenes for 2017 or 2022; it
returned 0 items per summer at a test site where every other year has 17–31. (The Stage 11 corpus holds only 4 rows from
2022, which fits.) Both NLA surveys fall in those years, so the protocol's "`extract.py`, unchanged" matched no NLA visit.

**Change.** For observations dated in 2017 or 2022, the match uses Earth Search's `sentinel-2-l2a` collection (Sen2Cor
L2A, the same SCL and asset names) with that collection's own per-scene reflectance offset:
- **2022** (baseline 04.00, offset applied): ρ = DN × 0.0001 − 0.1, as in production;
- **2017** (baseline 00.01): ρ = DN × 0.0001.

Everything else in `extract.py` is unchanged: the gates, the 60 m disk and the pass choice. Other years keep
`sentinel-2-c1-l2a`.

**Consequence, stated now.** The 2017 and 2022 matches were screened on a Sen2Cor L2A that is not the production
collection. That is acceptable for blind construction, which only asks whether the station is clearly visible. The
engine being certified reads its own reflectance (L1C → ACOLITE), which exists for every year.
