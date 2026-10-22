# Sector Engine Navigation Refresh Report
Standards: Rehtac Cortex 2.1.0 @ 0f9ee75 (clean), pack sector/engine
Snapshot compared: sector-engine@7dae705-2026-10-20
Engine repository: Sector-Bowfishing/Sector_Engine · branch cortex/architecture-standardization-2026-10-20 (draft PR #40; origin/main 7dae7051 unchanged) · Date 2026-10-20

Adds to the three earlier 2026-10-20 refresh artifacts; supersedes their Depth/Vegetation rows ("branch only").

## Changes
| # | Snapshot ID affected | Change type | Was (snapshot) | Now (HEAD) | Evidence | Label |
|---|---|---|---|---|---|---|
| 1 | `brain.depth` | RELOCATED | branch `feat/depth-brain-foundation` `jobs/depth-brain/` (not on main) | canonical `brains/depth/` (runtime + candidate knowledge release + research/tools + contracts + Kit V1); branch untouched | `ec5db259` | VERIFIED_IMPLEMENTATION |
| 2 | `brain.vegetation` | RELOCATED | branch `feat/vegetation-brain-foundation` `jobs/vegetation-brain/` | canonical `brains/vegetation/` (same shape; no live writer) | `f5cf9790` | VERIFIED_IMPLEMENTATION |
| 3 | `platform.publisher-shadow` | CONTRACT_CHANGED | Depth/Vegetation identity-only | SHADOW registrations `depth-publication-v1`, `vegetation-publication-v1` | `publisher/registry.py` | VERIFIED_IMPLEMENTATION |
| 4 | `registry.control-manifest` / control plane | CONTRACT_CHANGED (additive) | shadow Brains counted in lake roll-ups | `control.SHADOW_BRAINS/SHADOW_SLOTS`: visible, never scored, never rolled up | `d9653754` | VERIFIED_IMPLEMENTATION |
| 5 | `registry.brain-identity-secondary` | CORRECTION | 6 locked ids; Depth/Vegetation unmigrated | 8 locked ids; `UNMIGRATED = set()` | `stable_brain_ids.json` | VERIFIED_IMPLEMENTATION |
| 6 | `framework.cert-kit-v1` | CERTIFICATION_CHANGED | score assumed | `has_score` spec field; conditional carried-finding mutation | `tools/brain_certification` | VERIFIED_IMPLEMENTATION |
| 7 | `framework.architecture-gates` | CERTIFICATION_CHANGED | — | Swift write-ownership gate; Swift Brain-boundary gate (pinned package surface) | `ede81316` | VERIFIED_IMPLEMENTATION |
| 8 | `ci.github-workflows` | ROUTE_CHANGED | Swift CI macOS only; no image builds | Linux Swift job (swift:6.1-jammy); image-build-verification workflow | `ede81316`, `ab4e4312` | VERIFIED_IMPLEMENTATION |
| 9 | (engineering status) | CONTRACT_CHANGED (additive) | v1.0.0 | v1.1.0: seven status layers, proof results, CI evidence | `ab4e4312` | VERIFIED_IMPLEMENTATION |

## Path verification
All new paths exist at HEAD (`git cat-file -e`), checked during the session.
