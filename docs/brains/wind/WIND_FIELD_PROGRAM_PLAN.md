# Field bank-pair programme — the smallest useful plan (prepared; nobody is asked to start yet)

Meets the minimum for evidence worth scoring: **≥ 40 scored pairs · ≥ 2 genuinely independent lakes · ≥ 3 wind-FROM quadrants**, blind to predictions, one-minute records (`WIND_FIELD_OBSERVATION_PROTOCOL.md`), accepted or rejected against `WIND_BANK_VALIDATION_V2_PREREG.md`. Candidate pairs: `WIND_BANK_PAIR_FIELD_PACK.md` (99 pairs, 9 lakes).

## Who, where
| System | Role | Pairs | Notes |
|---|---|---|---|
| **Lake Guntersville** (Tennessee River; AUDITED) | Michael / home-water tester | 20 | Wheeler, Wilson, Pickwick add sessions but are the **same environmental system**: they never count as extra independence |
| **Lake Hartwell** (SC/GA; ESTIMATED) | beta tester or local bowfisher | 16–20 (≥ 8 mandatory) | first physical test of the ESTIMATED tier |
| Third independent system (Mille Lacs / McConaughy / Toledo Bend / Maurepas) | local tester | 4+ | useful for generalisation and a fetch-heavy case; optional for the minimum |

## How long it takes (from CAL+H1 METAR, May–Oct 2026; planning only)
Qualifying **afternoons** (≥ 3 h at ≥ 8 mph, 10 am–6 pm CDT) at the Huntsville ASOS: **≈ 16 a month** (S 5.8, W 4.0, N 3.4, E 2.6); other Tennessee River stations 4–16. Qualifying **evenings** (7 pm–1 am) are rare: **≈ 3.6 a month** at Huntsville, 0.2–2.4 elsewhere. ≥ 10 mph afternoons ≈ 7.6 a month. Hartwell has no station in the corpus (assume similar; unverified).
- With ~half of those days practical and 1–2 pairs per session, one tester collects **≈ 6–12 pairs a month**. Two systems in parallel reach 40 pairs in **≈ 3 months**; autumn–spring winds are stronger (this corpus is summer-weighted), so it should be faster.
- **Evening-only sessions would take a year**, so afternoon sessions must count for the wave-response/fetch physics; each record carries a time-of-day tag and results are reported by day vs night. Whether daytime pairs earn certification credit is the Evidence Addendum owner's call — ask before relying on it. Night sessions are prioritised whenever a flagged ("could turn breezy") evening occurs.

## Session recipe (≈ 2.5–3 hours, 2 pairs)
1. Pick pairs from the plan whose axis matches the forecast (wind-FROM ± 25°, 8–15 mph, steady ≥ 3 h); the app/sheet shows neutral labels X/Y and coordinates only.
2. Per bank (≈ 1 min each): water surface calm/light/choppy/rough · bank EXPOSED/PROTECTED/UNSURE (optional DIRECT/CROSS on audited lakes) · boat control easy/noticeable/difficult · confidence 1–3 · photo upwind · wind speed/direction if an anemometer is aboard.
3. Visit both banks of a pair within 60 minutes; the portable anemometer (when available) reads 10 min at mid-fetch once per session.
4. Submit the records before looking at any Sector prediction.

## Quadrant coverage
Prefer different pairs/axes on different days: S and W are the commonest, N second, E rarest (≈ 2.6 afternoons/month): E and reverse-direction sessions are best taken from the **mirror pairs** (reverse the wind and the roles swap, so the same two banks are scored under a second quadrant).

## Data flow (all exists in code)
`field_schema.validate_observation` (reject, never repair) → write-once intake (existing `field_qa` pattern) → sealed predictions generated from the archive at the observation time (not shown to the observer) → `pair_concordance` and the v2 accuracy metrics after the dataset closes.

## Known gaps before the first session
- The existing blinded-packet tool (`fieldops packet`) is built for the four development lakes; it needs a generic version for any lake with a geometry tier (small work, not done here).
- A simple record entry surface for testers (sheet/app) — Ops or iOS owns presentation; Engine owns the schema.
- Sealed-prediction store location and access rules.
- Decision on who pays for / owns the portable instrument (Michael; nothing purchased).
