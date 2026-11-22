//
//  LakeBrainUSGSWaterDataTests.swift
//  Lake Brain: the USGS Water Data API (v1) readers and the LAKE_USGS_API switch (LakeLevelFeedsUSGSWaterData.swift). No network.
//
//  Fixtures: `tests/fixtures/usgs-waterdata-v1/` are HAND-BUILT from the published OGC API docs, not recordings (see its README).
//  The multi-sensor tests use the REAL 2026-10-07 recordings in `Tests/SectorEngineTests/Fixtures/USGS/fortworth-level-*.json`.
//

import XCTest
@testable import SectorEngine
@testable import LakeBrain

/// A fake v1 transport: answers by URL, records URLs and headers.
final class WaterDataFake: @unchecked Sendable {
    private let lock = NSLock()
    private var seen: [(url: String, headers: [String: String])] = []
    private var pauses = 0
    let route: @Sendable (String, Int) -> LakeFeedHTTP.Response?

    /// `route(url, n)`: `n` is how many earlier requests went to the same URL.
    init(_ route: @escaping @Sendable (String, Int) -> LakeFeedHTTP.Response?) { self.route = route }

    var urls: [String] { lock.lock(); defer { lock.unlock() }; return seen.map(\.url) }
    var headers: [[String: String]] { lock.lock(); defer { lock.unlock() }; return seen.map(\.headers) }
    var pauseCount: Int { lock.lock(); defer { lock.unlock() }; return pauses }

    func client(apiKey: String? = nil, maxPages: Int = 20) -> LakeUSGSWaterDataClient {
        LakeUSGSWaterDataClient(transport: { url, headers, _ in
            self.lock.lock()
            let n = self.seen.filter { $0.url == url }.count
            self.seen.append((url, headers))
            self.lock.unlock()
            return self.route(url, n)
        }, apiKey: apiKey, maxPages: maxPages, pause: { _ in
            self.lock.lock(); self.pauses += 1; self.lock.unlock()
        })
    }
}

final class LineLog: @unchecked Sendable {
    private let lock = NSLock()
    private var all: [String] = []
    func add(_ s: String) { lock.lock(); all.append(s); lock.unlock() }
    var lines: [String] { lock.lock(); defer { lock.unlock() }; return all }
}

final class LakeBrainUSGSWaterDataTests: XCTestCase {

    func iso(_ s: String) -> Date { ISO8601DateFormatter().date(from: s)! }
    let utc = TimeZone(identifier: "UTC")!

    static func v1(_ name: String) throws -> Data {
        try Data(contentsOf: URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("fixtures/usgs-waterdata-v1/\(name)"))
    }
    static func stageFixture(_ name: String) throws -> Data {
        try Data(contentsOf: URL(fileURLWithPath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("fixtures/usgs-stage/\(name)"))
    }
    /// The real 2026-10-07 recordings of the Engine's OGC client tests.
    static func recorded(_ name: String) throws -> Data {
        var u = URL(fileURLWithPath: #filePath)
        for _ in 0..<5 { u = u.deletingLastPathComponent() }
        return try Data(contentsOf: u.appendingPathComponent("Tests/SectorEngineTests/Fixtures/USGS/\(name).json"))
    }

    static func ok(_ d: Data) -> LakeFeedHTTP.Response { LakeFeedHTTP.Response(status: 200, body: d) }
    static func status(_ s: Int) -> LakeFeedHTTP.Response { LakeFeedHTTP.Response(status: s, body: Data()) }

    static func collection(_ features: [String], next: String? = nil) -> Data {
        let links = next.map { #"[{"rel":"next","href":"\#($0)"}]"# } ?? "[]"
        return Data(#"{"type":"FeatureCollection","features":[\#(features.joined(separator: ","))],"links":\#(links)}"#.utf8)
    }
    static func feature(_ ts: String, site: String, param: String, time: String, value: String, stat: String = "00011",
                        unit: String = "ft", qualifier: String = "null") -> String {
        #"{"type":"Feature","id":"x","properties":{"time_series_id":"\#(ts)","monitoring_location_id":"USGS-\#(site)","parameter_code":"\#(param)","statistic_id":"\#(stat)","time":"\#(time)","value":\#(value),"unit_of_measure":"\#(unit)","qualifier":\#(qualifier)}}"#
    }

    // MARK: switch and key

    func testSwitchDefaultsToLegacy() {
        XCTAssertEqual(LakeUSGSAPIMode.fromEnvironment([:]), .legacy)
        XCTAssertEqual(LakeUSGSAPIMode.fromEnvironment(["LAKE_USGS_API": ""]), .legacy)
        XCTAssertEqual(LakeUSGSAPIMode.fromEnvironment(["LAKE_USGS_API": "ogc"]), .legacy, "unknown value: legacy")
        XCTAssertEqual(LakeUSGSAPIMode.fromEnvironment(["LAKE_USGS_API": " V1 "]), .v1)
        XCTAssertEqual(LakeUSGSAPIMode.fromEnvironment(["LAKE_USGS_API": "shadow"]), .shadow)
        XCTAssertEqual(LakeUSGSStageClient(fetch: { _, _ in nil }, cache: USGSSiteCache()).mode, .legacy)
    }

    func testAPIKeyIsAnOptionalHeaderAndNeverInTheURL() async throws {
        XCTAssertNil(LakeUSGSWaterDataClient.live(env: [:]).apiKey)
        XCTAssertEqual(LakeUSGSWaterDataClient.live(env: ["USGS_API_KEY": " "]).headers, [:])
        XCTAssertEqual(LakeUSGSWaterDataClient.live(env: ["USGS_API_KEY": "k-123"]).headers, ["X-Api-Key": "k-123"])
        let empty = try Self.v1("empty.json")
        let fake = WaterDataFake { _, _ in Self.ok(empty) }
        _ = await fake.client(apiKey: "k-123").recentLevel(site: "03351700", parameter: "62614", hours: 24)
        _ = await fake.client().recentLevel(site: "03351700", parameter: "62614", hours: 24)
        XCTAssertEqual(fake.headers, [["X-Api-Key": "k-123"], [:]])
        XCTAssertFalse(fake.urls.contains { $0.contains("k-123") || $0.contains("api_key") })
    }

    // MARK: D1 several series per site

    func recordedFortWorth() throws -> WaterDataFake {
        let cont = try Self.recorded("fortworth-level-continuous"), meta = try Self.recorded("fortworth-level-metadata")
        return WaterDataFake { url, _ in url.contains("/time-series-metadata/") ? Self.ok(meta) : Self.ok(cont) }
    }

    func testRecordedMultiSensorSiteReadsOnlyThePrimarySeries() async throws {
        let fake = try recordedFortWorth()
        let r = await fake.client().recentLevel(site: "08062095", parameter: "00065", hours: 12)
        XCTAssertNil(r.result.error)
        XCTAssertEqual(r.result.observations.count, 47)
        XCTAssertEqual(r.result.observations.last?.ft ?? 0, 7.80, accuracy: 1e-9, "the Primary sensor")
        XCTAssertEqual(r.result.observations.last?.at, iso("2026-10-07T20:00:00Z"))
        XCTAssertFalse(r.result.observations.contains { $0.ft == 12.68 }, "never the secondary sensor, never merged")
        let m = try XCTUnwrap(fake.urls.first { $0.contains("/time-series-metadata/") })
        XCTAssertTrue(m.contains("0a00e4fb42604397be6c101535b01355") && m.contains("79d6eedeb0d44f2890566ef2677f75ff"), m)
    }

    func testRecordedSiteWithTwoPrimarySeriesIsRefused() async throws {
        let r = try await recordedFortWorth().client().recentLevel(site: "08048890", parameter: "00065", hours: 12)
        XCTAssertTrue(r.result.error?.contains("2 marked Primary; ambiguous") ?? false, r.result.error ?? "")
        XCTAssertTrue(r.result.observations.isEmpty)
    }

    func testSeveralSeriesWithoutReadableMetadataAreRefused() async throws {
        let cont = try Self.recorded("fortworth-level-continuous")
        let fake = WaterDataFake { url, _ in url.contains("/time-series-metadata/") ? Self.status(500) : Self.ok(cont) }
        let r = await fake.client().recentLevel(site: "08062095", parameter: "00065", hours: 12)
        XCTAssertTrue(r.result.error?.contains("refused rather than merged") ?? false, r.result.error ?? "")
    }

    func testOneSeriesNeedsNoMetadata() async throws {
        let fake = try recordedFortWorth()
        let r = await fake.client().recentLevel(site: "07332610", parameter: "00065", hours: 12)   // Lk Bonham: one series
        XCTAssertNil(r.result.error)
        XCTAssertFalse(fake.urls.contains { $0.contains("/time-series-metadata/") })
    }

    // MARK: D2 timestamps

    func testTimestampsWithAndWithoutFractionalSeconds() {
        let a = LakeUSGSWaterDataClient.parseTime("2026-10-07T08:30:00+00:00")
        XCTAssertNotNil(a)
        XCTAssertEqual(LakeUSGSWaterDataClient.parseTime("2026-10-07T08:30:00Z"), a)
        XCTAssertEqual(LakeUSGSWaterDataClient.parseTime("2026-10-07T03:30:00.000-05:00"), a)
        XCTAssertNil(LakeUSGSWaterDataClient.parseTime("2026-10-07"))
    }

    // MARK: D4 no data, nulls, sentinels

    func testNullAndSentinelValuesAreSkippedAndQualifiersCounted() async throws {
        let body = Self.collection([
            Self.feature("s", site: "03351700", param: "62614", time: "2026-11-22T09:00:00+00:00", value: #""745.10""#),
            Self.feature("s", site: "03351700", param: "62614", time: "2026-11-22T09:15:00+00:00", value: "null"),
            Self.feature("s", site: "03351700", param: "62614", time: "2026-11-22T09:30:00+00:00", value: #""-999999""#),
            Self.feature("s", site: "03351700", param: "62614", time: "2026-11-22T09:45:00Z", value: "745.12", qualifier: #"["ICE"]"#),
        ])
        let r = await WaterDataFake { _, _ in Self.ok(body) }.client().recentLevel(site: "03351700", parameter: "62614", hours: 2)
        XCTAssertEqual(r.result.observations.map(\.ft), [745.10, 745.12])
        XCTAssertEqual(r.qualifiers, ["ICE": 1])
    }

    func testEmpty200IsNoReadingsLiveAndAnEmptyHistory() async throws {
        let empty = try Self.v1("empty.json")
        let fake = WaterDataFake { _, _ in Self.ok(empty) }
        let c = fake.client()
        let live = await c.recentLevel(site: "03351700", parameter: "62614", hours: 24)
        XCTAssertEqual(live.result.error, "USGS 03351700 62614: no readings")
        let dv = await c.daily(site: "03351700", param: "62614", stat: "dv", offsetFt: 0, since: nil, now: iso("2026-11-22T12:00:00Z"),
                               timeZone: utc, src: "usgs:03351700:62614:dv", singleSeries: false)
        XCTAssertEqual(dv, [])
        let before = fake.urls.count
        let iv = await c.daily(site: "03351700", param: "62614", stat: "iv", offsetFt: 0, since: nil, now: iso("2026-11-22T12:00:00Z"),
                               timeZone: utc, src: "usgs:03351700:62614:iv", singleSeries: false)
        XCTAssertEqual(iv, [])
        XCTAssertEqual(fake.urls.count - before, 2, "two empty years stop the walk, as the legacy 404s did")
    }

    func testBlackoutPageIsAFailureNotData() async throws {
        let html = try Self.v1("blackout.html")
        let c = WaterDataFake { _, _ in Self.ok(html) }.client()
        let live = await c.recentLevel(site: "03351700", parameter: "62614", hours: 24)
        XCTAssertTrue(live.result.error?.contains("unreadable JSON") ?? false, live.result.error ?? "")
        let dv = await c.daily(site: "03351700", param: "62614", stat: "dv", offsetFt: 0, since: nil, now: iso("2026-11-22T12:00:00Z"),
                               timeZone: utc, src: "x", singleSeries: false)
        XCTAssertNil(dv)
    }

    // MARK: paging and rate limit

    func testPagingFollowsNextAndRefusesBeyondThePageLimit() async throws {
        let p1 = try Self.v1("continuous_395540082291600_page1.json"), p2 = try Self.v1("continuous_395540082291600_page2.json")
        let fake = WaterDataFake { url, _ in Self.ok(url.contains("offset=2") ? p2 : p1) }
        let r = await fake.client().recentLevel(site: "395540082291600", parameter: "62614", hours: 24)
        XCTAssertEqual(r.result.observations.map(\.ft), [891.02, 891.03, 891.05])
        XCTAssertEqual(r.qualifiers, ["ICE": 1])
        XCTAssertEqual(fake.urls.count, 2)
        XCTAssertTrue(fake.urls[0].contains("monitoring_location_id=USGS-395540082291600") && fake.urls[0].contains("time=PT24H"), fake.urls[0])
        let capped = await WaterDataFake { url, _ in Self.ok(url.contains("offset=2") ? p2 : p1) }.client(maxPages: 1)
            .recentLevel(site: "395540082291600", parameter: "62614", hours: 24)
        XCTAssertTrue(capped.result.error?.contains("more than 1 pages") ?? false, "a truncated answer is refused, never served")
    }

    func testA429IsRetriedAfterAPauseThenGivesUp() async throws {
        let p2 = try Self.v1("continuous_395540082291600_page2.json")
        let fake = WaterDataFake { _, n in n < 2 ? Self.status(429) : Self.ok(p2) }
        let r = await fake.client().recentLevel(site: "395540082291600", parameter: "62614", hours: 24)
        XCTAssertEqual(r.result.observations.count, 1)
        XCTAssertEqual(fake.pauseCount, 2)
        let never = WaterDataFake { _, _ in Self.status(429) }
        let f = await never.client().recentLevel(site: "395540082291600", parameter: "62614", hours: 24)
        XCTAssertTrue(f.result.error?.contains("HTTP 429") ?? false, f.result.error ?? "")
        XCTAssertEqual(never.urls.count, 3)
    }

    // MARK: D3 daily statistics

    func testDailyStatisticsKeepTheLegacyPrecedence() async throws {
        let d = try Self.v1("daily_01314500_62614.json")
        let fake = WaterDataFake { _, _ in Self.ok(d) }
        let out = await fake.client().daily(site: "01314500", param: "62614", stat: "dv", offsetFt: -0.01, since: nil,
                                            now: iso("2026-11-22T12:00:00Z"), timeZone: utc, src: "usgs:01314500:62614:dv", singleSeries: false)
        let got = try XCTUnwrap(out)
        XCTAssertEqual(got.map(\.date), ["2026-11-18", "2026-11-19", "2026-11-20", "2026-11-21"])
        XCTAssertEqual(got.map(\.ft)[0], 1556.19, accuracy: 1e-9)
        XCTAssertEqual(got.map(\.ft)[1], 1556.30, accuracy: 1e-9, "a null 00003 is filled by 30800")
        XCTAssertEqual(got.map(\.ft)[2], 1556.23, accuracy: 1e-9, "00003 before 30800")
        XCTAssertEqual(got.map(\.ft)[3], 1556.34, accuracy: 1e-9)
        XCTAssertEqual(Set(got.map(\.sourceId)), ["usgs:01314500:62614:dv"])
        let u = try XCTUnwrap(fake.urls.first)
        XCTAssertTrue(u.contains("/daily/items") && u.contains("statistic_id=00003,32400,30800,00001,00002")
                      && u.contains("time=1900-01-01/2026-11-22"), u)
    }

    func testANamedStatisticTakesOnlyThatStatistic() async throws {
        let d = try Self.v1("daily_01314500_62614.json")
        let out = await WaterDataFake { _, _ in Self.ok(d) }.client().daily(site: "01314500", param: "62614", stat: "30800", offsetFt: 0,
            since: nil, now: iso("2026-11-22T12:00:00Z"), timeZone: utc, src: "s", singleSeries: false)
        XCTAssertEqual(out?.map(\.ft), [1556.31, 1556.33, 1556.35])
    }

    func testAStatisticTheAPIDoesNotServeIsRefusedNeverSubstituted() async throws {
        let empty = try Self.v1("empty.json"), meta = try Self.v1("tsmeta_01314500_30800.json")
        let now = iso("2026-11-22T12:00:00Z")
        // 32400 at 01314500: /daily has nothing and time-series-metadata lists no daily 32400 series.
        let none = WaterDataFake { _, _ in Self.ok(empty) }
        let a = await none.client().daily(site: "01314500", param: "62614", stat: "32400", offsetFt: 0, since: "2026-11-01", now: now,
                                          timeZone: utc, src: "s", singleSeries: false)
        XCTAssertNil(a)
        XCTAssertTrue(none.urls.contains { $0.contains("/time-series-metadata/") && $0.contains("statistic_id=32400") })
        // 30800 is served but nothing is new since the last pull: an empty increment, not a refusal.
        let served = WaterDataFake { url, _ in Self.ok(url.contains("/time-series-metadata/") ? meta : empty) }
        let b = await served.client().daily(site: "01314500", param: "62614", stat: "30800", offsetFt: 0, since: "2026-11-21", now: now,
                                            timeZone: utc, src: "s", singleSeries: false)
        XCTAssertEqual(b, [])
        // A full-history pull that is empty is refused even when the series is listed.
        let c = await served.client().daily(site: "01314500", param: "62614", stat: "30800", offsetFt: 0, since: nil, now: now,
                                            timeZone: utc, src: "s", singleSeries: false)
        XCTAssertNil(c)
        // "dv" never asks whether one statistic is served: it merges what exists.
        let dv = await served.client().daily(site: "01314500", param: "62614", stat: "dv", offsetFt: 0, since: "2026-11-21", now: now,
                                             timeZone: utc, src: "s", singleSeries: false)
        XCTAssertEqual(dv, [])
    }

    func testTwoSeriesOfOneDailyStatisticArePickedByPrimaryOrRefused() async throws {
        let body = Self.collection([
            Self.feature("a", site: "10297000", param: "00062", time: "2026-11-20", value: #""1.00""#, stat: "32400"),
            Self.feature("b", site: "10297000", param: "00062", time: "2026-11-20", value: #""9.00""#, stat: "32400"),
        ])
        let meta = Data(#"{"type":"FeatureCollection","features":[{"id":"a","properties":{"primary":"Primary"}},{"id":"b","properties":{"primary":null}}]}"#.utf8)
        let fake = WaterDataFake { url, _ in Self.ok(url.contains("/time-series-metadata/") ? meta : body) }
        let now = iso("2026-11-22T12:00:00Z")
        let picked = await fake.client().daily(site: "10297000", param: "00062", stat: "32400", offsetFt: 4899.97, since: "2026-11-01",
                                               now: now, timeZone: utc, src: "s", singleSeries: false)
        XCTAssertEqual(picked?.first?.ft ?? 0, 4900.97, accuracy: 1e-9)
        let strict = await fake.client().daily(site: "10297000", param: "00062", stat: "32400", offsetFt: 4899.97, since: "2026-11-01",
                                               now: now, timeZone: utc, src: "s", singleSeries: true)
        XCTAssertNil(strict, "the gage-height reader refuses several series outright")
    }

    // MARK: history walk (stat "iv")

    func testInstantaneousHistoryWalksLakeLocalYearsInUTCWindows() async throws {
        let p2 = try Self.v1("continuous_395540082291600_page2.json"), empty = try Self.v1("empty.json")
        let fake = WaterDataFake { url, _ in Self.ok(url.contains("time=2026-") ? p2 : empty) }
        let ny = TimeZone(identifier: "America/New_York")!
        let out = await fake.client().daily(site: "395540082291600", param: "62614", stat: "iv", offsetFt: 0, since: nil,
                                            now: iso("2026-11-22T12:00:00Z"), timeZone: ny, src: "usgs:395540082291600:62614:iv",
                                            singleSeries: false)
        XCTAssertEqual(out?.map(\.date), ["2026-11-22"])
        XCTAssertEqual(fake.urls.count, 3, "2026 with data, then 2025 and 2024 empty")
        XCTAssertTrue(fake.urls[0].contains("time=2026-01-01T05:00:00Z/2026-11-23T04:59:59Z"), fake.urls[0])
        XCTAssertTrue(fake.urls[1].contains("time=2025-01-01T05:00:00Z/2026-01-01T04:59:59Z"), fake.urls[1])
    }

    // MARK: gage height + site altitude (v1)

    func stageClient(mode: LakeUSGSAPIMode, legacy: URLRecorder, v1: WaterDataFake, log: LineLog) throws -> LakeUSGSStageClient {
        let rdb = try Self.stageFixture("04082500_site.rdb"), iv = try Self.stageFixture("04082500_iv_00065.json")
        return LakeUSGSStageClient(fetch: { url, _ in
            legacy.add(url)
            return Self.ok(url.contains("/nwis/site/") ? rdb : iv)
        }, cache: USGSSiteCache(), mode: mode, waterData: v1.client(), shadowLog: { log.add($0) })
    }

    func v1Stage(location: Data? = nil, stage: Data? = nil) throws -> WaterDataFake {
        let loc = try location ?? Self.v1("location_04082500.json"), st = try stage ?? Self.v1("stage_04082500_continuous_00065.json")
        return WaterDataFake { url, _ in Self.ok(url.contains("/monitoring-locations/") ? loc : st) }
    }

    func ref(_ datum: String?) -> LevelSeriesRef {
        LevelSeriesRef(provider: .usgsStage, capability: .directLakeGauge, station: "04082500", series: datum, cadenceMin: 60, lagMin: 60)
    }

    func testV1StageMatchesTheLegacyReader() async throws {
        let legacyRec = URLRecorder(), log = LineLog()
        let legacy = try stageClient(mode: .legacy, legacy: legacyRec, v1: try v1Stage(), log: log)
        let fake = try v1Stage()
        let v1 = try stageClient(mode: .v1, legacy: URLRecorder(), v1: fake, log: log)
        let a = await legacy.recent(ref("NAVD88"), hours: 24), b = await v1.recent(ref("NAVD88"), hours: 24)
        XCTAssertNil(b.error)
        XCTAssertEqual(a.observations, b.observations)
        XCTAssertEqual(b.observations.first?.ft ?? 0, 746.75, accuracy: 1e-9)
        XCTAssertTrue(fake.urls.contains { $0.hasSuffix("/monitoring-locations/items/USGS-04082500?f=json") })
        XCTAssertTrue(fake.urls.contains { $0.contains("/continuous/items") && $0.contains("parameter_code=00065") })
        XCTAssertTrue(log.lines.isEmpty, "only shadow logs")
    }

    func testV1SiteRecordRefusals() async throws {
        let loc = String(decoding: try Self.v1("location_04082500.json"), as: UTF8.self)
        func refusal(_ body: String) -> String? {
            if case .refused(let why) = LakeUSGSWaterDataClient.parseLocation(Data(body.utf8), site: "04082500") { return why }
            return nil
        }
        XCTAssertTrue(refusal(loc.replacingOccurrences(of: #""altitude": 743.91"#, with: #""altitude": null"#))?.contains("no published altitude") ?? false)
        XCTAssertTrue(refusal(loc.replacingOccurrences(of: #""vertical_datum": "NAVD88""#, with: #""vertical_datum": null"#))?.contains("vertical_datum") ?? false)
        XCTAssertTrue(refusal(loc.replacingOccurrences(of: "USGS-04082500\"", with: "USGS-04084445\""))?.contains("not found") ?? false)
        guard case .ok(let d) = LakeUSGSWaterDataClient.parseLocation(Data(loc.utf8), site: "04082500") else { return XCTFail() }
        XCTAssertEqual(d.altitudeFt, 743.91)
        XCTAssertEqual(d.datum, "NAVD88")
        XCTAssertEqual(d.siteType, "LK")
        XCTAssertEqual(d.accuracyFt ?? 0, 0.01, accuracy: 1e-9)

        let log = LineLog()
        let ngvd = Data(loc.replacingOccurrences(of: #""vertical_datum": "NAVD88""#, with: #""vertical_datum": "NGVD29""#).utf8)
        let other = try await stageClient(mode: .v1, legacy: URLRecorder(), v1: try v1Stage(location: ngvd), log: log).recent(ref("NAVD88"), hours: 24)
        XCTAssertTrue(other.error?.contains("datum is NGVD29") ?? false, other.error ?? "")
        let gone = WaterDataFake { _, _ in Self.status(404) }
        let missing = try await stageClient(mode: .v1, legacy: URLRecorder(), v1: gone, log: log).recent(ref("NAVD88"), hours: 24)
        XCTAssertTrue(missing.error?.contains("site record not found") ?? false, missing.error ?? "")
    }

    func testV1StageRefusesSeveralSeriesAndNonFeet() async throws {
        let log = LineLog()
        let two = Self.collection([
            Self.feature("a", site: "04082500", param: "00065", time: "2026-11-22T10:00:00+00:00", value: #""2.84""#),
            Self.feature("b", site: "04082500", param: "00065", time: "2026-11-22T10:00:00+00:00", value: #""9.10""#),
        ])
        let r = try await stageClient(mode: .v1, legacy: URLRecorder(), v1: try v1Stage(stage: two), log: log).recent(ref("NAVD88"), hours: 24)
        XCTAssertTrue(r.error?.contains("sub-locations") ?? false, r.error ?? "")
        let metres = Self.collection([Self.feature("a", site: "04082500", param: "00065", time: "2026-11-22T10:00:00+00:00", value: #""0.87""#, unit: "m")])
        let m = try await stageClient(mode: .v1, legacy: URLRecorder(), v1: try v1Stage(stage: metres), log: log).recent(ref("NAVD88"), hours: 24)
        XCTAssertTrue(m.error?.contains("not feet") ?? false, m.error ?? "")
    }

    // MARK: shadow

    func testShadowStageServesLegacyAndLogsAgreement() async throws {
        let legacyRec = URLRecorder(), log = LineLog()
        let shadow = try stageClient(mode: .shadow, legacy: legacyRec, v1: try v1Stage(), log: log)
        let legacy = try stageClient(mode: .legacy, legacy: URLRecorder(), v1: try v1Stage(), log: LineLog())
        let s = await shadow.recent(ref("NAVD88"), hours: 24), l = await legacy.recent(ref("NAVD88"), hours: 24)
        XCTAssertEqual(s.observations, l.observations)
        XCTAssertEqual(s.error, l.error)
        let lines = log.lines
        XCTAssertTrue(lines.contains { $0.hasPrefix("[usgs-shadow] site=04082500 param=00065 kind=site verdict=agree") }, "\(lines)")
        XCTAssertTrue(lines.contains { $0.hasPrefix("[usgs-shadow] site=04082500 param=00065 kind=live verdict=agree") }, "\(lines)")
    }

    func testShadowServesLegacyEvenWhenV1Disagrees() async throws {
        let log = LineLog()
        let off = Self.collection([Self.feature("a", site: "04082500", param: "00065", time: "2026-11-22T10:45:00+00:00", value: #""3.83""#)])
        let s = try await stageClient(mode: .shadow, legacy: URLRecorder(), v1: try v1Stage(stage: off), log: log).recent(ref("NAVD88"), hours: 24)
        XCTAssertEqual(s.observations.last?.ft ?? 0, 746.74, accuracy: 1e-9, "the legacy value is served")
        XCTAssertTrue(log.lines.contains { $0.contains("kind=live verdict=disagree reason=latest-delta") }, "\(log.lines)")
    }

    func testRoutingCallsOnlyWhatTheSwitchSays() async {
        let calls = LineLog()
        func run(_ m: LakeUSGSAPIMode) async -> Int {
            await LakeUSGSRouting.run(m, legacy: { () -> Int in calls.add("legacy"); return 1 },
                                      v1: { () -> String in calls.add("v1"); return "2" },
                                      adopt: { (s: String) -> Int in Int(s)! }, compare: { (l: Int, o: String) -> String in "cmp \(l) \(o)" },
                                      log: { calls.add($0) })
        }
        let a = await run(.legacy)
        XCTAssertEqual(a, 1); XCTAssertEqual(calls.lines, ["legacy"])
        let b = await run(.v1)
        XCTAssertEqual(b, 2); XCTAssertEqual(calls.lines, ["legacy", "v1"])
        let c = await run(.shadow)
        XCTAssertEqual(c, 1, "shadow returns the legacy answer")
        XCTAssertEqual(calls.lines, ["legacy", "v1", "legacy", "v1", "cmp 1 2"])
    }

    func testLiveAgreementRule() {
        func feed(_ xs: [(String, Double)]) -> FeedResult { FeedResult(observations: xs.map { LevelObservation(at: iso($0.0), ft: $0.1) }, error: nil) }
        let l = feed([("2026-11-22T10:00:00Z", 745.10), ("2026-11-22T11:00:00Z", 745.12)])
        XCTAssertEqual(LakeUSGSShadow.compareLive(legacy: l, ogc: l).verdict, "agree")
        let newer = LakeUSGSShadow.compareLive(legacy: l, ogc: feed([("2026-11-22T10:00:00Z", 745.10), ("2026-11-22T11:00:00Z", 745.12), ("2026-11-22T12:30:00Z", 745.2)]))
        XCTAssertEqual(newer.verdict, "agree"); XCTAssertEqual(newer.reason, "ogc-newer"); XCTAssertEqual(newer.tsDelta, 5400)
        XCTAssertEqual(LakeUSGSShadow.compareLive(legacy: l, ogc: feed([("2026-11-22T11:00:00Z", 745.12), ("2026-11-22T13:30:00Z", 745.2)])).reason, "ogc-newer-over-2h")
        XCTAssertEqual(LakeUSGSShadow.compareLive(legacy: l, ogc: feed([("2026-11-22T10:00:00Z", 745.10)])).reason, "ogc-older")
        XCTAssertEqual(LakeUSGSShadow.compareLive(legacy: l, ogc: feed([("2026-11-22T10:00:00Z", 745.10), ("2026-11-22T11:00:00Z", 745.14)])).reason, "latest-delta")
        XCTAssertEqual(LakeUSGSShadow.compareLive(legacy: .failed("x"), ogc: l).verdict, "legacy-unavailable")
        XCTAssertEqual(LakeUSGSShadow.compareLive(legacy: l, ogc: .failed("x")).reason, "ogc-failed")
    }

    func testDailyAndSiteAgreementRules() {
        func days(_ xs: [(String, Double)]) -> [DailyLevel] { xs.map { DailyLevel(date: $0.0, ft: $0.1, sourceId: "s") } }
        let l = days([("2026-11-19", 1.0), ("2026-11-20", 1.1), ("2026-11-21", 1.2)])
        XCTAssertEqual(LakeUSGSShadow.compareDaily(legacy: l, ogc: l).verdict, "agree")
        XCTAssertEqual(LakeUSGSShadow.compareDaily(legacy: l, ogc: l + days([("2026-11-22", 1.3)])).reason, "ogc-newer")
        XCTAssertEqual(LakeUSGSShadow.compareDaily(legacy: l, ogc: Array(l.prefix(2))).reason, "ogc-older")
        XCTAssertEqual(LakeUSGSShadow.compareDaily(legacy: l, ogc: days([("2026-11-21", 1.2)])).reason, "missing-dates")
        XCTAssertEqual(LakeUSGSShadow.compareDaily(legacy: l, ogc: days([("2026-11-19", 1.0), ("2026-11-20", 1.5), ("2026-11-21", 1.2)])).reason, "common-dates")
        XCTAssertEqual(LakeUSGSShadow.compareDaily(legacy: nil, ogc: l).verdict, "legacy-unavailable")
        XCTAssertEqual(LakeUSGSShadow.compareDaily(legacy: l, ogc: nil).reason, "ogc-failed")

        let a = USGSSiteDatum(site: "04082500", name: nil, siteType: "LK", altitudeFt: 743.91, accuracyFt: 0.01, datum: "NAVD88")
        var b = a; b.datum = " navd88 "
        XCTAssertEqual(LakeUSGSShadow.compareSite(legacy: .ok(a), ogc: .ok(b)).verdict, "agree")
        b.datum = "NGVD29"
        XCTAssertEqual(LakeUSGSShadow.compareSite(legacy: .ok(a), ogc: .ok(b)).verdict, "disagree")
        b = a; b.altitudeFt = 743.95
        XCTAssertEqual(LakeUSGSShadow.compareSite(legacy: .ok(a), ogc: .ok(b)).reason, "altitude")
        XCTAssertEqual(LakeUSGSShadow.compareSite(legacy: .refused("USGS x: site service unreachable"), ogc: .ok(a)).verdict, "legacy-unavailable")
    }

    // MARK: legacy is unchanged

    func testLegacySwitchMakesExactlyTheLegacyRequestsAndAnswers() async throws {
        let dv = Data(#"{"value":{"timeSeries":[{"name":"USGS:01314500:62614:00003","variable":{"noDataValue":-999999.0,"options":{"option":[{"optionCode":"00003"}]}},"values":[{"value":[{"value":"1556.20","dateTime":"2026-11-20T00:00:00.000"}]}]}]}}"#.utf8)
        let rec = URLRecorder(), v1 = WaterDataFake { _, _ in nil }, log = LineLog()
        let fleet = LakeFleetClients(transport: { url, _, _ in rec.add(url); return Self.ok(dv) }, usgsMode: .legacy,
                                     waterData: v1.client(), shadowLog: { log.add($0) })
        let now = iso("2026-11-22T12:00:00Z")
        let out = await fleet.usgsDaily(site: "01314500", param: "62614", stat: "30800", offsetFt: -0.01, since: "2026-11-01", now: now, timeZone: utc)
        XCTAssertEqual(out, LakeFleetClients.parseUSGSDV(dv, offsetFt: -0.01, src: "usgs:01314500:62614:30800"))
        XCTAssertEqual(rec.urls, ["https://waterservices.usgs.gov/nwis/dv/?format=json&sites=01314500&parameterCd=62614&startDT=2026-11-01&endDT=2026-11-22&siteStatus=all&statCd=30800"])
        XCTAssertTrue(v1.urls.isEmpty)
        XCTAssertTrue(log.lines.isEmpty)

        // Shadow: the same legacy request and answer, plus one v1 read and one comparison line.
        let srec = URLRecorder(), sv1 = WaterDataFake { _, _ in Self.ok(Self.collection([])) }, slog = LineLog()
        let shadow = LakeFleetClients(transport: { url, _, _ in srec.add(url); return Self.ok(dv) }, usgsMode: .shadow,
                                      waterData: sv1.client(), shadowLog: { slog.add($0) })
        let s = await shadow.usgsDaily(site: "01314500", param: "62614", stat: "30800", offsetFt: -0.01, since: "2026-11-01", now: now, timeZone: utc)
        XCTAssertEqual(s, out)
        XCTAssertEqual(srec.urls, rec.urls)
        XCTAssertFalse(sv1.urls.isEmpty)
        XCTAssertEqual(slog.lines.count, 1)
        XCTAssertTrue(slog.lines[0].hasPrefix("[usgs-shadow] site=01314500 param=62614 kind=daily verdict=disagree reason=ogc-failed"), slog.lines[0])
    }
}
