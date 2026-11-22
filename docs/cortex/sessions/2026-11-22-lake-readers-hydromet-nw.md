# Session record: Lake Brain readers for the Pacific Northwest and Great Plains (Hydromet, NWRFC, CWMS NWDP / NWDM)

Standards: Rehtac Cortex pack sector/engine (pin ecaef70). Date: 2026-11-22. Branch: `feat/lake-readers-hydromet-nw-2026-11-22` (off main 669d4928; main merged after #219). PR #220.

## Scope
Owner decision (Michael, chat 2026-11-22): build Lake Brain level readers for lakes that passed the binding checks but need a reader the Engine does not have. This session: Reclamation Hydromet (PN and GP), NWRFC observed pool elevation, USACE Northwestern Division CWMS offices NWDP / NWDM. Owner source-access rule (Michael, chat 2026-11-22 08:00Z; Sector_Ops #51 comment 7076252747), quoted in `docs/brains/LAKE_BRAIN_PROVIDERS.md` section 7. No binding, no deploy, no rules or IAM change.

## Done
- CWMS NWDP / NWDM: no reader change needed. The CWMS reader passes the binding's office to the CDA unchanged; 23 accepted lakes bind NWDM and 7 bind NWDP (primary or fallback, from `bindings.proposed.v1.json` and `accepted_batch.json`). Test `brains/lake/tests/swift/LakeBrainCWMSDivisionOfficeTests.swift` (fake transport, no network).
- Reclamation Hydromet: not built. usbr.gov robots.txt disallows `/pn-bin` and `/gp-bin`; under the owner rule it needs Reclamation's permission first. A reader written before the rule was applied is parked, unmerged, on `parked/lake-hydromet-reader-2026-11-22` (fixtures assembled from documentation, not recorded).
- NWRFC: not built (robots.txt unreadable, no documented API, one probe returned another station's table; the same DCP data is read through NWPS / HADS).
- `LAKE_BRAIN_PROVIDERS.md` section 7: the rule, the findings, the robots.txt quotes and the Hydromet endpoint research.

## Verification
Python suites `brains/lake`, `tools/architecture`, `jobs/brain_platform`, `tools/brain_certification`, `tools/ops/tests`, `jobs/lake-brain` pass locally; Swift tests run in CI (macOS and Linux). Engineering-status digests regenerated on the merged tree.

## Decisions for Michael
- GP Hydromet publishes an automated-retrieval guide (`www.usbr.gov/gp/hydromet/automated_retrieval.pdf`) while robots.txt disallows `/gp-bin`: edge case, owner decides whether that guide counts as permission for GP.
- Lake Roosevelt (FDR)|WA (`cwms-nwdp` research label) and Lake Cushman|WA (NWRFC) stay held; admitting them is an acceptance-gate decision.

## Not changed
Live systems, schedulers, bindings, knowledge release, validation status, scores, science.
