# Depth Brain Cross-Brain Opportunities

Research only. No other Brain is edited. Each item lists what Depth supplies, the evidence that it would help, and the guardrail.

| Brain | Depth supplies | Value | Guardrail |
|---|---|---|---|
| **Lake Brain** | Nothing back; consumes `differenceFromNormalPoolFt` and `fullPoolFt`. Provides acres-per-ft (3DEP proxy, 85 % within x2 of CWMS truth, n=33) as a candidate Lake Brain context field. | Level interpretation becomes habitat interpretation (a 3 ft drop on Guntersville moves about 14,700 acres of waterline) | Lake Brain keeps ownership of level; Depth only reads |
| **Water Temp** | Mean depth class and shallow-area share per lake | Shallow water heats/cools faster; Water Temp already uses a modeled mean depth with x1.5-x2.4 error (`depth_proxy_candidates.csv`). Contour-derived mean depth for Tier A/B lakes would replace the proxy for those lakes; a drawdown shift changes thermal volume | Do not feed modeled Dmax into stratification; GLOBathy fails at both ends (3.6x too deep for <8 m lakes, 0.51x for >40 m) |
| **Water Clarity** | Shallow-zone mask and effective depth over flats | Wind resuspension is shallow-water; bottom reflectance bias over 0-3 ft; a flat that dries or floods changes turbidity. `grassPct` already measures vegetated shallows; Depth gives the denominator | Clarity keeps `grassPct`; Depth does not rebuild satellite grass |
| **Vegetation** (inside Clarity today) | Depth limit for submerged vegetation (light-limited, roughly <6-10 ft in clear water) | Convert "vegetation share" to "vegetation share of shootable water" | Needs Tier A/B depth; skip elsewhere |
| **Biological Brain** | Nothing; supplies preferred depth bands per species and season (e.g. spawning band 1.2-6.1 m) | Fish-depth matching needs the Depth zones | Depth never encodes preference |
| **Sector Intelligence** | `effectiveDepthState`, zone shares, `unknown` reasons | Overlap of fish preference and current effective depth: "the 2-5 ft flats carp use are 38 % smaller than normal; shoreline moved out 400 ft" | Intelligence must treat `shiftOnly` as a delta and `unknown` as missing, mirroring the FishIntel `unmeasured` rule |
| **FishIntel (iOS/Android)** | Replace the single 2007 IENC 9 ft binary (Guntersville, 67 % segment coverage) with zone classes where Tier A/B exists; fill the 33 % unmeasured with shift-aware status | Fixes the "38 % habitatUnknown" beta-readiness item | Client contract unchanged: unmeasured → factor dropped |

## Highest-leverage hand-offs
1. Effective-depth shift to Intelligence (175 lakes usable now).
2. Tier A/B zone shares to Water Temp for the lakes where its mean-depth proxy is poor.
3. Acres-per-foot into Lake Brain's flood/drawdown narrative.
