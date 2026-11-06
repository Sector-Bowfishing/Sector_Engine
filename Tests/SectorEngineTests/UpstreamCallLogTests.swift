//
//  UpstreamCallLogTests.swift
//  SectorEngineTests
//
//  The upstream call log (Sector_Ops #51 F1): one `[http]` line per outbound
//  call and one `[usgs]` line per USGS box. These lines go to Cloud Logging, so
//  they must never carry a query string (some upstreams put keys there) or an
//  error's text (it can echo the URL).
//

import XCTest
import AsyncHTTPClient
@testable import SectorEngine

final class UpstreamCallLogTests: XCTestCase {

    private let t0 = Date(timeIntervalSince1970: 1_762_448_000)   // 2025-11-06T16:53:20Z

    func testLogLineHasHostPathStatusBytesAndTime() {
        let url = URL(string: "https://api.waterdata.usgs.gov/ogcapi/v1/collections/continuous/items?f=json&bbox=1,2,3,4")!
        let line = HTTP.logLine(url: url, outcome: "200", bytes: 1_067_779, started: t0, now: t0.addingTimeInterval(1.0996))
        XCTAssertEqual(line, "[http] at=2025-11-06T16:53:20.000Z host=api.waterdata.usgs.gov "
                       + "path=/ogcapi/v1/collections/continuous/items status=200 bytes=1067779 ms=1100")
    }

    func testTheQueryStringIsNeverLogged() {
        let url = URL(string: "https://firebaseremoteconfig.googleapis.com/v1/projects/p/remoteConfig?key=SECRET123&x=1")!
        let line = HTTP.logLine(url: url, outcome: "200", bytes: 10, started: t0, now: t0)
        XCTAssertFalse(line.contains("SECRET123"))
        XCTAssertFalse(line.contains("?"))
        XCTAssertTrue(line.contains("path=/v1/projects/p/remoteConfig "))
    }

    func testALongPathIsCapped() {
        let long = "/" + String(repeating: "a", count: 200)
        let line = HTTP.logLine(url: URL(string: "https://example.com\(long)")!, outcome: "200", bytes: 0, started: t0, now: t0)
        XCTAssertTrue(line.contains("path=/" + String(repeating: "a", count: HTTP.maxLoggedPath - 1) + "… "))
    }

    func testAnEmptyPathIsLoggedAsSlash() {
        let line = HTTP.logLine(url: URL(string: "https://example.com")!, outcome: "200", bytes: 0, started: t0, now: t0)
        XCTAssertTrue(line.contains(" path=/ "))
    }

    func testErrorLabelsAreShortAndNeverEchoTheError() {
        XCTAssertEqual(HTTP.errorLabel(CancellationError()), "CANCELLED")
        XCTAssertEqual(HTTP.errorLabel(HTTPClientError.deadlineExceeded), "TIMEOUT")
        XCTAssertEqual(HTTP.errorLabel(HTTPClientError.readTimeout), "READ_TIMEOUT")
        XCTAssertEqual(HTTP.errorLabel(HTTPClientError.connectTimeout), "CONNECT_TIMEOUT")
        struct Leaky: Error, CustomStringConvertible { var description: String { "https://x/?key=SECRET123" } }
        let label = HTTP.errorLabel(Leaky())
        XCTAssertEqual(label, "ERR_Leaky")
        XCTAssertFalse(label.contains("SECRET123"))
    }

    func testUSGSLineNamesTheBoxAndWhichAPIAnswered() {
        let line = WaterLevelService.usgsLogLine(codes: "63680", box: 0.25, api: "legacy-after-ogc-TIMEOUT", outcome: "ok",
                                                 series: 0, started: t0, now: t0.addingTimeInterval(8.0))
        XCTAssertEqual(line, "[usgs] param=63680 box=0.25 api=legacy-after-ogc-TIMEOUT outcome=ok series=0 ms=8000")
    }
}
