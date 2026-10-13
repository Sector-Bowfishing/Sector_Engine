# iOS Guntersville IENC figures: correction request (iOS NOT edited)

Repository audited read-only: `/Users/mcather/Desktop/Development/iOS/sector-intel-phase3` (HEAD `7ef2e02a`, branch `research/sector-intelligence-phase3-buffalo`). Evidence: `DEPTH_GUNTERSVILLE_IENC_AUDIT.md` (this folder; asset counted from `Sector/Assets.xcassets/FishIntel/GuntersvilleSegmentGeometry.dataset/Guntersville.segments.geojson.gz`, 6,504 segments of 200 m).

## 1. The numbers

| Quantity | Wrong value in the iOS repo | Audited value | Basis |
|---|---|---|---|
| Segments with a depth class | "62%" | **67.2%** (4,371 of 6,504) | `depthStatus = classified`: 4,059 `shallow` + 312 `deep` |
| Segments with no charted depth | "2,445 unmeasured" | **2,133 (32.8%)** | `depthStatus = unavailable` (421.5 of 1,292 km of shoreline) |
| Charted share of the lake *area* | (not stated) | 82.3% (17.7% = 47.1 km2 uncharted) | polygon overlay (IENC audit) |

`2,445` is not a depth-coverage figure: it is the count of fixed-buffer littoral polygons (`littoralBoundary = fixedBuffer`). The iOS repo itself already contains the right numbers in older handoffs (`PHASE_1_3_VALIDATION_HANDOFF.md:140` "4,371 (67.2%)", `PHASE_4:315`, `PHASE_6:183` "No charted depth 2,133 / 33%", `PHASE_9:172` `.partial(coveragePct: 67.2)`), so the repo contradicts itself.

**Not wrong, a different quantity:** `habitatUnknown` = 2,487 of 6,504 (38%) in `PHASE_9:692`, `LakeRegistry.swift:306`, `FISH_INTELLIGENCE_BETA_READINESS.md:77`. That counts segments where the Fish Intelligence habitat answer is unknown for any reason (it includes more than missing depth). Keep it, but stop attributing it solely to the depth survey or equating it with 100 - depth coverage.

## 2. Where the wrong figures are (exact follow-up list for the iOS repo)

| File | Line | Current text | Replace with |
|---|---|---|---|
| `Sector/FishIntel/Lake/LakeRegistry.swift` | ~185 | `note: "2,445 of 6,504 segments are unmeasured ..."` | `2,133 of 6,504 segments (32.8%) have no charted depth and are reported as ...` |
| `Sector/FishIntel/Lake/LakeOnboarding.swift` | ~100 | "... IENC 9 ft contour covering 62%." | "... covering 67.2% of segments (82.3% of the lake area)." |
| `Sector/FishIntel/Lake/LayerCapabilityGate.swift` | 24-25, 109 | "Depth at Guntersville is 62% ... says 62%" | 67.2% (comments; check the runtime `coveragePct` is read from the asset, not typed) |
| `Sector/FishIntel/Lake/LakeCapability.swift` | 26 | "covering 62% of the shoreline" | 67.2% |
| `FISH_INTELLIGENCE_BETA_READINESS.md` | 77-92 | "covering 62% of segments", "The other 2,445 are unmeasured" | 67.2% / 2,133; keep the 38% habitatUnknown line but explain it is a different quantity |
| `PHASE_12_VALIDATION_HANDOFF.md` | 50, 204 | "62%" | 67.2% (or leave history and add a correction note) |

Before editing, grep the app for the literal `62` near `depth`/`coveragePct` and confirm which value the UI actually shows (the PHASE_9 notes say the sheet prints "Covers 67% of the shoreline"). A single source of truth should compute coverage from the asset at build time; add a unit test that asserts `classified + unavailable == 6504` and the printed percentage equals `classified / 6504`.

## 3. Semantics that must travel with the number (from the audit)

* **Datum:** the IENC depths reference "local low water" (S-57 datum code 31); **no pool elevation is encoded**. The contour cannot be level-adjusted. Do not describe it as "9 ft below normal pool".
* **The "shallow" polygon is a residual**, not a measured shallow zone: the 0-2.74 m polygon is shore-to-contour water that is shallower **or not surveyed**. A segment classed `shallow` means "inside the charted 9 ft line", not "measured 0-9 ft".
* **Survey age:** 2007 (shallow-side polygons) and 2008 (deep polygons), ZOC B (about +/-50 m horizontal, +/-1.05 m vertical at 9 ft). The `Source_Date` of the footprint layer (2021/2023) is a compile date, not a survey year.
* **Gaps** are mostly tributary arms (mainstem 0.6% unavailable, large arms 47%, minor creeks 32%); the reason (embayments not compiled) is inferred from where gaps fall, not stated by USACE.
* The fleet overlap CSV in the research branch (`ienc_fleet_overlap.csv`, `Source_Date` 20210210;20230321) must not be read as survey years either.

## 4. Why this matters for Depth Brain

Depth treats the Guntersville IENC contour as **PARTIAL measured contour evidence, tier C-limited** (no zones, no level adjustment). A wrong 62% / 2,445 in a customer-visible sheet would understate measured coverage while the "unmeasured" label would overstate it; neither matches the data. No Depth code reads the iOS figures.
