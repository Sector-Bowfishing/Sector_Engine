# Current Clarity candidate — frozen research (Stages 10–18)

The research behind the **uncertified** Current Clarity candidate, preserved from the session scratchpad (where macOS's
`/private/tmp` cleanup had already deleted part of it once). Nothing here is used by the production engine.

| | |
|---|---|
| **Baseline** | Stage 16: frozen C-gbm (`stage14/engine`) + posterior reliability gate (`stage16/engine/rule16.json`, 0.70 / 0.70), tier 2 boundary-only, Sentinel-2C lower authority, algal modifier |
| **Challenger** | Stage 17: inverse-uncertainty weighting of frozen scene predictions over ±10 days, no rain rule, S2C off (`stage18/engine/challenger17.json`) |
| **Development** | operational 7/10 (0.693), harmful 10.6%, severe 1.5% (Stage 16); challenger 0.743 / 11.6% (Stage 17) |
| **Certification** | none passed. Readiness stays 2/10 as deployed. Every blind pool so far is spent (Stage 14 set, sealed WQP tier, P2 fresh pool) |
| **Frozen** | 2026-10-02T04:13:27Z (`stage18/FREEZE_STAGE18.json`) |

## Rules that travel with this directory

- **Uncertified.** Any product built from it says so.
- **Field observations are scoring-only.** Michael's clarity reports, the Stage 8 field-survey form and the Guntersville
  survey (`stage10` targets) are never used to fit, tune or select anything. They may only score a frozen engine.
- **Frozen means frozen.** No refit, no threshold change, no new feature. A change is a new stage with its own
  pre-registration.

## Reproduce

```bash
cd research/clarity-candidate
PYTHON=python3.12 env/bootstrap.sh          # needs Python 3.12.8 and gcloud (for the LUT backup); ~2.5 GB
geo/bin/python golden/golden_test.py all    # ~4 min; downloads six Sentinel-2 L1C products
```

`env/bootstrap.sh` rebuilds, inside this directory and gitignored:
- `geo/` from `env/requirements-geo.txt`;
- the ACOLITE venv from `env/requirements-acolite.txt`;
- ACOLITE itself at commit `f73cbe7` (20260421.0). Its 269 LUT files (1.89 GB) are pinned by sha256 in
  `env/acolite.lock.json`, because ACOLITE's own LUT source is a moving branch.

`env/verify_env.py` checks the result. The LUT backup is `gs://sector-clarity-candidate/acolite/f73cbe7/` (private).

**The golden test** compares against outputs written at freeze time, never against a fresh run of itself:

| Check | What must hold |
|---|---|
| `hashes` | 134 frozen files match their freeze-time sha256 |
| `models` | `dev14.py`, `dev15.py`, `dev16.py` and `freeze18.py` regenerate their frozen outputs byte for byte (including `semantics15.json`, `rule16.json`, `challenger17.json`); a C-gbm refit reproduces `frozen_gbm.pkl` (max \|difference\| 0 over 1,397 rows) |
| `selfcheck` | engine14 on all 1,574 Stage 14 certification rows and engine16 on all 108 Stage 16 fresh rows, from stored raw inputs, give every output field unchanged; `N:t15769` → p = 0.7750620848927173 (Normal, 5.957 ft) |
| `scenes` | the six development validation scenes through the frozen ACOLITE path reproduce `stage14/cert/validate_res` (264 values, max \|difference\| 0) |

`golden/challenger17_fixtures.json` holds the frozen `dev17.py` challenger's outputs on every development event (made by
`golden/make_challenger_fixtures.py`). Any port of the challenger must reproduce them exactly.

**First pass:** 2026-10-02, on macOS arm64 with a freshly bootstrapped environment. `provenance/GOLDEN_RESULT_macos.json`.

## What changed when it moved here

**Paths only.** Scripts hard-coded the scratchpad path. Three byte-level rewrites (`provenance/FROZEN_HASH_CHECK.json`,
`rules_in_order`) point them at `$CLARITY_RESEARCH_ROOT`, and engine files imported from the `Sector_Engine-fusion`
worktree at `vendor/Sector_Engine-fusion` (`feat/clarity-algal-warning` @ 0393791).
- `provenance/PATH_REWRITES.json` lists the 84 rewritten files.
- The `hashes` check undoes the rewrite before hashing.

**Freeze-hash status** (`provenance/FROZEN_HASH_CHECK.json`):
- 135 entries match.
- 3 are hashes of lists, not files.
- 1 is `dev17.py`'s pre-analysis hash. It was corrected during Stage 17 (the M-agree state bug); the final version is
  frozen in Stage 18.

**Not in git:**
- `stage11/ac` (15 GB of Stage 11 ACOLITE NetCDFs; regenerable);
- the raw WQP pulls (`q9/wqp/raw`);
- C2RCC and POLYMER (`stage11/tools`; POLYMER's licence is Michael's call);
- the Stage 10 survey map tiles.

All of these are in `gs://sector-clarity-candidate/research-archive/` (private), except the 15 GB.

## Layout

- `stage6`–`stage18`: as in the scratchpad.
- `q9`: the WQP eligible files frozen in Stage 14.
- `vendor/`: the engine files the research imported.
- `env/`: environment pins.
- `golden/`: the golden test.
- `provenance/`: hashes and the rewrite record.
