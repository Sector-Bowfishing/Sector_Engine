//
//  LakeBrainHistoryWalkTests.swift
//  Lake Brain: window walking of the CDEC (`cdecDaily`) and USGS gage-height + altitude (`usgsStageDaily`) history pulls, through an
//  injected transport. Contiguous windows, the two-empty-windows stop, a failed window failing the whole pull, the `since` filter.
//  No network: every answer below is built in the test.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

final class LakeBrainHistoryWalkTests: XCTestCase {

    let utc = TimeZone(identifier: "UTC")!
    let pacific = TimeZone(identifier: "America/Los_Angeles")!
    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    static func ok(_ s: String) -> LakeFeedHTTP.Response { LakeFeedHTTP.Response(status: 200, body: Data(s.utf8)) }

    /// `key=value` from a URL's query.
    static func param(_ url: String, _ key: String) -> String? {
        URLComponents(string: url)?.queryItems?.first { $0.name == key }?.value
    }

    // MARK: CDEC

    static func cdecDays(_ days: [String], station: String = "SHA", dur: String = "D") -> String {
        "[" + days.enumerated().map { i, d in
            #"{"stationId":"\#(station)","durCode":"\#(dur)","SENSOR_NUM":6,"sensorType":"RES ELE","date":"\#(d) 00:00","value":\#(1000 + i),"dataFlag":" ","units":"FEET"}"#
        }.joined(separator: ",") + "]"
    }

    func testCDECWindowsAreContiguousAndTwoEmptyWindowsEndTheWalk() async throws {
        let rec = URLRecorder()
        let fleet = LakeFleetClients(transport: { url, _, _ in
            rec.add(url)
            switch rec.urls.count {
            case 1: return Self.ok(Self.cdecDays(["2026-11-20", "2026-11-21"]))
            case 2: return Self.ok(Self.cdecDays(["2010-06-01"]))
            default: return Self.ok("[]")
            }
        })
        let dPulled = await fleet.cdecDaily(station: "SHA", sensor: "6", dur: "D", offsetFt: 0, since: nil,
                                                     now: iso("2026-11-22T12:00:00Z"), timeZone: pacific)
        let d = try XCTUnwrap(dPulled)
        XCTAssertEqual(d.map(\.date), ["2010-06-01", "2026-11-20", "2026-11-21"])
        let urls = rec.urls
        XCTAssertEqual(urls.count, 4, "data, data, empty, empty: two empty windows in a row end the walk")
        for (newer, older) in zip(urls, urls.dropFirst()) {
            let start = try XCTUnwrap(Self.param(newer, "Start")), end = try XCTUnwrap(Self.param(older, "End"))
            XCTAssertEqual(LakeLevelCalendar.previousDay(start), end, "the older window ends the day before the newer one starts")
        }
    }

    func testCDECFailedWindowFailsThePullAndSinceBoundsIt() async throws {
        let rec = URLRecorder()
        let failing = LakeFleetClients(transport: { url, _, _ in
            rec.add(url)
            return rec.urls.count == 1 ? Self.ok(Self.cdecDays(["2026-11-20"])) : LakeFeedHTTP.Response(status: 500, body: Data())
        })
        let failed = await failing.cdecDaily(station: "SHA", sensor: "6", dur: "D", offsetFt: 0, since: nil, now: iso("2026-11-22T12:00:00Z"), timeZone: pacific)
        XCTAssertNil(failed, "no silent hole")

        let rec2 = URLRecorder()
        let bounded = LakeFleetClients(transport: { url, _, _ in
            rec2.add(url); return Self.ok(Self.cdecDays(["2026-11-18", "2026-11-19", "2026-11-20"]))
        })
        let dPulled = await bounded.cdecDaily(station: "SHA", sensor: "6", dur: "D", offsetFt: 1.5, since: "2026-11-19",
                                                       now: iso("2026-11-22T12:00:00Z"), timeZone: pacific)
        let d = try XCTUnwrap(dPulled)
        XCTAssertEqual(d.map(\.date), ["2026-11-19", "2026-11-20"], "rows before since dropped")
        XCTAssertEqual(d[0].ft, 1002.5, "offset applied")
        XCTAssertEqual(rec2.urls.count, 1, "one window reaches since")
        XCTAssertEqual(Self.param(rec2.urls[0], "Start"), "2026-11-19")
    }

    func testCDECIgnoresRowsOfAnotherStationOrDuration() {
        let mixed = "[" + [Self.cdecDays(["2026-11-20"]), Self.cdecDays(["2026-11-19"], station: "ORO"), Self.cdecDays(["2026-11-18"], dur: "H")]
            .map { String($0.dropFirst().dropLast()) }.joined(separator: ",") + "]"
        let (rows, error) = LakeFleetClients.parseCDEC(Data(mixed.utf8), station: "SHA", sensor: "6", dur: "D")
        XCTAssertNil(error)
        XCTAssertEqual(rows.map(\.day), ["2026-11-20"])
    }

    // MARK: USGS gage height + altitude

    static let rdb: String = {
        let cols = ["agency_cd", "site_no", "station_nm", "site_tp_cd", "alt_va", "alt_acy_va", "alt_datum_cd"]
        return "#\n" + cols.joined(separator: "\t") + "\n" + ["5s", "15s", "50s", "7s", "8s", "3s", "10s"].joined(separator: "\t") + "\n"
            + ["USGS", "04082500", "LAKE WINNEBAGO AT OSHKOSH, WI", "LK", "743.91", ".01", "NAVD88"].joined(separator: "\t") + "\n"
    }()

    /// A WaterServices IV answer for 00065 with one reading per given ISO instant (2.00 ft each); `blocks` value blocks.
    static func iv(_ instants: [String], blocks: Int = 1) -> String {
        let vals = instants.map { #"{"value":"2.00","qualifiers":["A"],"dateTime":"\#($0)"}"# }.joined(separator: ",")
        let block = #"{"value":[\#(vals)],"qualifier":[],"method":[{"methodID":1}]}"#
        return #"{"value":{"timeSeries":[{"variable":{"unit":{"unitCode":"ft"},"noDataValue":-999999.0},"values":[\#(Array(repeating: block, count: blocks).joined(separator: ","))],"name":"USGS:04082500:00065:00000"}]}}"#
    }

    func stage(_ rec: URLRecorder) -> LakeUSGSStageClient {
        LakeUSGSStageClient(fetch: { url, _ in rec.add(url); return Self.ok(Self.rdb) }, cache: USGSSiteCache())
    }

    func testUSGSStageIVHistoryWalksWholeYearsUntilTwoEmptyYears() async throws {
        let rec = URLRecorder(), siteRec = URLRecorder()
        let fleet = LakeFleetClients(transport: { url, _, _ in
            rec.add(url)
            switch Self.param(url, "startDT").map({ String($0.prefix(4)) }) ?? "" {
            case "2026": return Self.ok(Self.iv(["2026-11-21T12:00:00.000-06:00"]))
            case "2025": return Self.ok(Self.iv(["2025-03-01T12:00:00.000-06:00"]))
            default: return LakeFeedHTTP.Response(status: 404, body: Data())   // USGS "no data"
            }
        })
        let dPulled = await stage(siteRec).daily(site: "04082500", datum: "NAVD88", stat: "iv", since: nil,
                                                          now: iso("2026-11-22T12:00:00Z"), timeZone: utc, fleet: fleet)
        let d = try XCTUnwrap(dPulled)
        XCTAssertEqual(d.map(\.date), ["2025-03-01", "2026-11-21"])
        XCTAssertEqual(d[0].ft, 745.91, accuracy: 1e-9, "2.00 ft + 743.91 ft")
        let windows = rec.urls.map { (Self.param($0, "startDT") ?? "", Self.param($0, "endDT") ?? "") }
        XCTAssertEqual(windows.map { $0.0 }, ["2026-01-01", "2025-01-01", "2024-01-01", "2023-01-01"], "two empty years end the walk")
        XCTAssertEqual(windows.map { $0.1 }, ["2026-11-22", "2025-12-31", "2024-12-31", "2023-12-31"], "contiguous whole years")
        XCTAssertTrue(rec.urls.allSatisfy { $0.contains("parameterCd=00065") })
    }

    func testUSGSStageHistoryFailsOnAFailedYearOrSeveralSeriesAndHonoursSince() async throws {
        let failing = LakeFleetClients(transport: { url, _, _ in
            Self.param(url, "startDT")?.hasPrefix("2026") == true ? Self.ok(Self.iv(["2026-11-21T12:00:00.000-06:00"])) : LakeFeedHTTP.Response(status: 500, body: Data())
        })
        let f = await stage(URLRecorder()).daily(site: "04082500", datum: "NAVD88", stat: "iv", since: nil, now: iso("2026-11-22T12:00:00Z"), timeZone: utc, fleet: failing)
        XCTAssertNil(f, "a failed year is no silent hole")

        let twoSeries = LakeFleetClients(transport: { _, _, _ in Self.ok(Self.iv(["2026-11-21T12:00:00.000-06:00"], blocks: 2)) })
        let t = await stage(URLRecorder()).daily(site: "04082500", datum: "NAVD88", stat: "iv", since: nil, now: iso("2026-11-22T12:00:00Z"), timeZone: utc, fleet: twoSeries)
        XCTAssertNil(t, "two gage-height series at one site: refused")

        let rec = URLRecorder()
        let bounded = LakeFleetClients(transport: { url, _, _ in rec.add(url); return Self.ok(Self.iv(["2026-11-21T12:00:00.000-06:00"])) })
        let dPulled = await stage(URLRecorder()).daily(site: "04082500", datum: "NAVD88", stat: "iv", since: "2026-11-01",
                                                                now: iso("2026-11-22T12:00:00Z"), timeZone: utc, fleet: bounded)
        let d = try XCTUnwrap(dPulled)
        XCTAssertEqual(d.map(\.date), ["2026-11-21"])
        XCTAssertEqual(rec.urls.count, 1, "since bounds the walk to its year")
        XCTAssertEqual(Self.param(rec.urls[0], "startDT"), "2026-11-01")
    }
}
