# Vegetation Brain — Seasonal Model

**RESEARCH ONLY. Proposed Brain.** Evidence grades follow `VEGETATION_SOURCE_LEDGER.md`: **[V]** opened/fetched, **[S]** search-excerpt, **[L]** literature recall (not re-checked), **[E]** expert estimate/modelling assumption, **[A]** anecdotal. Source notes: `Sector_Research_Data/vegetation-brain/notes/03_*.md`, `03b_verification.md`.

## 1. Answer to the key question
> Can Sector build seasonal vegetation expectations when clouds block the satellite?

**Yes as a labelled fallback, not as an observation.** Timing is predictable from temperature/photoperiod; amplitude is not (it depends on management, grass carp, floods, drought). The honest product is *"Typically X this week (confidence Y), last seen Z days ago"* — never a map of "grass here". Expected performance (exact 4-class weekly agreement) is a **hypothesis [E]**: ≈65–75 % for unmanaged southern reservoirs, ≈40–50 % for herbicide/grass-carp-managed or recently disturbed lakes. It must be back-tested on the Sentinel-2/Landsat history before any claim; that back-test is blocker B-04.

## 2. What drives timing and amount

| Driver | Effect | Grade |
|---|---|---|
| Water temperature / degree-days | EWM photosynthesises from ~10 °C, shoots emerge approaching 15 °C, biomass peaks shortly after June flowering, evergreen where water stays >10 °C | [V] MTRI |
| | Hydrilla germination optimum 15–35 °C; north-Texas ponds keep winter biomass within 50 % of peak; peaks in July and again Oct–Nov; regrowth from crowns/stolons, not tubers | [V] Madsen & Owens 1998 |
| | Water hyacinth: growth >50 °F; doubling in 6–18 days; winter dieback in north FL, year-round in south FL | [V] UF/IFAS |
| | Curlyleaf pondweed: sprouts in fall, first pondweed up in spring, flowers/turions in June, dies back mid-summer | [V] MN DNR |
| Photoperiod | Tuber/turion set under short days; monoecious vs dioecious hydrilla differ | [L] |
| Light/clarity | Sets depth limit (§5) and delays green-up under spring turbidity | [V] Canfield |
| Management | Spraying / grass carp cause step changes. Lake Toho held ~50 % cover with >3,500 ac/yr treatment [S]; Guntersville 1,494 ac treated in 2025 [S]; Lake Conroe: 270,000 diploid grass carp (1981–82) removed all vegetation by Oct 1983 [V] | |
| Disturbance | Okeechobee SAV <3,000 ac (2006) → >46,000 ac (2009) after hurricanes + drought-low stage — non-monotonic with stage; turbidity is the mediator [V] | |
| Ice | Halts growth; curlyleaf survives under ice | [L] |

## 3. Group phenology (generic; shift by region)

| Group | Green-up | Peak | Senescence | Winter state | Grade |
|---|---|---|---|---|---|
| Hydrilla (dioecious, South) | Feb–Apr from overwintering shoots/crowns | Jul and Oct–Nov highs (TX ponds) | frost-kills surface canopy N Gulf / TN valley | ~50–60 % of peak biomass in TX ponds; low *surface* canopy | [V] |
| Hydrilla (monoecious) | Apr–May | Aug–Sep | Oct | dormant to tubers | [L] |
| Eurasian watermilfoil | Mar–May (10–15 °C) | Jun–Aug (post-flower) | late fall | evergreen if water >10 °C | [V]/[S] |
| Curlyleaf pondweed | Fall germination; spring growth | late May–June (Midwest) | mid-summer crash | green under ice; southern: winter peak | [V]/[S] |
| Coontail | Mar–May | Jul–Sep | autumn | often green late | [L] (timing unverified) |
| Chara/stonewort, vallisneria (eelgrass) | spring | Jun–Aug | autumn | low | [L] |
| American lotus, lily, watershield | May | Jul–Sep | Sep–Oct | leaves absent Dec–Apr | [L]/[A] (unverified) |
| Water hyacinth/lettuce/salvinia | year-round in S FL/Gulf | Jul–Oct | frost | frost-browned, regrow | [V] hyacinth; [L] others |
| Cattail/bulrush/phragmites | Apr–May | Jul–Sep | Oct–Nov | **standing dead stems persist** | [L] (unverified) |
| Flooded buttonbush/willow/grass | woody leaf-out Mar–May; grass flush after drawdown + rain | structure year-round | leaf-off Nov | structure persists | [E] |

Important modelling note: winter **emergent stands look dormant to NDVI while still physically blocking boats**, and southern hydrilla keeps substantial biomass below a non-topped surface in winter. Surface visibility ≠ biomass.

## 4. Regional expectation table (dominant canopy group; expert synthesis [E])
Codes: 0 none/dormant · S sparse · M moderate · D dense/topped-out · B brown/senescent · N ice.

| Region | J | F | M | A | M | J | J | A | S | O | N | D |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Gulf (hydrilla/hyacinth/lotus) | S | S | S-M | M | M-D | D | D | D | D | M-D | M | S |
| Southeast reservoir | 0-S | 0-S | S | S-M | M | M-D | D | D | D | M | B | S |
| Mid-South / TN valley | 0 | 0 | S | S-M | M | M-D | D | D | D | M-B | B | 0-S |
| Midwest (CLP, EWM, coontail) | 0 | 0 | S | M | M-D | M | M | M-D | M | S-B | S | 0 |
| Upper Midwest / Great Lakes | N | N | N-0 | S | S-M | M | M-D | D | M | S-B | 0 | N |
| Northeast | N | N | 0 | S | S-M | M | M-D | D | M | B | 0 | N |
| Plains (mostly emergent/flooded grass; SAV turbidity-limited) | 0 | 0 | 0 | S | S-M | M | M | M | M | S | 0 | 0 |
| Mountain West | N | N | N | 0 | S | M | M-D | M-D | M | S | 0 | N |
| Pacific NW | 0 | 0 | S | S | M | M-D | D | D | M | S-B | 0 | 0 |
| California | S | S | S-M | M | M | D | D | D | M-D | M | S | S |
| Southwest | 0 | 0 | S | S | S | M | M | M | S | S | 0 | 0 |
| Alaska | N | N | N | N | 0 | S | M | M | S | 0 | N | N |

**Do not ship these cells.** They are unvalidated expert synthesis; correction from 03b: the Southeast/Mid-South Jan–Feb "0-S" understates hydrilla biomass (surface vs biomass distinction), and hydrilla is bimodal. These cells exist to seed a *learned* climatology from the satellite archive.

Uncertainty [E]: onset ±3–5 weeks year to year; peak ±3–4 weeks; dieback ±2–4 weeks (first frost); peak-cover CV 30–60 % unmanaged, >100 % managed/disturbed.

## 5. Proposed algorithm (draft, for back-test)
1. **Temperature proxy:** Water Temp Brain surface temperature (preferred) or lagged/smoothed air temperature; accumulate GDD10 since the winter minimum.
2. **Group curve** `P_g(t)` = logistic green-up in GDD × logistic senescence triggered by Tw<15–18 °C and photoperiod<12 h; curlyleaf gets an inverted curve (peak at low GDD; crash at Tw>~22 °C).
3. **Lake amplitude** `A_l` = shrunk mean of the lake's own past-summer 90th-percentile cover (from the satellite archive) toward a regional prior; weight by number of clear scenes.
4. **Level/depth modifier** (see `VEGETATION_LEVEL_DEPTH_INTERACTION.md`): shift depth bands by Lake Brain pool anomaly; flag flooded-terrestrial candidates when pool rises >1–2 ft in spring.
5. **Management modifier** `M`: down-weight after recorded spraying/drawdown/grass-carp regime; zero after a documented collapse until a clear observation.
6. **Blend:** prior ∝ `P_g · A_l · L · M`; update with the last clear observation using an exponential decay with half-life ≈14–21 d in growing season, ≈45–60 d in dormant season [E]; cap prior influence when a clear observation <10 d old exists.
7. **Output:** class probabilities, point class, confidence band, reason string ("Seasonal: Southeast hydrilla topped-out period; pool +1.5 ft; last seen 19 d ago"), tier `SEASONAL_EXPECTATION`.

## 6. Back-test plan (blocker B-04)
- Build per-lake weekly surface-reaching state from Sentinel-2 L2A 2017–2025 (cloud-masked) for ~60 stratified lakes.
- Hold out each year in turn (leave-one-year-out). Compare three predictors: (a) week-of-year median, (b) GDD-based, (c) GDD+pool anomaly.
- Metrics: exact-class agreement, within-one-class, Brier score of class probabilities, error by shoulder weeks, error by regime (managed vs unmanaged).
- Pass gate for a seasonal score ≥7: beats naive climatology by a pre-registered margin on managed and unmanaged strata separately.

## 7. Where the evidence is thin
Coontail/lotus/cattail timing, all GDD thresholds, the regional table, Guntersville/Kentucky/Seminole/Toledo Bend pool-vegetation numbers (none found), and any US remote-sensing macrophyte phenology curve (only Baiyangdian, China, found — do not transfer timing).
