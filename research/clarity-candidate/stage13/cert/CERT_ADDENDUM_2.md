# Certification protocol, addendum 2 (Stage 13): expanding the blind set

This extends `stage12/cert/CERT_PROTOCOL_STAGE12.md` and its addenda B/B2. Everything not changed here stays as it was.
No Secchi value is fetched.

**1. SYKE, the whole eligible pool.**
- **Lakes.** Every lake with an eligible event under the Stage 12 bulk rules (lake site, April–November, 2017-04-01 to
  2025-11-30, no ice record), not only the first 400.
- **Events per lake:**
  - every eligible cool-season event (April, October, November), up to 3;
  - plus up to 3 warm-season events in distinct months where possible;
  - seed 20261002.

**2. Metadata prescreen (value-blind).**
- **The rule.** An event goes to the extractor only if a STAC search finds an item within ±1 day with
  `eo:cloud_cover ≤ 60%`, in the addendum B/B2 collections.
- **Why.** It only drops events unlikely to pass the production gates. It can lose matches, but it cannot select on
  clarity.

**3. Matching.** The extractor rules are unchanged, as are addenda B/B2.

**4. The per-lake cap,** 3 matched observations, is filled cool-season first, then warm, in seeded order.

**5. Other sources.** No other source is added unless it is anonymous, keeps sites and visits separate from values, and
is independent of development.
- **None was identified besides SYKE.** NLA 2017 and 2022 are already used in full.
- **The "downloaded in Stage 1, never analysed" WQP tier is not used without Michael's approval.**

**6. Readiness.** The Stage 12 rule is unchanged: the US core carries the verdicts, and SYKE counts toward the total and
the cool season.
