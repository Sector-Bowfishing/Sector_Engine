//
//  SingleFlightCacheTests.swift
//  SectorEngineTests
//
//  The adapters' shared caches (TVA, SWPA, APC, CWMS, NOAA tides) all go
//  through SingleFlightCache. These pin the three properties the 2026-09-14
//  hardening relies on: concurrent callers share one fetch, values expire, and
//  failures are remembered only when asked.
//

import XCTest
@testable import SectorEngine

private actor Counter {
    private(set) var count = 0
    func bump() { count += 1 }
}

final class SingleFlightCacheTests: XCTestCase {

    func testConcurrentCallersShareOneComputation() async {
        let cache = SingleFlightCache<String, Int>(ttl: 60)
        let calls = Counter()

        let results = await withTaskGroup(of: Int?.self, returning: [Int?].self) { group in
            for _ in 0..<50 {
                group.addTask {
                    await cache.value(for: "k") {
                        await calls.bump()
                        try? await Task.sleep(nanoseconds: 100_000_000)   // a slow upstream
                        return 42
                    }
                }
            }
            var out: [Int?] = []
            for await r in group { out.append(r) }
            return out
        }

        XCTAssertEqual(results.count, 50)
        XCTAssertTrue(results.allSatisfy { $0 == 42 })
        let n = await calls.count
        XCTAssertEqual(n, 1, "a burst of callers for one key must trigger exactly one fetch")
    }

    func testFreshValueIsReusedAndExpiredValueIsRefetched() async throws {
        let cache = SingleFlightCache<String, Int>(ttl: 0.2)
        let calls = Counter()
        let compute: @Sendable () async -> Int? = { await calls.bump(); return await calls.count }

        let first = await cache.value(for: "k", compute: compute)
        let second = await cache.value(for: "k", compute: compute)
        XCTAssertEqual(first, 1)
        XCTAssertEqual(second, 1, "within ttl the cached value is served")

        try await Task.sleep(nanoseconds: 300_000_000)
        let third = await cache.value(for: "k", compute: compute)
        XCTAssertEqual(third, 2, "after ttl the value is recomputed")
    }

    func testNilIsNotCachedWithoutFailureTTL() async {
        let cache = SingleFlightCache<String, Int>(ttl: 60, failureTTL: 0)
        let calls = Counter()
        _ = await cache.value(for: "k") { await calls.bump(); return nil }
        _ = await cache.value(for: "k") { await calls.bump(); return nil }
        let n = await calls.count
        XCTAssertEqual(n, 2, "with failureTTL 0 every call retries a failed fetch")
    }

    func testNilIsRememberedForFailureTTL() async throws {
        let cache = SingleFlightCache<String, Int>(ttl: 60, failureTTL: 0.2)
        let calls = Counter()
        let failing: @Sendable () async -> Int? = { await calls.bump(); return nil }

        _ = await cache.value(for: "k", compute: failing)
        _ = await cache.value(for: "k", compute: failing)
        var n = await calls.count
        XCTAssertEqual(n, 1, "a failure is remembered so a dead upstream isn't hammered")

        try await Task.sleep(nanoseconds: 300_000_000)
        _ = await cache.value(for: "k", compute: failing)
        n = await calls.count
        XCTAssertEqual(n, 2, "after failureTTL the fetch is retried")
    }

    func testDistinctKeysComputeIndependently() async {
        let cache = SingleFlightCache<String, String>(ttl: 60)
        let a = await cache.value(for: "a") { "A" }
        let b = await cache.value(for: "b") { "B" }
        XCTAssertEqual(a, "A")
        XCTAssertEqual(b, "B")
    }

    func testFailedRefetchServesLastGoodValueAndBacksOff() async throws {
        // ttl 0.2s, failures remembered 5s, stale values served up to 60s.
        let cache = SingleFlightCache<String, Int>(ttl: 0.2, failureTTL: 5, staleOnErrorTTL: 60)
        let calls = Counter()
        let good = await cache.value(for: "k") { await calls.bump(); return 7 }
        XCTAssertEqual(good, 7)

        try await Task.sleep(nanoseconds: 300_000_000)                 // past ttl
        let afterOutage = await cache.value(for: "k") { await calls.bump(); return nil }
        XCTAssertEqual(afterOutage, 7, "an upstream outage costs freshness, not data")

        let again = await cache.value(for: "k") { await calls.bump(); return nil }
        XCTAssertEqual(again, 7)
        let n = await calls.count
        XCTAssertEqual(n, 2, "within failureTTL the stale value is served without re-hitting the failing upstream")
    }

    func testForcedRefreshThatFailsKeepsTheGoodValue() async {
        let cache = SingleFlightCache<String, Int>(ttl: 60, failureTTL: 5)
        _ = await cache.value(for: "k") { 9 }
        let forced = await cache.value(for: "k", force: true) { nil }
        XCTAssertEqual(forced, 9, "a pull-to-refresh during a blip doesn't evict a good entry")
        let later = await cache.value(for: "k") { 1 }
        XCTAssertEqual(later, 9, "…for anyone else either")
    }

    func testEntriesAreBounded() async {
        let cache = SingleFlightCache<Int, Int>(ttl: 60, maxEntries: 10)
        let calls = Counter()
        for i in 0..<50 {
            _ = await cache.value(for: i) { await calls.bump(); return i }
        }
        // The oldest keys were evicted, so asking for key 0 again recomputes.
        _ = await cache.value(for: 0) { await calls.bump(); return 0 }
        let n = await calls.count
        XCTAssertEqual(n, 51)
    }
}
