# Water Temperature research (rules only — no data)

Research rules are in [`../BRAIN_OPERATING_CONTRACT.md`](../BRAIN_OPERATING_CONTRACT.md) §8–§12. Research lives in the private research workspace **`water-temperature`** (logical id; the physical root is never recorded in this public repo). The runtime never reads it.

The gap register is [`GAPS.json`](GAPS.json). Its first gap, WATER-VAL-001, is the score blocker *Level-4 protected-truth sufficiency* (`docs/brains/scoring/frozen-scores.json`).

[`docs/brains/water-temp-protected-truth/`](../../../docs/brains/water-temp-protected-truth/) holds the pre-registered protocol for that gate (`PT-L4-2026-11-23`, hashed before any truth value was fetched), the candidate truth sources (public metadata leads only) and a draft Mac mini request. Its runner is `tools/research/water_temp_protected_truth.py`. Truth values never enter this repository.

v1's step A was INSUFFICIENT_TRUTH (Sector_Ops #51, 2026-11-23). The current protocol is `PT-L4-2026-11-23-v6` in [`docs/brains/water-temp-protected-truth-v6/`](../../../docs/brains/water-temp-protected-truth-v6/): it reads result depth without the value, replaces short lakes by cast counts only, counts unknowns against the model, and fetches only counted casts in step B. Every run is bound to the shared Engine run ledger (`tools/research/protocol_run_ledger.py`) in this Brain's research folder, anchored by a public `Run anchor:` on Sector_Ops #51. v2 to v5 were superseded before they ran. Runner: `tools/research/water_temp_protected_truth_v6.py`.

Never here: protected-lake truth data, research candidates' training data, private calibration documents.
