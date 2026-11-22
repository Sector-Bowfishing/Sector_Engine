//
//  LakeHistoryOffsetTests.swift
//  Lake Brain: a history entry's recorded offsetFt applies for every provider, with one sign convention (added to the reading),
//  never twice, and an offset of 0 leaves the archived history byte-identical. No network.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

/// Returns the same fixed rows for every history source (standing in for each provider's reader output).
private final class FixedDailyFeeds: LakeLevelFeeds, @unchecked Sendable {
    let rows: [DailyLevel]
    var asked: [LakeHistorySource] = []
    init(_ rows: [DailyLevel]) { self.rows = rows }
    func recent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult { FeedResult(observations: [], error: nil) }
    func guide(_ source: LakeGuideSource, day: String, timeZone: TimeZone) async -> LakeGuideForDay? { nil }
    func daily(_ source: LakeHistorySource, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? { asked.append(source); return rows }
    func archivedHourly(_ source: LakeHistorySource, days: Int, now: Date, timeZone: TimeZone) async -> [LevelObservation] { [] }
}

private final class FailingDailyFeeds: LakeLevelFeeds, @unchecked Sendable {
    func recent(_ ref: LevelSeriesRef, hours: Int, now: Date) async -> FeedResult { FeedResult(observations: [], error: nil) }
    func guide(_ source: LakeGuideSource, day: String, timeZone: TimeZone) async -> LakeGuideForDay? { nil }
    func daily(_ source: LakeHistorySource, since: String?, now: Date, timeZone: TimeZone) async -> [DailyLevel]? { nil }
    func archivedHourly(_ source: LakeHistorySource, days: Int, now: Date, timeZone: TimeZone) async -> [LevelObservation] { [] }
}

final class LakeHistoryOffsetTests: XCTestCase {

    let utc = TimeZone(identifier: "UTC")!
    let now = ISO8601DateFormatter().date(from: "2026-11-22T12:00:00Z")!
    let rows = [DailyLevel(date: "2026-11-01", ft: 400.00, sourceId: "src"), DailyLevel(date: "2026-11-02", ft: 400.25, sourceId: "src")]

    // Each history kind whose LakeHistorySource case has no offset field.
    let cwms = LakeHistorySource.cwmsDaily(office: "MVS", series: "Rend Lk-Big Muddy.Elev.Inst.~1Day.0.datman-rev")
    let rise = LakeHistorySource.riseDaily(item: "509")
    let tvaGuide = LakeHistorySource.tvaOperatingGuide(locationId: "GVDA1")
    let coops = LakeHistorySource.coopsDaily(station: "9087044")
    let usgsStage = LakeHistorySource.usgsStageDaily(site: "04082500", datum: "NAVD88", stat: "iv")

    private func shifted(_ source: LakeHistorySource, offset: Double, lake: String = "Rend Lake|IL") async -> [DailyLevel]? {
        await LakeBrainRunner.historyDaily(source, lakeId: lake, feeds: FixedDailyFeeds(rows), since: nil, now: now, timeZone: utc,
                                           offsets: [lake: [(source, offset)]])
    }

    private func assertShifted(_ got: [DailyLevel]?, by off: Double, file: StaticString = #filePath, line: UInt = #line) {
        XCTAssertEqual(got?.map(\.date), rows.map(\.date), file: file, line: line)
        XCTAssertEqual(got?.map(\.sourceId), rows.map(\.sourceId), file: file, line: line)
        for (g, r) in zip(got ?? [], rows) { XCTAssertEqual(g.ft, r.ft + off, accuracy: 1e-9, file: file, line: line) }
    }

    // MARK: per provider: the runner applies the recorded offset (added to the reading)

    func testCwmsDailyAppliesRecordedOffset() async {
        assertShifted(await shifted(cwms, offset: -0.55), by: -0.55)
        assertShifted(await shifted(cwms, offset: 0.36, lake: "Lake Washington|WA"), by: 0.36)
    }

    func testRiseDailyAppliesRecordedOffset() async { assertShifted(await shifted(rise, offset: -0.65), by: -0.65) }

    func testTVAOperatingGuideAppliesRecordedOffset() async { assertShifted(await shifted(tvaGuide, offset: 0.10), by: 0.10) }

    func testCOOPSDailyAppliesRecordedOffset() async { assertShifted(await shifted(coops, offset: -0.20), by: -0.20) }

    func testUSGSStageDailyAddsRecordedOffsetOnTopOfAltitude() async { assertShifted(await shifted(usgsStage, offset: 0.05), by: 0.05) }

    func testOffsetIsKeyedOnTheExactSourceAndLake() async {
        let table: LakeHistoryOffsets.Table = ["Rend Lake|IL": [(cwms, -0.55)]]
        XCTAssertEqual(LakeHistoryOffsets.offsetFt(lakeId: "Rend Lake|IL", source: cwms, table: table), -0.55)
        XCTAssertEqual(LakeHistoryOffsets.offsetFt(lakeId: "Rend Lake|IL", source: .cwmsDaily(office: "MVS", series: "other"), table: table), 0)
        XCTAssertEqual(LakeHistoryOffsets.offsetFt(lakeId: "Carlyle Lake|IL", source: cwms, table: table), 0)
    }

    func testUnavailableSourceStaysUnavailable() async {
        let got = await LakeBrainRunner.historyDaily(cwms, lakeId: "Rend Lake|IL", feeds: FailingDailyFeeds(), since: nil, now: now,
                                                     timeZone: utc, offsets: ["Rend Lake|IL": [(cwms, -0.55)]])
        XCTAssertNil(got)
    }

    // MARK: per provider: readers that carry the offset in their case apply it, and the runner does not apply it again

    func testUSGSDailyReaderAppliesOffsetOnce() async {
        let body = #"{"value":{"timeSeries":[{"variable":{"noDataValue":-999999,"options":{"option":[{"optionCode":"00003"}]}},"values":[{"value":[{"dateTime":"2026-11-01T00:00:00.000","value":"2.00"}]}]}]}}"#
        let d = LakeFleetClients.parseUSGSDV(Data(body.utf8), offsetFt: 743.91, src: "usgs:04082500:00065")
        XCTAssertEqual(d?.first?.ft ?? 0, 745.91, accuracy: 1e-9)
        let src = LakeHistorySource.usgsDaily(site: "04082500", param: "00065", stat: "dv", offsetFt: 743.91)
        XCTAssertTrue(LakeHistoryOffsets.carriesOwnOffset(src))
        // Even if a table somehow listed it, the runner leaves reader output alone.
        assertShifted(await shifted(src, offset: 743.91), by: 0)
    }

    func testHADSDailyReaderAppliesOffsetOnce() async {
        let obs = [LevelObservation(at: now, ft: 500.0)]
        XCTAssertEqual(LakeFleetClients.dailyMedians(obs, timeZone: utc, offsetFt: -1.82, src: "hads").first?.ft ?? 0, 498.18, accuracy: 1e-9)
        assertShifted(await shifted(.hadsDaily(lid: "THYM2", pe: "HP", offsetFt: -1.82), offset: -1.82), by: 0)
    }

    func testCDECDailyReaderAppliesOffsetOnce() async {
        let r = [LakeFleetClients.CDECRow(day: "2026-11-01", at: now, ft: 1000.0)]
        XCTAssertEqual(LakeFleetClients.cdecDailyLevels(r, dur: "D", timeZone: utc, offsetFt: 1.5, src: "cdec").first?.ft ?? 0, 1001.5, accuracy: 1e-9)
        assertShifted(await shifted(.cdecDaily(station: "SHA", sensor: "6", dur: "D", offsetFt: 1.5), offset: 1.5), by: 0)
    }

    // MARK: offset 0 is byte-identical

    func testZeroOffsetLakeIsByteIdentical() async {
        let before = LakeDailyHistory.encode(rows)
        for s in [cwms, rise, tvaGuide, coops, usgsStage] {
            let explicitZero = await shifted(s, offset: 0)
            XCTAssertEqual(explicitZero, rows)
            XCTAssertEqual(LakeDailyHistory.encode(explicitZero ?? []), before)
            let unlisted = await LakeBrainRunner.historyDaily(s, lakeId: "Carlyle Lake|IL", feeds: FixedDailyFeeds(rows), since: nil, now: now, timeZone: utc)
            XCTAssertEqual(LakeDailyHistory.encode(unlisted ?? []), before)
        }
        XCTAssertEqual(LakeHistoryOffsets.apply(rows, offsetFt: 0), rows)
    }

    // MARK: the generated table

    private func record(_ lakeId: String, history: String) throws -> LakeGeneratedBindings.Record {
        let json = """
        {"lakeId": "\(lakeId)", "capability": "directOperatorPool", "timeZone": "America/Chicago",
         "live": [{"provider": "cwms", "capability": "directOperatorPool", "station": "MVS", "series": "x", "cadenceMin": 60, "lagMin": 60}],
         "history": \(history), "historyCompleteYears": 30, "historyClass": "SUFFICIENT",
         "verification": {"criteriaVersion": "v", "researchStatus": "s", "wave": "w", "checksPassed": "c", "probedAt": "p"}}
        """
        return try JSONDecoder().decode(LakeGeneratedBindings.Record.self, from: Data(json.utf8))
    }

    func testTableTakesOnlyNonZeroOffsetsOnKindsWithoutTheirOwn() throws {
        let rend = try record("Rend Lake|IL", history: #"[{"kind": "cwmsDaily", "office": "MVS", "series": "Rend Lk-Big Muddy.Elev.Inst.~1Day.0.datman-rev", "offsetFt": -0.55}, {"kind": "usgsDaily", "site": "05595730", "param": "62614", "stat": "dv", "offsetFt": 0.4}]"#)
        let zero = try record("Carlyle Lake|IL", history: #"[{"kind": "cwmsDaily", "office": "MVS", "series": "Carlyle.Elev", "offsetFt": 0}]"#)
        let none = try record("Kaw Lake|OK", history: #"[{"kind": "cwmsDaily", "office": "SWT", "series": "KAWL.Elev"}]"#)
        let t = LakeHistoryOffsets.table([rend, zero, none])
        XCTAssertEqual(t.keys.sorted(), ["Rend Lake|IL"])
        XCTAssertEqual(t["Rend Lake|IL"]?.count, 1)
        XCTAssertEqual(t["Rend Lake|IL"]?.first?.source, cwms)
        XCTAssertEqual(t["Rend Lake|IL"]?.first?.offsetFt, -0.55)
    }

    /// No recorded history offset in the packaged table is dropped: each one is applied exactly once, by its reader or by the runner.
    func testEveryRecordedHistoryOffsetInTheGeneratedTableIsApplied() {
        var checked = 0
        for r in LakeGeneratedBindings.records {
            for h in r.history {
                guard let recorded = h.offsetFt, recorded != 0, let s = LakeGeneratedBindings.history(h) else { continue }
                let byReader: Double
                switch s {
                case .usgsDaily(_, _, _, let o), .hadsDaily(_, _, let o), .cdecDaily(_, _, _, let o): byReader = o
                default: byReader = 0
                }
                let byRunner = LakeHistoryOffsets.offsetFt(lakeId: r.lakeId, source: s)
                XCTAssertEqual(byReader + byRunner, recorded, accuracy: 1e-9, "\(r.lakeId) \(h.kind)")
                XCTAssertTrue(byReader == 0 || byRunner == 0, "\(r.lakeId) \(h.kind): applied twice")
                checked += 1
            }
        }
        XCTAssertGreaterThan(checked, 0)
    }
}
