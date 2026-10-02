# Addendum A to PREREGISTRATION_STAGE12.md: the ACOLITE-path harmonisation

Recorded before any ACOLITE-path tandem validation was computed.

**What prompted it (disclosed).** A technical check on one tandem pair (Lake Pontchartrain, 15RYP), with the production
coefficients (which include that pair), showed that the TOA harmonisation does not carry through ACOLITE's dark-spectrum
aerosol step:
- **Aerosol.** ACOLITE's mean AOT(550) was 0.176 on S2A, 0.191 on raw S2C and 0.172 on harmonised S2C.
- **Visible bands.** The harmonised S2C read about 4% brighter than S2A, where raw S2C read about the same.
- **Why.** The aerosol estimate depends on the darkest pixels, which median-based harmonisation does not align.

No held-out pair, and no Secchi, turbidity or chlorophyll value, was looked at.

**Added method, V-ρw.** A per-band linear harmonisation of ACOLITE's own water reflectance:
- **Form:** A = g·C + o, plus the B05 term k·(C_B06 − C_B04), the same form as §2.
- **Fit:** on the BEST-configuration ρw of S2A against raw S2C, over the matched water pixels of the training pairs, with
  equal pair weights and the same trimming.
- **Use:** applied to the held-out pair's raw S2C ρw (leave-one-pair-out).
- **Cost:** no extra ACOLITE run.

**Correction to §2.**
- **V-full cannot be the operational method.** It removes the commissioning visible gain, which operational S2C may not
  carry.
- **The operational ACOLITE-path method** is whichever of V-op and V-ρw has the lower held-out mean flip rate on the
  ACOLITE-path P2 route; ties within 0.5 points go to V-ρw.
- **The S2C HARMONIZED ACOLITE-path condition and the §2 platform-invariance condition (a)** are judged on the adopted
  method.
- **V-full is still reported,** as the emulation of fully calibrated operational data.

**Caveat, stated for every method.** The only public tandem is the commissioning one. Any visible-band correction derived
from it may not apply to operational S2C.
