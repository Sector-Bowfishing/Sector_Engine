# Explanation model: traceable, no hallucinated prose

## 1. Structure (fixed, five blocks)
```
RESULT      species · zone (or "lake-level") · window · rating · trend
BEST        factors that are FAVORABLE   — "water 74 °F (observed, lake-level)  [water-temp@1.0]"
LIMITING    factors LIMITING/BLOCKING, and gates, with the binding one first
UNKNOWN     factors with no value or beyond a Brain's horizon — "depth: not published"
FRESHNESS   age of each input; STALE flagged                         — "vegetation 14 d old — STALE"
CONFIDENCE  word + the weakest deciding factor + the separate validation line
```
This is the requested BEST / LIMITING / UNKNOWN / FRESHNESS / CONFIDENCE, plus caveats generated from support level.

## 2. Generation rule (what makes it not hallucination)
- Every line is a template over exactly one factor record: `{factor, value, unit, kind, support, age, source@version}`.
- A line cannot be emitted without a record; a record cannot exist without a Brain state. The prototype test `test_R8` asserts every `best/limiting/freshness` line's `factor` and `source` equal an input record.
- Natural-language framing (e.g. "bank is protected from the current wind") is a **lookup keyed on state + factor**, authored once by Sector, reviewed, versioned, and testable. No model writes sentences at runtime. LLM-generated copy is out of scope until a verified-claims layer exists: the claim-checker would itself be the deterministic template layer, making the LLM redundant.
- Unknown is rendered, never omitted. The absence of depth and vegetation today must be visible in every zone answer.

## 3. Example (prototype output, synthetic mixed evidence)
```
WORTH_A_LOOK · confidence LOW
BEST: waterTemp 74 (observed, lake) [waterTemp-brain@t]
BEST: depth 0.8 (modeled, bank_area) [depth-brain@t]
BEST: vegetation 0.5 (observed, bank_area) [vegetation-brain@t]
BEST: wind 2 (forecast, bank_area) [wind-brain@t]
BEST: clarity 6 (measured, bank_area) [clarity-brain@t]
FRESHNESS: vegetation 400 h old — STALE
CONFIDENCE: LOW (weakest deciding factor: depth)
caveats: waterTemp is lake-level, not specific to this zone; would rate START_HERE but the weakest deciding factor is too uncertain to say so
```
(Values and brain names are synthetic fixtures; no Brain published them.)

## 4. Customer-facing compression
Customers get one sentence + two chips, derived from the same record:
- Sentence: top 2 BEST and the binding LIMITING factor, by fixed priority per species.
- Chips: `Confidence: Medium`, `Depth is modeled`.
- Everything else behind "Why".
A bowfisher needs WHERE / WHEN / WHY / CONFIDENCE; forty fields stay behind the audit trail for Ops and support.

## 5. Production gap to close
Today `topReasons` is capped at four strings built in `ConditionsAggregator.reasons`, is not tied to Brain versions, does not list unknowns, and the `whereToLook` cards are generic copy keyed on a few thresholds (generic "cold water: drop to the edges"), not derived from species or zone. Moving to the structure above is mostly a re-shaping of facts the Engine already computes, plus the unknown/freshness blocks.

## 6. Tests to require
1. Traceability: every emitted line resolves to an input record.
2. Completeness: every UNKNOWN deciding factor appears in UNKNOWN.
3. Determinism: same inputs → byte-identical output.
4. No-claim: if a Brain value is absent, the output contains no phrase from that factor's lookup table.
5. Comprehension (user-facing, later): 5 testers explain "why this spot" from the screen without help; target ≥4/5 correct.
