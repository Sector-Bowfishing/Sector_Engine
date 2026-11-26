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
- New Lake release `lake-knowledge-2026-11-25.1`, digest `sha256:5fc7d3e8...5e9b`, approval NOT_RECORDED (`docs/cortex/approvals/lake-knowledge-2026-11-25.1.md`). Only the generated Swift file changed.
- Depth: `test_counts_on_the_committed_release` pin moves seriesMedian 19 to 20 and notLive 113 to 112 (Moses now live on its history gauge).

## Verification
brains/lake 81 passed; brains/depth 352 passed (the Percy Priest case fails on this base and is fixed by #254, which this branch is stacked on); jobs/lake-brain and jobs/brain_platform 1183 passed. No Swift toolchain here: Swift tests run in CI.

## Not done / needs Michael
Approve the release digest; Lake rebuild and Pulse switch are separate requests. Customer-visible, so no merge by me.
