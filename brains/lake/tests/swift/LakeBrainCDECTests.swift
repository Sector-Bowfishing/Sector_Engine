//
//  LakeBrainCDECTests.swift
//  Lake Brain: the California DWR CDEC reservoir-elevation reader (LakeLevelFeedsCDEC.swift). No network.
//
//  The fixture tests/fixtures/cdec/SHA_6_H.json has the JSONDataServlet row shape (stationId, durCode, SENSOR_NUM, sensorType, date,
//  obsDate, value, dataFlag, units) with a -9999 sentinel row. It was assembled from the documented format, not captured from CDEC: the
//  host was not reachable from the session that wrote this reader. Replace it with a recorded answer when one is captured.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakeBrainCDECTests: XCTestCase {

    let pacific = TimeZone(identifier: "America/Los_Angeles")!
    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    static let fixtureURL = URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("fixtures/cdec/SHA_6_H.json")

    func fixture() throws -> Data { try Data(contentsOf: Self.fixtureURL) }

    // MARK: parser

    func testFixtureParsesDropsTheSentinelAndReadsPacificStandardTime() throws {
        let (rows, error) = LakeFleetClients.parseCDEC(try fixture(), station: "SHA", sensor: "6")
        XCTAssertNil(error)
        XCTAssertEqual(rows.map(\.ft), [1015.42, 1015.44, 1015.47, 1015.51, 1015.52, 1015.55], "-9999 dropped")
        // November: PST, UTC-8
        XCTAssertEqual(rows[0].at, iso("2026-11-20T18:00:00Z"))
        XCTAssertEqual(rows[0].day, "2026-11-20")
        // 23:00 Pacific on the 20th is 07:00Z on the 21st; the row keeps its Pacific date
        XCTAssertEqual(rows[3].at, iso("2026-11-21T07:00:00Z"))
        XCTAssertEqual(rows[3].day, "2026-11-20")
    }

    func testSummerStampsAreDaylightTime() {
        let json = """
        [{"stationId":"SHA","durCode":"H","SENSOR_NUM":6,"sensorType":"RES ELE","date":"2026-07-15 13:00","obsDate":"2026-07-15 13:00","value":1050.1,"dataFlag":" ","units":"FEET"}]
        """
        let (rows, error) = LakeFleetClients.parseCDEC(Data(json.utf8), station: "SHA", sensor: "6")
        XCTAssertNil(error)
        XCTAssertEqual(rows.first?.at, iso("2026-07-15T20:00:00Z"), "July: PDT, UTC-7")
    }

    func testStorageZeroOtherSensorsAndBadAnswers() {
        let storage = """
        [{"stationId":"SHA","durCode":"D","SENSOR_NUM":15,"sensorType":"STORAGE","date":"2026-11-20 00:00","value":2950000,"dataFlag":" ","units":"AF"}]
        """
        let s = LakeFleetClients.parseCDEC(Data(storage.utf8), station: "SHA", sensor: "15")
        XCTAssertNotNil(s.error, "acre-feet is not a level")
        XCTAssertTrue(s.rows.isEmpty)
        // a mixed answer: the other sensor's rows are ignored, a 0.0 elevation is a mechanical error
        let mixed = """
        [{"stationId":"SHA","durCode":"D","SENSOR_NUM":15,"date":"2026-11-20 00:00","value":2950000,"units":"AF"},
         {"stationId":"SHA","durCode":"D","SENSOR_NUM":6,"date":"2026-11-19 00:00","value":0,"units":"FEET"},
         {"stationId":"SHA","durCode":"D","SENSOR_NUM":6,"date":"2026-11-20 00:00","value":1015,"units":"FEET"}]
        """
        let m = LakeFleetClients.parseCDEC(Data(mixed.utf8), station: "SHA", sensor: "6")
        XCTAssertNil(m.error)
        XCTAssertEqual(m.rows.map(\.ft), [1015])
        XCTAssertNotNil(LakeFleetClients.parseCDEC(Data("<html>error</html>".utf8), station: "SHA", sensor: "6").error)
        XCTAssertEqual(LakeFleetClients.parseCDEC(Data("[]".utf8), station: "SHA", sensor: "6").rows, [])
    }

    func testDateParsing() {
        XCTAssertEqual(LakeFleetClients.cdecDate("2026-01-05 07:30:00")?.at, iso("2026-01-05T15:30:00Z"))
        XCTAssertEqual(LakeFleetClients.cdecDate("2026-01-05")?.day, "2026-01-05")
        XCTAssertNil(LakeFleetClients.cdecDate("01/05/2026 07:30"))
        XCTAssertNil(LakeFleetClients.cdecDate("2026-13-05 07:30"))
    }

    // MARK: live

    func testLiveKeepsTheRequestedWindow() throws {
        let r = LakeFleetClients.cdecLive(try fixture(), station: "SHA", sensor: "6", since: iso("2026-11-20T21:00:00Z"))
        XCTAssertNil(r.error)
        XCTAssertEqual(r.observations.map(\.ft), [1015.47, 1015.51, 1015.52, 1015.55])
        XCTAssertEqual(r.observations.last?.at, iso("2026-11-21T09:00:00Z"))
        let none = LakeFleetClients.cdecLive(Data("[]".utf8), station: "SHA", sensor: "6", since: .distantPast)
        XCTAssertNotNil(none.error)
    }

    func testStorageAndMalformedSeriesAreRefusedBeforeAnyRequest() async {
        let feeds = PublicLakeLevelFeeds.legacyUSGS()
        for series in ["15", "1", "6:M", "six", "6:H:x"] {
            let ref = LevelSeriesRef(provider: .cdec, capability: .directOperatorPool, station: "SHA", series: series, cadenceMin: 60, lagMin: 120)
            let r = await feeds.recent(ref, hours: 24, now: Date())
            XCTAssertNotNil(r.error, series)
            XCTAssertTrue(r.observations.isEmpty, series)
        }
        let bad = LevelSeriesRef(provider: .cdec, capability: .directOperatorPool, station: "SHA&x=1", series: "6", cadenceMin: 60, lagMin: 120)
        let r = await feeds.recent(bad, hours: 24, now: Date())
        XCTAssertNotNil(r.error)
        // history: storage refused, no request made
        let h = await feeds.daily(.cdecDaily(station: "SHA", sensor: "15", dur: "D", offsetFt: 0), since: nil, now: Date(), timeZone: pacific)
        XCTAssertNil(h)
    }

    func testSeriesURLAndIds() {
        XCTAssertEqual(LakeFleetClients.cdecSeries(nil)?.dur, "H")
        XCTAssertEqual(LakeFleetClients.cdecSeries("6")?.sensor, "6")
        XCTAssertEqual(LakeFleetClients.cdecSeries("6:d")?.dur, "D")
        XCTAssertEqual(LakeFleetClients.cdecSeries("6:E")?.dur, "E")
        XCTAssertNil(LakeFleetClients.cdecSeries("6:X"))
        XCTAssertEqual(LakeFleetClients.cdecURL(station: "sha", sensor: "6", dur: "H", start: "2026-11-19", end: "2026-11-21"),
                       "https://cdec.water.ca.gov/dynamicapp/req/JSONDataServlet?Stations=SHA&SensorNums=6&dur_code=H&Start=2026-11-19&End=2026-11-21")
        let ref = LevelSeriesRef(provider: .cdec, capability: .directOperatorPool, station: "SHA", series: "6:H", cadenceMin: 60, lagMin: 120)
        XCTAssertEqual(ref.sourceId, "cdec:SHA:6:H")
        XCTAssertEqual(ref.providerName, "California DWR CDEC")
        XCTAssertEqual(LakeHistorySource.cdecDaily(station: "SHA", sensor: "6", dur: "D", offsetFt: 0).profileDescription, "cdec:SHA:6:D (daily values)")
        XCTAssertEqual(LakeHistorySource.cdecDaily(station: "SHA", sensor: "6", dur: "H", offsetFt: 1.5).profileDescription,
                       "cdec:SHA:6:H (daily median of hourly values), datum offset 1.50 ft")
    }

    // MARK: history

    func testDailyLevelsKeepTheStampedDateOrTakeTheLakeLocalMedian() throws {
        let (rows, _) = LakeFleetClients.parseCDEC(try fixture(), station: "SHA", sensor: "6")
        let hourly = LakeFleetClients.cdecDailyLevels(rows, dur: "H", timeZone: pacific, offsetFt: 0, src: "cdec:SHA:6:H")
        XCTAssertEqual(hourly.map(\.date), ["2026-11-20", "2026-11-21"])
        XCTAssertEqual(hourly[0].ft, 1015.455, accuracy: 0.0001, "median of the four Pacific Nov 20 readings")
        XCTAssertEqual(hourly[1].ft, 1015.535, accuracy: 0.0001)
        XCTAssertEqual(hourly[0].sourceId, "cdec:SHA:6:H")

        let daily = """
        [{"stationId":"SHA","durCode":"D","SENSOR_NUM":6,"date":"2026-11-19 00:00","value":1015.2,"dataFlag":" ","units":"FEET"},
         {"stationId":"SHA","durCode":"D","SENSOR_NUM":6,"date":"2026-11-20 00:00","value":-9999,"dataFlag":" ","units":"FEET"},
         {"stationId":"SHA","durCode":"D","SENSOR_NUM":6,"date":"2026-11-21 00:00","value":1015.5,"dataFlag":" ","units":"FEET"}]
        """
        let (drows, _) = LakeFleetClients.parseCDEC(Data(daily.utf8), station: "SHA", sensor: "6")
        // a UTC lake calendar would move a 00:00 Pacific stamp to 08:00Z the same day; the date in the stamp is kept either way
        let d = LakeFleetClients.cdecDailyLevels(drows, dur: "D", timeZone: TimeZone(identifier: "UTC")!, offsetFt: -2, src: "x")
        XCTAssertEqual(d.map(\.date), ["2026-11-19", "2026-11-21"], "missing day left missing, never filled")
        XCTAssertEqual(d.count, 2)
        XCTAssertEqual(d[0].ft, 1013.2, accuracy: 0.0001, "+ datum offset")
        XCTAssertEqual(d[1].ft, 1013.5, accuracy: 0.0001)
    }

    func testHistoryWindowsMatchTheDuration() {
        XCTAssertEqual(LakeFleetClients.cdecWindowSeconds(dur: "D"), 10 * 365.25 * 86_400, accuracy: 1)
        XCTAssertEqual(LakeFleetClients.cdecWindowSeconds(dur: "H"), 365.25 * 86_400, accuracy: 1)
        XCTAssertEqual(LakeFleetClients.cdecWindowSeconds(dur: "E"), 60 * 86_400, accuracy: 1)
        // a daily CDEC history is expected up to yesterday, like the other operator daily feeds
        let now = iso("2026-11-22T18:00:00Z")
        XCTAssertEqual(LakeBrainRunner.expectedLatestDay(.cdecDaily(station: "SHA", sensor: "6", dur: "D", offsetFt: 0), now: now, timeZone: pacific), "2026-11-21")
    }

    // MARK: generated table rows can name CDEC

    func testGeneratedRecordsMapCDECLiveAndHistory() throws {
        let live = try JSONDecoder().decode(LakeGeneratedBindings.Record.Live.self, from: Data("""
        {"provider":"cdec","capability":"DIRECT_OPERATOR_POOL","station":"SHA","series":"6:H","cadenceMin":60,"lagMin":120}
        """.utf8))
        let ref = try XCTUnwrap(LakeGeneratedBindings.ref(live))
        XCTAssertEqual(ref.provider, .cdec)
        XCTAssertEqual(ref.sourceId, "cdec:SHA:6:H")
        let hist = try JSONDecoder().decode(LakeGeneratedBindings.Record.Hist.self, from: Data("""
        {"kind":"cdecDaily","station":"SHA","sensor":"6","dur":"D","offsetFt":0.5}
        """.utf8))
        XCTAssertEqual(LakeGeneratedBindings.history(hist), .cdecDaily(station: "SHA", sensor: "6", dur: "D", offsetFt: 0.5))
        let incomplete = try JSONDecoder().decode(LakeGeneratedBindings.Record.Hist.self, from: Data(#"{"kind":"cdecDaily","station":"SHA"}"#.utf8))
        XCTAssertNil(LakeGeneratedBindings.history(incomplete))
    }

    func testNoLakeIsBoundToCDEC() {
        XCTAssertFalse(LakeSourceBindings.all.contains { $0.live.contains { $0.provider == .cdec } }, "binding a lake needs the owner's review")
    }
}
