//
//  LakeBrainCOOPSTests.swift
//  Lake Brain: the NOAA CO-OPS Great Lakes water-level reader (LakeLevelFeedsCOOPS.swift). No network.
//
//  Fixtures (tests/fixtures/coops/) have the datagetter JSON shape (`metadata{id,name,lat,lon}`, `data[{t,v,s,f,q}]`,
//  `{"error":{"message"}}`). Station, keys, flag layout and the values of the unflagged rows were read from the live API on
//  2026-11-22 (Calumet Harbor 9087044: water_level latest 578.537 at 06:30Z, daily_mean 2026-10-01..03, hourly_height
//  2026-11-01 00..03Z). They are transcribed, not byte-for-byte captures (the session's shell could not reach the host); the
//  empty-value and flagged rows were added to exercise the traps.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

/// Records every URL a fake transport is asked for.
final class URLRecorder: @unchecked Sendable {
    private let lock = NSLock()
    private var seen: [String] = []
    func add(_ u: String) { lock.lock(); seen.append(u); lock.unlock() }
    var urls: [String] { lock.lock(); defer { lock.unlock() }; return seen }
}

final class LakeBrainCOOPSTests: XCTestCase {

    let chicago = TimeZone(identifier: "America/Chicago")!
    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }

    static func fixture(_ name: String) throws -> Data {
        try Data(contentsOf: URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("fixtures/coops/\(name)"))
    }

    func client(_ rec: URLRecorder, _ answer: @escaping @Sendable (String) -> LakeFeedHTTP.Response?) -> LakeCOOPSClient {
        LakeCOOPSClient(fetch: { url in rec.add(url); return answer(url) }, gate: HADSGate(), gapSeconds: 0)
    }

    static func ok(_ d: Data) -> LakeFeedHTTP.Response { LakeFeedHTTP.Response(status: 200, body: d) }

    // MARK: parser

    func testWaterLevelDropsEmptyFlatLineAndLimitRowsAndKeepsRateOfChange() throws {
        guard case .rows(let rows) = LakeCOOPSClient.parse(try Self.fixture("9087044_water_level.json"), station: "9087044", product: "water_level") else {
            return XCTFail("expected rows")
        }
        XCTAssertEqual(rows.map(\.v), [578.592, 578.579, 578.566, 578.551, 578.544, 578.537], "empty v, F (flat-line) and L (limit) rows dropped; R kept")
        let obs = LakeCOOPSClient.observations(rows)
        XCTAssertEqual(obs.last?.at, iso("2026-11-22T06:30:00Z"), "stamps are GMT")
    }

    func testHourlyHeightAndDailyMeanUseTheTwoFlagLayout() throws {
        guard case .rows(let h) = LakeCOOPSClient.parse(try Self.fixture("9087044_hourly_height.json"), station: "9087044", product: "hourly_height") else {
            return XCTFail("expected rows")
        }
        XCTAssertEqual(h.map(\.v), [579.16, 579.006, 578.957, 578.99])
        XCTAssertTrue(LakeCOOPSClient.flagged("0,1", q: nil), "I,L: limit")
        XCTAssertFalse(LakeCOOPSClient.flagged("1,0", q: nil), "inferred is kept")
        XCTAssertFalse(LakeCOOPSClient.flagged("0,0,0,1", q: "v"), "verified I,F,R,T: T is not a limit flag")
        XCTAssertTrue(LakeCOOPSClient.flagged("0,0,0,1", q: "p"))
    }

    func testErrorsNoDataAndWrongStation() throws {
        guard case .noData = LakeCOOPSClient.parse(try Self.fixture("no_data.json"), station: "9087044", product: "daily_mean") else {
            return XCTFail("'No data was found' is an empty window")
        }
        let tidal = #"{"error":{"message":"Wrong Datum: Datum IGLD is only available for Great Lakes stations"}}"#
        guard case .failed(let why) = LakeCOOPSClient.parse(Data(tidal.utf8), station: "8724580", product: "water_level") else { return XCTFail() }
        XCTAssertTrue(why.contains("8724580") && why.contains("IGLD"))
        guard case .failed = LakeCOOPSClient.parse(try Self.fixture("9087044_water_level.json"), station: "9063020", product: "water_level") else {
            return XCTFail("a response for another station is refused")
        }
        guard case .failed = LakeCOOPSClient.parse(Data("<html>".utf8), station: "9087044", product: "water_level") else { return XCTFail() }
    }

    // MARK: live

    func testLiveAsksIGLDFeetGMTAndIdentifiesItself() async throws {
        let rec = URLRecorder(), data = try Self.fixture("9087044_water_level.json")
        let c = client(rec) { _ in Self.ok(data) }
        let ref = LevelSeriesRef(provider: .coops, capability: .directLakeGauge, station: "9087044", series: nil, cadenceMin: 60, lagMin: 60)
        let r = await c.recent(ref, hours: 192)
        XCTAssertNil(r.error)
        XCTAssertEqual(r.observations.count, 6)
        XCTAssertEqual(r.observations.last?.ft, 578.537)
        let u = try XCTUnwrap(rec.urls.first)
        for part in ["product=water_level", "station=9087044", "datum=IGLD", "units=english", "time_zone=gmt", "format=json",
                     "application=Sector_LakeBrain", "range=192"] {
            XCTAssertTrue(u.contains(part), "\(part) missing from \(u)")
        }
        XCTAssertEqual(ref.sourceId, "coops:9087044:water_level")
        XCTAssertEqual(ref.providerName, "NOAA CO-OPS")
    }

    func testLiveRefusesVerifiedOnlyProductsAndBadStationsBeforeAnyRequest() async {
        let rec = URLRecorder()
        let c = client(rec) { _ in nil }
        var ref = LevelSeriesRef(provider: .coops, capability: .directLakeGauge, station: "9087044", series: "hourly_height", cadenceMin: 60, lagMin: 60)
        let h = await c.recent(ref, hours: 48)
        XCTAssertTrue(h.error?.contains("verified-only") ?? false)
        ref.series = nil; ref.station = "CHII2"
        let bad = await c.recent(ref, hours: 48)
        XCTAssertNotNil(bad.error)
        XCTAssertTrue(rec.urls.isEmpty, "refused before a request")
    }

    func testLiveFailuresAreErrors() async {
        let rec = URLRecorder()
        let ref = LevelSeriesRef(provider: .coops, capability: .directLakeGauge, station: "9087044", series: nil, cadenceMin: 60, lagMin: 60)
        let down = await client(rec) { _ in nil }.recent(ref, hours: 48)
        XCTAssertEqual(down.error, "CO-OPS 9087044 unreachable")
        let http = await client(rec) { _ in LakeFeedHTTP.Response(status: 503, body: Data()) }.recent(ref, hours: 48)
        XCTAssertEqual(http.error, "CO-OPS 9087044 water_level: HTTP 503")
        let empty = await client(rec) { _ in Self.ok(Data(#"{"error":{"message":"No data was found. This product may not be offered at this station at the requested time."}}"#.utf8)) }
            .recent(ref, hours: 48)
        XCTAssertNotNil(empty.error)
    }

    // MARK: history

    func testHistoryIsVerifiedDailyMeansThenLakeLocalMediansOfThePreliminaryTail() async throws {
        let rec = URLRecorder()
        let dm = try Self.fixture("9087044_daily_mean.json"), wl = try Self.fixture("9087044_water_level.json"), none = try Self.fixture("no_data.json")
        let c = client(rec) { url in
            if url.contains("product=daily_mean") { return Self.ok(url.contains("begin_date=20170101") ? dm : none) }
            return Self.ok(wl)
        }
        let d = try XCTUnwrap(await c.daily(station: "9087044", since: nil, now: iso("2026-11-22T12:00:00Z"), timeZone: chicago))
        XCTAssertEqual(d.map(\.date), ["2026-10-01", "2026-10-02", "2026-10-03", "2026-11-21", "2026-11-22"])
        XCTAssertEqual(d.prefix(3).map(\.ft), [579.383, 579.478, 579.314])
        XCTAssertEqual(Set(d.prefix(3).map(\.sourceId)), ["coops:9087044:daily_mean"])
        // 05:42Z / 05:48Z are 23:42 / 23:48 CST on the 21st; 06:00Z .. 06:30Z fall on the 22nd
        XCTAssertEqual(d[3].ft, (578.592 + 578.579) / 2, accuracy: 1e-9)
        XCTAssertEqual(d[4].ft, (578.551 + 578.544) / 2, accuracy: 1e-9)
        XCTAssertEqual(d[4].sourceId, "coops:9087044:water_level")
        let urls = rec.urls
        XCTAssertEqual(urls.filter { $0.contains("product=daily_mean") }.count, 2, "newest 10-year chunk, then one empty chunk ends the walk")
        XCTAssertTrue(urls.filter { $0.contains("product=daily_mean") }.allSatisfy { $0.contains("time_zone=lst") }, "daily_mean must be asked in lst")
        let tail = urls.filter { $0.contains("product=water_level") }
        XCTAssertEqual(tail.count, 2, "Oct 4 .. now in 31-day windows")
        XCTAssertTrue(tail[0].contains("begin_date=20261004%2005:00"), tail[0])
    }

    func testHistoryFailsWholeOnAnyFailedRequest() async throws {
        let rec = URLRecorder(), dm = try Self.fixture("9087044_daily_mean.json")
        let c = client(rec) { url in url.contains("product=daily_mean") ? Self.ok(dm) : LakeFeedHTTP.Response(status: 500, body: Data()) }
        let d = await c.daily(station: "9087044", since: "2026-11-01", now: iso("2026-11-22T12:00:00Z"), timeZone: chicago)
        XCTAssertNil(d, "a failed tail window is no silent hole")
    }

    func testIncrementalHistoryStartsAtSince() async throws {
        let rec = URLRecorder(), wl = try Self.fixture("9087044_water_level.json"), none = try Self.fixture("no_data.json")
        let c = client(rec) { url in Self.ok(url.contains("product=daily_mean") ? none : wl) }
        let d = try XCTUnwrap(await c.daily(station: "9087044", since: "2026-11-01", now: iso("2026-11-22T12:00:00Z"), timeZone: chicago))
        XCTAssertEqual(d.map(\.date), ["2026-11-21", "2026-11-22"])
        let dmURL = try XCTUnwrap(rec.urls.first { $0.contains("product=daily_mean") })
        XCTAssertTrue(dmURL.contains("begin_date=20261101") && dmURL.contains("end_date=20261122"), dmURL)
        XCTAssertEqual(rec.urls.filter { $0.contains("product=daily_mean") }.count, 1)
    }

    // MARK: types

    func testHistorySourceDecodesFromTheGeneratedTable() throws {
        let h = try JSONDecoder().decode(LakeGeneratedBindings.Record.Hist.self, from: Data(#"{"kind":"coopsDaily","station":"9087044"}"#.utf8))
        XCTAssertEqual(LakeGeneratedBindings.history(h), .coopsDaily(station: "9087044"))
        XCTAssertTrue(LakeHistorySource.coopsDaily(station: "9087044").profileDescription.hasPrefix("coops:9087044"))
    }

    func testNoLakeIsBoundToCOOPS() {
        for b in LakeSourceBindings.all {
            XCTAssertFalse(b.live.contains { $0.provider == .coops }, b.lakeId)
            XCTAssertFalse(b.history.contains { if case .coopsDaily = $0 { return true } else { return false } }, b.lakeId)
        }
    }
}
