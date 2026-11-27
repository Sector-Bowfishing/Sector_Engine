# Session record: Moses Lake live and Flannagan history rebind (2026-11-25)

Standards: Rehtac Cortex 3.1.6 @ a785035 (cloud session without CORTEX_HOME; followed the repo CLAUDE.md files)

## Request
Michael (chat, 2026-11-25 23:22 CT, "I approve all your recommendations"), item 6 of the Morning summary: Moses Lake live goes to USGS 12471000:62614; Flannagan history goes to the CWMS observed series, as one reviewed rebind PR. A Lake rebuild and a Pulse switch need their own request.

## Observed
- Moses Lake WA: live was CWMS NWDP `MLAW.Elev-Forebay` (RFC-RAW). It has read +0.34 ft above USGS 12471000 since 2026-11-13. History already uses the USGS gauge.
- Flannagan Reservoir VA: history was the CWMS rule curve `JWFlannagan-Lake.Elev.Inst.1Day.0.RUL`, which sits -30 to +34 ft from observed.

## Change
- `build_bindings_table.py`: `REBINDS_2026_11_25` and `apply_rebinds`, applied after `apply_dryrun_fixes`, so a rebuild reproduces the table.
- `bindings.proposed.v1.json` patched with the same function (the research inputs are not in this session); `LakeSourceBindingsGenerated.swift` regenerated (`generate-lake-bindings.py --check` clean); `reviewed-lake-bindings-v1.json` Moses entry updated by hand to the export shape (Swift export test checks it in CI).
- New Lake release `lake-knowledge-2026-11-26.1`, digest `sha256:4f2d6154...fa47`, approval NOT_RECORDED (`docs/cortex/approvals/lake-knowledge-2026-11-26.1.md`). Only the generated Swift file changed.
- Depth: `test_counts_on_the_committed_release` pin moves seriesMedian 19 to 20 and notLive 113 to 112 (Moses now live on its history gauge).

## Verification
brains/lake 81 passed; brains/depth 354 passed (the Percy Priest case fails on this base and is fixed by #254, which this branch is stacked on); jobs/lake-brain and jobs/brain_platform 1183 passed. No Swift toolchain here: Swift tests run in CI.

## Not done / needs Michael
Approve the release digest; Lake rebuild and Pulse switch are separate requests. Customer-visible, so no merge by me.

## 2026-11-26 review fix
Independent review found Flannagan's history stats still counted the rule curve (13 years from 2013). They now follow the observed series (5 complete years, first year 2020, SUFFICIENT), counted from the series start (2020-08-12); the Mac mini should confirm with a read. Releases are immutable, so the release is cut again as `lake-knowledge-2026-11-26.1` (the 25.1 digest was never approved or merged).

## 2026-11-26 approval
Michael approved release `lake-knowledge-2026-11-26.1` (digest `sha256:4f2d6154...fa47`) in chat at 20:57 CT. Recorded APPROVED in the release manifest, approval record and brain.json. Merge, Lake rebuild and Pulse switch are not covered.
