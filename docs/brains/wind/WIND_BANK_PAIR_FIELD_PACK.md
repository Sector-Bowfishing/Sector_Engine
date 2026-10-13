# Bank-pair field pack (candidate pairs from the pilot and contrast lakes)

Purpose: obtain the **physical truth** Wind lacks (BWIS B3 + D2; certification dims 6/7) with observations a tester can do in about a minute per bank (`WIND_FIELD_OBSERVATION_PROTOCOL.md`). Pairs were selected by geometry alone (`jobs/wind-hourly/research/field_pairs.py`; no forecasts, no H2): all 99 candidates are in `data/field_pairs_candidates.json`. **Access and safety are not verified** — check public ramps, hazards and permission before any visit; coordinates are shoreline anchors, not launch points.

## Independence warning
Guntersville, Wheeler, Wilson and Pickwick are four reaches of the Tennessee River system with similar wind climate and fetch geometry; **they count as one environment** for generalisation (and the same 8 METAR stations back all four). Lake Hartwell (SC/GA, ESTIMATED geometry), Mille Lacs (open natural lake), Lake McConaughy (plains reservoir), Toledo Bend (large southern reservoir, ESTIMATED) and Lake Maurepas (shallow coastal) are added for independence and to test the ESTIMATED tier. Smith Mountain Lake VA (dendritic, max p90 fetch 0.75 km) is a useful *negative control* (everything should read protected/low) but has no strong pairs.

## Pair types
- **Mirror pair:** opposite shores of one open-water run. Wind from θ → A (downwind shore) DIRECT/HIGH FETCH, B (upwind shore) PROTECTED. **Reverse the wind and the roles swap**, so the same two banks test the model in both directions.
- **Cove vs point:** ≤ 1.5 km apart, one exposed point, one true cove (the "is this cove sheltered?" question).
- **Subtle ordering:** two exposed banks ≤ 3 km apart, predicted waves 1.25–2.5× different (tests fetch *ordering*, not just land vs water).

## Conditions that make a session count (all pairs)
- Wind from the stated direction ±25°, **8–15 mph sustained** (a forecast ≥ 5 mph with the NBM breezy-risk flag is ideal), steady ≥ 3 h; evening or night (the product window 7 pm–1 am local) — daytime is acceptable for the first sessions.
- Visit both banks within **60 minutes** (same device, same height, 60-s average). Nights with a flag are the most informative (they also test the risk flag).
- Skip: < 5 mph (direction unreliable), thunderstorms, wind shifting > 45° during the session, or wind from the reverse direction unless that is the planned reverse session.

## What to record (per bank)
Water: calm / light / choppy / rough · boat control: easy / noticeable / difficult · exposure: DIRECT / CROSS / PROTECTED / UNSURE · wind direction (handheld or compass + visual) and speed (handheld if available) · confidence 1–3 · one photo looking upwind from the boat at the bank. **The observer does not see the model's prediction** until after submitting.

## What would falsify the model (proposed; the canonical scorer owns real thresholds)
- Mirror/cove pair: predicted-rougher bank is observed **rougher by at least one step** in a session = concordant; equal = half; calmer = discordant.
- After **≥ 20 qualifying sessions on ≥ 2 independent lakes**: concordance < 0.70 → the vocabulary/fetch model is not supported as a bank ranking.
- **False-PROTECTED:** a bank called PROTECTED recorded *choppy or rough* (or boat control *difficult*) while wind ≥ 8 mph from the stated direction: more than **1 in 10** such PROTECTED calls (≥ 15 calls) → ESTIMATED labels stay withheld and the margin policy is reopened.
- ESTIMATED lakes (Hartwell, Toledo Bend) are scored separately from AUDITED lakes.
- Evidence Addendum v1 sets the scoring volume for certification credit (≥ 40 holdout pairs, ≥ 2 lakes, ≥ 3 wind quadrants; concordance ≥ 80% earns full credit, 50% none).


## Guntersville|AL — pilot · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** GT-005719 (34.5346, -86.1217) · **B** GT-001172 (34.4906, -86.1707) | from **SW** (225°) | A DIRECT + HIGH FETCH, 7.8 km, ~8.8 in · B PROTECTED, 31 m, ~0.6 in; reversed (NE) A PROTECTED, B DIRECT (6.3 km) | 252× fetch, 14.7× wave | 6.6 km |
| 2 | Mirror | **A** GT-005212 (34.4231, -86.3213) · **B** GT-000393 (34.3592, -86.3146) | from **S** (180°) | A DIRECT + HIGH FETCH, 6.6 km, ~8.1 in · B PROTECTED, 31 m, ~0.6 in; reversed (N) A PROTECTED, B DIRECT (4.6 km) | 212× fetch, 13.5× wave | 7.1 km |
| 3 | Cove Vs Point | **A** GT-005626 (34.5277, -86.1459) · **B** GT-004651 (34.5328, -86.1473) | from **SW** (225°) | A CROSS + HIGH FETCH, 6.6 km, ~8.1 in · B PROTECTED, 31 m, ~0.6 in | 214× fetch, 13.5× wave | 0.6 km |
| 4 | Subtle Ordering | **A** GT-001039 (34.4221, -86.1978) · **B** GT-001025 (34.4350, -86.1814) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.0 km, ~7.7 in · B DIRECT, 2381 m, ~4.9 in | 3× fetch, 1.6× wave | 2.1 km |

Geometry confidence note: AUDITED geometry; 6217 usable banks; strong-fetch threshold 1200 m. Audited geometry (modeled exposure, no field truth).

## Wheeler|AL — pilot · geometry AUDITED (MEDIUM)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** WH-W000328 (34.7777, -87.2230) · **B** WH-W003903 (34.7376, -87.2716) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.3 km, ~7.9 in · B PROTECTED, 28 m, ~0.5 in; reversed (NE) A PROTECTED, B DIRECT (6.2 km) | 225× fetch, 15.8× wave | 6.3 km |
| 2 | Mirror | **A** WH-W000495 (34.6935, -87.0614) · **B** WH-W003544 (34.6519, -87.0618) | from **S** (180°) | A DIRECT + HIGH FETCH, 4.4 km, ~6.7 in · B PROTECTED, 26 m, ~0.5 in; reversed (N) A PROTECTED, B DIRECT (4.3 km) | 171× fetch, 13.4× wave | 4.6 km |
| 3 | Cove Vs Point | **A** WH-W000333 (34.7775, -87.2186) · **B** WH-W000343 (34.7778, -87.2043) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.0 km, ~7.7 in · B PROTECTED, 31 m, ~0.6 in | 194× fetch, 12.8× wave | 1.3 km |
| 4 | Subtle Ordering | **A** WH-W000337 (34.7761, -87.2103) · **B** WH-W000367 (34.7629, -87.1821) | from **SW** (225°) | A DIRECT + HIGH FETCH, 4.7 km, ~6.8 in · B DIRECT, 2964 m, ~5.4 in | 2× fetch, 1.3× wave | 3.0 km |

Geometry confidence note: AUDITED geometry; 4462 usable banks; strong-fetch threshold 1259 m. Audited geometry (modeled exposure, no field truth).

## Wilson|AL — pilot · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** WI-W000424 (34.8417, -87.5334) · **B** WI-W001002 (34.8037, -87.5824) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.1 km, ~7.8 in · B PROTECTED, 71 m, ~0.8 in; reversed (NE) A PROTECTED, B CROSS (5.8 km) | 86× fetch, 9.8× wave | 6.2 km |
| 2 | Mirror | **A** WI-W000554 (34.8118, -87.4365) · **B** WI-W000791 (34.7858, -87.4382) | from **S** (180°) | A DIRECT, 3.1 km, ~5.6 in · B PROTECTED, 20 m, ~0.4 in; reversed (N) A PROTECTED, B DIRECT (3.0 km) | 155× fetch, 14.0× wave | 2.9 km |
| 3 | Cove Vs Point | **A** WI-W000418 (34.8432, -87.5412) · **B** WI-W000406 (34.8422, -87.5523) | from **SW** (225°) | A CROSS + HIGH FETCH, 6.7 km, ~8.2 in · B PROTECTED, 28 m, ~0.5 in | 241× fetch, 16.4× wave | 1.0 km |
| 4 | Subtle Ordering | **A** WI-W000426 (34.8422, -87.5315) · **B** WI-W000460 (34.8382, -87.5206) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.0 km, ~7.7 in · B DIRECT, 3712 m, ~6.1 in | 2× fetch, 1.3× wave | 1.1 km |

Geometry confidence note: AUDITED geometry; 1046 usable banks; strong-fetch threshold 1699 m. Audited geometry (modeled exposure, no field truth).

## Pickwick Lake|TN — pilot · geometry AUDITED (MEDIUM)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** PK-W000682 (34.9179, -88.0436) · **B** PK-W001582 (34.8890, -88.0778) | from **SW** (225°) | A DIRECT + HIGH FETCH, 4.3 km, ~6.5 in · B PROTECTED, 31 m, ~0.6 in; reversed (NE) A PROTECTED, B CROSS (4.4 km) | 138× fetch, 10.8× wave | 4.5 km |
| 2 | Mirror | **A** PK-W000787 (34.8570, -87.9320) · **B** PK-W001440 (34.8168, -87.9331) | from **S** (180°) | A DIRECT + HIGH FETCH, 4.4 km, ~6.7 in · B PROTECTED, 31 m, ~0.6 in; reversed (N) A PROTECTED, B DIRECT (4.8 km) | 143× fetch, 11.2× wave | 4.5 km |
| 3 | Cove Vs Point | **A** PK-W000681 (34.9178, -88.0457) · **B** PK-W000604 (34.9164, -88.0612) | from **SW** (225°) | A CROSS + HIGH FETCH, 4.3 km, ~6.6 in · B PROTECTED, 28 m, ~0.5 in | 155× fetch, 13.2× wave | 1.4 km |
| 4 | Subtle Ordering | **A** PK-W000687 (34.9170, -88.0328) · **B** PK-W000647 (34.9398, -88.0391) | from **SW** (225°) | A DIRECT, 3.4 km, ~5.9 in · B DIRECT, 2116 m, ~4.6 in | 2× fetch, 1.3× wave | 2.6 km |

Geometry confidence note: AUDITED geometry; 2490 usable banks; strong-fetch threshold 1454 m. Audited geometry (modeled exposure, no field truth).

## Lake Hartwell|SC — pilot (ESTIMATED geometry) · geometry ESTIMATED (MEDIUM)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** E-0351 (34.3875, -82.8224) · **B** E-0385 (34.3632, -82.8538) | from **SW** (225°) | A DIRECT, 3.5 km, ~5.9 in · B PROTECTED, 20 m, ~0.4 in; reversed (NE) A PROTECTED, B CROSS (3.1 km) | 175× fetch, 14.8× wave | 3.9 km |
| 2 | Mirror | **A** E-0192 (34.4842, -82.8771) · **B** E-0249 (34.4638, -82.8793) | from **S** (180°) | A DIRECT, 2.1 km, ~4.6 in · B PROTECTED, 20 m, ~0.4 in; reversed (N) A PROTECTED, B DIRECT (2.0 km) | 105× fetch, 11.5× wave | 2.3 km |
| 3 | Cove Vs Point | **A** E-0351 (34.3875, -82.8224) · **B** E-0372 (34.3764, -82.8134) | from **SW** (225°) | A DIRECT, 3.5 km, ~5.9 in · B PROTECTED, 20 m, ~0.4 in | 175× fetch, 14.8× wave | 1.5 km |
| 4 | Subtle Ordering | **A** E-0251 (34.4632, -82.8476) · **B** E-0227 (34.4733, -82.8448) | from **SW** (225°) | A DIRECT, 2.4 km, ~4.9 in · B DIRECT, 1424 m, ~3.8 in | 2× fetch, 1.3× wave | 1.2 km |

Geometry confidence note: ESTIMATED geometry; 399 usable banks; strong-fetch threshold 1200 m. **Validates the ESTIMATED tier** — priority for field time.

## Mille Lacs Lake|MN — open natural lake · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** N-B06BD2-W000431 (46.1999, -93.4930) · **B** N-B06BD2-W000617 (46.1317, -93.5974) | from **SW** (225°) | A DIRECT + HIGH FETCH, 11.5 km, ~10.7 in · B PROTECTED, 278 m, ~1.7 in; reversed (NE) A PROTECTED, B CROSS (10.8 km) | 41× fetch, 6.3× wave | 11.0 km |
| 2 | Mirror | **A** N-B06BD2-W000196 (46.3265, -93.7816) · **B** N-B06BD2-W000095 (46.2262, -93.7832) | from **S** (180°) | A DIRECT + HIGH FETCH, 12.3 km, ~11.1 in · B PROTECTED, 76 m, ~0.9 in; reversed (N) A PROTECTED, B CROSS (11.0 km) | 161× fetch, 12.3× wave | 11.2 km |
| 3 | Cove Vs Point | **A** N-B06BD2-W000442 (46.1843, -93.4928) · **B** N-B06BD2-W000457 (46.1753, -93.4811) | from **SW** (225°) | A CROSS + HIGH FETCH, 8.3 km, ~9.1 in · B PROTECTED, 46 m, ~0.7 in | 181× fetch, 13.0× wave | 1.4 km |
| 4 | Subtle Ordering | **A** N-B06BD2-W000459 (46.1733, -93.4816) · **B** N-B06BD2-W000470 (46.1670, -93.4730) | from **SW** (225°) | A DIRECT + HIGH FETCH, 5.0 km, ~7.1 in · B DIRECT, 3214 m, ~5.7 in | 2× fetch, 1.2× wave | 1.0 km |

Geometry confidence note: AUDITED geometry; 741 usable banks; strong-fetch threshold 3000 m. Audited geometry (modeled exposure, no field truth).

## Lake McConaughy|NE — plains reservoir · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** N-E0790D-W000290 (41.2476, -101.7019) · **B** N-E0790D-W000444 (41.2076, -101.7539) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.1 km, ~7.8 in · B PROTECTED, 28 m, ~0.5 in; reversed (NE) A PROTECTED, B DIRECT (5.8 km) | 217× fetch, 15.6× wave | 6.2 km |
| 2 | Mirror | **A** N-E0790D-W000242 (41.2548, -101.7620) · **B** N-E0790D-W000449 (41.2097, -101.7609) | from **S** (180°) | A DIRECT + HIGH FETCH, 5.0 km, ~7.1 in · B PROTECTED, 184 m, ~1.4 in; reversed (N) A PROTECTED, B CROSS (4.9 km) | 27× fetch, 5.1× wave | 5.0 km |
| 3 | Cove Vs Point | **A** N-E0790D-W000290 (41.2476, -101.7019) · **B** N-E0790D-W000275 (41.2486, -101.7154) | from **SW** (225°) | A DIRECT + HIGH FETCH, 6.1 km, ~7.8 in · B PROTECTED, 28 m, ~0.5 in | 217× fetch, 15.6× wave | 1.1 km |
| 4 | Subtle Ordering | **A** N-E0790D-W000326 (41.2378, -101.6767) · **B** N-E0790D-W000332 (41.2276, -101.6729) | from **SW** (225°) | A DIRECT + HIGH FETCH, 4.9 km, ~7.0 in · B DIRECT, 3002 m, ~5.5 in | 2× fetch, 1.3× wave | 1.2 km |

Geometry confidence note: AUDITED geometry; 471 usable banks; strong-fetch threshold 3000 m. Audited geometry (modeled exposure, no field truth).

## Toledo Bend Reservoir|TX — large southern reservoir (ESTIMATED geometry) · geometry ESTIMATED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** E-0293 (31.3579, -93.6384) · **B** E-0316 (31.3009, -93.6979) | from **SW** (225°) | A DIRECT + HIGH FETCH, 8.1 km, ~9.0 in · B PROTECTED, 30 m, ~0.5 in; reversed (NE) A PROTECTED, B CROSS (9.4 km) | 270× fetch, 18.0× wave | 8.5 km |
| 2 | Mirror | **A** E-0139 (31.6019, -93.7789) · **B** E-0193 (31.5247, -93.7863) | from **S** (180°) | A DIRECT + HIGH FETCH, 10.9 km, ~10.5 in · B PROTECTED, 70 m, ~0.8 in; reversed (N) A PROTECTED, B DIRECT (14.7 km) | 156× fetch, 13.1× wave | 8.6 km |
| 3 | Cove Vs Point | **A** E-0348 (31.2494, -93.5886) · **B** E-0346 (31.2534, -93.5886) | from **SW** (225°) | A DIRECT + HIGH FETCH, 7.7 km, ~8.7 in · B PROTECTED, 30 m, ~0.5 in | 255× fetch, 17.4× wave | 0.4 km |
| 4 | Subtle Ordering | **A** E-0075 (31.7973, -93.8117) · **B** E-0074 (31.8018, -93.7953) | from **SW** (225°) | A DIRECT + HIGH FETCH, 4.6 km, ~6.8 in · B DIRECT, 1051 m, ~3.2 in | 4× fetch, 2.1× wave | 1.6 km |

Geometry confidence note: ESTIMATED geometry; 395 usable banks; strong-fetch threshold 2817 m. **Validates the ESTIMATED tier** — priority for field time.

## Lake Maurepas|LA — shallow coastal lake · geometry AUDITED (HIGH)

| # | Type | Banks (shoreline anchor lat, lon) | Best separating wind | Predicted at 12 mph | Contrast | Distance |
|---|---|---|---|---|---|---|
| 1 | Mirror | **A** N-043DCB-W000357 (30.2399, -90.4291) · **B** N-043DCB-W000064 (30.1719, -90.5096) | from **SW** (225°) | A DIRECT + HIGH FETCH, 11.0 km, ~10.5 in · B PROTECTED, 34 m, ~0.6 in; reversed (NE) A PROTECTED, B CROSS (11.1 km) | 324× fetch, 17.5× wave | 10.8 km |
| 2 | Mirror | **A** N-043DCB-W000273 (30.3241, -90.4370) · **B** N-043DCB-W000370 (30.2186, -90.4379) | from **S** (180°) | A DIRECT + HIGH FETCH, 11.8 km, ~10.9 in · B PROTECTED, 32 m, ~0.6 in; reversed (N) A PROTECTED, B DIRECT (10.9 km) | 369× fetch, 18.2× wave | 11.7 km |
| 3 | Cove Vs Point | **A** N-043DCB-W000312 (30.2891, -90.4012) · **B** N-043DCB-W000320 (30.2849, -90.3881) | from **SW** (225°) | A DIRECT + HIGH FETCH, 17.5 km, ~13.2 in · B PROTECTED, 151 m, ~1.2 in | 116× fetch, 11.0× wave | 1.3 km |
| 4 | Subtle Ordering | **A** N-043DCB-W000129 (30.2099, -90.5831) · **B** N-043DCB-W000124 (30.2114, -90.5926) | from **SW** (225°) | A DIRECT, 1.5 km, ~3.9 in · B DIRECT, 402 m, ~2.0 in | 4× fetch, 1.9× wave | 0.9 km |

Geometry confidence note: AUDITED geometry; 355 usable banks; strong-fetch threshold 3000 m. Audited geometry (modeled exposure, no field truth).

## Suggested first programme (no one drives hundreds of lakes)
1. **Guntersville** (home water): 6 sessions covering SW/NE and S/N mirror pairs — also tests wind-from reversals within days.
2. **Lake Hartwell** (ESTIMATED): 6 sessions — the first physical check of the ESTIMATED tier.
3. **One open natural lake** (Mille Lacs) or plains reservoir (McConaughy) via a trusted local tester: 4 sessions with ≥ 10 mph.
4. **Toledo Bend** (ESTIMATED, long fetch): 4 sessions via a local tester.
5. Trusted beta testers can do single-bank observations (no pairing) opportunistically; they feed the agreement matrix between the tester's DIRECT/CROSS/PROTECTED call and the Brain's, but only paired sessions count toward concordance.
