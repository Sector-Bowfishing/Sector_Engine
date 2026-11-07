//
//  USGSParallelBoxesCacheTests.swift
//  SectorEngineTests
//
//  Sector_Ops #51 F3 + F4: the USGS box sizes run at once but are decided
//  smallest-first (the same answer the old one-after-another loop gave), and
//  per-query readings are cached for 15 min with a 6 h last-good fallback.
//

import XCTest
@testable import SectorEngine

final class USGSParallelBoxesCacheTests: XCTestCase {

    private static func reading(_ site: String, lat: Double = 34.4, lon: Double = -86.3) -> WaterLevelReading {
        WaterLevelReading(siteCode: site, siteName: site, parameterCode: "00060", parameterName: "Discharge", value: 1,
                          unit: "ft3/s", dateTime: Date(timeIntervalSince1970: 0), latitude: lat, longitude: lon,
                          trend: .steady, change: 0)
    }

    private struct Boom: Error {}

    private let found: @Sendable ([WaterLevelReading]) -> WaterLevelService.BoxDecision = { rs in
        rs.isEmpty ? .next : .done(rs[0])
    }

    // MARK: F3: decided in box order

    func testTheSmallestBoxWithAGaugeWinsEvenIfItAnswersLast() async throws {
        let got = try await WaterLevelService.firstAcrossRadii([0.25, 1.0, 2.5], fetch: { r in
            if r == 0.25 { try await Task.sleep(nanoseconds: 50_000_000); return [Self.reading("small")] }
            return [Self.reading(r == 1.0 ? "mid" : "big")]
        }, decide: found)
        XCTAssertEqual(got?.siteCode, "small")
    }

    func testEmptySmallBoxFallsThroughToTheNextBox() async throws {
        let got = try await WaterLevelService.firstAcrossRadii([0.25, 1.0, 2.5], fetch: { r in
            r == 0.25 ? [] : [Self.reading(r == 1.0 ? "mid" : "big")]
        }, decide: found)
        XCTAssertEqual(got?.siteCode, "mid")
    }

    func testAnErrorInALargerBoxDoesNotMatterOnceASmallerBoxAnswered() async throws {
        let got = try await WaterLevelService.firstAcrossRadii([0.25, 1.0, 2.5], fetch: { r in
            if r == 2.5 { throw Boom() }
            return r == 0.25 ? [Self.reading("small")] : []
        }, decide: found)
        XCTAssertEqual(got?.siteCode, "small")
    }

    func testAnErrorIsThrownWhenEverySmallerBoxWasEmpty() async {
        do {
            _ = try await WaterLevelService.firstAcrossRadii([0.25, 1.0, 2.5], fetch: { r in
                if r == 1.0 { throw Boom() }
                return r == 0.25 ? [] : [Self.reading("big")]
            }, decide: found)
            XCTFail("expected the 1° box's error, as the sequential loop threw it")
        } catch { XCTAssertTrue(error is Boom) }
    }

    func testATooFarGaugeStopsTheSearchWithNil() async throws {
        let got = try await WaterLevelService.firstAcrossRadii([0.25, 1.0], fetch: { _ in [Self.reading("far")] },
                                                               decide: { _ in .done(nil) })
        XCTAssertNil(got)
    }

    func testNothingAnywhereIsNil() async throws {
        let got = try await WaterLevelService.firstAcrossRadii([0.25, 1.0, 2.5], fetch: { _ in [] }, decide: found)
        XCTAssertNil(got)
    }

    func testTheLargerBoxesAreCancelledOnceTheAnswerIsKnown() async throws {
        let start = Date()
        let got = try await WaterLevelService.firstAcrossRadii([0.25, 2.5], fetch: { r in
            if r == 2.5 { try await Task.sleep(nanoseconds: 5_000_000_000) }
            return [Self.reading(r == 0.25 ? "small" : "big")]
        }, decide: found)
        XCTAssertEqual(got?.siteCode, "small")
        XCTAssertLessThan(Date().timeIntervalSince(start), 2, "the slow 2.5° box must be cancelled, not awaited")
    }

    // MARK: F4: the cache

    func testFreshForFifteenMinutesIncludingAnEmptyAnswer() async {
        let c = USGSReadingCache(), t = Date(timeIntervalSince1970: 1_000_000)
        await c.put("k", [], now: t)
        let empty = await c.fresh("k", now: t.addingTimeInterval(14 * 60))
        XCTAssertEqual(empty, [])
        let expired = await c.fresh("k", now: t.addingTimeInterval(16 * 60))
        XCTAssertNil(expired)
    }

    func testLastGoodIsTheLatestNonEmptyAnswerForSixHours() async {
        let c = USGSReadingCache(), t = Date(timeIntervalSince1970: 1_000_000)
        await c.put("k", [Self.reading("a")], now: t)
        await c.put("k", [], now: t.addingTimeInterval(60))           // a later empty answer does not erase the last good one
        let lg = await c.lastGood("k", now: t.addingTimeInterval(5 * 3600))
        XCTAssertEqual(lg?.first?.siteCode, "a")
        let gone = await c.lastGood("k", now: t.addingTimeInterval(7 * 3600))
        XCTAssertNil(gone)
    }

    func testTheCacheIsCapped() async {
        let c = USGSReadingCache(), t = Date(timeIntervalSince1970: 1_000_000)
        for i in 0..<(USGSReadingCache.maxEntries + 5) { await c.put("k\(i)", [], now: t.addingTimeInterval(Double(i))) }
        let n = await c.count
        XCTAssertEqual(n, USGSReadingCache.maxEntries)
        let oldest = await c.fresh("k0", now: t.addingTimeInterval(10))
        XCTAssertNil(oldest, "the oldest entries go first")
    }
}
