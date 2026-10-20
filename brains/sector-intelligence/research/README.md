# Sector Intelligence research (rules only — no data)

Research rules are in [`../BRAIN_OPERATING_CONTRACT.md`](../BRAIN_OPERATING_CONTRACT.md) §8–§12. Intelligence research lives in the private research workspace **`sector-intelligence`** (logical id; the physical root is never recorded in this public repo). Nothing in the runtime reads it.

No research gap register (`GAPS.json`) exists yet: Intelligence's open items are the declared blockers in `runtime/catalog.json` (`declaredBlockers`), reviewed by hand. A gap register is created only when a named research gap is approved; none is invented here.

Never here: research corpora, customer or per-lake private data, species presence (read from the Brain RTDB at run time, never committed).
