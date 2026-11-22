# Session record: Lake history datum offset applied for every provider

Standards: Rehtac Cortex 3.1.2 @ ecaef70 (clean), pack sector/engine (briefing run by hand from the local Cortex checkout; `CORTEX_HOME` unset). Date: 2026-11-22. Branch: `fix/lake-history-offsets-all-providers-2026-11-22` (off main 1234faf9). Cloud session.

## Finding (the gap is real, history only)
- **History.** `LakeHistorySource` cases `usgsDaily`, `hadsDaily`, `cdecDaily` carry `offsetFt` and their readers add it (`LakeLevelFeedsFleet.swift:312` `parseUSGSDV`, `:375` `dailyMedians` for USGS iv and HADS, `LakeLevelFeedsCDEC.swift:168/170`). `cwmsDaily`, `riseDaily`, `tvaOperatingGuide`, `coopsDaily`, `usgsStageDaily` have no offset field: `LakeGeneratedBindings.history(_:)` (`LakeGeneratedBindings.swift:150-152, 156, 149, 163, 164-166`) dropped a recorded `offsetFt` on those kinds, and their readers use offset 0 (`LakeLevelFeeds.swift:251` CWMS `dailyMedians(offsetFt: 0)`, `LakeLevelFeedsCOOPS.swift:195`). The runner (`LakeBrainRunner.swift:173-179`) passed the source straight to `feeds.daily`.
- **Live.** Consistent: `LakeLevelClassifier.swift:214` adds `sel.ref.datumOffsetFt` for every provider; `:226` uses it in the fallback datum check. No live reader adds it, so nothing is applied twice. Trend deltas are offset-invariant.

## Impact
- **Main (187 accepted + 5 pilots):** no non-zero offset on a provider that ignores it. Pilots have none. Batch 1 (2026-11-21): Deep Creek history is `usgsDaily` 62615 −1.82 (applied), THYM2 and Havasu LKHC1 are `nwps` live −1.82 / −0.65 (applied by the classifier); Jennings Randolph and Beltzville were series swaps, no offset.
- **PR #222 (batch 2, open):** Rend Lake IL `cwmsDaily` MVS `datman-rev` −0.55 and Lake Washington WA `cwmsDaily` NWDP `LWSC…NWSRADIO-RAW` +0.36 were recorded but not applied (#222's own doc says so). Toledo Bend −0.18 is `usgsDaily` (applied).

## Fix (outside the packaged release files)
- `LakeHistoryOffsets.swift` (new): builds lakeId → (source, offset) from the generated records for the kinds whose case has no offset; `LakeBrainRunner.historyDaily` applies it after `feeds.daily`. Sign convention documented: offset is **added** to the reading (the `usgsDaily` convention). Kinds that carry their own offset are never shifted here. Offset 0 returns the rows unchanged.
- `LakeBrainRunner.swift`: both history pulls go through `historyDaily`.
- `docs/brains/LAKE_BRAIN_PROVIDERS.md` §2: the convention.
- Tests `LakeHistoryOffsetTests.swift`: per provider (cwms, rise, TVA guide, CO-OPS, USGS stage shifted by the runner; USGS daily, HADS, CDEC shifted once by the reader), byte-identical history for offset 0, table construction, and an invariant over the packaged table: every recorded history offset is applied exactly once.
- Release: `LakeSourceBindings.swift`, `LakeGeneratedBindings.swift`, `LakeSourceBindingsGenerated.swift` unchanged, so no new knowledge release (`lake-knowledge-2026-11-22.3` not created).

## Owner step (not done here): history archive rebuild
On main no lake is affected, so Pulse's Lake archive holds no unshifted rows from this gap unless a #222 build has run against it. After #222 and this PR are merged, on the Mac mini:
1. Check whether `history/Rend_Lake_IL/daily.csv` and `history/Lake_Washington_WA/daily.csv` exist in Pulse's Lake archive. If neither exists, nothing to do (the first run backfills with the offset).
2. If one exists: back it up (copy beside it with a dated suffix), delete it, then run the Lake job for that lake with `--backfill --force --lake "<lakeId>"` so the full record is re-pulled with the offset. Deleting first matters for Rend Lake: its older rows came from `MVDhist-rev`, which the new source no longer serves, so a merge would keep them.
3. Lake Washington's +0.36 sign is "as the comparator reported it; direction to be confirmed on the Mac mini" (#222). Confirm it before the rebuild: after the fix, its archived history should sit within ~0.1 ft of the live `LWKW` series over the overlap.

## Not done
No push to main, merge, deploy, rules or IAM. #222's notes ("not applied until cwmsDaily gains an offset") become stale when this merges.
