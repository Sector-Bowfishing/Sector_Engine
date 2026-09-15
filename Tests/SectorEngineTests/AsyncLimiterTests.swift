//
//  AsyncLimiterTests.swift
//  SectorEngineTests
//
//  The limiter in front of USGS must never admit more than its limit, must hand
//  slots on as work finishes, and must let a cancelled waiter (a withDeadline
//  that gave up) leave the queue without leaking a slot.
//

import XCTest
@testable import SectorEngine

private actor Gauge {
    private(set) var current = 0
    private(set) var peak = 0
    func enter() { current += 1; peak = max(peak, current) }
    func leave() { current -= 1 }
}

final class AsyncLimiterTests: XCTestCase {

    func testNeverRunsMoreThanTheLimit() async throws {
        let limiter = AsyncLimiter(limit: 3)
        let gauge = Gauge()
        try await withThrowingTaskGroup(of: Void.self) { group in
            for _ in 0..<20 {
                group.addTask {
                    try await withLimit(limiter) {
                        await gauge.enter()
                        try await Task.sleep(nanoseconds: 20_000_000)
                        await gauge.leave()
                    }
                }
            }
            try await group.waitForAll()
        }
        let peak = await gauge.peak
        XCTAssertLessThanOrEqual(peak, 3)
        XCTAssertGreaterThan(peak, 1, "work should actually run concurrently up to the limit")
    }

    func testCancelledWaiterLeavesTheQueue() async throws {
        let limiter = AsyncLimiter(limit: 1)
        let held = await limiter.acquire()                            // hold the only slot
        XCTAssertTrue(held)

        let waiter = Task { await limiter.acquire() }
        try await Task.sleep(nanoseconds: 50_000_000)                 // let it queue
        waiter.cancel()
        let admitted = await waiter.value
        XCTAssertFalse(admitted, "a cancelled waiter is not admitted")

        await limiter.release()                                       // slot must be free again
        let next = Task { await limiter.acquire() }
        let got = await next.value
        XCTAssertTrue(got, "cancellation didn't leak the slot")
    }
}
