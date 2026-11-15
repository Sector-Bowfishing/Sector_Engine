//
//  LakesReadyWindTests.swift
//  SectorEngineTests
//
//  Sector_Engine #158 (owner approval on Sector_Ops #51, 2026-11-11 ~23:40Z): `GET /lakes/ready` adds a lake-wide `wind`
//  layer, computed by the Engine from its Open-Meteo forecast at the lake's point and labeled ESTIMATE. Wind never lists a
//  lake; one request covers every point; the cache bounds the cost; a slow forecast never holds the response. No test here
//  touches the network: the fetch is a fake.
//

import XCTest
@testable import SectorEngine

final class LakesReadyWindTests: XCTestCase {

    static let now = LakesReadyAPITests.now   // 2026-11-10T15:30:00Z
    static let h14 = 1794319200.0, h15 = 1794322800.0, h16 = 1794326400.0, h17 = 1794330000.0
    static let h03 = 1794366000.0, h04 = 1794369600.0

    /// One Open-Meteo location (`timeformat=unixtime`).
    static func location(_ hours: [(Double, Double?, Double?)]) -> String {
        func list(_ v: [Double?]) -> String { "[" + v.map { $0.map { String($0) } ?? "null" }.joined(separator: ",") + "]" }
        return """
        {"latitude":41.0,"longitude":-81.0,"utc_offset_seconds":0,"timezone":"GMT",
         "hourly_units":{"time":"unixtime","wind_speed_10m":"mp/h","wind_direction_10m":"°"},
         "hourly":{"time":\(list(hours.map { $0.0 })),"wind_speed_10m":\(list(hours.map { $0.1 })),
                   "wind_direction_10m":\(list(hours.map { $0.2 }))}}
        """
    }

    static func forecast(_ hours: [(Double, Double?, Double?)]) -> LakeWindForecast {
        LakeWind.parse(Data(location(hours).utf8), count: 1)![0]!
    }

    /// The golden scenario's wind: Berlin has a past hour, three hours in the window and one past the 12-hour cut; Canyon only
    /// the current hour; Flathead none (listed without wind); Guntersville has wind but is not ready, so it is not listed.
    static let goldenWind: [String: LakeWindForecast] = [
        "Berlin Lake|OH": forecast([(h14, 7.0, 210), (h15, 9.43, 225.4), (h16, 11.2, 230), (h17, 12.8, 240), (h04, 20, 250)]),
        "Canyon Lake|TX": forecast([(h15, 4.6, 160)]),
        "Guntersville|AL": forecast([(h15, 8, 180)]),
    ]

    // MARK: parse

    func testParseReadsOneLocationOrSeveral() throws {
        let one = try XCTUnwrap(LakeWind.parse(Data(Self.location([(Self.h15, 5, 90)]).utf8), count: 1))
        XCTAssertEqual(one.count, 1)
        let two = "[\(Self.location([(Self.h15, 5, 90)])),{\"latitude\":1}]"
        let parsed = try XCTUnwrap(LakeWind.parse(Data(two.utf8), count: 2))
        XCTAssertNotNil(parsed[0])
        XCTAssertNil(parsed[1], "a location without hourly wind has no forecast")
        XCTAssertNil(LakeWind.parse(Data(two.utf8), count: 3), "a response for another number of points is a failure")
        XCTAssertNil(LakeWind.parse(Data("nope".utf8), count: 1))
        XCTAssertNil(LakeWind.parse(Data("[1,2]".utf8), count: 2))
    }

    func testParseDropsUnusableHoursAndRounds() throws {
        let f = Self.forecast([(Self.h14 + 60, 5, 90), (Self.h15, 9.46, 359.6), (Self.h16, -1, 90), (Self.h17, 300, 90),
                               (Self.h03, nil, 90), (Self.h04, 5, 361)])
        XCTAssertEqual(f.samples, [LakeWindSample(time: Date(timeIntervalSince1970: Self.h15), speedMph: 9.5, fromDeg: 0)],
                       "off-the-hour, negative, impossible, missing and out-of-range hours are dropped; 359.6° is 0°")
        XCTAssertNil(LakeWind.parse(Data(Self.location([(Self.h15, nil, nil)]).utf8), count: 1)?[0] ?? nil)
    }

    // MARK: layer

    func testLayerIsTheCurrentHourAndTheNextTwelve() throws {
        let layer = try XCTUnwrap(Self.goldenWind["Berlin Lake|OH"]?.layer(now: Self.now))
        XCTAssertEqual(layer.status, "ESTIMATE")
        XCTAssertEqual(layer.asOf, "2026-11-10T15:00:00Z")
        XCTAssertEqual(layer.speedMph, 9.4)
        XCTAssertEqual(layer.fromDeg, 225)
        XCTAssertEqual(layer.hourly.map(\.time), ["2026-11-10T15:00:00Z", "2026-11-10T16:00:00Z", "2026-11-10T17:00:00Z"],
                       "the past hour and the hour 13 h later are left out")
        XCTAssertEqual(layer.hourly[0], ReadyWindHour(time: layer.asOf, speedMph: layer.speedMph, fromDeg: layer.fromDeg))
        let late = Self.forecast([(Self.h15, 5, 90), (Self.h03, 6, 100), (Self.h04, 7, 110)])
        XCTAssertEqual(late.layer(now: Self.now)?.hourly.last?.time, "2026-11-11T03:00:00Z", "12 h after the current hour is kept")
    }

    func testNoValueForTheCurrentHourIsNoLayer() {
        XCTAssertNil(Self.forecast([(Self.h16, 5, 90), (Self.h17, 6, 90)]).layer(now: Self.now), "no current hour: no wind")
        XCTAssertNil(Self.forecast([(Self.h14, 5, 90)]).layer(now: Self.now), "only the past: no wind")
    }

    // MARK: point and request

    func testPointIsTheBBoxCentreElseTheCentroid() {
        let c = ReadyLakeCentroid(lat: 34.123, lon: -86.456)
        let withBox = ReadyLake(lakeId: "Guntersville|AL", name: "Guntersville", centroid: c,
                                extent: ReadyLakeExtent(bbox: ReadyLakeBBox(west: -86.4, south: 34.28, east: -85.62, north: 35.04),
                                                        confidence: "HIGH"),
                                layers: ReadyLakeLayers(clarity: nil, waterTemp: nil, level: nil))
        XCTAssertEqual(LakeWindPoint.of(withBox), LakeWindPoint(lat: 34.66, lon: -86.01))
        XCTAssertEqual(LakeWindPoint.of(withBox).key, "34.66,-86.01")
        let without = ReadyLake(lakeId: "Guntersville|AL", name: "Guntersville", centroid: c, extent: nil,
                                layers: ReadyLakeLayers(clarity: nil, waterTemp: nil, level: nil))
        XCTAssertEqual(LakeWindPoint.of(without).key, "34.12,-86.46")
    }

    func testOneRequestForEveryPointOnTheBestMatchModelInUTC() {
        let q = LakeWind.queryItems([LakeWindPoint(lat: 41.03, lon: -81.0), LakeWindPoint(lat: 29.87, lon: -98.25)])
        let d = Dictionary(uniqueKeysWithValues: q.map { ($0.name, $0.value ?? "") })
        XCTAssertEqual(d["latitude"], "41.03,29.87")
        XCTAssertEqual(d["longitude"], "-81.00,-98.25")
        XCTAssertEqual(d["hourly"], "wind_speed_10m,wind_direction_10m")
        XCTAssertEqual(d["wind_speed_unit"], "mph")
        XCTAssertEqual(d["timezone"], "GMT")
        XCTAssertEqual(d["timeformat"], "unixtime")
        XCTAssertNil(d["models"], "no model parameter: best_match, the Wind Brain's tonight model (WS-5)")
        XCTAssertEqual(WindOutlookModelOutputAPI.tonightModel, "best_match")
    }

    // MARK: response

    func testWindIsAddedToListedLakesOnlyAndNeverListsOne() async throws {
        let got = await LakesReadyAPI.response(config: LakesReadyAPITests.on,
                                               reader: LakesReadyAPITests.Recording(["customer/lakes": LakesReadyAPITests.subtree]),
                                               extents: LakesReadyAPITests.extents, wind: Self.goldenWind,
                                               levelEligibility: LakesReadyAPITests.levelOn, now: Self.now)
        let out = try XCTUnwrap(got)
        XCTAssertEqual(out.lakes.map(\.lakeId), ["Berlin Lake|OH", "Canyon Lake|TX", "Flathead Lake|MT"],
                       "Guntersville has wind but no ready copy: not listed")
        XCTAssertEqual(out.lakes[0].layers.wind?.speedMph, 9.4)
        XCTAssertEqual(out.lakes[1].layers.wind?.hourly.count, 1)
        XCTAssertNil(out.lakes[2].layers.wind)
        XCTAssertTrue(ReadyLakeLayers(clarity: nil, waterTemp: nil, level: nil,
                                      wind: Self.goldenWind["Berlin Lake|OH"]!.layer(now: Self.now)).isEmpty,
                      "a wind layer alone does not make a lake ready")

        let none = await LakesReadyAPI.response(config: LakesReadyAPITests.on, reader: nil, wind: Self.goldenWind, now: Self.now)
        XCTAssertEqual(none?.lakes, [], "no reader: still no lakes, whatever the wind")
    }

    /// Answers every request with a forecast per point (an object for one point, an array for several); records each request.
    final class FakeForecast: @unchecked Sendable {
        private let lock = NSLock()
        private var _requests: [[String: String]] = []
        private var _failing = false
        let delayNanos: UInt64
        init(delayNanos: UInt64 = 0) { self.delayNanos = delayNanos }
        var requests: [[String: String]] { lock.lock(); defer { lock.unlock() }; return _requests }
        func setFailing(_ v: Bool) { lock.lock(); _failing = v; lock.unlock() }
        func fetch(_ q: [URLQueryItem]) async throws -> Data {
            let d = Dictionary(uniqueKeysWithValues: q.map { ($0.name, $0.value ?? "") })
            lock.lock(); _requests.append(d); let failing = _failing; lock.unlock()
            if delayNanos > 0 { try await Task.sleep(nanoseconds: delayNanos) }
            if failing { throw WeatherError.requestFailed }
            let n = d["latitude"]!.split(separator: ",").count
            let one = LakesReadyWindTests.location([(LakesReadyWindTests.h15, 6.5, 200), (LakesReadyWindTests.h16, 7.5, 210)])
            return Data((n == 1 ? one : "[" + Array(repeating: one, count: n).joined(separator: ",") + "]").utf8)
        }
    }

    final class Clock: @unchecked Sendable { var t = Date(timeIntervalSince1970: 0) }

    func cache(_ f: FakeForecast, clock: Clock) -> LakeWindCache {
        LakeWindCache(fetch: { try await f.fetch($0) }, ttl: 1800, maxAge: 3 * 3600, failureTTL: 60, clock: { clock.t })
    }

    func serverResponse(_ winds: LakeWindCache?, budget: Double = LakesReadyAPI.windBudget,
                        config: LakesReadyConfig = LakesReadyAPITests.on) async -> LakesReadyResponse? {
        let extents = LakeRegistryExtentCache(url: URL(string: "https://example.invalid/x")!,
                                              fetch: { _ in Data(LakesReadyAPITests.registryIndex.utf8) })
        return await LakesReadyAPI.response(config: config,
                                            cache: LakesReadySnapshotCache(reader: LakesReadyAPITests.Recording(
                                                ["customer/lakes": LakesReadyAPITests.subtree])),
                                            extents: extents, winds: winds, windBudget: budget,
                                            levelEligibility: LakesReadyAPITests.levelOn, now: Self.now)
    }

    func testServerFormFetchesEveryListedLakeInOneRequest() async throws {
        let f = FakeForecast()
        let got = await serverResponse(cache(f, clock: Clock()))
        let out = try XCTUnwrap(got)
        XCTAssertEqual(f.requests.count, 1)
        // Berlin and Flathead from their registry boxes, Canyon (LOW confidence: no extent) from its centroid.
        XCTAssertEqual(f.requests[0]["latitude"], "41.03,29.87,47.90")
        XCTAssertEqual(f.requests[0]["longitude"], "-81.02,-98.25,-114.15")
        for lake in out.lakes {
            XCTAssertEqual(lake.layers.wind, ReadyWindLayer(status: "ESTIMATE", asOf: "2026-11-10T15:00:00Z", speedMph: 6.5, fromDeg: 200,
                                                            hourly: [ReadyWindHour(time: "2026-11-10T15:00:00Z", speedMph: 6.5, fromDeg: 200),
                                                                     ReadyWindHour(time: "2026-11-10T16:00:00Z", speedMph: 7.5, fromDeg: 210)]))
        }
        let fields = try PhoneContractTests.loadContract(LakesReadyAPITests.contractFile)
        let doc = try JSONSerialization.jsonObject(with: SectorEngineAPI.makeEncoder().encode(out))
        XCTAssertEqual(PhoneContractTests.validate(doc, fields), [])
    }

    func testNoWindCacheOrFlagOffFetchesNoForecast() async throws {
        let f = FakeForecast()
        let off = await serverResponse(cache(f, clock: Clock()), config: LakesReadyConfig(enabled: false))
        XCTAssertNil(off)
        let plainGot = await serverResponse(nil)
        let plain = try XCTUnwrap(plainGot)
        XCTAssertTrue(plain.lakes.allSatisfy { $0.layers.wind == nil })
        XCTAssertEqual(f.requests.count, 0)
    }

    func testASlowForecastNeverHoldsTheResponse() async throws {
        let f = FakeForecast(delayNanos: 2_000_000_000)
        let started = Date()
        let got = await serverResponse(cache(f, clock: Clock()), budget: 0.2)
        let out = try XCTUnwrap(got)
        XCTAssertLessThan(Date().timeIntervalSince(started), 1.5)
        XCTAssertEqual(out.lakes.count, 3, "the lakes are still listed")
        XCTAssertTrue(out.lakes.allSatisfy { $0.layers.wind == nil }, "past the budget: no wind")
    }

    // MARK: cache

    func testCacheFetchesOncePerTTLAndDeduplicatesPoints() async {
        let f = FakeForecast(), clock = Clock()
        let c = cache(f, clock: clock)
        let a = LakeWindPoint(lat: 41.03, lon: -81.0), b = LakeWindPoint(lat: 29.87, lon: -98.25)
        let first = await c.forecasts(for: [a, b, a])
        XCTAssertEqual(Set(first.keys), [a.key, b.key])
        XCTAssertEqual(f.requests.count, 1)
        XCTAssertEqual(f.requests[0]["latitude"], "41.03,29.87", "a point asked for twice is fetched once")
        clock.t = clock.t.addingTimeInterval(1799)
        _ = await c.forecasts(for: [a, b])
        XCTAssertEqual(f.requests.count, 1, "inside the TTL: no new request")
        let cNew = LakeWindPoint(lat: 47.87, lon: -114.11)
        _ = await c.forecasts(for: [a, cNew])
        XCTAssertEqual(f.requests.count, 2)
        XCTAssertEqual(f.requests[1]["latitude"], "47.87", "only the point without a forecast is fetched")
        clock.t = clock.t.addingTimeInterval(2)
        _ = await c.forecasts(for: [a, b])
        XCTAssertEqual(f.requests[2]["latitude"], "41.03,29.87", "after the TTL both are fetched again, in one request")
    }

    func testAFailureIsRetriedAfterAMinuteAndTheLastGoodForecastIsServedMeanwhile() async {
        let f = FakeForecast(), clock = Clock()
        let c = cache(f, clock: clock)
        let a = LakeWindPoint(lat: 41.03, lon: -81.0)
        _ = await c.forecasts(for: [a])
        f.setFailing(true)
        clock.t = clock.t.addingTimeInterval(1800)
        let during = await c.forecasts(for: [a])
        XCTAssertNotNil(during[a.key], "a failed refresh keeps the last good forecast")
        XCTAssertEqual(f.requests.count, 2)
        clock.t = clock.t.addingTimeInterval(30)
        _ = await c.forecasts(for: [a])
        XCTAssertEqual(f.requests.count, 2, "within a minute of a failure: no new request")
        clock.t = clock.t.addingTimeInterval(31)
        _ = await c.forecasts(for: [a])
        XCTAssertEqual(f.requests.count, 3)
        clock.t = Date(timeIntervalSince1970: 3 * 3600)
        let expired = await c.forecasts(for: [a])
        XCTAssertNil(expired[a.key], "a forecast older than 3 h is not served")

        let down = FakeForecast()
        down.setFailing(true)
        let none = await cache(down, clock: Clock()).forecasts(for: [a])
        XCTAssertEqual(none, [:], "never fetched: no forecast")
    }

    func testConcurrentRequestsShareOneFetch() async {
        let f = FakeForecast(delayNanos: 200_000_000)
        let c = cache(f, clock: Clock())
        let a = LakeWindPoint(lat: 41.03, lon: -81.0)
        let counts = await withTaskGroup(of: Int.self) { group -> [Int] in
            for _ in 0..<8 { group.addTask { await c.forecasts(for: [a]).count } }
            var out: [Int] = []
            for await n in group { out.append(n) }
            return out
        }
        XCTAssertEqual(counts, Array(repeating: 1, count: 8))
        XCTAssertEqual(f.requests.count, 1)
    }

    func testManyPointsAreSplitIntoRequestsOfAHundred() async {
        let f = FakeForecast()
        let c = cache(f, clock: Clock())
        let points = (0..<150).map { LakeWindPoint(lat: 30 + Double($0) / 100, lon: -90) }
        let got = await c.forecasts(for: points)
        XCTAssertEqual(got.count, 150)
        XCTAssertEqual(f.requests.map { $0["latitude"]!.split(separator: ",").count }.sorted(), [50, 100])
    }
}
