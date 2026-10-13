# Vegetation Brain — Lake Level and Depth Interaction

**RESEARCH ONLY. Proposed Brain.** Vegetation consumes Lake Brain level state and (future) Depth Brain depth; it does **not** compute or republish either. Grades as in the Source Ledger: **[V]** verified, **[S]** search-excerpt, **[L]** recall, **[E]** estimate, **[A]** anecdotal.

## 1. Interfaces (who owns what)

| Input | Owner | Used for | Vegetation must NOT |
|---|---|---|---|
| `poolAnomalyFt` (current vs full/normal pool), trend, basis, confidence | Lake Brain | shift depth bands, flag flooded shoreline / stranded flats | recompute pool level or invent a pool basis |
| `effectiveDepthFt` per cell, shallow zones, littoral area | Depth Brain (future) | potential-SAV bands, accessibility | estimate depth; until Depth exists use only modelled `shallow_frac` flagged `MODELLED` |
| Secchi / clarity class + confidence | Water Clarity Brain | detectability confidence, potential-SAV depth limit | invent clarity |
| Water temperature / GDD | Water Temp Brain | seasonal curve | — |

Lake Brain readiness matters: the fleet has 425 full-pool rows and 621 lakes, and pool basis confidence varies (`high`/`low`). Vegetation must pass Lake Brain's `confidence` through to its own level-dependent outputs.

## 2. What lake level does to vegetation (verified vs expected)

| Pool change | Flooded terrestrial / shoreline grass | Emergent | Submerged | Access for boats/bowfishing | Grade |
|---|---|---|---|---|---|
| **Rising +1 to +3 ft** (spring) | Grass/shrub on flat shorelines flooded; large horizontal gain (a 2 ft rise on a 1:50 slope moves the shoreline ≈100 ft); stays green 2–6 weeks then decays [E] | partly submerged, new lanes | shallow SAV deeper → less light if turbid | more shallow reach; snaggy | [E]/[L] |
| **High pool +5 ft or more** | brush/timber flooded | emergents drown if inundated well above stems for long periods; floating-leaved tolerate 3–5 ft [E] | zone shifts shoreward; **multi-year high water + turbidity can collapse SAV** (Okeechobee after 2004–05 hurricanes) | stump/fence hazards | [V] Okeechobee, [E] rest |
| **Low −1 to −3 ft** | shoreline grass exposed/dying; new moist-soil annuals on mud flats, re-flooded later | stranded or colonising downslope | rooted SAV in 0–1.5 ft stranded; deeper SAV gets more light (topped-out canopies) | flats unreachable; fish concentrate on bed edges | [E]/[L] |
| **Drawdown −5 ft or more** | large exposed area; terrestrial plants establish in 4–12 weeks [E] | expands downslope | SAV confined below waterline; winter drawdown controls EWM only with deep freeze; **hydrilla tubers not reliably killed** (north-Texas reservoir 12-month drawdown) | ramps unusable | [S]/[L] |

Verified anchors: **Sam Rayburn** pool fluctuates ~6–7 ft/yr; dominant plants hydrilla and American lotus; "drastic water level changes can decrease the amount of vegetation"; high water floods trees/bushes [V] (TPWD). **Okeechobee** SAV <3,000 ac (2006) → >46,000 ac (2009) under drought/low stage, then declined again — stage→SAV is **non-monotonic**, mediated by light/turbidity [V]. **Lake Conroe** hydrilla eliminated by grass carp 1981–83 regardless of level [V]. No quantitative pool-elevation vs coverage study was found for Guntersville, Kentucky Lake, Seminole, Toledo Bend or Missouri reservoirs (blocker B-09) — treat level effects as hypotheses.

## 3. Depth interaction: maximum colonisation depth

Verified model (Canfield et al. 1985, 108 lakes in Finland/Florida/Wisconsin):
- Pooled: `log10(MDC) = 0.61·log10(SD) + 0.26` (m); r² = 0.56; **95 % CI 46–236 % of the predicted MDC** — a soft prior only.
- Florida: `log10(MDC) = 0.42·log10(SD) + 0.41` (r² 0.71, n=26).
- Chambers & Kalff 1985 (angiosperms): `Zc^0.5 = 1.33·log10(D) + 1.40` — from an abstract excerpt, verify before use.
- Computed: Canfield pooled MDC for SD 0.5/1/2/3 m = 1.2/1.8/2.8/3.5 m; Florida 1.9/2.6/3.5/4.2 m. Zmax/Secchi **falls** as water clears (≈2–3.8× in turbid, ≈1.2–1.8× at SD 2–3 m) — the earlier "1–2.5× Secchi" rule was corrected.
- Hydrilla grows to depths receiving ~0.5–1.2 % of surface light in several FL lakes; the model underestimates in very clear water.

**Use in product:** `POTENTIAL_HABITAT` depth ceiling = Canfield (regionally selected), with the CI carried as confidence; never an observation.

## 4. Vegetation likelihood by depth band (hypothesis [E], for calibration)
Probability that macrophyte cover >10 % in the band at peak season:

| Band | Clear | Stained | Turbid |
|---|---|---|---|
| 0–1 ft | 0.6 (emergent/floating dominant; SAV limited by wave, ice, desiccation) | 0.6 | 0.4 |
| 1–3 ft | 0.8 | 0.7 | 0.3 |
| 3–6 ft | 0.8 | 0.6 | 0.1 |
| 6–10 ft | 0.6 | 0.25 | ~0.02 |
| >10 ft | 0.1–0.3 | ~0.02 | ~0 |

These are **calibrate-me** numbers: fit them against the 80-lake NLA/FWC overlap and the GloBathy-derived shallow fraction once Depth Brain delivers bands. Note the peak vegetation band (≈1–6 ft) coincides with the bowfishing band, so Depth is the single biggest lever on vegetation *potential*.

## 5. Accessibility (the bowfishing question)
- **Accessible-water denominator:** compute cover and density over the 0–8 ft band (Depth Brain) rather than the lake, otherwise whole-lake PAC understates dense shallow cover (FWC PAC vs PVI gap illustrates this).
- **Density and travel:** no quantitative source exists linking cover to boat passage or arrow deflection (only anecdote and MN DNR "dense mats… inhibit water recreationists"). The `DENSE` class is therefore labelled "likely hard to move through" [A], with the cutoff in the scheme tag until field-validated by users.
- **Level and access:** at pool anomalies below roughly −2 to −3 ft shallow vegetated flats may be unreachable by boat (Sam Rayburn-type 6–7 ft swings) [E]; that is an *access flag*, not a vegetation property — compute it in Intelligence from Lake/Depth/Vegetation, not inside Vegetation.

## 6. Output contract fragments
```
levelContext: { poolAnomalyFt, poolTrend7dFt, basis, confidence, source:"lake-brain", asOf }
floodedShorelineCandidate: { areaFraction, rule:"anomaly>+1ft & land-cover grass/shrub within contour", tier:"POTENTIAL_HABITAT" }
strandedShallowRisk: { flag, rule:"anomaly<-2ft & cells depth<=anomaly" }
potentialSAV: { maxDepthFt, ciLowFt, ciHighFt, clarityInput{secchiM, confidence}, model:"canfield-1985-FL|pooled" }
```
All carry the confidence of the weakest upstream input.
