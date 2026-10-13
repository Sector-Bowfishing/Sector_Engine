# Vegetation Brain — Submerged Vegetation Research

**RESEARCH ONLY. Proposed Brain.** This is the hardest and most valuable class for bowfishing (fish cover under the surface). The honest answer is: **satellites do not reliably observe it at fleet scale; a model-based "potential" product plus targeted ground truth is the credible path.**

## 1. Direct answer: at what clarity/depth can submerged vegetation be detected?

| Evidence | Result |
|---|---|
| **Empirical, this campaign (PNW polygons)** | Submerged assemblages: best shore-matched AUC 0.77 (NDAVI), best-threshold F1 0.74 against a 0.667 no-skill baseline. Much of the apparent skill comes from mixed polygons containing floating-leaf/emergent species. |
| **Empirical, this campaign (FL points, presence-only)** | Submersed-only points: best AUC 0.68 (FAI); below chance (AUC <0.5) at several depths; Sector rule recall **4.5 %**; recall falls with depth (9.6 % at 0.6–1.2 m → 0.5 % at >3 m). A multi-band learned model did not rescue it (FL AUC 0.41–0.79, most lakes at chance). |
| **Literature** | Point-validated submerged accuracy 59 % (4 Chinese lakes, Sentinel-2, deep learning) [V]; one WASI-2D study at Secchi 4.2 m reliable to ~2.5 m [V]; multispectral cannot separate species [V]. |
| **Physics** | NIR (used by NDVI/NDAVI/FAI) is absorbed within ~10–15 cm; only blue/green/red reach the bottom; signal ∝ exp(−2·Kd·z) [B] |

| **Empirical, note 05 (lake-level sonar)** | FWC sonar PVI/PAC (130 lake-years): the rule+S2 tracks biovolume ρ≈0.43 but only where beds reach ≳40 % of the water column; sees essentially none of the submersed-only cells (cell vote 3–8 %). |
| **Clarity does not rescue it (note 05)** | Secchi from WQP: S2–sonar agreement ρ is 0.78 / 0.63 / 0.26 / 0.11 across Secchi <0.5 / 0.5–1 / 1–2 / ≥2 m. Clear Florida lakes carry their sonar volume as *deep* submerged beds that never reach the surface; the agreement in turbid lakes reflects surface-reaching vegetation. Proxy quality low (n=7 original lakes; confounded with vegetation type). |
| **Pixel-level truth unavailable** | FWC BioVolume ImageServers 2015–2023 are listed but hang on every request; a Carver County MN sonar pilot (Reitz Lake) was inconclusive (AUC ≈0.5, survey date unknown). |

**Working conclusion (planning prior [U], not a measured result):** with Sentinel-2, observed submerged vegetation is plausible only when all hold: (a) clear water (Secchi ≳ 2–3 m), (b) depth ≲ 1–1.5× Secchi and ≲ ~2 m, (c) canopy-forming or bright-contrast bed, (d) calm, low-glint scene, (e) per-lake calibration against survey/sonar. Outside that envelope, claim nothing observed.

Clarity-by-depth planning table (unvalidated):

| Secchi | Depth to bottom | Canopy-forming SAV | Low-growing SAV |
|---|---|---|---|
| >3 m | 0–1.5 m | Good (planning 80–90 %) | Fair-good |
| >3 m | 1.5–3 m | Fair | Poor |
| 1–3 m | 0–1 m | Fair-good | Fair |
| 1–3 m | >2 m | Only topped-out | Not detectable |
| <1 m | any | Only surface-reaching canopy | Not detectable |

## 2. What limits submerged detection (and which Brain supplies the input)

| Limit | Effect | Input owner |
|---|---|---|
| Water clarity (Kd, CDOM, chl, TSS) | caps detectable depth; tannin kills blue band | Water Clarity Brain (must supply Secchi + confidence; Vegetation must not invent it) |
| Depth | bottom signal decays with depth | Depth Brain |
| Bottom reflectance | dark muck hides dark plants; bright sand improves contrast; periphyton mimics SAV | substrate data (none yet) |
| Sun angle / glint / wind | adds noise to dark water | Wind Brain, scene geometry |
| Mixed 10 m pixels | beds smaller than 10 m or in narrow arms are lost | polygons |
| Atmospheric correction | large errors over inland water in red/NIR | processing choice (Polymer/C2RCC vs Sen2Cor) |
| Algal bloom vs plant | both high NIR/FAI | phenology + red-edge |
| Drawdown / water-level change | moves vegetation zone; timing mismatch with survey | Lake Brain |

## 3. The credible product: `POTENTIAL_HABITAT` plus observation where it works

1. **Potential-SAV zone** (modelled, tier `POTENTIAL_HABITAT`):
   `P(SAV | cell) = f(depth ≤ Zmax(Secchi), season, region/species group, substrate, wave exposure, lake history)`
   - Zmax from Canfield et al. 1985: pooled `log MDC = 0.61·log SD + 0.26`, Florida `0.42·log SD + 0.41`; pooled 95 % CI is 46–236 % of the prediction [V]. So the output is a probability band, not a line.
   - Historical persistence: surface-reaching detections over 3–5 summers (hydrilla/milfoil beds often recur in the same cells) raise `P` and reveal where beds top out.
   - **Never** labelled "observed submerged".
2. **Observed topped-out submerged**: when a SAV canopy reaches the surface it behaves as a surface-reaching mat (`surfaceTopped:true`), detectable (AUC ≈0.98 for floating-leaf beds in clear water; FL lower). Report as `SUBMERGED surfaceTopped` only when species context supports it (e.g., survey or season), otherwise as generic `FLOATING/MAT`.
3. **Observed deep submerged**: only via sonar (FWC BioVolume rasters exist for FL; crowd/consumer sonar for the rest) or agency survey — treated as `OBSERVED_SURVEY`.
4. **Edge and structure hints**: class boundaries between mats and open water are visible and are valuable bowfishing structure regardless of what lies below (fish hold at weed edges [A]).

## 4. Why not just train a model?
The leave-one-lake-out gradient-boosted model did not generalise for submerged (many lakes at chance) even with 12 spectral features; the labels are mixed and presence-only; and there is no fleet-wide clarity covariate. A model could work *inside* a single lake with abundant dated sonar/survey labels (FWC Biovolume), which supports a **per-lake calibrated** layer for a few dozen lakes, not a fleet-wide one.

## 5. Experiments needed (ranked)
1. **Sonar-truth test at pixel level** — the FWC BioVolume rasters hung (see note 05); obtain them from FWC directly (or via the BioBase/WHOML team), or collect other lake-scale sonar rasters (NYSDEC Niagara, Minnesota county sonar points). Lake-level result already in hand: S2 sees beds above ≈40 % canopy/water-column ratio.
2. **Depth-invariant indices** (Lyzenga green/blue, green/red) on clear shallow lakes with polygon truth (Snohomish) — expected modest gain, untested.
3. **Clarity-stratified detectability** — needs Secchi per lake/date (Clarity Brain output, FL LAKEWATCH, NLA secchi fields).
4. **Persistence-based potential** — does 3–5 yr surface-detection history predict beds below the surface in later years (use FWC LTM repeat surveys 2015–2023)?
5. **UAV/hyperspectral calibration lakes** — only for method validation, not production.

## 6. What Sector can honestly say today
- "Submerged vegetation likely along the 2–8 ft shelf in clear water" → `POTENTIAL_HABITAT`, labelled modelled, with confidence from clarity and depth inputs.
- "Surface-topped weed mats visible on this date at these cells" → `OBSERVED_SATELLITE`.
- Never: "grass here" from NDVI alone for non-topped submerged beds.
