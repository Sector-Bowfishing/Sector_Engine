# Wind Brain — next implementation plan (proposal; nothing here is built or approved)

Ordered by bowfishing value per effort. Each item stays inside the Wind Brain and keeps Unknown honest.

1. **Add the tonight block to WindState** (small): from-direction compass (shown only if forecast ≥ 5 mph), strength class, **breezy-risk flag from NBM P90** (data already archived at 00/06/12/18Z), trend easing/steady (suppress rising/"lay-down"), a plain-word confidence. Pre-register the H2 re-test (V1–V7 definitions already written in `WIND_RESEARCH_PREREG.md`) so it can be scored the day H2 opens (2027-01-01).
2. **Publish per-bank exposure with a vocabulary** (small–medium): label each bank DIRECT / CROSS / PROTECTED + HIGH FETCH tag at mean and P90 speed; the engine already computes ranks for 4 lakes + 70 tables, add facing bearing (anchor→standoff already in the tables) and the α rule. Must always be shown with the "modelled, not field-validated" qualifier.
3. **Fleet tier** (medium): productionise polygon fetch from Lake Brain polygons as an `ESTIMATED` tier for ~544 lakes (HIGH/MEDIUM confidence), with SHA-pinned outputs; keep the audited tier separate. First fix the G2 gap: a matched per-bank comparison on a **shared polygon** (rasterise the same NHD polygon with both implementations) before claiming parity; add the 4 failing geometry types.
4. **Move NBM sampling to all 621 lake points** (medium): one CONUS pull per cycle sampled at each lake (plus AK/HI domains), replacing the 4-lake cut-outs, so forecast/direction/trend exist everywhere. Validate per region at the existing 8 stations only for CONUS-east; flag other regions "unvalidated region".
5. **Shelter factor study** (research, medium): upwind land-cover/canopy within 200 m to reduce the texture floor for coves; pre-register; validate only when the bank network produces truth.
6. **Production decision (Michael):** serve NBM wind from the Engine so customers see the Brain's wind; fixes direction (0.62 → 0.72–0.76), calm-night bias (+1.13 → +0.14) and the free-tier dependence.
7. **Hardware (Michael):** one on-lake anemometer at Guntersville (over-water truth + nowcast) → then the two-lake bank network. These are the only paths to certification 5+.
8. **Rubric review (Michael + independent reviewer):** consider probabilistic event scoring, night/speed-weighted direction, so bowfishing-relevant skill registers. No change made here.

Do not do: more provider shopping, WindNinja, per-point wind fields, wave-height-to-the-inch claims, GLMP/LAMP rebuild before the ordinary-decision pre-registration is approved.
