# Session record: drop TVA from Lake live sources where another live source exists (2026-11-24)

Standards: Rehtac Cortex 3.1.6 @ a785035 (cloud session without CORTEX_HOME; followed the repo CLAUDE.md files)

## Request
Michael (chat, 2026-11-24): after TVA's robots.txt finding (Sector_Ops #51, 2026-11-23), move Lake's live pool levels off TVA's RestApi where an alternative exists; keep tva-only lakes until TVA answers the permission email he sent.

## Observed
Committed bindings: 15 lakes list a TVA live source (bindings.proposed.v1.json) plus 5 in bindings.batch2.v1.json (Cherokee, Chickamauga, Kentucky KY, Kentucky TN, Lake Barkley). Of the 20, 14 have another live source (nwps, a2w or cwms). Six are tva-only (Pickwick, South Holston, Tims Ford, Wheeler, Wilson, Kentucky TN). History for 11 lakes still reads TVA's operating guide (`tvaOperatingGuide`); not changed here.

## Change
`build_bindings_table.drop_tva_live` removes tva from a lake's live list when any other live source exists, and keeps it when it is the only one. The record's provider, station, series and capability follow `live[0]`. Applies to the proposed table and batch 2 (both use `build_record`). Three unit tests; bindings tests 17 pass.

## Not done
The committed tables and generated Swift are NOT regenerated: they come from research inputs that are not in this session. A Mac mini regeneration and review are required before any lake changes. Customer-visible; not merged.

## 2026-11-25 update: Percy Priest Depth evidence re-recorded (option a)
The review of #254 found `brains/depth` failing: Depth's Percy Priest SAME_SOURCE record pinned Lake's live binding including `tva:JPHT1`, so dropping the fallback refused it. Michael approved option (a) in chat on 2026-11-25 ("I approve all your recommendations"). `liveSourceIds` in `datum_verification.json` now lists the two remaining ids (A2W and CWMS, same JPHT1 location); the level, reference and datum evidence is unchanged. The test now refuses a dropped recorded source and a returned TVA fallback. Main merged in; the status digest regenerated. No Lake digest change.
