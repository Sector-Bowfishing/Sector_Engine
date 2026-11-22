//
//  LakeHistoryOffsets.swift
//  Sector — Lake Brain: the recorded history datum offset, applied the same way for every history provider
//
//  SIGN CONVENTION (the usgsDaily convention, now for every provider): a history entry's `offsetFt` is ADDED to each daily value the
//  source returns, so the archived row is `source reading + offsetFt`, on the live series' datum. A history that reads 0.55 ft above
//  live is recorded as -0.55. Live is the same: `LevelSeriesRef.datumOffsetFt` is added to every live reading by the classifier
//  (LakeLevelClassifier.evaluate), whatever the provider.
//
//  WHY THIS FILE EXISTS (2026-11-22): `usgsDaily`, `hadsDaily` and `cdecDaily` carry `offsetFt` in their `LakeHistorySource` case and
//  their readers add it. `cwmsDaily`, `riseDaily`, `tvaOperatingGuide`, `coopsDaily` and `usgsStageDaily` have no offset in their case,
//  so `LakeGeneratedBindings.history(_:)` dropped a recorded `offsetFt` on those kinds and the runner never applied it. Those cases
//  live in the packaged release files (LakeSourceBindings.swift / LakeGeneratedBindings.swift); to fix the runner without a new
//  release, the offset is read here from the generated record (which already decodes `offsetFt` for every kind) and added by
//  `LakeBrainRunner.historyDaily`. A kind whose case carries its own offset is never shifted here, so nothing is applied twice.
//  `usgsStageDaily` adds the site altitude in its reader; a recorded offset on it is an extra shift on top.
//
//  An offset of 0 (or none) leaves the rows untouched: such a lake's history is byte-identical to before.
//

import Foundation

enum LakeHistoryOffsets {

    /// The history kinds whose `LakeHistorySource` case carries `offsetFt` and whose reader adds it.
    static func carriesOwnOffset(_ s: LakeHistorySource) -> Bool {
        switch s {
        case .usgsDaily, .hadsDaily, .cdecDaily: return true
        case .tvaOperatingGuide, .sharedTVAArchive, .cwmsDaily, .riseDaily, .coopsDaily, .usgsStageDaily: return false
        }
    }

    /// lakeId → (history source, non-zero recorded offset) for the kinds whose case drops it.
    typealias Table = [String: [(source: LakeHistorySource, offsetFt: Double)]]

    static func table(_ records: [LakeGeneratedBindings.Record]) -> Table {
        var out: Table = [:]
        for r in records {
            for h in r.history {
                guard let off = h.offsetFt, off != 0, let s = LakeGeneratedBindings.history(h), !carriesOwnOffset(s) else { continue }
                out[r.lakeId, default: []].append((s, off))
            }
        }
        return out
    }

    static let generated: Table = table(LakeGeneratedBindings.records)

    /// The offset recorded for `source` on `lakeId` that its reader does not apply (0 when none).
    static func offsetFt(lakeId: String, source: LakeHistorySource, table: Table = generated) -> Double {
        guard !carriesOwnOffset(source) else { return 0 }
        return table[lakeId]?.first { $0.source == source }?.offsetFt ?? 0
    }

    /// `rows` shifted by `offsetFt`; returned unchanged when the offset is 0.
    static func apply(_ rows: [DailyLevel], offsetFt: Double) -> [DailyLevel] {
        guard offsetFt != 0 else { return rows }
        return rows.map { DailyLevel(date: $0.date, ft: $0.ft + offsetFt, sourceId: $0.sourceId) }
    }
}

extension LakeBrainRunner {
    /// One history source's daily rows with the lake's recorded offset applied (see LakeHistoryOffsets for the sign convention).
    static func historyDaily(_ source: LakeHistorySource, lakeId: String, feeds: LakeLevelFeeds, since: String?, now: Date,
                             timeZone: TimeZone, offsets: LakeHistoryOffsets.Table = LakeHistoryOffsets.generated) async -> [DailyLevel]? {
        guard let rows = await feeds.daily(source, since: since, now: now, timeZone: timeZone) else { return nil }
        return LakeHistoryOffsets.apply(rows, offsetFt: LakeHistoryOffsets.offsetFt(lakeId: lakeId, source: source, table: offsets))
    }
}
