# Water Temperature research (rules only — no data)

Research rules are in [`../BRAIN_OPERATING_CONTRACT.md`](../BRAIN_OPERATING_CONTRACT.md) §8–§12. Research lives in the private research workspace **`water-temperature`** (logical id; the physical root is never recorded in this public repo). The runtime never reads it.

The gap register is [`GAPS.json`](GAPS.json). Its first gap, WATER-VAL-001, is the score blocker *Level-4 protected-truth sufficiency* (`docs/brains/scoring/frozen-scores.json`).

[`docs/brains/water-temp-protected-truth/`](../../../docs/brains/water-temp-protected-truth/) holds the pre-registered protocol for that gate (`PT-L4-2026-11-23`, hashed before any truth value was fetched), the candidate truth sources (public metadata leads only) and a draft Mac mini request. Its runner is `tools/research/water_temp_protected_truth.py`. Truth values never enter this repository.

v1's step A was INSUFFICIENT_TRUTH (Sector_Ops #51, 2026-11-23). [`docs/brains/water-temp-protected-truth-v2/`](../../../docs/brains/water-temp-protected-truth-v2/) holds protocol `PT-L4-2026-11-23-v2`: it reads result depth without the value, replaces short lakes by cast counts only, and fetches only counted casts in step B. Runner: `tools/research/water_temp_protected_truth_v2.py`.

Never here: protected-lake truth data, research candidates' training data, private calibration documents.
